"""SETTINGS : seuils du moteur (avec chiffres du benchmark), modèles, caméra,
OSINT, clés API (chiffrées), protection des données."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget)

from face_analyse.core.paths import resource_path, user_data_dir, user_models_dir
from face_analyse.engine.registry import DETECTORS, EMBEDDERS, available_embedders
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, card, muted, section_label


def load_benchmark() -> dict | None:
    for p in (resource_path("benchmark.json"),):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


class SettingsPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("SETTINGS", "Paramètres du moteur, de la caméra, de l'OSINT et protection des données.", parent, help_key="settings")
        self.ctx = ctx
        self.bench = load_benchmark()
        s = ctx.settings

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(14)

        # ----- moteur
        c, cl = card()
        cl.addWidget(section_label("Moteur facial"))
        form = QFormLayout()
        self.threshold = QSlider(Qt.Orientation.Horizontal)
        self.threshold.setRange(20, 80)
        self.threshold.setValue(int(round(s.engine.match_threshold * 100)))
        self.threshold_lbl = QLabel()
        self.threshold_lbl.setObjectName("Mono")
        trow = QHBoxLayout()
        trow.addWidget(self.threshold, 1)
        trow.addWidget(self.threshold_lbl)
        form.addRow("Seuil de décision", trow)
        self.threshold_info = muted("")
        form.addRow("", self.threshold_info)
        self.margin = QDoubleSpinBox(decimals=3, minimum=0.0, maximum=0.2, singleStep=0.01, value=s.engine.ambiguity_margin)
        form.addRow("Marge d'ambiguïté", self.margin)
        self.det_score = QDoubleSpinBox(decimals=2, minimum=0.3, maximum=0.99, singleStep=0.05, value=s.engine.detection_score)
        form.addRow("Confiance de détection min.", self.det_score)
        self.enhance = QCheckBox("Correction automatique des images sombres / surexposées")
        self.enhance.setChecked(s.engine.enhance_lighting)
        form.addRow("", self.enhance)
        self.top_k = QSpinBox(minimum=1, maximum=20, value=s.engine.top_k)
        form.addRow("Candidats affichés", self.top_k)
        self.embedder = QComboBox()
        for key in available_embedders():
            label = EMBEDDERS[key].description if key in EMBEDDERS else f"Modèle personnalisé : {key[5:]}"
            self.embedder.addItem(label, key)
        idx = self.embedder.findData(s.engine.embedder)
        self.embedder.setCurrentIndex(max(idx, 0))
        form.addRow("Modèle d'empreintes", self.embedder)
        form.addRow("Détecteur", QLabel(DETECTORS[s.engine.detector].description))
        cl.addLayout(form)
        models_btn = QPushButton("OUVRIR LE DOSSIER DES MODÈLES PERSONNALISÉS")
        models_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_models_dir()))))
        cl.addWidget(muted("Pour remplacer le modèle sans recompiler : déposez un fichier .onnx de type ArcFace "
                           "(entrée 112×112) dans ce dossier, redémarrez, puis sélectionnez-le. Le seuil doit alors "
                           "être recalibré (scripts/run_benchmark.py)."))
        cl.addWidget(models_btn, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(c)

        # ----- caméra
        c, cl = card()
        cl.addWidget(section_label("Caméra"))
        form = QFormLayout()
        self.cam_index = QSpinBox(minimum=0, maximum=9, value=s.camera.device_index)
        form.addRow("Caméra par défaut (index)", self.cam_index)
        self.interval = QSpinBox(minimum=1, maximum=30, value=s.camera.recognition_interval)
        form.addRow("Reconnaissance toutes les N images", self.interval)
        self.cam_consent = QCheckBox("Ne plus demander l'autorisation avant d'activer la caméra")
        self.cam_consent.setChecked(s.camera.camera_consent_given)
        form.addRow("", self.cam_consent)
        cl.addLayout(form)
        lay.addWidget(c)

        # ----- OSINT
        c, cl = card()
        cl.addWidget(section_label("OSINT & assistant IA"))
        form = QFormLayout()
        self.timeout = QDoubleSpinBox(decimals=0, minimum=3, maximum=60, value=s.osint.timeout_s, suffix=" s")
        form.addRow("Délai par source", self.timeout)
        self.handles = QCheckBox("Vérifier les pseudonymes par défaut")
        self.handles.setChecked(s.osint.username_check)
        form.addRow("", self.handles)
        self.ai_model = QComboBox()
        for m in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
            self.ai_model.addItem(m)
        self.ai_model.setCurrentText(s.osint.ai_model)
        form.addRow("Modèle Claude", self.ai_model)
        self.api_key = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("déjà enregistrée" if ctx.repo.get_secret("anthropic_api_key") else "sk-ant-…")
        form.addRow("Clé API Claude", self.api_key)
        self.openalex_key = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.openalex_key.setPlaceholderText("déjà enregistrée" if ctx.repo.get_secret("openalex_api_key") else "facultatif")
        form.addRow("Clé API OpenAlex", self.openalex_key)
        cl.addLayout(form)
        cl.addWidget(muted("Les clés sont chiffrées dans la base locale (et protégées par DPAPI sous Windows). "
                           "Laisser vide pour conserver la clé actuelle."))
        lay.addWidget(c)

        # ----- compte & accès
        c, cl = card()
        cl.addWidget(section_label("Compte & accès"))
        form = QFormLayout()
        self.server_url = QLineEdit(s.auth.server_url)
        self.server_url.setPlaceholderText("https://panel.mondomaine.fr  (vide = mode autonome, sans compte)")
        form.addRow("Serveur de comptes", self.server_url)
        self.remember = QCheckBox("Rester connecté entre deux lancements")
        self.remember.setChecked(s.auth.remember)
        form.addRow("", self.remember)
        acc = ctx.account
        if acc is not None:
            form.addRow("Connecté", QLabel(f"@{acc.pseudo} ({acc.provider}) — rôle {acc.role}"))
        cl.addLayout(form)
        account_row = QHBoxLayout()
        logout_btn = QPushButton("SE DÉCONNECTER")
        logout_btn.clicked.connect(self._logout)
        logout_btn.setEnabled(acc is not None)
        account_row.addWidget(logout_btn)
        account_row.addStretch(1)
        cl.addLayout(account_row)
        cl.addWidget(muted("Avec un serveur, l'app exige une connexion (e-mail, Discord ou Google) et "
                           "l'administrateur peut suspendre un compte à distance. Ce qui est journalisé est "
                           "affiché à la connexion. Un changement d'URL prend effet au prochain démarrage."))
        lay.addWidget(c)

        # ----- données
        c, cl = card()
        cl.addWidget(section_label("Données & confidentialité"))
        cl.addWidget(muted(f"Dossier des données : {user_data_dir()}"))
        row = QHBoxLayout()
        open_btn = QPushButton("OUVRIR LE DOSSIER")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_data_dir()))))
        del_keys = QPushButton("SUPPRIMER LES CLÉS API")
        del_keys.clicked.connect(self._delete_keys)
        wipe = QPushButton("EFFACER TOUTE LA BASE BIOMÉTRIQUE")
        wipe.setObjectName("Danger")
        wipe.clicked.connect(self._wipe)
        row.addWidget(open_btn)
        row.addWidget(del_keys)
        row.addStretch(1)
        row.addWidget(wipe)
        cl.addLayout(row)
        lay.addWidget(c)

        lay.addStretch(1)
        scroll.setWidget(body)
        self.root.addWidget(scroll, 1)
        save = QPushButton("ENREGISTRER LES PARAMÈTRES")
        save.setObjectName("Primary")
        save.clicked.connect(self.save)
        self.root.addWidget(save, 0, Qt.AlignmentFlag.AlignRight)

        self.threshold.valueChanged.connect(self._threshold_changed)
        self._threshold_changed(self.threshold.value())

    def _threshold_changed(self, v: int):
        t = v / 100.0
        self.threshold_lbl.setText(f"{t:.2f}")
        if not self.bench or self.embedder.currentData() != "sface":
            self.threshold_info.setText("Pas de mesure disponible pour ce modèle : calibrez-le avec le benchmark.")
            return
        rows = self.bench.get("open_set", [])
        ver = next((r for r in self.bench.get("verification", []) if r["variant"] == "original"), None)
        if not rows:
            return
        nearest = min(rows, key=lambda r: abs(r["threshold"] - t))
        txt = (f"Mesuré sur LFW (seuil {nearest['threshold']:.3f}, galerie de {nearest['gallery_identities']} identités) : "
               f"personnes absentes nommées à tort {nearest['unknown_false_identification_rate'] * 100:.1f} % · "
               f"personnes enregistrées reconnues {nearest['correct_identification_rate'] * 100:.1f} % · "
               f"rejetées {nearest['known_rejected_rate'] * 100:.1f} %.")
        if ver:
            fmr = ver["fmr_at_threshold"].get(f"{nearest['threshold']:.3f}")
            if fmr:
                txt += f" Comparaison 1:1 : faux positifs {fmr[0] * 100:.2f} %, faux négatifs {fmr[1] * 100:.2f} %."
        txt += " Plus le seuil est haut, moins il y a de faux positifs, mais plus de vraies correspondances sont rejetées."
        self.threshold_info.setText(txt)

    def save(self):
        s = self.ctx.settings
        s.engine.match_threshold = self.threshold.value() / 100.0
        s.engine.ambiguity_margin = self.margin.value()
        s.engine.detection_score = self.det_score.value()
        s.engine.enhance_lighting = self.enhance.isChecked()
        s.engine.top_k = self.top_k.value()
        s.engine.embedder = self.embedder.currentData()
        s.camera.device_index = self.cam_index.value()
        s.camera.recognition_interval = self.interval.value()
        s.camera.camera_consent_given = self.cam_consent.isChecked()
        s.osint.timeout_s = self.timeout.value()
        s.osint.username_check = self.handles.isChecked()
        s.osint.ai_model = self.ai_model.currentText()
        new_server = self.server_url.text().strip().rstrip("/")
        server_changed = new_server != s.auth.server_url
        s.auth.server_url = new_server
        s.auth.remember = self.remember.isChecked()
        s.save()
        if server_changed:
            self.ctx.notify.emit("Serveur enregistré : il sera pris en compte au prochain démarrage.", "info")
        if self.api_key.text().strip():
            self.ctx.repo.set_secret("anthropic_api_key", self.api_key.text().strip())
            self.api_key.clear()
            self.api_key.setPlaceholderText("déjà enregistrée")
        if self.openalex_key.text().strip():
            self.ctx.repo.set_secret("openalex_api_key", self.openalex_key.text().strip())
            self.openalex_key.clear()
            self.openalex_key.setPlaceholderText("déjà enregistrée")
        self.ctx.apply_engine_settings()
        self.ctx.notify.emit("Paramètres enregistrés.", "success")

    def _logout(self):
        if self.ctx.auth is not None:
            self.ctx.auth.logout()
        self.ctx.repo.set_secret("auth_token", "")
        self.ctx.stop_heartbeat()
        self.ctx.notify.emit("Déconnecté. Fermez puis rouvrez l'application pour vous reconnecter.", "info")

    def _delete_keys(self):
        self.ctx.repo.set_secret("anthropic_api_key", "")
        self.ctx.repo.set_secret("openalex_api_key", "")
        self.api_key.setPlaceholderText("sk-ant-…")
        self.openalex_key.setPlaceholderText("facultatif")
        self.ctx.notify.emit("Clés API supprimées.", "success")

    def _wipe(self):
        ok = QMessageBox.warning(
            self, "Effacement complet",
            "Effacer TOUTES les personnes, photos et empreintes faciales ?\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok == QMessageBox.StandardButton.Yes:
            self.ctx.repo.wipe_biometrics()
            self.ctx.refresh_gallery()
            self.ctx.notify.emit("Base biométrique effacée.", "success")
