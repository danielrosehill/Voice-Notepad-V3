#!/bin/bash
# Voice Notepad V3 - Build Script
#
# Master entry point for all build operations.
# Individual build scripts are in scripts/build/
#
# Usage:
#   ./build.sh                  Show this help
#   ./build.sh --deb [VERSION]  Build Debian package
#   ./build.sh --appimage [V]   Build AppImage
#   ./build.sh --tarball [V]    Build tarball
#   ./build.sh --all [VERSION]  Build all formats
#   ./build.sh --install        Install latest .deb
#   ./build.sh --dev            Quick dev build (fast mode)
#   ./build.sh --release [TYPE] Version bump + build (TYPE: major|minor|patch)
#   ./build.sh --screenshots    Take screenshots for release
#
# Examples:
#   ./build.sh --deb 1.3.0      Build v1.3.0 .deb
#   ./build.sh --all            Build all formats (version from pyproject.toml)
#   ./build.sh --dev            Fast dev build + install
#   ./build.sh --release minor  Bump minor version and build all

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_SCRIPTS="$SCRIPT_DIR/scripts/build"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${BLUE}Voice Notepad V3 - Build System${NC}"
    echo ""
    echo "Usage: ./build.sh <command> [options]"
    echo ""
    echo -e "${GREEN}Package Builds:${NC}"
    echo "  --deb [VERSION]       Build Debian package (.deb)"
    echo "  --appimage [VERSION]  Build AppImage"
    echo "  --tarball [VERSION]   Build portable tarball"
    echo "  --all [VERSION]       Build all formats + checksums"
    echo ""
    echo -e "${GREEN}Development:${NC}"
    echo "  --dev                 Fast dev build (--deb --fast + install)"
    echo "  --install             Install latest .deb from dist/"
    echo ""
    echo -e "${GREEN}Release:${NC}"
    echo "  --release [TYPE]      Bump version + screenshots + build all"
    echo "                        TYPE: major, minor, or patch (default: patch)"
    echo "  --release-deb [TYPE]  Same as --release but only build .deb"
    echo "  --screenshots         Take screenshots for release"
    echo ""
    echo -e "${GREEN}Options:${NC}"
    echo "  --fast                Skip compression (faster, larger .deb)"
    echo "  --checksums           Generate SHA256 checksums"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./build.sh --deb 1.3.0        # Build v1.3.0 .deb"
    echo "  ./build.sh --all              # Build all (version from pyproject.toml)"
    echo "  ./build.sh --dev              # Quick dev iteration"
    echo "  ./build.sh --release minor    # Bump minor version, build all"
    echo ""

    # Show current version
    if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
        VERSION=$(grep -Po '(?<=^version = ")[^"]+' "$SCRIPT_DIR/pyproject.toml")
        echo -e "${BLUE}Current version: $VERSION${NC}"
    fi
}

# No arguments - show help
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

# Parse first argument as command
COMMAND="$1"
shift

case "$COMMAND" in
    --deb|-d)
        exec "$BUILD_SCRIPTS/deb.sh" "$@"
        ;;
    --appimage|-a)
        exec "$BUILD_SCRIPTS/appimage.sh" "$@"
        ;;
    --tarball|-t)
        exec "$BUILD_SCRIPTS/tarball.sh" "$@"
        ;;
    --all)
        exec "$BUILD_SCRIPTS/all.sh" "$@"
        ;;
    --install|-i)
        exec "$BUILD_SCRIPTS/install.sh" "$@"
        ;;
    --dev)
        # Quick dev build: fast deb + install
        echo -e "${BLUE}=== Quick Dev Build ===${NC}"
        "$BUILD_SCRIPTS/deb.sh" --fast "$@"
        "$BUILD_SCRIPTS/install.sh"
        ;;
    --release|-r)
        # Full release: version bump + screenshots + all formats
        exec "$BUILD_SCRIPTS/release.sh" "$@"
        ;;
    --release-deb)
        # Personal release: version bump + screenshots + deb only
        exec "$BUILD_SCRIPTS/release.sh" --deb-only "$@"
        ;;
    --screenshots|-s)
        exec "$BUILD_SCRIPTS/screenshots.sh" "$@"
        ;;
    --help|-h)
        show_help
        exit 0
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
