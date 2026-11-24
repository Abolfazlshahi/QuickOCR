#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  QuickOCR Linux Setup (OCRia-nano-1)"
echo "============================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 (3.10+) not found. Install Python 3 and python3-venv first."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/4] Virtual environment already exists."
fi

echo "[2/4] Installing Python dependencies..."
.venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1 || true
.venv/bin/python -m pip install -r requirements.txt

export LITEPARSE_MODEL_DIR="$SCRIPT_DIR/models"
if [ ! -f "models/ocria-nano/det.onnx" ] || ! ls models/ocria-nano/runtime/libonnxruntime.so* >/dev/null 2>&1; then
    echo "[3/4] Downloading default ocria-nano Linux weights & runtime..."
    .venv/bin/lit models pull ocria-nano
else
    echo "[3/4] Bundled ocria-nano Linux model verified offline."
fi

echo "[4/4] Registering desktop entry & permissions..."
chmod +x "$SCRIPT_DIR/QuickOCR.sh" "$SCRIPT_DIR/setup_linux.sh"

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APP_DIR"
cat > "$APP_DIR/quickocr.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=QuickOCR
Comment=Minimal pure-black trilingual offline OCR utility
Exec="$SCRIPT_DIR/QuickOCR.sh" %U
Path=$SCRIPT_DIR
Icon=$SCRIPT_DIR/assets/logo.png
Terminal=false
Categories=Utility;Graphics;
StartupNotify=false
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo ""
echo "[DONE] QuickOCR installed cleanly!"
echo " - Launch from your Applications menu or run: $SCRIPT_DIR/QuickOCR.sh"
echo " - Tip (Wayland global hotkey): bind a desktop shortcut to:"
echo "     \"$SCRIPT_DIR/QuickOCR.sh\" --snip"
