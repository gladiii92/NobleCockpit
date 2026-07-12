"""
noble_cockpit/benchmarks/benchmark_loader.py
Vergleicht die aus BWAPosition-Objekten berechneten Kennzahlen eines Mandanten
mit den amtlichen Richtsaetzen des Bundesfinanzministeriums (Richtsatzsammlung).

Datenquelle: noble_cockpit/benchmarks/data/*.json
Jede JSON-Datei entspricht EINER Gewerbeklasse (z.B. "Glas- und Gebaeudereinigung")
und enthaelt die vom BMF veroeffentlichten Rahmensaetze (min/durchschnitt/max) fuer
Rohgewinn II, Halbreingewinn und Reingewinn, gestaffelt nach drei Umsatzklassen.

WICHTIG - Warum genau diese drei Kennzahlen:
Bei Fertigungsbetrieben ohne Wareneinsatz (wie Glas- und Gebaeudereinigung, siehe
Vorbemerkungen der Richtsatzsammlung Nr. 5) entfallen "Rohgewinnaufschlag" und
"Rohgewinn I" - diese gelten nur fuer Handelsbetriebe mit Wareneinsatz. Es bleiben:

    Rohgewinn II    = (Umsatz - Fertigungsloehne) / Umsatz * 100
    Halbreingewinn  = (Rohgewinn_II_Betrag - allgemeine Betriebsaufwendungen) / Umsatz * 100
    Reingewinn      = (Halbreingewinn_Betrag - besondere sachliche/personelle Aufwendungen) / Umsatz * 100

MAPPING-PROBLEM UND LOESUNG:
Die Richtsatzsammlung definiert diese Begriffe ueber ein bundeseinheitliches Schema
(vgl. Vorbemerkungen Nr. 8.3 - 8.4), das NICHT 1:1 mit den Positionsnamen einer
Lexware-BWA uebereinstimmt. Jede Buchhaltungssoftware benennt und gruppiert ihre
BWA-Zeilen unterschiedlich. Deshalb existiert hier eine explizite, dokumentierte
Zuordnungstabelle (KENNZAHLEN_MAPPING) - KEINE impliziten Annahmen im Code verstreut.

Wird ein Format ergaenzt, bei dem eine benoetigte Position fehlt oder anders benannt
ist, schlaegt die Berechnung mit einer praezisen Fehlermeldung fehl (fail-fast),
statt stillschweigend mit 0.0 oder falschen Werten weiterzurechnen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------------
# Datenmodelle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rahmensatz:
    """Ein einzelner Richtsatz-Wert: unterer Rahmensatz, Mittelsatz, oberer Rahmensatz."""
    min: float
    durchschnitt: float
    max: float

    def einordnen(self, wert: float) -> str:
        """
        Ordnet einen berechneten Prozentwert relativ zum amtlichen Rahmensatz ein.
        Gibt einen von vier Zustaenden zurueck - bewusst als String-Literal statt
        Enum, weil dies direkt in Berichtstexten (Schritt 5: pdf_report.py)
        verwendet wird und keine weitere Übersetzungsebene braucht.
        """
        if wert < self.min:
            return "unterhalb"
        if wert > self.max:
            return "oberhalb"
        if wert < self.durchschnitt:
            return "im_rahmen_unter_durchschnitt"
        return "im_rahmen_ueber_durchschnitt"


@dataclass(frozen=True)
class Umsatzklasse:
    key: str
    label: str
    umsatz_von: float
    umsatz_bis: Optional[float]  # None = keine Obergrenze
    kennzahlen: dict[str, Rahmensatz]

    def enthaelt(self, umsatz: float) -> bool:
        if umsatz < self.umsatz_von:
            return False
        if self.umsatz_bis is None:
            return True
        return umsatz < self.umsatz_bis


@dataclass(frozen=True)
class BenchmarkDaten:
    branche: str
    gewerbekennzahl_wz2008: list[str]
    quelle: str
    stand: str
    umsatzklassen: list[Umsatzklasse]

    def passende_umsatzklasse(self, jahresumsatz: float) -> Umsatzklasse:
        for klasse in self.umsatzklassen:
            if klasse.enthaelt(jahresumsatz):
                return klasse
        # Sollte bei korrekt konfigurierten, lueckenlosen Umsatzklassen nie
        # eintreten (letzte Klasse hat umsatz_bis=None). Sicherheitsnetz fuer
        # unplausible Eingaben (z.B. negativer Umsatz).
        raise ValueError(
            f"Kein Umsatzklassen-Bereich fuer Jahresumsatz {jahresumsatz:.2f} EUR "
            f"in Branche '{self.branche}' gefunden. Umsatzklassen: "
            f"{[(k.umsatz_von, k.umsatz_bis) for k in self.umsatzklassen]}"
        )


@dataclass(frozen=True)
class KennzahlErgebnis:
    """Ergebnis EINER berechneten und eingeordneten Kennzahl fuer einen Mandanten."""
    kennzahl: str
    wert_prozent: float
    rahmensatz: Rahmensatz
    einordnung: str
    umsatzklasse: Umsatzklasse


# ---------------------------------------------------------------------------
# Kennzahlen-Mapping: Richtsatz-Kennzahl -> benoetigte BWAPosition-Keys
# ---------------------------------------------------------------------------
#
# Jede Kennzahl definiert:
#   - "benoetigt": Liste kanonischer BWAPosition-Keys (aus lexware_parser.py),
#     die zwingend vorhanden sein muessen, um die Kennzahl zu berechnen.
#   - "formel": Callable, das aus einem dict[key, float] (Werte fuer EINE Periode)
#     den Kennzahl-Betrag in EURO zurueckgibt (noch nicht in % - die Umrechnung
#     in % vom Umsatz erfolgt zentral in berechne_kennzahlen()).
#
# Diese Struktur bewusst explizit statt "magisch": Wenn ein neues BWA-Format
# auftaucht und eine Position anders heisst/fehlt, siehst du hier sofort,
# WELCHER kanonische Key gebraucht wird - und kannst in lexware_parser.py
# gezielt das BEZEICHNUNG_MAPPING ergaenzen, statt hier zu raten.
#
# Zuordnung zu den Vorbemerkungen der Richtsatzsammlung:
#   Rohgewinn II   (Nr. 8.3.2): wirtsch. Umsatz ./. Fertigungsloehne
#     -> "personalkosten" wird hier als Naeherung fuer Fertigungsloehne verwendet,
#        weil die vorliegenden BWA-Formate KEINE separate Trennung zwischen
#        Fertigungs- und Verwaltungsloehnen ausweisen (anders als das amtliche
#        Schema in Zeile 18, Spalte 3 vs. 5). Das ist eine bewusste, dokumentierte
#        Vereinfachung, KEIN Bug - bei kleinen Betrieben mit wenig/keiner
#        Verwaltungsangestellten ist diese Näherung meist ausreichend genau.
#   Halbreingewinn (Nr. 8.4): Rohgewinn II ./. allgemeine sachliche Betriebsaufwendungen
#     -> Raumkosten, Fahrzeugkosten, Werbe-/Reisekosten, Steuern/Versicherungen,
#        Buerobedarf, Porto/Telefon, Instandhaltung, verschiedene Kosten
#   Reingewinn (Nr. 8.4, Zeile 82-86): Halbreingewinn ./. besondere sachliche
#     und personelle Aufwendungen
#     -> Rechts-/Beratungskosten, Abschreibungen, sonstige Aufwendungen
#
# WICHTIG: "summe_erloese" wird als Bezugsgroesse fuer den wirtschaftlichen
# Umsatz verwendet (Netto-Erloese ohne Umsatzsteuer, exakt das, was die
# Richtsatzsammlung unter "wirtschaftlicher Umsatz" versteht, Nr. 8.1.1).
# "summe_betriebseinnahmen" waere FALSCH, weil dort Forderungsveraenderungen
# und erhaltene Anzahlungen bereits eingerechnet sind - das verzerrt den
# Vergleich mit der Richtsatzsammlung, die auf Erloesen, nicht auf
# Zahlungsstroemen basiert.

UMSATZ_BASIS_KEY = "summe_erloese"

# Fallback, falls ein Format "summe_erloese" nicht ausweist (z.B. SMD nutzt
# stattdessen "erloese_betrieblich" + "sonstige_ertraege" ohne eigene Summenzeile
# - siehe lexware_parser.py BEZEICHNUNG_MAPPING). In diesem Fall wird der Umsatz
# additiv aus den Einzelpositionen rekonstruiert.
UMSATZ_BASIS_FALLBACK_KEYS = ["erloese_betrieblich", "sonstige_ertraege"]


def _umsatz(werte: dict[str, float]) -> float:
    if UMSATZ_BASIS_KEY in werte:
        return werte[UMSATZ_BASIS_KEY]
    fallback_summe = sum(werte.get(k, 0.0) for k in UMSATZ_BASIS_FALLBACK_KEYS)
    if fallback_summe == 0.0 and not any(k in werte for k in UMSATZ_BASIS_FALLBACK_KEYS):
        raise KeyError(
            f"Weder '{UMSATZ_BASIS_KEY}' noch Fallback-Keys "
            f"{UMSATZ_BASIS_FALLBACK_KEYS} in den BWA-Werten vorhanden. "
            f"Umsatz kann nicht ermittelt werden - pruefe BEZEICHNUNG_MAPPING "
            f"in lexware_parser.py fuer dieses Format."
        )
    return fallback_summe


def _rohgewinn_ii_betrag(werte: dict[str, float]) -> float:
    umsatz = _umsatz(werte)
    fertigungsloehne = werte.get("personalkosten", 0.0)
    return umsatz - fertigungsloehne


ALLGEMEINE_BETRIEBSAUFWENDUNGEN_KEYS = [
    "raumkosten",
    "fahrzeugkosten",
    "werbe_reisekosten",
    "steuern_versicherungen",
    "buerobedarf",
    "porto_telefon",
    "instandhaltung",
    "verschiedene_kosten",
    "kosten_warenabgabe",
]

BESONDERE_AUFWENDUNGEN_KEYS = [
    "rechts_beratungskosten",
    "abschreibungen",
    "sonstige_aufwendungen",
]


def _halbreingewinn_betrag(werte: dict[str, float]) -> float:
    rohgewinn_ii = _rohgewinn_ii_betrag(werte)
    allgemeine_aufwendungen = sum(
        werte.get(k, 0.0) for k in ALLGEMEINE_BETRIEBSAUFWENDUNGEN_KEYS
    )
    return rohgewinn_ii - allgemeine_aufwendungen


def _reingewinn_betrag(werte: dict[str, float]) -> float:
    halbreingewinn = _halbreingewinn_betrag(werte)
    besondere_aufwendungen = sum(
        werte.get(k, 0.0) for k in BESONDERE_AUFWENDUNGEN_KEYS
    )
    return halbreingewinn - besondere_aufwendungen


# "benoetigt": Keys, deren Fehlen die Kennzahl UNBERECHENBAR bzw. fachlich
#              sinnlos macht (Umsatzbasis, Personalkosten). Fehlt einer davon,
#              wird fail-fast mit KeyError abgebrochen.
# "optional":  Keys, die additiv in die Formel eingehen, aber in einer
#              konkreten BWA legitim FEHLEN duerfen, weil der Betrieb in der
#              betreffenden Periode schlicht keine Auspraegung dieser
#              Kostenart hatte (z.B. keine "Kosten Warenabgabe"). Diese
#              werden mit .get(key, 0.0) behandelt - Fehlen bedeutet 0 EUR,
#              NICHT "Fehler". Kein KeyError, keine Warnung notwendig.
KENNZAHLEN_MAPPING: dict[str, dict] = {
    "rohgewinn_ii": {
        "benoetigt": [UMSATZ_BASIS_KEY, "personalkosten"],
        "optional": [],
        "formel": _rohgewinn_ii_betrag,
        "beschreibung": "Wirtschaftlicher Umsatz abzueglich Fertigungsloehne (genaehert ueber Personalkosten).",
    },
    "halbreingewinn": {
        "benoetigt": [UMSATZ_BASIS_KEY, "personalkosten"],
        "optional": ALLGEMEINE_BETRIEBSAUFWENDUNGEN_KEYS,
        "formel": _halbreingewinn_betrag,
        "beschreibung": "Rohgewinn II abzueglich allgemeiner sachlicher Betriebsaufwendungen.",
    },
    "reingewinn": {
        "benoetigt": [UMSATZ_BASIS_KEY, "personalkosten"],
        "optional": ALLGEMEINE_BETRIEBSAUFWENDUNGEN_KEYS + BESONDERE_AUFWENDUNGEN_KEYS,
        "formel": _reingewinn_betrag,
        "beschreibung": "Halbreingewinn abzueglich besonderer sachlicher/personeller Aufwendungen.",
    },
}


# ---------------------------------------------------------------------------
# Laden der Benchmark-JSON-Dateien
# ---------------------------------------------------------------------------

def load_benchmark(branche_datei: str) -> BenchmarkDaten:
    """
    Laedt eine Benchmark-JSON-Datei aus noble_cockpit/benchmarks/data/.

    branche_datei: Dateiname OHNE Endung, z.B. "gebaeudereinigung"
                    (entspricht data/gebaeudereinigung.json)
    """
    pfad = DATA_DIR / f"{branche_datei}.json"
    if not pfad.exists():
        vorhandene = sorted(p.stem for p in DATA_DIR.glob("*.json"))
        raise FileNotFoundError(
            f"Keine Benchmark-Datei fuer '{branche_datei}' gefunden unter {pfad}.\n"
            f"Vorhandene Branchen: {vorhandene}"
        )

    with open(pfad, encoding="utf-8") as f:
        rohdaten = json.load(f)

    umsatzklassen = []
    for klasse_raw in rohdaten["umsatzklassen"]:
        kennzahlen = {
            kz_name: Rahmensatz(**kz_werte)
            for kz_name, kz_werte in klasse_raw["kennzahlen"].items()
        }
        umsatzklassen.append(
            Umsatzklasse(
                key=klasse_raw["key"],
                label=klasse_raw["label"],
                umsatz_von=klasse_raw["umsatz_von"],
                umsatz_bis=klasse_raw["umsatz_bis"],
                kennzahlen=kennzahlen,
            )
        )

    # Umsatzklassen nach umsatz_von sortieren, damit passende_umsatzklasse()
    # sich nicht auf die Reihenfolge in der JSON-Datei verlassen muss.
    umsatzklassen.sort(key=lambda k: k.umsatz_von)

    return BenchmarkDaten(
        branche=rohdaten["branche"],
        gewerbekennzahl_wz2008=rohdaten["gewerbekennzahl_wz2008"],
        quelle=rohdaten["quelle"],
        stand=rohdaten["stand"],
        umsatzklassen=umsatzklassen,
    )


# ---------------------------------------------------------------------------
# Kennzahlenberechnung aus BWA-Werten
# ---------------------------------------------------------------------------

def _pruefe_benoetigte_keys(kennzahl: str, werte: dict[str, float]) -> None:
    """
    Fail-fast: Bricht mit einer praezisen Fehlermeldung ab, wenn Positionen
    fehlen, die fuer die Berechnung zwingend benoetigt werden - statt
    stillschweigend mit 0.0 weiterzurechnen und einen falschen Reingewinn
    auszuweisen. Das ist der wichtigste Unterschied zu einer "quick and dirty"
    Implementierung: ein fehlender Wert darf NIE unbemerkt bleiben, weil er
    sich direkt auf eine steuerlich/betriebswirtschaftlich relevante Aussage
    auswirkt.

    Sonderfall UMSATZ_BASIS_KEY: Manche Formate (z.B. SMD) weisen keine eigene
    Summenzeile 'summe_erloese' aus, sondern nur die Einzelpositionen
    (UMSATZ_BASIS_FALLBACK_KEYS). _umsatz() rekonstruiert die Summe in diesem
    Fall additiv. Diese Pruefung muss denselben Fallback kennen, sonst schlaegt
    sie faelschlich fehl, obwohl der Umsatz sehr wohl berechenbar ist.
    """
    definition = KENNZAHLEN_MAPPING[kennzahl]
    fehlende = []
    for benoetigter_key in definition["benoetigt"]:
        if benoetigter_key == UMSATZ_BASIS_KEY:
            umsatz_verfuegbar = (
                UMSATZ_BASIS_KEY in werte
                or any(k in werte for k in UMSATZ_BASIS_FALLBACK_KEYS)
            )
            if not umsatz_verfuegbar:
                fehlende.append(
                    f"{UMSATZ_BASIS_KEY} (auch nicht ueber Fallback "
                    f"{UMSATZ_BASIS_FALLBACK_KEYS} rekonstruierbar)"
                )
        elif benoetigter_key not in werte:
            fehlende.append(benoetigter_key)
    # "optional"-Keys werden bewusst NICHT geprueft: ihr Fehlen ist fachlich
    # gueltig (siehe Kommentar bei KENNZAHLEN_MAPPING) und wird von den
    # Formel-Funktionen selbst per .get(key, 0.0) abgefangen.

    if fehlende:
        raise KeyError(
            f"Kennzahl '{kennzahl}' kann nicht berechnet werden - "
            f"folgende BWAPosition-Keys fehlen in den uebergebenen Werten: "
            f"{fehlende}.\n"
            f"Benoetigt werden insgesamt: {definition['benoetigt']}.\n"
            f"Pruefe, ob diese Positionen im BWA-Format vorhanden sind und "
            f"korrekt in lexware_parser.py's BEZEICHNUNG_MAPPING abgebildet werden."
        )


def berechne_kennzahlen(werte: dict[str, float]) -> dict[str, float]:
    """
    Berechnet alle in KENNZAHLEN_MAPPING definierten Kennzahlen als Prozentsatz
    des wirtschaftlichen Umsatzes (kompatibel zur Richtsatzsammlung).

    werte: dict[kanonischer_key, wert] fuer EINE Periode (z.B. alle Werte
           einer Jahressumme wie 'KUM_M12_2025' oder 'Q1-Q4_2022').
           Der Aufrufer (main.py) ist dafuer verantwortlich, aus den
           BWAPosition.werte-dicts die Werte EINER konkreten Period
           herauszufiltern, bevor diese Funktion aufgerufen wird - diese
           Funktion selbst kennt keine Period-Objekte, nur flache dicts.

    Gibt {"rohgewinn_ii": 62.3, "halbreingewinn": 41.0, "reingewinn": 28.7}
    zurueck (Werte in Prozent, nicht in Euro).
    """
    umsatz = _umsatz(werte)
    if umsatz == 0:
        raise ZeroDivisionError(
            "Wirtschaftlicher Umsatz ist 0 - Kennzahlen koennen nicht als "
            "Prozentsatz vom Umsatz berechnet werden (Division durch Null). "
            "Pruefe, ob die uebergebene Periode tatsaechlich Umsatzdaten enthaelt "
            "(z.B. keine Monatsperiode ausserhalb der Geschaeftstaetigkeit)."
        )

    ergebnisse: dict[str, float] = {}
    for kennzahl_name, definition in KENNZAHLEN_MAPPING.items():
        _pruefe_benoetigte_keys(kennzahl_name, werte)
        betrag = definition["formel"](werte)
        ergebnisse[kennzahl_name] = (betrag / umsatz) * 100

    return ergebnisse


# ---------------------------------------------------------------------------
# Oeffentliche Hauptfunktion: Vergleich Mandant vs. Richtsatzsammlung
# ---------------------------------------------------------------------------

def vergleiche_mit_benchmark(
    werte: dict[str, float],
    benchmark: BenchmarkDaten,
) -> list[KennzahlErgebnis]:
    """
    Berechnet die Kennzahlen eines Mandanten aus den BWA-Werten EINER
    Jahresperiode und ordnet sie gegen die passende Umsatzklasse der
    Richtsatzsammlung ein.

    werte: dict[kanonischer_key, wert] fuer eine Jahresperiode (Aggregat!).
           Monatswerte einzeln gegen die Richtsatzsammlung zu vergleichen
           ergibt keinen Sinn, weil die Richtsaetze auf Jahresbasis kalkuliert
           sind (z.B. saisonale Schwankungen bei Aussenreinigung im Winter).
           main.py muss sicherstellen, dass hier eine Period mit
           is_aggregate=True verwendet wird.

    Gibt eine Liste von KennzahlErgebnis zurueck, sortiert in der
    Reihenfolge von KENNZAHLEN_MAPPING (rohgewinn_ii, halbreingewinn,
    reingewinn).
    """
    umsatz = _umsatz(werte)
    umsatzklasse = benchmark.passende_umsatzklasse(umsatz)
    berechnete_kennzahlen = berechne_kennzahlen(werte)

    ergebnisse: list[KennzahlErgebnis] = []
    for kennzahl_name, wert_prozent in berechnete_kennzahlen.items():
        if kennzahl_name not in umsatzklasse.kennzahlen:
            raise KeyError(
                f"Kennzahl '{kennzahl_name}' wird berechnet, ist aber in der "
                f"Benchmark-Datei fuer Umsatzklasse '{umsatzklasse.key}' "
                f"(Branche '{benchmark.branche}') nicht definiert. "
                f"Pruefe die JSON-Struktur in noble_cockpit/benchmarks/data/."
            )
        rahmensatz = umsatzklasse.kennzahlen[kennzahl_name]
        ergebnisse.append(
            KennzahlErgebnis(
                kennzahl=kennzahl_name,
                wert_prozent=round(wert_prozent, 2),
                rahmensatz=rahmensatz,
                einordnung=rahmensatz.einordnen(wert_prozent),
                umsatzklasse=umsatzklasse,
            )
        )

    return ergebnisse


# ---------------------------------------------------------------------------
# Erklaertexte fuer die Kennzahlen (fuer PDF-Bericht, Schritt 5: pdf_report.py)
# ---------------------------------------------------------------------------
#
# Zweck: Nicht jeder Mandant weiss, was "Rohgewinn II" oder "Halbreingewinn"
# bedeutet. Diese Texte werden zentral hier gepflegt, damit pdf_report.py sie
# 1:1 uebernehmen kann, ohne fachliche Definitionen im Report-Layer duplizieren
# zu muessen. Bei Aenderungen an der Berechnungslogik (KENNZAHLEN_MAPPING)
# MUESSEN diese Texte mitgeprueft werden, ob sie noch stimmen.

KENNZAHLEN_ERKLAERUNGEN: dict[str, str] = {
    "rohgewinn_ii": (
        "Der Rohgewinn II zeigt, wie viel vom Umsatz uebrig bleibt, nachdem "
        "die direkten Personalkosten (Loehne fuer die eigentliche "
        "Reinigungsleistung) abgezogen wurden. Ein niedriger Wert bedeutet: "
        "Ein grosser Teil des Umsatzes fliesst direkt in Loehne - typisch "
        "fuer die personalintensive Reinigungsbranche."
    ),
    "halbreingewinn": (
        "Der Halbreingewinn zieht vom Rohgewinn II zusaetzlich die "
        "laufenden allgemeinen Betriebskosten ab - etwa Fahrzeuge, Miete, "
        "Versicherungen, Werbung, Buerobedarf. Er zeigt, was nach den "
        "'gewoehnlichen' Betriebsausgaben vom Umsatz uebrig bleibt."
    ),
    "reingewinn": (
        "Der Reingewinn ist der Gewinn vor Steuern: Alle Kosten sind hier "
        "bereits abgezogen, inklusive Rechts- und Beratungskosten sowie "
        "Abschreibungen. Das ist der Betrag, der wirtschaftlich am Ende "
        "tatsaechlich uebrig bleibt, bevor Steuern gezahlt werden."
    ),
}

# ---------------------------------------------------------------------------
# Zusaetzliche Kontext-Referenzen (nicht amtlich, nur zur Einordnung)
# ---------------------------------------------------------------------------
#
# Diese Werte stammen NICHT aus der Richtsatzsammlung, sondern aus oeffentlich
# zugaenglichen Geschaeftsberichten grosser Facility-Service-Konzerne. Sie
# dienen ausschliesslich als zusaetzlicher Kontext (z.B. "ist eine hohe
# Personalkostenquote branchenueblich?") und duerfen NIEMALS mit den
# Rahmensaetzen aus der Richtsatzsammlung verrechnet oder gleichgesetzt
# werden - andere Bezugsgroesse, anderer Konzernmix (Reinigung + Sicherheit +
# Gebaeudetechnik + Catering), keine Umsatzklassen-Staffelung.
KONTEXT_REFERENZEN: dict[str, dict] = {
    "personalaufwandsquote_facility_service": {
        "wert_prozent": 59.4,
        "quelle": "AVECO Holding Geschaeftsbericht 2024, WISAG Facility Service Konzern",
        "hinweis": (
            "Bezieht sich auf den GESAMTEN Facility-Service-Konzern (Reinigung, "
            "Sicherheit, Gebaeudetechnik, Catering), nicht isoliert auf "
            "Gebaeudereinigung. Bei reinen Reinigungsbetrieben liegt die "
            "tatsaechliche Personalkostenquote erfahrungsgemaess eher hoeher, "
            "da Reinigung ueberdurchschnittlich personalintensiv ist."
        ),
    },
}


# ---------------------------------------------------------------------------
# Kostenstruktur-Anteilsberechnung (Hauptposten-Vergleich innerhalb des
# Mandanten selbst - unabhaengig von externen Benchmarks)
# ---------------------------------------------------------------------------
#
# Zeigt dem Mandanten, welchen Anteil JEDE Kostenposition an den GESAMTEN
# Betriebsausgaben hat. Das beantwortet "wo verliere ich am meisten Geld"
# unabhaengig davon, ob es dafuer eine externe Vergleichszahl gibt.

KOSTENSTRUKTUR_KEYS = [
    "personalkosten",
    "raumkosten",
    "fahrzeugkosten",
    "werbe_reisekosten",
    "steuern_versicherungen",
    "buerobedarf",
    "porto_telefon",
    "instandhaltung",
    "verschiedene_kosten",
    "kosten_warenabgabe",
    "rechts_beratungskosten",
    "abschreibungen",
    "sonstige_aufwendungen",
]


@dataclass(frozen=True)
class KostenpositionAnteil:
    position: str
    betrag: float
    anteil_an_gesamtkosten_prozent: float
    anteil_an_umsatz_prozent: float


def berechne_kostenstruktur(werte: dict[str, float]) -> list[KostenpositionAnteil]:
    """
    Berechnet fuer jede in KOSTENSTRUKTUR_KEYS gelistete Position ihren Anteil
    an den Gesamtkosten UND ihren Anteil am Umsatz. Ergebnis ist absteigend
    nach Betrag sortiert - die grosste Kostenposition steht oben, damit der
    Mandant im Bericht sofort sieht, wo das meiste Geld hinfliesst.

    Positionen mit Betrag 0.0 (nicht vorhanden oder tatsaechlich 0) werden
    NICHT ausgeschlossen, damit z.B. "wir hatten dieses Jahr keine
    Fahrzeugkosten" ebenfalls sichtbar bleibt.
    """
    umsatz = _umsatz(werte)
    gesamtkosten = sum(werte.get(k, 0.0) for k in KOSTENSTRUKTUR_KEYS)

    anteile = []
    for position in KOSTENSTRUKTUR_KEYS:
        betrag = werte.get(position, 0.0)
        anteil_gesamtkosten = (betrag / gesamtkosten * 100) if gesamtkosten else 0.0
        anteil_umsatz = (betrag / umsatz * 100) if umsatz else 0.0
        anteile.append(
            KostenpositionAnteil(
                position=position,
                betrag=round(betrag, 2),
                anteil_an_gesamtkosten_prozent=round(anteil_gesamtkosten, 2),
                anteil_an_umsatz_prozent=round(anteil_umsatz, 2),
            )
        )

    anteile.sort(key=lambda a: a.betrag, reverse=True)
    return anteile


# ---------------------------------------------------------------------------
# Interne Benchmark: wachsende, eigene Datenbasis aus tatsaechlichen Mandanten
# ---------------------------------------------------------------------------
#
# Zweck: Mit jedem neuen Mandanten (in derselben Branche) wird die eigene
# Vergleichsbasis praeziser - unabhaengig von externen Quellen. Die
# Richtsatzsammlung bleibt die "amtliche" Referenz, die interne Statistik
# wird als ZUSAETZLICHER, eigener Vergleichswert ausgewiesen, sobald
# genuegend Datenpunkte vorliegen.
#
# Speicherformat: EINE JSON-Datei pro Branche unter
# noble_cockpit/benchmarks/data/interne_benchmark_<branche_datei>.json,
# als Liste von Beobachtungen (append-only). Bewusst kein Ueberschreiben
# vorhandener Eintraege bei erneuter Auswertung desselben Mandanten/Jahres -
# das wird ueber (mandant_id, jahr) als Duplikatschluessel verhindert.
#
# WICHTIG - Datenschutz/Mandantengeheimnis: Es wird NUR eine anonyme
# mandant_id (z.B. Hash oder Kuerzel, von main.py vergeben) gespeichert,
# NIEMALS Klarname, Adresse oder andere identifizierende Merkmale. Diese
# Datei darf NICHT ins Git-Repository - sie enthaelt reale Betriebsdaten
# von Mandanten und gehoert in .gitignore (analog zu data/bwa_samples/).

MIN_BEOBACHTUNGEN_FUER_INTERNE_STATISTIK = 3


@dataclass(frozen=True)
class MandantBeobachtung:
    mandant_id: str
    jahr: int
    umsatzklasse_key: str
    umsatz: float
    kennzahlen_prozent: dict[str, float]


@dataclass(frozen=True)
class InterneStatistik:
    anzahl_beobachtungen: int
    mittelwert: float
    minimum: float
    maximum: float


def _interne_benchmark_pfad(branche_datei: str) -> Path:
    return DATA_DIR / f"interne_benchmark_{branche_datei}.json"


def speichere_mandant_beobachtung(
    branche_datei: str,
    beobachtung: MandantBeobachtung,
) -> None:
    """
    Haengt eine neue Mandanten-Beobachtung an die interne Benchmark-Datei an.
    Idempotent bei gleichem (mandant_id, jahr): ein bereits vorhandener
    Eintrag fuer denselben Mandanten/Jahr wird ERSETZT (z.B. bei erneuter,
    korrigierter Auswertung), nicht dupliziert.
    """
    pfad = _interne_benchmark_pfad(branche_datei)
    beobachtungen: list[dict] = []
    if pfad.exists():
        with open(pfad, encoding="utf-8") as f:
            beobachtungen = json.load(f)

    beobachtungen = [
        b for b in beobachtungen
        if not (b["mandant_id"] == beobachtung.mandant_id and b["jahr"] == beobachtung.jahr)
    ]
    beobachtungen.append(
        {
            "mandant_id": beobachtung.mandant_id,
            "jahr": beobachtung.jahr,
            "umsatzklasse_key": beobachtung.umsatzklasse_key,
            "umsatz": beobachtung.umsatz,
            "kennzahlen_prozent": beobachtung.kennzahlen_prozent,
        }
    )

    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(beobachtungen, f, ensure_ascii=False, indent=2)


def lade_interne_beobachtungen(branche_datei: str) -> list[MandantBeobachtung]:
    pfad = _interne_benchmark_pfad(branche_datei)
    if not pfad.exists():
        return []
    with open(pfad, encoding="utf-8") as f:
        rohdaten = json.load(f)
    return [
        MandantBeobachtung(
            mandant_id=b["mandant_id"],
            jahr=b["jahr"],
            umsatzklasse_key=b["umsatzklasse_key"],
            umsatz=b["umsatz"],
            kennzahlen_prozent=b["kennzahlen_prozent"],
        )
        for b in rohdaten
    ]


def berechne_interne_statistik(
    branche_datei: str,
    umsatzklasse_key: str,
    kennzahl: str,
) -> Optional[InterneStatistik]:
    """
    Berechnet Mittelwert/Min/Max ueber alle bisherigen Mandanten-Beobachtungen
    derselben Umsatzklasse fuer eine Kennzahl.

    Gibt None zurueck, wenn weniger als MIN_BEOBACHTUNGEN_FUER_INTERNE_STATISTIK
    Datenpunkte vorliegen - bei z.B. nur 1-2 Mandanten waere ein "Durchschnitt"
    statistisch nicht aussagekraeftig und wuerde dem Berater eine falsche
    Praezision vorspiegeln. Diese Schwelle ist bewusst konservativ, kann in
    main.py bei Bedarf ueberschrieben werden, indem die Konstante direkt
    importiert und temporaer gesetzt wird.
    """
    beobachtungen = lade_interne_beobachtungen(branche_datei)
    relevante_werte = [
        b.kennzahlen_prozent[kennzahl]
        for b in beobachtungen
        if b.umsatzklasse_key == umsatzklasse_key and kennzahl in b.kennzahlen_prozent
    ]

    if len(relevante_werte) < MIN_BEOBACHTUNGEN_FUER_INTERNE_STATISTIK:
        return None

    return InterneStatistik(
        anzahl_beobachtungen=len(relevante_werte),
        mittelwert=round(sum(relevante_werte) / len(relevante_werte), 2),
        minimum=round(min(relevante_werte), 2),
        maximum=round(max(relevante_werte), 2),
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))

    from noble_cockpit.parser.lexware_parser import parse_bwa_pdf

    pdf_pfad = _Path(__file__).resolve().parent.parent.parent / "data" / "bwa_samples" / "BWA_2024_SMD.pdf"
    if not pdf_pfad.exists():
        print(f"Test-PDF nicht gefunden: {pdf_pfad}")
        sys.exit(1)

    positionen = parse_bwa_pdf(pdf_pfad)

    ziel_period_label = "KUM_M12_2025"
    werte_fuer_period: dict[str, float] = {}
    for pos in positionen:
        for period, wert in pos.werte.items():
            if period.label == ziel_period_label:
                werte_fuer_period[pos.kanonischer_key] = wert

    if not werte_fuer_period:
        print(f"Keine Werte fuer Periode '{ziel_period_label}' gefunden.")
        sys.exit(1)

    benchmark = load_benchmark("gebaeudereinigung")
    ergebnisse = vergleiche_mit_benchmark(werte_fuer_period, benchmark)

    print(f"Branche: {benchmark.branche} | Quelle: {benchmark.quelle}\n")
    for ergebnis in ergebnisse:
        print(
            f"{ergebnis.kennzahl:16s} | Mandant: {ergebnis.wert_prozent:6.2f}% "
            f"| Richtsatz ({ergebnis.umsatzklasse.label}): "
            f"{ergebnis.rahmensatz.min:.0f}-{ergebnis.rahmensatz.max:.0f}% "
            f"(Ø {ergebnis.rahmensatz.durchschnitt:.0f}%) "
            f"| Einordnung: {ergebnis.einordnung}"
        )