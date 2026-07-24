"""Split-conformal ProposalNet type/support candidate sets."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np

from .proposal_net import ProposalQuery, union_queries


@dataclass(frozen=True)
class CalibrationExample:
    family: str
    type_confidence: float
    support_iou: float
    source_group: str
    admission_rank: int = 1
    candidate_count: int = 1
    support_iou_floor: float = 0.50

    @property
    def nonconformity(self) -> float:
        if self.candidate_count <= 0 or self.admission_rank <= 0:
            raise ValueError("conformal admission ranks must be positive")
        if self.support_iou < self.support_iou_floor:
            return 1.0
        return float(np.clip(
            (self.admission_rank - 1) / max(1, self.candidate_count),
            0.0, 1.0,
        ))


@dataclass(frozen=True)
class ConformalThreshold:
    family: str
    alpha: float
    threshold: float
    calibration_count: int
    empirical_coverage: float


@dataclass(frozen=True)
class ConformalCalibration:
    target_coverage: float
    thresholds: tuple[ConformalThreshold, ...]
    global_threshold: float
    split_policy: str
    provenance: tuple[str, ...]

    def by_family(self) -> dict[str, ConformalThreshold]:
        return {row.family: row for row in self.thresholds}

    def validate(self) -> None:
        if not 0.0 < self.target_coverage < 1.0:
            raise ValueError("invalid conformal target coverage")
        if not 0.0 <= self.global_threshold <= 1.0:
            raise ValueError("invalid global conformal threshold")
        for row in self.thresholds:
            if not 0.0 <= row.threshold <= 1.0 or row.calibration_count <= 0:
                raise ValueError("invalid class conformal calibration")


def conformal_calibration_from_dict(payload: dict) -> ConformalCalibration:
    if not isinstance(payload, dict):
        raise ValueError("conformal calibration payload must be a mapping")
    try:
        result = ConformalCalibration(
            target_coverage=float(payload["target_coverage"]),
            thresholds=tuple(
                ConformalThreshold(**row) for row in payload["thresholds"]
            ),
            global_threshold=float(payload["global_threshold"]),
            split_policy=str(payload["split_policy"]),
            provenance=tuple(str(value) for value in payload["provenance"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid conformal calibration payload") from error
    result.validate()
    if "exact-runtime-prefix-rank-with-support-IoU-floor" not in result.provenance:
        raise ValueError("conformal calibration uses a non-runtime admission score")
    return result


def _finite_sample_quantile(values: np.ndarray, coverage: float) -> float:
    if not len(values):
        return 1.0
    rank = int(math.ceil((len(values) + 1) * coverage))
    # Standard split-conformal finite-sample correction.  If the requested
    # coverage is finer than the calibration sample can resolve, the valid
    # bounded-score threshold is 1.0 (a deliberately wide/vacuous set), not
    # the largest observed score.
    if rank > len(values):
        return 1.0
    return float(np.sort(values)[rank - 1])


def calibrate_conformal_sets(
    examples: Iterable[CalibrationExample], *, target_coverage: float = 0.99,
    minimum_class_examples: int = 8,
) -> ConformalCalibration:
    rows = tuple(examples)
    if not rows:
        raise ValueError("conformal calibration set is empty")
    scores = np.asarray([row.nonconformity for row in rows], np.float64)
    global_threshold = _finite_sample_quantile(scores, target_coverage)
    thresholds = []
    for family in sorted({row.family for row in rows}):
        family_scores = np.asarray([
            row.nonconformity for row in rows if row.family == family
        ], np.float64)
        threshold = (
            _finite_sample_quantile(family_scores, target_coverage)
            if len(family_scores) >= minimum_class_examples else global_threshold
        )
        coverage = float(np.mean(family_scores <= threshold))
        thresholds.append(ConformalThreshold(
            family=family, alpha=1.0 - target_coverage,
            threshold=threshold, calibration_count=len(family_scores),
            empirical_coverage=coverage,
        ))
    result = ConformalCalibration(
        target_coverage=target_coverage, thresholds=tuple(thresholds),
        global_threshold=global_threshold,
        split_policy="held-out-source-family+semantic-class",
        provenance=(
            "finite-sample-higher-quantile",
            "exact-runtime-prefix-rank-with-support-IoU-floor",
            "low-confidence-expands-prefix-never-destructive-threshold",
        ),
    )
    result.validate(); return result


def conformal_query_set(
    queries: Iterable[ProposalQuery], calibration: ConformalCalibration,
    *, maximum_per_family: int = 64,
) -> tuple[ProposalQuery, ...]:
    calibration.validate(); thresholds = calibration.by_family()
    grouped: dict[str, list[ProposalQuery]] = {}
    for query in queries:
        query.validate(); grouped.setdefault(query.family, []).append(query)
    selected = []
    for family, rows in grouped.items():
        rows.sort(key=lambda row: (-row.confidence, row.id))
        threshold = thresholds.get(family)
        q = threshold.threshold if threshold is not None else calibration.global_threshold
        bounded_count = min(len(rows), maximum_per_family)
        # Calibration scores the 1-based rank of the first query with correct
        # type and IoU support.  Apply that exact observable prefix rule at
        # runtime; target IoU is never consulted during admission.
        limit = min(
            bounded_count,
            max(1, int(math.floor(q * bounded_count)) + 1),
        )
        selected.extend(rows[:limit])
    return tuple(selected)


def runtime_conformal_query_set(
    classical: Iterable[ProposalQuery], neural: Iterable[ProposalQuery],
    calibration: ConformalCalibration | None, *, maximum_queries: int,
) -> tuple[ProposalQuery, ...]:
    """Apply the one canonical runtime admission transaction.

    Calibration is family-local, while the quality-mode budget is global.
    Keeping union, conformal prefix selection and the final global cap in one
    function prevents an offline audit from accidentally proving a wider set
    than Fast/Balanced/Max actually deliver.
    """

    if maximum_queries <= 0:
        raise ValueError("runtime query budget must be positive")
    combined = union_queries(
        classical, neural, max_per_family=maximum_queries,
    )
    if calibration is not None:
        combined = conformal_query_set(
            combined, calibration, maximum_per_family=maximum_queries,
        )
    return tuple(sorted(
        combined, key=lambda row: (-row.confidence, row.id),
    )[:maximum_queries])


def audit_conformal_coverage(
    examples: Iterable[CalibrationExample], calibration: ConformalCalibration,
) -> dict[str, float]:
    thresholds = calibration.by_family(); by_family = {}
    for family in sorted({row.family for row in examples}):
        rows = [row for row in examples if row.family == family]
        threshold = thresholds.get(family)
        q = threshold.threshold if threshold else calibration.global_threshold
        by_family[family] = float(np.mean([row.nonconformity <= q for row in rows]))
    return by_family
