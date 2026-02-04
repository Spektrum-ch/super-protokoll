"""
create_pdf.py
-------------
Wandelt eine Protokoll-Markdown-Datei in ein professionell formatiertes PDF um.
Verwendet fpdf2 für die PDF-Erstellung.

Layout-Stil: Mix aus RAST (strukturiertes Deckblatt) und ETH RAUM (kompakter Inhalt)
- Deckblatt mit Metadaten, Teilnehmenden-Tabelle, Traktanden
- Inhalt als Fliesstext mit nummerierten Überschriften
- Aufgaben/Pendenzen mit Zuständigkeit

Verwendung:
    python execution/create_pdf.py /pfad/zur/protocol.md /pfad/zum/zielordner

Rückgabe:
    Pfad zur erstellten PDF-Datei
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

# Projektroot
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ProtocolPDF(FPDF):
    """
    Professionelle PDF-Klasse für Meeting-Protokolle.
    Styling inspiriert von RAST Raumstrategie und ETH RAUM Vorlagen.
    """

    # Farbkonstanten (RGB)
    BLACK = (0, 0, 0)
    GRAY = (100, 100, 100)

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        self.set_margins(left=20, top=20, right=20)
        self.is_first_page = True
        self.doc_title = ""

    def header(self):
        """Header auf Folgeseiten (nicht auf Deckblatt)."""
        if not self.is_first_page and self.page_no() > 1:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*self.BLACK)
            self.cell(0, 10, self.doc_title[:60], align="L")
            self.ln(10)

    def footer(self):
        """Fusszeile mit Seitenzahl."""
        self.set_y(-15)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.GRAY)
        # Format: "2/4  Projekttitel"
        page_info = f"{self.page_no()}/{{nb}}"
        self.cell(15, 10, page_info, align="L")
        self.cell(0, 10, self.doc_title[:50], align="L")

    def add_main_title(self, text: str):
        """Haupttitel des Projekts - gross, schwarz."""
        self.doc_title = text
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*self.GRAY)
        self.ln(10)
        self.cell(0, 6, text, align="L")
        self.ln(8)

    def add_protocol_title(self, text: str):
        """Protokoll-Titel - fett, grösser."""
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.BLACK)
        self.cell(0, 8, text, align="L")
        self.ln(12)

    def add_meta_label(self, label: str, value: str):
        """Metadaten-Zeile (z.B. Datum: ..., Ort: ...)."""
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.BLACK)
        self.cell(25, 6, label, align="L")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, value, align="L")
        self.ln(6)

    def add_section_header(self, text: str):
        """Abschnitts-Header (z.B. "Teilnehmende", "Traktanden") - fett, unterstrichen."""
        self.ln(6)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.BLACK)
        text_width = self.get_string_width(text)
        self.cell(text_width, 6, text, align="L")
        self.ln(1)
        # Unterstrich
        self.set_draw_color(*self.BLACK)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.l_margin + text_width, self.get_y())
        self.ln(5)

    def add_participant_row(self, name: str, role: str = ""):
        """Teilnehmer-Zeile mit Name und Funktion."""
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        if role:
            # Feste Breite für Name (40mm), Rest für Funktion
            self.cell(40, 5, name, align="L")
            self.set_text_color(*self.GRAY)
            self.cell(0, 5, role, align="L")
            self.ln(5)
        else:
            self.cell(0, 5, name, align="L")
            self.ln(5)

    def add_traktandum(self, number: str, text: str):
        """Traktanden-Eintrag."""
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        self.cell(8, 5, number, align="L")
        self.cell(0, 5, text, align="L")
        self.ln(5)

    def add_content_title(self, number: str, text: str):
        """Nummerierte Inhalts-Überschrift (z.B. "1  Begrüssung")."""
        self.ln(6)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.BLACK)
        # Nummer und Titel mit Tab-Abstand
        if number:
            self.cell(10, 7, number, align="L")
        self.cell(0, 7, text, align="L")
        self.ln(9)

    def add_body_text(self, text: str):
        """Fliesstext - 10pt, Blocksatz-ähnlich."""
        # X-Position zurücksetzen auf linken Rand
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        # Unicode-Zeichen ersetzen
        text = text.replace("\u2022", "-").replace(chr(149), "-")
        text = text.replace("**", "")
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def add_task_row(self, task: str, responsible: str):
        """Aufgaben-Zeile mit Zuständigkeit am rechten Rand."""
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)

        # Einfache Lösung: Task und Zuständigkeit auf einer Zeile
        page_width = self.w - self.l_margin - self.r_margin

        # Bullet-Punkt vor der Aufgabe
        self.cell(5, 6, "-", align="L")

        # Task links, Zuständigkeit rechts (Rest)
        task_width = page_width - 55
        self.cell(task_width, 6, task[:80], align="L")  # Kürzen falls zu lang

        if responsible:
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*self.GRAY)
            self.cell(50, 6, responsible, align="R")

        self.ln(6)

    def add_signature(self, name: str, date: str):
        """Protokollführer-Signatur am Ende."""
        self.ln(10)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        self.cell(0, 5, f"{name}, {date}", align="L")


def parse_markdown_to_pdf(markdown_text: str, output_path: str) -> str:
    """
    Parst Markdown-Text und erstellt ein professionell formatiertes PDF.
    """
    pdf = ProtocolPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    lines = markdown_text.split("\n")
    i = 0
    in_participants = False
    in_traktanden = False
    in_tasks = False

    while i < len(lines):
        line = lines[i].strip()

        # Leere Zeilen
        if not line:
            in_participants = False
            in_traktanden = False
            in_tasks = False
            i += 1
            continue

        # Trennlinien und Marker ignorieren
        if line in ["---", "===DECKBLATT===", "===INHALT===", "===ABSCHLUSS==="]:
            if line == "===INHALT===":
                pdf.is_first_page = False
                # Visuelle Trennung: Linie vor dem Inhalt
                pdf.ln(8)
                pdf.set_draw_color(*pdf.GRAY)
                pdf.set_line_width(0.5)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(4)
            i += 1
            continue

        # Alle Tabellen-Zeilen (beginnen mit |)
        if line.startswith("|"):
            # Trennzeilen ignorieren (| --- | --- |)
            if "---" in line:
                i += 1
                continue

            # Header-Zeilen: Aufgaben-Tabelle erkennen
            if "Aufgabe" in line or "Zuständig" in line or "Termin" in line:
                in_tasks = True
                i += 1
                continue

            # Header-Zeilen für Teilnehmende ignorieren
            if "Name" in line or "Funktion" in line:
                i += 1
                continue

            # Daten-Zeilen parsen
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 1:
                if in_tasks:
                    responsible = parts[1] if len(parts) > 1 else ""
                    pdf.add_task_row(parts[0], responsible)
                else:
                    role = parts[1] if len(parts) > 1 else ""
                    pdf.add_participant_row(parts[0], role)
            i += 1
            continue

        # H1: Haupttitel
        if line.startswith("# "):
            title = line[2:].strip()
            pdf.add_main_title(title)
            i += 1
            continue

        # H2: Untertitel oder Inhalts-Überschrift
        if line.startswith("## "):
            subtitle = line[3:].strip()
            # Prüfen ob nummeriert (z.B. "## 1 Begrüssung")
            match = re.match(r"^(\d+)\s+(.+)$", subtitle)
            if match:
                pdf.add_content_title(match.group(1), match.group(2))
            elif "Protokoll" in subtitle:
                pdf.add_protocol_title(subtitle)
            else:
                pdf.add_content_title("", subtitle)
            i += 1
            continue

        # Metadaten: **Label:** Wert
        if line.startswith("**") and ":**" in line:
            match = re.match(r"\*\*(.+?):\*\*\s*(.*)", line)
            if match:
                label = match.group(1) + ":"
                value = match.group(2)

                if label == "Teilnehmende:":
                    pdf.add_section_header("Teilnehmende")
                    in_participants = True
                elif label == "Entschuldigte:":
                    pdf.add_section_header("Entschuldigte")
                    in_participants = True
                elif label == "Traktanden:":
                    pdf.add_section_header("Traktanden")
                    in_traktanden = True
                else:
                    pdf.add_meta_label(label, value)
            i += 1
            continue

        # Traktanden-Liste
        if in_traktanden and re.match(r"^\d+\.", line):
            match = re.match(r"^(\d+)\.\s*(.+)", line)
            if match:
                pdf.add_traktandum(match.group(1), match.group(2))
            i += 1
            continue

        # Nummerierte Liste (ausserhalb Traktanden)
        if re.match(r"^\d+\.\s", line) and not in_traktanden:
            match = re.match(r"^(\d+)\.\s*(.+)", line)
            if match:
                pdf.add_traktandum(match.group(1), match.group(2))
            i += 1
            continue


        # Signatur am Ende (Name, Datum)
        if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+,\s+\d", line):
            parts = line.split(",", 1)
            if len(parts) == 2:
                pdf.add_signature(parts[0].strip(), parts[1].strip())
            i += 1
            continue

        # Platzhalter-Signaturen ignorieren
        if "[Protokollführer" in line or "[Datum" in line:
            i += 1
            continue

        # Alles andere: Fliesstext
        # Sicherheit: leere oder zu kurze Zeilen überspringen
        clean_line = line.replace("**", "").replace("\u2022", "-").strip()
        if len(clean_line) > 0:
            pdf.add_body_text(clean_line)
        i += 1

    # PDF speichern
    pdf.output(output_path)
    return output_path


def create_pdf(protocol_path: str, output_folder: str) -> str:
    """
    Erstellt ein PDF aus einer Protokoll-Markdown-Datei.
    Gibt den Pfad zur PDF-Datei zurück.
    """
    # Protokoll laden
    if not os.path.isfile(protocol_path):
        print(f"FEHLER: Protokoll nicht gefunden: {protocol_path}")
        sys.exit(1)

    with open(protocol_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    if not markdown_text.strip():
        print("FEHLER: Protokoll ist leer!")
        sys.exit(1)

    # Zielordner validieren
    if not os.path.isdir(output_folder):
        print(f"FEHLER: Zielordner nicht gefunden: {output_folder}")
        sys.exit(1)

    # PDF-Dateiname generieren
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    pdf_filename = f"Protokoll_{timestamp}.pdf"
    pdf_path = os.path.join(output_folder, pdf_filename)

    print(f"Erstelle PDF: {pdf_path}")
    parse_markdown_to_pdf(markdown_text, pdf_path)

    file_size = os.path.getsize(pdf_path)
    print(f"PDF erstellt: {pdf_path} ({file_size / 1024:.1f} KB)")

    return pdf_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Verwendung: python execution/create_pdf.py /pfad/zur/protocol.md /pfad/zum/zielordner")
        sys.exit(1)

    protocol_file = sys.argv[1]
    target_folder = sys.argv[2]
    result = create_pdf(protocol_file, target_folder)
    print(f"\nERGEBNIS: {result}")
