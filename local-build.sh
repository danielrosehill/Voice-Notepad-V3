#!/bin/bash
# Voice Notepad - Local Build & Install
#
# Builds a .deb package and installs it locally without publishing.
# This is a convenience wrapper around: ./build.sh --dev

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Voice Notepad: Local Build & Install ==="
echo ""

# Run the dev build (fast deb + install)
"$SCRIPT_DIR/build.sh" --dev

echo ""
echo "Done! Voice Notepad has been built and installed locally."
