"""Capture vidéo + détection/suivi/reconnaissance dans un thread dédié."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass

import cv2
import numpy as np
from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal
from PySide6.QtGui import QImage

from face_analyse.engine.pipeline import FaceEngine
from face_analyse.engine.tracking import FaceTracker
from face_analyse.ui.widgets.image_view import bgr_to_qimage

log = logging.getLogger(__name__)


@dataclass
class TrackView:
    track_id: int
    box: tuple[float, float, float, float]
    label: str
    known: bool
    similarity: float | None


def open_capture(index: int) -> cv2.VideoCapture | None:
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF] if sys.platform.startswith("win") else [cv2.CAP_ANY]
    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if cap is not None and cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            ok, _ = cap.read()
            if ok:
                return cap
        if cap is not None:
            cap.release()
    return None


class CameraThread(QThread):
    frame_ready = Signal(QImage, list)  # image, list[TrackView]
    stats = Signal(float, int)  # fps, nombre de visages
    failed = Signal(str)
    opened = Signal(int)  # index réellement ouvert

    def __init__(self, engine: FaceEngine, index: int, mirror: bool, recognition_interval: int = 5):
        super().__init__()
        self.engine = engine
        self.index = index
        self.mirror = mirror
        self.interval = max(1, recognition_interval)
        self._stop = False
        self._mutex = QMutex()
        self._last_frame: np.ndarray | None = None
        self.tracker = FaceTracker()

    def stop(self):
        self._stop = True
        self.wait(3000)

    def last_frame(self) -> np.ndarray | None:
        with QMutexLocker(self._mutex):
            return None if self._last_frame is None else self._last_frame.copy()

    def run(self):
        cap = open_capture(self.index)
        if cap is None:
            self.failed.emit(f"Impossible d'ouvrir la caméra n°{self.index}. Vérifiez qu'elle est branchée, "
                             "qu'aucune autre application ne l'utilise, et que Windows autorise l'accès "
                             "(Paramètres › Confidentialité › Caméra).")
            return
        self.opened.emit(self.index)
        t_prev = time.perf_counter()
        fps = 0.0
        misses = 0
        try:
            while not self._stop:
                ok, frame = cap.read()
                if not ok or frame is None:
                    misses += 1
                    if misses > 30:
                        self.failed.emit("Flux caméra interrompu.")
                        break
                    self.msleep(10)
                    continue
                misses = 0
                if self.mirror:
                    frame = cv2.flip(frame, 1)
                with QMutexLocker(self._mutex):
                    self._last_frame = frame

                faces = self.engine.detector.detect(frame)
                tracks = self.tracker.update(faces)
                views = []
                for t in tracks:
                    if t.frames_since_recognition >= self.interval:
                        try:
                            emb = self.engine.embedding_for(frame, t.face)
                            t.add_decision(self.engine.matcher.search(emb, top_k=2))
                        except ValueError:
                            pass
                        t.frames_since_recognition = 0
                    x, y, w, h = (float(v) for v in t.smooth_box)
                    views.append(TrackView(t.track_id, (x, y, w, h), t.label, t.is_known, t.last_similarity))

                now = time.perf_counter()
                fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_prev, 1e-3))
                t_prev = now
                self.frame_ready.emit(bgr_to_qimage(frame), views)
                self.stats.emit(fps, len(views))
        except Exception as exc:  # noqa: BLE001
            log.exception("Erreur caméra")
            self.failed.emit(f"Erreur caméra : {exc}")
        finally:
            cap.release()
