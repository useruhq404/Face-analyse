"""HISTORY : journal local des actions (analyses, enrôlements, recherches)."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTextBrowser)

from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page

MODULES = [("Tous", None), ("Analyse", "analysis"), ("Caméra", "camera"), ("Base", "database"), ("OSINT", "osint")]


class HistoryPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("HISTORY", "Historique local horodaté de toutes les opérations.", parent)
        self.ctx = ctx
        bar = QHBoxLayout()
        self.filter = QComboBox()
        for label, key in MODULES:
            self.filter.addItem(label, key)
        self.filter.currentIndexChanged.connect(self.reload)
        refresh = QPushButton("ACTUALISER")
        refresh.clicked.connect(self.reload)
        clear = QPushButton("EFFACER L'HISTORIQUE")
        clear.setObjectName("Danger")
        clear.clicked.connect(self._clear)
        bar.addWidget(self.filter)
        bar.addWidget(refresh)
        bar.addStretch(1)
        bar.addWidget(clear)
        self.root.addLayout(bar)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date (heure locale)", "Module", "Action", "Résumé"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.currentCellChanged.connect(lambda r, *_: self._detail(r))
        self.root.addWidget(self.table, 1)
        self.details = QTextBrowser()
        self.details.setMaximumHeight(120)
        self.root.addWidget(self.details)
        self._entries = []

    def on_show(self):
        self.reload()

    def reload(self):
        self._entries = self.ctx.repo.history(self.filter.currentData())
        self.table.setRowCount(len(self._entries))
        for i, h in enumerate(self._entries):
            ts = h.timestamp.astimezone() if h.timestamp.tzinfo else h.timestamp
            for j, text in enumerate([f"{ts:%d/%m/%Y %H:%M:%S}", h.module, h.action, h.summary]):
                self.table.setItem(i, j, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()

    def _detail(self, row: int):
        if 0 <= row < len(self._entries):
            try:
                pretty = json.dumps(json.loads(self._entries[row].details_json), indent=2, ensure_ascii=False)
            except ValueError:
                pretty = self._entries[row].details_json
            self.details.setPlainText(pretty)

    def _clear(self):
        if QMessageBox.question(self, "Historique", "Effacer tout l'historique ?") == QMessageBox.StandardButton.Yes:
            self.ctx.repo.clear_history()
            self.reload()
            self.ctx.notify.emit("Historique effacé.", "success")
