# NobleCockpit

> Lokales bzw. später cloudfähiges Analyse- und Steuerungssystem für KMU. NobleCockpit liest BWA-/EÜR-Daten strukturiert ein, leitet Kennzahlen ab, erkennt Auffälligkeiten und formuliert priorisierte, verständliche Handlungsempfehlungen.

**Status:** 🚧 In aktiver Entwicklung — Layer 0 (MVP)

---

## Was NobleCockpit nicht ist

- Kein Steuerberater-Ersatz
- Keine Rechtsberatung
- Keine automatische Entscheidungshoheit durch das LLM

NobleCockpit ordnet, priorisiert und kommuniziert betriebswirtschaftliche Zahlen — die fachliche Entscheidung trifft immer der Unternehmer bzw. sein Berater.

---

## Kernproblem

> Unternehmer verstehen ihre Monatszahlen nicht schnell genug, ziehen zu wenig konkrete Schlüsse daraus und steuern ihren Betrieb dadurch reaktiv statt aktiv.

NobleCockpit übersetzt BWA-/EÜR-Daten in priorisierte, nachvollziehbare Handlungsempfehlungen mit Evidenz statt in reine Zahlenlisten.

---

## Architekturprinzip

**Das LLM formuliert. Die Fachlogik entscheidet nicht durch das LLM.**

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
   PDF / Report
```

**Warum dieser Ansatz:**
- Ergebnisse bleiben reproduzierbar und testbar
- Regeln sind versionierbar (`confidence`, `version`, `evidence` pro Regel)
- Fachliche Verantwortung bleibt im deterministischen System, nicht im LLM
- Fehler lassen sich isoliert lokalisieren und beheben

---

## Tech-Stack

| Bereich | Technologie |
|---|---|
| Sprache | Python 3.11+ |
| Datenverarbeitung | pandas, openpyxl |
| Regel-Engine | Klassenbasiert (JSON-Regeln, versioniert) |
| Formulierung | LLM (lokal via Ollama oder API-basiert) |
| Report-Generierung | WeasyPrint / ReportLab |
| Tests | pytest, Golden-Master-Testing gegen verifizierte BWA-Fixtures |
| Benchmarks | lokale Benchmark-Dateien (später anonymisierte Kundendaten) |

---

## Aktueller Entwicklungsstand (Layer 0)

- [x] BWA-Parser für mehrere Quellformate (bisher nur PDF)
- [x] Normalisierung heterogener BWA-Layouts in einheitliche Struktur
- [x] Duplicate-Key-Check zur Vermeidung stiller Datenkollisionen
- [x] Golden-Master-Test-Infrastruktur (Regressionsschutz bei neuen Formaten)
- [ ] Kennzahlen-Engine (5–10 Kernkennzahlen)
- [ ] Regel-Engine mit Confidence-Scoring
- [ ] Benchmark-Loader
- [ ] PDF-Report-Generierung
- [ ] Rechtlicher Pflicht-Layer (Disclaimer, AVV, Vertragsvorlagen)

---

## Roadmap (Kurzfassung)

| Layer | Fokus | Betriebsform |
|---|---|---|
| 0 (MVP) | Betriebsaudit-Report: Parser, Kennzahlen, priorisierte Hinweise | Lokal |
| 0.5 | Vertrieb parallel zum Aufbau | Lokal |
| 1 | Trendanalyse, Anomalie-Erkennung, GBP-Check | Lokal + kontrollierte Tests |
| 2 | Kundenverwaltung, KPI-Dashboard, Liquiditäts-Cockpit | Cloud-Basis |
| 3 | Teilautomatisierung, Alerting, Workflow-Automation (n8n) | Erst nach bewiesener Nachfrage |
| 4 | Vertical SaaS, White-Label, API | Vision |



---

## Projektkontext

Dieses Projekt wird parallel als praktisches Anwendungsbeispiel für Digitalisierung von Geschäftsprozessen, Datenintegration heterogener Quellen und Wirtschaftlichkeitsbewertung im Rahmen eines Wirtschaftsinformatik-Studiums dokumentiert.

---

## Lizenz / rechtlicher Hinweis

NobleCockpit befindet sich in aktiver, nicht-produktiver Entwicklung. Es ersetzt keine steuerliche oder rechtliche Beratung. Lizenzmodell wird vor öffentlichem Rollout final festgelegt.
Das Produkt darf NICHT genutzt werden!