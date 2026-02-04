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
import math
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

# ffmpeg für Audio-Splitting
import subprocess
import shutil
import platform
import urllib.request

# Typische ffmpeg-Pfade auf macOS
FFMPEG_PATHS = [
    "/opt/homebrew/bin/ffmpeg",  # Apple Silicon Homebrew
    "/usr/local/bin/ffmpeg",      # Intel Homebrew
    "/usr/bin/ffmpeg",            # System
]

def find_ffmpeg():
    """Findet ffmpeg auf dem System oder im Projektordner."""
    # Erst im Projektordner suchen (falls PROJECT_ROOT existiert)
    try:
        local_ffmpeg = Path(__file__).resolve().parent / "ffmpeg"
        if local_ffmpeg.exists() and os.access(str(local_ffmpeg), os.X_OK):
            return str(local_ffmpeg)
    except:
        pass
    # Im PATH suchen
    path = shutil.which("ffmpeg")
    if path:
        return path
    # Bekannte Pfade prüfen
    for p in FFMPEG_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None

def install_ffmpeg_brew():
    """Installiert ffmpeg über Homebrew."""
    brew_paths = ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]
    brew = None
    for bp in brew_paths:
        if os.path.isfile(bp):
            brew = bp
            break
    if brew:
        try:
            result = subprocess.run([brew, "install", "ffmpeg"],
                                   capture_output=True, timeout=600)
            return result.returncode == 0
        except:
            pass
    return False

def get_ffmpeg_path():
    """Gibt den ffmpeg-Pfad zurück."""
    return find_ffmpeg()

# ffmpeg beim Start suchen
FFMPEG_PATH = find_ffmpeg()
FFMPEG_AVAILABLE = FFMPEG_PATH is not None

# .env laden (für lokale Entwicklung)
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# Logo-Pfad (für App Logo)
LOGO_PATH = PROJECT_ROOT / "ICON.png"
LOGO_AVAILABLE = LOGO_PATH.exists()


def get_secret(key: str, default: str = "") -> str:
    """Holt Secret aus Streamlit Cloud oder .env."""
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# Konfiguration
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".ogg", ".webm", ".mp4", ".mpeg", ".mpga")
WHISPER_CHUNK_SIZE = 24 * 1024 * 1024  # 24 MB (Whisper Limit ist 25 MB)
CHUNK_DURATION_MS = 10 * 60 * 1000  # 10 Minuten pro Chunk
MAX_FILE_SIZE = 200 * 1024 * 1024  # Immer 200 MB erlauben
MAX_FILE_SIZE_MB = 200

# ============================================================================
# PWA (Progressive Web App) Konfiguration
# ============================================================================

PWA_META_TAGS = """
<link rel="manifest" href="./static/manifest.json">
<meta name="theme-color" content="#4F46E5">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Protokoll AI">
<link rel="apple-touch-icon" href="./static/icon-192.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="application-name" content="Protokoll AI">
<meta name="msapplication-TileColor" content="#4F46E5">
<meta name="msapplication-TileImage" content="./static/icon-192.png">
"""

PWA_SERVICE_WORKER = """
<script>
    // PWA Service Worker Registration
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
            navigator.serviceWorker.register('./static/service-worker.js')
                .then(function(registration) {
                    console.log('Protokoll AI ServiceWorker registered:', registration.scope);
                })
                .catch(function(error) {
                    console.log('Protokoll AI ServiceWorker registration failed:', error);
                });
        });
    }

    // PWA Install Prompt
    let deferredPrompt;
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        // Show install button in UI if needed
        console.log('Protokoll AI can be installed as PWA');
    });
</script>
"""

# ============================================================================
# Custom CSS - Apple-Style minimalistisches Design
# ============================================================================

