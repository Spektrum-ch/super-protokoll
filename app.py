"""
Meeting-Protokoll App
=====================
Streamlit-App für den kompletten Protokoll-Workflow:
1. Audio hochladen
2. Transkribieren (OpenAI Whisper)
3. Protokoll generieren (GPT-4o)
4. PDF erstellen
5. Download oder E-Mail-Versand

Starten mit: streamlit run app.py
"""

import os
import io
import re
import tempfile
import smtplib
from datetime import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import streamlit as st
from openai import OpenAI
from fpdf import FPDF
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from dotenv import load_dotenv

# .env laden (für lokale Entwicklung)
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def get_secret(key: str, default: str = "") -> str:
    """Holt Secret aus Streamlit Cloud oder .env."""
    # Zuerst Streamlit Secrets prüfen (für Cloud)
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        # Fallback auf .env
        return os.getenv(key, default)


# Konfiguration
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".ogg", ".webm", ".mp4", ".mpeg", ".mpga")
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB (Whisper Limit)

# ============================================================================
# PDF-Klasse (aus create_pdf.py)
# ============================================================================

class ProtocolPDF(FPDF):
    """Professionelle PDF-Klasse für Meeting-Protokolle."""

    BLACK = (0, 0, 0)
    GRAY = (100, 100, 100)

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        self.set_margins(left=20, top=20, right=20)
        self.is_first_page = True
        self.doc_title = ""

    def header(self):
        if not self.is_first_page and self.page_no() > 1:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*self.BLACK)
            self.cell(0, 10, self.doc_title[:60], align="L")
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.GRAY)
        page_info = f"{self.page_no()}/{{nb}}"
        self.cell(15, 10, page_info, align="L")
        self.cell(0, 10, self.doc_title[:50], align="L")

    def add_main_title(self, text: str):
        self.doc_title = text
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*self.GRAY)
        self.ln(10)
        self.cell(0, 6, text, align="L")
        self.ln(8)

    def add_protocol_title(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.BLACK)
        self.cell(0, 8, text, align="L")
        self.ln(12)

    def add_meta_label(self, label: str, value: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.BLACK)
        self.cell(25, 6, label, align="L")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, value, align="L")
        self.ln(6)

    def add_section_header(self, text: str):
        self.ln(6)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.BLACK)
        text_width = self.get_string_width(text)
        self.cell(text_width, 6, text, align="L")
        self.ln(1)
        self.set_draw_color(*self.BLACK)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.l_margin + text_width, self.get_y())
        self.ln(5)

    def add_participant_row(self, name: str, role: str = ""):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        if role:
            self.cell(40, 5, name, align="L")
            self.set_text_color(*self.GRAY)
            self.cell(0, 5, role, align="L")
            self.ln(5)
        else:
            self.cell(0, 5, name, align="L")
            self.ln(5)

    def add_traktandum(self, number: str, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        self.cell(8, 5, number, align="L")
        self.cell(0, 5, text, align="L")
        self.ln(5)

    def add_content_title(self, number: str, text: str):
        self.ln(6)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.BLACK)
        if number:
            self.cell(10, 7, number, align="L")
        self.cell(0, 7, text, align="L")
        self.ln(9)

    def add_body_text(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        text = text.replace("\u2022", "-").replace(chr(149), "-")
        text = text.replace("**", "")
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def add_task_row(self, task: str, responsible: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        page_width = self.w - self.l_margin - self.r_margin
        self.cell(5, 6, "-", align="L")
        task_width = page_width - 55
        self.cell(task_width, 6, task[:80], align="L")
        if responsible:
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*self.GRAY)
            self.cell(50, 6, responsible, align="R")
        self.ln(6)

    def add_signature(self, name: str, date: str):
        self.ln(10)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.BLACK)
        self.cell(0, 5, f"{name}, {date}", align="L")


# ============================================================================
# Kernfunktionen
# ============================================================================

