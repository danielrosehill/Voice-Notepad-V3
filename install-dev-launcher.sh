#!/bin/bash
# Install Voice Notepad V3 Dev Launcher
# Creates a system launcher that runs the dev version from this repository

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/voice-notepad-dev.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_FILE="$ICON_DIR/voice-notepad-dev.png"

echo "Installing Voice Notepad V3 Dev Launcher..."

# Create icon directory if needed
mkdir -p "$ICON_DIR"

# Copy icon if it exists
if [ -f "$SCRIPT_DIR/app/icon.png" ]; then
    cp "$SCRIPT_DIR/app/icon.png" "$ICON_FILE"
    echo "✓ Icon installed to $ICON_FILE"
else
    echo "⚠ Warning: icon.png not found, launcher will use default icon"
fi

# Create desktop entry
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Voice Notepad V3 (Dev)
Comment=Voice recording with AI transcription (Development Version)
Exec=$SCRIPT_DIR/run.sh
Icon=voice-notepad-dev
Terminal=false
Categories=AudioVideo;Audio;Recorder;
StartupWMClass=voice-notepad-v3
Keywords=voice;audio;transcription;recording;AI;
EOF

chmod +x "$DESKTOP_FILE"

echo "✓ Desktop entry created at $DESKTOP_FILE"

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications"
    echo "✓ Desktop database updated"
fi

echo ""
echo "============================================"
echo "Dev launcher installed successfully!"
echo "============================================"
echo ""
echo "You should now see 'Voice Notepad V3 (Dev)' in your application menu."
echo "This launcher runs the dev version from:"
echo "  $SCRIPT_DIR/run.sh"
echo ""
echo "To uninstall the dev launcher, run:"
echo "  ./uninstall-dev-launcher.sh"
echo ""