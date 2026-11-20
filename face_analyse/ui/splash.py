"""Écran d'accueil : petite fenêtre 750×450 avec le titre, la signature,
un menu d'actions numérotées (1-6) et le bouton ENTER."""

from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, QSequentialAnimationGroup,
                            Qt, Signal)
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPixmap
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from face_analyse import __app_name__, __signature__, __version__
from face_analyse.core.paths import resource_path
from face_analyse.ui import theme
from face_analyse.ui.widgets.dot_field import DotField
from face_analyse.ui.widgets.pixel_title import PixelTitle

#: (clé de page, libellé) — l'ordre définit les raccourcis 1 à 6.
MENU = [
    ("analysis", "ANALYSE PHOTO"),
    ("camera", "CAMÉRA LIVE"),
    ("database", "BASE DE VISAGES"),
    ("osint", "RECHERCHE OSINT"),
    ("tools", "IP · USERNAME"),
    ("history", "HISTORIQUE"),
    ("guide", "GUIDE / INFO"),
    ("settings", "PARAMÈTRES"),
]


class MenuItem(QPushButton):
    def __init__(self, index: int, label: str, parent=None):
        super().__init__(f"{index:02d}   {label}", parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"""QPushButton {{ border: none; text-align: left; padding: 3px 10px; color: {theme.MUTED};
                letter-spacing: 3px; font-size: 9pt; background: transparent; }}
                QPushButton:hover {{ color: {theme.WHITE}; }}
                QPushButton:checked {{ color: {theme.WHITE}; border-left: 1px solid {theme.WHITE}; }}"""
        )


class WelcomeWindow(QWidget):
    #: émis avec la clé de la page choisie
    entered = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(__app_name__)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(750, 450)  # taille fixe : la composition est pensée pour ce format
        self._drag: QPoint | None = None
        self._selected = 0

        pix = QPixmap(str(resource_path("images", "background.png")))
        self.field = DotField(self, pix if not pix.isNull() else None, spacing=18, image_opacity=0.55)
        self.field.setGeometry(self.rect())

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 18, 26, 22)

        top = QHBoxLayout()
        ver = QLabel(f"v{__version__}  ·  LOCAL  ·  CHIFFRÉ")
        ver.setStyleSheet(f"color: {theme.MUTED}; font-size: 7pt; letter-spacing: 3px; background: transparent;")
        close = QPushButton("✕")
        close.setFixedSize(26, 26)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"QPushButton {{ border: none; color: {theme.MUTED}; padding: 0; }}"
                            f"QPushButton:hover {{ color: {theme.WHITE}; }}")
        close.clicked.connect(self.close)
        top.addWidget(ver)
        top.addStretch(1)
        top.addWidget(close)
        root.addLayout(top)
        root.addStretch(3)

        self.title = PixelTitle(__app_name__, pixel=4, gap=1, max_drip=7)
        glow = QGraphicsDropShadowEffect(self.title)
        glow.setBlurRadius(28)
        glow.setOffset(0, 0)
        glow.setColor(QColor(255, 255, 255, 150))
        self.title.setGraphicsEffect(glow)
        self._glow = glow

        self.signature = QLabel(__signature__)
        self.signature.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signature.setStyleSheet(f"color: {theme.MUTED}; background: transparent; font-size: 6pt;"
                                     f"font-family: '{theme.mono_font_family()}'; letter-spacing: 2px;")

        root.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(2)
        root.addWidget(self.signature)
        root.addStretch(2)

        bottom = QHBoxLayout()
        menu_box = QVBoxLayout()
        menu_box.setSpacing(1)
        self.items: list[MenuItem] = []
        for i, (_key, label) in enumerate(MENU, start=1):
            item = MenuItem(i, label)
            item.clicked.connect(lambda _=False, idx=i - 1: self._select(idx))
            menu_box.addWidget(item)
            self.items.append(item)
        bottom.addLayout(menu_box)
        bottom.addStretch(1)

        self.enter_btn = QPushButton("ENTER")
        self.enter_btn.setObjectName("Primary")
        self.enter_btn.setFixedSize(150, 40)
        self.enter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enter_btn.clicked.connect(self._enter)
        hint = QLabel("1–8 pour choisir · ↵ pour entrer")
        hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 7pt; letter-spacing: 1px; background: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        right = QVBoxLayout()
        right.addStretch(1)
        right.addWidget(self.enter_btn, 0, Qt.AlignmentFlag.AlignRight)
        right.addSpacing(6)
        right.addWidget(hint)
        bottom.addLayout(right)
        root.addLayout(bottom)

        self._select(0)
        self._intro_animation()

    # ------------------------------------------------------------ animation
    def _fade(self, widget: QWidget, duration: int, delay_group: QSequentialAnimationGroup | None = None):
        fx = widget.graphicsEffect()
        if not isinstance(fx, QGraphicsOpacityEffect):
            fx = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(fx)
        fx.setOpacity(0.0)
        anim = QPropertyAnimation(fx, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    def _intro_animation(self):
        self.setWindowOpacity(0.0)
        win = QPropertyAnimation(self, b"windowOpacity", self)
        win.setDuration(450)
        win.setStartValue(0.0)
        win.setEndValue(1.0)

        glow_anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        glow_anim.setDuration(1600)
        glow_anim.setStartValue(0.0)
        glow_anim.setKeyValueAt(0.5, 46.0)
        glow_anim.setEndValue(24.0)
        glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        seq = QSequentialAnimationGroup(self)
        seq.addAnimation(win)
        par = QParallelAnimationGroup(self)
        par.addAnimation(glow_anim)
        par.addAnimation(self._fade(self.signature, 1400))
        for i, item in enumerate(self.items):
            a = self._fade(item, 500 + 90 * i)
            par.addAnimation(a)
        par.addAnimation(self._fade(self.enter_btn, 1200))
        seq.addAnimation(par)
        seq.start()
        self._intro = seq

    def _outro_and_emit(self, key: str):
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(380)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(lambda: (self.entered.emit(key), self.close()))
        anim.start()
        self._outro = anim

    # ------------------------------------------------------------ interaction
    def _select(self, idx: int):
        self._selected = idx % len(MENU)
        for i, item in enumerate(self.items):
            item.setChecked(i == self._selected)

    def _enter(self):
        self.enter_btn.setEnabled(False)
        self._outro_and_emit(MENU[self._selected][0])

    def keyPressEvent(self, e: QKeyEvent):
        key = e.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_8:
            self._select(key - Qt.Key.Key_1)
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Tab):
            self._select(self._selected + 1)
        elif key == Qt.Key.Key_Up:
            self._select(self._selected - 1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._enter()
        elif key == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
