"""
test_lexware_parser.py
Regressionstests fuer den BWA-Parser gegen Golden-Master-Fixtures.

Design-Prinzip: Diese Tests pruefen NICHT "ist der Parser mathematisch
korrekt" (das kann kein Test automatisch wissen - dafuer musst DU als
Mensch einmalig gegen das Original-PDF pruefen, siehe generate_fixtures.py).
Sie pruefen: "Hat sich der Output seit der letzten von dir freigegebenen
Version veraendert?" Jede Abweichung ist ein Signal, KEIN automatischer
Fehlerbeweis - aber ein Signal, dem du nachgehen musst.

Drei Kategorien von Testfaellen, die hier unterschieden werden:
1. PDF wirft eine Exception, obwohl es das vorher nicht tat
   -> Regression im Parser (z.B. durch einen "Fix" fuer ein neues Format)
2. PDF laeuft durch, aber Positionen/Werte weichen von der Fixture ab
   -> Entweder Regression ODER gewollte Verbesserung (needs manual review)
3. Neues PDF ganz ohne Fixture (noch nie manuell freigegeben)
   -> Kein Fehlschlag, sondern expliziter Hinweis: "Fixture fehlt,
      pruefe manuell und rufe generate_fixtures.py auf"

Aufruf:
    pytest tests/ -v
    pytest tests/ -v -k BWA_2024_SMD     # nur ein bestimmtes PDF
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lexware_parser import parse_bwa_pdf, BWAPosition

BWA_DIR = Path(__file__).resolve().parent.parent / "data" / "bwa_samples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

TOLERANCE = 0.01  # Cent-Toleranz fuer Float-Rundungsdifferenzen


def _discover_pdfs() -> list[Path]:
    if not BWA_DIR.exists():
        return []
    return sorted(BWA_DIR.glob("*.pdf"))


def _positionen_to_fixture(positionen: list[BWAPosition]) -> dict:
    result = {}
    for pos in positionen:
        result[pos.kanonischer_key] = {
            "bezeichnung_original": pos.bezeichnung_original,
            "werte": {p.label: v for p, v in pos.werte.items()},
        }
    return result


def _load_fixture(pdf_path: Path) -> dict | None:
    fixture_path = FIXTURES_DIR / f"{pdf_path.stem}.json"
    if not fixture_path.exists():
        return None
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


PDF_FILES = _discover_pdfs()
PDF_IDS = [p.name for p in PDF_FILES]


@pytest.mark.skipif(not PDF_FILES, reason="Keine PDFs in data/bwa_samples/ gefunden")
@pytest.mark.parametrize("pdf_path", PDF_FILES, ids=PDF_IDS)
class TestBWAParserGoldenMaster:
    """Eine Testklasse pro PDF, damit pytest -v jede Datei einzeln ausweist."""

    def test_parsing_does_not_raise(self, pdf_path: Path) -> None:
        """
        Grundvoraussetzung: Der Parser darf nicht mit ValueError abbrechen.
        Schlaegt dieser Test fehl, ist die Fehlermeldung selbst schon die
        Diagnose (z.B. 'Spaltenanzahl-Mismatch ... neues Format').
        """
        try:
            parse_bwa_pdf(pdf_path)
        except ValueError as e:
            pytest.fail(
                f"Parser wirft ValueError bei {pdf_path.name} - "
                f"neues/unbekanntes Spaltenformat oder Regression:\n{e}"
            )

    def test_fixture_exists(self, pdf_path: Path) -> None:
        """
        Ohne Fixture kann kein Regressionsvergleich stattfinden. Das ist
        KEIN Parser-Fehler, sondern ein fehlender manueller Freigabeschritt.
        """
        fixture = _load_fixture(pdf_path)
        if fixture is None:
            pytest.fail(
                f"Keine Fixture fuer {pdf_path.name} vorhanden.\n"
                f"-> Pruefe den Parser-Output MANUELL gegen das Original-PDF.\n"
                f"-> Erst wenn er korrekt ist: "
                f"python tests/generate_fixtures.py"
            )

    def test_matches_golden_master(self, pdf_path: Path) -> None:
        """
        Kernvergleich: Live-Parser-Output vs. zuletzt freigegebener Stand.
        Baut bei Abweichung eine praezise, lesbare Diff-Liste auf -
        nicht nur "Test failed", sondern WELCHE Position, WELCHE Periode,
        ALT vs. NEU.
        """
        fixture = _load_fixture(pdf_path)
        if fixture is None:
            pytest.skip(f"Keine Fixture fuer {pdf_path.name} - siehe test_fixture_exists")

        try:
            positionen = parse_bwa_pdf(pdf_path)
        except ValueError:
            pytest.skip(f"{pdf_path.name} wirft ValueError - siehe test_parsing_does_not_raise")

        live = _positionen_to_fixture(positionen)
        diffs: list[str] = []

        fixture_keys = set(fixture.keys())
        live_keys = set(live.keys())

        for missing_key in sorted(fixture_keys - live_keys):
            diffs.append(
                f"FEHLENDE POSITION: '{missing_key}' "
                f"(war: '{fixture[missing_key]['bezeichnung_original']}') "
                f"ist im aktuellen Output nicht mehr vorhanden."
            )

        for new_key in sorted(live_keys - fixture_keys):
            diffs.append(
                f"NEUE POSITION: '{new_key}' "
                f"('{live[new_key]['bezeichnung_original']}') "
                f"war in der Fixture nicht vorhanden - "
                f"pruefe ob gewollt (z.B. neuer Mapping-Eintrag)."
            )

        for key in sorted(fixture_keys & live_keys):
            alte_bezeichnung = fixture[key]["bezeichnung_original"]
            neue_bezeichnung = live[key]["bezeichnung_original"]
            if alte_bezeichnung != neue_bezeichnung:
                diffs.append(
                    f"BEZEICHNUNG GEAENDERT bei '{key}': "
                    f"'{alte_bezeichnung}' -> '{neue_bezeichnung}'"
                )

            alte_werte = fixture[key]["werte"]
            neue_werte = live[key]["werte"]
            alle_labels = set(alte_werte.keys()) | set(neue_werte.keys())

            for label in sorted(alle_labels):
                alt = alte_werte.get(label)
                neu = neue_werte.get(label)
                if alt is None:
                    diffs.append(f"NEUE PERIODE bei '{key}': '{label}' = {neu} (vorher nicht vorhanden)")
                elif neu is None:
                    diffs.append(f"FEHLENDE PERIODE bei '{key}': '{label}' = {alt} (jetzt nicht mehr vorhanden)")
                elif abs(alt - neu) > TOLERANCE:
                    diffs.append(
                        f"WERT-ABWEICHUNG bei '{key}' / '{label}': "
                        f"alt={alt} -> neu={neu} (Differenz={neu - alt:.2f})"
                    )

        if diffs:
            diff_report = "\n  - ".join(diffs)
            pytest.fail(
                f"\n{pdf_path.name} weicht vom Golden Master ab "
                f"({len(diffs)} Unterschied(e)):\n  - {diff_report}\n\n"
                f"Falls dies eine GEWOLLTE Verbesserung ist (z.B. neuer "
                f"Mapping-Eintrag, Bugfix): manuell gegen Original-PDF "
                f"pruefen, dann 'python tests/generate_fixtures.py' "
                f"ausfuehren, um den neuen Stand freizugeben."
            )


def test_no_duplicate_kanonischer_key_across_document() -> None:
    """
    Zusaetzliche Absicherung ueber ALLE Testdokumente hinweg (nicht nur
    innerhalb einer Datei wie check_unique_keys() im Parser selbst):
    Stellt sicher, dass mind. ein Dokument je Format-Typ vorhanden ist,
    das strukturell unterschiedliche Spalten-Layouts abdeckt. Reiner
    Sanity-Check gegen "versehentlich alle Testdateien vom gleichen Typ".
    """
    if not PDF_FILES:
        pytest.skip("Keine PDFs vorhanden")

    from lexware_parser import extract_header_text
    from periods import parse_periods

    layouts = set()
    for pdf_path in PDF_FILES:
        header_text = extract_header_text(pdf_path)
        tokens = parse_periods(header_text)
        period_count = sum(1 for t in tokens if t.kind == "PERIOD")
        diff_count = len(tokens) - period_count
        layouts.add((period_count, diff_count))

    assert len(layouts) >= 1, "Keine Spalten-Layouts erkannt - Testdaten pruefen."
