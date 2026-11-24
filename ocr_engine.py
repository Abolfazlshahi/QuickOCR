"""Extensible multi-backend OCR engine (OCRia-nano, Surya, EasyOCR, PP-OCRv6/v5/v4, Tesseract, Marker, Vision API)."""

from __future__ import annotations

import base64
import importlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
RAPID_DIR = MODEL_DIR / "rapidocr"
TESSDATA_DIR = MODEL_DIR / "tessdata"
TESSBEST_DIR = MODEL_DIR / "tessdata_best"
EASYOCR_DIR = MODEL_DIR / "easyocr"
SURYA_DIR = MODEL_DIR / "surya"
os.environ.setdefault("LITEPARSE_MODEL_DIR", str(MODEL_DIR))
os.environ.setdefault("MODEL_CACHE_DIR", str(SURYA_DIR))
os.environ.setdefault("HF_HOME", str(MODEL_DIR / "hf"))

from liteparse import LiteParse, models  # noqa: E402

_engine_lock = threading.Lock()
_liteparse_cache: Dict[str, LiteParse] = {}
_rapid_cache: Dict[str, Any] = {}
_easyocr_cache: Dict[str, Any] = {}
_surya_cache: Optional[Callable[[Image.Image], Any]] = None
_marker_cache: Any = None

_TESS_VARIANTS: Dict[str, Tuple[Path, Tuple[str, ...], str]] = {
    "tesseract-multi": (
        TESSDATA_DIR,
        ("fas", "eng", "chi_sim", "rus"),
        "https://github.com/tesseract-ocr/tessdata_fast/raw/main",
    ),
    "tesseract-best": (
        TESSBEST_DIR,
        ("fas", "ara", "eng", "chi_sim", "rus"),
        "https://github.com/tesseract-ocr/tessdata_best/raw/main",
    ),
}

