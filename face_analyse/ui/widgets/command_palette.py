"""Palette de commandes (Ctrl+K) : changement de module au clavier.

Même langage visuel que l'application : fond noir, monospace, sélection fine.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from face_analyse.ui import theme


class CommandPalette(QDialog):
    def __init__(self, commands: list[tuple[str, Callable[[], None]]], parent=None):
        super().__init__(parent)
        self.commands = commands
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedWidth(560)
        self.setStyleSheet(f"""
            QDialog {{ background: {theme.PANEL}; border: 1px solid {theme.LINE_2}; }}
            QLineEdit {{ background: {theme.BG}; border: none; border-bottom: 1px solid {theme.LINE_2};
                        padding: 14px 16px; font-family: {theme.mono_font_family()}; font-size: 12pt;
                        color: {theme.WHITE}; }}
            QListWidget {{ background: {theme.PANEL}; border: none; font-family: {theme.mono_font_family()};
                          outline: none; padding: 6px; }}
            QListWidget::item {{ padding: 8px 12px; color: {theme.FG}; letter-spacing: 1px; }}
            QListWidget::item:selected {{ background: #1e1e1e; color: {theme.WHITE}; }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.input = QLineEdit(placeholderText="› aller à un module…   (↑↓ pour choisir, ↵ pour ouvrir, Échap pour fermer)")
        self.list = QListWidget()
        self.list.setMaximumHeight(320)
        lay.addWidget(self.input)
        lay.addWidget(self.list)
        self.input.textChanged.connect(self._filter)
        self.list.itemActivated.connect(lambda _it: self._run())
        self.input.installEventFilter(self)
        self._filter("")

    def _filter(self, text: str):
        text = text.strip().lower()
        self.list.clear()
        for label, cb in self.commands:
            if text in label.lower():
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, cb)
                self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _run(self):
        item = self.list.currentItem()
        if item is not None:
            cb = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
            cb()

    def eventFilter(self, obj, ev):
        if obj is self.input and ev.type() == QKeyEvent.Type.KeyPress:
            key = ev.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.list.currentRow()
                row += 1 if key == Qt.Key.Key_Down else -1
                self.list.setCurrentRow(max(0, min(row, self.list.count() - 1)))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._run()
                return True
        return super().eventFilter(obj, ev)

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(e)

    @classmethod
    def open_for(cls, parent, commands):
        dlg = cls(commands, parent)
        dlg.input.setFocus()
        # centré sur la fenêtre parente, un peu au-dessus du milieu
        if parent is not None:
            g = parent.geometry()
            dlg.move(g.center().x() - dlg.width() // 2, g.top() + int(g.height() * 0.18))
        dlg.exec()
