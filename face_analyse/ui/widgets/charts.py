"""Visualisations monochromes peintes à la main (identité dot-matrix).

Aucune dépendance graphique externe : tout est tracé au QPainter, en cohérence
avec l'esthétique de l'écran d'accueil.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from face_analyse.ui import theme


class ActivityDots(QWidget):
    """Histogramme en points : une colonne par jour, remplie de bas en haut.

    La hauteur de chaque colonne (nombre de points allumés) est proportionnelle
    à l'activité du jour ; la dernière colonne (aujourd'hui) est mise en avant.
    """

    def __init__(self, parent=None, rows: int = 7):
        super().__init__(parent)
        self.rows = rows
        self._data: list[tuple[str, int]] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(150)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = list(data)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        if not self._data:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Aucune activité enregistrée.")
            return
        peak = max((v for _, v in self._data), default=0)
        n = len(self._data)
        pad_l, pad_r, pad_t, pad_b = 8, 8, 10, 22
        area_w = self.width() - pad_l - pad_r
        area_h = self.height() - pad_t - pad_b
        col_w = area_w / n
        dot = min(col_w * 0.5, area_h / (self.rows * 1.8), 9.0)
        gap_y = area_h / self.rows
        p.setPen(Qt.PenStyle.NoPen)
        mono = QFont(theme.mono_font_family(), 7)
        for i, (label, value) in enumerate(self._data):
            cx = pad_l + col_w * (i + 0.5)
            filled = 0 if peak == 0 else max(1 if value > 0 else 0, round(self.rows * value / peak))
            last = i == n - 1
            for r in range(self.rows):
                cy = pad_t + area_h - gap_y * (r + 0.5)
                on = r < filled
                if on:
                    col = QColor(theme.WHITE) if last else QColor(235, 235, 235)
                else:
                    col = QColor(32, 32, 32)
                p.setBrush(col)
                p.drawEllipse(QRectF(cx - dot / 2, cy - dot / 2, dot, dot))
            # étiquette du jour (JJ) une colonne sur deux
            if n <= 10 or i % 2 == 0 or last:
                p.setPen(QColor(theme.WHITE if last else theme.MUTED))
                p.setFont(mono)
                day = label[-2:]
                p.drawText(QRectF(cx - col_w / 2, self.height() - pad_b + 4, col_w, 16),
                           Qt.AlignmentFlag.AlignHCenter, day)
                p.setPen(Qt.PenStyle.NoPen)
        p.end()


class BarList(QWidget):
    """Barres horizontales fines : (label, valeur). Pour la répartition par module."""

    def __init__(self, parent=None, max_rows: int = 6):
        super().__init__(parent)
        self.max_rows = max_rows
        self._data: list[tuple[str, int]] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = list(data)[: self.max_rows]
        self.setMinimumHeight(max(40, 26 * len(self._data) + 6))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._data:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "—")
            return
        peak = max(v for _, v in self._data)
        row_h = 26
        label_w = min(140, self.width() * 0.4)
        bar_x = label_w + 8
        bar_w = self.width() - bar_x - 44
        name_font = QFont(theme.ui_font_family(), 9)
        mono = QFont(theme.mono_font_family(), 9)
        for i, (label, value) in enumerate(self._data):
            y = i * row_h
            p.setPen(QColor(theme.FG))
            p.setFont(name_font)
            p.drawText(QRectF(0, y, label_w, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       label.upper())
            w = 0 if peak == 0 else bar_w * value / peak
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(28, 28, 28))
            p.drawRect(QRectF(bar_x, y + row_h / 2 - 3, bar_w, 6))
            p.setBrush(QColor(theme.WHITE))
            p.drawRect(QRectF(bar_x, y + row_h / 2 - 3, max(2.0, w), 6))
            p.setPen(QColor(theme.MUTED))
            p.setFont(mono)
            p.drawText(QRectF(bar_x + bar_w + 6, y, 40, row_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(value))
        p.end()
