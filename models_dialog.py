"""Pure-black embedded Model Manager view with animated category filtering and 1-click installs."""

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
    QLayout,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import ocr_engine
from i18n import tr
from ui_kit import (
    APP_QSS,
    C_BG,
    C_BORDER,
    C_DIM,
    C_MUTED,
    C_OK,
    C_SURFACE,
    C_TEXT,
    AnimatedButton,
    AnimatedSegmented,
    apply_window_taskbar_identity,
)

FORM_QSS = f"""
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
QFrame#StatusBox {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
}}
QProgressBar#ModelProgress {{
    background-color: #1F1F23;
    border: none;
    border-radius: 3px;
}}
QProgressBar#ModelProgress::chunk {{
    background-color: #FAFAFA;
    border-radius: 3px;
}}
"""


class _WorkerSignals(QObject):
    finished = Signal(bool, str)
    progress = Signal(int, str)
    detected = Signal(list, str)


class ModelsView(QWidget):
    """Embedded Model Manager page with 1-click download, language tiers, and Vision APIs."""

    def __init__(
        self,
        lang: str,
        active_model_id: str,
        custom_models: List[Dict[str, Any]],
        on_models_changed: Callable[[str, List[Dict[str, Any]]], None],
        on_back: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.lang = lang
        self.active_model_id = active_model_id
        self.custom_models = [dict(m) for m in custom_models]
        self.on_models_changed = on_models_changed
        self.on_back = on_back
        self._category = "recommended"
        self._busy = False

        self.signals = _WorkerSignals()
        self.signals.finished.connect(self._on_task_done)
        self.signals.progress.connect(self._on_progress)
        self.signals.detected.connect(self._on_models_detected)

        self.setObjectName("ModelsPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            APP_QSS
            + FORM_QSS
            + f"\nQWidget#ModelsPage, QWidget#ModelsScrollBody {{ background-color: {C_BG}; color: {C_TEXT}; }}\n"
        )
        self._build_ui()
        self._rebuild_list()

    def _t(self, key: str) -> str:
        return tr(self.lang, key)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # Header with smooth Back button
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        self.back_btn = AnimatedButton(
            self._t("btn_back"), variant="secondary", radius=9, height=30, padx=12
        )
        self.back_btn.clicked.connect(lambda: self.on_back() if self.on_back else None)
        if self.on_back is None:
            self.back_btn.hide()
        hdr.addWidget(self.back_btn)

        self.title_lbl = QLabel(self._t("models_title"))
        tf = QFont(self.font())
        tf.setPointSize(12)
        tf.setWeight(QFont.Bold)
        self.title_lbl.setFont(tf)
        self.title_lbl.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        hdr.addWidget(self.title_lbl)
        hdr.addStretch(1)

        self.import_btn = AnimatedButton(
            self._t("btn_import_dir"), variant="ghost", radius=9, height=28, padx=10
        )
        self.import_btn.clicked.connect(self._on_import_dir)
        hdr.addWidget(self.import_btn)
        root.addLayout(hdr)

        # Animated category filter bar
        self.cat_seg = AnimatedSegmented(
            options=(
                ("recommended", self._t("tab_rec")),
                ("all", self._t("tab_all")),
                ("fast", self._t("tab_fast")),
                ("heavy", self._t("tab_heavy")),
                ("api", self._t("tab_api")),
            ),
            initial="recommended",
            on_change=self._on_category_change,
            height=30,
            min_seg_width=54,
        )
        root.addWidget(self.cat_seg)

        # Scrollable list with opaque black viewport (prevents scroll ghosting)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignTop)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(True)
        scroll.viewport().setStyleSheet(f"background-color: {C_BG};")
        root.addWidget(scroll, 1)

        container = QWidget()
        container.setObjectName("ModelsScrollBody")
        container.setAutoFillBackground(True)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        scroll.setWidget(container)
        self.scroll_col = QVBoxLayout(container)
        self.scroll_col.setContentsMargins(12, 2, 12, 6)
        self.scroll_col.setSpacing(10)
        self.scroll_col.setSizeConstraint(QLayout.SetMinimumSize)

        self.sec1_lbl = QLabel(self._t("models_local_sec"))
        self.sec1_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        self.scroll_col.addWidget(self.sec1_lbl)

        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(8)
        self.scroll_col.addLayout(self.cards_layout)

        # Custom Vision LLM / Server form card
        self.sec2_lbl = QLabel(self._t("models_custom_sec"))
        self.sec2_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 8.5pt; padding-top: 4px; background: transparent;"
        )
        self.scroll_col.addWidget(self.sec2_lbl)

        self.custom_card = QFrame()
        self.custom_card.setObjectName("Card")
        self.custom_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        cc = QVBoxLayout(self.custom_card)
        cc.setSizeConstraint(QLayout.SetMinimumSize)
        cc.setContentsMargins(14, 12, 14, 12)
        cc.setSpacing(8)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        self.preset_lbl = QLabel(self._t("lbl_preset_srv"))
        self.preset_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 8.5pt; background: transparent;")
        presets_row.addWidget(self.preset_lbl)
        for name, url in (
            ("LM Studio", "http://localhost:1234/v1"),
            ("Ollama", "http://localhost:11434/v1"),
        ):
            pb = AnimatedButton(name, variant="ghost", radius=8, height=24, padx=10)
            pb.clicked.connect(lambda _=False, u=url: self.url_edit.setText(u))
            presets_row.addWidget(pb)
        presets_row.addStretch(1)
        cc.addLayout(presets_row)

        self.url_lbl = QLabel(self._t("lbl_endpoint"))
        self.url_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        cc.addWidget(self.url_lbl)

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

        self.model_lbl = QLabel(self._t("lbl_model_name"))
        self.model_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        cc.addWidget(self.model_lbl)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setLayoutDirection(Qt.LeftToRight)
        self.model_combo.setEditText("qwen2.5-vl")
        cc.addWidget(self.model_combo)

        for chip_pair in (
            ("qwen2.5-vl", "deepseek-ocr"),
            ("MedAIBase/PaddleOCR-VL", "richardyoung/olmocr2:7b-q8"),
        ):
            vlm_row = QHBoxLayout()
            vlm_row.setSpacing(6)
            for mname in chip_pair:
                chip = AnimatedButton(mname, variant="ghost", radius=7, height=22, padx=8)
                chip.setLayoutDirection(Qt.LeftToRight)
                chip.clicked.connect(
                    lambda _=False, n=mname: self.model_combo.setEditText(n)
                )
                vlm_row.addWidget(chip)
            vlm_row.addStretch(1)
            cc.addLayout(vlm_row)

        self.key_lbl = QLabel(self._t("lbl_api_key"))
        self.key_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        cc.addWidget(self.key_lbl)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setLayoutDirection(Qt.LeftToRight)
        self.key_edit.setPlaceholderText("sk-...")
        cc.addWidget(self.key_edit)

        self.add_custom_btn = AnimatedButton(
            self._t("btn_add_custom"), variant="primary", radius=10, height=34, padx=16
        )
        self.add_custom_btn.clicked.connect(self._on_add_custom)
        cc.addWidget(self.add_custom_btn)

        self.scroll_col.addWidget(self.custom_card)
        self.scroll_col.addStretch(1)

        # Dedicated status & progress footer (prevents overlap on cards)
        self.status_frame = QFrame()
        self.status_frame.setObjectName("StatusBox")
        sf_col = QVBoxLayout(self.status_frame)
        sf_col.setContentsMargins(12, 8, 12, 8)
        sf_col.setSpacing(6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("ModelProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.hide()
        sf_col.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 8.5pt; background: transparent;")
        self.status_lbl.setWordWrap(True)
        sf_col.addWidget(self.status_lbl)
        self.status_frame.hide()
        root.addWidget(self.status_frame)

    def refresh_language(self, lang: str) -> None:
        self.lang = lang
        self.setLayoutDirection(Qt.RightToLeft if lang == "fa" else Qt.LeftToRight)
        self.back_btn.setText(self._t("btn_back"))
        self.title_lbl.setText(self._t("models_title"))
        self.import_btn.setText(self._t("btn_import_dir"))
        self.cat_seg.update_labels(
            [
                self._t("tab_rec"),
                self._t("tab_all"),
                self._t("tab_fast"),
                self._t("tab_heavy"),
                self._t("tab_api"),
            ]
        )
        self.sec1_lbl.setText(self._t("models_local_sec"))
        self.sec2_lbl.setText(self._t("models_custom_sec"))
        self.preset_lbl.setText(self._t("lbl_preset_srv"))
        self.url_lbl.setText(self._t("lbl_endpoint"))
        self.detect_btn.setText(self._t("btn_detect"))
        self.model_lbl.setText(self._t("lbl_model_name"))
        self.key_lbl.setText(self._t("lbl_api_key"))
        self.add_custom_btn.setText(self._t("btn_add_custom"))
        self._rebuild_list()

    def _on_category_change(self, cat: str) -> None:
        self._category = cat
        self._rebuild_list()

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _rebuild_list(self) -> None:
        self._clear_cards()
        show_local = self._category in ("recommended", "all", "fast", "heavy")
        show_custom = self._category in ("all", "api")

        self.sec1_lbl.setVisible(show_local or (show_custom and len(self.custom_models) > 0))
        self.sec2_lbl.setVisible(show_custom)
        self.custom_card.setVisible(show_custom)

        if show_local:
            for spec in ocr_engine.MODEL_CATALOG:
                if self._category == "recommended":
                    if not spec.get("recommended"):
                        continue
                elif self._category != "all" and spec["category"] != self._category:
                    continue
                mid = spec["id"]
                installed = ocr_engine.is_model_installed(mid)
                title = spec["title"]
                if mid == "ocria-nano":
                    ok, ver_info = ocr_engine.is_ocria_installed()
                    if ok:
                        title = f"{title} ({ver_info})"
                entry = {
                    "id": mid,
                    "title": title,
                    "desc": self._t(spec["desc_key"]),
                    "langs": spec["langs"],
                    "badge": spec["badge"],
                    "recommended": bool(spec.get("recommended")),
                    "installed": installed,
                    "can_download": True,
                    "can_remove": installed,
                }
                self.cards_layout.addWidget(self._make_model_card(entry, is_custom=False))

        if show_custom:
            for cm in self.custom_models:
                entry = {
                    "id": cm["id"],
                    "title": cm.get("name") or cm["model_name"],
                    "desc": f"{cm['base_url']}  •  {cm['model_name']}",
                    "langs": "Vision LLM",
                    "badge": "API",
                    "installed": True,
                    "can_download": False,
                    "can_remove": True,
                }
                self.cards_layout.addWidget(self._make_model_card(entry, is_custom=True))

    def _make_model_card(self, entry: Dict[str, Any], is_custom: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        col = QVBoxLayout(card)
        col.setSizeConstraint(QLayout.SetMinimumSize)
        col.setContentsMargins(12, 10, 12, 10)
        col.setSpacing(6)

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
        col.addLayout(top_line)

        meta_line = QHBoxLayout()
        meta_line.setSpacing(6)
        if entry.get("recommended"):
            rec_pill = QLabel(f"★ {self._t('badge_rec')}")
            rec_pill.setStyleSheet(
                "background: #1B180E; color: #FACC15; border: 1px solid #3D3514; "
                "border-radius: 5px; padding: 1px 6px; font-size: 7.5pt;"
            )
            meta_line.addWidget(rec_pill)
        for tag_text in (entry["langs"], entry["badge"]):
            pill = QLabel(tag_text)
            pill.setLayoutDirection(Qt.LeftToRight)
            pill.setStyleSheet(
                f"background: #141417; color: {C_MUTED}; border: 1px solid #232327; "
                "border-radius: 5px; padding: 1px 6px; font-family: Consolas; font-size: 7.5pt;"
            )
            meta_line.addWidget(pill)
        meta_line.addStretch(1)
        col.addLayout(meta_line)

        desc_lbl = QLabel(entry["desc"])
        desc_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 8pt; background: transparent;")
        desc_lbl.setWordWrap(True)
        col.addWidget(desc_lbl)

        mid = entry["id"]
        action_btns: List[AnimatedButton] = []
        if entry["installed"] and not is_active:
            sel_btn = AnimatedButton(
                self._t("btn_select"), variant="primary", radius=8, height=28, padx=12
            )
            sel_btn.clicked.connect(lambda _=False, m=mid: self._select_model(m))
            action_btns.append(sel_btn)
        elif not entry["installed"] and entry["can_download"]:
            dl_btn = AnimatedButton(
                self._t("btn_download"), variant="secondary", radius=8, height=28, padx=12
            )
            dl_btn.setEnabled(not self._busy)
            dl_btn.clicked.connect(lambda _=False, m=mid: self._download_model(m))
            action_btns.append(dl_btn)

        if entry["can_remove"] and (is_custom or mid != "ocria-nano" or not is_active):
            rm_btn = AnimatedButton(
                self._t("btn_remove"), variant="danger", radius=8, height=28, padx=10
            )
            rm_btn.setEnabled(not self._busy)
            rm_btn.clicked.connect(
                lambda _=False, m=mid, c=is_custom: self._remove_model(m, c)
            )
            action_btns.append(rm_btn)

        if action_btns:
            act_line = QHBoxLayout()
            act_line.setSpacing(6)
            for btn in action_btns:
                act_line.addWidget(btn)
            act_line.addStretch(1)
            col.addLayout(act_line)

        return card

    def _emit_change(self) -> None:
        self.on_models_changed(self.active_model_id, self.custom_models)
        self._rebuild_list()

    def _select_model(self, model_id: str) -> None:
        self.active_model_id = model_id
        self._emit_change()

    def _set_status_msg(self, text: str, show_progress: bool = False, pct: int = 0) -> None:
        self.status_lbl.setText(text)
        if show_progress:
            self.progress_bar.setValue(max(0, min(100, pct)))
            self.progress_bar.show()
        else:
            self.progress_bar.hide()
        self.status_frame.setVisible(bool(text) or show_progress)

    def _on_progress(self, pct: int, detail: str) -> None:
        if not self._busy:
            return
        label = f"{pct}%  •  {detail}" if detail else f"{pct}%"
        self._set_status_msg(label, show_progress=True, pct=pct)

    def _download_model(self, model_id: str) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status_msg(f"0%  •  {self._t('msg_downloading')}", show_progress=True, pct=0)
        self._rebuild_list()

        def worker() -> None:
            try:
                ocr_engine.install_model(
                    model_id,
                    on_progress=lambda p, m: self.signals.progress.emit(p, m),
                )
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
                ocr_engine.remove_model(model_id)
                self.signals.finished.emit(True, f"removed:{model_id}")
            except Exception as exc:
                self.signals.finished.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_import_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._t("btn_import_dir"))
        if not folder or self._busy:
            return
        self._busy = True
        self._set_status_msg(f"0%  •  {self._t('msg_downloading')}", show_progress=True, pct=0)

        def worker() -> None:
            try:
                ocr_engine.pull_model(
                    from_dir=folder,
                    on_progress=lambda p, m: self.signals.progress.emit(p, m),
                )
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
                self._set_status_msg("", show_progress=False)
            else:
                self.active_model_id = info
                self._set_status_msg(self._t("msg_install_ready"), show_progress=False)
            self._emit_change()
        else:
            self._set_status_msg(info, show_progress=False)
            self._rebuild_list()

    def _on_detect_models(self) -> None:
        url = self.url_edit.text().strip()
        key = self.key_edit.text().strip()
        if not url:
            return
        self.detect_btn.setEnabled(False)
        self._set_status_msg(self._t("msg_detecting"))

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
            self._set_status_msg(err)
            return
        if not found:
            self._set_status_msg(self._t("msg_no_models_found"))
            return
        self.model_combo.clear()
        self.model_combo.addItems(found)
        self._set_status_msg(f"{len(found)} model(s) detected")

    def _on_add_custom(self) -> None:
        url = self.url_edit.text().strip()
        model_name = self.model_combo.currentText().strip()
        api_key = self.key_edit.text().strip()
        if not url or not model_name:
            self._set_status_msg(self._t("msg_enter_url_model"))
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
        self._set_status_msg("")
        self._emit_change()


class ModelsDialog(QDialog):
    """Standalone dialog wrapper around ModelsView."""

    def __init__(
        self,
        lang: str,
        active_model_id: str,
        custom_models: List[Dict[str, Any]],
        on_models_changed: Callable[[str, List[Dict[str, Any]]], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MainRoot")
        self.setWindowTitle(tr(lang, "models_title"))
        self.setLayoutDirection(Qt.RightToLeft if lang == "fa" else Qt.LeftToRight)
        self.setStyleSheet(APP_QSS + FORM_QSS)
        self.resize(520, 620)
        apply_window_taskbar_identity(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = ModelsView(lang, active_model_id, custom_models, on_models_changed, parent=self)
        lay.addWidget(self.view)
