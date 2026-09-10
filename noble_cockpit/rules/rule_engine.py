"""
rule_engine.py
Deterministische Regel-Engine fuer das NobleCockpit.
Wertet BWA-Kennzahlen gegen Benchmarks aus und erzeugt priorisierte
Handlungsempfehlungen inkl. geschätztem Potenzial (als Range, nie als Zusage).

Architekturprinzip (Roadmap v7.1, Kap. 4):
Das LLM formuliert - die Fachlogik entscheidet deterministisch.
Keine Regel ohne confidence, version, evidence, Fallback-Logik.

Benchmark-Zugriff: Der Benchmark kann als DICT ({key: {min,durchschnitt,max}})
oder als Objekt (Rahmensatz-Attribute) uebergeben werden. Die Helper
`benchmark_objekt()` / `benchmark_wert()` abstrahieren beides, damit Regeln
nicht an eine konkrete Datenstruktur gebunden sind.
"""

from dataclasses import dataclass
from typing import Callable, List, Dict, Tuple, Any, Optional

@dataclass
class Rule:
    key: str
    priority: int
    possible_causes: List[str]
    recommendation: str
    confidence: float
    owner: str
    branch: str
    fallback_if_no_benchmark: str
    disclaimer_required: bool
    version: str
    # Die Logik wird als Callable definiert: Nimmt BWA-Daten und Benchmark,
    # gibt (is_triggered, evidence_string, potenzial_text) zurueck.
    condition: Callable[[Dict[str, float], Dict[str, Any]], Tuple[bool, str, str]]

@dataclass
class AusgeloesteRegel:
    rule: Rule
    evidence: str
    potenzial: str = ""       # Langform fuer Aktionsplan: "Geschätztes Potenzial: X-Y EUR/Jahr"
    potenzial_kurz: str = ""  # Kurzform fuer Feuerwehr-Streifen S.2: "Potenzial: X-Y EUR/Jahr"

# ---------------------------------------------------------------------------
# Benchmark-Zugriff (robust gegen dict UND Objekt)
# ---------------------------------------------------------------------------

def get_value(bwa_data: Dict[str, float], fallback_keys: List[str]) -> float:
    """Holt den Wert sicher aus der BWA, probiert alternative kanonische Keys."""
    for key in fallback_keys:
        if key in bwa_data:
            return bwa_data[key]
    return 0.0


def benchmark_objekt(benchmark: Any, key: str) -> Optional[Any]:
    """Holt das Benchmark-Teilobjekt (Rahmensatz) robust aus dict oder Objekt."""
    if isinstance(benchmark, dict):
        return benchmark.get(key)
    return getattr(benchmark, key, None)


def benchmark_wert(benchmark: Any, key: str, feld: str) -> float:
    """
    Liest einen Zahlenwert (min / durchschnitt / max) aus einem
    Benchmark-Rahmensatz - gleichgueltig, ob er als dict
    {"min": 45.0, ...} oder als Objekt (Rahmensatz) vorliegt.
    Gibt 0.0 zurueck, wenn nichts lesbar ist (Regeln pruefen > 0).
    """
    obj = benchmark_objekt(benchmark, key)
    if obj is None:
        return 0.0
    if isinstance(obj, dict):
        return float(obj.get(feld, 0.0))
    return float(getattr(obj, feld, 0.0))


def _eur(betrag: float) -> str:
    """Formatiert einen Euro-Betrag deutsch: 12345 -> '12.345'."""
    return f"{betrag:,.0f}".replace(",", ".")


def _potenzial_text(potenzial_eur: float) -> str:
    """
    Formuliert ein geschätztes Einspar-/Verbesserungspotenzial als Range.
    Roadmap-Kap. 8 (Sprachprinzipien): IMMER Range, nie exakte Zusage.
    Bei Betraegen unter 500 EUR wird bewusst KEIN Potenzial ausgewiesen -
    die Praezision waere vorgespiegelt.
    """
    if potenzial_eur <= 500.0:
        return ""
    unten = potenzial_eur * 0.8
    oben = potenzial_eur * 1.2
    return f"Geschätztes Potenzial: {_eur(unten)}–{_eur(oben)} €/Jahr"


