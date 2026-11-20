"""Lance le benchmark LFW et écrit docs/BENCHMARK.md + docs/benchmark.json.

Usage :
    python scripts/run_benchmark.py --lfw <dossier lfw_home>
        [--variants original sombre ...] [--no-tta]

Le dossier doit contenir ``pairs.txt`` et ``lfw_funneled/`` (ou ``lfw/``).
Avec scikit-learn : ``sklearn.datasets.fetch_lfw_pairs(data_home=...)``
télécharge exactement ces fichiers.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from face_analyse.core.config import EngineSettings  # noqa: E402
from face_analyse.engine import benchmark as bm  # noqa: E402
from face_analyse.engine.pipeline import FaceEngine  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lfw", required=True, type=Path)
    ap.add_argument("--variants", nargs="+", default=list(bm.DEGRADATIONS))
    ap.add_argument("--no-tta", action="store_true", help="désactive la moyenne image/miroir")
    ap.add_argument("--out", type=Path, default=ROOT / "docs")
    args = ap.parse_args()

    images = args.lfw / "lfw_funneled"
    if not images.is_dir():
        images = args.lfw / "lfw"
    pairs = bm.parse_lfw_pairs(args.lfw / "pairs.txt", images)

    engine = FaceEngine.from_settings(EngineSettings(detection_score=0.6, enhance_lighting=True))
    engine.flip_tta = not args.no_tta

    results = {"model": engine.embedder.model_id, "detector": engine.detector.name,
               "flip_tta": engine.flip_tta, "date": time.strftime("%Y-%m-%d %H:%M"), "verification": [], "open_set": []}
    for v in args.variants:
        t0 = time.time()
        rep, _, _ = bm.verification(pairs, engine, v)
        print(f"[{v}] acc={rep.accuracy_10fold_mean:.4f}±{rep.accuracy_10fold_std:.4f} auc={rep.auc:.4f} "
              f"eer={rep.eer:.4f} t*={rep.best_threshold:.3f} fail={rep.detection_failures} "
              f"{rep.ms_per_image:.1f}ms/img ({time.time() - t0:.0f}s)", flush=True)
        results["verification"].append(asdict(rep))

    thresholds = (0.363, 0.40, 0.45, 0.50, 0.55, 0.60)
    for r in bm.open_set(images, engine, thresholds):
        print(f"[open-set t={r.threshold:.3f}] correct={r.correct_identification_rate:.3f} "
              f"wrong={r.wrong_identity_rate:.4f} rejected={r.known_rejected_rate:.3f} "
              f"unknown->named={r.unknown_false_identification_rate:.4f}", flush=True)
        results["open_set"].append(asdict(r))

    args.out.mkdir(exist_ok=True)
    (args.out / "benchmark.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("écrit :", args.out / "benchmark.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
