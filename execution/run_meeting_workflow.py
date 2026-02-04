"""
run_meeting_workflow.py
-----------------------
Orchestrator-Script für den gesamten Meeting-Protokoll-Workflow.

Ablauf:
    1. Audiodateien transkribieren (Whisper API)
    2. Protokoll generieren (GPT-4o)
    3. PDF erstellen (fpdf2)
    4. E-Mail versenden (SMTP)

Verwendung:
    python execution/run_meeting_workflow.py /pfad/zum/audio-ordner

Optional:
    python execution/run_meeting_workflow.py /pfad/zum/audio-ordner empfaenger@email.com
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Projektroot für Imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "execution"))

from transcribe_audio import transcribe_folder
from generate_protocol import generate_protocol
from create_pdf import create_pdf
from send_email import send_email


def run_workflow(audio_folder: str, recipient: str | None = None) -> bool:
    """
    Führt den gesamten Meeting-Protokoll-Workflow aus.

    Args:
        audio_folder: Pfad zum Ordner mit Audiodateien
        recipient: E-Mail-Empfänger (optional, Standard aus .env)

    Returns:
        True bei Erfolg, False bei Fehler
    """
    start_time = time.time()
    print("=" * 60)
    print("  MEETING-PROTOKOLL WORKFLOW")
    print(f"  Gestartet: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Audio-Ordner: {audio_folder}")
    print("=" * 60)

    # --- SCHRITT 1: Transkription ---
    print("\n" + "─" * 60)
    print("SCHRITT 1/4: Audiodateien transkribieren")
    print("─" * 60)
    try:
        transcript_path = transcribe_folder(audio_folder)
        print(f"✓ Transkription abgeschlossen: {transcript_path}")
    except SystemExit:
        print("✗ Transkription fehlgeschlagen!")
        return False
    except Exception as e:
        print(f"✗ Transkription fehlgeschlagen: {e}")
        return False

    # --- SCHRITT 2: Protokoll generieren ---
    print("\n" + "─" * 60)
    print("SCHRITT 2/4: Protokoll mit GPT-4o erstellen")
    print("─" * 60)
    try:
        protocol_path = generate_protocol(transcript_path)
        print(f"✓ Protokoll erstellt: {protocol_path}")
    except SystemExit:
        print("✗ Protokoll-Erstellung fehlgeschlagen!")
        return False
    except Exception as e:
        print(f"✗ Protokoll-Erstellung fehlgeschlagen: {e}")
        return False

    # --- SCHRITT 3: PDF erstellen ---
    print("\n" + "─" * 60)
    print("SCHRITT 3/4: PDF erstellen")
    print("─" * 60)
    try:
        pdf_path = create_pdf(protocol_path, audio_folder)
        print(f"✓ PDF erstellt: {pdf_path}")
    except SystemExit:
        print("✗ PDF-Erstellung fehlgeschlagen!")
        return False
    except Exception as e:
        print(f"✗ PDF-Erstellung fehlgeschlagen: {e}")
        return False

    # --- SCHRITT 4: E-Mail versenden ---
    print("\n" + "─" * 60)
    print("SCHRITT 4/4: E-Mail versenden")
    print("─" * 60)
    try:
        date_str = datetime.now().strftime("%d.%m.%Y")
        subject = f"Meeting-Protokoll vom {date_str}"
        success = send_email(pdf_path, subject, recipient)
        if success:
            print(f"✓ E-Mail versendet!")
        else:
            print("✗ E-Mail-Versand fehlgeschlagen!")
            print("  Das PDF wurde trotzdem erstellt: " + pdf_path)
            return False
    except Exception as e:
        print(f"✗ E-Mail-Versand fehlgeschlagen: {e}")
        print(f"  Das PDF wurde trotzdem erstellt: {pdf_path}")
        return False

    # --- ZUSAMMENFASSUNG ---
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("  WORKFLOW ABGESCHLOSSEN")
    print(f"  Dauer: {elapsed:.1f} Sekunden")
    print(f"  PDF: {pdf_path}")
    print(f"  E-Mail: versendet an {recipient or os.getenv('DEFAULT_RECIPIENT', 'andreas.rupf@gmail.com')}")
    print("=" * 60)

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Verwendung:")
        print("  python execution/run_meeting_workflow.py /pfad/zum/audio-ordner")
        print("  python execution/run_meeting_workflow.py /pfad/zum/audio-ordner empfaenger@email.com")
        sys.exit(1)

    folder = sys.argv[1]
    rcpt = sys.argv[2] if len(sys.argv) > 2 else None

    success = run_workflow(folder, rcpt)
    sys.exit(0 if success else 1)
