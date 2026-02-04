"""
generate_protocol.py
--------------------
Wandelt ein Meeting-Transkript über GPT-4o in ein strukturiertes Protokoll um.

Struktur gemäss Vorlage (directives/examples/Beispiel 1.pdf):
- Kopfbereich mit Titel, Teilnehmenden, Datum, Ort
- Nummerierte Abschnitte pro Thema
- To-Dos am Ende, gruppiert nach Person

Verwendung:
    python execution/generate_protocol.py /pfad/zur/transcript.txt

Rückgabe:
    Pfad zur Protokoll-Markdown-Datei (.tmp/protocol_YYYY-MM-DD_HH-MM.md)
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

# .env laden (Projektroot)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# GPT-4o Token-Limit (ca. 128k Context)
MAX_TRANSCRIPT_CHARS = 400_000  # Sicherheitsmarge

SYSTEM_PROMPT = """Du bist ein professioneller Meeting-Protokollant. Du erhältst ein Transkript eines Meetings und erstellst daraus ein strukturiertes Protokoll im professionellen Schweizer Stil.

WICHTIG: Halte dich strikt an folgendes Format:

===DECKBLATT===

# [Projekt/Thema aus dem Gespräch ableiten]
## Protokoll der Sitzung

**Datum:** [Wochentag, Datum, Uhrzeit - falls erwähnt, sonst "Nicht angegeben"]
**Ort:** [Ort oder "Online" - falls erwähnt, sonst weglassen]

**Teilnehmende**
| Name | Funktion/Organisation |
[Für jeden Teilnehmer eine Zeile mit Name und Rolle/Organisation falls bekannt]

**Entschuldigte**
[Namen falls erwähnt, sonst weglassen]

**Traktanden**
1. [Erstes Thema]
2. [Zweites Thema]
3. [etc.]
4. Weiteres Vorgehen

===INHALT===

## 1 [Erstes Traktandum]

[Fliesstext: Was wurde besprochen, welche Positionen wurden vertreten, was wurde entschieden. Schreibe zusammenhängend, nicht in Stichpunkten. Erwähne relevante Personen im Text.]

[Falls es konkrete Aufgaben gibt, am Ende des Abschnitts:]
| Aufgabe | Zuständig |

## 2 [Zweites Traktandum]

[Gleiche Struktur: Fliesstext mit eingebetteten Aufgaben]

## 3 [Weiteres Vorgehen]

[Nächste Schritte, Termine, offene Punkte als Fliesstext]

| Aufgabe | Zuständig | Termin |

===ABSCHLUSS===

[Protokollführer], [Datum]

===FORMATIERUNGSREGELN===
- Deckblatt mit strukturierten Metadaten (Datum, Ort, Teilnehmende als Tabelle, Traktanden)
- Inhalt als Fliesstext (NICHT als Bullet-Listen!)
- Aufgaben/Pendenzen als Tabelle mit Zuständigkeit am rechten Rand
- Nummerierte Überschriften ohne Punkt (1, 2, 3 nicht 1., 2., 3.)
- Sprache: Sachlich, professionell, Schweizer Hochdeutsch (ss statt ß)
- Blocksatz-Stil im Fliesstext

REGELN:
- Schreibe auf Deutsch (Schweizer Hochdeutsch)
- Fliesstext statt Aufzählungen - das wirkt professioneller
- Wenn Teilnehmer nicht namentlich genannt werden: "Teilnehmer 1", "Teilnehmer 2"
- Pendenzen/Aufgaben IMMER mit Zuständigkeit versehen
- Protokollführer am Ende: Falls nicht bekannt, weglassen
- Fasse zusammen, füge nichts Erfundenes hinzu
"""


def generate_protocol(transcript_path: str) -> str:
    """
    Generiert ein strukturiertes Protokoll aus einem Transkript.
    Gibt den Pfad zur Protokoll-Datei zurück.
    """
    # Transkript laden
    if not os.path.isfile(transcript_path):
        print(f"FEHLER: Transkript nicht gefunden: {transcript_path}")
        sys.exit(1)

    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    if not transcript.strip():
        print("FEHLER: Transkript ist leer!")
        sys.exit(1)

    print(f"Transkript geladen: {len(transcript)} Zeichen")

    # Transkript kürzen falls zu lang
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        print(f"WARNUNG: Transkript gekürzt von {len(transcript)} auf {MAX_TRANSCRIPT_CHARS} Zeichen")
        transcript = transcript[:MAX_TRANSCRIPT_CHARS]

    # OpenAI Client initialisieren
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("FEHLER: OPENAI_API_KEY nicht in .env gesetzt!")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # GPT-4o aufrufen
    print("Erstelle Protokoll mit GPT-4o...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Hier ist das Meeting-Transkript:\n\n{transcript}"}
        ],
        temperature=0.3,  # Niedrig für konsistente, faktentreue Ausgabe
        max_tokens=4096
    )

    protocol_text = response.choices[0].message.content
    print(f"Protokoll generiert: {len(protocol_text)} Zeichen")

    # Protokoll speichern
    tmp_dir = PROJECT_ROOT / ".tmp"
    tmp_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    output_path = tmp_dir / f"protocol_{timestamp}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(protocol_text)

    print(f"Protokoll gespeichert: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Verwendung: python execution/generate_protocol.py /pfad/zur/transcript.txt")
        sys.exit(1)

    transcript_file = sys.argv[1]
    result = generate_protocol(transcript_file)
    print(f"\nERGEBNIS: {result}")
