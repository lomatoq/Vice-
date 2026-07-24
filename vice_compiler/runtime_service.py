"""Phase-10 persistent, bounded and anytime PCDC runtime.

One request owns one immutable REIR evidence pass.  Every later checkpoint is
a complete valid scene, so a deadline or optional-stage failure can return the
last proof-carrying result instead of a partial program.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .abstraction_egraph import GuardedAbstractionResult, guarded_abstract
from .atlas_renderer import ExactRoiAtlas
from .certificates import topology_signature
from .column_generation import run_column_generation
from .conformal import (
    ConformalCalibration,
    conformal_calibration_from_dict,
    runtime_conformal_query_set,
)
from .continuous_refine import (
    ContinuousRefinementResult,
    owner_partition_digest,
    refine_selected_scene,
)
from .design_program import DesignProgramIR, build_design_program
from .evidence_ir import EvidenceCache, RasterEvidenceIR
from .exact_font_provider import ReirExactFontProvider
from .export_writer import (
    _candidate_core_mask,
    render_svg_roundtrip,
    render_svg_roundtrip_roi,
    render_text_delivery,
    scene_to_svg,
)
from .extraction_profiles import (
    ExtractionFinalist,
    ExtractionProfile,
    FinalistPreferenceSelector,
    build_profile_finalists,
    choose_profile_finalist,
)
from .layer_solver import (
    LayeredScene,
    build_layered_scene,
    rekey_layered_scene,
)
from .legacy_best import LegacyBestResolver
from .local_refinement_lattice import (
    LocalRefinementAudit,
    materialize_local_refinements,
    remap_candidate_core_ownership,
)
from .macro_extractor import rollback_conflict_components
from .macro_ir import CandidateMacroIR, MacroCandidate, MacroKind, SceneProgram
from .macro_registry import (
    build_base_registry,
    extend_registry,
    rekey_draft_candidate,
)
from .master_constraints import MasterResourceLimits, ProductionMasterConstraints
from .master_problem import MasterSolution, initial_master_solution
from .native_core import backend_summary
from .phase5_macros import (
    Phase5Budgets,
    Phase5MacroBundle,
    generate_phase5_macros,
)
from .production_court import ProductionCourtAudit, RuntimeMacroCourt
from .proposal_net import (
    ProposalNet,
    ProposalNetConfig,
    ProposalQuery,
    reir_queries,
)
from .renderer_posterior import freeze_renderer_posterior
from .runtime_budget import StageBudget, StageProfiler
from .text_macros import (
    TextLineProposal,
    TextMacroSet,
    generate_text_macros,
    glyph_catastrophe_count,
)
from .visible_damage import (
    VisibleDamageMetrics,
    damage_regressed,
    visible_damage_metrics,
)
from .visible_scene import VisibleSceneIR, build_visible_scene

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_PROPOSAL_CHECKPOINT = PROJECT / "models" / "proposal_net_v1.pt"
REQUIRED_PROPOSAL_LABEL_CONTRACT = "pcdc-source-disjoint-svg-owner-labels/v1"
SUPPORTED_PROPOSAL_LABEL_CONTRACTS = frozenset({
    REQUIRED_PROPOSAL_LABEL_CONTRACT,
    "pcdc-explicit-owner-typed-mixed-replay-labels/v2",
    "pcdc-explicit-owner-counterfactual-mixed-replay-labels/v3",
    "pcdc-explicit-owner-counterfactual-mixed-replay-labels/v4",
})


def _runtime_conformal_calibration(manifest: dict) -> ConformalCalibration | None:
    version = str(manifest.get("label_contract_version", ""))
    payload = manifest.get("conformal_calibration")
    if version.endswith("/v4"):
        if manifest.get("conformal_admission_contract") != (
            "exact-family-prefix-rank/support-IoU>=0.50/v1"
        ):
            raise RuntimeError("v4 promotion lacks the runtime conformal contract")
        runtime_admission = manifest.get("runtime_conformal_admission") or {}
        if (
            runtime_admission.get("contract")
            != "exact-production-union+family-prefix+global-cap/v1"
            or runtime_admission.get("exact_runtime_rule") is not True
            or runtime_admission.get(
                "all_quality_modes_coverage_ge_99pct"
            ) is not True
        ):
            raise RuntimeError(
                "v4 promotion lacks passing Fast/Balanced/Max admission"
            )
        try:
            return conformal_calibration_from_dict(payload)
        except ValueError as error:
            raise RuntimeError("v4 promotion lacks valid conformal calibration") from error
    return None


def _proposal_promotion_manifest(checkpoint: Path) -> Path:
    """Return the immutable approval sidecar for a runtime checkpoint."""
    return checkpoint.with_suffix(checkpoint.suffix + ".promotion.json")


def _validate_proposal_promotion(checkpoint: Path, manifest_path: Path) -> None:
    """Fail closed unless the frozen campaign approved these exact bytes."""
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if not manifest_path.is_file():
        raise RuntimeError(
            f"unpromoted proposal checkpoint (missing {manifest_path.name})"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "pcdc-proposal-runtime-promotion/v1":
        raise RuntimeError("unsupported proposal promotion manifest schema")
    if manifest.get("promotion_ready") is not True:
        raise RuntimeError("proposal checkpoint did not pass runtime promotion")
    if manifest.get("all_promotion_gates_passed") is not True:
        raise RuntimeError("full frozen promotion gates are incomplete")
    from .build_identity import evaluation_source_sha256
    live_evaluators = {
        "experiment9_evaluation_source_sha256": evaluation_source_sha256(
            "vice_compiler/experiment9_proposal_calibration.py",
        ),
        "phase12_evaluation_source_sha256": evaluation_source_sha256(
            "vice_compiler/experiment12_full_campaign.py",
        ),
    }
    if any(manifest.get(key) != value for key, value in live_evaluators.items()):
        raise RuntimeError("proposal promotion evaluation code is stale")
    manifest_version = str(manifest.get("label_contract_version", ""))
    if manifest_version not in SUPPORTED_PROPOSAL_LABEL_CONTRACTS:
        raise RuntimeError("proposal promotion uses an unproved label contract")
    manifest_label_sha = str(manifest.get("label_contract_sha256", "")).lower()
    if len(manifest_label_sha) != 64:
        raise RuntimeError("proposal promotion lacks a label-contract checksum")
    expected = str(manifest.get("checkpoint_sha256", "")).lower()
    observed = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if expected != observed:
        raise RuntimeError("proposal promotion checksum mismatch")
    import torch
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if payload.get("label_contract_version") != manifest_version:
        raise RuntimeError("proposal checkpoint has an unproved label contract")
    if str(payload.get("label_contract_sha256", "")).lower() != manifest_label_sha:
        raise RuntimeError("proposal label-contract checksum mismatch")
    _runtime_conformal_calibration(manifest)


def _validate_proposal_candidate_evaluation(
    checkpoint: Path, manifest_path: Path,
) -> None:
    """Authorize exact candidate bytes for an explicit Phase-12 run only."""
    if not checkpoint.is_file() or not manifest_path.is_file():
        raise RuntimeError("candidate evaluation checkpoint/manifest is missing")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if manifest.get("schema") != "pcdc-proposal-candidate-evaluation/v1":
        raise RuntimeError("unsupported candidate evaluation manifest schema")
    if not (
        manifest.get("evaluation_ready") is True
        and manifest.get("large_training_gate_passed") is True
        and manifest.get("real_locus_gate_passed") is True
    ):
        raise RuntimeError("candidate has not passed pre-campaign gates")
    from .build_identity import evaluation_source_sha256
    if manifest.get(
        "experiment9_evaluation_source_sha256"
    ) != evaluation_source_sha256(
        "vice_compiler/experiment9_proposal_calibration.py",
    ):
        raise RuntimeError("candidate evaluation code is stale")
    expected = str(manifest.get("checkpoint_sha256", "")).lower()
    observed = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if expected != observed:
        raise RuntimeError("candidate evaluation checksum mismatch")
    manifest_version = str(manifest.get("label_contract_version", ""))
    manifest_label_sha = str(manifest.get("label_contract_sha256", "")).lower()
    if (
        manifest_version not in SUPPORTED_PROPOSAL_LABEL_CONTRACTS
        or len(manifest_label_sha) != 64
    ):
        raise RuntimeError("candidate evaluation has an unproved label contract")
    import torch
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if (
        payload.get("label_contract_version") != manifest_version
        or str(payload.get("label_contract_sha256", "")).lower()
        != manifest_label_sha
    ):
        raise RuntimeError("candidate evaluation label contract mismatch")
    _runtime_conformal_calibration(manifest)


class QualityMode(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    MAX = "max"

    @classmethod
    def parse(cls, value: str | "QualityMode") -> "QualityMode":
        if isinstance(value, cls):
            return value
        return cls(str(value).strip().lower())


@dataclass(frozen=True)
class QualityBudget:
    mode: QualityMode
    max_dim: int
    phase5: Phase5Budgets
    text_rois: int
    text_exact_per_line: int
    proposal_queries: int
    exact_render_limit: int
    solver_ms: float
    refine_iterations: int
    abstraction_ms: float
    use_layers: bool
    use_exact_font: bool
    minimum_typed_lower: float
    target_p50_ms: float | None
    target_p95_ms: float | None

    @property
    def typed_roi_limit(self) -> int:
        return (
            self.phase5.shape_rois + self.phase5.stroke_rois
            + self.phase5.appearance_rois + self.phase5.codec_loci
            + self.text_rois
        )

    def validate(self) -> None:
        if self.mode in {QualityMode.FAST, QualityMode.BALANCED} and self.typed_roi_limit > 64:
            raise ValueError("Fast/Balanced typed ROI budget exceeds 64")
        if self.phase5.shapes_per_roi > 4 or self.phase5.appearances_per_roi > 4:
            raise ValueError("exact finalist budget exceeds four per ROI")
        if self.exact_render_limit > 256:
            raise ValueError("exact ROI render budget exceeds 256")


QUALITY_BUDGETS: dict[QualityMode, QualityBudget] = {
    QualityMode.FAST: QualityBudget(
        mode=QualityMode.FAST, max_dim=384,
        phase5=Phase5Budgets(
            shape_rois=10, shapes_per_roi=3, stroke_rois=6,
            appearance_rois=6, appearances_per_roi=3, codec_loci=4,
        ),
        text_rois=6, text_exact_per_line=0, proposal_queries=24,
        exact_render_limit=64, solver_ms=35.0, refine_iterations=0,
        abstraction_ms=20.0, use_layers=False, use_exact_font=False,
        minimum_typed_lower=0.42, target_p50_ms=1000.0,
        target_p95_ms=2000.0,
    ),
    QualityMode.BALANCED: QualityBudget(
        mode=QualityMode.BALANCED, max_dim=512,
        phase5=Phase5Budgets(
            shape_rois=20, shapes_per_roi=4, stroke_rois=12,
            appearance_rois=12, appearances_per_roi=4, codec_loci=8,
        ),
        text_rois=12, text_exact_per_line=0, proposal_queries=48,
        exact_render_limit=192, solver_ms=100.0, refine_iterations=8,
        abstraction_ms=50.0, use_layers=True, use_exact_font=False,
        minimum_typed_lower=0.0, target_p50_ms=2000.0,
        target_p95_ms=5000.0,
    ),
    QualityMode.MAX: QualityBudget(
        mode=QualityMode.MAX, max_dim=512,
        phase5=Phase5Budgets(
            shape_rois=30, shapes_per_roi=4, stroke_rois=20,
            appearance_rois=20, appearances_per_roi=4, codec_loci=12,
        ),
        text_rois=24, text_exact_per_line=4, proposal_queries=64,
        exact_render_limit=256, solver_ms=250.0, refine_iterations=16,
        abstraction_ms=75.0, use_layers=True, use_exact_font=True,
        minimum_typed_lower=0.0, target_p50_ms=None, target_p95_ms=None,
    ),
}
for _budget in QUALITY_BUDGETS.values():
    _budget.validate()


@dataclass(frozen=True)
class AnytimeCheckpoint:
    stage: str
    elapsed_ms: float
    selected_ids: tuple[str, ...]
    utility: float
    exact_cover: bool
    proof_valid: bool
    note: str


@dataclass(frozen=True)
class TextLocusVisibleAudit:
    candidate_id: str
    line_id: str
    path: str
    source_topology: tuple[int, int]
    rendered_topology: tuple[int, int]
    baseline_topology: tuple[int, int] | None
    catastrophes: int
    baseline_catastrophes: int | None
    ink_iou: float
    baseline_ink_iou: float | None
    ink_precision: float
    ink_recall: float
    contrast: float
    regressed_vs_baseline: bool
    passed: bool
    reason: str


@dataclass(frozen=True)
class VisibleRenderAudit:
    passed: bool
    ink_iou: float
    boundary_f: float
    normalized_mae: float
    source_topology: tuple[int, int]
    rendered_topology: tuple[int, int]
    topology_error: int
    baseline_available: bool
    baseline_ink_iou: float | None
    baseline_boundary_f: float | None
    baseline_normalized_mae: float | None
    baseline_topology_error: int | None
    regressed_vs_baseline: bool
    baseline_dominates: bool
    candidate_complexity: int
    baseline_complexity: int | None
    topology_improved_vs_baseline: bool
    damage: VisibleDamageMetrics
    baseline_damage: VisibleDamageMetrics | None
    damage_regressed: bool
    text_loci: tuple[TextLocusVisibleAudit, ...]
    text_regressed: bool
    reason: str


@dataclass(frozen=True)
class VisibleRenderTransaction:
    audit: VisibleRenderAudit
    candidate_rgba: np.ndarray
    baseline_rgba: np.ndarray | None
    candidate_svg: str
    baseline_svg: str | None


@dataclass(frozen=True)
class RuntimeContractAudit:
    hierarchy_nodes: int
    hierarchy_limit: int
    typed_rois: int
    typed_roi_limit: int
    generated_typed_columns: int
    generated_column_limit: int
    exact_finalists_per_roi: int
    exact_roi_renders: int
    exact_roi_render_limit: int
    image_formation_models: int
    visible_extractions: int
    hidden_extractions: int
    final_full_renders: int
    one_reir_pass: bool
    native_backend: dict[str, object]

    def validate(self) -> None:
        if self.hierarchy_nodes > self.hierarchy_limit:
            raise ValueError("hierarchy node contract exceeded")
        if self.typed_rois > self.typed_roi_limit:
            raise ValueError("typed ROI contract exceeded")
        if self.generated_typed_columns > self.generated_column_limit:
            raise ValueError("typed column contract exceeded")
        if self.exact_finalists_per_roi > 4:
            raise ValueError("exact finalist contract exceeded")
        if self.exact_roi_renders > self.exact_roi_render_limit:
            raise ValueError("exact render contract exceeded")
        if self.image_formation_models > 8:
            raise ValueError("renderer posterior contract exceeded")
        if self.visible_extractions > 1 or self.hidden_extractions > 1:
            raise ValueError("extraction pass contract exceeded")
        if self.final_full_renders > 1 or not self.one_reir_pass:
            raise ValueError("single-pass/final-render contract exceeded")


@dataclass(frozen=True)
class RuntimeCompileResult:
    mode: QualityMode
    requested_extraction_profile: ExtractionProfile
    extraction_profile: ExtractionProfile | None
    source_path: str
    elapsed_ms: float
    deadline_ms: float | None
    deadline_exceeded: bool
    best_stage: str
    reir: RasterEvidenceIR
    cmir: CandidateMacroIR
    solution: MasterSolution
    visible_scene: VisibleSceneIR
    phase5_bundle: Phase5MacroBundle | None
    text_macros: TextMacroSet | None
    proposal_queries: tuple[ProposalQuery, ...]
    finalists: tuple[ExtractionFinalist, ...]
    layered_scene: LayeredScene | None
    refinement: ContinuousRefinementResult | None
    design_program: DesignProgramIR | None
    abstraction: GuardedAbstractionResult | None
    production_court_audit: ProductionCourtAudit | None
    local_refinement_audit: LocalRefinementAudit | None
    visible_render_audit: VisibleRenderAudit | None
    checkpoints: tuple[AnytimeCheckpoint, ...]
    contract: RuntimeContractAudit
    stage_profile: dict[str, Any]
    warnings: tuple[str, ...]

    def validate(self) -> None:
        self.reir.validate(); self.cmir.validate(); self.visible_scene.validate(self.cmir)
        self.contract.validate()
        if not self.solution.feasible or not self.solution.fallback_always_feasible:
            raise ValueError("runtime returned an infeasible checkpoint")
        if not self.checkpoints or self.checkpoints[-1].stage != self.best_stage:
            raise ValueError("best stage is not the last committed checkpoint")
        order = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}
        stages = [order[row.stage] for row in self.checkpoints]
        if stages != sorted(stages) or not all(row.proof_valid for row in self.checkpoints):
            raise ValueError("anytime checkpoint sequence is invalid")
        committed_stages = {row.stage for row in self.checkpoints}
        if "T2" in committed_stages and (
            self.extraction_profile is None
            or len(self.finalists) != 3
            or not any(row.pareto for row in self.finalists)
        ):
            raise ValueError("T2 checkpoint lacks three profiled Pareto candidates")
        if "T3" in committed_stages:
            refined_delivery = bool(
                self.refinement is not None
                and self.refinement.committed
                and self.refinement.selected_ids
                == self.visible_scene.selected_macro_ids
            )
            layered_delivery = bool(
                self.layered_scene is not None
                and self.layered_scene.hidden_completions
                and self.layered_scene.render_check.opaque_occlusion_proof
            )
            if not (refined_delivery or layered_delivery):
                raise ValueError("T3 checkpoint lacks a deployed proof-carrying change")
        if "T4" in committed_stages and (
            self.abstraction is None
            or not (
                self.abstraction.cost_after.total
                < self.abstraction.cost_before.total - 1e-9
            )
        ):
            raise ValueError("T4 checkpoint lacks a cheaper delivered XIR")

    def summary(self) -> dict[str, Any]:
        return {
            "schema": "pcdc-runtime-result/v1",
            "mode": self.mode.value, "source": self.source_path,
            "requested_extraction_profile": self.requested_extraction_profile.value,
            "extraction_profile": (
                self.extraction_profile.value
                if self.extraction_profile is not None else None
            ),
            "elapsed_ms": self.elapsed_ms, "deadline_ms": self.deadline_ms,
            "deadline_exceeded": self.deadline_exceeded,
            "best_stage": self.best_stage,
            "visible_render_audit": (
                asdict(self.visible_render_audit)
                if self.visible_render_audit is not None else None
            ),
            "local_refinement_audit": (
                asdict(self.local_refinement_audit)
                if self.local_refinement_audit is not None else None
            ),
            "selected_macros": len(self.solution.selected_ids),
            "finalists": [
                {
                    **asdict(row),
                    "profile": row.profile.value,
                }
                for row in self.finalists
            ],
            "proposal_queries": len(self.proposal_queries),
            "checkpoints": [asdict(row) for row in self.checkpoints],
            "contract": asdict(self.contract),
            "profile": self.stage_profile, "warnings": list(self.warnings),
        }


class WarmProposalWorker:
    """One checkpoint load and one warm model for all service requests."""

    def __init__(
        self, checkpoint: str | Path = DEFAULT_PROPOSAL_CHECKPOINT,
        *, promotion_manifest: str | Path | None = None,
        allow_candidate_evaluation: bool = False,
    ) -> None:
        self.checkpoint = Path(checkpoint)
        self.promotion_manifest = (
            Path(promotion_manifest) if promotion_manifest is not None
            else _proposal_promotion_manifest(self.checkpoint)
        )
        self._lock = threading.RLock()
        self.model: ProposalNet | None = None
        self.calibration: ConformalCalibration | None = None
        self.device = "unavailable"
        self.error: str | None = None
        try:
            if allow_candidate_evaluation:
                _validate_proposal_candidate_evaluation(
                    self.checkpoint, self.promotion_manifest,
                )
            else:
                _validate_proposal_promotion(
                    self.checkpoint, self.promotion_manifest,
                )
            manifest = json.loads(self.promotion_manifest.read_text("utf-8"))
            self.calibration = _runtime_conformal_calibration(manifest)
            import torch
            payload = torch.load(
                self.checkpoint, map_location="cpu", weights_only=False,
            )
            config = ProposalNetConfig(**payload["config"])
            model = ProposalNet(config)
            model.load_state_dict(payload["model"])
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = model.to(device).eval()
            with torch.inference_mode():
                model(torch.zeros((1, 4, 128, 128), device=device))
            self.model = model; self.device = str(device)
        except Exception as error:  # Neural proposals fail open to REIR queries.
            self.error = f"{type(error).__name__}: {error}"

    def infer(self, reir: RasterEvidenceIR, *, max_queries: int) -> tuple[ProposalQuery, ...]:
        classical = reir_queries(reir, max_queries=max_queries)
        if self.model is None:
            return tuple(classical[:max_queries])
        try:
            import torch
            rgba = cv2.resize(
                reir.raster.straight_rgba, (128, 128),
                interpolation=cv2.INTER_AREA,
            ).astype(np.float32)
            tensor = torch.from_numpy(np.transpose(rgba, (2, 0, 1))[None]).to(self.device)
            with self._lock, torch.inference_mode():
                neural = self.model.infer(
                    tensor, confidence_floor=0.05,
                    max_queries=min(max_queries, self.model.config.query_count),
                )[0]
            return runtime_conformal_query_set(
                classical, neural, self.calibration,
                maximum_queries=max_queries,
            )
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"
            return tuple(classical[:max_queries])


class FontGlyphCache:
    def __init__(self, *, max_entries: int = 16) -> None:
        self.max_entries = max(1, int(max_entries))
        self._rows: OrderedDict[
            tuple[str, str, int, int, bool, str], TextMacroSet
        ] = OrderedDict()
        self._lock = threading.RLock()

    def get_or_build(
        self, reir: RasterEvidenceIR, budget: QualityBudget,
        proposal_queries: tuple[ProposalQuery, ...] = (),
    ) -> tuple[TextMacroSet, bool]:
        key = (
            reir.source_sha256, reir.config_fingerprint,
            budget.text_rois, budget.text_exact_per_line,
            budget.use_exact_font,
            _proposal_queries_digest(proposal_queries),
        )
        with self._lock:
            cached = self._rows.get(key)
            if cached is not None:
                self._rows.move_to_end(key)
                return cached, True
        provider = None
        if budget.use_exact_font:
            provider = ReirExactFontProvider(
                reir, max_fonts=12, top_k=4, refine_rounds=1,
                # Max is an optional anytime lane: the valid font-free T2
                # checkpoint already exists, so a bounded 3x OCR retry may
                # recover physically tiny words without delaying Balanced.
                allow_upscale_ocr=True,
                # Canonical real-locus calibration admitted no catalog font
                # in 172 searches.  Max still buys OCR + the glyph prior;
                # exact catalog fitting remains an explicit provider feature
                # until a cheap font-identity proof can price it.
                enable_font_search=False,
            )
        generated = generate_text_macros(
            reir, exact_font_provider=provider,
            max_line_proposals=budget.text_rois,
            max_exact_per_line=max(1, budget.text_exact_per_line),
            validate_reir=False, proposal_queries=proposal_queries,
        )
        with self._lock:
            self._rows[key] = generated; self._rows.move_to_end(key)
            while len(self._rows) > self.max_entries:
                self._rows.popitem(last=False)
        return generated, False


def _proposal_queries_digest(
    proposal_queries: tuple[ProposalQuery, ...],
) -> str:
    """Bind every ProposalQuery field that can affect text macro generation."""
    digest = hashlib.sha256()

    def add_text(value: str) -> None:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)

    def add_array(value: object, dtype: np.dtype) -> None:
        array = np.ascontiguousarray(np.asarray(value, dtype=dtype))
        add_text(array.dtype.str)
        digest.update(len(array.shape).to_bytes(4, "big"))
        digest.update(np.asarray(array.shape, np.int64).tobytes())
        digest.update(array.tobytes())

    digest.update(len(proposal_queries).to_bytes(8, "big"))
    for query in proposal_queries:
        add_text(query.id)
        add_text(query.family)
        add_array(query.roi_xyxy, np.float64)
        add_array(query.soft_support, np.float32)
        add_array(query.parameters, np.float64)
        add_array(query.covariance, np.float64)
        add_array((query.confidence,), np.float64)
        digest.update(len(query.relation_tokens).to_bytes(8, "big"))
        for name, probability in query.relation_tokens:
            add_text(name)
            add_array((probability,), np.float64)
        add_array(query.topology_code, np.int64)
        add_text(query.hard_negative_class or "")
        digest.update(len(query.provenance).to_bytes(8, "big"))
        for value in query.provenance:
            add_text(value)
    return digest.hexdigest()


def _legacy_solution(cmir: CandidateMacroIR) -> MasterSolution:
    lookup = cmir.by_id(); covered = 0; utility = 0.0
    selected = cmir.legacy_ids or cmir.atomic_ids
    for candidate_id in selected:
        candidate = lookup[candidate_id]
        covered |= candidate.core_bits; utility += candidate.score_bounds.lower
    all_bits = (1 << cmir.leaf_count) - 1
    feasible = covered == all_bits
    return MasterSolution(
        selected_ids=tuple(selected), utility=utility,
        covered_bits=covered, feasible=feasible, exact_cover=feasible,
        used_atomic_fallback=not bool(cmir.legacy_ids),
        fallback_always_feasible=feasible,
        solve_ms=0.0, exact_components=0, bounded_components=0,
        fallback_reason=None if feasible else "fallback-incomplete",
    )


def _visible_metrics_from_rgba(
    reir: RasterEvidenceIR, rendered_rgba: np.ndarray,
) -> tuple[float, float, float, tuple[int, int], tuple[int, int], int]:
    rendered_rgba = np.asarray(rendered_rgba, np.float32)
    if rendered_rgba.shape != (reir.height, reir.width, 4):
        rendered_rgba = cv2.resize(
            rendered_rgba, (reir.width, reir.height),
            interpolation=cv2.INTER_AREA,
        )
    rendered_alpha = rendered_rgba[..., 3:4] / 255.0
    rendered = (
        rendered_rgba[..., :3] * rendered_alpha
        + 255.0 * (1.0 - rendered_alpha)
    )
    source_rgba = np.clip(reir.raster.straight_rgba, 0.0, 1.0) * 255.0
    source = source_rgba[..., :3] * (source_rgba[..., 3:4] / 255.0) + (
        255.0 * (1.0 - source_rgba[..., 3:4] / 255.0)
    )
    border = np.concatenate((source[0], source[-1], source[:, 0], source[:, -1]))
    background = np.median(border, axis=0)
    source_ink = np.sum(np.abs(source - background), axis=2) > 90.0
    rendered_ink = np.sum(np.abs(rendered - background), axis=2) > 90.0
    union = int(np.sum(source_ink | rendered_ink))
    ink_iou = float(np.sum(source_ink & rendered_ink) / union) if union else 1.0

    def edges(image: np.ndarray) -> np.ndarray:
        gray = np.mean(image, axis=2).astype(np.float32)
        gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
        gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
        magnitude = np.hypot(gx, gy)
        peak = float(magnitude.max())
        return magnitude >= 0.12 * peak if peak > 1e-6 else np.zeros(gray.shape, bool)

    source_edges = edges(source); rendered_edges = edges(rendered)
    if np.any(source_edges) and np.any(rendered_edges):
        to_source = cv2.distanceTransform(
            (~source_edges).astype(np.uint8), cv2.DIST_L2, 3,
        )
        to_rendered = cv2.distanceTransform(
            (~rendered_edges).astype(np.uint8), cv2.DIST_L2, 3,
        )
        precision = float(np.mean(to_source[rendered_edges] <= 1.5))
        recall = float(np.mean(to_rendered[source_edges] <= 1.5))
        boundary_f = 2.0 * precision * recall / max(1e-9, precision + recall)
    else:
        boundary_f = float(not np.any(source_edges) and not np.any(rendered_edges))
    source_topology = topology_signature(source_ink)
    rendered_topology = topology_signature(rendered_ink)
    topology_error = sum(
        abs(first - second)
        for first, second in zip(source_topology, rendered_topology)
    )
    normalized_mae = float(np.mean(np.abs(rendered - source)) / 255.0)
    return (
        ink_iou, boundary_f, normalized_mae, source_topology,
        rendered_topology, topology_error,
    )


def _visible_rgb_from_rgba(
    reir: RasterEvidenceIR, rendered_rgba: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return exact opaque candidate/source RGB at source-native resolution."""
    rgba = np.asarray(rendered_rgba, np.float32)
    if rgba.shape != (reir.height, reir.width, 4):
        rgba = cv2.resize(
            rgba, (reir.width, reir.height), interpolation=cv2.INTER_AREA,
        )
    alpha = np.clip(rgba[..., 3:4] / 255.0, 0.0, 1.0)
    rendered = rgba[..., :3] * alpha + 255.0 * (1.0 - alpha)
    source_rgba = np.clip(reir.raster.straight_rgba, 0.0, 1.0) * 255.0
    source_alpha = source_rgba[..., 3:4] / 255.0
    source = source_rgba[..., :3] * source_alpha + 255.0 * (1.0 - source_alpha)
    return (
        np.clip(np.rint(rendered), 0, 255).astype(np.uint8),
        np.clip(np.rint(source), 0, 255).astype(np.uint8),
    )


