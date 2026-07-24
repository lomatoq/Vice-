"""Experiment D: oracle-template layout fit (the v9.5 Template-Warp core).

For each degraded synthetic line (held-out family, balanced lengths) the true
font and transcript are given as an ORACLE template, but none of the render
parameters (tracking, stroke, connected/outline effect) are - the fitter
recovers them from the degraded raster, exactly like the future v9.5 lane will
after retrieval. The fit follows audit S9.1 step 4:

  1. vertical scale from the robust observed ink height;
  2. tracking solved analytically from the observed ink width (+/- refine);
  3. per-glyph horizontal offsets (bounded +/-3 px greedy fit) - the
     "per-glyph width/offset" stage, a bounded topology-preserving warp;
  4. stroke thickness swept at canvas resolution;
  5. explicit topology operators none/connected/outline (audit S8.8).

Arenas:

- fixed   = the wordmark prior's 64x256 letterbox canvas: head-to-head
            comparable with the model diagnostics (ppg shrinks with length);
- dynamic = 64x4096 canvas: height-driven letterbox, pixels-per-glyph
            preserved for every length - the production regime of the lane.

Reported two ways per audit S9.3 (proposal/selector decomposition):

- selected = best candidate by IoU against the thresholded observation;
- oracle   = best candidate by IoU against the clean GT support
             (generator ceiling; the gap is the selector gap).

Usage:
  C:\\Python312\\python.exe diagnose_template_warp_oracle.py --arena dynamic
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

FONT_SIZE = 128
TRACKING_REFINE = (-0.01, 0.0, 0.01)
XSCALE_GRID = (0.95, 1.0, 1.05)
STROKE_RADII = (0, 1, 2, 3, 4)  # canvas-resolution dilation radii
EFFECTS = ("none", "connected1", "connected2", "connected3", "outline")
GLYPH_SHIFT_LIMIT = 3


def _sample_fixed_length_text(generator, length: int, characters: str) -> str:
    mode = int(generator.integers(0, 5))
    if mode == 0:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    elif mode == 1:
        alphabet = "abcdefghijklmnopqrstuvwxyz"
    elif mode == 2:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    elif mode == 3:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    else:
        alphabet = characters.rstrip(" ")
    return "".join(generator.choice(tuple(alphabet), size=length).tolist())


@lru_cache(maxsize=256)
def _cached_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, font_size)


def _render_glyph_layers(
    font_path: str, text: str, tracking_fraction: float,
) -> tuple[np.ndarray, list[np.ndarray]] | None:
    """Render the line once per glyph so offsets can move glyphs later.

    Returns (joint high-res alpha cropped to ink, per-glyph layers in the same
    cropped frame). None when the face renders no ink.
    """
    font = _cached_font(font_path, FONT_SIZE)
    tracking = tracking_fraction * FONT_SIZE
    advances = [
        max(1.0, float(font.getlength(character)) + tracking)
        for character in text
    ]
    bounds = font.getbbox(text)
    canvas_width = max(FONT_SIZE, int(math.ceil(FONT_SIZE + sum(advances))))
    canvas_height = max(
        FONT_SIZE, int(math.ceil(bounds[3] - bounds[1] + 3 * FONT_SIZE // 4)),
    )
    layers: list[np.ndarray] = []
    joint = np.zeros((canvas_height, canvas_width), np.uint8)
    cursor = FONT_SIZE // 2
    y = 3 * FONT_SIZE // 8 - bounds[1]
    for character, advance in zip(text, advances):
        canvas = Image.new("L", (canvas_width, canvas_height), 0)
        ImageDraw.Draw(canvas).text(
            (cursor, y), character, font=font, fill=255,
        )
        layer = np.asarray(canvas, np.uint8)
        layers.append(layer)
        joint = np.maximum(joint, layer)
        cursor += advance
    ys, xs = np.nonzero(joint)
    if not len(xs):
        return None
    y0 = max(0, int(ys.min()) - 2)
    y1 = min(joint.shape[0], int(ys.max()) + 3)
    x0 = max(0, int(xs.min()) - 2)
    x1 = min(joint.shape[1], int(xs.max()) + 3)
    return joint[y0:y1, x0:x1], [layer[y0:y1, x0:x1] for layer in layers]


def _letterbox_geometry(
    shape: tuple[int, int], height: int, width: int,
) -> tuple[float, int, int]:
    """The wordmark prior's canvas policy: factor and paste offsets."""
    margin_y = max(2, height // 14)
    margin_x = max(3, width // 40)
    factor = min(
        (width - 2 * margin_x) / max(1, shape[1]),
        (height - 2 * margin_y) / max(1, shape[0]),
    )
    target_width = max(1, int(round(shape[1] * factor)))
    target_height = max(1, int(round(shape[0] * factor)))
    return factor, (width - target_width) // 2, (height - target_height) // 2


def _letterbox_layer(
    layer: np.ndarray, factor: float, x: int, y: int,
    height: int, width: int,
) -> np.ndarray:
    target_width = max(1, int(round(layer.shape[1] * factor)))
    target_height = max(1, int(round(layer.shape[0] * factor)))
    resized = cv2.resize(
        layer, (target_width, target_height), interpolation=cv2.INTER_AREA,
    )
    canvas = np.zeros((height, width), np.float32)
    canvas[y:y + target_height, x:x + target_width] = resized / 255.0
    return canvas


def _apply_effect(support: np.ndarray, effect: str) -> np.ndarray:
    if effect == "none":
        return support
    mask = support.astype(np.uint8)
    if effect.startswith("connected"):
        radius = int(effect[-1])
        return cv2.morphologyEx(
            mask, cv2.MORPH_CLOSE, np.ones((3, 2 * radius + 1), np.uint8),
        ) > 0
    outer = cv2.dilate(mask, np.ones((3, 3), np.uint8)) > 0
    inner = cv2.erode(mask, np.ones((3, 3), np.uint8)) > 0
    outlined = outer & ~inner
    return outlined if np.any(outlined) else support


def _robust_ink(mask: np.ndarray) -> np.ndarray | None:
    """Major ink components: degradation islands must not steer geometry."""
    if not np.any(mask):
        return None
    _count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8,
    )
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = np.flatnonzero(areas >= max(4, 0.05 * areas.max())) + 1
    return np.isin(labels, keep)


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def _xscale_layer(layer: np.ndarray, factor: float) -> np.ndarray:
    """Widen/narrow one glyph about its own center: per-glyph width."""
    if factor == 1.0 or not np.any(layer):
        return layer
    x0, x1, y0, y1 = _bbox(layer)
    crop = layer[y0:y1 + 1, x0:x1 + 1].astype(np.uint8) * 255
    new_width = max(1, int(round((x1 - x0 + 1) * factor)))
    resized = cv2.resize(
        crop, (new_width, y1 - y0 + 1), interpolation=cv2.INTER_AREA,
    ) >= 128
    out = np.zeros_like(layer)
    center = (x0 + x1) // 2
    n_x0 = max(0, center - new_width // 2)
    x_end = min(out.shape[1], n_x0 + new_width)
    out[y0:y1 + 1, n_x0:x_end] = resized[:, :x_end - n_x0]
    return out


def _shift(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    if dx == 0 and dy == 0:
        return mask
    shifted = np.zeros_like(mask)
    height, width = mask.shape
    ys, xs = np.nonzero(mask)
    ys = ys + dy
    xs = xs + dx
    keep = (ys >= 0) & (ys < height) & (xs >= 0) & (xs < width)
    shifted[ys[keep], xs[keep]] = True
    return shifted


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    union = np.sum(first | second)
    return float(np.sum(first & second) / max(1, union))


def fit_template_line(
    font_path: str, text: str, observed_float: np.ndarray,
    observed_bbox: tuple[int, int, int, int], consider,
) -> bool:
    """The v9.5 fit cascade for one template face against one line.

    Calls `consider(candidate_mask)` for every candidate produced.
    Returns False when the face renders no ink for the text.
    """
    height, arena_width = observed_float.shape
    obs_x0, obs_x1, obs_y0, obs_y1 = observed_bbox
    # Tracking solved analytically from the observed ink width: the
    # letterbox factor is known from the probe render, so the missing
    # width must come from tracking.
    probe = _render_glyph_layers(font_path, text, 0.0)
    if probe is None:
        return False
    probe_joint, _probe_layers = probe
    margin_y = max(2, height // 14)
    margin_x = max(3, arena_width // 40)
    width_factor = (arena_width - 2 * margin_x) / max(1, probe_joint.shape[1])
    height_factor = (height - 2 * margin_y) / max(1, probe_joint.shape[0])
    probe_factor = min(width_factor, height_factor)
    observed_width = float(obs_x1 - obs_x0 + 1)
    observed_height = float(obs_y1 - obs_y0 + 1)
    if height_factor <= width_factor:
        # Height-driven letterbox: the factor is fixed by the ink height, so
        # the missing width must come from tracking.
        factor = min(probe_factor, observed_height / probe_joint.shape[0])
        width_gap = (
            observed_width / max(1e-6, factor) - probe_joint.shape[1]
        )
        analytic_tracking = width_gap / max(1, len(text)) / FONT_SIZE
        analytic_tracking = float(np.clip(analytic_tracking, -0.25, 0.30))
    else:
        # Width-bound letterbox (fixed arena, long lines): widening by
        # tracking only shrinks the whole render back to the same width -
        # the width equation is degenerate and thin strokes vanish. Stay at
        # zero tracking and let per-glyph offsets absorb the spacing.
        analytic_tracking = 0.0

    for refine in TRACKING_REFINE:
        tracking = analytic_tracking + refine
        rendered = _render_glyph_layers(
            font_path, text, tracking,
        )
        if rendered is None:
            continue
        joint, layers = rendered
        geometry_factor, x0, y0 = _letterbox_geometry(
            joint.shape, height, arena_width,
        )
        float_layers = [
            _letterbox_layer(
                layer, geometry_factor, x0, y0, height, arena_width,
            )
            for layer in layers
        ]
        boxed_base = [layer >= 0.5 for layer in float_layers]
        if not any(np.any(layer) for layer in boxed_base):
            # Heavily squeezed thin strokes sink below 0.5 coverage; a
            # lower binarization keeps the candidate set non-empty and the
            # court still judges the result.
            boxed_base = [layer >= 0.30 for layer in float_layers]
        if not any(np.any(layer) for layer in boxed_base):
            continue

        # Per-glyph bounded offsets: the topology-preserving warp
        # stage - each glyph keeps its own topology, only its
        # placement moves within +/-GLYPH_SHIFT_LIMIT px.
        for xscale in XSCALE_GRID:
            # Per-glyph width (audit: "per-glyph width/offset"): the
            # GT stroke widens glyphs while the height-driven global
            # factor cannot compensate width independently.
            boxed = [
                _xscale_layer(layer, xscale) for layer in boxed_base
            ]
            base = np.zeros((height, arena_width), bool)
            for layer in boxed:
                base |= layer
            if not np.any(base):
                continue
            # Global alignment onto the robust observed ink box.
            c_x0, c_x1, c_y0, c_y1 = _bbox(base)
            dx = int(round((obs_x0 + obs_x1) / 2 - (c_x0 + c_x1) / 2))
            dy = int(round((obs_y0 + obs_y1) / 2 - (c_y0 + c_y1) / 2))
            boxed = [_shift(layer, dx, dy) for layer in boxed]
            # Per-glyph CUMULATIVE offsets, left to right: each glyph
            # searches +/-GLYPH_SHIFT_LIMIT around the previous
            # glyph's correction, so a linear tracking residual
            # (0.5 px/glyph crosses 15 px over 32 glyphs) is absorbed
            # while the layout stays monotonic - the audit's
            # explicit-layout stage.
            fitted = []
            cumulative_dx = 0
            for layer in boxed:
                if not np.any(layer):
                    fitted.append(layer)
                    continue
                l_x0, l_x1, _l_y0, _l_y1 = _bbox(layer)
                best_shift = (-1.0, layer, cumulative_dx)
                for step in range(
                    -GLYPH_SHIFT_LIMIT, GLYPH_SHIFT_LIMIT + 1,
                ):
                    glyph_dx = cumulative_dx + step
                    moved = _shift(layer, glyph_dx, 0)
                    band0 = max(0, l_x0 + glyph_dx - 1)
                    band1 = min(arena_width, l_x1 + glyph_dx + 2)
                    if band1 <= band0:
                        continue
                    # Score only inside the glyph's own column band -
                    # against the full mask a glyph is pulled toward
                    # its neighbours' ink.
                    score = float(np.sum(np.minimum(
                        moved[:, band0:band1].astype(np.float32),
                        observed_float[:, band0:band1],
                    )))
                    if score > best_shift[0]:
                        best_shift = (score, moved, glyph_dx)
                fitted.append(best_shift[1])
                cumulative_dx = best_shift[2]
            composed = np.zeros((height, arena_width), bool)
            for layer in fitted:
                composed |= layer
            for stroke in STROKE_RADII:
                thick = composed
                if stroke:
                    kernel = cv2.getStructuringElement(
                        cv2.MORPH_ELLIPSE,
                        (2 * stroke + 1, 2 * stroke + 1),
                    )
                    thick = cv2.dilate(
                        composed.astype(np.uint8), kernel,
                    ) > 0
                for effect in EFFECTS:
                    consider(_apply_effect(thick, effect))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root", type=Path,
        default=ROOT / ".training_snapshots" / "wordmark_full_v4_20260723",
    )
    parser.add_argument(
        "--font-manifest", type=Path,
        default=ROOT / "fonts" / "google-fonts-manifest.json",
    )
    parser.add_argument(
        "--font-root", type=Path, default=ROOT / "fonts" / "google-fonts",
    )
    parser.add_argument("--arena", choices=("fixed", "dynamic"), default="fixed")
    parser.add_argument("--lengths", type=str, default="1,2,4,8,16,24,32")
    parser.add_argument("--samples-per-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--dump-dir", type=Path, default=None,
        help="save GT(red)/candidate(green) overlays for slot 0 of each length",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.out is None:
        args.out = (
            ROOT / "benchmarks" / "pcdc_pre_v14"
            / f"template_warp_oracle_{args.arena}_diagnostic.json"
        )

    source_root = args.source_root.resolve()
    sys.path.insert(0, str(source_root))
    from vice_compiler.wordmark_prior import (
        WORDMARK_CHARACTERS,
        WordmarkPriorConfig,
        topology_signature,
    )
    from vice_compiler.wordmark_prior_data import (
        _rng,
        degrade_wordmark,
        render_clean_wordmark,
    )
    from vice_compiler.glyph_prior_data import (
        load_font_records,
        split_font_families,
    )

    started = time.perf_counter()
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    test_fonts = split.test
    if args.arena == "fixed":
        config = WordmarkPriorConfig()
    else:
        # Height-driven letterbox: pixels per glyph no longer shrink with L.
        config = WordmarkPriorConfig(image_height=64, image_width=4096)
    config.validate()
    maximum_topology = config.topology_classes - 1
    height, width = config.image_height, config.image_width

    lengths = tuple(int(value) for value in args.lengths.split(","))
    per_length = int(args.samples_per_length)
    total = len(lengths) * per_length

    selected_match = np.zeros(total, bool)
    oracle_match = np.zeros(total, bool)
    selected_edit = np.zeros(total, np.int64)
    oracle_edit = np.zeros(total, np.int64)
    selected_iou_gt = np.zeros(total, np.float64)
    oracle_iou_gt = np.zeros(total, np.float64)
    selected_iou_observed = np.zeros(total, np.float64)
    sample_length = np.zeros(total, np.int64)
    pixels_per_glyph = np.zeros(total, np.float64)
    no_candidate: list[dict] = []

    generated = 0
    for length_index, length in enumerate(lengths):
        for slot in range(per_length):
            row = length_index * per_length + slot
            gt = None
            for retry in range(64):
                index = row + retry * total
                generator = _rng(args.seed, index)
                font = test_fonts[int(generator.integers(0, len(test_fonts)))]
                text = _sample_fixed_length_text(
                    generator, length, WORDMARK_CHARACTERS,
                )
                coverage, support = render_clean_wordmark(
                    font.path, text, config,
                    seed=args.seed + 104729 * index,
                )
                if not np.any(support):
                    continue
                components, holes = topology_signature(support)
                if components > maximum_topology or holes > maximum_topology:
                    continue
                observed = degrade_wordmark(
                    coverage, support, seed=args.seed + 130363 * index,
                )
                gt = (font, text, support, (components, holes), observed)
                break
            if gt is None:
                raise RuntimeError(
                    f"length {length} slot {slot}: resampling exhausted"
                )
            font, text, support, truth, observed = gt
            # Crop the arena to the ink neighbourhood: identical metrics, an
            # order of magnitude less work on the wide dynamic canvas.
            ink_columns = np.flatnonzero(
                (support | (observed >= 0.15)).any(axis=0)
            )
            crop0 = max(0, int(ink_columns.min()) - 40)
            crop1 = min(width, int(ink_columns.max()) + 41)
            support = support[:, crop0:crop1]
            observed = observed[:, crop0:crop1]
            arena_width = support.shape[1]
            # Score against the FLOAT observation: thin strokes and outline
            # rings sink below a 0.5 threshold under blur/gamma, and a binary
            # mask would blind both the alignment and the court.
            observed_float = np.clip(observed, 0.0, 1.0).astype(np.float32)
            observed_ink = None
            for geometry_threshold in (0.30, 0.15):
                observed_ink = _robust_ink(observed >= geometry_threshold)
                if observed_ink is not None:
                    break
            if observed_ink is None:
                observed_ink = support
            obs_x0, obs_x1, obs_y0, obs_y1 = _bbox(observed_ink)
            columns = np.flatnonzero(support.any(axis=0))
            pixels_per_glyph[row] = float(
                (columns[-1] - columns[0] + 1) / length
            )

            best_observed: tuple[float, np.ndarray | None] = (-1.0, None)
            best_gt: tuple[float, np.ndarray | None] = (-1.0, None)

            def _soft_iou(candidate: np.ndarray, reference: np.ndarray) -> float:
                candidate_float = candidate.astype(np.float32)
                return float(
                    np.sum(np.minimum(candidate_float, reference))
                    / max(1e-6, np.sum(np.maximum(candidate_float, reference)))
                )

            def _consider(candidate: np.ndarray) -> None:
                nonlocal best_observed, best_gt
                iou_observed = _soft_iou(candidate, observed_float)
                if iou_observed > best_observed[0]:
                    best_observed = (iou_observed, candidate)
                iou_gt = _iou(candidate, support)
                if iou_gt > best_gt[0]:
                    best_gt = (iou_gt, candidate)

            fitted_any = fit_template_line(
                str(font.path), text, observed_float,
                (obs_x0, obs_x1, obs_y0, obs_y1), _consider,
            )
            if not fitted_any or best_observed[1] is None:
                # Fail-closed accounting: the sample stays in its bucket as
                # a topology miss with IoU 0 and is listed explicitly.
                no_candidate.append(
                    {"length": length, "slot": slot, "text": text},
                )
                print(
                    f"WARN no candidate for {text!r} (len {length})",
                    flush=True,
                )
                sample_length[row] = length
                generated += 1
                continue
            selected = best_observed[1]
            oracle = best_gt[1]
            if args.dump_dir is not None and slot < 4:
                args.dump_dir.mkdir(parents=True, exist_ok=True)
                union_columns = np.flatnonzero((support | selected).any(axis=0))
                u0, u1 = int(union_columns.min()), int(union_columns.max())
                overlay = np.zeros((height, u1 - u0 + 1, 3), np.uint8)
                overlay[..., 2] = support[:, u0:u1 + 1] * np.uint8(255)
                overlay[..., 1] = selected[:, u0:u1 + 1] * np.uint8(255)
                cv2.imwrite(
                    str(
                        args.dump_dir
                        / f"len{length:02d}_s{slot}_{args.arena}.png"
                    ),
                    cv2.resize(
                        overlay, ((u1 - u0 + 1) * 2, height * 2),
                        interpolation=cv2.INTER_NEAREST,
                    ),
                )
            selected_signature = topology_signature(selected)
            oracle_signature = topology_signature(oracle)
            if args.verbose:
                print(
                    f"len={length:2d} slot={slot} text={text!r} "
                    f"gt={truth} sel={selected_signature} "
                    f"orc={oracle_signature} "
                    f"sel_iou={_iou(selected, support):.3f} "
                    f"orc_iou={best_gt[0]:.3f}",
                    flush=True,
                )
            selected_match[row] = selected_signature == truth
            oracle_match[row] = oracle_signature == truth
            selected_edit[row] = (
                abs(selected_signature[0] - truth[0])
                + abs(selected_signature[1] - truth[1])
            )
            oracle_edit[row] = (
                abs(oracle_signature[0] - truth[0])
                + abs(oracle_signature[1] - truth[1])
            )
            selected_iou_gt[row] = _iou(selected, support)
            oracle_iou_gt[row] = best_gt[0]
            selected_iou_observed[row] = best_observed[0]
            sample_length[row] = length
            generated += 1
            if generated % 128 == 0:
                print(f"fitted {generated}/{total}", flush=True)

    def _bucket(mask: np.ndarray) -> dict[str, float]:
        return {
            "samples": int(np.sum(mask)),
            "pixels_per_glyph_mean": float(np.mean(pixels_per_glyph[mask])),
            "selected_topology_accuracy": float(np.mean(selected_match[mask])),
            "oracle_topology_accuracy": float(np.mean(oracle_match[mask])),
            "selected_topology_edit_distance": float(
                np.mean(selected_edit[mask])
            ),
            "oracle_topology_edit_distance": float(
                np.mean(oracle_edit[mask])
            ),
            "selected_iou_gt": float(np.mean(selected_iou_gt[mask])),
            "oracle_iou_gt": float(np.mean(oracle_iou_gt[mask])),
            "selected_iou_observed": float(
                np.mean(selected_iou_observed[mask])
            ),
        }

    report = {
        "schema": "vice-template-warp-oracle-diagnostic/v3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Experiment D of the 2026-07-24 external audit: oracle template "
            "+ layout/effect fit on degraded input, held-out families"
        ),
        "arena": args.arena,
        "canvas": [height, width],
        "source_root": str(source_root),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "seed": int(args.seed),
        "split_seed": int(args.split_seed),
        "lengths": list(lengths),
        "samples_per_length": per_length,
        "tracking_policy": "analytic-from-observed-width plus refine",
        "tracking_refine": list(TRACKING_REFINE),
        "xscale_grid": list(XSCALE_GRID),
        "stroke_radii": list(STROKE_RADII),
        "glyph_shift_limit": GLYPH_SHIFT_LIMIT,
        "effects": list(EFFECTS),
        "overall": _bucket(np.ones(total, bool)),
        "per_length": {
            str(length): _bucket(sample_length == length) for length in lengths
        },
        "no_candidate_samples": no_candidate,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({
        "arena": args.arena,
        "overall": report["overall"],
        "per_length": {
            key: {
                "ppg": round(value["pixels_per_glyph_mean"], 1),
                "sel_topo": round(value["selected_topology_accuracy"], 4),
                "orc_topo": round(value["oracle_topology_accuracy"], 4),
                "sel_iou_gt": round(value["selected_iou_gt"], 4),
            }
            for key, value in report["per_length"].items()
        },
    }, indent=2))
    print(f"report written to {args.out}")


if __name__ == "__main__":
    main()
