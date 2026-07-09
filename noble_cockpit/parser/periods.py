"""
periods.py — Periodensystem fuer BWA-Dokumente unterschiedlicher Software.

Loest drei Probleme:
1. Positionsbasierte Werte-Listen sind mehrdeutig, weil dieselbe
   Spaltenanzahl bei unterschiedlichen Formaten unterschiedliche
   Zeitsemantik hat (Quartalsreihe vs. Vorjahresvergleich vs. Monat+Kumulativ).
2. Manche Formate (z.B. SMD) enthalten zusaetzliche Nicht-Werte-Spalten
   ('Differenz'), die weder eine Zahl noch eine Periode tragen, aber
   trotzdem eine Position im Spaltenraster belegen. Diese muessen bei
   der Werte-Zuordnung explizit uebersprungen werden (ColumnToken.kind
   == 'DIFF'), sonst verschieben sich alle nachfolgenden Perioden.
3. Bei SMD zerreisst pdfplumber die Kopfzeile so inkonsistent, dass die
   'Kum. bis <Monat>'-Labels VOR der Bezeichnungszeile stehen, ihre
   zugehoerigen Jahreszahlen aber DANACH. Die textuelle Lesereihenfolge
   entspricht dort NICHT der tatsaechlichen Spaltenreihenfolge in den
   Datenzeilen - deshalb braucht dieses Layout eine eigene
   Rekonstruktionslogik statt reiner Positionssortierung.

Teil des NobleCockpit BWA-Parsers (noble_cockpit/parser/).
"""

import re
from dataclasses import dataclass
from enum import Enum


class PeriodKind(str, Enum):
    QUARTER = "quarter"                    # z.B. 1. Quartal 2023
    QUARTER_RANGE = "quarter_range"        # z.B. 1.-4. Quartal 2023 (Jahressumme)
    MONTH = "month"                        # z.B. Dez 2025
    MONTH_CUMULATIVE = "month_cumulative"  # z.B. Kum. bis Dez 2025 (Jahressumme)


@dataclass(frozen=True)
class Period:
    """
    Unveraenderliches, hashbares Periodenobjekt.
    frozen=True erlaubt Verwendung als dict-Key.
    """
    kind: PeriodKind
    year: int
    start: int
    end: int

    @property
    def label(self) -> str:
        if self.kind == PeriodKind.QUARTER:
            return f"Q{self.start}_{self.year}"
        if self.kind == PeriodKind.QUARTER_RANGE:
            return f"Q{self.start}-Q{self.end}_{self.year}"
        if self.kind == PeriodKind.MONTH:
            return f"M{self.start:02d}_{self.year}"
        if self.kind == PeriodKind.MONTH_CUMULATIVE:
            return f"KUM_M{self.start:02d}_{self.year}"
        raise ValueError(f"Unbekannter PeriodKind: {self.kind}")

    @property
    def is_aggregate(self) -> bool:
        """True fuer Jahressummen/Kumulativwerte (keine Einzelperiode)."""
        return self.kind in (PeriodKind.QUARTER_RANGE, PeriodKind.MONTH_CUMULATIVE)


@dataclass(frozen=True)
class ColumnToken:
    """
    Repraesentiert EINE Spalte im Header, in der tatsaechlichen
    Spaltenreihenfolge der Datenzeilen (NICHT notwendigerweise in der
    Zeichenreihenfolge des rohen Header-Textes - siehe SMD-Sonderfall).

    kind == 'DIFF' markiert Spalten, die keine eigene Zahlen-Periode
    tragen (z.B. 'Veraenderung', 'Differenz'), aber trotzdem eine
    Position im Spaltenraster belegen und daher beim Zuordnen von
    Werten zu Perioden UEBERSPRUNGEN werden muessen.
    """
    position: int          # Zeichenposition im Header-Text (nur fuer Sortierung im Positional-Fallback relevant)
    kind: str               # "PERIOD" oder "DIFF"
    period: Period | None   # gesetzt wenn kind == "PERIOD", sonst None


MONTH_MAP = {
    "jan": 1, "feb": 2, "mae": 3, "apr": 4, "mai": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}