def _potenzial_kurz(potenzial_eur: float) -> str:
    """
    Kurzform des Potenzials (eine Zeile) fuer den Feuerwehr-Streifen auf
    Seite 2 des Reports. Gerundet auf 100 EUR, damit der Streifen lesbar
    bleibt - die genaue Range steht im Aktionsplan (Langform).
    """
    if potenzial_eur <= 500.0:
        return ""
    unten = _eur(round(potenzial_eur * 0.8, -2))
    oben = _eur(round(potenzial_eur * 1.2, -2))
    return f"Potenzial: {unten}–{oben} €/Jahr"

# ---------------------------------------------------------------------------
# Regel-Logik (Branch: Gebäudereinigung)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Regel-Logik (Branch: Gebaeudereinigung)
# Alle Checks liefern: (is_triggered, evidence, potenzial_text)
# Potenzial-Logik: Differenz zwischen Ist- und Ziel-Quote x Umsatz,
# bewusst als 0.8x-1.2x-Range (vgl. Roadmap: 'Geschätztes Potenzial: X-Y EUR').
# ---------------------------------------------------------------------------

def check_rohgewinn_ii(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese", "summe_betriebseinnahmen"])
    rohertrag = get_value(bwa_data, ["rohertrag_betrieblich", "summe_rohertrag"])

    if erloese <= 0:
        return False, "", ""

    quote = (rohertrag / erloese) * 100
    bm_schnitt = benchmark_wert(benchmark, "rohgewinn_ii", "durchschnitt")

    if bm_schnitt > 0 and quote < bm_schnitt:
        evidence = (
            f"Von 100 € Umsatz bleiben nach den Löhnen nur {quote:.1f} € übrig - "
            f"der durchschnittliche Vergleichsbereich liegt bei {bm_schnitt:.1f} € "
            f"(BMF Richtsatzsammlung)."
        )
        potenzial = _potenzial_text((bm_schnitt - quote) / 100.0 * erloese)
        return True, evidence, potenzial
    return False, "", ""


def check_verwaltungskosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    rohertrag = get_value(bwa_data, ["rohertrag_betrieblich", "summe_rohertrag"])
    personal = get_value(bwa_data, ["personalkosten"])

    if erloese <= 0:
        return False, "", ""

    halbreingewinn = rohertrag - personal
    rg_quote = (rohertrag / erloese) * 100
    hrg_quote = (halbreingewinn / erloese) * 100
    bwa_spread = rg_quote - hrg_quote

    bm_rg = benchmark_wert(benchmark, "rohgewinn_ii", "durchschnitt")
    bm_hrg = benchmark_wert(benchmark, "halbreingewinn", "durchschnitt")
    bm_spread = bm_rg - bm_hrg

    if bm_spread > 0 and bwa_spread > (bm_spread * 1.1):
        evidence = (
            f"Der Unterschied zwischen 'nach Löhnen' und 'nach allen laufenden "
            f"Kosten' liegt bei {bwa_spread:.1f} € je 100 € Umsatz - der "
            f"Vergleichsbereich bei {bm_spread:.1f} €. Büro, Fuhrpark und "
            f"Verwaltung kosten also überdurchschnittlich viel."
        )
        potenzial = _potenzial_text((bwa_spread - bm_spread) / 100.0 * erloese)
        return True, evidence, potenzial
    return False, "", ""


def check_reingewinn_warnung(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    ergebnis = get_value(bwa_data, ["vorlaeufiges_ergebnis"])

    if erloese <= 0:
        return False, "", ""

    quote = (ergebnis / erloese) * 100
    bm_min = benchmark_wert(benchmark, "reingewinn", "min")

    if quote <= (bm_min * 1.2):
        evidence = (
            f"Was am Ende des Jahres übrig bleibt, sind nur {quote:.1f} € je "
            f"100 € Umsatz - akut nah am Branchen-Minimum von {bm_min:.1f} €."
        )
        potenzial = _potenzial_text(max(bm_min - quote, 0.0) / 100.0 * erloese)
        return True, evidence, potenzial
    return False, "", ""


def _kostenquote_check(
    bwa_data: Dict[str, float],
    benchmark: Dict[str, Any],
    kosten_key: str,
    benchmark_key: str,
) -> Tuple[bool, str, str]:
    """
    Generischer Check fuer Kostenquoten mit Praxis-Limit aus der
    Benchmark-JSON (kostenstruktur_referenz.grenzwerte_prozent_vom_umsatz).
    """
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    kosten = get_value(bwa_data, [kosten_key])
    if erloese <= 0:
        return False, "", ""

    quote = (kosten / erloese) * 100
    ref: Dict[str, Any] = {}
    if isinstance(benchmark, dict):
        ref = benchmark.get("kostenstruktur_referenz", {}).get(
            "grenzwerte_prozent_vom_umsatz", {}
        )
    limit = float(ref.get(benchmark_key, {}).get("max", 0.0)) if isinstance(ref, dict) else 0.0
    if limit <= 0:
        return False, "", ""

    if quote > limit:
        evidence = (
            f"Diese Kostenstelle liegt bei {quote:.1f} % vom Umsatz - "
            f"erfahrene Betriebe geben dafür meist max. {limit:.0f} % aus."
        )
        potenzial = _potenzial_text((quote - limit) / 100.0 * erloese)
        return True, evidence, potenzial
    return False, "", ""


def check_personalkosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str, str]:
    return _kostenquote_check(bwa_data, benchmark, "personalkosten", "personalkosten")


def check_fahrzeugkosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str, str]:
    return _kostenquote_check(bwa_data, benchmark, "fahrzeugkosten", "fahrzeugkosten")


