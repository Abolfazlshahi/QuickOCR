"""Extensible multi-backend OCR engine (OCRia-nano, RapidOCR, Tesseract, Vision API)."""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
os.environ.setdefault("LITEPARSE_MODEL_DIR", str(MODEL_DIR))

from liteparse import LiteParse, models  # noqa: E402

_engine_lock = threading.Lock()
_liteparse_cache: Dict[str, LiteParse] = {}
_rapid_cache: Any = None


def is_ocria_installed() -> Tuple[bool, str]:
    """Return (ready, size_str) for the bundled ocria-nano weights."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for m in models.list():
        if m.name == "ocria-nano" and m.complete:
            size_mb = m.size_bytes / (1024 * 1024)
            ver = m.version or "1.0.0"
            return True, f"v{ver} • {size_mb:.1f} MB"
    return False, ""


def get_model_status(
    active_model_id: str = "ocria-nano",
    custom_models: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str]:
    """Return (is_ready, status_summary) for the currently selected model."""
    if active_model_id == "ocria-nano":
        ok, info = is_ocria_installed()
        return ok, (f"ocria-nano ({info})" if ok else "ocria-nano missing")
    if active_model_id == "rapidocr":
        ok = is_rapidocr_installed()
        return ok, ("RapidOCR ONNX" if ok else "RapidOCR not installed")
    if active_model_id == "tesseract":
        ok = is_tesseract_installed()
        return ok, ("Tesseract" if ok else "Tesseract not found")

    for cm in custom_models or []:
        if cm.get("id") == active_model_id:
            return True, cm.get("name") or cm.get("model_name") or active_model_id
    return is_ocria_installed()[0], "ocria-nano"


def pull_model(from_dir: Optional[str] = None) -> str:
    """Download (or import from local directory) ocria-nano weights."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with _engine_lock:
        _liteparse_cache.pop("ocria-nano", None)
    return models.pull("ocria-nano", from_dir=from_dir, quiet=True)


def remove_ocria_nano() -> None:
    with _engine_lock:
        _liteparse_cache.pop("ocria-nano", None)
    models.rm("ocria-nano")


def is_rapidocr_installed() -> bool:
    return importlib.util.find_spec("rapidocr_onnxruntime") is not None


def install_rapidocr() -> None:
    global _rapid_cache
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-warn-script-location", "rapidocr-onnxruntime"],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    importlib.invalidate_caches()
    with _engine_lock:
        _rapid_cache = None


def remove_rapidocr() -> None:
    global _rapid_cache
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "rapidocr-onnxruntime"],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    importlib.invalidate_caches()
    with _engine_lock:
        _rapid_cache = None


def is_tesseract_installed() -> bool:
    return shutil.which("tesseract") is not None


def _get_liteparse(backend: str) -> LiteParse:
    if backend not in _liteparse_cache:
        if backend == "ocria-nano" and not is_ocria_installed()[0]:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            models.pull("ocria-nano", quiet=True)
        _liteparse_cache[backend] = LiteParse(
            ocr_backend=backend,
            output_format="markdown",
            quiet=True,
        )
    return _liteparse_cache[backend]


def _get_rapidocr() -> Any:
    global _rapid_cache
    if _rapid_cache is None:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        _rapid_cache = RapidOCR()
    return _rapid_cache


def warm_up(active_model_id: str = "ocria-nano") -> None:
    """Pre-load the active local model into RAM for sub-second snip OCR."""
    if active_model_id == "ocria-nano":
        dummy = Image.new("RGB", (64, 32), "white")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            dummy.save(tmp_path, format="PNG")
            with _engine_lock:
                _get_liteparse("ocria-nano").parse(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    elif active_model_id == "rapidocr" and is_rapidocr_installed():
        with _engine_lock:
            _get_rapidocr()


def fetch_remote_models(base_url: str, api_key: str = "") -> List[str]:
    """Query an OpenAI-compatible (/v1/models) or Ollama endpoint for available models."""
    base = base_url.strip().rstrip("/")
    if not base:
        return []
    url = f"{base}/models"
    headers = {"Accept": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=4.0) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    names: List[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        for item in payload["data"]:
            if isinstance(item, dict) and item.get("id"):
                names.append(str(item["id"]))
    elif isinstance(payload, dict) and isinstance(payload.get("models"), list):
        for item in payload["models"]:
            if isinstance(item, dict) and (item.get("name") or item.get("model")):
                names.append(str(item.get("name") or item.get("model")))
    return names


def _extract_liteparse(image: Image.Image, backend: str, output_format: str) -> str:
    if image.width < 48 or image.height < 36:
        edge_color = image.getpixel((0, 0))
        image = ImageOps.expand(image, border=14, fill=edge_color)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        image.save(tmp_path, format="PNG")
        with _engine_lock:
            result = _get_liteparse(backend).parse(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    if output_format == "text":
        parts = [p.text for p in result.pages if p.text]
        return "\n".join(parts).strip()

    parts = [p.markdown or p.text for p in result.pages if (p.markdown or p.text)]
    return ("\n\n".join(parts) if parts else result.text).strip()


def _extract_rapidocr(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    with _engine_lock:
        engine = _get_rapidocr()
        result, _ = engine(buf.getvalue())
    if not result:
        return ""
    lines = [row[1] for row in result if len(row) >= 2 and row[1]]
    return "\n".join(lines).strip()


def _extract_vision_api(
    image: Image.Image,
    base_url: str,
    model_name: str,
    api_key: str,
    output_format: str,
) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    prompt = (
        "Extract all text from this image verbatim. Preserve tables, headings, and layout in clean Markdown. Output only the extracted text."
        if output_format == "markdown"
        else "Extract all text from this image verbatim as plain text. Output only the extracted text."
    )

    body = {
        "model": model_name,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
    }

    base = base_url.strip().rstrip("/")
    url = f"{base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    content = msg.get("content", "")
    return content.strip() if isinstance(content, str) else ""


def extract_text(
    image: Image.Image,
    output_format: str = "markdown",
    active_model_id: str = "ocria-nano",
    custom_models: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Extract text from a PIL Image using the selected OCR backend or Vision LLM."""
    if image.mode != "RGB":
        image = image.convert("RGB")

    if active_model_id == "rapidocr":
        return _extract_rapidocr(image)
    if active_model_id == "tesseract":
        return _extract_liteparse(image, "tesseract", output_format)
    if active_model_id != "ocria-nano":
        for cm in custom_models or []:
            if cm.get("id") == active_model_id:
                return _extract_vision_api(
                    image=image,
                    base_url=cm["base_url"],
                    model_name=cm["model_name"],
                    api_key=cm.get("api_key", ""),
                    output_format=output_format,
                )

    return _extract_liteparse(image, "ocria-nano", output_format)
