"""
tests/test_benchmark_loader.py
Unit-Tests fuer noble_cockpit/benchmarks/benchmark_loader.py

Testet drei Ebenen unabhaengig voneinander:
  1. Laden und Parsen der Benchmark-JSON (Struktur, Umsatzklassen-Sortierung)
  2. Reine Berechnungslogik (Formeln, optionale vs. benoetigte Keys)
  3. End-to-end Integration mit echten SMD-Parser-Daten (Golden-Master-Stil)
"""
from __future__ import annotations

import pytest

from noble_cockpit.benchmarks.benchmark_loader import (
    berechne_kennzahlen,
    load_benchmark,
    vergleiche_mit_benchmark,
    Rahmensatz,
)


# ---------------------------------------------------------------------------
# 1. Benchmark-Datei laden
# ---------------------------------------------------------------------------

class TestLoadBenchmark:
    def test_laedt_gebaeudereinigung(self):
        benchmark = load_benchmark("gebaeudereinigung")
        assert benchmark.branche == "Glas- und Gebaeudereinigung"
        assert len(benchmark.umsatzklassen) == 3

    def test_umsatzklassen_sortiert_nach_umsatz_von(self):
        benchmark = load_benchmark("gebaeudereinigung")
        umsatz_von_werte = [k.umsatz_von for k in benchmark.umsatzklassen]
        assert umsatz_von_werte == sorted(umsatz_von_werte)

    def test_unbekannte_branche_wirft_aussagekraeftigen_fehler(self):
        with pytest.raises(FileNotFoundError, match="nicht_existierende_branche"):
            load_benchmark("nicht_existierende_branche")

    def test_passende_umsatzklasse_untere_grenze(self):
        benchmark = load_benchmark("gebaeudereinigung")
        klasse = benchmark.passende_umsatzklasse(50_000.0)
        assert klasse.key == "bis_150k"

    def test_passende_umsatzklasse_obere_klasse_ohne_deckel(self):
        benchmark = load_benchmark("gebaeudereinigung")
        klasse = benchmark.passende_umsatzklasse(10_000_000.0)
        assert klasse.key == "ueber_300k"

    def test_passende_umsatzklasse_exakte_grenze_gehoert_zur_hoeheren_klasse(self):
        # Nr. 8 Vorbemerkungen: "ueber 150.000" - die Grenze selbst gehoert
        # zur unteren Klasse (< statt <=), siehe Umsatzklasse.enthaelt().
        benchmark = load_benchmark("gebaeudereinigung")
        klasse = benchmark.passende_umsatzklasse(150_000.0)
        assert klasse.key == "150k_bis_300k"


# ---------------------------------------------------------------------------
# 2. Rahmensatz.einordnen()
# ---------------------------------------------------------------------------

class TestRahmensatzEinordnen:
    @pytest.fixture
    def rahmensatz(self) -> Rahmensatz:
        return Rahmensatz(min=20.0, durchschnitt=40.0, max=60.0)

    def test_unterhalb_rahmen(self, rahmensatz):
        assert rahmensatz.einordnen(10.0) == "unterhalb"

    def test_oberhalb_rahmen(self, rahmensatz):
        assert rahmensatz.einordnen(70.0) == "oberhalb"

    def test_im_rahmen_unter_durchschnitt(self, rahmensatz):
        assert rahmensatz.einordnen(30.0) == "im_rahmen_unter_durchschnitt"

    def test_im_rahmen_ueber_durchschnitt(self, rahmensatz):
        assert rahmensatz.einordnen(50.0) == "im_rahmen_ueber_durchschnitt"

    def test_exakt_am_minimum_gilt_als_im_rahmen(self, rahmensatz):
        assert rahmensatz.einordnen(20.0) == "im_rahmen_unter_durchschnitt"

    def test_exakt_am_maximum_gilt_als_im_rahmen(self, rahmensatz):
        assert rahmensatz.einordnen(60.0) == "im_rahmen_ueber_durchschnitt"


# ---------------------------------------------------------------------------
# 3. berechne_kennzahlen() - reine Formellogik mit synthetischen Werten
# ---------------------------------------------------------------------------

