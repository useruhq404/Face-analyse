"""CYBER LAB — apprendre l'offensif légalement : plateformes, lab isolé, méthodo.

Aucune attaque fournie : des ressources vers des cibles faites pour la pratique
(CTF, VMs vulnérables), un guide de lab isolé, et une méthodologie de pentest dont
la progression est sauvegardée en local. Le DoS reste étudié côté défense.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget)

from face_analyse.lab import progress
from face_analyse.lab.content import CHECKLIST, PLATFORMS, THEMES, total_items
from face_analyse.ui import theme
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, card, muted, section_label


class LabPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("CYBER LAB",
                         "Apprendre la sécurité offensive — légalement. Plateformes de challenges, montage d'un "
                         "lab isolé, et une méthodologie suivie. Tout se pratique sur des cibles faites pour ça.",
                         parent, help_key="lab")
        self.ctx = ctx
        self._done = progress.load_done()
        self._boxes: list[QCheckBox] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        col = QVBoxLayout(body)
        col.setSpacing(18)

        col.addWidget(self._build_methodology())
        col.addWidget(section_label("Plateformes légales · cibles faites pour la pratique"))
        col.addWidget(self._build_platforms())
        col.addWidget(section_label("Par thème · compétences et ressources officielles"))
        for w in self._build_themes():
            col.addWidget(w)
        col.addStretch(1)
        col.addWidget(muted("Rappel : ne pratique que sur TES machines, un lab isolé, ou avec une autorisation "
                            "écrite. Viser un système tiers sans accord est un délit (art. 323-1 et suivants)."))
        scroll.setWidget(body)
        self.root.addWidget(scroll, 1)

    # ------------------------------------------------------------ méthodologie
    _CHECK_QSS = (
        "QCheckBox { color: %s; spacing: 10px; padding: 3px 0; background: transparent; }"
        "QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid %s; background: %s; }"
        "QCheckBox::indicator:hover { border-color: %s; }"
        "QCheckBox::indicator:checked { background: %s; border-color: %s; }"
    ) % (theme.FG, theme.LINE_2, theme.PANEL, theme.WHITE, theme.WHITE, theme.WHITE)

    def _build_methodology(self) -> QWidget:
        wrap, lay = card()
        header = QVBoxLayout()
        header.setSpacing(2)
        header.addWidget(section_label("Méthodologie pentest · progression locale"))
        self.progress_lbl = QLabel()
        self.progress_lbl.setObjectName("Mono")
        header.addWidget(self.progress_lbl)
        lay.addLayout(header)

        for phase in CHECKLIST:
            ph = QLabel(phase.title)
            ph.setStyleSheet(f"color: {theme.WHITE}; letter-spacing: 1px; margin-top: 6px;")
            lay.addWidget(ph)
            for item_id, text in phase.items:
                box = QCheckBox(text)
                box.setStyleSheet(self._CHECK_QSS)
                box.setChecked(item_id in self._done)
                box.toggled.connect(lambda checked, i=item_id: self._toggle(i, checked))
                self._boxes.append(box)
                lay.addWidget(box)
        self._refresh_progress()
        return wrap

    def _toggle(self, item_id: str, checked: bool):
        if checked:
            self._done.add(item_id)
        else:
            self._done.discard(item_id)
        progress.save_done(self._done)
        self._refresh_progress()

    def _refresh_progress(self):
        total = total_items()
        done = sum(1 for b in self._boxes if b.isChecked()) if self._boxes else len(self._done)
        pct = round(100 * done / total) if total else 0
        bar = "█" * (pct // 5) + "·" * (20 - pct // 5)
        self.progress_lbl.setText(f"{done}/{total}  [{bar}]  {pct}%")

    # -------------------------------------------------------------- plateformes
    def _build_platforms(self) -> QWidget:
        wrap, lay = card()
        grid = QGridLayout()
        grid.setSpacing(10)
        for i, p in enumerate(PLATFORMS):
            cell = QLabel(
                f"<a href='{escape(p.url)}' style='color:{theme.WHITE};text-decoration:none'>{escape(p.name)}</a>"
                f"  <span style='color:{theme.MUTED}'>· {escape(p.level)}</span>"
                f"<br><span style='color:{theme.MUTED}'>{escape(p.desc)}</span>")
            cell.setTextFormat(Qt.TextFormat.RichText)
            cell.setOpenExternalLinks(True)
            cell.setWordWrap(True)
            grid.addWidget(cell, i // 2, i % 2)
        lay.addLayout(grid)
        return wrap

    # ------------------------------------------------------------------ thèmes
    def _build_themes(self) -> list[QWidget]:
        cards = []
        for t in THEMES:
            wrap, lay = card()
            title = QLabel(t.title)
            title.setStyleSheet(f"color: {theme.WHITE}; letter-spacing: 1px; font-size: 12pt;")
            lay.addWidget(title)
            lay.addWidget(muted(t.summary))
            skills = QLabel("<br>".join(f"<span style='color:{theme.MUTED}'>▸</span> {escape(s)}" for s in t.skills))
            skills.setTextFormat(Qt.TextFormat.RichText)
            skills.setWordWrap(True)
            lay.addWidget(skills)
            if t.resources:
                res = QLabel(" · ".join(
                    f"<a href='{escape(u)}' style='color:{theme.WHITE}'>{escape(label)}</a>"
                    for label, u in t.resources))
                res.setTextFormat(Qt.TextFormat.RichText)
                res.setOpenExternalLinks(True)
                res.setWordWrap(True)
                lay.addWidget(res)
            cards.append(wrap)
        return cards
