# Changelog

All notable changes to **QuickOCR** are documented here.

---

## v1.3.0

### Highlights
- **Flagship `OCRia-1` (4B VLM — Q8_0 GGUF) Added to Recommended Hub (`ocr_engine.py`, `models_dialog.py`)**:
  - Added **`OCRia-1 (4B Flagship GGUF)`** (`llamaindex/OCRia-1-GGUF` — the full 4-billion-parameter teacher model behind `OCRia-nano-1`) directly inside the **Recommended (`★`)** tab with 1-click installation.
  - Automatically downloads the official `ggml-org/llama.cpp` prebuilt server binary (`win-cpu-x64` / `ubuntu-x64`), `mmproj-OCRia-1-f16.gguf`, and `OCRia-1-Q8_0.gguf` (`~5.5 GB`), running locally on demand with clean process shutdown (`shutdown_engines()`).
  - Upgraded `download_file` with **HTTP `Range` resume** (`206 Partial Content` / `.part` checkpointing) so multi-gigabyte downloads resume cleanly after network drops.
- **Vision API Quick Preset**: Added **`llamaindex/ocria-1`** 1-click preset chip in the Vision API / Ollama tab.

---

## v1.2.0

### Highlights
- **Zero-Setup Native Releases for Windows & Linux (With Full Runtime Model Installer)**:
  - **Windows Native Setup & Portable (`QuickOCR-v1.2.0-Windows-Setup.exe` & `QuickOCR-v1.2.0-Windows-Portable.zip`)**: Bundles a self-contained non-MSIX Python 3.11 runtime with `PySide6`, `liteparse`, `ocria-nano`, and `pip` pre-installed — no system Python or `Setup.bat` needed! Clicking **Download & Install** for `Surya OCR`, `EasyOCR`, `PP-OCRv5`, or `Marker` continues to work directly inside the app folder.
  - **Linux AppImage & Portable (`QuickOCR-v1.2.0-Linux-x86_64.AppImage` & `QuickOCR-v1.2.0-Linux-Portable.tar.gz`)**: Bundles relocatable standalone CPython + ELF `QuickOCR` launcher + Linux `libonnxruntime.so`. Added automatic writable `DATA_DIR` + `PACKAGES_DIR` fallback (`~/.local/share/QuickOCR`) so even single-file read-only `.AppImage` users can install new models & self-update seamlessly!
- **OCR Text Spacing & Dark-Mode Accuracy Fix (`ocr_engine.py`)**:
  - Added `_preprocess_ocr_image` (automatic Dark-Mode background luminance detection & inversion, smart 1.5x/2x upscaling for sharp UI screenshots, and 24px edge padding) plus `preserve_very_small_text=True` and `ocr_despeckle_scans=False` on `LiteParse` — preserving Persian word spaces, hyphens (`QuickOCR Self-Check 2026`), and English words on dark interfaces cleanly.
- **Launcher Polish**: Updated `QuickOCR.bat` and `Uninstall.bat` to launch and stop `QuickOCR.exe` directly, and added `--version` CLI support.

---

## v1.1.0

### Highlights
- **In-App GitHub Auto-Updater (`updater.py` & Footer Bar)**:
  - Displays the active version pill (`v1.1.0`) and a **Check Updates** button at the bottom of the main window, with a silent background check shortly after launch.
  - When a newer GitHub release is found, downloads the platform archive (`Windows.zip` or `Linux.tar.gz`) with live progress percentage (`0–100%`), safely preserves `config.json`, `.venv/`, and downloaded user models, swaps application files, and restarts QuickOCR automatically.
- **Model Manager Progress Bar, Resilient `pip` & RTL Scrollbar Fix (`models_dialog.py`, `ocr_engine.py`)**:
  - Added a dedicated bottom status & progress card with live `0–100%` progress streaming (`urllib` byte progress, `pip` stage progress, and model-weight folder progress).
  - Upgraded `pip` runner with `--timeout 180 --retries 5`, live stdout/stderr streaming, and clear `ERROR:` reporting instead of opaque `exit status 1` failures; re-enables cards cleanly if a download errors out so retries work immediately.
  - Fixed vertical scrollbar collision against model card borders in Persian RTL layouts by adding symmetric scroll padding and refined scrollbar spacing.
