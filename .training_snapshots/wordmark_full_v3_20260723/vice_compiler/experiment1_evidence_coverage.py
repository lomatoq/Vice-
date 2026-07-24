"""Foundational Experiment 1: Evidence-Lattice Coverage.

Only human reviews or independently aligned owned-SVG ground truth are
admissible. Pending machine suggestions are reported as a blocker and never
converted into positive labels. Candidate preference is required later, when
real candidates exist, but it is not fabricated for the evidence-only gate.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
from typing import Any

import cv2
import numpy as np

from .build_identity import bind_report
from .experiment_inputs import real_locus_input_identity

from .evidence_ir import EvidenceCache, RasterEvidenceIR


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment1" / "report.json"
FAMILY_MAP = {
    "text": {"text"},
    "small_shape": {"shape", "component", "symmetry"},
    "layer_knockout": {"layer", "component"},
    "stroke_diagram": {"stroke"},
    "gradient": {"gradient"},
    "codec_detail": {"codec_detail", "component"},
}


def decode_support_rle(
    runs: list[list[int]], width: int, height: int
) -> np.ndarray:
    flat = np.zeros(width * height, dtype=bool)
    previous_end = 0
    for start, length in runs:
        end = int(start) + int(length)
        if start < previous_end or length <= 0 or end > flat.size:
            raise ValueError("invalid support RLE")
        flat[int(start):end] = True
        previous_end = end
    return flat.reshape((height, width))


def _token_support_mask(token: Any, shape: tuple[int, int]) -> np.ndarray | None:
    width, height = token.support_size
    count = width * height
    if token.support_bits:
        mask = np.unpackbits(
            np.frombuffer(token.support_bits, dtype=np.uint8),
            count=count,
            bitorder="little",
        ).astype(bool, copy=False).reshape((height, width))
    elif token.support_rle:
        flat = np.zeros(count, dtype=bool)
        for start, length in token.support_rle:
            flat[start:start + length] = True
        mask = flat.reshape((height, width))
    else:
        return None
    if mask.shape != shape:
        mask = cv2.resize(
            mask.astype(np.uint8),
            (shape[1], shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    return mask


def _mask_bits(mask: np.ndarray) -> int:
    packed = np.packbits(mask, axis=None, bitorder="little")
    return int.from_bytes(packed.tobytes(), "little")


def _bits_mask(bits: int, shape: tuple[int, int]) -> np.ndarray:
    byte_count = (shape[0] * shape[1] + 7) // 8
    packed = bits.to_bytes(byte_count, "little")
    return np.unpackbits(
        np.frombuffer(packed, dtype=np.uint8),
        count=shape[0] * shape[1],
        bitorder="little",
    ).astype(bool, copy=False).reshape(shape)


def _support_recall_at_k(
    reir: RasterEvidenceIR,
    support: np.ndarray,
    k_values: tuple[int, ...] = (1, 4, 8, 16, 32),
) -> tuple[dict[str, float], np.ndarray, dict[str, int]]:
    labels = reir.hierarchy.leaf_labels
    if support.shape != labels.shape:
        support_u8 = support.astype(np.uint8) * 255
        support = cv2.resize(
            support_u8, (labels.shape[1], labels.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    support_area = int(support.sum())
    if support_area <= 0:
        return (
            {str(k): 0.0 for k in k_values}, np.zeros_like(labels, dtype=bool),
            {"hierarchy_candidates": 0, "typed_macro_candidates": 0,
             "eligible_candidates": 0},
        )
    leaf_count = reir.hierarchy.leaf_count
    leaf_areas = np.bincount(labels.ravel(), minlength=leaf_count)
    support_labels = labels[support]

    hierarchy_sets: list[tuple[int, ...]] = []
    for node in reir.hierarchy.nodes:
        if node.left is None:
            hierarchy_sets.append((node.id,))
        else:
            hierarchy_sets.append(tuple(sorted(
                set(hierarchy_sets[node.left]) | set(hierarchy_sets[node.right])
            )))
    descriptors: list[tuple[str, Any]] = []
    seen_leaves: set[tuple[int, ...]] = set()
    for candidate in hierarchy_sets:
        if candidate and candidate not in seen_leaves:
            descriptors.append(("leaves", candidate))
            seen_leaves.add(candidate)
    typed_count = 0
    seen_rle: set[tuple[tuple[int, int], ...]] = set()
    seen_bits: set[bytes] = set()
    for token in reir.proposal_tokens:
        if token.support_bits and token.support_size[0] > 0:
            typed_count += 1
            if token.support_bits not in seen_bits:
                descriptors.append(("bits", token))
                seen_bits.add(token.support_bits)
        elif token.support_rle and token.support_size[0] > 0:
            typed_count += 1
            if token.support_rle not in seen_rle:
                descriptors.append(("rle", token))
                seen_rle.add(token.support_rle)
        elif token.support_leaf_ids:
            typed_count += 1
            candidate = tuple(sorted(set(token.support_leaf_ids)))
            if candidate and candidate not in seen_leaves:
                descriptors.append(("leaves", candidate))
                seen_leaves.add(candidate)

    eligible_descriptors: list[tuple[str, Any]] = []
    eligible_projections: list[np.ndarray] = []
    for kind, payload in descriptors:
        if kind == "leaves":
            leaf_ids = np.asarray(payload, dtype=np.intp)
            candidate_area = int(leaf_areas[leaf_ids].sum())
            projection = np.isin(support_labels, leaf_ids)
        elif kind == "rle":
            token = payload
            flat = np.zeros(token.support_size[0] * token.support_size[1], dtype=bool)
            for start, length in token.support_rle:
                flat[start:start + length] = True
            candidate_mask = flat.reshape(
                (token.support_size[1], token.support_size[0])
            )
            if candidate_mask.shape != labels.shape:
                candidate_mask = cv2.resize(
                    candidate_mask.astype(np.uint8),
                    (labels.shape[1], labels.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                ) > 0
            candidate_area = int(candidate_mask.sum())
            projection = candidate_mask[support]
        else:
            token = payload
            count = token.support_size[0] * token.support_size[1]
            candidate_mask = np.unpackbits(
                np.frombuffer(token.support_bits, dtype=np.uint8),
                count=count,
                bitorder="little",
            ).astype(bool, copy=False).reshape(
                (token.support_size[1], token.support_size[0])
            )
            if candidate_mask.shape != labels.shape:
                candidate_mask = cv2.resize(
                    candidate_mask.astype(np.uint8),
                    (labels.shape[1], labels.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                ) > 0
            candidate_area = int(candidate_mask.sum())
            projection = candidate_mask[support]
        intersection = int(projection.sum())
        precision = intersection / max(1, candidate_area)
        if intersection > 0 and precision >= 0.82:
            eligible_descriptors.append((kind, payload))
            eligible_projections.append(projection)
    eligible_matrix = (
        np.stack(eligible_projections, axis=0)
        if eligible_projections
        else np.zeros((0, support_area), dtype=bool)
    )

    covered = np.zeros(support_area, dtype=bool)
    used = np.zeros(len(eligible_descriptors), dtype=bool)
    chosen_by_k: dict[int, tuple[int, ...]] = {}
    selected: list[int] = []
    requested = set(k_values)
    for step in range(1, max(k_values) + 1):
        gains = np.sum(eligible_matrix & ~covered, axis=1)
        gains[used] = -1
        best = int(np.argmax(gains)) if len(gains) else -1
        if best < 0 or gains[best] <= 0:
            for k in requested:
                if k >= step and k not in chosen_by_k:
                    chosen_by_k[k] = tuple(selected)
            break
        used[best] = True
        selected.append(best)
        covered |= eligible_matrix[best]
        if step in requested:
            chosen_by_k[step] = tuple(selected)
    for k in k_values:
        chosen_by_k.setdefault(k, tuple(selected))
    results: dict[str, float] = {}
    for k in k_values:
        chosen = chosen_by_k[k]
        explained = (
            np.any(eligible_matrix[np.asarray(chosen, dtype=np.intp)], axis=0)
            if chosen else np.zeros(support_area, dtype=bool)
        )
        results[str(k)] = float(explained.mean())
    all_explained = (
        np.any(eligible_matrix, axis=0)
        if len(eligible_matrix) else np.zeros(support_area, dtype=bool)
    )
    results["all"] = float(all_explained.mean())

    chosen_mask = np.zeros_like(labels, dtype=bool)
    for selected_index in chosen_by_k[32]:
        kind, payload = eligible_descriptors[selected_index]
        if kind == "leaves":
            chosen_mask |= np.isin(labels, payload)
        elif kind == "rle":
            token = payload
            flat = np.zeros(token.support_size[0] * token.support_size[1], dtype=bool)
            for start, length in token.support_rle:
                flat[start:start + length] = True
            token_mask = flat.reshape(
                (token.support_size[1], token.support_size[0])
            )
            if token_mask.shape != labels.shape:
                token_mask = cv2.resize(
                    token_mask.astype(np.uint8),
                    (labels.shape[1], labels.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                ) > 0
            chosen_mask |= token_mask
        else:
            token = payload
            count = token.support_size[0] * token.support_size[1]
            token_mask = np.unpackbits(
                np.frombuffer(token.support_bits, dtype=np.uint8),
                count=count,
                bitorder="little",
            ).astype(bool, copy=False).reshape(
                (token.support_size[1], token.support_size[0])
            )
            if token_mask.shape != labels.shape:
                token_mask = cv2.resize(
                    token_mask.astype(np.uint8),
                    (labels.shape[1], labels.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                ) > 0
            chosen_mask |= token_mask
    diagnostics = {
        "hierarchy_candidates": len(hierarchy_sets),
        "typed_macro_candidates": typed_count,
        "unique_candidates": len(descriptors),
        "eligible_candidates": len(eligible_descriptors),
    }
    return results, chosen_mask, diagnostics


def _topology_recall(
    reir: RasterEvidenceIR,
    support: np.ndarray,
    chosen_mask: np.ndarray,
    components: int,
    holes: int,
) -> float:
    target = (components, holes)

    def signature(mask: np.ndarray) -> tuple[int, int]:
        contours, hierarchy = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )
        if hierarchy is None or not contours:
            return 0, 0
        parents = hierarchy[0, :, 3]
        return int(np.sum(parents < 0)), int(np.sum(parents >= 0))

    support_bits = _mask_bits(support)
    support_area = int(support.sum())
    candidates: list[tuple[int, int, int, float]] = []
    seen: set[int] = set()

    def admit(mask: np.ndarray) -> None:
        bits = _mask_bits(mask)
        if bits == 0 or bits in seen:
            return
        seen.add(bits)
        area = bits.bit_count()
        intersection = (bits & support_bits).bit_count()
        precision = intersection / max(1, area)
        recall = intersection / max(1, support_area)
        if precision < 0.82 or recall < 0.05:
            return
        f1 = 2.0 * precision * recall / max(1e-9, precision + recall)
        candidates.append((bits, area, intersection, f1))

    if np.any(chosen_mask):
        admit(chosen_mask)

    labels = reir.hierarchy.leaf_labels
    leaf_count = reir.hierarchy.leaf_count
    leaf_area = np.bincount(labels.ravel(), minlength=leaf_count)
    leaf_intersection = np.bincount(labels[support], minlength=leaf_count)
    hierarchy_sets: list[tuple[int, ...]] = []
    for node in reir.hierarchy.nodes:
        if node.left is None:
            leaf_ids = (node.id,)
        else:
            leaf_ids = tuple(sorted(
                set(hierarchy_sets[node.left]) | set(hierarchy_sets[node.right])
            ))
        hierarchy_sets.append(leaf_ids)
        indices = np.asarray(leaf_ids, dtype=np.intp)
        area = int(leaf_area[indices].sum())
        intersection = int(leaf_intersection[indices].sum())
        if (
            intersection / max(1, area) >= 0.82
            and intersection / max(1, support_area) >= 0.05
        ):
            admit(np.isin(labels, indices))

    for token in reir.proposal_tokens:
        mask = _token_support_mask(token, support.shape)
        if mask is not None:
            admit(mask)

    # Topology recall asks whether an admissible explanation exists, not
    # whether the single maximum-recall greedy union happens to preserve it.
    for bits, area, intersection, _f1 in candidates:
        if (
            intersection / max(1, support_area) >= 0.55
            and signature(_bits_mask(bits, support.shape)) == target
        ):
            return 1.0

    finalists = sorted(candidates, key=lambda row: -row[3])[:64]

    def union_matches(union: int) -> bool:
        intersection = (union & support_bits).bit_count()
        union_area = union.bit_count()
        return bool(
            intersection / max(1, support_area) >= 0.55
            and intersection / max(1, union_area) >= 0.82
            and signature(_bits_mask(union, support.shape)) == target
        )

    # A single greedy set-cover path can destroy a counter or join two glyphs
    # even when another equally admissible first token preserves topology.
    # Explore a bounded set of high-F1 seeds and outside-support penalties.
    # This is still an existence probe, not a candidate preference model.
    seed_indices: tuple[int | None, ...] = (
        (None,) + tuple(range(min(16, len(finalists))))
    )
    for outside_penalty in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0):
        for seed_index in seed_indices:
            union = 0
            used: set[int] = set()
            if seed_index is not None:
                union = finalists[seed_index][0]
                used.add(seed_index)
                if union_matches(union):
                    return 1.0
            for _step in range(min(32, len(finalists))):
                best_index = -1
                best_score = 0.0
                for index, (
                    bits, _area, _intersection, _f1
                ) in enumerate(finalists):
                    if index in used:
                        continue
                    new_bits = bits & ~union
                    gain = (new_bits & support_bits).bit_count()
                    outside = (new_bits & ~support_bits).bit_count()
                    score = gain - outside_penalty * outside
                    if score > best_score:
                        best_score = score
                        best_index = index
                if best_index < 0:
                    break
                used.add(best_index)
                union |= finalists[best_index][0]
                if union_matches(union):
                    return 1.0
    return 0.0


def _boundary_feasibility(reir: RasterEvidenceIR, support: np.ndarray) -> float:
    if support.shape != reir.cells.boundary_mask.shape:
        support = cv2.resize(
            support.astype(np.uint8),
            (reir.width, reir.height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    kernel = np.ones((3, 3), np.uint8)
    support_boundary = cv2.morphologyEx(
        support.astype(np.uint8), cv2.MORPH_GRADIENT, kernel
    ) > 0
    count = int(support_boundary.sum())
    if count == 0:
        return 1.0
    feasible = cv2.dilate(
        reir.cells.boundary_mask.astype(np.uint8), kernel
    ) > 0
    return float(np.sum(support_boundary & feasible) / count)


def _family_recall(reir: RasterEvidenceIR, family: str) -> float:
    expected = FAMILY_MAP.get(family, {family})
    return float(any(token.family in expected for token in reir.proposal_tokens))


def evaluate_locus(
    locus: dict[str, Any], review: dict[str, Any], cache: EvidenceCache
) -> dict[str, Any]:
    width, height = review["support_size"]
    support = decode_support_rle(review["support_rle"], width, height)
    reir, cache_hit = cache.get_or_build(locus["source"]["path"])
    evaluation_support = support
    if evaluation_support.shape != (reir.height, reir.width):
        evaluation_support = cv2.resize(
            evaluation_support.astype(np.uint8),
            (reir.width, reir.height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    profile_record = next(
        row for row in reir.stage_profile["records"]
        if row["name"] == "reir_total"
    )
    recall, chosen_mask, candidate_counts = _support_recall_at_k(
        reir, evaluation_support
    )
    return {
        "id": locus["id"],
        "semantic_class": locus["semantic_class"],
        "cache_hit": cache_hit,
        "support_recall_at_k": recall,
        "topology_recall": _topology_recall(
            reir, evaluation_support, chosen_mask,
            int(review["components"]), int(review["holes"])
        ),
        "boundary_band_feasibility": _boundary_feasibility(
            reir, evaluation_support
        ),
        "macro_family_recall": _family_recall(
            reir, str(review["macro_family"])
        ),
        "hierarchy_nodes": len(reir.hierarchy.nodes),
        "proposal_tokens": len(reir.proposal_tokens),
        "coverage_candidates": candidate_counts,
        "runtime_ms": float(profile_record["wall_ms"]),
        "runtime_budget_ok": bool(profile_record["budget_ok"]),
    }


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows]
    return float(statistics.fmean(values)) if values else None


def build_report(
    corpus_dir: Path = CORPUS, *, allow_partial: bool = False
) -> dict[str, Any]:
    input_identity = real_locus_input_identity(corpus_dir)
    manifest = json.loads((corpus_dir / "manifest.json").read_text("utf-8"))
    review_payload = json.loads((corpus_dir / "review.json").read_text("utf-8"))
    reviews = review_payload.get("reviews", {})
    evidence_reviews = {
        locus_id: review for locus_id, review in reviews.items()
        if review.get("status") in {
            "ground_truth_derived", "evidence_reviewed", "complete"
        }
    }
    required = int(manifest["total"])
    if len(evidence_reviews) != required and not allow_partial:
        return {
            "schema": "pcdc-experiment1/v1",
            "input_identity": input_identity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "blocked_pending_human_review",
            "required_evidence_reviews": required,
            "observed_evidence_reviews": len(evidence_reviews),
            "missing_evidence_reviews": required - len(evidence_reviews),
            "gate_pass": False,
            "stop_rule": (
                "Do not build judge/solver; complete human acceptable-support, "
                "topology, macro-family and layer-relation reviews."
            ),
            "rows": [],
        }
    cache = EvidenceCache()
    admitted_loci = [
        locus for locus in manifest["loci"] if locus["id"] in evidence_reviews
    ]
    rows = [
        evaluate_locus(locus, evidence_reviews[locus["id"]], cache)
        for locus in admitted_loci
    ]
    by_class: dict[str, dict[str, Any]] = {}
    for semantic_class in manifest["targets"]:
        class_rows = [
            row for row in rows if row["semantic_class"] == semantic_class
        ]
        by_class[semantic_class] = {
            "n": len(class_rows),
            "support_recall_at_32": (
                statistics.fmean(
                    row["support_recall_at_k"]["32"] for row in class_rows
                ) if class_rows else None
            ),
            "topology_recall": _mean(class_rows, "topology_recall"),
            "boundary_band_feasibility": _mean(
                class_rows, "boundary_band_feasibility"
            ),
            "macro_family_recall": _mean(class_rows, "macro_family_recall"),
        }
    overall_recall = statistics.fmean(
        row["support_recall_at_k"]["32"] for row in rows
    )
    runtime_values = sorted(row["runtime_ms"] for row in rows)
    runtime_p95 = runtime_values[min(len(runtime_values) - 1, int(0.95 * len(runtime_values)))]
    class_floor = min(
        value["support_recall_at_32"] for value in by_class.values()
        if value["support_recall_at_32"] is not None
    )
    text_recall = by_class["text"]["support_recall_at_32"]
    small_shape_recall = by_class["small_shape"]["support_recall_at_32"]
    stroke_recall = by_class["stroke_diagram"]["support_recall_at_32"]
    evidence_gate = (
        overall_recall >= 0.97
        and text_recall >= 0.99
        and small_shape_recall >= 0.98
        and stroke_recall >= 0.98
        and class_floor >= 0.95
        and runtime_p95 < 300.0
    )
    complete_annotations = len(evidence_reviews) == required
    gate = complete_annotations and evidence_gate
    return {
        "schema": "pcdc-experiment1/v1",
        "input_identity": input_identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "passed" if gate
            else "provisional_partial" if not complete_annotations
            else "failed_stop"
        ),
        "gate_pass": gate,
        "would_pass_evidence_gate": evidence_gate,
        "required_evidence_reviews": required,
        "observed_evidence_reviews": len(evidence_reviews),
        "missing_evidence_reviews": required - len(evidence_reviews),
        "metrics": {
            "overall_support_recall_at_32": overall_recall,
            "class_floor": class_floor,
            "runtime_p95_ms": runtime_p95,
            "topology_recall": _mean(rows, "topology_recall"),
            "boundary_band_feasibility": _mean(
                rows, "boundary_band_feasibility"
            ),
            "macro_family_recall": _mean(rows, "macro_family_recall"),
            "mean_hierarchy_nodes": _mean(rows, "hierarchy_nodes"),
            "mean_proposal_tokens": _mean(rows, "proposal_tokens"),
            "mean_unique_coverage_candidates": float(statistics.fmean(
                row["coverage_candidates"]["unique_candidates"] for row in rows
            )),
        },
        "by_class": by_class,
        "stop_rule": (
            None if gate else "Do not build judge/solver; fix evidence/proposals."
        ),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    report = bind_report(build_report(
        args.corpus, allow_partial=args.allow_partial,
    ))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        key: report.get(key) for key in (
            "status", "gate_pass", "required_evidence_reviews",
            "observed_evidence_reviews", "missing_evidence_reviews", "metrics"
        ) if key in report
    }, ensure_ascii=False, indent=2))
    return int(not report["gate_pass"])


if __name__ == "__main__":
    raise SystemExit(main())
