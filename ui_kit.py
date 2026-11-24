"""Minimal pure-black rounded PySide6 components, Win32 taskbar icon fix, and 60fps animations."""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys
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
    QUrl,
    Property,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QWidget,
)

# Pure black monochrome palette (OLED / Swiss minimalism)
C_BG = "#000000"
C_CARD = "#0C0C0C"
C_SURFACE = "#161616"
C_SURFACE_HOVER = "#2A2A2E"
C_BORDER = "#242426"
C_BORDER_FOCUS = "#52525B"
C_ACCENT = "#FAFAFA"
C_ACCENT_HOVER = "#D4D4D8"
C_ON_ACCENT = "#000000"
C_TEXT = "#FAFAFA"
C_MUTED = "#A1A1AA"
C_DIM = "#71717A"
C_OK = "#22C55E"
C_WARN = "#F59E0B"
C_DANGER_BG = "#160D0D"
C_DANGER_HOVER = "#2B1517"
C_DANGER_FG = "#F87171"
C_DANGER_BORDER = "#3B1B1B"
C_DANGER_BORDER_HOVER = "#7F1D1D"

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
    margin: 4px 2px;
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


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_uint32)]


class _PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_uint16),
        ("r1", ctypes.c_uint16),
        ("r2", ctypes.c_uint16),
        ("r3", ctypes.c_uint16),
        ("pwszVal", ctypes.c_wchar_p),
        ("pad", ctypes.c_uint64),
    ]


