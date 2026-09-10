import sys
from pathlib import Path

from noble_cockpit.parser.lexware_parser import parse_bwa_pdf
from noble_cockpit.benchmarks.benchmark_loader import (
    load_benchmark,
    vergleiche_mit_benchmark,
    berechne_kostenstruktur,
)
from noble_cockpit.rules.rule_engine import evaluate_bwa
from noble_cockpit.report.pdf_report import (
    BerichtsDaten,
    Handlungsempfehlung,
    erstelle_bericht,
    erstelle_standard_einschaetzung,
)


def waehle_aggregat_periode(positionen):
    """
    Waehlt die aktuellste Aggregat-Periode (Jahressumme/Kumulativ) aus den
    geparsten BWA-Positionen und baut das flache Werte-dict fuer Engine + Report.

    Warum Aggregat: Die BMF-Richtsaetze sind auf JAHRESbasis kalkuliert
    (saisonale Schwankungen, z.B. Aussenreinigung im Winter). Ein einzelner
    Monat waere gegen die Richtsatzsammlung nicht aussagekraeftig.

    Rueckgabe: (werte_dict, berichtsjahr). Fallback: Falls keine Aggregat-Periode
    existiert, wird die aktuellste Einzelperiode verwendet.
    """
    aggregat_jahr = None
    sonstige_jahr = None

    for pos in positionen:
        for period in pos.werte:
            if period.is_aggregate:
                if aggregat_jahr is None or period.year > aggregat_jahr:
                    aggregat_jahr = period.year
            else:
                if sonstige_jahr is None or period.year > sonstige_jahr:
                    sonstige_jahr = period.year

    ziel_is_aggregat = aggregat_jahr is not None
    ziel_jahr = aggregat_jahr if ziel_is_aggregat else sonstige_jahr
    if ziel_jahr is None:
        return {}, None

    # Bei mehreren Perioden desselben Jahres (z.B. Q1-Q4 + KUM_M12) gewinnt
    # die mit dem hoechsten end-Wert (spaeteste Periode = komplette Jahressumme)
    beste_periode = {}
    for pos in positionen:
        for period, wert in pos.werte.items():
            if period.year != ziel_jahr or period.is_aggregate != ziel_is_aggregat:
                continue
            alt = beste_periode.get(pos.kanonischer_key)
            if alt is None or period.end >= alt.end:
                beste_periode[pos.kanonischer_key] = period

    werte = {
        pos.kanonischer_key: pos.werte[periode]
        for pos in positionen
        for periode in [beste_periode.get(pos.kanonischer_key)]
        if periode is not None and periode in pos.werte
    }
    return werte, ziel_jahr


def baue_benchmark_fuer_rules(umsatz: float) -> tuple[dict, str]:
    """
    Baut das Benchmark-dict fuer die Regel-Engine dynamisch:
    1. Rahmensaetze der PASSENDEN Umsatzklasse (Bug-Fix: frueher war
       '150k_bis_300k' hardcodiert, unabhaengig vom Mandanten-Umsatz)
    2. Kostenstruktur-Grenzwerte (Praxis-Limits: Personal max 75% etc.)

    Rueckgabe: (benchmark_dict, umsatzklasse_label)
    """
    import json

    benchmark_daten = load_benchmark("gebaeudereinigung")
    umsatzklasse = benchmark_daten.passende_umsatzklasse(umsatz)
    print(f"Umsatzklasse: {umsatzklasse.label}")

    benchmark_fuer_rules: dict = {}
    for kennzahl, rahmensatz in umsatzklasse.kennzahlen.items():
        benchmark_fuer_rules[kennzahl] = {
            "min": rahmensatz.min,
            "durchschnitt": rahmensatz.durchschnitt,
            "max": rahmensatz.max,
        }

    # Kostenstruktur-Referenz aus der rohen JSON (Grenzwerte als dict-struktur)
    benchmark_pfad = (
        Path(__file__).resolve().parent
        / "noble_cockpit" / "benchmarks" / "data" / "gebaeudereinigung.json"
    )
    with open(benchmark_pfad, "r", encoding="utf-8") as f:
        raw_json = json.load(f)
    benchmark_fuer_rules["kostenstruktur_referenz"] = raw_json.get("kostenstruktur_referenz", {})

    return benchmark_fuer_rules, umsatzklasse.label


