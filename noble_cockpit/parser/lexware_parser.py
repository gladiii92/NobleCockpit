"""
lexware_parser.py
NobleCockpit BWA-Parser mit Multi-Format-Unterstuetzung (Lexware + SMD).

Pipeline:
1. extract_raw_table() + extract_header_text()
       - Tabellenstruktur ueber pdfplumber (fuer Datenzeilen, robust genug
         dort weil Zahlen/Bezeichnung klar trennbar sind)
       - Header-Text ueber page.extract_text() (fuer Periodenerkennung,
         WEIL extract_table() Jahreszahlen und Woerter an Spaltengrenzen
         zerreisst - z.B. '2023' -> '202' + '3' - und das Periodenmuster
         dadurch nicht mehr matcht)
       - Header wird gezielt ab der Zeile extrahiert, die mit
         'Bezeichnung' beginnt, NICHT ab Zeile 0 der Seite - sonst
         matcht das Periodenmuster faelschlich bereits im Dokumenttitel
         (z.B. '... | 4. Quartal 2023') und erzeugt eine Phantom-Periode
2. clean_row()               - trennt Bezeichnung von Zahlenwerten pro Zeile
3. match_orphaned_rows()     - verbindet Werte-Zeilen mit versetzt liegenden Bezeichnungen
4. filter_by_mode_columns()  - entfernt Kopf-/Fusszeilen strukturell (falsche Spaltenanzahl)
5. map_to_canonical()        - uebersetzt Format-spezifische Bezeichnungen auf ein Schema
6. assign_periods_to_values()- ordnet jeder Zahl ein typisiertes Period-Objekt zu,
                                UEBERSPRINGT dabei DIFF-Spalten (z.B. 'Differenz',
                                'Veraenderung in %'), die im Header zwar als Spalte
                                existieren, aber keine eigene Zeitperiode repraesentieren

Design-Prinzip: Formatspezifika bleiben in dieser Datei gekapselt (Mapping-Tabelle).
Nachgelagerte Module (Kennzahlen, Regel-Engine) sehen nur BWAPosition-Objekte
mit typisierten Period-Keys statt roher Listen-Positionen.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from periods import Period, ColumnToken, KUM_LABEL_PATTERN, parse_periods

TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 4,
}

# ---------------------------------------------------------------------------
# Kanonisches Zielschema
# ---------------------------------------------------------------------------

@dataclass
class BWAPosition:
    bezeichnung_original: str
    kanonischer_key: str
    werte: dict[Period, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Bezeichnungs-Mapping (waechst additiv bei neuer Buchhaltungssoftware)
# ---------------------------------------------------------------------------

BEZEICHNUNG_MAPPING: dict[str, str] = {
    "erlöse aus betrieblicher tätigkeit": "erloese_betrieblich",
    "umsatzerlöse": "erloese_betrieblich",
    "sonstige erlöse": "sonstige_ertraege",
    "sonstige betriebliche erträge": "sonstige_ertraege",
    "summe der erlöse": "summe_erloese",
    "umsatzsteuer": "umsatzsteuer",
    "umsatzsteuer-erstattung": "umsatzsteuer_erstattung",
    "erhaltene anzahlungen": "erhaltene_anzahlungen",
    "abzüglich forderungsveränderungen": "forderungsveraenderung",
    "summe der betriebseinnahmen": "summe_betriebseinnahmen",
    "summe betriebseinnahme": "summe_betriebseinnahmen",
    "waren, material und stoffe": "wareneinkauf",
    "fremdleistungen": "fremdleistungen",
    "summe wareneinkauf": "summe_wareneinkauf",
    "rohertrag": "summe_rohertrag",
    "betrieblicher rohertrag": "rohertrag_betrieblich",
    "aufschlagsermittlung in %": "aufschlag_prozent",
    "personalkosten": "personalkosten",
    "raumkosten": "raumkosten",
    "steuern, versicherungen und beiträge": "steuern_versicherungen",
    "steuern/versicherung/beitr": "steuern_versicherungen",
    "fahrzeugkosten": "fahrzeugkosten",
    "werbe- und reisekosten": "werbe_reisekosten",
    "kosten warenabgabe": "kosten_warenabgabe",
    "instandhaltung und werkzeuge": "instandhaltung",
    "abschreibungen": "abschreibungen",
    "verschiedene kosten": "verschiedene_kosten",
    "summe der kosten": "summe_kosten",
    "summe kosten": "summe_kosten",
    "porto/telefon": "porto_telefon",
    "bürobedarf": "buerobedarf",
    "vorsteuer": "vorsteuer",
    "vorsteuer- ust-zahlungen": "vorsteuer_ust_zahlung_einnahmen",
    "vorsteuer- / ust-zahlungen": "vorsteuer_ust_zahlung_ausgaben",
    "umsatzsteuer-zahlung": "umsatzsteuer_zahlung",
    "rechts- beratungskosten": "rechts_beratungskosten",
    "sonstige betriebliche aufwe": "sonstige_aufwendungen",
    "sonstige aufwendungen": "sonstige_aufwendungen",
    "buchwert anlagenabgänge": "buchwert_anlagenabgaenge",
    "abzüglich verbindlichkeitsveränderungen": "verbindlichkeitsveraenderung",
    "summe der betriebsausgaben": "summe_betriebsausgaben",
    "summe betriebsausgaben": "summe_betriebsausgaben",
    "vorläufiges betriebliches ergebnis": "vorlaeufiges_ergebnis",
    "unternehmensergebn": "vorlaeufiges_ergebnis",
}


def parse_german_number(text: str) -> float:
    """Wandelt '17.311,15' oder '-6.639,52' in float um."""
    cleaned = text.strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def parse_cell(cell: str) -> float | None:
    """Parst eine einzelne Tabellenzelle. Gibt None fuer Nicht-Zahlen zurueck."""
    cell = cell.strip()
    if not cell or cell == "€":
        return None
    cell_clean = cell.rstrip("%").replace("€", "").strip()
    if not cell_clean:
        return None
    try:
        return parse_german_number(cell_clean)
    except ValueError:
        return None


def clean_row(row: list[str | None]) -> tuple[str, list[float]] | None:
    """
    Trennt eine Rohzeile in (Bezeichnung, Zahlenwerte).
    Verwirft reine Leerzeilen. Behaelt Zeilen mit NUR Bezeichnung
    oder NUR Zahlen (relevant fuer match_orphaned_rows).

    Bugfix-Historie: Frueher wurden Veraenderungs-Prozentwerte
    ('65,53 %') hier semantisch herausgefiltert (is_percent_value()),
    weil sie keine eigene Periode tragen. Das brach bei SMD, weil
    dort die DIFF-Spalte KEINE Prozentzahl, sondern ein absoluter
    Euro-Betrag ist ('-647,27') - numerisch nicht von einem echten
    Messwert unterscheidbar. Jetzt werden ALLE Zahlenwerte behalten
    (inkl. DIFF-Spalten, egal ob Prozent oder absolut). Die Trennung
    PERIOD- vs. DIFF-Spalte erfolgt danach ausschliesslich positional
    in assign_periods_to_values(), nicht mehr anhand des Zellinhalts.
    """
    cells = [c for c in row if c and c.strip()]
    if not cells:
        return None

    bezeichnung = ""
    werte: list[float] = []

    for cell in cells:
        value = parse_cell(cell)
        if value is not None:
            werte.append(value)
        elif not bezeichnung:
            bezeichnung = cell.strip()

    if not bezeichnung and not werte:
        return None
    return bezeichnung, werte


def match_orphaned_rows(
    rows: list[tuple[str, list[float]]]
) -> list[tuple[str, list[float]]]:
    """
    Verbindet Zeilen, bei denen Werte und Bezeichnung auf getrennten
    Zeilen liegen (SMD-Formatfehler, z.B. ROHERTRAG-Sektion).
    Regel: erste verwaiste Werte-Zeile -> erste nachfolgende
    verwaiste Bezeichnung-Zeile, in Auftrittsreihenfolge.
    Laeuft generisch ueber das gesamte Dokument, nicht nur an
    einer erwarteten Stelle - robuster gegen unbekannte Faelle.
    """
    result: list[tuple[str, list[float]]] = []
    pending_values: list[list[float]] = []

    for bezeichnung, werte in rows:
        if not bezeichnung and werte:
            pending_values.append(werte)
        elif bezeichnung and not werte and pending_values:
            result.append((bezeichnung, pending_values.pop(0)))
        elif bezeichnung and werte:
            result.append((bezeichnung, werte))
        elif bezeichnung and not werte:
            result.append((bezeichnung, werte))

    return result


def filter_by_mode_columns(
    rows: list[tuple[str, list[float]]], min_rows_for_mode: int = 10
) -> list[tuple[str, list[float]]]:
    """
    Verwirft Zeilen, deren Spaltenanzahl von der haeufigsten (Mode)
    abweicht. Filtert damit Kopf-/Fusszeilen strukturell, ohne
    Blacklists mit Textmustern.
    """
    non_empty = [(b, w) for b, w in rows if w]
    if len(non_empty) < min_rows_for_mode:
        return non_empty  # zu wenig Daten, um Mode sinnvoll zu bestimmen

    counts = Counter(len(w) for _, w in non_empty)
    mode_len = counts.most_common(1)[0][0]

    return [(b, w) for b, w in non_empty if len(w) == mode_len]


def normalize_bezeichnung(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def map_to_canonical(
    rows: list[tuple[str, list[float]]]
) -> list[tuple[str, str, list[float]]]:
    """Gibt (bezeichnung_original, kanonischer_key, werte) zurueck."""
    result = []
    for bezeichnung, werte in rows:
        key = BEZEICHNUNG_MAPPING.get(
            normalize_bezeichnung(bezeichnung), "UNBEKANNT"
        )
        result.append((bezeichnung, key, werte))
    return result


def extract_raw_table(pdf_path: Path) -> list[list[str | None]]:
    """Extrahiert die Rohtabelle aus allen Seiten eines BWA-PDFs."""
    all_rows: list[list[str | None]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table(table_settings=TABLE_SETTINGS)
            if table:
                all_rows.extend(table)
    return all_rows


def extract_header_text(pdf_path: Path, initial_window: int = 8, max_window: int = 30) -> str:
    """
    Liest den Header-Bereich aus dem VOLLEN Seiten-Fliesstext
    (page.extract_text()), NICHT aus der Tabellenstruktur.

    Grund 1: extract_table() zerreisst Woerter/Jahreszahlen an
    Spaltengrenzen (z.B. '2023' -> '202' + '3'), wodurch das
    Periodenmuster nicht mehr erkennbar ist. extract_text() liefert
    den Fliesstext unzerbrochen, wie ihn ein Mensch lesen wuerde.

    Grund 2: Der Dokumenttitel (z.B. '... | 4. Quartal 2023') enthaelt
    haeufig SELBST ein Quartals- oder Monatsmuster und wuerde bei
    naiver Verwendung der ersten N Zeilen eine Phantom-Periode
    erzeugen. Deshalb wird gezielt erst ab der Zeile geparst, die mit
    'Bezeichnung' beginnt.

    Grund 3 (Bugfix Lookback): Bei SMD steht das Signal-Muster
    'Kum. bis Dez Kum. bis Dez' in der Zeile UNMITTELBAR VOR
    'Bezeichnung', nicht danach (siehe echter PDF-Dump: Zeile 5
    'Kum. bis Dez Kum. bis Dez', Zeile 6 'Bezeichnung ...'). Ohne
    diese Zeile im Header-Text kann periods.py den SMD-Sonderfall
    nicht erkennen und faellt lautlos auf das falsche, positionsbasierte
    Verfahren zurueck. Deshalb wird eine Zeile VOR 'Bezeichnung' mit
    eingeschlossen (lookback_start).

    Grund 4 (Bugfix dynamisches Fenster): Bei SMD ist 'Kum. bis Dez\\n2025'
    teils feingranularer umgebrochen als angenommen. Das Fenster wird
    deshalb dynamisch erweitert: Es wird so lange um jeweils 4 Zeilen
    vergroessert, bis ein zusaetzlicher Parse-Versuch KEINE neuen
    Perioden-Tokens mehr findet - dann ist der Header sicher vollstaendig
    erfasst.
    """
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text() or ""

    lines = first_page_text.split("\n")
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("bezeichnung"):
            start_idx = i
            break

    if start_idx is None:
        raise ValueError(
            "Keine Zeile beginnend mit 'Bezeichnung' im PDF-Text gefunden - "
            "vermutlich ein neues, noch unbekanntes BWA-Format."
        )

    # Bugfix: Der Lookback darf NICHT unconditional erfolgen. Bei MTL/WA
    # steht in der Zeile VOR 'Bezeichnung' der Dokumenttitel (z.B.
    # 'Jahresuebersicht | 4. Quartal 2023'), der selbst ein Quartalsmuster
    # enthaelt und sonst als Phantom-Periode mitgezaehlt wird. Der Lookback
    # wird deshalb an ein strukturelles Signal gekoppelt: nur wenn die
    # Vorzeile tatsaechlich das fragmentierte SMD-Signal
    # ('Kum. bis <Monat>' OHNE Jahreszahl) enthaelt, wird sie einbezogen.
    lookback_start = start_idx
    if start_idx > 0 and KUM_LABEL_PATTERN.search(lines[start_idx - 1]):
        lookback_start = start_idx - 1

    window = initial_window
    previous_token_count = -1

    while window <= max_window:
        header_candidate = "\n".join(lines[lookback_start:start_idx + window])
        try:
            tokens = parse_periods(header_candidate)
            token_count = len(tokens)
        except ValueError:
            token_count = 0

        if token_count == previous_token_count and token_count > 0:
            return header_candidate

        previous_token_count = token_count
        window += 4

    return "\n".join(lines[lookback_start:start_idx + window])


def assign_periods_to_values(
    rows: list[tuple[str, str, list[float]]], tokens: list[ColumnToken]
) -> list[BWAPosition]:
    """
    Verknuepft Werte-Listen mit den extrahierten ColumnTokens.

    WICHTIG (Architektur-Fix): Fruehere Version ging davon aus, dass
    'werte' NUR echte PERIOD-Werte enthaelt (DIFF-Werte wurden bereits
    in clean_row() semantisch herausgefiltert). Das brach bei SMD, weil
    die DIFF-Spalte dort ein absoluter Euro-Betrag ist und nicht von
    einem echten Messwert unterscheidbar war. Jetzt enthaelt 'werte'
    JEDE Zahl der Zeile (inkl. DIFF-Spalten), und die Zuordnung zu
    PERIOD- vs. DIFF-Spalte erfolgt ausschliesslich ueber die Position
    im Spaltenraster (tokens), analog zur Datenzeile: Index i in 'werte'
    entspricht Index i in 'tokens'. Nur an PERIOD-Token-Positionen wird
    ein Wert uebernommen, DIFF-Positionen werden strukturell uebersprungen.

    Wirft explizit einen ValueError, wenn die Gesamtanzahl der Werte
    nicht zur Gesamtanzahl der Spalten-Tokens passt - lieber laut
    scheitern als stillschweigend falsche Zuordnung riskieren.
    """
    result = []
    for bezeichnung, key, werte in rows:
        if len(werte) != len(tokens):
            period_count = sum(1 for t in tokens if t.kind == "PERIOD")
            diff_count = len(tokens) - period_count
            raise ValueError(
                f"Spaltenanzahl-Mismatch bei '{bezeichnung}': "
                f"{len(werte)} Werte vs. {len(tokens)} Spalten-Tokens "
                f"insgesamt ({period_count} PERIOD, {diff_count} DIFF). "
                f"Vermutlich ein neues, noch unbekanntes Spaltenformat."
            )
        werte_dict = {
            tok.period: v
            for tok, v in zip(tokens, werte)
            if tok.kind == "PERIOD"
        }
        result.append(
            BWAPosition(
                bezeichnung_original=bezeichnung,
                kanonischer_key=key,
                werte=werte_dict,
            )
        )
    return result


def check_unique_keys(positionen: list[BWAPosition]) -> None:
    """
    Verhindert stillen Datenverlust durch zu grobes BEZEICHNUNG_MAPPING.

    Kontext: 'Vorsteuer- USt-Zahlungen' (Betriebseinnahmen-Sektion) und
    'Vorsteuer- / USt-Zahlungen' (Betriebsausgaben-Sektion) sind bei SMD
    ZWEI unterschiedliche BWA-Positionen mit unterschiedlichen Werten,
    wurden aber beide auf denselben kanonischen Key gemappt. Das erzeugt
    KEINEN Parser-Fehler (Spaltenanzahl stimmt ja), sondern nur einen
    stillen Verlust, sobald eine nachgelagerte Stelle (Rule-Engine,
    Report) die Liste zu einem dict[key, ...] reduziert - dann
    ueberschreibt die zweite Zeile lautlos die erste.

    Deshalb: sobald zwei UNTERSCHIEDLICHE Original-Bezeichnungen auf
    denselben kanonischen Key abbilden, wird hart abgebrochen - lieber
    beim Parsen der Testdaten auffallen als spaeter beim Kunden im
    Report fehlende Zahlen zu haben.

    'UNBEKANNT' ist bewusst ausgenommen, weil dort mehrere echte
    Positionen legitim denselben (fehlenden) Key teilen, ohne dass eine
    inhaltliche Kollision vorliegt - diese Zeilen werden ohnehin separat
    als Warnung markiert (siehe __main__-Block).
    """
    seen: dict[str, str] = {}
    for pos in positionen:
        if pos.kanonischer_key == "UNBEKANNT":
            continue
        vorherige_bezeichnung = seen.get(pos.kanonischer_key)
        if vorherige_bezeichnung is not None and vorherige_bezeichnung != pos.bezeichnung_original:
            raise ValueError(
                f"Kollidierender kanonischer Key '{pos.kanonischer_key}': "
                f"'{vorherige_bezeichnung}' UND '{pos.bezeichnung_original}' "
                f"mappen auf denselben Key, sind aber unterschiedliche "
                f"BWA-Positionen. BEZEICHNUNG_MAPPING ist zu grob - "
                f"pruefe, ob beide Bezeichnungen einen eigenen, "
                f"eindeutigen Key benoetigen."
            )
        seen[pos.kanonischer_key] = pos.bezeichnung_original


def parse_bwa_pdf(pdf_path: Path) -> list[BWAPosition]:
    """Vollstaendige Pipeline: PDF -> Liste kanonischer BWAPosition-Objekte."""
    raw_table = extract_raw_table(pdf_path)
    header_text = extract_header_text(pdf_path)
    tokens = parse_periods(header_text)

    cleaned = [clean_row(r) for r in raw_table]
    cleaned = [c for c in cleaned if c is not None]

    matched = match_orphaned_rows(cleaned)
    filtered = filter_by_mode_columns(matched)
    mapped = map_to_canonical(filtered)

    positionen = assign_periods_to_values(mapped, tokens)
    check_unique_keys(positionen)
    return positionen


if __name__ == "__main__":
    BWA_DIR = Path("data/bwa_samples")
    pdf_files = sorted(BWA_DIR.glob("*.pdf"))

    for pdf_path in pdf_files:
        print(f"\n{'=' * 80}\nDATEI: {pdf_path.name}\n{'=' * 80}")
        try:
            positionen = parse_bwa_pdf(pdf_path)
        except ValueError as e:
            print(f"FEHLER: {e}")
            continue

        for pos in positionen:
            marker = " ⚠️ UNBEKANNT" if pos.kanonischer_key == "UNBEKANNT" else ""
            werte_str = ", ".join(f"{p.label}={v}" for p, v in pos.werte.items())
            print(f"{pos.kanonischer_key:35s} | {pos.bezeichnung_original:45s} | {werte_str}{marker}")