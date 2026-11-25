<p align="center">
  <img src="assets/logo.png" width="104" alt="QuickOCR Logo" />
</p>

<h1 align="center">QuickOCR</h1>

<p align="center">
  Minimal, offline-first Windows &amp; Linux screen &amp; clipboard OCR utility powered by <b>OCRia-nano-1</b>, <b>Surya OCR</b>, <b>EasyOCR</b>, <b>PP-OCRv6 / v5 / v4</b>, <b>Tesseract Best LSTM</b>, <b>Marker</b>, and Vision LLMs with a pure-black animated PySide6 UI.
</p>

<p align="center">
  <a href="https://t.me/pythash"><img src="https://img.shields.io/badge/Telegram-%40pythash-24A1DE?style=flat-square&logo=telegram&logoColor=white" alt="Telegram @pythash" /></a>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-000000?style=flat-square" alt="Windows and Linux" />
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
- **Silent System Tray, Cross-Platform & Auto-Update**: Runs natively on Windows (`QuickOCR.exe`) and Linux (`QuickOCR.sh` / XDG autostart), checks GitHub Releases automatically, and installs updates in one click with live `%` progress while keeping your `config.json`, `.venv`, and downloaded models intact.
- **1-Click Multi-Model Hub (`Recommended ★` / `All` / `Fast` / `Accurate` / `Vision API`)**:
  - **Recommended (`★`) Curated View**: Opens directly on top picks balancing ultra-fast CPU inference, best Persian/Arabic RTL precision, EN/ZH accuracy, and academic layout parsing, with live percentage progress bars (`0–100%`) and resilient retry diagnostics.
  - **OCRia-nano-1** *(Default, bundled offline — 45.6 MB)*: Ultra-fast CPU inference for Persian/Arabic, English, CJK & Markdown tables.
  - **OCRia-1 (4B Flagship GGUF — ~5.5 GB)**: The full 4B-parameter teacher VLM behind `OCRia-nano-1` (`llamaindex/OCRia-1-GGUF`, Q8_0 + `llama-server` auto-setup with resumable HTTP Range downloads) — top ParseBench accuracy for multilingual documents, complex tables, charts, and math formulas.
  - **Surya OCR (Multilingual SOTA — ~1.2 GB)**: High-precision neural line detection and RTL recognition across Persian, Arabic & 90+ languages.
  - **Tesseract Best LSTM (5-Lang RTL — ~75 MB)** & **Tesseract Fast (4-Lang)**: Automatically downloads `tessdata_best` (`fas`, `ara`, `eng`, `chi_sim`, `rus`) or lightweight `tessdata_fast` packs.
  - **EasyOCR Neural Packs (`FA + EN`, `AR + FA + EN`, `RU + ZH + EN`)**: Neural scene-text readers tuned for screenshots, mixed RTL text, and busy backgrounds.
  - **PP-OCRv6 (`Tiny` / `Small` / `Medium`)**, **PP-OCRv5 (`Persian/Arabic`, `Russian/Cyrillic`, `English`, `Server HD`)**, & **PP-OCRv4 (`Persian/Arabic`)**: RapidOCR ONNX models across lightweight and server tiers.
  - **Marker (`marker-pdf`)**: Deep layout analysis, complex tables, and mathematical equations converted cleanly to Markdown.
  - **Custom Vision LLMs**: Connect **LM Studio** (`localhost:1234/v1`), **Ollama** (`localhost:11434/v1`), or any OpenAI-compatible Vision API with 1-click presets (`llamaindex/ocria-1`, `qwen2.5-vl`, `deepseek-ocr`, `MedAIBase/PaddleOCR-VL`, `richardyoung/olmocr2:7b-q8`) and automatic `/v1/models` detection.
- **Trilingual Animated UI**: Instant live switching between **Persian (`فارسی` RTL with bundled Vazirmatn)**, **English**, and **Simplified Chinese (`中文`)** with smooth page-slide, toggle, segmented-pill, and window animations.

---

### Installation

