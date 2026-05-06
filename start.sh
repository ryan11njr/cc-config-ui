#!/usr/bin/env bash
# CC CONFIG UI - Mac/Linux Launcher
echo ""
echo "  Starting CC CONFIG UI..."
echo "  Opening browser..."
echo ""

# Open browser (try different commands)
if command -v xdg-open &> /dev/null; then
    xdg-open http://127.0.0.1:8787
elif command -v open &> /dev/null; then
    open http://127.0.0.1:8787
fi

# Get the directory where this script lives
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/server.py"
