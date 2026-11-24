"""Minimal pure-black rounded PySide6 components and 60fps animations."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Property,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

# Pure black monochrome palette (OLED / Swiss minimalism)
C_BG = "#000000"
C_CARD = "#0C0C0C"
C_SURFACE = "#161616"
C_SURFACE_HOVER = "#232323"
C_BORDER = "#242426"
C_BORDER_FOCUS = "#52525B"
C_ACCENT = "#FAFAFA"
C_ACCENT_HOVER = "#E4E4E7"
C_ON_ACCENT = "#000000"
C_TEXT = "#FAFAFA"
C_MUTED = "#A1A1AA"
C_DIM = "#71717A"
C_OK = "#22C55E"
C_WARN = "#F59E0B"
C_DANGER_BG = "#160D0D"
C_DANGER_HOVER = "#241414"
C_DANGER_FG = "#F87171"
C_DANGER_BORDER = "#3B1B1B"

APP_QSS = f"""
QWidget#MainRoot {{
    background-color: {C_BG};
    color: {C_TEXT};
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: #27272A;
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3F3F46;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0px;
}}
QFrame#Card {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 14px;
}}
QFrame#Divider {{
    background-color: #1A1A1C;
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
QLineEdit#HotkeyEdit {{
    background-color: {C_SURFACE};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 5px 12px;
    font-family: "Consolas";
    font-size: 10pt;
    selection-background-color: #3F3F46;
}}
QLineEdit#HotkeyEdit:focus {{
    border: 1px solid {C_BORDER_FOCUS};
}}
QTextEdit#PreviewEdit {{
    background-color: #080808;
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: #27272A;
}}
QMenu {{
    background-color: #0E0E10;
    color: {C_TEXT};
    border: 1px solid #2A2A2E;
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 16px;
    border-radius: 7px;
}}
QMenu::item:selected {{
    background-color: #202024;
}}
QMenu::separator {{
    height: 1px;
    background: #222226;
    margin: 4px 8px;
}}
"""


def load_app_fonts(fonts_dir: Path) -> str:
    """Register bundled Vazirmatn TTF weights and return primary family name."""
    loaded_family = "Vazirmatn"
    if fonts_dir.exists():
        for ttf in sorted(fonts_dir.glob("*.ttf")):
            fid = QFontDatabase.addApplicationFont(str(ttf))
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    loaded_family = fams[0]
    return loaded_family


def enable_dark_window(win: QWidget) -> None:
    """Apply pure black Windows 11 titlebar, rounded corners, and hairline border."""
    try:
        hwnd = int(win.winId())
        for attr, val in (
            (20, 1),           # DWMWA_USE_IMMERSIVE_DARK_MODE
            (33, 2),           # DWMWA_WINDOW_CORNER_PREFERENCE = DWMWCP_ROUND
            (34, 0x00242424),  # DWMWA_BORDER_COLOR
            (35, 0x00000000),  # DWMWA_CAPTION_COLOR = pure black
        ):
            cval = ctypes.c_int(val)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(cval), ctypes.sizeof(cval)
            )
    except Exception:
        pass


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


class AnimatedButton(QPushButton):
    """Vector anti-aliased rounded button with 60fps hover easing and crisp borders."""

    def __init__(
        self,
        text: str,
        variant: str = "secondary",
        radius: int = 10,
        height: int = 36,
        padx: int = 16,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        palettes = {
            "primary": (C_ACCENT, C_ACCENT_HOVER, C_ON_ACCENT, C_ACCENT),
            "secondary": (C_SURFACE, C_SURFACE_HOVER, C_TEXT, C_BORDER),
            "ghost": (C_CARD, C_SURFACE, C_MUTED, "transparent"),
            "danger": (C_DANGER_BG, C_DANGER_HOVER, C_DANGER_FG, C_DANGER_BORDER),
        }
        bg, hover, fg, border = palettes[variant]
        self._bg_idle = QColor(bg)
        self._bg_hover = QColor(hover)
        self._fg = QColor(fg)
        self._border = QColor(0, 0, 0, 0) if border == "transparent" else QColor(border)
        self._radius = radius
        self._padx = padx
        self._fixed_h = height
        self._hover_t = 0.0
        self._pressed = False

        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)

        self._anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    @Property(float)
    def hoverProgress(self) -> float:
        return self._hover_t

    @hoverProgress.setter
    def hoverProgress(self, val: float) -> None:
        self._hover_t = val
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        w = fm.horizontalAdvance(self.text()) + self._padx * 2
        return QSize(max(48, w), self._fixed_h)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def setText(self, text: str) -> None:
        super().setText(text)
        self.updateGeometry()
        self.update()

    def enterEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover_t)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover_t)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        fill = _lerp_color(self._bg_idle, self._bg_hover, self._hover_t)
        if not self.isEnabled():
            fill = QColor(C_SURFACE)
        elif self._pressed:
            fill = _lerp_color(fill, QColor("#000000"), 0.14)

        p.setBrush(fill)
        if self._border.alpha() > 0:
            p.setPen(QPen(self._border, 1.0))
        else:
            p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, self._radius, self._radius)

        fg = self._fg if self.isEnabled() else QColor(C_DIM)
        p.setPen(fg)
        p.setFont(self.font())
        text_rect = QRectF(0, 1 if self._pressed else 0, self.width(), self.height())
        p.drawText(text_rect, Qt.AlignCenter, self.text())


class AnimatedToggle(QAbstractButton):
    """Smooth 60fps monochrome pill toggle switch."""

    def __init__(self, checked: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(42, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0

        self._anim = QPropertyAnimation(self, b"thumbPos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._on_toggled)

    @Property(float)
    def thumbPos(self) -> float:
        return self._pos

    @thumbPos.setter
    def thumbPos(self, val: float) -> None:
        self._pos = val
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setCheckedSilent(self, checked: bool) -> None:
        self.blockSignals(True)
        self.setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self.update()
        self.blockSignals(False)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        track_color = _lerp_color(QColor("#27272A"), QColor(C_ACCENT), self._pos)
        knob_color = _lerp_color(QColor("#71717A"), QColor(C_ON_ACCENT), self._pos)

        p.setPen(Qt.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(QRectF(0, 1, 42, 22), 11, 11)

        kx = 3.0 + self._pos * 18.0
        p.setBrush(knob_color)
        p.drawEllipse(QRectF(kx, 4.0, 16.0, 16.0))


class ToggleRow(QWidget):
    """Responsive label + AnimatedToggle row adapting cleanly to RTL and LTR."""

    def __init__(
        self,
        label_text: str,
        checked: bool,
        on_change: Callable[[bool], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(12)

        self.label = QLabel(label_text, self)
        self.label.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        self.label.setCursor(Qt.PointingHandCursor)

        self.toggle = AnimatedToggle(checked, self)
        self.toggle.toggled.connect(on_change)

        layout.addWidget(self.label, 1)
        layout.addWidget(self.toggle, 0)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.toggle.toggle()
        super().mousePressEvent(event)

    def setText(self, text: str) -> None:
        self.label.setText(text)


class AnimatedSegmented(QWidget):
    """Multi-option rounded pill selector with sliding white indicator."""

    def __init__(
        self,
        options: Sequence[Tuple[str, str]],
        initial: str,
        on_change: Callable[[str], None],
        height: int = 32,
        min_seg_width: int = 64,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._items = list(options)
        self._on_change = on_change
        self._height = height
        self._min_seg_w = min_seg_width
        self._idx = next((i for i, (v, _) in enumerate(self._items) if v == initial), 0)
        self._pos = float(self._idx)

        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self._anim = QPropertyAnimation(self, b"pillPos", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    @Property(float)
    def pillPos(self) -> float:
        return self._pos

    @pillPos.setter
    def pillPos(self, val: float) -> None:
        self._pos = val
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        max_lbl = max((fm.horizontalAdvance(lbl) for _, lbl in self._items), default=40)
        seg_w = max(self._min_seg_w, max_lbl + 22)
        return QSize(seg_w * len(self._items) + 6, self._height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def update_labels(self, labels: Sequence[str]) -> None:
        self._items = [(val, lbl) for (val, _), lbl in zip(self._items, labels)]
        self.updateGeometry()
        self.update()

    def _sync_pos_immediately(self) -> None:
        self._pos = float(self._idx)
        self.update()

    def set_value(self, value: str) -> None:
        for i, (v, _) in enumerate(self._items):
            if v == value:
                self._anim.stop()
                self._idx = i
                self._pos = float(i)
                self.update()
                break

    def changeEvent(self, event) -> None:
        if event.type() == event.Type.LayoutDirectionChange:
            self.update()
        super().changeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or not self._items:
            return
        n = len(self._items)
        seg_w = max(1.0, (self.width() - 6) / n)
        vis_idx = min(n - 1, max(0, int((event.position().x() - 3) // seg_w)))
        is_rtl = self.layoutDirection() == Qt.RightToLeft
        new_idx = (n - 1 - vis_idx) if is_rtl else vis_idx
        if new_idx == self._idx:
            return
        self._idx = new_idx
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(float(new_idx))
        self._anim.start()
        self._on_change(self._items[new_idx][0])

    def paintEvent(self, _event) -> None:
        if not self._items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        n = len(self._items)
        seg_w = (w - 6.0) / n
        is_rtl = self.layoutDirection() == Qt.RightToLeft

        # Outer pill track
        p.setBrush(QColor(C_SURFACE))
        p.setPen(QPen(QColor(C_BORDER), 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 10, 10)

        # Map logical self._pos -> visual horizontal position
        vis_pos = ((n - 1.0) - self._pos) if is_rtl else self._pos
        pill_x = 3.0 + vis_pos * seg_w
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_ACCENT))
        p.drawRoundedRect(QRectF(pill_x, 3.0, seg_w, h - 6.0), 7.5, 7.5)

        f = QFont(self.font())
        f.setPointSize(max(8, f.pointSize() - 1))
        f.setWeight(QFont.DemiBold)
        p.setFont(f)

        for logical_i, (_, label) in enumerate(self._items):
            vis_i = (n - 1 - logical_i) if is_rtl else logical_i
            dist = min(1.0, abs(self._pos - logical_i))
            fg = _lerp_color(QColor(C_ON_ACCENT), QColor(C_MUTED), dist)
            p.setPen(fg)
            cell = QRectF(3.0 + vis_i * seg_w, 0.0, seg_w, float(h))
            p.drawText(cell, Qt.AlignCenter, label)


class FloatingToast(QWidget):
    """Non-focus-stealing rounded floating pill with 60fps spinner & fade slide."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(292, 44)

        self._mode = "idle"
        self._msg = ""
        self._sub = ""
        self._angle = 0
        self._target_x = 100
        self._target_y = 24
        self._fading_out = False

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(16)
        self._spin_timer.timeout.connect(self._tick_spin)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._pos_anim = QPropertyAnimation(self, b"pos", self)
        self._pos_anim.setDuration(200)
        self._pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._op_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._op_anim.setDuration(200)
        self._op_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._op_anim.finished.connect(self._on_op_anim_finished)

    def _on_op_anim_finished(self) -> None:
        if self._fading_out:
            self.hide()

    def _place_top_center(self) -> None:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else QRect(0, 0, 1366, 768)
        self._target_x = geo.x() + (geo.width() - self.width()) // 2
        self._target_y = geo.y() + 24

    def show_loading(self, text: str) -> None:
        self._hide_timer.stop()
        self._op_anim.stop()
        self._pos_anim.stop()
        self._mode = "loading"
        self._msg = text
        self._sub = ""
        self._place_top_center()

        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.move(self._target_x, self._target_y - 12)
            self.show()
            self._animate_in()
        else:
            self.setWindowOpacity(0.96)
            self.move(self._target_x, self._target_y)

        self._spin_timer.start()
        self.update()

    def show_result(self, text: str, ok: bool = True, sub: str = "") -> None:
        self._spin_timer.stop()
        self._hide_timer.stop()
        self._op_anim.stop()
        self._pos_anim.stop()
        self._mode = "ok" if ok else "warn"
        self._msg = text
        self._sub = sub
        self._place_top_center()

        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.move(self._target_x, self._target_y - 12)
            self.show()
            self._animate_in()
        else:
            self.setWindowOpacity(0.96)
            self.move(self._target_x, self._target_y)

        self.update()
        self._hide_timer.start(1450)

    def _animate_in(self) -> None:
        self._fading_out = False
        self._op_anim.setStartValue(self.windowOpacity())
        self._op_anim.setEndValue(0.96)
        self._op_anim.start()

        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPointF(self._target_x, self._target_y).toPoint())
        self._pos_anim.start()

    def _fade_out(self) -> None:
        self._fading_out = True
        self._op_anim.setStartValue(self.windowOpacity())
        self._op_anim.setEndValue(0.0)
        self._op_anim.start()

        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPointF(self._target_x, self._target_y - 10).toPoint())
        self._pos_anim.start()

    def _tick_spin(self) -> None:
        self._angle = (self._angle - 9) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        p.setBrush(QColor("#0B0B0D"))
        p.setPen(QPen(QColor("#2E2E32"), 1.0))
        p.drawRoundedRect(rect, 21.0, 21.0)

        from PySide6.QtGui import QGuiApplication

        is_rtl = QGuiApplication.layoutDirection() == Qt.RightToLeft

        cy = self.height() / 2.0
        if self._mode == "loading":
            arc_rect = QRectF(18.0, cy - 7.0, 14.0, 14.0)
            p.setPen(QPen(QColor("#27272A"), 2.0))
            p.drawEllipse(arc_rect)
            pen = QPen(QColor(C_ACCENT), 2.0, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(arc_rect, self._angle * 16, 115 * 16)
        else:
            dot = QColor(C_OK if self._mode == "ok" else C_WARN)
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            p.drawEllipse(QRectF(20.0, cy - 4.5, 9.0, 9.0))

        p.setPen(QColor(C_TEXT))
        f = QFont(self.font())
        f.setPointSize(9)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)

        if is_rtl:
            text_left = 40.0
            if self._sub:
                p.setPen(QColor(C_DIM))
                p.setFont(QFont("Consolas", 8))
                p.drawText(
                    QRectF(36.0, 0.0, 62.0, float(self.height())),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    f"\u202a{self._sub}\u202c",
                )
                text_left = 100.0
            p.setPen(QColor(C_TEXT))
            p.setFont(f)
            p.drawText(
                QRectF(text_left, 0.0, self.width() - text_left - 20.0, float(self.height())),
                Qt.AlignVCenter | Qt.AlignRight,
                self._msg,
            )
        else:
            text_right = self.width() - 18.0
            if self._sub:
                p.setPen(QColor(C_DIM))
                p.setFont(QFont("Consolas", 8))
                p.drawText(
                    QRectF(self.width() - 78.0, 0.0, 60.0, float(self.height())),
                    Qt.AlignVCenter | Qt.AlignRight,
                    f"\u202a{self._sub}\u202c",
                )
                text_right = self.width() - 82.0
            p.setPen(QColor(C_TEXT))
            p.setFont(f)
            p.drawText(
                QRectF(42.0, 0.0, text_right - 42.0, float(self.height())),
                Qt.AlignVCenter | Qt.AlignLeft,
                self._msg,
            )
