"""
rule_engine.py
Deterministische Regel-Engine für das NobleCockpit.
Wertet BWA-Kennzahlen gegen Benchmarks aus und erzeugt priorisierte Handlungsempfehlungen.
"""

from dataclasses import dataclass
from typing import Callable, List, Dict, Tuple, Any

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
    # Die Logik wird als Callable definiert: Nimmt BWA-Daten und Benchmark, gibt (is_triggered, evidence_string) zurück
    condition: Callable[[Dict[str, float], Dict[str, Dict[str, float]]], Tuple[bool, str]]

@dataclass
class AusgeloesteRegel:
    rule: Rule
    evidence: str

def get_value(bwa_data: Dict[str, float], fallback_keys: List[str]) -> float:
    """Holt den Wert sicher aus der BWA, probiert alternative kanonische Keys."""
    for key in fallback_keys:
        if key in bwa_data:
            return bwa_data[key]
    return 0.0

# ---------------------------------------------------------------------------
# Regel-Logik (Branch: Gebäudereinigung)
# ---------------------------------------------------------------------------

def check_rohgewinn_ii(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese", "summe_betriebseinnahmen"])
    rohertrag = get_value(bwa_data, ["rohertrag_betrieblich", "summe_rohertrag"])
    
    if erloese <= 0:
        return False, ""
        
    quote = (rohertrag / erloese) * 100
    
    # Zugriff über Objekt-Attribut statt .get()
    rg_bm = benchmark.get("rohgewinn_ii") if isinstance(benchmark, dict) else getattr(benchmark, "rohgewinn_ii", None)
    bm_schnitt = rg_bm.durchschnitt if rg_bm and hasattr(rg_bm, "durchschnitt") else 0.0
    
    if bm_schnitt > 0 and quote < bm_schnitt:
        return True, f"Rohgewinn II Quote liegt bei {quote:.1f}% (BMF-Schnitt: {bm_schnitt:.1f}%)."
    return False, ""

def check_verwaltungskosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    rohertrag = get_value(bwa_data, ["rohertrag_betrieblich", "summe_rohertrag"])
    personal = get_value(bwa_data, ["personalkosten"])
    
    if erloese <= 0:
        return False, ""
        
    halbreingewinn = rohertrag - personal
    rg_quote = (rohertrag / erloese) * 100
    hrg_quote = (halbreingewinn / erloese) * 100
    bwa_spread = rg_quote - hrg_quote
    
    rg_bm = benchmark.get("rohgewinn_ii") if isinstance(benchmark, dict) else getattr(benchmark, "rohgewinn_ii", None)
    hrg_bm = benchmark.get("halbreingewinn") if isinstance(benchmark, dict) else getattr(benchmark, "halbreingewinn", None)
    
    bm_rg = rg_bm.durchschnitt if rg_bm and hasattr(rg_bm, "durchschnitt") else 0.0
    bm_hrg = hrg_bm.durchschnitt if hrg_bm and hasattr(hrg_bm, "durchschnitt") else 0.0
    bm_spread = bm_rg - bm_hrg
    
    if bm_spread > 0 and bwa_spread > (bm_spread * 1.1):
        return True, f"Verwaltungskosten-Spread liegt bei {bwa_spread:.1f}% (Branchenschnitt: {bm_spread:.1f}%)."
    return False, ""

def check_reingewinn_warnung(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    ergebnis = get_value(bwa_data, ["vorlaeufiges_ergebnis"])
    
    if erloese <= 0:
        return False, ""
        
    quote = (ergebnis / erloese) * 100
    rw_bm = benchmark.get("reingewinn") if isinstance(benchmark, dict) else getattr(benchmark, "reingewinn", None)
    bm_min = rw_bm.min if rw_bm and hasattr(rw_bm, "min") else 0.0
    
    if quote <= (bm_min * 1.2):
        return True, f"Reingewinn-Quote liegt kritisch bei {quote:.1f}% (BMF-Minimum: {bm_min:.1f}%)."
    return False, ""

def check_personalkosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    personal = get_value(bwa_data, ["personalkosten"])
    if erloese <= 0:
        return False, ""
    quote = (personal / erloese) * 100
    
    ref = benchmark.get("kostenstruktur_referenz", {}).get("grenzwerte_prozent_vom_umsatz", {})
    limit = ref.get("personalkosten", {}).get("max", 70.0)
    
    if quote > limit:
        return True, f"Personalkostenquote liegt kritisch bei {quote:.1f}% (Praxis-Limit: max. {limit}%)."
    return False, ""

def check_fahrzeugkosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    fahrzeuge = get_value(bwa_data, ["fahrzeugkosten"])
    if erloese <= 0:
        return False, ""
    quote = (fahrzeuge / erloese) * 100
    
    ref = benchmark.get("kostenstruktur_referenz", {}).get("grenzwerte_prozent_vom_umsatz", {})
    limit = ref.get("fahrzeugkosten", {}).get("max", 8.0)
    
    if quote > limit:
        return True, f"Fahrzeugkostenquote beträgt {quote:.1f}% (Praxis-Limit: max. {limit}%)."
    return False, ""

def check_raumkosten(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    raum = get_value(bwa_data, ["raumkosten"])
    if erloese <= 0:
        return False, ""
    quote = (raum / erloese) * 100
    
    ref = benchmark.get("kostenstruktur_referenz", {}).get("grenzwerte_prozent_vom_umsatz", {})
    limit = ref.get("raumkosten", {}).get("max", 4.0)
    
    if quote > limit:
        return True, f"Raumkostenquote liegt bei {quote:.1f}% (Praxis-Limit: max. {limit}%)."
    return False, ""

def check_fremdleistungen(bwa_data: Dict[str, float], benchmark: Dict[str, Any]) -> Tuple[bool, str]:
    erloese = get_value(bwa_data, ["erloese_betrieblich", "summe_erloese"])
    fremd = get_value(bwa_data, ["fremdleistungen"])
    if erloese <= 0:
        return False, ""
    quote = (fremd / erloese) * 100
    
    ref = benchmark.get("kostenstruktur_referenz", {}).get("grenzwerte_prozent_vom_umsatz", {})
    limit = ref.get("fremdleistungen", {}).get("max", 15.0)
    
    if quote > limit:
        return True, f"Subunternehmer-Quote liegt bei {quote:.1f}% (Praxis-Limit: max. {limit}%)."
    return False, ""

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

def evaluate_bwa(bwa_data: Dict[str, float], benchmark_data: Dict[str, Dict[str, float]]) -> List[AusgeloesteRegel]:
    """Wertet ein dict von BWA-Werten gegen die Benchmark-Daten aus."""
    ausgeloeste_regeln = []
    
    for rule in ruleset_gebaeudereinigung:
        is_triggered, evidence = rule.condition(bwa_data, benchmark_data)
        if is_triggered:
            ausgeloeste_regeln.append(AusgeloesteRegel(rule=rule, evidence=evidence))
            
    # Sortiere nach Priorität (1 ist am wichtigsten)
    return sorted(ausgeloeste_regeln, key=lambda x: x.rule.priority)