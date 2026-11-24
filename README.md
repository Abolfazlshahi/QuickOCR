<p align="center">
  <img src="assets/logo.png" width="104" alt="QuickOCR Logo" />
</p>

<h1 align="center">QuickOCR</h1>

<p align="center">
  Minimal, offline-first Windows screen &amp; clipboard OCR utility powered by <b>OCRia-nano-1</b>, with extensible local/Vision-LLM backends and a pure-black PySide6 UI.
</p>

<p align="center">
  <a href="https://t.me/pythash"><img src="https://img.shields.io/badge/Telegram-%40pythash-000000?style=flat-square&logo=telegram" alt="Telegram @pythash" /></a>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-000000?style=flat-square" alt="Windows" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-000000?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/Engine-OCRia--nano--1-000000?style=flat-square" alt="OCRia-nano-1" />
  <img src="https://img.shields.io/badge/License-MIT-000000?style=flat-square" alt="License" />
</p>

<p align="center">
  Join our Telegram channel <a href="https://t.me/pythash"><b>@pythash</b></a> for updates, releases, and tips.
</p>

---

### Highlights

- **One-Shortcut Spotlight Capture (`Ctrl + Alt + C`)**: Freezes the screen across multi-monitor and High-DPI displays with a full-brightness spotlight inside your selection box and animated viewfinder brackets.
- **Floating Status Pill**: Non-focus-stealing animated pill shows live progress and extraction timing (`ms`) before copying the result straight to your clipboard.
- **Silent System Tray Mode**: Starts quietly in the Windows System Tray; click the tray icon anytime to open settings or switch backends.
- **Extensible Multi-Model Manager**:
  - **OCRia-nano-1** *(Default, bundled offline in `models/ocria-nano` — 45.6 MB)*: Ultra-fast CPU inference supporting Persian/Arabic (RTL), English, CJK, and Markdown tables.
  - **RapidOCR (PaddleOCR ONNX)**: Optional one-click install inside the Model Manager (~15 MB CPU ONNX).
  - **Tesseract OCR**: Optional system backend via LiteParse.
  - **Custom Vision LLMs / Local Servers**: Connect **LM Studio** (`localhost:1234/v1`), **Ollama** (`localhost:11434/v1`), or any OpenAI-compatible Vision API with automatic `/v1/models` detection.
- **Trilingual Pure-Black UI**: Live instant switching between **Persian (`فارسی` RTL with bundled Vazirmatn font)**, **English**, and **Simplified Chinese (`中文`)**.

---

### Installation (Windows)

```powershell
git clone https://github.com/Abolfazlshahi/QuickOCR.git
cd QuickOCR
.\Setup.bat
```

Or download the repository ZIP, extract it anywhere (e.g. `D:\app\QuickOCR`), and double-click **`Setup.bat`**.

`Setup.bat` automatically:
1. Creates an isolated `.venv` virtual environment.
2. Installs dependencies from `requirements.txt`.
3. Verifies the bundled offline `models/ocria-nano` weights.
4. Compiles the native `QuickOCR.exe` launcher with `icon.ico` and creates Desktop & Start Menu shortcuts.
5. Starts QuickOCR silently in the System Tray.

To stop QuickOCR and remove its shortcuts, run **`Uninstall.bat`**.

---

### Project Structure

| File / Folder | Purpose |
|---|---|
| `app.py` | Main PySide6 application, System Tray lifecycle, single-instance IPC, settings & shortcuts |
| `ui_kit.py` | Pure-black rounded controls (`AnimatedButton`, `AnimatedToggle`, `AnimatedSegmented`, `FloatingToast`) |
| `snipper.py` | Multi-monitor DPI-aware `SnipOverlay` and monochrome logo/icon generator |
| `ocr_engine.py` | Multi-backend OCR router (`ocria-nano`, `rapidocr`, `tesseract`, `openai_vision`) |
| `models_dialog.py` | Model Manager UI for switching, downloading, importing, and configuring Vision servers |
| `i18n.py` | Trilingual dictionary (`fa`, `en`, `zh`) |
| `launcher.cs` | Minimal C# source compiled into `QuickOCR.exe` |
| `models/ocria-nano/` | Bundled offline OCRia-nano-1 ONNX weights & runtime |
| `assets/fonts/` | Bundled Vazirmatn static TTF font family |
| `check_ocr.py` | Automated end-to-end UI, layout, snip, and OCR verification check |

---

### License

Application source code is licensed under the [MIT License](LICENSE).
The bundled **OCRia-nano-1** model weights and ONNX Runtime in `models/ocria-nano/` are governed by their own license terms in [`models/ocria-nano/LICENSE`](models/ocria-nano/LICENSE).
