"""GitHub Release update checker and non-destructive self-installer for QuickOCR."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.request
import zipfile

import ocr_engine

APP_VERSION = "1.1.0"
GITHUB_LATEST_API = "https://api.github.com/repos/Abolfazlshahi/QuickOCR/releases/latest"

_PRESERVED_ROOT_NAMES = frozenset({"config.json", ".venv"})
_PRESERVED_MODEL_SUBDIRS = frozenset(
    {"rapidocr", "tessdata", "tessdata_best", "easyocr", "surya", "hf"}
)


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    notes: str
    asset_name: str
    download_url: str
    asset_size: int = 0


def parse_version(tag: str) -> Tuple[int, ...]:
    """Convert a version tag like 'v1.1.0' or '1.0.3-beta' into a numeric tuple."""
    clean = tag.strip().lstrip("vV").split("-", 1)[0].split("+", 1)[0]
    parts: List[int] = []
    for seg in clean.split("."):
        digits = "".join(ch for ch in seg if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def is_newer_version(latest_tag: str, current_tag: str = APP_VERSION) -> bool:
    """Return True when latest_tag represents a strictly newer semver than current_tag."""
    a = list(parse_version(latest_tag))
    b = list(parse_version(current_tag))
    n = max(len(a), len(b))
    a.extend([0] * (n - len(a)))
    b.extend([0] * (n - len(b)))
    return tuple(a) > tuple(b)


def select_release_asset(
    assets: List[Dict[str, Any]],
    platform: str = sys.platform,
) -> Optional[Dict[str, Any]]:
    """Pick the appropriate archive asset for the running OS."""
    is_win = platform == "win32"
    for asset in assets:
        name = str(asset.get("name") or "")
        low = name.lower()
        if is_win and "windows" in low and low.endswith(".zip"):
            return asset
        if not is_win and "linux" in low and (low.endswith(".tar.gz") or low.endswith(".tgz")):
            return asset
    return None


def check_latest_release(
    current_version: str = APP_VERSION,
    timeout: float = 8.0,
) -> Optional[ReleaseInfo]:
    """Query GitHub latest release and return ReleaseInfo if a newer platform asset exists."""
    req = urllib.request.Request(
        GITHUB_LATEST_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"QuickOCR/{current_version}",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    tag = str(data.get("tag_name") or "").strip()
    if not tag or not is_newer_version(tag, current_version):
        return None
    asset = select_release_asset(data.get("assets") or [], sys.platform)
    if not asset or not asset.get("browser_download_url"):
        return None
    return ReleaseInfo(
        tag=tag,
        notes=str(data.get("body") or ""),
        asset_name=str(asset["name"]),
        download_url=str(asset["browser_download_url"]),
        asset_size=int(asset.get("size") or 0),
    )


def _ensure_within(root: Path, candidate: Path) -> None:
    root_resolved = root.resolve()
    cand_resolved = candidate.resolve()
    if not (cand_resolved == root_resolved or cand_resolved.is_relative_to(root_resolved)):
        raise ValueError(f"Unsafe archive entry path: {candidate}")


def extract_update_archive(archive_path: Path, stage_dir: Path) -> Path:
    """Safely extract .zip or .tar.gz into stage_dir and return the inner package root."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    low = archive_path.name.lower()
    if low.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.infolist():
                _ensure_within(stage_dir, stage_dir / member.filename)
            zf.extractall(stage_dir)
    elif low.endswith(".tar.gz") or low.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                _ensure_within(stage_dir, stage_dir / member.name)
            tf.extractall(stage_dir)
    else:
        raise ValueError(f"Unsupported archive format: {archive_path.name}")

    entries = [p for p in stage_dir.iterdir() if p.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return stage_dir


def _prune_preserved(source_root: Path) -> None:
    for name in _PRESERVED_ROOT_NAMES:
        target = source_root / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink(missing_ok=True)
    models_src = source_root / "models"
    if models_src.is_dir():
        for sub in _PRESERVED_MODEL_SUBDIRS:
            sub_dir = models_src / sub
            if sub_dir.exists():
                shutil.rmtree(sub_dir, ignore_errors=True)


def copy_update_tree(source_root: Path, app_dir: Path) -> None:
    """Overlay extracted files onto app_dir without overwriting user config, .venv, or user models."""
    _prune_preserved(source_root)
    for src in source_root.rglob("*"):
        rel = src.relative_to(source_root)
        dst = app_dir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def apply_update_and_prepare_restart(
    release: ReleaseInfo,
    app_dir: Path,
    on_progress: ocr_engine.ProgressCallback = None,
) -> Callable[[], None]:
    """Download release asset, stage extracted payload, and return a post-quit restart callable."""
    tmp_root = Path(tempfile.mkdtemp(prefix="quickocr_upd_"))
    archive_path = tmp_root / release.asset_name
    stage_dir = tmp_root / "extracted"

    ocr_engine.download_file(
        release.download_url,
        archive_path,
        on_progress=lambda p, m: ocr_engine._emit_progress(
            on_progress, int(p * 0.85), m
        ),
        timeout=180.0,
        label=release.asset_name,
    )
    ocr_engine._emit_progress(on_progress, 90, "Extracting...")
    source_root = extract_update_archive(archive_path, stage_dir)
    _prune_preserved(source_root)
    ocr_engine._emit_progress(on_progress, 96, "Preparing install...")

    if sys.platform == "win32":
        pid = os.getpid()
        exe_target = app_dir / "QuickOCR.exe"
        pyw_target = app_dir / ".venv" / "Scripts" / "pythonw.exe"
        launch_cmd = (
            f'start "" "{exe_target}"'
            if exe_target.exists()
            else f'start "" "{pyw_target if pyw_target.exists() else sys.executable}" "{app_dir / "app.py"}"'
        )
        cmd_script = tmp_root / "apply_update.cmd"
        cmd_script.write_text(
            "@echo off\n"
            f'powershell -NoProfile -Command "Wait-Process -Id {pid} -Timeout 15 -ErrorAction SilentlyContinue"\n'
            f'xcopy /E /Y /I /Q "{source_root}\\*" "{app_dir}\\"\n'
            f"{launch_cmd}\n"
            f'rmdir /S /Q "{tmp_root}"\n',
            encoding="utf-8",
        )
        ocr_engine._emit_progress(on_progress, 100, release.tag)

        def _win_restart() -> None:
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "CREATE_NO_WINDOW", 0
            )
            subprocess.Popen(["cmd", "/c", str(cmd_script)], creationflags=flags)

        return _win_restart

    copy_update_tree(source_root, app_dir)
    for sh_name in ("QuickOCR.sh", "setup_linux.sh"):
        sh_path = app_dir / sh_name
        if sh_path.exists():
            os.chmod(sh_path, 0o755)
    shutil.rmtree(tmp_root, ignore_errors=True)
    ocr_engine._emit_progress(on_progress, 100, release.tag)

    def _posix_restart() -> None:
        os.execv(sys.executable, [sys.executable, str(app_dir / "app.py")])

    return _posix_restart
