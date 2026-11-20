"""FACE DATABASE : personnes consentantes, photos de référence, suppression complète."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from face_analyse.core.errors import FaceAnalyseError
from face_analyse.engine.preprocessing import load_image
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, card, muted, pick_images, section_label
from face_analyse.ui.pages.enroll_dialog import EnrollDialog
from face_analyse.ui.workers import run_async


class DatabasePage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("FACE DATABASE",
                         "Personnes ayant volontairement enregistré leurs photos. Photos et empreintes sont chiffrées "
                         "sur ce poste ; la suppression efface définitivement toutes les données d'une personne.", parent)
        self.ctx = ctx
        self.current_id: int | None = None

        split = QSplitter(Qt.Orientation.Horizontal)
        # ----- liste
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher (nom, prénom, notes)…")
        self.search.textChanged.connect(self.reload)
        self.people = QListWidget()
        self.people.currentItemChanged.connect(self._select)
        add = QPushButton("+  AJOUTER UNE PERSONNE")
        add.setObjectName("Primary")
        add.clicked.connect(self._add_person)
        self.stats = muted("")
        ll.addWidget(self.search)
        ll.addWidget(self.people, 1)
        ll.addWidget(add)
        ll.addWidget(self.stats)
        split.addWidget(left)

        # ----- détail
        right, rl = card()
        rl.addWidget(section_label("Fiche"))
        form = QFormLayout()
        self.first = QLineEdit()
        self.last = QLineEdit()
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(80)
        self.consent_lbl = muted("")
        form.addRow("Prénom", self.first)
        form.addRow("Nom", self.last)
        form.addRow("Notes", self.notes)
        form.addRow("Consentement", self.consent_lbl)
        rl.addLayout(form)
        btns = QHBoxLayout()
        self.save_btn = QPushButton("ENREGISTRER")
        self.save_btn.clicked.connect(self._save)
        self.delete_btn = QPushButton("SUPPRIMER TOUTES SES DONNÉES")
        self.delete_btn.setObjectName("Danger")
        self.delete_btn.clicked.connect(self._delete_person)
        btns.addWidget(self.save_btn)
        btns.addStretch(1)
        btns.addWidget(self.delete_btn)
        rl.addLayout(btns)

        rl.addWidget(section_label("Photos de référence"))
        rl.addWidget(muted("Plusieurs photos (angles, lumières, époques différentes) améliorent nettement la reconnaissance."))
        self.photos = QListWidget()
        self.photos.setViewMode(QListWidget.ViewMode.IconMode)
        self.photos.setIconSize(QSize(110, 110))
        self.photos.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.photos.setSpacing(8)
        self.photos.setMinimumHeight(170)
        rl.addWidget(self.photos, 1)
        pb = QHBoxLayout()
        self.add_photos_btn = QPushButton("+  AJOUTER DES PHOTOS")
        self.add_photos_btn.clicked.connect(self._add_photos)
        self.del_photo_btn = QPushButton("RETIRER LA PHOTO")
        self.del_photo_btn.clicked.connect(self._delete_photo)
        pb.addWidget(self.add_photos_btn)
        pb.addWidget(self.del_photo_btn)
        pb.addStretch(1)
        rl.addLayout(pb)
        self.reencode_box = QLabel("")
        self.reencode_box.setObjectName("Warn")
        self.reencode_box.setWordWrap(True)
        self.reencode_btn = QPushButton("RECALCULER LES EMPREINTES")
        self.reencode_btn.clicked.connect(self._reencode)
        rl.addWidget(self.reencode_box)
        rl.addWidget(self.reencode_btn, 0, Qt.AlignmentFlag.AlignLeft)
        split.addWidget(right)
        split.setSizes([300, 700])
        self.root.addWidget(split, 1)

        ctx.engine_ready.connect(self._check_model)
        ctx.gallery_changed.connect(self._update_stats)
        self.reload()
        self._show_person(None)

    # ------------------------------------------------------------ chargement
    def on_show(self):
        self.reload()
        self._check_model()

    def reload(self):
        keep = self.current_id
        self.people.blockSignals(True)
        self.people.clear()
        for p in self.ctx.repo.list_people(self.search.text()):
            item = QListWidgetItem(f"{p.display_name}\n{p.photo_count} photo(s)")
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.people.addItem(item)
            if p.id == keep:
                self.people.setCurrentItem(item)
        self.people.blockSignals(False)
        self._show_person(keep if self.people.currentItem() else None)
        self._update_stats()

    def _update_stats(self):
        s = self.ctx.repo.stats()
        self.stats.setText(f"{s['persons']} personne(s) · {s['photos']} photo(s) · {s['embeddings']} empreinte(s)")

    def _check_model(self):
        if self.ctx.engine is None:
            self.reencode_box.setText("")
            self.reencode_btn.hide()
            return
        missing = self.ctx.repo.photos_missing_model(self.ctx.engine.embedder.model_id)
        if missing:
            self.reencode_box.setText(f"{missing} photo(s) n'ont pas d'empreinte pour le modèle actif "
                                      f"({self.ctx.engine.embedder.model_id}). Elles sont ignorées par la recherche.")
            self.reencode_btn.show()
        else:
            self.reencode_box.setText("")
            self.reencode_btn.hide()

    def _select(self, item: QListWidgetItem | None, _prev=None):
        self._show_person(item.data(Qt.ItemDataRole.UserRole) if item else None)

    def _show_person(self, pid: int | None):
        self.current_id = pid
        enabled = pid is not None
        for w in (self.first, self.last, self.notes, self.save_btn, self.delete_btn, self.add_photos_btn, self.del_photo_btn):
            w.setEnabled(enabled)
        self.photos.clear()
        if pid is None:
            self.first.clear()
            self.last.clear()
            self.notes.clear()
            self.consent_lbl.setText("—")
            return
        p = self.ctx.repo.get_person(pid)
        if p is None:
            return
        self.first.setText(p.first_name)
        self.last.setText(p.last_name)
        self.notes.setPlainText(p.notes)
        self.consent_lbl.setText(f"recueilli le {p.consent_at:%d/%m/%Y à %H:%M} (UTC)")
        for ph in self.ctx.repo.list_photos(pid):
            img = QImage.fromData(ph.thumbnail_jpeg)
            item = QListWidgetItem(QIcon(QPixmap.fromImage(img)), f"qualité {ph.quality:.2f}")
            item.setData(Qt.ItemDataRole.UserRole, ph.id)
            self.photos.addItem(item)

    # ------------------------------------------------------------ actions
    def _add_person(self):
        dlg = EnrollDialog(self.ctx.repo, self)
        dlg.person.setCurrentIndex(0)
        dlg.person.setEnabled(False)
        dlg.setWindowTitle("Ajouter une personne")
        if not dlg.exec():
            return
        try:
            pid = dlg.resolve(self.ctx.repo)
        except FaceAnalyseError as exc:
            self.ctx.notify.emit(exc.user_message, "error")
            return
        self.current_id = pid
        self.reload()
        self.ctx.notify.emit("Personne ajoutée. Ajoutez maintenant ses photos de référence.", "success")
        self._add_photos()

    def _save(self):
        if self.current_id is None:
            return
        try:
            self.ctx.repo.update_person(self.current_id, self.first.text(), self.last.text(), self.notes.toPlainText())
        except FaceAnalyseError as exc:
            self.ctx.notify.emit(exc.user_message, "error")
            return
        self.reload()
        self.ctx.refresh_gallery()
        self.ctx.notify.emit("Fiche enregistrée.", "success")

    def _delete_person(self):
        if self.current_id is None:
            return
        name = f"{self.first.text()} {self.last.text()}".strip()
        ok = QMessageBox.question(
            self, "Suppression complète",
            f"Supprimer définitivement {name} ?\n\nToutes ses photos et empreintes faciales seront effacées "
            "et la base sera compactée. Cette action est irréversible.",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        self.ctx.repo.delete_person(self.current_id)
        self.current_id = None
        self.reload()
        self.ctx.refresh_gallery()
        self.ctx.notify.emit(f"Données de {name} supprimées.", "success")

    def _add_photos(self):
        if self.current_id is None:
            return
        if self.ctx.engine is None:
            self.ctx.notify.emit("Moteur non chargé.", "warning")
            return
        files = pick_images(self, multiple=True)
        if not files:
            return
        pid, engine, repo = self.current_id, self.ctx.engine, self.ctx.repo

        def job(progress):
            report = []
            for i, f in enumerate(files):
                progress("Enrôlement des photos", i, len(files))
                try:
                    _, warnings = repo.add_photo(pid, load_image(f), engine)
                    report.append((Path(f).name, True, warnings))
                except FaceAnalyseError as exc:
                    report.append((Path(f).name, False, [exc.user_message]))
            progress("Enrôlement des photos", len(files), len(files))
            return report

        self.add_photos_btn.setEnabled(False)
        run_async(job, on_done=self._photos_added, on_error=lambda m: self.ctx.notify.emit(m, "error"),
                  on_progress=lambda l, d, n: self.ctx.busy.emit(l, d, n))

    def _photos_added(self, report):
        self.add_photos_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        ok = sum(1 for _, success, _ in report if success)
        problems = [f"{name} : {' '.join(w)}" for name, success, w in report if not success or w]
        self.ctx.refresh_gallery()
        self.reload()
        self.ctx.notify.emit(f"{ok}/{len(report)} photo(s) ajoutée(s).", "success" if ok == len(report) else "warning")
        if problems:
            QMessageBox.information(self, "Rapport d'enrôlement", "\n".join(problems[:20]))

    def _delete_photo(self):
        item = self.photos.currentItem()
        if item is None:
            self.ctx.notify.emit("Sélectionnez une photo.", "info")
            return
        self.ctx.repo.delete_photo(item.data(Qt.ItemDataRole.UserRole))
        self.ctx.refresh_gallery()
        self.reload()

    def _reencode(self):
        if self.ctx.engine is None:
            return
        engine, repo = self.ctx.engine, self.ctx.repo
        self.reencode_btn.setEnabled(False)
        run_async(lambda progress: repo.reencode_all(engine, progress=lambda d, n: progress("Recalcul des empreintes", d, n)),
                  on_done=self._reencoded, on_error=lambda m: self.ctx.notify.emit(m, "error"),
                  on_progress=lambda l, d, n: self.ctx.busy.emit(l, d, n))

    def _reencoded(self, res):
        ok, fail = res
        self.reencode_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.ctx.refresh_gallery()
        self._check_model()
        self.ctx.notify.emit(f"Empreintes recalculées : {ok} réussie(s), {fail} échec(s).", "success" if not fail else "warning")
