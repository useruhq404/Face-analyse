"""SYSTEM OVERVIEW — l'écran d'entrée de l'environnement de recherche.

Composition cinématographique, données **réelles** (base locale et historique).
En l'absence d'activité, des états vides soignés remplacent toute statistique
inventée.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget)

from face_analyse import __version__
from face_analyse.core.paths import resource_path
from face_analyse.ui import theme
from face_analyse.ui.pages.common import Page, muted, section_label
from face_analyse.ui.widgets.charts import ActivityDots, BarList

#: (clé de navigation, identifiant, nom, description)
MODULES = [
    ("analysis", "01", "FACE ANALYSIS", "Détection, empreintes, correspondances"),
    ("camera", "02", "LIVE CAMERA", "Reconnaissance en direct, base consentante"),
    ("database", "03", "FACE DATABASE", "Personnes, photos, empreintes chiffrées"),
    ("osint", "04", "OSINT SEARCH", "Sources publiques, recherche par nom"),
    ("graph", "05", "INTEL GRAPH", "Graphe relationnel interactif"),
    ("datalab", "06", "DATA LAB", "Import CSV/JSON/TXT, statistiques"),
    ("timeline", "07", "TIMELINE", "Chronologie interactive des événements"),
    ("tools", "08", "IP · USERNAME", "IP, pseudo, e-mail, téléphone, générateurs"),
    ("console", "09", "CONSOLE", "Terminal : recon réseau, crypto, apprendre"),
    ("loadtest", "10", "STRESS TEST", "Test de charge de tes propres cibles"),
    ("history", "11", "HISTORY", "Journal local horodaté"),
    ("guide", "12", "GUIDE / INFO", "Rôle et fonctionnement des modules"),
    ("settings", "13", "SETTINGS", "Moteur, compte, données"),
]

_MODULE_LABELS = {
    "analysis": "Analyse", "camera": "Caméra", "database": "Base", "osint": "OSINT",
    "tools": "Outils", "ip_lookup": "IP Lookup", "username": "Username", "nav": "Navigation",
    "app": "Application", "auth": "Compte",
}


class StatTile(QFrame):
    def __init__(self, label: str, value: str = "—"):
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        self.value_lbl = QLabel(value)
        f = QFont(theme.ui_font_family(), 22)
        f.setWeight(QFont.Weight.Light)
        self.value_lbl.setFont(f)
        self.value_lbl.setStyleSheet(f"color: {theme.WHITE};")
        l = QLabel(label.upper())
        l.setStyleSheet(f"color: {theme.MUTED}; font-size: 8pt; letter-spacing: 2px;")
        lay.addWidget(self.value_lbl)
        lay.addWidget(l)

    def set_value(self, v: str):
        self.value_lbl.setText(v)


class ModuleCard(QFrame):
    clicked = Signal(str)

    def __init__(self, key: str, num: str, name: str, desc: str, status: str = "actif"):
        super().__init__()
        self.key = key
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        top = QHBoxLayout()
        num_lbl = QLabel(num)
        num_lbl.setStyleSheet(f"color: {theme.MUTED}; font-family: {theme.mono_font_family()}; font-size: 9pt;")
        dot = QLabel("●  " + status)
        dot.setStyleSheet(f"color: {theme.OK}; font-size: 8pt; letter-spacing: 1px;")
        top.addWidget(num_lbl)
        top.addStretch(1)
        top.addWidget(dot)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {theme.WHITE}; letter-spacing: 2px;")
        nf = QFont(theme.ui_font_family(), 11)
        name_lbl.setFont(nf)
        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("Muted")
        desc_lbl.setWordWrap(True)
        lay.addLayout(top)
        lay.addWidget(name_lbl)
        lay.addWidget(desc_lbl)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)

    def enterEvent(self, e):
        self.setStyleSheet("QFrame#Card { border-color: #ffffff; }")

    def leaveEvent(self, e):
        self.setStyleSheet("")


class OverviewPage(Page):
    navigate = Signal(str)

    def __init__(self, ctx, parent=None):
        super().__init__("SYSTEM OVERVIEW",
                         "Environnement de recherche et d'intelligence numérique — traitement local, "
                         "données réelles.", parent)
        self.ctx = ctx

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        col = QVBoxLayout(body)
        col.setSpacing(18)

        # ---- bandeau : emblème + statut système
        banner = QHBoxLayout()
        banner.setSpacing(18)
        self.emblem = QLabel()
        pix = QPixmap(str(resource_path("images", "emblem.png")))
        if not pix.isNull():
            self.emblem.setPixmap(pix.scaled(108, 108, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        banner.addWidget(self.emblem, 0, Qt.AlignmentFlag.AlignTop)

        tiles_wrap = QVBoxLayout()
        tiles_wrap.setSpacing(8)
        tiles_wrap.addWidget(section_label("System status"))
        self.tiles_row = QGridLayout()
        self.tiles_row.setSpacing(8)
        self.tiles = {
            "persons": StatTile("Personnes"), "photos": StatTile("Photos"),
            "embeddings": StatTile("Empreintes"), "events": StatTile("Événements"),
            "modules": StatTile("Modules"), "engine": StatTile("Moteur"),
        }
        for i, t in enumerate(self.tiles.values()):
            self.tiles_row.addWidget(t, 0, i)
        tiles_wrap.addLayout(self.tiles_row)
        self.health = muted("")
        tiles_wrap.addWidget(self.health)
        banner.addLayout(tiles_wrap, 1)
        col.addLayout(banner)

        # ---- activité + répartition
        mid = QHBoxLayout()
        mid.setSpacing(18)
        act_col = QVBoxLayout()
        act_col.setSpacing(6)
        act_col.addWidget(section_label("Research activity · 14 jours"))
        self.activity = ActivityDots()
        act_col.addWidget(self.activity)
        mid.addLayout(act_col, 3)
        dist_col = QVBoxLayout()
        dist_col.setSpacing(6)
        dist_col.addWidget(section_label("Par module"))
        self.usage = BarList()
        dist_col.addWidget(self.usage)
        dist_col.addStretch(1)
        mid.addLayout(dist_col, 2)
        col.addLayout(mid)

        # ---- modules
        col.addWidget(section_label("Module status"))
        self.module_grid = QGridLayout()
        self.module_grid.setSpacing(10)
        for i, (key, num, name, desc) in enumerate(MODULES):
            card = ModuleCard(key, num, name, desc)
            card.clicked.connect(self.navigate.emit)
            self.module_grid.addWidget(card, i // 4, i % 4)
        col.addLayout(self.module_grid)

        # ---- activité récente
        col.addWidget(section_label("Recent activity"))
        self.recent = QLabel()
        self.recent.setObjectName("Mono")
        self.recent.setTextFormat(Qt.TextFormat.RichText)
        self.recent.setWordWrap(True)
        self.recent.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.recent)

        col.addStretch(1)
        ver = muted(f"FACE ANALYSE v{__version__} · traitement local · chiffré")
        col.addWidget(ver)
        scroll.setWidget(body)
        self.root.addWidget(scroll, 1)

        ctx.engine_ready.connect(self.refresh)
        ctx.gallery_changed.connect(self.refresh)

    # ------------------------------------------------------------ données
    def on_show(self):
        self.refresh()

    def refresh(self):
        repo = self.ctx.repo
        try:
            stats = repo.stats()
            events = repo.history_count()
            activity = repo.activity_by_day(14)
            usage = repo.module_usage()
            recent = repo.history(limit=10)
        except Exception:  # noqa: BLE001 - l'overview ne doit jamais planter l'app
            return
        self.tiles["persons"].set_value(str(stats["persons"]))
        self.tiles["photos"].set_value(str(stats["photos"]))
        self.tiles["embeddings"].set_value(str(stats["embeddings"]))
        self.tiles["events"].set_value(str(events))
        self.tiles["modules"].set_value(str(len(MODULES)))
        self.tiles["engine"].set_value("OK" if self.ctx.engine else "…")

        # santé système
        parts = []
        parts.append(f"moteur : {'chargé' if self.ctx.engine else 'chargement…'}")
        if self.ctx.auth is not None:
            acc = self.ctx.account
            parts.append(f"compte : {'@' + acc.pseudo if acc else 'non connecté'}")
        else:
            parts.append("mode autonome (sans compte)")
        try:
            size = repo.db_path.stat().st_size
            parts.append(f"stockage local : {size / 1024:.0f} Ko")
        except OSError:
            pass
        self.health.setText("   ·   ".join(parts))

        self.activity.set_data(activity)
        self.usage.set_data([(_MODULE_LABELS.get(m, m), n) for m, n in usage])

        if recent:
            lines = []
            for h in recent:
                ts = h.timestamp.astimezone() if h.timestamp.tzinfo else h.timestamp
                mod = _MODULE_LABELS.get(h.module, h.module)
                lines.append(
                    f"<span style='color:{theme.MUTED}'>{ts:%d/%m %H:%M:%S}</span>  "
                    f"<span style='color:{theme.WHITE}'>{mod}</span> · {h.summary}"
                )
            self.recent.setText("<br>".join(lines))
        else:
            self.recent.setText(
                f"<span style='color:{theme.MUTED}'>Aucune activité enregistrée pour l'instant. "
                "Lancez une analyse, une recherche OSINT ou un IP Lookup — les événements "
                "apparaîtront ici et dans HISTORY.</span>"
            )
