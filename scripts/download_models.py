"""Télécharge (ou vérifie) les modèles officiels OpenCV Zoo avec contrôle SHA-256.

Usage : python scripts/download_models.py [--verify-only]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from face_analyse.core.paths import models_dir  # noqa: E402
from face_analyse.engine.registry import DETECTORS, EMBEDDERS, sha256_file  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()
    dest = models_dir()
    dest.mkdir(parents=True, exist_ok=True)
    status = 0
    for spec in [*DETECTORS.values(), *EMBEDDERS.values()]:
        target = dest / spec.filename
        if target.exists() and sha256_file(target) == spec.sha256:
            print(f"[OK]       {spec.filename}")
            continue
        if args.verify_only:
            print(f"[MANQUANT] {spec.filename}")
            status = 1
            continue
        print(f"[TÉLÉCH.]  {spec.filename} ← {spec.url}")
        with requests.get(spec.url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(dir=dest, delete=False) as tmp:
                for chunk in r.iter_content(1 << 20):
                    tmp.write(chunk)
        tmp_path = Path(tmp.name)
        if sha256_file(tmp_path) != spec.sha256:
            tmp_path.unlink()
            print(f"[ERREUR]   empreinte SHA-256 invalide pour {spec.filename}")
            status = 1
            continue
        tmp_path.replace(target)
        print(f"[OK]       {spec.filename} ({spec.license})")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
