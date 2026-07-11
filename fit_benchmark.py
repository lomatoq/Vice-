"""Quantitative fit benchmark: rasterize ground-truth SVGs, run the paper fitter on
each region boundary, and MEASURE how far the fit strays from the true raster boundary
(overshoot/crookedness) plus corner precision/recall vs the SVG's true corners.

Turns "looks crooked" into numbers so fitter changes are regression-tested, not eyeballed.

    C:/Python312/python.exe fit_benchmark.py --n 60
"""
from __future__ import annotations

import argparse
import glob
import random
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np

from corner_classifier import predict_corners, load, _to_ccw
from geometry_vectorizer import (paper_corner_positions, fit_loop_paper,
                                 _PAPER_FIT_ALPHA_K)
from svg_corners import svg_region_masks
from vectorize_papers import mask_loops, eval_curve

CORPUS = Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset")
GT = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/ground truth/Default")


def _boundary_points(loop_curves, samples: int = 24) -> np.ndarray:
    if not loop_curves:
        return np.zeros((0, 2))
    return np.vstack([eval_curve(c, samples) for c in loop_curves])


def _dist_to(points: np.ndarray, ref: np.ndarray) -> np.ndarray:
    # min distance from each point to the ref polyline vertices (dense enough here)
    if len(ref) == 0 or len(points) == 0:
        return np.zeros(len(points))
    return np.min(np.linalg.norm(points[:, None, :] - ref[None, :, :], axis=2), axis=1)


def bench_file(svg: str, res: int) -> dict | None:
    try:
        regions = svg_region_masks(svg, target=res)
    except Exception:
        return None
    W = max(res, 1)
    alpha = _PAPER_FIT_ALPHA_K / W
    fit_max, fit_rms, tp, fp, fn, n_prim, n_loops = [], [], 0, 0, 0, 0, 0
    for mask, gt in regions:
        for raw in mask_loops(mask):
            if len(raw) > 1 and np.allclose(raw[0], raw[-1]):
                raw = raw[:-1]
            loop = _to_ccw(raw.astype(float))
            if len(loop) < 64:
                continue
            n_loops += 1
            corners = paper_corner_positions(loop)
            fitted = fit_loop_paper(loop, alpha, corner_positions=corners, px=1.0)
            pts = _boundary_points(fitted.curves)
            d = _dist_to(pts, loop)                        # fit vs true boundary
            if len(d):
                fit_max.append(float(d.max())); fit_rms.append(float(np.sqrt((d ** 2).mean())))
            n_prim += len(fitted.curves)
            # corner match (pred vs GT within 3px), only GT that lie on THIS loop
            pred = np.asarray(corners, float).reshape(-1, 2)
            if len(gt):
                on = np.min(np.linalg.norm(loop[:, None, :] - gt[None, :, :], axis=2), axis=0) <= 3.0
                gtl = gt[on]
            else:
                gtl = np.zeros((0, 2))
            used = np.zeros(len(gtl), bool)
            for p in pred:
                if len(gtl) and np.linalg.norm(gtl - p, axis=1).min() <= 4.0:
                    j = int(np.linalg.norm(gtl - p, axis=1).argmin())
                    if not used[j]:
                        used[j] = True; tp += 1
                    else:
                        fp += 1
                else:
                    fp += 1
            fn += int((~used).sum())
    if not fit_max:
        return None
    return {"fit_max": float(np.mean(fit_max)), "fit_max_p95": float(np.percentile(fit_max, 95)),
            "fit_rms": float(np.mean(fit_rms)), "tp": tp, "fp": fp, "fn": fn,
            "prim": n_prim, "loops": n_loops}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--corpus", action="store_true", help="sample from the big corpus instead of GT logos")
    args = ap.parse_args()
    if args.corpus:
        files = glob.glob(str(CORPUS / "icons/local/**/*.svg"), recursive=True)
    else:
        files = glob.glob(str(GT / "*.svg"))
    rng = random.Random(args.seed)
    rng.shuffle(files)
    files = files[: args.n]
    rows = []
    for i, f in enumerate(files):
        res = rng.choice([48, 96, 160, 240])
        r = bench_file(f, res)
        if r:
            rows.append(r)
    if not rows:
        print("no results"); return
    agg = lambda k: float(np.mean([r[k] for r in rows]))
    TP = sum(r["tp"] for r in rows); FP = sum(r["fp"] for r in rows); FN = sum(r["fn"] for r in rows)
    prec = TP / max(1, TP + FP); rec = TP / max(1, TP + FN)
    print(f"files={len(rows)}  loops={sum(r['loops'] for r in rows)}")
    print(f"FIT vs boundary (px):  mean_max={agg('fit_max'):.2f}  p95_max={agg('fit_max_p95'):.2f}  rms={agg('fit_rms'):.2f}")
    print(f"CORNERS (pred vs GT):  precision={prec:.2f}  recall={rec:.2f}  F1={2*prec*rec/max(1e-9,prec+rec):.2f}")
    print(f"primitives total={sum(r['prim'] for r in rows)}")


if __name__ == "__main__":
    main()
