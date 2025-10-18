#!/usr/bin/env bash
# Simple run script for Poly TUI
# Automatically uses the correct Python installation

# Try to find the right Python with packages installed
if /opt/homebrew/bin/python3.11 -c "import textual" 2>/dev/null; then
    echo "Starting Poly TUI..."
    exec /opt/homebrew/bin/python3.11 -m poly "$@"
elif python3.11 -c "import textual" 2>/dev/null; then
    echo "Starting Poly TUI..."
    exec python3.11 -m poly "$@"
elif python3 -c "import textual" 2>/dev/null; then
    echo "Starting Poly TUI..."
    exec python3 -m poly "$@"
else
    echo "Error: Could not find Python with textual installed."
    echo "Please run: pip install -e ."
    exit 1
fi