QUARTER_PATTERN = re.compile(r"(\d)\.\s*(?:-\s*(\d)\.)?\s*Quartal\s*(\d{4})", re.IGNORECASE)
MONTH_PATTERN = re.compile(
    r"\b(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\.?\s*(\d{4})\b",
    re.IGNORECASE | re.DOTALL,
)
KUM_PATTERN = re.compile(
    r"Kum\.?\s*bis\s*(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\.?\s*(\d{4})",
    re.IGNORECASE | re.DOTALL,
)
# 'Kum. bis <Monat>' OHNE nachfolgende Jahreszahl - Signal fuer das
# fragmentierte SMD-Layout, bei dem die Jahreszahlen separat stehen.
KUM_LABEL_PATTERN = re.compile(
    r"Kum\.?\s*bis\s*(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\b(?!\.?\s*\d{4})",
    re.IGNORECASE,
)
STANDALONE_YEAR_PATTERN = re.compile(r"\b(\d{4})\b")
# Bugfix: Wortgrenzen (\b) sind zwingend notwendig. Ohne sie matcht
# "Ver[aä]nderung" faelschlich auch als Teilstring in ganz normalen
# Bezeichnungen wie "Forderungsveraenderungen" oder
# "Verbindlichkeitsveraenderungen", die in der Datenzeile (nicht im
# Spalten-Header!) vorkommen und Teil des Header-Fensters werden
# (dynamisches Fenster in extract_header_text() liest mehrere Zeilen).
# Das erzeugte bei WA eine Phantom-DIFF-Spalte zu viel.
DIFF_PATTERN = re.compile(r"\bVer[aä]nderung(?:\s*\n?\s*in\s*%)?\b|\bDifferenz\b", re.IGNORECASE | re.DOTALL)


def _month_num(month_str: str) -> int:
    key = month_str.lower().replace("ä", "ae")[:3]
    return MONTH_MAP[key]


def _build_column_tokens_positional(header_text: str) -> list[ColumnToken]:
    """
    Urspruengliches, positionsbasiertes Verfahren: sortiert alle
    gefundenen Perioden- und DIFF-Muster einfach nach ihrer
    Zeichenposition im Header-Text.

    Funktioniert zuverlaessig fuer MTL und WA, weil dort die Kopfzeile
    von pdfplumber nicht fragmentiert wird und die Textreihenfolge der
    tatsaechlichen Spaltenreihenfolge entspricht. Wird als Fallback
    verwendet, wenn KEIN 'Kum. bis <Monat>'-ohne-Jahr-Muster gefunden
    wird (das waere das SMD-Sonderfall-Signal).
    """
    raw_tokens: list[tuple[int, ColumnToken]] = []

    for m in QUARTER_PATTERN.finditer(header_text):
        start, end, year = m.groups()
        start, year = int(start), int(year)
        if end:
            period = Period(PeriodKind.QUARTER_RANGE, year, start, int(end))
        else:
            period = Period(PeriodKind.QUARTER, year, start, start)
        raw_tokens.append((m.start(), ColumnToken(m.start(), "PERIOD", period)))

    kum_matches = list(KUM_PATTERN.finditer(header_text))
    for m in kum_matches:
        month_str, year = m.groups()
        month_num = _month_num(month_str)
        period = Period(PeriodKind.MONTH_CUMULATIVE, int(year), month_num, month_num)
        raw_tokens.append((m.start(), ColumnToken(m.start(), "PERIOD", period)))

    for m in MONTH_PATTERN.finditer(header_text):
        is_inside_kum = any(km.start() <= m.start() < km.end() for km in kum_matches)
        if is_inside_kum:
            continue
        month_str, year = m.groups()
        month_num = _month_num(month_str)
        period = Period(PeriodKind.MONTH, int(year), month_num, month_num)
        raw_tokens.append((m.start(), ColumnToken(m.start(), "PERIOD", period)))

    for m in DIFF_PATTERN.finditer(header_text):
        raw_tokens.append((m.start(), ColumnToken(m.start(), "DIFF", None)))

    raw_tokens.sort(key=lambda t: t[0])
    return [tok for _, tok in raw_tokens]


