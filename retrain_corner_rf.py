"""D2 step 0: reproduce the paper's RF corner classifiers on the released
training data (157 boundary/corners.1 pairs) with modern sklearn.

Recipe: PAPER_TRAINING_RECONSTRUCTION_20260714.md §16 — relative (x,y)
stencils of s neighbours each side (4s features), D4x8 augmentation with
order-parity fix, labels {-1,+1}, per-resolution RF configs from the
reconstruction table, inference = max over the 8 transforms.

This run establishes the BASELINE (their data, their configs, our sklearn)
with the released fold table for >=32.  Our-condition augmentations
(native marching-squares staircase, q30 renders, deblur-4x) come next and
must beat this baseline on the same protocol before touching production.

Output: benchmarks/retrain_rf_step0.json + models under models/retrain/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
DATA = Path(r"C:/Users/nirrt/Downloads/training-data (1)/training-data/training")
OUT_JSON = ROOT / "benchmarks" / "retrain_rf_step0.json"
OUT_DIR = ROOT / "models" / "retrain"

# reconstruction table (per resolution): s, criterion, bootstrap,
# max_features (fraction), min_samples_split, min_samples_leaf
CFG = {
    32:  dict(s=15, criterion="gini",    bootstrap=True,  max_features=0.8811676, min_split=2, min_leaf=3),
    64:  dict(s=16, criterion="entropy", bootstrap=False, max_features=0.3480541, min_split=9, min_leaf=10),
    128: dict(s=20, criterion="entropy", bootstrap=False, max_features=0.3777868, min_split=9, min_leaf=6),
}
FOLDS = [  # released fold table (test artist shapes per fold), >=32 only
    ["axe", "fighter"], ["mailbox", "headphone2"], ["ringbell", "lamp"],
    ["castle", "bow"], ["plane", "key"], ["pin", "lamp"],
    ["dress2", "lipstick"], ["dumbbell", "enterprise"], ["fragile", "whale"],
    ["guitar2", "zeppelin"],
]


def load_pairs(res: int):
    """[(name, boundary Nx2, labels {-1,+1} N)] for one resolution."""
    pairs = []
    for bfile in sorted(DATA.rglob(f"*{res}*_boundary.txt")):
        # names look like <shape>/<res>_boundary.txt or <shape>_<res>_boundary.txt
        cfile = Path(str(bfile).replace("_boundary.txt", "_corners.1.txt"))
        if not cfile.exists():
            continue
        try:
            pts = np.loadtxt(bfile, dtype=float)
        except Exception:
            continue
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 8:
            continue
        # resolution bucket check: the max bbox side must match res closely
        span = max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1]))
        if not (res * 0.4 <= span <= res * 1.6):
            continue
        raw = cfile.read_text().split()
        idx = np.array([int(float(v)) for v in raw], dtype=int) if raw else np.empty(0, int)
        labels = np.full(len(pts), -1, dtype=int)
        idx = idx[(idx >= 0) & (idx < len(pts))]
        labels[idx] = 1
        shape = bfile.parent.name if bfile.parent != DATA else bfile.stem.split("_")[0]
        pairs.append((str(bfile.parent.name) + "/" + bfile.name, shape, pts, labels))
    return pairs


def orient_ccw(pts: np.ndarray) -> tuple[np.ndarray, bool]:
    x, y = pts[:, 0], pts[:, 1]
    area = float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    if area < 0:
        return pts[::-1].copy(), True
    return pts, False


def stencil_features(pts: np.ndarray, s: int) -> np.ndarray:
    n = len(pts)
    feats = np.empty((n, 4 * s), dtype=np.float32)
    for k in range(1, s + 1):
        prev = np.roll(pts, k, axis=0) - pts       # p_(i-k) - p_i
        nxt = np.roll(pts, -k, axis=0) - pts       # p_(i+k) - p_i
        feats[:, (k - 1) * 2:(k - 1) * 2 + 2] = prev
        feats[:, 2 * s + (k - 1) * 2:2 * s + (k - 1) * 2 + 2] = nxt
    return feats


def d4_augment(feats: np.ndarray, s: int) -> list[np.ndarray]:
    """8 dihedral transforms of the relative-coordinate stencil.
    Odd-parity transforms swap the prev/next halves (boundary order flips)."""
    out = []
    f = feats.reshape(len(feats), 2 * s, 2)        # [prev_1..prev_s, next_1..next_s]
    for mx in (1, -1):
        for my in (1, -1):
            for swap in (False, True):
                g = f.copy()
                g[:, :, 0] *= mx
                g[:, :, 1] *= my
                if swap:
                    g = g[:, :, ::-1]
                # parity: mirror count odd -> boundary direction flips ->
                # exchange prev/next blocks and reverse within each block
                parity = (mx < 0) ^ (my < 0) ^ swap
                if parity:
                    prev, nxt = g[:, :s][:, ::-1], g[:, s:][:, ::-1]
                    g = np.concatenate([nxt, prev], axis=1)
                out.append(g.reshape(len(feats), 4 * s).astype(np.float32))
    return out


def run_res(res: int) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    cfg = CFG[res]
    s = cfg["s"]
    pairs = load_pairs(res)
    if not pairs:
        return {"res": res, "error": "no pairs"}
    per_fold = []
    t0 = time.time()
    for fold in FOLDS:
        train_X, train_y, test = [], [], []
        for name, shape, pts, labels in pairs:
            pts_o, _ = orient_ccw(pts)
            labels_o = labels if pts_o is pts else labels[::-1].copy()
            feats = stencil_features(pts_o, s)
            if shape in fold:
                test.append((feats, labels_o))
            else:
                for g in d4_augment(feats, s):
                    train_X.append(g)
                    train_y.append(labels_o)
        if not test or not train_X:
            continue
        X = np.vstack(train_X)
        y = np.concatenate(train_y)
        clf = RandomForestClassifier(
            n_estimators=320, random_state=0, n_jobs=6,
            criterion=cfg["criterion"], bootstrap=cfg["bootstrap"],
            max_features=cfg["max_features"], min_samples_split=cfg["min_split"],
            min_samples_leaf=cfg["min_leaf"])
        clf.fit(X, y)
        fold_probs, fold_actual = [], []
        for feats, labels_o in test:
            probs = np.zeros(len(feats))
            for g in d4_augment(feats, s):
                p = clf.predict_proba(g)[:, list(clf.classes_).index(1)]
                probs = np.maximum(probs, p)
            fold_probs.append(probs)
            fold_actual.append(labels_o == 1)
        per_fold.append({"fold": fold,
                         "probs": [p.round(4).tolist() for p in fold_probs],
                         "actual": [a.tolist() for a in fold_actual]})
        print(f"res {res} fold {fold}: done", flush=True)
    # score over a threshold grid: the paper reports the classifier's F1 at
    # its best threshold; the 0.125 working point is the 95%-recall RELAX set
    def score(th: float) -> tuple[float, float, float]:
        tp = fp = fn = 0
        for f in per_fold:
            for probs, actual in zip(f["probs"], f["actual"]):
                pred = np.asarray(probs) > th
                act = np.asarray(actual)
                tp += int(np.sum(pred & act))
                fp += int(np.sum(pred & ~act))
                fn += int(np.sum(~pred & act))
        P = tp / max(1, tp + fp)
        R = tp / max(1, tp + fn)
        return P, R, 2 * P * R / max(1e-9, P + R)
    grid = {round(th, 3): score(th) for th in np.arange(0.05, 0.95, 0.05)}
    best_th, (bP, bR, bF) = max(grid.items(), key=lambda kv: kv[1][2])
    P125, R125, F125 = score(0.125)
    return {"res": res, "pairs": len(pairs),
            "F1_at_0.125": round(F125, 4), "R_at_0.125": round(R125, 4),
            "best_th": best_th, "best_F1": round(bF, 4),
            "best_P": round(bP, 4), "best_R": round(bR, 4),
            "paper_F1": {32: 0.871, 64: 0.877, 128: 0.901}.get(res),
            "secs": round(time.time() - t0, 1)}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_res(r) for r in (32, 64, 128)]
    OUT_JSON.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps([{k: v for k, v in r.items() if k != "folds"} for r in results], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