CUSTOM_CSS = """
<style>
    /* Apple-Style: Clean, minimal, viel Weissraum */

    /* Hauptcontainer - zentriert mit viel Raum */
    .main .block-container {
        padding-top: 3rem;
        padding-bottom: 3rem;
        max-width: 680px;
    }

    /* Grosse, klare Überschriften */
    h1 {
        font-size: 3rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
        color: #1d1d1f !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }

    h2, h3 {
        font-weight: 600 !important;
        color: #1d1d1f !important;
        letter-spacing: -0.01em;
    }

    /* Subheadline */
    .main p {
        color: #86868b;
        font-size: 1.1rem;
        line-height: 1.5;
    }

    /* Apple-Style Button - Blau, abgerundet */
    .stButton > button {
        background: #0071e3 !important;
        color: white !important;
        border: none !important;
        border-radius: 980px !important;
        padding: 12px 24px !important;
        font-size: 17px !important;
        font-weight: 400 !important;
        transition: all 0.3s ease !important;
        min-height: 50px;
    }

    .stButton > button:hover {
        background: #0077ED !important;
        transform: scale(1.02);
    }

    .stButton > button:disabled {
        background: #d2d2d7 !important;
        color: #86868b !important;
    }

    /* Download Buttons - Grün */
    .stDownloadButton > button {
        background: #34c759 !important;
        border: none !important;
        border-radius: 980px !important;
        font-size: 17px !important;
        min-height: 50px;
    }

    .stDownloadButton > button:hover {
        background: #30d158 !important;
    }

    /* File Uploader - Clean */
    .stFileUploader {
        margin: 2rem 0;
    }

    .stFileUploader label {
        font-size: 1rem;
        color: #1d1d1f;
    }

    /* Text Areas */
    .stTextArea textarea {
        border-radius: 12px;
        border: 1px solid #d2d2d7;
        font-size: 15px;
        padding: 12px;
    }

    .stTextArea textarea:focus {
        border-color: #0071e3;
        box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
    }

    /* Expander - Clean */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #1d1d1f;
        border-radius: 12px;
    }

    /* Sidebar - Minimal */
    [data-testid="stSidebar"] {
        background: #fbfbfd;
        border-right: 1px solid #d2d2d7;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-size: 1.2rem !important;
        text-align: left !important;
    }

    /* Alerts - Soft */
    .stAlert {
        border-radius: 12px;
        border: none;
    }

    /* Progress Bar */
    .stProgress > div > div {
        background: #0071e3 !important;
        border-radius: 10px;
    }

    /* Metric Cards */
    [data-testid="metric-container"] {
        background: #f5f5f7;
        border-radius: 18px;
        padding: 1.25rem;
        border: none;
    }

    /* Divider - Subtle */
    hr {
        border-color: #d2d2d7;
        margin: 2.5rem 0;
        opacity: 0.5;
    }

    /* Links */
    a {
        color: #0066cc;
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }

    /* Success/Info Messages */
    .stSuccess, .stInfo {
        border-radius: 12px;
    }

    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Hide GitHub icon and header buttons */
    header {visibility: hidden;}
    .stApp [data-testid="stToolbar"] {display: none !important;}
    .stApp [data-testid="stDecoration"] {display: none !important;}
    .stDeployButton {display: none !important;}

    /* ============================================
       Animierte Verarbeitungsanzeige
       ============================================ */

    /* Container für Animation */
    .processing-animation {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem 0;
    }

    /* Pulsierende Kreise Animation */
    .pulse-loader {
        display: flex;
        gap: 8px;
        align-items: center;
        justify-content: center;
        margin-bottom: 1.5rem;
    }

    .pulse-loader span {
        width: 12px;
        height: 12px;
        background: #0071e3;
        border-radius: 50%;
        animation: pulse 1.4s ease-in-out infinite;
    }

    .pulse-loader span:nth-child(1) { animation-delay: 0s; }
    .pulse-loader span:nth-child(2) { animation-delay: 0.2s; }
    .pulse-loader span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes pulse {
        0%, 100% {
            transform: scale(0.8);
            opacity: 0.5;
        }
        50% {
            transform: scale(1.2);
            opacity: 1;
        }
    }

    /* Rotierender Ring */
    .spinner {
        width: 50px;
        height: 50px;
        border: 3px solid #f5f5f7;
        border-top-color: #0071e3;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 1rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Status Text Animation */
    .status-text {
        color: #1d1d1f;
        font-size: 17px;
        text-align: center;
        animation: fadeInOut 2s ease-in-out infinite;
    }

    @keyframes fadeInOut {
        0%, 100% { opacity: 0.7; }
        50% { opacity: 1; }
    }

    /* Logo oben links */
    .top-logo {
        position: fixed;
        top: 1rem;
        left: 1rem;
        z-index: 1000;
        height: 40px;
    }

    .top-logo img {
        height: 40px;
        width: auto;
    }
</style>
"""

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

def get_ffprobe_path():
    """Findet ffprobe (liegt im gleichen Ordner wie ffmpeg)."""
    if FFMPEG_PATH:
        ffprobe = FFMPEG_PATH.replace("ffmpeg", "ffprobe")
        if os.path.isfile(ffprobe):
            return ffprobe
    return shutil.which("ffprobe")