def transcribe_audio(audio_file, client: OpenAI) -> str:
    """Transkribiert eine Audio-Datei mit OpenAI Whisper."""
        # Datei-Extension aus dem Dateinamen extrahieren
        file_ext = os.path.splitext(audio_file.name)[1].lower() or ".mp3"


    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp: 
                tmp.write(audio_file.read())
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="de",
                response_format="text"
            )
        return transcript
    finally:
        os.unlink(tmp_path)


def generate_protocol_text(transcript: str, client: OpenAI) -> str:
    """Generiert ein strukturiertes Protokoll aus dem Transkript."""

    system_prompt = """Du bist ein professioneller Meeting-Protokollant. Du erhältst ein Transkript eines Meetings und erstellst daraus ein strukturiertes Protokoll im professionellen Schweizer Stil.

WICHTIG: Halte dich strikt an folgendes Format:

===DECKBLATT===

# [Projekt/Thema aus dem Gespräch ableiten]
## Protokoll der Sitzung

**Datum:** [Wochentag, Datum, Uhrzeit - falls erwähnt, sonst "Nicht angegeben"]
**Ort:** [Ort oder "Online" - falls erwähnt, sonst weglassen]

**Teilnehmende**
| Name | Funktion/Organisation |
[Für jeden Teilnehmer eine Zeile mit Name und Rolle/Organisation falls bekannt]

**Traktanden**
1. [Erstes Thema]
2. [Zweites Thema]
3. [etc.]

===INHALT===

## 1 [Erstes Traktandum]

[Fliesstext: Was wurde besprochen, welche Positionen wurden vertreten, was wurde entschieden.]

| Aufgabe | Zuständig |

## 2 [Zweites Traktandum]

[Gleiche Struktur]

===ABSCHLUSS===

[Protokollführer], [Datum]

REGELN:
- Schreibe auf Deutsch (Schweizer Hochdeutsch)
- Fliesstext statt Aufzählungen
- Pendenzen/Aufgaben IMMER mit Zuständigkeit versehen
- Fasse zusammen, füge nichts Erfundenes hinzu"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Hier ist das Meeting-Transkript:\n\n{transcript}"}
        ],
        temperature=0.3,
        max_tokens=4096
    )

    return response.choices[0].message.content


def parse_markdown_to_pdf(markdown_text: str) -> bytes:
    """Konvertiert Markdown-Protokoll zu PDF und gibt Bytes zurück."""
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

        if not line:
            in_participants = False
            in_traktanden = False
            in_tasks = False
            i += 1
            continue

        if line in ["---", "===DECKBLATT===", "===INHALT===", "===ABSCHLUSS==="]:
            if line == "===INHALT===":
                pdf.is_first_page = False
                pdf.ln(8)
                pdf.set_draw_color(*pdf.GRAY)
                pdf.set_line_width(0.5)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(4)
            i += 1
            continue

        if line.startswith("|"):
            if "---" in line:
                i += 1
                continue

            if "Aufgabe" in line or "Zuständig" in line or "Termin" in line:
                in_tasks = True
                i += 1
                continue

            if "Name" in line or "Funktion" in line:
                i += 1
                continue

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

        if line.startswith("# "):
            title = line[2:].strip()
            pdf.add_main_title(title)
            i += 1
            continue

        if line.startswith("## "):
            subtitle = line[3:].strip()
            match = re.match(r"^(\d+)\s+(.+)$", subtitle)
            if match:
                pdf.add_content_title(match.group(1), match.group(2))
            elif "Protokoll" in subtitle:
                pdf.add_protocol_title(subtitle)
            else:
                pdf.add_content_title("", subtitle)
            i += 1
            continue

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

        if in_traktanden and re.match(r"^\d+\.", line):
            match = re.match(r"^(\d+)\.\s*(.+)", line)
            if match:
                pdf.add_traktandum(match.group(1), match.group(2))
            i += 1
            continue

        if re.match(r"^\d+\.\s", line) and not in_traktanden:
            match = re.match(r"^(\d+)\.\s*(.+)", line)
            if match:
                pdf.add_traktandum(match.group(1), match.group(2))
            i += 1
            continue

        if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+,\s+\d", line):
            parts = line.split(",", 1)
            if len(parts) == 2:
                pdf.add_signature(parts[0].strip(), parts[1].strip())
            i += 1
            continue

        if "[Protokollführer" in line or "[Datum" in line:
            i += 1
            continue

        clean_line = line.replace("**", "").replace("\u2022", "-").strip()
        if len(clean_line) > 0:
            pdf.add_body_text(clean_line)
        i += 1

    # PDF als Bytes zurückgeben
    return bytes(pdf.output())


def parse_markdown_to_docx(markdown_text: str) -> bytes:
    """Konvertiert Markdown-Protokoll zu Word-Dokument und gibt Bytes zurück."""
    doc = Document()

    # Standardschrift setzen
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    lines = markdown_text.split("\n")
    i = 0
    in_table = False
    table_data = []

    while i < len(lines):
        line = lines[i].strip()

        # Leere Zeilen
        if not line:
            if in_table and table_data:
                # Tabelle erstellen
                if len(table_data) > 0:
                    table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
                    table.style = 'Table Grid'
                    for row_idx, row_data in enumerate(table_data):
                        for col_idx, cell_text in enumerate(row_data):
                            table.rows[row_idx].cells[col_idx].text = cell_text
                    doc.add_paragraph()
                table_data = []
                in_table = False
            i += 1
            continue

        # Marker ignorieren
        if line in ["---", "===DECKBLATT===", "===INHALT===", "===ABSCHLUSS==="]:
            if line == "===INHALT===":
                # Trennlinie hinzufügen
                doc.add_paragraph("_" * 60)
            i += 1
            continue

        # Tabellen
        if line.startswith("|"):
            # Trennzeilen ignorieren
            if "---" in line:
                i += 1
                continue

            in_table = True
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts:
                table_data.append(parts)
            i += 1
            continue

        # Falls noch Tabelle offen, jetzt schliessen
        if in_table and table_data:
            if len(table_data) > 0:
                table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
                table.style = 'Table Grid'
                for row_idx, row_data in enumerate(table_data):
                    for col_idx, cell_text in enumerate(row_data):
                        if col_idx < len(table.rows[row_idx].cells):
                            table.rows[row_idx].cells[col_idx].text = cell_text
                doc.add_paragraph()
            table_data = []
            in_table = False

        # H1: Haupttitel
        if line.startswith("# "):
            title = line[2:].strip()
            p = doc.add_paragraph()
            run = p.add_run(title)
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(100, 100, 100)
            i += 1
            continue

        # H2: Untertitel
        if line.startswith("## "):
            subtitle = line[3:].strip()
            p = doc.add_paragraph()
            run = p.add_run(subtitle)
            run.bold = True
            run.font.size = Pt(13)
            i += 1
            continue

        # Metadaten: **Label:** Wert
        if line.startswith("**") and ":**" in line:
            match = re.match(r"\*\*(.+?):\*\*\s*(.*)", line)
            if match:
                label = match.group(1) + ":"
                value = match.group(2)
                p = doc.add_paragraph()
                run_label = p.add_run(label + " ")
                run_label.bold = True
                p.add_run(value)
            i += 1
            continue

        # Nummerierte Listen
        if re.match(r"^\d+\.\s", line):
            match = re.match(r"^(\d+)\.\s*(.+)", line)
            if match:
                p = doc.add_paragraph(f"{match.group(1)}. {match.group(2)}")
            i += 1
            continue

        # Platzhalter ignorieren
        if "[Protokollführer" in line or "[Datum" in line:
            i += 1
            continue

        # Signatur
        if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+,\s+\d", line):
            doc.add_paragraph()
            p = doc.add_paragraph(line)
            p.paragraph_format.space_before = Pt(24)
            i += 1
            continue

        # Fliesstext
        clean_line = line.replace("**", "").replace("\u2022", "-").strip()
        if clean_line:
            doc.add_paragraph(clean_line)
        i += 1

    # Falls noch Tabelle offen
    if in_table and table_data and len(table_data) > 0:
        table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
        table.style = 'Table Grid'
        for row_idx, row_data in enumerate(table_data):
            for col_idx, cell_text in enumerate(row_data):
                if col_idx < len(table.rows[row_idx].cells):
                    table.rows[row_idx].cells[col_idx].text = cell_text

    # Als Bytes zurückgeben
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def send_email_with_pdf(pdf_bytes: bytes, recipient: str, filename: str) -> tuple[bool, str]:
    """Versendet das PDF per E-Mail."""
    smtp_email = get_secret("SMTP_EMAIL")
    smtp_password = get_secret("SMTP_PASSWORD")
    smtp_server = get_secret("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(get_secret("SMTP_PORT", "587"))

    if not smtp_email or not smtp_password:
        return False, "SMTP-Konfiguration fehlt in .env"

    msg = MIMEMultipart()
    msg["From"] = smtp_email
    msg["To"] = recipient
    msg["Subject"] = f"Meeting-Protokoll vom {datetime.now().strftime('%d.%m.%Y')}"

    body_text = (
        f"Guten Tag,\n\n"
        f"im Anhang finden Sie das Meeting-Protokoll.\n\n"
        f"Datei: {filename}\n\n"
        f"Freundliche Grüsse\n"
        f"Meeting-Protokoll App"
    )
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(pdf_attachment)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return True, f"E-Mail erfolgreich an {recipient} gesendet!"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP-Authentifizierung fehlgeschlagen. Prüfe .env-Datei."
    except Exception as e:
        return False, f"Fehler beim Versand: {str(e)}"


# ============================================================================
# Streamlit App
# ============================================================================

def main():
    st.set_page_config(
        page_title="Meeting-Protokoll",
        page_icon="📝",
        layout="centered"
    )

    st.title("📝 Meeting-Protokoll App")
    st.markdown("Audio hochladen → Transkribieren → PDF erstellen → Versenden")

    # API-Key prüfen
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        st.error("⚠️ OPENAI_API_KEY nicht gefunden! Bitte in .env oder Streamlit Secrets konfigurieren.")
        st.stop()

    client = OpenAI(api_key=api_key)

    # Session State initialisieren
    if "transcript" not in st.session_state:
        st.session_state.transcript = None
    if "protocol" not in st.session_state:
        st.session_state.protocol = None
    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None
    if "docx_bytes" not in st.session_state:
        st.session_state.docx_bytes = None

    # -------------------------------------------------------------------------
    # Schritt 1: Audio Upload
    # -------------------------------------------------------------------------
    st.header("1️⃣ Audio hochladen")

    uploaded_file = st.file_uploader(
        "Wähle eine Audiodatei",
        type=["mp3", "wav", "m4a", "ogg", "webm", "mp4"],
        help="Unterstützte Formate: MP3, WAV, M4A, OGG, WEBM, MP4"
    )

    if uploaded_file:
        file_size = len(uploaded_file.getvalue())
        st.info(f"📁 {uploaded_file.name} ({file_size / 1024 / 1024:.1f} MB)")

        if file_size > MAX_FILE_SIZE:
            st.warning("⚠️ Datei ist grösser als 25 MB. Transkription könnte fehlschlagen.")

    # -------------------------------------------------------------------------
    # Schritt 2: Transkription
    # -------------------------------------------------------------------------
    st.header("2️⃣ Transkribieren")

    if st.button("🎙️ Transkribieren", disabled=not uploaded_file, use_container_width=True):
        with st.spinner("Transkribiere Audio mit OpenAI Whisper..."):
            try:
                uploaded_file.seek(0)
                transcript = transcribe_audio(uploaded_file, client)
                st.session_state.transcript = transcript
                st.success("✅ Transkription abgeschlossen!")
            except Exception as e:
                st.error(f"❌ Fehler: {str(e)}")

    if st.session_state.transcript:
        with st.expander("📄 Transkript anzeigen", expanded=False):
            st.text_area("Transkript", st.session_state.transcript, height=200)

    # -------------------------------------------------------------------------
    # Schritt 3: Protokoll generieren
    # -------------------------------------------------------------------------
    st.header("3️⃣ Protokoll erstellen")

    if st.button("📋 Protokoll generieren", disabled=not st.session_state.transcript, use_container_width=True):
        with st.spinner("Erstelle Protokoll mit GPT-4o..."):
            try:
                protocol = generate_protocol_text(st.session_state.transcript, client)
                st.session_state.protocol = protocol
                st.success("✅ Protokoll erstellt!")
            except Exception as e:
                st.error(f"❌ Fehler: {str(e)}")

    if st.session_state.protocol:
        with st.expander("📝 Protokoll anzeigen/bearbeiten", expanded=True):
            edited_protocol = st.text_area(
                "Protokoll (Markdown)",
                st.session_state.protocol,
                height=400
            )
            if edited_protocol != st.session_state.protocol:
                st.session_state.protocol = edited_protocol

    # -------------------------------------------------------------------------
    # Schritt 4: Dokumente erstellen (PDF & Word)
    # -------------------------------------------------------------------------
    st.header("4️⃣ Dokumente erstellen")

    if st.button("📄 PDF & Word generieren", disabled=not st.session_state.protocol, use_container_width=True):
        with st.spinner("Erstelle PDF und Word..."):
            try:
                pdf_bytes = parse_markdown_to_pdf(st.session_state.protocol)
                st.session_state.pdf_bytes = pdf_bytes

                docx_bytes = parse_markdown_to_docx(st.session_state.protocol)
                st.session_state.docx_bytes = docx_bytes

                st.success(f"✅ PDF ({len(pdf_bytes) / 1024:.1f} KB) und Word ({len(docx_bytes) / 1024:.1f} KB) erstellt!")
            except Exception as e:
                st.error(f"❌ Fehler: {str(e)}")

    # -------------------------------------------------------------------------
    # Schritt 5: Download & Versand
    # -------------------------------------------------------------------------
    if st.session_state.pdf_bytes:
        st.header("5️⃣ Download & Versand")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename_pdf = f"Protokoll_{timestamp}.pdf"
        filename_docx = f"Protokoll_{timestamp}.docx"

        st.subheader("Download")
        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="⬇️ PDF herunterladen",
                data=st.session_state.pdf_bytes,
                file_name=filename_pdf,
                mime="application/pdf",
                use_container_width=True
            )

        with col2:
            if st.session_state.docx_bytes:
                st.download_button(
                    label="⬇️ Word herunterladen",
                    data=st.session_state.docx_bytes,
                    file_name=filename_docx,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )

        st.subheader("E-Mail-Versand")
        default_recipient = get_secret("DEFAULT_RECIPIENT", "")
        recipient = st.text_input("E-Mail-Adresse", value=default_recipient)

        if st.button("📧 PDF per E-Mail senden", use_container_width=True):
            if recipient:
                with st.spinner("Sende E-Mail..."):
                    success, message = send_email_with_pdf(
                        st.session_state.pdf_bytes,
                        recipient,
                        filename_pdf
                    )
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            else:
                st.warning("Bitte E-Mail-Adresse eingeben")

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------
    st.divider()
    if st.button("🔄 Neues Protokoll starten"):
        st.session_state.transcript = None
        st.session_state.protocol = None
        st.session_state.pdf_bytes = None
        st.session_state.docx_bytes = None
        st.rerun()


if __name__ == "__main__":
    main()
