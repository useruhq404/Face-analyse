"""Titre en pixel-art « dégoulinant » : lettres en blocs, dégradé vertical,
coulures de pixels qui s'allongent doucement sous chaque lettre."""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

# Police bitmap 5×7 (1 = pixel allumé).
GLYPHS: dict[str, list[str]] = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    " ": ["000", "000", "000", "000", "000", "000", "000"],
}
ROWS = 7


class PixelTitle(QWidget):
    def __init__(self, text: str, pixel: int = 4, gap: int = 1, top: QColor | None = None,
                 bottom: QColor | None = None, max_drip: int = 5, animated: bool = True, seed: int = 7, bold: bool = True, parent=None):
        super().__init__(parent)
        self.text = text.upper()
        self.pixel = pixel
        self.gap = gap
        self.top = top or QColor(255, 255, 255)
        self.bottom = bottom or QColor(120, 120, 120)
        self.max_drip = max_drip
        self.bold = bold
        self._t = 0.0
        self._cells = self._layout()
        rng = random.Random(seed)
        # Coulures : sous certains pixels du bas de chaque colonne.
        self._drips = []
        for (cx, cy) in self._bottom_cells():
            if rng.random() < 0.55:
                self._drips.append((cx, cy, rng.randint(1, max_drip), rng.random() * 6.28))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if animated:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(60)

    # ------------------------------------------------------------ géométrie
    def _layout(self) -> list[tuple[int, int]]:
        cells, x = [], 0
        for ch in self.text:
            glyph = GLYPHS.get(ch, GLYPHS[" "])
            for r, row in enumerate(glyph):
                for c, bit in enumerate(row):
                    if bit == "1":
                        cells.append((x + c, r))
                        if self.bold:  # trait doublé : lettres pleines, façon blocs
                            cells.append((x + c + 1, r))
            x += len(glyph[0]) + (2 if self.bold else 1)
        cells = sorted(set(cells))
        self._cols = max(x - 1, 1)
        return cells

    def _bottom_cells(self) -> list[tuple[int, int]]:
        lowest: dict[int, int] = {}
        for cx, cy in self._cells:
            lowest[cx] = max(lowest.get(cx, -1), cy)
        return sorted(lowest.items())

    def sizeHint(self) -> QSize:
        step = self.pixel + self.gap
        return QSize(self._cols * step, (ROWS + self.max_drip + 1) * step)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _tick(self):
        self._t += 0.06
        self.update()

    # ------------------------------------------------------------ rendu
    def paintEvent(self, _):
        p = QPainter(self)
        step = self.pixel + self.gap
        ox = (self.width() - self._cols * step) / 2
        oy = 0
        grad = QLinearGradient(0, oy, 0, oy + ROWS * step)
        grad.setColorAt(0.0, self.top)
        grad.setColorAt(1.0, self.bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        for cx, cy in self._cells:
            p.drawRect(QRectF(ox + cx * step, oy + cy * step, self.pixel, self.pixel))
        # Coulures : longueur qui « respire », pixels de plus en plus transparents.
        for cx, cy, length, phase in self._drips:
            cur = max(1, round(length * (0.65 + 0.35 * math.sin(self._t + phase))))
            for k in range(1, cur + 1):
                a = int(220 * (1 - k / (self.max_drip + 1.5)))
                c = QColor(self.bottom)
                c.setAlpha(max(a, 25))
                p.setBrush(c)
                size = self.pixel if k < cur else max(1, self.pixel - 1)
                p.drawRect(QRectF(ox + cx * step, oy + (cy + k) * step, size, size))
        p.end()
