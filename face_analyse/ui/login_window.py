"""Écran de connexion / inscription (requis quand un serveur est configuré).

Affiche clairement, avant toute inscription, ce qui est journalisé (RGPD).
Prend en charge e-mail + mot de passe, Discord et Google (si activés).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from face_analyse.auth.client import Account, AuthClient, ServerConfig
from face_analyse.core.errors import FaceAnalyseError
from face_analyse.database.repository import Repository
from face_analyse.ui import theme
from face_analyse.ui.widgets.pixel_title import PixelTitle
from face_analyse.ui.workers import run_async

log = logging.getLogger(__name__)
TOKEN_SECRET = "auth_token"


class LoginWindow(QDialog):
    authenticated = Signal(object)  # Account

    def __init__(self, auth: AuthClient, repo: Repository, remember: bool, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.repo = repo
        self.remember = remember
        self.config: ServerConfig | None = None
        self.account: Account | None = None
        self._avatar_bytes: bytes | None = None
        self._avatar_type = "image/png"

        self.setWindowTitle("FACE ANALYSE — Connexion")
        self.setFixedSize(520, 620)
        self.setStyleSheet(theme.stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 26, 34, 26)
        title = PixelTitle("FACE ANALYSE", pixel=3, gap=1, max_drip=4)
        root.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        intro = QLabel("Connectez-vous pour utiliser FACE ANALYSE")
        intro.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        intro.setStyleSheet(f"color: {theme.FG}; letter-spacing: 1px;")
        root.addWidget(intro)
        self.server_lbl = QLabel(f"serveur : {auth.base_url}")
        self.server_lbl.setObjectName("Muted")
        self.server_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.server_lbl)
        root.addSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_login_tab(), "CONNEXION")
        self.tabs.addTab(self._build_register_tab(), "INSCRIPTION")
        root.addWidget(self.tabs, 1)

        self.oauth_hint = QLabel("— ou en un clic —")
        self.oauth_hint.setObjectName("Muted")
        self.oauth_hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.oauth_hint)
        self.oauth_row = QHBoxLayout()
        self.discord_btn = QPushButton("Discord")
        self.discord_btn.clicked.connect(lambda: self._oauth("discord"))
        self.google_btn = QPushButton("Google")
        self.google_btn.clicked.connect(lambda: self._oauth("google"))
        self.oauth_row.addWidget(self.discord_btn)
        self.oauth_row.addWidget(self.google_btn)
        root.addLayout(self.oauth_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.discord_btn.setEnabled(False)
        self.google_btn.setEnabled(False)
        self._fetch_config()

    # ------------------------------------------------------------ onglets
    def _build_login_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.l_id = QLineEdit(placeholderText="E-mail ou pseudo")
        self.l_pw = QLineEdit(placeholderText="Mot de passe", echoMode=QLineEdit.EchoMode.Password)
        self.l_pw.returnPressed.connect(self._login)
        btn = QPushButton("SE CONNECTER")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._login)
        form.addRow("Identifiant", self.l_id)
        form.addRow("Mot de passe", self.l_pw)
        form.addRow("", btn)
        return w

    def _build_register_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        self.r_pseudo = QLineEdit(placeholderText="Votre pseudonyme")
        self.r_email = QLineEdit(placeholderText="E-mail (facultatif)")
        self.r_pw = QLineEdit(placeholderText="Mot de passe (8 caractères min.)", echoMode=QLineEdit.EchoMode.Password)
        avatar_row = QHBoxLayout()
        self.avatar_prev = QLabel()
        self.avatar_prev.setFixedSize(48, 48)
        self.avatar_prev.setStyleSheet(f"border:1px solid {theme.LINE_2};border-radius:24px;background:{theme.PANEL}")
        self.avatar_prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pick = QPushButton("Choisir un avatar…")
        pick.clicked.connect(self._pick_avatar)
        avatar_row.addWidget(self.avatar_prev)
        avatar_row.addWidget(pick)
        avatar_row.addStretch(1)
        form.addRow("Pseudo", self.r_pseudo)
        form.addRow("E-mail", self.r_email)
        form.addRow("Mot de passe", self.r_pw)
        form.addRow("Avatar", avatar_row)
        lay.addLayout(form)

        self.consent_box = QTextBrowser()
        self.consent_box.setMaximumHeight(130)
        self.consent_box.setPlainText("Chargement des conditions…")
        lay.addWidget(QLabel("Données enregistrées :"))
        lay.addWidget(self.consent_box)
        self.consent = QCheckBox("J'ai lu et j'accepte la collecte décrite ci-dessus.")
        lay.addWidget(self.consent)
        self.reg_btn = QPushButton("CRÉER MON COMPTE")
        self.reg_btn.setObjectName("Primary")
        self.reg_btn.clicked.connect(self._register)
        lay.addWidget(self.reg_btn)
        return w

    # ------------------------------------------------------------ config serveur
    def _fetch_config(self):
        self.status.setText("Connexion au serveur…")
        run_async(self.auth.config, on_done=self._config_ready, on_error=self._fail)

    def _config_ready(self, cfg: ServerConfig):
        self.config = cfg
        self.status.setText("")
        self.consent_box.setPlainText(cfg.consent_notice)
        self.discord_btn.setVisible(cfg.discord_enabled)
        self.google_btn.setVisible(cfg.google_enabled)
        self.discord_btn.setEnabled(cfg.discord_enabled)
        self.google_btn.setEnabled(cfg.google_enabled)
        self.oauth_hint.setVisible(cfg.discord_enabled or cfg.google_enabled)
        if not cfg.open_registration:
            self.reg_btn.setEnabled(False)
            self.reg_btn.setText("INSCRIPTIONS FERMÉES")

    # ------------------------------------------------------------ actions
    def _busy(self, on: bool, text: str = ""):
        for b in (self.discord_btn, self.google_btn, self.reg_btn):
            b.setEnabled(not on and b.isEnabled() or (not on and b is self.reg_btn and
                         bool(self.config and self.config.open_registration)))
        self.status.setText(text)

    def _login(self):
        self.status.setText("Connexion…")
        run_async(self.auth.login, self.l_id.text().strip(), self.l_pw.text(),
                  on_done=self._success, on_error=self._fail)

    def _register(self):
        if not self.consent.isChecked():
            self.status.setText("Vous devez accepter la collecte de données pour créer un compte.")
            return
        self.status.setText("Création du compte…")
        run_async(self.auth.register, self.r_pseudo.text().strip(), self.r_email.text().strip() or None,
                  self.r_pw.text(), True, on_done=self._success_with_avatar, on_error=self._fail)

    def _oauth(self, provider: str):
        self.status.setText(f"Ouverture de {provider} dans le navigateur…")
        try:
            url, link = self.auth.oauth_start(provider)
        except FaceAnalyseError as exc:
            self.status.setText(exc.user_message)
            return
        QDesktopServices.openUrl(QUrl(url))
        self.status.setText("Terminez la connexion dans le navigateur, puis revenez ici…")
        run_async(self.auth.oauth_poll, link, on_done=self._success, on_error=self._fail)

    def _pick_avatar(self):
        path, _ = QFileDialog.getOpenFileName(self, "Avatar", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            self.status.setText("Image illisible.")
            return
        with open(path, "rb") as fh:
            self._avatar_bytes = fh.read()
        self._avatar_type = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        self.avatar_prev.setPixmap(pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                              Qt.TransformationMode.SmoothTransformation))

    # ------------------------------------------------------------ fin
    def _success_with_avatar(self, account: Account):
        if self._avatar_bytes:
            try:
                self.auth.set_avatar(self._avatar_bytes, self._avatar_type)
            except FaceAnalyseError:
                pass
        self._success(account)

    def _success(self, account: Account):
        self.account = account
        if self.remember and self.auth.token:
            try:
                self.repo.set_secret(TOKEN_SECRET, self.auth.token)
            except FaceAnalyseError:
                pass
        self.authenticated.emit(account)
        self.accept()

    def _fail(self, msg: str):
        self.status.setText(msg)