# Curated catalog of built-in & 1-click downloadable OCR models
MODEL_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "ocria-nano",
        "title": "OCRia-nano-1",
        "desc_key": "desc_ocria_nano",
        "category": "fast",
        "recommended": True,
        "langs": "FA • AR • EN • ZH • +20",
        "badge": "45.6 MB • CPU",
        "kind": "liteparse_ocria",
    },
    {
        "id": "surya-ocr",
        "title": "Surya OCR (Multilingual SOTA)",
        "desc_key": "desc_surya",
        "category": "heavy",
        "recommended": True,
        "langs": "FA • AR • EN • ZH • +90",
        "badge": "~1.2 GB • RTL",
        "kind": "surya",
    },
    {
        "id": "tesseract-best",
        "title": "Tesseract Best LSTM (5-Lang RTL)",
        "desc_key": "desc_tesseract_best",
        "category": "heavy",
        "recommended": True,
        "langs": "FA • AR • EN • ZH • RU",
        "badge": "~75 MB • Best LSTM",
        "kind": "tesseract",
    },
    {
        "id": "ppocrv5-arabic",
        "title": "PP-OCRv5 Persian / Arabic",
        "desc_key": "desc_ppocrv5_arabic",
        "category": "fast",
        "recommended": True,
        "langs": "FA • AR",
        "badge": "~12 MB • Mobile",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV5",
        "model_type": "MOBILE",
        "lang_type": "arabic",
    },
    {
        "id": "easyocr-fa",
        "title": "EasyOCR Persian + English",
        "desc_key": "desc_easyocr_fa",
        "category": "heavy",
        "recommended": True,
        "langs": "FA • EN",
        "badge": "~100 MB • Neural",
        "kind": "easyocr",
        "langs_list": ["fa", "en"],
    },
    {
        "id": "ppocrv6-medium",
        "title": "PP-OCRv6 Medium",
        "desc_key": "desc_ppocrv6_medium",
        "category": "heavy",
        "recommended": True,
        "langs": "EN • ZH • Latin",
        "badge": "~34 MB • High Acc",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV6",
        "model_type": "MEDIUM",
        "lang_type": "ch",
    },
    {
        "id": "marker-pdf",
        "title": "Marker (Surya AI Layout)",
        "desc_key": "desc_marker",
        "category": "heavy",
        "recommended": True,
        "langs": "FA • AR • EN • ZH • Math",
        "badge": "~1.8 GB • PyTorch",
        "kind": "marker",
    },
    {
        "id": "easyocr-ar-fa",
        "title": "EasyOCR Arabic + Persian + EN",
        "desc_key": "desc_easyocr_ar",
        "category": "heavy",
        "recommended": False,
        "langs": "AR • FA • EN",
        "badge": "~115 MB • Neural",
        "kind": "easyocr",
        "langs_list": ["ar", "fa", "en"],
    },
    {
        "id": "easyocr-ru-zh",
        "title": "EasyOCR Russian + Chinese + EN",
        "desc_key": "desc_easyocr_ruz",
        "category": "heavy",
        "recommended": False,
        "langs": "RU • ZH • EN",
        "badge": "~140 MB • Neural",
        "kind": "easyocr",
        "langs_list": ["ru", "ch_sim", "en"],
    },
    {
        "id": "ppocrv6-tiny",
        "title": "PP-OCRv6 Tiny",
        "desc_key": "desc_ppocrv6_tiny",
        "category": "fast",
        "recommended": False,
        "langs": "EN • ZH • Latin",
        "badge": "~6 MB • Ultra-Fast",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV6",
        "model_type": "TINY",
        "lang_type": "ch",
    },
    {
        "id": "ppocrv6-small",
        "title": "PP-OCRv6 Small",
        "desc_key": "desc_ppocrv6_small",
        "category": "fast",
        "recommended": False,
        "langs": "EN • ZH • Latin",
        "badge": "~14 MB • Balanced",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV6",
        "model_type": "SMALL",
        "lang_type": "ch",
    },
    {
        "id": "ppocrv5-cyrillic",
        "title": "PP-OCRv5 Russian / Cyrillic",
        "desc_key": "desc_ppocrv5_cyrillic",
        "category": "fast",
        "recommended": False,
        "langs": "RU • Cyrillic",
        "badge": "~12 MB • Mobile",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV5",
        "model_type": "MOBILE",
        "lang_type": "cyrillic",
    },
    {
        "id": "ppocrv5-en",
        "title": "PP-OCRv5 English Fast",
        "desc_key": "desc_ppocrv5_en",
        "category": "fast",
        "recommended": False,
        "langs": "EN",
        "badge": "~11 MB • Mobile",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV5",
        "model_type": "MOBILE",
        "lang_type": "en",
    },
    {
        "id": "ppocrv5-server",
        "title": "PP-OCRv5 Server HD",
        "desc_key": "desc_ppocrv5_server",
        "category": "heavy",
        "recommended": False,
        "langs": "ZH • EN",
        "badge": "~85 MB • Server",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV5",
        "model_type": "SERVER",
        "lang_type": "ch",
    },
    {
        "id": "ppocrv4-arabic",
        "title": "PP-OCRv4 Persian / Arabic",
        "desc_key": "desc_ppocrv4_arabic",
        "category": "fast",
        "recommended": False,
        "langs": "FA • AR",
        "badge": "~10 MB • Mobile",
        "kind": "rapidocr",
        "ocr_ver": "PPOCRV4",
        "model_type": "MOBILE",
        "lang_type": "arabic",
    },
    {
        "id": "tesseract-multi",
        "title": "Tesseract OCR Fast (4-Lang)",
        "desc_key": "desc_tesseract",
        "category": "fast",
        "recommended": False,
        "langs": "FA • EN • ZH • RU",
        "badge": "~25 MB • tessdata",
        "kind": "tesseract",
    },
]

_CATALOG_MAP: Dict[str, Dict[str, Any]] = {m["id"]: m for m in MODEL_CATALOG}


