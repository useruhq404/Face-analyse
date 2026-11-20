"""OUTILS : IP Lookup et Username Tracker."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from face_analyse.osint.http import PoliteSession
from face_analyse.osint.iplookup import IpInfo, lookup
from face_analyse.osint.usernames import PLATFORMS, Presence, check_usernames
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, muted
from face_analyse.ui.workers import run_async


def _ip_html(i: IpInfo) -> str:
    rows = [
        ("Requête", i.query), ("IP", f"{i.ip}  ({i.ip_type})" if i.ip_type else i.ip),
        ("DNS inverse", i.hostname or "—"),
        ("Localisation", " · ".join(x for x in (i.city, i.region, i.country) if x) or "—"),
        ("Code postal", i.postal or "—"), ("Fuseau horaire", i.timezone or "—"),
        ("Opérateur (ASN)", " ".join(x for x in (i.asn, i.org or i.isp) if x) or "—"),
        ("Domaine opérateur", i.domain or "—"),
    ]
    flags = []
    if i.is_hosting:
        flags.append("hébergeur/datacenter probable")
    if i.is_anycast:
        flags.append("anycast")
    if i.is_proxy:
        flags.append("proxy/VPN signalé")
    body = "".join(f"<tr><td style='color:#888;padding-right:16px'>{escape(k)}</td>"
                   f"<td>{escape(str(v))}</td></tr>" for k, v in rows)
    extra = f"<p style='color:#ffe9b0'>Indices : {escape(', '.join(flags))}</p>" if flags else ""
    mapl = (f"<p><a href='{escape(i.map_url)}'>Voir la zone approximative sur la carte</a> "
            f"({i.latitude:.3f}, {i.longitude:.3f})</p>" if i.map_url else "")
    return (f"<table cellspacing=4>{body}</table>{extra}{mapl}"
            f"<p style='color:#888'>Sources : {escape(', '.join(i.sources))}. "
            "La géolocalisation IP indique la zone de l'opérateur, pas une adresse personnelle.</p>")


class IpLookupTab(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.input = QLineEdit(placeholderText="Adresse IP (1.1.1.1) ou domaine (exemple.com)")
        self.input.returnPressed.connect(self.run)
        self.btn = QPushButton("RECHERCHER")
        self.btn.setObjectName("Primary")
        self.btn.clicked.connect(self.run)
        bar.addWidget(self.input, 1)
        bar.addWidget(self.btn)
        lay.addLayout(bar)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        lay.addWidget(self.view, 1)
        lay.addWidget(muted("Données publiques approximatives (ipwho.is, ipinfo.io). "
                            "N'identifie pas une personne ni son domicile exact."))

    def run(self):
        value = self.input.text().strip()
        if not value:
            return
        self.btn.setEnabled(False)
        self.ctx.busy.emit("IP Lookup…", 0, 0)
        timeout = self.ctx.settings.osint.timeout_s
        run_async(lookup, value, timeout, on_done=self._done, on_error=self._error)
        self.ctx.log_event("ip_lookup", "lookup", {"query": value})

    def _done(self, info: IpInfo):
        self.btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.view.setHtml(_ip_html(info))
        self.ctx.repo.log_history("tools", "ip_lookup", f"IP Lookup : {info.query} → {info.ip}",
                                  {"query": info.query, "ip": info.ip, "country": info.country})

    def _error(self, msg: str):
        self.btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.view.setHtml(f"<p style='color:#ff9a9a'>{escape(msg)}</p>")
        self.ctx.notify.emit(msg, "error")


class UsernameTrackerTab(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.input = QLineEdit(placeholderText="Pseudonyme à pister (ex. john.doe)")
        self.input.returnPressed.connect(self.run)
        self.btn = QPushButton("PISTER")
        self.btn.setObjectName("Primary")
        self.btn.clicked.connect(self.run)
        bar.addWidget(self.input, 1)
        bar.addWidget(self.btn)
        lay.addLayout(bar)
        self.summary = muted("")
        lay.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Plateforme", "État", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._open)
        lay.addWidget(self.table, 1)
        lay.addWidget(muted("« Trouvé » signifie qu'un compte porte ce pseudo, pas qu'il appartient à "
                            "une personne précise. Le contenu des profils n'est pas récupéré."))
        self._rows: list = []

    def run(self):
        username = self.input.text().strip().lstrip("@")
        if not username:
            return
        self.btn.setEnabled(False)
        self.table.setRowCount(0)
        self.summary.setText("Recherche en cours…")
        http = PoliteSession(timeout=self.ctx.settings.osint.timeout_s)
        run_async(lambda progress: check_usernames(http, [username], PLATFORMS,
                                                    progress=lambda d, n: progress("Username Tracker", d, n)),
                  on_done=self._done, on_error=self._error,
                  on_progress=lambda l, d, n: self.ctx.busy.emit(l, d, n))
        self.ctx.log_event("username", "track", {"username": username})

    def _done(self, hits: list):
        self.btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        order = {Presence.FOUND: 0, Presence.UNKNOWN: 1, Presence.ABSENT: 2}
        self._rows = sorted(hits, key=lambda h: (order[h.presence], h.platform))
        found = sum(1 for h in hits if h.presence == Presence.FOUND)
        self.summary.setText(f"{found} compte(s) trouvé(s) sur {len(hits)} plateformes testées.")
        self.table.setRowCount(len(self._rows))
        for i, h in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(h.platform))
            state = QTableWidgetItem({"trouvé": "● trouvé", "absent": "absent", "indéterminé": "? indéterminé"}
                                     .get(h.presence.value, h.presence.value))
            self.table.setItem(i, 1, state)
            self.table.setItem(i, 2, QTableWidgetItem(h.url if h.presence == Presence.FOUND else ""))
        self.table.resizeColumnsToContents()
        if self._rows:
            self.ctx.repo.log_history("tools", "username_track",
                                      f"Username Tracker : {self._rows[0].username} → {found} profil(s)",
                                      {"username": self._rows[0].username, "found": found})

    def _error(self, msg: str):
        self.btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.summary.setText(msg)
        self.ctx.notify.emit(msg, "error")

    def _open(self, row: int, _col: int):
        if 0 <= row < len(self._rows) and self._rows[row].presence == Presence.FOUND:
            QDesktopServices.openUrl(QUrl(self._rows[row].url))


class ToolsPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("OUTILS",
                         "IP Lookup et Username Tracker : informations publiques sur une IP/un domaine ou un pseudonyme.",
                         parent, help_key="tools_ip")
        tabs = QTabWidget()
        tabs.addTab(IpLookupTab(ctx), "IP LOOKUP")
        tabs.addTab(UsernameTrackerTab(ctx), "USERNAME TRACKER")
        self.root.addWidget(tabs, 1)