- **Full Linux Support & Release Package (`QuickOCR-v1.1.0-Linux.tar.gz`)**:
  - Guarded all Windows-only calls (`winsound`, `win32` ctypes, shortcuts) and added native Linux alternatives (`QGuiApplication.screens()` multi-monitor capture, XDG `~/.config/autostart/quickocr.desktop`, `xdg-open`, Qt clipboard & `--snip` IPC).
  - Added `setup_linux.sh` and `QuickOCR.sh` installers plus GitHub Actions `ubuntu-latest` CI verification (`xvfb-run check_ocr.py`) and Linux archive packaging.

---

## v1.0.3

### Highlights
- **Curated `Recommended (★)` Hub (`models_dialog.py`)**:
  - Opens directly on a **Recommended / پیشنهادی** default tab showcasing curated top-tier OCR models balanced across CPU speed, Persian/Arabic RTL precision, EN/ZH, and full document parsing.
  - Added warm gold `★ Recommended` pills across catalog views and refactored model cards to vertical rows preventing horizontal clipping in narrow RTL/LTR windows.
- **High-Accuracy Persian, Arabic & Multilingual Models (`ocr_engine.py`, `i18n.py`)**:
  - **`Surya OCR (Multilingual SOTA)`**: Neural layout-aware line & RTL recognition across Persian, Arabic, and 90+ languages (`~1.2 GB`).
  - **`Tesseract Best LSTM (5-Lang RTL)`**: Automatic `tessdata_best` LSTM download for `fas`, `ara`, `eng`, `chi_sim`, `rus` (`~75 MB`).
  - **`EasyOCR` Neural Packs**: `EasyOCR FA+EN`, `EasyOCR AR+FA+EN`, and `EasyOCR RU+ZH+EN` tuned for noisy UI screenshots.
- **Quick VLM Presets**: Added 1-click preset chips for `qwen2.5-vl`, `deepseek-ocr`, `MedAIBase/PaddleOCR-VL`, and `richardyoung/olmocr2:7b-q8` inside the Vision API tab.

---

## v1.0.2

### Highlights
- **Telegram Promo Banner & Animated Page Navigation (`ui_kit.py`, `app.py`)**:
  - Redesigned the top promo banner for [`@pythash`](https://t.me/pythash) in signature Telegram blue gradient with hover animation and trilingual labels.
  - Added `AnimatedStackedWidget` for 60fps horizontal slide + cross-fade navigation between Settings and the embedded Model Manager.
- **Expanded Multi-Model Hub**:
  - Added 1-click downloads and switching for **`PP-OCRv6` (`Tiny` / `Small` / `Medium`)**, **`PP-OCRv5` (`Persian/Arabic`, `Russian/Cyrillic`, `English`, `Server HD`)**, **`PP-OCRv4` (`Persian/Arabic`)**, **`Tesseract OCR (4-Lang)`**, and **`Marker` (`marker-pdf` + Surya AI)**.

---

## v1.0.1

### Highlights
- **Native Taskbar Icon Host (`launcher.cs`, `Setup.bat`)**:
  - Replaced Windows Store Python invocation with an in-process x64 C# host (`QuickOCR.exe`) loading standalone non-MSIX `runtime/python311.dll` + explicit `AppUserModelID` and `SHGetPropertyStoreForWindow` binding so Windows Taskbar and Start Menu show QuickOCR's monochrome icon cleanly.
- **60fps Motion Polish (`snipper.py`, `app.py`, `ui_kit.py`)**:
  - Added animated `introProgress` backdrop fading & instruction pill motion in `SnipOverlay`, breathing halo `StatusDot`, and slide+fade `show_window` transitions.
  - Added initial `@pythash` channel promo card cleanly integrated into the pure-black UI.

---

## v1.0.0

### Highlights
- **Offline Screen & Clipboard OCR (`OCRia-nano-1`)**:
  - First public release bundling the 45.6 MB offline `OCRia-nano-1` ONNX pipeline (`det.onnx`, `rec_rtl`, `rec_cjk`, `rec_latin`, `rec_world`, `tablenet.onnx`) inside `models/ocria-nano/`.
- **Pure-Black Trilingual UI & System Tray (`app.py`, `ui_kit.py`, `i18n.py`)**:
  - OLED `#000000` rounded PySide6 interface with bundled **Vazirmatn** fonts supporting instant switching between **Persian (RTL)**, **English**, and **Simplified Chinese**.
  - Global hotkey (`ctrl+alt+c`), multi-monitor DPI-aware `SnipOverlay` spotlight cutout, non-focus-stealing `FloatingToast`, System Tray lifecycle, `Setup.bat` installer, and custom Vision LLM API support (LM Studio / Ollama / OpenAI-compatible).
