"""The paper's ORIGINAL detector setup, reproduced exactly: one Random Forest PER RESOLUTION
(8/16/32/64/128/256), trained ONLY on the released Hoshyari training set (paper_data), with the
model auto-selected at inference by the loop's resolution (nearest power of two, paper Sec 7).

Per-resolution feature window s follows the loop sizes at each resolution (a 4s+4-vertex window
must fit the loop; the paper tuned s per resolution in its supplementary, values unpublished).
The per-res lax threshold is calibrated to ~95% recall on the training rows (paper Sec 4.1).

Train:    C:/Python312/python.exe corner_perres.py --train
Bundle:   models/corner_perres_paper.joblib   {res: {model, s, thr}}
Predict:  predict_corners_perres(loop, threshold=None, nms_px=2.0) -> bool mask (auto-selects res)
"""
from __future__ import annotations
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
BUNDLE_PATH = ROOT / "models" / "corner_perres_paper.joblib"

# feature half-window per resolution: must satisfy 4s+4 <= typical loop length at that res
S_MAP = {8: 5, 16: 8, 32: 12, 64: 14, 128: 14, 256: 14}
RES_KEYS = sorted(S_MAP)


def train(out_path: Path = BUNDLE_PATH, target_recall: float = 0.95) -> dict:
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    import corner_classifier as CC
    import paper_data

    by_res: dict[int, list] = {r: [] for r in RES_KEYS}
    for loop, cxy, res, name in paper_data.paper_examples():
        if res in by_res:
            by_res[res].append((loop, cxy))

    bundle, report = {}, {}
    for res in RES_KEYS:
        s = S_MAP[res]
        fx, fy = [], []
        used = 0
        for loop, cxy in by_res[res]:
            lp = CC._to_ccw(loop.astype(np.float64))
            if len(lp) < 4 * s + 4:
                continue
            used += 1
            base = CC.featurize(lp, s)
            tgt = CC._labels(lp, cxy)
            for v in CC._augment(base, s):
                fx.append(v)
                fy.append(tgt)
        if not fx:
            continue
        X = np.vstack(fx); Y = np.concatenate(fy)
        model = RandomForestClassifier(n_estimators=100, max_depth=22, min_samples_leaf=10,
                                       max_features="sqrt", class_weight="balanced",
                                       n_jobs=-1, random_state=0)
        model.fit(X, Y)
        prob = model.predict_proba(X)[:, 1]
        pos = prob[Y == 1]
        thr = float(np.quantile(pos, 1.0 - target_recall)) if len(pos) else 0.125
        thr = max(0.05, min(0.5, thr))
        bundle[res] = {"model": model, "s": s, "thr": thr}
        report[res] = {"examples": used, "rows": int(len(Y)), "pos_rate": round(float(Y.mean()), 4),
                       "thr95": round(thr, 3)}
        print(f"res {res:3d}: examples={used:3d} rows={len(Y):7d} pos={Y.mean():.4f} thr95={thr:.3f}",
              flush=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)
    print(f"saved {out_path}")
    return report


_BUNDLE = None


def _load():
    global _BUNDLE
    if _BUNDLE is None:
        import joblib
        _BUNDLE = joblib.load(BUNDLE_PATH)
    return _BUNDLE


def pick_res(work_res: float) -> int:
    return min(RES_KEYS, key=lambda r: abs(math.log2(max(2.0, work_res)) - math.log2(r)))


def predict_corners_perres(loop: np.ndarray, threshold: float | None = None,
                           nms_px: float = 2.0) -> np.ndarray:
    """Boolean corner mask; the per-resolution model is AUTO-selected by the loop's extent.
    threshold=None uses the bundle's calibrated per-res ~95%-recall lax point."""
    from corner_classifier import predict_corners, _to_ccw
    bundle = _load()
    n = len(loop)
    work_res = max(1.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2)
    entry = bundle.get(pick_res(work_res))
    if entry is None:
        return np.zeros(n, bool)
    s = entry["s"]
    if n < 4 * s + 4:
        # fall back to the smallest model that fits this loop
        for r in RES_KEYS:
            e = bundle.get(r)
            if e and n >= 4 * e["s"] + 4:
                entry, s = e, e["s"]
                break
        else:
            return np.zeros(n, bool)
    thr = entry["thr"] if threshold is None else threshold
    # normalize winding like training; remember whether we reversed to map the mask back
    x, y = loop[:, 0], loop[:, 1]
    area = float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    rev = area < 0
    lp = (loop[::-1] if rev else loop).astype(np.float64)
    mask = predict_corners(lp, entry["model"], s=s, threshold=thr, nms_radius=nms_px)
    return mask[::-1].copy() if rev else mask


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    a = ap.parse_args()
    if a.train:
        print(json.dumps(train(), indent=1))