def apply_window_taskbar_identity(
    win: QWidget,
    icon_path: Optional[Path] = None,
    exe_path: Optional[Path] = None,
) -> None:
    """Bind HWND property store, Win32 WM_SETICON, and Windows 11 pure-black frame."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(win.winId())
        # 1. Windows 11 pure-black caption, rounded window corners, dark hairline border
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

        # 2. Explicit Win32 ICON_BIG (32x32) and ICON_SMALL (16x16) on HWND
        if icon_path is not None and icon_path.exists():
            u32 = ctypes.windll.user32
            for icon_type, sz in ((1, 32), (0, 16)):
                hicon = u32.LoadImageW(0, str(icon_path), 1, sz, sz, 0x00000010)
                if hicon:
                    u32.SendMessageW(hwnd, 0x0080, icon_type, hicon)  # WM_SETICON

        # 3. Explicit HWND AppUserModelID + RelaunchIconResource for Windows 11 Taskbar
        iid_ps = _GUID(0x886D8EEB, 0x8CF2, 0x4446, (ctypes.c_ubyte * 8)(0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99))
        fmt = _GUID(0x9F4C2855, 0x9F79, 0x4B39, (ctypes.c_ubyte * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3))
        pps = ctypes.c_void_p()
        hr = ctypes.windll.shell32.SHGetPropertyStoreForWindow(
            hwnd, ctypes.byref(iid_ps), ctypes.byref(pps)
        )
        if hr == 0 and pps.value:
            vtbl = ctypes.cast(
                ctypes.cast(pps, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p),
            )
            set_val = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT)
            )(vtbl[6])
            commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtbl[7])
            release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])

            icon_res = f"{exe_path},0" if (exe_path and exe_path.exists()) else (str(icon_path) if icon_path else "")
            cmd_res = str(exe_path) if (exe_path and exe_path.exists()) else ""
            entries = [
                (_PROPERTYKEY(fmt, 5), "QuickOCR.Desktop.App.1"),
                (_PROPERTYKEY(fmt, 4), "QuickOCR"),
            ]
            if icon_res:
                entries.append((_PROPERTYKEY(fmt, 3), icon_res))
            if cmd_res:
                entries.append((_PROPERTYKEY(fmt, 2), cmd_res))
            for pk, val in entries:
                pv = _PROPVARIANT(31, 0, 0, 0, val, 0)  # VT_LPWSTR
                set_val(pps, ctypes.byref(pk), ctypes.byref(pv))
            commit(pps)
            release(pps)
    except Exception:
        pass


def enable_dark_window(win: QWidget) -> None:
    """Backward-compatible helper delegating to apply_window_taskbar_identity."""
    apply_window_taskbar_identity(win)


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


class AnimatedButton(QPushButton):
    """Vector anti-aliased rounded button with 60fps hover color/border easing."""

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
        self._hover_t = 0.0
        self._pressed = False
        self._radius = radius
        self._padx = padx
        self._fixed_h = height
        self.setVariant(variant)

        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)

        self._anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._anim.setDuration(190)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def setVariant(self, variant: str) -> None:
        palettes = {
            "primary": (C_ACCENT, C_ACCENT_HOVER, C_ON_ACCENT, C_ACCENT, "#FFFFFF"),
            "secondary": (C_SURFACE, C_SURFACE_HOVER, C_TEXT, C_BORDER, "#52525B"),
            "ghost": (C_CARD, "#1F1F24", C_MUTED, "transparent", "#323238"),
            "danger": (C_DANGER_BG, C_DANGER_HOVER, C_DANGER_FG, C_DANGER_BORDER, C_DANGER_BORDER_HOVER),
        }
        bg, hover, fg, border, border_hover = palettes[variant]
        self._bg_idle = QColor(bg)
        self._bg_hover = QColor(hover)
        self._fg = QColor(fg)
        self._border_idle = QColor(0, 0, 0, 0) if border == "transparent" else QColor(border)
        self._border_hover = QColor(border_hover)
        self.update()

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

        inset = 1.25 if self._pressed else 0.75
        rect = QRectF(inset, inset, self.width() - inset * 2, self.height() - inset * 2)
        fill = _lerp_color(self._bg_idle, self._bg_hover, self._hover_t)
        border = _lerp_color(self._border_idle, self._border_hover, self._hover_t)
        if not self.isEnabled():
            fill = QColor(C_SURFACE)
        elif self._pressed:
            fill = _lerp_color(fill, QColor("#000000"), 0.16)

        p.setBrush(fill)
        if border.alpha() > 0:
            p.setPen(QPen(border, 1.0))
        else:
            p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, self._radius, self._radius)

        fg = self._fg if self.isEnabled() else QColor(C_DIM)
        p.setPen(fg)
        p.setFont(self.font())
        text_rect = QRectF(0, 1.2 if self._pressed else 0, self.width(), self.height())
        p.drawText(text_rect, Qt.AlignCenter, self.text())


class TelegramBanner(QWidget):
    """Minimal pure-black Telegram channel promo card with smooth hover animation."""

    CHANNEL_URL = "https://t.me/pythash"

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._hover_t = 0.0
        self._pressed = False
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    @Property(float)
    def hoverProgress(self) -> float:
        return self._hover_t

    @hoverProgress.setter
    def hoverProgress(self, val: float) -> None:
        self._hover_t = val
        self.update()

    def setText(self, text: str) -> None:
        self._text = text
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
        was_pressed = self._pressed
        self._pressed = False
        self.update()
        if was_pressed and event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            QDesktopServices.openUrl(QUrl(self.CHANNEL_URL))
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = float(self.width()), float(self.height())
        is_rtl = self.layoutDirection() == Qt.RightToLeft

        c1 = _lerp_color(QColor("#24A1DE"), QColor("#2FB5F4"), self._hover_t)
        c2 = _lerp_color(QColor("#1B86BC"), QColor("#229ED9"), self._hover_t)
        if self._pressed:
            c1 = _lerp_color(c1, QColor("#000000"), 0.16)
            c2 = _lerp_color(c2, QColor("#000000"), 0.16)

        grad = QLinearGradient(0.0, 0.0, w, h)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        border = _lerp_color(QColor("#3AB2E8"), QColor("#7CD4FA"), self._hover_t)

        p.setBrush(grad)
        p.setPen(QPen(border, 1.0))
        p.drawRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 12.0, 12.0)

        # Crisp white circle + Telegram-blue paper plane
        icon_cx = w - 24.0 if is_rtl else 24.0
        icon_cy = h / 2.0
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(icon_cx, icon_cy), 13.0, 13.0)

        plane = QPainterPath()
        plane.moveTo(icon_cx - 6.0, icon_cy + 0.5)
        plane.lineTo(icon_cx + 6.5, icon_cy - 5.0)
        plane.lineTo(icon_cx + 4.2, icon_cy + 5.5)
        plane.lineTo(icon_cx + 0.3, icon_cy + 2.5)
        plane.lineTo(icon_cx - 2.0, icon_cy + 4.4)
        plane.lineTo(icon_cx - 1.8, icon_cy + 1.5)
        plane.closeSubpath()
        p.setBrush(QColor("#1B86BC"))
        p.drawPath(plane)

        # High-contrast white @pythash pill on opposite edge
        pill_w, pill_h = 86.0, 24.0
        pill_x = 11.0 if is_rtl else (w - pill_w - 11.0)
        pill_y = (h - pill_h) / 2.0
        pill_fill = _lerp_color(QColor("#FFFFFF"), QColor("#E0F4FF"), self._hover_t)
        p.setBrush(pill_fill)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pill_x, pill_y, pill_w, pill_h), 12.0, 12.0)

        p.setPen(QColor("#1271A3"))
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        nudge = 1.5 * self._hover_t * (-1 if is_rtl else 1)
        p.drawText(QRectF(pill_x + nudge, pill_y, pill_w, pill_h), Qt.AlignCenter, "\u202a@pythash ↗\u202c")

        # Bold crisp white promo text
        p.setPen(QColor("#FFFFFF"))
        f = QFont(self.font())
        f.setPointSize(8)
        f.setWeight(QFont.Bold)
        p.setFont(f)
        if is_rtl:
            txt_rect = QRectF(pill_x + pill_w + 10.0, 0.0, w - 44.0 - (pill_x + pill_w + 10.0), h)
            p.drawText(txt_rect, Qt.AlignVCenter | Qt.AlignRight, self._text)
        else:
            txt_rect = QRectF(44.0, 0.0, pill_x - 54.0, h)
            p.drawText(txt_rect, Qt.AlignVCenter | Qt.AlignLeft, self._text)


class _SlideOverlay(QWidget):
    """Paints smooth 60fps slide + cross-fade transition between two stacked pages."""

    def __init__(self, old_pix: QPixmap, new_pix: QPixmap, direction: int, parent: QWidget) -> None:
        super().__init__(parent)
        self._old = old_pix
        self._new = new_pix
        self._dir = direction  # +1 forward, -1 backward
        self._t = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(parent.rect())

    @Property(float)
    def progress(self) -> float:
        return self._t

    @progress.setter
    def progress(self, val: float) -> None:
        self._t = val
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_BG))
        w = float(self.width())
        offset = w * 0.28 * self._dir

        p.setOpacity(max(0.0, 1.0 - self._t * 1.15))
        p.drawPixmap(QPointF(-offset * self._t, 0.0), self._old)

        p.setOpacity(min(1.0, self._t * 1.1))
        p.drawPixmap(QPointF(offset * (1.0 - self._t), 0.0), self._new)


class AnimatedStackedWidget(QStackedWidget):
    """QStackedWidget with silky 60fps OutCubic slide + cross-fade transitions."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._overlay: Optional[_SlideOverlay] = None
        self._anim: Optional[QPropertyAnimation] = None

    def slideToIndex(self, index: int) -> None:
        cur = self.currentIndex()
        if index == cur or index < 0 or index >= self.count():
            return

        if self.width() < 20 or self.height() < 20 or not self.isVisible():
            self.setCurrentIndex(index)
            return

        if self._anim is not None:
            self._anim.stop()
            self._cleanup_overlay()

        old_w = self.widget(cur)
        new_w = self.widget(index)
        old_pix = old_w.grab()

        new_w.resize(self.size())
        self.setCurrentIndex(index)
        new_pix = new_w.grab()

        step_dir = 1 if index > cur else -1
        if self.layoutDirection() == Qt.RightToLeft:
            step_dir = -step_dir

        ov = _SlideOverlay(old_pix, new_pix, step_dir, self)
        ov.show()
        ov.raise_()
        self._overlay = ov

        anim = QPropertyAnimation(ov, b"progress", self)
        anim.setDuration(280)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self._cleanup_overlay)
        self._anim = anim
        anim.start()

    def _cleanup_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        self._anim = None


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
        self._anim.setDuration(210)
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
        from PySide6.QtWidgets import QHBoxLayout, QLabel

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
    """Multi-option rounded pill selector with 60fps sliding white indicator."""

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
        self._anim.setDuration(230)
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

        p.setBrush(QColor(C_SURFACE))
        p.setPen(QPen(QColor(C_BORDER), 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 10, 10)

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
    """Non-focus-stealing rounded floating pill with 60fps spinner & slide-fade."""

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
        self.setFixedSize(296, 46)

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
        self._pos_anim.setDuration(220)
        self._pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._op_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._op_anim.setDuration(220)
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
            self.move(self._target_x, self._target_y - 20)
            self.show()
            self._animate_in()
        else:
            self.setWindowOpacity(0.97)
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
            self.move(self._target_x, self._target_y - 20)
            self.show()
            self._animate_in()
        else:
            self.setWindowOpacity(0.97)
            self.move(self._target_x, self._target_y)

        self.update()
        self._hide_timer.start(1600)

    def _animate_in(self) -> None:
        self._fading_out = False
        self._op_anim.setStartValue(self.windowOpacity())
        self._op_anim.setEndValue(0.97)
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
        self._pos_anim.setEndValue(QPointF(self._target_x, self._target_y - 16).toPoint())
        self._pos_anim.start()

    def _tick_spin(self) -> None:
        self._angle = (self._angle - 10) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QGuiApplication

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        p.setBrush(QColor("#0B0B0D"))
        p.setPen(QPen(QColor("#323238"), 1.0))
        p.drawRoundedRect(rect, 22.0, 22.0)

        is_rtl = QGuiApplication.layoutDirection() == Qt.RightToLeft
        cy = self.height() / 2.0
        if self._mode == "loading":
            arc_rect = QRectF(18.0, cy - 7.0, 14.0, 14.0)
            p.setPen(QPen(QColor("#27272A"), 2.0))
            p.drawEllipse(arc_rect)
            pen = QPen(QColor(C_ACCENT), 2.2, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(arc_rect, self._angle * 16, 120 * 16)
        else:
            dot = QColor(C_OK if self._mode == "ok" else C_WARN)
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            p.drawEllipse(QRectF(20.0, cy - 4.5, 9.0, 9.0))

        f = QFont(self.font())
        f.setPointSize(9)
        f.setWeight(QFont.DemiBold)

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
