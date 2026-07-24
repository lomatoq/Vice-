"""Integrated bounded Phase-5 typed-macro generation and extraction entry."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import time
from typing import Iterable, TYPE_CHECKING

from .appearance_macros import AppearanceMacroSet, generate_appearance_macros
from .cleanup_macros import CodecMacroSet, generate_cleanup_macros
from .evidence_ir import RasterEvidenceIR
from .macro_extractor import extract_visible_scene
from .macro_ir import CandidateMacroIR, MacroCandidate
from .macro_registry import build_base_registry, extend_registry
from .master_problem import MasterSolution
from .shape_macros import ShapeMacroSet, generate_shape_macros
from .stroke_macros import StrokeMacroSet, generate_stroke_macros

if TYPE_CHECKING:
    from .proposal_net import ProposalQuery


@dataclass(frozen=True)
class Phase5Budgets:
    shape_rois: int = 64
    shapes_per_roi: int = 4
    stroke_rois: int = 64
    appearance_rois: int = 32
    appearances_per_roi: int = 4
    codec_loci: int = 32

    @property
    def maximum_columns(self) -> int:
        # Shape repeated groups are independently bounded at 16.  Each codec
        # locus has exactly five named counterfactual types at most.
        return (
            self.shape_rois * self.shapes_per_roi + 16
            + self.stroke_rois
            + self.appearance_rois * self.appearances_per_roi
            + self.codec_loci * 5
        )


@dataclass(frozen=True)
class Phase5MacroBundle:
    shapes: ShapeMacroSet
    strokes: StrokeMacroSet
    appearances: AppearanceMacroSet
    cleanup: CodecMacroSet
    lane_ms: tuple[tuple[str, float], ...]
    elapsed_ms: float
    budget: Phase5Budgets
    provenance: tuple[str, ...]

    @property
    def candidates(self) -> tuple[MacroCandidate, ...]:
        return (
            self.shapes.candidates + self.strokes.candidates
            + self.appearances.candidates + self.cleanup.candidates
        )

    @property
    def counts(self) -> dict[str, int]:
        return {
            "whole_shapes": len(self.shapes.records),
            "repeated_parameter_groups": len(self.shapes.groups),
            "stroke_networks": len(self.strokes.records),
            "appearance_models": len(self.appearances.records),
            "codec_counterfactuals": len(self.cleanup.records),
            "total": len(self.candidates),
        }

    def validate(self, reir: RasterEvidenceIR) -> None:
        counts = self.counts
        if counts["whole_shapes"] > self.budget.shape_rois * self.budget.shapes_per_roi:
            raise ValueError("whole-shape candidate budget exceeded")
        if counts["repeated_parameter_groups"] > 16:
            raise ValueError("repeated-shape group budget exceeded")
        if counts["stroke_networks"] > self.budget.stroke_rois:
            raise ValueError("stroke candidate budget exceeded")
        if counts["appearance_models"] > (
            self.budget.appearance_rois * self.budget.appearances_per_roi
        ):
            raise ValueError("appearance candidate budget exceeded")
        if counts["codec_counterfactuals"] > self.budget.codec_loci * 5:
            raise ValueError("codec counterfactual budget exceeded")
        if counts["total"] > self.budget.maximum_columns:
            raise ValueError("Phase-5 global candidate budget exceeded")
        if len({row.id for row in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate identity across Phase-5 lanes")
        for row in self.shapes.records:
            row.validate(reir)
        for row in self.strokes.records:
            row.validate(reir)
        for row in self.appearances.records:
            row.validate(reir)
        for row in self.cleanup.records:
            row.validate(reir, self.cleanup.renderer_posterior)


@dataclass(frozen=True)
class Phase5Extraction:
    bundle: Phase5MacroBundle
    cmir: CandidateMacroIR
    solution: MasterSolution


def _timed(name: str, function):
    started = time.perf_counter()
    value = function()
    return name, value, (time.perf_counter() - started) * 1000.0


def generate_phase5_macros(
    reir: RasterEvidenceIR, *, budget: Phase5Budgets | None = None,
    parallel: bool = True, validate_reir: bool = True,
    proposal_queries: Iterable["ProposalQuery"] = (),
    protected_text_masks: Iterable[object] = (),
) -> Phase5MacroBundle:
    if validate_reir:
        reir.validate()
    limits = budget or Phase5Budgets()
    guided_queries = tuple(proposal_queries)
    protected_text = tuple(protected_text_masks)
    jobs = {
        "shapes": lambda: generate_shape_macros(
            reir, max_rois=limits.shape_rois,
            max_per_roi=limits.shapes_per_roi, validate_reir=False,
            proposal_queries=guided_queries,
            protected_text_masks=protected_text,
        ),
        "strokes": lambda: generate_stroke_macros(
            reir, max_rois=limits.stroke_rois, validate_reir=False,
            proposal_queries=guided_queries,
        ),
        "appearances": lambda: generate_appearance_macros(
            reir, max_rois=limits.appearance_rois,
            max_models_per_roi=limits.appearances_per_roi,
            validate_reir=False, proposal_queries=guided_queries,
        ),
        "cleanup": lambda: generate_cleanup_macros(
            reir, max_loci=limits.codec_loci, validate_reir=False,
            proposal_queries=guided_queries,
        ),
    }
    started = time.perf_counter()
    if parallel:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="pcdc-phase5") as pool:
            futures = {
                name: pool.submit(_timed, name, function)
                for name, function in jobs.items()
            }
            completed = {name: future.result() for name, future in futures.items()}
    else:
        completed = {
            name: _timed(name, function) for name, function in jobs.items()
        }
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    lane_ms = tuple(sorted(
        (name, float(row[2])) for name, row in completed.items()
    ))
    bundle = Phase5MacroBundle(
        shapes=completed["shapes"][1],
        strokes=completed["strokes"][1],
        appearances=completed["appearances"][1],
        cleanup=completed["cleanup"][1],
        lane_ms=lane_ms, elapsed_ms=elapsed_ms, budget=limits,
        provenance=(
            "phase5-typed-lanes-generated-before-selection",
            "bounded-parallel-generation" if parallel else "bounded-serial-generation",
            "all-lanes-compete-in-one-cmir",
        ),
    )
    bundle.validate(reir)
    return bundle


def build_phase5_registry(
    reir: RasterEvidenceIR, *, budget: Phase5Budgets | None = None,
    parallel: bool = True,
) -> tuple[Phase5MacroBundle, CandidateMacroIR]:
    bundle = generate_phase5_macros(
        reir, budget=budget, parallel=parallel,
    )
    cmir = extend_registry(reir, build_base_registry(reir), bundle.candidates)
    return bundle, cmir


def extract_phase5_scene(
    reir: RasterEvidenceIR, *, budget: Phase5Budgets | None = None,
    parallel: bool = True, exact_component_limit: int = 18,
    time_budget_ms: float = 250.0,
) -> Phase5Extraction:
    bundle, cmir = build_phase5_registry(
        reir, budget=budget, parallel=parallel,
    )
    solution = extract_visible_scene(
        cmir, reir.hierarchy, exact_component_limit=exact_component_limit,
        time_budget_ms=time_budget_ms,
    )
    if not solution.feasible or not solution.fallback_always_feasible:
        raise RuntimeError("Phase-5 extraction lost the valid fallback")
    return Phase5Extraction(bundle=bundle, cmir=cmir, solution=solution)
