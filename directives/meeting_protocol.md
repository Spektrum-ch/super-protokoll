# Directive: Meeting-Audiodatei → Protokoll-PDF → E-Mail

## Ziel

Audiodateien von Meetings automatisch transkribieren, in ein strukturiertes Protokoll umwandeln, als PDF speichern und per E-Mail versenden.

## Schnellstart (für den Agenten)

**WICHTIG:** Immer das Orchestrator-Script verwenden, um den kompletten Workflow auszuführen:

```bash
python3 execution/run_meeting_workflow.py /pfad/zum/audio-ordner
```

**Mit spezifischem Empfänger:**
```bash
python3 execution/run_meeting_workflow.py /pfad/zum/audio-ordner empfaenger@email.com
```

Das Script führt automatisch alle 4 Schritte aus:
1. ✅ Transkribieren (Whisper API)
2. ✅ Protokoll generieren (GPT-4o)
3. ✅ PDF erstellen
4. ✅ E-Mail versenden

**NICHT** die einzelnen Scripts manuell nacheinander aufrufen!

## Inputs

- **Ordner-Pfad**: Pfad zu einem Ordner mit Audiodateien (mp3, wav, m4a, ogg, webm)
- **Empfänger** (optional): E-Mail-Adresse. Standard: `andreas.rupf@gmail.com`

## Ablauf (intern)

### Schritt 1: Transkription
- **Script:** `execution/transcribe_audio.py`
- Alle Audiodateien im Ordner finden
- Jede Datei über OpenAI Whisper API transkribieren
- Transkripte als `.txt` in `.tmp/` speichern
- Bei Dateien >25MB: Datei in Chunks aufteilen (Whisper-Limit)

### Schritt 2: Protokoll-Erstellung
- **Script:** `execution/generate_protocol.py`
- Transkript an GPT-4o senden mit strukturiertem Prompt
- Protokoll gemäss Vorlage (siehe unten) strukturieren
- Ergebnis als Markdown in `.tmp/` speichern

### Schritt 3: PDF-Erstellung
- **Script:** `execution/create_pdf.py`
- Markdown-Protokoll in sauber formatiertes PDF umwandeln
- PDF im Audio-Quellordner ablegen
- Dateiname: `Protokoll_YYYY-MM-DD_HH-MM.pdf`

### Schritt 4: E-Mail-Versand
- **Script:** `execution/send_email.py`
- PDF als Anhang per SMTP (Gmail) versenden
- Betreff: `Meeting-Protokoll vom [Datum]`
- Kurzer Body-Text mit Hinweis auf Anhang

### Orchestrierung
- **Script:** `execution/run_meeting_workflow.py`
- Führt Schritte 1-4 nacheinander aus
- Logging und Fehlerbehandlung an jeder Stelle

## Outputs

- **PDF-Datei** im Audio-Quellordner
- **E-Mail** mit PDF-Anhang an den Empfänger

## Benötigte Konfiguration (.env)

```
OPENAI_API_KEY=sk-...
SMTP_EMAIL=absender@gmail.com
SMTP_PASSWORD=gmail-app-passwort
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
DEFAULT_RECIPIENT=andreas.rupf@gmail.com
```

## Protokoll-Vorlage

Das generierte Protokoll folgt einem professionellen Layout, inspiriert von RAST Raumstrategie (strukturiertes Deckblatt) und ETH RAUM (kompakter Fliesstext). Siehe Beispiele in `directives/examples/`.

### Markdown-Format (intern)

Das GPT-generierte Protokoll verwendet spezielle Marker:

```markdown
===DECKBLATT===

# [Projekt/Thema]
## Protokoll der Sitzung

**Datum:** [Datum]

**Teilnehmende**
| Name | Funktion/Organisation |
| --- | --- |
| [Name 1] | [Funktion 1] |
| [Name 2] | [Funktion 2] |

**Traktanden**
1. [Erstes Thema]
2. [Zweites Thema]
3. [Drittes Thema]

===INHALT===

## 1 [Erstes Traktandum]

[Fliesstext mit Zusammenfassung des besprochenen Themas...]

## 2 [Zweites Traktandum]

[Fliesstext...]

| Aufgabe | Zuständig |
| --- | --- |
| [Aufgabe 1] | [Person] |
| [Aufgabe 2] | [Person] |

===ABSCHLUSS===

[Protokollführer], [Datum]
```

### PDF-Layout

**Deckblatt-Bereich (oben):**
- Projekttitel grau, 11pt
- "Protokoll der Sitzung" fett, 14pt
- Metadaten (Datum, Ort) mit Label fett
- Teilnehmende als Tabelle (Name | Funktion)
- Traktanden nummeriert

**Trennlinie** zwischen Deckblatt und Inhalt

**Inhalt:**
- Nummerierte Überschriften fett, 11pt (z.B. "1  Verhandlungsstrategien")
- Fliesstext 10pt, Blocksatz-ähnlich
- Aufgaben als Liste mit Bullet (-) und Zuständigkeit rechts ausgerichtet

**Fusszeile:**
- Format: "1/2  [Dokumenttitel]"
- Auf jeder Seite unten links

**Header (ab Seite 2):**
- Dokumenttitel fett, 10pt

### Formatierungsregeln

- **Sprache**: Sachlich, prägnant, Schweizer Hochdeutsch (ss statt ß)
- **Überschriften**: Nummeriert ohne Punkt (1, 2, 3)
- **Aufgaben**: In Tabelle am Ende des relevanten Abschnitts
- **Fliesstext**: Zusammenfassend, keine Bullet-Listen im Inhalt
- **Schriftart**: Helvetica (eingebettet in PDF)

## Edge Cases & Learnings

- **Whisper API Limit:** Max 25MB pro Datei. Bei grösseren Dateien muss die Datei in Chunks aufgeteilt werden (pydub).
- **Lange Meetings:** Bei Transkripten >100k Zeichen ggf. in Teilen an GPT-4o senden.
- **SMTP-Auth-Fehler:** Gmail erfordert ein App-Passwort (nicht das normale Passwort). 2FA muss aktiv sein.
- **Leerer Ordner:** Script gibt Warnung aus und bricht sauber ab.
- **Keine Teilnehmer erkannt:** GPT-4o markiert Sprecher als "Sprecher 1", "Sprecher 2" etc.
- **Fehlende To-Dos:** Falls keine Aufgaben besprochen wurden, Abschnitt trotzdem aufführen mit "Keine To-Dos definiert."
- **Unklare Beschlüsse:** Als "Offener Punkt" markieren, nicht weglassen.
