"""Test du lanceur local (création et stabilité de la configuration)."""

from __future__ import annotations

import importlib
import json


def test_local_config_created_and_stable(tmp_path, monkeypatch):
    monkeypatch.setenv("FA_DATA_DIR", str(tmp_path))
    import start_local

    importlib.reload(start_local)  # relit DATA_DIR avec le FA_DATA_DIR du test

    cfg = start_local.load_or_create_config()
    assert set(cfg) >= {"secret_key", "admin_email", "admin_password", "admin_pseudo"}
    assert len(cfg["secret_key"]) >= 32 and len(cfg["admin_password"]) >= 8
    assert start_local.CONFIG.exists()

    # Deuxième appel : mêmes identifiants (stables entre deux lancements).
    cfg2 = start_local.load_or_create_config()
    assert cfg2 == cfg
    on_disk = json.loads(start_local.CONFIG.read_text(encoding="utf-8"))
    assert on_disk["admin_email"] == cfg["admin_email"]
