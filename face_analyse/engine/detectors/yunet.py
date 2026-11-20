"""Détecteur YuNet (OpenCV Zoo, licence MIT) via ``cv2.FaceDetectorYN``."""

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np

from face_analyse.core.errors import ModelError
from face_analyse.engine.interfaces import FaceDetector
from face_analyse.engine.preprocessing import enhance_low_light, resize_max_side
from face_analyse.engine.types import DetectedFace


class YuNetDetector(FaceDetector):
    name = "yunet"

    def __init__(
        self,
        model_path: Path,
        score_threshold: float = 0.8,
        nms_threshold: float = 0.3,
        max_side: int = 1280,
        min_face_size: int = 20,
        enhance_lighting: bool = True,
        upscale_small: bool = True,
    ):
        if not Path(model_path).is_file():
            raise ModelError(f"Modèle YuNet introuvable : {model_path}")
        try:
            self._det = cv2.FaceDetectorYN.create(
                str(model_path), "", (320, 320), score_threshold, nms_threshold, 5000
            )
        except cv2.error as exc:
            raise ModelError("Chargement du modèle YuNet impossible") from exc
        self.score_threshold = score_threshold
        self.max_side = max_side
        self.min_face_size = min_face_size
        self.enhance_lighting = enhance_lighting
        self.upscale_small = upscale_small
        self._lock = threading.Lock()

    def set_score_threshold(self, value: float) -> None:
        self.score_threshold = value
        self._det.setScoreThreshold(value)

    def _run(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        with self._lock:
            self._det.setInputSize((w, h))
            _, faces = self._det.detect(image)
        return faces if faces is not None else np.empty((0, 15), np.float32)

    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        if image_bgr is None or image_bgr.size == 0:
            return []
        if image_bgr.ndim == 2:
            image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)
        elif image_bgr.shape[2] == 4:
            image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_BGRA2BGR)

        work, scale = resize_max_side(image_bgr, self.max_side)
        # Les petites images (miniatures, photos d'identité basse définition)
        # sont agrandies : YuNet détecte mal les visages < ~20 px.
        if self.upscale_small and max(work.shape[:2]) < 320:
            factor = 320.0 / max(work.shape[:2])
            work = cv2.resize(work, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
            scale *= factor
        if self.enhance_lighting:
            work = enhance_low_light(work)

        rows = self._run(work)
        results: list[DetectedFace] = []
        inv = 1.0 / scale
        for r in rows:
            face = DetectedFace(
                x=float(r[0]) * inv,
                y=float(r[1]) * inv,
                w=float(r[2]) * inv,
                h=float(r[3]) * inv,
                landmarks=(r[4:14].reshape(5, 2) * inv).astype(np.float32),
                score=float(r[14]),
            )
            if face.size >= self.min_face_size:
                results.append(face)
        results.sort(key=lambda f: f.w * f.h, reverse=True)
        return results
