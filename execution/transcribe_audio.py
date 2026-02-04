"""
transcribe_audio.py
-------------------
Transkribiert alle Audiodateien in einem Ordner über die OpenAI Whisper API.
Speichert die Transkripte als .txt in .tmp/.

Grosse Dateien (>25MB) werden automatisch per macOS afconvert + Python
in 10-Minuten-Chunks aufgeteilt.

Verwendung:
    python execution/transcribe_audio.py /pfad/zum/audio-ordner

Rückgabe:
    Pfad zur kombinierten Transkript-Datei (.tmp/transcript_YYYY-MM-DD_HH-MM.txt)
"""

import os
import sys
import glob
import struct
import subprocess
import wave
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

# .env laden (Projektroot)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Unterstützte Audio-Formate
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".ogg", ".webm", ".mp4", ".mpeg", ".mpga")

# Whisper API Limit: 25 MB
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB in Bytes
CHUNK_DURATION_SECS = 10 * 60  # 10 Minuten pro Chunk


def find_audio_files(folder_path: str) -> list[str]:
    """Findet alle Audiodateien im angegebenen Ordner."""
    audio_files = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(glob.glob(os.path.join(folder_path, f"*{ext}")))
        # Auch Grossbuchstaben-Endungen
        audio_files.extend(glob.glob(os.path.join(folder_path, f"*{ext.upper()}")))
    # Duplikate entfernen und sortieren
    audio_files = sorted(set(audio_files))
    return audio_files


def convert_to_wav(file_path: str, output_path: str) -> bool:
    """
    Konvertiert eine Audiodatei zu WAV mit macOS afconvert.
    Funktioniert ohne ffmpeg/pydub auf jedem Mac.
    """
    try:
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", file_path, output_path],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"  FEHLER bei Konvertierung: {e.stderr}")
        return False


def split_wav_file(wav_path: str) -> list[str]:
    """
    Teilt eine WAV-Datei in Chunks von max. 10 Minuten auf.
    Rein mit Python - keine externen Abhängigkeiten nötig.
    """
    tmp_dir = PROJECT_ROOT / ".tmp"
    chunk_paths = []

    with wave.open(wav_path, "rb") as wav_in:
        n_channels = wav_in.getnchannels()
        sampwidth = wav_in.getparams().sampwidth
        framerate = wav_in.getframerate()
        total_frames = wav_in.getnframes()
        frames_per_chunk = CHUNK_DURATION_SECS * framerate

        total_duration = total_frames / framerate
        num_chunks = int(total_duration // CHUNK_DURATION_SECS) + (1 if total_duration % CHUNK_DURATION_SECS > 0 else 0)
        print(f"  Dauer: {total_duration / 60:.1f} Minuten → {num_chunks} Chunk(s)")

        for i in range(num_chunks):
            chunk_path = str(tmp_dir / f"chunk_{i+1:03d}.wav")
            frames_to_read = min(frames_per_chunk, total_frames - (i * frames_per_chunk))
            data = wav_in.readframes(frames_to_read)

            with wave.open(chunk_path, "wb") as wav_out:
                wav_out.setnchannels(n_channels)
                wav_out.setsampwidth(sampwidth)
                wav_out.setframerate(framerate)
                wav_out.writeframes(data)

            chunk_size = os.path.getsize(chunk_path)
            print(f"  Chunk {i+1}/{num_chunks}: {chunk_size / 1024 / 1024:.1f} MB")
            chunk_paths.append(chunk_path)

    return chunk_paths


def split_audio_file(file_path: str) -> list[str]:
    """
    Teilt eine grosse Audiodatei in Chunks auf.
    Konvertiert zuerst zu WAV (via macOS afconvert), dann Split per Python.
    """
    print(f"  Teile Audiodatei in Chunks auf...")

    tmp_dir = PROJECT_ROOT / ".tmp"
    tmp_dir.mkdir(exist_ok=True)

    # Schritt 1: Zu WAV konvertieren
    wav_path = str(tmp_dir / "temp_full.wav")
    print(f"  Konvertiere zu WAV...")
    if not convert_to_wav(file_path, wav_path):
        print("  FEHLER: Konvertierung fehlgeschlagen!")
        return []

    # Schritt 2: WAV in Chunks aufteilen
    chunk_paths = split_wav_file(wav_path)

    # Temporäre WAV-Datei aufräumen
    os.remove(wav_path)

    return chunk_paths


def transcribe_file(client: OpenAI, file_path: str) -> str:
    """Transkribiert eine einzelne Audiodatei über die Whisper API."""
    file_size = os.path.getsize(file_path)

    # Grosse Dateien automatisch aufteilen
    if file_size > MAX_FILE_SIZE:
        print(f"  Datei ist {file_size / 1024 / 1024:.1f} MB (> 25 MB) → Auto-Split")
        chunk_paths = split_audio_file(file_path)

        if not chunk_paths:
            return "[FEHLER: Audio-Split fehlgeschlagen]"

        # Jeden Chunk einzeln transkribieren
        all_parts = []
        for i, chunk_path in enumerate(chunk_paths, 1):
            print(f"  Transkribiere Chunk {i}/{len(chunk_paths)}...")
            with open(chunk_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="de",
                    response_format="text"
                )
            all_parts.append(transcript)
            # Chunk-Datei aufräumen
            os.remove(chunk_path)

        return " ".join(all_parts)

    print(f"  Transkribiere: {os.path.basename(file_path)} ({file_size / 1024 / 1024:.1f} MB)...")

    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="de",  # Deutsch als Standardsprache
            response_format="text"
        )

    return transcript


def transcribe_folder(folder_path: str) -> str:
    """
    Transkribiert alle Audiodateien in einem Ordner.
    Gibt den Pfad zur kombinierten Transkript-Datei zurück.
    """
    # Ordner validieren
    if not os.path.isdir(folder_path):
        print(f"FEHLER: Ordner nicht gefunden: {folder_path}")
        sys.exit(1)

    # Audiodateien finden
    audio_files = find_audio_files(folder_path)
    if not audio_files:
        print(f"WARNUNG: Keine Audiodateien gefunden in: {folder_path}")
        print(f"  Unterstützte Formate: {', '.join(AUDIO_EXTENSIONS)}")
        sys.exit(1)

    print(f"Gefunden: {len(audio_files)} Audiodatei(en)")

    # OpenAI Client initialisieren
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("FEHLER: OPENAI_API_KEY nicht in .env gesetzt!")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # .tmp/ Ordner erstellen
    tmp_dir = PROJECT_ROOT / ".tmp"
    tmp_dir.mkdir(exist_ok=True)

    # Alle Dateien transkribieren
    all_transcripts = []
    for i, audio_file in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] Verarbeite: {os.path.basename(audio_file)}")
        transcript = transcribe_file(client, audio_file)
        all_transcripts.append(f"--- {os.path.basename(audio_file)} ---\n{transcript}")

    # Kombiniertes Transkript speichern
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    output_path = tmp_dir / f"transcript_{timestamp}.txt"
    combined = "\n\n".join(all_transcripts)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(combined)

    print(f"\nTranskript gespeichert: {output_path}")
    print(f"Gesamtlänge: {len(combined)} Zeichen")

    return str(output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Verwendung: python execution/transcribe_audio.py /pfad/zum/audio-ordner")
        sys.exit(1)

    folder = sys.argv[1]
    result = transcribe_folder(folder)
    print(f"\nERGEBNIS: {result}")
