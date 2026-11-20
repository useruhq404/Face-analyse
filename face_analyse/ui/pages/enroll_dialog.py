"""Dialogue d'enrôlement : personne existante ou nouvelle (consentement obligatoire)."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                               QVBoxLayout)

from face_analyse.database.repository import CONSENT_TEXT, Repository


class EnrollDialog(QDialog):
    NEW = -1

    def __init__(self, repo: Repository, parent=None, preselect: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Enregistrer ce visage")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.person = QComboBox()
        self.person.addItem("— Nouvelle personne —", self.NEW)
        for p in repo.list_people():
            self.person.addItem(f"{p.display_name}  ({p.photo_count} photo(s))", p.id)
        if preselect is not None:
            idx = self.person.findData(preselect)
            if idx >= 0:
                self.person.setCurrentIndex(idx)
        self.first = QLineEdit()
        self.last = QLineEdit()
        form.addRow("Personne", self.person)
        form.addRow("Prénom", self.first)
        form.addRow("Nom", self.last)
        lay.addLayout(form)
        consent_text = QLabel(CONSENT_TEXT)
        consent_text.setWordWrap(True)
        consent_text.setObjectName("Muted")
        self.consent = QCheckBox("La personne a donné son consentement explicite")
        lay.addWidget(consent_text)
        lay.addWidget(self.consent)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self.person.currentIndexChanged.connect(self._refresh)
        self.first.textChanged.connect(self._refresh)
        self.last.textChanged.connect(self._refresh)
        self.consent.toggled.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        new = self.person.currentData() == self.NEW
        self.first.setEnabled(new)
        self.last.setEnabled(new)
        self.consent.setVisible(new)
        ok = (not new) or (self.consent.isChecked() and (self.first.text().strip() or self.last.text().strip()))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(ok))

    def resolve(self, repo: Repository) -> int:
        pid = self.person.currentData()
        if pid == self.NEW:
            pid = repo.add_person(self.first.text(), self.last.text(), consent=self.consent.isChecked())
        return int(pid)
