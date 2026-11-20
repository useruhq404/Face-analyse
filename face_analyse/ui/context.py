"""État partagé de l'application : paramètres, base, moteur (chargé en tâche de fond)."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal

from face_analyse.core.config import Settings
from face_analyse.database.repository import Repository
from face_analyse.engine.pipeline import FaceEngine
from face_analyse.ui.workers import run_async

log = logging.getLogger(__name__)


class AppContext(QObject):
    engine_ready = Signal()
    engine_failed = Signal(str)
    gallery_changed = Signal()
    notify = Signal(str, str)  # message, niveau (info/success/warning/error)
    busy = Signal(str, int, int)  # libellé, fait, total (total=0 : indéterminé, -1 : terminé)
    account_revoked = Signal(str)  # session fermée à distance / compte suspendu

    def __init__(self, settings: Settings, repo: Repository, auth=None):
        super().__init__()
        self.settings = settings
        self.repo = repo
        self.auth = auth  # face_analyse.auth.client.AuthClient | None
        self.engine: FaceEngine | None = None
        self.engine_error: str = ""
        self._loaded_keys: tuple[str, str] | None = None
        self._heartbeat: QTimer | None = None

    # ------------------------------------------------------------ moteur
    def load_engine(self) -> None:
        self.busy.emit("Chargement des modèles…", 0, 0)
        run_async(FaceEngine.from_settings, self.settings.engine,
                  on_done=self._engine_loaded, on_error=self._engine_error)

    def _engine_loaded(self, engine: FaceEngine) -> None:
        self.engine = engine
        self._loaded_keys = (self.settings.engine.detector, self.settings.engine.embedder)
        self.engine_error = ""
        self.refresh_gallery()
        self.busy.emit("", -1, -1)
        self.engine_ready.emit()

    def _engine_error(self, msg: str) -> None:
        self.engine = None
        self.engine_error = msg
        self.busy.emit("", -1, -1)
        self.engine_failed.emit(msg)
        self.notify.emit(msg, "error")

    def refresh_gallery(self) -> None:
        if self.engine is None:
            return
        entries = self.repo.gallery(self.engine.embedder.model_id)
        n = self.engine.matcher.load(entries, self.engine.embedder.model_id)
        log.info("Galerie : %d références, %d personnes", n, self.engine.matcher.person_count)
        self.gallery_changed.emit()

    def apply_engine_settings(self) -> None:
        """Applique seuils et options sans recharger les modèles si possible."""
        if self.engine is None:
            return
        s = self.settings.engine
        if (s.detector, s.embedder) != self._loaded_keys:
            self.load_engine()  # changement de modèle : rechargement complet
            return
        self.engine.matcher.threshold = s.match_threshold
        self.engine.matcher.ambiguity_margin = s.ambiguity_margin
        det = self.engine.detector
        if hasattr(det, "set_score_threshold"):
            det.set_score_threshold(s.detection_score)
        if hasattr(det, "enhance_lighting"):
            det.enhance_lighting = s.enhance_lighting

    # ------------------------------------------------------------ compte / télémétrie
    @property
    def account(self):
        return self.auth.account if self.auth else None

    def log_event(self, module: str, action: str, detail: dict | None = None) -> None:
        """Journalise une action côté serveur (si connecté), sans bloquer l'UI.

        N'envoie jamais le contenu des images ni des recherches — seulement le
        module et l'action, comme annoncé à l'utilisateur à la connexion.
        """
        if self.auth is None or not self.auth.token:
            return
        run_async(self.auth.log_event, module, action, detail or {})

    def start_heartbeat(self) -> None:
        if self.auth is None or not self.auth.token:
            return
        interval = max(15, self.settings.auth.heartbeat_s) * 1000
        self._heartbeat = QTimer(self)
        self._heartbeat.timeout.connect(self._tick_heartbeat)
        self._heartbeat.start(interval)

    def stop_heartbeat(self) -> None:
        if self._heartbeat is not None:
            self._heartbeat.stop()
            self._heartbeat = None

    def _tick_heartbeat(self) -> None:
        if self.auth is None:
            return
        run_async(self.auth.heartbeat, on_done=self._heartbeat_ok, on_error=self._heartbeat_failed)

    def _heartbeat_ok(self, data: dict) -> None:
        if data.get("user_status") == "banned":
            self.account_revoked.emit("Votre compte a été suspendu par l'administrateur.")

    def _heartbeat_failed(self, msg: str) -> None:
        # Session révoquée à distance, ou serveur injoignable.
        if "révoquée" in msg or "suspendu" in msg or "invalide" in msg:
            self.account_revoked.emit(msg)
