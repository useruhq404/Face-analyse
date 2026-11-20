"""Suivi des visages en vidéo (association par IoU) + vote temporel.

La détection tourne à chaque image ; la reconnaissance (plus coûteuse) est
faite périodiquement par piste. L'étiquette affichée est le résultat d'un
vote sur les dernières décisions : un nom n'apparaît que s'il est
majoritaire et au-dessus du seuil, sinon la piste reste UNKNOWN.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

import numpy as np

from face_analyse.engine.types import DetectedFace, IdentityDecision, MatchStatus


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    track_id: int
    face: DetectedFace
    smooth_box: np.ndarray
    age: int = 0
    missed: int = 0
    frames_since_recognition: int = 10**6
    votes: deque = field(default_factory=lambda: deque(maxlen=7))
    last_similarity: float | None = None

    def add_decision(self, d: IdentityDecision) -> None:
        ident = d.identity
        if d.status == MatchStatus.MATCH and ident is not None:
            self.votes.append((ident.person_id, ident.display_name))
        else:
            self.votes.append((None, "UNKNOWN"))
        self.last_similarity = d.candidates[0].similarity if d.candidates else None

    @property
    def label(self) -> str:
        if not self.votes:
            return "ANALYSE…"
        (pid, name), n = Counter(self.votes).most_common(1)[0]
        if pid is not None and n >= max(2, (len(self.votes) + 1) // 2):
            return name
        return "UNKNOWN" if len(self.votes) >= 2 else "ANALYSE…"

    @property
    def is_known(self) -> bool:
        return self.label not in ("UNKNOWN", "ANALYSE…")


class FaceTracker:
    def __init__(self, iou_threshold: float = 0.3, max_missed: int = 8, smoothing: float = 0.55):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.smoothing = smoothing
        self.tracks: list[Track] = []
        self._next_id = 1

    def update(self, faces: list[DetectedFace]) -> list[Track]:
        unmatched = set(range(len(faces)))
        pairs = sorted(
            ((iou(t.face.box, f.box), ti, fi) for ti, t in enumerate(self.tracks) for fi, f in enumerate(faces)),
            reverse=True,
        )
        used_tracks: set[int] = set()
        for score, ti, fi in pairs:
            if score < self.iou_threshold:
                break
            if ti in used_tracks or fi not in unmatched:
                continue
            t = self.tracks[ti]
            t.face = faces[fi]
            new_box = np.array(faces[fi].box, dtype=np.float32)
            # Lissage exponentiel : cadre fluide qui suit la tête sans trembler.
            t.smooth_box = self.smoothing * new_box + (1 - self.smoothing) * t.smooth_box
            t.age += 1
            t.missed = 0
            t.frames_since_recognition += 1
            used_tracks.add(ti)
            unmatched.discard(fi)

        for ti, t in enumerate(self.tracks):
            if ti not in used_tracks:
                t.missed += 1
        self.tracks = [t for t in self.tracks if t.missed <= self.max_missed]

        for fi in sorted(unmatched):
            f = faces[fi]
            self.tracks.append(Track(self._next_id, f, np.array(f.box, dtype=np.float32)))
            self._next_id += 1
        return [t for t in self.tracks if t.missed == 0]

    def reset(self) -> None:
        self.tracks.clear()
