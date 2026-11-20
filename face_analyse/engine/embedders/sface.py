"""Embedder SFace (OpenCV Zoo, Apache-2.0) via ``cv2.FaceRecognizerSF``.

Sortie : vecteur 128-D. Entraîné avec une perte « sigmoid-constrained
hypersphere » sur MS-Celeb-1M.
"""

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np

from face_analyse.core.errors import ModelError
from face_analyse.engine.interfaces import FaceEmbedder
from face_analyse.engine.types import DetectedFace


class SFaceEmbedder(FaceEmbedder):
    model_id = "sface-2021dec"
    dim = 128
    default_threshold = 0.363  # valeur publiée par OpenCV pour la similarité cosinus

    def __init__(self, model_path: Path):
        if not Path(model_path).is_file():
            raise ModelError(f"Modèle SFace introuvable : {model_path}")
        try:
            self._rec = cv2.FaceRecognizerSF.create(str(model_path), "")
        except cv2.error as exc:
            raise ModelError("Chargement du modèle SFace impossible") from exc
        self._lock = threading.Lock()

    def align(self, image_bgr: np.ndarray, face: DetectedFace) -> np.ndarray:
        with self._lock:
            return self._rec.alignCrop(image_bgr, face.to_yunet_row())

    def embed_aligned(self, aligned_bgr: np.ndarray) -> np.ndarray:
        with self._lock:
            return self._rec.feature(aligned_bgr).reshape(-1)
