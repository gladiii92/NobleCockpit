"""
generate_fixtures.py
Erzeugt/aktualisiert die Golden-Master-Fixtures fuer den BWA-Parser.

WICHTIG - Zweck und Abgrenzung:
Dieses Script ist bewusst NICHT Teil der automatischen Test-Suite
(test_lexware_parser.py). Es ist ein manuell auszufuehrendes Werkzeug,
mit dem DU als Entwickler entscheidest: "Der aktuelle Parser-Output
fuer diese PDFs ist korrekt - das ist jetzt der neue Referenzstand."

Workflow (Golden-Master-Testing):
1. Neues PDF-Format taucht auf ODER Parser-Bug wird gefixt.
2. Du pruefst den Output MANUELL gegen das Original-PDF (wie zuletzt
   bei BWA_2024_SMD.pdf: Wert-fuer-Wert-Abgleich).
3. Erst wenn der Output nachweislich korrekt ist, fuehrst du dieses
   Script aus - es schreibt den aktuellen Output als neue "Wahrheit"
   nach tests/fixtures/*.json.
4. test_lexware_parser.py vergleicht bei JEDEM Testlauf (z.B. vor jedem
   Git-Commit) den LIVE-Parser-Output gegen genau diese gespeicherten
   Fixtures. Jede Abweichung ist entweder:
   a) ein Regressions-Bug (du hast etwas kaputt gemacht) -> Test schlaegt
      fehl, FIX den Parser, NICHT die Fixture.
   b) eine gewollte Verbesserung (z.B. neuer Mapping-Eintrag) -> Test
      schlaegt zunaechst fehl, du pruefst den neuen Output manuell,
      und erst DANN aktualisierst du die Fixture erneut mit diesem
      Script.

Fixtures werden NIE automatisch ueberschrieben - nur durch bewussten,
manuellen Aufruf dieses Scripts. Das ist der Kern von Golden-Master-
Testing: Die Referenz ist von einem Menschen freigegebener Output,
nicht mathematisch abgeleitete Erwartung.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lexware_parser import parse_bwa_pdf, BWAPosition

BWA_DIR = Path(__file__).resolve().parent.parent / "data" / "bwa_samples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def positionen_to_fixture(positionen: list[BWAPosition]) -> dict:
    """
    Wandelt eine Liste von BWAPosition-Objekten in ein JSON-serialisierbares
    dict um. Periods werden ueber ihr .label (z.B. 'Q3_2023', 'KUM_M12_2025')
    als Schluessel verwendet - das ist stabil, lesbar und git-diff-freundlich.
    """
    result = {}
    for pos in positionen:
        result[pos.kanonischer_key] = {
            "bezeichnung_original": pos.bezeichnung_original,
            "werte": {p.label: v for p, v in pos.werte.items()},
        }
    return result


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(BWA_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"Keine PDFs gefunden in {BWA_DIR}")
        return

    for pdf_path in pdf_files:
        fixture_path = FIXTURES_DIR / f"{pdf_path.stem}.json"
        try:
            positionen = parse_bwa_pdf(pdf_path)
        except ValueError as e:
            print(f"UEBERSPRUNGEN (Parser-Fehler): {pdf_path.name}\n  -> {e}")
            continue

        fixture = positionen_to_fixture(positionen)
        with open(fixture_path, "w", encoding="utf-8") as f:
            json.dump(fixture, f, ensure_ascii=False, indent=2, sort_keys=True)

        print(f"Fixture geschrieben: {fixture_path.name} ({len(fixture)} Positionen)")


if __name__ == "__main__":
    main()
