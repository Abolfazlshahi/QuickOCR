"""QuickOCR — Responsive minimal black trilingual desktop app (PySide6 + OCRia-nano-1)."""

from __future__ import annotations

import ctypes
import json
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import winsound

import keyboard
import pyperclip
from PIL import Image, ImageGrab
from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import ocr_engine
from i18n import LANGUAGES, tr
from models_dialog import ModelsView
from snipper import SnipOverlay, make_app_icon
from ui_kit import (
    APP_QSS,
    C_BG,
    C_CARD,
    C_DIM,
    C_MUTED,
    C_OK,
    C_SURFACE,
    C_TEXT,
    AnimatedButton,
    AnimatedSegmented,
    AnimatedStackedWidget,
    FloatingToast,
    TelegramBanner,
    ToggleRow,
    apply_window_taskbar_identity,
    load_app_fonts,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
ICON_PATH = BASE_DIR / "icon.ico"
LOGO_PATH = BASE_DIR / "assets" / "logo.png"
FONTS_DIR = BASE_DIR / "assets" / "fonts"
EXE_LAUNCHER = BASE_DIR / "QuickOCR.exe"
PYTHONW_EXE = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
APP_SCRIPT = BASE_DIR / "app.py"
IPC_NAME = "QuickOCR_LocalIPC_v2"

DEFAULT_CONFIG: Dict[str, Any] = {
    "hotkey": "ctrl+alt+c",
    "output_format": "markdown",
    "play_sound": True,
    "start_minimized": True,
    "language": "fa",
    "active_model": "ocria-nano",
    "custom_models": [],
}


def set_app_user_model_id() -> None:
    """Bind process to a dedicated Windows AppUserModelID so Taskbar uses QuickOCR's icon."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QuickOCR.Desktop.App.1")
    except Exception:
        pass


def load_config() -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: data[k] for k in DEFAULT_CONFIG if k in data})
        except Exception:
            pass
    if cfg.get("language") not in LANGUAGES:
        cfg["language"] = "fa"
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_startup_shortcut_path() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "QuickOCR.lnk"


def create_windows_shortcut(
    lnk_path: Path,
    target: Path,
    arguments: str,
    workdir: Path,
    icon_path: Path,
) -> None:
    """Create a Windows .lnk shortcut using built-in WScript.Shell."""
    def esc(s: str) -> str:
        return s.replace("'", "''")

    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{esc(str(lnk_path))}'); "
        f"$s.TargetPath = '{esc(str(target))}'; "
        f"$s.Arguments = '{esc(str(arguments))}'; "
        f"$s.WorkingDirectory = '{esc(str(workdir))}'; "
        f"$s.IconLocation = '{esc(str(icon_path))}'; "
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def is_autostart_enabled() -> bool:
    return get_startup_shortcut_path().exists()


def set_autostart(enabled: bool) -> None:
    lnk = get_startup_shortcut_path()
    if enabled:
        lnk.parent.mkdir(parents=True, exist_ok=True)
        if EXE_LAUNCHER.exists():
            target, args = EXE_LAUNCHER, "--minimized"
        else:
            target = PYTHONW_EXE if PYTHONW_EXE.exists() else Path(sys.executable)
            args = f'"{APP_SCRIPT}" --minimized'
        create_windows_shortcut(
            lnk_path=lnk,
            target=target,
            arguments=args,
            workdir=BASE_DIR,
            icon_path=ICON_PATH,
        )
    elif lnk.exists():
        lnk.unlink()


class _Bridge(QObject):
    hotkey_fired = Signal()
    warmup_done = Signal(bool, str)
    ocr_done = Signal(str, int)
    ocr_error = Signal(str)


class StatusDot(QWidget):
    """Crisp anti-aliased circular status dot with subtle 60fps breathing halo."""

    def __init__(self, color: str = C_MUTED, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._breathing = False
        self._phase = 0.0
        self.setFixedSize(14, 14)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def setColor(self, color: str, breathe: bool = False) -> None:
        self._color = QColor(color)
        self._breathing = breathe
        if breathe and not self._timer.isActive():
            self._timer.start()
        elif not breathe and self._timer.isActive():
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.1) % (2.0 * math.pi)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        if self._breathing:
            halo_alpha = int(40 + 45 * (0.5 + 0.5 * math.sin(self._phase)))
            halo = QColor(self._color.red(), self._color.green(), self._color.blue(), halo_alpha)
            p.setBrush(halo)
            p.drawEllipse(1, 1, 12, 12)
        p.setBrush(self._color)
        p.drawEllipse(3, 3, 8, 8)


class QuickOCRWindow(QWidget):
    def __init__(
        self,
        qapp: QApplication,
        ipc_server: Optional[QLocalServer] = None,
        start_minimized: bool = False,
    ) -> None:
        super().__init__()
        self.qapp = qapp
        self.ipc_server = ipc_server
        self.config = load_config()
        self.lang = self.config["language"]

        self._model_ready = False
        self._snip_active = False
        self._ocr_busy = False
        self._restore_after_snip = False
        self._registered_hotkey: Optional[str] = None
        self._snip_overlay: Optional[SnipOverlay] = None
        self._status_key = "status_bg_ready"
        self._last_elapsed_ms: Optional[int] = None

        make_app_icon(ICON_PATH, LOGO_PATH)
        self.app_icon = QIcon(str(ICON_PATH))
        self.qapp.setWindowIcon(self.app_icon)

        self.setObjectName("MainRoot")
        self.setWindowTitle("QuickOCR")
        self.setWindowIcon(self.app_icon)
        self.resize(495, 688)
        self.setMinimumSize(390, 480)
        apply_window_taskbar_identity(self, ICON_PATH, EXE_LAUNCHER)

        self.bridge = _Bridge()
        self.bridge.hotkey_fired.connect(self._open_snip_overlay)
        self.bridge.warmup_done.connect(self._on_warmup_done)
        self.bridge.ocr_done.connect(self._handle_ocr_success)
        self.bridge.ocr_error.connect(self._handle_ocr_error)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(240)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._slide_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_anim.setDuration(240)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._show_group = QParallelAnimationGroup(self)
        self._show_group.addAnimation(self._fade_anim)
        self._show_group.addAnimation(self._slide_anim)

        self.toast = FloatingToast()

        self._build_ui()
        self._apply_language(self.lang, save=False)
        self._apply_hotkey(self.config["hotkey"], silent=True)
        self._setup_tray()

        if self.ipc_server is not None:
            self.ipc_server.newConnection.connect(self._on_ipc_connection)

        hide_on_start = start_minimized or bool(self.config.get("start_minimized", True))
        if not hide_on_start:
            self.show_window()
        elif not start_minimized and QSystemTrayIcon.isSystemTrayAvailable():
            hk = self.config["hotkey"]
            self.tray.showMessage(
                self._t("tray_ready_title"),
                self._t("tray_ready_body", hk=hk),
                QSystemTrayIcon.NoIcon,
                2400,
            )

        threading.Thread(target=self._warmup_worker, daemon=True).start()

    def _t(self, key: str, **kwargs: str) -> str:
        return tr(self.lang, key, **kwargs)

    def _build_ui(self) -> None:
        win_layout = QVBoxLayout(self)
        win_layout.setContentsMargins(0, 0, 0, 0)
        win_layout.setSpacing(0)

        self.stack = AnimatedStackedWidget(self)
        win_layout.addWidget(self.stack)

        main_page = QWidget()
        main_page.setObjectName("MainRoot")
        outer = QVBoxLayout(main_page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable container guarantees zero clipped controls at any window size
        scroll = QScrollArea(main_page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setAutoFillBackground(True)
        scroll.viewport().setStyleSheet(f"background-color: {C_BG};")
        outer.addWidget(scroll)

        body = QWidget()
        body.setObjectName("MainRoot")
        body.setAutoFillBackground(True)
        scroll.setWidget(body)

        root_col = QVBoxLayout(body)
        root_col.setContentsMargins(18, 12, 18, 6)
        root_col.setSpacing(8)

        # --- Header ---
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        title_lbl = QLabel("QuickOCR")
        title_font = QFont(self.font())
        title_font.setPointSize(14)
        title_font.setWeight(QFont.Bold)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        hdr.addWidget(title_lbl)

        self.status_dot = StatusDot(C_MUTED)
        hdr.addWidget(self.status_dot)

        self.model_lbl = QLabel()
        self.model_lbl.setStyleSheet(f"color: {C_MUTED}; background: transparent;")
        hdr.addWidget(self.model_lbl)
        hdr.addStretch(1)

        self.folder_btn = AnimatedButton(
            "", variant="ghost", radius=9, height=30, padx=12
        )
        self.folder_btn.clicked.connect(lambda: os.startfile(str(BASE_DIR)))
        hdr.addWidget(self.folder_btn)
        root_col.addLayout(hdr)

        # --- Telegram Channel Promo Banner ---
        self.tg_banner = TelegramBanner()
        root_col.addWidget(self.tg_banner)

        # --- Hero Action Buttons ---
        hero = QHBoxLayout()
        hero.setSpacing(10)

        self.snip_btn = AnimatedButton("", variant="primary", radius=11, height=40, padx=18)
        btn_f = QFont(self.font())
        btn_f.setWeight(QFont.DemiBold)
        self.snip_btn.setFont(btn_f)
        self.snip_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.snip_btn.clicked.connect(self._trigger_snip_from_button)
        hero.addWidget(self.snip_btn, 1)

        self.clip_btn = AnimatedButton("", variant="secondary", radius=11, height=40, padx=16)
        self.clip_btn.clicked.connect(self._trigger_clipboard_ocr)
        hero.addWidget(self.clip_btn, 0)
        root_col.addLayout(hero)

        # --- Settings Card ---
        cfg_card = QFrame()
        cfg_card.setObjectName("Card")
        cfg_col = QVBoxLayout(cfg_card)
        cfg_col.setContentsMargins(14, 8, 14, 8)
        cfg_col.setSpacing(5)

        # Language row
        lang_row = QHBoxLayout()
        lang_row.setSpacing(10)
        self.lang_lbl = QLabel()
        self.lang_lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; background: transparent;")
        lang_row.addWidget(self.lang_lbl)
        lang_row.addStretch(1)
        self.lang_seg = AnimatedSegmented(
            options=(("fa", "فارسی"), ("en", "EN"), ("zh", "中文")),
            initial=self.lang,
            on_change=lambda v: self._apply_language(v, save=True),
            height=30,
            min_seg_width=56,
        )
        lang_row.addWidget(self.lang_seg)
        cfg_col.addLayout(lang_row)

        cfg_col.addWidget(self._divider())

        # Active OCR Model row + Manager button
        mdl_row = QHBoxLayout()
        mdl_row.setSpacing(8)
        self.mdl_lbl = QLabel()
        self.mdl_lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; background: transparent;")
        mdl_row.addWidget(self.mdl_lbl)
        mdl_row.addStretch(1)

        self.active_model_pill = QLabel()
        self.active_model_pill.setLayoutDirection(Qt.LeftToRight)
        self.active_model_pill.setStyleSheet(
            f"background: {C_SURFACE}; color: {C_MUTED}; border: 1px solid #242426; "
            "border-radius: 8px; padding: 3px 10px; font-family: Consolas; font-size: 8.5pt;"
        )
        mdl_row.addWidget(self.active_model_pill)

        self.models_btn = AnimatedButton("", variant="secondary", radius=9, height=30, padx=12)
        self.models_btn.clicked.connect(self._open_models_dialog)
        mdl_row.addWidget(self.models_btn)
        cfg_col.addLayout(mdl_row)

        cfg_col.addWidget(self._divider())

        # Hotkey row
        hk_row = QHBoxLayout()
        hk_row.setSpacing(8)
        self.hk_lbl = QLabel()
        self.hk_lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; background: transparent;")
        hk_row.addWidget(self.hk_lbl)
        hk_row.addStretch(1)

        self.hotkey_edit = QLineEdit(self.config["hotkey"])
        self.hotkey_edit.setObjectName("HotkeyEdit")
        self.hotkey_edit.setLayoutDirection(Qt.LeftToRight)
        self.hotkey_edit.setAlignment(Qt.AlignCenter)
        self.hotkey_edit.setMinimumWidth(140)
        self.hotkey_edit.setMaximumWidth(190)
        self.hotkey_edit.setFixedHeight(32)
        self.hotkey_edit.returnPressed.connect(self._on_save_hotkey)
        hk_row.addWidget(self.hotkey_edit)

        self.save_hk_btn = AnimatedButton("", variant="secondary", radius=9, height=32, padx=14)
        self.save_hk_btn.clicked.connect(self._on_save_hotkey)
        hk_row.addWidget(self.save_hk_btn)
        cfg_col.addLayout(hk_row)

        # Preset chips (explicit LTR group)
        chips_wrap = QWidget()
        chips_wrap.setLayoutDirection(Qt.LeftToRight)
        chips_wrap.setStyleSheet("background: transparent;")
        chips = QHBoxLayout(chips_wrap)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        chips.addStretch(1)
        for preset in ("ctrl+alt+c", "ctrl+shift+c", "ctrl+alt+o"):
            chip = AnimatedButton(preset, variant="ghost", radius=8, height=24, padx=10)
            chip_f = QFont("Consolas", 8)
            chip.setFont(chip_f)
            chip.clicked.connect(lambda _=False, p=preset: self._set_preset_hotkey(p))
            chips.addWidget(chip)
        cfg_col.addWidget(chips_wrap)

        cfg_col.addWidget(self._divider())

        # Output format segmented row
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(10)
        self.fmt_lbl = QLabel()
        self.fmt_lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; background: transparent;")
        fmt_row.addWidget(self.fmt_lbl)
        fmt_row.addStretch(1)
        self.fmt_seg = AnimatedSegmented(
            options=(("markdown", "Markdown"), ("text", "Plain Text")),
            initial=self.config["output_format"],
            on_change=self._set_output_format,
            height=30,
            min_seg_width=80,
        )
        fmt_row.addWidget(self.fmt_seg)
        cfg_col.addLayout(fmt_row)

        cfg_col.addWidget(self._divider())

        # Animated toggles
        self.sound_row = ToggleRow(
            "", bool(self.config.get("play_sound", True)), self._on_toggle_sound
        )
        cfg_col.addWidget(self.sound_row)

        self.tray_row = ToggleRow(
            "", bool(self.config.get("start_minimized", True)), self._on_toggle_tray_start
        )
        cfg_col.addWidget(self.tray_row)

        self.autostart_row = ToggleRow(
            "", is_autostart_enabled(), self._on_toggle_autostart
        )
        cfg_col.addWidget(self.autostart_row)

        root_col.addWidget(cfg_card)

        # --- Output Preview Card ---
        res_card = QFrame()
        res_card.setObjectName("Card")
        res_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        res_col = QVBoxLayout(res_card)
        res_col.setContentsMargins(14, 9, 14, 9)
        res_col.setSpacing(6)

        res_hdr = QHBoxLayout()
        res_hdr.setSpacing(8)
        self.preview_lbl = QLabel()
        self.preview_lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; background: transparent;")
        res_hdr.addWidget(self.preview_lbl)
        res_hdr.addStretch(1)

        self.timing_lbl = QLabel("")
        self.timing_lbl.setLayoutDirection(Qt.LeftToRight)
        self.timing_lbl.setStyleSheet(
            f"color: {C_DIM}; font-family: Consolas; font-size: 8pt; background: transparent;"
        )
        res_hdr.addWidget(self.timing_lbl)

        self.copy_btn = AnimatedButton("", variant="secondary", radius=8, height=28, padx=12)
        self.copy_btn.clicked.connect(self._copy_preview)
        res_hdr.addWidget(self.copy_btn)
        res_col.addLayout(res_hdr)

        self.preview_edit = QTextEdit()
        self.preview_edit.setObjectName("PreviewEdit")
        self.preview_edit.setMinimumHeight(48)
        self.preview_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        res_col.addWidget(self.preview_edit, 1)

        root_col.addWidget(res_card, 1)

        # --- Pinned Status + Footer outside scroll area ---
        footer_wrap = QWidget()
        footer_wrap.setObjectName("MainRoot")
        footer_col = QVBoxLayout(footer_wrap)
        footer_col.setContentsMargins(18, 4, 18, 14)
        footer_col.setSpacing(8)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 8.5pt; background: transparent;")
        status_row.addWidget(self.status_lbl)
        status_row.addStretch(1)

        self.hk_pill = QLabel(self.config["hotkey"])
        self.hk_pill.setLayoutDirection(Qt.LeftToRight)
        self.hk_pill.setStyleSheet(
            f"background: {C_SURFACE}; color: {C_MUTED}; border: 1px solid #242426; "
            "border-radius: 7px; padding: 2px 8px; font-family: Consolas; font-size: 8pt;"
        )
        status_row.addWidget(self.hk_pill)
        footer_col.addLayout(status_row)

        foot = QHBoxLayout()
        foot.setSpacing(10)
        self.hide_btn = AnimatedButton("", variant="secondary", radius=10, height=34, padx=16)
        self.hide_btn.clicked.connect(self.hide_to_tray)
        foot.addWidget(self.hide_btn)
        foot.addStretch(1)

        self.quit_btn = AnimatedButton("", variant="danger", radius=10, height=34, padx=16)
        self.quit_btn.clicked.connect(self.quit_app)
        foot.addWidget(self.quit_btn)
        footer_col.addLayout(foot)

        outer.addWidget(footer_wrap)
        self.stack.addWidget(main_page)

        self.models_view = ModelsView(
            lang=self.lang,
            active_model_id=self.config.get("active_model", "ocria-nano"),
            custom_models=self.config.get("custom_models", []),
            on_models_changed=self._on_models_changed,
            on_back=lambda: self.stack.slideToIndex(0),
        )
        self.stack.addWidget(self.models_view)

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        return line

    # --- Internationalization ---

    def _apply_language(self, lang: str, save: bool = True) -> None:
        if lang not in LANGUAGES:
            lang = "fa"
        self.lang = lang
        if save:
            self.config["language"] = lang
            save_config(self.config)

        direction = Qt.RightToLeft if lang == "fa" else Qt.LeftToRight
        self.qapp.setLayoutDirection(direction)
        self.setLayoutDirection(direction)
        self.lang_seg.set_value(lang)

        # Re-apply Vazirmatn + Segoe UI + YaHei font family cleanly
        f = QFont(self.qapp.font())
        f.setFamilies(["Vazirmatn", "Segoe UI", "Microsoft YaHei UI"])
        self.qapp.setFont(f)

        self.model_lbl.setText(
            self._t("status_ready") if self._model_ready else self._t("status_loading_model")
        )
        self.folder_btn.setText(self._t("btn_open_folder"))
        self.tg_banner.setText(self._t("tg_promo"))
        self.snip_btn.setText(self._t("btn_snip"))
        self.clip_btn.setText(self._t("btn_clipboard"))
        self.lang_lbl.setText(self._t("lbl_language"))
        self.mdl_lbl.setText(self._t("lbl_model"))
        self.models_btn.setText(self._t("btn_models"))
        self._refresh_model_pill()
        self.hk_lbl.setText(self._t("lbl_hotkey"))
        self.save_hk_btn.setText(self._t("btn_save_hotkey"))
        self.fmt_lbl.setText(self._t("lbl_format"))
        self.fmt_seg.update_labels([self._t("fmt_markdown"), self._t("fmt_text")])
        self.sound_row.setText(self._t("opt_sound"))
        self.tray_row.setText(self._t("opt_tray"))
        self.autostart_row.setText(self._t("opt_autostart"))
        self.preview_lbl.setText(self._t("lbl_preview"))
        self.preview_edit.setPlaceholderText(self._t("preview_placeholder"))
        self.copy_btn.setText(self._t("btn_copy"))
        self.hide_btn.setText(self._t("btn_hide"))
        self.quit_btn.setText(self._t("btn_quit"))
        self.status_lbl.setText(self._t(self._status_key))

        if hasattr(self, "models_view"):
            self.models_view.refresh_language(lang)
        if hasattr(self, "tray"):
            self._rebuild_tray_menu()

    def _refresh_model_pill(self) -> None:
        active_id = self.config.get("active_model", "ocria-nano")
        _, label = ocr_engine.get_model_status(active_id, self.config.get("custom_models", []))
        self.active_model_pill.setText(label)

    def _open_models_dialog(self) -> None:
        self.models_view._rebuild_list()
        self.stack.slideToIndex(1)

    def _on_models_changed(self, active_id: str, custom_models: List[Dict[str, Any]]) -> None:
        self.config["active_model"] = active_id
        self.config["custom_models"] = custom_models
        save_config(self.config)
        self._refresh_model_pill()
        self._set_status("status_model_switched")
        threading.Thread(target=self._warmup_worker, daemon=True).start()

    # --- Warmup & IPC ---

    def _warmup_worker(self) -> None:
        active_id = self.config.get("active_model", "ocria-nano")
        custom = self.config.get("custom_models", [])
        try:
            ready, _ = ocr_engine.get_model_status(active_id, custom)
            if not ready and active_id == "ocria-nano":
                self.bridge.warmup_done.emit(False, "status_downloading_model")
            ocr_engine.warm_up(active_id)
            ready, _ = ocr_engine.get_model_status(active_id, custom)
            self.bridge.warmup_done.emit(ready, "status_ready" if ready else "status_error")
        except Exception as exc:
            self.bridge.warmup_done.emit(False, str(exc))

    def _on_warmup_done(self, ok: bool, msg_or_key: str) -> None:
        self._model_ready = ok
        self.status_dot.setColor(C_OK if ok else C_MUTED, breathe=ok)
        text = self._t(msg_or_key) if msg_or_key.startswith("status_") else msg_or_key
        self.model_lbl.setText(text)

    def _on_ipc_connection(self) -> None:
        if self.ipc_server is None:
            return
        while self.ipc_server.hasPendingConnections():
            sock = self.ipc_server.nextPendingConnection()
            if sock is not None:
                sock.waitForReadyRead(100)
                sock.close()
                sock.deleteLater()
        self.show_window()

    # --- Settings & Hotkey ---

    def _set_preset_hotkey(self, preset: str) -> None:
        self.hotkey_edit.setText(preset)
        self._on_save_hotkey()

    def _on_save_hotkey(self) -> None:
        raw = self.hotkey_edit.text().strip().lower().replace(" ", "")
        if not raw:
            QMessageBox.warning(
                self, self._t("err_invalid_hotkey_title"), self._t("err_invalid_hotkey_msg")
            )
            return
        if self._apply_hotkey(raw, silent=False):
            self.config["hotkey"] = raw
            save_config(self.config)
            self.hk_pill.setText(raw)
            self._set_status("status_hotkey_saved")
            self._rebuild_tray_menu()

    def _apply_hotkey(self, hotkey_str: str, silent: bool = False) -> bool:
        try:
            keyboard.parse_hotkey(hotkey_str)
        except Exception as exc:
            if not silent:
                QMessageBox.warning(
                    self,
                    self._t("err_invalid_hotkey_title"),
                    f"{self._t('err_invalid_hotkey_msg')}\n({exc})",
                )
            return False

        if self._registered_hotkey is not None:
            try:
                keyboard.remove_hotkey(self._registered_hotkey)
            except Exception:
                pass
            self._registered_hotkey = None

        try:
            self._registered_hotkey = keyboard.add_hotkey(
                hotkey_str,
                self.bridge.hotkey_fired.emit,
                suppress=False,
            )
            return True
        except Exception as exc:
            if not silent:
                QMessageBox.warning(self, self._t("err_invalid_hotkey_title"), str(exc))
            return False

    def _set_output_format(self, val: str) -> None:
        self.config["output_format"] = val
        save_config(self.config)
        self._set_status("status_saved")

    def _on_toggle_sound(self, checked: bool) -> None:
        self.config["play_sound"] = bool(checked)
        save_config(self.config)
        self._set_status("status_saved")

    def _on_toggle_tray_start(self, checked: bool) -> None:
        self.config["start_minimized"] = bool(checked)
        save_config(self.config)
        self._set_status("status_saved")

    def _on_toggle_autostart(self, checked: bool) -> None:
        try:
            set_autostart(bool(checked))
            self._set_status("status_autostart_on" if checked else "status_autostart_off")
        except Exception as exc:
            self.autostart_row.toggle.setCheckedSilent(not checked)
            QMessageBox.warning(self, "QuickOCR", f"{self._t('err_autostart_fail')}\n{exc}")

    def _set_status(self, key: str) -> None:
        self._status_key = key
        self.status_lbl.setText(self._t(key))

    # --- Capture & OCR ---

    def _trigger_snip_from_button(self) -> None:
        if self._snip_active or self._ocr_busy:
            return
        self._restore_after_snip = self.isVisible() and not self.isMinimized()
        if self._restore_after_snip:
            self.hide()
            from PySide6.QtCore import QTimer

            QTimer.singleShot(180, self._open_snip_overlay)
        else:
            self._open_snip_overlay()

    def _open_snip_overlay(self) -> None:
        if self._snip_active or self._ocr_busy:
            return
        self._snip_active = True
        try:
            ov = SnipOverlay(hint_text=self._t("snip_hint"))
            ov.captured.connect(self._on_snip_captured)
            ov.cancelled.connect(self._on_snip_cancelled)
            self._snip_overlay = ov
            ov.start()
        except Exception as exc:
            self._snip_active = False
            self._snip_overlay = None
            self._maybe_restore_window()
            self.status_lbl.setText(f"{self._t('status_error')}: {exc}")

    def _on_snip_cancelled(self) -> None:
        self._snip_active = False
        self._snip_overlay = None
        self._maybe_restore_window()
        self._set_status("status_cancelled")

    def _on_snip_captured(self, image: Image.Image) -> None:
        self._snip_active = False
        self._snip_overlay = None
        self._maybe_restore_window()
        self._run_ocr_async(image)

    def _maybe_restore_window(self) -> None:
        if self._restore_after_snip:
            self._restore_after_snip = False
            self.show_window()

    def _trigger_clipboard_ocr(self) -> None:
        if self._ocr_busy:
            return
        try:
            clip = ImageGrab.grabclipboard()
        except Exception as exc:
            self.status_lbl.setText(f"{self._t('status_error')}: {exc}")
            return

        image: Optional[Image.Image] = None
        if isinstance(clip, Image.Image):
            image = clip
        elif isinstance(clip, list) and clip:
            try:
                image = Image.open(clip[0])
            except Exception:
                image = None

        if image is None:
            self._set_status("status_no_clip_img")
            self.toast.show_result(self._t("status_no_clip_img"), ok=False)
            if self.config.get("play_sound", True):
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return

        self._run_ocr_async(image)

    def _run_ocr_async(self, image: Image.Image) -> None:
        self._ocr_busy = True
        self._set_status("status_processing")
        self.toast.show_loading(self._t("status_processing"))
        fmt = self.config.get("output_format", "markdown")
        active_id = self.config.get("active_model", "ocria-nano")
        custom = self.config.get("custom_models", [])

        def worker() -> None:
            t0 = time.perf_counter()
            try:
                text = ocr_engine.extract_text(
                    image,
                    output_format=fmt,
                    active_model_id=active_id,
                    custom_models=custom,
                )
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                self.bridge.ocr_done.emit(text, elapsed_ms)
            except Exception as exc:
                self.bridge.ocr_error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_ocr_success(self, text: str, elapsed_ms: int) -> None:
        self._ocr_busy = False
        self._last_elapsed_ms = elapsed_ms
        self.timing_lbl.setText(f"{elapsed_ms} ms")

        if text:
            pyperclip.copy(text)
            self.preview_edit.setPlainText(text)
            self._set_status("status_copied")
            self.toast.show_result(self._t("status_copied"), ok=True, sub=f"{elapsed_ms} ms")
            if self.config.get("play_sound", True):
                try:
                    winsound.Beep(1050, 80)
                except RuntimeError:
                    winsound.MessageBeep(winsound.MB_OK)
        else:
            self.preview_edit.clear()
            self._set_status("status_no_text")
            self.toast.show_result(self._t("status_no_text"), ok=False)
            if self.config.get("play_sound", True):
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    def _handle_ocr_error(self, msg: str) -> None:
        self._ocr_busy = False
        self.status_lbl.setText(f"{self._t('status_error')}: {msg}")
        self.toast.show_result(self._t("status_error"), ok=False)

    def _copy_preview(self) -> None:
        content = self.preview_edit.toPlainText().strip()
        if content:
            pyperclip.copy(content)
            self._set_status("status_recopied")
            self.toast.show_result(self._t("status_recopied"), ok=True)

    # --- Tray & Window Lifecycle ---

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.app_icon, self)
        self.tray_menu = QMenu()
        self.tray_menu.setLayoutDirection(self.layoutDirection())
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self._rebuild_tray_menu()
        self.tray.show()

    def _rebuild_tray_menu(self) -> None:
        self.tray_menu.clear()
        self.tray_menu.setLayoutDirection(
            Qt.RightToLeft if self.lang == "fa" else Qt.LeftToRight
        )
        hk = self.config.get("hotkey", "ctrl+alt+c")
        self.tray.setToolTip(f"QuickOCR ({hk})")

        act_snip = QAction(f"{self._t('tray_snip')} ({hk})", self.tray_menu)
        act_snip.triggered.connect(self._open_snip_overlay)
        self.tray_menu.addAction(act_snip)

        act_clip = QAction(self._t("tray_clip"), self.tray_menu)
        act_clip.triggered.connect(self._trigger_clipboard_ocr)
        self.tray_menu.addAction(act_clip)

        self.tray_menu.addSeparator()

        act_open = QAction(self._t("tray_open"), self.tray_menu)
        act_open.triggered.connect(self.show_window)
        self.tray_menu.addAction(act_open)

        act_quit = QAction(self._t("tray_quit"), self.tray_menu)
        act_quit.triggered.connect(self.quit_app)
        self.tray_menu.addAction(act_quit)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self) -> None:
        self._show_group.stop()
        if not self.isVisible():
            self.stack.setCurrentIndex(0)
            self.setWindowOpacity(0.0)
            self.show()
            apply_window_taskbar_identity(self, ICON_PATH, EXE_LAUNCHER)
            target_pos = self.pos()
            self.move(target_pos + QPoint(0, 18))
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._slide_anim.setStartValue(target_pos + QPoint(0, 18))
            self._slide_anim.setEndValue(target_pos)
            self._show_group.start()
        else:
            self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
            apply_window_taskbar_identity(self, ICON_PATH, EXE_LAUNCHER)
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self) -> None:
        self.hide()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide_to_tray()

    def quit_app(self) -> None:
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self._snip_overlay is not None:
            self._snip_overlay.close()
        self.toast.close()
        if hasattr(self, "tray"):
            self.tray.hide()
        if self.ipc_server is not None:
            self.ipc_server.close()
        self.qapp.quit()


def _notify_existing_instance() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(IPC_NAME)
    if sock.waitForConnected(250):
        sock.write(b"SHOW")
        sock.flush()
        sock.waitForBytesWritten(200)
        sock.close()
        return True
    return False


def main() -> None:
    set_app_user_model_id()
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)

    if _notify_existing_instance():
        return

    load_app_fonts(FONTS_DIR)
    base_font = QFont()
    base_font.setFamilies(["Vazirmatn", "Segoe UI", "Microsoft YaHei UI"])
    base_font.setPointSize(10)
    qapp.setFont(base_font)
    qapp.setStyleSheet(APP_QSS)

    ipc_server = QLocalServer()
    if not ipc_server.listen(IPC_NAME):
        QLocalServer.removeServer(IPC_NAME)
        ipc_server.listen(IPC_NAME)

    start_minimized = "--minimized" in sys.argv
    win = QuickOCRWindow(qapp, ipc_server=ipc_server, start_minimized=start_minimized)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
