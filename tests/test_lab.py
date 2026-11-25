"""Tests du module CYBER LAB : contenu, persistance, construction de la page."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from face_analyse.lab import content, progress


def test_content_integrity():
    assert content.total_items() == sum(len(p.items) for p in content.CHECKLIST)
    ids = [i for p in content.CHECKLIST for i, _ in p.items]
    assert len(ids) == len(set(ids))  # identifiants uniques
    for pf in content.PLATFORMS:
        assert pf.url.startswith("https://")


def test_progress_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("FACE_ANALYSE_HOME", str(tmp_path))
    assert progress.load_done() == set()
    progress.save_done({"prep_lab", "scan_ports"})
    assert progress.load_done() == {"prep_lab", "scan_ports"}


def test_progress_handles_garbage(tmp_path, monkeypatch):
    monkeypatch.setenv("FACE_ANALYSE_HOME", str(tmp_path))
    (tmp_path / "lab_progress.json").write_text("not json", "utf-8")
    assert progress.load_done() == set()


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from face_analyse.ui import theme

    app.setStyleSheet(theme.stylesheet())
    theme.apply_fonts(app)
    return app


def test_lab_page_builds_and_persists(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("FACE_ANALYSE_HOME", str(tmp_path))
    from face_analyse.core.config import Settings
    from face_analyse.database.repository import Repository
    from face_analyse.lab.content import CHECKLIST
    from face_analyse.ui.context import AppContext
    from face_analyse.ui.pages.lab import LabPage

    repo = Repository(tmp_path / "lab.db")
    page = LabPage(AppContext(Settings.load(), repo))
    # cocher la première étape → sauvegardée
    first_id = CHECKLIST[0].items[0][0]
    page._boxes[0].setChecked(True)
    assert first_id in progress.load_done()
    page._boxes[0].setChecked(False)
    assert first_id not in progress.load_done()
    page.deleteLater()
    repo.close()
