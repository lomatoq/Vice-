"""Discrete scene moves, continuous fits, local re-optimization, and abstention."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .contracts import LayerEdge, SceneGraph, SceneHypothesis, ScoreBreakdown
from .ingest import CanonicalRaster
from .render_models import (ForwardScore, forward_model_catalog,
                            marginalized_forward_nll, score_forward,
                            select_forward_model)
from .scene_graph import SceneBuildResult, replace_shape_candidate


@dataclass(frozen=True)
class OptimizationAudit:
    action: str
    accepted: bool
    score_before: float
    score_after: float
    details: str


@dataclass(frozen=True)
class OptimizationResult:
    hypothesis: SceneHypothesis
    audits: tuple[OptimizationAudit, ...]
    runner_up_total: float | None
    abstained: bool
    abstain_reasons: tuple[str, ...] = ()


def optimize_scenes(builds: tuple[SceneBuildResult, ...], raster: CanonicalRaster,
                    model_names: tuple[str, ...], *, enable_forward_court: bool = True,
                    max_local_moves: int = 24) -> OptimizationResult:
    if not builds:
        raise ValueError("optimizer received no scene hypotheses")
    models = forward_model_catalog(model_names if enable_forward_court else ("clean-aa",))
    hypotheses: list[tuple[SceneHypothesis, SceneBuildResult, ForwardScore, float]] = []
    for index, build in enumerate(builds):
        best_render, model_scores = select_forward_model(build.graph, raster, models)
        breakdown = _breakdown(build, best_render,
                               marginalized_forward_nll(model_scores))
        marginalized = marginalized_forward_nll(model_scores)
        hypotheses.append((SceneHypothesis(
            id=f"scene-hypothesis-{index}", graph=build.graph,
            render_model=best_render.model,
            evidence_refs=("evidence-pyramid", build.topology_id),
            score_breakdown=breakdown,
            provenance=("top-K-topology", "whole-shape-tournaments", "forward-model-court"),
        ), build, best_render, marginalized))
    hypotheses.sort(key=lambda row: row[0].score_breakdown.total)
    incumbent, build, forward, incumbent_render_nll = hypotheses[0]
    audits: list[OptimizationAudit] = []
    moves = 0
    # Localized graph optimization jointly courts shape class and nearby draw
    # order. This is necessary for hidden-shape completion: a recovered circle
    # may only become correct after it moves below its occluder.
    candidate_rows = {shape_id: _candidate_subset(candidates)
                      for shape_id, candidates in build.alternatives.items()}
    max_rank = max((len(rows) for rows in candidate_rows.values()), default=0)
    for candidate_rank in range(max_rank):
        for shape_id in sorted(candidate_rows):
            if moves >= max_local_moves:
                break
            if candidate_rank >= len(candidate_rows[shape_id]):
                continue
            candidate = candidate_rows[shape_id][candidate_rank]
            moves += 1
            replaced_graph = replace_shape_candidate(incumbent.graph, shape_id, candidate)
            fast_rows = []
            for layer_action, trial_graph in _candidate_layer_graphs(replaced_graph, shape_id):
                trial_fast = score_forward(trial_graph, raster, incumbent.render_model)
                fast_rows.append((trial_fast.nll, layer_action, trial_graph))
            _, layer_action, trial_graph = min(fast_rows, key=lambda row: row[0])
            trial_forward, trial_scores = select_forward_model(trial_graph, raster, models)
            trial_render_nll = marginalized_forward_nll(trial_scores)
            # Candidate MDL is a per-shape model-choice prior.  The global
            # likelihood is a mean per observed pixel, so adding the raw MDL
            # once per region made deleting letters/components overwhelmingly
            # profitable.  Compare average per-shape model cost here, while
            # topology_score carries the explicit region-count prior.
            shape_count = max(1, len(incumbent.graph.shapes))
            delta_mdl = (_candidate_mdl(candidate) - _shape_mdl(
                next(shape for shape in incumbent.graph.shapes
                     if shape.id == shape_id))) / shape_count
            trial_total = (incumbent.score_breakdown.total
                           + trial_render_nll - incumbent.score_breakdown.render_nll
                           + delta_mdl)
            accepted = trial_total + 1e-9 < incumbent.score_breakdown.total
            audits.append(OptimizationAudit(
                action=f"reclassify:{shape_id}:{candidate.family}:{layer_action}", accepted=accepted,
                score_before=incumbent.score_breakdown.total, score_after=trial_total,
                details="localized shape + draw-order move with rollback",
            ))
            if accepted:
                breakdown = ScoreBreakdown(
                    render_nll=trial_render_nll,
                    mdl=incumbent.score_breakdown.mdl + delta_mdl,
                    topology=incumbent.score_breakdown.topology,
                    regularity=incumbent.score_breakdown.regularity,
                    semantics=incumbent.score_breakdown.semantics,
                    unsupported_evidence=incumbent.score_breakdown.unsupported_evidence,
                )
                incumbent = SceneHypothesis(
                    id=incumbent.id, graph=trial_graph, render_model=trial_forward.model,
                    evidence_refs=incumbent.evidence_refs,
                    score_breakdown=breakdown,
                    provenance=incumbent.provenance + (f"accepted:{shape_id}:{candidate.family}",),
                )
                forward = trial_forward
                incumbent_render_nll = trial_render_nll
        if moves >= max_local_moves:
            break
    runner_up = hypotheses[1][0].score_breakdown.total if len(hypotheses) > 1 else None
    abstain_reasons = []
    if runner_up is not None and abs(runner_up - incumbent.score_breakdown.total) < 0.0025:
        abstain_reasons.append("posterior-gap")
    if forward.nll > .16:
        abstain_reasons.append("absolute-forward-nll")
    if forward.worst_window > .24:
        abstain_reasons.append("local-worst-window")
    low_confidence = sum(shape.confidence < .2 for shape in incumbent.graph.shapes)
    if low_confidence > max(4, int(.25 * len(incumbent.graph.shapes))):
        abstain_reasons.append("unsupported-shapes")
    shape_limit = max(48, int(raster.width * raster.height / 512))
    if len(incumbent.graph.shapes) > shape_limit:
        abstain_reasons.append("shape-explosion")
    abstained = bool(abstain_reasons)
    if abstained:
        audits.append(OptimizationAudit("abstain", True, incumbent.score_breakdown.total,
                                        incumbent.score_breakdown.total,
                                        ",".join(abstain_reasons)
                                        + "; retain alternatives in trace"))
    return OptimizationResult(incumbent, tuple(audits), runner_up, abstained,
                              tuple(abstain_reasons))


def assert_monotonic(audits: tuple[OptimizationAudit, ...]) -> None:
    for audit in audits:
        if audit.accepted and audit.action != "abstain" and audit.score_after > audit.score_before + 1e-9:
            raise AssertionError(f"accepted optimizer move increased objective: {audit}")


def _breakdown(build: SceneBuildResult, forward: ForwardScore,
               marginalized_nll: float | None = None) -> ScoreBreakdown:
    # Shape MDLs are calibrated for the local whole-shape tournament.  Their
    # mean is the global family prior; summing them duplicated the topology
    # region-count penalty and caused catastrophic text/component collapse.
    values = tuple(_candidate_mdl(candidate) for candidate in build.selected.values())
    mdl = float(np.mean(values)) if values else 0.0
    topology = (float(build.topology_score)
                + 0.002 * sum(len(shape.negative_loops)
                              for shape in build.graph.shapes))
    regularity = -0.001 * len(build.graph.constraints)
    semantics = -0.0015 * sum(shape.model_family == "glyph" for shape in build.graph.shapes)
    unsupported = 0.001 * sum(shape.confidence < .25 for shape in build.graph.shapes)
    return ScoreBreakdown(forward.nll if marginalized_nll is None else marginalized_nll,
                          mdl, topology, regularity, semantics, unsupported)


def _candidate_mdl(candidate) -> float:
    return float(candidate.mdl)


def _shape_mdl(shape) -> float:
    simple = {"circle": .004, "ellipse": .006, "rectangle": .005,
              "rounded-rectangle": .007, "triangle": .006,
              "isosceles-triangle": .0045, "quadrilateral": .008,
              "ring": .007, "glyph": .010}
    return simple.get(shape.model_family, .014)


def _candidate_subset(candidates) -> tuple:
    """One best candidate/family plus explicit robust completion proposals."""
    result = []
    counts = {}
    limits = {"rounded-rectangle": 4, "rectangle": 2, "ellipse": 2}
    for candidate in candidates:
        robust = any("occlusion-robust" in item
                     for primitive in candidate.positive
                     for item in primitive.provenance)
        limit = limits.get(candidate.family, 1)
        count = counts.get(candidate.family, 0)
        if count < limit or robust:
            result.append(candidate)
            counts[candidate.family] = count + 1
    return tuple(result)


def _candidate_layer_graphs(graph: SceneGraph, shape_id: str) -> tuple[tuple[str, SceneGraph], ...]:
    ordered = sorted(graph.shapes, key=lambda item: (item.layer, item.id))
    current = next(index for index, item in enumerate(ordered) if item.id == shape_id)
    positions = sorted({current, max(0, current - 1), min(len(ordered) - 1, current + 1)})
    return tuple(("layer-stay" if position == current else f"layer-{current}-to-{position}",
                  _move_shape_layer(graph, shape_id, position)) for position in positions)


def _move_shape_layer(graph: SceneGraph, shape_id: str, target: int) -> SceneGraph:
    ordered = sorted(graph.shapes, key=lambda item: (item.layer, item.id))
    moving = next(item for item in ordered if item.id == shape_id)
    ordered.remove(moving)
    ordered.insert(int(np.clip(target, 0, len(ordered))), moving)
    rank = {item.id: index for index, item in enumerate(ordered)}
    shapes = tuple(replace(item, layer=rank[item.id]) for item in graph.shapes)
    edges = tuple(LayerEdge(ordered[index - 1].id, ordered[index].id)
                  for index in range(1, len(ordered)))
    result = replace(graph, shapes=shapes, layer_edges=edges)
    result.validate()
    return result
