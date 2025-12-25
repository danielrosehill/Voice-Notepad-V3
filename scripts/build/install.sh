#!/bin/bash
# Install or upgrade Voice Notepad V3 from a built .deb package
# Finds the latest package in dist/ and installs it

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
cd "$PROJECT_ROOT"

echo "=== Voice Notepad V3 - Install/Upgrade ==="
echo ""

# Find the latest .deb package
DIST_DIR="$PROJECT_ROOT/dist"
if [ ! -d "$DIST_DIR" ]; then
    echo "Error: dist/ directory not found. Run ./build.sh --deb first."
    exit 1
fi

# Get the most recent .deb file
LATEST_DEB=$(ls -t "$DIST_DIR"/voice-notepad_*.deb 2>/dev/null | head -1)

if [ -z "$LATEST_DEB" ]; then
    echo "Error: No .deb package found in dist/. Run ./build.sh --deb first."
    exit 1
fi

# Extract version from filename
VERSION=$(basename "$LATEST_DEB" | sed 's/voice-notepad_\(.*\)_amd64.deb/\1/')

echo "Found package: $(basename "$LATEST_DEB")"
echo "Version: $VERSION"
echo ""

# Check if already installed
if dpkg -l voice-notepad 2>/dev/null | grep -q "^ii"; then
    CURRENT_VERSION=$(dpkg -l voice-notepad | grep "^ii" | awk '{print $3}')
    echo "Currently installed: v$CURRENT_VERSION"
    echo "Installing: v$VERSION"
    echo ""
fi

# Install/upgrade
echo "Installing package (requires sudo)..."
sudo dpkg -i "$LATEST_DEB"

# Fix any missing dependencies
if [ $? -ne 0 ]; then
    echo ""
    echo "Fixing dependencies..."
    sudo apt-get install -f -y
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Run with: voice-notepad"
echo "Or search 'Voice Notepad' in your app launcher"
echo ""
