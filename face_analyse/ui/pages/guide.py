"""GUIDE : explication de chaque module (à quoi ça sert, comment ça marche)."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QTextBrowser

from face_analyse import __app_name__, __signature__, __version__
from face_analyse.help_content import TOPICS, HelpTopic
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page


def topic_html(t: HelpTopic) -> str:
    steps = "".join(f"<li>{escape(s)}</li>" for s in t.steps)
    cautions = "".join(f"<li>{escape(c)}</li>" for c in t.cautions)
    return f"""
    <h2 style="font-weight:300;letter-spacing:3px">{escape(t.title)}</h2>
    <h3 style="color:#aaa;font-weight:400">À QUOI ÇA SERT</h3><p>{escape(t.purpose)}</p>
    <h3 style="color:#aaa;font-weight:400">COMMENT ÇA MARCHE</h3><p>{escape(t.how)}</p>
    <h3 style="color:#aaa;font-weight:400">UTILISATION</h3><ol>{steps}</ol>
    <h3 style="color:#ffe9b0;font-weight:400">À SAVOIR</h3><ul style="color:#ddd">{cautions}</ul>
    """


class GuidePage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("GUIDE",
                         "Chaque module expliqué : à quoi il sert, comment il fonctionne et comment l'utiliser.", parent)
        self.ctx = ctx
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumWidth(240)
        for t in TOPICS:
            item = QListWidgetItem(t.title)
            item.setData(Qt.ItemDataRole.UserRole, t.key)
            self.list.addItem(item)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.list.currentRowChanged.connect(self._show)
        body.addWidget(self.list)
        body.addWidget(self.view, 1)
        self.root.addLayout(body, 1)
        self.list.setCurrentRow(0)

    def _show(self, row: int):
        if 0 <= row < len(TOPICS):
            self.view.setHtml(topic_html(TOPICS[row]))

    def show_topic(self, key: str):
        for i, t in enumerate(TOPICS):
            if t.key == key:
                self.list.setCurrentRow(i)
                return

    def on_show(self):
        header = (f"<p style='color:#888'>{escape(__app_name__)} v{__version__} · {escape(__signature__)}</p>")
        if self.view.toPlainText().strip() == "":
            self.view.setHtml(header)
