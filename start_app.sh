#!/bin/bash
# ============================================
# Protokoll AI - Start Script
# ============================================
# Startet die App und öffnet automatisch den Browser

cd "$(dirname "$0")"

# Farben für Terminal-Ausgabe
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

APP_URL="http://localhost:8501"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}    ${GREEN}Protokoll AI${NC} - Meeting-Protokoll App   ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Python finden (macOS verwendet python3)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PIP_CMD="pip"
else
    echo -e "${RED}❌ Python nicht gefunden!${NC}"
    echo ""
    echo "Bitte installiere Python:"
    echo "  1. Öffne: https://www.python.org/downloads/"
    echo "  2. Oder mit Homebrew: brew install python"
    echo ""
    exit 1
fi

echo -e "Python: ${GREEN}$($PYTHON_CMD --version)${NC}"

# Prüfen ob streamlit installiert ist
if ! $PYTHON_CMD -c "import streamlit" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Streamlit nicht gefunden. Installiere Abhängigkeiten...${NC}"
    echo ""
    $PIP_CMD install -r requirements.txt
    echo ""
fi

# Funktion um Browser zu öffnen (plattformübergreifend)
open_browser() {
    sleep 3  # Warte bis Server gestartet ist

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "$APP_URL"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v xdg-open &> /dev/null; then
            xdg-open "$APP_URL"
        elif command -v gnome-open &> /dev/null; then
            gnome-open "$APP_URL"
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows
        start "$APP_URL"
    fi

    echo -e "${GREEN}✓ Browser geöffnet: ${APP_URL}${NC}"
}

echo -e "${GREEN}🚀 Starte Protokoll AI...${NC}"
echo -e "   URL: ${BLUE}${APP_URL}${NC}"
echo ""
echo -e "${YELLOW}Drücke Ctrl+C zum Beenden${NC}"
echo ""

# Browser im Hintergrund öffnen
open_browser &

# App starten mit python3 -m streamlit
$PYTHON_CMD -m streamlit run app.py \
    --server.port 8501 \
    --server.headless true \
    --browser.gatherUsageStats false