def main():
    if len(sys.argv) < 2:
        print("Nutzung: python main.py <pfad_zum_pdf> [mandant_name]")
        print("Beispiel: python main.py data/bwa_samples/BWA_2024_SMD.pdf SMD")
        sys.exit(1)

    pdf_pfad = Path(sys.argv[1])
    mandant_name = sys.argv[2] if len(sys.argv) > 2 else "Muster-Mandant"

    projekt_root = Path(__file__).resolve().parent
    logo_pfad = projekt_root / "assets" / "logo.png"
    ausgabe_pfad = projekt_root / "output" / f"BWA_Bericht_{mandant_name}.pdf"

    if not pdf_pfad.exists():
        print(f"Fehler: PDF-Datei nicht gefunden unter {pdf_pfad}")
        sys.exit(1)

    print(f"Starte NobleCockpit Audit für: {pdf_pfad.name}")

    # 1. BWA parsen
    try:
        positionen = parse_bwa_pdf(pdf_pfad)
    except Exception as e:
        print(f"Fehler beim Parsen der BWA: {e}")
        sys.exit(1)

    # 2. Flaches Werte-dict der aktuellsten Aggregat-Periode bauen
    werte, berichtsjahr = waehle_aggregat_periode(positionen)
    if berichtsjahr is None:
        print("Fehler: Keine Periode mit Werten gefunden.")
        sys.exit(1)
    umsatz = werte.get("erloese_betrieblich") or werte.get("summe_erloese") or 0.0
    if umsatz <= 0:
        print("Warnung: Keine Erlöse in der gewählten Periode erkannt.")
        sys.exit(1)

    # 3. Benchmarks laden (dynamische Umsatzklasse statt hardcodiert)
    try:
        benchmark_komplett = load_benchmark("gebaeudereinigung")
    except Exception as e:
        print(f"Fehler beim Laden der Benchmarks: {e}")
        sys.exit(1)

    benchmark_fuer_rules, umsatzklasse_label = baue_benchmark_fuer_rules(umsatz)

    # 4. Regel-Engine ausführen
    print("\nWerte BWA gegen Benchmark aus...")
    ausgeloeste_regeln = evaluate_bwa(werte, benchmark_fuer_rules)

    # 5. Handlungsempfehlungen für das PDF vorbereiten (inkl. Potenzial-Range)
    empfehlungen_fuer_pdf = [
        Handlungsempfehlung(
            prio=alarm.rule.priority,
            titel=alarm.rule.key,
            evidenz=alarm.evidence + (" " + alarm.potenzial if alarm.potenzial else ""),
            ursachen=", ".join(alarm.rule.possible_causes),
            aktion=alarm.rule.recommendation,
            potenzial_kurz=alarm.potenzial_kurz,
        )
        for alarm in ausgeloeste_regeln
    ]

    # Konsolenausgabe für den Nutzer
    for empf in empfehlungen_fuer_pdf:
        print(f"PRIO {empf.prio} | {empf.titel.upper()}\nEvidenz: {empf.evidenz}\n")

    if not empfehlungen_fuer_pdf:
        print("Keine kritischen Abweichungen gefunden. Alles im grünen Bereich!\n")

    # 6. Daten für PDF-Generierung berechnen
    print("Berechne Kostenstruktur und generiere PDF-Bericht...")
    ergebnisse = vergleiche_mit_benchmark(werte, benchmark_komplett)
    kostenstruktur = berechne_kostenstruktur(werte)
    einschaetzung = erstelle_standard_einschaetzung(ergebnisse)

    daten = BerichtsDaten(
        mandant_name=mandant_name,
        branche_label="Glas- und Gebäudereinigung",
        berichtsjahr=berichtsjahr,
        ergebnisse=ergebnisse,
        kostenstruktur=kostenstruktur,
        einschaetzung_text=einschaetzung,
        logo_pfad=logo_pfad,
        ausgabe_pfad=ausgabe_pfad,
        empfehlungen=empfehlungen_fuer_pdf,
        umsatz_eur=umsatz,
        umsatzklasse_label=umsatzklasse_label,
    )

    # 7. PDF erstellen
    try:
        fertiges_pdf = erstelle_bericht(daten)
        print(f"ERFOLG! Bericht erstellt unter: {fertiges_pdf}")
    except Exception as e:
        print(f"Fehler bei der PDF-Erstellung: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
