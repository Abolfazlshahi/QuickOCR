"""Pure-black minimal Model Manager dialog for switching, downloading, and adding OCR models."""

from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import ocr_engine
from i18n import tr
from ui_kit import (
    APP_QSS,
    C_BG,
    C_BORDER,
    C_CARD,
    C_DIM,
    C_MUTED,
    C_OK,
    C_SURFACE,
    C_TEXT,
    AnimatedButton,
    enable_dark_window,
)

DIALOG_QSS = f"""
QDialog#ModelsDlg {{
    background-color: {C_BG};
    color: {C_TEXT};
}}
QComboBox {{
    background-color: {C_SURFACE};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 5px 12px;
    min-height: 22px;
}}
QComboBox:focus {{
    border: 1px solid #52525B;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: #101012;
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    selection-background-color: #27272A;
}}
QLineEdit {{
    background-color: {C_SURFACE};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 6px 12px;
}}
QLineEdit:focus {{
    border: 1px solid #52525B;
}}
"""


class _WorkerSignals(QObject):
    finished = Signal(bool, str)
    detected = Signal(list, str)


class ModelsDialog(QDialog):
    """Modal dialog to switch, download, remove, or add OCR & Vision LLM models."""

    def __init__(
        self,
        lang: str,
        active_model_id: str,
        custom_models: List[Dict[str, Any]],
        on_models_changed: Callable[[str, List[Dict[str, Any]]], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.lang = lang
        self.active_model_id = active_model_id
        self.custom_models = [dict(m) for m in custom_models]
        self.on_models_changed = on_models_changed
        self._busy = False

        self.signals = _WorkerSignals()
        self.signals.finished.connect(self._on_task_done)
        self.signals.detected.connect(self._on_models_detected)

        self.setObjectName("ModelsDlg")
        self.setWindowTitle(self._t("models_title"))
        self.setLayoutDirection(Qt.RightToLeft if lang == "fa" else Qt.LeftToRight)
        self.setStyleSheet(APP_QSS + DIALOG_QSS)
        self.resize(500, 580)
        self.setMinimumSize(420, 480)
        enable_dark_window(self)

        self._build_ui()
        self._rebuild_list()

    def _t(self, key: str) -> str:
        return tr(self.lang, key)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel(self._t("models_title"))
        tf = QFont(self.font())
        tf.setPointSize(12)
        tf.setWeight(QFont.Bold)
        title.setFont(tf)
        title.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch(1)

        import_btn = AnimatedButton(
            self._t("btn_import_dir"), variant="secondary", radius=9, height=28, padx=10
        )
        import_btn.clicked.connect(self._on_import_dir)
        hdr.addWidget(import_btn)
        root.addLayout(hdr)

        # Scrollable model list
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll, 1)

        container = QWidget()
        container.setObjectName("MainRoot")
        scroll.setWidget(container)
        self.scroll_col = QVBoxLayout(container)
        self.scroll_col.setContentsMargins(0, 0, 0, 0)
        self.scroll_col.setSpacing(10)

        sec1 = QLabel(self._t("models_local_sec"))
        sec1.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        self.scroll_col.addWidget(sec1)

        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(8)
        self.scroll_col.addLayout(self.cards_layout)

        # Custom Vision LLM / Server form card
        sec2 = QLabel(self._t("models_custom_sec"))
        sec2.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; padding-top: 4px; background: transparent;")
        self.scroll_col.addWidget(sec2)

        custom_card = QFrame()
        custom_card.setObjectName("Card")
        cc = QVBoxLayout(custom_card)
        cc.setContentsMargins(14, 12, 14, 12)
        cc.setSpacing(8)

        # Server presets
        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        pl = QLabel(self._t("lbl_preset_srv"))
        pl.setStyleSheet(f"color: {C_DIM}; font-size: 8.5pt; background: transparent;")
        presets_row.addWidget(pl)
        for name, url in (("LM Studio", "http://localhost:1234/v1"), ("Ollama", "http://localhost:11434/v1")):
            pb = AnimatedButton(name, variant="ghost", radius=8, height=24, padx=10)
            pb.clicked.connect(lambda _=False, u=url: self.url_edit.setText(u))
            presets_row.addWidget(pb)
        presets_row.addStretch(1)
        cc.addLayout(presets_row)

        # Endpoint URL + Detect
        u_lbl = QLabel(self._t("lbl_endpoint"))
        u_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        cc.addWidget(u_lbl)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_edit = QLineEdit("http://localhost:1234/v1")
        self.url_edit.setLayoutDirection(Qt.LeftToRight)
        url_row.addWidget(self.url_edit, 1)

        self.detect_btn = AnimatedButton(
            self._t("btn_detect"), variant="secondary", radius=9, height=32, padx=12
        )
        self.detect_btn.clicked.connect(self._on_detect_models)
        url_row.addWidget(self.detect_btn)
        cc.addLayout(url_row)

        # Model Name (editable combo)
        m_lbl = QLabel(self._t("lbl_model_name"))
        m_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        cc.addWidget(m_lbl)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setLayoutDirection(Qt.LeftToRight)
        self.model_combo.setEditText("qwen2.5-vl")
        cc.addWidget(self.model_combo)

        # Optional API Key
        k_lbl = QLabel(self._t("lbl_api_key"))
        k_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        cc.addWidget(k_lbl)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setLayoutDirection(Qt.LeftToRight)
        self.key_edit.setPlaceholderText("sk-...")
        cc.addWidget(self.key_edit)

        add_btn = AnimatedButton(
            self._t("btn_add_custom"), variant="primary", radius=10, height=34, padx=16
        )
        add_btn.clicked.connect(self._on_add_custom)
        cc.addWidget(add_btn)

        self.scroll_col.addWidget(custom_card)
        self.scroll_col.addStretch(1)

        # Bottom status + close
        foot = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        foot.addWidget(self.status_lbl, 1)

        close_btn = AnimatedButton(
            self._t("btn_close"), variant="secondary", radius=10, height=32, padx=16
        )
        close_btn.clicked.connect(self.accept)
        foot.addWidget(close_btn)
        root.addLayout(foot)

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _rebuild_list(self) -> None:
        self._clear_cards()

        ocria_ok, ocria_info = ocr_engine.is_ocria_installed()
        rapid_ok = ocr_engine.is_rapidocr_installed()
        tess_ok = ocr_engine.is_tesseract_installed()

        builtins = [
            {
                "id": "ocria-nano",
                "title": f"OCRia-nano-1 ({ocria_info})" if ocria_ok else "OCRia-nano-1",
                "desc": self._t("model_desc_ocria"),
                "installed": ocria_ok,
                "can_download": True,
                "can_remove": ocria_ok,
            },
            {
                "id": "rapidocr",
                "title": "RapidOCR (PaddleOCR ONNX)",
                "desc": self._t("model_desc_rapid"),
                "installed": rapid_ok,
                "can_download": True,
                "can_remove": rapid_ok,
            },
            {
                "id": "tesseract",
                "title": "Tesseract OCR",
                "desc": self._t("model_desc_tess"),
                "installed": tess_ok,
                "can_download": False,
                "can_remove": False,
            },
        ]

        for entry in builtins:
            self.cards_layout.addWidget(self._make_model_card(entry, is_custom=False))

        for cm in self.custom_models:
            entry = {
                "id": cm["id"],
                "title": cm.get("name") or cm["model_name"],
                "desc": f"{cm['base_url']}  •  {cm['model_name']}",
                "installed": True,
                "can_download": False,
                "can_remove": True,
            }
            self.cards_layout.addWidget(self._make_model_card(entry, is_custom=True))

    def _make_model_card(self, entry: Dict[str, Any], is_custom: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        top_line = QHBoxLayout()
        top_line.setSpacing(6)
        name_lbl = QLabel(entry["title"])
        name_lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; background: transparent;")
        top_line.addWidget(name_lbl)

        is_active = entry["id"] == self.active_model_id
        if is_active:
            badge_txt = self._t("model_active")
            badge_style = (
                f"background: #102A1A; color: {C_OK}; border: 1px solid #1E462C; "
                "border-radius: 6px; padding: 1px 6px; font-size: 7.5pt;"
            )
        elif entry["installed"]:
            badge_txt = self._t("model_installed")
            badge_style = (
                f"background: {C_SURFACE}; color: {C_MUTED}; border: 1px solid {C_BORDER}; "
                "border-radius: 6px; padding: 1px 6px; font-size: 7.5pt;"
            )
        else:
            badge_txt = self._t("model_not_installed")
            badge_style = (
                f"background: {C_SURFACE}; color: {C_DIM}; border: 1px solid {C_BORDER}; "
                "border-radius: 6px; padding: 1px 6px; font-size: 7.5pt;"
            )

        badge = QLabel(badge_txt)
        badge.setStyleSheet(badge_style)
        top_line.addWidget(badge)
        top_line.addStretch(1)
        info_col.addLayout(top_line)

        desc_lbl = QLabel(entry["desc"])
        desc_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 8pt; background: transparent;")
        desc_lbl.setWordWrap(True)
        info_col.addWidget(desc_lbl)
        row.addLayout(info_col, 1)

        mid = entry["id"]
        if entry["installed"] and not is_active:
            sel_btn = AnimatedButton(
                self._t("btn_select"), variant="primary", radius=8, height=28, padx=12
            )
            sel_btn.clicked.connect(lambda _=False, m=mid: self._select_model(m))
            row.addWidget(sel_btn)
        elif not entry["installed"] and entry["can_download"]:
            dl_btn = AnimatedButton(
                self._t("btn_download"), variant="secondary", radius=8, height=28, padx=12
            )
            dl_btn.setEnabled(not self._busy)
            dl_btn.clicked.connect(lambda _=False, m=mid: self._download_model(m))
            row.addWidget(dl_btn)

        if entry["can_remove"] and (is_custom or mid != "ocria-nano" or not is_active):
            rm_btn = AnimatedButton(
                self._t("btn_remove"), variant="danger", radius=8, height=28, padx=10
            )
            rm_btn.setEnabled(not self._busy)
            rm_btn.clicked.connect(
                lambda _=False, m=mid, c=is_custom: self._remove_model(m, c)
            )
            row.addWidget(rm_btn)

        return card

    def _emit_change(self) -> None:
        self.on_models_changed(self.active_model_id, self.custom_models)
        self._rebuild_list()

    def _select_model(self, model_id: str) -> None:
        self.active_model_id = model_id
        self._emit_change()

    def _download_model(self, model_id: str) -> None:
        if self._busy:
            return
        self._busy = True
        self.status_lbl.setText(self._t("msg_downloading"))
        self._rebuild_list()

        def worker() -> None:
            try:
                if model_id == "ocria-nano":
                    ocr_engine.pull_model()
                elif model_id == "rapidocr":
                    ocr_engine.install_rapidocr()
                self.signals.finished.emit(True, model_id)
            except Exception as exc:
                self.signals.finished.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _remove_model(self, model_id: str, is_custom: bool) -> None:
        if is_custom:
            self.custom_models = [m for m in self.custom_models if m["id"] != model_id]
            if self.active_model_id == model_id:
                self.active_model_id = "ocria-nano"
            self._emit_change()
            return

        if self._busy:
            return
        self._busy = True
        self._rebuild_list()

        def worker() -> None:
            try:
                if model_id == "ocria-nano":
                    ocr_engine.remove_ocria_nano()
                elif model_id == "rapidocr":
                    ocr_engine.remove_rapidocr()
                self.signals.finished.emit(True, f"removed:{model_id}")
            except Exception as exc:
                self.signals.finished.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_import_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._t("btn_import_dir"))
        if not folder or self._busy:
            return
        self._busy = True
        self.status_lbl.setText(self._t("msg_downloading"))

        def worker() -> None:
            try:
                ocr_engine.pull_model(from_dir=folder)
                self.signals.finished.emit(True, "ocria-nano")
            except Exception as exc:
                self.signals.finished.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_task_done(self, ok: bool, info: str) -> None:
        self._busy = False
        if ok:
            if info.startswith("removed:"):
                removed_id = info.split(":", 1)[1]
                if self.active_model_id == removed_id:
                    self.active_model_id = "ocria-nano"
                self.status_lbl.setText("")
            else:
                self.active_model_id = info
                self.status_lbl.setText("")
            self._emit_change()
        else:
            self.status_lbl.setText(info)
            self._rebuild_list()

    def _on_detect_models(self) -> None:
        url = self.url_edit.text().strip()
        key = self.key_edit.text().strip()
        if not url:
            return
        self.detect_btn.setEnabled(False)
        self.status_lbl.setText(self._t("msg_detecting"))

        def worker() -> None:
            try:
                found = ocr_engine.fetch_remote_models(url, key)
                self.signals.detected.emit(found, "")
            except Exception as exc:
                self.signals.detected.emit([], str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_models_detected(self, found: list, err: str) -> None:
        self.detect_btn.setEnabled(True)
        if err:
            self.status_lbl.setText(err)
            return
        if not found:
            self.status_lbl.setText(self._t("msg_no_models_found"))
            return
        self.model_combo.clear()
        self.model_combo.addItems(found)
        self.status_lbl.setText(f"{len(found)} model(s) detected")

    def _on_add_custom(self) -> None:
        url = self.url_edit.text().strip()
        model_name = self.model_combo.currentText().strip()
        api_key = self.key_edit.text().strip()
        if not url or not model_name:
            self.status_lbl.setText(self._t("msg_enter_url_model"))
            return
        new_id = f"custom_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": new_id,
            "name": model_name,
            "kind": "openai_vision",
            "base_url": url,
            "model_name": model_name,
            "api_key": api_key,
        }
        self.custom_models.append(entry)
        self.active_model_id = new_id
        self.status_lbl.setText("")
        self._emit_change()
