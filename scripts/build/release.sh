#!/bin/bash
# Release script for Voice Notepad
# - Increments version (patch by default)
# - Builds packages (all formats for public release, or deb-only for personal use)
#
# Usage: ./scripts/build/release.sh [major|minor|patch] [--deb-only]
#   Default: patch (1.3.0 -> 1.3.1)
#   --deb-only: Only build Debian package (skip AppImage/tarball)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
cd "$PROJECT_ROOT"

# Parse arguments
BUMP_TYPE="patch"
DEB_ONLY=false

for arg in "$@"; do
    case $arg in
        major|minor|patch)
            BUMP_TYPE="$arg"
            ;;
        --deb-only)
            DEB_ONLY=true
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: ./scripts/build/release.sh [major|minor|patch] [--deb-only]"
            exit 1
            ;;
    esac
done

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep -Po '(?<=^version = ")[^"]+' pyproject.toml)
echo "Current version: $CURRENT_VERSION"

# Parse version
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
VERSION_UNDERSCORE="${MAJOR}_${MINOR}_${PATCH}"

echo "New version: $NEW_VERSION"
if [ "$DEB_ONLY" = true ]; then
    echo "Mode: Debian only (personal use)"
else
    echo "Mode: Full release (all formats)"
fi
echo ""

# Update version in pyproject.toml
sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
echo "Updated pyproject.toml"

echo ""
echo "=== Building Packages ==="

if [ "$DEB_ONLY" = true ]; then
    # Personal use: just build the deb
    "$SCRIPT_DIR/deb.sh" "$NEW_VERSION"
else
    # Public release: build all formats
    "$SCRIPT_DIR/all.sh" "$NEW_VERSION"
fi

echo ""
echo "=== Release Complete ==="
echo "Version: $NEW_VERSION"

if [ "$DEB_ONLY" = true ]; then
    echo "Package: dist/voice-notepad_${NEW_VERSION}_amd64.deb"
else
    echo "Packages:"
    echo "  - dist/voice-notepad_${NEW_VERSION}_amd64.deb"
    echo "  - dist/Voice_Notepad-${NEW_VERSION}-x86_64.AppImage"
    echo "  - dist/voice-notepad-${NEW_VERSION}-linux-x86_64.tar.gz"
    echo "  - dist/voice-notepad-${NEW_VERSION}-SHA256SUMS.txt"
fi
