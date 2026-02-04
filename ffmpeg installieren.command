#!/bin/bash
echo "🔧 Installiere ffmpeg..."
echo ""

# Prüfen ob Homebrew installiert ist
if ! command -v brew &> /dev/null; then
    echo "📦 Homebrew wird zuerst installiert..."
    echo "(Das kann einige Minuten dauern)"
    echo ""
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Homebrew zum PATH hinzufügen (Apple Silicon)
    if [ -f "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

echo ""
echo "📦 Installiere ffmpeg..."
brew install ffmpeg

echo ""
echo "✅ Fertig! Du kannst dieses Fenster schliessen."
echo "   Starte jetzt 'Protokoll AI starten.command' neu."
echo ""
read -p "Drücke Enter zum Beenden..."
