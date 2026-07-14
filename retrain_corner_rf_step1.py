"""D2 step 1: does our-condition augmentation (native re-raster, JPEG q30,
deblur-4x) improve the corner RF on OUR domains without hurting the paper's?

Discovery that reshaped this step (2026-07-15): the paper's released
boundaries are themselves unit-step axis-aligned staircases (two origin
conventions, .0 and .5 - translation drops out of the relative stencils),
i.e. the SAME geometric class as our mask_loops output.  So "native" is a
near-duplicate sanity domain; the real gaps this step measures are q30
(JPEG wobble) and db4 (4x-magnified blocky corners, production deblur).

Protocol: same 10 folds as step 0, fold membership by BASE shape name so a
variant of a test shape can never leak into training.  Per fold two models:
  A = orig only            (step-0 replica, the baseline)
  B = orig + native + q30  (+ db4 in the 128 bucket)
Both evaluated per domain on the fold's test shapes.  Threshold panel per
(model, domain): best-th F1 and F1/R at the paper's 0.125 working point.

CRITERION: B must beat A on q30/db4 best-F1 and must not lose more than
0.01 on orig.  Output: benchmarks/retrain_rf_step1.json (partial write
after each resolution so background progress is visible).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from retrain_corner_rf import (CFG, FOLDS, load_pairs, orient_ccw,  # noqa: E402
                               stencil_features, d4_augment)

AUG = ROOT / "datasets" / "retrain_step1"
OUT_JSON = ROOT / "benchmarks" / "retrain_rf_step1.json"


def load_aug(res_bucket: int) -> list[tuple[str, str, np.ndarray, np.ndarray]]:
    man = json.loads((AUG / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for e in man["entries"]:
        if e["res"] != res_bucket:
            continue
        d = AUG / e["dir"]
        pts = np.loadtxt(d / f"{res_bucket}_boundary.txt", dtype=float)
        raw = (d / f"{res_bucket}_corners.1.txt").read_text().split()
        idx = np.asarray([int(v) for v in raw], dtype=int) if raw else np.empty(0, int)
        labels = np.full(len(pts), -1, dtype=int)
        labels[idx[(idx >= 0) & (idx < len(pts))]] = 1
        out.append((e["base"], e["domain"], pts, labels))
    return out


def prep(pairs):
    """[(base, domain, feats_oriented, labels_oriented)] with stencil built once."""
    out = []
    for base, domain, pts, labels, s in pairs:
        pts_o, flipped = orient_ccw(pts)
        labels_o = labels[::-1].copy() if flipped else labels
        out.append((base, domain, stencil_features(pts_o, s), labels_o))
    return out


def score(bucket: list[tuple[np.ndarray, np.ndarray]]) -> dict:
    def at(th: float):
        tp = fp = fn = 0
        for probs, actual in bucket:
            pred = probs > th
            tp += int(np.sum(pred & actual))
            fp += int(np.sum(pred & ~actual))
            fn += int(np.sum(~pred & actual))
        P = tp / max(1, tp + fp)
        R = tp / max(1, tp + fn)
        return P, R, 2 * P * R / max(1e-9, P + R)
    grid = {round(th, 3): at(th) for th in np.arange(0.05, 0.95, 0.05)}
    best_th, (bP, bR, bF) = max(grid.items(), key=lambda kv: kv[1][2])
    P125, R125, F125 = at(0.125)
    n_pos = int(sum(a.sum() for _, a in bucket))
    return {"n_items": len(bucket), "n_corners": n_pos,
            "best_th": best_th, "best_F1": round(bF, 4),
            "F1_at_0.125": round(F125, 4), "R_at_0.125": round(R125, 4)}


def run_res(res: int) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    cfg = CFG[res]
    s = cfg["s"]
    orig = [(shape, "orig", pts, labels, s)
            for name, shape, pts, labels in load_pairs(res)]
    aug = [(base, domain, pts, labels, s)
           for base, domain, pts, labels in load_aug(res)]
    orig_p, aug_p = prep(orig), prep(aug)
    domains = sorted({d for _, d, _, _ in orig_p + aug_p})
    buckets: dict[tuple[str, str], list] = {(m, d): [] for m in "AB" for d in domains}
    t0 = time.time()
    for fold in FOLDS:
        trainA = [p for p in orig_p if p[0] not in fold]
        trainB_extra = [p for p in aug_p if p[0] not in fold]
        tests = [p for p in orig_p + aug_p if p[0] in fold]
        if not tests or not trainA:
            continue

        def stack(items):
            X, y = [], []
            for _, _, feats, labels_o in items:
                for g in d4_augment(feats, s):
                    X.append(g)
                    y.append(labels_o)
            return X, y
        XA, yA = stack(trainA)
        XE, yE = stack(trainB_extra)
        sets = {"A": (np.vstack(XA), np.concatenate(yA)),
                "B": (np.vstack(XA + XE), np.concatenate(yA + yE))}
        for m, (X, y) in sets.items():
            clf = RandomForestClassifier(
                n_estimators=320, random_state=0, n_jobs=6,
                criterion=cfg["criterion"], bootstrap=cfg["bootstrap"],
                max_features=cfg["max_features"],
                min_samples_split=cfg["min_split"],
                min_samples_leaf=cfg["min_leaf"])
            clf.fit(X, y)
            pos = list(clf.classes_).index(1)
            for base, domain, feats, labels_o in tests:
                probs = np.zeros(len(feats))
                for g in d4_augment(feats, s):
                    probs = np.maximum(probs, clf.predict_proba(g)[:, pos])
                buckets[(m, domain)].append((probs, labels_o == 1))
        print(f"res {res} fold {fold}: done {time.time() - t0:.0f}s", flush=True)
    panel = {m: {d: score(buckets[(m, d)]) for d in domains if buckets[(m, d)]}
             for m in "AB"}
    crit = {d: round(panel["B"][d]["best_F1"] - panel["A"][d]["best_F1"], 4)
            for d in domains if d in panel["A"] and d in panel["B"]}
    return {"res": res, "n_orig": len(orig_p), "n_aug": len(aug_p),
            "panel": panel, "delta_bestF1_B_minus_A": crit,
            "secs": round(time.time() - t0, 1)}


def main() -> int:
    results = []
    for res in (32, 64, 128):
        r = run_res(res)
        results.append(r)
        OUT_JSON.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(json.dumps({k: r[k] for k in ("res", "delta_bestF1_B_minus_A", "secs")}),
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
