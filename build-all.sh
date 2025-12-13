#!/bin/bash
# Build all distribution packages for Voice Notepad V3
# Output: dist/ with .deb, AppImage, and tarball
#
# Usage: ./build-all.sh [VERSION] [--deb] [--appimage] [--tarball] [--checksums]
#
# Options:
#   VERSION      Version string (default: from pyproject.toml)
#   --deb        Build only Debian package
#   --appimage   Build only AppImage
#   --tarball    Build only tarball
#   --checksums  Generate SHA256 checksums (default when building all)
#
# With no format flags, builds all formats.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
VERSION=""
BUILD_DEB=false
BUILD_APPIMAGE=false
BUILD_TARBALL=false
GEN_CHECKSUMS=false
EXPLICIT_FORMAT=false

for arg in "$@"; do
    case $arg in
        --deb)
            BUILD_DEB=true
            EXPLICIT_FORMAT=true
            ;;
        --appimage)
            BUILD_APPIMAGE=true
            EXPLICIT_FORMAT=true
            ;;
        --tarball)
            BUILD_TARBALL=true
            EXPLICIT_FORMAT=true
            ;;
        --checksums)
            GEN_CHECKSUMS=true
            ;;
        *)
            # Assume it's a version if it looks like one
            if [[ "$arg" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                VERSION="$arg"
            fi
            ;;
    esac
done

# If no explicit format specified, build all
if [ "$EXPLICIT_FORMAT" = false ]; then
    BUILD_DEB=true
    BUILD_APPIMAGE=true
    BUILD_TARBALL=true
    GEN_CHECKSUMS=true
fi

# Get version from pyproject.toml if not specified
if [ -z "$VERSION" ]; then
    VERSION=$(grep -Po '(?<=^version = ")[^"]+' pyproject.toml)
fi

echo "=============================================="
echo "  Voice Notepad Multi-Format Build"
echo "  Version: $VERSION"
echo "=============================================="
echo ""

# Show what we're building
echo "Building formats:"
[ "$BUILD_DEB" = true ] && echo "  - Debian (.deb)"
[ "$BUILD_APPIMAGE" = true ] && echo "  - AppImage"
[ "$BUILD_TARBALL" = true ] && echo "  - Tarball (.tar.gz)"
echo ""

# Ensure dist directory exists
mkdir -p "$SCRIPT_DIR/dist"

# Track build results
BUILT_FILES=()
FAILED_BUILDS=()

# Build Debian package
if [ "$BUILD_DEB" = true ]; then
    echo ""
    echo ">>> Building Debian package..."
    echo "----------------------------------------"
    if ./build.sh "$VERSION"; then
        BUILT_FILES+=("dist/voice-notepad_${VERSION}_amd64.deb")
        echo "[OK] Debian package built"
    else
        FAILED_BUILDS+=("Debian")
        echo "[FAILED] Debian package"
    fi
fi

# Build AppImage
if [ "$BUILD_APPIMAGE" = true ]; then
    echo ""
    echo ">>> Building AppImage..."
    echo "----------------------------------------"
    if ./build-appimage.sh "$VERSION"; then
        BUILT_FILES+=("dist/Voice_Notepad-${VERSION}-x86_64.AppImage")
        echo "[OK] AppImage built"
    else
        FAILED_BUILDS+=("AppImage")
        echo "[FAILED] AppImage"
    fi
fi

# Build Tarball
if [ "$BUILD_TARBALL" = true ]; then
    echo ""
    echo ">>> Building Tarball..."
    echo "----------------------------------------"
    if ./build-tarball.sh "$VERSION"; then
        BUILT_FILES+=("dist/voice-notepad-${VERSION}-linux-x86_64.tar.gz")
        echo "[OK] Tarball built"
    else
        FAILED_BUILDS+=("Tarball")
        echo "[FAILED] Tarball"
    fi
fi

# Generate checksums
if [ "$GEN_CHECKSUMS" = true ] && [ ${#BUILT_FILES[@]} -gt 0 ]; then
    echo ""
    echo ">>> Generating checksums..."
    echo "----------------------------------------"

    CHECKSUM_FILE="$SCRIPT_DIR/dist/voice-notepad-${VERSION}-SHA256SUMS.txt"
    > "$CHECKSUM_FILE"

    cd "$SCRIPT_DIR/dist"
    for file in "${BUILT_FILES[@]}"; do
        filename=$(basename "$file")
        if [ -f "$filename" ]; then
            sha256sum "$filename" >> "voice-notepad-${VERSION}-SHA256SUMS.txt"
        fi
    done
    cd "$SCRIPT_DIR"

    echo "Checksums written to: $CHECKSUM_FILE"
fi

# Summary
echo ""
echo "=============================================="
echo "  Build Summary"
echo "=============================================="
echo ""

if [ ${#BUILT_FILES[@]} -gt 0 ]; then
    echo "Successfully built:"
    for file in "${BUILT_FILES[@]}"; do
        if [ -f "$SCRIPT_DIR/$file" ]; then
            SIZE=$(du -h "$SCRIPT_DIR/$file" | cut -f1)
            echo "  $file ($SIZE)"
        fi
    done
fi

if [ ${#FAILED_BUILDS[@]} -gt 0 ]; then
    echo ""
    echo "Failed builds:"
    for build in "${FAILED_BUILDS[@]}"; do
        echo "  - $build"
    done
fi

if [ "$GEN_CHECKSUMS" = true ] && [ -f "$SCRIPT_DIR/dist/voice-notepad-${VERSION}-SHA256SUMS.txt" ]; then
    echo ""
    echo "Checksums: dist/voice-notepad-${VERSION}-SHA256SUMS.txt"
fi

echo ""
echo "Output directory: $SCRIPT_DIR/dist/"
echo ""

# Exit with error if any builds failed
if [ ${#FAILED_BUILDS[@]} -gt 0 ]; then
    exit 1
fi
