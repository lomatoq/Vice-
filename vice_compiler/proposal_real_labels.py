"""Typed ProposalNet labels for the Real Locus Corpus.

The Phase-0 ``semantic_class`` is a corpus sampling bucket, not necessarily a
ProposalNet query family.  In particular, the historical ``diagrams`` bucket
contains filled arrows, badges and overlapping solids, while the
``transparency`` bucket describes the encoded canvas and not automatically a
layer relation.  Treating those bucket names as model labels creates false
domain-gap failures and, worse, would fine-tune the wrong head.

This module keeps the two contracts separate.  A reviewed locus participates
in ProposalNet training/evaluation only when it has an explicit
``proposal_family``.  A small owned-SVG subset can be migrated automatically
when its provenance makes the family objective; everything else remains
untyped until a human reviews the model-facing family.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"

PROPOSAL_FAMILIES = (
    "text_line",
    "whole_shape",
    "stroke_network",
    "layer_relation",
    "appearance_model",
    "symmetry_repeat_group",
    "risk_hard_negative",
)

FAMILY_TO_EVALUATION_CLASS = {
    "text_line": "text",
    "whole_shape": "small_shape",
    "stroke_network": "stroke_diagram",
    "layer_relation": "layer_knockout",
    "appearance_model": "gradient",
    "symmetry_repeat_group": "symmetry_repeat_group",
    "risk_hard_negative": "codec_detail",
}

_ACCEPTED_REVIEW_STATUS = frozenset({
    "ground_truth_derived", "evidence_reviewed", "complete",
})


def reviewed_proposal_family(review: dict[str, Any]) -> str | None:
    """Return a valid explicit family; never infer from a sampling bucket."""

    family = str(review.get("proposal_family", "")).strip()
    return family if family in PROPOSAL_FAMILIES else None


def infer_owned_proposal_family(
    locus: dict[str, Any], review: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Infer only families proved by owned-source provenance.

    Codec/detail is intentionally excluded: the current review support is the
    clean design support, whereas ``risk_hard_negative`` requires a residual
    artifact locus.  Human-reviewed raster-only rows are also excluded because
    accepting a mask does not prove its model-facing family.
    """

    if review.get("status") != "ground_truth_derived":
        return None, None
    source_asset_value = locus.get("source", {}).get("source_asset")
    if not source_asset_value:
        return None, None
    source_asset = Path(str(source_asset_value))
    if source_asset.suffix.lower() != ".svg" or not source_asset.is_file():
        return None, None

    semantic_class = str(locus.get("semantic_class", ""))
    if semantic_class == "text":
        return "text_line", "owned-svg-text-locus/v1"
    if semantic_class == "small_shape":
        return "whole_shape", "owned-svg-shape-locus/v1"
    if semantic_class == "gradient":
        return "appearance_model", "owned-svg-appearance-locus/v1"
    if semantic_class == "layer_knockout":
        return "layer_relation", "owned-svg-mask-clip-locus/v1"
    if semantic_class == "stroke_diagram":
        generator_family = source_asset.parent.name.lower()
        if generator_family == "overlap":
            return "layer_relation", "owned-svg-generator-family:overlap/v1"
        if generator_family in {"arrow", "badge", "monogram-frame"}:
            return "whole_shape", (
                f"owned-svg-generator-family:{generator_family}/v1"
            )
    return None, None


def audit_and_migrate(
    corpus_dir: Path = DEFAULT_CORPUS, *, write: bool = False,
) -> dict[str, Any]:
    manifest_path = corpus_dir / "manifest.json"
    review_path = corpus_dir / "review.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    review_payload = json.loads(review_path.read_text("utf-8"))
    reviews = review_payload.get("reviews", {})
    rows_by_id = {row["id"]: row for row in manifest["loci"]}

    explicit_before = Counter()
    inferred = Counter()
    unresolved = Counter()
    changed = 0
    for locus_id, review in reviews.items():
        if review.get("status") not in _ACCEPTED_REVIEW_STATUS:
            continue
        existing = reviewed_proposal_family(review)
        if existing is not None:
            explicit_before[existing] += 1
            continue
        locus = rows_by_id.get(locus_id)
        if locus is None:
            unresolved["missing_manifest_row"] += 1
            continue
        family, provenance = infer_owned_proposal_family(locus, review)
        if family is None:
            unresolved[str(locus.get("semantic_class", "unknown"))] += 1
            continue
        inferred[family] += 1
        if write:
            review["proposal_family"] = family
            review["proposal_family_provenance"] = provenance
            changed += 1

    if write and changed:
        review_payload["proposal_family_migration"] = {
            "schema": "pcdc-real-proposal-family-migration/v1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "changed": changed,
            "policy": "objective-owned-svg-provenance-only",
        }
        temporary = review_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n",
            "utf-8",
        )
        temporary.replace(review_path)

    return {
        "schema": "pcdc-real-proposal-family-audit/v1",
        "corpus": str(corpus_dir.resolve()),
        "write": bool(write),
        "changed": changed,
        "explicit_before": dict(sorted(explicit_before.items())),
        "objectively_inferable": dict(sorted(inferred.items())),
        "unresolved_by_sampling_bucket": dict(sorted(unresolved.items())),
        "typed_after": sum(explicit_before.values()) + sum(inferred.values()),
        "accepted_review_rows": sum(
            review.get("status") in _ACCEPTED_REVIEW_STATUS
            for review in reviews.values()
        ),
        "warning": (
            "semantic_class/macro_family are sampling and Phase-0 annotation "
            "fields; they are forbidden as implicit ProposalNet labels"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit_and_migrate(args.corpus, write=args.write)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
