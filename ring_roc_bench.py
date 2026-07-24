"""Council N3/N6 ring ROC stand: signed measurements before shape-court code."""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

import benchmark_vai as bv
import geometry_vectorizer as gv
from vectorize_papers import fit_circle, mask_loops, signed_area

ROOT = Path(__file__).parent
SIZE = 64
SCALE = 4


def _polygon(center: tuple[float, float], radii: list[float], start: float = -math.pi / 2):
    cx, cy = center
    return [(cx + radius * math.cos(start + 2 * math.pi * i / len(radii)),
             cy + radius * math.sin(start + 2 * math.pi * i / len(radii)))
            for i, radius in enumerate(radii)]


def make_shape(kind: str, radius: float, phase: tuple[float, float]) -> Image.Image:
    image = Image.new("L", (SIZE * SCALE, SIZE * SCALE), 255)
    draw = ImageDraw.Draw(image)
    center = ((SIZE / 2 + phase[0]) * SCALE, (SIZE / 2 + phase[1]) * SCALE)
    r = radius * SCALE
    box = (center[0] - r, center[1] - r, center[0] + r, center[1] + r)
    if kind == "disc":
        draw.ellipse(box, fill=0)
    elif kind == "ring":
        draw.ellipse(box, fill=0)
        inner = max(1.0, r - max(2.0, radius * 0.28) * SCALE)
        draw.ellipse((center[0] - inner, center[1] - inner,
                      center[0] + inner, center[1] + inner), fill=255)
    elif kind == "bitten":
        draw.ellipse(box, fill=0)
        bite = (center[0] + 0.35 * r, center[1] - 0.55 * r,
                center[0] + 1.25 * r, center[1] + 0.20 * r)
        draw.ellipse(bite, fill=255)
    elif kind == "crescent":
        draw.ellipse(box, fill=0)
        draw.ellipse((center[0] - 0.05 * r, center[1] - 0.9 * r,
                      center[0] + 1.55 * r, center[1] + 0.9 * r), fill=255)
    elif kind == "pacman":
        draw.ellipse(box, fill=0)
        draw.polygon([center, (center[0] + 1.3 * r, center[1] - 0.75 * r),
                      (center[0] + 1.3 * r, center[1] + 0.75 * r)], fill=255)
    elif kind == "rounded_square":
        draw.rounded_rectangle(box, radius=max(1, int(0.28 * r)), fill=0)
    elif kind == "diamond":
        draw.polygon(_polygon(center, [r] * 4), fill=0)
    elif kind == "octagon":
        draw.polygon(_polygon(center, [r] * 8, start=math.pi / 8), fill=0)
    elif kind == "gear":
        draw.polygon(_polygon(center, [r if i % 2 == 0 else 0.76 * r for i in range(20)]), fill=0)
    elif kind == "drop":
        points = []
        for i in range(48):
            angle = 2 * math.pi * i / 48
            radial = r * (1.0 + 0.30 * math.cos(angle))
            points.append((center[0] + radial * math.cos(angle),
                           center[1] + 0.82 * radial * math.sin(angle)))
        draw.polygon(points, fill=0)
    else:
        raise ValueError(kind)
    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS).convert("RGB")


def degrade(image: Image.Image, condition: str) -> Image.Image:
    if condition == "clean":
        return image
    arr = np.asarray(image, np.float32) / 255.0
    quality = 30 if condition in {"q30", "gamma13_q30"} else 45
    if condition == "gamma13_q30":
        arr = np.power(arr, 1.0 / 1.3)
    image = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, subsampling=2, optimize=False)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _cyclic_longest_run(signs: np.ndarray) -> int:
    if not len(signs):
        return 0
    doubled = np.concatenate((signs, signs))
    best = run = 0
    previous = None
    for value in doubled:
        if value == previous:
            run += 1
        else:
            run = 1
            previous = value
        best = max(best, run)
    return min(best, len(signs))


