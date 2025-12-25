#!/bin/bash
# Build a portable tarball for Voice Notepad V3
# Output: dist/voice-notepad-VERSION-linux-x86_64.tar.gz
#
# Creates a self-contained archive that can be extracted anywhere.
# Includes install.sh for optional system integration.
#
# Usage: ./scripts/build/tarball.sh [VERSION]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
cd "$PROJECT_ROOT"

VERSION="${1:-1.3.0}"
PACKAGE_NAME="voice-notepad"
ARCH="x86_64"

echo "=== Building Voice Notepad Tarball - v${VERSION} ==="
echo ""

# Build directories
BUILD_DIR="$PROJECT_ROOT/build/tarball"
PKG_DIR="$BUILD_DIR/${PACKAGE_NAME}-${VERSION}"

# Cache directory for venv (shared with other builds)
CACHE_DIR="$PROJECT_ROOT/.build-cache"
CACHED_VENV="$CACHE_DIR/venv"
REQUIREMENTS_HASH_FILE="$CACHE_DIR/requirements.hash"

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$PKG_DIR"
mkdir -p "$CACHE_DIR"

# Check if we need to rebuild the venv
CURRENT_HASH=$(sha256sum app/requirements.txt | cut -d' ' -f1)
CACHED_HASH=""
if [ -f "$REQUIREMENTS_HASH_FILE" ]; then
    CACHED_HASH=$(cat "$REQUIREMENTS_HASH_FILE")
fi

if [ "$CURRENT_HASH" = "$CACHED_HASH" ] && [ -d "$CACHED_VENV" ]; then
    echo "Using cached venv (requirements unchanged)..."
    cp -a "$CACHED_VENV" "$PKG_DIR/.venv"
else
    echo "Creating virtual environment and installing dependencies..."

    # Create venv using uv with system Python
    uv venv "$PKG_DIR/.venv" --python /usr/bin/python3 --seed
    source "$PKG_DIR/.venv/bin/activate"

    # Install dependencies using uv
    uv pip install -r app/requirements.txt

    deactivate 2>/dev/null || true

    # Cache the venv for next time
    echo "Caching venv for future builds..."
    rm -rf "$CACHED_VENV"
    cp -a "$PKG_DIR/.venv" "$CACHED_VENV"
    echo "$CURRENT_HASH" > "$REQUIREMENTS_HASH_FILE"
fi

# Copy source files
echo "Copying application files..."
cp -r app/src "$PKG_DIR/"
cp app/requirements.txt "$PKG_DIR/"

# Create run script
cat > "$PKG_DIR/voice-notepad" << 'EOF'
#!/bin/bash
# Voice Notepad launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="/usr/bin:$PATH"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

SITE_PACKAGES=$(find .venv/lib -name "site-packages" -type d | head -1)
export PYTHONPATH="$SITE_PACKAGES:$PYTHONPATH"

exec .venv/bin/python -m src.main "$@"
EOF
chmod +x "$PKG_DIR/voice-notepad"

# Create icon
mkdir -p "$PKG_DIR/icons"
cat > "$PKG_DIR/icons/voice-notepad.svg" << 'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#dc3545">
  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
</svg>
EOF

# Create desktop entry template
cat > "$PKG_DIR/voice-notepad.desktop" << 'EOF'
[Desktop Entry]
Name=Voice Notepad
Comment=Voice recording with AI-powered transcription
Exec=INSTALL_PATH/voice-notepad
Icon=INSTALL_PATH/icons/voice-notepad.svg
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Utility;
Keywords=voice;transcription;ai;speech;recording;
StartupWMClass=voice-notepad
EOF

# Create install script for system integration
cat > "$PKG_DIR/install.sh" << 'INSTALL_EOF'
#!/bin/bash
# Install Voice Notepad to system
# Creates symlink in /usr/local/bin and desktop entry
#
# Usage: sudo ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo ./install.sh"
    exit 1
fi

echo "Installing Voice Notepad..."

# Create symlink
ln -sf "$SCRIPT_DIR/voice-notepad" /usr/local/bin/voice-notepad
echo "Created symlink: /usr/local/bin/voice-notepad"

# Install desktop entry
DESKTOP_FILE="/usr/share/applications/voice-notepad.desktop"
sed "s|INSTALL_PATH|$SCRIPT_DIR|g" "$SCRIPT_DIR/voice-notepad.desktop" > "$DESKTOP_FILE"
echo "Installed desktop entry: $DESKTOP_FILE"

# Install icon
mkdir -p /usr/share/icons/hicolor/128x128/apps
cp "$SCRIPT_DIR/icons/voice-notepad.svg" /usr/share/icons/hicolor/128x128/apps/
echo "Installed icon"

# Update caches
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo ""
echo "Installation complete!"
echo "Run 'voice-notepad' or find it in your applications menu."
INSTALL_EOF
chmod +x "$PKG_DIR/install.sh"

# Create uninstall script
cat > "$PKG_DIR/uninstall.sh" << 'UNINSTALL_EOF'
#!/bin/bash
# Uninstall Voice Notepad from system
# Removes symlink and desktop entry (not the app directory)
#
# Usage: sudo ./uninstall.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo ./uninstall.sh"
    exit 1
fi

echo "Uninstalling Voice Notepad..."

rm -f /usr/local/bin/voice-notepad
rm -f /usr/share/applications/voice-notepad.desktop
rm -f /usr/share/icons/hicolor/128x128/apps/voice-notepad.svg

# Update caches
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo "Uninstallation complete."
echo "You can now delete this directory if desired."
UNINSTALL_EOF
chmod +x "$PKG_DIR/uninstall.sh"

# Create README
cat > "$PKG_DIR/README.txt" << EOF
Voice Notepad v${VERSION}
========================

Voice recording with AI-powered transcription and cleanup.

QUICK START
-----------
Run directly: ./voice-notepad

Or install to system: sudo ./install.sh
Then run: voice-notepad

REQUIREMENTS
------------
- Python 3.10+
- ffmpeg
- portaudio (libportaudio2)

On Debian/Ubuntu: sudo apt install ffmpeg portaudio19-dev

CONFIGURATION
-------------
On first run, go to Settings and add your API key:
- OpenRouter (recommended): https://openrouter.ai/
- Google Gemini: https://aistudio.google.com/
- OpenAI: https://platform.openai.com/
- Mistral: https://console.mistral.ai/

UNINSTALL
---------
If installed to system: sudo ./uninstall.sh
Then delete this directory.

MORE INFO
---------
https://github.com/danielrosehill/Voice-Notepad-V3
EOF

# Create the tarball
echo "Creating tarball..."
OUTPUT_DIR="$PROJECT_ROOT/dist"
mkdir -p "$OUTPUT_DIR"

cd "$BUILD_DIR"
tar -czf "$OUTPUT_DIR/${PACKAGE_NAME}-${VERSION}-linux-${ARCH}.tar.gz" "${PACKAGE_NAME}-${VERSION}"

# Clean up build directory
rm -rf "$BUILD_DIR"

echo ""
echo "=== Tarball Build Complete ==="
echo ""
echo "Package: $OUTPUT_DIR/${PACKAGE_NAME}-${VERSION}-linux-${ARCH}.tar.gz"
echo ""
echo "To use:"
echo "  tar -xzf ${PACKAGE_NAME}-${VERSION}-linux-${ARCH}.tar.gz"
echo "  cd ${PACKAGE_NAME}-${VERSION}"
echo "  ./voice-notepad"
echo ""
