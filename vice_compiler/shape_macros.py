"""Phase-5 whole-shape and repeated-parameter macro generator.

The generator consumes only immutable REIR evidence.  Every analytic proposal
is rendered back to the native lattice and must pass topology, angular/support
and boundary-preimage walls before it becomes a CMIR column.  Near-circle to
circle is therefore a selection candidate, never a post-hoc snap.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Iterable, TYPE_CHECKING

import cv2
import numpy as np

from .certificates import mask_sha256, topology_signature
from .evidence_ir import RasterEvidenceIR
from .macro_ir import MacroCandidate, MacroKind, ResourceEstimate, SceneProgram
from .macro_registry import (
    candidate_from_support, decode_token_mask, descendant_leaf_bits,
    encode_mask_rle, leaf_bits_mask, rekey_draft_candidate,
)
from .proposal_net import query_support_mask

if TYPE_CHECKING:
    from .proposal_net import ProposalQuery


@dataclass(frozen=True)
class ShapeFitRecord:
    candidate: MacroCandidate
    primitive: str
    source_mask: np.ndarray
    rendered_mask: np.ndarray
    parameters: tuple[tuple[str, float | int | str], ...]
    iou: float
    boundary_p95_px: float
    angular_coverage: float
    condition_number: float
    source_token_ids: tuple[int, ...]

    def validate(self, reir: RasterEvidenceIR) -> None:
        shape = (reir.height, reir.width)
        if (
            self.source_mask.shape != shape
            or self.rendered_mask.shape != shape
            or self.source_mask.flags.writeable
            or self.rendered_mask.flags.writeable
        ):
            raise ValueError("shape fit masks must be immutable REIR lattices")
        if not 0.0 <= self.iou <= 1.0 or not 0.0 <= self.angular_coverage <= 1.0:
            raise ValueError("shape fit evidence lies outside [0,1]")
        if not math.isfinite(self.boundary_p95_px) or self.boundary_p95_px < 0:
            raise ValueError("shape boundary error is invalid")
        # Generators return draft candidates.  The global registry assigns the
        # final index and conflict bitmap later, so validate through a temporary
        # one-column view without mutating the immutable draft.
        replace(self.candidate, registry_index=0, conflict_bits=0).validate(
            leaf_count=reir.hierarchy.leaf_count,
            interface_count=len(reir.interfaces.interfaces),
            candidate_count=1,
        )


@dataclass(frozen=True)
class RepeatedShapeGroup:
    candidate: MacroCandidate
    primitive: str
    member_ids: tuple[str, ...]
    shared_parameters: tuple[tuple[str, float], ...]
    residuals: tuple[tuple[str, float], ...]
    mdl_saving_bits: float


@dataclass(frozen=True)
class ShapeMacroSet:
    records: tuple[ShapeFitRecord, ...]
    groups: tuple[RepeatedShapeGroup, ...]
    rois_considered: int
    candidates_pruned: int
    provenance: tuple[str, ...]

    @property
    def candidates(self) -> tuple[MacroCandidate, ...]:
        return tuple(row.candidate for row in self.records) + tuple(
            row.candidate for row in self.groups
        )


def _freeze(mask: np.ndarray) -> np.ndarray:
    result = np.ascontiguousarray(mask, dtype=bool)
    result.setflags(write=False)
    return result


def _bbox(mask: np.ndarray, pad: int = 1) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("cannot bound an empty shape")
    return (
        max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + 1 + pad),
        min(mask.shape[0], int(ys.max()) + 1 + pad),
    )


def _boundary(mask: np.ndarray) -> np.ndarray:
    return cv2.morphologyEx(
        np.asarray(mask, np.uint8), cv2.MORPH_GRADIENT,
        np.ones((3, 3), np.uint8),
    ) > 0


def _boundary_error(first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
    union = np.asarray(first, dtype=bool) | np.asarray(second, dtype=bool)
    if not np.any(union):
        return 0.0, 0.0
    x1, y1, x2, y2 = _bbox(union, pad=4)
    first = np.asarray(first, dtype=bool)[y1:y2, x1:x2]
    second = np.asarray(second, dtype=bool)[y1:y2, x1:x2]
    a = _boundary(first); b = _boundary(second)
    if not np.any(a) or not np.any(b):
        diagonal = float(math.hypot(*first.shape))
        return diagonal, diagonal
    to_a = cv2.distanceTransform((~a).astype(np.uint8), cv2.DIST_L2, 5)
    to_b = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 5)
    distances = np.concatenate((to_a[b], to_b[a])).astype(np.float64)
    return float(np.quantile(distances, 0.95)), float(np.max(distances))


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    intersection = int(np.sum(first & second)); union = int(np.sum(first | second))
    return intersection / max(1, union)


def _angular_coverage(contour: np.ndarray, center: tuple[float, float]) -> float:
    points = contour.reshape((-1, 2)).astype(np.float64)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    bins = np.unique(np.floor((angles + np.pi) * (24.0 / (2.0 * np.pi))).astype(int))
    return float(min(1.0, len(bins) / 24.0))


def _render_circle(
    shape: tuple[int, int], center: tuple[float, float], radius: float,
) -> np.ndarray:
    result = np.zeros(shape, np.uint8)
    cv2.circle(
        result, (int(round(center[0])), int(round(center[1]))),
        max(1, int(round(radius))), 1, -1, lineType=cv2.LINE_AA,
    )
    return result > 0


def _render_ellipse(
    shape: tuple[int, int], center: tuple[float, float],
    axes: tuple[float, float], angle: float,
) -> np.ndarray:
    result = np.zeros(shape, np.uint8)
    cv2.ellipse(
        result, (int(round(center[0])), int(round(center[1]))),
        (max(1, int(round(axes[0]))), max(1, int(round(axes[1])))),
        float(angle), 0.0, 360.0, 1, -1, lineType=cv2.LINE_AA,
    )
    return result > 0


def _render_polygon(shape: tuple[int, int], points: np.ndarray) -> np.ndarray:
    result = np.zeros(shape, np.uint8)
    cv2.fillPoly(result, [np.round(points).astype(np.int32)], 1, lineType=cv2.LINE_AA)
    return result > 0


def _render_rounded_rect(
    shape: tuple[int, int], bbox: tuple[int, int, int, int], radius: float,
) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    r = max(1, min(int(round(radius)), (x2 - x1) // 2, (y2 - y1) // 2))
    result = np.zeros(shape, np.uint8)
    cv2.rectangle(result, (x1 + r, y1), (x2 - r - 1, y2 - 1), 1, -1)
    cv2.rectangle(result, (x1, y1 + r), (x2 - 1, y2 - r - 1), 1, -1)
    for center in ((x1 + r, y1 + r), (x2 - r - 1, y1 + r),
                   (x1 + r, y2 - r - 1), (x2 - r - 1, y2 - r - 1)):
        cv2.circle(result, center, r, 1, -1, lineType=cv2.LINE_AA)
    return result > 0


def _render_bullet(
    shape: tuple[int, int], bbox: tuple[int, int, int, int], left_round: bool,
) -> np.ndarray:
    x1, y1, x2, y2 = bbox; radius = max(1, (y2 - y1) // 2)
    result = np.zeros(shape, np.uint8)
    if left_round:
        center = (x1 + radius, (y1 + y2 - 1) // 2)
        cv2.rectangle(result, center, (x2 - 1, y2 - 1), 1, -1)
    else:
        center = (x2 - radius - 1, (y1 + y2 - 1) // 2)
        cv2.rectangle(result, (x1, y1), center, 1, -1)
    cv2.circle(result, center, radius, 1, -1, lineType=cv2.LINE_AA)
    return result > 0


def _candidate_rows(
    source: np.ndarray,
) -> Iterable[tuple[str, tuple[tuple[str, float | int | str], ...], np.ndarray, float, float]]:
    """Yield primitive, params, native render, coverage, condition."""
    binary = np.asarray(source, np.uint8)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None or not contours:
        return
    outer_ids = [index for index, row in enumerate(hierarchy[0]) if int(row[3]) < 0]
    if len(outer_ids) != 1:
        return
    contour = contours[outer_ids[0]]
    if len(contour) < 4:
        return
    area = max(1.0, abs(float(cv2.contourArea(contour))))
    perimeter = max(1.0, float(cv2.arcLength(contour, True)))
    moments = cv2.moments(contour)
    center = (
        float(moments["m10"] / moments["m00"]),
        float(moments["m01"] / moments["m00"]),
    ) if abs(moments["m00"]) > 1e-9 else tuple(map(float, contour[0, 0]))
    coverage = _angular_coverage(contour, center)
    x, y, width, height = cv2.boundingRect(contour)
    condition = max(width, height) / max(1.0, min(width, height))

    # Circle / ring.
    radius = math.sqrt(area / math.pi)
    circle = _render_circle(source.shape, center, radius)
    if len(outer_ids) == 1 and 0.72 <= width / max(1.0, height) <= 1.38:
        if topology_signature(source) == (1, 1):
            children = [i for i, row in enumerate(hierarchy[0]) if int(row[3]) == outer_ids[0]]
            if len(children) == 1:
                inner = contours[children[0]]
                inner_area = max(1.0, abs(float(cv2.contourArea(inner))))
                im = cv2.moments(inner)
                inner_center = (
                    float(im["m10"] / im["m00"]), float(im["m01"] / im["m00"])
                ) if abs(im["m00"]) > 1e-9 else center
                ring = circle.astype(np.uint8)
                cv2.circle(
                    ring, (int(round(inner_center[0])), int(round(inner_center[1]))),
                    max(1, int(round(math.sqrt(inner_area / math.pi)))), 0, -1,
                    lineType=cv2.LINE_AA,
                )
                yield "ring", (
                    ("cx", center[0]), ("cy", center[1]), ("radius", radius),
                    ("inner_cx", inner_center[0]), ("inner_cy", inner_center[1]),
                    ("inner_radius", math.sqrt(inner_area / math.pi)),
                ), ring > 0, coverage, condition
        else:
            yield "circle", (("cx", center[0]), ("cy", center[1]),
                             ("radius", radius)), circle, coverage, condition

    if len(contour) >= 5:
        (cx, cy), (axis_a, axis_b), angle = cv2.fitEllipse(contour)
        ellipse = _render_ellipse(
            source.shape, (cx, cy), (axis_a / 2.0, axis_b / 2.0), angle,
        )
        ellipse_condition = max(axis_a, axis_b) / max(1.0, min(axis_a, axis_b))
        yield "ellipse", (
            ("cx", float(cx)), ("cy", float(cy)),
            ("rx", float(axis_a / 2.0)), ("ry", float(axis_b / 2.0)),
            ("angle", float(angle)),
        ), ellipse, coverage, ellipse_condition

    approx = cv2.approxPolyDP(contour, 0.018 * perimeter, True).reshape((-1, 2))
    if len(approx) in {3, 4} and cv2.isContourConvex(approx.astype(np.int32)):
        primitive = "triangle" if len(approx) == 3 else "quadrilateral"
        yield primitive, tuple(
            (f"p{index}_{axis}", float(point[coordinate]))
            for index, point in enumerate(approx)
            for coordinate, axis in enumerate(("x", "y"))
        ), _render_polygon(source.shape, approx), coverage, condition

    rect = (x, y, x + width, y + height)
    rectangle = np.zeros(source.shape, np.uint8)
    cv2.rectangle(rectangle, (x, y), (x + width - 1, y + height - 1), 1, -1)
    yield "rectangle", (("x", x), ("y", y), ("width", width),
                        ("height", height)), rectangle > 0, coverage, condition
    for fraction in (0.12, 0.22, 0.34):
        rounded = _render_rounded_rect(source.shape, rect, min(width, height) * fraction)
        yield "rounded_rectangle", (
            ("x", x), ("y", y), ("width", width), ("height", height),
            ("radius", min(width, height) * fraction),
        ), rounded, coverage, condition

    if 1.35 <= condition <= 5.0:
        for left_round in (True, False):
            yield "D_bullet", (
                ("x", x), ("y", y), ("width", width), ("height", height),
                ("round_side", "left" if left_round else "right"),
            ), _render_bullet(source.shape, rect, left_round), coverage, condition

    if 8 <= len(approx) <= 16:
        radii = np.linalg.norm(approx.astype(np.float64) - np.asarray(center), axis=1)
        if len(radii) >= 8:
            even = float(np.mean(radii[::2])); odd = float(np.mean(radii[1::2]))
            alternation = min(even, odd) / max(1e-6, max(even, odd))
            if alternation <= 0.78:
                yield "star", tuple(
                    (f"p{index}_{axis}", float(point[coordinate]))
                    for index, point in enumerate(approx)
                    for coordinate, axis in enumerate(("x", "y"))
                ), _render_polygon(source.shape, approx), coverage, condition

    curve_parameters: tuple[tuple[str, float | int | str], ...] = (
        ("contour_vertices", int(len(contour))),
    )
    if topology_signature(source) == (1, 0):
        # Keep a bounded set of physical anchors in CMIR.  These are the
        # actual control variables later consumed by the SVG writer, rather
        # than a diagnostic vertex count that cannot change delivery.
        reduced = None
        for fraction in (0.010, 0.014, 0.020, 0.028, 0.040, 0.060):
            proposal = cv2.approxPolyDP(
                contour, max(0.35, fraction * perimeter), True,
            ).reshape((-1, 2))
            if 3 <= len(proposal) <= 24:
                reduced = proposal
                break
        if reduced is not None:
            curve_parameters = (
                *curve_parameters,
                ("curve_point_count", int(len(reduced))),
                ("curve_tension", 1.0),
                *tuple(
                    (f"curve_p{index}_{axis}", float(point[coordinate]))
                    for index, point in enumerate(reduced)
                    for coordinate, axis in enumerate(("x", "y"))
                ),
            )
    yield "free_curve", curve_parameters, source, 1.0, condition


def _dominant_color_unions(
    reir: RasterEvidenceIR, *, limit: int = 6,
) -> list[tuple[np.ndarray, tuple[str, ...]]]:
    """Return color-coherent visible fragments for occlusion-aware fitting.

    A whole authored shape can be split into several connected components by
    foreground lettering or a knockout.  Component-only proposal generation
    can never recover that carrier.  These masks use only hard, dominant
    source colors; antialias shades and the border background are excluded.
    """
    rgba = np.asarray(reir.raster.straight_rgba, np.float32)
    rgb = np.clip(np.round(rgba[..., :3] * 255.0), 0, 255).astype(np.uint8)
    opaque = rgba[..., 3] >= 0.50
    if not np.any(opaque):
        return []
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    background = np.median(border, axis=0)
    quantized = (rgb.astype(np.int32) // 16).clip(0, 15)
    keys = quantized[..., 0] * 256 + quantized[..., 1] * 16 + quantized[..., 2]
    counts = np.bincount(keys[opaque].ravel(), minlength=4096)
    minimum = max(16, int(round(0.004 * reir.width * reir.height)))
    rows: list[tuple[np.ndarray, tuple[str, ...]]] = []
    for key in np.argsort(counts)[::-1]:
        if int(counts[key]) < minimum or len(rows) >= limit:
            break
        seed = (keys == int(key)) & opaque
        if not np.any(seed):
            continue
        color = np.median(rgb[seed].astype(np.float32), axis=0)
        if float(np.linalg.norm(color - background)) < 28.0:
            continue
        distance = np.linalg.norm(rgb.astype(np.float32) - color, axis=2)
        mask = (distance <= 24.0) & opaque
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), 8,
        )
        cleaned = np.zeros(mask.shape, bool)
        for label in range(1, count):
            if int(stats[label, cv2.CC_STAT_AREA]) >= 4:
                cleaned |= labels == label
        area = int(cleaned.sum())
        if not (minimum <= area <= int(0.90 * cleaned.size)):
            continue
        frozen = _freeze(cleaned)
        digest = mask_sha256(frozen)
        if any(mask_sha256(previous) == digest for previous, _ in rows):
            continue
        rows.append((
            frozen,
            (
                "occlusion-color-union",
                f"dominant-rgb:{int(color[0])},{int(color[1])},{int(color[2])}",
            ),
        ))
    return rows


def _occlusion_candidate_rows(
    source: np.ndarray,
) -> Iterable[tuple[str, tuple[tuple[str, float | int | str], ...], np.ndarray, float, float]]:
    """Fit complete carriers to disconnected, same-color visible fragments."""
    points_yx = np.argwhere(source)
    if len(points_yx) < 12:
        return
    points = points_yx[:, ::-1].astype(np.float32)
    hull = cv2.convexHull(points.reshape((-1, 1, 2)))
    if len(hull) < 5:
        return
    hull_mask = np.zeros(source.shape, np.uint8)
    cv2.fillConvexPoly(hull_mask, np.round(hull).astype(np.int32), 1)
    hull_bool = hull_mask > 0

    # The exact visible union is the conservative alternative to every hidden
    # completion.  It groups same-color fragments into one editable compound
    # path but never invents pixels behind an occluder.
    yield "free_curve", (
        ("contour_vertices", int(len(points))),
        ("visible_color_union", 1),
    ), source, 1.0, 1.0

    (cx, cy), radius = cv2.minEnclosingCircle(hull)
    circle = _render_circle(source.shape, (float(cx), float(cy)), float(radius))
    radial = np.linalg.norm(hull.reshape((-1, 2)) - np.asarray((cx, cy)), axis=1)
    circle_residual = float(np.sqrt(np.mean((radial - radius) ** 2)) / max(1.0, radius))
    circle_hull_iou = _iou(circle, hull_bool)
    if circle_residual <= 0.055 and circle_hull_iou >= 0.88:
        yield "circle", (
            ("cx", float(cx)), ("cy", float(cy)), ("radius", float(radius)),
            ("occlusion_completion", 1),
        ), circle, 1.0, 1.0

    (ex, ey), (axis_a, axis_b), angle = cv2.fitEllipse(hull)
    ellipse = _render_ellipse(
        source.shape, (float(ex), float(ey)),
        (float(axis_a) / 2.0, float(axis_b) / 2.0), float(angle),
    )
    ellipse_hull_iou = _iou(ellipse, hull_bool)
    condition = max(axis_a, axis_b) / max(1.0, min(axis_a, axis_b))
    if ellipse_hull_iou >= 0.90 and condition <= 8.0:
        yield "ellipse", (
            ("cx", float(ex)), ("cy", float(ey)),
            ("rx", float(axis_a) / 2.0), ("ry", float(axis_b) / 2.0),
            ("angle", float(angle)), ("occlusion_completion", 1),
        ), ellipse, 1.0, float(condition)


def _source_rois(
    reir: RasterEvidenceIR, max_rois: int,
    proposal_queries: Iterable["ProposalQuery"] = (),
    protected_text_masks: Iterable[np.ndarray] = (),
) -> list[tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]]:
    rows: list[tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]] = []
    protected = tuple(np.asarray(mask, bool) for mask in protected_text_masks)

    def text_claims(mask: np.ndarray) -> bool:
        area = max(1, int(np.sum(mask)))
        return any(
            int(np.sum(mask & text_mask)) / area >= 0.50
            for text_mask in protected
        )
    for token in reir.proposal_tokens:
        if token.family not in {"shape", "component", "topology", "symmetry"}:
            continue
        mask = decode_token_mask(token, (reir.height, reir.width))
        if mask is None or not np.any(mask):
            continue
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            np.asarray(mask, np.uint8), 8,
        )
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < 6:
                continue
            component = labels == label
            if text_claims(component):
                continue
            rows.append((
                _freeze(component), (token.id,), float(token.score),
                (token.provenance, f"component:{label}"),
            ))
    leaf_bits = descendant_leaf_bits(reir)
    for node in sorted(
        (row for row in reir.hierarchy.nodes if row.left is not None),
        key=lambda row: (-row.merge_level, row.area, row.id),
    )[:16]:
        mask = leaf_bits_mask(reir, leaf_bits[node.id])
        if (
            6 <= int(mask.sum()) <= int(0.80 * mask.size)
            and not text_claims(mask)
        ):
            rows.append((
                _freeze(mask), (), float(np.clip(1.0 - node.merge_level, 0, 1)),
                ("ucm-closed-region", f"node:{node.id}"),
            ))
    for mask, provenance in _dominant_color_unions(reir):
        # Reserve the very small occlusion-aware bank ahead of noisy token
        # fragments.  Without this priority a 20-ROI Balanced budget was
        # exhausted by connected pieces and could never even propose the
        # complete carrier they collectively support.
        if not text_claims(mask):
            rows.append((mask, (), 1.15, provenance))
    for query in proposal_queries:
        if query.family not in {"whole_shape", "symmetry_repeat_group"}:
            continue
        mask = query_support_mask(reir, query, minimum_pixels=6)
        if mask is None or int(mask.sum()) > int(0.90 * mask.size):
            continue
        if text_claims(mask):
            continue
        from .proposal_net import query_head_prior_score
        query_score, head_provenance = query_head_prior_score(
            query, mask,
            expected_relation_groups=(
                ("same_group",), ("repeat", "mirror"),
            ) if query.family == "symmetry_repeat_group" else (),
        )
        rows.append((
            mask, (), query_score,
            ("ProposalNet-guided-before-shape-fitting", query.id,
             *head_provenance, *query.provenance),
        ))
    unique: dict[str, tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]] = {}
    for row in rows:
        digest = mask_sha256(row[0])
        previous = unique.get(digest)
        if previous is None or row[2] > previous[2]:
            unique[digest] = row
    return sorted(
        unique.values(), key=lambda row: (-row[2], -int(row[0].sum()), mask_sha256(row[0]))
    )[:max(1, min(64, int(max_rois)))]


def _make_record(
    reir: RasterEvidenceIR, source: np.ndarray, token_ids: tuple[int, ...],
    source_score: float, provenance: tuple[str, ...], primitive: str,
    parameters: tuple[tuple[str, float | int | str], ...], rendered: np.ndarray,
    angular: float, condition: float,
) -> ShapeFitRecord | None:
    rendered = np.asarray(rendered, bool)
    rgba = np.asarray(reir.raster.straight_rgba, np.float32)
    border = np.concatenate((
        rgba[0], rgba[-1], rgba[:, 0], rgba[:, -1],
    ))
    background = np.median(border, axis=0)
    source_color = np.median(rgba[source], axis=0)
    if (
        float(np.linalg.norm(source_color[:3] - background[:3])) < 0.035
        and abs(float(source_color[3] - background[3])) < 0.08
    ):
        return None
    iou = _iou(source, rendered)
    analytic = primitive != "free_curve"
    if not analytic:
        area_fraction = float(np.sum(source) / max(1, source.size))
        sx1, sy1, sx2, sy2 = _bbox(source)
        border_contacts = sum((
            sx1 <= 0, sy1 <= 0,
            sx2 >= source.shape[1], sy2 >= source.shape[0],
        ))
        # A canvas/background-sized exact mask path is not a typed geometric
        # explanation; it duplicates the hierarchy lane and creates giant
        # overlapping contours.  Keep free curves local and let analytic
        # carriers compete for large authored regions.
        if area_fraction > 0.50 or border_contacts >= 2:
            return None
    occlusion_source = "occlusion-color-union" in provenance
    occlusion_completion = occlusion_source and analytic
    source_coverage = float(np.sum(source & rendered) / max(1, np.sum(source)))
    visible_fraction = float(np.sum(source & rendered) / max(1, np.sum(rendered)))
    # IoU is a necessary wall and much cheaper than topology/distance fields.
    # Failed analytic proposals must not consume exact-court work.
    if analytic and not occlusion_completion and iou < 0.78:
        return None
    if occlusion_completion and (
        source_coverage < 0.975 or visible_fraction < 0.35
    ):
        return None
    source_bbox = _bbox(source)
    x1, y1, x2, y2 = source_bbox
    rendered_bbox = _bbox(rendered)
    ux1 = min(x1, rendered_bbox[0]); uy1 = min(y1, rendered_bbox[1])
    ux2 = max(x2, rendered_bbox[2]); uy2 = max(y2, rendered_bbox[3])
    source_topology = topology_signature(source[uy1:uy2, ux1:ux2])
    rendered_topology = topology_signature(rendered[uy1:uy2, ux1:ux2])
    topology_ok = source_topology == rendered_topology
    if not topology_ok and not occlusion_completion:
        return None
    occlusion_hull_iou = 0.0
    if not analytic:
        p95, _maximum = 0.0, 0.0
    elif occlusion_completion:
        points = np.argwhere(source)[:, ::-1].astype(np.int32)
        hull = cv2.convexHull(points.reshape((-1, 1, 2)))
        hull_mask = np.zeros(source.shape, np.uint8)
        cv2.fillConvexPoly(hull_mask, hull, 1)
        occlusion_hull_iou = _iou(hull_mask > 0, rendered)
        p95, _maximum = _boundary_error(hull_mask > 0, rendered)
    else:
        p95, _maximum = _boundary_error(source, rendered)
    diagonal = math.hypot(x2 - x1, y2 - y1)
    tolerance = max(1.25, min(2.5, 0.035 * diagonal))
    completion_tolerance = max(tolerance, min(10.0, 0.02 * diagonal))
    admissible = (
        (topology_ok or occlusion_completion) and (
            not analytic or (
                (iou >= 0.78 or (
                    occlusion_completion and occlusion_hull_iou >= 0.97
                ))
                and p95 <= (
                    completion_tolerance if occlusion_completion else tolerance
                )
                and (angular >= 0.58 or primitive in {
                    "rectangle", "rounded_rectangle", "triangle",
                    "quadrilateral", "D_bullet", "star",
                })
            )
        )
    )
    if not admissible:
        return None
    complexity_bonus = {
        "circle": 0.18, "ring": 0.20, "ellipse": 0.14,
        "rectangle": 0.16, "rounded_rectangle": 0.15,
        "triangle": 0.14, "quadrilateral": 0.10, "star": 0.10,
        "D_bullet": 0.11, "free_curve": 0.01,
    }[primitive]
    fidelity = source_coverage if occlusion_completion else iou
    score = float(np.clip(
        0.50 * fidelity + 0.18 * math.exp(-p95 / max(0.5, tolerance))
        + 0.14 * source_score + complexity_bonus, 0.0, 1.5,
    ))
    frozen_source = _freeze(source); frozen_rendered = _freeze(rendered)
    candidate = candidate_from_support(
        reir, family="shape", mask=frozen_source,
        roi_xyxy=rendered_bbox, evidence_token_ids=token_ids,
        score=score, kind=MacroKind.SHAPE,
        components=source_topology[0], holes=source_topology[1],
        prefix=f"shape-{primitive}",
        core_fraction=1.0 if occlusion_completion else 0.50,
        provenance=(
            "phase5-whole-shape", f"primitive:{primitive}", *provenance,
        ),
    )
    if candidate is None:
        return None
    notes = candidate.certificates.notes + (
        f"iou={iou:.6f}", f"boundary_p95={p95:.6f}",
        f"angular_coverage={angular:.6f}",
        f"source_coverage={source_coverage:.6f}",
        f"visible_fraction={visible_fraction:.6f}",
        f"occlusion_hull_iou={occlusion_hull_iou:.6f}",
        "digital-preimage-feasible", "topology-preserved",
    )
    candidate = replace(
        candidate,
        hidden_geometry=((
            "mode", "analytic-occlusion-completion"
        ), (
            "full_support_rle", encode_mask_rle(frozen_rendered)
        )) if occlusion_completion else None,
        program=SceneProgram(f"Shape/{primitive}", parameters),
        continuous_params=tuple(
            (name, float(value)) for name, value in parameters
            if isinstance(value, (float, int)) and (
                primitive != "free_curve"
                or name == "curve_tension"
                or name.startswith("curve_p") and name.endswith(("_x", "_y"))
            )
        ),
        covariance=tuple(
            max(0.02, 0.08 * (1.0 + condition))
            for _name, value in parameters if isinstance(value, (float, int))
        ),
        certificates=replace(candidate.certificates, notes=notes),
        prerequisite_claims=(
            "type-specific-identifiability-wall", "digital-preimage-feasible",
            "native-topology-preserved", "bounded-render-residual",
            *(('visible-ownership-before-hidden-completion',)
              if occlusion_completion else ()),
        ),
        resource_estimate=ResourceEstimate(
            fitting_ms=0.12, render_pixels=int(frozen_rendered.sum()),
            memory_bytes=512, solver_variables=1,
        ),
    )
    candidate = rekey_draft_candidate(candidate, prefix=f"shape-{primitive}")
    return ShapeFitRecord(
        candidate=candidate, primitive=primitive,
        source_mask=frozen_source, rendered_mask=frozen_rendered,
        parameters=parameters, iou=iou, boundary_p95_px=p95,
        angular_coverage=angular, condition_number=condition,
        source_token_ids=token_ids,
    )


def _parameter(record: ShapeFitRecord, name: str) -> float | None:
    values = dict(record.parameters)
    value = values.get(name)
    return float(value) if isinstance(value, (float, int)) else None


def _record_center(record: ShapeFitRecord) -> tuple[float, float] | None:
    values = dict(record.candidate.program.parameters)
    if isinstance(values.get("cx"), (float, int)) and isinstance(
        values.get("cy"), (float, int)
    ):
        return float(values["cx"]), float(values["cy"])
    if all(isinstance(values.get(name), (float, int)) for name in (
        "x", "y", "width", "height",
    )):
        return (
            float(values["x"]) + 0.5 * float(values["width"]),
            float(values["y"]) + 0.5 * float(values["height"]),
        )
    return None


def materialize_repeated_group_members(
    group: RepeatedShapeGroup, records: tuple[ShapeFitRecord, ...],
    *, shared_scale: float | None = None, shared_gap: float | None = None,
) -> tuple[MacroCandidate, ...]:
    """Apply a group's shared physical parameter to its member programs."""
    lookup = {row.candidate.id: row for row in records}
    shared = (
        float(shared_scale) if shared_scale is not None
        else dict(group.shared_parameters).get("scale")
    )
    if shared is None:
        return ()
    shared_rows = dict(group.shared_parameters)
    gap = (
        float(shared_gap) if shared_gap is not None
        else shared_rows.get("gap")
    )
    axis = np.asarray((
        shared_rows.get("axis_x", 0.0), shared_rows.get("axis_y", 0.0),
    ), np.float64)
    axis_norm = float(np.linalg.norm(axis))
    if gap is not None and axis_norm > 1e-9:
        axis /= axis_norm
    else:
        gap = None
    member_records = [lookup.get(member_id) for member_id in group.member_ids]
    if any(record is None for record in member_records):
        return ()
    typed_records = [record for record in member_records if record is not None]
    shifts: dict[str, tuple[float, float]] = {}
    if gap is not None and len(typed_records) >= 2:
        centers = [_record_center(record) for record in typed_records]
        if all(center is not None for center in centers):
            center_array = np.asarray(centers, np.float64)
            projections = center_array @ axis
            order = np.argsort(projections)
            group_center = float(np.mean(projections))
            offsets = (
                np.arange(len(order), dtype=np.float64)
                - 0.5 * (len(order) - 1)
            ) * float(gap)
            for rank, member_index in enumerate(order):
                delta = group_center + offsets[rank] - projections[member_index]
                shifts[typed_records[member_index].candidate.id] = (
                    float(delta * axis[0]), float(delta * axis[1]),
                )
    output: list[MacroCandidate] = []
    for member_id in group.member_ids:
        record = lookup.get(member_id)
        if record is None:
            return ()
        parameters = list(record.candidate.program.parameters)
        target_name = {
            "circle": "radius", "ring": "radius",
            "ellipse": "rx", "rectangle": "width",
            "rounded_rectangle": "width",
        }.get(group.primitive)
        if target_name is None:
            return ()
        updated = tuple(
            (name, float(shared) if name == target_name else value)
            for name, value in parameters
        )
        dx, dy = shifts.get(record.candidate.id, (0.0, 0.0))
        updated = tuple(
            (
                name,
                float(value) + dx if name in {"cx", "x"}
                else float(value) + dy if name in {"cy", "y"}
                else value,
            )
            for name, value in updated
        )
        continuous = tuple(
            (
                name,
                float(shared) if name == target_name
                else float(value) + dx if name in {"cx", "x"}
                else float(value) + dy if name in {"cy", "y"}
                else value,
            )
            for name, value in record.candidate.continuous_params
        )
        output.append(replace(
            record.candidate,
            program=SceneProgram(record.candidate.program.operator, updated),
            continuous_params=continuous,
        ))
    return tuple(output)


