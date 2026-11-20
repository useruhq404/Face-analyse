"""Dashboard principal : barre latérale, pages, indicateurs, notifications."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow,
                               QProgressBar, QPushButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget)

from face_analyse import __app_name__, __author__, __version__
from face_analyse.core.paths import resource_path
from face_analyse.ui import theme
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.analysis import AnalysisPage
from face_analyse.ui.pages.camera import CameraPage
from face_analyse.ui.pages.common import Page
from face_analyse.ui.pages.database import DatabasePage
from face_analyse.ui.pages.history import HistoryPage
from face_analyse.ui.pages.osint import OsintPage
from face_analyse.ui.pages.settings import SettingsPage
from face_analyse.ui.widgets.dot_field import DotField
from face_analyse.ui.widgets.toast import ToastHost

NAV = [
    ("analysis", "FACE ANALYSIS", AnalysisPage),
    ("camera", "LIVE CAMERA", CameraPage),
    ("database", "FACE DATABASE", DatabasePage),
    ("osint", "OSINT SEARCH", OsintPage),
    ("history", "HISTORY", HistoryPage),
    ("settings", "SETTINGS", SettingsPage),
]


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{__app_name__} — fait par {__author__}")
        self.resize(1360, 840)
        self.setMinimumSize(1080, 680)

        # Fond : champ de points discret + image d'accueil très atténuée.
        bg = QPixmap(str(resource_path("images", "background.png")))
        self.field = DotField(None, bg if not bg.isNull() else None, spacing=28, image_opacity=0.10, fps=20)
        self.setCentralWidget(self.field)
        outer = QHBoxLayout(self.field)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ----- barre latérale
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(256)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 26, 0, 18)
        sl.setSpacing(2)
        brand = QLabel(__app_name__)
        brand.setFont(theme.title_font(13))
        brand.setStyleSheet(f"color: {theme.WHITE}; padding-left: 22px; background: transparent;")
        sig = QLabel(f"fait par {__author__}")
        sig.setStyleSheet(f"color: {theme.MUTED}; font-size: 8pt; letter-spacing: 3px; padding-left: 22px; background: transparent;")
        sl.addWidget(brand)
        sl.addWidget(sig)
        sl.addSpacing(28)

        self.stack = QStackedWidget()
        self.pages: dict[str, Page] = {}
        self.buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for i, (key, label, cls) in enumerate(NAV, start=1):
            page = cls(ctx)
            self.pages[key] = page
            self.stack.addWidget(page)
            btn = QPushButton(f"{i:02d}   {label}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            group.addButton(btn)
            self.buttons[key] = btn
            sl.addWidget(btn)
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, activated=lambda k=key: self.show_page(k))
        sl.addStretch(1)
        self.engine_lbl = QLabel("● moteur : chargement…")
        self.engine_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 8pt; padding-left: 22px; background: transparent;")
        self.gallery_lbl = QLabel("")
        self.gallery_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 8pt; padding-left: 22px; background: transparent;")
        ver = QLabel(f"v{__version__} · traitement local")
        ver.setStyleSheet(f"color: #444; font-size: 7pt; padding-left: 22px; background: transparent;")
        for w in (self.engine_lbl, self.gallery_lbl, ver):
            sl.addWidget(w)
        outer.addWidget(side)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self.stack, 1)
        outer.addWidget(content, 1)

        # ----- barre d'état
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_lbl = QLabel("Prêt")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(240)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        status.addWidget(self.status_lbl, 1)
        status.addPermanentWidget(self.progress)

        self.toasts = ToastHost(self.field)
        ctx.notify.connect(self.toasts.show_message)
        ctx.busy.connect(self._busy)
        ctx.engine_ready.connect(self._engine_ready)
        ctx.engine_failed.connect(lambda m: self.engine_lbl.setText("● moteur : indisponible"))
        ctx.gallery_changed.connect(self._gallery_changed)
        self._current: str | None = None

    # ------------------------------------------------------------ navigation
    def show_page(self, key: str):
        if key not in self.pages or key == self._current:
            self.buttons[key].setChecked(True)
            return
        if self._current:
            self.pages[self._current].on_hide()
        self._current = key
        page = self.pages[key]
        self.buttons[key].setChecked(True)
        self.stack.setCurrentWidget(page)
        page.on_show()
        fx = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", page)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start()
        self._page_anim = anim

    def fade_in(self):
        self.setWindowOpacity(0.0)
        self.show()
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(420)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._win_anim = anim

    # ------------------------------------------------------------ indicateurs
    def _busy(self, label: str, done: int, total: int):
        if total < 0:
            self.progress.hide()
            self.status_lbl.setText("Prêt")
            return
        self.status_lbl.setText(label)
        self.progress.show()
        if total == 0:
            self.progress.setRange(0, 0)  # indéterminé (traitement réel en cours)
        else:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _engine_ready(self):
        e = self.ctx.engine
        if e:
            self.engine_lbl.setText(f"● moteur : {e.detector.name} + {e.embedder.model_id}")
            self.engine_lbl.setStyleSheet(f"color: {theme.FG}; font-size: 8pt; padding-left: 22px; background: transparent;")

    def _gallery_changed(self):
        e = self.ctx.engine
        if e:
            self.gallery_lbl.setText(f"● base : {e.matcher.person_count} personne(s), {e.matcher.size} réf.")

    def closeEvent(self, e: QCloseEvent):
        for page in self.pages.values():
            page.on_hide()
        super().closeEvent(e)
