"""Affichage d'image avec cadres de visages (proportions conservées)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from face_analyse.ui import theme


def bgr_to_qimage(img: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


@dataclass
class Overlay:
    box: tuple[float, float, float, float]  # coordonnées image
    label: str
    sublabel: str = ""
    known: bool = False
    index: int | None = None


def draw_face_frame(p: QPainter, r: QRectF, label: str, sublabel: str, known: bool) -> None:
    """Cadre « viseur » : coins lumineux + étiquette."""
    color = theme.QC_KNOWN if known else theme.QC_UNKNOWN
    pen = QPen(color, 2)
    p.setPen(pen)
    corner = max(10.0, min(r.width(), r.height()) * 0.22)
    x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
    for (ax, ay, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        p.drawLine(QPointF(ax, ay), QPointF(ax + dx * corner, ay))
        p.drawLine(QPointF(ax, ay), QPointF(ax, ay + dy * corner))
    thin = QPen(QColor(color.red(), color.green(), color.blue(), 70), 1)
    p.setPen(thin)
    p.drawRect(r)

    f = QFont(theme.ui_font_family(), 10)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
    p.setFont(f)
    text = label.upper()
    fm = p.fontMetrics()
    tw = fm.horizontalAdvance(text) + 14
    th = fm.height() + 6
    ty = y0 - th - 4 if y0 - th - 4 > 0 else y1 + 4
    p.fillRect(QRectF(x0, ty, tw, th), QColor(0, 0, 0, 200))
    p.setPen(color)
    p.drawText(QRectF(x0 + 7, ty, tw, th), Qt.AlignmentFlag.AlignVCenter, text)
    if sublabel:
        f2 = QFont(theme.mono_font_family(), 8)
        p.setFont(f2)
        p.setPen(QColor(200, 200, 200))
        p.drawText(QPointF(x0, y1 + (th + 14 if ty > y1 else 14)), sublabel)


class ImageView(QWidget):
    def __init__(self, parent=None, placeholder: str = "Aucune image"):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 240)
        self._pix: QPixmap | None = None
        self._img_size = (1, 1)
        self.overlays: list[Overlay] = []
        self.placeholder = placeholder

    def set_image(self, img: np.ndarray | QImage | None) -> None:
        if img is None:
            self._pix = None
        else:
            qimg = img if isinstance(img, QImage) else bgr_to_qimage(img)
            self._pix = QPixmap.fromImage(qimg)
            self._img_size = (qimg.width(), qimg.height())
        self.update()

    def set_overlays(self, overlays: list[Overlay]) -> None:
        self.overlays = overlays
        self.update()

    def _target_rect(self) -> QRectF:
        iw, ih = self._img_size
        scale = min(self.width() / iw, self.height() / ih)
        w, h = iw * scale, ih * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(6, 6, 6))
        if self._pix is None:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholder)
            return
        target = self._target_rect()
        p.drawPixmap(target, self._pix, QRectF(self._pix.rect()))
        scale = target.width() / self._img_size[0]
        for ov in self.overlays:
            x, y, w, h = ov.box
            r = QRectF(target.left() + x * scale, target.top() + y * scale, w * scale, h * scale)
            label = f"#{ov.index}  {ov.label}" if ov.index is not None else ov.label
            draw_face_frame(p, r, label, ov.sublabel, ov.known)
        p.end()