def _repeated_groups(
    reir: RasterEvidenceIR, records: tuple[ShapeFitRecord, ...],
    *, max_groups: int = 16,
) -> tuple[RepeatedShapeGroup, ...]:
    rows: list[RepeatedShapeGroup] = []
    for primitive in ("circle", "ring", "ellipse", "rectangle", "rounded_rectangle"):
        family = [row for row in records if row.primitive == primitive]
        used: set[str] = set()
        for anchor in family:
            if anchor.candidate.id in used:
                continue
            anchor_scale = (
                _parameter(anchor, "radius")
                or _parameter(anchor, "width")
                or _parameter(anchor, "rx")
            )
            if anchor_scale is None or anchor_scale <= 0:
                continue
            members = [
                row for row in family
                if row.candidate.id not in used
                and (lambda value: value is not None and abs(value - anchor_scale)
                    / max(anchor_scale, value) <= 0.10)(
                        _parameter(row, "radius")
                        or _parameter(row, "width")
                        or _parameter(row, "rx")
                    )
            ]
            anchor_color = np.median(
                reir.raster.oklab[anchor.source_mask], axis=0,
            )
            anchor_alpha = float(np.median(
                reir.raster.straight_rgba[..., 3][anchor.source_mask]
            ))
            members = [
                row for row in members
                if float(np.linalg.norm(
                    np.median(reir.raster.oklab[row.source_mask], axis=0)
                    - anchor_color
                )) <= 0.08
                and abs(float(np.median(
                    reir.raster.straight_rgba[..., 3][row.source_mask]
                )) - anchor_alpha) <= 0.10
            ]
            if len(members) < 2:
                continue
            members = sorted(members, key=lambda row: row.candidate.id)[:32]
            shared = float(np.median([
                _parameter(row, "radius") or _parameter(row, "width")
                or _parameter(row, "rx") for row in members
            ]))
            group_parameters: list[tuple[str, float]] = [("scale", shared)]
            group_continuous: list[tuple[str, float]] = [
                ("shared_scale", shared),
            ]
            group_covariance: list[float] = []
            centers = [_record_center(row) for row in members]
            if len(members) >= 3 and all(center is not None for center in centers):
                center_array = np.asarray(centers, np.float64)
                centered = center_array - np.mean(center_array, axis=0)
                _u, _singular, vh = np.linalg.svd(centered, full_matrices=False)
                axis = vh[0]
                if axis[0] < 0.0 or (abs(axis[0]) < 1e-9 and axis[1] < 0.0):
                    axis = -axis
                projections = np.sort(center_array @ axis)
                gaps = np.diff(projections)
                perpendicular = centered - (centered @ axis)[:, None] * axis
                gap = float(np.median(gaps)) if len(gaps) else 0.0
                gap_cv = float(np.std(gaps) / max(1.0, gap)) if len(gaps) else 1.0
                line_error = float(np.sqrt(np.mean(np.sum(
                    perpendicular * perpendicular, axis=1,
                ))))
                if gap > 0.0 and gap_cv <= 0.20 and line_error <= 0.20 * shared:
                    group_parameters.extend((
                        ("gap", gap), ("axis_x", float(axis[0])),
                        ("axis_y", float(axis[1])),
                    ))
                    group_continuous.append(("shared_gap", gap))
                    group_covariance.append(max(0.01, float(np.var(gaps))))
            union = np.zeros((reir.height, reir.width), bool)
            residuals = []
            for row in members:
                union |= row.rendered_mask
                value = (
                    _parameter(row, "radius") or _parameter(row, "width")
                    or _parameter(row, "rx") or shared
                )
                residuals.append((row.candidate.id, abs(value - shared) / max(1.0, shared)))
            saving = float(max(0.0, (len(members) - 1) * 14.0 - 4.0))
            score = float(np.clip(
                np.mean([row.candidate.score_bounds.expected for row in members])
                + 0.04 * math.log2(len(members))
                - 0.15 * np.mean([value for _id, value in residuals]),
                0.0, 2.0,
            ))
            candidate = candidate_from_support(
                reir, family="shape", mask=union, roi_xyxy=_bbox(union),
                evidence_token_ids=tuple(sorted({
                    token for row in members for token in row.source_token_ids
                })), score=score, kind=MacroKind.SHAPE,
                components=topology_signature(union)[0],
                holes=topology_signature(union)[1],
                prefix=f"shape-repeat-{primitive}",
                provenance=(
                    "phase5-repeated-parameter-group", f"primitive:{primitive}",
                ),
            )
            if candidate is None:
                continue
            candidate = replace(
                candidate,
                program=SceneProgram(f"RepeatGroup/{primitive}", (
                    ("members", len(members)), ("shared_scale", shared),
                    *((
                        ("shared_gap", dict(group_parameters)["gap"]),
                    ) if "gap" in dict(group_parameters) else ()),
                    ("member_ids", ",".join(row.candidate.id for row in members)),
                )),
                continuous_params=tuple(group_continuous),
                covariance=(
                    max(0.01, float(np.var([
                        value for _id, value in residuals
                    ]))),
                    *tuple(group_covariance),
                ),
                prerequisite_claims=(
                    "members-compete-with-independent-shapes",
                    "shared-parameter-evidence", "bounded-member-residuals",
                ),
            )
            candidate = rekey_draft_candidate(
                candidate, prefix=f"shape-repeat-{primitive}",
            )
            rows.append(RepeatedShapeGroup(
                candidate=candidate, primitive=primitive,
                member_ids=tuple(row.candidate.id for row in members),
                shared_parameters=tuple(group_parameters),
                residuals=tuple(residuals), mdl_saving_bits=saving,
            ))
            used.update(row.candidate.id for row in members)
            if len(rows) >= max_groups:
                return tuple(rows)
    return tuple(rows)