def _visible_damage_from_rgba(
    reir: RasterEvidenceIR, rendered_rgba: np.ndarray,
) -> VisibleDamageMetrics:
    rendered, source = _visible_rgb_from_rgba(reir, rendered_rgba)
    return visible_damage_metrics(rendered, source)


def _visible_metrics(
    reir: RasterEvidenceIR, svg: str,
) -> tuple[float, float, float, tuple[int, int], tuple[int, int], int]:
    return _visible_metrics_from_rgba(
        reir, render_svg_roundtrip(svg, width=reir.width),
    )


def _svg_linear_premultiplied(
    reir: RasterEvidenceIR, svg: str,
) -> np.ndarray:
    rgba = render_svg_roundtrip(svg, width=reir.width).astype(np.float32) / 255.0
    if rgba.shape[:2] != (reir.height, reir.width):
        rgba = cv2.resize(
            rgba, (reir.width, reir.height), interpolation=cv2.INTER_AREA,
        )
    alpha = np.clip(rgba[..., 3:4], 0.0, 1.0)
    rgb = np.clip(rgba[..., :3], 0.0, 1.0)
    linear = np.where(
        rgb <= 0.04045, rgb / 12.92,
        np.power((rgb + 0.055) / 1.055, 2.4),
    ).astype(np.float32)
    result = np.concatenate((linear * alpha, alpha), axis=2)
    return np.ascontiguousarray(result, np.float32)


