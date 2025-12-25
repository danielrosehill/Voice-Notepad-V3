#!/bin/bash
# Take screenshots of Voice Notepad UI for releases
# Auto-detects version from pyproject.toml

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
cd "$PROJECT_ROOT/app"

# Ensure venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/python3 -m pip install -q --upgrade pip
    .venv/bin/python3 -m pip install -q -r requirements.txt
fi

exec .venv/bin/python3 -m src.screenshot_tool