def _pip_python() -> str:
    venv_py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    return str(venv_py) if venv_py.exists() else sys.executable


def _run_pip(*args: str) -> None:
    subprocess.run(
        [_pip_python(), "-m", "pip", *args],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    importlib.invalidate_caches()


def _find_tesseract_exe() -> Optional[str]:
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(candidate).exists():
            tess_dir = str(Path(candidate).parent)
            if tess_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{tess_dir};{os.environ.get('PATH', '')}"
            return candidate
    return None


def is_ocria_installed() -> Tuple[bool, str]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for m in models.list():
        if m.name == "ocria-nano" and m.complete:
            size_mb = m.size_bytes / (1024 * 1024)
            ver = m.version or "1.0.0"
            return True, f"v{ver} • {size_mb:.1f} MB"
    return False, ""


def is_rapidocr_pkg_installed() -> bool:
    return (
        importlib.util.find_spec("rapidocr") is not None
        and importlib.util.find_spec("onnxruntime") is not None
    )


def is_easyocr_pkg_installed() -> bool:
    return importlib.util.find_spec("easyocr") is not None


def is_surya_installed() -> bool:
    return importlib.util.find_spec("surya") is not None and (
        (SURYA_DIR / ".ready").exists() or is_marker_installed()
    )


def is_tesseract_installed(model_id: str = "tesseract-multi") -> bool:
    data_dir, langs, _ = _TESS_VARIANTS[model_id]
    has_data = all((data_dir / f"{lang}.traineddata").exists() for lang in langs)
    return _find_tesseract_exe() is not None and has_data


def is_marker_installed() -> bool:
    return importlib.util.find_spec("marker") is not None


def is_model_installed(model_id: str) -> bool:
    if model_id == "ocria-nano":
        return is_ocria_installed()[0]
    if model_id in _TESS_VARIANTS:
        return is_tesseract_installed(model_id)
    if model_id == "surya-ocr":
        return is_surya_installed()
    if model_id == "marker-pdf":
        return is_marker_installed()
    spec = _CATALOG_MAP.get(model_id)
    if not spec:
        return False
    if spec.get("kind") == "rapidocr":
        return is_rapidocr_pkg_installed() and (RAPID_DIR / f".ready_{model_id}").exists()
    if spec.get("kind") == "easyocr":
        return is_easyocr_pkg_installed() and (EASYOCR_DIR / f".ready_{model_id}").exists()
    return False


def get_model_status(
    active_model_id: str = "ocria-nano",
    custom_models: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str]:
    """Return (is_ready, summary_label) for the selected model."""
    if active_model_id == "ocria-nano":
        ok, info = is_ocria_installed()
        return ok, (f"ocria-nano ({info})" if ok else "ocria-nano missing")
    spec = _CATALOG_MAP.get(active_model_id)
    if spec:
        ok = is_model_installed(active_model_id)
        return ok, spec["title"]

    for cm in custom_models or []:
        if cm.get("id") == active_model_id:
            return True, cm.get("name") or cm.get("model_name") or active_model_id
    return is_ocria_installed()[0], "ocria-nano"


def _build_rapidocr_engine(model_id: str) -> Any:
    from rapidocr import EngineType, ModelType, OCRVersion, RapidOCR  # type: ignore

    spec = _CATALOG_MAP[model_id]
    RAPID_DIR.mkdir(parents=True, exist_ok=True)
    ver = getattr(OCRVersion, spec["ocr_ver"])
    mtype = getattr(ModelType, spec["model_type"])
    det_mtype = ModelType.MOBILE if spec["model_type"] == "SERVER" else mtype
    if spec["ocr_ver"] == "PPOCRV5" and spec["model_type"] == "SERVER":
        det_mtype = ModelType.SERVER

    return RapidOCR(
        params={
            "Global.model_root_dir": str(RAPID_DIR),
            "Global.use_cls": False,
            "Det.engine_type": EngineType.ONNXRUNTIME,
            "Det.ocr_version": ver,
            "Det.model_type": det_mtype,
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Rec.ocr_version": ver,
            "Rec.model_type": mtype,
            "Rec.lang_type": spec["lang_type"],
        }
    )


def _build_easyocr_engine(model_id: str) -> Any:
    import easyocr  # type: ignore

    spec = _CATALOG_MAP[model_id]
    EASYOCR_DIR.mkdir(parents=True, exist_ok=True)
    return easyocr.Reader(
        spec["langs_list"],
        gpu=False,
        model_storage_directory=str(EASYOCR_DIR),
        verbose=False,
    )


def _build_surya_runner() -> Callable[[Image.Image], Any]:
    os.environ.setdefault("MODEL_CACHE_DIR", str(SURYA_DIR))
    os.environ.setdefault("HF_HOME", str(MODEL_DIR / "hf"))
    try:
        from surya import SuryaInferenceManager  # type: ignore
        from surya.recognition import RecognitionPredictor  # type: ignore

        manager = SuryaInferenceManager()
        rec = RecognitionPredictor(manager)
        return lambda img: rec([img])
    except ImportError:
        from surya.detection import DetectionPredictor  # type: ignore
        from surya.foundation import FoundationPredictor  # type: ignore
        from surya.recognition import RecognitionPredictor  # type: ignore

        foundation = FoundationPredictor()
        det = DetectionPredictor()
        rec = RecognitionPredictor(foundation)
        return lambda img: rec([img], det_predictor=det)


def pull_model(from_dir: Optional[str] = None) -> str:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with _engine_lock:
        _liteparse_cache.pop("ocria-nano", None)
    return models.pull("ocria-nano", from_dir=from_dir, quiet=True)


def install_model(model_id: str) -> None:
    """One-click download & prepare any catalog model cleanly."""
    global _marker_cache, _surya_cache
    if model_id == "ocria-nano":
        pull_model()
        return

    if model_id in _TESS_VARIANTS:
        data_dir, langs, base_url = _TESS_VARIANTS[model_id]
        data_dir.mkdir(parents=True, exist_ok=True)
        for lang in langs:
            dest = data_dir / f"{lang}.traineddata"
            if not dest.exists():
                url = f"{base_url}/{lang}.traineddata"
                req = urllib.request.Request(url, headers={"User-Agent": "QuickOCR"})
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    dest.write_bytes(resp.read())

        if _find_tesseract_exe() is None:
            winget = shutil.which("winget")
            if winget:
                subprocess.run(
                    [
                        winget,
                        "install",
                        "-e",
                        "--id",
                        "UB-Mannheim.TesseractOCR",
                        "--accept-source-agreements",
                        "--accept-package-agreements",
                        "--silent",
                    ],
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            if _find_tesseract_exe() is None:
                raise RuntimeError(
                    "tessdata downloaded, but tesseract.exe is not installed. Install UB-Mannheim TesseractOCR."
                )
        with _engine_lock:
            _liteparse_cache.pop(model_id, None)
        return

    if model_id == "surya-ocr":
        if importlib.util.find_spec("surya") is None:
            _run_pip("install", "--no-warn-script-location", "surya-ocr")
        SURYA_DIR.mkdir(parents=True, exist_ok=True)
        dummy = Image.new("RGB", (96, 48), "white")
        with _engine_lock:
            runner = _build_surya_runner()
            runner(dummy)
            _surya_cache = runner
        (SURYA_DIR / ".ready").write_text("ok", encoding="utf-8")
        return

    if model_id == "marker-pdf":
        if not is_marker_installed():
            _run_pip("install", "--no-warn-script-location", "marker-pdf")
        from marker.converters.pdf import PdfConverter  # type: ignore
        from marker.models import create_model_dict  # type: ignore

        with _engine_lock:
            _marker_cache = PdfConverter(artifact_dict=create_model_dict())
        return

    spec = _CATALOG_MAP.get(model_id)
    if not spec:
        return

    if spec.get("kind") == "rapidocr":
        if not is_rapidocr_pkg_installed():
            _run_pip("install", "--no-warn-script-location", "rapidocr[rtl]", "onnxruntime")
        dummy = Image.new("RGB", (64, 32), "white")
        buf = io.BytesIO()
        dummy.save(buf, format="PNG")
        with _engine_lock:
            eng = _build_rapidocr_engine(model_id)
            eng(buf.getvalue())
            _rapid_cache[model_id] = eng
        RAPID_DIR.mkdir(parents=True, exist_ok=True)
        (RAPID_DIR / f".ready_{model_id}").write_text("ok", encoding="utf-8")
        return

    if spec.get("kind") == "easyocr":
        if not is_easyocr_pkg_installed():
            _run_pip("install", "--no-warn-script-location", "easyocr")
        with _engine_lock:
            reader = _build_easyocr_engine(model_id)
            _easyocr_cache[model_id] = reader
        EASYOCR_DIR.mkdir(parents=True, exist_ok=True)
        (EASYOCR_DIR / f".ready_{model_id}").write_text("ok", encoding="utf-8")


def remove_model(model_id: str) -> None:
    global _marker_cache, _surya_cache
    if model_id == "ocria-nano":
        with _engine_lock:
            _liteparse_cache.pop("ocria-nano", None)
        models.rm("ocria-nano")
        return

    if model_id in _TESS_VARIANTS:
        data_dir, _, _ = _TESS_VARIANTS[model_id]
        with _engine_lock:
            _liteparse_cache.pop(model_id, None)
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)
        return

    if model_id == "surya-ocr":
        with _engine_lock:
            _surya_cache = None
        if SURYA_DIR.exists():
            shutil.rmtree(SURYA_DIR, ignore_errors=True)
        if importlib.util.find_spec("surya") is not None and not is_marker_installed():
            _run_pip("uninstall", "-y", "surya-ocr")
        return

    if model_id == "marker-pdf":
        with _engine_lock:
            _marker_cache = None
        _run_pip("uninstall", "-y", "marker-pdf")
        return

    spec = _CATALOG_MAP.get(model_id)
    if not spec:
        return
    if spec.get("kind") == "rapidocr":
        with _engine_lock:
            _rapid_cache.pop(model_id, None)
        marker_file = RAPID_DIR / f".ready_{model_id}"
        if marker_file.exists():
            marker_file.unlink()
    elif spec.get("kind") == "easyocr":
        with _engine_lock:
            _easyocr_cache.pop(model_id, None)
        marker_file = EASYOCR_DIR / f".ready_{model_id}"
        if marker_file.exists():
            marker_file.unlink()
        if EASYOCR_DIR.exists() and not any(EASYOCR_DIR.glob(".ready_*")):
            shutil.rmtree(EASYOCR_DIR, ignore_errors=True)


def _get_liteparse(model_id: str) -> LiteParse:
    if model_id not in _liteparse_cache:
        if model_id in _TESS_VARIANTS:
            data_dir, langs, _ = _TESS_VARIANTS[model_id]
            _find_tesseract_exe()
            _liteparse_cache[model_id] = LiteParse(
                ocr_backend="tesseract",
                tessdata_path=str(data_dir),
                ocr_language="+".join(langs),
                output_format="markdown",
                quiet=True,
            )
        else:
            if not is_ocria_installed()[0]:
                MODEL_DIR.mkdir(parents=True, exist_ok=True)
                models.pull("ocria-nano", quiet=True)
            _liteparse_cache[model_id] = LiteParse(
                ocr_backend="ocria-nano",
                output_format="markdown",
                quiet=True,
            )
    return _liteparse_cache[model_id]


def _get_rapidocr(model_id: str) -> Any:
    if model_id not in _rapid_cache:
        _rapid_cache[model_id] = _build_rapidocr_engine(model_id)
    return _rapid_cache[model_id]


def _get_easyocr(model_id: str) -> Any:
    if model_id not in _easyocr_cache:
        _easyocr_cache[model_id] = _build_easyocr_engine(model_id)
    return _easyocr_cache[model_id]


def _get_surya() -> Callable[[Image.Image], Any]:
    global _surya_cache
    if _surya_cache is None:
        _surya_cache = _build_surya_runner()
    return _surya_cache


def _get_marker() -> Any:
    global _marker_cache
    if _marker_cache is None:
        from marker.converters.pdf import PdfConverter  # type: ignore
        from marker.models import create_model_dict  # type: ignore

        _marker_cache = PdfConverter(artifact_dict=create_model_dict())
    return _marker_cache


def warm_up(active_model_id: str = "ocria-nano") -> None:
    """Pre-load the active local model into RAM when already installed."""
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
        return

    spec = _CATALOG_MAP.get(active_model_id)
    if not spec or not is_model_installed(active_model_id):
        return
    kind = spec["kind"]
    with _engine_lock:
        if kind == "rapidocr":
            _get_rapidocr(active_model_id)
        elif kind == "easyocr":
            _get_easyocr(active_model_id)
        elif kind == "tesseract":
            _get_liteparse(active_model_id)


def fetch_remote_models(base_url: str, api_key: str = "") -> List[str]:
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


def _extract_liteparse(image: Image.Image, model_id: str, output_format: str) -> str:
    if image.width < 48 or image.height < 36:
        edge_color = image.getpixel((0, 0))
        image = ImageOps.expand(image, border=14, fill=edge_color)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        image.save(tmp_path, format="PNG")
        with _engine_lock:
            result = _get_liteparse(model_id).parse(tmp_path)
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


def _extract_rapidocr(image: Image.Image, model_id: str, output_format: str) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    with _engine_lock:
        engine = _get_rapidocr(model_id)
        res = engine(buf.getvalue())

    if res is None or not getattr(res, "txts", None):
        return ""
    if output_format == "markdown" and hasattr(res, "to_markdown"):
        try:
            md = res.to_markdown()
            if md and md.strip():
                return md.strip()
        except Exception:
            pass
    return "\n".join(t for t in res.txts if t).strip()


def _extract_easyocr(image: Image.Image, model_id: str) -> str:
    import numpy as np  # type: ignore

    with _engine_lock:
        reader = _get_easyocr(model_id)
        lines = reader.readtext(np.array(image), detail=0, paragraph=True)
    return "\n".join(str(line).strip() for line in lines if str(line).strip()).strip()


def _extract_surya(image: Image.Image) -> str:
    with _engine_lock:
        preds = _get_surya()(image)
    if not preds:
        return ""
    lines = getattr(preds[0], "text_lines", None) or []
    return "\n".join(
        getattr(line, "text", "").strip()
        for line in lines
        if getattr(line, "text", "").strip()
    ).strip()


def _extract_marker(image: Image.Image) -> str:
    from marker.output import text_from_rendered  # type: ignore

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        image.convert("RGB").save(tmp_path, format="PDF", resolution=150.0)
        with _engine_lock:
            rendered = _get_marker()(tmp_path)
        text, _, _ = text_from_rendered(rendered)
        return (text or "").strip()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


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
    """Extract text from a PIL Image using the active OCR backend or Vision LLM."""
    if image.mode != "RGB":
        image = image.convert("RGB")

    spec = _CATALOG_MAP.get(active_model_id)
    if spec:
        kind = spec["kind"]
        if kind == "rapidocr":
            return _extract_rapidocr(image, active_model_id, output_format)
        if kind == "easyocr":
            return _extract_easyocr(image, active_model_id)
        if kind == "surya":
            return _extract_surya(image)
        if kind == "tesseract":
            return _extract_liteparse(image, active_model_id, output_format)
        if kind == "marker":
            return _extract_marker(image)
        return _extract_liteparse(image, "ocria-nano", output_format)

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
