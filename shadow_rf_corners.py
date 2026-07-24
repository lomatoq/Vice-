"""D2 step (b): SHADOW comparison of the promoted corner RFs vs the
production CNN on OUR corpus protocol - measurement only, no production
change.

The RF drop-in mirrors production semantics: per-vertex probabilities on
the native-density ring, max over the D4x8 stencil transforms (the paper's
own inference), model picked by span bucket (<96 -> q30_64, else q30_128;
spans below 48 keep the CNN - no RF bucket was promoted for 32).  The RF
was trained on {-1,+1} labels with position-tolerant scoring; its
probability calibration differs from the CNN's, so the joint machinery's
thresholds (superset 0.20, defer 0.30, price 1+5(1-p)) may misalign - the
shadow run measures the SYSTEM effect of that too.

Outputs: corpus event-F1 (val split, tol 3.0) for CNN and RF paths,
spotify-380 kept-C0 counts, and synthetic star/lshape/rect corner counts.
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

import geometry_vectorizer as gv  # noqa: E402
from eval_joint_corners import joint_corner_positions  # noqa: E402
from retrain_corner_rf import stencil_features, d4_augment  # noqa: E402

BUNDLES = {
    64: joblib.load(ROOT / "models" / "retrain" / "corner_rf_q30_64.joblib"),
    128: joblib.load(ROOT / "models" / "retrain" / "corner_rf_q30_128.joblib"),
    "db4": joblib.load(ROOT / "models" / "retrain" / "corner_rf_db4_128.joblib"),
}
_cnn_probs = gv._corner_probabilities
RF_LANE = "native"       # "native" -> span-bucketed q30 models; "db4" -> lane model


def rf_corner_probabilities(loop: np.ndarray) -> np.ndarray | None:
    span = float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2.0
    if span < 48.0:
        return _cnn_probs(loop)            # no promoted RF bucket below 64
    bundle = BUNDLES["db4"] if RF_LANE == "db4" else BUNDLES[64 if span < 96.0 else 128]
    clf, s = bundle["model"], bundle["s"]
    if len(loop) < 2 * s + 2:
        return _cnn_probs(loop)
    feats = stencil_features(np.asarray(loop, float), s)
    pos = list(clf.classes_).index(1)
    probs = np.zeros(len(feats))
    for g in d4_augment(feats, s):
        probs = np.maximum(probs, clf.predict_proba(g)[:, pos])
    return probs


def to_db4(loop: np.ndarray) -> np.ndarray | None:
    """Re-quantise a GT loop into the production deblur-4x condition:
    rasterise its mask, LANCZOS 4x, threshold 0.5, re-trace on the 4x
    lattice.  GT event positions simply scale by 4 (position matching
    absorbs the lattice noise via the scaled tolerance)."""
    import cv2
    from augment_training_data import rasterize, biggest_loop
    mask, shift = rasterize(loop)
    up = cv2.resize((mask * 255).astype(np.float32), None, fx=4, fy=4,
                    interpolation=cv2.INTER_LANCZOS4)
    lp = biggest_loop(up >= 127.5)
    if lp is None:
        return None
    # mask_loops reports boundary-pixel centres; after a 4x half-pixel resize
    # the traced ring is centred half a native pixel high/right unless the
    # pixel-centre phase is restored.  Keep the result in GT-frame x4 units.
    return lp - shift[None, :] * 4.0 - 2.0


def _production_classic_positions(loop: np.ndarray, lattice_scale: int) -> np.ndarray:
    """Classic fallback used by ``process`` when the joint prerequisite defers."""
    coarse = loop[::max(1, int(lattice_scale))]
    positions = gv.paper_corner_positions(coarse)
    return np.asarray(positions, float) if len(positions) else np.empty((0, 2))


def _production_corner_positions(loop: np.ndarray, lattice_scale: int) -> tuple[np.ndarray, bool]:
    pred = joint_corner_positions(loop, lattice_scale=lattice_scale)
    if pred is None:
        return _production_classic_positions(loop, lattice_scale), False
    return pred, True


def corpus_f1(limit: int, tolerance: float, condition: str = "native") -> dict:
    from svg_corner_gt import iter_shard_examples
    dataset = ROOT / "datasets" / "corner_gt_v4_perceptual_events"
    tp = fp = fn = 0
    loops_seen = 0
    joint_used = 0
    lattice_scale = 4 if condition == "db4" else 1
    for points, labels, meta in iter_shard_examples(dataset, {"val"}):
        if loops_seen >= limit:
            break
        loop = np.asarray(points, float)
        event_ids = np.asarray(meta["event_ids"])
        if len(loop) < 24:
            continue
        base_loop = loop
        if condition == "db4":
            lp4 = to_db4(loop)
            if lp4 is None:
                continue
            # Production divides the traced 4x-lattice ring before fitting.
            # The geometry is native px; density remains 4 samples/native px.
            loop = lp4 / 4.0
        loops_seen += 1
        pred, used_joint = _production_corner_positions(loop, lattice_scale)
        if used_joint:
            joint_used += 1
        events = []
        for eid in np.unique(event_ids):
            if eid < 0:
                continue
            events.append(base_loop[event_ids == eid].mean(axis=0))
        events = np.asarray(events, float) if events else np.empty((0, 2))
        matched_e: set[int] = set()
        matched_p: set[int] = set()
        if len(pred) and len(events):
            d = np.linalg.norm(pred[:, None, :] - events[None, :, :], axis=2)
            order = np.dstack(np.unravel_index(np.argsort(d, axis=None), d.shape))[0]
            for pi, ei in order:
                if d[pi, ei] > tolerance:
                    break
                if pi in matched_p or ei in matched_e:
                    continue
                matched_p.add(int(pi))
                matched_e.add(int(ei))
        tp += len(matched_e)
        fp += len(pred) - len(matched_p)
        fn += len(events) - len(matched_e)
    P = tp / max(1, tp + fp)
    R = tp / max(1, tp + fn)
    return {"loops": loops_seen, "joint_used": joint_used,
            "P": round(P, 4), "R": round(R, 4),
            "F1": round(2 * P * R / max(1e-9, P + R), 4),
            "tp": tp, "fp": fp, "fn": fn}


def spotify_counts() -> list[int]:
    from benchmark_stages import svg_region_masks, _to_ccw, COR
    from vectorize_papers import mask_loops
    out = []
    for m, _ in svg_region_masks(COR / "simple-icons/spotify.svg", target=380):
        for lp in mask_loops(m):
            lp = lp.astype(float)
            if len(lp) > 1 and np.allclose(lp[0], lp[-1]):
                lp = lp[:-1]
            if len(lp) < 8:
                continue
            pred = joint_corner_positions(_to_ccw(lp))
            out.append(-1 if pred is None else len(pred))
    return out


def synth_counts() -> dict:
    from PIL import Image, ImageDraw
    from vectorize_papers import mask_loops
    from benchmark_stages import _to_ccw
    import math
    shapes = {}
    img = Image.new("L", (300, 300), 0)
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(10):
        r = 130 if i % 2 == 0 else 55
        a = -math.pi / 2 + math.pi * i / 5
        pts.append((150 + r * math.cos(a), 150 + r * math.sin(a)))
    d.polygon(pts, fill=255)
    shapes["star(10)"] = np.asarray(img) > 128
    img = Image.new("L", (300, 300), 0)
    d = ImageDraw.Draw(img)
    d.polygon([(40, 40), (260, 40), (260, 140), (150, 140), (150, 260), (40, 260)], fill=255)
    shapes["lshape(6)"] = np.asarray(img) > 128
    img = Image.new("L", (300, 300), 0)
    d = ImageDraw.Draw(img)
    d.rectangle([60, 80, 240, 220], fill=255)
    shapes["rect(4)"] = np.asarray(img) > 128
    out = {}
    for name, mask in shapes.items():
        loops = mask_loops(mask)
        loop = max(loops, key=len).astype(float)
        if np.allclose(loop[0], loop[-1]):
            loop = loop[:-1]
        pred = joint_corner_positions(_to_ccw(loop))
        out[name] = -1 if pred is None else len(pred)
    return out


def _synth_loops() -> dict[str, np.ndarray]:
    """Canonical native loops shared by the count and db4-equivalence gates."""
    from PIL import Image, ImageDraw
    from vectorize_papers import mask_loops
    from benchmark_stages import _to_ccw
    import math

    masks: dict[str, np.ndarray] = {}
    img = Image.new("L", (300, 300), 0)
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(10):
        r = 130 if i % 2 == 0 else 55
        a = -math.pi / 2 + math.pi * i / 5
        pts.append((150 + r * math.cos(a), 150 + r * math.sin(a)))
    d.polygon(pts, fill=255)
    masks["star(10)"] = np.asarray(img) > 128
    img = Image.new("L", (300, 300), 0)
    d = ImageDraw.Draw(img)
    d.polygon([(40, 40), (260, 40), (260, 140), (150, 140), (150, 260), (40, 260)], fill=255)
    masks["lshape(6)"] = np.asarray(img) > 128
    img = Image.new("L", (300, 300), 0)
    d = ImageDraw.Draw(img)
    d.rectangle([60, 80, 240, 220], fill=255)
    masks["rect(4)"] = np.asarray(img) > 128

    loops: dict[str, np.ndarray] = {}
    for name, mask in masks.items():
        loop = max(mask_loops(mask), key=len).astype(float)
        if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
            loop = loop[:-1]
        loops[name] = _to_ccw(loop)
    return loops


def synth_counts_db4() -> dict:
    """N2 contract gate: native and db4 production arms must be equivalent.

    Counts are the ideal 10/6/4 and corresponding corner positions may move
    by at most 0.75 native px after the 4x trace is divided by four.
    """
    from scipy.optimize import linear_sum_assignment

    expected = {"star(10)": 10, "lshape(6)": 6, "rect(4)": 4}
    rows = {}
    passed = True
    for name, loop in _synth_loops().items():
        native, _ = _production_corner_positions(loop, 1)
        lp4 = to_db4(loop)
        if lp4 is None:
            rows[name] = {"expected": expected[name], "error": "to_db4 failed", "pass": False}
            passed = False
            continue
        db4, _ = _production_corner_positions(lp4 / 4.0, 4)
        max_delta = None
        if len(native) == len(db4) and len(native):
            dist = np.linalg.norm(native[:, None, :] - db4[None, :, :], axis=2)
            ri, ci = linear_sum_assignment(dist)
            max_delta = float(dist[ri, ci].max())
        row_pass = (len(native) == expected[name] == len(db4)
                    and max_delta is not None and max_delta <= 0.75)
        rows[name] = {
            "expected": expected[name],
            "native_count": int(len(native)),
            "db4_count": int(len(db4)),
            "max_position_delta_px": None if max_delta is None else round(max_delta, 4),
            "pass": bool(row_pass),
        }
        passed = passed and row_pass
    return {"pass": bool(passed), "shapes": rows}


def classifier_f1_db4(limit: int) -> dict:
    """Classifier-LEVEL comparison on db4-conditioned loops: probs -> run-NMS
    -> positions -> greedy match (step-2 scorer), NO joint DP.  The
    end-to-end db4 arms drowned in the 4x-density joint machinery (P~0.11
    for BOTH classifiers), so they measured the machinery, not the models."""
    from svg_corner_gt import iter_shard_examples
    from retrain_corner_rf_step2 import predicted_positions, match_prf
    dataset = ROOT / "datasets" / "corner_gt_v4_perceptual_events"
    THS = (0.125, 0.2, 0.3, 0.4, 0.5, 0.6)
    rows = {(tag, th): [0, 0, 0] for tag in ("CNN", "RF") for th in THS}
    loops_seen = 0
    for points, labels, meta in iter_shard_examples(dataset, {"val"}):
        if loops_seen >= limit:
            break
        loop = np.asarray(points, float)
        event_ids = np.asarray(meta["event_ids"])
        if len(loop) < 24:
            continue
        lp4 = to_db4(loop)
        if lp4 is None:
            continue
        loops_seen += 1
        events = []
        for eid in np.unique(event_ids):
            if eid < 0:
                continue
            events.append(loop[event_ids == eid].mean(axis=0) * 4.0)
        events = np.asarray(events, float) if events else np.empty((0, 2))
        for tag in ("CNN", "RF"):
            if tag == "CNN":
                probs = _cnn_probs(lp4)
            else:
                bundle = BUNDLES["db4"]
                clf, s = bundle["model"], bundle["s"]
                if len(lp4) < 2 * s + 2:
                    probs = None
                else:
                    feats = stencil_features(lp4, s)
                    pos_i = list(clf.classes_).index(1)
                    probs = np.zeros(len(feats))
                    for g in d4_augment(feats, s):
                        probs = np.maximum(probs, clf.predict_proba(g)[:, pos_i])
            if probs is None:
                continue
            # neither model's production threshold is fair for the other, so
            # sweep a shared grid and take the best GLOBAL point per model
            for th in THS:
                pred = predicted_positions(np.asarray(probs), lp4, th)
                a, b, c = match_prf(pred, events, 12.0)
                rows[(tag, th)][0] += a
                rows[(tag, th)][1] += b
                rows[(tag, th)][2] += c
    out = {"loops": loops_seen}
    for tag in ("CNN", "RF"):
        best = None
        for th in THS:
            tp, fp, fn = rows[(tag, th)]
            P = tp / max(1, tp + fp)
            R = tp / max(1, tp + fn)
            F = 2 * P * R / max(1e-9, P + R)
            if best is None or F > best["F1"]:
                best = {"th": th, "P": round(P, 4), "R": round(R, 4),
                        "F1": round(F, 4)}
        out[tag] = best
    return out


def main() -> int:
    global RF_LANE
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    report = {}
    for tag in ("CNN", "RF"):
        gv._corner_probabilities = _cnn_probs if tag == "CNN" else rf_corner_probabilities
        RF_LANE = "native"
        t0 = time.time()
        report[tag] = {"corpus": corpus_f1(limit, 3.0),
                       "spotify380": spotify_counts(),
                       "synth": synth_counts(),
                       "secs": round(time.time() - t0, 1)}
        print(tag, json.dumps(report[tag]), flush=True)
    # db4-conditioned arms: the SAME val loops, traced on the 4x lattice but
    # fed to the fitter in native coordinates exactly as production does.
    for tag in ("CNN_db4", "RF_db4"):
        gv._corner_probabilities = _cnn_probs if tag == "CNN_db4" else rf_corner_probabilities
        RF_LANE = "db4"
        t0 = time.time()
        report[tag] = {"corpus": corpus_f1(limit, 3.0, condition="db4"),
                       "secs": round(time.time() - t0, 1)}
        print(tag, json.dumps(report[tag]), flush=True)
    gv._corner_probabilities = _cnn_probs
    RF_LANE = "native"
    report["dp4x_equivalence"] = synth_counts_db4()
    print("dp4x_equivalence", json.dumps(report["dp4x_equivalence"]), flush=True)
    out = ROOT / "benchmarks" / "shadow_rf_corners.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
