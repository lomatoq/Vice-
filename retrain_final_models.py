"""D2 final models: train the PROMOTED configurations on the FULL data
(all 157 pairs + v2 augments, no folds) and save production candidates.

Promoted by step-2 + 320-tree confirmation (retrain_rf_step3_confirm.json):
  corner_rf_q30_64.joblib   = orig + q30, res 64 config   (native/q30 lanes)
  corner_rf_q30_128.joblib  = orig + q30, res 128 config  (native/q30 lanes)
  corner_rf_db4_128.joblib  = orig + db4, res 128 config  (deblur-4x lane)
Bucket 32 is NOT retrained (augments buy nothing there - step-2 verdict).

These are CANDIDATES: production integration happens only after the
CNN-vs-RF shadow comparison on our corpus protocol and full gates
(NEXT_STRIKES D2 items b-g).  Saved under models/retrain/ - the live
production checkpoints in models/ are never overwritten (iron rule).
Each bundle records its recipe for the audit trail.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from retrain_corner_rf import CFG, load_pairs, orient_ccw, stencil_features, d4_augment  # noqa: E402
from retrain_corner_rf_step1 import load_aug  # noqa: E402

OUT_DIR = ROOT / "models" / "retrain"
JOBS = [("corner_rf_q30_64", 64, ("orig", "q30")),
        ("corner_rf_q30_128", 128, ("orig", "q30")),
        ("corner_rf_db4_128", 128, ("orig", "db4"))]


def main() -> int:
    from sklearn.ensemble import RandomForestClassifier
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, res, doms in JOBS:
        cfg = CFG[res]
        s = cfg["s"]
        t0 = time.time()
        pool = [("orig", pts, labels) for _, _, pts, labels in load_pairs(res)]
        pool += [(dom, pts, labels) for _, dom, pts, labels in load_aug(res)]
        X, y = [], []
        for dom, pts, labels in pool:
            if dom not in doms:
                continue
            pts_o, flipped = orient_ccw(pts)
            labels_o = labels[::-1].copy() if flipped else labels
            feats = stencil_features(pts_o, s)
            for g in d4_augment(feats, s):
                X.append(g)
                y.append(labels_o)
        X = np.vstack(X)
        y = np.concatenate(y)
        clf = RandomForestClassifier(
            n_estimators=320, random_state=0, n_jobs=6,
            criterion=cfg["criterion"], bootstrap=cfg["bootstrap"],
            max_features=cfg["max_features"],
            min_samples_split=cfg["min_split"],
            min_samples_leaf=cfg["min_leaf"])
        clf.fit(X, y)
        bundle = {"model": clf, "s": s, "res": res, "domains": list(doms),
                  "recipe": "v2 data (faithful raster, apex transfer), D4x8, "
                            "max-over-transforms inference, 320 trees",
                  "confirmed_by": "benchmarks/retrain_rf_step3_confirm.json"}
        joblib.dump(bundle, OUT_DIR / f"{name}.joblib", compress=3)
        print(f"{name}: {X.shape[0]} samples, {time.time() - t0:.0f}s", flush=True)
    print(json.dumps({"saved": [j[0] for j in JOBS]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
