"""Compare complete corner pipelines, including post-detection removal.

Unlike :mod:`compare_corner_detectors`, this evaluator does not stop at the raw
CNN/RF mask.  It calls ``geometry_vectorizer.paper_corner_positions`` and maps
the surviving corner positions back to event-level predictions.  This makes it
suitable for measuring whether recentering, collapse, and iterated removal erase
detector gains.

Examples
--------
Quick smoke run::

    python compare_corner_pipeline.py --limit 24

Full held-out comparison with an explicit checkpoint::

    python compare_corner_pipeline.py \
      --dataset datasets/corner_gt_v4_perceptual_events \
      --splits val,test \
      --model models/corner_cnn_hybrid_large_v1.pt \
      --threshold 0.36 \
      --out test_runs/corner_pipeline_v4.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

import numpy as np

import compare_corner_detectors
import corner_cnn
import geometry_vectorizer


POLICIES = ("production", "tiny-safe", "cnn-conservative")


def _parse_policies(value: str) -> list[str]:
    """Return a stable, duplicate-free list of supported pipeline policies."""
    policies: list[str] = []
    for raw in value.split(","):
        policy = raw.strip()
        if not policy:
            continue
        if policy not in POLICIES:
            raise ValueError(
                f"unknown policy {policy!r}; choose from {', '.join(POLICIES)}")
        if policy not in policies:
            policies.append(policy)
    if not policies:
        raise ValueError("at least one postprocess policy is required")
    return policies


def _positions_to_mask(loop: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Map native/resampled output positions to the nearest input vertices."""
    loop = np.asarray(loop, dtype=float)
    out = np.zeros(len(loop), dtype=bool)
    if len(loop) == 0 or positions is None or len(positions) == 0:
        return out
    positions = np.asarray(positions, dtype=float).reshape(-1, 2)
    # A pipeline can return resampled coordinates for the RF path.  Event matching
    # is vertex-based, so deterministically snap each position to its nearest input
    # vertex.  Duplicate snaps intentionally collapse to one prediction.
    for position in positions:
        index = int(np.argmin(np.sum((loop - position) ** 2, axis=1)))
        out[index] = True
    return out


def _pipeline_detector(policy: str, detector: str) -> Callable[[np.ndarray], np.ndarray]:
    def predict(loop: np.ndarray) -> np.ndarray:
        positions = geometry_vectorizer.paper_corner_positions(
            loop, detector=detector, postprocess_policy=policy)
        return _positions_to_mask(loop, positions)

    return predict


@contextmanager
def _cnn_overrides(model: Path | None, threshold: float | None) -> Iterator[None]:
    """Temporarily route both CNN branches through optional A/B overrides."""
    old_small_model = corner_cnn.CNN_PATH
    old_large_model = geometry_vectorizer._CNN_HYBRID_MODEL_PATH
    old_small_threshold = geometry_vectorizer._CNN_LAX_THRESHOLD
    old_large_threshold = geometry_vectorizer._CNN_HYBRID_THRESHOLD
    try:
        if model is not None:
            resolved = model.resolve()
            # The hybrid dispatcher otherwise sends small loops to CNN_PATH and
            # normal loops to _CNN_HYBRID_MODEL_PATH.  Override both so --model
            # has the unsurprising meaning "evaluate only this checkpoint".
            corner_cnn.CNN_PATH = resolved
            geometry_vectorizer._CNN_HYBRID_MODEL_PATH = resolved
        if threshold is not None:
            geometry_vectorizer._CNN_LAX_THRESHOLD = float(threshold)
            geometry_vectorizer._CNN_HYBRID_THRESHOLD = float(threshold)
        yield
    finally:
        corner_cnn.CNN_PATH = old_small_model
        geometry_vectorizer._CNN_HYBRID_MODEL_PATH = old_large_model
        geometry_vectorizer._CNN_LAX_THRESHOLD = old_small_threshold
        geometry_vectorizer._CNN_HYBRID_THRESHOLD = old_large_threshold


@contextmanager
def _memoized_lax_detection(enabled: bool = True) -> Iterator[dict[str, int]]:
    """Reuse the identical raw detector result across policy evaluation passes.

    The policy changes only postprocessing, but ``evaluate`` intentionally owns a
    complete dataset pass.  Memoizing the internal lax detector preserves that
    simple, battle-tested event matcher without paying for CNN inference three
    times.  A fresh list is returned because downstream code may mutate it.
    """
    stats = {"hits": 0, "misses": 0}
    if not enabled:
        yield stats
        return

    original = geometry_vectorizer._detect_lax_corners
    cache: dict[tuple, tuple[int, ...]] = {}

    def cached(work: np.ndarray, work_res: float, model, s: int,
               detector: str = "cnn") -> list[int]:
        contiguous = np.ascontiguousarray(work)
        digest = hashlib.blake2b(contiguous.view(np.uint8), digest_size=16).digest()
        key = (detector, contiguous.shape, contiguous.dtype.str,
               round(float(work_res), 9), digest)
        if key not in cache:
            cache[key] = tuple(original(work, work_res, model, s, detector=detector))
            stats["misses"] += 1
        else:
            stats["hits"] += 1
        return list(cache[key])

    geometry_vectorizer._detect_lax_corners = cached
    try:
        yield stats
    finally:
        geometry_vectorizer._detect_lax_corners = original


