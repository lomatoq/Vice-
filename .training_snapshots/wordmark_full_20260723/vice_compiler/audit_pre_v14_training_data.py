"""Exhaustive, read-only ProposalNet supervision audit before v14 training."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .proposal_filter_cache import (
    corpus_data_contract_sha256, validate_filter_cache,
)
from .proposal_mixed_corpus import validate_mixed_corpus
from .proposal_net import HARD_NEGATIVE_TYPES, QUERY_FAMILIES, RELATION_TYPES
from .train_proposal_net_large import (
    LABEL_CONTRACT_VERSION, PairDataset, _label_contract_sha256,
    _read_pairs, _split_group, _stable_bucket, _svg_families,
)


AUDIT_SCHEMA = "pcdc-pre-v14-training-data-audit/v1"
REQUIRED_FAMILIES = frozenset(QUERY_FAMILIES[:-1])
RECALL_CAPACITY_GATES = {
    "overall": 0.97, "text_line": 0.99, "glyph_group": 0.99,
    "small_shape": 0.98, "layer_relation": 0.95,
    "stroke_network": 0.98, "appearance_model": 0.95,
    "symmetry_repeat_group": 0.95, "risk_hard_negative": 0.95,
}


def _families_for_rows(rows: list[dict], pair_root: Path) -> dict[str, tuple[str, ...]]:
    by_source: dict[tuple[str, str, str], tuple[str, ...]] = {}
    result = {}
    for row in rows:
        key = (
            str(row.get("source", "")), str(row.get("source_id", "")),
            str(row.get("target_svg", "")),
        )
        if key not in by_source:
            by_source[key] = _svg_families(row, pair_root)
        result[str(row["id"])] = by_source[key]
    return result


def _inspect_sample(sample: dict) -> dict:
    family = np.asarray(sample["family"])
    count = int(len(family))
    problems = []
    for field in (
        "support", "bbox", "topology", "relations", "relation_mask", "parameters",
        "parameter_mask", "hard_negative", "small_shape",
    ):
        if len(sample[field]) != count:
            problems.append(f"{field}:first-dimension-mismatch")
    if count <= 0:
        problems.append("no-targets")
    if count and np.any(np.sum(sample["support"], axis=(1, 2)) <= 0):
        problems.append("empty-support")
    for field in (
        "rgba", "support", "bbox", "relations", "relation_mask", "parameters",
    ):
        if not np.all(np.isfinite(sample[field])):
            problems.append(f"{field}:non-finite")
    hard_negative = np.asarray(sample["hard_negative"], np.int64)
    sentinel = len(HARD_NEGATIVE_TYPES)
    if np.any((hard_negative < 0) | (hard_negative > sentinel)):
        problems.append("hard-negative-class-out-of-range")
    class_rows = [
        HARD_NEGATIVE_TYPES[int(value)] for value in hard_negative
        if int(value) < sentinel
    ]
    relation_rows = []
    relation_negative_rows = []
    relations = np.asarray(sample["relations"], np.float32)
    relation_mask = np.asarray(sample["relation_mask"], np.float32)
    if relations.shape != relation_mask.shape or relations.shape[-1] != len(RELATION_TYPES):
        problems.append("relation-supervision-shape")
    elif (
        np.any((relations < 0.0) | (relations > 1.0))
        or np.any((relation_mask < 0.0) | (relation_mask > 1.0))
        or np.any((relations >= 0.5) & (relation_mask < 0.5))
    ):
        problems.append("relation-supervision-invalid")
    else:
        for truth, observed in zip(relations, relation_mask):
            relation_rows.extend(
                name for index, name in enumerate(RELATION_TYPES)
                if float(observed[index]) >= 0.5 and float(truth[index]) >= 0.5
            )
            relation_negative_rows.extend(
                name for index, name in enumerate(RELATION_TYPES)
                if float(observed[index]) >= 0.5 and float(truth[index]) < 0.5
            )
    parameter_supervision = np.sum(
        np.asarray(sample["parameter_mask"], np.float32) > 0.0, axis=0,
    ).astype(np.int64).tolist()
    return {
        "id": str(sample["id"]), "source_id": str(sample["source_id"]),
        "target_count": count,
        "families": [QUERY_FAMILIES[int(value)] for value in family],
        "hard_negative_classes": class_rows,
        "relation_tokens": relation_rows,
        "relation_negative_tokens": relation_negative_rows,
        "parameter_supervision": parameter_supervision,
        "small_shape_count": int(np.sum(sample["small_shape"])),
        "problems": problems,
    }


def _inspect_chunk(payload: tuple[list[dict], str, dict[str, tuple[str, ...]]]) -> dict:
    rows, root_text, families = payload
    root = Path(root_text)
    dataset = PairDataset(rows, root, families)
    family_counts: Counter[str] = Counter()
    negative_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    relation_negative_counts: Counter[str] = Counter()
    parameter_counts = np.zeros(16, np.int64)
    target_count = 0
    oracle_top5_capacity: Counter[str] = Counter()
    rows_over_top5_capacity = 0
    small_shape_count = 0
    errors = []
    for index in range(len(dataset)):
        try:
            row = _inspect_sample(dataset[index])
        except Exception as error:
            row = {
                "id": str(rows[index].get("id", index)),
                "source_id": str(rows[index].get("source_id", "")),
                "target_count": 0, "families": [],
                "hard_negative_classes": [], "relation_tokens": [],
                "relation_negative_tokens": [],
                "parameter_supervision": [0] * 16,
                "small_shape_count": 0,
                "problems": [f"{type(error).__name__}: {error}"],
            }
        target_count += int(row["target_count"])
        rows_over_top5_capacity += int(row["target_count"] > 5)
        small_shape_count += int(row["small_shape_count"])
        oracle_top5_capacity["overall"] += min(5, int(row["target_count"]))
        local_family_counts = Counter(row["families"])
        for family, count in local_family_counts.items():
            oracle_top5_capacity[family] += min(5, int(count))
        oracle_top5_capacity["small_shape"] += min(
            5, int(row["small_shape_count"]),
        )
        family_counts.update(row["families"])
        negative_counts.update(row["hard_negative_classes"])
        relation_counts.update(row["relation_tokens"])
        relation_negative_counts.update(row["relation_negative_tokens"])
        parameter_counts += np.asarray(row["parameter_supervision"], np.int64)
        if row["problems"]:
            errors.append({
                "id": row["id"], "source_id": row["source_id"],
                "problems": row["problems"],
            })
    return {
        "target_count": target_count, "family_counts": dict(family_counts),
        "negative_counts": dict(negative_counts),
        "relation_counts": dict(relation_counts),
        "relation_negative_counts": dict(relation_negative_counts),
        "parameter_counts": parameter_counts.tolist(), "errors": errors,
        "oracle_top5_capacity": dict(oracle_top5_capacity),
        "rows_over_top5_capacity": rows_over_top5_capacity,
        "small_shape_count": small_shape_count,
    }


def _degradation_families(row: dict) -> set[str]:
    augmentation = row.get("augmentation", {})
    result = set()
    if float(augmentation.get("blur_radius") or 0) > 0:
        result.add("blur")
    if float(augmentation.get("noise_sigma") or 0) > 0:
        result.add("noise")
    if augmentation.get("jpeg_quality") is not None:
        result.add("jpeg")
    if abs(float(augmentation.get("rotate_degrees") or 0)) > 0:
        result.add("rotation")
    if str(augmentation.get("background", "transparent")) != "transparent":
        result.add("background-composite")
    return result or {"clean"}


def audit_training_data(
    pair_root: Path, filter_cache: Path, *, processes: int = 4,
) -> dict:
    started = time.perf_counter()
    pair_root = pair_root.resolve()
    filter_cache = filter_cache.resolve()
    print(json.dumps({"stage": "validate-mixed-corpus"}), flush=True)
    mixed_report = validate_mixed_corpus(pair_root)
    corpus_contract = corpus_data_contract_sha256(pair_root)
    raw_rows = _read_pairs(pair_root, None)
    rows, rejected = validate_filter_cache(
        filter_cache, raw_rows,
        training_data_contract_sha256=corpus_contract,
    )
    identifiers = [str(row["id"]) for row in rows]
    duplicate_ids = len(identifiers) - len(set(identifiers))
    print(json.dumps({
        "stage": "derive-typed-families", "accepted_pairs": len(rows),
    }), flush=True)
    families = _families_for_rows(rows, pair_root)
    split_rows = {name: [] for name in ("train", "calibration", "test")}
    for row in rows:
        split_rows[_stable_bucket(_split_group(row))].append(row)
    group_sets = {
        name: {_split_group(row) for row in part}
        for name, part in split_rows.items()
    }
    group_overlap = {
        f"{first}|{second}": sorted(group_sets[first] & group_sets[second])
        for first, second in (
            ("train", "calibration"), ("train", "test"),
            ("calibration", "test"),
        )
    }

    source_counts = Counter(str(row.get("source", "")) for row in rows)
    renderer_counts = Counter(
        str(row.get("augmentation", {}).get("renderer") or "undeclared")
        for row in rows
    )
    split_renderers = {
        name: {
            str(row.get("augmentation", {}).get("renderer") or "undeclared")
            for row in part
        }
        for name, part in split_rows.items()
    }
    split_degradations = {
        name: set().union(*(
            _degradation_families(row) for row in part
        )) if part else set()
        for name, part in split_rows.items()
    }
    input_schemas = [str(row.get("schema", "")) for row in mixed_report["inputs"]]

    split_reports = {}
    errors = []
    worker_count = max(1, int(processes))
    executor = (
        ProcessPoolExecutor(max_workers=worker_count)
        if worker_count > 1 else None
    )
    try:
      for split, part in split_rows.items():
        print(json.dumps({
            "stage": "materialize-supervision", "split": split,
            "pairs": len(part), "processes": worker_count,
        }), flush=True)
        chunk_size = max(1, (len(part) + worker_count - 1) // worker_count)
        chunks = [part[start:start + chunk_size] for start in range(0, len(part), chunk_size)]
        payloads = [(
            chunk, str(pair_root),
            {str(row["id"]): families[str(row["id"])] for row in chunk},
        ) for chunk in chunks]
        chunk_reports = (
            list(executor.map(_inspect_chunk, payloads))
            if executor is not None else
            [_inspect_chunk(payload) for payload in payloads]
        )
        family_counts: Counter[str] = Counter()
        negative_counts: Counter[str] = Counter()
        relation_counts: Counter[str] = Counter()
        relation_negative_counts: Counter[str] = Counter()
        parameter_counts = np.zeros(16, np.int64)
        target_count = 0
        oracle_top5_capacity: Counter[str] = Counter()
        rows_over_top5_capacity = 0
        small_shape_count = 0
        for chunk_report in chunk_reports:
            target_count += int(chunk_report["target_count"])
            rows_over_top5_capacity += int(
                chunk_report["rows_over_top5_capacity"],
            )
            oracle_top5_capacity.update(chunk_report["oracle_top5_capacity"])
            small_shape_count += int(chunk_report["small_shape_count"])
            family_counts.update(chunk_report["family_counts"])
            negative_counts.update(chunk_report["negative_counts"])
            relation_counts.update(chunk_report["relation_counts"])
            relation_negative_counts.update(
                chunk_report["relation_negative_counts"],
            )
            parameter_counts += np.asarray(
                chunk_report["parameter_counts"], np.int64,
            )
            errors.extend({"split": split, **row} for row in chunk_report["errors"])
        measured_counts = {
            name: int(family_counts[name]) for name in QUERY_FAMILIES[:-1]
        }
        oracle_denominators = {
            "overall": target_count, "small_shape": small_shape_count,
            **measured_counts,
        }
        oracle_recall = {
            name: float(oracle_top5_capacity[name]) / max(
                1, int(oracle_denominators.get(name, 0)),
            )
            for name in RECALL_CAPACITY_GATES
        }
        split_reports[split] = {
            "pair_count": len(part), "target_count": target_count,
            "family_counts": measured_counts,
            "small_shape_count": small_shape_count,
            "rows_over_global_top5_capacity": rows_over_top5_capacity,
            "oracle_recall_at_5_capacity": oracle_recall,
            "hard_negative_counts": {
                name: int(negative_counts[name]) for name in HARD_NEGATIVE_TYPES
            },
            "relation_token_counts": {
                name: int(relation_counts[name]) for name in RELATION_TYPES
            },
            "relation_negative_token_counts": {
                name: int(relation_negative_counts[name]) for name in RELATION_TYPES
            },
            "parameter_dimension_counts": parameter_counts.tolist(),
            "all_required_families_present": all(
                family_counts[name] >= 100 for name in REQUIRED_FAMILIES
            ),
            "all_hard_negative_classes_present": all(
                negative_counts[name] >= 100 for name in HARD_NEGATIVE_TYPES
            ),
            "all_relation_tokens_present": all(
                relation_counts[name] >= 100 for name in RELATION_TYPES
            ),
            "all_relation_tokens_have_observed_negatives": all(
                relation_negative_counts[name] >= 100 for name in RELATION_TYPES
            ),
            "all_parameter_dimensions_supervised": bool(
                np.all(parameter_counts >= 100)
            ),
            "global_top5_gate_mathematically_feasible": all(
                oracle_recall[name] >= threshold
                for name, threshold in RECALL_CAPACITY_GATES.items()
            ),
        }
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    gates = {
        "mixed_corpus_attestation_valid": bool(mixed_report),
        "filter_cache_valid": True,
        "accepted_ids_unique": duplicate_ids == 0,
        "split_groups_disjoint": not any(group_overlap.values()),
        "every_row_materializes": not errors,
        "all_families_in_every_split": all(
            row["all_required_families_present"]
            for row in split_reports.values()
        ),
        "all_10_hard_negatives_in_every_split": all(
            row["all_hard_negative_classes_present"]
            for row in split_reports.values()
        ),
        "all_8_relation_tokens_have_positive_and_negative_supervision_in_every_split": all(
            row["all_relation_tokens_present"]
            and row["all_relation_tokens_have_observed_negatives"]
            for row in split_reports.values()
        ),
        "all_parameter_dimensions_in_every_split": all(
            row["all_parameter_dimensions_supervised"]
            for row in split_reports.values()
        ),
        "all_recall_at_5_gates_mathematically_feasible": all(
            row["global_top5_gate_mathematically_feasible"]
            for row in split_reports.values()
        ),
        "all_input_corpora_versioned": all(
            value and value != "unversioned" for value in input_schemas
        ),
        "all_rows_renderer_attested": "undeclared" not in renderer_counts,
        "renderer_diversity_ge_4": len([
            name for name in renderer_counts if name != "undeclared"
        ]) >= 4,
        "renderer_disjoint_holdout_exists": bool(
            split_renderers["test"] - split_renderers["train"]
        ),
        "degradation_disjoint_holdout_exists": bool(
            split_degradations["test"] - split_degradations["train"]
        ),
    }
    return {
        "schema": AUDIT_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_root": str(pair_root), "filter_cache": str(filter_cache),
        "pair_root_report_sha256": hashlib.sha256(
            (pair_root / "report.json").read_bytes()
        ).hexdigest(),
        "pairs_jsonl_sha256": hashlib.sha256(
            (pair_root / "pairs.jsonl").read_bytes()
        ).hexdigest(),
        "filter_cache_sha256": hashlib.sha256(filter_cache.read_bytes()).hexdigest(),
        "corpus_data_contract_sha256": corpus_contract,
        "label_contract_version": LABEL_CONTRACT_VERSION,
        "label_contract_sha256": _label_contract_sha256(),
        "raw_pair_count": len(raw_rows), "accepted_pair_count": len(rows),
        "rejected_pair_count": len(rejected), "duplicate_accepted_ids": duplicate_ids,
        "split_group_counts": {
            name: len(values) for name, values in group_sets.items()
        },
        "split_group_overlap": group_overlap,
        "source_counts": dict(sorted(source_counts.items())),
        "renderer_counts": dict(sorted(renderer_counts.items())),
        "input_corpus_schemas": input_schemas,
        "split_renderers": {
            name: sorted(values) for name, values in split_renderers.items()
        },
        "split_degradation_families": {
            name: sorted(values) for name, values in split_degradations.items()
        },
        "splits": split_reports,
        "error_count": len(errors), "errors": errors[:100],
        "gates": gates, "passed": all(gates.values()),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--filter-cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--processes", type=int, default=4)
    args = parser.parse_args()
    report = audit_training_data(
        args.pair_root, args.filter_cache, processes=args.processes,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "passed": report["passed"], "gates": report["gates"],
        "raw_pair_count": report["raw_pair_count"],
        "accepted_pair_count": report["accepted_pair_count"],
        "splits": report["splits"], "error_count": report["error_count"],
        "elapsed_seconds": report["elapsed_seconds"],
    }, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
