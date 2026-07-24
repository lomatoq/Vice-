"""Experiment F: approximate-template retrieval lane (v9.5 without oracles).

The oracle-font assumption of Experiment D is replaced by style retrieval:
the degraded line's cheap style features (stroke width, contrast, slant,
density) query the descriptor bank built by build_font_style_descriptors.py,
the top-K faces are fitted with the same v9.5 cascade (fit_template_line from
diagnose_template_warp_oracle), and the union candidate set is scored.

--exclude-gt-family answers the honest question: what does the lane deliver
when the true font is NOT in the bank (custom/unseen lettering)?
Without the flag it also reports how often retrieval finds the true face.

Known v0 bias, recorded deliberately: blur inflates the query stroke width,
pulling retrieval toward heavier faces. The production lane estimates the
image-formation posterior first (audit S4.5); this diagnostic does not.

Usage:
  C:\\Python312\\python.exe diagnose_template_warp_retrieval.py --top-k 8
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent

from diagnose_template_warp_oracle import (  # noqa: E402
    _bbox,
    _iou,
    _robust_ink,
    _sample_fixed_length_text,
    fit_template_line,
)

QUERY_FEATURES = ("stroke_width_norm", "stroke_contrast", "slant", "density")
CAP_FROM_INK_HEIGHT = 0.85  # ink box spans cap+descender; cap is ~85% of it


def query_features(observed: np.ndarray) -> dict[str, float] | None:
    ink = _robust_ink(observed >= 0.30)
    if ink is None:
        ink = _robust_ink(observed >= 0.15)
    if ink is None:
        return None
    x0, x1, y0, y1 = _bbox(ink)
    ink_height = float(y1 - y0 + 1)
    cap_proxy = max(4.0, CAP_FROM_INK_HEIGHT * ink_height)
    mask = ink.astype(np.uint8)
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    ink_distance = distance[mask > 0]
    moments = cv2.moments(mask, binaryImage=True)
    slant = (
        moments["mu11"] / moments["mu02"] if moments["mu02"] > 1e-6 else 0.0
    )
    box_area = float((x1 - x0 + 1) * (y1 - y0 + 1))
    return {
        "stroke_width_norm": float(2.0 * np.median(ink_distance) / cap_proxy),
        "stroke_contrast": float(
            np.percentile(ink_distance, 90)
            / max(0.5, np.percentile(ink_distance, 10))
        ),
        "slant": float(slant),
        "density": float(mask.sum() / max(1.0, box_area)),
    }


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
    parser.add_argument("--exclude-gt-family", action="store_true")
    parser.add_argument("--lengths", type=str, default="1,2,4,8,16,24,32")
    parser.add_argument("--samples-per-length", type=int, default=48)
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.out is None:
        mode = "unseenfont" if args.exclude_gt_family else "openbank"
        args.out = (
            ROOT / "benchmarks" / "pcdc_pre_v14"
            / f"template_warp_retrieval_{mode}_k{args.top_k}.json"
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
    gt_face_retrieved = np.zeros(total, bool)
    sample_length = np.zeros(total, np.int64)

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
            ink_columns = np.flatnonzero(
                (support | (observed >= 0.15)).any(axis=0)
            )
            crop0 = max(0, int(ink_columns.min()) - 40)
            crop1 = min(width, int(ink_columns.max()) + 41)
            support = support[:, crop0:crop1]
            observed = observed[:, crop0:crop1]
            observed_float = np.clip(observed, 0.0, 1.0).astype(np.float32)
            observed_ink = None
            for geometry_threshold in (0.30, 0.15):
                observed_ink = _robust_ink(observed >= geometry_threshold)
                if observed_ink is not None:
                    break
            if observed_ink is None:
                observed_ink = support
            observed_bbox = _bbox(observed_ink)

            query = query_features(observed_float)
            if query is None:
                raise RuntimeError(f"no queryable ink for {text!r}")
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

            best_observed: tuple[float, np.ndarray | None] = (-1.0, None)
            best_gt: tuple[float, np.ndarray | None] = (-1.0, None)

            def _soft_iou(candidate: np.ndarray) -> float:
                candidate_float = candidate.astype(np.float32)
                return float(
                    np.sum(np.minimum(candidate_float, observed_float))
                    / max(
                        1e-6,
                        np.sum(np.maximum(candidate_float, observed_float)),
                    )
                )

            def _consider(candidate: np.ndarray) -> None:
                nonlocal best_observed, best_gt
                iou_observed = _soft_iou(candidate)
                if iou_observed > best_observed[0]:
                    best_observed = (iou_observed, candidate)
                iou_gt = _iou(candidate, support)
                if iou_gt > best_gt[0]:
                    best_gt = (iou_gt, candidate)

            fitted_any = False
            for key in retrieved:
                face_path = str(ROOT / faces[key]["path"])
                fitted_any |= fit_template_line(
                    face_path, text, observed_float, observed_bbox, _consider,
                )
            if not fitted_any or best_observed[1] is None:
                raise RuntimeError(f"no candidate produced for {text!r}")

            selected_signature = topology_signature(best_observed[1])
            oracle_signature = topology_signature(best_gt[1])
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
            selected_iou_gt[row] = _iou(best_observed[1], support)
            oracle_iou_gt[row] = best_gt[0]
            sample_length[row] = length
            generated += 1
            if generated % 32 == 0:
                print(f"fitted {generated}/{total}", flush=True)

    def _bucket(mask: np.ndarray) -> dict[str, float]:
        return {
            "samples": int(np.sum(mask)),
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
            "gt_face_retrieved_rate": float(np.mean(gt_face_retrieved[mask])),
        }

    report = {
        "schema": "vice-template-warp-retrieval-diagnostic/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Experiment F: approximate style retrieval + v9.5 fit cascade "
            "on degraded input, held-out families, dynamic arena"
        ),
        "top_k": int(args.top_k),
        "exclude_gt_family": bool(args.exclude_gt_family),
        "query_features": list(QUERY_FEATURES),
        "descriptor_bank_sha256": bank["font_manifest_sha256"],
        "source_root": str(source_root),
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