def _with_explicit_sections(raw: dict) -> dict:
    """Make the JSON schema explicit while retaining event-matcher semantics.

    False positives do not have a ground-truth event kind, so ``by_kind`` is
    necessarily recall-only.  This is stated in the report instead of assigning
    an arbitrary kind to false positives.
    """
    overall_keys = (
        "P", "R", "F1", "tp_events", "fp_predictions", "fn_events",
        "loops", "fp_per_loop",
    )
    by_resolution = {}
    for resolution, row in raw.get("by_resolution", {}).items():
        precision = float(row.get("P", 0.0))
        recall = float(row.get("R", 0.0))
        enriched = dict(row)
        enriched["F1"] = round(
            2.0 * precision * recall / max(1e-12, precision + recall), 4)
        by_resolution[resolution] = enriched
    return {
        "overall": {key: raw[key] for key in overall_keys if key in raw},
        "by_resolution": by_resolution,
        "by_kind": {
            kind: {"R": recall}
            for kind, recall in raw.get("recall_by_kind", {}).items()
        },
        "by_family": raw.get("by_family", {}),
        "zero_event": raw.get("zero_event", {}),
    }


def build_report(dataset: Path, splits: set[str], policies: list[str],
                 detector: str, tolerance: float, limit: int,
                 model: Path | None = None, threshold: float | None = None,
                 cache_detection: bool = True) -> dict:
    results: dict[str, dict] = {}
    with _cnn_overrides(model, threshold):
        effective_cnn = {
            "small_model": str(Path(corner_cnn.CNN_PATH).resolve()),
            "large_model": str(Path(geometry_vectorizer._CNN_HYBRID_MODEL_PATH).resolve()),
            "small_threshold": geometry_vectorizer._CNN_LAX_THRESHOLD,
            "large_threshold": geometry_vectorizer._CNN_HYBRID_THRESHOLD,
        }
        with _memoized_lax_detection(cache_detection) as cache_stats:
            for policy in policies:
                raw = compare_corner_detectors.evaluate(
                    dataset,
                    _pipeline_detector(policy, detector),
                    splits,
                    tolerance,
                    limit,
                )
                results[policy] = _with_explicit_sections(raw)
                overall = results[policy]["overall"]
                print(
                    f"{policy}: P={overall['P']:.4f} R={overall['R']:.4f} "
                    f"F1={overall['F1']:.4f} loops={overall['loops']}",
                    file=sys.stderr,
                    flush=True,
                )
    return {
        "schema_version": 1,
        "dataset": str(dataset.resolve()),
        "splits": sorted(splits),
        "config": {
            "detector": detector,
            "postprocess_policies": policies,
            "tolerance_px": tolerance,
            "limit": limit,
            "model_override": str(model.resolve()) if model is not None else None,
            "threshold_override": threshold,
            "effective_cnn": effective_cnn if detector == "cnn" else None,
            "raw_detection_cache": bool(cache_detection),
            "raw_detection_cache_stats": cache_stats,
        },
        "metric_notes": {
            "matching": "one prediction per perceptual event within tolerance_px",
            "short_span": "a 1-2px labelled span is one event, not two vertices",
            "by_kind": "recall-only because false positives have no ground-truth kind",
            "zero_event": "false positives measured on loops containing no labelled events",
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path,
        default=Path("datasets/corner_gt_v4_perceptual_events"))
    parser.add_argument("--splits", default="val,test")
    parser.add_argument(
        "--policies", default=",".join(POLICIES),
        help=f"comma-separated subset of: {', '.join(POLICIES)}")
    parser.add_argument("--detector", choices=("cnn", "perres-paper"), default="cnn")
    parser.add_argument("--tolerance", type=float, default=3.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--model", type=Path, default=None,
        help="route both small/large CNN branches through this checkpoint")
    parser.add_argument(
        "--threshold", type=float, default=None,
        help="override both small/large CNN probability thresholds")
    parser.add_argument("--no-detection-cache", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    try:
        policies = _parse_policies(args.policies)
    except ValueError as error:
        parser.error(str(error))
    splits = {item.strip() for item in args.splits.split(",") if item.strip()}
    if not splits:
        parser.error("--splits must contain at least one split")
    if not args.dataset.is_dir():
        parser.error(f"dataset directory does not exist: {args.dataset}")
    if args.model is not None and not args.model.is_file():
        parser.error(f"model checkpoint does not exist: {args.model}")
    if args.detector != "cnn" and (args.model is not None or args.threshold is not None):
        parser.error("--model/--threshold apply only to --detector cnn")
    if args.threshold is not None and not 0.0 <= args.threshold <= 1.0:
        parser.error("--threshold must be in [0, 1]")
    if args.tolerance < 0.0:
        parser.error("--tolerance must be non-negative")
    if args.limit < 0:
        parser.error("--limit must be non-negative")

    report = build_report(
        args.dataset,
        splits,
        policies,
        args.detector,
        args.tolerance,
        args.limit,
        model=args.model,
        threshold=args.threshold,
        cache_detection=not args.no_detection_cache,
    )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
