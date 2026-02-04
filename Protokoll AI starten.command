#!/bin/bash
cd "$(dirname "$0")"

echo "🚀 Starte Protokoll AI..."
echo ""

# ffmpeg installieren falls nötig (für Audio-Splitting grosser Dateien)
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 Installiere ffmpeg für Audio-Verarbeitung..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "⚠️  Homebrew nicht gefunden. Installiere Homebrew zuerst:"
        echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo ""
        echo "   Danach erneut starten für volle Funktionalität."
    fi
    echo ""
fi

# Python-Abhängigkeiten installieren falls nötig
if ! python3 -c "import streamlit" &> /dev/null; then
    echo "📦 Installiere Python-Abhängigkeiten..."
    pip3 install -r requirements.txt
    echo ""
fi

# Browser öffnen nach 3 Sekunden
(sleep 3 && open "http://localhost:8501") &

# App starten
python3 -m streamlit run app.py --server.port 8501
