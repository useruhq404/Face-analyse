"""Évaluation de la qualité d'un visage (taille, netteté, exposition, pose).

Ces indicateurs n'interviennent pas dans la décision d'identité : ils
alertent l'utilisateur quand le score de similarité est moins fiable.
"""

from __future__ import annotations

import cv2
import numpy as np

from face_analyse.engine.types import DetectedFace, FaceQuality


def estimate_yaw_ratio(landmarks: np.ndarray) -> float:
    """Approximation de la rotation horizontale à partir des 5 points.

    Compare la distance nez→œil droit et nez→œil gauche. 0 = face, ~1 = profil.
    """
    pts = np.asarray(landmarks, dtype=np.float32).reshape(5, 2)
    right_eye, left_eye, nose = pts[0], pts[1], pts[2]
    d_r = abs(nose[0] - right_eye[0])
    d_l = abs(left_eye[0] - nose[0])
    total = d_r + d_l
    if total < 1e-6:
        return 1.0
    return float(abs(d_r - d_l) / total)


def assess(face: DetectedFace, aligned_bgr: np.ndarray | None) -> FaceQuality:
    warnings: list[str] = []
    sharpness = 0.0
    brightness = 0.0
    if aligned_bgr is not None and aligned_bgr.size:
        gray = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
    yaw = estimate_yaw_ratio(face.landmarks)

    size_s = float(np.clip((face.size - 30.0) / 90.0, 0.0, 1.0))
    sharp_s = float(np.clip(sharpness / 150.0, 0.0, 1.0))
    bright_s = float(np.clip(1.0 - abs(brightness - 120.0) / 100.0, 0.0, 1.0))
    pose_s = float(np.clip(1.0 - yaw / 0.7, 0.0, 1.0))
    det_s = float(np.clip((face.score - 0.6) / 0.35, 0.0, 1.0))
    score = 0.25 * size_s + 0.2 * sharp_s + 0.15 * bright_s + 0.25 * pose_s + 0.15 * det_s

    if face.size < 60:
        warnings.append(f"Visage de petite taille ({face.size:.0f} px) : précision réduite")
    if sharpness < 40:
        warnings.append("Image floue")
    if brightness < 50:
        warnings.append("Visage sous-exposé")
    elif brightness > 210:
        warnings.append("Visage surexposé")
    if yaw > 0.45:
        warnings.append("Visage tourné / de profil : précision réduite")
    if face.score < 0.85:
        warnings.append("Détection peu confiante")

    return FaceQuality(
        face_size=face.size,
        sharpness=sharpness,
        brightness=brightness,
        yaw_ratio=yaw,
        detection_score=face.score,
        score=float(score),
        warnings=warnings,
    )
