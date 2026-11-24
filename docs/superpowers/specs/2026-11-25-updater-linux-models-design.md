# QuickOCR v1.1.0 Design Spec: Progress & Bugfixes, Auto-Updater, Linux Support & Release Notes

## Overview

Extend QuickOCR with four coordinated improvements:
1. **Model Manager Download Reliability, Live Progress & RTL Scrollbar Fix**
2. **GitHub Auto-Update Checker & In-App Installer**
3. **Full Linux Compatibility, Desktop Integration & Release Packaging (`.tar.gz`)**
4. **Structured `CHANGELOG.md` + Automated Release Notes & Backfill (`v1.0.0`–`v1.0.3`)**

## Architecture & Module Boundaries

1. **`ocr_engine.py` & `models_dialog.py` & `ui_kit.py` (Model Downloads & UI)**
   - **RTL Scrollbar Fix:** Use symmetric horizontal scroll body margins `(12, 2, 12, 6)` in `ModelsView` and refine `QScrollBar:vertical` margins in `ui_kit.py` so the scrollbar track never collides with `QFrame#Card` borders in RTL (`fa`) or LTR (`en`/`zh`). Wrap the download progress bar and status message inside a dedicated rounded bottom status container below `QScrollArea`.
   - **Resilient Pip Runner & Live Progress:**
     - Add shared `download_file(url, dest, on_progress=None, timeout=120.0)` helper streaming 64 KB chunks via `urllib.request` using `Content-Length` to emit integer percentages `0..100` and downloaded MB counts.
     - Upgrade `_run_pip(*args, on_progress=None, base_pct=5, end_pct=60)` to invoke `pip` via `subprocess.Popen` with `--timeout 180`, `--retries 5`, `--no-input`, `--progress-bar off`, and merged `stdout=PIPE, stderr=STDOUT`, streaming progress lines cleanly and raising `RuntimeError` containing the tail error lines on non-zero exit (no opaque `exit status 1`).
     - Monitor destination model directory byte growth on a background polling timer during ONNX / EasyOCR / Surya / Marker weight initialization so progress advances smoothly toward `100%` alongside stage messages.

2. **`updater.py` & `app.py` (GitHub Update Checker & Self-Installer)**
   - Introduce `APP_VERSION = "1.1.0"` and pure helpers in `updater.py`:
     - `parse_version(tag: str) -> Tuple[int, ...]`
     - `is_newer_version(latest_tag: str, current_tag: str) -> bool`
     - `select_release_asset(assets: List[Dict[str, Any]], platform: str = sys.platform) -> Optional[Dict[str, Any]]` (`QuickOCR-*-Windows.zip` on `win32`, `QuickOCR-*-Linux.tar.gz` on `linux`)
     - `check_latest_release(current_version: str) -> Optional[ReleaseInfo]` querying `https://api.github.com/repos/Abolfazlshahi/QuickOCR/releases/latest`.
     - `download_and_apply_update(release_info, app_dir, on_progress)`: downloads the platform archive using `ocr_engine.download_file`, extracts into a temp directory, strips top-level folder prefix cleanly, preserves `config.json`, `.venv/`, downloaded user models inside `models/` (updating `ocria-nano` only if bundled files differ or updating source/assets/scripts/runtime), and triggers restart:
       - Windows (`win32`): spawns a detached short PowerShell/Batch helper waiting for current PID exit, copying updated files safely (handling locked `QuickOCR.exe` / `runtime/`), and relaunching `QuickOCR.exe` (or `pythonw.exe app.py`).
       - Linux (`linux`): atomically overlays updated files cleanly and restarts via `os.execv` / `QuickOCR.sh`.
   - In `app.py` footer_wrap: add compact version badge (`v1.1.0`), Update Check / Install button (`بررسی آپدیت` -> `دانلود و نصب vX.Y.Z`), and sleek inline progress bar/status indicator. Perform one non-blocking silent check ~1.5s after launch and allow manual checks anytime.

3. **Cross-Platform Linux Support (`app.py`, `snipper.py`, `ui_kit.py`, `ocr_engine.py`, `setup_linux.sh`, `QuickOCR.sh`)**
   - Guard all Windows-only calls (`winsound`, `ctypes.windll`, `os.startfile`, `WScript.Shell`, `CREATE_NO_WINDOW`) behind `sys.platform == "win32"`.
   - `snipper.py`: on non-Windows, compute virtual screen geometry from `QGuiApplication.screens()` (`virtualGeometry()` union) and grab screens cleanly via `QGuiApplication.screens()[i].grabWindow(0)` stitched into a PIL `Image` at full virtual bounds.
   - `app.py`: support `--snip` CLI / IPC command (`SHOW` or `SNIP` for Wayland desktop hotkey bindings), use `xdg-open` for "App Folder", `QApplication.beep()` for sound feedback, and `~/.config/autostart/quickocr.desktop` for Linux autostart toggle. Handle `keyboard.add_hotkey` failures cleanly without crashing on unprivileged Linux/Wayland sessions (falling back silently + status note if needed).
   - Provide `setup_linux.sh` (creates `.venv`, installs `requirements.txt`, verifies `models/ocria-nano`, installs `~/.local/share/applications/quickocr.desktop` with `assets/logo.png`) and `QuickOCR.sh`.

4. **`CHANGELOG.md` & GitHub Release Notes + CI (`.github/workflows/release.yml`)**
   - Author full bilingual/structured `CHANGELOG.md` sections for `v1.0.0`, `v1.0.1`, `v1.0.2`, `v1.0.3`, and `v1.1.0`.
   - Update `.github/workflows/release.yml` to build & test BOTH Windows (`windows-latest` -> `QuickOCR-$tag-Windows.zip`) and Linux (`ubuntu-latest` with `xvfb-run` + `check_ocr.py` -> `QuickOCR-$tag-Linux.tar.gz`), extract the matching section from `CHANGELOG.md` as release body (`--notes-file`), AND provide a `workflow_dispatch` step/job to backfill GitHub Release notes on prior tags (`v1.0.0`–`v1.0.3`) using `secrets.GITHUB_TOKEN`.
