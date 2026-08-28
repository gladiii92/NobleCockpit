import sys
from pathlib import Path

from noble_cockpit.parser.lexware_parser import parse_bwa_pdf
from noble_cockpit.benchmarks.benchmark_loader import (
    load_benchmark,
    vergleiche_mit_benchmark,
    berechne_kostenstruktur
)
from noble_cockpit.rules.rule_engine import evaluate_bwa
from noble_cockpit.report.pdf_report import (
    BerichtsDaten,
    Handlungsempfehlung,
    erstelle_bericht,
    erstelle_standard_einschaetzung
)

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

    # 2. Flaches Daten-Dictionary für die aktuellste Periode bauen
    werte = {}
    berichtsjahr = 2025 # Fallback-Jahr
    for pos in positionen:
        if pos.werte:
            # Wir greifen die erste Periode (Aggregate/Jahreswert) ab
            first_period = list(pos.werte.keys())[0]
            werte[pos.kanonischer_key] = pos.werte[first_period]
            # Setze das Berichtsjahr dynamisch, falls die Periode ein Jahr hat
            if hasattr(first_period, "year") and first_period.year:
                berichtsjahr = first_period.year

    # 3. Benchmarks laden
    try:
        benchmark_komplett = load_benchmark("gebaeudereinigung")
        # Wir laden die rohe JSON direkt für die Regel-Engine, um AttributeError zu vermeiden
        import json
        with open("noble_cockpit/benchmarks/data/gebaeudereinigung.json", "r", encoding="utf-8") as f:
            raw_json = json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden der Benchmarks: {e}")
        sys.exit(1)
        
    benchmark_fuer_rules = raw_json.get("kostenstruktur_referenz", {})
    for klasse in raw_json.get("umsatzklassen", []):
        if klasse["key"] == "150k_bis_300k":
            benchmark_fuer_rules.update(klasse["kennzahlen"])
            break

    # 4. Regel-Engine ausführen
    print("\nWerte BWA gegen Benchmark aus...")
    ausgeloeste_regeln = evaluate_bwa(werte, benchmark_fuer_rules)

    # 5. Handlungsempfehlungen für das PDF vorbereiten
    empfehlungen_fuer_pdf = [
        Handlungsempfehlung(
            prio=alarm.rule.priority,
            titel=alarm.rule.key,
            evidenz=alarm.evidence,
            ursachen=", ".join(alarm.rule.possible_causes),
            aktion=alarm.rule.recommendation
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
        empfehlungen=empfehlungen_fuer_pdf
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