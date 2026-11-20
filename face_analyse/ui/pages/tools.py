"""OUTILS : IP Lookup et Username Tracker."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from face_analyse.osint import generators as gen
from face_analyse.osint.email import EmailInfo
from face_analyse.osint.email import investigate as email_investigate
from face_analyse.osint.http import PoliteSession
from face_analyse.osint.images import NOTICE as IMG_NOTICE
from face_analyse.osint.images import reverse_image_links
from face_analyse.osint.iplookup import IpInfo, lookup
from face_analyse.osint.phone import PhoneInfo
from face_analyse.osint.phone import investigate as phone_investigate
from face_analyse.osint.usernames import PLATFORMS, Presence, check_usernames, profile_links
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, muted
from face_analyse.ui.workers import run_async


def _links_html(links: list[tuple[str, str]]) -> str:
    return " · ".join(f"<a href='{escape(u)}'>{escape(label)}</a>" for label, u in links)


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
        self.view.document().setDefaultStyleSheet('a{color:#ffffff;text-decoration:underline}')
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
        self.links_view = QTextBrowser()
        self.links_view.setOpenExternalLinks(True)
        self.links_view.setMaximumHeight(220)
        self.links_view.document().setDefaultStyleSheet('a{color:#ffffff;text-decoration:none}')
        lay.addWidget(self.links_view)
        lay.addWidget(muted("Liens profil direct : ces réseaux (Instagram, TikTok, Snapchat, LinkedIn, Discord…) "
                            "interdisent la collecte automatique — ouvre-les toi-même dans le navigateur."))
        self._rows: list = []

    def run(self):
        username = self.input.text().strip().lstrip("@")
        if not username:
            return
        self.btn.setEnabled(False)
        self.table.setRowCount(0)
        self.summary.setText("Recherche en cours…")
        self._show_profile_links(username)
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

    def _show_profile_links(self, username: str):
        links = profile_links(username)
        if not links:
            self.links_view.setHtml("")
            return
        by_cat: dict[str, list[tuple[str, str, str, str]]] = {}
        for name, cat, url, note in links:
            by_cat.setdefault(cat, []).append((name, cat, url, note))
        parts = [f"<p style='color:#888'>Liens profil direct « {escape(username)} » "
                 f"— {len(links)} réseaux, à ouvrir dans le navigateur :</p>"]
        for cat, items in by_cat.items():
            chips = " · ".join(
                f"<a href='{escape(u)}' title='{escape(nt)}'>{escape(nm)}</a>" for nm, _c, u, nt in items)
            parts.append(f"<p><span style='color:#666'>{escape(cat.upper())}</span><br>{chips}</p>")
        self.links_view.setHtml("".join(parts))


def _email_html(e: EmailInfo) -> str:
    rows = [("Adresse", e.email), ("Domaine", f"{e.domain} ({e.provider_type})")]
    body = "".join(f"<tr><td style='color:#888;padding-right:16px'>{escape(k)}</td><td>{escape(str(v))}</td></tr>"
                   for k, v in rows)
    grav = ""
    if e.gravatar_found and e.gravatar:
        g = e.gravatar
        accts = " · ".join(f"<a href='{escape(u)}'>{escape(name or 'profil')}</a>" for name, u in g.accounts) or "—"
        grav = (f"<h3 style='font-weight:300'>Profil Gravatar public</h3>"
                f"<table cellspacing=3><tr><td style='color:#888'>Pseudo</td><td>{escape(g.username)}</td></tr>"
                f"<tr><td style='color:#888'>Nom affiché</td><td>{escape(g.display_name)}</td></tr>"
                f"<tr><td style='color:#888'>Localisation</td><td>{escape(g.location) or '—'}</td></tr>"
                f"<tr><td style='color:#888'>Comptes liés</td><td>{accts}</td></tr>"
                f"<tr><td style='color:#888'>Page</td><td><a href='{escape(g.profile_url)}'>{escape(g.profile_url)}</a></td></tr></table>")
    else:
        grav = "<div style='color:#888'>Aucun profil Gravatar public pour cette adresse.</div>"
    cands = ", ".join(escape(c) for c in e.username_candidates) or "—"
    return (f"<table cellspacing=4>{body}</table>{grav}"
            f"<h3 style='font-weight:300'>Pseudonymes à tester</h3><div>{cands}</div>"
            f"<h3 style='font-weight:300'>Recherches (navigateur)</h3><div>{_links_html(e.links)}</div>"
            f"<p style='color:#888'>Sources publiques uniquement : profil Gravatar volontairement publié + liens. "
            "Aucun accès à un compte, aucune vérification de mot de passe.</p>")


def _phone_html(p: PhoneInfo) -> str:
    state = "valide" if p.valid else ("possible mais non valide" if p.possible else "non valide")
    rows = [("Saisie", p.raw), ("État", state), ("Pays", f"{p.region} ({p.country} +{p.country_code})"),
            ("Opérateur probable", p.carrier or "—"), ("Type de ligne", p.line_type),
            ("Fuseaux", ", ".join(p.timezones) or "—"),
            ("Formats", f"{p.e164} · {p.international} · {p.national}")]
    body = "".join(f"<tr><td style='color:#888;padding-right:16px'>{escape(k)}</td><td>{escape(str(v))}</td></tr>"
                   for k, v in rows)
    note = f"<p style='color:#ffe9b0'>{escape(p.note)}</p>" if p.note else ""
    return (f"<table cellspacing=4>{body}</table>{note}"
            f"<h3 style='font-weight:300'>Recherches (navigateur)</h3><div>{_links_html(p.links)}</div>"
            f"<p style='color:#888'>Métadonnées du plan de numérotation (hors ligne) + liens. "
            "Pas d'annuaire inversé, pas d'appel.</p>")


class EmailTab(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.input = QLineEdit(placeholderText="adresse@exemple.com")
        self.input.returnPressed.connect(self.run)
        self.btn = QPushButton("ANALYSER")
        self.btn.setObjectName("Primary")
        self.btn.clicked.connect(self.run)
        bar.addWidget(self.input, 1)
        bar.addWidget(self.btn)
        lay.addLayout(bar)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.document().setDefaultStyleSheet('a{color:#ffffff;text-decoration:underline}')
        lay.addWidget(self.view, 1)
        lay.addWidget(muted("Profil public Gravatar (si publié) + pistes + liens. Sources publiques uniquement."))

    def run(self):
        email = self.input.text().strip()
        if not email:
            return
        self.btn.setEnabled(False)
        self.ctx.busy.emit("Analyse e-mail…", 0, 0)
        http = PoliteSession(timeout=self.ctx.settings.osint.timeout_s)
        run_async(email_investigate, email, http, on_done=self._done, on_error=self._err)
        self.ctx.log_event("email", "investigate", {})

    def _done(self, e: EmailInfo):
        self.btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.view.setHtml(_email_html(e))
        self.ctx.repo.log_history("tools", "email", f"Analyse e-mail : {e.domain} (gravatar={e.gravatar_found})",
                                  {"domain": e.domain, "gravatar": e.gravatar_found})

    def _err(self, msg: str):
        self.btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.view.setHtml(f"<p style='color:#ff9a9a'>{escape(msg)}</p>")
        self.ctx.notify.emit(msg, "error")


class PhoneTab(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.input = QLineEdit(placeholderText="+33 6 12 34 56 78  (ou format local)")
        self.input.returnPressed.connect(self.run)
        self.region = QLineEdit(placeholderText="Pays par défaut (FR)")
        self.region.setMaximumWidth(150)
        self.region.setText("FR")
        self.btn = QPushButton("ANALYSER")
        self.btn.setObjectName("Primary")
        self.btn.clicked.connect(self.run)
        bar.addWidget(self.input, 1)
        bar.addWidget(self.region)
        bar.addWidget(self.btn)
        lay.addLayout(bar)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.document().setDefaultStyleSheet('a{color:#ffffff;text-decoration:underline}')
        lay.addWidget(self.view, 1)
        lay.addWidget(muted("Pays, opérateur probable, type de ligne, fuseaux (hors ligne) + liens de recherche."))

    def run(self):
        num = self.input.text().strip()
        if not num:
            return
        region = (self.region.text().strip() or "FR").upper()
        self.btn.setEnabled(False)
        run_async(phone_investigate, num, region, on_done=self._done, on_error=self._err)
        self.ctx.log_event("phone", "investigate", {"region": region})

    def _done(self, p: PhoneInfo):
        self.btn.setEnabled(True)
        self.view.setHtml(_phone_html(p))
        self.ctx.repo.log_history("tools", "phone", f"Analyse téléphone : {p.region} · {p.carrier} ({p.line_type})",
                                  {"country": p.country, "valid": p.valid})

    def _err(self, msg: str):
        self.btn.setEnabled(True)
        self.view.setHtml(f"<p style='color:#ff9a9a'>{escape(msg)}</p>")
        self.ctx.notify.emit(msg, "error")


class ReverseImageTab(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.input = QLineEdit(placeholderText="URL publique d'une image (facultatif)")
        self.input.returnPressed.connect(self.run)
        self.btn = QPushButton("PRÉPARER LES RECHERCHES")
        self.btn.setObjectName("Primary")
        self.btn.clicked.connect(self.run)
        bar.addWidget(self.input, 1)
        bar.addWidget(self.btn)
        lay.addLayout(bar)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.document().setDefaultStyleSheet('a{color:#ffffff;text-decoration:underline}')
        lay.addWidget(self.view, 1)
        lay.addWidget(muted(IMG_NOTICE))
        self.run()

    def run(self):
        links = reverse_image_links(self.input.text().strip())
        self.view.setHtml(
            f"<p style='color:#888'>{escape(IMG_NOTICE)}</p>"
            f"<h3 style='font-weight:300'>Moteurs de recherche inversée</h3>"
            + "".join(f"<p><a href='{escape(u)}'>{escape(label)}</a></p>" for label, u in links)
            + "<p style='color:#888'>Sans URL, ouvrez un moteur puis déposez votre image. "
            "La recherche trouve des images visuellement similaires — ce n'est pas une identification de personne.</p>"
        )
        if self.input.text().strip():
            self.ctx.log_event("image", "reverse_links", {})


class GeneratorsTab(QWidget):
    """Générateurs de données de test (IP, IBAN factice, UUID, MAC) + décodeur d'ID Discord."""

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(["IPv4 publiques", "IPv4 privées", "IPv6", "IBAN factice", "UUID v4", "Adresse MAC"])
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.country = QComboBox()
        self.country.addItems(sorted(gen.IBAN_LENGTHS))
        self.country.setCurrentText("FR")
        self.country.setVisible(False)
        self.count = QSpinBox(minimum=1, maximum=500, value=10)
        self.gen_btn = QPushButton("GÉNÉRER")
        self.gen_btn.setObjectName("Primary")
        self.gen_btn.clicked.connect(self.generate)
        self.copy_btn = QPushButton("COPIER")
        self.copy_btn.clicked.connect(self._copy)
        bar.addWidget(self.kind)
        bar.addWidget(self.country)
        bar.addWidget(self.count)
        bar.addWidget(self.gen_btn)
        bar.addWidget(self.copy_btn)
        bar.addStretch(1)
        lay.addLayout(bar)

        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setObjectName("Mono")
        lay.addWidget(self.out, 1)
        lay.addWidget(muted("Données de TEST calculées hors ligne. Un IBAN a une clé mod-97 valide mais ne "
                            "correspond à aucun compte réel ; une IP tirée au hasard ne désigne personne. "
                            "Pour tester des formulaires/parseurs — jamais pour frauder ou usurper."))

        # ---- décodeur Discord
        dbar = QHBoxLayout()
        self.discord_in = QLineEdit(placeholderText="ID Discord (snowflake) — utilisateur, serveur ou message")
        self.discord_in.returnPressed.connect(self.decode_discord)
        self.discord_btn = QPushButton("DÉCODER")
        self.discord_btn.setObjectName("Primary")
        self.discord_btn.clicked.connect(self.decode_discord)
        dbar.addWidget(self.discord_in, 1)
        dbar.addWidget(self.discord_btn)
        lay.addLayout(dbar)
        self.discord_out = QTextBrowser()
        self.discord_out.setMaximumHeight(130)
        self.discord_out.document().setDefaultStyleSheet("td{padding-right:16px}")
        lay.addWidget(self.discord_out)
        lay.addWidget(muted("Décodeur d'ID Discord : la date de création est encodée dans l'identifiant "
                            "(information publique). N'interroge pas Discord, ne révèle ni le nom ni le titulaire."))

    def _kind_changed(self):
        is_iban = self.kind.currentText() == "IBAN factice"
        self.country.setVisible(is_iban)

    def generate(self):
        k = self.kind.currentText()
        n = self.count.value()
        try:
            if k == "IPv4 publiques":
                vals = gen.random_ipv4(n, public_only=True)
            elif k == "IPv4 privées":
                vals = gen.random_ipv4_in("10.0.0.0/8", n)
            elif k == "IPv6":
                vals = gen.random_ipv6(n)
            elif k == "IBAN factice":
                vals = gen.fake_iban(self.country.currentText(), n)
            elif k == "UUID v4":
                vals = gen.random_uuid(n)
            else:
                vals = gen.random_mac(n)
        except Exception as exc:  # noqa: BLE001
            self.ctx.notify.emit(str(exc), "error")
            return
        self.out.setPlainText("\n".join(vals))
        self.ctx.log_event("tools", "generate", {"kind": k, "count": len(vals)})

    def _copy(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.out.toPlainText())
        self.ctx.notify.emit("Copié dans le presse-papier.", "success")

    def decode_discord(self):
        raw = self.discord_in.text().strip()
        if not raw:
            return
        try:
            info = gen.decode_discord_id(raw)
        except (ValueError, OverflowError):
            self.discord_out.setHtml("<p style='color:#ff9a9a'>Identifiant invalide (doit être numérique).</p>")
            return
        local = info.created_at.astimezone()
        rows = [("ID", str(info.snowflake)),
                ("Créé le (UTC)", info.created_at.strftime("%Y-%m-%d %H:%M:%S")),
                ("Créé le (local)", local.strftime("%d/%m/%Y %H:%M:%S")),
                ("Ancienneté", f"{info.age_days} jours"),
                ("Worker / Process / Incrément", f"{info.worker_id} / {info.process_id} / {info.increment}")]
        body = "".join(f"<tr><td style='color:#888'>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in rows)
        self.discord_out.setHtml(f"<table cellspacing=3>{body}</table>")
        self.ctx.log_event("tools", "discord_decode", {})


class ToolsPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("OUTILS",
                         "IP, pseudonyme, e-mail, téléphone, image inversée : informations issues de sources "
                         "publiques légales (aucun scraping, aucune identification biométrique).",
                         parent, help_key="tools_ip")
        tabs = QTabWidget()
        tabs.addTab(IpLookupTab(ctx), "IP LOOKUP")
        tabs.addTab(UsernameTrackerTab(ctx), "USERNAME TRACKER")
        tabs.addTab(EmailTab(ctx), "E-MAIL")
        tabs.addTab(PhoneTab(ctx), "TÉLÉPHONE")
        tabs.addTab(ReverseImageTab(ctx), "IMAGE INVERSÉE")
        tabs.addTab(GeneratorsTab(ctx), "GÉNÉRATEURS")
        self.root.addWidget(tabs, 1)
