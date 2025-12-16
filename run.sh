#!/bin/bash
# Run Voice Notepad V3 for development
# Sets up venv if needed

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/app"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/python3 -m pip install -q --upgrade pip
    .venv/bin/python3 -m pip install -q -r requirements.txt
fi

# Set dev mode flag for visual distinction in window title
export VOICE_NOTEPAD_DEV_MODE=1

# Use the venv python directly (more reliable than activate)
exec .venv/bin/python3 -m src.main "$@"
