<p align="center">
  <img src="assets/logo.png" width="104" alt="QuickOCR Logo" />
</p>

<h1 align="center">QuickOCR</h1>

<p align="center">
  Minimal, offline-first Windows screen &amp; clipboard OCR utility powered by <b>OCRia-nano-1</b>, <b>PP-OCRv6 / v5 / v4</b>, <b>Tesseract</b>, <b>Marker (Surya AI)</b>, and Vision LLMs with a pure-black animated PySide6 UI.
</p>

<p align="center">
  <a href="https://t.me/pythash"><img src="https://img.shields.io/badge/Telegram-%40pythash-24A1DE?style=flat-square&logo=telegram&logoColor=white" alt="Telegram @pythash" /></a>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-000000?style=flat-square" alt="Windows" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-000000?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/License-MIT-000000?style=flat-square" alt="License" />
</p>

<p align="center">
  Join our Telegram channel <a href="https://t.me/pythash"><b>@pythash</b></a> for updates, releases, and tips.
</p>

---

### Highlights

- **One-Shortcut Spotlight Capture (`Ctrl + Alt + C`)**: Freezes the screen across multi-monitor & High-DPI setups with a 60fps animated scrim, full-brightness spotlight cutout, glowing corner brackets, and marching dashed guide.
- **Floating Status Pill**: Non-focus-stealing animated pill shows live progress and extraction timing (`ms`) before copying the extracted text straight to your clipboard.
- **Silent System Tray & Native Host**: Runs as `QuickOCR.exe` directly in the Windows System Tray with custom monochrome taskbar/tray icons.
- **1-Click Multi-Model Hub (`All` / `Fast` / `Accurate` / `Vision API`)**:
  - **OCRia-nano-1** *(Default, bundled offline — 45.6 MB)*: Ultra-fast CPU inference for Persian/Arabic, English, CJK & Markdown tables.
  - **PP-OCRv6 (`Tiny` / `Small` / `Medium`)**: Next-gen RapidOCR ONNX models for high-speed & high-accuracy English, Chinese & Latin scripts.
  - **PP-OCRv5 (`Persian/Arabic`, `Russian/Cyrillic`, `English`, `Server HD`)** & **PP-OCRv4 (`Persian/Arabic`)**: Specialized language & quality tiers downloadable in one click.
  - **Tesseract OCR (4-Lang)**: Automatically downloads `fas`, `eng`, `chi_sim`, `rus` tessdata packs and pairs with Tesseract.
  - **Marker (`marker-pdf` + Surya AI)**: Deep layout analysis, complex tables, and mathematical equations converted cleanly to Markdown.
  - **Custom Vision LLMs**: Connect **LM Studio** (`localhost:1234/v1`), **Ollama** (`localhost:11434/v1`), or any OpenAI-compatible Vision API with automatic `/v1/models` detection.
- **Trilingual Animated UI**: Instant live switching between **Persian (`فارسی` RTL with bundled Vazirmatn)**, **English**, and **Simplified Chinese (`中文`)** with smooth page-slide, toggle, segmented-pill, and window animations.

---

### Installation (Windows)

Download **`QuickOCR-v1.0.2-Windows.zip`** from [Releases](https://github.com/Abolfazlshahi/QuickOCR/releases), extract it anywhere, and double-click **`Setup.bat`** — or clone directly:

```powershell
git clone https://github.com/Abolfazlshahi/QuickOCR.git
cd QuickOCR
.\Setup.bat
```

`Setup.bat` automatically:
1. Creates `.venv` and installs dependencies from `requirements.txt`.
2. Verifies the bundled offline `models/ocria-nano` weights.
3. Fetches the standalone non-MSIX Python 3.11 runtime and compiles `QuickOCR.exe`.
4. Creates Desktop & Start Menu shortcuts and starts QuickOCR in the System Tray.

Run **`Uninstall.bat`** to stop QuickOCR and remove its shortcuts.

---

### Project Structure

| File / Folder | Purpose |
|---|---|
| `app.py` | Main PySide6 application, tray lifecycle, single-instance IPC, animated window & page transitions |
| `ui_kit.py` | Pure-black rounded controls (`TelegramBanner`, `AnimatedStackedWidget`, `AnimatedButton`, `AnimatedToggle`, `AnimatedSegmented`, `FloatingToast`) |
| `snipper.py` | Multi-monitor DPI-aware `SnipOverlay` with 60fps spotlight & monochrome icon generator |
| `ocr_engine.py` | Multi-backend OCR catalog (`ocria-nano`, `PP-OCRv6/v5/v4`, `Tesseract`, `Marker`, `openai_vision`) |
| `models_dialog.py` | Embedded Model Manager page with category filters & 1-click download/switch/remove |
| `i18n.py` | Trilingual dictionary (`fa`, `en`, `zh`) |
| `launcher.cs` | Native x64 Windows host loading `python311.dll` in-process |
| `models/ocria-nano/` | Bundled offline OCRia-nano-1 ONNX weights & runtime |
| `assets/fonts/` | Bundled Vazirmatn static TTF font family |
| `check_ocr.py` | Automated end-to-end UI, RTL pill, model manager, snip, and OCR verification check |

---

### License

Application source code is licensed under the [MIT License](LICENSE).
The bundled **OCRia-nano-1** model weights in `models/ocria-nano/` are governed by [`models/ocria-nano/LICENSE`](models/ocria-nano/LICENSE).
