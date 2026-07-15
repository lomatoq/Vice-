"""D2 step 2: v2 protocol after the two v1 poisons were found and fixed.

v1 verdict (benchmarks/retrain_rf_step1.json): A collapses on our domains
(db4 0.135 vs orig 0.859 at 128) and B gains db4 +0.43 - but BOTH numbers
were confounded: (1) the v1 raster was half a pixel thinner than the corpus
convention (supersampled centre-in-polygon vs the true centre-chain-
inclusive fillPoly), (2) labels transferred to the euclidean-nearest vertex
(often the step neighbour of the apex), and (3) scoring demanded EXACT
vertex equality while the paper matches corner POSITIONS within 2 percent
of the image diagonal.  v2 fixes all three (generator regenerated with
faithful raster + injective apex transfer; this trainer scores positions).

Scoring: above-threshold vertices consolidate per cyclic RUN to the max-
prob vertex (one predicted corner per run), then greedy nearest matching
within tol = res * sqrt(2) * 0.02 (paper Sec 4 accuracy criterion).

Models per fold (n_estimators=160 for ALL - paired exploration; the chosen
candidate gets a 320-tree confirmation before any production step):
  A      = orig                      (baseline)
  B2     = orig + q30 + db4         (no native near-duplicates)
  C_q30  = orig + q30               (single-domain value, no cross-dilution)
  C_db4  = orig + db4               (128 bucket only - db4 lives there)
Panel: every model on every domain.  CRITERION: a candidate must beat A
on its target domain by >= 0.03 best-F1 and lose <= 0.01 on orig.

Output: benchmarks/retrain_rf_step2.json (partial write per resolution).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from retrain_corner_rf import (CFG, FOLDS, load_pairs, orient_ccw,  # noqa: E402
                               stencil_features, d4_augment)
from retrain_corner_rf_step1 import load_aug  # noqa: E402

OUT_JSON = ROOT / "benchmarks" / "retrain_rf_step2.json"
TREES = 160


def prep(pairs):
    out = []
    for base, domain, pts, labels, s in pairs:
        pts_o, flipped = orient_ccw(pts)
        labels_o = labels[::-1].copy() if flipped else labels
        out.append((base, domain, pts_o, stencil_features(pts_o, s), labels_o))
    return out


def predicted_positions(probs: np.ndarray, pts: np.ndarray, th: float) -> np.ndarray:
    """One corner per cyclic run of above-threshold vertices (max-prob wins)."""
    above = probs > th
    if not bool(above.any()):
        return np.empty((0, 2))
    if bool(above.all()):
        return pts[[int(np.argmax(probs))]]
    n = len(probs)
    # rotate so index 0 is below threshold -> runs never wrap
    start = int(np.flatnonzero(~above)[0])
    order = (np.arange(n) + start) % n
    picks = []
    run: list[int] = []
    for i in order:
        if above[i]:
            run.append(i)
        elif run:
            picks.append(run[int(np.argmax(probs[run]))])
            run = []
    if run:
        picks.append(run[int(np.argmax(probs[run]))])
    return pts[np.asarray(picks, dtype=int)]


def match_prf(pred: np.ndarray, gt: np.ndarray, tol: float) -> tuple[int, int, int]:
    if len(pred) == 0:
        return 0, 0, len(gt)
    if len(gt) == 0:
        return 0, len(pred), 0
    d = np.linalg.norm(pred[:, None, :] - gt[None, :, :], axis=2)
    tp = 0
    used_p: set[int] = set()
    used_g: set[int] = set()
    for k in np.argsort(d, axis=None):
        i, j = int(k // d.shape[1]), int(k % d.shape[1])
        if d[i, j] > tol:
            break
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        tp += 1
    return tp, len(pred) - tp, len(gt) - tp


def score(bucket, tol: float) -> dict:
    def at(th: float):
        tp = fp = fn = 0
        for probs, labels_o, pts in bucket:
            gt = pts[labels_o == 1]
            pred = predicted_positions(probs, pts, th)
            a, b, c = match_prf(pred, gt, tol)
            tp += a; fp += b; fn += c
        P = tp / max(1, tp + fp)
        R = tp / max(1, tp + fn)
        return P, R, 2 * P * R / max(1e-9, P + R)
    grid = {round(th, 3): at(th) for th in np.arange(0.05, 0.95, 0.05)}
    best_th, (bP, bR, bF) = max(grid.items(), key=lambda kv: kv[1][2])
    P125, R125, F125 = at(0.125)
    return {"n_items": len(bucket),
            "best_th": best_th, "best_F1": round(bF, 4),
            "best_P": round(bP, 4), "best_R": round(bR, 4),
            "F1_at_0.125": round(F125, 4), "R_at_0.125": round(R125, 4)}


def run_res(res: int) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    cfg = CFG[res]
    s = cfg["s"]
    tol = res * math.sqrt(2.0) * 0.02
    orig = [(shape, "orig", pts, labels, s)
            for name, shape, pts, labels in load_pairs(res)]
    aug = [(base, domain, pts, labels, s)
           for base, domain, pts, labels in load_aug(res)]
    orig_p, aug_p = prep(orig), prep(aug)
    domains = sorted({d for _, d, _, _, _ in orig_p + aug_p})
    have_db4 = any(d == "db4" for _, d, _, _, _ in aug_p)
    model_defs = {"A": ("orig",), "B2": ("orig", "q30", "db4"),
                  "C_q30": ("orig", "q30")}
    if have_db4:
        model_defs["C_db4"] = ("orig", "db4")
    buckets: dict[tuple[str, str], list] = {(m, d): [] for m in model_defs for d in domains}
    t0 = time.time()
    for fold in FOLDS:
        pool = [p for p in orig_p + aug_p if p[0] not in fold]
        tests = [p for p in orig_p + aug_p if p[0] in fold]
        if not tests:
            continue

        def stack(doms):
            X, y = [], []
            for _, dom, _, feats, labels_o in pool:
                if dom not in doms:
                    continue
                for g in d4_augment(feats, s):
                    X.append(g)
                    y.append(labels_o)
            return np.vstack(X), np.concatenate(y)
        for m, doms in model_defs.items():
            X, y = stack(doms)
            clf = RandomForestClassifier(
                n_estimators=TREES, random_state=0, n_jobs=6,
                criterion=cfg["criterion"], bootstrap=cfg["bootstrap"],
                max_features=cfg["max_features"],
                min_samples_split=cfg["min_split"],
                min_samples_leaf=cfg["min_leaf"])
            clf.fit(X, y)
            pos = list(clf.classes_).index(1)
            for base, domain, pts_o, feats, labels_o in tests:
                probs = np.zeros(len(feats))
                for g in d4_augment(feats, s):
                    probs = np.maximum(probs, clf.predict_proba(g)[:, pos])
                buckets[(m, domain)].append((probs, labels_o, pts_o))
        print(f"res {res} fold {fold}: done {time.time() - t0:.0f}s", flush=True)
    panel = {m: {d: score(buckets[(m, d)], tol) for d in domains if buckets[(m, d)]}
             for m in model_defs}
    deltas = {m: {d: round(panel[m][d]["best_F1"] - panel["A"][d]["best_F1"], 4)
                  for d in panel[m]} for m in model_defs if m != "A"}
    return {"res": res, "tol_px": round(tol, 2), "trees": TREES,
            "n_orig": len(orig_p), "n_aug": len(aug_p),
            "panel": panel, "delta_vs_A": deltas,
            "secs": round(time.time() - t0, 1)}


def main() -> int:
    results = []
    for res in (32, 64, 128):
        r = run_res(res)
        results.append(r)
        OUT_JSON.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(json.dumps({k: r[k] for k in ("res", "delta_vs_A", "secs")}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
