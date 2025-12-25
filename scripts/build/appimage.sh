#!/bin/bash
# Build an AppImage for Voice Notepad V3
# Output: dist/Voice_Notepad-VERSION-x86_64.AppImage
#
# AppImage bundles Python + venv + app into a single executable that runs
# on any Linux distribution without installation.
#
# Usage: ./scripts/build/appimage.sh [VERSION]
#
# Requirements:
#   - appimagetool (downloaded automatically if not found)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
cd "$PROJECT_ROOT"

VERSION="${1:-1.3.0}"
PACKAGE_NAME="Voice_Notepad"
ARCH="x86_64"

echo "=== Building Voice Notepad AppImage - v${VERSION} ==="
echo ""

# Build directories
BUILD_DIR="$PROJECT_ROOT/build/appimage"
APPDIR="$BUILD_DIR/${PACKAGE_NAME}.AppDir"

# Cache directory for venv (shared with deb build)
CACHE_DIR="$PROJECT_ROOT/.build-cache"
CACHED_VENV="$CACHE_DIR/venv"
REQUIREMENTS_HASH_FILE="$CACHE_DIR/requirements.hash"

# Tools directory
TOOLS_DIR="$CACHE_DIR/tools"
APPIMAGETOOL="$TOOLS_DIR/appimagetool"

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$APPDIR"
mkdir -p "$CACHE_DIR"
mkdir -p "$TOOLS_DIR"

# Download appimagetool if not present
if [ ! -x "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    curl -L -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

# Create AppDir structure
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/opt/voice-notepad"

# Check if we need to rebuild the venv
CURRENT_HASH=$(sha256sum app/requirements.txt | cut -d' ' -f1)
CACHED_HASH=""
if [ -f "$REQUIREMENTS_HASH_FILE" ]; then
    CACHED_HASH=$(cat "$REQUIREMENTS_HASH_FILE")
fi

if [ "$CURRENT_HASH" = "$CACHED_HASH" ] && [ -d "$CACHED_VENV" ]; then
    echo "Using cached venv (requirements unchanged)..."
    cp -a "$CACHED_VENV" "$APPDIR/opt/voice-notepad/.venv"
else
    echo "Creating virtual environment and installing dependencies..."

    # Create venv using uv with system Python
    uv venv "$APPDIR/opt/voice-notepad/.venv" --python /usr/bin/python3 --seed
    source "$APPDIR/opt/voice-notepad/.venv/bin/activate"

    # Install dependencies using uv
    uv pip install -r app/requirements.txt

    deactivate 2>/dev/null || true

    # Cache the venv for next time
    echo "Caching venv for future builds..."
    rm -rf "$CACHED_VENV"
    cp -a "$APPDIR/opt/voice-notepad/.venv" "$CACHED_VENV"
    echo "$CURRENT_HASH" > "$REQUIREMENTS_HASH_FILE"
fi

# Copy source files
echo "Copying application files..."
cp -r app/src "$APPDIR/opt/voice-notepad/"
cp app/requirements.txt "$APPDIR/opt/voice-notepad/"

# Create the main executable script
cat > "$APPDIR/opt/voice-notepad/voice-notepad" << 'EOF'
#!/bin/bash
# Voice Notepad launcher for AppImage
APPDIR_ROOT="$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")"
cd "$APPDIR_ROOT/opt/voice-notepad"

export PATH="/usr/bin:$PATH"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

SITE_PACKAGES=$(find .venv/lib -name "site-packages" -type d | head -1)
export PYTHONPATH="$SITE_PACKAGES:$PYTHONPATH"

exec .venv/bin/python -m src.main "$@"
EOF
chmod +x "$APPDIR/opt/voice-notepad/voice-notepad"

# Create symlink in usr/bin
ln -s ../../opt/voice-notepad/voice-notepad "$APPDIR/usr/bin/voice-notepad"

# Create AppRun script
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"
export PATH="$APPDIR/usr/bin:$PATH"
export LD_LIBRARY_PATH="$APPDIR/usr/lib:$LD_LIBRARY_PATH"
export XDG_DATA_DIRS="$APPDIR/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"

# Qt/Wayland settings
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

exec "$APPDIR/opt/voice-notepad/voice-notepad" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Create desktop entry
cat > "$APPDIR/voice-notepad.desktop" << EOF
[Desktop Entry]
Name=Voice Notepad
Comment=Voice recording with AI-powered transcription
Exec=voice-notepad
Icon=voice-notepad
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Utility;
Keywords=voice;transcription;ai;speech;recording;
StartupWMClass=voice-notepad
X-AppImage-Version=${VERSION}
EOF

# Copy to standard location too
cp "$APPDIR/voice-notepad.desktop" "$APPDIR/usr/share/applications/"

# Create icon (SVG)
cat > "$APPDIR/voice-notepad.svg" << 'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#dc3545">
  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
</svg>
EOF

# Copy icons to standard locations
cp "$APPDIR/voice-notepad.svg" "$APPDIR/usr/share/icons/hicolor/128x128/apps/"
cp "$APPDIR/voice-notepad.svg" "$APPDIR/usr/share/icons/hicolor/256x256/apps/"

# Create .DirIcon symlink (required by AppImage spec)
ln -sf voice-notepad.svg "$APPDIR/.DirIcon"

# Build the AppImage
echo "Building AppImage..."
OUTPUT_DIR="$PROJECT_ROOT/dist"
mkdir -p "$OUTPUT_DIR"

# Run appimagetool (extract and run to avoid FUSE requirement)
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" \
    "$OUTPUT_DIR/${PACKAGE_NAME}-${VERSION}-${ARCH}.AppImage"

# Clean up build directory
rm -rf "$BUILD_DIR"

echo ""
echo "=== AppImage Build Complete ==="
echo ""
echo "Package: $OUTPUT_DIR/${PACKAGE_NAME}-${VERSION}-${ARCH}.AppImage"
echo ""
echo "To run: chmod +x ${PACKAGE_NAME}-${VERSION}-${ARCH}.AppImage && ./${PACKAGE_NAME}-${VERSION}-${ARCH}.AppImage"
echo ""
