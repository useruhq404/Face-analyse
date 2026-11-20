"""CONSOLE — terminal intégré pour apprendre et manipuler (sources publiques).

Un vrai interpréteur de commandes, pas une décoration : recon réseau (DNS, RDAP,
crt.sh, en-têtes, ports locaux), crypto/encodage hors ligne, générateurs de
données de test, décodeur d'ID Discord, et une bibliothèque `learn`.

Cadre légal strict : rien ici n'attaque autrui. Le scan de ports est limité aux
hôtes locaux/privés (ou autorisés) ; aucun DDoS, bruteforce, scraping ou
contournement. Pour mesurer la charge de TES services → module STRESS TEST.
"""

from __future__ import annotations

import shlex

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QVBoxLayout

from face_analyse.osint import crypto_tools as ct
from face_analyse.osint import generators as gen
from face_analyse.osint import learn as learn_lib
from face_analyse.osint import netinfo as net
from face_analyse.osint.http import PoliteSession
from face_analyse.osint.iplookup import lookup as ip_lookup
from face_analyse.ui import theme
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page
from face_analyse.ui.workers import run_async

BANNER = r"""
  ███████╗ █████╗  ██████╗███████╗     ██████╗ ███╗   ██╗███████╗
  ██╔════╝██╔══██╗██╔════╝██╔════╝    ██╔═══██╗████╗  ██║██╔════╝
  █████╗  ███████║██║     █████╗      ██║   ██║██╔██╗ ██║███████╗
  ██╔══╝  ██╔══██║██║     ██╔══╝      ██║   ██║██║╚██╗██║╚════██║
  ██║     ██║  ██║╚██████╗███████╗    ╚██████╔╝██║ ╚████║███████║
  ╚═╝     ╚═╝  ╚═╝ ╚═════╝╚══════╝     ╚═════╝ ╚═╝  ╚═══╝╚══════╝
   console · sources publiques · à but éducatif · discord: 35ans
        tape  help  pour les commandes  ·  learn  pour apprendre
"""

HELP = """\
COMMANDES

 recon réseau (API publiques)
   ip <ip|domaine>            géoloc + opérateur (zone de l'IP, pas une personne)
   dns <domaine> [type]       DNS-over-HTTPS (A, AAAA, MX, NS, TXT, CNAME…)
   whois <domaine>            RDAP : registrar, dates, statut, serveurs de noms
   subdomains <domaine>       sous-domaines via les certificats (crt.sh)
   headers <url>              en-têtes HTTP + en-têtes de sécurité présents/absents
   cert <hôte>                certificat TLS présenté (sujet, émetteur, validité)
   ports <hôte>               scan TCP léger — LOCAL/privé uniquement (ou autorisé)

 crypto / encodage (hors ligne)
   hash <algo> <texte>        md5 | sha1 | sha256 | sha512
   hashid <valeur>            devine le type d'un hash
   b64 enc|dec <texte>        base64     url enc|dec <texte>     hex enc|dec <texte>
   rot13 <texte>              binary enc|dec <texte>             morse enc|dec <texte>
   pwgen [longueur]           mot de passe fort + entropie

 générateurs (données de test)
   genip [n] [public|prive]   geniban [pays] [n]   uuid [n]   mac [n]
   discord <id>               ID Discord → date de création (snowflake)

 apprendre
   learn [sujet]              fiches : osint recon web crypto passwords dos ethics

 divers
   clear                      efface l'écran        help    cette aide

Rappels : ne vise que TES systèmes. DDoS/bruteforce/scraping = illégaux, absents ici.
"""


class _Prompt(QLineEdit):
    """Entrée avec historique (flèches haut/bas)."""

    def __init__(self, on_enter, parent=None):
        super().__init__(parent)
        self._on_enter = on_enter
        self._history: list[str] = []
        self._idx = 0
        self.returnPressed.connect(self._enter)

    def _enter(self):
        text = self.text()
        if text.strip():
            self._history.append(text)
        self._idx = len(self._history)
        self.clear()
        self._on_enter(text)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Up and self._history:
            self._idx = max(0, self._idx - 1)
            self.setText(self._history[self._idx])
        elif e.key() == Qt.Key.Key_Down and self._history:
            self._idx = min(len(self._history), self._idx + 1)
            self.setText(self._history[self._idx] if self._idx < len(self._history) else "")
        else:
            super().keyPressEvent(e)


