#!/bin/bash
cd "$(dirname "$0")"

echo "🚀 Protokoll AI - GitHub Deployment"
echo ""

# Prüfen ob gh (GitHub CLI) installiert ist
if ! command -v gh &> /dev/null; then
    echo "📦 Installiere GitHub CLI..."
    brew install gh
fi

# GitHub Login prüfen
if ! gh auth status &> /dev/null; then
    echo "🔐 Bitte bei GitHub anmelden..."
    gh auth login
fi

# Repository erstellen
echo ""
echo "📁 Erstelle GitHub Repository..."
gh repo create protokoll-ai --private --source=. --push

echo ""
echo "✅ Fertig! Dein Repository ist jetzt auf GitHub."
echo ""
echo "Nächster Schritt:"
echo "1. Gehe zu https://share.streamlit.io"
echo "2. Klicke 'New app'"
echo "3. Wähle dein Repository 'protokoll-ai'"
echo "4. Main file: app.py"
echo "5. Unter 'Advanced settings' -> 'Secrets' füge ein:"
echo ""
echo "   APP_PASSWORD = \"spektrum2024\""
echo "   ADMIN_PASSWORD = \"spektrumadmin2024\""
echo "   OPENAI_API_KEY = \"dein-key\""
echo "   SMTP_EMAIL = \"deine-email\""
echo "   SMTP_PASSWORD = \"dein-app-passwort\""
echo ""
read -p "Drücke Enter zum Beenden..."
