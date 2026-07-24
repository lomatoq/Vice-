"""Machine-readable Phase 0-8 traceability against the canonical PCDC plan."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .build_identity import compiler_source_sha256, native_runtime_identity


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_pre_v14" / "plan_traceability.json"


def _module(relative: str) -> bool:
    return (PROJECT / relative).is_file()


def _source_contract(relative: str, required: tuple[str, ...]) -> bool:
    path = PROJECT / relative
    if not path.is_file():
        return False
    try:
        source = path.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return all(marker in source for marker in required)


def _behavior_contract(
    source_relative: str,
    source_markers: tuple[str, ...],
    test_relative: str,
    test_markers: tuple[str, ...],
) -> bool:
    """Require production code and an explicit behavioral regression.

    A filename or class name is not execution evidence.  This helper still is
    only a static preflight (the suite must be run separately), but it prevents
    traceability from calling a requirement complete when the delivery path or
    its behavioral assertion is absent.
    """
    return _source_contract(source_relative, source_markers) and _source_contract(
        test_relative, test_markers,
    )


def _read_json(relative: str) -> dict[str, Any] | None:
    path = PROJECT / relative
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _experiment_evidence(
    relative: str, schemas: tuple[str, ...], *, require_native: bool = True,
) -> dict[str, Any]:
    payload = _read_json(relative)
    current_compiler = compiler_source_sha256()
    current_native = native_runtime_identity()["sha256"]
    checks = {
        "report_exists": payload is not None,
        "schema_matches": bool(payload and payload.get("schema") in schemas),
        "gate_pass": bool(payload and payload.get("gate_pass") is True),
        "status_passed": bool(payload and payload.get("status") == "passed"),
        "compiler_hash_current": bool(
            payload and payload.get("compiler_source_sha256") == current_compiler
        ),
        "native_hash_current": bool(
            not require_native or payload
            and payload.get("native_runtime_identity", {}).get("sha256")
            == current_native
        ),
    }
    return {
        "path": relative,
        "complete": all(checks.values()),
        "checks": checks,
        "actual_schema": payload.get("schema") if payload else None,
        "actual_status": payload.get("status") if payload else None,
        "actual_compiler_source_sha256": (
            payload.get("compiler_source_sha256") if payload else None
        ),
        "actual_native_runtime_sha256": (
            payload.get("native_runtime_identity", {}).get("sha256")
            if payload else None
        ),
    }


def _experiment(relative: str, schema: str) -> bool:
    return bool(_experiment_evidence(relative, (schema,))["complete"])


def _glyph_model_contract_sha256() -> str:
    digest = hashlib.sha256()
    for name in ("glyph_prior.py", "glyph_prior_data.py"):
        path = PROJECT / "vice_compiler" / name
        if not path.is_file():
            return ""
        digest.update(name.encode("ascii"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _glyph_prior_training_evidence() -> dict[str, Any]:
    """Separate model validity from compiler promotion validity.

    Serving/court edits legitimately change the compiler hash without changing
    what the glyph checkpoint learned.  They require a new downstream ablation,
    not an automatic two-million-sample retrain.  The model/data contract hash
    is the correct identity for the training result.
    """
    report_path = PROJECT / "benchmarks/pcdc_pre_v14/glyph_prior_training.json"
    checkpoint_path = PROJECT / "models/glyph_prior_candidate_v1.pt"
    report = _read_json("benchmarks/pcdc_pre_v14/glyph_prior_training.json")
    checkpoint_sha256 = (
        hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
        if checkpoint_path.is_file() else None
    )
    current_model_contract = _glyph_model_contract_sha256()
    checks = {
        "report_exists": report_path.is_file() and report is not None,
        "checkpoint_exists": checkpoint_path.is_file(),
        "schema_matches": bool(
            report and report.get("schema") == "pcdc-glyph-prior-training/v1"
        ),
        "candidate_gate_passed": bool(
            report and report.get("gate_pass") is True
            and report.get("status") == "candidate-passed"
        ),
        "checkpoint_hash_matches": bool(
            report and checkpoint_sha256
            and report.get("checkpoint_sha256") == checkpoint_sha256
        ),
        "model_data_contract_current": bool(
            report and current_model_contract
            and report.get("contract", {}).get("glyph_prior_source_sha256")
            == current_model_contract
        ),
        "held_out_topology_ge_097": bool(
            report and float(report.get("held_out_test", {}).get(
                "mask_topology_accuracy", 0.0,
            )) >= 0.97
            and float(report.get("held_out_test", {}).get(
                "topology_head_accuracy", 0.0,
            )) >= 0.97
        ),
        "held_out_support_iou_ge_090": bool(
            report and float(report.get("held_out_test", {}).get(
                "support_iou", 0.0,
            )) >= 0.90
        ),
        "two_million_variants": bool(
            report and int(report.get("training_variants", 0)) >= 2_000_000
        ),
        "held_out_family_samples_ge_20000": bool(
            report and int(report.get("held_out_samples_per_split", 0))
            >= 20_000
        ),
    }
    return {
        "complete": all(checks.values()), "checks": checks,
        "report": str(report_path.relative_to(PROJECT)),
        "checkpoint": str(checkpoint_path.relative_to(PROJECT)),
        "checkpoint_sha256": checkpoint_sha256,
        "current_model_contract_sha256": current_model_contract,
        "training_compiler_hash_is_current": bool(
            report and report.get("compiler_source_sha256")
            == compiler_source_sha256()
        ),
    }


def _glyph_prior_training_ready() -> bool:
    return bool(_glyph_prior_training_evidence()["complete"])


def _wordmark_prior_training_evidence() -> dict[str, Any]:
    report_path = PROJECT / "benchmarks/pcdc_pre_v14/wordmark_prior_full_v1.json"
    checkpoint_path = PROJECT / "models/wordmark_prior_candidate_v1.pt"
    report = _read_json("benchmarks/pcdc_pre_v14/wordmark_prior_full_v1.json")
    checkpoint_sha256 = (
        hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
        if checkpoint_path.is_file() else None
    )
    try:
        from .wordmark_prior import wordmark_prior_source_sha256
        current_model_contract = wordmark_prior_source_sha256()
    except (ImportError, OSError, RuntimeError):
        current_model_contract = ""
    held_out = report.get("held_out_test", {}) if report else {}
    checks = {
        "report_exists": report_path.is_file() and report is not None,
        "checkpoint_exists": checkpoint_path.is_file(),
        "schema_matches": bool(
            report and report.get("schema") == "pcdc-wordmark-prior-training/v1"
        ),
        "candidate_gate_passed": bool(
            report and report.get("gate_pass") is True
            and report.get("status") == "candidate-passed"
        ),
        "checkpoint_hash_matches": bool(
            report and checkpoint_sha256
            and report.get("checkpoint_sha256") == checkpoint_sha256
        ),
        "model_data_contract_current": bool(
            report and current_model_contract
            and report.get("model_data_contract_sha256")
            == current_model_contract
        ),
        "held_out_support_iou_ge_088": bool(
            float(held_out.get("decoded_support_iou", 0.0)) >= 0.88
        ),
        "held_out_topology_ge_095": bool(
            float(held_out.get("decoded_topology_accuracy", 0.0)) >= 0.95
        ),
        "held_out_complex_topology_ge_090": bool(
            float(held_out.get("decoded_complex_topology_accuracy", 0.0))
            >= 0.90
        ),
        "held_out_heads_ge_090": bool(
            float(held_out.get("component_head_accuracy", 0.0)) >= 0.90
            and float(held_out.get("hole_head_accuracy", 0.0)) >= 0.90
        ),
        "two_million_unique_variants": bool(
            report and int(report.get("training_variants", 0)) >= 2_000_000
        ),
        "held_out_family_samples_ge_20000": bool(
            report and int(report.get("held_out_samples_per_split", 0))
            >= 20_000
        ),
    }
    return {
        "complete": all(checks.values()), "checks": checks,
        "report": str(report_path.relative_to(PROJECT)),
        "checkpoint": str(checkpoint_path.relative_to(PROJECT)),
        "checkpoint_sha256": checkpoint_sha256,
        "current_model_contract_sha256": current_model_contract,
    }


def _current_phase4_ablation_reports() -> tuple[str, str]:
    """Return the newest same-compiler model-OFF/ON Experiment-4 pair."""
    directory = PROJECT / "benchmarks" / "pcdc_experiment4"
    current_hash = compiler_source_sha256()
    baseline: list[tuple[str, Path]] = []
    candidate: list[tuple[str, Path]] = []
    for path in directory.glob("*.json") if directory.is_dir() else ():
        try:
            payload = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            payload.get("schema")
            not in {"pcdc-experiment4-textline/v1", "pcdc-experiment4-textline/v2"}
            or payload.get("compiler_source_sha256") != current_hash
            or len(payload.get("rows", ())) != 100
        ):
            continue
        created = str(payload.get("created_at") or "")
        target = (
            candidate if (
                payload.get("glyph_prior_checkpoint")
                or payload.get("wordmark_prior_checkpoint")
            ) else baseline
        )
        target.append((created, path))
    if not baseline or not candidate:
        return (
            "benchmarks/pcdc_experiment4/report_no_model_pre_spatial.json",
            "benchmarks/pcdc_experiment4/report_candidate_batched_reachable.json",
        )
    baseline_path = max(baseline)[1].relative_to(PROJECT).as_posix()
    candidate_path = max(candidate)[1].relative_to(PROJECT).as_posix()
    return baseline_path, candidate_path


def _phase4_runtime_ablation_evidence(
    *, expected_wordmark_sha256: str | None = None,
) -> dict[str, Any]:
    baseline_relative, candidate_relative = _current_phase4_ablation_reports()
    baseline = _read_json(baseline_relative)
    candidate = _read_json(candidate_relative)
    current_hash = compiler_source_sha256()
    changed = 0
    candidate_rows: dict[str, dict[str, Any]] = {}
    baseline_rows: dict[str, dict[str, Any]] = {}
    if baseline:
        baseline_rows = {
            str(row.get("id")): row for row in baseline.get("rows", [])
            if isinstance(row, dict)
        }
    if candidate:
        candidate_rows = {
            str(row.get("id")): row for row in candidate.get("rows", [])
            if isinstance(row, dict)
        }
    if baseline_rows and candidate_rows.keys() == baseline_rows.keys():
        changed = sum(
            candidate_rows[row_id].get("candidate_svg_digest")
            != baseline_rows[row_id].get("candidate_svg_digest")
            or candidate_rows[row_id].get("candidate_mask_digest")
            != baseline_rows[row_id].get("candidate_mask_digest")
            for row_id in candidate_rows
        )
    candidate_machine = candidate.get("machine", {}) if candidate else {}
    baseline_machine = baseline.get("machine", {}) if baseline else {}
    candidate_wordmark = (
        candidate.get("wordmark_prior_checkpoint", {}) if candidate else {}
    ) or {}
    checks = {
        "candidate_report_current": bool(
            candidate and candidate.get("compiler_source_sha256") == current_hash
        ),
        "candidate_bound_to_trained_wordmark": bool(
            expected_wordmark_sha256
            and candidate_wordmark.get("sha256") == expected_wordmark_sha256
        ),
        "same_100_loci": bool(
            len(candidate_rows) == 100
            and candidate_rows.keys() == baseline_rows.keys()
        ),
        "model_changes_delivered_output": changed > 0,
        "no_line_topology_regression": bool(
            candidate_machine.get("all_reviewed_lines_not_worse") is True
        ),
        "mean_iou_not_worse": bool(
            candidate_machine and baseline_machine
            and float(candidate_machine.get("candidate_mean_iou", -1.0))
            >= float(baseline_machine.get("candidate_mean_iou", 0.0)) - 1e-12
        ),
        "warm_p95_under_200ms": bool(
            candidate_machine
            and float(candidate_machine.get("warm_p95_ms_per_line", 1e30)) < 200.0
        ),
    }
    # A model that cannot alter the delivered output has no downstream effect,
    # regardless of how good its synthetic crop score is.
    return {
        "complete": all(checks.values()), "checks": checks,
        "baseline_report": baseline_relative,
        "candidate_report": candidate_relative,
        "delivered_rows_changed": changed,
        "candidate_mean_iou": candidate_machine.get("candidate_mean_iou"),
        "baseline_mean_iou": baseline_machine.get("candidate_mean_iou"),
        "candidate_gcr_rate": candidate_machine.get("candidate_gcr_rate"),
        "baseline_gcr_rate": baseline_machine.get("candidate_gcr_rate"),
        "warm_p95_ms_per_line": candidate_machine.get("warm_p95_ms_per_line"),
        "full_p95_ms_per_line": candidate_machine.get("full_p95_ms_per_line"),
    }


def _font_free_line_variable_delivery_evidence() -> dict[str, Any]:
    writer_path = PROJECT / "vice_compiler/export_writer.py"
    text_path = PROJECT / "vice_compiler/text_macros.py"
    test_path = PROJECT / "test_pcdc_text.py"
    try:
        writer = writer_path.read_text("utf-8")
        text_source = text_path.read_text("utf-8")
        tests = test_path.read_text("utf-8")
        start = writer.index("    def transformed(")
        end = writer.index(
            '    if record.path in {"exact-font", "semantic-font-idealization"}:',
            start,
        )
        delivery = writer[start:end]
    except (OSError, UnicodeDecodeError, ValueError):
        writer = text_source = tests = delivery = ""
    checks = {
        "baseline_reaches_exact_delivery": '"baseline"' in delivery,
        "x_height_reaches_exact_delivery": '"x_height"' in delivery,
        "cap_height_reaches_exact_delivery": '"cap_height"' in delivery,
        "overshoot_reaches_exact_delivery": '"overshoot"' in delivery,
        "slant_reaches_exact_delivery": '"slant"' in delivery,
        "tracking_reaches_font_free_delivery": '"tracking"' in delivery,
        "shared_stem_classes_reach_delivery": (
            '"shared_stem_width"' in delivery
            and "stem_delta" in delivery
        ),
        "prototype_assignments_reach_delivery": all(marker in text_source for marker in (
            "materialize_font_free_geometry", "repeated_glyph_em",
            "prototype.member_ids", "idealized",
        )),
        "all_variables_have_delivery_regression": all(marker in tests for marker in (
            "test_font_free_continuous_parameters_change_exact_delivery",
            "baseline", "x_height", "cap_height", "overshoot", "slant",
            "tracking", "shared_stem_width",
        )),
    }
    return {"complete": all(checks.values()), "checks": checks}


def _row(
    requirement: str, complete: bool, evidence: str,
    *, checks: dict[str, bool] | None = None,
) -> dict:
    row: dict[str, Any] = {
        "requirement": requirement, "complete": bool(complete),
        "evidence": evidence,
    }
    if checks is not None:
        row["checks"] = checks
        row["complete"] = bool(complete and all(checks.values()))
    return row


def build_report() -> dict:
    phase1_evidence = _experiment_evidence(
        "benchmarks/pcdc_experiment1/report.json", ("pcdc-experiment1/v1",),
    )
    phase1b_evidence = _experiment_evidence(
        "benchmarks/pcdc_experiment1b/report.json", ("pcdc-experiment1b/v1",),
        require_native=False,
    )
    phase2_evidence = _experiment_evidence(
        "benchmarks/pcdc_experiment2/report.json", ("pcdc-experiment2/v1",),
    )
    phase3_evidence = _experiment_evidence(
        "benchmarks/pcdc_experiment3/report.json", ("pcdc-experiment3/v1",),
    )
    _phase4_baseline, phase4_candidate = _current_phase4_ablation_reports()
    phase4_evidence = _experiment_evidence(
        phase4_candidate,
        ("pcdc-experiment4-textline/v1", "pcdc-experiment4-textline/v2"),
    )
    phase5_evidence = _experiment_evidence(
        "benchmarks/pcdc_experiment5/report.json", ("pcdc-experiment5/v1",),
    )
    glyph_training = _glyph_prior_training_evidence()
    glyph_prior_ready = bool(glyph_training["complete"])
    wordmark_training = _wordmark_prior_training_evidence()
    wordmark_prior_ready = bool(wordmark_training["complete"])
    phase4_ablation = _phase4_runtime_ablation_evidence(
        expected_wordmark_sha256=wordmark_training.get("checkpoint_sha256"),
    )
    phase0_completeness = _read_json(
        "benchmarks/pcdc_phase0/completeness_report.json"
    )
    phase0_benchmark_checks = {
        "ledger_complete": bool(
            phase0_completeness and phase0_completeness.get("complete") is True
        ),
        "vai50_has_50_explicit_rows": bool(
            phase0_completeness
            and len(phase0_completeness.get("campaigns", {}).get(
                "vai50", {},
            ).get("rows", [])) == 50
        ),
        "challenge_has_115_explicit_rows": bool(
            phase0_completeness
            and len(phase0_completeness.get("campaigns", {}).get(
                "challenge115", {},
            ).get("rows", [])) == 115
        ),
        "behavioral_ledger_test_present": _source_contract(
            "test_pcdc_phase0.py",
            ("test_every_frozen_item_has_an_explicit_complete_row",),
        ),
    }
    phases = {
        "phase0_freeze_current_truth": [
            _row(
                "V-ICE Best production fallback",
                _behavior_contract(
                    "vice_compiler/legacy_best.py",
                    ("LegacyBestArtifact", "LegacyBestResolver", "resolve"),
                    "test_pcdc_export.py",
                    ("test_real_legacy_fallback_is_hash_checked_and_exported_exactly",),
                ),
                "hash-checked fallback reaches the exact production writer",
            ),
            _row(
                "Scene Engine archived experimental",
                _behavior_contract(
                    "vice_compiler/benchmark_completeness.py",
                    ("Scene Engine · archived experiment", "scene_archived_label"),
                    "test_pcdc_phase0.py",
                    ("test_every_frozen_item_has_an_explicit_complete_row",),
                ) and bool(
                    phase0_completeness
                    and phase0_completeness.get("production_route", {}).get(
                        "scene_archived_label"
                    ) is True
                ),
                "production route and frozen ledger mark Scene Engine archived",
            ),
            _row(
                "benchmark input completeness",
                all(phase0_benchmark_checks.values()),
                "VAI50 50/50 and challenge115 115/115 explicit input ledger; "
                "this is not the deferred Phase-12 quality campaign",
                checks=phase0_benchmark_checks,
            ),
            _row(
                "Real Locus Corpus seed",
                _module("datasets/pcdc_real_loci_v1/manifest.json")
                and _module("datasets/pcdc_real_loci_v1/review.json"),
                "300-locus seed exists; 2k-5k reviewed calibration target is later",
            ),
            _row(
                "stage profiler",
                _behavior_contract(
                    "vice_compiler/runtime_service.py",
                    ("AnytimeCheckpoint", "stage_profile"),
                    "test_pcdc_phase0.py",
                    ("test_records_success_and_budget",
                     "test_records_failure_instead_of_dropping_stage"),
                ),
                "runtime checkpoints are asserted on the production service",
            ),
        ],
        "phase1_reir": [
            _row(
                "canonical immutable evidence cache",
                _behavior_contract(
                    "vice_compiler/evidence_ir.py",
                    ("EvidenceCache", "RasterEvidenceIR", "setflags(write=False)"),
                    "test_pcdc_reir.py",
                    ("test_reir_is_immutable_complete_and_bounded",
                     "test_content_addressed_cache_round_trip"),
                ),
                "REIR cache and immutability have behavioral regressions",
            ),
            _row(
                "UCM, inclusion trees, core/bands and half-edge interfaces",
                _behavior_contract(
                    "vice_compiler/evidence_ir.py",
                    ("hierarchy", "inclusion", "boundary_bands", "interfaces"),
                    "test_pcdc_reir.py",
                    ("test_half_edge_twins_are_involutive",
                     "test_transaction_splits_core_without_mutating_reir"),
                ),
                "the evidence lattice is tested as one immutable contract",
            ),
            _row(
                "Experiment 1 current and passing",
                bool(phase1_evidence["complete"]),
                phase1_evidence["path"], checks=phase1_evidence["checks"],
            ),
        ],
        "phase2_cmir_extractor": [
            _row(
                "atomic fallback, legacy adapter and feasible exact cover",
                _behavior_contract(
                    "vice_compiler/macro_registry.py",
                    ("build_base_registry", "candidate_from_support"),
                    "test_pcdc_cmir.py",
                    ("test_base_registry_has_symmetric_conflicts_and_atomic_cover",),
                ) and _module("vice_compiler/legacy_best.py"),
                "base registry feasibility is asserted, not inferred from a file",
            ),
            _row(
                "hierarchy DP, sparse conflict components and bounded exact solve",
                _behavior_contract(
                    "vice_compiler/macro_extractor.py",
                    ("conflict", "fallback", "selected_ids"),
                    "test_pcdc_cmir.py",
                    ("test_hierarchy_dp_is_an_exact_cover",
                     "test_master_selection_is_independent_of_wall_clock_jitter"),
                ),
                "selection behavior and deterministic fallback are tested",
            ),
            _row(
                "2-4 dual-guided pricing rounds without manual risk gate",
                _behavior_contract(
                    "vice_compiler/column_generation.py",
                    ("dual", "pricing", "round"),
                    "test_pcdc_cmir.py",
                    ("test_column_generation_is_bounded_and_has_no_manual_risk_gate",),
                ),
                "bounded column generation is wired into CMIR",
            ),
            _row(
                "Experiment 1B current and passing",
                bool(phase1b_evidence["complete"]),
                phase1b_evidence["path"], checks=phase1b_evidence["checks"],
            ),
            _row(
                "Experiment 2 current and passing",
                bool(phase2_evidence["complete"]),
                phase2_evidence["path"], checks=phase2_evidence["checks"],
            ),
        ],
        "phase3_court_certificates": [
            _row(
                "fixed fallback-conditioned renderer posterior",
                _behavior_contract(
                    "vice_compiler/renderer_posterior.py",
                    ("FixedRendererPosterior", "fallback_likelihoods"),
                    "test_pcdc_court.py",
                    ("test_fixed_posterior_is_sealed_and_bounded",
                     "test_render_lcb_conditions_only_on_fixed_fallback_evidence"),
                ),
                "candidate and fallback share one sealed posterior",
            ),
            _row(
                "cheap-to-expensive court with SDF/topology/exact ROI atlas",
                _behavior_contract(
                    "vice_compiler/local_court.py",
                    ("color-mass-lower-bound", "sdf-interval-bound", "topology",
                     "approximate-analytic-render", "exact-batched-roi-render"),
                    "test_pcdc_court.py",
                    ("test_color_mass_proof_prunes_robust_outlier_overfit",
                     "test_invalid_candidate_is_pruned_before_exact_atlas",
                     "test_roi_atlas_reports_exact_physical_budget"),
                ),
                "cascade order is asserted by behavioral court tests",
            ),
            _row(
                "optional human-preference tie-break only on physical ties",
                _behavior_contract(
                    "vice_compiler/local_court.py",
                    ("preference_tiebreaker", "tie-without-preference-model-fallback"),
                    "test_pcdc_court.py",
                    ("learned-preference-tiebreak-candidate",
                     "tie-without-preference-model-fallback"),
                ),
                "hook exists and abstention/tie returns fallback",
            ),
            _row(
                "topology, support, geometry and resource proof bundles",
                _behavior_contract(
                    "vice_compiler/certificates.py",
                    ("TopologyCertificate", "SupportCertificate",
                     "GeometryCertificate", "ResourceCertificate"),
                    "test_pcdc_court.py",
                    ("test_topology_and_canvas_eraser_are_hard_certificates",
                     "test_geometry_certificate_uses_finite_sdf_bound"),
                ),
                "hard certificates are required before selection",
            ),
            _row(
                "Experiment 3 current and passing",
                bool(phase3_evidence["complete"]),
                phase3_evidence["path"], checks=phase3_evidence["checks"],
            ),
        ],
        "phase4_text": [
            _row(
                "parallel REIR-direct line proposals from all planned sources",
                _behavior_contract(
                    "vice_compiler/text_macros.py",
                    ("SWT/stroke-consistency", "component-alignment", "OCR",
                     "both-polarities", "repeated-size/stem-evidence",
                     "top-layer-clue"),
                    "test_pcdc_text.py",
                    ("test_line_proposals_are_reir_direct_bounded_and_immutable",),
                ),
                "proposal recall is a union; one source is sufficient",
            ),
            _row(
                "joint line appearance before palette commit",
                _behavior_contract(
                    "vice_compiler/text_macros.py",
                    ("JointLineAppearance", "multi_color_groups", "soft_coverage_mean"),
                    "test_pcdc_text.py",
                    ("test_spatially_disjoint_multicolour_text_preserves_fill_layers",),
                ),
                "shared/multicolour line ink reaches production text delivery",
            ),
            _row(
                "exact-font retrieval, fit, topology/silhouette wall and true outlines",
                _behavior_contract(
                    "vice_compiler/exact_font_provider.py",
                    ("retrieval_score", "silhouette_iou", "tracking_em"),
                    "test_pcdc_text.py",
                    ("test_real_exact_font_provider_reads_reir_and_passes_silhouette_wall",
                     "data-pcdc-text-geometry=\"exact-font-outline\""),
                ),
                "licensed exact font is fail-open and writer emits real outlines",
            ),
            _row(
                "font-free dual-loop/SDF program representation",
                _behavior_contract(
                    "vice_compiler/text_macros.py", (
                        "DualLoopGlyphProgram", "topology_preserving_sdf_glyph",
                        "positive_loops", "negative_loops", "topology_code",
                    ),
                    "test_pcdc_text.py",
                    ("test_sdf_dual_loop_path_preserves_components_and_counters",),
                ),
                "deterministic dual-loop representation and topology-safe "
                "fallback exist; this alone is not the trained glyph prior",
            ),
            _row(
                "trained font-free glyph prior on family-disjoint open fonts",
                glyph_prior_ready
                and _source_contract("vice_compiler/glyph_prior.py", (
                    "support_logits", "sdf", "skeleton_logits",
                    "component_logits", "hole_logits",
                    "exact-source-topology-gate",
                ))
                and _source_contract("vice_compiler/glyph_prior_data.py", (
                    "split_font_families", "glyph_observation_features",
                    "OpenFontGlyphDataset",
                ))
                and _source_contract("vice_compiler/text_macros.py", (
                    "_ocr_neural_glyph_preimage",
                    "font-free-character-conditioned-glyph-prior",
                )),
                "checkpoint is bound to the current model/data contract; "
                "compiler edits require downstream A/B, not automatic retraining",
                checks=glyph_training["checks"],
            ),
            _row(
                "trained whole-line wordmark prior without character-cell seams",
                wordmark_prior_ready
                and _source_contract("vice_compiler/wordmark_prior.py", (
                    "WordmarkPriorNet", "text_encoder", "support_logits",
                    "component_logits", "hole_logits",
                ))
                and _source_contract("vice_compiler/wordmark_prior_data.py", (
                    "OpenFontWordmarkDataset", "wordmark_data_recipe",
                    "OCR_HINT_EXACT_FRACTION", "JPEG_CORRUPTION_FRACTION",
                ))
                and _source_contract("vice_compiler/wordmark_runtime.py", (
                    "propose_wordmark_masks", "native_probability",
                    "source_edit_fraction",
                ))
                and _source_contract("vice_compiler/text_macros.py", (
                    "font-free-whole-line-wordmark-prior",
                    "no-character-cell-seams",
                )),
                "2M unique variants, 20k calibration/test families and strict "
                "topology gates",
                checks=wordmark_training["checks"],
            ),
            _row(
                "trained neural text prior changes certified delivered output",
                bool(phase4_ablation["complete"]),
                "fresh model-OFF/ON Experiment-4 ablation",
                checks=phase4_ablation["checks"],
            ),
            _row(
                "all planned font-free line variables deploy into geometry",
                bool(_font_free_line_variable_delivery_evidence()["complete"]),
                "baseline/x-height/cap-height/overshoot/slant/stems/tracking/prototypes",
                checks=_font_free_line_variable_delivery_evidence()["checks"],
            ),
            _row(
                "repeated-glyph EM is transactionally materialized",
                _behavior_contract(
                    "vice_compiler/text_macros.py",
                    ("repeated_glyph_em", "prototype.member_ids", "idealized"),
                    "test_pcdc_text.py",
                    ("test_repeated_glyph_em_is_bounded",
                     "materialize_font_free_geometry"),
                ),
                "prototype+affine instances are not metadata-only",
            ),
            _row(
                "exact-font, font-free, conservative, custom and effect TextLine macros compete",
                _behavior_contract(
                    "vice_compiler/text_macros.py",
                    ("exact-font", "font-free-dual-loop", "conservative-outline",
                     "single-custom-glyph", "knockout-text",
                     "outlined-shadowed-text-group"),
                    "test_pcdc_text.py",
                    ("test_all_text_paths_enter_cmir_and_exact_font_is_fail_open",
                     "test_compound_text_paths_remain_typed_in_design_ir"),
                ),
                "all planned text families enter the same extractor",
            ),
            _row(
                "Experiment 4 uses line-level Glyph Catastrophe Rate",
                _behavior_contract(
                    "vice_compiler/experiment4_textline.py", (
                        "_line_gcr_reduction", "candidate_catastrophic_lines",
                        "component_severity_reduction",
                    ),
                    "test_pcdc_experiment4.py", ("human", "digest"),
                ),
                "primary GCR is catastrophic-line rate; component damage is "
                "reported separately and cannot impersonate the gate",
            ),
            _row(
                "Experiment 4 current and passing",
                bool(phase4_evidence["complete"]),
                phase4_evidence["path"], checks=phase4_evidence["checks"],
            ),
        ],
        "phase5_shapes_strokes_appearance": [
            _row(
                "whole-shape typed macros reach exact SVG delivery",
                _behavior_contract(
                    "vice_compiler/shape_macros.py", ("ShapeFitRecord", "groups"),
                    "test_pcdc_phase5.py",
                    ("test_shape_fits_are_native_bounded_certified_columns",
                     "test_free_curve_control_points_change_exact_svg_delivery"),
                ),
                "analytic and free-curve programs are production-delivered",
            ),
            _row(
                "stroke graphs, dashes, markers and diagram networks",
                _behavior_contract(
                    "vice_compiler/stroke_macros.py",
                    ("StrokeGraph", "dash_pattern", "markers"),
                    "test_pcdc_phase5.py",
                    ("test_collinear_dash_train_becomes_one_measured_svg_pattern",
                     "test_arrowhead_becomes_a_native_stroke_marker",
                     "test_partitioned_frame_is_classified_as_swimlane_structure"),
                ),
                "stroke programs compete with filled regions and ship natively",
            ),
            _row(
                "solid/gradient/translucent appearance before palette commit",
                _behavior_contract(
                    "vice_compiler/appearance_macros.py",
                    ("linear_gradient", "radial_gradient", "translucent"),
                    "test_pcdc_phase5.py",
                    ("test_appearance_models_compete_without_early_palette_quantization",
                     "test_three_overlapping_alpha_shapes_generate_certified_k3_stack"),
                ),
                "appearance models and bounded K-stack are behaviorally exercised",
            ),
            _row(
                "codec/detail counterfactuals reach raster-free bounded export",
                _behavior_contract(
                    "vice_compiler/phase5_macros.py",
                    ("CodecMacroSet", "generate_cleanup_macros",
                     "codec_counterfactuals"),
                    "test_pcdc_phase5.py",
                    ("test_codec_residual_creates_fixed_posterior_counterfactuals_only",
                     "test_risk_query_adds_a_bounded_codec_locus_before_fitting"),
                ),
                "risk query proposes only; fixed-posterior court decides",
            ),
            _row(
                "repeated parameter and symmetry groups compete before selection",
                _behavior_contract(
                    "vice_compiler/shape_macros.py",
                    ("shared_parameters", "RepeatGroup"),
                    "test_pcdc_phase5.py",
                    ("test_repeated_parameter_groups_compete_before_selection",
                     "test_linear_repeat_group_exposes_deployable_shared_gap"),
                ),
                "shared parameters are deployable, not export-only metadata",
            ),
            _row(
                "Experiment 5 current and passing",
                bool(phase5_evidence["complete"]),
                phase5_evidence["path"], checks=phase5_evidence["checks"],
            ),
        ],
        "phase6_layers": [
            _row(
                "visible support is frozen before hidden completion",
                _behavior_contract(
                    "vice_compiler/layer_solver.py",
                    ("visible_scene", "hidden"),
                    "test_pcdc_phase6.py",
                    ("test_visible_ownership_is_frozen_before_typed_hidden_completion",),
                ),
                "hidden geometry cannot repair wrong visible ownership",
            ),
            _row(
                "bounded top-layer cues and acyclic layer DAG",
                _behavior_contract(
                    "vice_compiler/layer_solver.py",
                    ("LayerOrderGraph", "cycle"),
                    "test_pcdc_phase6.py",
                    ("test_confidence_weighted_order_rejects_lowest_cycle_edge",
                     "test_local_cycle_alternative_beats_greedy_edge_insertion"),
                ),
                "cycle alternatives are explicitly solved",
            ),
            _row(
                "opaque or bounded ordered translucent ownership",
                _behavior_contract(
                    "vice_compiler/appearance_macros.py",
                    ("OrderedTranslucentLayer", "stack_layers"),
                    "test_pcdc_phase5.py",
                    ("test_overlapping_alpha_shapes_form_one_bounded_ordered_stack_column",
                     "test_three_overlapping_alpha_shapes_generate_certified_k3_stack"),
                ),
                "K<=3 ordered stack is represented as one exact-cover column",
            ),
        ],
        "phase7_continuous_refinement": [
            _row(
                "common sparse group optimizer",
                _behavior_contract(
                    "vice_compiler/continuous_refine.py", (
                        "curve_control_point_SDF",
                        "curve_G1_structural+G2_curvature",
                        "pairwise_shared_interface",
                        "coverage_render_residual",
                        "stroke_width+shared_interface",
                        "text_line_grammar",
                        "appearance_color+alpha_area_residual",
                        "equal_radius_width_gap+group_ADMM_consensus",
                        "render_text_delivery", "render_stroke_delivery",
                        "render_appearance_delivery", "render_group_delivery",
                    ),
                    "test_pcdc_phase7.py",
                    ("test_common_graph_has_area_symmetry_and_pairwise_interface_factors",
                     "test_free_curve_anchors_receive_sdf_g1_g2_and_coverage_factors"),
                ) and _source_contract(
                    "vice_compiler/runtime_service.py",
                    ("phase5_bundle=phase5", "text_macros=text_macros",
                     "refined_source_id", "certify_refined"),
                ),
                "one sparse CMIR graph binds curve/G1-G2/interface, shape, "
                "stroke, text, appearance and repeat variables to exact "
                "production delivery; runtime immutable re-key and court "
                "transaction are mandatory",
            ),
            _row(
                "exact rerender and certificate rollback",
                _behavior_contract(
                    "vice_compiler/continuous_refine.py",
                    ("native_error_after", "rollback_reason"),
                    "test_pcdc_phase7.py",
                    ("test_sparse_refinement_improves_native_circle_without_discrete_changes",
                     "test_topology_certificate_violation_rolls_back_macro"),
                ),
                "continuous edits commit only after exact production rerender",
            ),
        ],
        "phase8_design_abstraction": [
            _row(
                "guarded post-selection e-graph",
                _behavior_contract(
                    "vice_compiler/abstraction_egraph.py",
                    ("budget", "render", "Repeat"),
                    "test_pcdc_phase8.py",
                    ("test_duplicate_instances_become_guarded_repeat_and_shrink_cost",
                     "test_near_circle_free_curve_is_never_an_egraph_idealization"),
                ),
                "only certified-equivalent programs are rewritten",
            ),
            _row(
                "DPIR/XIR reaches SVG, EPS, PDF, DXF and PNG adapters",
                _behavior_contract(
                    "vice_compiler/export_writer.py",
                    ("svg", "eps", "pdf", "dxf", "png"),
                    "test_pcdc_export.py",
                    ("test_all_five_targets_are_real_files_and_vector_targets_are_editable",),
                ) and _behavior_contract(
                    "vice_compiler/design_program.py", ("DesignProgram",),
                    "test_pcdc_phase8.py",
                    ("test_one_design_program_adapts_to_all_export_structures",),
                ),
                "all adapters exist; Phase-12 semantic parity is still unmeasured",
            ),
        ],
    }
    phase_status = {
        name: all(row["complete"] for row in rows)
        for name, rows in phases.items()
    }
    all_complete = all(phase_status.values())
    return {
        "schema": "pcdc-plan-traceability/v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_source_sha256": compiler_source_sha256(),
        "canonical_plan": "V-ICE_proof_carrying_design_compiler_plan_ru_v2.md",
        "audit_rule": (
            "complete requires production contract plus behavioral regression; "
            "measured gates additionally require current compiler/native hashes"
        ),
        "diagnostics": {
            "glyph_prior_training": glyph_training,
            "wordmark_prior_training": wordmark_training,
            "neural_text_runtime_ablation": phase4_ablation,
            # Retained for readers of the earlier audit schema; the evidence
            # now explicitly requires the bound whole-line wordmark SHA.
            "glyph_prior_runtime_ablation": phase4_ablation,
            "experiments": {
                "experiment1": phase1_evidence,
                "experiment1b": phase1b_evidence,
                "experiment2": phase2_evidence,
                "experiment3": phase3_evidence,
                "experiment4": phase4_evidence,
                "experiment5": phase5_evidence,
            },
        },
        "phase_status": phase_status,
        "phases": phases,
        "all_pre_phase9_requirements_complete": all_complete,
        "blocking_requirements": [
            {"phase": phase, **row}
            for phase, rows in phases.items() for row in rows
            if not row["complete"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    print(json.dumps({
        "all_pre_phase9_requirements_complete": report[
            "all_pre_phase9_requirements_complete"
        ],
        "blocking_requirements": len(report["blocking_requirements"]),
        "out": str(args.out.resolve()),
    }, indent=2, sort_keys=True))
    if not report["all_pre_phase9_requirements_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
