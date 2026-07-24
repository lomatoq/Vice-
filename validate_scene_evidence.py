"""Held-out clean-room validation and guarded evidence-checkpoint promotion.

The candidate is compared with the deterministic production lower bound on
the dataset's validation and test splits.  Vectorizer.AI output is neither read
nor accepted by this tool.  A checkpoint is copied into the promoted slot only
when every fixed gate passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from vice_scene.evidence_model import DeterministicEvidenceModel, REQUIRED_HEADS
from vice_scene.ingest import decode_raster
from vice_scene.neural_evidence import HybridEvidenceModel
from vice_scene.raster_profile import diagnose_raster


PROBABILITY_HEADS = {
    "boundary_prob", "coverage_alpha", "corner_prob", "corner_type",
    "junction_prob", "shape_class_logits", "text_line_prob", "glyph_occupancy",
    "stroke_centerline_prob", "symmetry_evidence", "uncertainty",
}
CRITICAL_HEADS = (
    "boundary_prob", "subpixel_offset", "shape_class_logits", "text_line_prob",
    "glyph_occupancy", "stroke_centerline_prob", "stroke_half_width", "uncertainty",
)
HEAD_WEIGHTS = {
    "region_embedding": .04, "color_logits": .03, "boundary_prob": .15,
    "boundary_normal": .07, "subpixel_offset": .08, "coverage_alpha": .04,
    "corner_prob": .06, "corner_type": .02, "junction_prob": .04,
    "shape_class_logits": .10, "text_line_prob": .09, "glyph_occupancy": .09,
    "stroke_centerline_prob": .06, "stroke_half_width": .04,
    "symmetry_evidence": .04, "uncertainty": .05,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--training-dataset", type=Path,
                        help="dataset used to train the candidate; defaults to dataset")
    parser.add_argument("--out", type=Path,
                        default=Path("benchmarks/scene_evidence_validation.json"))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-per-split", type=int, default=0,
                        help="0 validates every held-out sample")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--real-ab-report", type=Path,
                        help="required passing real-image gate when --promote is used")
    parser.add_argument("--promote-to", type=Path,
                        default=Path("models/scene_evidence.promoted.pt"))
    args = parser.parse_args()

    evaluation_hash, manifest = _validate_manifest(args.dataset)
    training_dataset = args.training_dataset or args.dataset
    training_hash, _ = _validate_manifest(training_dataset)
    checkpoint_hash, metadata = _validate_checkpoint(args.candidate, training_hash)
    model = HybridEvidenceModel(args.candidate, device=args.device)
    baseline = DeterministicEvidenceModel()
    rows = {}
    failures = []
    independent_evaluation = evaluation_hash != training_hash
    if args.promote and not independent_evaluation:
        failures.append("promotion requires a manifest-disjoint evaluation dataset")
    real_ab = None
    if args.real_ab_report is not None:
        real_ab = _validate_real_ab_report(args.real_ab_report, checkpoint_hash)
    if args.promote and real_ab is None:
        failures.append("promotion requires --real-ab-report")
    elif args.promote and not real_ab.get("passed", False):
        failures.append("real-image evidence A/B gate did not pass")
    with tempfile.TemporaryDirectory(prefix="vice-evidence-validation-") as temp_name:
        temp_root = Path(temp_name)
        for split in ("validation", "test"):
            files = _split_files(args.dataset, split)
            if args.max_per_split > 0:
                files = files[:args.max_per_split]
            if not files:
                failures.append(f"missing held-out {split} samples")
                continue
            rows[split] = _evaluate_split(files, model, baseline, temp_root / split)
            failures.extend(_gate_split(split, rows[split]))

    payload = {
        "schema": "vice-scene-evidence-validation/1",
        "policy": "held-out synthetic clean-room gate; no Vectorizer.AI output",
        "evaluation_dataset_manifest_sha256": evaluation_hash,
        "evaluation_dataset_seed": manifest.get("seed"),
        "training_dataset_manifest_sha256": training_hash,
        "independent_evaluation_dataset": independent_evaluation,
        "candidate": str(args.candidate),
        "candidate_sha256": checkpoint_hash,
        "candidate_metadata": metadata,
        "candidate_inference": model.version,
        "baseline": baseline.version,
        "splits": rows,
        "gates": {
            "aggregate_candidate_vs_baseline": "candidate <= 0.98 * baseline",
            "critical_head_regression": "candidate <= 1.15 * baseline + 0.005",
            "finite_contract": True,
            "disjoint_training_split": "checkpoint training_split == train",
        },
        "failures": failures,
        "passed": not failures,
        "promoted": False,
        "real_ab_report": (str(args.real_ab_report) if args.real_ab_report else None),
    }
    if args.promote and not failures:
        promoted_hash = _promote(args.candidate, args.promote_to, payload)
        payload["promoted"] = True
        payload["promoted_checkpoint"] = str(args.promote_to)
        payload["promoted_sha256"] = promoted_hash
    elif args.promote:
        payload["promotion_blocked"] = True
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n", encoding="utf-8")
    for split, row in rows.items():
        print(f"{split}: n={row['samples']} candidate={row['candidate_score']:.6f} "
              f"baseline={row['baseline_score']:.6f}")
    print("PROMOTION: PASS" if not failures else "PROMOTION: FAIL")
    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"report -> {args.out}")
    return 0 if not failures else 1


def _evaluate_split(files: list[Path], model: HybridEvidenceModel,
                    baseline: DeterministicEvidenceModel, temp_root: Path) -> dict:
    candidate_errors = {name: [] for name in REQUIRED_HEADS}
    baseline_errors = {name: [] for name in REQUIRED_HEADS}
    prevalence = {name: [] for name in PROBABILITY_HEADS}
    temp_root.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(files):
        with np.load(source, allow_pickle=False) as archive:
            rgba = archive["input_rgba"].astype(np.uint8)
            image_path = temp_root / f"sample-{index:06d}.png"
            Image.fromarray(rgba, "RGBA").save(image_path)
            raster = decode_raster(image_path)
            _, fields = diagnose_raster(raster)
            candidate_heads = model.infer(raster, fields, (1.0,)).levels[0].heads
            baseline_heads = baseline.infer(raster, fields, (1.0,)).levels[0].heads
            for name in REQUIRED_HEADS:
                target = archive[name].astype(np.float32)
                candidate_value = np.asarray(candidate_heads[name], np.float32)
                baseline_value = np.asarray(baseline_heads[name], np.float32)
                if candidate_value.shape != target.shape or baseline_value.shape != target.shape:
                    raise ValueError(f"head {name!r} shape mismatch for {source}")
                scale = _error_scale(name, target.shape[:2])
                candidate_errors[name].append(float(np.mean(np.abs(candidate_value - target))) / scale)
                baseline_errors[name].append(float(np.mean(np.abs(baseline_value - target))) / scale)
                if name in PROBABILITY_HEADS:
                    prevalence[name].append(float(np.mean(target)))
    candidate_mean = {name: float(np.mean(values))
                      for name, values in candidate_errors.items()}
    baseline_mean = {name: float(np.mean(values))
                     for name, values in baseline_errors.items()}
    return {
        "samples": len(files),
        "candidate_score": _weighted_score(candidate_mean),
        "baseline_score": _weighted_score(baseline_mean),
        "candidate_mae": candidate_mean,
        "baseline_mae": baseline_mean,
        "target_prevalence": {name: float(np.mean(values))
                              for name, values in prevalence.items()},
    }


def _gate_split(split: str, row: dict) -> list[str]:
    failures = []
    candidate_score = float(row["candidate_score"])
    baseline_score = float(row["baseline_score"])
    if not np.isfinite(candidate_score) or candidate_score > .98 * baseline_score:
        failures.append(
            f"{split} aggregate evidence score {candidate_score:.6f} does not beat "
            f"deterministic {baseline_score:.6f} by 2%")
    for name in CRITICAL_HEADS:
        candidate = float(row["candidate_mae"][name])
        baseline = float(row["baseline_mae"][name])
        if not np.isfinite(candidate) or candidate > 1.15 * baseline + .005:
            failures.append(
                f"{split}/{name} regressed: {candidate:.6f} vs {baseline:.6f}")
    return failures


def _error_scale(name: str, shape: tuple[int, int]) -> float:
    if name == "boundary_normal":
        return 2.0
    if name == "stroke_half_width":
        return max(1.0, float(max(shape)))
    return 1.0


def _weighted_score(values: dict[str, float]) -> float:
    return float(sum(HEAD_WEIGHTS[name] * values[name] for name in REQUIRED_HEADS))


def _split_files(dataset: Path, split: str) -> list[Path]:
    root = dataset / split
    return sorted(root.rglob("*.npz")) if root.is_dir() else []


def _validate_manifest(dataset: Path) -> tuple[str, dict]:
    path = dataset / "dataset_manifest.json"
    if not path.is_file():
        raise ValueError("dataset_manifest.json is required")
    encoded = path.read_bytes()
    payload = json.loads(encoded.decode("utf-8"))
    if payload.get("schema") != "vice-synthetic-dataset/1":
        raise ValueError("unsupported evidence dataset schema")
    if "no Vectorizer.AI output" not in str(payload.get("policy", "")):
        raise ValueError("dataset is not marked clean-room")
    declared = {str(row.get("path")) for row in payload.get("samples", ())}
    actual = {path.relative_to(dataset).as_posix()
              for split in ("train", "validation", "test")
              for path in _split_files(dataset, split)}
    if declared != actual:
        raise ValueError("dataset files do not match the frozen manifest")
    return hashlib.sha256(encoded).hexdigest(), payload


def _validate_checkpoint(path: Path, manifest_hash: str) -> tuple[str, dict]:
    import torch

    if not path.is_file():
        raise ValueError(f"candidate checkpoint does not exist: {path}")
    encoded = path.read_bytes()
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("schema") != "vice-scene-evidence-checkpoint/1":
        raise ValueError("candidate lacks the evidence checkpoint schema")
    if payload.get("status") != "candidate" or payload.get("training_split") != "train":
        raise ValueError("only a train-split candidate checkpoint can be promoted")
    if payload.get("dataset_manifest_sha256") != manifest_hash:
        raise ValueError("candidate was trained on a different dataset manifest")
    metadata = {key: value for key, value in payload.items()
                if key != "state_dict"}
    return hashlib.sha256(encoded).hexdigest(), metadata


def _promote(candidate: Path, destination: Path, validation: dict) -> str:
    import torch

    from vice_scene.neural_evidence import HybridEvidenceModel

    payload = torch.load(candidate, map_location="cpu", weights_only=True)
    payload["status"] = "promoted"
    payload["routing_version"] = HybridEvidenceModel.routing_version
    canonical = json.dumps(validation, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode("utf-8")
    payload["promotion_validation_sha256"] = hashlib.sha256(canonical).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, destination)
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def _validate_real_ab_report(path: Path, candidate_hash: str) -> dict:
    if not path.is_file():
        raise ValueError(f"real A/B report does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "vice-scene-evidence-real-ab/1":
        raise ValueError("unsupported real A/B report schema")
    if payload.get("candidate_sha256") != candidate_hash:
        raise ValueError("real A/B report belongs to a different candidate")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
