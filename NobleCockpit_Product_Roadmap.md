# NobleCockpit – Produktroadmap v7.1
**Konsolidierte Arbeitsversion | Stand: Juni 2026**

---

## Inhaltsverzeichnis

1. [Zielbild](#1-zielbild)
2. [Ausgangslage & Validierung](#2-ausgangslage--validierung)
3. [Strategischer Grundsatz](#3-strategischer-grundsatz)
4. [Senior-Architekturprinzip](#4-senior-architekturprinzip)
5. [Betriebsmodus](#5-betriebsmodus)
6. [Marktvorteil & Burggraben](#6-marktvorteil--burggraben)
7. [Produktkern und Nutzenversprechen](#7-produktkern-und-nutzenversprechen)
8. [Layer 0 – Betriebsaudit-Report (MVP)](#8-layer-0--betriebsaudit-report-mvp)
9. [Layer 0.5 – Vertrieb](#9-layer-05--vertrieb)
10. [Layer 1 – Erweiterter Analyzer](#10-layer-1--erweiterter-analyzer)
11. [Layer 2 – NobleCockpit Basis](#11-layer-2--noblecockpit-basis)
12. [Layer 3 – Teilautomatisierung](#12-layer-3--teilautomatisierung)
13. [Layer 4 – Vertical SaaS](#13-layer-4--vertical-saas)
14. [KPI-Modul](#14-kpi-modul)
15. [Regelqualität und Evidenzsystem](#15-regelqualität-und-evidenzsystem)
16. [Benchmark-Entwicklung](#16-benchmark-entwicklung)
17. [Rechtlicher Pflicht-Layer](#17-rechtlicher-pflicht-layer)
18. [Optionales Weitergabe-Modul](#18-optionales-weitergabe-modul)
19. [Preismodell-Logik](#19-preismodell-logik)
20. [Interne Steuerungs-KPIs](#20-interne-steuerungs-kpis)
21. [Gesamtübersicht](#21-gesamtübersicht)
22. [Produkt-Matrix](#22-produkt-matrix)
23. [Erfolgswahrscheinlichkeiten](#23-erfolgswahrscheinlichkeiten)
24. [Nächste Schritte](#24-nächste-schritte)
25. [Positionierungssatz](#25-positionierungssatz)
26. [Anhang: Pflichtdokumente](#26-anhang-pflichtdokumente)

---

## 1. Zielbild

NobleCockpit ist **kein Steuerberater-Ersatz** und keine Buchhaltungssoftware.

NobleCockpit ist ein lokales bzw. später [[01_FOUNDER_OS/04_EVOLUTION/06_REFLECTION_SYSTEM|cloudfähiges Analyse- und Steuerungssystem]] für kleine Unternehmen, das BWA-/EÜR-Daten strukturiert auswertet, Kennzahlen ableitet, Auffälligkeiten erkennt, [[04_PRODUCT_OS/00_LOG_ENTRIES/2026-07-30_NOBLECOCKPIT_RULE_ENGINE|priorisierte Hinweise erzeugt und]] Ergebnisse verständlich formuliert.

**Kernpositionierung:**
- Keine steuerliche Beratung.
- Keine Rechtsberatung.
- Keine automatische Entscheidungshoheit des LLM.
- Fokus auf betriebswirtschaftliche Orientierung, Priorisierung und Kommunikation.

---

## 2. Ausgangslage & Validierung

> **Die Startvalidierung ist vorhanden.**

| Punkt | Status |
|---|---|
| Jemand hat für eine BWA-Analyse bezahlt | ✅ 100 € real erhalten |
| Der wahrgenommene Nutzen ist bestätigt | ✅ ja |
| Die Gesprächsführung funktioniert | ✅ ja |
| Zahlungsbereitschaft existiert | ✅ mindestens einmal bewiesen |

### Was diese Validierung bedeutet

Sie beweist **nicht** automatisch Product-Market-Fit.

Sie beweist aber drei wichtige Dinge:

1. Es gibt mindestens einen real zahlenden Kunden.
2. Die Leistung hat erkennbaren Wert.
3. Der Vertriebsansatz funktioniert mindestens einmal.

**Konsequenz:** Layer 0 darf direkt gebaut werden. Wiederholbarkeit und Skalierbarkeit müssen noch bewiesen werden.

---

## 3. Strategischer Grundsatz

> **Distribution → Kunden → Feedback → bessere Regeln → belastbareres Produkt**

Nicht möglichst viele [[FEATURES]] bauen.  
Nicht früh in komplexe Partner-Integrationen abdriften.  
Nicht aus einem funktionierenden Analyseprodukt zu früh eine große Plattform machen.

**Leitlinie:**
- Ein enges Kernproblem zuerst sehr gut lösen.
- Lokale Nutzbarkeit vor SaaS-Komplexität.
- Wiederholbare Wertschöpfung vor Feature-Breite.
- Optionale Module nur ergänzen, wenn ein echter Nutzungsdruck besteht.

---

## 4. Senior-Architekturprinzip

> **Das LLM formuliert. Die Fachlogik entscheidet nicht durch das LLM.**

```text
BWA / EÜR / CSV / Excel
↓
Parser
↓
Kennzahlen
↓
Regel-Engine
↓
Auffälligkeiten
↓
Ursachen-Hypothesen
↓
priorisierte Hinweise / Maßnahmen
↓
LLM formuliert verständlich
↓
PDF / Report / Monatsübersicht
```

### Warum dieser Ansatz professionell ist

- Ergebnisse bleiben reproduzierbar.
- Regeln sind testbar und versionierbar.
- Fehler lassen sich isoliert beheben.
- Die fachliche Verantwortung bleibt im deterministischen System.
- Spätere Branchenlogik kann ergänzt werden, ohne den Kern neu zu bauen.

### Regelobjekt statt harter If-Else-Ketten

```python
Rule(
    key="material_high",
    condition="materialquote > benchmark_median",
    priority=1,
    evidence="Materialquote 38% vs. Referenzwert 28%",
    possible_causes=["Einkauf", "Schwund", "Kalkulation", "Sonderauftrag"],
    recommendation="Einkaufsstruktur und Kalkulation prüfen",
    confidence=0.78,
    owner="cost_rules_v1",
    branch="allgemein",
    fallback_if_no_benchmark="show_hint_only",
    disclaimer_required=True,
    version="2026-06"
)
```

### Produktionsprinzipien

- Keine Regel ohne `confidence`.
- Keine Regel ohne `version`.
- Kein Benchmark-Fall ohne Fallback-Logik.
- Keine starke Empfehlung ohne Evidenz.
- Regeln unterhalb definierter Confidence-Schwellen werden sprachlich abgeschwächt.

---

## 5. Betriebsmodus

| Layer | Betriebsform | Begründung |
|---|---|---|
| Layer 0 | Lokal auf deinem Rechner | Schnell startbar, geringe Infrastrukturkomplexität |
| Layer 0.5 | Vertrieb parallel | Produkt ohne Nachfrage ist wertlos |
| Layer 1 | Lokal + kontrollierte Tests | Wiederholbarkeit und erste Retainer prüfen |
| Layer 2 | Cloud-Basis | Erst sinnvoll bei stabiler Nutzung |
| Layer 3 | Teilautomatisierung | Erst nach bewiesener Nachfrage |
| Layer 4 | Vertical SaaS | Vision, nicht Frühphasen-Priorität |

**Wichtig:**  
Eine enge Steuerberater-Integration ist **nicht Kernbestandteil** der Roadmap. Sie bleibt optional und wird nur als Zusatzmodul betrachtet, falls echte Nachfrage entsteht.

---

## 6. Marktvorteil & Burggraben

### Kurzfristiger Marktvorteil

NobleCockpit kombiniert:

1. Zahlenanalyse
2. Vergleichswerte
3. konkrete Maßnahmen
4. verständliche Formulierung
5. KPI-Steuerung
6. spätere Automatisierung

### Dogfooding als Vertrauensanker

> Du nutzt das Produkt zuerst selbst — für dein eigenes Business.

Das hat drei direkte Vorteile:

- Du findest Fehler vor dem Kunden.
- Du spürst früh, welche Outputs tatsächlich nützlich sind.
- Im Vertrieb ist die Aussage glaubwürdig:  
  *„Ich steuere meine eigenen Vertriebs- und Monitoring-Prozesse damit.“*

### Langfristiger Burggraben

```text
Hunderte echte BWAs
+ eigene Benchmarks
+ dokumentierte Maßnahmen
+ Erfolgsquoten je Regel
+ Zeitreihen je Branche
= schwer kopierbar
```

---

## 7. Produktkern und Nutzenversprechen

NobleCockpit löst zuerst nur dieses Problem:

> **Unternehmer verstehen ihre Monatszahlen nicht schnell genug, ziehen zu wenig konkrete Schlüsse daraus und steuern ihren Betrieb dadurch reaktiv statt aktiv.**

### Primärer Nutzen

- BWA-/EÜR-Daten werden strukturiert lesbar gemacht.
- Auffälligkeiten werden hervorgehoben.
- Kennzahlen werden in einfache Prioritäten übersetzt.
- Konkrete nächste Schritte werden formuliert.
- Monatliche Entwicklung wird sichtbar gemacht.

### Sekundärer Nutzen

- Unterlagen werden geordneter.
- Unternehmer erhalten mehr Klarheit vor Gesprächen mit Dritten.
- Optional kann eine geordnete Monatszusammenfassung an Berater, Banker oder interne Beteiligte weitergegeben werden.

---

## 8. Layer 0 – Betriebsaudit-Report (MVP)

> **Nur 3 Kernfunktionen. Nicht mehr.**

### Kernfunktionen

1. BWA / EÜR / CSV / Excel einlesen
2. Kennzahlen und Vergleichsbereiche ableiten
3. Priorisierte Hinweise und Maßnahmen in Reportform ausgeben

### Mindest-Output

- Übersicht zentraler Kostenposten
- 5–10 Kernkennzahlen
- Vergleich mit Referenzwerten / Orientierungswerten
- 3 priorisierte Hinweise mit Begründung
- geschätztes Potenzial als Range, nicht als harte Zusage
- klare nächste Schritte
- sichtbarer Haftungs-/Einordnungshinweis im PDF

### Sprachprinzipien

| Vermeiden | Besser |
|---|---|
| Branchendurchschnitt | Vergleichsbereich |
| Sie sparen exakt X € | Geschätztes Potenzial: X–Y € |
| Branchenstandard | Referenzwert / Orientierungswert |
| Optimale Quote | Plausibler Zielbereich |

### ROI-Formulierung

```text
Geschätztes Einsparpotenzial: 2.000–6.000 €/Jahr
abhängig von Einkauf, Lieferanten, Materialmix und Auslastung.
```

### Tech-Stack

```text
Python 3.11+
pandas + openpyxl
Regel-Engine (Klassen / JSON-Regeln)
LLM lokal oder API-basiert nur zur Formulierung
WeasyPrint oder ReportLab
lokale Benchmark-Dateien
```

### Angebotslogik

| Paket | Inhalt | Preis |
|---|---|---:|
| Audit | Einmalige Analyse + PDF | 99–199 € |
| Audit + Besprechung | Analyse + Gespräch | 299–499 € |
| Monatsmonitoring | Wiederkehrender Report | 99–149 €/Monat |

### Realistischer Umsatz Layer 0

| Kunden | Ø Preis/Monat | Monatsumsatz | Aufwand |
|---:|---:|---:|---:|
| 10 | 120 € | 1.200 € | ~3h |
| 20 | 130 € | 2.600 € | ~5h |
| 50 | 150 € | 7.500 € | ~12h |

---

## 9. Layer 0.5 – Vertrieb

> **Der Engpass ist Vertrieb, nicht Technik.**

### Vertriebsfokus

- Direktansprache kleiner Unternehmen
- regionale Netzwerke
- Unternehmergespräche
- Pilotkunden und Referenzfälle
- optional: lose Zusammenarbeit mit Steuerberatern, aber nicht als Produktabhängigkeit

### Frühphasen-Ziele

- 10 relevante Gespräche pro Woche
- 3 qualifizierte Demos pro Woche
- 1–2 neue zahlende Kunden pro Monat in der frühen Lernphase
- jedes Gespräch systematisch dokumentieren

### Senior-Prinzip

Vertrieb ist ein Messsystem, kein Bauchgefühl:

- Woher kam der Lead?
- Welche Branche?
- Welches Problem?
- Wofür wurde bezahlt?
- Wurde einmalig oder wiederkehrend gekauft?

### Multiplikatoren-Netzwerk

| Kanal | Warum | Konkret |
|---|---|---|
| Steuerberater | sehen Zahlenprobleme früh, können aber optional bleiben | nur gezielte Demos, kein Produktzwang |
| VR-Bank / Sparkasse | Kontakt zu Unternehmen mit Liquiditätsdruck | Firmenkundenbetreuer direkt ansprechen |
| IHK Oberfranken | Zugang zu regionalen Unternehmen | als Berater registrieren |
| Handwerkskammer | direkter Zugang zu Kernzielgruppen | Demo oder Kurzvortrag anbieten |
| regionale Unternehmernetzwerke | hoher Vertrauenshebel | Fallbeispiel statt Feature-Pitch |

---

## 10. Layer 1 – Erweiterter Analyzer

Start nur, wenn Layer 0 mehrfach verkauft und operativ stabil ist.

### Erweiterungen

- Mehrmonats-Trendanalyse
- Anomalie-Erkennung
- Kostenblock-Tiefenanalyse
- erste Verlaufsvergleiche
- Monatsreporting mit Standardstruktur
- optionale Zusammenfassungsansicht für Weitergabe an Dritte
- GBP-Status-Check
- optionaler Read-only-Zugang

### Paketlogik

| Paket | Preis |
|---|---:|
| Audit + Monitoring | 149–249 €/Monat |
| Audit + Setup | 199–399 € einmalig |

---

## 11. Layer 2 – NobleCockpit Basis

Start erst, wenn echte Retention und wiederkehrende Nutzung vorhanden sind.

### Funktionskern

- Kundenverwaltung light
- monatliche Reports automatisiert
- KPI-Dashboard für Kunden
- Trendansichten
- Regelhistorie
- Maßnahmenhistorie
- Datenraum je Kunde
- Liquiditäts-Cockpit
- Personalkosten-Monitor
- Erfolgsprovisions-Modul
- GBP Managed Add-on

### Optionales Zusatzmodul

**Drittweitergabe-Modul (optional, nicht Kernroadmap):**
- standardisierte Monatszusammenfassung als PDF
- geordneter Export für interne Verwendung oder externe Weitergabe
- keine verpflichtende Steuerberater-Sonderlogik
- nur bauen, wenn echte Nachfrage entsteht

### Umsatzlogik Layer 2

| Kunden | Ø Basis | Zusatz | Gesamt/Monat |
|---:|---:|---:|---:|
| 20 | 450 € | 80 € | 10.600 € |
| 50 | 500 € | 100 € | 30.000 € |
| 100 | 550 € | 150 € | 70.000 € |

---

## 12. Layer 3 – Teilautomatisierung

Erst sinnvoll bei stabiler Kundenbasis.

### Ausbau

- Beleg-/Dokumentenworkflow light
- automatisierte Report-Erstellung
- Alerting bei KPI-Abweichungen
- Benchmark-Verbesserung durch echte Datenbasis
- optionale Anbindungen an Vorsysteme
- Workflow-[[05_AUTOMATION|Automation]] via n8n
- Lexoffice-Anbindung
- Quartil-Benchmarks bei ausreichender Datenbasis

**Nicht Ziel dieses Layers:**
- vollständige Kanzlei-Integration
- komplexe Spezialmodule ohne validierte Nachfrage

### Umsatzlogik Layer 3

| Kunden | Ø Preis/Monat | Monatsumsatz |
|---:|---:|---:|
| 100 | 800 € | 80.000 € |
| 300 | 850 € | 255.000 € |

---

## 13. Layer 4 – Vertical SaaS

Vision statt operativer Nahplanung.

### Mögliche Perspektiven

- Mandantenfähigkeit
- White-Label
- Branchenmodule
- API
- erweiterte Benchmarksysteme
- Assistenzfunktionen für operative Steuerung
- branchenweite KPI-Benchmarks

Diese Ebene ist nur relevant, wenn vorherige Layer wirtschaftlich bewiesen wurden.

---

## 14. KPI-Modul

### Zweck

Das KPI-Modul macht aus einer einmaligen Analyse ein laufendes Steuerungssystem.

### Dogfooding zuerst

Das Modul wird zuerst intern genutzt. Das reduziert Fehlentwicklungen und verbessert die Vertriebs-Glaubwürdigkeit.

### Warum das Modul strategisch stark ist

| Bisher | Mit KPI-Modul |
|---|---|
| Einmaliger Audit | Permanentes Steuerungsinstrument |
| Erkenntnis einmalig | Entwicklung laufend sichtbar |
| Kündigung nach erstem Audit möglich | Niedrigere Kündigungsquote |
| Einmalzahlung | Wiederkehrender Umsatz |

### KPI-Beispiele

| KPI | Intervall | Zweck |
|---|---|---|
| Offene Angebote → Conversion | wöchentlich | Vertriebseffizienz |
| Offene Rechnungen / DSO | wöchentlich | Liquidität |
| Materialquote | monatlich | Kostenkontrolle |
| Stundenauslastung | wöchentlich | Kapazität |
| Neue Anfragen | wöchentlich | Nachfrage |
| Personalquote | monatlich | Kostenverschiebung |
| Umsatz vs. Vormonat | monatlich | Trend |

### Logik

```text
Im Zielbereich → grün
leichte Abweichung → gelb + Hinweis
klare Abweichung → rot + priorisierte Maßnahme
```

### Rollout-Plan KPI-Modul

| Phase | Nutzung | Zweck |
|---|---|---|
| Layer 0 | intern | Dogfooding, Fehler früh finden |
| Layer 1 | im Kundenreport | erste Tendenzen sichtbar machen |
| Layer 2 | Kunden-Dashboard | Add-on mit wiederkehrendem Nutzen |
| Layer 3 | Alerts + Automatisierung | KPI kippt → Reaktion |
| Layer 4 | Benchmark-Intelligenz | Branchensteuerung |

### Preismodell KPI-Modul

| Paket | Inhalt | Preis/Monat |
|---|---|---:|
| KPI Basis | 5 Kern-KPIs im Report | im Retainer enthalten |
| KPI Dashboard | vollständiges Dashboard, Ampel-Logik | 99–149 € add-on |
| KPI Alerts | Echtzeit-Benachrichtigung + Maßnahme | 149–249 € add-on |

---

## 15. Regelqualität und Evidenzsystem

Regelqualität ist kein Detail, sondern Kern des Produkts.

### Pflichtprinzipien

1. Keine Empfehlung ohne Evidenz.
2. Keine starke Aussage ohne Datengrundlage.
3. Keine Regel ohne Version.
4. Keine Regel ohne Confidence-Wert.
5. Kein Benchmark-Fall ohne Fallback-Logik.

### Ausgabeklassen

| Confidence | Ausgabeart |
|---|---|
| < 0.60 | Hinweis |
| 0.60–0.79 | Empfehlung mit Vorsichtshinweis |
| ≥ 0.80 | priorisierte Empfehlung |

### Senior-Erweiterung später

- Regel-Backtesting
- Erfolgsquoten je Regel
- branchenspezifische Kalibrierung
- statistische Benchmarks mit Quartilen

---

## 16. Benchmark-Entwicklung

| Phase | Datenquelle | Qualität |
|---|---|---|
| Layer 0 | öffentliche Quellen + Erfahrungswerte | Orientierung |
| Layer 1 | öffentliche Quellen + erste Kundendaten | brauchbar |
| Layer 2 | anonymisierte eigene Daten | hoch |
| Layer 3/4 | größere eigene Datenbasis mit Quartilen | stark |

### Regel

Quartil-Benchmarks erst verwenden, wenn genug Daten vorliegen. Frühphase bedeutet Orientierung, nicht Scheingenauigkeit.

---

## 17. Rechtlicher Pflicht-Layer

> **Dieser Layer ist ab dem ersten echten Kunden relevant – auch lokal.**

### Grundsatz

NobleCockpit ersetzt keine:
- steuerliche Beratung
- Rechtsberatung
- verbindliche betriebswirtschaftliche Einzelfallberatung durch Berufsträger

### Pflichtunterlagen ab Layer 0

- Dienstleistungsvertrag
- AVV nach Art. 28 DSGVO, soweit personenbezogene Daten verarbeitet werden
- Datenschutzhinweise / Datenschutzerklärung
- TOM-Kurzbeschreibung
- Haftungs- und Einordnungshinweis im Report
- Löschkonzept light

### Was lokal erleichtert wird

- geringere Infrastrukturkomplexität
- kein sofortiger Mehrmandanten-Cloudaufbau
- einfachere Zugriffskontrolle

### Was lokal **nicht** entfällt

- Vertraulichkeitspflichten
- DSGVO-Pflichten bei personenbezogenen Daten
- sichere Speicherung
- Löschkonzept
- saubere Vertragslage

### Mindest-TOMs für Layer 0

- passwortgeschütztes Gerät
- verschlüsselte Datenträger / Laufwerke
- klare Ordnertrennung je Kunde
- regelmäßige Backups
- keine unnötige Weitergabe per unsicheren Kanälen
- Löschung nach vereinbarter Frist

### Rechtliche Meilensteine

```text
Vor erstem zahlenden Kunden:
  ✅ Dienstleistungsvertrag vorbereitet
  ✅ AVV vorbereitet
  ✅ Disclaimer im PDF integriert
  ✅ TOM-Kurzbeschreibung vorhanden

Vor ersten Cloud-Tests:
  ✅ Hoster-AVV
  ✅ Datenlöschkonzept
  ✅ dokumentierte Zugriffsrechte

Vor Multi-Mandant:
  ✅ Verarbeitungsverzeichnis
  ✅ technische Sicherheitsdokumentation
  ✅ definierter Support-/Datenschutzprozess
```

---

## 18. Optionales Weitergabe-Modul

Dieses Modul ist **optional** und ausdrücklich kein Kern der Produktentwicklung.

### Mögliche Funktion

- Monatszusammenfassung als PDF
- geordnete Kennzahlenübersicht
- offene Punkte / fehlende Unterlagen
- Export für interne Weitergabe oder an Dritte

### Produktregel

Nur bauen, wenn mindestens 5–10 Kunden diesen Nutzen aktiv einfordern. Keine Sonderentwicklung nur aus theoretischer Möglichkeit.

---

## 19. Preismodell-Logik

> **Preise werden über wahrgenommenes Ergebnis gerechtfertigt, nicht über Technik.**

| Paket | Kundenergebnis | Preis |
|---|---|---:|
| Audit | Klarheit über Zahlen | 99–199 € |
| Audit + Monatsmonitoring | laufender Überblick | 149–249 €/Monat |
| Audit + KPI-Dashboard | laufende Steuerung | 249–399 €/Monat |
| Audit + Prozessoptimierung | konkrete operative Verbesserung | 299–599 €/Monat |
| Audit + Automatisierung | weniger manuelle Arbeit | 499 €+/Monat |

---

## 20. Interne Steuerungs-KPIs

### Vertrieb

| KPI | Ziel |
|---|---:|
| Unternehmer-Gespräche pro Woche | 10 |
| Demos pro Woche | 3 |
| Demo → Kunde | >20% |
| neue zahlende Kunden / Monat | 4–8 |

### Unit Economics

| KPI | Ziel |
|---|---:|
| Monatsumsatz pro Kunde | >150 € |
| Einmalumsatz Audit | >100 € |
| Kündigungsquote | <5% |
| Wiederkehrende Kunden | >50% |

### Produktivität

| KPI | Ziel |
|---|---:|
| Analysezeit pro Fall | <15 Min |
| Automatisierungsgrad | >90% |
| Zeit bis Report | <10 Min |
| Regeln mit Evidenz | 100% |

### Qualität

| KPI | Ziel |
|---|---:|
| Empfehlungen mit Nachweis | 100% |
| regelbasierte statt freie LLM-Entscheidungen | >95% |
| Kundenzufriedenheit | >8/10 |
| Wiederbuchungsquote | >30% |

---

## 21. Gesamtübersicht

| Ebene | Fokus | Umsatz realistisch | Bemerkung |
|---|---|---:|---|
| Layer 0 | 3 Kernfunktionen + internes KPI-Tracking | 1.200–7.500 €/Monat | direkt startbar |
| Layer 0.5 | Distribution | indirekt | kritischster Hebel |
| Layer 1 | Wiederholung + erste Kunden-KPIs | 4.000–11.000 €/Monat | nach Stabilität |
| Layer 2 | Produktisierung + KPI-Dashboard | 10.000–70.000 €/Monat | nach 20+ Retainern |
| Layer 3 | Datengraben + Echtzeit-KPIs | 80.000–255.000 €/Monat | nach PMF |
| Layer 4 | SaaS-Skalierung + KPI-Benchmarks | Vision | kein Kurzfristfokus |

---

## 22. Produkt-Matrix

| Modul | L0 | L1 | L2 | L3 | L4 |
|---|:---:|:---:|:---:|:---:|:---:|
| BWA-Import | ✅ | ✅ | ✅ | ✅ | ✅ |
| Vergleichsbereich / Referenzwert | ✅ | ✅ | ✅ | ✅ | ✅ |
| Regel-Engine | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ursachen-Auswahl | ✅ | ✅ | ✅ | ✅ | ✅ |
| LLM-Formulierung | ✅ | ✅ | ✅ | ✅ | ✅ |
| ROI-Range | ✅ | ✅ | ✅ | ✅ | ✅ |
| KPI intern (Dogfooding) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Trendanalyse | – | ✅ | ✅ | ✅ | ✅ |
| Anomalie-Erkennung | – | ✅ | ✅ | ✅ | ✅ |
| KPI Basis im Kundenreport | – | ✅ | ✅ | ✅ | ✅ |
| GBP-Check | – | ✅ | ✅ | ✅ | ✅ |
| CRM / Kundenverwaltung light | – | – | ✅ | ✅ | ✅ |
| Liquidität | – | – | ✅ | ✅ | ✅ |
| Erfolgsprovision | – | – | ✅ | ✅ | ✅ |
| KPI-Dashboard für Kunden | – | – | ✅ add-on | ✅ | ✅ |
| KPI-Alerts Echtzeit | – | – | – | ✅ | ✅ |
| Workflow-Automation | – | – | – | ✅ | ✅ |
| Quartil-Benchmarks | – | – | – | ✅ | ✅ |
| Weitergabe-Modul optional | – | ✅ optional | ✅ optional | ✅ optional | ✅ optional |
| API / White-Label | – | – | – | – | ✅ |
| Branchenweite KPI-Benchmarks | – | – | – | – | ✅ |

---

## 23. Erfolgswahrscheinlichkeiten

| Ziel | Einschätzung | Was entscheidet |
|---|---|---|
| Layer 0 bauen | hoch | technisch lösbar |
| mehrere zahlende Kunden | mittel bis hoch | Vertrieb |
| 20 Retainer-Kunden | mittel | Wiederholbarkeit |
| 50 Kunden | mittel | Positionierung + Automatisierung |
| 100 Kunden | eher niedrig bis mittel | Prozesse + Support |
| große SaaS-Skalierung | niedrig | Team + PMF + Kapital |

### Realistisches 12-Monats-Ziel

20 Kunden × Ø 200 € = **4.000 €/Monat**

Das ist erreichbar, aber nur bei aktivem Vertrieb und disziplinierter Fokussierung.

---

## 24. Nächste Schritte

### Sofort

- echte BWA / EÜR-Strukturen sammeln
- Parser definieren
- 5–10 Kernkennzahlen definieren
- 10–20 Kernregeln modellieren
- PDF-Layout erstellen
- Haftungshinweis in jeden Report integrieren
- Vertrags- und Datenschutzunterlagen vorbereiten
- internes KPI-Tracking starten

### Danach

- Demo-Report bauen
- erste Testkunden gewinnen
- Feedback in Regeln übersetzen
- Benchmark-Logik schärfen
- Monitoring-Paket validieren

### Nicht jetzt

- komplexe Steuerberater-Sondermodule
- große SaaS-Plattform
- breite Integrationslandschaft
- präzise Einsparversprechen ohne Datenbasis

---

## 25. Positionierungssatz

```text
NobleCockpit ersetzt keinen Steuerberater.
Es macht betriebswirtschaftliche Zahlen verständlicher,
ordnet Auffälligkeiten,
priorisiert sinnvolle Hinweise
und hilft kleinen Unternehmen,
ihren Betrieb strukturierter zu steuern.
```

---

## 26. Anhang: Pflichtdokumente

Für den Start sollten mindestens diese Dokumente vorbereitet werden:

1. Dienstleistungsvertrag
2. AVV / DPA nach Art. 28 DSGVO
3. Datenschutzhinweise
4. TOM-Kurzbeschreibung
5. Report-Disclaimer
6. Löschkonzept light

---

*Dateiname-Vorschlag: `NobleCockpit_Roadmap_v7_1.md`*