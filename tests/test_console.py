"""Tests de la console : analyse et dispatch des commandes synchrones."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from face_analyse.ui import theme

    app.setStyleSheet(theme.stylesheet())
    theme.apply_fonts(app)
    return app


@pytest.fixture
def console(qapp, tmp_path):
    from face_analyse.core.config import Settings
    from face_analyse.database.repository import Repository
    from face_analyse.ui.context import AppContext
    from face_analyse.ui.pages.console import ConsolePage

    repo = Repository(tmp_path / "c.db")
    page = ConsolePage(AppContext(Settings.load(), repo))
    yield page
    page.deleteLater()
    repo.close()


def _run(page, *cmds):
    for c in cmds:
        page._submit(c)
    return page.view.toPlainText()


def test_help_and_learn(console):
    out = _run(console, "help", "learn", "learn dos")
    assert "COMMANDES" in out and "recon" in out and "323-2" in out


def test_crypto_commands(console):
    out = _run(console, "hash sha256 bonjour", "b64 enc secret", "rot13 Aruka",
               "hashid 5d41402abc4b2a76b9719d911017c592", "pwgen 24")
    assert any(len(w) == 64 for w in out.split())  # sha256
    assert "c2VjcmV0" in out  # base64("secret")
    assert "MD5" in out and "bits" in out


def test_generators_and_discord(console):
    out = _run(console, "geniban FR 2", "uuid 1", "discord 175928847299117063")
    assert "FR" in out and "2016" in out


def test_unknown_and_usage_errors(console):
    out = _run(console, "nope", "hash")
    assert "inconnue" in out and "usage" in out
