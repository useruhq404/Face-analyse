"""Benchmark du moteur sur un jeu de données autorisé (LFW par défaut).

LFW (Labeled Faces in the Wild, UMass Amherst) est un jeu de données public
destiné à la recherche en vérification faciale. Mesures produites :

* **Vérification** (protocole officiel, 6 000 paires, 10 plis) : précision,
  AUC, EER, TAR à FAR fixé, seuil optimal.
* **Identification en ensemble ouvert** : une galerie d'identités enrôlées
  et des sondes dont une partie n'est PAS dans la galerie ; on mesure le
  taux d'identification correcte et, surtout, le taux de **fausses
  identifications** de personnes absentes (doivent sortir UNKNOWN).
* **Robustesse** : sous-exposition, surexposition, basse résolution,
  compression JPEG forte, flou.
"""

from __future__ import annotations

import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from face_analyse.engine.pipeline import FaceEngine
from face_analyse.engine.preprocessing import load_image
from face_analyse.engine.types import DetectedFace, FaceEmbedding

log = logging.getLogger(__name__)

Degradation = Callable[[np.ndarray], np.ndarray]


# ---------------------------------------------------------------- dégradations
def _gamma(img: np.ndarray, g: float) -> np.ndarray:
    lut = np.clip(((np.arange(256) / 255.0) ** g) * 255.0, 0, 255).astype(np.uint8)
    return cv2.LUT(img, lut)


DEGRADATIONS: dict[str, Degradation] = {
    "original": lambda im: im,
    "sombre": lambda im: _gamma((im * 0.35).astype(np.uint8), 1.0),
    "surexpose": lambda im: cv2.convertScaleAbs(im, alpha=1.6, beta=70),
    "basse_resolution": lambda im: cv2.resize(
        cv2.resize(im, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA),
        (im.shape[1], im.shape[0]), interpolation=cv2.INTER_LINEAR),
    "jpeg_q15": lambda im: cv2.imdecode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 15])[1], cv2.IMREAD_COLOR),
    "flou": lambda im: cv2.GaussianBlur(im, (0, 0), 2.0),
}


# ---------------------------------------------------------------- données LFW
@dataclass(frozen=True)
class Pair:
    a: Path
    b: Path
    same: bool
    fold: int


def lfw_image(root: Path, name: str, idx: int) -> Path:
    return root / name / f"{name}_{idx:04d}.jpg"


def parse_lfw_pairs(pairs_txt: Path, images_root: Path) -> list[Pair]:
    lines = pairs_txt.read_text().strip().splitlines()
    n_folds, n_per = (int(x) for x in lines[0].split())
    pairs: list[Pair] = []
    body = lines[1:]
    for i, line in enumerate(body):
        fold = i // (2 * n_per)
        parts = line.split("\t")
        if len(parts) == 3:
            pairs.append(Pair(lfw_image(images_root, parts[0], int(parts[1])),
                              lfw_image(images_root, parts[0], int(parts[2])), True, fold))
        elif len(parts) == 4:
            pairs.append(Pair(lfw_image(images_root, parts[0], int(parts[1])),
                              lfw_image(images_root, parts[2], int(parts[3])), False, fold))
    assert len(pairs) == n_folds * n_per * 2, "pairs.txt incomplet"
    return pairs


# ---------------------------------------------------------------- embeddings
class EmbeddingCache:
    """Calcule (et mémorise) l'embedding du visage central d'une image."""

    def __init__(self, engine: FaceEngine, degradation: Degradation):
        self.engine = engine
        self.degradation = degradation
        self.cache: dict[Path, FaceEmbedding | None] = {}
        self.failures = 0
        self.total_ms = 0.0

    @staticmethod
    def _central(faces: list[DetectedFace], shape) -> DetectedFace:
        cy, cx = shape[0] / 2, shape[1] / 2
        return min(faces, key=lambda f: (f.x + f.w / 2 - cx) ** 2 + (f.y + f.h / 2 - cy) ** 2)

    def get(self, path: Path) -> FaceEmbedding | None:
        if path in self.cache:
            return self.cache[path]
        img = self.degradation(load_image(path))
        t0 = time.perf_counter()
        faces = self.engine.detector.detect(img)
        emb = None
        if faces:
            emb = self.engine.embedding_for(img, self._central(faces, img.shape))
        else:
            self.failures += 1
        self.total_ms += (time.perf_counter() - t0) * 1000
        self.cache[path] = emb
        return emb


