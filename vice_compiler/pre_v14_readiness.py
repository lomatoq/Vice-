"""Single fail-closed TRAIN/NO-TRAIN verdict for ProposalNet v14."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import torch

from .audit_full_regression import regression_suite_source_sha256
from .build_identity import compiler_source_sha256, evaluation_source_sha256
from .exact_font_provider import SYSTEM_FONT_CATALOG
from .font_license_manifest import validate_manifest
from .glyph_prior import glyph_prior_contract_compatibility
from .proposal_filter_cache import corpus_data_contract_sha256
from .proposal_net import ProposalNetConfig
from .train_proposal_net_large import (
    LABEL_CONTRACT_VERSION,
    V14_REQUIRED_READINESS_GATES,
    _label_contract_sha256,
    _validate_tiny_overfit_preflight,
)

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT / "benchmarks" / "pcdc_pre_v14"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_artifact(
    path: Path, *, schemas: set[str],
    passed: Callable[[dict], bool], bind_compiler: bool = True,
    expected_evaluator_sha256: str | None = None,
) -> tuple[bool, dict]:
    if not path.is_file():
        return False, {"path": str(path.resolve()), "reason": "missing"}
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return False, {
            "path": str(path.resolve()),
            "reason": f"invalid-json:{type(error).__name__}",
        }
    reasons = []
    if payload.get("schema") not in schemas:
        reasons.append("schema")
    if not passed(payload):
        reasons.append("gate")
    current_compiler = compiler_source_sha256()
    if bind_compiler and payload.get("compiler_source_sha256") != current_compiler:
        reasons.append("compiler-source")
    if (
        expected_evaluator_sha256 is not None
        and payload.get("evaluation_source_sha256")
        != expected_evaluator_sha256
    ):
        reasons.append("evaluation-source")
    return not reasons, {
        "path": str(path.resolve()), "sha256": _sha256(path),
        "schema": payload.get("schema"), "reasons": reasons,
        "compiler_source_sha256": payload.get("compiler_source_sha256"),
        "evaluation_source_sha256": payload.get("evaluation_source_sha256"),
    }


def _load_config(path: Path) -> ProposalNetConfig:
    payload = json.loads(path.read_text("utf-8"))
    if payload.get("schema") != "pcdc-proposal-config/v1":
        raise ValueError("unsupported ProposalNet config artifact")
    return ProposalNetConfig(**payload["config"])


def _glyph_prior_artifact_passed(row: dict) -> bool:
    checkpoint = PROJECT / "models" / "glyph_prior_candidate_v1.pt"
    try:
        checkpoint_payload = torch.load(
            checkpoint, map_location="cpu", weights_only=False,
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return False
    reported_contract = row.get("contract", {}).get(
        "glyph_prior_source_sha256"
    )
    return bool(
        checkpoint.is_file()
        and checkpoint_payload.get("schema")
        == "pcdc-glyph-prior-checkpoint/v1"
        and checkpoint_payload.get("model_contract_sha256")
        == reported_contract
        and glyph_prior_contract_compatibility(reported_contract) is not None
        and row.get("gate_pass") is True
        and row.get("status") == "candidate-passed"
        and float(row.get("held_out_test", {}).get(
            "topology_accuracy", 0.0,
        )) >= 0.97
        and float(row.get("held_out_test", {}).get(
            "support_iou", 0.0,
        )) >= 0.90
        and float(row.get("held_out_test", {}).get(
            "mask_topology_accuracy", 0.0,
        )) >= 0.97
        and float(row.get("held_out_test", {}).get(
            "topology_head_accuracy", 0.0,
        )) >= 0.97
        and int(row.get("training_variants", 0)) >= 2_000_000
        and int(row.get("held_out_samples_per_split", 0)) >= 20_000
        and row.get("checkpoint_sha256") == _sha256(checkpoint)
    )


def build_readiness(
    *, pair_root: Path, filter_cache: Path, initialize: Path,
    proposal_config: Path, full_tests: Path, training_data_audit: Path,
    tiny_overfit: Path, experiment1: Path, experiment1b: Path,
    experiment2: Path, experiment3: Path, experiment4: Path,
    glyph_prior_training: Path, experiment5: Path, plan_audit: Path,
    real_calibration: Path,
    runtime_conformal: Path, untouched_holdout: Path, anti_forgetting: Path,
    cuda_reproducibility: Path,
) -> dict:
    compiler_sha = compiler_source_sha256()
    label_sha = _label_contract_sha256()
    config = _load_config(proposal_config)
    corpus_sha = corpus_data_contract_sha256(pair_root)

    artifact_specs = {
        "full_regression_suite": (
            full_tests, {"pcdc-full-regression-suite/v1"},
            lambda row: row.get("passed") is True
            and int(row.get("tests_run", 0)) >= 246,
        ),
        "training_data_and_head_supervision": (
            training_data_audit, {"pcdc-pre-v14-training-data-audit/v1"},
            lambda row: row.get("passed") is True
            and row.get("label_contract_sha256") == label_sha
            and row.get("corpus_data_contract_sha256") == corpus_sha,
        ),
        "experiment1_evidence_lattice": (
            experiment1, {"pcdc-experiment1/v1"},
            lambda row: row.get("gate_pass") is True,
        ),
        "experiment1b_dual_pricing": (
            experiment1b, {"pcdc-experiment1b/v1"},
            lambda row: row.get("gate_pass") is True,
        ),
        "experiment2_oracle_extraction": (
            experiment2, {"pcdc-experiment2/v1"},
            lambda row: row.get("gate_pass") is True,
        ),
        "experiment3_certificate_discrimination": (
            experiment3, {"pcdc-experiment3/v1"},
            lambda row: row.get("gate_pass") is True,
        ),
        "experiment4_textline": (
            experiment4, {
                "pcdc-experiment4-textline/v1",
                "pcdc-experiment4-textline/v2",
            },
            lambda row: row.get("gate_pass") is True
            and row.get("status") == "passed",
        ),
        "glyph_prior_held_out_training": (
            glyph_prior_training, {"pcdc-glyph-prior-training/v1"},
            _glyph_prior_artifact_passed,
        ),
        "experiment5_complexity_stress": (
            experiment5, {"pcdc-experiment5/v1"},
            lambda row: row.get("gate_pass") is True,
        ),
        "canonical_plan_traceability": (
            plan_audit, {
                "pcdc-plan-traceability/v1", "pcdc-plan-traceability/v2",
            },
            lambda row: row.get("all_pre_phase9_requirements_complete") is True,
        ),
        "real_calibration_capacity": (
            real_calibration, {"pcdc-real-calibration-readiness/v1"},
            lambda row: row.get("passed") is True,
        ),
        "runtime_conformal_harness_equivalence": (
            runtime_conformal, {"pcdc-runtime-conformal-harness/v1"},
            lambda row: row.get("passed") is True
            and row.get("exact_runtime_rule") is True
            and row.get("shared_runtime_function") is True
            and row.get("all_quality_modes_exercised") is True
            and row.get("global_budget_cap_verified") is True,
        ),
        "untouched_disjoint_holdout": (
            untouched_holdout, {"pcdc-untouched-holdout/v1"},
            lambda row: row.get("sealed_before_training") is True
            and row.get("contamination_detected") is False
            and row.get("all_required_axes_disjoint") is True,
        ),
        "anti_forgetting_pilot": (
            anti_forgetting, {"pcdc-anti-forgetting-pilot/v1"},
            lambda row: row.get("passed") is True
            and row.get("checkpoint_written") is False
            and row.get("adaptation_anchor_group_disjoint") is True
            and row.get("device") == "cuda"
            and row.get("checkpoint_sha256") == _sha256(initialize)
            and row.get("filter_cache_sha256") == _sha256(filter_cache)
            and row.get("label_contract_sha256") == label_sha
            and row.get("proposal_config") == asdict(config),
        ),
        "cuda_reproducibility": (
            cuda_reproducibility, {"pcdc-cuda-reproducibility/v1"},
            lambda row: row.get("passed") is True
            and row.get("same_seed_conclusion_stable") is True
            and row.get("state_sha256_equal") is True
            and row.get("loss_trace_sha256_equal") is True
            and row.get("checkpoint_written") is False
            and row.get("device") == "cuda"
            and row.get("checkpoint_sha256") == _sha256(initialize)
            and row.get("filter_cache_sha256") == _sha256(filter_cache)
            and row.get("label_contract_sha256") == label_sha
            and row.get("proposal_config") == asdict(config),
        ),
    }
    artifacts = {}
    gates = {}
    evaluator_identities = {
        "full_regression_suite": regression_suite_source_sha256(),
        "experiment1_evidence_lattice": evaluation_source_sha256(
            "vice_compiler/experiment1_evidence_coverage.py",
        ),
        "experiment1b_dual_pricing": evaluation_source_sha256(
            "vice_compiler/experiment1b_pricing_recall.py",
        ),
        "experiment2_oracle_extraction": evaluation_source_sha256(
            "vice_compiler/experiment2_oracle_extraction.py",
        ),
        "experiment3_certificate_discrimination": evaluation_source_sha256(
            "vice_compiler/experiment3_certificate_discrimination.py",
        ),
        "experiment4_textline": evaluation_source_sha256(
            "vice_compiler/experiment4_textline.py",
        ),
        "experiment5_complexity_stress": evaluation_source_sha256(
            "vice_compiler/experiment5_complexity_stress.py",
        ),
        "canonical_plan_traceability": evaluation_source_sha256(
            "vice_compiler/audit_plan_traceability.py",
        ),
        "real_calibration_capacity": evaluation_source_sha256(
            "vice_compiler/audit_real_calibration_capacity.py",
        ),
        "anti_forgetting_pilot": evaluation_source_sha256(
            "vice_compiler/audit_proposal_training_dynamics.py",
        ),
        "cuda_reproducibility": evaluation_source_sha256(
            "vice_compiler/audit_proposal_training_dynamics.py",
        ),
    }
    for name, (path, schemas, predicate) in artifact_specs.items():
        gates[name], artifacts[name] = _load_artifact(
            path, schemas=schemas, passed=predicate,
            bind_compiler=name != "glyph_prior_held_out_training",
            expected_evaluator_sha256=evaluator_identities.get(name),
        )

    try:
        tiny = _validate_tiny_overfit_preflight(
            tiny_overfit, config=config, checkpoint=initialize,
            pair_root=pair_root, filter_cache=filter_cache,
        )
        gates["tiny_multi_instance_overfit"] = True
        artifacts["tiny_multi_instance_overfit"] = {
            "path": str(tiny_overfit.resolve()),
            "sha256": _sha256(tiny_overfit), "schema": tiny.get("schema"),
            "reasons": [],
        }
    except Exception as error:
        gates["tiny_multi_instance_overfit"] = False
        artifacts["tiny_multi_instance_overfit"] = {
            "path": str(tiny_overfit.resolve()),
            "reason": f"{type(error).__name__}: {error}",
        }

    font_manifest_path = PROJECT / "fonts" / "google-fonts-manifest.json"
    try:
        font_manifest = json.loads(font_manifest_path.read_text("utf-8"))
        validate_manifest(
            font_manifest, root=PROJECT / "fonts" / "google-fonts",
        )
        licensed_paths = {
            str((PROJECT / "fonts" / "google-fonts" / row["font_path"]).resolve()).casefold()
            for row in font_manifest["fonts"]
        }
        runtime_paths = {
            str(Path(path).resolve()).casefold()
            for _name, path in SYSTEM_FONT_CATALOG
        }
        font_ok = (
            font_manifest.get("source_revision") not in {None, "", "unversioned"}
            and runtime_paths == licensed_paths
        )
        gates["licensed_font_bank_exactly_matches_runtime"] = font_ok
        artifacts["licensed_font_bank_exactly_matches_runtime"] = {
            "path": str(font_manifest_path.resolve()),
            "sha256": _sha256(font_manifest_path),
            "font_count": font_manifest.get("font_count"),
            "family_count": font_manifest.get("family_count"),
            "source_revision": font_manifest.get("source_revision"),
            "reasons": [] if font_ok else ["runtime-manifest-mismatch"],
        }
    except Exception as error:
        gates["licensed_font_bank_exactly_matches_runtime"] = False
        artifacts["licensed_font_bank_exactly_matches_runtime"] = {
            "path": str(font_manifest_path.resolve()),
            "reason": f"{type(error).__name__}: {error}",
        }

    authorized = bool(gates) and all(gates.values())
    if set(gates) != set(V14_REQUIRED_READINESS_GATES):
        missing = sorted(set(V14_REQUIRED_READINESS_GATES) - set(gates))
        extra = sorted(set(gates) - set(V14_REQUIRED_READINESS_GATES))
        raise RuntimeError(
            f"internal readiness gate mismatch: missing={missing}, extra={extra}"
        )
    return {
        "schema": "pcdc-v14-training-readiness/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "TRAIN" if authorized else "NO-TRAIN",
        "training_authorized": authorized,
        "compiler_source_sha256": compiler_sha,
        "evaluation_source_sha256": evaluation_source_sha256(__file__),
        "label_contract_version": LABEL_CONTRACT_VERSION,
        "label_contract_sha256": label_sha,
        "pair_root": str(pair_root.resolve()),
        "corpus_data_contract_sha256": corpus_sha,
        "filter_cache_sha256": _sha256(filter_cache),
        "initialization_checkpoint_sha256": _sha256(initialize),
        "proposal_config": asdict(config),
        "proposal_config_artifact": str(proposal_config.resolve()),
        "proposal_config_sha256": _sha256(proposal_config),
        "required_gates": gates, "artifacts": artifacts,
        "blocking_gates": [name for name, passed in gates.items() if not passed],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--filter-cache", type=Path, required=True)
    parser.add_argument("--initialize", type=Path, required=True)
    parser.add_argument("--proposal-config", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_ROOT / "readiness.json")
    defaults = {
        "full_tests": DEFAULT_ROOT / "full_tests.json",
        "training_data_audit": DEFAULT_ROOT / "training_data_audit.json",
        "tiny_overfit": DEFAULT_ROOT / "tiny_overfit.json",
        "experiment1": PROJECT / "benchmarks/pcdc_experiment1/report.json",
        "experiment1b": PROJECT / "benchmarks/pcdc_experiment1b/report.json",
        "experiment2": PROJECT / "benchmarks/pcdc_experiment2/report.json",
        "experiment3": PROJECT / "benchmarks/pcdc_experiment3/report.json",
        "experiment4": PROJECT / "benchmarks/pcdc_experiment4/report.json",
        "glyph_prior_training": DEFAULT_ROOT / "glyph_prior_training.json",
        "experiment5": PROJECT / "benchmarks/pcdc_experiment5/report.json",
        "plan_audit": DEFAULT_ROOT / "plan_traceability.json",
        "real_calibration": DEFAULT_ROOT / "real_calibration.json",
        "runtime_conformal": DEFAULT_ROOT / "runtime_conformal.json",
        "untouched_holdout": DEFAULT_ROOT / "untouched_holdout.json",
        "anti_forgetting": DEFAULT_ROOT / "anti_forgetting.json",
        "cuda_reproducibility": DEFAULT_ROOT / "cuda_reproducibility.json",
    }
    for name, default in defaults.items():
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, default=default)
    args = parser.parse_args()
    report = build_readiness(**{
        name: getattr(args, name) for name in (
            "pair_root", "filter_cache", "initialize", "proposal_config",
            *defaults,
        )
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "status": report["status"],
        "blocking_gates": report["blocking_gates"],
        "out": str(args.out.resolve()),
    }, indent=2, sort_keys=True))
    if not report["training_authorized"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
