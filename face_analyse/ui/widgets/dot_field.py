"""Fond animé : image en trame de points + champ de points lumineux.

L'esthétique « halftone » (points blancs sur noir) de l'image d'accueil est
prolongée par une grille de points qui scintillent doucement et réagissent
au curseur — discret, fluide, sans élément inutile.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget


class DotField(QWidget):
    def __init__(self, parent=None, background: QPixmap | None = None, spacing: int = 22,
                 image_opacity: float = 0.85, fps: int = 30):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)
        self._bg = background
        self._scaled: QPixmap | None = None
        self.spacing = spacing
        self.image_opacity = image_opacity
        self._t = 0.0
        self._mouse = QPointF(-1000, -1000)
        self._seeds: dict[tuple[int, int], float] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000 / fps))

    def set_background(self, pix: QPixmap | None) -> None:
        self._bg = pix
        self._scaled = None
        self.update()

    def _tick(self):
        self._t += 0.033
        self.update()

    def mouseMoveEvent(self, e):
        self._mouse = e.position()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._mouse = QPointF(-1000, -1000)
        super().leaveEvent(e)

    def resizeEvent(self, e):
        self._scaled = None
        super().resizeEvent(e)

    def _image_rect(self) -> QRectF:
        """Image centrée, proportions conservées (contain), jamais déformée."""
        assert self._bg is not None
        w, h = self.width(), self.height()
        iw, ih = self._bg.width(), self._bg.height()
        scale = min(w / iw, h / ih)
        sw, sh = iw * scale, ih * scale
        return QRectF((w - sw) / 2, (h - sh) / 2, sw, sh)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QColor(3, 3, 3))

        # Grille de points scintillants.
        s = self.spacing
        mx, my = self._mouse.x(), self._mouse.y()
        p.setPen(Qt.PenStyle.NoPen)
        for gx in range(s // 2, self.width(), s):
            for gy in range(s // 2, self.height(), s):
                seed = self._seeds.setdefault((gx, gy), random.random() * 6.283)
                a = 0.06 + 0.05 * math.sin(self._t * 0.9 + seed)
                d = math.hypot(gx - mx, gy - my)
                if d < 140:
                    a += 0.35 * (1 - d / 140)
                p.setBrush(QColor(255, 255, 255, int(255 * max(0.0, min(a, 1.0)))))
                p.drawEllipse(QPointF(gx, gy), 1.1, 1.1)

        # Image d'accueil intégrée au noir (proportions conservées).
        if self._bg is not None and not self._bg.isNull():
            rect = self._image_rect()
            if self._scaled is None or self._scaled.size() != rect.size().toSize():
                self._scaled = self._bg.scaled(rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
            breathe = 0.92 + 0.08 * math.sin(self._t * 0.6)
            p.setOpacity(self.image_opacity * breathe)
            p.drawPixmap(rect.topLeft(), self._scaled)
            p.setOpacity(1.0)

        # Vignettage : fond noir qui « absorbe » les bords.
        c = QPointF(self.width() / 2, self.height() / 2)
        g = QRadialGradient(c, max(self.width(), self.height()) * 0.72)
        g.setColorAt(0.0, QColor(0, 0, 0, 0))
        g.setColorAt(0.65, QColor(0, 0, 0, 40))
        g.setColorAt(1.0, QColor(0, 0, 0, 235))
        p.fillRect(self.rect(), g)
        p.end()
