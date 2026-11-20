"""Éléments communs aux pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QVBoxLayout, QWidget

from face_analyse.engine.preprocessing import SUPPORTED_EXTENSIONS

IMAGE_FILTER = "Images (" + " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS)) + ")"

SIMILARITY_NOTICE = (
    "Le score est une similarité cosinus entre empreintes faciales (−1 à 1). "
    "Ce n'est PAS une probabilité d'identité : deux personnes différentes peuvent se ressembler, "
    "et une même personne peut obtenir un score faible (angle, lumière, âge, qualité)."
)


class Page(QWidget):
    """Page avec en-tête (titre + sous-titre)."""

    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(34, 26, 34, 22)
        self.root.setSpacing(14)
        h1 = QLabel(title)
        h1.setObjectName("H1")
        h2 = QLabel(subtitle)
        h2.setObjectName("Muted")
        h2.setWordWrap(True)
        self.root.addWidget(h1)
        self.root.addWidget(h2)

    def on_show(self) -> None:
        """Appelé quand la page devient visible."""

    def on_hide(self) -> None:
        """Appelé quand la page est quittée."""


def card(parent=None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(parent)
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(8)
    return frame, lay


def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("H2")
    return lbl


def muted(text: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    lbl.setWordWrap(wrap)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


def pick_images(parent: QWidget, multiple: bool = False) -> list[str]:
    if multiple:
        files, _ = QFileDialog.getOpenFileNames(parent, "Choisir des photos", "", IMAGE_FILTER)
        return files
    file, _ = QFileDialog.getOpenFileName(parent, "Choisir une photo", "", IMAGE_FILTER)
    return [file] if file else []