def check_raumkosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str, str]:
    return _kostenquote_check(bwa_data, benchmark, "raumkosten", "raumkosten")


def check_fremdleistungen(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str, str]:
    return _kostenquote_check(bwa_data, benchmark, "fremdleistungen", "fremdleistungen")


# ---------------------------------------------------------------------------
# Regel-Set Registrierung
# ---------------------------------------------------------------------------

ruleset_gebaeudereinigung = [
    Rule(
        key="operative_effizienz_rg_ii",
        priority=1,
        possible_causes=["Stundensätze zu niedrig", "Unproduktive Zeiten (Fahrten/Rüstung) zu hoch"],
        recommendation="Preiskalkulation der laufenden Verträge prüfen und unproduktive Personalstunden reduzieren.",
        confidence=0.85,
        owner="cost_rules_v1",
        branch="gebaeudereinigung",
        fallback_if_no_benchmark="show_hint_only",
        disclaimer_required=True,
        version="2026-08",
        condition=check_rohgewinn_ii
    ),
    Rule(
        key="verwaltungskosten_spread",
        priority=2,
        possible_causes=["Zu teurer Fuhrpark", "Hohe Raumkosten", "Wasserkopf in der Verwaltung"],
        recommendation="Strukturkosten (Fuhrpark, Raumkosten, Versicherungen) auditieren und Leasingverträge prüfen.",
        confidence=0.80,
        owner="cost_rules_v1",
        branch="gebaeudereinigung",
        fallback_if_no_benchmark="skip",
        disclaimer_required=True,
        version="2026-08",
        condition=check_verwaltungskosten
    ),
    Rule(
        key="kritische_marge_reingewinn",
        priority=1,
        possible_causes=["Forderungsausfälle", "Strukturelle Fehlkalkulation der Gesamt-Objekte"],
        recommendation="Akutes Margenrisiko. Sofortiger Stopp von unprofitablen Objekten und striktes Forderungsmanagement einleiten.",
        confidence=0.95,
        owner="cost_rules_v1",
        branch="gebaeudereinigung",
        fallback_if_no_benchmark="skip",
        disclaimer_required=True,
        version="2026-08",
        condition=check_reingewinn_warnung
    ),
    Rule(
        key="personalkosten_kritisch",
        priority=1,
        possible_causes=["Zu viele unproduktive Stunden", "Überbesetzung", "Hoher Krankenstand"],
        recommendation="Einsatzplanung optimieren und Lohnkosten pro Objekt neu kalkulieren.",
        confidence=0.90,
        owner="cost_rules_v1",
        branch="gebaeudereinigung",
        fallback_if_no_benchmark="use_heuristic",
        disclaimer_required=True,
        version="2026-08",
        condition=check_personalkosten
    ),
    Rule(
        key="fahrzeugkosten_hoch",
        priority=2,
        possible_causes=["Unnötige Fahrten", "Teure Leasingverträge", "Fehlende GPS-Routenplanung"],
        recommendation="Fahrtenbuch-Analyse durchführen und Routenplanung der Teams straffen.",
        confidence=0.85,
        owner="cost_rules_v1",
        branch="gebaeudereinigung",
        fallback_if_no_benchmark="use_heuristic",
        disclaimer_required=False,
        version="2026-08",
        condition=check_fahrzeugkosten
    ),
    Rule(
        key="raumkosten_ineffizient",
        priority=3,
        possible_causes=["Zu großes Büro/Lager angemietet", "Ungenutzte Flächen"],
        recommendation="Prüfen, ob Lagerflächen verkleinert oder untervermietet werden können.",
        confidence=0.80,
        owner="cost_rules_v1",
        branch="gebaeudereinigung",
        fallback_if_no_benchmark="use_heuristic",
        disclaimer_required=False,
        version="2026-08",
        condition=check_raumkosten
    ),
    Rule(
        key="fremdleistungen_marge",
        priority=2,
        possible_causes=["Eigener Personalmangel", "Fehlende Spezialausrüstung (z.B. für Glasreinigung)"],
        recommendation="Subunternehmer-Einsatz reduzieren; stattdessen eigenes Personal weiterbilden.",
        confidence=0.85,
        owner="cost_rules_v1",
        branch="gebaeudereinigung",
        fallback_if_no_benchmark="use_heuristic",
        disclaimer_required=False,
        version="2026-08",
        condition=check_fremdleistungen
    )
]

