"""Chargement de jeux de données locaux : CSV, TSV, JSON, TXT.

Lecture robuste (détection de séparateur, chemins Unicode Windows), bornée en
mémoire. Aucune interprétation : les valeurs sont conservées telles quelles ;
c'est l'étage d'analyse qui tente les conversions numériques.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from face_analyse.core.errors import FaceAnalyseError

SUPPORTED = {".csv", ".tsv", ".json", ".txt"}
MAX_ROWS = 100_000
MAX_BYTES = 80_000_000


class DatasetError(FaceAnalyseError):
    user_message = "Jeu de données illisible."


@dataclass
class Dataset:
    name: str
    columns: list[str]
    rows: list[list]  # chaque ligne alignée sur ``columns``
    source_format: str
    truncated: bool = False
    meta: dict = field(default_factory=dict)

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        return len(self.columns)

    def column(self, name: str) -> list:
        i = self.columns.index(name)
        return [r[i] if i < len(r) else None for r in self.rows]


def load(path: str | Path) -> Dataset:
    p = Path(path)
    if p.suffix.lower() not in SUPPORTED:
        raise DatasetError(f"Format non pris en charge : {p.suffix or 'sans extension'}")
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise DatasetError(f"Fichier introuvable : {p.name}") from exc
    if size > MAX_BYTES:
        raise DatasetError("Fichier trop volumineux (> 80 Mo).")
    try:
        data = p.read_bytes()
    except OSError as exc:
        raise DatasetError(f"Lecture impossible : {p.name}") from exc
    text = data.decode("utf-8", errors="replace")
    suffix = p.suffix.lower()
    if suffix == ".json":
        return _load_json(p.name, text)
    if suffix == ".txt":
        return _load_txt(p.name, text)
    return _load_csv(p.name, text, delimiter="\t" if suffix == ".tsv" else None)


def _truncate(rows: list[list]) -> tuple[list[list], bool]:
    if len(rows) > MAX_ROWS:
        return rows[:MAX_ROWS], True
    return rows, False


def _load_csv(name: str, text: str, delimiter: str | None) -> Dataset:
    if delimiter is None:
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        all_rows = [row for row in reader]
    except csv.Error as exc:
        raise DatasetError(f"CSV invalide : {exc}") from exc
    if not all_rows:
        raise DatasetError("Fichier vide.")
    header = all_rows[0]
    # En-tête présent si aucune cellule n'est purement numérique.
    has_header = not all(_looks_numeric(c) for c in header if c.strip())
    if has_header and len(set(header)) == len(header):
        columns = [c.strip() or f"col{i+1}" for i, c in enumerate(header)]
        body = all_rows[1:]
    else:
        columns = [f"col{i+1}" for i in range(len(header))]
        body = all_rows
    width = len(columns)
    norm = [(r + [None] * width)[:width] for r in body]
    norm, truncated = _truncate(norm)
    return Dataset(name, columns, norm, "CSV", truncated, {"séparateur": repr(delimiter)})


def _looks_numeric(s: str) -> bool:
    try:
        float(str(s).replace(",", ".").strip())
        return True
    except (ValueError, AttributeError):
        return False


def _load_json(name: str, text: str) -> Dataset:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DatasetError(f"JSON invalide : {exc.msg} (ligne {exc.lineno})") from exc
    # liste d'objets -> tableau
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        columns: list[str] = []
        for item in obj[:1000]:
            for k in item:
                if k not in columns:
                    columns.append(str(k))
        rows = [[_jsonval(item.get(c)) for c in columns] for item in obj if isinstance(item, dict)]
    elif isinstance(obj, dict) and obj and all(isinstance(v, list) for v in obj.values()):
        columns = [str(k) for k in obj]
        length = max(len(v) for v in obj.values())
        rows = [[_jsonval(obj[c][i]) if i < len(obj[c]) else None for c in columns] for i in range(length)]
    elif isinstance(obj, list):
        columns = ["valeur"]
        rows = [[_jsonval(v)] for v in obj]
    else:
        raise DatasetError("Structure JSON non tabulaire (attendu : liste d'objets ou objet de listes).")
    rows, truncated = _truncate(rows)
    return Dataset(name, columns, rows, "JSON", truncated)


def _jsonval(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def _load_txt(name: str, text: str) -> Dataset:
    lines = text.splitlines()
    rows = [[ln] for ln in lines]
    rows, truncated = _truncate(rows)
    return Dataset(name, ["ligne"], rows, "TXT", truncated)
