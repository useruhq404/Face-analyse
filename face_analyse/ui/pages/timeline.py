"""TIMELINE — analyse temporelle des événements (historique local).

Timeline minimale et interactive (pas un composant générique) : axe de temps
zoomable, couloirs par module, sélection d'événement, filtres. Monochrome.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from face_analyse.ui import theme
from face_analyse.ui.pages.common import Page, muted, section_label

GUTTER = 128
PAD_T, PAD_B = 16, 34


@dataclass
class TEvent:
    ts: datetime
    module: str
    action: str
    summary: str


_LABELS = {"osint": "OSINT", "analysis": "Analyse", "camera": "Caméra", "database": "Base",
           "tools": "Outils", "datalab": "Data Lab", "nav": "Navigation", "app": "App", "graph": "Graphe"}


class TimelineView(QWidget):
    selected = Signal(object)  # TEvent | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.setMouseTracking(True)
        self._events: list[TEvent] = []
        self._lanes: list[str] = []
        self._hidden: set[str] = set()
        self._start = 0.0
        self._end = 1.0
        self._full = (0.0, 1.0)
        self._sel: TEvent | None = None
        self._pan_x: float | None = None

    def set_events(self, events: list[TEvent]):
        self._events = sorted(events, key=lambda e: e.ts)
        self._lanes = sorted({e.module for e in self._events}, key=lambda m: _LABELS.get(m, m))
        if self._events:
            lo = self._events[0].ts.timestamp()
            hi = self._events[-1].ts.timestamp()
            if hi - lo < 60:
                hi = lo + 60
            pad = (hi - lo) * 0.04
            self._full = (lo - pad, hi + pad)
            self._start, self._end = self._full
        self._sel = None
        self.selected.emit(None)
        self.update()

    def set_hidden(self, hidden: set[str]):
        self._hidden = hidden
        self.update()

    def reset_view(self):
        self._start, self._end = self._full
        self.update()

    # ------------------------------------------------------------ géométrie
    def _visible_lanes(self) -> list[str]:
        return [m for m in self._lanes if m not in self._hidden]

    def _x(self, ts: float) -> float:
        span = self._end - self._start or 1.0
        return GUTTER + (ts - self._start) / span * (self.width() - GUTTER - 16)

    def _lane_y(self, module: str) -> float:
        lanes = self._visible_lanes()
        if module not in lanes:
            return -100
        h = self.height() - PAD_T - PAD_B
        n = max(1, len(lanes))
        row = lanes.index(module)
        return PAD_T + h * (row + 0.5) / n

    # ------------------------------------------------------------ interactions
    def wheelEvent(self, e):
        if not self._events:
            return
        cursor_ts = self._start + (e.position().x() - GUTTER) / max(1, self.width() - GUTTER - 16) * (self._end - self._start)
        factor = 0.8 if e.angleDelta().y() > 0 else 1.25
        new_span = (self._end - self._start) * factor
        full_span = self._full[1] - self._full[0]
        new_span = max(60.0, min(new_span, full_span))
        left_frac = (cursor_ts - self._start) / max(1e-9, self._end - self._start)
        self._start = cursor_ts - left_frac * new_span
        self._end = self._start + new_span
        self._clamp()
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            hit = self._event_at(e.position())
            if hit is not None:
                self._sel = hit
                self.selected.emit(hit)
                self.update()
            else:
                self._pan_x = e.position().x()

    def mouseMoveEvent(self, e):
        if self._pan_x is not None:
            dx = e.position().x() - self._pan_x
            self._pan_x = e.position().x()
            span = self._end - self._start
            shift = -dx / max(1, self.width() - GUTTER - 16) * span
            self._start += shift
            self._end += shift
            self._clamp()
            self.update()

    def mouseReleaseEvent(self, e):
        self._pan_x = None

    def _clamp(self):
        lo, hi = self._full
        span = self._end - self._start
        if self._start < lo:
            self._start, self._end = lo, lo + span
        if self._end > hi:
            self._end, self._start = hi, hi - span
        self._start = max(self._start, lo)
        self._end = min(self._end, hi)

    def _event_at(self, pos: QPointF) -> TEvent | None:
        best, bestd = None, 12.0
        for ev in self._events:
            if ev.module in self._hidden:
                continue
            ex, ey = self._x(ev.ts.timestamp()), self._lane_y(ev.module)
            if ex < GUTTER - 4 or ex > self.width():
                continue
            d = ((pos.x() - ex) ** 2 + (pos.y() - ey) ** 2) ** 0.5
            if d < bestd:
                best, bestd = ev, d
        return best

    # ------------------------------------------------------------ rendu
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        if not self._events:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Aucun événement. Lancez des analyses / recherches pour peupler la chronologie.")
            return
        lanes = self._visible_lanes()
        mono = QFont(theme.mono_font_family(), 8)
        small = QFont(theme.mono_font_family(), 7)

        # couloirs + libellés
        for m in lanes:
            y = self._lane_y(m)
            p.setPen(QPen(QColor(24, 24, 24), 1))
            p.drawLine(GUTTER, int(y), self.width() - 16, int(y))
            p.setPen(QColor(theme.MUTED))
            p.setFont(mono)
            p.drawText(QRectF(8, y - 9, GUTTER - 16, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       _LABELS.get(m, m))

        # graduations de temps
        p.setFont(small)
        for frac in (i / 5 for i in range(6)):
            ts = self._start + frac * (self._end - self._start)
            x = self._x(ts)
            p.setPen(QPen(QColor(22, 22, 22), 1))
            p.drawLine(int(x), PAD_T, int(x), self.height() - PAD_B)
            p.setPen(QColor(theme.MUTED))
            dt = datetime.fromtimestamp(ts)
            label = dt.strftime("%d/%m %H:%M") if (self._end - self._start) < 3 * 86400 else dt.strftime("%d/%m/%y")
            p.drawText(QRectF(x - 40, self.height() - PAD_B + 4, 80, 16), Qt.AlignmentFlag.AlignHCenter, label)

        # événements
        for ev in self._events:
            if ev.module in self._hidden:
                continue
            x = self._x(ev.ts.timestamp())
            if x < GUTTER - 4 or x > self.width() - 8:
                continue
            y = self._lane_y(ev.module)
            sel = ev is self._sel
            p.setPen(Qt.PenStyle.NoPen)
            if sel:
                p.setBrush(QColor(255, 255, 255, 50))
                p.drawEllipse(QPointF(x, y), 9, 9)
            p.setBrush(QColor(theme.WHITE) if sel else QColor(200, 200, 200))
            p.drawEllipse(QPointF(x, y), 4.5 if sel else 3.2, 4.5 if sel else 3.2)
        p.end()


class TimelinePage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__("TIMELINE",
                         "Chronologie interactive des événements locaux. Molette : zoom temporel · "
                         "glisser : déplacer · clic : sélectionner.", parent)
        self.ctx = ctx
        bar = QHBoxLayout()
        self.reset_btn = QPushButton("Tout afficher")
        self.reset_btn.clicked.connect(lambda: self.view.reset_view())
        self.reload_btn = QPushButton("Actualiser")
        self.reload_btn.clicked.connect(self.reload)
        self.range_lbl = muted("")
        bar.addWidget(self.reset_btn)
        bar.addWidget(self.reload_btn)
        bar.addWidget(self.range_lbl, 1)
        self.root.addLayout(bar)

        body = QHBoxLayout()
        self.view = TimelineView()
        self.view.selected.connect(self._on_select)
        body.addWidget(self.view, 1)
        side = QVBoxLayout()
        side.setSpacing(8)
        side.addWidget(section_label("Modules"))
        self.legend = QVBoxLayout()
        self.legend.setSpacing(3)
        side.addLayout(self.legend)
        side.addWidget(section_label("Détail"))
        self.detail = QTextBrowser()
        self.detail.setMinimumHeight(140)
        side.addWidget(self.detail, 1)
        w = QWidget()
        w.setFixedWidth(250)
        w.setLayout(side)
        body.addWidget(w)
        self.root.addLayout(body, 1)
        self._hidden: set[str] = set()
        self._reset_detail()

    def on_show(self):
        self.reload()

    def reload(self):
        entries = self.ctx.repo.history(limit=800)
        events = [TEvent(h.timestamp.astimezone() if h.timestamp.tzinfo else h.timestamp,
                         h.module, h.action, h.summary) for h in entries]
        self.view.set_events(events)
        self._build_legend([e.module for e in events])
        if events:
            lo, hi = events[-1].ts, events[0].ts
            self.range_lbl.setText(f"{len(events)} événement(s) · du {lo:%d/%m/%Y %H:%M} au {hi:%d/%m/%Y %H:%M}")
        else:
            self.range_lbl.setText("Aucun événement.")
        self._reset_detail()

    def _build_legend(self, modules):
        while self.legend.count():
            it = self.legend.takeAt(0).widget()
            if it:
                it.deleteLater()
        for m in sorted(set(modules), key=lambda x: _LABELS.get(x, x)):
            cb = QCheckBox(_LABELS.get(m, m))
            cb.setChecked(True)
            cb.toggled.connect(lambda on, mm=m: self._toggle(mm, on))
            self.legend.addWidget(cb)

    def _toggle(self, module: str, on: bool):
        if on:
            self._hidden.discard(module)
        else:
            self._hidden.add(module)
        self.view.set_hidden(set(self._hidden))

    def _on_select(self, ev):
        if ev is None:
            self._reset_detail()
            return
        self.detail.setHtml(
            f"<h3 style='font-weight:300;letter-spacing:1px'>{_LABELS.get(ev.module, ev.module)}</h3>"
            f"<div style='color:#888'>{ev.ts:%d/%m/%Y %H:%M:%S}</div>"
            f"<div style='color:#888'>action : {ev.action}</div><p>{ev.summary}</p>"
        )

    def _reset_detail(self):
        self.detail.setHtml("<p style='color:#888'>Sélectionnez un point pour afficher le détail de l'événement.</p>")
