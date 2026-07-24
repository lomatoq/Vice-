"""Bind a gate-passing ProposalNet candidate to an explicit Phase-12 run."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import torch

from .conformal import conformal_calibration_from_dict
from .runtime_service import SUPPORTED_PROPOSAL_LABEL_CONTRACTS


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = PROJECT / "models" / "proposal_net_real_candidate_v9.pt"
DEFAULT_LARGE_REPORT = PROJECT / "benchmarks" / "pcdc_proposal_large_v9" / "report.json"
DEFAULT_REAL_REPORT = PROJECT / "benchmarks" / "pcdc_experiment9" / "report.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authorize_candidate(
    candidate: Path = DEFAULT_CANDIDATE,
    large_report_path: Path = DEFAULT_LARGE_REPORT,
    real_report_path: Path = DEFAULT_REAL_REPORT,
    output: Path | None = None,
) -> dict:
    large = json.loads(large_report_path.read_text("utf-8"))
    real = json.loads(real_report_path.read_text("utf-8"))
    if large.get("gate_pass") is not True:
        raise RuntimeError("large neural-only ProposalNet gate did not pass")
    if real.get("gate_pass") is not True:
        raise RuntimeError("real-locus ProposalNet gate did not pass")
    candidate_sha = _sha256(candidate)
    if str(real.get("checkpoint_sha256", "")).lower() != candidate_sha:
        raise RuntimeError("real-locus report is not bound to candidate bytes")
    large_sha = str(large.get("checkpoint_sha256", "")).lower()
    if str(real.get("initialization_sha256", "")).lower() != large_sha:
        raise RuntimeError("real-locus candidate was not initialized from large winner")
    payload = torch.load(candidate, map_location="cpu", weights_only=False)
    label_version = str(payload.get("label_contract_version", ""))
    label_sha = str(payload.get("label_contract_sha256", "")).lower()
    if label_version not in SUPPORTED_PROPOSAL_LABEL_CONTRACTS or len(label_sha) != 64:
        raise RuntimeError("candidate lacks the proved SVG-owner label contract")
    large_contract = large.get("label_contract") or {}
    if label_version != "pcdc-source-disjoint-svg-owner-labels/v1" and (
        large_contract.get("version") != label_version
        or str(large_contract.get("source_sha256", "")).lower() != label_sha
    ):
        raise RuntimeError("large report is not bound to the candidate label contract")
    conformal_fields = {}
    if label_version.endswith("/v4"):
        if (
            real.get("label_contract_version") != label_version
            or str(real.get("label_contract_sha256", "")).lower()
            != label_sha
        ):
            raise RuntimeError(
                "real report is not bound to the v4 label contract"
            )
        if real.get("conformal_admission_contract") != (
            "exact-family-prefix-rank/support-IoU>=0.50/v1"
        ):
            raise RuntimeError("real report lacks the exact runtime conformal contract")
        conformal_calibration_from_dict(real.get("calibration"))
        runtime_admission = real.get("runtime_conformal_admission") or {}
        if (
            runtime_admission.get("contract")
            != "exact-production-union+family-prefix+global-cap/v1"
            or runtime_admission.get("exact_runtime_rule") is not True
            or runtime_admission.get(
                "all_quality_modes_coverage_ge_99pct"
            ) is not True
        ):
            raise RuntimeError(
                "real report lacks passing exact Fast/Balanced/Max admission"
            )
        conformal_fields = {
            "conformal_admission_contract": real["conformal_admission_contract"],
            "conformal_calibration": real["calibration"],
            "runtime_conformal_admission": runtime_admission,
        }
    manifest = {
        "schema": "pcdc-proposal-candidate-evaluation/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_ready": True,
        "large_training_gate_passed": True,
        "real_locus_gate_passed": True,
        "checkpoint": str(candidate.resolve()),
        "checkpoint_sha256": candidate_sha,
        "label_contract_version": label_version,
        "label_contract_sha256": label_sha,
        "large_report": str(large_report_path.resolve()),
        "large_report_sha256": _sha256(large_report_path),
        "real_report": str(real_report_path.resolve()),
        "real_report_sha256": _sha256(real_report_path),
        "authorization_scope": "phase12-candidate-evaluation-only-not-production",
        **conformal_fields,
    }
    target = output or Path(str(candidate) + ".evaluation.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    temporary.replace(target)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--large-report", type=Path, default=DEFAULT_LARGE_REPORT)
    parser.add_argument("--real-report", type=Path, default=DEFAULT_REAL_REPORT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = authorize_candidate(
        args.candidate, args.large_report, args.real_report, args.output,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