def get_audio_duration(file_path: str) -> float:
    """Ermittelt die Dauer einer Audio-Datei in Sekunden mit ffprobe."""
    ffprobe = get_ffprobe_path()
    print(f"[DURATION] ffprobe path: {ffprobe}")
    if not ffprobe:
        print("[DURATION] FEHLER: ffprobe nicht gefunden!")
        return 0
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=30
        )
        print(f"[DURATION] ffprobe output: '{result.stdout.strip()}', stderr: '{result.stderr.strip()}'")
        duration = float(result.stdout.strip())
        print(f"[DURATION] Dauer: {duration} Sekunden")
        return duration
    except Exception as e:
        print(f"[DURATION] FEHLER: {e}")
        return 0


def split_audio_file(file_path: str, chunk_duration_ms: int = CHUNK_DURATION_MS) -> list:
    """Teilt eine Audio-Datei in kleinere Chunks auf mit ffmpeg."""
    print(f"[SPLIT] Start - ffmpeg available: {FFMPEG_AVAILABLE}, path: {FFMPEG_PATH}")

    if not FFMPEG_AVAILABLE or not FFMPEG_PATH:
        print("[SPLIT] FEHLER: ffmpeg nicht verfügbar!")
        return [file_path]

    try:
        # Audio-Dauer ermitteln
        duration_sec = get_audio_duration(file_path)
        chunk_duration_sec = chunk_duration_ms / 1000
        print(f"[SPLIT] Audio-Dauer: {duration_sec} Sekunden ({duration_sec/60:.1f} Minuten)")
        print(f"[SPLIT] Chunk-Dauer: {chunk_duration_sec} Sekunden")

        # Wenn Audio kurz genug ist oder Dauer unbekannt, nicht splitten
        if duration_sec <= 0:
            print("[SPLIT] FEHLER: Konnte Audio-Dauer nicht ermitteln!")
            return [file_path]

        if duration_sec <= chunk_duration_sec:
            print("[SPLIT] Audio kurz genug, kein Splitting nötig")
            return [file_path]

        # In Chunks aufteilen mit ffmpeg
        chunks = []
        num_chunks = math.ceil(duration_sec / chunk_duration_sec)
        base_path = os.path.splitext(file_path)[0]

        for i in range(num_chunks):
            start_sec = i * chunk_duration_sec
            chunk_path = f"{base_path}_chunk{i}.mp3"

            # ffmpeg Befehl: Segment extrahieren und als MP3 speichern
            cmd = [
                FFMPEG_PATH, "-y", "-i", file_path,
                "-ss", str(start_sec),
                "-t", str(chunk_duration_sec),
                "-acodec", "libmp3lame", "-b:a", "128k",
                "-loglevel", "error",
                chunk_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(chunk_path):
                chunks.append(chunk_path)
            else:
                # Bei Fehler: Aufräumen und Original zurückgeben
                for c in chunks:
                    if os.path.exists(c):
                        os.remove(c)
                return [file_path]

        return chunks
    except Exception as e:
        # Bei Fehler: Original-Datei zurückgeben
        return [file_path]


def transcribe_audio(audio_file, client: OpenAI, progress_callback=None, status_callback=None) -> str:
    """Transkribiert eine Audio-Datei mit OpenAI Whisper. Unterstützt große Dateien durch automatisches Splitting."""
    file_ext = os.path.splitext(audio_file.name)[1].lower() or ".mp3"

    # Temporäre Datei erstellen
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    chunk_paths = []

    try:
        # Dateigröße prüfen
        file_size = os.path.getsize(tmp_path)

        if status_callback:
            status_callback(f"📁 Dateigrösse: {file_size // (1024*1024)} MB")

        if file_size <= WHISPER_CHUNK_SIZE:
            # Kleine Datei - direkt transkribieren
            if status_callback:
                status_callback("📝 Kleine Datei - direkte Transkription...")
            with open(tmp_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="de",
                    response_format="text"
                )
            return transcript
        else:
            # Große Datei - in Chunks aufteilen
            if status_callback:
                status_callback(f"✂️ Grosse Datei - wird gesplittet (ffmpeg: {FFMPEG_PATH})...")

            chunk_paths = split_audio_file(tmp_path)

            if status_callback:
                status_callback(f"📦 {len(chunk_paths)} Audio-Teile erstellt")

            # Prüfen ob wirklich gesplittet wurde
            if len(chunk_paths) == 1 and chunk_paths[0] == tmp_path:
                if status_callback:
                    status_callback("⚠️ WARNUNG: Datei wurde NICHT gesplittet!")

            transcripts = []
            for i, chunk_path in enumerate(chunk_paths):
                if progress_callback:
                    progress_callback(i + 1, len(chunk_paths))
                if status_callback:
                    chunk_size = os.path.getsize(chunk_path) // (1024*1024)
                    status_callback(f"🎙️ Transkribiere Teil {i+1}/{len(chunk_paths)} ({chunk_size} MB)...")

                with open(chunk_path, "rb") as f:
                    chunk_transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="de",
                        response_format="text"
                    )
                transcripts.append(chunk_transcript)

                if status_callback:
                    words_in_chunk = len(chunk_transcript.split())
                    status_callback(f"✓ Teil {i+1}: {words_in_chunk} Wörter transkribiert")

            # Alle Transkripte zusammenführen
            full_transcript = " ".join(transcripts)
            if status_callback:
                total_words = len(full_transcript.split())
                status_callback(f"✅ Gesamt: {total_words} Wörter aus {len(chunk_paths)} Teilen")

            return full_transcript

    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg:
            raise Exception(f"Dateiformat-Fehler: Die Datei '{audio_file.name}' konnte nicht verarbeitet werden. Versuche MP3 oder WAV.")
        raise
    finally:
        # Aufräumen
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        for chunk_path in chunk_paths:
            if chunk_path != tmp_path and os.path.exists(chunk_path):
                os.unlink(chunk_path)


