"""CAMÉRA LIVE : détection en temps réel, cadre qui suit la tête, nom si
la personne est enregistrée (avec consentement) dans la base locale."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton, QVBoxLayout

from face_analyse.core.errors import FaceAnalyseError
from face_analyse.ui.camera_thread import CameraThread, TrackView
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, muted
from face_analyse.ui.pages.enroll_dialog import EnrollDialog
from face_analyse.ui.widgets.image_view import ImageView, Overlay
from face_analyse.ui.workers import run_async


class CameraPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("CAMÉRA LIVE",
                         "Reconnaissance en direct à partir de la base consentante. Les personnes non enregistrées "
                         "restent UNKNOWN : aucune recherche n'est faite en dehors de la base.", parent, help_key="camera")
        self.ctx = ctx
        self.thread: CameraThread | None = None

        bar = QHBoxLayout()
        self.start_btn = QPushButton("ACTIVER LA CAMÉRA")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self.toggle)
        self.switch_btn = QPushButton("⟲  CHANGER DE CAMÉRA")
        self.switch_btn.setToolTip("Passe à la caméra suivante (avant / arrière / externe)")
        self.switch_btn.clicked.connect(self.switch_camera)
        self.mirror = QCheckBox("Miroir")
        self.mirror.setChecked(ctx.settings.camera.mirror)
        self.mirror.toggled.connect(self._mirror_changed)
        self.enroll_btn = QPushButton("ENREGISTRER CE VISAGE")
        self.enroll_btn.setToolTip("Ajoute l'image actuelle comme photo de référence d'une personne consentante")
        self.enroll_btn.clicked.connect(self.enroll_current)
        for w in (self.start_btn, self.switch_btn, self.enroll_btn):
            bar.addWidget(w)
        bar.addWidget(self.mirror)
        bar.addStretch(1)
        self.stats_lbl = QLabel("—")
        self.stats_lbl.setObjectName("Mono")
        bar.addWidget(self.stats_lbl)
        self.root.addLayout(bar)

        body = QHBoxLayout()
        self.view = ImageView(placeholder="Caméra désactivée")
        body.addWidget(self.view, 1)
        side = QVBoxLayout()
        side.addWidget(QLabel("VISAGES SUIVIS"))
        self.tracks = QListWidget()
        self.tracks.setMaximumWidth(260)
        side.addWidget(self.tracks, 1)
        body.addLayout(side)
        self.root.addLayout(body, 1)
        self.root.addWidget(muted("Le nom affiché résulte d'un vote sur plusieurs images et d'un seuil de similarité. "
                                  "Ce n'est pas une preuve d'identité."))
        self._update_buttons()

    # ------------------------------------------------------------ consentement caméra
    def _ask_camera_permission(self) -> bool:
        if self.ctx.settings.camera.camera_consent_given:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Activer la caméra")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("FACE ANALYSE souhaite activer votre caméra.")
        box.setInformativeText(
            "Les images sont traitées uniquement sur cet ordinateur. Rien n'est envoyé sur Internet ni enregistré, "
            "sauf si vous cliquez sur « Enregistrer ce visage »."
        )
        remember = QCheckBox("Ne plus demander")
        box.setCheckBox(remember)
        allow = box.addButton("Autoriser", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Refuser", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        granted = box.clickedButton() is allow
        if granted and remember.isChecked():
            self.ctx.settings.camera.camera_consent_given = True
            self.ctx.settings.save()
        self.ctx.repo.log_history("camera", "permission", "Caméra autorisée" if granted else "Caméra refusée")
        self.ctx.log_event("camera", "permission", {"granted": granted})
        return granted

    # ------------------------------------------------------------ contrôle
    def toggle(self):
        if self.thread is not None:
            self.stop()
        else:
            self.start()

    def start(self, index: int | None = None):
        if self.ctx.engine is None:
            self.ctx.notify.emit("Moteur non chargé : " + (self.ctx.engine_error or "patientez…"), "warning")
            return
        if not self._ask_camera_permission():
            return
        cam = self.ctx.settings.camera
        idx = cam.device_index if index is None else index
        self.thread = CameraThread(self.ctx.engine, idx, self.mirror.isChecked(), cam.recognition_interval)
        self.thread.frame_ready.connect(self._on_frame)
        self.thread.stats.connect(lambda fps, n: self.stats_lbl.setText(f"cam {self.thread.index if self.thread else '-'} · {fps:4.1f} ips · {n} visage(s)"))
        self.thread.failed.connect(self._on_failed)
        self.thread.opened.connect(self._on_opened)
        self.thread.start()
        self.view.placeholder = "Ouverture de la caméra…"
        self.view.set_image(None)
        self._update_buttons()

    def stop(self):
        if self.thread is not None:
            t = self.thread
            self.thread = None
            t.frame_ready.disconnect()
            t.stop()
        self.view.placeholder = "Caméra désactivée"
        self.view.set_image(None)
        self.view.set_overlays([])
        self.tracks.clear()
        self.stats_lbl.setText("—")
        self._update_buttons()

    def switch_camera(self):
        """Passe à la caméra suivante ; essaie jusqu'à 4 index avant d'abandonner."""
        current = self.thread.index if self.thread else self.ctx.settings.camera.device_index
        self.stop()
        self._switch_attempts = 1
        self.start((current + 1) % 4)

    def _on_opened(self, index: int):
        self._switch_attempts = 0
        self.ctx.settings.camera.device_index = index
        self.ctx.settings.save()
        self.ctx.notify.emit(f"Caméra n°{index} active.", "success")

    def _on_failed(self, msg: str):
        failed_index = self.thread.index if self.thread else 0
        self.stop()
        attempts = getattr(self, "_switch_attempts", 0)
        if 0 < attempts < 4:
            self._switch_attempts = attempts + 1
            self.start((failed_index + 1) % 4)
            return
        self._switch_attempts = 0
        self.ctx.notify.emit(msg, "error")

    def _mirror_changed(self, on: bool):
        self.ctx.settings.camera.mirror = on
        self.ctx.settings.save()
        if self.thread is not None:
            self.thread.mirror = on
            self.thread.tracker.reset()

    def _update_buttons(self):
        running = self.thread is not None
        self.start_btn.setText("DÉSACTIVER" if running else "ACTIVER LA CAMÉRA")
        self.enroll_btn.setEnabled(running)

    # ------------------------------------------------------------ affichage
    def _on_frame(self, img: QImage, views: list[TrackView]):
        self.view.set_image(img)
        overlays = [
            Overlay(v.box, v.label, f"sim {v.similarity:+.2f}" if v.similarity is not None else "", known=v.known)
            for v in views
        ]
        self.view.set_overlays(overlays)
        self.tracks.clear()
        for v in views:
            sim = f"{v.similarity:+.3f}" if v.similarity is not None else "…"
            self.tracks.addItem(f"#{v.track_id:<3} {v.label:<22} {sim}")

    # ------------------------------------------------------------ enrôlement
    def enroll_current(self):
        if self.thread is None or self.ctx.engine is None:
            return
        frame = self.thread.last_frame()
        if frame is None:
            return
        dlg = EnrollDialog(self.ctx.repo, self)
        if not dlg.exec():
            return
        try:
            pid = dlg.resolve(self.ctx.repo)
        except FaceAnalyseError as exc:
            self.ctx.notify.emit(exc.user_message, "error")
            return
        engine = self.ctx.engine

        def done(res):
            _photo_id, warnings = res
            self.ctx.refresh_gallery()
            if self.thread is not None:
                self.thread.tracker.reset()
            msg = "Visage enregistré." + (" " + " ".join(warnings) if warnings else "")
            self.ctx.notify.emit(msg, "warning" if warnings else "success")

        run_async(self.ctx.repo.add_photo, pid, frame, engine, on_done=done,
                  on_error=lambda m: self.ctx.notify.emit(m, "error"))

    def on_hide(self):
        self.stop()