class TestBerechneKennzahlen:
    def test_einfacher_fall_ohne_optionale_positionen(self):
        werte = {"summe_erloese": 200_000.0, "personalkosten": 80_000.0}
        ergebnisse = berechne_kennzahlen(werte)
        # rohgewinn_ii = (200000 - 80000) / 200000 * 100 = 60.0
        assert ergebnisse["rohgewinn_ii"] == pytest.approx(60.0)
        # ohne optionale Aufwendungen sind halbreingewinn/reingewinn == rohgewinn_ii
        assert ergebnisse["halbreingewinn"] == pytest.approx(60.0)
        assert ergebnisse["reingewinn"] == pytest.approx(60.0)

    def test_mit_allgemeinen_betriebsaufwendungen(self):
        werte = {
            "summe_erloese": 200_000.0,
            "personalkosten": 80_000.0,
            "raumkosten": 10_000.0,
            "fahrzeugkosten": 5_000.0,
        }
        ergebnisse = berechne_kennzahlen(werte)
        assert ergebnisse["rohgewinn_ii"] == pytest.approx(60.0)
        # halbreingewinn = (120000 - 15000) / 200000 * 100 = 52.5
        assert ergebnisse["halbreingewinn"] == pytest.approx(52.5)

    def test_umsatz_fallback_ohne_summe_erloese(self):
        # SMD-Format weist keine 'summe_erloese' aus, nur Einzelpositionen.
        werte = {
            "erloese_betrieblich": 150_000.0,
            "sonstige_ertraege": 5_000.0,
            "personalkosten": 60_000.0,
        }
        ergebnisse = berechne_kennzahlen(werte)
        umsatz = 155_000.0
        erwartet = (umsatz - 60_000.0) / umsatz * 100
        assert ergebnisse["rohgewinn_ii"] == pytest.approx(erwartet)

    def test_fehlende_pflichtangabe_wirft_keyerror(self):
        werte = {"summe_erloese": 200_000.0}  # personalkosten fehlt komplett
        with pytest.raises(KeyError, match="personalkosten"):
            berechne_kennzahlen(werte)

    def test_fehlender_umsatz_wirft_keyerror(self):
        werte = {"personalkosten": 80_000.0}
        with pytest.raises(KeyError, match="summe_erloese"):
            berechne_kennzahlen(werte)

    def test_umsatz_null_wirft_zerodivisionerror(self):
        werte = {"summe_erloese": 0.0, "personalkosten": 0.0}
        with pytest.raises(ZeroDivisionError):
            berechne_kennzahlen(werte)

    def test_optionale_position_fehlt_kein_fehler(self):
        # Kein 'instandhaltung', 'verschiedene_kosten' etc. vorhanden - das ist
        # legitim (Betrieb hatte diese Kostenart nicht) und darf NICHT crashen.
        werte = {"summe_erloese": 100_000.0, "personalkosten": 40_000.0}
        ergebnisse = berechne_kennzahlen(werte)
        assert ergebnisse["halbreingewinn"] == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# 4. vergleiche_mit_benchmark() - Integration
# ---------------------------------------------------------------------------

class TestVergleicheMitBenchmark:
    def test_vollstaendiger_vergleich_liefert_drei_ergebnisse(self):
        benchmark = load_benchmark("gebaeudereinigung")
        werte = {
            "summe_erloese": 200_000.0,
            "personalkosten": 80_000.0,
            "raumkosten": 10_000.0,
        }
        ergebnisse = vergleiche_mit_benchmark(werte, benchmark)
        assert len(ergebnisse) == 3
        assert {e.kennzahl for e in ergebnisse} == {
            "rohgewinn_ii", "halbreingewinn", "reingewinn"
        }

    def test_richtige_umsatzklasse_wird_verwendet(self):
        benchmark = load_benchmark("gebaeudereinigung")
        werte = {"summe_erloese": 500_000.0, "personalkosten": 200_000.0}
        ergebnisse = vergleiche_mit_benchmark(werte, benchmark)
        assert all(e.umsatzklasse.key == "ueber_300k" for e in ergebnisse)

    def test_einordnung_unterhalb_bei_sehr_niedrigem_rohgewinn(self):
        benchmark = load_benchmark("gebaeudereinigung")
        # Extrem hohe Personalkosten -> Rohgewinn II sehr niedrig -> unterhalb
        werte = {"summe_erloese": 100_000.0, "personalkosten": 95_000.0}
        ergebnisse = vergleiche_mit_benchmark(werte, benchmark)
        rohgewinn_ergebnis = next(e for e in ergebnisse if e.kennzahl == "rohgewinn_ii")
        assert rohgewinn_ergebnis.einordnung == "unterhalb"


# ---------------------------------------------------------------------------
# 5. End-to-end mit echten Parser-Daten (SMD-Fixture)
# ---------------------------------------------------------------------------

class TestEndToEndMitSMDDaten:
    def test_smd_jahreswerte_liefern_plausible_kennzahlen(self):
        from pathlib import Path
        from noble_cockpit.parser.lexware_parser import parse_bwa_pdf

        pdf_pfad = (
            Path(__file__).resolve().parent.parent
            / "data" / "bwa_samples" / "BWA_2024_SMD.pdf"
        )
        if not pdf_pfad.exists():
            pytest.skip(f"Test-PDF nicht vorhanden: {pdf_pfad}")

        positionen = parse_bwa_pdf(pdf_pfad)
        werte: dict[str, float] = {}
        for pos in positionen:
            for period, wert in pos.werte.items():
                if period.is_aggregate and period.year == 2025:
                    werte[pos.kanonischer_key] = wert

        benchmark = load_benchmark("gebaeudereinigung")
        ergebnisse = vergleiche_mit_benchmark(werte, benchmark)

        assert len(ergebnisse) == 3
        for ergebnis in ergebnisse:
            # Plausibilitaets-Check statt Golden-Master: Prozentwerte muessen
            # in einem realistischen Bereich liegen (keine Vorzeichenfehler,
            # keine Faktor-100-Verwechslung etc.)
            assert -50.0 < ergebnis.wert_prozent < 150.0
