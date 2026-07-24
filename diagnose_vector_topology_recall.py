"""Vector-level candidate topology Recall@K for the template lane.

The audit's proposal-model gate (S15.1) asks for topology Recall@K of the
candidate GENERATOR, not top-1 raster accuracy. At the vector level a
template-line candidate's topology is compositional by construction:

    line topology = sum of per-glyph template topologies
    (non-touching placements; explicit operators change it analytically)

so the decisive question needs no raster fitting at all: does the top-K
style shortlist contain a face whose per-glyph topology composition equals
the ground-truth line topology?

Protocol details:

- GT truth is re-rendered at 4x height (256 px) with the SAME seed - the
  tracking/stroke draws replay identically - so hairline collapse of the
  64 px arena does not contaminate the target topology. Touching glyphs
  (negative tracking) are therefore included in the truth.
- Samples whose GT took a connected/outline raster effect are excluded by
  replaying the generator (those operators are 64px-resolution-defined by
  construction and belong to the operator-classification task, not to
  retrieval Recall).
- Per-glyph face topologies come from 256 px single-glyph renders, cached.
- Candidates assume non-touching placement (the vector lane enforces
  non-touching unless a join operator is chosen), so candidate line
  topology is the plain per-glyph sum.

Usage:
  C:\\Python312\\python.exe diagnose_vector_topology_recall.py [--exclude-gt-family]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

from diagnose_template_warp_oracle import (  # noqa: E402
    _render_glyph_layers,
    _sample_fixed_length_text,
)

COMPOSITION_TRACKINGS = (-0.10, 0.0, 0.10)
COMPOSITION_STROKES = (0, 2, 4)  # render-res dilation radii (shared stroke)
from diagnose_template_warp_retrieval import (  # noqa: E402
    QUERY_FEATURES,
    query_features,
)

GLYPH_RENDER_SIZE = 256


@lru_cache(maxsize=100000)
def _glyph_topology(font_path: str, character: str) -> tuple[int, int] | None:
    """(components, holes) of one glyph at 256 px - the analytic template
    topology for retrieval purposes."""
    try:
        font = ImageFont.truetype(font_path, GLYPH_RENDER_SIZE)
    except OSError:
        return None
    bounds = font.getbbox(character)
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return None
    pad = 8
    canvas = Image.new(
        "L",
        (bounds[2] - bounds[0] + 2 * pad, bounds[3] - bounds[1] + 2 * pad),
        0,
    )
    ImageDraw.Draw(canvas).text(
        (pad - bounds[0], pad - bounds[1]), character, font=font, fill=255,
    )
    mask = (np.asarray(canvas, np.uint8) >= 128).astype(np.uint8)
    if not mask.any():
        return None
    components = int(cv2.connectedComponents(mask, connectivity=8)[0]) - 1
    inverted = np.pad(1 - mask, 1, constant_values=1)
    holes = int(cv2.connectedComponents(inverted, connectivity=4)[0]) - 2
    return components, max(0, holes)


def _mask_topology(mask: np.ndarray) -> tuple[int, int]:
    binary = mask.astype(np.uint8)
    components = int(cv2.connectedComponents(binary, connectivity=8)[0]) - 1
    inverted = np.pad(1 - binary, 1, constant_values=1)
    holes = int(cv2.connectedComponents(inverted, connectivity=4)[0]) - 2
    return components, max(0, holes)


def _composed_topologies(
    font_path: str, text: str,
) -> set[tuple[int, int]] | None:
    """Candidate topology SET under explicit pair-interaction operators.

    The audit's S8.11: adjacent glyphs may be separate, touching (tracking)
    or joined by a shared stroke. Each (tracking, stroke) variant is one
    explicit operator choice; the composed line topology is measured on the
    actual composition, not assumed to be the glyph sum.
    """
    variants: set[tuple[int, int]] = set()
    for tracking in COMPOSITION_TRACKINGS:
        rendered = _render_glyph_layers(font_path, text, tracking)
        if rendered is None:
            continue
        joint = rendered[0] >= 128
        for stroke in COMPOSITION_STROKES:
            mask = joint
            if stroke:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (2 * stroke + 1, 2 * stroke + 1),
                )
                mask = cv2.dilate(joint.astype(np.uint8), kernel) > 0
            variants.add(_mask_topology(mask))
    return variants or None


def _line_topology_from_glyphs(
    font_path: str, text: str,
) -> tuple[int, int] | None:
    components = holes = 0
    for character in text:
        if character == " ":
            continue
        glyph = _glyph_topology(font_path, character)
        if glyph is None:
            return None
        components += glyph[0]
        holes += glyph[1]
    if components == 0:
        return None
    return components, holes


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
    parser.add_argument(
        "--descriptors", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "font_style_descriptors.json",
    )
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--composition", choices=("sum", "composed"), default="sum",
        help="sum = naive per-glyph topology sum; composed = measure the "
        "composed line under explicit pair-interaction operators (S8.11: "
        "tracking x shared-stroke variants)",
    )
    parser.add_argument("--exclude-gt-family", action="store_true")
    parser.add_argument("--lengths", type=str, default="1,2,4,8,16,24,32")
    parser.add_argument("--samples-per-length", type=int, default=192)
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.out is None:
        mode = "unseenfont" if args.exclude_gt_family else "openbank"
        suffix = "" if args.composition == "sum" else "_composed"
        args.out = (
            ROOT / "benchmarks" / "pcdc_pre_v14"
            / f"vector_topology_recall_{mode}{suffix}_k{args.top_k}.json"
        )

    source_root = args.source_root.resolve()
    sys.path.insert(0, str(source_root))
    from vice_compiler.wordmark_prior import (
        WORDMARK_CHARACTERS,
        WordmarkPriorConfig,
        topology_signature,
    )
    from vice_compiler.wordmark_prior_data import (
        CONNECTED_WORDMARK_FRACTION,
        OUTLINE_WORDMARK_FRACTION,
        _rng,
        degrade_wordmark,
        render_clean_wordmark,
    )
    from vice_compiler.glyph_prior_data import (
        load_font_records,
        split_font_families,
    )

    started = time.perf_counter()
    bank = json.loads(args.descriptors.read_text(encoding="utf-8"))
    normalization = bank["normalization"]
    faces = bank["faces"]
    face_keys = list(faces)
    matrix = np.array([
        [
            (faces[key]["features"][name] - normalization[name]["mean"])
            / normalization[name]["std"]
            for name in QUERY_FEATURES
        ]
        for key in face_keys
    ])

    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    if bank["font_manifest_sha256"] != str(manifest["content_sha256"]):
        raise RuntimeError("descriptor bank is stale for this font manifest")
    split = split_font_families(fonts, seed=args.split_seed)
    test_fonts = split.test
    effect_fraction = CONNECTED_WORDMARK_FRACTION + OUTLINE_WORDMARK_FRACTION
    # 64 px arena for the degraded observation the query sees; 256 px config
    # for the topology truth.
    query_config = WordmarkPriorConfig(image_height=64, image_width=4096)
    query_config.validate()
    truth_config = WordmarkPriorConfig(image_height=256, image_width=16384)
    truth_config.validate()
    maximum_topology = query_config.topology_classes - 1

    lengths = tuple(int(value) for value in args.lengths.split(","))
    per_length = int(args.samples_per_length)
    total = len(lengths) * per_length

    recall_at = {1: np.zeros(total, bool), args.top_k: np.zeros(total, bool)}
    gt_face_retrieved = np.zeros(total, bool)
    gt_face_topology_match = np.zeros(total, bool)
    truth_is_glyph_sum = np.zeros(total, bool)
    sample_length = np.zeros(total, np.int64)
    skipped_effects = 0
    unqueryable = 0

    generated = 0
    for length_index, length in enumerate(lengths):
        for slot in range(per_length):
            row = length_index * per_length + slot
            gt = None
            for retry in range(256):
                index = row + retry * total
                generator = _rng(args.seed, index)
                font = test_fonts[int(generator.integers(0, len(test_fonts)))]
                text = _sample_fixed_length_text(
                    generator, length, WORDMARK_CHARACTERS,
                )
                # Replay the render's own generator to know whether a
                # 64px raster effect (connected/outline) was applied: the
                # sequence inside render_clean_wordmark is uniform
                # (tracking), integers (stroke), random (effect).
                replay = _rng(args.seed + 104729 * index, 0)
                replay.uniform(-0.15, 0.22)
                replay.integers(0, 100)
                if float(replay.random()) < effect_fraction:
                    skipped_effects += 1
                    continue
                coverage, support = render_clean_wordmark(
                    font.path, text, query_config,
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
                gt = (font, text, observed, index)
                break
            if gt is None:
                raise RuntimeError(
                    f"length {length} slot {slot}: resampling exhausted"
                )
            font, text, observed, index = gt
            _truth_coverage, truth_support = render_clean_wordmark(
                font.path, text, truth_config,
                seed=args.seed + 104729 * index,
            )
            truth = topology_signature(truth_support)
            glyph_sum = _line_topology_from_glyphs(str(font.path), text)
            truth_is_glyph_sum[row] = glyph_sum == truth

            query = query_features(
                np.clip(observed, 0.0, 1.0).astype(np.float32)
            )
            if query is None:
                # Degradation left only sub-4px speckles at the query
                # thresholds: retrieval has nothing to rank - an explicit
                # recall miss, not a crash.
                unqueryable += 1
                sample_length[row] = length
                generated += 1
                continue
            vector = np.array([
                (query[name] - normalization[name]["mean"])
                / normalization[name]["std"]
                for name in QUERY_FEATURES
            ])
            distances = np.linalg.norm(matrix - vector, axis=1)
            order = np.argsort(distances)
            retrieved: list[str] = []
            for position in order:
                key = face_keys[int(position)]
                if (
                    args.exclude_gt_family
                    and faces[key]["family"] == font.family
                ):
                    continue
                retrieved.append(key)
                if len(retrieved) >= args.top_k:
                    break
            gt_face_retrieved[row] = any(
                faces[key]["family"] == font.family for key in retrieved
            )
            gt_face_topology_match[row] = glyph_sum is not None and (
                glyph_sum == truth
            )

            for rank, key in enumerate(retrieved):
                face_path = str(ROOT / faces[key]["path"])
                if args.composition == "sum":
                    candidate = _line_topology_from_glyphs(face_path, text)
                    matched = candidate is not None and candidate == truth
                else:
                    variants = _composed_topologies(face_path, text)
                    matched = variants is not None and truth in variants
                if matched:
                    if rank == 0:
                        recall_at[1][row] = True
                    recall_at[args.top_k][row] = True
                    break
            sample_length[row] = length
            generated += 1
            if generated % 256 == 0:
                print(f"scored {generated}/{total}", flush=True)

    def _bucket(mask: np.ndarray) -> dict[str, float]:
        return {
            "samples": int(np.sum(mask)),
            "recall_at_1": float(np.mean(recall_at[1][mask])),
            f"recall_at_{args.top_k}": float(
                np.mean(recall_at[args.top_k][mask])
            ),
            "gt_face_retrieved_rate": float(np.mean(gt_face_retrieved[mask])),
            "gt_face_topology_equals_truth": float(
                np.mean(gt_face_topology_match[mask])
            ),
            "truth_equals_glyph_sum_rate": float(
                np.mean(truth_is_glyph_sum[mask])
            ),
        }

    report = {
        "schema": "vice-vector-topology-recall/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "S15.1 candidate topology Recall@K at the vector/construction "
            "level: does the style shortlist contain a face whose per-glyph "
            "topology composition equals the 4x-truth line topology"
        ),
        "top_k": int(args.top_k),
        "composition": args.composition,
        "composition_trackings": list(COMPOSITION_TRACKINGS),
        "composition_strokes": list(COMPOSITION_STROKES),
        "exclude_gt_family": bool(args.exclude_gt_family),
        "no_effect_samples_only": True,
        "skipped_effect_samples": int(skipped_effects),
        "unqueryable_samples": int(unqueryable),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "seed": int(args.seed),
        "split_seed": int(args.split_seed),
        "lengths": list(lengths),
        "samples_per_length": per_length,
        "overall": _bucket(np.ones(total, bool)),
        "per_length": {
            str(length): _bucket(sample_length == length) for length in lengths
        },
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({
        "mode": "unseenfont" if args.exclude_gt_family else "openbank",
        "overall": report["overall"],
    }, indent=2))
    print(f"report written to {args.out}")


if __name__ == "__main__":
    main()
