"""Focused held-out checks for the cheap incremental training strategy.

Training uses Arial; evaluation uses Segoe UI Light.  Smooth curve bars are all
negative, while procedural thin/concave primitives have exact known corners.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

import corner_classifier as cc
import corner_cnn
import corner_perres
from compare_corner_detectors import _match
from svg_corner_gt import infer_corner_events


def examples():
    held_font = r"C:/Windows/Fonts/segoeuil.ttf"
    chars = "ABCEFGHKMNRSVWXYabefgkmnrsvwxy0235689"
    for char in chars:
        for res in (12, 16, 20, 24, 32, 48, 64):
            out = cc._synth_text(random.Random(res), res, text=char, font_path=held_font)
            if out is None:
                continue
            mask, corners = out
            for raw in cc.mask_loops(mask):
                loop = raw[:-1] if len(raw) > 1 and np.allclose(raw[0], raw[-1]) else raw
                if len(loop) < corner_cnn.MIN_LOOP:
                    continue
                loop = cc._to_ccw(loop.astype(float))
                valid = cc._validate_svg_corners(loop, corners)
                labels = corner_cnn._labels_for(loop, valid)
                event_ids, event_kinds = infer_corner_events(loop, labels.astype(np.uint8))
                yield "letters", loop, event_ids, event_kinds
    kinds = ("thin_rect", "diamond", "trapezoid", "chevron", "notch", "zigzag")
    for index in range(300):
        kind = kinds[index % len(kinds)]
        res = (16, 20, 24, 32, 48, 64, 96)[index % 7]
        mask, corners = cc._synth_shape(random.Random(1000 + index), res, forced_kind=kind)
        loop = cc.outer_loop(mask)
        if loop is None or len(loop) < corner_cnn.MIN_LOOP:
            continue
        loop = cc._to_ccw(loop)
        labels = corner_cnn._labels_for(loop, corners)
        event_ids, event_kinds = infer_corner_events(loop, labels.astype(np.uint8))
        yield "primitives", loop, event_ids, event_kinds
    for index in range(300):
        kind = "curvebar" if index % 2 else "sbar"
        res = (12, 16, 20, 24, 32, 48, 64, 96)[index % 8]
        mask = cc._synth_smooth_mask(random.Random(2000 + index), res, forced_kind=kind)
        for raw in cc.mask_loops(mask):
            loop = raw[:-1] if len(raw) > 1 and np.allclose(raw[0], raw[-1]) else raw
            if len(loop) < corner_cnn.MIN_LOOP:
                continue
            loop = cc._to_ccw(loop.astype(float))
            yield "smooth-curves", loop, np.full(len(loop), -1, np.int32), np.zeros(len(loop), np.uint8)


def evaluate(detector) -> dict:
    rows = {}
    for family, loop, event_ids, event_kinds in examples():
        pred = detector(loop)
        tp, fp, fn, _, _ = _match(loop, pred, event_ids, event_kinds, 3.0)
        row = rows.setdefault(family, [0, 0, 0, 0])
        row[0] += tp; row[1] += fp; row[2] += fn; row[3] += 1
    out = {}
    for family, (tp, fp, fn, loops) in rows.items():
        p = tp / max(1, tp + fp); r = tp / max(1, tp + fn)
        out[family] = {"P": round(p, 4), "R": round(r, 4),
                       "F1": round(2 * p * r / max(1e-12, p + r), 4),
                       "fp_per_loop": round(fp / max(1, loops), 4), "loops": loops}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", type=Path, default=[])
    parser.add_argument("--threshold", type=float, default=0.28)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    models = args.model or [corner_cnn.CNN_PATH]
    report = {}
    for model in models:
        report[f"cnn:{model.name}"] = evaluate(
            lambda loop, p=model: corner_cnn.predict_corners(
                loop, threshold=args.threshold, nms_px=2.0, model_path=p))
    report["paper-perres-rf"] = evaluate(
        lambda loop: corner_perres.predict_corners_perres(loop, threshold=None, nms_px=2.0))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
