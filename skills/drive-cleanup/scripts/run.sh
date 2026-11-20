#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="python3"

# Verify python availability
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    echo "Error: python3 is not installed or not in PATH." >&2
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/drive_cleanup.py" "$@"
