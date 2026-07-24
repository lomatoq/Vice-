"""Read-only ProposalNet evaluation on the source-disjoint real-locus corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import torch

from .experiment9_proposal_calibration import (
    CORPUS, _family_recall_at_k, _neural_entries, _prepare, _recall_at_k,
    _split_rows, _typed_reviewed_loci,
)
from .proposal_net import ProposalNet, ProposalNetConfig


PROJECT = Path(__file__).resolve().parents[1]


_REAL_GATE_SPEC = {
    "overall": ("overall", None, 0.97, 100),
    "text": ("text", "text", 0.99, 20),
    "glyph_group": ("glyph_group", "text", 0.99, 20),
    "small_shape": ("small_shape", "small_shape", 0.98, 20),
    "layer_knockout": ("layer_knockout", "layer_knockout", 0.95, 20),
    "stroke_diagram": ("stroke_diagram", "stroke_diagram", 0.98, 20),
    "gradient": ("gradient", "gradient", 0.95, 20),
    "codec_detail": ("codec_detail", "codec_detail", 0.95, 20),
}


def _real_gate_rows(
    metrics: dict, counts: dict, *, overall_count: int,
) -> dict:
    result = {}
    for gate, (metric, semantic_class, threshold, minimum) in _REAL_GATE_SPEC.items():
        instances = (
            int(overall_count) if semantic_class is None
            else int(counts.get(semantic_class, 0))
        )
        value = float(metrics.get(metric, 0.0))
        result[gate] = {
            "instances": instances, "minimum_instances": minimum,
            "threshold": threshold, "value": value,
            "passed": bool(instances >= minimum and value >= threshold),
        }
    return result


def _failure_decomposition(samples: list[dict], entries: dict) -> dict:
    """Separate missing geometry, wrong type and global-top5 ranking losses."""
    counts: dict[str, dict[str, int]] = {}
    for sample in samples:
        targets = [(sample["semantic_class"], sample["family"])]
        if sample["family"] == "text_line":
            targets.append(("glyph_group", "glyph_group"))
        ranked = sorted(
            entries[sample["id"]], key=lambda row: (-float(row[1]), row[0]),
        )
        for label, family in targets:
            row = counts.setdefault(label, {
                "instances": 0, "geometry_any_at_32": 0,
                "typed_at_32": 0, "typed_at_5": 0,
            })
            row["instances"] += 1
            row["geometry_any_at_32"] += int(any(
                float(candidate[2]) >= 0.50 for candidate in ranked[:32]
            ))
            row["typed_at_32"] += int(any(
                candidate[0] == family and float(candidate[2]) >= 0.50
                for candidate in ranked[:32]
            ))
            row["typed_at_5"] += int(any(
                candidate[0] == family and float(candidate[2]) >= 0.50
                for candidate in ranked[:5]
            ))
    result = {}
    for label, row in counts.items():
        total = max(1, row["instances"])
        result[label] = {
            **row,
            "geometry_any_recall_at_32": row["geometry_any_at_32"] / total,
            "typed_recall_at_32": row["typed_at_32"] / total,
            "typed_recall_at_5": row["typed_at_5"] / total,
        }
    return result


def evaluate(checkpoint: Path, *, device_name: str = "auto") -> dict:
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    reviews = json.loads((CORPUS / "review.json").read_text("utf-8"))["reviews"]
    loci, excluded_untyped = _typed_reviewed_loci(
        manifest["loci"], reviews,
    )
    splits = _split_rows(loci)
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    payload = torch.load(checkpoint, map_location=device, weights_only=False)
    if payload.get("schema") != "pcdc-proposal-net-checkpoint/v2-large":
        raise RuntimeError("real-locus evaluation requires a v2-large checkpoint")
    config = ProposalNetConfig(**payload["config"])
    model = ProposalNet(config).to(device)
    model.load_state_dict(payload["model"])
    support_size = (128 // 4) * int(config.mask_upsample)
    metrics = {}
    split_counts = {}
    class_counts = {}
    failure_decomposition = {}
    for split_name, rows in splits.items():
        samples = [
            _prepare(
                row, reviews[row["id"]], support_size=support_size,
            )
            for row in rows
        ]
        entries = _neural_entries(model, samples, device)
        recall = _recall_at_k(samples, entries, 5)
        recall["glyph_group"] = _family_recall_at_k(
            samples, entries, semantic_class="text",
            family="glyph_group", k=5,
        )
        metrics[split_name] = recall
        split_counts[split_name] = len(samples)
        class_counts[split_name] = {
            semantic_class: sum(
                row["semantic_class"] == semantic_class for row in samples
            )
            for semantic_class in sorted({
                row["semantic_class"] for row in samples
            })
        }
        failure_decomposition[split_name] = _failure_decomposition(
            samples, entries,
        )
    test = metrics["test"]
    gates = _real_gate_rows(
        test, class_counts["test"], overall_count=split_counts["test"],
    )
    return {
        "schema": "pcdc-proposal-real-locus-evaluation/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "device": str(device),
        "config": payload["config"],
        "split_policy": "source-asset-family-disjoint",
        "typed_annotation_contract": (
            "explicit review.proposal_family; corpus semantic_class is never "
            "used as an implicit model label"
        ),
        "excluded_untyped_count": len(excluded_untyped),
        "excluded_untyped_loci": excluded_untyped,
        "split_counts": split_counts,
        "class_counts": class_counts,
        "global_neural_only_recall_at_5_iou50": metrics,
        "failure_decomposition": failure_decomposition,
        "test_gates": gates,
        "gate_pass": all(row["passed"] for row in gates.values()),
        "promotion_rights": (
            "diagnostic-only; every typed real slice and sample floor must "
            "pass, while conformal and downstream gates remain separate"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = evaluate(args.checkpoint, device_name=args.device)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
