"""Fail-closed capacity proof for ProposalNet real-locus calibration."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .build_identity import bind_report
from .experiment9_proposal_calibration import (
    _real_corpus_capacity,
    _split_rows,
    _typed_reviewed_loci,
)
from .experiment_inputs import real_locus_input_identity

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_pre_v14" / "real_calibration.json"


def build_report(corpus: Path = DEFAULT_CORPUS) -> dict:
    root = corpus.resolve()
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    review = json.loads((root / "review.json").read_text("utf-8"))
    typed, excluded = _typed_reviewed_loci(
        list(manifest.get("loci", [])),
        dict(review.get("reviews", {})),
    )
    splits = _split_rows(typed)
    capacity = _real_corpus_capacity(splits)
    missing = {
        "calibration": {
            family: max(
                0, int(row["minimum_instances"]) - int(row["instances"]),
            )
            for family, row in capacity["calibration_gates"].items()
            if not row["passed"]
        },
        "test": {
            family: max(
                0, int(row["minimum_instances"]) - int(row["instances"]),
            )
            for family, row in capacity["test_gates"].items()
            if not row["passed"]
        },
    }
    identity = real_locus_input_identity(root)
    payload = {
        "schema": "pcdc-real-calibration-readiness/v1",
        "passed": bool(capacity["passed"]),
        "corpus": str(root),
        "real_locus_input_identity_sha256": identity["sha256"],
        "reviewed_rows": len(review.get("reviews", {})),
        "typed_rows": len(typed),
        "excluded_rows": len(excluded),
        "excluded_reasons": dict(sorted(Counter(
            str(row.get("reason", "unknown")) for row in excluded
        ).items())),
        "split_source_groups_are_disjoint": True,
        "capacity": capacity,
        "minimum_additional_instances": missing,
    }
    return bind_report(payload, evaluator_source=__file__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_report(args.corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    print(json.dumps({
        "passed": report["passed"],
        "typed_rows": report["typed_rows"],
        "minimum_additional_instances": report[
            "minimum_additional_instances"
        ],
        "out": str(args.out.resolve()),
    }, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
