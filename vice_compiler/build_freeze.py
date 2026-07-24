"""Phase-11 immutable PCDC BUILD_FREEZE ledger and verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
from PIL import __version__ as pillow_version

from .build_identity import (
    PRODUCTION_EXTERNAL_MODULES,
    compiler_source_sha256,
    evaluation_source_sha256,
    native_runtime_identity,
    runtime_model_identity,
)
from .exact_font_provider import SYSTEM_FONT_CATALOG
from .experiment_inputs import (
    certificate_court_input_identity,
    font_catalog_input_identity,
    real_locus_input_identity,
)
from .glyph_prior import (
    DEFAULT_GLYPH_PRIOR_CHECKPOINT,
    DEFAULT_GLYPH_PRIOR_PROMOTION,
    validate_glyph_prior_promotion,
)
from .local_court import CourtWeights
from .runtime_service import (
    DEFAULT_PROPOSAL_CHECKPOINT,
    QUALITY_BUDGETS,
    _proposal_promotion_manifest,
    _validate_proposal_promotion,
)
from .wordmark_runtime import (
    DEFAULT_WORDMARK_PRIOR_CHECKPOINT,
    DEFAULT_WORDMARK_PRIOR_PROMOTION,
    validate_wordmark_prior_promotion,
)

PROJECT = Path(__file__).resolve().parents[1]
PLAN = Path(r"C:/Users/nirrt/Downloads/V-ICE_proof_carrying_design_compiler_plan_ru_v2.md")
DEFAULT_OUT = PROJECT / "PCDC_BUILD_FREEZE.json"
EXPERIMENTS = ("1", "1b", "2", "3", "4", "5", "9", "10")
EXPERIMENT_EVALUATORS = {
    "pcdc_experiment1": "vice_compiler/experiment1_evidence_coverage.py",
    "pcdc_experiment1b": "vice_compiler/experiment1b_pricing_recall.py",
    "pcdc_experiment2": "vice_compiler/experiment2_oracle_extraction.py",
    "pcdc_experiment3": "vice_compiler/experiment3_certificate_discrimination.py",
    "pcdc_experiment4": "vice_compiler/experiment4_textline.py",
    "pcdc_experiment5": "vice_compiler/experiment5_complexity_stress.py",
    "pcdc_experiment9": "vice_compiler/experiment9_proposal_calibration.py",
    "pcdc_experiment10": "vice_compiler/experiment10_runtime.py",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _entry(path: Path, *, relative: bool = True) -> dict[str, Any]:
    resolved = path.resolve()
    display = (
        str(resolved.relative_to(PROJECT))
        if relative and resolved.is_relative_to(PROJECT) else str(resolved)
    )
    if not resolved.is_file():
        return {"path": display, "exists": False}
    return {
        "path": display, "exists": True,
        "bytes": resolved.stat().st_size, "sha256": _sha256(resolved),
    }


def _resolve_entry(entry: dict[str, Any]) -> Path:
    path = Path(entry["path"])
    return path if path.is_absolute() else PROJECT / path


def _git(command: list[str]) -> str | None:
    try:
        row = subprocess.run(
            ["git", *command], cwd=PROJECT, capture_output=True,
            text=True, timeout=20, check=False,
        )
        return row.stdout.strip() if row.returncode == 0 else None
    except Exception:
        return None


def _runtime_thresholds() -> dict[str, Any]:
    modes = {}
    for mode, budget in QUALITY_BUDGETS.items():
        row = asdict(budget)
        row["mode"] = mode.value
        modes[mode.value] = row
    return {
        "quality_modes": modes,
        "court_weights": asdict(CourtWeights()),
        "certificate_default_boundary_tolerance_px": 2.0,
        "renderer_model_limit": 8,
        "balanced_candidate_contract": {
            "hierarchy_nodes_per_leaf": 2,
            "typed_rois": 64, "macros_per_roi_before_screening": 12,
            "exact_finalists_per_roi": 4, "exact_roi_renders": 256,
            "visible_extractions": 1, "hidden_extractions": 1,
            "final_full_renders": 1,
        },
    }


def _json_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _annotation_status() -> dict[str, Any]:
    real = json.loads((PROJECT / "datasets/pcdc_real_loci_v1/review.json").read_text("utf-8"))
    certificate = json.loads((PROJECT / "datasets/pcdc_certificate_pairs_v1/review.json").read_text("utf-8"))
    text = json.loads((PROJECT / "datasets/pcdc_textline_pairs_v1/review.json").read_text("utf-8"))
    real_rows = real["reviews"]
    cert_rows = certificate.get("answers", certificate.get("reviews", []))
    text_rows = text.get("answers", text.get("reviews", []))
    exact_text_path = PROJECT / "datasets/pcdc_textline_pairs_v2/review.json"
    exact_text = (
        json.loads(exact_text_path.read_text("utf-8"))
        if exact_text_path.is_file() else {}
    )
    exact_text_rows = exact_text.get("answers", exact_text.get("reviews", []))
    return {
        "real_loci": {
            "count": len(real_rows),
            "pending": sum(
                row.get("status") not in {"ground_truth_derived", "evidence_reviewed", "complete"}
                for row in real_rows.values()
            ),
        },
        "certificate_human_court": {"count": len(cert_rows)},
        "textline_human_court": {"count": len(text_rows)},
        "exact_textline_human_court": {
            "exists": exact_text_path.is_file(),
            "count": len(exact_text_rows),
            "required": int(exact_text.get("required", 0)),
        },
    }


def _all_entries(groups: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for value in groups.values():
        if isinstance(value, dict) and "path" in value:
            yield value
        elif isinstance(value, list):
            for row in value:
                if isinstance(row, dict) and "path" in row:
                    yield row


def _optional_entry(path: Path, *, relative: bool = True) -> dict[str, Any]:
    """Seal an optional runtime artifact, including its explicit absence."""
    row = _entry(path, relative=relative)
    row["required"] = False
    return row


def _promotion_evidence_paths(manifests: Iterable[Path]) -> tuple[Path, ...]:
    """Return every report whose digest is sealed by a promotion decision."""
    rows: dict[str, Path] = {}
    for manifest in manifests:
        if not manifest.is_file():
            continue
        try:
            payload = json.loads(manifest.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for key, value in payload.items():
            if not key.endswith("_report") or not isinstance(value, str):
                continue
            path = Path(value).expanduser().resolve()
            rows[str(path).casefold()] = path
    return tuple(rows[key] for key in sorted(rows))


def _court_asset_paths(manifests: Iterable[Path]) -> tuple[Path, ...]:
    web_root = (PROJECT / "web_preview").resolve()
    rows: dict[str, Path] = {}
    for manifest_path in manifests:
        if not manifest_path.is_file():
            continue
        payload = json.loads(manifest_path.read_text("utf-8"))
        for case in payload.get("cases", []):
            for key in ("source_url", "a_url", "b_url"):
                url = str(case.get(key, ""))
                relative = Path(url.lstrip("/"))
                resolved = (web_root / relative).resolve()
                if web_root not in resolved.parents:
                    raise ValueError(f"court asset escapes web root: {url}")
                rows[str(resolved).casefold()] = resolved
    return tuple(rows[key] for key in sorted(rows))


def _text_court_asset_errors(manifests: Iterable[Path]) -> tuple[str, ...]:
    errors = []
    web_root = (PROJECT / "web_preview").resolve()
    for manifest_path in manifests:
        if not manifest_path.is_file():
            continue
        payload = json.loads(manifest_path.read_text("utf-8"))
        schema = str(payload.get("schema", ""))
        digest_required = schema == "pcdc-textline-human-court/v2"
        for case in payload.get("cases", []):
            side = str(case.get("candidate_side", ""))
            if side not in {"A", "B"}:
                errors.append(f"{manifest_path}: invalid candidate side")
                continue
            paths = {
                name: (
                    web_root
                    / Path(str(case[f"{name.lower()}_url"]).lstrip("/"))
                ).resolve()
                for name in ("A", "B")
            }
            if not all(
                web_root in path.parents and path.is_file()
                for path in paths.values()
            ):
                errors.append(f"{manifest_path}: missing SVG for {case.get('id')}")
                continue
            candidate_sha = _sha256(paths[side])
            legacy_sha = _sha256(paths["B" if side == "A" else "A"])
            candidate_expected = case.get("candidate_svg_digest")
            legacy_expected = case.get("legacy_svg_digest")
            if digest_required and not candidate_expected:
                errors.append(
                    f"{manifest_path}: missing candidate SVG digest for "
                    f"{case.get('id')}"
                )
            elif candidate_expected and candidate_sha != candidate_expected:
                errors.append(f"{manifest_path}: candidate SVG mismatch for {case.get('id')}")
            if digest_required and not legacy_expected:
                errors.append(
                    f"{manifest_path}: missing legacy SVG digest for "
                    f"{case.get('id')}"
                )
            elif legacy_expected and legacy_sha != legacy_expected:
                errors.append(f"{manifest_path}: legacy SVG mismatch for {case.get('id')}")
    return tuple(errors)


def _seal(payload: dict[str, Any]) -> str:
    stable = {
        key: value for key, value in payload.items()
        if key not in {"created_at", "freeze_hash"}
    }
    return _json_hash(stable)


def build_freeze() -> dict[str, Any]:
    code = [
        *sorted((PROJECT / "vice_compiler").glob("*.py")),
        *PRODUCTION_EXTERNAL_MODULES,
    ]
    native = [
        PROJECT / "native/pcdc_native_core/Cargo.toml",
        PROJECT / "native/pcdc_native_core/src/lib.rs",
        PROJECT / "native/pcdc_native_core/target/release/pcdc_native_core.dll",
    ]
    annotations = [
        PROJECT / "datasets/pcdc_real_loci_v1/manifest.json",
        PROJECT / "datasets/pcdc_real_loci_v1/review.json",
        PROJECT / "datasets/pcdc_real_loci_v1/gt_derivation_report.json",
    ]
    human = [
        PROJECT / "datasets/pcdc_certificate_pairs_v1/human_manifest.json",
        PROJECT / "datasets/pcdc_certificate_pairs_v1/review.json",
        PROJECT / "datasets/pcdc_textline_pairs_v1/human_manifest.json",
        PROJECT / "datasets/pcdc_textline_pairs_v1/review.json",
        PROJECT / "datasets/pcdc_textline_pairs_v2/human_manifest.json",
        PROJECT / "datasets/pcdc_textline_pairs_v2/review.json",
    ]
    court_manifests = (human[0], human[2], human[4])
    text_court_manifests = (human[2], human[4])
    court_assets = _court_asset_paths(court_manifests)
    court_asset_errors = _text_court_asset_errors(text_court_manifests)
    reports = [
        PROJECT / "benchmarks" / f"pcdc_experiment{number}" / "report.json"
        for number in EXPERIMENTS
    ]
    source_identity = compiler_source_sha256()
    current_native_runtime = native_runtime_identity()
    current_runtime_models = runtime_model_identity()
    current_real_inputs = real_locus_input_identity(
        PROJECT / "datasets/pcdc_real_loci_v1",
    )
    current_certificate_inputs = certificate_court_input_identity(
        PROJECT / "datasets/pcdc_certificate_pairs_v1",
    )
    current_font_catalog = font_catalog_input_identity()
    current_evaluators = {
        experiment: evaluation_source_sha256(source)
        for experiment, source in EXPERIMENT_EVALUATORS.items()
    }
    stale_reports = []
    failed_reports = []
    for path in reports:
        if not path.is_file():
            continue
        try:
            report_payload = json.loads(path.read_text("utf-8"))
            report_identity = report_payload.get("compiler_source_sha256")
        except Exception:
            report_payload = {}
            report_identity = None
        external_stale = bool(
            path.parent.name == "pcdc_experiment10"
            and report_payload.get("runtime_model_identity", {}).get("sha256")
            != current_runtime_models["sha256"]
        )
        external_stale = external_stale or (
            report_payload.get("native_runtime_identity", {}).get("sha256")
            != current_native_runtime["sha256"]
        )
        external_stale = external_stale or (
            report_payload.get("evaluation_source_sha256")
            != current_evaluators[path.parent.name]
        )
        expected_inputs = (
            current_real_inputs
            if path.parent.name in {
                "pcdc_experiment1", "pcdc_experiment1b",
                "pcdc_experiment2", "pcdc_experiment4",
                "pcdc_experiment9", "pcdc_experiment10",
            }
            else current_certificate_inputs
            if path.parent.name == "pcdc_experiment3"
            else None
        )
        if expected_inputs is not None:
            external_stale = external_stale or (
                report_payload.get("input_identity", {}).get("sha256")
                != expected_inputs["sha256"]
            )
        glyph_artifact = current_runtime_models["artifacts"].get(
            f"glyph:{DEFAULT_GLYPH_PRIOR_CHECKPOINT.name}",
        )
        if path.parent.name == "pcdc_experiment4" and glyph_artifact is not None:
            external_stale = external_stale or (
                report_payload.get("glyph_prior_checkpoint", {}).get("sha256")
                != glyph_artifact["sha256"]
            )
        wordmark_artifact = current_runtime_models["artifacts"].get(
            f"wordmark:{DEFAULT_WORDMARK_PRIOR_CHECKPOINT.name}",
        )
        if path.parent.name == "pcdc_experiment4" and wordmark_artifact is not None:
            external_stale = external_stale or (
                report_payload.get("wordmark_prior_checkpoint", {}).get("sha256")
                != wordmark_artifact["sha256"]
            )
        if path.parent.name == "pcdc_experiment4":
            external_stale = external_stale or (
                report_payload.get("font_catalog_identity", {}).get("sha256")
                != current_font_catalog["sha256"]
            )
            external_stale = external_stale or (
                report_payload.get("ocr_model_identity", {}).get("sha256")
                != current_runtime_models["trocr"]["sha256"]
            )
            human_proof = report_payload.get("human", {})
            review_source = human_proof.get("review_source")
            review_path = Path(str(review_source)) if review_source else None
            manifest_path = (
                review_path.with_name("human_manifest.json")
                if review_path is not None else None
            )
            external_stale = external_stale or bool(
                review_path is None or manifest_path is None
                or not review_path.is_file() or not manifest_path.is_file()
                or human_proof.get("review_sha256") != _sha256(review_path)
                or human_proof.get("manifest_sha256") != _sha256(manifest_path)
            )
        if report_identity != source_identity or external_stale:
            stale_reports.append(str(path.relative_to(PROJECT)))
        if report_payload.get("gate_pass") is not True:
            failed_reports.append(str(path.relative_to(PROJECT)))
    proposal_manifest = _proposal_promotion_manifest(
        DEFAULT_PROPOSAL_CHECKPOINT,
    )
    proposal_runtime_error = None
    try:
        _validate_proposal_promotion(
            DEFAULT_PROPOSAL_CHECKPOINT, proposal_manifest,
        )
        proposal_runtime_enabled = True
    except Exception as error:
        proposal_runtime_enabled = False
        proposal_runtime_error = f"{type(error).__name__}: {error}"
    glyph_runtime_error = None
    try:
        validate_glyph_prior_promotion()
        glyph_runtime_enabled = True
    except Exception as error:
        glyph_runtime_enabled = False
        glyph_runtime_error = f"{type(error).__name__}: {error}"
    wordmark_runtime_error = None
    try:
        validate_wordmark_prior_promotion()
        wordmark_runtime_enabled = True
    except Exception as error:
        wordmark_runtime_enabled = False
        wordmark_runtime_error = f"{type(error).__name__}: {error}"
    promotion_evidence = _promotion_evidence_paths((
        proposal_manifest,
        DEFAULT_GLYPH_PRIOR_PROMOTION,
        DEFAULT_WORDMARK_PRIOR_PROMOTION,
    ))
    files = {
        "canonical_plan": _entry(PLAN, relative=False),
        "compiler_source": [_entry(path) for path in code],
        "native_core": [_entry(path) for path in native],
        # The checkpoint and its promotion decision are one inseparable
        # runtime artifact.  Freezing checkpoint bytes alone used to make an
        # unpromoted v1 candidate look like the production neural model even
        # though WarmProposalWorker correctly refused to load it.
        "models": [
            _entry(DEFAULT_PROPOSAL_CHECKPOINT),
            _entry(proposal_manifest),
            # The rejected per-glyph experiment is an optional proposal lane.
            # Its absent state is sealed, but it cannot be a BUILD_FREEZE
            # blocker after the required whole-line wordmark lane supersedes
            # it.  Requiring both created an impossible promotion cycle: the
            # glyph candidate changed 0/100 delivered rows and therefore could
            # never pass its own downstream-effect gate.
            _optional_entry(DEFAULT_GLYPH_PRIOR_CHECKPOINT),
            _optional_entry(DEFAULT_GLYPH_PRIOR_PROMOTION),
            _entry(DEFAULT_WORDMARK_PRIOR_CHECKPOINT),
            _entry(DEFAULT_WORDMARK_PRIOR_PROMOTION),
        ],
        "promotion_evidence": [
            _entry(path, relative=False) for path in promotion_evidence
        ],
        "ocr_model": [
            _entry(Path(row["path"]), relative=False)
            for row in current_runtime_models["trocr"]["artifacts"].values()
        ],
        # Exact-font output contains the installed outline bytes, not a live
        # <text> dependency.  Seal the complete owned retrieval bank so a
        # machine/font update cannot silently change a frozen SVG build.
        "font_catalog": [
            _entry(Path(path), relative=False)
            for _name, path in SYSTEM_FONT_CATALOG
            if Path(path).is_file()
        ],
        "real_locus_annotations": [_entry(path) for path in annotations],
        "human_court_manifests_and_answers": [_entry(path) for path in human],
        "human_court_assets": [_entry(path, relative=False) for path in court_assets],
        "canonical_experiment_reports": [_entry(path) for path in reports],
        "renderer_sources": [
            _entry(PROJECT / "vice_compiler/renderer_posterior.py"),
            _entry(PROJECT / "vice_compiler/atlas_renderer.py"),
            _entry(PROJECT / "vice_compiler/local_court.py"),
        ],
    }
    thresholds = _runtime_thresholds()
    experiment9 = json.loads(
        (PROJECT / "benchmarks/pcdc_experiment9/report.json").read_text("utf-8")
    )
    calibration = {
        "target_coverage": experiment9["conformal_target_coverage"],
        "thresholds": experiment9["conformal_thresholds"],
        "vacuous_classes": experiment9["conformal_vacuous_classes"],
        "test_coverage": experiment9["test_conformal_coverage_by_family"],
        "source_report_sha256": _sha256(
            PROJECT / "benchmarks/pcdc_experiment9/report.json"
        ),
    }
    annotation_status = _annotation_status()
    exact_text_status = annotation_status["exact_textline_human_court"]
    exact_text_complete = bool(
        exact_text_status["exists"]
        and exact_text_status["required"] > 0
        and exact_text_status["count"] >= exact_text_status["required"]
    )
    missing = [
        row["path"] for row in _all_entries(files)
        if row.get("required", True) and not row.get("exists")
    ]
    status = _git(["status", "--short"])
    payload = {
        "schema": "pcdc-build-freeze/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "record-only after BUILD_FREEZE; any source/model/config/annotation/"
            "renderer/threshold change requires a new freeze and full campaign"
        ),
        "canonical_plan_sha256": files["canonical_plan"].get("sha256"),
        "compiler_source_sha256": source_identity,
        "git": {
            "head": _git(["rev-parse", "HEAD"]), "dirty": bool(status),
            "status_sha256": _json_hash(status) if status is not None else None,
        },
        "runtime": {
            "python": sys.version, "platform": platform.platform(),
            "numpy": np.__version__, "opencv": cv2.__version__,
            "pillow": pillow_version,
        },
        "runtime_model_identity": current_runtime_models,
        "native_runtime_identity": current_native_runtime,
        "canonical_input_identities": {
            "real_locus": current_real_inputs,
            "certificate_court": current_certificate_inputs,
            "font_catalog": current_font_catalog,
        },
        "canonical_evaluation_source_sha256": current_evaluators,
        "files": files,
        "thresholds": thresholds,
        "thresholds_sha256": _json_hash(thresholds),
        "calibration": calibration,
        "proposal_runtime": {
            "enabled": proposal_runtime_enabled,
            "checkpoint": str(DEFAULT_PROPOSAL_CHECKPOINT.relative_to(PROJECT)),
            "promotion_manifest": str(proposal_manifest.relative_to(PROJECT)),
            "validation_error": proposal_runtime_error,
        },
        "glyph_prior_runtime": {
            "enabled": glyph_runtime_enabled,
            "checkpoint": str(DEFAULT_GLYPH_PRIOR_CHECKPOINT.relative_to(PROJECT)),
            "promotion_manifest": str(DEFAULT_GLYPH_PRIOR_PROMOTION.relative_to(PROJECT)),
            "validation_error": glyph_runtime_error,
        },
        "wordmark_prior_runtime": {
            "enabled": wordmark_runtime_enabled,
            "checkpoint": str(
                DEFAULT_WORDMARK_PRIOR_CHECKPOINT.relative_to(PROJECT)
            ),
            "promotion_manifest": str(
                DEFAULT_WORDMARK_PRIOR_PROMOTION.relative_to(PROJECT)
            ),
            "validation_error": wordmark_runtime_error,
        },
        "annotation_status": annotation_status,
        "complete": bool(
            not missing and not stale_reports
            and not failed_reports
            and not court_asset_errors
            and proposal_runtime_enabled and wordmark_runtime_enabled
            and current_runtime_models["trocr_mode"] == "local-pinned-snapshot"
            and annotation_status["real_loci"]["pending"] == 0
            and exact_text_complete
        ),
        "missing": missing,
        "stale_experiment_reports": stale_reports,
        "failed_experiment_reports": failed_reports,
        "human_court_asset_errors": court_asset_errors,
        "promotion_ready": False,
        "promotion_blockers": (
            "Phase-12 full campaign not frozen/passed",
            "99% conformal sets remain vacuous on the 46-locus calibration split",
            "locked blind VAI parity gate not yet passed",
            *(() if not stale_reports else (
                "foundational experiment reports are not bound to current compiler bytes",
            )),
            *(() if not failed_reports else (
                "one or more canonical experiment gates failed",
            )),
            *(() if proposal_runtime_enabled else (
                "runtime ProposalNet lacks a valid hash-bound promotion sidecar",
            )),
            *(() if wordmark_runtime_enabled else (
                "runtime wordmark prior lacks a valid hash-bound promotion manifest",
            )),
            *(() if exact_text_complete else (
                "exact/OCR/neural-text TextLine blind court is incomplete",
            )),
            *(() if not court_asset_errors else (
                "human-court SVG assets do not match their private manifests",
            )),
            *(() if current_runtime_models["trocr_mode"] == "local-pinned-snapshot" else (
                "local pinned TrOCR snapshot is unavailable",
            )),
        ),
    }
    payload["freeze_hash"] = _seal(payload)
    return payload


def verify_freeze(payload: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    errors = []
    if payload.get("schema") != "pcdc-build-freeze/v1":
        errors.append("schema mismatch")
    if payload.get("freeze_hash") != _seal(payload):
        errors.append("freeze hash mismatch")
    if payload.get("compiler_source_sha256") != compiler_source_sha256():
        errors.append("compiler source identity changed")
    for entry in _all_entries(payload.get("files", {})):
        path = _resolve_entry(entry)
        if not path.is_file():
            if entry.get("required", True):
                errors.append(f"missing: {entry['path']}")
        elif _sha256(path) != entry.get("sha256"):
            errors.append(f"changed: {entry['path']}")
    thresholds = _runtime_thresholds()
    if payload.get("thresholds_sha256") != _json_hash(thresholds):
        errors.append("runtime thresholds changed")
    try:
        current_inputs = {
            "real_locus": real_locus_input_identity(
                PROJECT / "datasets/pcdc_real_loci_v1",
            ),
            "certificate_court": certificate_court_input_identity(
                PROJECT / "datasets/pcdc_certificate_pairs_v1",
            ),
            "font_catalog": font_catalog_input_identity(),
        }
        frozen_inputs = payload.get("canonical_input_identities", {})
        for name, identity in current_inputs.items():
            if frozen_inputs.get(name, {}).get("sha256") != identity["sha256"]:
                errors.append(f"canonical experiment inputs changed: {name}")
    except Exception as error:
        errors.append(
            "canonical experiment inputs unavailable: "
            f"{type(error).__name__}: {error}"
        )
    return not errors, tuple(errors)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify is not None:
        payload = json.loads(args.verify.read_text("utf-8"))
        valid, errors = verify_freeze(payload)
        print(json.dumps({"valid": valid, "errors": errors}, indent=2))
        return int(not valid)
    payload = build_freeze()
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    print(json.dumps({
        "complete": payload["complete"], "promotion_ready": payload["promotion_ready"],
        "freeze_hash": payload["freeze_hash"], "missing": payload["missing"],
        "out": str(args.out),
    }, indent=2))
    return int(not payload["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