def generate_shape_macros(
    reir: RasterEvidenceIR, *, max_rois: int = 64,
    max_per_roi: int = 4, validate_reir: bool = True,
    proposal_queries: Iterable["ProposalQuery"] = (),
    protected_text_masks: Iterable[np.ndarray] = (),
) -> ShapeMacroSet:
    if validate_reir:
        reir.validate()
    sources = _source_rois(
        reir, max_rois, proposal_queries, protected_text_masks,
    )
    records: list[ShapeFitRecord] = []
    pruned = 0
    for source, token_ids, source_score, provenance in sources:
        fitted = []
        candidate_rows = (
            _occlusion_candidate_rows(source)
            if "occlusion-color-union" in provenance
            else _candidate_rows(source)
        )
        for primitive, parameters, rendered, angular, condition in candidate_rows:
            record = _make_record(
                reir, source, token_ids, source_score, provenance,
                primitive, parameters, rendered, angular, condition,
            )
            if record is None:
                pruned += 1
            else:
                fitted.append(record)
        fitted.sort(key=lambda row: (
            -row.candidate.score_bounds.lower,
            row.primitive == "free_curve", row.candidate.id,
        ))
        records.extend(fitted[:max(1, min(12, int(max_per_roi)))])
        pruned += max(0, len(fitted) - max_per_roi)
    # One stable candidate identity per rendered support/type.
    unique: dict[tuple[str, str], ShapeFitRecord] = {}
    for row in records:
        key = (row.primitive, mask_sha256(row.rendered_mask))
        previous = unique.get(key)
        if previous is None or (
            row.candidate.score_bounds.lower > previous.candidate.score_bounds.lower
        ):
            unique[key] = row
    final_records = tuple(sorted(
        unique.values(), key=lambda row: (row.candidate.roi_xyxy, row.primitive, row.candidate.id)
    ))
    for row in final_records:
        row.validate(reir)
    groups = _repeated_groups(reir, final_records)
    return ShapeMacroSet(
        records=final_records, groups=groups,
        rois_considered=len(sources), candidates_pruned=pruned,
        provenance=(
            "REIR-hierarchy+interface+deterministic-fit",
            "phase5-whole-shape-generator/v1", "bounded-64x12x4",
        ),
    )
