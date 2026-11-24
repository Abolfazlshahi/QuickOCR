#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PY="$SCRIPT_DIR/.venv/bin/python"
else
    PY="$(command -v python3)"
fi

export LITEPARSE_MODEL_DIR="$SCRIPT_DIR/models"
exec "$PY" "$SCRIPT_DIR/app.py" "$@"
