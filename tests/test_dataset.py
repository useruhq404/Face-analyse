"""Tests du Data Lab : chargement (CSV/JSON/TXT) et analyse."""

from __future__ import annotations

import json

import pytest

from face_analyse.dataset import analysis as A
from face_analyse.dataset.loader import DatasetError, load


def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


CSV = "nom,age,ville,score\nAlice,30,Paris,8.5\nBob,25,Lyon,6.2\nChloé,42,Paris,9.1\nDavid,,Lyon,7.0\nAlice,30,Paris,8.5\n"


def test_load_csv_header_and_shape(tmp_path):
    ds = load(write(tmp_path, "d.csv", CSV))
    assert ds.source_format == "CSV"
    assert ds.columns == ["nom", "age", "ville", "score"]
    assert ds.n_rows == 5 and ds.n_cols == 4


def test_load_csv_semicolon_delimiter(tmp_path):
    ds = load(write(tmp_path, "d.csv", "a;b;c\n1;2;3\n4;5;6\n"))
    assert ds.columns == ["a", "b", "c"] and ds.rows[0] == ["1", "2", "3"]


def test_load_json_list_of_objects(tmp_path):
    data = json.dumps([{"id": 1, "type": "x"}, {"id": 2, "type": "y", "extra": True}])
    ds = load(write(tmp_path, "d.json", data))
    assert ds.columns == ["id", "type", "extra"] and ds.n_rows == 2
    assert ds.rows[0] == [1, "x", None]


def test_load_txt_lines(tmp_path):
    ds = load(write(tmp_path, "d.txt", "l1\nl2\nl3\n"))
    assert ds.columns == ["ligne"] and ds.n_rows == 3


def test_unsupported_and_missing(tmp_path):
    with pytest.raises(DatasetError):
        load(write(tmp_path, "d.xyz", "x"))
    with pytest.raises(DatasetError):
        load(tmp_path / "nope.csv")
    with pytest.raises(DatasetError):
        load(write(tmp_path, "bad.json", "{not json"))


def test_column_stats_numeric_and_text(tmp_path):
    ds = load(write(tmp_path, "d.csv", CSV))
    age = A.column_stats(ds, "age")
    assert age.kind == "numérique" and age.count == 4 and age.missing == 1
    assert age.minimum == 25.0 and age.maximum == 42.0
    assert age.mean == pytest.approx((30 + 25 + 42 + 30) / 4)
    ville = A.column_stats(ds, "ville")
    assert ville.kind == "texte" and dict(ville.top)["Paris"] == 3


def test_overview_and_duplicates(tmp_path):
    ds = load(write(tmp_path, "d.csv", CSV))
    ov = A.overview(ds)
    assert ov["rows"] == 5 and ov["cols"] == 4
    assert ov["duplicates"] == 1       # la ligne Alice est dupliquée
    assert ov["missing_cells"] == 1    # l'âge de David


def test_histogram_bins():
    hist = A.histogram([1, 1, 2, 2, 2, 3], bins=3)
    assert sum(c for _, c in hist) == 6
    assert len(hist) == 3
    assert A.histogram([], bins=5) == []
    assert A.histogram([4, 4, 4]) == [("4", 3)]


def test_small_sample_flagged(tmp_path):
    ds = load(write(tmp_path, "d.csv", "x\n1\n2\n"))
    assert A.column_stats(ds, "x").reliable is False
