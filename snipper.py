"""DPI-aware multi-monitor animated screen snipping overlay (PySide6) and app icon."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageGrab
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget


def get_virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """Return (left, top, width, height) covering all connected monitors in physical px."""
    u32 = ctypes.windll.user32
    vx = u32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    vy = u32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
    vw = u32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    vh = u32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
    if vw <= 0 or vh <= 0:
        vw = u32.GetSystemMetrics(0)
        vh = u32.GetSystemMetrics(1)
        vx, vy = 0, 0
    return vx, vy, vw, vh


def make_app_icon(
    ico_path: Optional[Path] = None,
    png_path: Optional[Path] = None,
) -> Image.Image:
    """Create a crisp 256x256 pure-black monochrome geometric QuickOCR logo (2x SSAA)."""
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Pure OLED black squircle with crisp metallic border
    d.rounded_rectangle([16, 16, 495, 495], radius=116, fill="#050505", outline="#3F3F46", width=12)
    d.rounded_rectangle([32, 32, 479, 479], radius=100, fill=None, outline="#18181B", width=6)

    # Bold high-contrast viewfinder brackets with smooth round caps
    c = "#FAFAFA"
    w = 30
    r = w // 2
    arm = 84
    m = 98
    e = size - m
    brackets = [
        [(m, m + arm), (m, m), (m + arm, m)],
        [(e - arm, m), (e, m), (e, m + arm)],
        [(m, e - arm), (m, e), (m + arm, e)],
        [(e - arm, e), (e, e), (e, e - arm)],
    ]
    for pts in brackets:
        d.line(pts, fill=c, width=w, joint="curve")
        for px, py in (pts[0], pts[-1]):
            d.ellipse([px - r, py - r, px + r, py + r], fill=c)

    # Minimal white scan bar + stylized OCR lines inside viewfinder
    d.rounded_rectangle([154, 178, 358, 210], radius=16, fill="#FAFAFA")
    d.rounded_rectangle([154, 240, 314, 270], radius=15, fill="#A1A1AA")
    d.rounded_rectangle([154, 300, 268, 330], radius=15, fill="#52525B")

    img = img.resize((256, 256), Image.Resampling.LANCZOS)

    if png_path is not None:
        png_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(png_path, format="PNG")
    if ico_path is not None:
        img.save(
            ico_path,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    return img


def _pil_to_pixmap(img: Image.Image) -> QPixmap:
    rgb = img.convert("RGB")
    raw = rgb.tobytes("raw", "RGB")
    qimg = QImage(raw, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


class SnipOverlay(QWidget):
    """Fullscreen frozen-screen overlay with spotlight cutout and 60fps corner animation."""

    captured = Signal(object)
    cancelled = Signal()

    def __init__(
        self,
        hint_text: str = "کادر بکشید  •  لغو با راست‌کلیک یا Esc",
        screenshot: Optional[Image.Image] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self._hint_text = hint_text
        self._closed = False
        self._start: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self._dash_offset = 0.0
        self._intro = 0.0

        if screenshot is not None:
            self._raw_shot = screenshot
            geom = QRect(0, 0, screenshot.width, screenshot.height)
        else:
            vx, vy, vw, vh = get_virtual_screen_bounds()
            self._raw_shot = ImageGrab.grab(
                bbox=(vx, vy, vx + vw, vy + vh),
                include_layered_windows=True,
                all_screens=True,
            )
            ps = QGuiApplication.primaryScreen()
            geom = ps.virtualGeometry() if ps else QRect(vx, vy, vw, vh)

        self._pixmap = _pil_to_pixmap(self._raw_shot)

        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setCursor(Qt.CrossCursor)
        self.setGeometry(geom)

        self._dash_timer = QTimer(self)
        self._dash_timer.setInterval(16)
        self._dash_timer.timeout.connect(self._tick_dash)

        self._intro_anim = QPropertyAnimation(self, b"introProgress", self)
        self._intro_anim.setDuration(240)
        self._intro_anim.setStartValue(0.0)
        self._intro_anim.setEndValue(1.0)
        self._intro_anim.setEasingCurve(QEasingCurve.OutCubic)

    @Property(float)
    def introProgress(self) -> float:
        return self._intro

    @introProgress.setter
    def introProgress(self, val: float) -> None:
        self._intro = val
        self.update()

    def start(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._intro_anim.start()

    def _tick_dash(self) -> None:
        self._dash_offset = (self._dash_offset - 0.5) % 10.0
        self.update()

    def _selection_rect(self) -> Optional[QRect]:
        if self._start is None or self._current is None:
            return None
        return QRect(self._start, self._current).normalized()

    def begin_drag(self, pos: QPoint) -> None:
        self._start = pos
        self._current = pos
        if not self._dash_timer.isActive():
            self._dash_timer.start()
        self.update()

    def move_drag(self, pos: QPoint) -> None:
        if self._start is None:
            return
        self._current = pos
        self.update()

    def end_drag(self, pos: QPoint) -> None:
        if self._closed or self._start is None:
            return
        self._current = pos
        rect = self._selection_rect()
        self._cleanup_and_close()

        if rect is None or rect.width() < 8 or rect.height() < 8:
            self.cancelled.emit()
            return

        # Map widget coordinates proportionally to physical screenshot pixels
        sx = self._raw_shot.width / max(1, self.width())
        sy = self._raw_shot.height / max(1, self.height())
        left = max(0, int(round(rect.left() * sx)))
        top = max(0, int(round(rect.top() * sy)))
        right = min(self._raw_shot.width, int(round((rect.right() + 1) * sx)))
        bottom = min(self._raw_shot.height, int(round((rect.bottom() + 1) * sy)))

        if (right - left) < 4 or (bottom - top) < 4:
            self.cancelled.emit()
            return

        cropped = self._raw_shot.crop((left, top, right, bottom))
        self.captured.emit(cropped)

    def cancel_snip(self) -> None:
        if self._closed:
            return
        self._cleanup_and_close()
        self.cancelled.emit()

    def _cleanup_and_close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._dash_timer.stop()
        self._intro_anim.stop()
        self.close()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.begin_drag(event.position().toPoint())
        elif event.button() == Qt.RightButton:
            self.cancel_snip()

    def mouseMoveEvent(self, event) -> None:
        if self._start is not None:
            self.move_drag(event.position().toPoint())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._start is not None:
            self.end_drag(event.position().toPoint())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancel_snip()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Fullscreen frozen shot + animated scrim darkness (60fps, zero DWM flicker)
        p.drawPixmap(self.rect(), self._pixmap)
        scrim_alpha = int(152 * self._intro)
        p.fillRect(self.rect(), QColor(0, 0, 0, scrim_alpha))

        # Top rounded instruction pill sliding smoothly down into view
        hint_font = QFont(self.font())
        hint_font.setPointSize(9)
        hint_font.setWeight(QFont.DemiBold)
        p.setFont(hint_font)
        fm = QFontMetrics(hint_font)
        pill_w = fm.horizontalAdvance(self._hint_text) + 38
        pill_h = 34
        pill_y = -40.0 + 60.0 * self._intro
        pill_rect = QRectF((self.width() - pill_w) / 2.0, pill_y, pill_w, pill_h)
        pill_alpha = int(238 * self._intro)
        p.setBrush(QColor(12, 12, 14, pill_alpha))
        p.setPen(QPen(QColor(63, 63, 70, pill_alpha), 1.0))
        p.drawRoundedRect(pill_rect, pill_h / 2.0, pill_h / 2.0)
        p.setPen(QColor(250, 250, 250, int(255 * self._intro)))
        p.drawText(pill_rect, Qt.AlignCenter, self._hint_text)

        rect = self._selection_rect()
        if rect is None or rect.width() < 2 or rect.height() < 2:
            return

        # Full-brightness spotlight cutout inside selection
        p.save()
        p.setClipRect(rect)
        p.drawPixmap(self.rect(), self._pixmap)
        p.restore()

        # Subtle glowing outer halo + animated marching dashed guide
        p.setPen(QPen(QColor(255, 255, 255, 42), 3.0))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(rect).adjusted(-0.5, -0.5, 0.5, 0.5))

        dash_pen = QPen(QColor(255, 255, 255, 200), 1.0)
        dash_pen.setDashPattern([6, 4])
        dash_pen.setDashOffset(self._dash_offset)
        p.setPen(dash_pen)
        p.drawRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5))

        # Crisp white L-shaped rounded-cap corner viewfinder brackets
        arm = float(min(16, max(5, rect.width() // 3), max(5, rect.height() // 3)))
        bracket_pen = QPen(QColor("#FFFFFF"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(bracket_pen)
        l, t, r, b = float(rect.left()), float(rect.top()), float(rect.right()), float(rect.bottom())
        p.drawPolyline([QPoint(int(l), int(t + arm)), QPoint(int(l), int(t)), QPoint(int(l + arm), int(t))])
        p.drawPolyline([QPoint(int(r - arm), int(t)), QPoint(int(r), int(t)), QPoint(int(r), int(t + arm))])
        p.drawPolyline([QPoint(int(l), int(b - arm)), QPoint(int(l), int(b)), QPoint(int(l + arm), int(b))])
        p.drawPolyline([QPoint(int(r - arm), int(b)), QPoint(int(r), int(b)), QPoint(int(r), int(b - arm))])

        # Live dimension rounded pill (keep W x H strictly LTR)
        dim_text = f"\u202a{rect.width()} × {rect.height()}\u202c"
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        dm = QFontMetrics(p.font())
        bw = dm.horizontalAdvance(dim_text) + 20
        bh = 24
        by = float(rect.top() - bh - 8) if rect.top() >= bh + 12 else float(rect.bottom() + 8)
        bx = min(float(self.width() - bw - 8), max(8.0, float(rect.left())))
        badge = QRectF(bx, by, bw, bh)
        p.setBrush(QColor(12, 12, 14, 235))
        p.setPen(QPen(QColor("#3F3F46"), 1.0))
        p.drawRoundedRect(badge, bh / 2.0, bh / 2.0)
        p.setPen(QColor("#FAFAFA"))
        p.drawText(badge, Qt.AlignCenter, dim_text)
