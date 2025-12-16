#!/bin/bash
# Uninstall Voice Notepad V3 Dev Launcher

set -e

DESKTOP_FILE="$HOME/.local/share/applications/voice-notepad-dev.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/256x256/apps/voice-notepad-dev.png"

echo "Uninstalling Voice Notepad V3 Dev Launcher..."

# Remove desktop entry
if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "✓ Removed desktop entry"
else
    echo "⚠ Desktop entry not found"
fi

# Remove icon
if [ -f "$ICON_FILE" ]; then
    rm "$ICON_FILE"
    echo "✓ Removed icon"
else
    echo "⚠ Icon not found"
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications"
    echo "✓ Desktop database updated"
fi

echo ""
echo "Dev launcher uninstalled successfully!"
echo ""
