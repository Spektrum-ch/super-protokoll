"""
send_email.py
-------------
Versendet eine E-Mail mit PDF-Anhang über SMTP (Gmail).

Verwendung:
    python execution/send_email.py /pfad/zur/datei.pdf "Betreff der E-Mail" empfaenger@email.com

Konfiguration über .env:
    SMTP_EMAIL=absender@gmail.com
    SMTP_PASSWORD=gmail-app-passwort
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=587
    DEFAULT_RECIPIENT=andreas.rupf@gmail.com
"""

import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

from dotenv import load_dotenv

# .env laden (Projektroot)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def send_email(
    pdf_path: str,
    subject: str,
    recipient: str | None = None
) -> bool:
    """
    Versendet eine E-Mail mit PDF-Anhang.

    Args:
        pdf_path: Pfad zur PDF-Datei
        subject: E-Mail-Betreff
        recipient: Empfänger-Adresse (optional, Standard aus .env)

    Returns:
        True bei Erfolg, False bei Fehler
    """
    # Konfiguration laden
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    default_recipient = os.getenv("DEFAULT_RECIPIENT", "andreas.rupf@gmail.com")

    # Validierung
    if not smtp_email:
        print("FEHLER: SMTP_EMAIL nicht in .env gesetzt!")
        return False

    if not smtp_password:
        print("FEHLER: SMTP_PASSWORD nicht in .env gesetzt!")
        print("HINWEIS: Für Gmail benötigst du ein App-Passwort:")
        print("  1. Google-Konto → Sicherheit → 2FA aktivieren")
        print("  2. App-Passwörter → Neues App-Passwort erstellen")
        return False

    if not os.path.isfile(pdf_path):
        print(f"FEHLER: PDF nicht gefunden: {pdf_path}")
        return False

    recipient = recipient or default_recipient
    pdf_filename = os.path.basename(pdf_path)

    # E-Mail zusammenbauen
    msg = MIMEMultipart()
    msg["From"] = smtp_email
    msg["To"] = recipient
    msg["Subject"] = subject

    # Body
    body_text = (
        f"Guten Tag,\n\n"
        f"im Anhang finden Sie das Meeting-Protokoll.\n\n"
        f"Datei: {pdf_filename}\n\n"
        f"Das Protokoll enthält:\n"
        f"- Seite 1: Meeting-Protokoll (Themen, Beschlüsse)\n"
        f"- Seite 2: To-Dos pro Teilnehmer\n"
        f"- Seite 3: Executive Summary\n\n"
        f"Freundliche Grüsse\n"
        f"Meeting-Protokoll Workflow"
    )
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # PDF-Anhang
    with open(pdf_path, "rb") as f:
        pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
        pdf_attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=pdf_filename
        )
        msg.attach(pdf_attachment)

    # E-Mail versenden
    print(f"Versende E-Mail an {recipient}...")
    print(f"  Betreff: {subject}")
    print(f"  Anhang: {pdf_filename}")
    print(f"  Server: {smtp_server}:{smtp_port}")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)

        print(f"E-Mail erfolgreich versendet an {recipient}!")
        return True

    except smtplib.SMTPAuthenticationError:
        print("FEHLER: SMTP-Authentifizierung fehlgeschlagen!")
        print("  Prüfe SMTP_EMAIL und SMTP_PASSWORD in .env")
        print("  Für Gmail: App-Passwort verwenden (nicht normales Passwort)")
        return False

    except smtplib.SMTPException as e:
        print(f"FEHLER: SMTP-Fehler: {e}")
        return False

    except Exception as e:
        print(f"FEHLER: Unbekannter Fehler: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Verwendung: python execution/send_email.py /pfad/zur/datei.pdf \"Betreff\"")
        print("  Optional: python execution/send_email.py /pfad/zur/datei.pdf \"Betreff\" empfaenger@email.com")
        sys.exit(1)

    pdf_file = sys.argv[1]
    email_subject = sys.argv[2]
    email_recipient = sys.argv[3] if len(sys.argv) > 3 else None

    success = send_email(pdf_file, email_subject, email_recipient)
    if not success:
        sys.exit(1)
    print("\nERGEBNIS: E-Mail erfolgreich versendet")
