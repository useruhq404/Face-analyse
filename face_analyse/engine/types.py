"""Structures de données échangées entre les étages du moteur.

Les trois étages sont strictement séparés :

1. **Détection**   : image  -> ``DetectedFace`` (boîte, 5 points, score)
2. **Embedding**   : image + ``DetectedFace`` -> ``FaceEmbedding`` (vecteur L2-normalisé)
3. **Identité**    : ``FaceEmbedding`` + galerie -> ``IdentityDecision``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


@dataclass(frozen=True)
class DetectedFace:
    """Visage détecté, coordonnées dans le repère de l'image d'origine."""

    x: float
    y: float
    w: float
    h: float
    landmarks: np.ndarray  # (5, 2) : œil droit, œil gauche, nez, coin bouche droit, gauche
    score: float

    @property
    def box(self) -> tuple[int, int, int, int]:
        return int(round(self.x)), int(round(self.y)), int(round(self.w)), int(round(self.h))

    @property
    def size(self) -> float:
        return float(min(self.w, self.h))

    def to_yunet_row(self) -> np.ndarray:
        """Format 15 colonnes attendu par ``cv2.FaceRecognizerSF.alignCrop``."""
        return np.array(
            [self.x, self.y, self.w, self.h, *self.landmarks.reshape(-1), self.score],
            dtype=np.float32,
        )


@dataclass(frozen=True)
class FaceEmbedding:
    vector: np.ndarray  # (D,) float32, norme L2 = 1
    model_id: str

    def __post_init__(self):
        if self.vector.ndim != 1:
            raise ValueError("L'embedding doit être un vecteur 1D")


@dataclass
class FaceQuality:
    """Indicateurs de qualité ; servent à prévenir l'utilisateur, pas à décider."""

    face_size: float
    sharpness: float  # variance du Laplacien sur le visage aligné
    brightness: float  # luminance moyenne 0-255
    yaw_ratio: float  # 0 = de face, 1 = profil
    detection_score: float
    score: float = 0.0  # synthèse 0-1
    warnings: list[str] = field(default_factory=list)


class MatchStatus(str, Enum):
    MATCH = "MATCH"  # au-dessus du seuil, sans ambiguïté
    AMBIGUOUS = "AMBIGUOUS"  # au-dessus du seuil mais 2 identités proches
    UNKNOWN = "UNKNOWN"  # sous le seuil : aucune identité n'est retournée


@dataclass(frozen=True)
class Candidate:
    person_id: int
    display_name: str
    similarity: float  # similarité cosinus [-1, 1] — PAS une probabilité
    best_reference_id: int | None = None


@dataclass
class IdentityDecision:
    status: MatchStatus
    threshold: float
    candidates: list[Candidate]  # triés par similarité décroissante
    note: str = ""

    @property
    def identity(self) -> Candidate | None:
        """Identité retenue — ``None`` si UNKNOWN. Jamais inventée."""
        if self.status == MatchStatus.UNKNOWN or not self.candidates:
            return None
        return self.candidates[0]

    @property
    def label(self) -> str:
        ident = self.identity
        if ident is None:
            return "UNKNOWN"
        prefix = "? " if self.status == MatchStatus.AMBIGUOUS else ""
        return f"{prefix}{ident.display_name}"


@dataclass
class FaceAnalysis:
    """Résultat complet pour un visage d'une image."""

    face: DetectedFace
    embedding: FaceEmbedding | None
    quality: FaceQuality
    decision: IdentityDecision | None = None
