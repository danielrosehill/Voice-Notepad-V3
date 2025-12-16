#!/bin/bash
# Local build script for development - no venv caching
# Builds .deb and installs it immediately

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "Building Voice Notepad (Local Dev Build)"
echo "========================================="

# Get version from pyproject.toml
VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
echo "Version: $VERSION"

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf dist/
mkdir -p dist

# Build directory
BUILD_DIR="/tmp/voice-notepad-build-$$"
echo "Build directory: $BUILD_DIR"

# Clean and create build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/opt/voice-notepad"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_DIR/usr/local/bin"

# Copy application files
echo ""
echo "Copying application files..."
cp -r app/src "$BUILD_DIR/opt/voice-notepad/"
cp pyproject.toml "$BUILD_DIR/opt/voice-notepad/"
cp app/requirements.txt "$BUILD_DIR/opt/voice-notepad/"

# Create fresh venv in build directory
echo ""
echo "Creating Python virtual environment..."
cd "$BUILD_DIR/opt/voice-notepad"
python3 -m venv .venv

# Activate and install dependencies
echo "Installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

cd "$SCRIPT_DIR"

# Create launcher script
echo ""
echo "Creating launcher script..."
cat > "$BUILD_DIR/opt/voice-notepad/voice-notepad.sh" << 'EOF'
#!/bin/bash
# Voice Notepad launcher script

# Get the directory where this script is located (follow symlinks)
SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT")"

# Set Wayland backend for Qt
export QT_QPA_PLATFORM=wayland

# Run using the venv python directly
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python3" -m src.main "$@"
EOF

chmod +x "$BUILD_DIR/opt/voice-notepad/voice-notepad.sh"

# Create symlink in /usr/local/bin
ln -s /opt/voice-notepad/voice-notepad.sh "$BUILD_DIR/usr/local/bin/voice-notepad"

# Copy icon
echo "Copying icon..."
if [ -f "assets/icon.png" ]; then
    cp assets/icon.png "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/voice-notepad.png"
else
    echo "Warning: assets/icon.png not found, skipping icon"
fi

# Create desktop entry
echo "Creating desktop entry..."
cat > "$BUILD_DIR/usr/share/applications/voice-notepad.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Voice Notepad
Comment=Voice recording with AI-powered transcription
Exec=/opt/voice-notepad/voice-notepad.sh
Icon=voice-notepad
Terminal=false
Categories=Audio;AudioVideo;Utility;
Keywords=voice;recording;transcription;AI;
StartupNotify=true
EOF

# Create DEBIAN control file
echo "Creating control file..."
INSTALLED_SIZE=$(du -sk "$BUILD_DIR" | cut -f1)

cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: voice-notepad
Version: $VERSION
Section: sound
Priority: optional
Architecture: amd64
Installed-Size: $INSTALLED_SIZE
Depends: python3 (>= 3.10), python3-venv, ffmpeg, portaudio19-dev
Maintainer: Daniel Rosehill <public@danielrosehill.com>
Description: Voice recording with AI-powered transcription
 Voice Notepad V3 is a PyQt6 desktop application for voice recording
 with AI-powered transcription and cleanup using multimodal models.
 .
 Features:
  - Record audio with system hotkeys
  - AI transcription via OpenRouter, Gemini, OpenAI, or Mistral
  - Customizable cleanup prompts with format presets
  - Voice Activity Detection (VAD) for silence removal
  - Transcript history and cost tracking
  - Audio archival in Opus format
EOF

# Build the .deb package
echo ""
echo "Building .deb package..."
DEB_FILE="$SCRIPT_DIR/dist/voice-notepad_${VERSION}_amd64.deb"
dpkg-deb --build "$BUILD_DIR" "$DEB_FILE"

# Cleanup build directory
rm -rf "$BUILD_DIR"

echo ""
echo "========================================="
echo "Build complete!"
echo "Package: $DEB_FILE"
echo "========================================="

# Install the package
echo ""
read -p "Install the package now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Installing Voice Notepad..."
    sudo dpkg -i "$DEB_FILE"

    echo ""
    echo "========================================="
    echo "Installation complete!"
    echo "Run with: voice-notepad"
    echo "========================================="
else
    echo ""
    echo "Skipping installation."
    echo "Install manually with: sudo dpkg -i $DEB_FILE"
fi