class ConsolePage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("CONSOLE",
                         "Terminal intégré : recon réseau, crypto, générateurs et fiches d'apprentissage — "
                         "sources publiques, tes propres cibles uniquement.", parent, help_key="console")
        self.ctx = ctx
        mono = QFont(theme.mono_font_family(), 10)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(mono)
        self.view.setStyleSheet(
            f"QPlainTextEdit{{background:{theme.BG};color:{theme.FG};border:1px solid {theme.LINE};"
            f"padding:10px;selection-background-color:{theme.LINE_2};}}")
        self.root.addWidget(self.view, 1)

        self.input = _Prompt(self._submit)
        self.input.setFont(mono)
        self.input.setPlaceholderText("tape une commande (help)…")
        self.input.setStyleSheet(
            f"QLineEdit{{background:{theme.PANEL};color:{theme.OK};border:1px solid {theme.LINE_2};"
            f"padding:8px 10px;}}")
        self.root.addWidget(self.input)

        self._print(BANNER)
        self._busy = False

    # ---------------------------------------------------------------- affichage
    def _print(self, text: str = ""):
        self.view.appendPlainText(text)
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def _echo_cmd(self, line: str):
        self._print(f"\n┌─[face@analyse]\n└─$ {line}")

    # ------------------------------------------------------------------ dispatch
    def _submit(self, line: str):
        line = line.strip()
        if not line:
            return
        self._echo_cmd(line)
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]
        try:
            self._dispatch(cmd, args)
        except Exception as exc:  # noqa: BLE001
            self._print(f"  erreur : {exc}")

    def _dispatch(self, cmd: str, args: list[str]):
        if cmd in ("help", "?", "aide"):
            self._print(HELP)
        elif cmd == "clear":
            self.view.clear()
            self._print(BANNER)
        elif cmd == "learn":
            self._print(learn_lib.lesson(args[0] if args else ""))
        # ---- crypto / encodage (synchrone)
        elif cmd == "hash":
            self._need(args, 2, "hash <algo> <texte>")
            self._print(f"  {ct.hash_text(args[0], ' '.join(args[1:]))}")
        elif cmd == "hashid":
            self._need(args, 1, "hashid <valeur>")
            cand = ct.identify_hash(args[0])
            self._print("  " + (", ".join(cand) if cand else "type inconnu (longueur/forme non reconnue)"))
        elif cmd == "b64":
            self._codec(args, ct.b64_encode, ct.b64_decode, "b64 enc|dec <texte>")
        elif cmd == "url":
            self._codec(args, ct.url_encode, ct.url_decode, "url enc|dec <texte>")
        elif cmd == "hex":
            self._codec(args, ct.hex_encode, ct.hex_decode, "hex enc|dec <texte>")
        elif cmd == "binary":
            self._codec(args, ct.to_binary, ct.from_binary, "binary enc|dec <texte>")
        elif cmd == "morse":
            self._codec(args, ct.to_morse, ct.from_morse, "morse enc|dec <texte>")
        elif cmd == "rot13":
            self._need(args, 1, "rot13 <texte>")
            self._print("  " + ct.rot13(" ".join(args)))
        elif cmd == "pwgen":
            length = int(args[0]) if args and args[0].isdigit() else 20
            pw = ct.generate_password(length)
            self._print(f"  {pw}\n  force : {ct.password_strength(pw)}")
        # ---- générateurs
        elif cmd == "genip":
            n = int(args[0]) if args and args[0].isdigit() else 10
            priv = len(args) > 1 and args[1].lower().startswith("priv")
            vals = gen.random_ipv4_in("10.0.0.0/8", n) if priv else gen.random_ipv4(n)
            self._print("  " + "  ".join(vals))
        elif cmd == "geniban":
            country = args[0].upper() if args and args[0].isalpha() else "FR"
            n = next((int(a) for a in args if a.isdigit()), 5)
            self._print("\n".join("  " + x for x in gen.fake_iban(country, n)))
        elif cmd == "uuid":
            n = int(args[0]) if args and args[0].isdigit() else 5
            self._print("\n".join("  " + x for x in gen.random_uuid(n)))
        elif cmd == "mac":
            n = int(args[0]) if args and args[0].isdigit() else 5
            self._print("  " + "  ".join(gen.random_mac(n)))
        elif cmd == "discord":
            self._need(args, 1, "discord <id>")
            info = gen.decode_discord_id(args[0])
            self._print(f"  créé le   {info.created_at:%Y-%m-%d %H:%M:%S} UTC  ({info.age_days} j)\n"
                        f"  worker {info.worker_id} · process {info.process_id} · incrément {info.increment}")
        # ---- recon réseau (asynchrone)
        elif cmd == "ip":
            self._need(args, 1, "ip <ip|domaine>")
            self._async(ip_lookup, args[0], self.ctx.settings.osint.timeout_s, fmt=self._fmt_ip)
        elif cmd == "dns":
            self._need(args, 1, "dns <domaine> [type]")
            rtype = args[1] if len(args) > 1 else "A"
            self._async(lambda: net.dns_query(self._http(), args[0], rtype),
                        fmt=lambda rows: "  " + ("\n  ".join(rows) if rows else "(aucune réponse)"))
        elif cmd == "whois":
            self._need(args, 1, "whois <domaine>")
            self._async(lambda: net.rdap_domain(self._http(), args[0]), fmt=self._fmt_whois)
        elif cmd == "subdomains":
            self._need(args, 1, "subdomains <domaine>")
            self._async(lambda: net.crt_subdomains(self._http(), args[0]),
                        fmt=lambda subs: f"  {len(subs)} sous-domaine(s) :\n  " + "\n  ".join(subs) if subs
                        else "  (aucun certificat trouvé)")
        elif cmd == "headers":
            self._need(args, 1, "headers <url>")
            self._async(lambda: net.http_headers(self._http(), args[0]), fmt=self._fmt_headers)
        elif cmd == "cert":
            self._need(args, 1, "cert <hôte>")
            self._async(lambda: net.tls_cert_info(args[0]),
                        fmt=lambda d: "\n".join(f"  {k:12} {v}" for k, v in d.items()))
        elif cmd == "ports":
            self._need(args, 1, "ports <hôte>")
            authorized = "--yes" in args or "-y" in args
            host = args[0]
            self._async(lambda: net.scan_ports(host, authorized=authorized), fmt=self._fmt_ports)
        else:
            self._print(f"  commande inconnue : {cmd}  (tape  help)")

    # ---------------------------------------------------------------- utilitaires
    def _http(self) -> PoliteSession:
        return PoliteSession(timeout=self.ctx.settings.osint.timeout_s)

    def _need(self, args: list[str], n: int, usage: str):
        if len(args) < n:
            raise ValueError(f"usage : {usage}")

    def _codec(self, args, enc, dec, usage):
        self._need(args, 2, usage)
        mode = args[0].lower()
        payload = " ".join(args[1:])
        if mode in ("enc", "e", "encode"):
            self._print("  " + enc(payload))
        elif mode in ("dec", "d", "decode"):
            self._print("  " + dec(payload))
        else:
            raise ValueError(usage)

    def _async(self, fn, *fargs, fmt):
        if self._busy:
            self._print("  (une commande réseau est déjà en cours…)")
            return
        self._busy = True
        self._print("  …")

        def done(result):
            self._busy = False
            self._print(fmt(result))

        def err(msg):
            self._busy = False
            self._print(f"  erreur réseau : {msg}")

        run_async(fn, *fargs, on_done=done, on_error=err)

    # ---------------------------------------------------------------- formatteurs
    @staticmethod
    def _fmt_ip(i) -> str:
        loc = " · ".join(x for x in (i.city, i.region, i.country) if x) or "—"
        flags = [f for f, c in (("hébergeur", i.is_hosting), ("proxy/VPN", i.is_proxy)) if c]
        out = [f"  IP        {i.ip} ({i.ip_type})" if i.ip_type else f"  IP        {i.ip}",
               f"  lieu      {loc}", f"  opérateur {' '.join(x for x in (i.asn, i.org or i.isp) if x) or '—'}"]
        if i.hostname:
            out.append(f"  dns inv.  {i.hostname}")
        if flags:
            out.append(f"  indices   {', '.join(flags)}")
        return "\n".join(out)

    @staticmethod
    def _fmt_whois(d) -> str:
        out = [f"  domaine   {d.domain}"]
        if d.registrar:
            out.append(f"  registrar {d.registrar}")
        for k, label in (("registration", "créé"), ("expiration", "expire"), ("last changed", "modifié")):
            if d.events.get(k):
                out.append(f"  {label:9} {d.events[k]}")
        if d.statuses:
            out.append(f"  statut    {', '.join(d.statuses)}")
        if d.nameservers:
            out.append(f"  ns        {', '.join(d.nameservers)}")
        return "\n".join(out)

    @staticmethod
    def _fmt_headers(h) -> str:
        out = [f"  {h.status} {h.url}", f"  serveur   {h.server or '—'}",
               f"  sécurité  présents : {', '.join(h.present) or 'aucun'}",
               f"            absents  : {', '.join(h.missing) or 'aucun'}"]
        return "\n".join(out)

    @staticmethod
    def _fmt_ports(r) -> str:
        if not r.open_ports:
            return f"  {r.host} : aucun port ouvert parmi {r.scanned} testés"
        lines = [f"  {r.host} — {len(r.open_ports)} port(s) ouvert(s) / {r.scanned} :"]
        lines += [f"    {p:>5}  {name}" for p, name in r.open_ports]
        return "\n".join(lines)
