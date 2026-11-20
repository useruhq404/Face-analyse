"""Contrats abstraits : tout nouveau modèle implémente l'une de ces classes.

Remplacer un modèle = écrire une sous-classe + l'enregistrer dans
``engine.registry``. Le reste de l'application (UI, base, recherche) ne
dépend que de ces interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from face_analyse.engine.types import DetectedFace, FaceEmbedding


class FaceDetector(ABC):
    """Détecte tous les visages d'une image BGR, connus ou non."""

    name: str = "detector"

    @abstractmethod
    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        ...


class FaceEmbedder(ABC):
    """Transforme un visage détecté en vecteur L2-normalisé."""

    #: Identifiant stocké avec chaque embedding. Deux modèles différents
    #: produisent des espaces incomparables : la recherche ne mélange jamais
    #: des embeddings de ``model_id`` différents.
    model_id: str = "embedder"
    dim: int = 0
    #: Seuil cosinus suggéré par l'auteur du modèle (avant calibration).
    default_threshold: float = 0.5

    @abstractmethod
    def align(self, image_bgr: np.ndarray, face: DetectedFace) -> np.ndarray:
        """Retourne le recadrage aligné utilisé par le modèle."""

    @abstractmethod
    def embed_aligned(self, aligned_bgr: np.ndarray) -> np.ndarray:
        """Vecteur brut (non normalisé) pour un recadrage aligné."""

    def embed(self, image_bgr: np.ndarray, face: DetectedFace, flip_tta: bool = True) -> FaceEmbedding:
        aligned = self.align(image_bgr, face)
        vec = self.embed_aligned(aligned).astype(np.float32).reshape(-1)
        if flip_tta:
            # Moyenne avec le miroir horizontal : plus robuste à l'angle.
            vec = vec + self.embed_aligned(np.ascontiguousarray(aligned[:, ::-1])).astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm == 0.0 or not np.isfinite(norm):
            raise ValueError("Embedding dégénéré")
        return FaceEmbedding(vector=vec / norm, model_id=self.model_id)