# ---------------------------------------------------------------------------
# Engine Execution
# ---------------------------------------------------------------------------

def evaluate_bwa(bwa_data: Dict[str, float], benchmark_data: Dict[str, Any]) -> List[AusgeloesteRegel]:
    """Wertet ein dict von BWA-Werten gegen die Benchmark-Daten aus."""
    ausgeloeste_regeln = []

    for rule in ruleset_gebaeudereinigung:
        is_triggered, evidence, potenzial = rule.condition(bwa_data, benchmark_data)
        if is_triggered:
            ausgeloeste_regeln.append(
                AusgeloesteRegel(
                    rule=rule,
                    evidence=evidence,
                    potenzial=potenzial,
                    potenzial_kurz=_potenzial_kurz_text(potenzial),
                )
            )

    # Sortiere nach Priorität (1 ist am wichtigsten)
    return sorted(ausgeloeste_regeln, key=lambda x: x.rule.priority)


def _potenzial_kurz_text(langform: str) -> str:
    """
    Leitet die Kurzform aus der Langform ab (robust gegen Format-Aenderungen):
    "Geschätztes Potenzial: 42.101-63.152 EUR/Jahr" -> "Potenzial: 42.101-63.152 EUR/Jahr".
    """
    if not langform or ":" not in langform:
        return ""
    betrag = langform.split(":", 1)[1].strip()
    return f"Potenzial: {betrag}"
