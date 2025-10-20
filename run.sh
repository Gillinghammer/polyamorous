#!/usr/bin/env bash
# Simple run script for Polly TUI
# Automatically uses the correct Python installation

# Default to `run` if no subcommand provided
if [ $# -eq 0 ]; then
  set -- run
fi

# Try to find the right Python with packages installed
if /opt/homebrew/bin/python3.11 -c "import textual" 2>/dev/null; then
    echo "Starting Polly TUI..."
    exec /opt/homebrew/bin/python3.11 -m polly "$@"
elif python3.11 -c "import textual" 2>/dev/null; then
    echo "Starting Polly TUI..."
    exec python3.11 -m polly "$@"
elif python3 -c "import textual" 2>/dev/null; then
    echo "Starting Polly TUI..."
    exec python3 -m polly "$@"
else
    echo "Error: Could not find Python with textual installed."
    echo "Please run: pip install -e ."
    exit 1
fi

