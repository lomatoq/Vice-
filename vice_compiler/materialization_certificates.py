"""M6: correspondence, separation and delivery identity (plan S4.2-S4.5, M6).

Counting components is not a topology proof.  The current TextLine claims
only that the candidate has at least as many components and holes as the
source; that census passes even when two letters fuse and one letter splits,
because the totals still match.  The human court found exactly that failure
("тут рамка засталася у б як трэба а у а усё злілося").

This module proves the missing statements:

    which source body became which delivered body,
    that no two source bodies fused without an explicit operator,
    that each counter stayed inside its own glyph,
    and that the delivered fragment is the one that was judged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import cv2
import numpy as np

from .vector_program import TextVectorProgram, serialize_text_vector_program

#: Bodies closer than this are "adjacent" and need a proven background gap.
ADJACENCY_DISTANCE_PX = 5.0
#: A delivered body below this share of a source body is not a real match.
MATCH_IOU_FLOOR = 0.10
#: Specks this small are antialiasing residue, not semantic bodies.
DEFAULT_MIN_BODY_AREA_PX = 4


# --------------------------------------------------------------------------
# S4.2 component correspondence
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentMatch:
    source_id: str
    delivered_id: str
    overlap_iou: float
    source_recall: float
    delivered_precision: float
    source_holes: int
    delivered_holes: int


@dataclass(frozen=True)
class TopologyCorrespondenceCertificate:
    valid: bool
    matches: tuple[ComponentMatch, ...]
    unmatched_source_ids: tuple[str, ...]
    unmatched_delivered_ids: tuple[str, ...]
    fused_source_groups: tuple[tuple[str, ...], ...]
    split_source_groups: tuple[tuple[str, ...], ...]
    counter_mismatches: tuple[str, ...]
    violations: tuple[str, ...] = ()


def _bodies(
    mask: np.ndarray, *, min_area: int,
) -> tuple[list[np.ndarray], list[int]]:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        np.asarray(mask, np.uint8), 8,
    )
    masks: list[np.ndarray] = []
    holes: list[int] = []
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) < min_area:
            continue
        body = labels == label
        masks.append(body)
        holes.append(_hole_count(body, min_area=min_area))
    return masks, holes


def _hole_count(body: np.ndarray, *, min_area: int) -> int:
    inverse = np.pad((~body).astype(np.uint8), 1, constant_values=1)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        inverse, 4,
    )
    outside = labels[0, 0]
    return int(sum(
        1 for label in range(1, count)
        if label != outside
        and int(stats[label, cv2.CC_STAT_AREA]) >= min_area
    ))


def component_correspondence(
    source_mask: np.ndarray, delivered_mask: np.ndarray, *,
    min_area: int = DEFAULT_MIN_BODY_AREA_PX,
    allow_fusion: bool = False,
) -> TopologyCorrespondenceCertificate:
    """Maximum-weight matching between source and delivered bodies (S4.2)."""
    source_bodies, source_holes = _bodies(source_mask, min_area=min_area)
    delivered_bodies, delivered_holes = _bodies(
        delivered_mask, min_area=min_area,
    )
    if not source_bodies:
        return TopologyCorrespondenceCertificate(
            valid=not delivered_bodies, matches=(), unmatched_source_ids=(),
            unmatched_delivered_ids=tuple(
                f"delivered-{index}" for index in range(len(delivered_bodies))
            ),
            fused_source_groups=(), split_source_groups=(),
            counter_mismatches=(),
            violations=("no-source-body",) if delivered_bodies else (),
        )
    overlap = np.zeros((len(source_bodies), len(delivered_bodies)))
    for i, source in enumerate(source_bodies):
        for j, delivered in enumerate(delivered_bodies):
            intersection = float(np.sum(source & delivered))
            if intersection <= 0.0:
                continue
            union = float(np.sum(source | delivered))
            overlap[i, j] = intersection / max(1.0, union)

    try:
        from scipy.optimize import linear_sum_assignment

        rows, columns = linear_sum_assignment(-overlap)
        assignment = {
            int(row): int(column) for row, column in zip(rows, columns)
            if overlap[row, column] > MATCH_IOU_FLOOR
        }
    except Exception:
        assignment = {}
        taken: set[int] = set()
        for i in np.argsort(-overlap.max(axis=1)):
            order = np.argsort(-overlap[i])
            for j in order:
                if int(j) in taken or overlap[i, j] <= MATCH_IOU_FLOOR:
                    continue
                assignment[int(i)] = int(j)
                taken.add(int(j))
                break

    matches: list[ComponentMatch] = []
    for i, j in sorted(assignment.items()):
        source = source_bodies[i]
        delivered = delivered_bodies[j]
        intersection = float(np.sum(source & delivered))
        matches.append(ComponentMatch(
            source_id=f"source-{i}", delivered_id=f"delivered-{j}",
            overlap_iou=float(overlap[i, j]),
            source_recall=intersection / max(1.0, float(np.sum(source))),
            delivered_precision=intersection / max(
                1.0, float(np.sum(delivered)),
            ),
            source_holes=source_holes[i], delivered_holes=delivered_holes[j],
        ))

    # A source body is "unmatched" only when NO delivered body carries it.
    # Losing the 1-1 assignment because a neighbour fused onto the same
    # delivered body is a fusion violation, reported separately - counting
    # it twice would make an explicit ligature impossible to admit.
    unmatched_source = tuple(
        f"source-{i}" for i in range(len(source_bodies))
        if float(np.max(overlap[i])) <= MATCH_IOU_FLOOR
    )
    unmatched_delivered = tuple(
        f"delivered-{j}" for j in range(len(delivered_bodies))
        if j not in set(assignment.values())
    )

    # Fusion: several source bodies land on one delivered body.
    fused: list[tuple[str, ...]] = []
    for j in range(len(delivered_bodies)):
        owners = [
            f"source-{i}" for i in range(len(source_bodies))
            if overlap[i, j] > MATCH_IOU_FLOOR
        ]
        if len(owners) > 1:
            fused.append(tuple(owners))
    # Split: one source body lands on several delivered bodies.
    split: list[tuple[str, ...]] = []
    for i in range(len(source_bodies)):
        pieces = [
            f"delivered-{j}" for j in range(len(delivered_bodies))
            if overlap[i, j] > MATCH_IOU_FLOOR
        ]
        if len(pieces) > 1:
            split.append(tuple(pieces))

    counter_mismatches = tuple(
        match.source_id for match in matches
        if match.delivered_holes < match.source_holes
    )
    violations: list[str] = []
    if unmatched_source:
        violations.append("persistent-source-body-unmatched")
    if unmatched_delivered:
        violations.append("unsupported-delivered-body")
    if fused and not allow_fusion:
        violations.append("source-bodies-fused-without-operator")
    if split:
        violations.append("source-body-split")
    if counter_mismatches:
        violations.append("counter-lost")
    return TopologyCorrespondenceCertificate(
        valid=not violations, matches=tuple(matches),
        unmatched_source_ids=unmatched_source,
        unmatched_delivered_ids=unmatched_delivered,
        fused_source_groups=tuple(fused), split_source_groups=tuple(split),
        counter_mismatches=counter_mismatches,
        violations=tuple(violations),
    )


# --------------------------------------------------------------------------
# S4.3 separation corridors
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SeparationCorridor:
    left_source_id: str
    right_source_id: str
    sampled_points_xy: tuple[tuple[float, float], ...]
    minimum_background_coverage: float
    native_pass: bool
    scale2_pass: bool
    scale4_pass: bool
    phase_pass_count: int


@dataclass(frozen=True)
class SeparationCertificate:
    valid: bool
    corridors: tuple[SeparationCorridor, ...]
    explicit_fusion_operator: str | None = None
    violations: tuple[str, ...] = ()


def gap_corridor_points(
    left: np.ndarray, right: np.ndarray, *, maximum_gap_px: float = 6.0,
    samples: int = 9,
) -> list[tuple[float, float]]:
    """Medial points of the background gap between two bodies (plan M6.3)."""
    left_distance = cv2.distanceTransform(
        (~left).astype(np.uint8), cv2.DIST_L2, 3,
    )
    right_distance = cv2.distanceTransform(
        (~right).astype(np.uint8), cv2.DIST_L2, 3,
    )
    background = ~(left | right)
    total = left_distance + right_distance
    ridge = (
        background
        & (np.abs(left_distance - right_distance) <= 1.0)
        & (total <= maximum_gap_px)
    )
    ys, xs = np.nonzero(ridge)
    if not len(xs):
        return []
    order = np.argsort(total[ys, xs])
    ys, xs = ys[order], xs[order]
    step = max(1, len(xs) // max(1, samples))
    chosen = [(float(xs[i]) + 0.5, float(ys[i]) + 0.5)
              for i in range(0, len(xs), step)][:samples]
    return chosen


def separation_certificate(
    source_mask: np.ndarray, rendered_alphas: dict[str, np.ndarray], *,
    min_area: int = DEFAULT_MIN_BODY_AREA_PX,
    explicit_fusion_operator: str | None = None,
    coverage_threshold: float = 0.5,
) -> SeparationCertificate:
    """Adjacent source bodies must stay separated in the DELIVERED render.

    ``rendered_alphas`` maps a scale/phase label to a canvas-sized alpha in
    [0, 1]; the native entry must be present.  Multi-scale checking is the
    plan's M6.4 requirement: a bridge that only appears at 2x is still a
    bridge in the user's zoomed SVG.
    """
    bodies, _holes = _bodies(source_mask, min_area=min_area)
    corridors: list[SeparationCorridor] = []
    violations: list[str] = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            left, right = bodies[i], bodies[j]
            distance = cv2.distanceTransform(
                (~left).astype(np.uint8), cv2.DIST_L2, 3,
            )
            if float(np.min(distance[right])) > ADJACENCY_DISTANCE_PX:
                continue
            points = gap_corridor_points(left, right)
            if not points:
                continue
            results: dict[str, bool] = {}
            worst = 1.0
            for label, alpha in rendered_alphas.items():
                array = np.asarray(alpha, np.float32)
                height, width = array.shape[:2]
                scale_y = height / source_mask.shape[0]
                scale_x = width / source_mask.shape[1]
                values = []
                for x, y in points:
                    px = min(width - 1, max(0, int(x * scale_x)))
                    py = min(height - 1, max(0, int(y * scale_y)))
                    values.append(float(array[py, px]))
                worst = min(worst, 1.0 - max(values) if values else 1.0)
                results[label] = all(
                    value < coverage_threshold for value in values
                )
            corridor = SeparationCorridor(
                left_source_id=f"source-{i}", right_source_id=f"source-{j}",
                sampled_points_xy=tuple(points),
                minimum_background_coverage=float(worst),
                native_pass=bool(results.get("native", True)),
                scale2_pass=bool(results.get("scale2", True)),
                scale4_pass=bool(results.get("scale4", True)),
                phase_pass_count=int(sum(
                    1 for label, ok in results.items()
                    if label.startswith("phase") and ok
                )),
            )
            corridors.append(corridor)
            if not all(results.values()) and explicit_fusion_operator is None:
                violations.append(
                    f"fusion-{corridor.left_source_id}-"
                    f"{corridor.right_source_id}",
                )
    return SeparationCertificate(
        valid=not violations, corridors=tuple(corridors),
        explicit_fusion_operator=explicit_fusion_operator,
        violations=tuple(violations),
    )


# --------------------------------------------------------------------------
# S4.5 delivery identity
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeliveryIdentityCertificate:
    valid: bool
    program_sha256: str
    svg_fragment_sha256: str
    rendered_rgba_sha256: str
    serializer_version: str
    renderer_version: str
    violations: tuple[str, ...] = ()


def delivery_identity_certificate(
    program: TextVectorProgram, *, rendered_rgba_sha256: str,
) -> DeliveryIdentityCertificate:
    from .svg_fragment_renderer import RENDERER_VERSION
    from .vector_program import SERIALIZER_VERSION, program_digest

    fragment = serialize_text_vector_program(program)
    fragment_sha = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
    violations: list[str] = []
    if fragment_sha != program.exact_fragment_sha256:
        violations.append("fragment-digest-mismatch")
    if program_digest(program) != program.program_sha256:
        violations.append("program-digest-mismatch")
    return DeliveryIdentityCertificate(
        valid=not violations, program_sha256=program.program_sha256,
        svg_fragment_sha256=fragment_sha,
        rendered_rgba_sha256=rendered_rgba_sha256,
        serializer_version=SERIALIZER_VERSION,
        renderer_version=RENDERER_VERSION, violations=tuple(violations),
    )


# --------------------------------------------------------------------------
# bundle
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MaterializationCertificates:
    """Everything the materialization court checks before it compares."""

    topology: TopologyCorrespondenceCertificate | None = None
    separation: SeparationCertificate | None = None
    fairness: object | None = None
    appearance: object | None = None
    identity: DeliveryIdentityCertificate | None = None
    extra: tuple[tuple[str, object], ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        for certificate in (
            self.topology, self.separation, self.fairness, self.appearance,
            self.identity,
        ):
            if certificate is not None and not getattr(
                certificate, "valid", True,
            ):
                return False
        return True

    def violations(self) -> tuple[str, ...]:
        found: list[str] = []
        for name, certificate in (
            ("topology", self.topology), ("separation", self.separation),
            ("fairness", self.fairness), ("appearance", self.appearance),
            ("identity", self.identity),
        ):
            if certificate is None:
                continue
            if not getattr(certificate, "valid", True):
                reasons = getattr(certificate, "violations", ())
                found.extend(
                    f"{name}:{reason}" for reason in (reasons or ("invalid",))
                )
        return tuple(found)