def generate_protocol_text(transcript: str, client: OpenAI) -> str:
    """Generiert ein strukturiertes Protokoll aus dem Transkript."""

    # Debug: Transkript-Länge
    transcript_words = len(transcript.split())
    transcript_chars = len(transcript)
    print(f"[PROTOKOLL] Transkript-Eingabe: {transcript_words} Wörter, {transcript_chars} Zeichen")

    system_prompt = """Du bist ein professioneller Meeting-Protokollant. Erstelle ein AUSFÜHRLICHES Protokoll im Schweizer Stil.

⚠️ KRITISCHE LÄNGENVORGABE ⚠️
Das Protokoll MUSS MINDESTENS 1800 Wörter haben (ca. 4 A4-Seiten).
- Schreibe AUSFÜHRLICH und DETAILLIERT
- JEDES Traktandum braucht 2-4 Absätze Fliesstext
- Erfasse ALLE besprochenen Punkte aus dem Transkript
- Kürze NICHT - das Transkript enthält wichtige Informationen!

===FORMAT===

# [Projekt/Thema]
## Protokoll der Sitzung

**Datum:** [aus Transkript oder "Nicht angegeben"]
**Ort:** [aus Transkript oder weglassen]

**Teilnehmende**
| Name | Funktion/Organisation |

**Traktanden**
1. [Thema 1]
2. [Thema 2]
...

---

## 1 [Erstes Traktandum]

[AUSFÜHRLICHER Fliesstext - mindestens 2-4 Absätze:
- Ausgangslage und Kontext
- Was wurde diskutiert (alle Punkte!)
- Welche Meinungen/Positionen gab es
- Was wurde entschieden]

**Pendenzen:**
| Aufgabe | Zuständig | Termin |

## 2 [Zweites Traktandum]

[Wieder ausführlich - 2-4 Absätze]

[... weitere Traktanden ...]

---

## Pendenzen (Gesamtübersicht)
| Nr. | Aufgabe | Zuständig | Termin |

---
[Protokollführer], [Datum]

===REGELN===
- MINDESTENS 1800 Wörter (4 A4-Seiten)
- Schweizer Hochdeutsch
- Fliesstext, keine Aufzählungen im Haupttext
- ALLE Diskussionspunkte erfassen
- Wer hat was gesagt
- Nichts weglassen!"""

    user_prompt = f"""Hier ist das Meeting-Transkript ({transcript_words} Wörter).

WICHTIG: Erstelle ein AUSFÜHRLICHES Protokoll mit MINDESTENS 1800 Wörtern.
Erfasse ALLE besprochenen Themen und Diskussionspunkte.
Kürze NICHT - jeder Punkt aus dem Transkript ist relevant!

TRANSKRIPT:
{transcript}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.4,
        max_tokens=12000
    )

    result = response.choices[0].message.content
    result_words = len(result.split())
    print(f"[PROTOKOLL] Generiertes Protokoll: {result_words} Wörter")

    return result


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

    return bytes(pdf.output())


def parse_markdown_to_docx(markdown_text: str) -> bytes:
    """Konvertiert Markdown-Protokoll zu Word-Dokument und gibt Bytes zurück."""
    doc = Document()

    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    lines = markdown_text.split("\n")
    i = 0
    in_table = False
    table_data = []

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            if in_table and table_data:
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

        if line in ["---", "===DECKBLATT===", "===INHALT===", "===ABSCHLUSS==="]:
            if line == "===INHALT===":
                doc.add_paragraph("_" * 60)
            i += 1
            continue

        if line.startswith("|"):
            if "---" in line:
                i += 1
                continue

            in_table = True
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts:
                table_data.append(parts)
            i += 1
            continue

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

        if line.startswith("# "):
            title = line[2:].strip()
            p = doc.add_paragraph()
            run = p.add_run(title)
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(100, 100, 100)
            i += 1
            continue

        if line.startswith("## "):
            subtitle = line[3:].strip()
            p = doc.add_paragraph()
            run = p.add_run(subtitle)
            run.bold = True
            run.font.size = Pt(13)
            i += 1
            continue

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

        if re.match(r"^\d+\.\s", line):
            match = re.match(r"^(\d+)\.\s*(.+)", line)
            if match:
                p = doc.add_paragraph(f"{match.group(1)}. {match.group(2)}")
            i += 1
            continue

        if "[Protokollführer" in line or "[Datum" in line:
            i += 1
            continue

        if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+,\s+\d", line):
            doc.add_paragraph()
            p = doc.add_paragraph(line)
            p.paragraph_format.space_before = Pt(24)
            i += 1
            continue

        clean_line = line.replace("**", "").replace("\u2022", "-").strip()
        if clean_line:
            doc.add_paragraph(clean_line)
        i += 1

    if in_table and table_data and len(table_data) > 0:
        table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
        table.style = 'Table Grid'
        for row_idx, row_data in enumerate(table_data):
            for col_idx, cell_text in enumerate(row_data):
                if col_idx < len(table.rows[row_idx].cells):
                    table.rows[row_idx].cells[col_idx].text = cell_text

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def send_email_with_protocol(pdf_bytes: bytes, docx_bytes: bytes, recipient: str, filename_base: str) -> tuple[bool, str]:
    """Versendet PDF und Word-Dokument per E-Mail."""
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
        f"Im Anhang finden Sie das Meeting-Protokoll als PDF und Word-Dokument.\n\n"
        f"Freundliche Grüsse\n"
        f"Protokoll AI"
    )
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # PDF anhängen
    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=f"{filename_base}.pdf")
    msg.attach(pdf_attachment)

    # Word anhängen
    docx_attachment = MIMEApplication(docx_bytes, _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document")
    docx_attachment.add_header("Content-Disposition", "attachment", filename=f"{filename_base}.docx")
    msg.attach(docx_attachment)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return True, f"E-Mail mit PDF und Word erfolgreich an {recipient} gesendet!"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP-Authentifizierung fehlgeschlagen. Prüfe .env-Datei."
    except Exception as e:
        return False, f"Fehler beim Versand: {str(e)}"


# ============================================================================
# UI Komponenten
# ============================================================================

def render_progress_tracker(current_step: int):
    """Rendert einen minimalistischen Fortschritts-Tracker im Apple-Stil."""
    steps = ["Upload", "Transkription", "Protokoll", "Dokumente", "Fertig"]

    # Einfache Progress Bar
    progress_value = (current_step - 1) / (len(steps) - 1) if current_step > 1 else 0
    st.progress(progress_value)

    # Aktueller Schritt als Text
    st.markdown(
        f"<p style='text-align:center; color:#86868b; font-size:14px; margin-top:8px;'>"
        f"Schritt {current_step} von {len(steps)}: <strong style='color:#1d1d1f;'>{steps[current_step-1]}</strong></p>",
        unsafe_allow_html=True
    )


def render_sidebar():
    """Rendert eine minimalistische Sidebar im Apple-Stil."""
    with st.sidebar:
        st.markdown("")  # Spacing

        # Logo - Clean
        if LOGO_AVAILABLE:
            st.image(str(LOGO_PATH), width=120)
            st.markdown("")
        st.markdown("### Protokoll AI")
        st.caption("Meeting-Protokoll Generator")

        st.markdown("---")

        # Status - Minimal
        st.caption("STATUS")

        if st.session_state.get("transcript"):
            st.markdown("✓ Transkript")
        if st.session_state.get("protocol"):
            st.markdown("✓ Protokoll")
        if st.session_state.get("pdf_bytes"):
            st.markdown("✓ Dokumente")

        if not any([st.session_state.get("transcript"), st.session_state.get("protocol"), st.session_state.get("pdf_bytes")]):
            st.markdown("_Bereit zum Start_")

        st.markdown("---")

        # Info - Minimal
        st.caption("TECHNOLOGIE")
        st.markdown("Whisper · GPT-4o")

        st.markdown("")
        st.caption("INSTALLATION")
        st.markdown("📱 [Als App installieren](#)", help="iOS: Teilen → Zum Home-Bildschirm\nChrome: Menü → App installieren")

        # Admin-Bereich: Aktivitäts-Log (nur für Admins)
        if st.session_state.get("is_admin"):
            st.markdown("---")
            st.caption("🔧 ADMIN")

            with st.expander("📊 Aktivitäts-Log"):
                logs = get_activity_logs()
                if logs:
                    # Neueste zuerst
                    for log in reversed(logs[-20:]):
                        st.text(f"{log['timestamp']}")
                        st.caption(f"{log['action']}: {log['details']}")
                        st.markdown("")
                else:
                    st.caption("Keine Aktivitäten")

        # Abmelden für alle Benutzer
        if st.session_state.get("authenticated"):
            st.markdown("---")
            if st.button("Abmelden", use_container_width=True):
                log_activity("Logout", "Admin" if st.session_state.get("is_admin") else "Benutzer")
                st.session_state.authenticated = False
                st.session_state.is_admin = False
                st.rerun()


def get_current_step() -> int:
    """Ermittelt den aktuellen Schritt basierend auf dem Session State."""
    if st.session_state.get("pdf_bytes"):
        return 5
    elif st.session_state.get("protocol"):
        return 4
    elif st.session_state.get("transcript"):
        return 3
    elif st.session_state.get("uploaded_file_name"):
        return 2
    return 1


# ============================================================================
# Aktivitäts-Logging
# ============================================================================

import json

ACTIVITY_LOG_FILE = PROJECT_ROOT / "activity_log.json"

def log_activity(action: str, details: str = ""):
    """Speichert eine Aktivität im Log."""
    try:
        # Bestehende Logs laden
        if ACTIVITY_LOG_FILE.exists():
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        # Neue Aktivität hinzufügen
        logs.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "details": details
        })

        # Nur letzte 100 Einträge behalten
        logs = logs[-100:]

        # Speichern
        with open(ACTIVITY_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except:
        pass  # Logging-Fehler ignorieren


def get_activity_logs() -> list:
    """Lädt alle Aktivitäts-Logs."""
    try:
        if ACTIVITY_LOG_FILE.exists():
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return []


# ============================================================================
# Streamlit App
# ============================================================================

def check_password():
    """Prüft ob das Passwort korrekt ist."""
    app_password = get_secret("APP_PASSWORD")
    admin_password = get_secret("ADMIN_PASSWORD", "")

    # Wenn kein Passwort gesetzt, Zugang erlauben (für lokale Entwicklung)
    if not app_password:
        return True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    if st.session_state.authenticated:
        return True

    # Login-Formular
    st.markdown("")
    st.markdown("<h1 style='text-align:center;'>🔐 Protokoll AI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#86868b;'>Bitte Passwort eingeben</p>", unsafe_allow_html=True)
    st.markdown("")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("Passwort", type="password", label_visibility="collapsed", placeholder="Passwort")
        if st.button("Anmelden", use_container_width=True, type="primary"):
            if password == app_password:
                st.session_state.authenticated = True
                st.session_state.is_admin = False
                log_activity("Login", "Benutzer-Login")
                st.rerun()
            elif admin_password and password == admin_password:
                st.session_state.authenticated = True
                st.session_state.is_admin = True
                log_activity("Login", "Admin-Login")
                st.rerun()
            else:
                log_activity("Login fehlgeschlagen", "Falsches Passwort")
                st.error("Falsches Passwort")

    return False


def main():
    st.set_page_config(
        page_title="Protokoll AI",
        page_icon="📝",
        layout="centered",
        initial_sidebar_state="collapsed",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )

    # Custom CSS laden
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Passwortschutz
    if not check_password():
        st.stop()

    # PWA Meta Tags und Service Worker laden
    st.markdown(PWA_META_TAGS, unsafe_allow_html=True)
    st.markdown(PWA_SERVICE_WORKER, unsafe_allow_html=True)

    # Sidebar rendern
    render_sidebar()

    # API-Key prüfen
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY nicht gefunden! Bitte in .env oder Streamlit Secrets konfigurieren.")
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
    if "processing" not in st.session_state:
        st.session_state.processing = False
    if "error" not in st.session_state:
        st.session_state.error = None

    # Hero Header - Apple Style mit Logo mittig
    st.markdown("")

    # Logo oben mittig mit CSS
    if LOGO_AVAILABLE:
        import base64
        with open(LOGO_PATH, "rb") as f:
            logo_data = base64.b64encode(f.read()).decode()
        st.markdown(f"""
            <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
                <img src="data:image/png;base64,{logo_data}" width="100">
            </div>
        """, unsafe_allow_html=True)

    st.title("Protokoll AI")
    st.markdown("<p style='text-align:center; font-size:21px; color:#86868b;'>Verwandle Audio in professionelle Protokolle.</p>", unsafe_allow_html=True)
    st.markdown("")

    # =========================================================================
    # FERTIG - Dokumente bereit
    # =========================================================================
    if st.session_state.pdf_bytes:
        st.markdown("<p style='text-align:center; font-size:17px; color:#34c759;'>✓ Dein Protokoll ist fertig!</p>", unsafe_allow_html=True)
        st.markdown("")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename_pdf = f"Protokoll_{timestamp}.pdf"
        filename_docx = f"Protokoll_{timestamp}.docx"

        # Download Buttons
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="PDF laden",
                data=st.session_state.pdf_bytes,
                file_name=filename_pdf,
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            st.download_button(
                label="Word laden",
                data=st.session_state.docx_bytes,
                file_name=filename_docx,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )

        st.markdown("")
        st.markdown("---")
        st.markdown("")

        # E-Mail Versand
        st.markdown("<p style='text-align:center; color:#1d1d1f; font-weight:600;'>Per E-Mail versenden</p>", unsafe_allow_html=True)
        st.markdown("")

        recipient = st.text_input("", placeholder="E-Mail-Adresse eingeben", label_visibility="collapsed")

        if st.button("Senden (PDF + Word)", use_container_width=True, type="primary"):
            if recipient:
                with st.spinner("Sende PDF und Word..."):
                    success, message = send_email_with_protocol(
                        st.session_state.pdf_bytes,
                        st.session_state.docx_bytes,
                        recipient,
                        f"Protokoll_{timestamp}"
                    )
                    if success:
                        st.success("✓ E-Mail mit PDF und Word gesendet!")
                        log_activity("E-Mail gesendet", f"An: {recipient}")
                    else:
                        st.error(message)
                        log_activity("E-Mail fehlgeschlagen", message)
            else:
                st.warning("Bitte E-Mail-Adresse eingeben")

        st.markdown("")
        st.markdown("")

        # Protokoll anzeigen (optional)
        with st.expander("Protokoll anzeigen"):
            st.text_area("", st.session_state.protocol, height=300, label_visibility="collapsed")

        st.markdown("")

        # Neu starten
        if st.button("Neues Protokoll erstellen", use_container_width=True):
            st.session_state.transcript = None
            st.session_state.protocol = None
            st.session_state.pdf_bytes = None
            st.session_state.docx_bytes = None
            st.session_state.processing = False
            st.session_state.error = None
            st.rerun()

    # =========================================================================
    # UPLOAD - Warte auf Datei
    # =========================================================================
    else:
        # File Uploader
        uploaded_file = st.file_uploader(
            "Audio-Datei hochladen",
            type=["mp3", "wav", "m4a", "ogg", "webm", "mp4"],
            help=f"MP3, WAV, M4A, OGG, WEBM, MP4 · Max. {MAX_FILE_SIZE_MB} MB",
            label_visibility="collapsed"
        )

        st.markdown(f"<p style='text-align:center; color:#86868b; font-size:14px;'>MP3, WAV, M4A · Max. {MAX_FILE_SIZE_MB} MB</p>", unsafe_allow_html=True)

        # Fehler anzeigen falls vorhanden
        if st.session_state.error:
            st.error(st.session_state.error)
            if st.button("Erneut versuchen", use_container_width=True):
                st.session_state.error = None
                st.rerun()

        # =====================================================================
        # AUTOMATISCHER WORKFLOW nach Upload
        # =====================================================================
        if uploaded_file and not st.session_state.processing and not st.session_state.error:
            st.session_state.processing = True

            file_size = len(uploaded_file.getvalue())

            if file_size > MAX_FILE_SIZE:
                st.session_state.error = f"Datei ist zu gross ({file_size // (1024*1024)} MB). Maximum: {MAX_FILE_SIZE_MB} MB"
                st.session_state.processing = False
                st.rerun()

            # Prüfen ob Datei zu gross für Whisper und ffmpeg benötigt wird
            if file_size > WHISPER_CHUNK_SIZE:
                global FFMPEG_PATH, FFMPEG_AVAILABLE
                # ffmpeg suchen
                FFMPEG_PATH = get_ffmpeg_path()
                FFMPEG_AVAILABLE = FFMPEG_PATH is not None

                if not FFMPEG_AVAILABLE:
                    # Versuche ffmpeg zu installieren
                    install_status = st.empty()
                    install_status.info("🔧 Installiere ffmpeg für Audio-Verarbeitung... (kann einige Minuten dauern)")

                    if install_ffmpeg_brew():
                        FFMPEG_PATH = get_ffmpeg_path()
                        FFMPEG_AVAILABLE = FFMPEG_PATH is not None
                        install_status.empty()

                if not FFMPEG_AVAILABLE:
                    st.session_state.error = "ffmpeg wird benötigt. Bitte im Terminal ausführen: brew install ffmpeg"
                    st.session_state.processing = False
                    st.rerun()

            # Animierte Verarbeitungsanzeige
            st.markdown("""
            <div class="processing-animation">
                <div class="spinner"></div>
                <div class="pulse-loader">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # Debug: ffmpeg Status anzeigen
                debug_info = st.empty()
                if FFMPEG_AVAILABLE:
                    debug_info.success(f"✓ ffmpeg gefunden: {FFMPEG_PATH}")
                else:
                    debug_info.error("✗ ffmpeg NICHT gefunden - Datei wird nicht gesplittet!")

                # Schritt 1: Transkription
                status_text.markdown("<p class='status-text'>🎙️ Transkribiere Audio...</p>", unsafe_allow_html=True)
                progress_bar.progress(10)

                # Status-Log für Debugging
                log_container = st.expander("📋 Verarbeitungs-Log", expanded=True)
                log_messages = []

                def log_status(msg):
                    log_messages.append(msg)
                    with log_container:
                        st.text("\n".join(log_messages))

                uploaded_file.seek(0)
                transcript = transcribe_audio(uploaded_file, client, status_callback=log_status)

                # Debug: Transkript-Länge anzeigen
                word_count = len(transcript.split())
                char_count = len(transcript)
                log_status(f"📊 TOTAL: {word_count} Wörter, {char_count} Zeichen")
                debug_info.info(f"📊 Transkript: {word_count} Wörter, {char_count} Zeichen")
                st.session_state.transcript = transcript

                # Schritt 2: Protokoll erstellen
                status_text.markdown("<p class='status-text'>📝 Erstelle Protokoll...</p>", unsafe_allow_html=True)
                progress_bar.progress(50)
                log_status(f"📝 Sende {word_count} Wörter an GPT-4o...")

                protocol = generate_protocol_text(transcript, client)
                st.session_state.protocol = protocol

                # Debug: Protokoll-Länge
                protocol_words = len(protocol.split())
                log_status(f"📄 Protokoll generiert: {protocol_words} Wörter")
                if protocol_words < 1500:
                    log_status(f"⚠️ WARNUNG: Protokoll zu kurz! ({protocol_words} < 1500 Wörter)")

                # Schritt 3: PDF erstellen
                status_text.markdown("<p class='status-text'>📄 Generiere PDF...</p>", unsafe_allow_html=True)
                progress_bar.progress(75)

                pdf_bytes = parse_markdown_to_pdf(protocol)
                st.session_state.pdf_bytes = pdf_bytes

                # Schritt 4: Word erstellen
                status_text.markdown("<p class='status-text'>📃 Generiere Word...</p>", unsafe_allow_html=True)
                progress_bar.progress(90)

                docx_bytes = parse_markdown_to_docx(protocol)
                st.session_state.docx_bytes = docx_bytes

                # Fertig
                progress_bar.progress(100)
                status_text.markdown("<p style='text-align:center; color:#34c759; font-size:17px;'>✓ Fertig!</p>", unsafe_allow_html=True)

                # Aktivität loggen
                log_activity("Protokoll erstellt", f"{protocol_words} Wörter, {word_count} Wörter Transkript")

                st.session_state.processing = False
                st.rerun()

            except Exception as e:
                st.session_state.error = f"Fehler: {str(e)}"
                st.session_state.processing = False
                st.rerun()


if __name__ == "__main__":
    main()
