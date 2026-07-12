"""Event-level corner metric for the JOINT DP path (Stage 2.3/2.6 round 2).

compare_corner_pipeline evaluates paper_corner_positions policies, but the
production fitter is now _fit_loop_joint, whose corner SET is decided inside
the shortest path.  This evaluator extracts those decisions directly: run the
joint fit per GT loop, read the welded C0 positions (seam + paid joins), and
match them against V4 perceptual events with the same greedy 1:1 tolerance
matching compare_corner_detectors uses.

Usage: python eval_joint_corners.py [--split val] [--limit 400] [--tolerance 3]
Also reports the spotify smooth-FP probe through the SAME joint machinery.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import numpy as np


def joint_corner_positions(loop: np.ndarray) -> np.ndarray | None:
    """The corner set the production joint fitter would weld C0 (or None when
    the joint path would defer to classic)."""
    import geometry_vectorizer as gv
    n = len(loop)
    if n < 24:
        return None
    spacing = float(np.median(np.linalg.norm(np.roll(loop, -1, axis=0) - loop, axis=1)))
    stride = max(1, int(round(1.0 / max(spacing, 1e-6)))) if spacing < 0.6 else 1
    coarse = loop[::stride]
    if len(coarse) < 10:
        return None
    probs = gv._corner_probabilities(coarse)
    if probs is None or len(probs) != len(coarse):
        return None
    above = probs >= gv._JOINT_SUPERSET_THRESHOLD
    if not bool(above.any()):
        return np.empty((0, 2))
    fl = gv._fit_loop_joint(loop, 32.0 / max(16.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2), 1.0)
    if fl is None:
        return None
    # C0 positions = joins whose tangents disagree beyond the G1 dead zone
    curves = fl.curves
    if len(curves) < 2:
        return np.empty((0, 2))
    corners = []
    for i in range(len(curves)):
        a, b = curves[i], curves[(i + 1) % len(curves)]
        ta = gv._tangent_out(a)
        tb = gv._tangent_in(b)
        ang = float(np.degrees(np.arccos(np.clip(float(ta @ tb), -1.0, 1.0))))
        if ang > 12.0:                     # a real kept corner, not a G1 join
            corners.append(0.5 * (a.control[-1] + b.control[0]))
    return np.asarray(corners, float) if corners else np.empty((0, 2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--tolerance", type=float, default=3.0)
    args = ap.parse_args()

    from svg_corner_gt import iter_shard_examples
    import geometry_vectorizer as gv

    dataset = ROOT / "datasets" / "corner_gt_v4_perceptual_events"
    tp = fp = fn = 0
    loops_seen = 0
    joint_used = 0
    for points, labels, meta in iter_shard_examples(dataset, {args.split}):
        if loops_seen >= args.limit:
            break
        loop = np.asarray(points, float)
        event_ids = np.asarray(meta["event_ids"])
        if len(loop) < 24:
            continue
        loops_seen += 1
        pred = joint_corner_positions(loop)
        if pred is None:                    # joint deferred -> classic handles it
            positions = gv.paper_corner_positions(loop)
            pred = np.asarray(positions, float) if len(positions) else np.empty((0, 2))
        else:
            joint_used += 1
        # events: one latent corner per event id (midpoint of its vertices)
        events = []
        for eid in np.unique(event_ids):
            if eid < 0:
                continue
            pts = loop[event_ids == eid]
            events.append(pts.mean(axis=0))
        events = np.asarray(events, float) if events else np.empty((0, 2))
        matched_e = set()
        matched_p = set()
        if len(pred) and len(events):
            d = np.linalg.norm(pred[:, None, :] - events[None, :, :], axis=2)
            order = np.dstack(np.unravel_index(np.argsort(d, axis=None), d.shape))[0]
            for pi, ei in order:
                if d[pi, ei] > args.tolerance:
                    break
                if pi in matched_p or ei in matched_e:
                    continue
                matched_p.add(int(pi))
                matched_e.add(int(ei))
        tp += len(matched_e)
        fp += len(pred) - len(matched_p)
        fn += len(events) - len(matched_e)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    print(f"loops {loops_seen} (joint path on {joint_used})  "
          f"P {precision:.4f}  R {recall:.4f}  F1 {f1:.4f}  (tp {tp} fp {fp} fn {fn})")

    # spotify smooth-FP probe through the SAME machinery
    spotify = ROOT / "web_preview" / "uploads"
    from svg_corners import svg_region_masks
    probe = None
    for cand in [Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset/icons/iconify/logos/spotify-icon.svg")]:
        if cand.is_file():
            probe = cand
            break
    if probe is not None:
        from vectorize_papers import mask_loops
        for mask, _ in svg_region_masks(probe, target=380):
            for lp in mask_loops(mask):
                if len(lp) < 200:
                    continue
                pred = joint_corner_positions(np.asarray(lp, float))
                count = -1 if pred is None else len(pred)
                print(f"spotify loop len {len(lp)}: joint corners = {count} (must be 0; -1 = deferred)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
