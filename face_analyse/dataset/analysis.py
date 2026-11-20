"""Analyse de jeux de données : types, statistiques, histogrammes, doublons.

Aucune conclusion n'est inventée : les fonctions retournent des mesures brutes,
et l'interface signale explicitement quand l'échantillon est insuffisant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from face_analyse.dataset.loader import Dataset

MIN_SAMPLE = 5  # en dessous : statistiques non fiables


def _is_missing(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _to_float(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.replace(",", ".").strip())
        except ValueError:
            return None
    return None


@dataclass
class ColumnStats:
    name: str
    kind: str          # "numérique" | "texte" | "vide"
    count: int         # valeurs non manquantes
    missing: int
    distinct: int
    numeric: list[float]           # valeurs numériques (si applicable)
    top: list[tuple[str, int]]     # valeurs les plus fréquentes (texte)
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None

    @property
    def reliable(self) -> bool:
        return self.count >= MIN_SAMPLE


def column_stats(ds: Dataset, name: str) -> ColumnStats:
    values = ds.column(name)
    present = [v for v in values if not _is_missing(v)]
    missing = len(values) - len(present)
    distinct = len({str(v) for v in present})

    nums = [f for f in (_to_float(v) for v in present) if f is not None]
    numeric_ratio = (len(nums) / len(present)) if present else 0.0
    if present and numeric_ratio >= 0.8:
        kind = "numérique"
    elif not present:
        kind = "vide"
    else:
        kind = "texte"

    stats = ColumnStats(name=name, kind=kind, count=len(present), missing=missing,
                        distinct=distinct, numeric=nums, top=[])
    if kind == "numérique" and nums:
        stats.minimum = min(nums)
        stats.maximum = max(nums)
        stats.mean = sum(nums) / len(nums)
        srt = sorted(nums)
        mid = len(srt) // 2
        stats.median = srt[mid] if len(srt) % 2 else (srt[mid - 1] + srt[mid]) / 2
        if len(nums) > 1:
            var = sum((x - stats.mean) ** 2 for x in nums) / (len(nums) - 1)
            stats.std = math.sqrt(var)
    else:
        counts: dict[str, int] = {}
        for v in present:
            counts[str(v)] = counts.get(str(v), 0) + 1
        stats.top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
    return stats


def histogram(values: list[float], bins: int = 12) -> list[tuple[str, int]]:
    """Histogramme de valeurs numériques → [(libellé d'intervalle, effectif)]."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [(f"{lo:g}", len(values))]
    width = (hi - lo) / bins
    edges = [lo + i * width for i in range(bins + 1)]
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1

    def fmt(x: float) -> str:
        return f"{x:.2f}".rstrip("0").rstrip(".")

    return [(f"{fmt(edges[i])}–{fmt(edges[i+1])}", counts[i]) for i in range(bins)]


def duplicate_rows(ds: Dataset) -> int:
    """Nombre de lignes en double (occurrences au-delà de la première)."""
    seen: set[tuple] = set()
    dup = 0
    for r in ds.rows:
        key = tuple("" if _is_missing(c) else str(c) for c in r)
        if key in seen:
            dup += 1
        else:
            seen.add(key)
    return dup


def overview(ds: Dataset) -> dict:
    """Synthèse globale du jeu de données (valeurs réelles uniquement)."""
    total_cells = ds.n_rows * ds.n_cols
    missing = sum(column_stats(ds, c).missing for c in ds.columns) if ds.columns else 0
    return {
        "rows": ds.n_rows,
        "cols": ds.n_cols,
        "missing_cells": missing,
        "missing_ratio": (missing / total_cells) if total_cells else 0.0,
        "duplicates": duplicate_rows(ds),
    }
