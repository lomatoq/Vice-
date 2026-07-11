"""Honest event-level comparison of CNN checkpoints and the paper per-resolution RF.

The evaluator consumes only val/test shards from the reviewed SVG event dataset.  A
short 1--2px corner span counts as one perceptual event even when it has two positive
vertices.  This is the metric needed to choose CNN vs RF without confusing vertex
duplication, NMS, or the later corner-removal stage with detector quality.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

import corner_cnn
import corner_perres
from svg_corner_gt import (EVENT_OCCLUSION, EVENT_POINT, EVENT_SHORT_SPAN,
                           iter_shard_examples)


KIND_NAMES = {EVENT_POINT: "point", EVENT_SHORT_SPAN: "short-span",
              EVENT_OCCLUSION: "occlusion"}


def _match(loop: np.ndarray, predicted: np.ndarray, event_ids: np.ndarray,
           event_kinds: np.ndarray, tolerance: float) -> tuple[int, int, int, Counter, Counter]:
    events: dict[int, np.ndarray] = {}
    kinds: dict[int, int] = {}
    for event_id in np.unique(event_ids[event_ids >= 0]):
        indexes = np.flatnonzero(event_ids == event_id)
        events[int(event_id)] = loop[indexes]
        kinds[int(event_id)] = int(event_kinds[indexes[0]])
    pred_indexes = list(np.flatnonzero(predicted))
    candidates = []
    for pi in pred_indexes:
        for event_id, points in events.items():
            distance = float(np.min(np.linalg.norm(points - loop[pi], axis=1)))
            if distance <= tolerance:
                candidates.append((distance, pi, event_id))
    candidates.sort()
    used_pred: set[int] = set()
    used_event: set[int] = set()
    for _, pi, event_id in candidates:
        if pi not in used_pred and event_id not in used_event:
            used_pred.add(pi)
            used_event.add(event_id)
    total_by_kind = Counter(KIND_NAMES.get(kinds[e], str(kinds[e])) for e in events)
    hit_by_kind = Counter(KIND_NAMES.get(kinds[e], str(kinds[e])) for e in used_event)
    return len(used_event), len(pred_indexes) - len(used_pred), len(events) - len(used_event), hit_by_kind, total_by_kind


def evaluate(dataset: Path, detector, splits: set[str], tolerance: float,
             limit: int = 0) -> dict:
    tp = fp = fn = loops = 0
    hit_kinds: Counter = Counter()
    total_kinds: Counter = Counter()
    by_resolution: dict[int, list[int]] = {}
    by_family: dict[str, list[int]] = {}       # tp, fp, fn, loops, zero-event loops, zero-event fp
    for loop, _labels, meta in iter_shard_examples(dataset, splits=splits):
        if limit and loops >= limit:
            break
        loop = np.asarray(loop, float)
        predicted = detector(loop)
        a, b, c, hk, tk = _match(loop, predicted, np.asarray(meta["event_ids"]),
                                  np.asarray(meta["event_kinds"]), tolerance)
        tp += a; fp += b; fn += c; loops += 1
        hit_kinds.update(hk); total_kinds.update(tk)
        res = int(meta.get("resolution", 0))
        row = by_resolution.setdefault(res, [0, 0, 0])
        row[0] += a; row[1] += b; row[2] += c
        family = Path(str(meta.get("path", "unknown"))).parent.name or "unknown"
        frow = by_family.setdefault(family, [0, 0, 0, 0, 0, 0])
        frow[0] += a; frow[1] += b; frow[2] += c; frow[3] += 1
        if not np.any(np.asarray(meta["event_ids"]) >= 0):
            frow[4] += 1
            frow[5] += b
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "P": round(precision, 4), "R": round(recall, 4), "F1": round(f1, 4),
        "tp_events": tp, "fp_predictions": fp, "fn_events": fn, "loops": loops,
        "fp_per_loop": round(fp / max(1, loops), 4),
        "zero_event": {
            "loops": sum(row[4] for row in by_family.values()),
            "fp": sum(row[5] for row in by_family.values()),
            "fp_per_loop": round(sum(row[5] for row in by_family.values()) /
                                 max(1, sum(row[4] for row in by_family.values())), 4),
        },
        "recall_by_kind": {kind: round(hit_kinds[kind] / max(1, total), 4)
                           for kind, total in sorted(total_kinds.items())},
        "by_resolution": {
            str(res): {"P": round(a / max(1, a + b), 4), "R": round(a / max(1, a + c), 4),
                       "events": a + c}
            for res, (a, b, c) in sorted(by_resolution.items())
        },
        "by_family": {
            family: {
                "P": round(a / max(1, a + b), 4),
                "R": round(a / max(1, a + c), 4),
                "F1": round(2 * a / max(1, 2 * a + b + c), 4),
                "fp_per_loop": round(b / max(1, count), 4),
                "zero_event_loops": zero_count,
                "zero_event_fp_per_loop": round(zero_fp / max(1, zero_count), 4),
            }
            for family, (a, b, c, count, zero_count, zero_fp) in sorted(by_family.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("datasets/corner_gt_v4_perceptual_events"))
    parser.add_argument("--model", action="append", type=Path, default=[],
                        help="CNN checkpoint; may be supplied more than once")
    parser.add_argument("--thresholds", default="0.14,0.20,0.28")
    parser.add_argument("--splits", default="val,test")
    parser.add_argument("--tolerance", type=float, default=3.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-rf", action="store_true")
    parser.add_argument("--hybrid-small-model", type=Path, default=None)
    parser.add_argument("--hybrid-large-model", type=Path, default=None)
    parser.add_argument("--hybrid-small-threshold", type=float, default=0.28)
    parser.add_argument("--hybrid-large-threshold", type=float, default=0.36)
    parser.add_argument("--hybrid-cutoffs", default="",
                        help="comma-separated loop extents; small model is used at/below each cutoff")
    parser.add_argument("--hybrid-max-density", type=float, default=0.0,
                        help="also use the small model above this vertices/extent density")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    models = args.model or [corner_cnn.CNN_PATH]
    thresholds = [float(value) for value in args.thresholds.split(",") if value.strip()]
    splits = {value.strip() for value in args.splits.split(",") if value.strip()}
    report = {"dataset": str(args.dataset), "splits": sorted(splits),
              "tolerance": args.tolerance, "detectors": {}}
    for model in models:
        for threshold in thresholds:
            name = f"cnn:{model.name}@{threshold:.2f}"
            report["detectors"][name] = evaluate(
                args.dataset,
                lambda loop, p=model, t=threshold: corner_cnn.predict_corners(
                    loop, threshold=t, nms_px=2.0, model_path=p),
                splits, args.tolerance, args.limit)
            print(name, report["detectors"][name], flush=True)
    if args.hybrid_small_model and args.hybrid_large_model and args.hybrid_cutoffs:
        for cutoff in [float(value) for value in args.hybrid_cutoffs.split(",") if value.strip()]:
            def hybrid(loop, cut=cutoff):
                extent = max(1.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2.0)
                density = len(loop) / extent
                if extent <= cut or (args.hybrid_max_density > 0 and density > args.hybrid_max_density):
                    return corner_cnn.predict_corners(
                        loop, threshold=args.hybrid_small_threshold, nms_px=2.0,
                        model_path=args.hybrid_small_model)
                return corner_cnn.predict_corners(
                    loop, threshold=args.hybrid_large_threshold, nms_px=2.0,
                    model_path=args.hybrid_large_model)
            name = (f"hybrid:{args.hybrid_small_model.name}@{args.hybrid_small_threshold:.2f}"
                    f"<={cutoff:g}px,density>{args.hybrid_max_density:g}/"
                    f"{args.hybrid_large_model.name}@{args.hybrid_large_threshold:.2f}")
            report["detectors"][name] = evaluate(
                args.dataset, hybrid, splits, args.tolerance, args.limit)
            print(name, report["detectors"][name], flush=True)
    if not args.no_rf:
        name = "paper-perres-rf"
        report["detectors"][name] = evaluate(
            args.dataset,
            lambda loop: corner_perres.predict_corners_perres(loop, threshold=None, nms_px=2.0),
            splits, args.tolerance, args.limit)
        print(name, report["detectors"][name], flush=True)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
