"""Recherche d'identité dans la galerie locale (personnes consentantes).

Règles intangibles :

* La similarité cosinus est une **mesure de ressemblance**, pas une
  probabilité d'identité.
* En dessous du seuil : ``UNKNOWN``. Aucun nom n'est retourné.
* Une personne absente de la galerie ne peut jamais être nommée : la
  galerie est la seule source d'identités.
* Plusieurs photos de référence par personne : le score d'une personne
  est la meilleure similarité parmi ses références.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from face_analyse.engine.types import Candidate, FaceEmbedding, IdentityDecision, MatchStatus


@dataclass(frozen=True)
class GalleryEntry:
    reference_id: int
    person_id: int
    display_name: str
    vector: np.ndarray
    model_id: str


class IdentityMatcher:
    """Index en mémoire (produit matriciel vectorisé, ~µs pour 10⁴ références)."""

    def __init__(self, threshold: float, ambiguity_margin: float = 0.05):
        self.threshold = float(threshold)
        self.ambiguity_margin = float(ambiguity_margin)
        self._lock = threading.RLock()
        self._model_id: str | None = None
        self._matrix = np.empty((0, 0), np.float32)
        self._person_ids = np.empty(0, np.int64)
        self._ref_ids = np.empty(0, np.int64)
        self._names: dict[int, str] = {}

    # ------------------------------------------------------------------
    def load(self, entries: list[GalleryEntry], model_id: str) -> int:
        """Charge les références compatibles avec ``model_id``. Retourne leur nombre."""
        usable = [e for e in entries if e.model_id == model_id]
        with self._lock:
            self._model_id = model_id
            if usable:
                self._matrix = np.stack([e.vector.astype(np.float32) for e in usable])
                self._matrix /= np.linalg.norm(self._matrix, axis=1, keepdims=True)
            else:
                self._matrix = np.empty((0, 0), np.float32)
            self._person_ids = np.array([e.person_id for e in usable], np.int64)
            self._ref_ids = np.array([e.reference_id for e in usable], np.int64)
            self._names = {e.person_id: e.display_name for e in usable}
        return len(usable)

    @property
    def size(self) -> int:
        return int(self._matrix.shape[0])

    @property
    def person_count(self) -> int:
        return len(self._names)

    # ------------------------------------------------------------------
    def search(self, query: FaceEmbedding, top_k: int = 5) -> IdentityDecision:
        with self._lock:
            if self._model_id is not None and query.model_id != self._model_id:
                return IdentityDecision(
                    MatchStatus.UNKNOWN, self.threshold, [],
                    note="Modèle de l'embedding différent de celui de la galerie : comparaison refusée.",
                )
            if self.size == 0:
                return IdentityDecision(
                    MatchStatus.UNKNOWN, self.threshold, [],
                    note="Base locale vide : aucune identité ne peut être proposée.",
                )
            sims = self._matrix @ query.vector.astype(np.float32)
            person_ids, ref_ids, names = self._person_ids, self._ref_ids, self._names

        # Meilleure référence par personne (vectorisé).
        order = np.argsort(-sims)
        seen: set[int] = set()
        candidates: list[Candidate] = []
        for idx in order:
            pid = int(person_ids[idx])
            if pid in seen:
                continue
            seen.add(pid)
            candidates.append(Candidate(pid, names[pid], float(sims[idx]), int(ref_ids[idx])))
            if len(candidates) >= top_k:
                break

        best = candidates[0]
        if best.similarity < self.threshold:
            return IdentityDecision(
                MatchStatus.UNKNOWN, self.threshold, candidates,
                note=(f"Meilleure similarité {best.similarity:.3f} < seuil {self.threshold:.3f} : "
                      "visage non reconnu dans la base consentante."),
            )
        if len(candidates) > 1 and best.similarity - candidates[1].similarity < self.ambiguity_margin \
                and candidates[1].similarity >= self.threshold:
            return IdentityDecision(
                MatchStatus.AMBIGUOUS, self.threshold, candidates,
                note="Deux identités enregistrées ont des scores très proches : vérification humaine requise.",
            )
        return IdentityDecision(
            MatchStatus.MATCH, self.threshold, candidates,
            note="Ressemblance au-dessus du seuil. Ce n'est pas une preuve d'identité.",
        )


def cosine_similarity(a: FaceEmbedding, b: FaceEmbedding) -> float:
    if a.model_id != b.model_id:
        raise ValueError("Embeddings issus de modèles différents : non comparables")
    return float(np.dot(a.vector, b.vector))
