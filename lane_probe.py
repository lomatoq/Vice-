"""Council N3 causal lane stand for codec-confetti decisions.

This is intentionally a read-only diagnostic with respect to production.  It
profiles the exact loci that the parked confetti mechanism would mutate, then
asks four independent questions: does the residue regenerate after erasure and
JPEG cycling, does its palette assignment persist, how much does it flutter,
and is it confined to an estimated codec grid?  No scalar is allowed to become
a deletion rule merely because it looks plausible on one icon.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import benchmark_vai as bv
import geometry_vectorizer as gv
from subpixel_mininet import compact_palette


ROOT = Path(__file__).parent
CHALLENGE = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack/eval/crops")
OUT = ROOT / "benchmarks" / "lane_probe.json"


COHORTS = [
    ("057_flecks", CHALLENGE / "item057.png", "target"),
    ("caption_glyphs", bv.find_source("icon_group_4_62"), "protect"),
    ("clean_accents_a", bv.find_source("icon_group_4_16"), "protect"),
    ("clean_accents_b", bv.find_source("icon_group_4_21"), "protect"),
    ("stub_loci_059", CHALLENGE / "item059.png", "protect"),
    ("stub_loci_068", CHALLENGE / "item068.png", "protect"),
]

PROFILE_NAMED = ["item053", "item057", "item059", "item068",
                 "item082", "item104", "item111"]


def _jpeg_cycle(image: Image.Image, quality: int, shift: tuple[int, int] = (0, 0)) -> Image.Image:
    rgb = image.convert("RGB")
    sx, sy = shift
    if sx or sy:
        arr = np.asarray(rgb)
        padded = cv2.copyMakeBorder(arr, sy, 0, sx, 0, cv2.BORDER_REFLECT_101)
        rgb = Image.fromarray(padded, "RGB")
    stream = io.BytesIO()
    rgb.save(stream, "JPEG", quality=int(quality), subsampling=0)
    decoded = Image.open(io.BytesIO(stream.getvalue())).convert("RGB")
    if sx or sy:
        decoded = decoded.crop((sx, sy, sx + image.width, sy + image.height))
    return decoded


def _ghost_quality(image: Image.Image) -> dict:
    """Small deterministic JPEG-ghost scan; fallback values are council-signed."""
    src = np.asarray(image.convert("RGB"), np.float32)
    scores = {}
    for quality in (20, 35, 50):
        rec = np.asarray(_jpeg_cycle(image, quality), np.float32)
        # Block-aware residual: matching double quantization minimizes both the
        # RGB change and the change in Laplacian structure at codec boundaries.
        rgb_mse = float(np.mean((rec - src) ** 2))
        lum_a = cv2.cvtColor(src.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        lum_b = cv2.cvtColor(rec.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        lap_mse = float(np.mean((cv2.Laplacian(lum_a, cv2.CV_32F)
                                 - cv2.Laplacian(lum_b, cv2.CV_32F)) ** 2))
        scores[str(quality)] = rgb_mse + 0.15 * lap_mse
    quality = min((20, 35, 50), key=lambda q: scores[str(q)])
    return {"quality": int(quality), "scores": scores}


def _palette_labs(image: Image.Image) -> np.ndarray:
    anchors = compact_palette(image.convert("RGB"), thick_core_veto=False)
    if not len(anchors):
        return np.empty((0, 3), np.float32)
    return cv2.cvtColor(anchors.reshape(1, -1, 3).astype(np.uint8),
                        cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)


def _nearest_anchor(lab_color: np.ndarray, palette_labs: np.ndarray) -> np.ndarray:
    if not len(palette_labs):
        return lab_color.astype(np.float32)
    return palette_labs[int(np.argmin(np.linalg.norm(palette_labs - lab_color, axis=1)))]


def _native_support(component: np.ndarray, scale: int, native_size: tuple[int, int]) -> np.ndarray:
    w, h = native_size
    if scale == 1:
        return component.astype(bool)
    coverage = cv2.resize(component.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
    # One 4x lattice pixel is meaningful AA evidence; keep it in the causal crop.
    return coverage >= (0.5 / float(scale * scale))


def _lab_pixels(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(image.convert("RGB"), np.uint8),
                        cv2.COLOR_RGB2LAB).astype(np.float32)


def _grid_confinement(support: np.ndarray, grid: dict) -> float:
    if not support.any() or not grid.get("period"):
        return 0.0
    boundary = support & ~cv2.erode(support.astype(np.uint8), np.ones((3, 3), np.uint8),
                                    iterations=1).astype(bool)
    ys, xs = np.nonzero(boundary)
    if not len(xs):
        return 0.0
    period = int(grid["period"])

    def phase_dist(coords: np.ndarray, phase: int) -> np.ndarray:
        residue = (coords - int(phase)) % period
        return np.minimum(residue, period - residue)

    dist = np.minimum(phase_dist(xs, int(grid["phase_x"])),
                      phase_dist(ys, int(grid["phase_y"])))
    return float(np.mean(dist <= 1))


def _candidate_context(image: Image.Image, ghost: dict) -> dict:
    quality = int(ghost["quality"])
    perturbations = [
        _jpeg_cycle(image, quality),
        _jpeg_cycle(image, max(5, quality - 15)),
        _jpeg_cycle(image, quality, shift=(4, 4)),
    ]
    return {
        "quality": quality,
        "base_rgb": np.asarray(image.convert("RGB"), np.uint8),
        "base_lab": _lab_pixels(image),
        "base_palette": _palette_labs(image),
        "perturbations": [(perturbed, _lab_pixels(perturbed),
                            _palette_labs(perturbed))
                           for perturbed in perturbations],
    }


def _candidate_metrics(image: Image.Image, component: np.ndarray, scale: int,
                       grid: dict, context: dict) -> dict:
    support = _native_support(component, scale, image.size)
    if not support.any():
        return {"regeneration": 0.0, "anchor_persistence": 0.0,
                "flutter": 0.0, "mod_grid_confinement": 0.0}
    kernel = np.ones((3, 3), np.uint8)
    ring = cv2.dilate(support.astype(np.uint8), kernel, iterations=2).astype(bool) & ~support
    base_rgb = context["base_rgb"]
    base_lab = context["base_lab"]
    if not ring.any():
        ring = ~support
    fill = np.median(base_rgb[ring], axis=0).astype(np.uint8)
    base_color = np.median(base_lab[support], axis=0).astype(np.float32)
    ring_color = np.median(base_lab[ring], axis=0).astype(np.float32)
    contrast = max(1.0, float(np.linalg.norm(base_color - ring_color)))

    quality = int(context["quality"])
    base_anchor = _nearest_anchor(base_color, context["base_palette"])
    anchor_deltas = []
    flutter = []
    for perturbed, lab, palette in context["perturbations"]:
        local_color = np.median(lab[support], axis=0).astype(np.float32)
        anchor = _nearest_anchor(local_color, palette)
        anchor_deltas.append(float(np.linalg.norm(anchor - base_anchor)))
        flutter.append(float(np.mean(np.linalg.norm(
            lab[support] - base_lab[support], axis=1))))

    erased = base_rgb.copy()
    erased[support] = fill
    regenerated = np.asarray(_jpeg_cycle(Image.fromarray(erased, "RGB"), quality), np.float32)
    original_mass = float(np.mean(np.linalg.norm(base_rgb[support].astype(np.float32)
                                                 - fill.astype(np.float32), axis=1)))
    regenerated_mass = float(np.mean(np.linalg.norm(regenerated[support]
                                                    - fill.astype(np.float32), axis=1)))
    regeneration = regenerated_mass / max(1.0, original_mass)
    return {
        "regeneration": float(regeneration),
        "original_mass": original_mass,
        "regenerated_mass": regenerated_mass,
        "anchor_persistence": float(np.mean(np.asarray(anchor_deltas) <= 12.0)),
        "anchor_delta_median": float(np.median(anchor_deltas)),
        "flutter": float(np.median(flutter) / contrast),
        "flutter_lab": float(np.median(flutter)),
        "local_contrast_lab": contrast,
        "mod_grid_confinement": _grid_confinement(support, grid),
        "native_support_px": int(support.sum()),
    }


def _extract_audit(image: Image.Image) -> tuple[list[dict], int]:
    measured_noise = gv.measure_image_noise(image)
    _, masks, _, _, _, scale, _ = gv.extract_perceptual_masks(
        image, use_icm=True, merge=True, deblur=max(image.size) <= 512,
        sanctuary=None, palette_thick_veto=measured_noise < 0.27)
    masks = sorted((m for m in masks if int(m.sum()) >= 2),
                   key=lambda mask: int(mask.sum()), reverse=True)
    reference = np.asarray(image.convert("RGB").resize(
        (masks[0].shape[1], masks[0].shape[0]), Image.Resampling.BILINEAR), np.uint8)
    masks, fills = gv._merge_gradient_stacks(masks, reference, scale)
    if not fills:
        masks, _ = gv._merge_gradient_field(masks, reference, scale)
    audit: list[dict] = []
    gv._absorb_contact_confetti(masks, scale, reference, audit=audit)
    return audit, scale


def _best_split(rows: list[dict], key: str) -> dict:
    samples = [(float(row[key]), row["role"] == "target")
               for row in rows if key in row and np.isfinite(float(row[key]))]
    positives = sum(int(label) for _, label in samples)
    negatives = len(samples) - positives
    if not positives or not negatives:
        return {"status": "insufficient_classes", "n": len(samples)}
    values = sorted({value for value, _ in samples})
    candidates = [values[0] - 1e-6] + [(a + b) / 2.0 for a, b in zip(values, values[1:])] + [values[-1] + 1e-6]
    best = None
    for direction in ("ge", "le"):
        for threshold in candidates:
            tp = fp = tn = fn = 0
            for value, label in samples:
                pred = value >= threshold if direction == "ge" else value <= threshold
                tp += int(pred and label)
                fp += int(pred and not label)
                tn += int(not pred and not label)
                fn += int(not pred and label)
            recall = tp / positives
            specificity = tn / negatives
            bal = 0.5 * (recall + specificity)
            candidate = (bal, recall, specificity, direction, threshold)
            if best is None or candidate > best:
                best = candidate
    assert best is not None
    pvals = [v for v, label in samples if label]
    nvals = [v for v, label in samples if not label]
    overlap_width = max(0.0, min(max(pvals), max(nvals)) - max(min(pvals), min(nvals)))
    union_width = max(max(pvals), max(nvals)) - min(min(pvals), min(nvals))
    overlap = overlap_width / max(1e-9, union_width)
    bal, recall, specificity, direction, threshold = best
    return {"status": "promote" if bal >= 0.90 and overlap <= 0.20 else "feature_only",
            "balanced_accuracy": bal, "target_recall": recall,
            "protection_specificity": specificity, "direction": direction,
            "threshold": threshold, "range_overlap": overlap,
            "n_target": positives, "n_protect": negatives}


def _profile_one(name: str, path: Path) -> dict:
    image = Image.open(path).convert("RGB")
    return {"name": name, "path": str(path), "size": image.size,
            "noise_slack": gv.measure_image_noise(image),
            "grid": gv.estimate_jpeg_grid(image), "ghost": _ghost_quality(image)}


def main() -> int:
    loci = []
    cohorts = []
    for name, path, role in COHORTS:
        if path is None or not Path(path).exists():
            cohorts.append({"name": name, "role": role, "error": "missing source"})
            continue
        image = Image.open(path).convert("RGB")
        grid = gv.estimate_jpeg_grid(image)
        ghost = _ghost_quality(image)
        context = _candidate_context(image, ghost)
        audit, scale = _extract_audit(image)
        cohort_row = {"name": name, "role": role, "path": str(path),
                      "scale": scale, "candidate_count": len(audit),
                      "grid": grid, "ghost": ghost,
                      "noise_slack": gv.measure_image_noise(image)}
        cohorts.append(cohort_row)
        for index, event in enumerate(audit):
            component = event.pop("component_mask")
            row = {"cohort": name, "role": role, "index": index, **event,
                   "grid_confidence": float(grid["confidence"]),
                   **_candidate_metrics(image, component, scale, grid, context)}
            loci.append(row)
        print(f"{name}: {len(audit)} candidate loci, scale={scale}, "
              f"grid={grid['period']}@({grid['phase_x']},{grid['phase_y']}) "
              f"conf={grid['confidence']:.3f}", flush=True)

    named_profile = []
    for name in PROFILE_NAMED:
        path = CHALLENGE / f"{name}.png"
        if path.exists():
            named_profile.append(_profile_one(name, path))
    vai_profile = []
    for stem in bv.frozen_stems(50):
        path = bv.find_source(stem)
        if path is not None:
            vai_profile.append(_profile_one(stem, path))

    signals = ["regeneration", "anchor_persistence", "flutter",
               "mod_grid_confinement", "grid_confidence"]
    splits = {signal: _best_split(loci, signal) for signal in signals}
    # The grid is a causal *key*, never an action: low confidence cannot mean
    # "delete".  Council law is abstention when the diseased target itself has
    # no ghost/grid minimum, even if that absence separates this tiny cohort.
    if splits["grid_confidence"].get("status") == "promote":
        splits["grid_confidence"]["status"] = "feature_only"
        splits["grid_confidence"]["reason"] = "codec grid is a positive key, never a low-confidence deletion signal"
    target_grids = [float(row["grid"]["confidence"]) for row in cohorts
                    if row.get("role") == "target" and "grid" in row]
    target_grid_minimum = min(target_grids, default=0.0)
    causal_signals = ("regeneration", "anchor_persistence", "flutter",
                      "mod_grid_confinement")
    promotable = [key for key in causal_signals
                  if splits[key].get("status") == "promote"
                  and target_grid_minimum >= 0.15]
    if target_grid_minimum < 0.15:
        verdict = "ABSTAIN_NO_TARGET_CODEC_KEY"
    elif promotable:
        verdict = "CAUSAL_KEY_FOUND"
    else:
        verdict = "ALL_SIGNALS_FEATURE_ONLY"
    result = {
        "contract": "diagnostic-only; no production deletion from a scalar signal",
        "cohorts": cohorts, "loci": loci, "signal_splits": splits,
        "target_grid_minimum": target_grid_minimum,
        "verdict": verdict,
        "promotable_signals": promotable,
        "profile": {"named": named_profile, "vai50": vai_profile},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "promotable": promotable,
                      "loci": len(loci), "artifact": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
