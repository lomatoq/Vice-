"""Seal a source-, renderer-, degradation-, and payload-disjoint v14 holdout."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .audit_pre_v14_training_data import _degradation_families
from .build_identity import compiler_source_sha256, evaluation_source_sha256
from .proposal_data_contract import TYPED_STRUCTURE_FAMILIES
from .proposal_filter_cache import (
    corpus_data_contract_sha256, validate_filter_cache,
)
from .proposal_mixed_corpus import validate_mixed_corpus
from .train_proposal_net_large import (
    _read_pairs, _split_group, _stable_bucket,
)


SCHEMA = "pcdc-untouched-holdout/v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _payload_hashes(
    rows: list[dict], pair_root: Path, field: str,
) -> set[str]:
    cache: dict[Path, str] = {}
    result = set()
    for row in rows:
        path = (pair_root / str(row[field])).resolve()
        if path not in cache:
            cache[path] = _sha256(path)
        result.add(cache[path])
    return result


def audit_rows(
    rows: list[dict], pair_root: Path, forbid_checkpoint: Path, *,
    minimum_holdout_rows: int = 300, minimum_family_rows: int = 80,
) -> dict:
    split_rows = {name: [] for name in ("train", "calibration", "test")}
    for row in rows:
        split_rows[_stable_bucket(_split_group(row))].append(row)
    groups = {
        name: {_split_group(row) for row in part}
        for name, part in split_rows.items()
    }
    group_overlap = (
        (groups["train"] & groups["calibration"])
        | (groups["train"] & groups["test"])
        | (groups["calibration"] & groups["test"])
    )

    renderers = {
        name: {
            str(row.get("augmentation", {}).get("renderer") or "undeclared")
            for row in part
        }
        for name, part in split_rows.items()
    }
    degradations = {
        name: set().union(*(
            _degradation_families(row) for row in part
        )) if part else set()
        for name, part in split_rows.items()
    }
    held_out_renderers = renderers["test"] - renderers["train"]
    held_out_degradations = degradations["test"] - degradations["train"]
    holdout = [
        row for row in split_rows["test"]
        if (
            str(row.get("augmentation", {}).get("renderer") or "undeclared")
            in held_out_renderers
            or bool(_degradation_families(row) & held_out_degradations)
        )
    ]
    comparison = split_rows["train"] + split_rows["calibration"]
    holdout_input_hashes = _payload_hashes(holdout, pair_root, "input_png")
    comparison_input_hashes = _payload_hashes(
        comparison, pair_root, "input_png",
    )
    holdout_target_hashes = _payload_hashes(holdout, pair_root, "target_svg")
    comparison_target_hashes = _payload_hashes(
        comparison, pair_root, "target_svg",
    )
    duplicate_input_hashes = holdout_input_hashes & comparison_input_hashes
    duplicate_target_hashes = holdout_target_hashes & comparison_target_hashes
    family_counts = Counter(
        str(row.get("macro_family_contract", {}).get("families", [""])[0])
        for row in holdout
        if row.get("macro_family_contract", {}).get("families")
    )
    family_floor_passed = all(
        family_counts[family] >= int(minimum_family_rows)
        for family in TYPED_STRUCTURE_FAMILIES
    )
    contamination_detected = bool(
        group_overlap or duplicate_input_hashes or duplicate_target_hashes
    )
    all_required_axes_disjoint = bool(
        not group_overlap
        and held_out_renderers
        and held_out_degradations
        and not duplicate_input_hashes
        and not duplicate_target_hashes
        and len(holdout) >= int(minimum_holdout_rows)
        and family_floor_passed
    )
    sealed_before_training = not forbid_checkpoint.exists()
    return {
        "sealed_before_training": sealed_before_training,
        "forbidden_checkpoint": str(forbid_checkpoint.resolve()),
        "contamination_detected": contamination_detected,
        "all_required_axes_disjoint": all_required_axes_disjoint,
        "holdout_pair_count": len(holdout),
        "minimum_holdout_pair_count": int(minimum_holdout_rows),
        "minimum_typed_family_pair_count": int(minimum_family_rows),
        "typed_family_counts": {
            family: int(family_counts[family])
            for family in sorted(TYPED_STRUCTURE_FAMILIES)
        },
        "held_out_renderers": sorted(held_out_renderers),
        "held_out_degradations": sorted(held_out_degradations),
        "split_renderers": {
            name: sorted(values) for name, values in renderers.items()
        },
        "split_degradations": {
            name: sorted(values) for name, values in degradations.items()
        },
        "split_group_counts": {
            name: len(values) for name, values in groups.items()
        },
        "group_overlap_count": len(group_overlap),
        "duplicate_input_payload_count": len(duplicate_input_hashes),
        "duplicate_target_payload_count": len(duplicate_target_hashes),
        "passed": bool(
            sealed_before_training
            and not contamination_detected
            and all_required_axes_disjoint
        ),
    }


def build_report(
    pair_root: Path, filter_cache: Path, forbid_checkpoint: Path,
) -> dict:
    pair_root = pair_root.resolve()
    filter_cache = filter_cache.resolve()
    validate_mixed_corpus(pair_root)
    corpus_contract = corpus_data_contract_sha256(pair_root)
    raw_rows = _read_pairs(pair_root, None)
    rows, rejected = validate_filter_cache(
        filter_cache, raw_rows,
        training_data_contract_sha256=corpus_contract,
    )
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_source_sha256": compiler_source_sha256(),
        "evaluation_source_sha256": evaluation_source_sha256(__file__),
        "pair_root": str(pair_root),
        "corpus_data_contract_sha256": corpus_contract,
        "filter_cache": str(filter_cache),
        "filter_cache_sha256": _sha256(filter_cache),
        "accepted_pair_count": len(rows),
        "rejected_pair_count": len(rejected),
        **audit_rows(rows, pair_root, forbid_checkpoint),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--filter-cache", type=Path, required=True)
    parser.add_argument("--forbid-checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        args.pair_root, args.filter_cache, args.forbid_checkpoint,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "passed": report["passed"],
        "holdout_pair_count": report["holdout_pair_count"],
        "held_out_renderers": report["held_out_renderers"],
        "held_out_degradations": report["held_out_degradations"],
        "out": str(args.out.resolve()),
    }, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
