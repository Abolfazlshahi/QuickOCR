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
from i18n import LANGUAGES, TRANSLATIONS
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

    # 0. Trilingual key completeness check (Updater + Download progress)
    req_i18n = (
        "btn_check_update",
        "btn_install_update",
        "msg_checking_update",
        "msg_up_to_date",
        "msg_update_avail",
        "msg_update_downloading",
        "msg_update_applying",
        "msg_update_err",
        "msg_pip_stage",
        "msg_weights_stage",
        "msg_install_ready",
        "desc_ocria_1",
    )
    for lang_code in LANGUAGES:
        for k in req_i18n:
            assert k in TRANSLATIONS[lang_code], f"Missing i18n[{lang_code!r}][{k!r}]"

    # 1. Model present inside D:\app\QuickOCR\models & multi-model API check
    ready, status = ocr_engine.get_model_status("ocria-nano")
    assert ready, f"Model not ready: {status}"
    assert (ocr_engine.MODEL_DIR / "ocria-nano").exists()

    # 2. Hotkey syntax check
    if sys.platform == "win32":
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
    if sys.platform == "win32":
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
        "ocria-1",
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
    lm, _, rm, _ = mv.scroll_col.getContentsMargins()
    assert lm >= 10 and rm >= 10, f"Scroll margins too tight for RTL scrollbar: {(lm, rm)}"
    assert hasattr(mv, "progress_bar") and hasattr(mv, "status_frame")
    mv._busy = True
    mv._on_progress(45, "Downloading...")
    qapp.processEvents()
    assert mv.progress_bar.value() == 45 and not mv.progress_bar.isHidden()
    mv._on_task_done(False, "Sample error detail")
    qapp.processEvents()
    assert not mv._busy and mv.progress_bar.isHidden() and "Sample error" in mv.status_lbl.text()

    # Check download_file progress & pip error reporting
    assert hasattr(ocr_engine, "download_file")
    import http.server, threading, socketserver
    payload = b"OCR-TEST" * 1024
    class _H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), _H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.handle_request, daemon=True)
    t.start()
    pcts = []
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        dst = Path(tf.name)
    try:
        ocr_engine.download_file(f"http://127.0.0.1:{port}/test.bin", dst, on_progress=lambda p, _s="": pcts.append(p))
        assert dst.read_bytes() == payload and 100 in pcts
    finally:
        srv.server_close()
        dst.unlink(missing_ok=True)
    err_msg = ocr_engine._extract_pip_error(["Collecting x", "ERROR: No matching distribution found for x"], 1)
    assert "No matching distribution" in err_msg

    # Verify HTTP Range resume in download_file, markdown fence strip, and llama.cpp asset matcher
    assert any(m["id"] == "ocria-1" and m.get("recommended") for m in ocr_engine.MODEL_CATALOG)
    assert ocr_engine._strip_markdown_fence("```markdown\n# Title\nBody\n```") == "# Title\nBody"
    assert ocr_engine._select_llamacpp_asset(
        [{"name": "llama-b1-bin-win-cpu-x64.zip", "browser_download_url": "https://x/w.zip"},
         {"name": "llama-b1-bin-ubuntu-x64.tar.gz", "browser_download_url": "https://x/l.tgz"}],
        "win32",
    )[1].endswith("win-cpu-x64.zip")
    class _RangeH(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            rng = self.headers.get("Range", "")
            start = int(rng.replace("bytes=", "").split("-")[0]) if rng.startswith("bytes=") else 0
            chunk = payload[start:]
            self.send_response(206 if start > 0 else 200)
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
        def log_message(self, *args):
            pass
    srv2 = socketserver.TCPServer(("127.0.0.1", 0), _RangeH)
    t2 = threading.Thread(target=srv2.handle_request, daemon=True)
    t2.start()
    with tempfile.NamedTemporaryFile(delete=False) as tf2:
        dst2 = Path(tf2.name)
    try:
        dst2.unlink(missing_ok=True)
        part2 = dst2.with_suffix(dst2.suffix + ".part")
        part2.write_bytes(payload[:2048])
        ocr_engine.download_file(f"http://127.0.0.1:{srv2.server_address[1]}/big.bin", dst2, resume=True)
        assert dst2.read_bytes() == payload
    finally:
        srv2.server_close()
        dst2.unlink(missing_ok=True)
        dst2.with_suffix(dst2.suffix + ".part").unlink(missing_ok=True)

    for i in range(mv.cards_layout.count()):
        card_w = mv.cards_layout.itemAt(i).widget().minimumSizeHint().width()
        assert card_w <= win.width(), f"Card {i} overflowed window width: {card_w} > {win.width()}"
    # 5b. Auto-updater pure logic + UI footer check
    import updater
    assert updater.parse_version("v1.1.0") == (1, 1, 0)
    assert updater.is_newer_version("v1.2.0", "v1.1.0")
    assert not updater.is_newer_version("v1.1.0", "1.1.0")
    assert not updater.is_newer_version("v1.0.3", "1.1.0")
    fake_assets = [
        {"name": "QuickOCR-v1.2.0-Windows-Portable.zip", "browser_download_url": "https://example.invalid/w.zip", "size": 100},
        {"name": "QuickOCR-v1.2.0-Windows-Setup.exe", "browser_download_url": "https://example.invalid/s.exe", "size": 120},
        {"name": "QuickOCR-v1.2.0-Linux-Portable.tar.gz", "browser_download_url": "https://example.invalid/l.tar.gz", "size": 90},
        {"name": "QuickOCR-v1.2.0-Linux-x86_64.AppImage", "browser_download_url": "https://example.invalid/l.AppImage", "size": 95},
    ]
    assert updater.select_release_asset(fake_assets, "win32")["name"].endswith("Windows-Portable.zip")
    assert updater.select_release_asset(fake_assets, "linux")["name"].endswith("Linux-Portable.tar.gz")
    assert updater.select_release_asset(fake_assets, "linux", prefer_appimage=True)["name"].endswith(".AppImage")
    assert hasattr(ocr_engine, "resolve_data_dir")
    assert ocr_engine.resolve_data_dir(app.BASE_DIR) == app.BASE_DIR
    assert ocr_engine.resolve_data_dir(app.BASE_DIR, force_readonly=True) != app.BASE_DIR

    import zipfile
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        zpath = tdp / "upd.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("QuickOCR/app.py", "# new app")
            zf.writestr("QuickOCR/config.json", '{"should_not_overwrite": true}')
            zf.writestr("QuickOCR/packages/stale.py", "x")
        target = tdp / "installed"
        target.mkdir()
        (target / "config.json").write_text('{"keep": 1}', encoding="utf-8")
        (target / ".venv").mkdir()
        (target / ".venv" / "marker.txt").write_text("keep", encoding="utf-8")
        (target / "packages").mkdir()
        (target / "packages" / "pkg.txt").write_text("keep", encoding="utf-8")
        staged = updater.extract_update_archive(zpath, tdp / "stage")
        updater.copy_update_tree(staged, target)
        assert (target / "app.py").read_text(encoding="utf-8") == "# new app"
        assert '"keep": 1' in (target / "config.json").read_text(encoding="utf-8")
        assert (target / ".venv" / "marker.txt").exists()
        assert (target / "packages" / "pkg.txt").exists()

    assert hasattr(win, "update_btn") and hasattr(win, "ver_lbl") and hasattr(win, "update_progress")
    win._on_update_checked(
        True,
        updater.ReleaseInfo("v9.9.9", "Test notes", "QuickOCR-v9.9.9-Windows.zip", "https://example.invalid/w.zip", 123),
        "",
    )
    qapp.processEvents()
    assert "v9.9.9" in win.update_btn.text()
    win._available_release = None
    win.update_btn.setText(win._t("btn_check_update"))
    win.update_status_lbl.setText("")

    # 5c. Linux cross-platform helpers & shell installers
    assert hasattr(app, "get_linux_autostart_path")
    assert str(app.get_linux_autostart_path()).replace("\\", "/").endswith(".config/autostart/quickocr.desktop")
    assert hasattr(app, "_play_beep") and hasattr(app, "_open_app_folder")
    assert (app.BASE_DIR / "setup_linux.sh").exists()
    assert (app.BASE_DIR / "QuickOCR.sh").exists()
    assert (app.BASE_DIR / "installer.iss").exists()
    import snipper
    qt_shot = snipper._capture_qt_virtual_screen()
    assert qt_shot.width > 0 and qt_shot.height > 0
    assert app._parse_ipc_command(b"SNIP") == "SNIP"
    assert app._parse_ipc_command(b"SHOW") == "SHOW"

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
    assert "QuickOCR Self-Check 2026" in md
    assert "QuickOCR Self-Check 2026" in txt

    # Dark-mode mixed Persian+English OCR quality check
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtCore import QRect
    dark_qi = QImage(780, 80, QImage.Format_RGB888)
    dark_qi.fill(QColor(18, 18, 22))
    dp = QPainter(dark_qi)
    dp.setPen(QColor(244, 244, 245))
    dp.setFont(QFont(family, 13))
    dp.drawText(QRect(16, 10, 748, 60), Qt.AlignRight | Qt.AlignVCenter, "سلام دنیای QuickOCR نسخه 2026 عالی است.")
    dp.end()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        dp_path = Path(tf.name)
    try:
        dark_qi.save(str(dp_path))
        dark_pil = Image.open(dp_path).convert("RGB")
    finally:
        dp_path.unlink(missing_ok=True)
    prepped = ocr_engine._preprocess_ocr_image(dark_pil)
    assert prepped.getpixel((4, 4))[0] > 200 and prepped.width > dark_pil.width
    fa_out = ocr_engine.extract_text(dark_pil, output_format="text")
    assert (
        "quickocr" in fa_out.lower()
        and "2026" in fa_out
        and fa_out.count(" ") >= 4
        and any("\u0600" <= ch <= "\u06ff" for ch in fa_out)
    ), f"Bad dark FA OCR: {fa_out!r}"

    QTimer.singleShot(250, win.quit_app)
    qapp.exec()

    print(f"ALL CHECKS PASSED (font={family}, pill_rtl_fixed=True, models_mgr=OK, ocr={txt!r})")


if __name__ == "__main__":
    main()
