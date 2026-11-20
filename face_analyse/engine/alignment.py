"""Alignement 5 points vers le gabarit ArcFace standard 112×112.

Utilisé par les embedders ONNX génériques (le gabarit est celui
d'InsightFace / ArcFace, aussi utilisé en interne par SFace).
"""

from __future__ import annotations

import cv2
import numpy as np

ARCFACE_TEMPLATE_112 = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def align_5pts(image_bgr: np.ndarray, landmarks: np.ndarray, size: int = 112) -> np.ndarray:
    src = np.asarray(landmarks, dtype=np.float32).reshape(5, 2)
    dst = ARCFACE_TEMPLATE_112 * (size / 112.0)
    matrix, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    if matrix is None:
        raise ValueError("Alignement impossible (points de repère dégénérés)")
    return cv2.warpAffine(image_bgr, matrix, (size, size), borderValue=0)