def measure(image: Image.Image) -> dict | None:
    gray = np.asarray(image.convert("L"), np.uint8)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    loops = mask_loops(binary > 0)
    if not loops:
        return None
    loop = max(loops, key=lambda candidate: abs(signed_area(candidate))).astype(float)
    if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
        loop = loop[:-1]
    fitted = fit_circle(loop)
    if fitted is None:
        return None
    center, radius, rms = fitted
    residual = np.linalg.norm(loop - center, axis=1) - radius
    mad = float(np.median(np.abs(residual - np.median(residual))))
    angles = np.mod(np.arctan2(loop[:, 1] - center[1], loop[:, 0] - center[0]), 2 * math.pi)
    bins = np.floor(angles / (2 * math.pi / 24)).astype(int)
    radial_bins = np.full(24, np.nan)
    for index in range(24):
        values = residual[bins == index]
        if len(values):
            radial_bins[index] = float(np.median(values))
    coverage = int(np.count_nonzero(np.isfinite(radial_bins)))
    filled = radial_bins.copy()
    filled[~np.isfinite(filled)] = 0.0
    spectrum = np.abs(np.fft.rfft(filled - np.mean(filled))) / max(1, len(filled))
    harmonic = float(np.sum(spectrum[2:5]) / max(radius, 1e-9))
    high_harmonic = float(np.max(spectrum[5:13]) / max(radius, 1e-9))
    signs = np.sign(filled)
    signs[signs == 0] = 1
    longest = _cyclic_longest_run(signs)
    area = abs(float(signed_area(loop)))
    peri = max(float(gv.perimeter(np.vstack((loop, loop[:1])))), 1e-9)
    q = 4.0 * math.pi * area / (peri * peri)
    existing = gv._whole_loop_circle(np.vstack((loop, loop[:1])), 1.0) is not None
    return {"radius": round(float(radius), 4), "rms": round(float(rms), 5),
            "mad": round(mad, 5), "harmonic_2_4": round(harmonic, 6),
            "harmonic_5_12_max": round(high_harmonic, 6),
            "longest_sign_run": int(longest), "sector_coverage": coverage,
            "isoperimetric_q": round(float(q), 5),
            "rot90_iou": round(float(bv.rot90_iou(binary > 0)), 5),
            "existing_circle": bool(existing)}


def threshold_probe(rows: list[dict], key: str, lower_positive: bool) -> dict:
    ordinary = [row for row in rows if row["class"] in {"positive", "negative"}]
    values = sorted({float(row["metrics"][key]) for row in ordinary})
    candidates = values + [(a + b) / 2 for a, b in zip(values, values[1:])]
    best = None
    for threshold in candidates:
        correct = 0
        for row in ordinary:
            pred = (row["metrics"][key] <= threshold) if lower_positive else (
                row["metrics"][key] >= threshold)
            correct += pred == (row["class"] == "positive")
        accuracy = correct / max(1, len(ordinary))
        if best is None or accuracy > best[0]:
            best = (accuracy, threshold)
    return {"best_accuracy": round(float(best[0]), 4),
            "threshold": round(float(best[1]), 6),
            "positive_if": "<=" if lower_positive else ">="}


def main() -> int:
    rows = []
    phases = ((0.0, 0.0), (0.25, 0.0), (0.5, 0.5))
    conditions = ("clean", "q45", "q30", "gamma13_q30")
    positive = ("disc", "ring")
    negative = ("drop", "rounded_square", "diamond", "crescent", "pacman", "octagon", "gear")
    appeal = ("bitten",)
    for kind, cls in [(kind, "positive") for kind in positive] + [
            (kind, "negative") for kind in negative] + [(kind, "appeal") for kind in appeal]:
        for radius in (6.0, 10.0, 14.0):
            for phase in phases:
                for condition in conditions:
                    metrics = measure(degrade(make_shape(kind, radius, phase), condition))
                    if metrics is None:
                        continue
                    rows.append({"shape": kind, "class": cls, "radius": radius,
                                 "phase": list(phase), "condition": condition,
                                 "metrics": metrics})
    existing = [row for row in rows if row["class"] in {"positive", "negative"}]
    tp = sum(row["class"] == "positive" and row["metrics"]["existing_circle"] for row in existing)
    fn = sum(row["class"] == "positive" and not row["metrics"]["existing_circle"] for row in existing)
    fp = sum(row["class"] == "negative" and row["metrics"]["existing_circle"] for row in existing)
    tn = sum(row["class"] == "negative" and not row["metrics"]["existing_circle"] for row in existing)
    probes = {
        "mad": threshold_probe(rows, "mad", True),
        "harmonic_2_4": threshold_probe(rows, "harmonic_2_4", True),
        "harmonic_5_12_max": threshold_probe(rows, "harmonic_5_12_max", True),
        "longest_sign_run": threshold_probe(rows, "longest_sign_run", True),
        "sector_coverage": threshold_probe(rows, "sector_coverage", False),
        "isoperimetric_q": threshold_probe(rows, "isoperimetric_q", False),
        "rot90_iou": threshold_probe(rows, "rot90_iou", False),
    }
    report = {"n": len(rows), "existing_detector": {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
              "recall": round(tp / max(1, tp + fn), 4),
              "precision": round(tp / max(1, tp + fp), 4)},
              "single_feature_probes": probes, "rows": rows}
    out = ROOT / "benchmarks" / "ring_roc.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