#### Windows (No Python Required)
- **Installer (Recommended):** Download **`QuickOCR-v1.3.0-Windows-Setup.exe`** from [Releases](https://github.com/Abolfazlshahi/QuickOCR/releases) and run it directly — creates Start Menu & Desktop icons with bundled runtime and `pip` (supports installing extra models like `OCRia-1`, `Surya OCR` & `EasyOCR` right inside the app folder).
- **Portable:** Download **`QuickOCR-v1.3.0-Windows-Portable.zip`**, extract anywhere, and double-click **`QuickOCR.exe`**.
- **From Source:**
  ```powershell
  git clone https://github.com/Abolfazlshahi/QuickOCR.git
  cd QuickOCR
  .\Setup.bat
  ```

Run **`Uninstall.bat`** (or Windows Apps & Features if installed with Setup.exe) to remove QuickOCR.

#### Linux (No System Python Required)
- **Single-File Binary (`AppImage`):** Download **`QuickOCR-v1.3.0-Linux-x86_64.AppImage`** from [Releases](https://github.com/Abolfazlshahi/QuickOCR/releases):
  ```bash
  chmod +x QuickOCR-v1.3.0-Linux-x86_64.AppImage
  ./QuickOCR-v1.3.0-Linux-x86_64.AppImage
  ```
  Extra downloaded models & optional packages persist cleanly in `~/.local/share/QuickOCR`.
- **Portable Bundle:** Download **`QuickOCR-v1.3.0-Linux-Portable.tar.gz`**, extract, and run `./QuickOCR`.
- **From Source:**
  ```bash
  git clone https://github.com/Abolfazlshahi/QuickOCR.git
  cd QuickOCR
  ./setup_linux.sh
  ```
  On Wayland desktops, bind a system shortcut to `QuickOCR --snip`.

---

### Project Structure

| File / Folder | Purpose |
|---|---|
| `app.py` | Main PySide6 application, tray lifecycle, single-instance IPC, animated window & page transitions |
| `ui_kit.py` | Pure-black rounded controls (`TelegramBanner`, `AnimatedStackedWidget`, `AnimatedButton`, `AnimatedToggle`, `AnimatedSegmented`, `FloatingToast`) |
| `snipper.py` | Multi-monitor DPI-aware `SnipOverlay` with 60fps spotlight & monochrome icon generator |
| `ocr_engine.py` | Multi-backend OCR catalog (`ocria-nano`, `Surya OCR`, `EasyOCR`, `PP-OCRv6/v5/v4`, `Tesseract Best/Fast`, `Marker`, `openai_vision`) |
| `models_dialog.py` | Embedded Model Manager page with Recommended/category filters, live `%` progress bar, VLM presets & 1-click install |
| `updater.py` | GitHub Release version checker, cross-platform archive fetcher, safe updater & auto-restart |
| `installer.iss` | Inno Setup 6 Windows single-file installer specification |
| `setup_linux.sh` | Linux virtual environment setup & XDG desktop integration (from source) |
| `QuickOCR.sh` | Linux shell launcher (supports `--minimized`, `--snip` IPC, `--version`) |
| `CHANGELOG.md` | Release history & automated GitHub Release notes source |
| `i18n.py` | Trilingual dictionary (`fa`, `en`, `zh`) |
| `launcher.cs` | Native x64 Windows host loading `python311.dll` in-process |
| `launcher_linux.c` | Native ELF Linux host (`QuickOCR`) launching bundled Python runtime |
| `models/ocria-nano/` | Bundled offline OCRia-nano-1 ONNX weights & runtime |
| `assets/fonts/` | Bundled Vazirmatn static TTF font family |
| `check_ocr.py` | Automated end-to-end UI, RTL pill, model manager, snip, and OCR verification check |

---

### License

Application source code is licensed under the [MIT License](LICENSE).
The bundled **OCRia-nano-1** model weights in `models/ocria-nano/` are governed by [`models/ocria-nano/LICENSE`](models/ocria-nano/LICENSE).
