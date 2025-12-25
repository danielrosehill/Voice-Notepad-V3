#!/bin/bash
# Parked Code: Automatic Screenshot Capture During Release
# Originally from: scripts/build/release.sh (lines 75-76)
# Removed: 2025-12-17
# Reason: User preference to manually control when screenshots are taken
#
# This snippet automatically took screenshots during the release process.
# It can be re-enabled by adding it back to release.sh if needed.

echo ""
echo "=== Taking Screenshots ==="
"$SCRIPT_DIR/screenshots.sh"
