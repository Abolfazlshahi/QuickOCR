"""Runnable self-check for QuickOCR UI, RTL pill bugfix, multi-model manager, icon, and OCR."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import keyboard
from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

import app
import ocr_engine
from snipper import SnipOverlay, get_virtual_screen_bounds, make_app_icon
from ui_kit import APP_QSS, FloatingToast, load_app_fonts


def main() -> None:
    app.set_app_user_model_id()
    qapp = QApplication.instance() or QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)

    family = load_app_fonts(app.FONTS_DIR)
    assert family == "Vazirmatn", f"Expected Vazirmatn font, got {family!r}"
    f = QFont()
    f.setFamilies([family, "Segoe UI", "Microsoft YaHei UI"])
    f.setPointSize(10)
    qapp.setFont(f)
    qapp.setStyleSheet(APP_QSS)

    # 1. Model present inside D:\app\QuickOCR\models & multi-model API check
    ready, status = ocr_engine.get_model_status("ocria-nano")
    assert ready, f"Model not ready: {status}"
    assert (ocr_engine.MODEL_DIR / "ocria-nano").exists()

    # 2. Hotkey syntax check
    for hk in ("ctrl+alt+c", "ctrl+shift+c", "ctrl+alt+o"):
        assert keyboard.parse_hotkey(hk)

    # 3. Screen bounds, monochrome icon, and native exe check
    vx, vy, vw, vh = get_virtual_screen_bounds()
    assert vw > 0 and vh > 0
    with tempfile.NamedTemporaryFile(suffix=".ico", delete=False) as tmp:
        ico_tmp = Path(tmp.name)
    try:
        make_app_icon(ico_tmp)
        assert ico_tmp.stat().st_size > 0
    finally:
        if ico_tmp.exists():
            ico_tmp.unlink()
    assert (app.BASE_DIR / "QuickOCR.exe").exists(), "QuickOCR.exe missing"

    # 4. Main window: background start, RTL segmented pill fix, 3 languages, responsive
    app.save_config(app.DEFAULT_CONFIG)
    win = app.QuickOCRWindow(qapp, ipc_server=None, start_minimized=False)
    assert not win.isVisible(), "Window should start hidden in tray by default"
    assert not win.windowIcon().isNull()
    assert not qapp.windowIcon().isNull()

    win.show_window()
    qapp.processEvents()

    # Verify visual pill placement & Telegram banner in each language
    for lang, expected_dir, expected_idx, expected_vis_pos in (
        ("fa", Qt.RightToLeft, 0, 2.0),  # Rightmost slot in RTL = فارسی
        ("en", Qt.LeftToRight, 1, 1.0),  # Middle slot in LTR = EN
        ("zh", Qt.LeftToRight, 2, 2.0),  # Rightmost slot in LTR = 中文
    ):
        win._apply_language(lang, save=False)
        qapp.processEvents()
        assert qapp.layoutDirection() == expected_dir
        assert win.lang_seg._idx == expected_idx
        assert win.tg_banner._text == win._t("tg_promo")
        n = len(win.lang_seg._items)
        is_rtl = win.lang_seg.layoutDirection() == Qt.RightToLeft
        vis_pos = ((n - 1.0) - win.lang_seg._pos) if is_rtl else win.lang_seg._pos
        assert abs(vis_pos - expected_vis_pos) < 0.01, (
            f"Pill mismatch for {lang}: got vis_pos={vis_pos}, expected {expected_vis_pos}"
        )

    for w, h in ((400, 500), (495, 675), (640, 680)):
        win.resize(w, h)
        qapp.processEvents()
        assert win.width() >= w and win.height() >= h
        assert win.snip_btn.geometry().right() <= win.width()
        assert win.quit_btn.geometry().right() <= win.width()

    win._apply_language("fa", save=True)

    # 5. Embedded Model Manager view + AnimatedStackedWidget slide + catalog check
    assert len(ocr_engine.MODEL_CATALOG) >= 16
    rec_models = [m for m in ocr_engine.MODEL_CATALOG if m.get("recommended")]
    assert len(rec_models) >= 6
    for req_id in (
        "ocria-nano",
        "surya-ocr",
        "tesseract-best",
        "easyocr-fa",
        "easyocr-ar-fa",
        "easyocr-ru-zh",
        "ppocrv6-tiny",
        "ppocrv6-small",
        "ppocrv6-medium",
        "ppocrv5-arabic",
        "ppocrv5-cyrillic",
        "tesseract-multi",
        "marker-pdf",
    ):
        assert any(m["id"] == req_id for m in ocr_engine.MODEL_CATALOG), f"Missing {req_id}"

    win.stack.slideToIndex(1)
    qapp.processEvents()
    mv = win.models_view
    assert mv._category == "recommended"
    assert mv.cards_layout.count() == len(rec_models)
    assert not mv.custom_card.isVisible()

    mv._on_category_change("all")
    qapp.processEvents()
    assert mv.cards_layout.count() == len(ocr_engine.MODEL_CATALOG)
    assert mv.custom_card.isVisible()

    mv._on_category_change("api")
    qapp.processEvents()
    assert mv.cards_layout.count() == 0
    mv.url_edit.setText("http://localhost:1234/v1")
    mv.model_combo.setEditText("qwen2.5-vl-7b")
    mv._on_add_custom()
    assert win.config["active_model"].startswith("custom_")
    assert len(win.config["custom_models"]) == 1
    assert mv.cards_layout.count() == 1
    mv._remove_model(win.config["active_model"], is_custom=True)
    assert win.config["active_model"] == "ocria-nano"
    assert len(win.config["custom_models"]) == 0

    mv._on_category_change("recommended")
    qapp.processEvents()
    assert mv.cards_layout.count() == len(rec_models)
    for i in range(mv.cards_layout.count()):
        card_w = mv.cards_layout.itemAt(i).widget().minimumSizeHint().width()
        assert card_w <= win.width(), f"Card {i} overflowed window width: {card_w} > {win.width()}"
    win.stack.slideToIndex(0)
    qapp.processEvents()

    # 6. SnipOverlay drag-crop + cancel + FloatingToast + real OCR
    sample = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(sample)
    draw.text((120, 60), "QuickOCR Self-Check 2026", fill="black")

    captured = []
    ov = SnipOverlay(hint_text=win._t("snip_hint"), screenshot=sample)
    ov.captured.connect(captured.append)
    ov.start()
    ov.begin_drag(QPoint(90, 40))
    ov.move_drag(QPoint(460, 130))
    ov._tick_dash()
    ov.end_drag(QPoint(460, 130))

    cancelled = []
    ov2 = SnipOverlay(hint_text=win._t("snip_hint"), screenshot=sample)
    ov2.cancelled.connect(lambda: cancelled.append(True))
    ov2.start()
    ov2.cancel_snip()

    toast = FloatingToast()
    toast.show_loading(win._t("status_processing"))
    qapp.processEvents()
    toast.show_result(win._t("status_copied"), ok=True, sub="185 ms")
    qapp.processEvents()
    toast.close()

    assert len(captured) == 1 and captured[0].size == (371, 91), f"Bad crop: {captured}"
    assert cancelled == [True]

    md = ocr_engine.extract_text(captured[0], output_format="markdown")
    txt = ocr_engine.extract_text(captured[0], output_format="text")
    assert "QuickOCR" in md and "2026" in md
    assert "QuickOCR" in txt and "2026" in txt

    QTimer.singleShot(250, win.quit_app)
    qapp.exec()

    print(f"ALL CHECKS PASSED (font={family}, pill_rtl_fixed=True, models_mgr=OK, ocr={txt!r})")


if __name__ == "__main__":
    main()
