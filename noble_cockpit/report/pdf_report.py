"""
noble_cockpit/reports/pdf_report.py
Erstellt den 6-seitigen BWA-Analysebericht im NobleConsulting-Corporate-Design.

Design-Grundlage: www.noble-consulting.de (siehe Design-Abstimmung im Projekt-Chat)
  - Primaerfarbe:      #14192B (dunkles Navy)
  - Akzentfarbe:        #C9A34E (Gold)
  - Hintergrund hell:   #F7F4ED (Creme)
  - Ampel positiv:      #4A7856 (gedaempftes Gruen)
  - Ampel negativ:      #A6453B (gedaempftes Terracotta-Rot)
  - Typografie:         Times/Georgia-Serife fuer Headlines, Helvetica fuer Fliesstext,
                        GROSSBUCHSTABEN mit Sperrung fuer Label/Kategorien

Seitenaufbau:
  1. Deckblatt (Logo, Mandant, Zeitraum, Einordnungssatz, Feuerwehr-Blick, Kurz-Disclaimer)
  2. Management Summary (3 Kennzahlen-Kacheln mit Euro-Betraegen + Fliesstext-Einschaetzung)
  3. Kennzahlen im Detail (Meister-Glossar + Range-Chart vs. Vergleichsbereich)
  4. Kostenstruktur (Balkendiagramm der Hauptkostenpositionen + Querverweis Aktionsplan)
  5. Aktionsplan (Top-3 Handlungsempfehlungen in Meistersprache, inkl. Potenzial-Range)
  6. Rechtlicher Hinweis (fette Fruehwarn-Box + Haftungstexte)

Dieses Modul ist bewusst UI-frei und nimmt ausschliesslich bereits berechnete
Daten aus benchmark_loader.py entgegen (KennzahlErgebnis, KostenpositionAnteil).
Es fuehrt selbst keine Kennzahlenberechnung durch - Trennung von Berechnung
und Darstellung (Single Responsibility).
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from noble_cockpit.benchmarks.benchmark_loader import (
    KENNZAHLEN_ERKLAERUNGEN,
    KennzahlErgebnis,
    KostenpositionAnteil,
)

# ---------------------------------------------------------------------------
# Corporate-Design-Konstanten
# ---------------------------------------------------------------------------

NAVY = HexColor("#14192B")
GOLD = HexColor("#C9A34E")
CREAM = HexColor("#F7F4ED")
GREEN = HexColor("#4A7856")
RED = HexColor("#A6453B")
GRAY = HexColor("#6B7080")
WHITE = HexColor("#FFFFFF")

NAVY_HEX = "#14192B"
GOLD_HEX = "#C9A34E"
CREAM_HEX = "#F7F4ED"
GREEN_HEX = "#4A7856"
RED_HEX = "#A6453B"
GRAY_HEX = "#6B7080"

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm

KENNZAHL_LABELS: dict[str, str] = {
    "rohgewinn_ii": "Rohgewinn II",
    "halbreingewinn": "Halbreingewinn",
    "reingewinn": "Reingewinn",
}

# Meistersprache: Was bedeutet die Kennzahl in einem Satz?
KENNZAHL_UNTERTITEL: dict[str, str] = {
    "rohgewinn_ii": "Was nach den Löhnen bleibt",
    "halbreingewinn": "Was nach Löhnen + laufenden Kosten bleibt",
    "reingewinn": "Was am Jahresende übrig bleibt",
}

KOSTENPOSITION_LABELS: dict[str, str] = {
    "personalkosten": "Personalkosten",
    "raumkosten": "Raumkosten",
    "fahrzeugkosten": "Fahrzeugkosten",
    "werbe_reisekosten": "Werbung / Reisekosten",
    "steuern_versicherungen": "Steuern / Versicherungen",
    "buerobedarf": "Bürobedarf",
    "porto_telefon": "Porto / Telefon",
    "instandhaltung": "Instandhaltung",
    "verschiedene_kosten": "Verschiedene Kosten",
    "kosten_warenabgabe": "Kosten der Warenabgabe",
    "rechts_beratungskosten": "Rechts- / Beratungskosten",
    "abschreibungen": "Abschreibungen",
    "sonstige_aufwendungen": "Sonstige Aufwendungen",
}

# Roadmap-Kap. 8 (Sprachprinzipien): "Vergleichsbereich" statt "Benchmark".
EINORDNUNG_LABELS: dict[str, tuple[str, HexColor]] = {
    "unterhalb": ("Unter Vergleichsbereich – bitte prüfen", RED),
    "im_rahmen_unter_durchschnitt": ("Im Vergleichsbereich, unter Mitte", GREEN),
    "im_rahmen_ueber_durchschnitt": ("Im Vergleichsbereich, über Mitte", GREEN),
    "oberhalb": ("Über Vergleichsbereich – bitte prüfen", RED),
}

# Regel-Keys -> Titel in Meistersprache (Seite 5 + Feuerwehr-Blick Seite 1).
REGEL_TITEL_MEISTER: dict[str, str] = {
    "operative_effizienz_rg_ii": "Preise und unproduktive Stunden prüfen",
    "verwaltungskosten_spread": "Verwaltung kostet überdurchschnittlich viel",
    "kritische_marge_reingewinn": "Gewinn am Limit – bitte sofort prüfen",
    "personalkosten_kritisch": "Lohnkosten zu hoch",
    "fahrzeugkosten_hoch": "Fuhrpark zu teuer",
    "raumkosten_ineffizient": "Büro / Lager zu teuer",
    "fremdleistungen_marge": "Subunternehmer kosten Marge",
}

# Kurz-Disclaimer Seite 1 (Killer gegen den Steuerberater-Einwand).
FRUEHWARN_KURZ = (
    "Dieser Report ist keine steuerliche Beratung, sondern ein "
    "betriebswirtschaftliches Frühwarnsystem auf Basis Ihrer BWA-Rohdaten "
    "zur Erkennung von Abweichungen vom Branchenschnitt."
)

# Fette Box Seite 6: Exakt-Wortlaut + Sonderabschreibungs-Killer-Satz.
FRUEHWARN_BOX_TITEL = "Bitte vor dem Gespräch mit Ihrem Steuerberater lesen"
FRUEHWARN_BOX_TEXT = (
    "Dieser Report ist keine steuerliche Beratung, sondern ein "
    "betriebswirtschaftliches Frühwarnsystem auf Basis Ihrer BWA-Rohdaten "
    "zur Erkennung von Abweichungen vom Branchenschnitt. "
    "Sonderabschreibungen, Einmaleffekte oder zeitliche Abgrenzungen können "
    "einzelne Abweichungen erklären – das ändert nichts am Frühwarn-Charakter: "
    "Wo der Report rot zeigt, lohnt das Gespräch. Details klären Sie bitte "
    "mit Ihrem Steuerberater."
)

FUSSZEILE_HINWEIS = (
    "Keine Steuerberatung – betriebswirtschaftliche Orientierung, "
    "Entscheidung beim Unternehmer/Berater."
)


def _eur_betrag(betrag: float) -> str:
    """Formatiert einen Euro-Betrag deutsch: 123456 -> '123.456'."""
    return f"{betrag:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------
# Eingabedaten des Berichts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Handlungsempfehlung:
    prio: int
    titel: str
    evidenz: str
    ursachen: str
    aktion: str
    potenzial_kurz: str = ""  # Kurzform z.B. "Potenzial: 3.400–5.100 €/Jahr" (Feuerwehr-Streifen)

@dataclass(frozen=True)
class BerichtsDaten:
    mandant_name: str
    branche_label: str
    berichtsjahr: int
    ergebnisse: list[KennzahlErgebnis]
    kostenstruktur: list[KostenpositionAnteil]
    einschaetzung_text: str
    logo_pfad: Path
    ausgabe_pfad: Path
    empfehlungen: list[Handlungsempfehlung] = field(default_factory=list)
    umsatz_eur: float = 0.0
    umsatzklasse_label: str = ""
    kanzlei_name: str = "NobleConsulting – David Heinke"
    kanzlei_website: str = "www.noble-consulting.de"

# ---------------------------------------------------------------------------
# Logo-Vorverarbeitung
# ---------------------------------------------------------------------------

def _logo_mit_transparenz(logo_pfad: Path, ausgabe_verzeichnis: Path) -> Path:
    img = Image.open(logo_pfad)

    if img.mode == "RGBA":
        alpha_werte = img.getchannel("A").getextrema()
        if alpha_werte[0] < 255:
            return logo_pfad

    img_rgb = img.convert("RGB")
    import numpy as np

    arr = np.array(img_rgb)
    weiss_maske = (arr > 235).all(axis=-1)
    alpha = (~weiss_maske).astype("uint8") * 255
    rgba = np.dstack([arr, alpha])

    ausgabe_pfad = ausgabe_verzeichnis / f"_{logo_pfad.stem}_transparent.png"
    Image.fromarray(rgba, mode="RGBA").save(ausgabe_pfad)
    return ausgabe_pfad

# ---------------------------------------------------------------------------
# Chart-Erstellung
# ---------------------------------------------------------------------------

def _erstelle_richtsatz_chart(ergebnisse: list[KennzahlErgebnis], ausgabe_pfad: Path) -> Path:
    fig = go.Figure()
    kategorien = [KENNZAHL_LABELS[e.kennzahl] for e in ergebnisse]

    for i, ergebnis in enumerate(ergebnisse):
        y = KENNZAHL_LABELS[ergebnis.kennzahl]
        rahmensatz = ergebnis.rahmensatz

        fig.add_trace(go.Bar(
            x=[rahmensatz.max - rahmensatz.min], y=[y], base=rahmensatz.min,
            orientation="h", marker=dict(color=CREAM_HEX, line=dict(color=NAVY_HEX, width=1.5)),
            showlegend=False, hoverinfo="skip", width=0.45,
            name="Vergleichsbereich (min-max)",
        ))
        fig.add_trace(go.Scatter(
            x=[rahmensatz.durchschnitt], y=[y], mode="markers",
            marker=dict(symbol="line-ns", size=34, color=GRAY_HEX, line=dict(width=3, color=GRAY_HEX)),
            showlegend=(i == 0), name="Mitte des Vergleichsbereichs", hoverinfo="skip",
        ))
        farbe = GREEN_HEX if "im_rahmen" in ergebnis.einordnung else RED_HEX
        fig.add_trace(go.Scatter(
            x=[ergebnis.wert_prozent], y=[y], mode="markers+text",
            marker=dict(symbol="diamond", size=18, color=farbe, line=dict(width=2, color=NAVY_HEX)),
            text=[f"{ergebnis.wert_prozent:.1f}%"], textposition="top center",
            textfont=dict(size=16, color=NAVY_HEX, family="Georgia, serif"),
            showlegend=(i == 0), name="Ihr Betrieb",
        ))

    fig.update_layout(
        title={"text": (
            "Kennzahlen im Vergleich zum Vergleichsbereich<br>"
            "<span style='font-size:19px;font-weight:normal;color:#555555'>"
            "Quelle: BMF Richtsatzsammlung 2025</span>"
        )},
        plot_bgcolor="#FFFFFF", paper_bgcolor=CREAM_HEX,
        font=dict(family="Georgia, serif", color=NAVY_HEX, size=18),
        margin=dict(l=180, r=70, t=130, b=80), height=620, width=1200,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=16)),
    )
    fig.update_xaxes(title_text="Prozent vom Umsatz", ticksuffix="%", gridcolor="#EDEAE0", zeroline=False, range=[0, 100])
    fig.update_yaxes(title_text="", categoryorder="array", categoryarray=list(reversed(kategorien)))

    pfad = ausgabe_pfad / "_chart_richtsatz_vergleich.png"
    fig.write_image(str(pfad), scale=2)
    return pfad

def _erstelle_kostenstruktur_chart(
    kostenstruktur: list[KostenpositionAnteil],
    mandant_name: str,
    berichtsjahr: int,
    ausgabe_pfad: Path,
    max_positionen: int = 8,
) -> Path:
    relevante = [k for k in kostenstruktur if k.betrag > 0][:max_positionen]
    aufsteigend = sorted(relevante, key=lambda k: k.betrag)

    farben = [GOLD_HEX if i == len(aufsteigend) - 1 else NAVY_HEX for i in range(len(aufsteigend))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[k.anteil_an_gesamtkosten_prozent for k in aufsteigend],
        y=[KOSTENPOSITION_LABELS.get(k.position, k.position) for k in aufsteigend],
        orientation="h", marker=dict(color=farben),
        text=[f"{k.anteil_an_gesamtkosten_prozent:.1f}%" for k in aufsteigend],
        textposition="outside", textfont=dict(size=14, color=NAVY_HEX, family="Georgia, serif"),
        cliponaxis=False,
    ))
    max_wert = max((k.anteil_an_gesamtkosten_prozent for k in aufsteigend), default=10)
    fig.update_layout(
        title={"text": (
            "Kostenstruktur: Wohin fließt das Geld?<br>"
            f"<span style='font-size:15px;font-weight:normal;color:#555555'>"
            f"Anteil an den Gesamtkosten, {mandant_name}, Jahr {berichtsjahr}</span>"
        )},
        plot_bgcolor="#FFFFFF", paper_bgcolor=CREAM_HEX,
        font=dict(family="Georgia, serif", color=NAVY_HEX, size=15),
        margin=dict(l=170, r=80, t=110, b=60), height=460, width=1200, showlegend=False,
    )
    fig.update_xaxes(title_text="Anteil Gesamtkosten", ticksuffix="%", gridcolor="#EDEAE0", range=[0, max_wert * 1.2])
    fig.update_yaxes(title_text="")

    pfad = ausgabe_pfad / "_chart_kostenstruktur.png"
    fig.write_image(str(pfad), scale=2)
    return pfad

# ---------------------------------------------------------------------------
# PDF-Seiten
# ---------------------------------------------------------------------------

def _meister_titel(rule_key: str) -> str:
    """Regel-Key -> Titel in Meistersprache (Fallback: Key lesbar gemacht)."""
    return REGEL_TITEL_MEISTER.get(rule_key, rule_key.replace("_", " "))

def _zeichne_deckblatt(c: canvas.Canvas, daten: BerichtsDaten, logo_pfad: Path) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    logo_img = ImageReader(str(logo_pfad))
    logo_px_w, logo_px_h = Image.open(logo_pfad).size
    logo_ratio = logo_px_h / logo_px_w
    logo_draw_w = 90 * mm
    logo_draw_h = logo_draw_w * logo_ratio
    c.drawImage(
        logo_img, (PAGE_W - logo_draw_w) / 2, PAGE_H - 100 * mm,
        width=logo_draw_w, height=logo_draw_h, mask="auto",
    )

    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.line((PAGE_W / 2) - 25 * mm, PAGE_H - 110 * mm, (PAGE_W / 2) + 25 * mm, PAGE_H - 110 * mm)

    c.setFont("Helvetica", 9)
    c.setFillColor(GOLD)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 120 * mm, "B E T R I E B S W I R T S C H A F T L I C H E   A N A L Y S E")

    c.setFont("Times-Roman", 30)
    c.setFillColor(WHITE)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 145 * mm, f"Mandant {daten.mandant_name}")

    c.setFont("Times-Italic", 13)
    c.setFillColor(HexColor("#D8D5CB"))
    c.drawCentredString(PAGE_W / 2, PAGE_H - 155 * mm, f"{daten.branche_label}  |  Berichtsjahr {daten.berichtsjahr}")

    c.setStrokeColor(GOLD)
    c.setLineWidth(0.6)
    c.line((PAGE_W / 2) - 30 * mm, PAGE_H - 172 * mm, (PAGE_W / 2) + 30 * mm, PAGE_H - 172 * mm)

    c.setFont("Times-Italic", 13)
    c.setFillColor(HexColor("#EDEAE0"))
    reingewinn_ergebnis = next((e for e in daten.ergebnisse if e.kennzahl == "reingewinn"), None)
    if reingewinn_ergebnis is not None and "im_rahmen" in reingewinn_ergebnis.einordnung:
        vergleich = "über" if reingewinn_ergebnis.wert_prozent >= reingewinn_ergebnis.rahmensatz.durchschnitt else "im Bereich"
        zitat = [f"Der Reingewinn liegt {vergleich} dem", "Branchendurchschnitt der Richtsatzsammlung."]
    else:
        zitat = ["Eine detaillierte Einordnung finden Sie", "im Management Summary dieses Berichts."]

    y = PAGE_H - 185 * mm
    for zeile in zitat:
        c.drawCentredString(PAGE_W / 2, y, zeile)
        y -= 6.5 * mm

    # Cover bewusst clean: Feuerwehr-Blick und Kurz-Disclaimer stehen auf Seite 2.
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GRAY)
    c.drawCentredString(PAGE_W / 2, 20 * mm, FUSSZEILE_HINWEIS)
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, 15 * mm, f"{daten.kanzlei_name}  |  {daten.kanzlei_website}")
    c.showPage()

def _zeichne_seitenkopf(c: canvas.Canvas, label: str, ueberschrift: str) -> None:
    c.setFillColor(CREAM)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    gesperrt = "   ".join(list(label.upper()))
    c.drawString(MARGIN, PAGE_H - 25 * mm, gesperrt)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(MARGIN, PAGE_H - 27 * mm, MARGIN + 18 * mm, PAGE_H - 27 * mm)

    c.setFillColor(NAVY)
    c.setFont("Times-Roman", 20)
    c.drawString(MARGIN, PAGE_H - 38 * mm, ueberschrift)

def _zeichne_fusszeile(c: canvas.Canvas, seite_aktuell: int, seite_gesamt: int, kanzlei_name: str = "") -> None:
    c.setFont("Helvetica", 8)
    c.setFillColor(GRAY)
    text = f"Seite {seite_aktuell} von {seite_gesamt}"
    if kanzlei_name:
        text = f"{text}  |  {kanzlei_name}"
    c.drawCentredString(PAGE_W / 2, 12 * mm, text)
    c.setFont("Helvetica", 7)
    c.drawCentredString(PAGE_W / 2, 8 * mm, FUSSZEILE_HINWEIS)

def _zeichne_management_summary(c: canvas.Canvas, daten: BerichtsDaten) -> None:
    _zeichne_seitenkopf(c, "Management Summary", "Ihre Kennzahlen im Überblick")

    # --- Kacheln (hoeher, damit Untertitel/Euro/Ampel innen bleiben) ---
    kachel_anzahl = len(daten.ergebnisse)
    kachel_abstand = 8 * mm
    kachel_w = (PAGE_W - 2 * MARGIN - (kachel_anzahl - 1) * kachel_abstand) / kachel_anzahl if kachel_anzahl else 0
    kachel_y = PAGE_H - 88 * mm
    kachel_h = 50 * mm

    for i, ergebnis in enumerate(daten.ergebnisse):
        x = MARGIN + i * (kachel_w + kachel_abstand)
        c.setFillColor(WHITE)
        c.roundRect(x, kachel_y, kachel_w, kachel_h, 3 * mm, fill=1, stroke=0)

        # Label + Meister-Untertitel oben (unten gekappte Flaeche durch 3mm-Rand)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 5 * mm, kachel_y + kachel_h - 8 * mm, KENNZAHL_LABELS[ergebnis.kennzahl].upper())

        c.setFillColor(GRAY)
        c.setFont("Helvetica-Oblique", 7)
        ut = KENNZAHL_UNTERTITEL.get(ergebnis.kennzahl, "")
        c.drawString(x + 5 * mm, kachel_y + kachel_h - 13.5 * mm, ut[:28])

        # Prozent gross in der Mitte
        c.setFillColor(NAVY)
        c.setFont("Times-Roman", 27)
        c.drawString(x + 5 * mm, kachel_y + 22 * mm, f"{ergebnis.wert_prozent:.1f}%")

        # Euro-Betrag darunter (Prozent x Umsatz = greifbarer Betrag)
        if daten.umsatz_eur > 0:
            euro = daten.umsatz_eur * ergebnis.wert_prozent / 100.0
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(HexColor("#333333"))
            c.drawString(x + 5 * mm, kachel_y + 15 * mm, f"≈ {_eur_betrag(euro)} €")

        # Ampel-Einordnung unten, untertitel-gekappt damit sie nie auslaeuft
        label, farbe = EINORDNUNG_LABELS[ergebnis.einordnung]
        c.setFillColor(farbe)
        c.circle(x + 6 * mm, kachel_y + 7 * mm, 1.2 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica", 7)
        c.drawString(x + 9 * mm, kachel_y + 5.9 * mm, label.replace(" – bitte prüfen", ""))

    # --- Feuerwehr-Streifen: Was laeuft super, wo brennt es akut? ---
    items = daten.empfehlungen[:3]
    rows = max(1, len(items))
    streifen_h = 16 + rows * 6.5  # mm
    streifen_top = kachel_y - 12 * mm
    c.setFillColor(WHITE)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.0)
    c.roundRect(MARGIN, streifen_top - streifen_h, PAGE_W - 2 * MARGIN, streifen_h, 2 * mm, fill=1, stroke=1)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN + 7 * mm, streifen_top - 7 * mm, "FEUERWEHR-BLICK: WO BRENNT ES?")

    iy = streifen_top - 13 * mm
    if not items:
        c.setFillColor(GREEN)
        c.circle(MARGIN + 9 * mm, iy + 1 * mm, 1.7 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica", 9.5)
        c.drawString(MARGIN + 14 * mm, iy, "Alles im grünen Bereich – keine kritischen Abweichungen.")
    else:
        for empf in items:
            farbe = RED if empf.prio == 1 else GOLD
            c.setFillColor(farbe)
            c.circle(MARGIN + 9 * mm, iy + 1 * mm, 1.7 * mm, fill=1, stroke=0)
            c.setFillColor(NAVY)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(MARGIN + 14 * mm, iy, _meister_titel(empf.titel))
            c.setFillColor(GRAY)
            c.setFont("Helvetica", 8.5)
            if empf.potenzial_kurz:
                c.drawRightString(PAGE_W - MARGIN - 7 * mm, iy, empf.potenzial_kurz)
            iy -= 6.5 * mm

    # --- Einschaeztzung unter dem Streifen ---
    text_y = streifen_top - streifen_h - 10 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN, text_y, "Einschätzung")

    c.setFont("Helvetica", 10.5)
    c.setFillColor(HexColor("#333333"))
    ty = text_y - 8 * mm
    for zeile in textwrap.wrap(daten.einschaetzung_text, width=95)[:6]:
        c.drawString(MARGIN, ty, zeile)
        ty -= 5 * mm

    _zeichne_fusszeile(c, 2, 6)
    c.showPage()

def _zeichne_kennzahlen_detail(c: canvas.Canvas, daten: BerichtsDaten, richtsatz_chart_pfad: Path) -> None:
    _zeichne_seitenkopf(c, "Kennzahlen im Detail", "Was bedeuten diese Kennzahlen?")
    y_cursor = PAGE_H - 50 * mm
    for ergebnis in daten.ergebnisse:
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN, y_cursor, KENNZAHL_LABELS[ergebnis.kennzahl])
        y_cursor -= 5 * mm

        # Meister-Untertitel direkt unter dem Fachbegriff.
        c.setFont("Helvetica-Oblique", 9.5)
        c.setFillColor(GRAY)
        c.drawString(MARGIN, y_cursor, KENNZAHL_UNTERTITEL.get(ergebnis.kennzahl, ""))
        y_cursor -= 6 * mm

        c.setFont("Helvetica", 9.5)
        c.setFillColor(HexColor("#333333"))
        erklaerung = KENNZAHLEN_ERKLAERUNGEN.get(ergebnis.kennzahl, "")
        for zeile in textwrap.wrap(erklaerung, width=100):
            c.drawString(MARGIN, y_cursor, zeile)
            y_cursor -= 4.6 * mm
        y_cursor -= 6 * mm

    chart_w = PAGE_W - 2 * MARGIN
    chart_px_w, chart_px_h = Image.open(richtsatz_chart_pfad).size
    chart_h = chart_w * (chart_px_h / chart_px_w)
    c.drawImage(ImageReader(str(richtsatz_chart_pfad)), MARGIN, y_cursor - chart_h - 2 * mm, width=chart_w, height=chart_h)

    _zeichne_fusszeile(c, 3, 6)
    c.showPage()

def _zeichne_kostenstruktur_seite(c: canvas.Canvas, daten: BerichtsDaten, kostenstruktur_chart_pfad: Path) -> None:
    _zeichne_seitenkopf(c, "Kostenstruktur", "Wohin fließt das Geld?")
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#333333"))
    intro = (
        "Die folgende Übersicht zeigt, welchen Anteil jede Kostenposition an den "
        "gesamten Betriebsausgaben hat. Bei personalintensiven Branchen wie der "
        "Gebäudereinigung ist ein hoher Personalkostenanteil branchentypisch und "
        "kein Warnsignal für sich genommen."
    )
    ty = PAGE_H - 48 * mm
    for zeile in textwrap.wrap(intro, width=100):
        c.drawString(MARGIN, ty, zeile)
        ty -= 4.6 * mm

    chart_w = PAGE_W - 2 * MARGIN
    chart_px_w, chart_px_h = Image.open(kostenstruktur_chart_pfad).size
    chart_h = chart_w * (chart_px_h / chart_px_w)
    c.drawImage(ImageReader(str(kostenstruktur_chart_pfad)), MARGIN, ty - chart_h - 6 * mm, width=chart_w, height=chart_h)

    # Querverweis: Konkrete Betraege stehen im Aktionsplan.
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, ty - chart_h - 12 * mm, "Auffällige Positionen finden Sie mit konkretem Potenzial im Aktionsplan (Seite 5).")

    _zeichne_fusszeile(c, 4, 6)
    c.showPage()

def _zeichne_handlungsempfehlungen(c: canvas.Canvas, daten: BerichtsDaten) -> None:
    _zeichne_seitenkopf(c, "Aktionsplan", "Priorisierte Handlungsempfehlungen")

    if not daten.empfehlungen:
        c.setFont("Helvetica", 11)
        c.setFillColor(NAVY)
        c.drawString(MARGIN, PAGE_H - 60 * mm, "Es wurden keine kritischen Abweichungen festgestellt. Alle geprüften")
        c.drawString(MARGIN, PAGE_H - 66 * mm, "Werte bewegen sich im wirtschaftlich soliden Rahmen.")
        _zeichne_fusszeile(c, 5, 6)
        c.showPage()
        return

    box_h = 50 * mm
    y_cursor = PAGE_H - 50 * mm
    for empf in daten.empfehlungen[:3]: # Rendert exakt die Top 3
        # Hintergrund-Box
        c.setFillColor(WHITE)
        c.roundRect(MARGIN, y_cursor - box_h, PAGE_W - 2 * MARGIN, box_h, 2 * mm, fill=1, stroke=0)

        # Prio-Marker (Rot für Prio 1, Gold für andere)
        farbe = RED if empf.prio == 1 else GOLD
        c.setFillColor(farbe)
        c.roundRect(MARGIN, y_cursor - box_h, 3 * mm, box_h, 2 * mm, fill=1, stroke=0)

        # Titel in Meistersprache
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGIN + 8 * mm, y_cursor - 7 * mm, _meister_titel(empf.titel))

        # Evidenz (mehrzeilig, inkl. Potenzial-Range aus der Regel-Engine)
        c.setFont("Helvetica", 9.5)
        c.setFillColor(GRAY)
        ey = y_cursor - 14 * mm
        for zeile in textwrap.wrap(f"Befund: {empf.evidenz}", width=80)[:3]:
            c.drawString(MARGIN + 8 * mm, ey, zeile)
            ey -= 4.3 * mm

        # Ursachen
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(HexColor("#555555"))
        uy = ey - 2 * mm
        for zeile in textwrap.wrap(f"Mögliche Ursachen: {empf.ursachen}", width=82)[:2]:
            c.drawString(MARGIN + 8 * mm, uy, zeile)
            uy -= 4.3 * mm

        # Aktion (hervorgehoben)
        c.setFillColor(farbe)
        c.setFont("Helvetica-Bold", 9.5)
        ay_label_y = y_cursor - 40 * mm
        c.drawString(MARGIN + 8 * mm, ay_label_y, "Empfehlung:")

        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 9.5)
        ty = ay_label_y
        for line in textwrap.wrap(empf.aktion, width=60)[:2]:
            c.drawString(MARGIN + 28 * mm, ty, line)
            ty -= 4.5 * mm

        y_cursor -= (box_h + 6 * mm)

    _zeichne_fusszeile(c, 5, 6)
    c.showPage()

RECHTLICHER_HINWEIS_TEXT = (
    "Dieser Bericht wurde automatisiert auf Basis der von Ihnen zur Verfügung "
    "gestellten betriebswirtschaftlichen Auswertung (BWA) erstellt. Die verwendeten "
    "Richtsätze stammen aus der Richtsatzsammlung des Bundesministeriums der "
    "Finanzen für das Kalenderjahr 2025 und dienen der Finanzverwaltung als "
    "Anhaltspunkt für Verprobungen, nicht als verbindliche Norm für einzelne "
    "Betriebe. Abweichungen von den Richtsätzen sind branchenüblich und stellen "
    "für sich genommen keinen Hinweis auf Fehler in der Buchführung dar.\n\n"
    "Dieser Bericht ersetzt keine steuerliche oder betriebswirtschaftliche Beratung "
    "im Einzelfall und begründet kein Mandatsverhältnis. Er dient ausschließlich "
    "der unternehmerischen Selbsteinschätzung. Für die Richtigkeit und "
    "Vollständigkeit der zugrunde liegenden BWA-Daten wird keine Haftung "
    "übernommen. Bei Fragen zu den Ergebnissen wenden Sie sich bitte an Ihren "
    "Steuerberater oder an NobleConsulting."
)

def _zeichne_rechtlicher_hinweis(c: canvas.Canvas, daten: BerichtsDaten) -> None:
    _zeichne_seitenkopf(c, "Rechtlicher Hinweis", "")

    # Fette Fruehwarn-Box: Steuerberater-Einwand vorab killen.
    box_top = PAGE_H - 48 * mm
    box_h = 42 * mm
    c.setFillColor(WHITE)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    c.roundRect(MARGIN, box_top - box_h, PAGE_W - 2 * MARGIN, box_h, 2 * mm, fill=1, stroke=1)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN + 8 * mm, box_top - 9 * mm, FRUEHWARN_BOX_TITEL)

    c.setFont("Helvetica-Bold", 9.5)
    ty = box_top - 16 * mm
    for zeile in textwrap.wrap(FRUEHWARN_BOX_TEXT, width=88):
        c.drawString(MARGIN + 8 * mm, ty, zeile)
        ty -= 4.6 * mm

    # Restliche Haftungstexte ohne Rahmen darunter.
    c.setFillColor(HexColor("#333333"))
    c.setFont("Helvetica", 9.5)
    ty = box_top - box_h - 10 * mm
    for absatz in RECHTLICHER_HINWEIS_TEXT.split("\n\n"):
        for zeile in textwrap.wrap(absatz, width=95):
            c.drawString(MARGIN, ty, zeile)
            ty -= 4.8 * mm
        ty -= 3 * mm

    _zeichne_fusszeile(c, 6, 6, daten.kanzlei_name)
    c.showPage()

# ---------------------------------------------------------------------------
# Oeffentliche Hauptfunktion
# ---------------------------------------------------------------------------

def erstelle_bericht(daten: BerichtsDaten) -> Path:
    daten.ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)

    logo_transparent_pfad = _logo_mit_transparenz(daten.logo_pfad, daten.ausgabe_pfad.parent)
    richtsatz_chart_pfad = _erstelle_richtsatz_chart(daten.ergebnisse, daten.ausgabe_pfad.parent)
    kostenstruktur_chart_pfad = _erstelle_kostenstruktur_chart(
        daten.kostenstruktur, daten.mandant_name, daten.berichtsjahr, daten.ausgabe_pfad.parent,
    )

    c = canvas.Canvas(str(daten.ausgabe_pfad), pagesize=A4)

    _zeichne_deckblatt(c, daten, logo_transparent_pfad)
    _zeichne_management_summary(c, daten)
    _zeichne_kennzahlen_detail(c, daten, richtsatz_chart_pfad)
    _zeichne_kostenstruktur_seite(c, daten, kostenstruktur_chart_pfad)
    _zeichne_handlungsempfehlungen(c, daten)
    _zeichne_rechtlicher_hinweis(c, daten)

    c.save()
    return daten.ausgabe_pfad

def erstelle_standard_einschaetzung(ergebnisse: list[KennzahlErgebnis]) -> str:
    reingewinn = next((e for e in ergebnisse if e.kennzahl == "reingewinn"), None)
    if reingewinn is None:
        return "Für diesen Mandanten liegen keine ausreichenden Daten für eine automatische Einschätzung vor."

    im_rahmen = [e for e in ergebnisse if "im_rahmen" in e.einordnung]
    ausserhalb = [e for e in ergebnisse if e.einordnung in ("unterhalb", "oberhalb")]

    saetze = []
    if len(im_rahmen) == len(ergebnisse):
        saetze.append(
            "Der Betrieb bewegt sich bei allen betrachteten Kennzahlen innerhalb "
            "des Vergleichsbereichs der Branche."
        )
    elif ausserhalb:
        positionen = ", ".join(KENNZAHL_LABELS[e.kennzahl] for e in ausserhalb)
        saetze.append(
            f"Bei folgenden Kennzahlen liegt der Betrieb außerhalb des üblichen "
            f"Vergleichsbereichs und sollte näher betrachtet werden: {positionen}."
        )

    vergleich = "über" if reingewinn.wert_prozent >= reingewinn.rahmensatz.durchschnitt else "unter"
    saetze.append(
        f"Der Reingewinn liegt mit {reingewinn.wert_prozent:.1f} Prozent {vergleich} der "
        f"Mitte des Vergleichsbereichs von {reingewinn.rahmensatz.durchschnitt:.0f} Prozent "
        f"(BMF Richtsatzsammlung 2025)."
    )

    return " ".join(saetze)

if __name__ == "__main__":
    pass # Dummy-Schutz beim Direktaufruf ohne main.py
