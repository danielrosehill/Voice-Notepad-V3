#!/bin/bash
# Build Debian package for Voice Notepad V3
# Targets: Ubuntu/Debian with Python 3.10+

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build"
DIST_DIR="$PROJECT_DIR/dist"

# Package metadata
APP_NAME="voice-notepad"
VERSION=$(grep 'version = ' "$PROJECT_DIR/pyproject.toml" | head -1 | cut -d'"' -f2)
MAINTAINER="Daniel Rosehill <public@danielrosehill.com>"
DESCRIPTION="Voice recording with AI-powered transcription and cleanup"
ARCH="all"  # Python package, architecture independent

echo "Building $APP_NAME version $VERSION"

# Check dependencies
check_deps() {
    local missing=()

    command -v dpkg-deb >/dev/null || missing+=("dpkg-deb")
    command -v fakeroot >/dev/null || missing+=("fakeroot")

    if [ ${#missing[@]} -gt 0 ]; then
        echo "Missing build dependencies: ${missing[*]}"
        echo "Install with: sudo apt install dpkg fakeroot"
        exit 1
    fi
}

# Clean previous builds
clean() {
    echo "Cleaning previous builds..."
    rm -rf "$BUILD_DIR"
    rm -rf "$DIST_DIR"
}

# Create directory structure
create_structure() {
    echo "Creating package structure..." >&2

    local pkg_dir="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}"

    # Create directories
    mkdir -p "$pkg_dir/DEBIAN"
    mkdir -p "$pkg_dir/usr/lib/$APP_NAME"
    mkdir -p "$pkg_dir/usr/bin"
    mkdir -p "$pkg_dir/usr/share/applications"
    mkdir -p "$pkg_dir/usr/share/icons/hicolor/256x256/apps"
    mkdir -p "$pkg_dir/usr/share/doc/$APP_NAME"

    echo "$pkg_dir"
}

# Copy application files
copy_files() {
    local pkg_dir="$1"

    echo "Copying application files..."

    # Copy Python source
    cp -r "$PROJECT_DIR/src" "$pkg_dir/usr/lib/$APP_NAME/"
    cp "$PROJECT_DIR/requirements.txt" "$pkg_dir/usr/lib/$APP_NAME/"
    cp "$PROJECT_DIR/pyproject.toml" "$pkg_dir/usr/lib/$APP_NAME/"

    # Copy documentation
    cp "$PROJECT_DIR/README.md" "$pkg_dir/usr/share/doc/$APP_NAME/"
    cp "$PROJECT_DIR/.env.example" "$pkg_dir/usr/share/doc/$APP_NAME/"

    # Create launcher script
    cat > "$pkg_dir/usr/bin/$APP_NAME" << 'LAUNCHER'
#!/bin/bash
# Voice Notepad launcher

INSTALL_DIR="/usr/lib/voice-notepad"
VENV_DIR="$HOME/.local/share/voice-notepad/venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "First run: Setting up Python environment..."
    mkdir -p "$(dirname "$VENV_DIR")"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
fi

# Run the application from install directory
cd "$INSTALL_DIR"
exec "$VENV_DIR/bin/python" -m src.main "$@"
LAUNCHER
    chmod +x "$pkg_dir/usr/bin/$APP_NAME"
}

# Create .desktop file
create_desktop_file() {
    local pkg_dir="$1"

    echo "Creating desktop entry..."

    cat > "$pkg_dir/usr/share/applications/$APP_NAME.desktop" << DESKTOP
[Desktop Entry]
Name=Voice Notepad
Comment=Voice recording with AI transcription
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Utility;
Keywords=voice;recording;transcription;ai;speech;
StartupWMClass=voice-notepad
DESKTOP
}

# Create control file
create_control() {
    local pkg_dir="$1"

    echo "Creating control files..."

    # Calculate installed size (in KB)
    local size=$(du -sk "$pkg_dir/usr" | cut -f1)

    cat > "$pkg_dir/DEBIAN/control" << CONTROL
Package: $APP_NAME
Version: $VERSION
Section: sound
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-venv, python3-pip, ffmpeg, libportaudio2
Installed-Size: $size
Maintainer: $MAINTAINER
Description: $DESCRIPTION
 Voice Notepad V3 uses multimodal AI models (Gemini, OpenAI, Mistral)
 to transcribe and clean up voice recordings in a single pass.
 Features include global hotkeys, markdown output, and system tray integration.
Homepage: https://github.com/danielrosehill/Voice-Notepad-V3
CONTROL
}

# Create postinst script
create_postinst() {
    local pkg_dir="$1"

    cat > "$pkg_dir/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e

# Update desktop database
if command -v update-desktop-database >/dev/null; then
    update-desktop-database -q /usr/share/applications || true
fi

# Update icon cache
if command -v gtk-update-icon-cache >/dev/null; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

echo ""
echo "Voice Notepad installed successfully!"
echo ""
echo "First run will set up a Python virtual environment."
echo "Configure API keys in Settings or ~/.config/voice-notepad-v3/config.json"
echo ""

exit 0
POSTINST
    chmod +x "$pkg_dir/DEBIAN/postinst"
}

# Create postrm script
create_postrm() {
    local pkg_dir="$1"

    cat > "$pkg_dir/DEBIAN/postrm" << 'POSTRM'
#!/bin/bash
set -e

case "$1" in
    purge)
        # Remove user data on purge
        echo "Note: User config in ~/.config/voice-notepad-v3/ not removed."
        echo "Note: Python venv in ~/.local/share/voice-notepad/ not removed."
        echo "Remove manually if desired."
        ;;
esac

# Update desktop database
if command -v update-desktop-database >/dev/null; then
    update-desktop-database -q /usr/share/applications || true
fi

exit 0
POSTRM
    chmod +x "$pkg_dir/DEBIAN/postrm"
}

# Build the package
build_package() {
    local pkg_dir="$1"

    echo "Building .deb package..."

    mkdir -p "$DIST_DIR"

    # Set correct permissions
    find "$pkg_dir" -type d -exec chmod 755 {} \;
    find "$pkg_dir/usr" -type f -exec chmod 644 {} \;
    chmod 755 "$pkg_dir/usr/bin/$APP_NAME"
    chmod 755 "$pkg_dir/DEBIAN/postinst"
    chmod 755 "$pkg_dir/DEBIAN/postrm"

    # Build with fakeroot
    fakeroot dpkg-deb --build "$pkg_dir" "$DIST_DIR/"

    local deb_file="$DIST_DIR/${APP_NAME}_${VERSION}_${ARCH}.deb"

    echo ""
    echo "Package built: $deb_file"
    echo "Size: $(du -h "$deb_file" | cut -f1)"
    echo ""
    echo "Install with: sudo dpkg -i $deb_file"
    echo "Or:           sudo apt install ./$deb_file"
}

# Main
main() {
    cd "$PROJECT_DIR"

    check_deps
    clean

    local pkg_dir=$(create_structure)

    copy_files "$pkg_dir"
    create_desktop_file "$pkg_dir"
    create_control "$pkg_dir"
    create_postinst "$pkg_dir"
    create_postrm "$pkg_dir"
    build_package "$pkg_dir"
}

main "$@"