def _build_column_tokens_smd(header_text: str, kum_label_matches: list) -> list[ColumnToken]:
    """
    Rekonstruiert die Spaltenreihenfolge fuer das fragmentierte
    SMD-Layout aus dem bekannten, fixen Spaltenschema dieses
    Berichtstyps: [Monat aktuell, Monat Vorjahr, Diff,
    Kum aktuell, Kum Vorjahr, Diff].

    Vorgehen:
    1. Alle 'Monat Jahr'-Treffer, die NICHT Teil eines vollstaendigen
       'Kum. bis <Monat> <Jahr>'-Ausdrucks sind, liefern die beiden
       Monatsspalten (in Textreihenfolge - hier ist die Reihenfolge
       im echten Layout korrekt, weil sie in derselben Zeile wie
       'Bezeichnung' stehen).
    2. Alle alleinstehenden 4-stelligen Jahreszahlen, die keiner
       Monatsspalte zugeordnet sind, liefern die Jahre der
       Kumulativspalten - in ihrer Auftrittsreihenfolge im Text
       (bei SMD stehen sie in einer eigenen Zeile NACH der
       Bezeichnungszeile, aber weiterhin in der richtigen
       gegenseitigen Reihenfolge: aktuelles Jahr vor Vorjahr).
    3. Der gemeinsame Monatsname aus den KUM_LABEL_PATTERN-Treffern
       wird auf alle rekonstruierten Kumulativspalten angewendet.
    4. Die Anzahl der 'Differenz'-Vorkommen wird gleichmaessig auf
       'nach dem Monatspaar' und 'nach dem Kumulativpaar' verteilt
       (Standard-BWA-Muster: ein Diff pro Aktuell/Vorjahr-Paar).
    """
    kum_full_spans = [(m.start(), m.end()) for m in KUM_PATTERN.finditer(header_text)]

    month_only_matches = [
        m for m in MONTH_PATTERN.finditer(header_text)
        if not any(s <= m.start() < e for s, e in kum_full_spans)
    ]
    month_tokens = []
    for m in month_only_matches:
        month_str, year = m.groups()
        month_num = _month_num(month_str)
        period = Period(PeriodKind.MONTH, int(year), month_num, month_num)
        month_tokens.append(ColumnToken(m.start(), "PERIOD", period))

    excluded_spans = [(m.start(), m.end()) for m in month_only_matches] + kum_full_spans
    standalone_year_matches = [
        m for m in STANDALONE_YEAR_PATTERN.finditer(header_text)
        if not any(s <= m.start() < e for s, e in excluded_spans)
    ]

    kum_month_str = kum_label_matches[0].group(1)
    kum_month_num = _month_num(kum_month_str)

    kum_tokens = []
    for year_match in standalone_year_matches[: len(kum_label_matches)]:
        year = int(year_match.group(1))
        period = Period(PeriodKind.MONTH_CUMULATIVE, year, kum_month_num, kum_month_num)
        kum_tokens.append(ColumnToken(year_match.start(), "PERIOD", period))

    diff_count = len(DIFF_PATTERN.findall(header_text))
    diff_after_month = 1 if diff_count >= 1 else 0
    diff_after_kum = max(diff_count - diff_after_month, 0)

    tokens: list[ColumnToken] = []
    tokens.extend(month_tokens)
    tokens.extend(ColumnToken(-1, "DIFF", None) for _ in range(diff_after_month))
    tokens.extend(kum_tokens)
    tokens.extend(ColumnToken(-1, "DIFF", None) for _ in range(diff_after_kum))

    return tokens


def build_column_tokens(header_text: str) -> list[ColumnToken]:
    """
    Oeffentlicher Dispatcher: erkennt automatisch, ob das fragmentierte
    SMD-Layout vorliegt (Signal: 'Kum. bis <Monat>' OHNE nachfolgende
    Jahreszahl - diese stehen bei SMD in einer separaten Zeile) und
    waehlt entsprechend die spezialisierte Rekonstruktions-Logik oder
    das einfache positionsbasierte Verfahren.
    """
    kum_label_matches = list(KUM_LABEL_PATTERN.finditer(header_text))

    if kum_label_matches:
        return _build_column_tokens_smd(header_text, kum_label_matches)

    return _build_column_tokens_positional(header_text)


def parse_periods(header_text: str) -> list[ColumnToken]:
    """
    Oeffentliche Einstiegsfunktion. Gibt die vollstaendige, geordnete
    Spalten-Token-Liste zurueck (inkl. DIFF-Platzhaltern), damit die
    Werte-Zuordnung im Parser exakt Spalte-fuer-Spalte erfolgen kann.
    """
    tokens = build_column_tokens(header_text)
    if not tokens:
        raise ValueError(f"Kein bekanntes Periodenmuster in Header erkannt: {header_text!r}")
    return tokens