def _svg_complexity(svg: str) -> int:
    return len(re.findall(
        r"[MLCQAZHVSTmlcqazhvst]", svg,
    )) + len(re.findall(
        r"<(?:circle|ellipse|rect|polygon|polyline|line)\b", svg,
        flags=re.IGNORECASE,
    ))


def _opaque_linear_rgb(rgba8: np.ndarray) -> np.ndarray:
    """Convert an exact renderer result to linear RGB over a white viewer."""
    rgba = np.asarray(rgba8, np.float32) / 255.0
    alpha = np.clip(rgba[..., 3:4], 0.0, 1.0)
    srgb = np.clip(rgba[..., :3], 0.0, 1.0)
    linear = np.where(
        srgb <= 0.04045, srgb / 12.92,
        np.power((srgb + 0.055) / 1.055, 2.4),
    ).astype(np.float32)
    return np.ascontiguousarray(linear * alpha + (1.0 - alpha), np.float32)


def _opaque_text_color(values: tuple[float, float, float, float]) -> np.ndarray:
    premultiplied = np.asarray(values, np.float32)
    alpha = float(np.clip(premultiplied[3], 0.0, 1.0))
    return np.clip(premultiplied[:3] + (1.0 - alpha), 0.0, 1.0)


def _text_ink_from_exact_render(
    line: TextLineProposal, rendered_linear_rgb: np.ndarray,
    *, audit_domain: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Recover visible line ink inside one certified delivery domain.

    The production writer may emit paths, exact-font silhouettes or AA edge
    pixels.  Comparing the exact final render to the line's robust foreground
    and background colors works for all three without trusting SVG markup.
    The caller must nevertheless scope that appearance test to the exact text
    delivery: a rectangular line ROI can contain unrelated scene marks whose
    color is legitimately closer to the text foreground.
    """
    reference = np.asarray(line.support_mask, bool)
    domain = np.asarray(audit_domain, bool)
    if domain.shape != reference.shape:
        raise ValueError("TextLine audit domain shape mismatch")
    foregrounds = [_opaque_text_color(line.appearance.foreground_linear_rgba)]
    foregrounds.extend(
        _opaque_text_color(color)
        for _count, color in line.appearance.multi_color_groups
    )
    background = _opaque_text_color(line.appearance.background_linear_rgba)
    contrast = max(
        float(np.linalg.norm(foreground - background))
        for foreground in foregrounds
    )
    scope = reference | domain
    if not np.any(scope):
        return np.zeros(reference.shape, bool), contrast
    ys, xs = np.nonzero(scope)
    x1 = max(0, int(xs.min()) - 1); y1 = max(0, int(ys.min()) - 1)
    x2 = min(reference.shape[1], int(xs.max()) + 2)
    y2 = min(reference.shape[0], int(ys.max()) + 2)
    local = np.asarray(rendered_linear_rgb[y1:y2, x1:x2], np.float32)
    distance_background = np.linalg.norm(
        local - background[None, None, :], axis=2,
    )
    distance_foreground = np.min(np.stack([
        np.linalg.norm(local - foreground[None, None, :], axis=2)
        for foreground in foregrounds
    ], axis=0), axis=0)
    # A nearest-appearance decision corresponds to a physical 50% coverage
    # midline for a flat foreground over its measured local background.
    local_ink = (
        distance_foreground <= distance_background
    ) & domain[y1:y2, x1:x2]
    result = np.zeros(reference.shape, bool)
    result[y1:y2, x1:x2] = local_ink
    return result, contrast


def _text_delivery_audit_domain(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR,
    candidate: MacroCandidate, text: TextMacroSet,
) -> np.ndarray:
    """Bind a full-scene text audit to certified writer bytes and ownership.

    Positive alpha says that the exact serialized TextLine can affect a pixel;
    CMIR core ownership says that the selected macro is licensed to affect it.
    Their intersection is the only scene region where color proximity may be
    attributed to this TextLine.  Missing source support remains outside the
    recovered mask and is therefore still charged through recall/topology.
    """
    delivery = render_text_delivery(reir, candidate, text)
    if delivery is None or delivery.shape != (reir.height, reir.width, 4):
        raise ValueError("TextLine has no exact delivery render")
    alpha_domain = np.asarray(delivery[..., 3], np.uint8) > 0
    ownership = np.asarray(_candidate_core_mask(reir, cmir, candidate), bool)
    if ownership.shape != alpha_domain.shape or not np.any(alpha_domain):
        raise ValueError("TextLine exact delivery domain is empty or malformed")
    if np.any(alpha_domain & ~ownership):
        raise ValueError("TextLine exact delivery exceeds certified ownership")
    domain = np.ascontiguousarray(alpha_domain & ownership, bool)
    domain.setflags(write=False)
    return domain


def _text_overlap_metrics(
    reference: np.ndarray, candidate: np.ndarray,
) -> tuple[float, float, float]:
    reference = np.asarray(reference, bool); candidate = np.asarray(candidate, bool)
    intersection = int(np.sum(reference & candidate))
    union = int(np.sum(reference | candidate))
    iou = float(intersection / union) if union else 1.0
    precision = float(intersection / max(1, int(np.sum(candidate))))
    recall = float(intersection / max(1, int(np.sum(reference))))
    return iou, precision, recall


def _audit_text_loci(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    text: TextMacroSet, candidate_rgba: np.ndarray,
    baseline_rgba: np.ndarray | None,
) -> tuple[TextLocusVisibleAudit, ...]:
    """Fail closed per selected TextLine after the one exact scene render."""
    lookup = cmir.by_id()
    records = {row.candidate.id: row for row in text.records}
    lines = {row.id: row for row in text.proposals}
    candidate_linear = _opaque_linear_rgb(candidate_rgba)
    baseline_linear = (
        _opaque_linear_rgb(baseline_rgba)
        if baseline_rgba is not None else None
    )
    rows: list[TextLocusVisibleAudit] = []
    for candidate_id in scene.selected_macro_ids:
        candidate = lookup[candidate_id]
        if candidate.kind is not MacroKind.TEXT_LINE:
            continue
        record = records.get(candidate_id)
        line = lines.get(record.line_id) if record is not None else None
        if record is None or line is None:
            rows.append(TextLocusVisibleAudit(
                candidate_id=candidate_id,
                line_id=record.line_id if record is not None else "missing",
                path=record.path if record is not None else "missing",
                source_topology=(0, 0), rendered_topology=(0, 0),
                baseline_topology=None, catastrophes=1,
                baseline_catastrophes=None, ink_iou=0.0,
                baseline_ink_iou=None, ink_precision=0.0, ink_recall=0.0,
                contrast=0.0, regressed_vs_baseline=True, passed=False,
                reason="missing-text-delivery-record",
            ))
            continue
        reference = np.asarray(line.support_mask, bool)
        try:
            audit_domain = _text_delivery_audit_domain(
                reir, cmir, candidate, text,
            )
        except Exception:
            source_topology = topology_signature(reference)
            rows.append(TextLocusVisibleAudit(
                candidate_id=candidate_id, line_id=line.id, path=record.path,
                source_topology=source_topology,
                rendered_topology=(0, 0), baseline_topology=None,
                catastrophes=max(1, sum(source_topology)),
                baseline_catastrophes=None, ink_iou=0.0,
                baseline_ink_iou=None, ink_precision=0.0, ink_recall=0.0,
                contrast=0.0, regressed_vs_baseline=True, passed=False,
                reason="invalid-text-delivery-domain",
            ))
            continue
        rendered, contrast = _text_ink_from_exact_render(
            line, candidate_linear, audit_domain=audit_domain,
        )
        iou, precision, recall = _text_overlap_metrics(reference, rendered)
        source_topology = topology_signature(reference)
        rendered_topology = topology_signature(rendered)
        catastrophes = glyph_catastrophe_count(reference, rendered)
        baseline_topology = None
        baseline_catastrophes = None
        baseline_iou = None
        if baseline_linear is not None:
            baseline, _baseline_contrast = _text_ink_from_exact_render(
                line, baseline_linear, audit_domain=audit_domain,
            )
            baseline_topology = topology_signature(baseline)
            baseline_catastrophes = glyph_catastrophe_count(reference, baseline)
            baseline_iou, _baseline_precision, _baseline_recall = (
                _text_overlap_metrics(reference, baseline)
            )
        regressed = bool(
            baseline_catastrophes is not None
            and (
                catastrophes > baseline_catastrophes
                or (
                    catastrophes == baseline_catastrophes
                    and baseline_iou is not None
                    and iou < baseline_iou - 0.15
                )
            )
        )
        failures = []
        if contrast < 0.055:
            failures.append("unverifiable-contrast")
        if catastrophes:
            failures.append("glyph-topology-catastrophe")
        if iou < 0.72 or precision < 0.72 or recall < 0.78:
            failures.append("line-support-fidelity")
        if regressed:
            failures.append("baseline-text-regression")
        passed = not failures
        rows.append(TextLocusVisibleAudit(
            candidate_id=candidate_id, line_id=line.id, path=record.path,
            source_topology=source_topology,
            rendered_topology=rendered_topology,
            baseline_topology=baseline_topology,
            catastrophes=catastrophes,
            baseline_catastrophes=baseline_catastrophes,
            ink_iou=iou, baseline_ink_iou=baseline_iou,
            ink_precision=precision, ink_recall=recall, contrast=contrast,
            regressed_vs_baseline=regressed, passed=passed,
            reason="passed" if passed else "failed:" + ",".join(failures),
        ))
    return tuple(rows)


def _make_visible_audit(
    candidate_values: tuple[
        float, float, float, tuple[int, int], tuple[int, int], int,
    ],
    *, candidate_complexity: int,
    baseline_values: tuple[
        float, float, float, tuple[int, int], tuple[int, int], int,
    ] | None,
    baseline_complexity: int | None,
    damage: VisibleDamageMetrics,
    baseline_damage: VisibleDamageMetrics | None,
    text_loci: tuple[TextLocusVisibleAudit, ...] = (),
    allow_equal_baseline_topology: bool = False,
) -> VisibleRenderAudit:
    (
        ink_iou, boundary_f, normalized_mae, source_topology,
        rendered_topology, topology_error,
    ) = candidate_values
    if baseline_values is None:
        baseline_iou = baseline_boundary = baseline_mae = None
        baseline_topology_error = None
        baseline_dominates = False
        topology_improved = False
    else:
        (
            baseline_iou, baseline_boundary, baseline_mae, _baseline_source,
            _baseline_rendered, baseline_topology_error,
        ) = baseline_values
        if baseline_complexity is None:
            raise ValueError("baseline metrics require baseline complexity")
        topology_improved = topology_error < baseline_topology_error
        no_worse = (
            baseline_topology_error <= topology_error
            and baseline_iou >= ink_iou - 0.002
            and baseline_boundary >= boundary_f - 0.002
            and baseline_mae <= normalized_mae + 0.002
            and baseline_complexity <= candidate_complexity
        )
        materially_better = (
            baseline_topology_error < topology_error
            or baseline_iou > ink_iou + 0.002
            or baseline_boundary > boundary_f + 0.002
            or baseline_mae < normalized_mae - 0.002
            or baseline_complexity < candidate_complexity
        )
        baseline_dominates = bool(no_worse and materially_better)
    topology_ok = bool(
        topology_error == 0
        or (
            baseline_topology_error is not None
            and (
                topology_error < baseline_topology_error
                or (
                    allow_equal_baseline_topology
                    and topology_error == baseline_topology_error
                )
            )
        )
    )
    fidelity_ok = bool(
        (
            ink_iou >= 0.94 and boundary_f >= 0.95
            and normalized_mae <= 0.035
        )
        or (
            topology_improved and ink_iou >= 0.80 and boundary_f >= 0.90
            and normalized_mae <= 0.08
        )
    )
    text_regressed = any(not row.passed for row in text_loci)
    structural_regression = damage_regressed(damage, baseline_damage)
    passed = bool(
        topology_ok and fidelity_ok and not baseline_dominates
        and not structural_regression and not text_regressed
    )
    failed = []
    if not topology_ok:
        failed.append("topology")
    if not fidelity_ok:
        failed.append("fidelity-wall")
    if baseline_dominates:
        failed.append("baseline-pareto-dominates")
    if structural_regression:
        failed.append("catastrophic-locus-regression")
    if text_regressed:
        failed.append("text-locus-catastrophe")
    return VisibleRenderAudit(
        passed=passed, ink_iou=ink_iou, boundary_f=boundary_f,
        normalized_mae=normalized_mae, source_topology=source_topology,
        rendered_topology=rendered_topology, topology_error=topology_error,
        baseline_available=baseline_values is not None,
        baseline_ink_iou=baseline_iou,
        baseline_boundary_f=baseline_boundary,
        baseline_normalized_mae=baseline_mae,
        baseline_topology_error=baseline_topology_error,
        regressed_vs_baseline=bool(
            baseline_dominates or structural_regression or text_regressed
        ),
        baseline_dominates=baseline_dominates,
        candidate_complexity=candidate_complexity,
        baseline_complexity=baseline_complexity,
        topology_improved_vs_baseline=topology_improved,
        damage=damage, baseline_damage=baseline_damage,
        damage_regressed=structural_regression,
        text_loci=text_loci, text_regressed=text_regressed,
        reason="passed" if passed else "failed:" + ",".join(failed),
    )


def _visible_export_transaction(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    phase5: Phase5MacroBundle, text: TextMacroSet,
    *, baseline_svg: str | None = None,
) -> VisibleRenderTransaction:
    """One candidate render, compared to evidence and the real incumbent."""
    svg, _native, _fallback = scene_to_svg(
        reir, cmir, scene, phase5_bundle=phase5, text_macros=text,
    )
    candidate_complexity = _svg_complexity(svg)
    candidate_rgba = render_svg_roundtrip(svg, width=reir.width)
    candidate_values = _visible_metrics_from_rgba(reir, candidate_rgba)

    baseline_rgba = (
        render_svg_roundtrip(baseline_svg, width=reir.width)
        if baseline_svg is not None else None
    )
    baseline_values = (
        _visible_metrics_from_rgba(reir, baseline_rgba)
        if baseline_rgba is not None else None
    )
    baseline_complexity = (
        _svg_complexity(baseline_svg) if baseline_svg is not None else None
    )
    candidate_damage = _visible_damage_from_rgba(reir, candidate_rgba)
    baseline_damage = (
        _visible_damage_from_rgba(reir, baseline_rgba)
        if baseline_rgba is not None else None
    )
    text_loci = _audit_text_loci(
        reir, cmir, scene, text, candidate_rgba, baseline_rgba,
    )
    audit = _make_visible_audit(
        candidate_values, candidate_complexity=candidate_complexity,
        baseline_values=baseline_values,
        baseline_complexity=baseline_complexity,
        damage=candidate_damage, baseline_damage=baseline_damage,
        text_loci=text_loci,
    )
    candidate_rgba = np.ascontiguousarray(candidate_rgba, np.uint8)
    candidate_rgba.setflags(write=False)
    if baseline_rgba is not None:
        baseline_rgba = np.ascontiguousarray(baseline_rgba, np.uint8)
        baseline_rgba.setflags(write=False)
    return VisibleRenderTransaction(
        audit=audit, candidate_rgba=candidate_rgba,
        baseline_rgba=baseline_rgba, candidate_svg=svg,
        baseline_svg=baseline_svg,
    )


def _audit_cached_component_rollback(
    reir: RasterEvidenceIR, transaction: VisibleRenderTransaction,
    rollback_mask: np.ndarray, recovered_svg: str,
    cmir: CandidateMacroIR, recovered_scene: VisibleSceneIR,
    text: TextMacroSet,
) -> VisibleRenderTransaction:
    """Audit a rollback using the one cached exact full-scene transaction."""
    if transaction.baseline_rgba is None or transaction.baseline_svg is None:
        raise ValueError("component rollback requires an exact incumbent render")
    mask = np.asarray(rollback_mask, bool)
    if mask.shape != (reir.height, reir.width):
        raise ValueError("component rollback mask shape mismatch")
    recovered = np.asarray(transaction.candidate_rgba, np.uint8).copy()
    recovered[mask] = transaction.baseline_rgba[mask]
    text_loci = _audit_text_loci(
        reir, cmir, recovered_scene, text, recovered,
        transaction.baseline_rgba,
    )
    audit = _make_visible_audit(
        _visible_metrics_from_rgba(reir, recovered),
        candidate_complexity=_svg_complexity(recovered_svg),
        baseline_values=_visible_metrics_from_rgba(
            reir, transaction.baseline_rgba,
        ),
        baseline_complexity=_svg_complexity(transaction.baseline_svg),
        damage=_visible_damage_from_rgba(reir, recovered),
        baseline_damage=_visible_damage_from_rgba(
            reir, transaction.baseline_rgba,
        ),
        text_loci=text_loci,
    )
    audit = replace(
        audit,
        reason=(
            "passed:cached-exact-marginal-component-rollback"
            if audit.passed else audit.reason
            + ",cached-exact-marginal-component-rollback"
        ),
    )
    recovered = np.ascontiguousarray(recovered, np.uint8)
    recovered.setflags(write=False)
    return VisibleRenderTransaction(
        audit=audit, candidate_rgba=recovered,
        baseline_rgba=transaction.baseline_rgba,
        candidate_svg=recovered_svg, baseline_svg=transaction.baseline_svg,
    )


def _audit_cached_exact_roi_update(
    reir: RasterEvidenceIR, transaction: VisibleRenderTransaction,
    changed_mask: np.ndarray, candidate_svg: str,
    cmir: CandidateMacroIR, scene: VisibleSceneIR, text: TextMacroSet,
) -> VisibleRenderAudit:
    """Verify T3 by exact ROI rerender over the one cached T2 full render."""
    mask = np.asarray(changed_mask, bool)
    if mask.shape != (reir.height, reir.width) or not np.any(mask):
        raise ValueError("T3 exact recheck requires a non-empty native ROI")
    ys, xs = np.nonzero(mask)
    # Include the complete antialias footprint while keeping the rerender
    # bounded.  Any analytic extension is already part of the court rollback
    # mask and hidden completions contribute their full masks below.
    x1 = max(0, int(xs.min()) - 2); y1 = max(0, int(ys.min()) - 2)
    x2 = min(reir.width, int(xs.max()) + 3)
    y2 = min(reir.height, int(ys.max()) + 3)
    patch = render_svg_roundtrip_roi(
        candidate_svg, roi_xyxy=(x1, y1, x2, y2),
    )
    recovered = np.asarray(transaction.candidate_rgba, np.uint8).copy()
    # resvg may quantize antialias coverage a few levels differently when a
    # document is tiled.  Only the certified changed support (plus its AA
    # footprint) is allowed to replace the cached full render; unrelated
    # boundaries inside the bounding box stay byte-identical to T2.
    changed = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    local_changed = changed[y1:y2, x1:x2]
    recovered_patch = recovered[y1:y2, x1:x2]
    recovered_patch[local_changed] = patch[local_changed]
    text_loci = _audit_text_loci(
        reir, cmir, scene, text, recovered, transaction.candidate_rgba,
    )
    audit = _make_visible_audit(
        _visible_metrics_from_rgba(reir, recovered),
        candidate_complexity=_svg_complexity(candidate_svg),
        baseline_values=_visible_metrics_from_rgba(
            reir, transaction.candidate_rgba,
        ),
        baseline_complexity=_svg_complexity(transaction.candidate_svg),
        damage=_visible_damage_from_rgba(reir, recovered),
        baseline_damage=_visible_damage_from_rgba(
            reir, transaction.candidate_rgba,
        ),
        text_loci=text_loci, allow_equal_baseline_topology=True,
    )
    return replace(
        audit,
        reason=(
            "passed:cached-T2+exact-T3-ROI-recheck"
            if audit.passed else audit.reason + ",exact-T3-ROI-recheck"
        ),
    )


class PersistentCompilerService:
    def __init__(
        self, *, evidence_cache: EvidenceCache | None = None,
        proposal_checkpoint: str | Path = DEFAULT_PROPOSAL_CHECKPOINT,
        proposal_promotion_manifest: str | Path | None = None,
        allow_candidate_evaluation: bool = False,
        legacy_resolver: LegacyBestResolver | None = None,
        finalist_preference_selector: FinalistPreferenceSelector | None = None,
        cpu_workers: int = 4, recycle_after: int = 64,
    ) -> None:
        self.evidence_cache = evidence_cache or EvidenceCache()
        self.legacy_resolver = legacy_resolver or LegacyBestResolver()
        self.finalist_preference_selector = finalist_preference_selector
        self.proposal_worker = WarmProposalWorker(
            proposal_checkpoint,
            promotion_manifest=proposal_promotion_manifest,
            allow_candidate_evaluation=allow_candidate_evaluation,
        )
        self.font_cache = FontGlyphCache()
        self.atlas = ExactRoiAtlas(max_requests=256)
        self.cpu_workers = max(1, min(8, int(cpu_workers)))
        self.recycle_after = max(1, int(recycle_after))
        self._pool = ThreadPoolExecutor(
            max_workers=self.cpu_workers, thread_name_prefix="pcdc-runtime",
        )
        self._proposal_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="pcdc-proposal",
        )
        self._request_count = 0
        self._lock = threading.RLock()
        self._closed = False

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            cpu = self._pool; proposal = self._proposal_pool
        cpu.shutdown(wait=True, cancel_futures=False)
        proposal.shutdown(wait=True, cancel_futures=False)

    def __enter__(self) -> "PersistentCompilerService":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _recycle_if_needed(self) -> None:
        with self._lock:
            self._request_count += 1
            if self._request_count < self.recycle_after or self._closed:
                return
            old = self._pool
            self._pool = ThreadPoolExecutor(
                max_workers=self.cpu_workers, thread_name_prefix="pcdc-runtime",
            )
            self._request_count = 0
        old.shutdown(wait=False, cancel_futures=False)

    def compile(
        self, path: str | Path, *, mode: str | QualityMode = QualityMode.BALANCED,
        profile: str | ExtractionProfile = ExtractionProfile.BALANCED,
        deadline_ms: float | None = None,
    ) -> RuntimeCompileResult:
        with self._lock:
            if self._closed:
                raise RuntimeError("compiler service is closed")
            pool = self._pool
        future = pool.submit(
            self._compile_request, Path(path), QualityMode.parse(mode),
            ExtractionProfile.parse(profile), deadline_ms,
        )
        try:
            result = future.result()
        finally:
            self._recycle_if_needed()
        return result

    def _compile_request(
        self, path: Path, mode: QualityMode,
        extraction_profile: ExtractionProfile,
        deadline_ms: float | None,
    ) -> RuntimeCompileResult:
        budget = QUALITY_BUDGETS[mode]; budget.validate()
        delivered_profile: ExtractionProfile | None = None
        started = time.perf_counter()
        deadline = (
            None if deadline_ms is None
            else started + max(0.0, float(deadline_ms)) / 1000.0
        )
        profiler = StageProfiler({
            "evidence": StageBudget(350.0 if mode is not QualityMode.FAST else 260.0),
            "visible_extract": StageBudget(budget.solver_ms * 1.15),
        })
        warnings: list[str] = []
        checkpoints: list[AnytimeCheckpoint] = []

        def elapsed() -> float:
            return (time.perf_counter() - started) * 1000.0

        def out_of_time() -> bool:
            return deadline is not None and time.perf_counter() >= deadline

        def commit(stage: str, solution: MasterSolution, note: str) -> VisibleSceneIR:
            scene = build_visible_scene(cmir_holder[0], solution)
            checkpoints.append(AnytimeCheckpoint(
                stage=stage, elapsed_ms=elapsed(),
                selected_ids=solution.selected_ids, utility=solution.utility,
                exact_cover=solution.exact_cover, proof_valid=True, note=note,
            ))
            return scene

        with profiler.stage("evidence", mode=mode.value):
            reir, cache_hit = self.evidence_cache.get_or_build(
                path, max_dim=budget.max_dim,
            )
        # Neural inference begins as soon as the immutable evidence IR exists;
        # legacy resolution and base-master construction proceed in parallel.
        # Queries are consumed before fitting, never as an after-the-fact log.
        proposal_future: Future[tuple[ProposalQuery, ...]] = self._proposal_pool.submit(
            self.proposal_worker.infer, reir, max_queries=budget.proposal_queries,
        )
        with profiler.stage("legacy_resolve"):
            legacy_artifact = self.legacy_resolver.resolve(path, reir)
        with profiler.stage("base_registry"):
            base_cmir = build_base_registry(
                reir, legacy_artifact=legacy_artifact,
            )
        cmir_holder = [base_cmir]
        fallback_solution = _legacy_solution(base_cmir)
        if not fallback_solution.feasible:
            raise RuntimeError("mandatory legacy T0 fallback is infeasible")
        fallback_scene = build_visible_scene(base_cmir, fallback_solution)
        solution = fallback_solution
        scene = commit(
            "T0", solution,
            "real V-ICE Best fallback available" if legacy_artifact is not None
            else "atomic fallback available; no frozen legacy artifact",
        )
        baseline_svg = None
        if legacy_artifact is not None:
            baseline_svg, _legacy_native, _legacy_paths = scene_to_svg(
                reir, base_cmir, fallback_scene,
            )
            warnings.append(f"V-ICE Best fallback={legacy_artifact.path}")
        else:
            warnings.append("V-ICE Best fallback unavailable for this source")

        with profiler.stage("hierarchy_solution"):
            hierarchy_solution = initial_master_solution(base_cmir, reir.hierarchy)
        if legacy_artifact is None:
            solution = hierarchy_solution
            scene = commit("T1", solution, "laminar hierarchy solution")
            baseline_svg, _base_native, _base_paths = scene_to_svg(
                reir, base_cmir, scene,
            )
        try:
            queries = proposal_future.result(
                timeout=0.001 if out_of_time() else None,
            )
        except Exception as error:
            warnings.append(
                f"proposal worker failed open: {type(error).__name__}: {error}"
            )
            queries = reir_queries(reir, max_queries=budget.proposal_queries)
        warnings.append(
            f"proposal queries consumed before fit={len(queries)}; "
            f"neural worker={self.proposal_worker.error or 'ready'}"
        )
        phase5_bundle: Phase5MacroBundle | None = None
        text_macros: TextMacroSet | None = None
        finalists: tuple[ExtractionFinalist, ...] = ()
        production_court_audit: ProductionCourtAudit | None = None
        local_refinement_audit: LocalRefinementAudit | None = None
        layered: LayeredScene | None = None
        refinement: ContinuousRefinementResult | None = None
        design: DesignProgramIR | None = None
        abstraction: GuardedAbstractionResult | None = None
        visible_render_audit: VisibleRenderAudit | None = None
        visible_transaction: VisibleRenderTransaction | None = None
        visible_extractions = hidden_extractions = final_renders = 0
        rollback_solution = solution
        rollback_scene = scene

        if not out_of_time():
            try:
                with profiler.stage("typed_macro_generation"):
                    text_macros, font_hit = self.font_cache.get_or_build(
                        reir, budget, proposal_queries=tuple(queries),
                    )
                    protected_text_masks = tuple(
                        row.support_mask for row in text_macros.proposals
                        if row.polarity != "native-ink-coverage"
                        and row.score >= 0.65 and len(row.glyphs) >= 2
                    )
                    phase5_bundle = generate_phase5_macros(
                        reir, budget=budget.phase5, parallel=True,
                        validate_reir=False, proposal_queries=tuple(queries),
                        protected_text_masks=protected_text_masks,
                    )
                warnings.append(f"font/glyph cache hit={font_hit}")
                additions: tuple[MacroCandidate, ...] = (
                    phase5_bundle.candidates
                    + tuple(row.candidate for row in text_macros.records)
                )
                # Occlusion-complete carriers participate only through their
                # certified visible support here.  Full geometry is still
                # gated downstream by the layer DAG + opaque-occluder proof.
                if budget.minimum_typed_lower > 0:
                    additions = tuple(
                        row for row in additions
                        if row.score_bounds.lower >= budget.minimum_typed_lower
                    )
                if baseline_svg is None:
                    raise RuntimeError("local court has no incumbent scene render")
                incumbent_render = _svg_linear_premultiplied(reir, baseline_svg)
                court = RuntimeMacroCourt(
                    reir, phase5_bundle, text_macros, atlas=self.atlas,
                    exact_request_limit=budget.exact_render_limit,
                    fallback_premultiplied_linear_rgba=incumbent_render,
                )
                resource_scale = {
                    QualityMode.FAST: 2,
                    QualityMode.BALANCED: 4,
                    QualityMode.MAX: 8,
                }[mode]
                master_constraints = ProductionMasterConstraints.from_phase5(
                    phase5_bundle,
                    limits=MasterResourceLimits(
                        fitting_ms={
                            QualityMode.FAST: 24.0,
                            QualityMode.BALANCED: 96.0,
                            QualityMode.MAX: 256.0,
                        }[mode],
                        render_pixels=(
                            reir.width * reir.height * resource_scale
                        ),
                        memory_bytes={
                            QualityMode.FAST: 16 << 20,
                            QualityMode.BALANCED: 48 << 20,
                            QualityMode.MAX: 128 << 20,
                        }[mode],
                        solver_variables={
                            QualityMode.FAST: 512,
                            QualityMode.BALANCED: 2048,
                            QualityMode.MAX: 8192,
                        }[mode],
                    ),
                )
                def production_selection_constraint(
                    selected: tuple[MacroCandidate, ...],
                    candidate: MacroCandidate,
                ) -> bool:
                    return (
                        master_constraints(selected, candidate)
                        and court.selection_compatible(selected, candidate)
                    )
                pricing_rounds = {
                    QualityMode.FAST: 2,
                    QualityMode.BALANCED: 3,
                    QualityMode.MAX: 4,
                }[mode]
                with profiler.stage("dual_pricing_and_local_court"):
                    column_result = run_column_generation(
                        reir, rounds=pricing_rounds,
                        max_columns_per_oracle=12,
                        extraction_budget_ms=budget.solver_ms,
                        exact_component_limit=18,
                        base_cmir=base_cmir,
                        candidate_pool=additions,
                        admit_candidate=court.certify,
                        allow_support_qualification=False,
                        require_proofs=True,
                        selection_constraint=production_selection_constraint,
                    )
                production_court_audit = court.audit()
                warnings.append(
                    "production local court: "
                    f"considered={production_court_audit.considered}, "
                    f"certified={production_court_audit.certified}, "
                    f"rejected={production_court_audit.rejected}, "
                    f"exact-renders={production_court_audit.exact_render_requests}"
                )
                if column_result.final_columns == column_result.initial_columns:
                    warnings.append("T2 skipped: no typed macro won its local court")
                    raise RuntimeError("no-certified-improving-typed-column")
                refinement_cells = {
                    QualityMode.FAST: 256,
                    QualityMode.BALANCED: 512,
                    QualityMode.MAX: 768,
                }[mode]
                refinement_lattice = materialize_local_refinements(
                    reir, column_result.cmir, court,
                    maximum_cells=refinement_cells,
                )
                cmir_holder[0] = refinement_lattice.cmir
                local_refinement_audit = refinement_lattice.audit
                warnings.append(
                    "local cell refinement: "
                    f"planned={local_refinement_audit.planned_candidates}, "
                    f"materialized={len(local_refinement_audit.materialized_candidate_ids)}, "
                    f"cells={local_refinement_audit.initial_cells}->"
                    f"{local_refinement_audit.final_cells}"
                )
                with profiler.stage("pareto_profile_extraction"):
                    finalists = build_profile_finalists(
                        cmir_holder[0], reir.hierarchy,
                        marginals=production_court_audit.marginals,
                        exact_component_limit=18,
                        time_budget_ms=budget.solver_ms,
                        selection_constraint=production_selection_constraint,
                        balanced_solution=(
                            column_result.solution
                            if not local_refinement_audit.materialized_candidate_ids
                            else None
                        ),
                    )
                    chosen_finalist = choose_profile_finalist(
                        finalists, extraction_profile,
                        selector=self.finalist_preference_selector,
                    )
                    typed_solution = chosen_finalist.solution
                warnings.append(
                    "Pareto extraction profiles="
                    + ",".join(
                        f"{row.profile.value}:{'P' if row.pareto else 'D'}:"
                        f"typed={row.typed_macros}"
                        for row in finalists
                    )
                    + f"; selected={chosen_finalist.profile.value}"
                )
                if not any(
                    not cmir_holder[0].by_id()[candidate_id].is_base
                    for candidate_id in typed_solution.selected_ids
                ):
                    raise RuntimeError(
                        "selected Pareto profile contains no typed macro"
                    )
                visible_extractions = 1
                typed_scene = build_visible_scene(cmir_holder[0], typed_solution)
                with profiler.stage("visible_full_render_court"):
                    visible_transaction = _visible_export_transaction(
                        reir, cmir_holder[0], typed_scene,
                        phase5_bundle, text_macros,
                        baseline_svg=baseline_svg,
                    )
                    visible_render_audit = visible_transaction.audit
                    final_renders = 1
                if not visible_render_audit.passed:
                    selected_typed_count = sum(
                        not cmir_holder[0].by_id()[candidate_id].is_base
                        for candidate_id in typed_solution.selected_ids
                    )
                    selected_typed_summary = ",".join(
                        (
                            cmir_holder[0].by_id()[candidate_id].program.operator
                            + "@" + str(cmir_holder[0].by_id()[candidate_id].roi_xyxy)
                        )
                        for candidate_id in typed_solution.selected_ids
                        if not cmir_holder[0].by_id()[candidate_id].is_base
                    )
                    warnings.append(
                        "T2 full-render court rejected typed scene: "
                        + visible_render_audit.reason
                        + (
                            f"; ink_iou={visible_render_audit.ink_iou:.5f}"
                            f"; boundary_f={visible_render_audit.boundary_f:.5f}"
                            f"; mae={visible_render_audit.normalized_mae:.5f}"
                            f"; topology_error={visible_render_audit.topology_error}"
                            f"; baseline_topology_error="
                            f"{visible_render_audit.baseline_topology_error}"
                            f"; baseline_iou={visible_render_audit.baseline_ink_iou}"
                            f"; selected_typed={selected_typed_count}"
                            f"; operators={selected_typed_summary}"
                        )
                    )
                    selected_typed_ids = tuple(
                        candidate_id for candidate_id in typed_solution.selected_ids
                        if not cmir_holder[0].by_id()[candidate_id].is_base
                    )
                    blame_order = court.marginal_blame_order(
                        selected_typed_ids,
                        topology_regressed=(
                            visible_render_audit.baseline_topology_error is not None
                            and visible_render_audit.topology_error
                            > visible_render_audit.baseline_topology_error
                        ),
                        support_regressed=(
                            visible_render_audit.baseline_ink_iou is not None
                            and visible_render_audit.ink_iou
                            < visible_render_audit.baseline_ink_iou - 0.002
                        ),
                        pixels_regressed=(
                            visible_render_audit.baseline_normalized_mae is not None
                            and visible_render_audit.normalized_mae
                            > visible_render_audit.baseline_normalized_mae + 0.002
                        ),
                        complexity_regressed=(
                            visible_render_audit.baseline_complexity is not None
                            and visible_render_audit.candidate_complexity
                            > visible_render_audit.baseline_complexity
                        ),
                    )
                    recovered = False
                    if visible_transaction is not None:
                        for count in range(1, len(blame_order) + 1):
                            closure = court.rollback_closure(
                                selected_typed_ids, blame_order[:count],
                            )
                            rollback = rollback_conflict_components(
                                cmir_holder[0], reir.hierarchy, typed_solution,
                                closure, require_proofs=True,
                                selection_constraint=production_selection_constraint,
                            )
                            retained = set(rollback.retained_typed_ids)
                            removed = tuple(
                                candidate_id for candidate_id in selected_typed_ids
                                if candidate_id not in retained
                            )
                            if not removed or not retained:
                                continue
                            rollback_mask = np.zeros(
                                (reir.height, reir.width), bool,
                            )
                            for candidate_id in removed:
                                mask = court.rollback_mask(candidate_id)
                                if mask is None:
                                    rollback_mask[:] = True
                                    break
                                rollback_mask |= mask
                            recovered_scene = build_visible_scene(
                                cmir_holder[0], rollback.solution,
                            )
                            recovered_svg, _native, _fallback = scene_to_svg(
                                reir, cmir_holder[0], recovered_scene,
                                phase5_bundle=phase5_bundle,
                                text_macros=text_macros,
                            )
                            recovered_transaction = _audit_cached_component_rollback(
                                reir, visible_transaction, rollback_mask,
                                recovered_svg, cmir_holder[0], recovered_scene,
                                text_macros,
                            )
                            recovered_audit = recovered_transaction.audit
                            if not recovered_audit.passed:
                                continue
                            solution = rollback.solution
                            delivered_profile = chosen_finalist.profile
                            visible_render_audit = recovered_audit
                            visible_transaction = recovered_transaction
                            scene = commit(
                                "T2", solution,
                                "cached marginal blame rolled back "
                                f"{len(removed)} macro(s) in "
                                f"{rollback.affected_components} affected "
                                "conflict component(s)",
                            )
                            warnings.append(
                                "T2 recovered by marginal component rollback: "
                                f"removed={','.join(removed)}; "
                                f"retained={len(retained)}"
                            )
                            recovered = True
                            break
                    if not recovered:
                        cmir_holder[0] = base_cmir
                        solution = rollback_solution
                        scene = rollback_scene
                else:
                    solution = typed_solution
                    delivered_profile = chosen_finalist.profile
                    scene = commit(
                        "T2", solution,
                        "typed macros passed exact visible full-render court",
                    )
            except Exception as error:
                warnings.append(
                    f"T2 failed open to safe fallback: {type(error).__name__}: {error}"
                )
                cmir_holder[0] = base_cmir
                solution = rollback_solution
                scene = rollback_scene

        if budget.use_layers and checkpoints[-1].stage == "T2" and not out_of_time():
            try:
                with profiler.stage("layers_and_refinement"):
                    hidden_extractions = 1
                    layered = build_layered_scene(reir, cmir_holder[0], scene)
                    proposed_refinement = refine_selected_scene(
                        reir, cmir_holder[0], scene, layered=layered,
                        max_iterations=budget.refine_iterations,
                        samples_per_shape=64,
                        phase5_bundle=phase5_bundle,
                        text_macros=text_macros,
                    )
                    lookup = cmir_holder[0].by_id()
                    selected_typed = {
                        candidate_id: lookup[candidate_id]
                        for candidate_id in solution.selected_ids
                        if not lookup[candidate_id].is_base
                    }
                    replacements: dict[str, MacroCandidate] = {}
                    rejected_refinements: dict[str, str] = {}
                    hidden_carriers = {
                        row.source_macro_id
                        for row in layered.hidden_completions
                    }
                    for row in proposed_refinement.macros:
                        source = selected_typed.get(row.macro_id)
                        if (
                            source is None or not row.committed
                            or row.refined_program == row.original_program
                        ):
                            continue
                        if source.id in hidden_carriers:
                            rejected_refinements[source.id] = (
                                "refined-hidden-carrier-needs-fresh-layer-court"
                            )
                            continue
                        refined_parameters = tuple(
                            (name, value)
                            for name, value in row.refined_program.parameters
                            if name != "refined_source_id"
                        ) + (("refined_source_id", source.id),)
                        draft = replace(
                            source, id="", registry_index=-1, conflict_bits=0,
                            proof_bundle=None, program=SceneProgram(
                                row.refined_program.operator,
                                refined_parameters,
                            ),
                            continuous_params=row.refined_params,
                            covariance=row.covariance,
                            provenance=(
                                *source.provenance,
                                "sparse-continuous-refinement",
                                "pending-production-recourt",
                            ),
                        )
                        draft = rekey_draft_candidate(
                            draft, prefix="refined-continuous",
                        )
                        if draft.id == source.id:
                            rejected_refinements[source.id] = "immutable-id-unchanged"
                            continue
                        certified = court.certify_refined(source.id, draft)
                        if certified is None:
                            rejected_refinements[source.id] = "production-court-rejected"
                            continue
                        if (
                            local_refinement_audit is not None
                            and local_refinement_audit.materialized_candidate_ids
                        ):
                            # Continuous refinement freezes discrete ownership;
                            # bind the fresh geometry proof to the already
                            # materialized child cells before registry entry.
                            certified = remap_candidate_core_ownership(
                                certified, source.core_bits, refined=True,
                            )
                        trial = dict(selected_typed)
                        trial.update(replacements)
                        trial[source.id] = certified
                        trial_rows = tuple(sorted(
                            trial.values(), key=lambda candidate: candidate.id,
                        ))
                        prefix: tuple[MacroCandidate, ...] = ()
                        compatible = True
                        for candidate in trial_rows:
                            if not production_selection_constraint(prefix, candidate):
                                compatible = False
                                break
                            prefix = (*prefix, candidate)
                        if not compatible:
                            rejected_refinements[source.id] = (
                                "global-proof-or-delivery-conflict"
                            )
                            continue
                        replacements[source.id] = certified

                    production_court_audit = court.audit()
                    trial_cmir = None
                    trial_solution = None
                    trial_scene = None
                    trial_layered = None
                    if replacements:
                        if visible_transaction is None:
                            raise RuntimeError(
                                "T3 refinement lacks the cached T2 exact transaction"
                            )
                        trial_cmir = extend_registry(
                            reir, cmir_holder[0], replacements.values(),
                        )
                        trial_id_map = {
                            source_id: candidate.id
                            for source_id, candidate in replacements.items()
                        }
                        trial_selected_ids = tuple(
                            trial_id_map.get(candidate_id, candidate_id)
                            for candidate_id in solution.selected_ids
                        )
                        trial_solution = replace(
                            solution, selected_ids=trial_selected_ids,
                        )
                        trial_scene = build_visible_scene(
                            trial_cmir, trial_solution,
                        )
                        trial_layered = rekey_layered_scene(
                            reir, trial_cmir, layered, trial_scene, trial_id_map,
                        )
                        # Re-render only the exact native region touched by the
                        # refined deliveries.  The unchanged pixels come from
                        # the one cached T2 full-scene transaction, preserving
                        # the plan's <=1 final full-render contract.
                        changed = np.zeros((reir.height, reir.width), bool)
                        for replacement in replacements.values():
                            mask = court.rollback_mask(replacement.id)
                            if mask is None:
                                changed[:] = True
                                break
                            changed |= mask
                        trial_svg, _trial_native, _trial_fallback = scene_to_svg(
                            reir, trial_cmir, trial_scene,
                            phase5_bundle=phase5_bundle,
                            text_macros=text_macros,
                        )
                        t3_audit = _audit_cached_exact_roi_update(
                            reir, visible_transaction, changed, trial_svg,
                            trial_cmir, trial_scene, text_macros,
                        )
                        if not t3_audit.passed:
                            for source_id in replacements:
                                rejected_refinements[source_id] = (
                                    "exact-T3-ROI-visible-regression"
                                )
                            warnings.append(
                                "T3 exact ROI transaction rejected refinements: "
                                + t3_audit.reason
                                + f"; topology_error={t3_audit.topology_error}"
                                + "; baseline_topology_error="
                                + f"{t3_audit.baseline_topology_error}"
                                + f"; loci={t3_audit.damage.catastrophic_locus_count}"
                                + f"->{t3_audit.baseline_damage.catastrophic_locus_count}"
                            )
                            replacements = {}
                        else:
                            visible_render_audit = t3_audit
                    if replacements:
                        if (
                            trial_cmir is None or trial_solution is None
                            or trial_scene is None or trial_layered is None
                        ):
                            raise RuntimeError("T3 trial transaction is incomplete")
                        cmir_holder[0] = trial_cmir
                        solution = trial_solution
                        selected_ids = solution.selected_ids
                        scene = trial_scene
                        layered = trial_layered
                        deployed_rows = []
                        native_after = 0.0
                        for row in proposed_refinement.macros:
                            replacement = replacements.get(row.macro_id)
                            if replacement is not None:
                                deployed = replace(
                                    row, macro_id=replacement.id,
                                    refined_program=replacement.program,
                                    committed=True, rollback_reason=None,
                                )
                            elif row.committed:
                                deployed = replace(
                                    row, refined_program=row.original_program,
                                    refined_params=row.original_params,
                                    committed=False,
                                    rollback_reason=rejected_refinements.get(
                                        row.macro_id,
                                        "not-a-deployable-continuous-program",
                                    ),
                                    native_error_after=row.native_error_before,
                                )
                            else:
                                deployed = row
                            deployed_rows.append(deployed)
                            if deployed.native_error_before is not None:
                                native_after += float(
                                    deployed.native_error_after
                                    if deployed.native_error_after is not None
                                    else deployed.native_error_before
                                )
                        ownership_digest = owner_partition_digest(
                            scene.owner_by_leaf,
                        )
                        refinement = replace(
                            proposed_refinement,
                            selected_ids=selected_ids,
                            owner_digest_before=ownership_digest,
                            owner_digest_after=ownership_digest,
                            layer_order_before=layered.order_graph.back_to_front,
                            layer_order_after=layered.order_graph.back_to_front,
                            macros=tuple(deployed_rows),
                            native_render_error_after=native_after,
                            committed=True, rollback_reason=None,
                            provenance=(
                                *proposed_refinement.provenance,
                                "production-court-certified-delivery",
                                "cached-T2+exact-T3-ROI-recheck",
                                "immutable-CMIR-rekey",
                            ),
                        )
                        refinement.validate()
                        checkpoints.append(AnytimeCheckpoint(
                            stage="T3", elapsed_ms=elapsed(),
                            selected_ids=solution.selected_ids,
                            utility=solution.utility,
                            exact_cover=True, proof_valid=True,
                            note=(
                                "frozen ownership/layers plus "
                                f"{len(replacements)} court-certified "
                                "analytic refinement(s)"
                            ),
                        ))
                        warnings.append(
                            "T3 committed court-certified refinements="
                            + str(len(replacements))
                        )
                    else:
                        refinement = replace(
                            proposed_refinement,
                            macros=tuple(
                                replace(
                                    row,
                                    refined_program=row.original_program,
                                    refined_params=row.original_params,
                                    committed=False,
                                    rollback_reason=(
                                        rejected_refinements.get(
                                            row.macro_id,
                                            row.rollback_reason
                                            or "no-certified-delivery-change",
                                        )
                                    ),
                                    native_error_after=row.native_error_before,
                                ) if row.committed else row
                                for row in proposed_refinement.macros
                            ),
                            native_render_error_after=(
                                proposed_refinement.native_render_error_before
                            ),
                            committed=False,
                            rollback_reason="no-certified-delivery-change",
                            provenance=(
                                *proposed_refinement.provenance,
                                "production-court-withheld-delivery",
                            ),
                        )
                        refinement.validate()
                        if (
                            layered.hidden_completions
                            and layered.render_check.opaque_occlusion_proof
                        ):
                            checkpoints.append(AnytimeCheckpoint(
                                stage="T3", elapsed_ms=elapsed(),
                                selected_ids=solution.selected_ids,
                                utility=solution.utility,
                                exact_cover=True, proof_valid=True,
                                note=(
                                    "opaque typed occluders certify "
                                    f"{len(layered.hidden_completions)} hidden "
                                    "analytic completion(s)"
                                ),
                            ))
                            warnings.append(
                                "T3 committed opaque hidden completions="
                                + str(len(layered.hidden_completions))
                            )
                        else:
                            warnings.append(
                                "T3 withheld: no refinement or hidden layer "
                                "changed delivered geometry with a proof"
                            )
            except Exception as error:
                warnings.append(f"T3 failed open to T2: {type(error).__name__}: {error}")
                layered = None; refinement = None

        if checkpoints[-1].stage in {"T2", "T3"} and not out_of_time():
            try:
                design_layers = (
                    layered
                    if (
                        layered is not None
                        and (
                            not layered.hidden_completions
                            or checkpoints[-1].stage == "T3"
                        )
                    ) else None
                )
                with profiler.stage("design_abstraction"):
                    design = build_design_program(
                        cmir_holder[0], scene, layered=design_layers,
                        refinement=refinement,
                    )
                    abstraction = guarded_abstract(
                        design, max_nodes=256, max_iterations=8,
                        time_budget_ms=budget.abstraction_ms,
                    )
                if abstraction.cost_after.total < abstraction.cost_before.total - 1e-9:
                    xir_svg, _xir_native, _xir_fallback = scene_to_svg(
                        reir, cmir_holder[0], scene,
                        phase5_bundle=phase5_bundle,
                        text_macros=text_macros,
                        layered_scene=design_layers,
                        design_program=abstraction.extracted,
                    )
                    if 'data-pcdc-xir="' not in xir_svg:
                        warnings.append(
                            "T4 withheld: cheaper DPIR produced no semantic "
                            "XIR group in the SVG writer"
                        )
                    else:
                        checkpoints.append(AnytimeCheckpoint(
                            stage="T4", elapsed_ms=elapsed(),
                            selected_ids=solution.selected_ids,
                            utility=solution.utility,
                            exact_cover=True, proof_valid=True,
                            note=(
                                "guarded cheaper DPIR consumed as exact "
                                "semantic SVG XIR groups"
                            ),
                        ))
                else:
                    warnings.append(
                        "T4 withheld: guarded abstraction made no delivered "
                        "program change"
                    )
            except Exception as error:
                warnings.append(f"T4 failed open: {type(error).__name__}: {error}")
                design = None; abstraction = None

        typed_rois = 0
        typed_columns = 0
        column_limit = 0
        if phase5_bundle is not None:
            typed_rois = (
                phase5_bundle.shapes.rois_considered
                + phase5_bundle.strokes.rois_considered
                + phase5_bundle.appearances.rois_considered
                + len(phase5_bundle.cleanup.loci)
            )
            typed_columns = len(phase5_bundle.candidates)
            column_limit = budget.phase5.maximum_columns
        if text_macros is not None:
            typed_rois += len(text_macros.proposals)
            typed_columns += len(text_macros.records)
            # two lazy structural paths plus bounded exact-font hypotheses.
            column_limit += budget.text_rois * (2 + budget.text_exact_per_line)
        audit = RuntimeContractAudit(
            hierarchy_nodes=len(reir.hierarchy.nodes),
            hierarchy_limit=max(1, 2 * reir.hierarchy.leaf_count),
            typed_rois=typed_rois, typed_roi_limit=budget.typed_roi_limit,
            generated_typed_columns=typed_columns,
            generated_column_limit=column_limit,
            exact_finalists_per_roi=4,
            exact_roi_renders=(
                production_court_audit.exact_render_requests
                if production_court_audit is not None else 0
            ),
            exact_roi_render_limit=budget.exact_render_limit,
            image_formation_models=len(freeze_renderer_posterior(reir).models),
            visible_extractions=visible_extractions,
            hidden_extractions=hidden_extractions,
            final_full_renders=final_renders, one_reir_pass=True,
            native_backend=backend_summary(),
        )
        audit.validate()
        result = RuntimeCompileResult(
            mode=mode, requested_extraction_profile=extraction_profile,
            extraction_profile=delivered_profile,
            source_path=str(path.resolve()), elapsed_ms=elapsed(),
            deadline_ms=deadline_ms, deadline_exceeded=out_of_time(),
            best_stage=checkpoints[-1].stage, reir=reir,
            cmir=cmir_holder[0], solution=solution, visible_scene=scene,
            phase5_bundle=phase5_bundle, text_macros=text_macros,
            proposal_queries=tuple(queries), finalists=finalists,
            layered_scene=layered,
            refinement=refinement, design_program=design,
            abstraction=abstraction, visible_render_audit=visible_render_audit,
            production_court_audit=production_court_audit,
            local_refinement_audit=local_refinement_audit,
            checkpoints=tuple(checkpoints),
            contract=audit, stage_profile=profiler.summary(),
            warnings=tuple((f"REIR cache hit={cache_hit}", *warnings)),
        )
        result.validate()
        return result
