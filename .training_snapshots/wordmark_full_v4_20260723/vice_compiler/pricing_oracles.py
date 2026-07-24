"""Dual-guided typed pricing oracles for phase-2 column generation."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import time

from .evidence_ir import RasterEvidenceIR
from .macro_ir import (
    CandidateMacroIR, MacroCandidate, ResourceEstimate, SceneProgram,
    ScoreBounds, stable_macro_id,
)
from .macro_registry import kind_for_family
from .master_problem import DualPrices, reduced_gain


@dataclass(frozen=True)
class PricingContext:
    reir: RasterEvidenceIR
    cmir: CandidateMacroIR
    prices: DualPrices
    round_index: int
    candidate_pool: tuple[MacroCandidate, ...]
    max_columns: int = 12
    # Production may only admit the exact delivered program that was fitted
    # and rendered in court.  The Experiment-1B support-qualification path
    # deliberately synthesises a new generic program, so it remains available
    # for the isolated experiment but is forbidden in the production runtime.
    allow_support_qualification: bool = True


@dataclass(frozen=True)
class PricedColumn:
    candidate: MacroCandidate
    reduced_gain: float
    oracle: str


@dataclass(frozen=True)
class PricingBatch:
    oracle: str
    columns: tuple[PricedColumn, ...]
    considered: int
    elapsed_ms: float
    used_manual_risk_threshold: bool = False


class TokenPricingOracle:
    name = "token"
    accepted_families: frozenset[str] = frozenset()
    direct_share = 1.0 / 3.0

    def accepts(self, family: str) -> bool:
        return family in self.accepted_families

    @staticmethod
    def _reduced_gain(candidate: MacroCandidate, prices: DualPrices) -> float:
        topology_claim = bool(
            candidate.certificates.components is not None
            or candidate.certificates.holes is not None
            or any(
                claim.startswith(("components=", "persistent-counters="))
                or "topology" in claim
                for claim in candidate.prerequisite_claims
            )
        )
        layer_claim = bool(
            candidate.family == "layer"
            or candidate.hidden_geometry is not None
            or any("layer" in claim for claim in candidate.prerequisite_claims)
        )
        return reduced_gain(
            candidate.core_bits,
            candidate.score_bounds.lower,
            prices,
            candidate.boundary_interfaces,
            topology_claim=topology_claim,
            layer_claim=layer_claim,
        )

    @staticmethod
    def _support_key(candidate: MacroCandidate) -> tuple[object, ...]:
        certificate = candidate.certificates
        if certificate.support_bits:
            return ("bits", certificate.support_size,
                    certificate.support_bits)
        if certificate.support_rle:
            return ("rle", certificate.support_size,
                    certificate.support_rle)
        return ("core", candidate.core_bits, candidate.roi_xyxy)

    @classmethod
    def _unique_supports(
        cls, candidates: list[MacroCandidate] | tuple[MacroCandidate, ...]
    ) -> list[MacroCandidate]:
        unique: dict[tuple[object, ...], MacroCandidate] = {}
        for candidate in candidates:
            key = cls._support_key(candidate)
            previous = unique.get(key)
            if previous is None or (
                candidate.score_bounds.lower,
                -candidate.cell_count,
                candidate.id,
            ) > (
                previous.score_bounds.lower,
                -previous.cell_count,
                previous.id,
            ):
                unique[key] = candidate
        return list(unique.values())

    def _support_pool(
        self, context: PricingContext, cues: list[MacroCandidate]
    ) -> list[MacroCandidate]:
        return sorted(
            self._unique_supports(context.candidate_pool),
            key=lambda candidate: (
                -self._reduced_gain(candidate, context.prices),
                candidate.id,
            ),
        )

    @staticmethod
    def _qualified_support(
        cue: MacroCandidate, support: MacroCandidate
    ) -> MacroCandidate:
        """Attach a semantic cue to an independently measured support column."""
        family = cue.family
        kind = kind_for_family(family)
        evidence = tuple(sorted(set((*cue.soft_evidence, *support.soft_evidence))))
        expected = (
            0.44 * cue.score_bounds.expected
            + 0.56 * support.score_bounds.expected
            + 0.012 * math.log2(max(1, support.cell_count))
        )
        lower = (
            0.44 * cue.score_bounds.lower
            + 0.56 * support.score_bounds.lower
        )
        upper = max(expected, (
            0.44 * cue.score_bounds.upper
            + 0.56 * support.score_bounds.upper
            + 0.02 * math.log2(max(1, support.cell_count))
        ))
        x1 = min(cue.roi_xyxy[0], support.roi_xyxy[0])
        y1 = min(cue.roi_xyxy[1], support.roi_xyxy[1])
        x2 = max(cue.roi_xyxy[2], support.roi_xyxy[2])
        y2 = max(cue.roi_xyxy[3], support.roi_xyxy[3])
        candidate_id = stable_macro_id("qualified", {
            "cue": cue.id, "support": support.id, "family": family,
        })
        return replace(
            support, id=candidate_id, registry_index=-1,
            kind=kind, family=family,
            roi_xyxy=(x1, y1, x2, y2), soft_evidence=evidence,
            program=SceneProgram(kind.value, (
                ("family", family), ("semantic_cue", cue.id),
                ("support_column", support.id),
            )),
            certificates=replace(
                support.certificates,
                evidence_token_ids=evidence,
                notes=tuple(sorted(set((
                    *support.certificates.notes,
                    "semantic-cue+independent-support",
                )))),
            ),
            conflict_bits=0,
            score_bounds=ScoreBounds(lower, expected, upper),
            resource_estimate=ResourceEstimate(
                fitting_ms=(cue.resource_estimate.fitting_ms
                            + support.resource_estimate.fitting_ms),
                render_pixels=support.resource_estimate.render_pixels,
                memory_bytes=(cue.resource_estimate.memory_bytes
                              + support.resource_estimate.memory_bytes),
                solver_variables=1,
            ),
            provenance=tuple(sorted(set((
                *cue.provenance, *support.provenance,
                "semantic-support-qualified-pricing",
            )))),
        )

    def price(self, context: PricingContext) -> PricingBatch:
        started = time.perf_counter()
        existing = {candidate.id for candidate in context.cmir.candidates}
        direct: list[PricedColumn] = []
        qualified: list[PricedColumn] = []
        cues = self._unique_supports([
            candidate for candidate in context.candidate_pool
            if self.accepts(candidate.family)
        ])
        considered = len(cues)
        for candidate in cues:
            if candidate.id in existing:
                continue
            gain = self._reduced_gain(candidate, context.prices)
            if gain <= 0.0:
                continue
            direct.append(PricedColumn(
                candidate=candidate, reduced_gain=gain, oracle=self.name,
            ))
        if cues and context.allow_support_qualification:
            cue = max(
                cues,
                key=lambda candidate: (
                    candidate.score_bounds.lower, -candidate.cell_count,
                    candidate.id,
                ),
            )
            support_pool = self._support_pool(
                context, cues
            )[:max(8, context.max_columns * 3)]
            considered += len(support_pool)
            for support in support_pool:
                candidate = self._qualified_support(cue, support)
                if candidate.id in existing:
                    continue
                gain = self._reduced_gain(candidate, context.prices)
                if gain > 0.0:
                    qualified.append(PricedColumn(
                        candidate=candidate, reduced_gain=gain,
                        oracle=self.name,
                    ))
        # A pure reduced-gain sort is biased towards the largest support: its
        # cell-price sum can swamp a very strong local typed proof.  Reserve a
        # bounded part of every batch for the best direct semantic columns and
        # the rest for dual-guided support expansion.  This is a deterministic
        # column budget, not a semantic risk threshold.
        direct.sort(key=lambda item: (
            -item.candidate.score_bounds.lower,
            -item.reduced_gain,
            item.candidate.id,
        ))
        qualified.sort(key=lambda item: (
            -item.reduced_gain,
            -item.candidate.score_bounds.lower,
            item.candidate.id,
        ))
        limit = max(0, int(context.max_columns))
        direct_budget = int(round(limit * self.direct_share))
        direct_limit = min(len(direct), direct_budget) if limit else 0
        support_limit = min(len(qualified), limit - direct_limit)
        selected = [*direct[:direct_limit], *qualified[:support_limit]]
        if len(selected) < limit:
            selected_ids = {item.candidate.id for item in selected}
            remainder = [
                item for item in (*direct[direct_limit:],
                                  *qualified[support_limit:])
                if item.candidate.id not in selected_ids
            ]
            remainder.sort(key=lambda item: (
                -item.reduced_gain,
                -item.candidate.score_bounds.lower,
                item.candidate.id,
            ))
            selected.extend(remainder[:limit - len(selected)])
        columns = tuple(selected)
        return PricingBatch(
            oracle=self.name, columns=columns, considered=considered,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )


class TextPricingOracle(TokenPricingOracle):
    name = "text"
    accepted_families = frozenset({"text"})


class ShapePricingOracle(TokenPricingOracle):
    name = "shape"
    accepted_families = frozenset({"shape", "symmetry"})


class ComponentPricingOracle(TokenPricingOracle):
    name = "component"
    accepted_families = frozenset({"component"})


class StrokePricingOracle(TokenPricingOracle):
    name = "stroke"
    accepted_families = frozenset({"stroke"})
    direct_share = 0.0

    @staticmethod
    def _bbox_iou(
        first: tuple[int, int, int, int],
        second: tuple[int, int, int, int],
    ) -> float:
        x1 = max(first[0], second[0])
        y1 = max(first[1], second[1])
        x2 = min(first[2], second[2])
        y2 = min(first[3], second[3])
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        first_area = max(1, (first[2] - first[0]) * (first[3] - first[1]))
        second_area = max(
            1, (second[2] - second[0]) * (second[3] - second[1])
        )
        return intersection / max(1, first_area + second_area - intersection)

    def _support_pool(
        self, context: PricingContext, cues: list[MacroCandidate]
    ) -> list[MacroCandidate]:
        # Individual Hough strokes are intentionally local.  Their envelope
        # is the evidence-bearing network ROI; ranking support against only the
        # single strongest segment misses large diagrams and wordmarks.
        strongest = sorted(
            cues,
            key=lambda candidate: (
                -candidate.score_bounds.lower, candidate.id
            ),
        )[:4]
        envelope = (
            min(candidate.roi_xyxy[0] for candidate in strongest),
            min(candidate.roi_xyxy[1] for candidate in strongest),
            max(candidate.roi_xyxy[2] for candidate in strongest),
            max(candidate.roi_xyxy[3] for candidate in strongest),
        )
        return sorted(
            self._unique_supports(context.candidate_pool),
            key=lambda candidate: (
                -self._bbox_iou(envelope, candidate.roi_xyxy),
                -self._reduced_gain(candidate, context.prices),
                candidate.id,
            ),
        )


class LayerPricingOracle(TokenPricingOracle):
    name = "layer"
    accepted_families = frozenset({"layer"})


class AppearancePricingOracle(TokenPricingOracle):
    name = "appearance"
    accepted_families = frozenset({"gradient"})
    direct_share = 0.0

    def _support_pool(
        self, context: PricingContext, cues: list[MacroCandidate]
    ) -> list[MacroCandidate]:
        # A smooth-color cue can cover the whole visible canvas while the
        # actual gradient belongs to one nested component.  Pure dual sorting
        # then repeatedly returns only the largest masks.  One best improving
        # support from each deterministic scale stratum preserves the lazy
        # budget while covering the full bounded component lattice.
        candidates = sorted(
            self._unique_supports(context.candidate_pool),
            key=lambda candidate: (candidate.cell_count, candidate.id),
        )
        count = min(
            len(candidates), max(8, int(context.max_columns) * 3)
        )
        if count <= 0:
            return []
        selected: list[MacroCandidate] = []
        for index in range(count):
            start = index * len(candidates) // count
            end = (index + 1) * len(candidates) // count
            bucket = candidates[start:max(start + 1, end)]
            selected.append(max(
                bucket,
                key=lambda candidate: (
                    candidate.score_bounds.lower,
                    self._reduced_gain(candidate, context.prices),
                    candidate.id,
                ),
            ))
        return selected


class CleanupPricingOracle(TokenPricingOracle):
    name = "cleanup"
    accepted_families = frozenset({"codec_detail"})


def default_pricing_oracles() -> tuple[TokenPricingOracle, ...]:
    return (
        TextPricingOracle(), ShapePricingOracle(),
        ComponentPricingOracle(), StrokePricingOracle(),
        LayerPricingOracle(), AppearancePricingOracle(),
        CleanupPricingOracle(),
    )