# ---------------------------------------------------------------- métriques
def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos, neg = scores[labels], scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order))
    ranks[order] = np.arange(1, len(order) + 1)
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def best_threshold(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    cand = np.unique(scores)
    best_t, best_acc = 0.0, -1.0
    for t in np.linspace(cand.min(), cand.max(), 2000):
        acc = float(((scores >= t) == labels).mean())
        if acc > best_acc:
            best_t, best_acc = float(t), acc
    return best_t, best_acc


def rates_at(scores: np.ndarray, labels: np.ndarray, t: float) -> tuple[float, float]:
    """(FMR = faux positifs, FNMR = faux négatifs) au seuil t."""
    fmr = float((scores[~labels] >= t).mean()) if (~labels).any() else 0.0
    fnmr = float((scores[labels] < t).mean()) if labels.any() else 0.0
    return fmr, fnmr


def threshold_at_fmr(scores: np.ndarray, labels: np.ndarray, fmr: float) -> float:
    neg = np.sort(scores[~labels])[::-1]
    k = max(int(np.floor(fmr * len(neg))), 0)
    return float(neg[k]) + 1e-6 if k < len(neg) else float(neg[-1])


def eer(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Taux d'égale erreur (FMR = FNMR) et seuil correspondant."""
    best_gap, best_val, best_t = np.inf, 1.0, 0.0
    for t in np.linspace(scores.min(), scores.max(), 2000):
        fmr, fnmr = rates_at(scores, labels, t)
        if abs(fmr - fnmr) < best_gap:
            best_gap, best_val, best_t = abs(fmr - fnmr), (fmr + fnmr) / 2, float(t)
    return best_val, best_t


@dataclass
class VerificationReport:
    variant: str
    n_pairs: int
    n_skipped: int
    detection_failures: int
    accuracy_10fold_mean: float
    accuracy_10fold_std: float
    auc: float
    eer: float
    best_threshold: float
    fmr_at_threshold: dict[str, tuple[float, float]] = field(default_factory=dict)
    tar_at_far: dict[str, float] = field(default_factory=dict)
    ms_per_image: float = 0.0
    genuine_mean: float = 0.0
    impostor_mean: float = 0.0


def verification(pairs: list[Pair], engine: FaceEngine, variant: str = "original",
                 thresholds: tuple[float, ...] = (0.363, 0.40, 0.45, 0.50, 0.55, 0.60)) -> tuple[VerificationReport, np.ndarray, np.ndarray]:
    cache = EmbeddingCache(engine, DEGRADATIONS[variant])
    scores, labels, folds = [], [], []
    skipped = 0
    for p in pairs:
        ea, eb = cache.get(p.a), cache.get(p.b)
        if ea is None or eb is None:
            # Protocole strict : une paire non détectée compte comme rejet
            # (score -1) — on ne l'exclut pas pour ne pas embellir les chiffres.
            skipped += 1
            s = -1.0
        else:
            s = float(np.dot(ea.vector, eb.vector))
        scores.append(s)
        labels.append(p.same)
        folds.append(p.fold)
    s_arr, l_arr, f_arr = np.array(scores), np.array(labels), np.array(folds)

    accs = []
    for k in np.unique(f_arr):
        train, test = f_arr != k, f_arr == k
        t, _ = best_threshold(s_arr[train], l_arr[train])
        accs.append(float(((s_arr[test] >= t) == l_arr[test]).mean()))
    t_best, _ = best_threshold(s_arr, l_arr)
    e, _ = eer(s_arr, l_arr)
    rep = VerificationReport(
        variant=variant,
        n_pairs=len(pairs),
        n_skipped=skipped,
        detection_failures=cache.failures,
        accuracy_10fold_mean=float(np.mean(accs)),
        accuracy_10fold_std=float(np.std(accs)),
        auc=roc_auc(s_arr, l_arr),
        eer=e,
        best_threshold=t_best,
        ms_per_image=cache.total_ms / max(len(cache.cache), 1),
        genuine_mean=float(s_arr[l_arr].mean()),
        impostor_mean=float(s_arr[~l_arr].mean()),
    )
    for t in thresholds:
        rep.fmr_at_threshold[f"{t:.3f}"] = rates_at(s_arr, l_arr, t)
    for far in (1e-3, 1e-2):
        t = threshold_at_fmr(s_arr, l_arr, far)
        rep.tar_at_far[f"{far:g}"] = 1.0 - rates_at(s_arr, l_arr, t)[1]
        rep.tar_at_far[f"seuil@{far:g}"] = t
    return rep, s_arr, l_arr


# ---------------------------------------------------------------- open-set
@dataclass
class OpenSetReport:
    threshold: float
    gallery_identities: int
    gallery_refs_per_identity: int
    known_probes: int
    unknown_probes: int
    correct_identification_rate: float  # sonde connue -> bonne identité
    wrong_identity_rate: float  # sonde connue -> MAUVAISE identité nommée
    known_rejected_rate: float  # sonde connue -> UNKNOWN (faux négatif)
    unknown_false_identification_rate: float  # sonde absente -> un nom est donné (faux positif)


def open_set(images_root: Path, engine: FaceEngine, thresholds: tuple[float, ...],
             n_gallery: int = 300, n_unknown: int = 600, refs: int = 3, seed: int = 0) -> list[OpenSetReport]:
    from face_analyse.engine.matcher import GalleryEntry, IdentityMatcher

    rng = random.Random(seed)
    people = defaultdict(list)
    for d in sorted(images_root.iterdir()):
        if d.is_dir():
            people[d.name] = sorted(d.glob("*.jpg"))
    rich = [n for n, imgs in people.items() if len(imgs) >= refs + 1]
    singles = [n for n, imgs in people.items() if len(imgs) == 1]
    rng.shuffle(rich)
    rng.shuffle(singles)
    gallery_names = rich[:n_gallery]
    unknown_names = singles[:n_unknown]

    cache = EmbeddingCache(engine, DEGRADATIONS["original"])
    entries: list[GalleryEntry] = []
    probes: list[tuple[int | None, FaceEmbedding]] = []
    ref_id = 0
    for pid, name in enumerate(gallery_names):
        imgs = people[name]
        for path in imgs[:refs]:
            e = cache.get(path)
            if e is not None:
                ref_id += 1
                entries.append(GalleryEntry(ref_id, pid, name, e.vector, e.model_id))
        probe = cache.get(imgs[refs])
        if probe is not None:
            probes.append((pid, probe))
    for name in unknown_names:
        e = cache.get(people[name][0])
        if e is not None:
            probes.append((None, e))

    reports = []
    for t in thresholds:
        m = IdentityMatcher(t, ambiguity_margin=0.0)
        m.load(entries, engine.embedder.model_id)
        ok = wrong = rej = known = unk = unk_fp = 0
        for truth, emb in probes:
            ident = m.search(emb, top_k=1).identity
            if truth is None:
                unk += 1
                unk_fp += ident is not None
            else:
                known += 1
                if ident is None:
                    rej += 1
                elif ident.person_id == truth:
                    ok += 1
                else:
                    wrong += 1
        reports.append(OpenSetReport(
            threshold=t, gallery_identities=len(gallery_names), gallery_refs_per_identity=refs,
            known_probes=known, unknown_probes=unk,
            correct_identification_rate=ok / max(known, 1),
            wrong_identity_rate=wrong / max(known, 1),
            known_rejected_rate=rej / max(known, 1),
            unknown_false_identification_rate=unk_fp / max(unk, 1),
        ))
    return reports
