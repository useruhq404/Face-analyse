"""INTELLIGENCE GRAPH — graphe relationnel interactif (QGraphicsView).

Zoom, déplacement, sélection, mise en évidence du voisinage, légende avec
filtres par catégorie, recherche, panneau de détail, réagencement et
réinitialisation de la vue. Rendu monochrome fidèle à l'identité.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QGraphicsItem, QGraphicsLineItem, QGraphicsScene, QGraphicsView,
                               QHBoxLayout, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from face_analyse.graph.layout import force_directed
from face_analyse.graph.model import TYPE_LABELS, Graph, Node, build_graph
from face_analyse.ui import theme
from face_analyse.ui.pages.common import Page, muted, section_label
from face_analyse.ui.workers import run_async

SCENE_W, SCENE_H = 2600, 1700
NODE_R = 13


def _shape_path(ntype: str, r: float) -> QPainterPath:
    p = QPainterPath()
    if ntype in ("person",):
        p.addEllipse(QPointF(0, 0), r, r)
    elif ntype == "photo":
        p.addRect(QRectF(-r, -r, 2 * r, 2 * r))
    elif ntype == "document":
        p.addRoundedRect(QRectF(-r * 0.8, -r, r * 1.6, 2 * r), 3, 3)
    elif ntype == "query":
        for i, (dx, dy) in enumerate([(0, -r), (r, 0), (0, r), (-r, 0)]):
            p.moveTo(dx, dy) if i == 0 else p.lineTo(dx, dy)
        p.closeSubpath()
    elif ntype == "source":
        for i, (dx, dy) in enumerate([(0, -r), (r, r), (-r, r)]):
            p.moveTo(dx, dy) if i == 0 else p.lineTo(dx, dy)
        p.closeSubpath()
    elif ntype == "tool":
        for i, (dx, dy) in enumerate([(0, r), (r, -r), (-r, -r)]):
            p.moveTo(dx, dy) if i == 0 else p.lineTo(dx, dy)
        p.closeSubpath()
    else:  # org / domain / event : polygone
        sides = {"org": 6, "domain": 8, "event": 5}.get(ntype, 6)
        for i in range(sides):
            a = -math.pi / 2 + 2 * math.pi * i / sides
            x, y = r * math.cos(a), r * math.sin(a)
            p.moveTo(x, y) if i == 0 else p.lineTo(x, y)
        p.closeSubpath()
    return p


class NodeItem(QGraphicsItem):
    def __init__(self, node: Node):
        super().__init__()
        self.node = node
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self._hover = False
        self._dim = False
        self._match = False
        self.setToolTip(f"{TYPE_LABELS.get(node.ntype, node.ntype)} · {node.label}")

    def boundingRect(self) -> QRectF:
        return QRectF(-70, -NODE_R - 2, 140, NODE_R + 34)

    def shape(self) -> QPainterPath:
        return _shape_path(self.node.ntype, NODE_R + 3)

    def set_dim(self, dim: bool):
        if dim != self._dim:
            self._dim = dim
            self.update()

    def set_match(self, m: bool):
        if m != self._match:
            self._match = m
            self.update()

    def hoverEnterEvent(self, e):
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False
        self.update()

    def paint(self, p: QPainter, option, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sel = self.isSelected()
        base = 1.0 if not self._dim else 0.22
        demo = self.node.demo
        outline = QColor(255, 255, 255) if (sel or self._hover or self._match) else QColor(205, 205, 205)
        outline.setAlphaF(base)
        fill = QColor(26, 26, 26)
        fill.setAlphaF(base)
        pen = QPen(outline, 2.4 if (sel or self._match) else 1.6)
        if demo:
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(QBrush(fill))
        p.drawPath(_shape_path(self.node.ntype, NODE_R))
        if sel or self._match:
            halo = QColor(255, 255, 255, 40)
            p.setPen(QPen(halo, 6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(_shape_path(self.node.ntype, NODE_R + 5))

        # étiquette
        f = QFont(theme.mono_font_family(), 7)
        p.setFont(f)
        col = QColor(255, 255, 255) if (sel or self._hover or self._match) else QColor(150, 150, 150)
        col.setAlphaF(base)
        p.setPen(col)
        label = (self.node.label[:20] + "…") if len(self.node.label) > 21 else self.node.label
        p.drawText(QRectF(-68, NODE_R + 2, 136, 16), Qt.AlignmentFlag.AlignHCenter, label)


class EdgeItem(QGraphicsLineItem):
    def __init__(self, src: str, dst: str, kind: str):
        super().__init__()
        self.src, self.dst, self.kind = src, dst, kind
        self.setZValue(1)
        self._set(False)

    def _set(self, hot: bool):
        c = QColor(120, 120, 120) if hot else QColor(45, 45, 45)
        self.setPen(QPen(c, 1.4 if hot else 1.0))

    def highlight(self, hot: bool):
        self._set(hot)


class GraphView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor(5, 5, 5))
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._pan = False
        self._pan_start = QPointF()

    def wheelEvent(self, e):
        factor = 1.18 if e.angleDelta().y() > 0 else 1 / 1.18
        cur = self.transform().m11()
        if (cur * factor) < 0.12 or (cur * factor) > 6:
            return
        self.scale(factor, factor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.itemAt(e.pos()) is None:
            self._pan = True
            self._pan_start = e.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._pan:
            delta = e.position() - self._pan_start
            self._pan_start = e.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._pan:
            self._pan = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            e.accept()
            return
        super().mouseReleaseEvent(e)


class IntelligenceGraphPage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__("INTELLIGENCE GRAPH",
                         "Relations entre entités de la base locale et un sous-graphe de démonstration "
                         "(synthétique, étiqueté). Molette : zoom · glisser le fond : déplacer · clic : sélection.",
                         parent)
        self.ctx = ctx
        self.graph: Graph | None = None
        self.node_items: dict[str, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []
        self._hidden_types: set[str] = set()

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, SCENE_W, SCENE_H)
        self.scene.selectionChanged.connect(self._on_selection)
        self.view = GraphView(self.scene)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.view, 1)

        # ----- panneau latéral
        self.side = QWidget()
        self.side.setFixedWidth(270)
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(10)
        self.search = QLineEdit(placeholderText="Rechercher un nœud…")
        self.search.textChanged.connect(self._search)
        sl.addWidget(self.search)
        btns = QHBoxLayout()
        self.relayout_btn = QPushButton("Réagencer")
        self.relayout_btn.clicked.connect(self._relayout)
        self.fit_btn = QPushButton("Recentrer")
        self.fit_btn.clicked.connect(self._fit)
        btns.addWidget(self.relayout_btn)
        btns.addWidget(self.fit_btn)
        sl.addLayout(btns)
        self.full_btn = QPushButton("Masquer le panneau")
        self.full_btn.clicked.connect(self._toggle_full)
        sl.addWidget(self.full_btn)

        sl.addWidget(section_label("Légende · filtres"))
        self.legend_box = QVBoxLayout()
        self.legend_box.setSpacing(3)
        sl.addLayout(self.legend_box)

        sl.addWidget(section_label("Détail"))
        self.detail = QTextBrowser()
        self.detail.setMinimumHeight(180)
        sl.addWidget(self.detail, 1)
        self.count_lbl = muted("")
        sl.addWidget(self.count_lbl)
        body.addWidget(self.side)
        self.root.addLayout(body, 1)
        self._reset_detail()

    # ------------------------------------------------------------ chargement
    def on_show(self):
        if self.graph is None:
            self._load()

    def _load(self):
        self.detail.setHtml("<p style='color:#888'>Construction du graphe…</p>")
        repo = self.ctx.repo

        def job():
            g = build_graph(repo, include_demo=True)
            return g, force_directed(g)

        run_async(job, on_done=self._build_scene, on_error=self._err)

    def _err(self, msg: str):
        self.detail.setHtml(f"<p style='color:#ff9a9a'>{msg}</p>")

    def _build_scene(self, result):
        graph, pos = result
        self.graph = graph
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        margin = 120
        for n in graph.nodes:
            x, y = pos.get(n.id, (0.5, 0.5))
            item = NodeItem(n)
            item.setPos(margin + x * (SCENE_W - 2 * margin), margin + y * (SCENE_H - 2 * margin))
            self.scene.addItem(item)
            self.node_items[n.id] = item
        for e in graph.edges:
            a, b = self.node_items.get(e.src), self.node_items.get(e.dst)
            if a is None or b is None:
                continue
            edge = EdgeItem(e.src, e.dst, e.kind)
            edge.setLine(a.x(), a.y(), b.x(), b.y())
            self.scene.addItem(edge)
            self.edge_items.append(edge)
        self._build_legend()
        self._fit()
        demo = sum(1 for n in graph.nodes if n.demo)
        self.count_lbl.setText(f"{len(graph.nodes)} nœuds · {len(graph.edges)} liens · "
                               f"{len(graph.nodes) - demo} réels, {demo} démo")
        self._reset_detail()

    # ------------------------------------------------------------ légende
    def _build_legend(self):
        while self.legend_box.count():
            w = self.legend_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        assert self.graph is not None
        for t in self.graph.types_present():
            cb = QCheckBox(f"{TYPE_LABELS.get(t, t)}")
            cb.setChecked(True)
            cb.toggled.connect(lambda on, tt=t: self._toggle_type(tt, on))
            self.legend_box.addWidget(cb)

    def _toggle_type(self, ntype: str, on: bool):
        if on:
            self._hidden_types.discard(ntype)
        else:
            self._hidden_types.add(ntype)
        for nid, item in self.node_items.items():
            item.setVisible(item.node.ntype not in self._hidden_types)
        for edge in self.edge_items:
            sa = self.node_items.get(edge.src)
            sb = self.node_items.get(edge.dst)
            edge.setVisible(bool(sa and sb and sa.isVisible() and sb.isVisible()))

    # ------------------------------------------------------------ interactions
    def _on_selection(self):
        items = [i for i in self.scene.selectedItems() if isinstance(i, NodeItem)]
        if not items:
            self._reset_detail()
            for it in self.node_items.values():
                it.set_dim(False)
            for e in self.edge_items:
                e.highlight(False)
            return
        node = items[0].node
        assert self.graph is not None
        nb = self.graph.neighbors(node.id)
        keep = nb | {node.id}
        for nid, it in self.node_items.items():
            it.set_dim(nid not in keep)
        for e in self.edge_items:
            e.highlight(e.src == node.id or e.dst == node.id)
        self._show_detail(node, nb)

    def _show_detail(self, node: Node, neighbors: set[str]):
        meta = "".join(f"<tr><td style='color:#888;padding-right:10px'>{k}</td><td>{v}</td></tr>"
                       for k, v in node.meta.items())
        nb_list = "".join(f"<li>{self.node_items[n].node.label} "
                          f"<span style='color:#777'>({TYPE_LABELS.get(self.node_items[n].node.ntype,'')})</span></li>"
                          for n in sorted(neighbors) if n in self.node_items)
        tag = " <span style='color:#ffe9b0'>· démo</span>" if node.demo else ""
        self.detail.setHtml(
            f"<h3 style='font-weight:300;letter-spacing:1px'>{node.label}{tag}</h3>"
            f"<div style='color:#888'>{TYPE_LABELS.get(node.ntype, node.ntype)}</div>"
            f"<table cellspacing=3>{meta}</table>"
            f"<div style='color:#888;margin-top:8px'>Relations ({len(neighbors)})</div><ul>{nb_list or '<li>—</li>'}</ul>"
        )

    def _reset_detail(self):
        self.detail.setHtml("<p style='color:#888'>Sélectionnez un nœud pour afficher ses relations. "
                            "Les nœuds en pointillés sont synthétiques (démonstration).</p>")

    def _search(self, text: str):
        text = text.strip().lower()
        first = None
        for item in self.node_items.values():
            m = bool(text) and text in item.node.label.lower()
            item.set_match(m)
            if m and first is None:
                first = item
        if first is not None:
            self.view.centerOn(first)

    def _relayout(self):
        if self.graph is None:
            return
        import random

        pos = force_directed(self.graph, seed=random.randint(1, 9999))
        margin = 120
        for nid, item in self.node_items.items():
            x, y = pos.get(nid, (0.5, 0.5))
            item.setPos(margin + x * (SCENE_W - 2 * margin), margin + y * (SCENE_H - 2 * margin))
        for edge in self.edge_items:
            a, b = self.node_items.get(edge.src), self.node_items.get(edge.dst)
            if a and b:
                edge.setLine(a.x(), a.y(), b.x(), b.y())
        self._fit()

    def _fit(self):
        if self.node_items:
            rect = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _toggle_full(self):
        self.side.setVisible(not self.side.isVisible())
        self.full_btn.setText("Afficher le panneau" if not self.side.isVisible()
                              else "Masquer le panneau")
