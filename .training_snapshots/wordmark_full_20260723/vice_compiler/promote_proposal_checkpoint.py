"""Atomically promote only a fully audited ProposalNet candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import torch

from .experiment12_full_campaign import (
    _blind_parity_evidence, _proposal_calibration_evidence,
)
from .runtime_service import (
    SUPPORTED_PROPOSAL_LABEL_CONTRACTS,
    _validate_proposal_candidate_evaluation,
)


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = PROJECT / "models" / "proposal_net_real_candidate_v9.pt"
DEFAULT_EVALUATION = Path(str(DEFAULT_CANDIDATE) + ".evaluation.json")
DEFAULT_CAMPAIGN = (
    PROJECT / "benchmarks" / "pcdc_experiment12" / "runs" / "promotion" / "report.json"
)
DEFAULT_BLIND = (
    PROJECT / "benchmarks" / "pcdc_experiment12" / "blind_vai_court" / "review.json"
)
DEFAULT_OUTPUT = PROJECT / "models" / "proposal_net_v1.pt"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promote_candidate(
    candidate: Path = DEFAULT_CANDIDATE,
    evaluation_manifest: Path = DEFAULT_EVALUATION,
    campaign_report: Path = DEFAULT_CAMPAIGN,
    blind_review: Path = DEFAULT_BLIND,
    output: Path = DEFAULT_OUTPUT,
) -> dict:
    _validate_proposal_candidate_evaluation(candidate, evaluation_manifest)
    evaluation = json.loads(evaluation_manifest.read_text("utf-8"))
    campaign = json.loads(campaign_report.read_text("utf-8"))
    if campaign.get("schema") != "pcdc-experiment12/v1":
        raise RuntimeError("unsupported Phase-12 campaign report")
    candidate_sha = _sha256(candidate)
    evaluated = campaign.get("proposal_evaluation") or {}
    if (
        evaluated.get("mode") != "candidate-evaluation"
        or str(evaluated.get("checkpoint_sha256", "")).lower() != candidate_sha
    ):
        raise RuntimeError("Phase-12 campaign did not evaluate candidate bytes")
    technical_names = (
        "valid_complete_build_freeze",
        "canonical_50_plus_115", "all_requested_completed",
        "zero_timeout_or_error", "deterministic_export",
        "zero_whole_scene_topology_failures", "balanced_speed",
    )
    gates = campaign.get("gates", {})
    if not all(gates.get(name) is True for name in technical_names):
        raise RuntimeError("Phase-12 technical campaign gates are incomplete")
    calibration_path = Path(str(evaluation.get("real_report", "")))
    if (
        not calibration_path.is_file()
        or _sha256(calibration_path)
        != str(evaluation.get("real_report_sha256", "")).lower()
    ):
        raise RuntimeError("candidate evaluation does not bind its calibration report")
    calibration_payload = json.loads(calibration_path.read_text("utf-8"))
    if str(calibration_payload.get("checkpoint_sha256", "")).lower() != candidate_sha:
        raise RuntimeError("calibration report belongs to another checkpoint")
    calibration = _proposal_calibration_evidence(calibration_path)
    if not calibration.get("passed"):
        raise RuntimeError("non-vacuous real conformal calibration did not pass")
    payload = torch.load(candidate, map_location="cpu", weights_only=False)
    label_version = str(payload.get("label_contract_version", ""))
    label_sha = str(payload.get("label_contract_sha256", "")).lower()
    if label_version not in SUPPORTED_PROPOSAL_LABEL_CONTRACTS or len(label_sha) != 64:
        raise RuntimeError("candidate label contract is not promotable")
    conformal_fields = {}
    if label_version.endswith("/v4"):
        if (
            calibration_payload.get("label_contract_version") != label_version
            or str(calibration_payload.get(
                "label_contract_sha256", ""
            )).lower() != label_sha
        ):
            raise RuntimeError(
                "calibration report is not bound to the v4 label contract"
            )
        conformal_payload = calibration_payload.get("calibration")
        conformal_contract = calibration_payload.get("conformal_admission_contract")
        if conformal_contract != "exact-family-prefix-rank/support-IoU>=0.50/v1":
            raise RuntimeError("calibration report lacks exact runtime admission")
        runtime_admission = calibration_payload.get(
            "runtime_conformal_admission"
        ) or {}
        if (
            runtime_admission.get("contract")
            != "exact-production-union+family-prefix+global-cap/v1"
            or runtime_admission.get("exact_runtime_rule") is not True
            or runtime_admission.get(
                "all_quality_modes_coverage_ge_99pct"
            ) is not True
        ):
            raise RuntimeError(
                "calibration report lacks passing Fast/Balanced/Max replay"
            )
        conformal_fields = {
            "conformal_admission_contract": conformal_contract,
            "conformal_calibration": conformal_payload,
            "runtime_conformal_admission": runtime_admission,
        }
    blind = _blind_parity_evidence(blind_review)
    if not blind.get("passed"):
        raise RuntimeError("locked blind VAI parity did not pass")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_checkpoint = output.with_suffix(output.suffix + ".tmp")
    shutil.copy2(candidate, temporary_checkpoint)
    temporary_checkpoint.replace(output)
    output_sha = _sha256(output)
    if output_sha != candidate_sha:
        raise RuntimeError("atomic candidate copy checksum mismatch")
    manifest = {
        "schema": "pcdc-proposal-runtime-promotion/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "promotion_ready": True, "all_promotion_gates_passed": True,
        "checkpoint_sha256": output_sha,
        "label_contract_version": label_version,
        "label_contract_sha256": label_sha,
        "candidate_evaluation_manifest_sha256": _sha256(evaluation_manifest),
        "calibration_report_sha256": _sha256(calibration_path),
        **conformal_fields,
        "phase12_campaign_report_sha256": _sha256(campaign_report),
        "blind_review_sha256": _sha256(blind_review),
        "blind_parity_score": blind["parity_score"],
        "blind_slice_scores": blind["slice_scores"],
        "technical_gates": {name: True for name in technical_names},
    }
    manifest_path = output.with_suffix(output.suffix + ".promotion.json")
    temporary_manifest = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    temporary_manifest.replace(manifest_path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--evaluation-manifest", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--campaign-report", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--blind-review", type=Path, default=DEFAULT_BLIND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = promote_candidate(
        args.candidate, args.evaluation_manifest, args.campaign_report,
        args.blind_review, args.output,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
