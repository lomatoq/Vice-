"""N12 direct coverage-contour stand for the item053 AARCH line.

The repaired coverage field is fitted outside the shared-region graph.  This
script compares several fit policies against the exact CC/Euler reference and
emits an enlarged visual court; it does not change production routing.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

import geometry_vectorizer as gv
from subpixel_mininet import compact_palette, deblur_4x


ROOT = Path(__file__).parent
SOURCE = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack/eval/crops/item053.png")
BASELINE = ROOT / "benchmarks" / "n4_eval_cap_reverted" / "item053" / "item053" / "03_rebuilt_filled.png"
BOX = (8.33, 9.67, 42.33, 26.0)  # frozen N3 OCR-box evidence, native coordinates
OUT_JSON = ROOT / "benchmarks" / "glyph_coverage_probe.json"
OUT_SHEET = ROOT / "benchmarks" / "glyph_coverage_probe.png"


def _field() -> dict:
    source = Image.open(SOURCE).convert("RGB")
    flat = gv._flatten_white(source)
    analysis = deblur_4x(source, snap_palette=False)
    scale = 4
    pixels = np.asarray(analysis.convert("RGB"), np.uint8)
    anchors = compact_palette(flat, thick_core_veto=False).clip(0, 255).astype(np.uint8)
    lab = cv2.cvtColor(pixels, cv2.COLOR_RGB2LAB).astype(np.float32)
    anchor_lab = cv2.cvtColor(anchors.reshape(1, -1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    labels = np.argmin(np.sum((lab[..., None, :] - anchor_lab[None, None, :, :]) ** 2, axis=3),
                       axis=2).astype(np.int16)
    labels = gv._icm_labels(lab, anchor_lab, labels)

    x0, y0, x1, y1 = [int(round(value * scale)) for value in BOX]
    crop_labels = labels[y0:y1, x0:x1]
    border_labels = np.concatenate((crop_labels[0], crop_labels[-1],
                                    crop_labels[:, 0], crop_labels[:, -1]))
    surround = int(np.bincount(border_labels, minlength=len(anchors)).argmax())
    present = [int(index) for index in np.unique(crop_labels) if int(index) != surround]
    ink = min(present, key=lambda index: float(anchor_lab[index, 0]))

    source_gray = cv2.resize(np.asarray(source.convert("L"), np.uint8),
                             labels.shape[::-1], interpolation=cv2.INTER_LANCZOS4)
    reference_gray = source_gray[y0:y1, x0:x1]
    border_gray = np.concatenate((reference_gray[0], reference_gray[-1],
                                  reference_gray[:, 0], reference_gray[:, -1]))
    deviation = np.abs(reference_gray.astype(float) - float(np.median(border_gray)))
    _, reference_raw = cv2.threshold(deviation.astype(np.uint8), 0, 255,
                                     cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    reference, reference_cc, reference_holes = gv._interior_component_mask(reference_raw > 0, 8)

    surround_rgb = anchors[surround].astype(float)
    axis = anchors[ink].astype(float) - surround_rgb
    crop_pixels = pixels[y0:y1, x0:x1].astype(float)
    projection = np.sum((crop_pixels - surround_rgb) * axis, axis=2) / float(axis @ axis)
    candidates = []
    for threshold in np.linspace(0.15, 0.85, 15):
        candidate, cc, holes = gv._interior_component_mask(projection >= float(threshold), 8)
        if cc != reference_cc or holes > reference_holes + 1:
            continue
        union = int(np.count_nonzero(candidate | reference))
        iou = float(np.count_nonzero(candidate & reference)) / union if union else 1.0
        candidates.append((iou, -abs(float(threshold) - 0.5), float(threshold), holes, candidate))
    if not candidates:
        raise RuntimeError("no CC/Euler-matched coverage field")
    iou, _, threshold, holes, candidate = max(candidates, key=lambda row: row[:2])
    global_mask = np.zeros_like(labels, bool)
    global_mask[y0:y1, x0:x1] = candidate
    return {"source": source, "scale": scale, "anchors": anchors, "ink": ink,
            "surround": surround, "bbox_analysis": (x0, y0, x1, y1),
            "reference": reference, "reference_cc": reference_cc,
            "reference_holes": reference_holes, "threshold": threshold,
            "coverage_iou": iou, "coverage_holes": holes,
            "candidate": candidate, "global_mask": global_mask}


def _fit(mask: np.ndarray, scale: int, ink: tuple[int, int, int], mode: str) -> tuple[Image.Image, list]:
    loops = []
    for raw in gv.mask_loops(mask):
        if gv.perimeter(raw) < 4 * scale:
            continue
        full = raw / float(scale)
        if mode == "paper-1.0":
            alpha = gv._PAPER_FIT_ALPHA_K / max(16.0, float(np.ptp(full[:, 0]) + np.ptp(full[:, 1])) / 2)
            fitted = gv.fit_loop_paper(full, alpha, px=1.0, lattice_scale=scale)
        elif mode == "paper-0.6":
            alpha = gv._PAPER_FIT_ALPHA_K / max(16.0, float(np.ptp(full[:, 0]) + np.ptp(full[:, 1])) / 2)
            fitted = gv.fit_loop_paper(full, alpha, px=0.6, lattice_scale=scale)
        elif mode == "paper-simplify-1.0":
            alpha = gv._PAPER_FIT_ALPHA_K / max(16.0, float(np.ptp(full[:, 0]) + np.ptp(full[:, 1])) / 2)
            corners = gv.paper_corner_positions(full[::scale])
            fitted = gv.fit_loop_paper(full, alpha, corner_positions=corners,
                                       px=1.0, lattice_scale=scale,
                                       preserve_tiny=False)
        elif mode == "paper-simplify-0.6":
            alpha = gv._PAPER_FIT_ALPHA_K / max(16.0, float(np.ptp(full[:, 0]) + np.ptp(full[:, 1])) / 2)
            corners = gv.paper_corner_positions(full[::scale])
            fitted = gv.fit_loop_paper(full, alpha, corner_positions=corners,
                                       px=0.6, lattice_scale=scale,
                                       preserve_tiny=False)
        elif mode == "perceptual":
            fitted = gv.fit_perceptual_loop(full, feature_scale=0.48)
        elif mode.startswith("rdp-"):
            epsilon = float(mode.split("-", 1)[1])
            approx = cv2.approxPolyDP(full.astype(np.float32).reshape(-1, 1, 2),
                                      epsilon, True).reshape(-1, 2).astype(float)
            curves = [gv.Curve(1, np.vstack((approx[index], approx[(index + 1) % len(approx)])))
                      for index in range(len(approx))]
            fitted = gv.FittedLoop(full, curves, f"glyph-rdp-{epsilon:g}")
        else:
            raise ValueError(mode)
        loops.append(fitted)
    region = gv.Region(ink, int(mask.sum() / (scale * scale)), loops)
    return gv.render_regions([region], Image.open(SOURCE).size, scale=4), loops


def _binary_from_render(render: Image.Image, ink: np.ndarray, surround: np.ndarray,
                        size: tuple[int, int]) -> np.ndarray:
    arr = np.asarray(render.convert("RGB").resize(size, Image.Resampling.LANCZOS), np.uint8)
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB).astype(np.float32)
    poles = cv2.cvtColor(np.asarray((ink, surround), np.uint8).reshape(1, 2, 3),
                         cv2.COLOR_RGB2LAB).reshape(2, 3).astype(np.float32)
    return np.linalg.norm(lab - poles[0], axis=2) <= np.linalg.norm(lab - poles[1], axis=2)


def _topology(mask: np.ndarray) -> tuple[int, int]:
    _, count, holes = gv._interior_component_mask(mask, 8)
    return int(count), int(holes)


def _stem_ratio(mask: np.ndarray) -> float:
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    local = dist[(dist > 0) & (dist >= cv2.dilate(dist, np.ones((3, 3), np.uint8)) - 1e-6)]
    if len(local) < 4:
        return 99.0
    return float(np.percentile(local, 90) / max(1e-6, np.percentile(local, 10)))


def _control_length(curve) -> float:
    control = np.asarray(curve.control, float)
    return float(np.sum(np.linalg.norm(np.diff(control, axis=0), axis=1)))


def main() -> int:
    field = _field()
    x0, y0, x1, y1 = field["bbox_analysis"]
    reference = field["reference"]
    rows = []
    renders = []
    for mode in ("paper-1.0", "paper-simplify-1.0",
                 "rdp-0.2", "rdp-0.35", "rdp-0.5"):
        render, loops = _fit(field["global_mask"], field["scale"],
                             tuple(int(v) for v in field["anchors"][field["ink"]]), mode)
        binary = _binary_from_render(render, field["anchors"][field["ink"]],
                                     field["anchors"][field["surround"]],
                                     field["global_mask"].shape[::-1])[y0:y1, x0:x1]
        material, cc, holes = gv._interior_component_mask(binary, 8)
        union = int(np.count_nonzero(material | reference))
        iou = float(np.count_nonzero(material & reference)) / union if union else 1.0
        curves = [curve for loop in loops for curve in loop.curves]
        rows.append({"mode": mode, "cc": cc, "holes": holes, "iou": iou,
                     "stem_p90_p10": _stem_ratio(material),
                     "loops": len(loops), "curves": len(curves),
                     "micro_curves": sum(_control_length(curve) < 1.0 for curve in curves),
                     "templates": [loop.template for loop in loops]})
        renders.append((mode, render))

    baseline = Image.open(BASELINE).convert("RGB") if BASELINE.exists() else Image.new("RGB", field["source"].size, "white")
    zoom = 8
    tiles = [("SOURCE", field["source"]), ("BASELINE", baseline)] + [(name.upper(), image) for name, image in renders]
    sheet = Image.new("RGB", (len(tiles) * field["source"].width * zoom,
                              field["source"].height * zoom + 28), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(tiles):
        x = index * field["source"].width * zoom
        sheet.paste(image.resize((field["source"].width * zoom,
                                  field["source"].height * zoom), Image.Resampling.NEAREST), (x, 28))
        draw.text((x + 4, 6), label, fill="black")
    OUT_SHEET.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT_SHEET)
    result = {"source": str(SOURCE), "bbox": BOX,
              "reference_cc": field["reference_cc"],
              "reference_holes": field["reference_holes"],
              "coverage_threshold": field["threshold"],
              "coverage_iou": field["coverage_iou"], "rows": rows,
              "sheet": str(OUT_SHEET)}
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
