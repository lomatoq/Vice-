"""Whole-shape tournaments with exact analytic geometry and MDL selection.

Parameter conventions:
* circle: ``cx, cy, r``
* ellipse: ``cx, cy, rx, ry, angle_degrees``
* rect/rounded-rect: ``cx, cy, width, height, angle_degrees[, radius]``
* star: ``cx, cy, outer_radius, inner_radius, point_count, angle_radians``
* polyline/triangle/quad/D: geometry lives in ``points``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import cv2
import numpy as np

from .contracts import GeometryPrimitive
from .topology import RegionProposal


@dataclass(frozen=True)
class ShapeCandidate:
    family: str
    positive: tuple[GeometryPrimitive, ...]
    negatives: tuple[tuple[GeometryPrimitive, ...], ...]
    parameters: tuple[float, ...]
    render_error: float
    boundary_error_px: float
    mdl: float
    topology_penalty: float
    covariance: tuple[float, ...]
    confidence: float

    @property
    def score(self) -> float:
        return self.render_error + self.boundary_error_px * 0.035 + self.mdl + self.topology_penalty


FAMILY_MDL = {
    "circle": 0.004, "ellipse": 0.006, "rectangle": 0.005,
    "rounded-rectangle": 0.007, "triangle": 0.006,
    "isosceles-triangle": 0.0045, "quadrilateral": 0.008,
    "star-3": 0.008, "star-4": 0.008, "star-5": 0.009, "star-6": 0.009,
    "D-shape": 0.008, "ring": 0.007, "ribbon": 0.011,
}


def tournament_region(region: RegionProposal, *, uncertainty: np.ndarray | None = None,
                      shape_prior: np.ndarray | None = None,
                      max_candidates: int = 24) -> tuple[ShapeCandidate, tuple[ShapeCandidate, ...]]:
    mask = np.asarray(region.mask, np.uint8)
    height, width = mask.shape
    contour = _open_contour(region.positive_contour)
    if len(contour) < 3:
        generic = _generic_candidate(mask, contour, region.negative_contours, uncertainty)
        generic = _with_shape_prior(generic, shape_prior)
        return generic, (generic,)
    candidates: list[ShapeCandidate] = []
    contour_cv = contour.astype(np.float32).reshape(-1, 1, 2)
    area = abs(float(cv2.contourArea(contour_cv)))
    hull_area = abs(float(cv2.contourArea(cv2.convexHull(contour_cv))))
    convexity = area / max(hull_area, 1e-6)
    perimeter = max(float(cv2.arcLength(contour_cv, True)), 1e-6)
    coarse_vertices = len(cv2.approxPolyDP(contour_cv, .018 * perimeter, True))
    x, y, width, height = cv2.boundingRect(contour_cv)
    aspect = max(width, height) / max(min(width, height), 1)
    fitters = [_fit_circle, _fit_circle_ransac, _fit_ellipse, _fit_rectangle]
    if coarse_vertices <= 6:
        fitters.extend((_fit_triangle, _fit_isosceles_triangle, _fit_quadrilateral))
    if 4 <= coarse_vertices <= 12:
        fitters.append(_fit_d_shape)
    if aspect >= 2.0 or convexity < .86:
        fitters.append(_fit_ribbon)
    for fitter in fitters:
        try:
            proposal = fitter(mask, contour, region.negative_contours, uncertainty)
        except (cv2.error, ValueError, FloatingPointError, np.linalg.LinAlgError):
            proposal = None
        if proposal is not None:
            candidates.append(proposal)
    candidates.extend(_fit_rounded_rect_candidates(
        mask, contour, region.negative_contours, uncertainty))
    if convexity < .96:
        for point_count in range(3, 7):
            proposal = _fit_star(mask, contour, region.negative_contours, uncertainty, point_count)
            if proposal is not None:
                candidates.append(proposal)
    if region.negative_contours:
        ring = _fit_ring(mask, contour, region.negative_contours, uncertainty)
        if ring is not None:
            candidates.append(ring)
    candidates.append(_generic_candidate(mask, contour, region.negative_contours, uncertainty))
    if region.soft_membership is not None:
        candidates = [_with_soft_membership(candidate, mask, region.soft_membership,
                                            uncertainty, region.bbox) for candidate in candidates]
    candidates = [_with_shape_prior(candidate, shape_prior) for candidate in candidates]
    candidates.sort(key=lambda item: item.score)
    # Refine only plausible finalists. Refining every family made runtime grow
    # with the vocabulary and was the source of minute-long ordinary jobs.
    refined_families = set()
    for candidate in tuple(candidates[:7]):
        if (candidate.family == "ring" or len(candidate.positive) != 1
                or candidate.positive[0].kind not in {"circle", "ellipse", "rect",
                                                       "rounded-rect", "star"}
                or candidate.render_error > .22):
            continue
        if candidate.family in refined_families:
            continue
        refined_families.add(candidate.family)
        primitive = _refine_analytic(mask, candidate.positive[0], candidate.negatives)
        candidates.append(_candidate(
            candidate.family, mask, (primitive,), candidate.negatives,
            primitive.parameters, uncertainty, candidate.covariance,
            candidate.topology_penalty, candidate.mdl,
        ))
    if region.soft_membership is not None:
        candidates = [_with_soft_membership(candidate, mask, region.soft_membership,
                                            uncertainty, region.bbox) for candidate in candidates]
    candidates.sort(key=lambda item: item.score)
    ranked = tuple(candidates[:max_candidates])
    best = ranked[0]
    return best, ranked


def generic_region_candidate(region: RegionProposal, *,
                             uncertainty: np.ndarray | None = None,
                             shape_prior: np.ndarray | None = None) -> ShapeCandidate:
    """Build only the non-parametric candidate for a real no-shapes ablation."""
    mask = np.asarray(region.mask, np.uint8)
    contour = _open_contour(region.positive_contour)
    candidate = _generic_candidate(mask, contour, region.negative_contours, uncertainty)
    if region.soft_membership is not None:
        candidate = _with_soft_membership(candidate, mask, region.soft_membership,
                                          uncertainty, region.bbox)
    return _with_shape_prior(candidate, shape_prior)


def _with_shape_prior(candidate: ShapeCandidate,
                      shape_prior: np.ndarray | None) -> ShapeCandidate:
    """Convert the frozen shape head into a weak, auditable tournament prior."""
    if shape_prior is None:
        return candidate
    values = np.asarray(shape_prior, np.float64).reshape(-1)
    if len(values) < 4 or not np.isfinite(values[:4]).all():
        return candidate
    channel = 3
    if candidate.family in {"circle", "ellipse", "ring"}:
        channel = 0
    elif candidate.family in {"rectangle", "rounded-rectangle", "triangle",
                              "isosceles-triangle", "quadrilateral", "D-shape",
                              "star-3", "star-4", "star-5", "star-6"}:
        channel = 1
    elif candidate.family == "ribbon":
        channel = 2
    support = float(np.clip(values[channel], 0.0, 1.0))
    return replace(candidate, topology_penalty=candidate.topology_penalty
                   + 0.012 * (1.0 - support))


def _with_soft_membership(candidate: ShapeCandidate, mask: np.ndarray,
                          membership: np.ndarray,
                          uncertainty: np.ndarray | None,
                          bbox: tuple[int, int, int, int]) -> ShapeCandidate:
    x0, y0, x1, y1 = bbox
    rendered = render_geometry_mask(
        (y1 - y0, x1 - x0), candidate.positive, candidate.negatives,
        supersample=4, origin=(x0, y0),
    ).astype(np.float32) / 255.0
    reference = np.clip(np.asarray(membership, np.float32), 0.0, 1.0)
    support = np.maximum(reference, rendered)
    if uncertainty is not None and uncertainty.shape == mask.shape:
        weights = 1.0 - .35 * np.clip(uncertainty[y0:y1, x0:x1], 0.0, 1.0)
    else:
        weights = np.ones(reference.shape, np.float32)
    error = float(np.sum(weights * np.abs(reference - rendered))
                  / max(float(np.sum(weights * support)), 1e-6))
    return replace(candidate, render_error=error,
                   confidence=float(np.clip(math.exp(-3.5 *
                       (error + .035 * candidate.boundary_error_px)), 0.0, 1.0)))


def _candidate(family: str, mask: np.ndarray, positive: tuple[GeometryPrimitive, ...],
               negatives: tuple[tuple[GeometryPrimitive, ...], ...],
               params: tuple[float, ...], uncertainty: np.ndarray | None,
               covariance: tuple[float, ...] = (), topology_penalty: float = 0.0,
               mdl: float | None = None) -> ShapeCandidate:
    reference, rendered, bbox = _local_render_pair(mask, positive, negatives)
    rendered_binary = rendered >= 128
    reference_binary = reference > 0
    union = np.logical_or(reference_binary, rendered_binary)
    weights = np.ones(reference.shape, np.float32)
    if uncertainty is not None and uncertainty.shape == mask.shape:
        # Weak evidence makes exact extra detail less valuable, never free.
        x0, y0, x1, y1 = bbox
        weights = 1.0 - 0.55 * np.clip(uncertainty[y0:y1, x0:x1], 0.0, 1.0)
    xor = np.logical_xor(reference_binary, rendered_binary)
    render_error = float(np.sum(weights * xor) / max(1e-6, np.sum(weights * union)))
    boundary_error = _boundary_chamfer(reference, rendered)
    model_mdl = FAMILY_MDL.get(family, 0.014 + 0.00035 * _primitive_complexity(positive)) if mdl is None else mdl
    total_data = render_error + 0.035 * boundary_error
    confidence = float(np.clip(math.exp(-3.5 * total_data), 0.0, 1.0))
    return ShapeCandidate(family, positive, negatives, params, render_error,
                          boundary_error, float(model_mdl), topology_penalty,
                          covariance, confidence)


def _fit_circle(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    if len(contour) < 6:
        return None
    x, y = contour[:, 0], contour[:, 1]
    design = np.column_stack((2.0 * x, 2.0 * y, np.ones(len(x))))
    rhs = x * x + y * y
    solution, *_ = np.linalg.lstsq(design, rhs, rcond=None)
    cx, cy, c = solution
    radius2 = c + cx * cx + cy * cy
    if radius2 <= 0:
        return None
    radius = float(math.sqrt(radius2))
    radial = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    rms = float(np.sqrt(np.mean((radial - radius) ** 2)))
    if radius < 0.65:
        return None
    span_x = max(float(np.ptp(x)), 1.0)
    span_y = max(float(np.ptp(y)), 1.0)
    span = max(span_x, span_y)
    # This is the complete-shape LSQ candidate.  Short, nearly collinear
    # codec fragments can have algebraically perfect circles hundreds of
    # pixels wide; local crop clipping hid the footprint until final export.
    # Partial arcs belong to the separately gated occlusion-RANSAC proposal.
    if (radius > .80 * span + 1.0
            or not (float(x.min()) - .25 * span <= cx
                    <= float(x.max()) + .25 * span)
            or not (float(y.min()) - .25 * span <= cy
                    <= float(y.max()) + .25 * span)):
        return None
    primitive = GeometryPrimitive("circle", (float(cx), float(cy), radius),
                                  confidence=float(math.exp(-rms)), evidence_rms_px=rms,
                                  provenance=("algebraic-circle-lsq",))
    negative = tuple(_fit_hole_geometry(hole) for hole in holes)
    return _candidate("circle", mask, (primitive,), negative,
                      primitive.parameters, uncertainty, (rms * rms,) * 3,
                      topology_penalty=.005 if negative else 0.0)


def _fit_circle_ransac(mask: np.ndarray, contour: np.ndarray,
                       holes: tuple[np.ndarray, ...],
                       uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    """Recover a hidden circle from a visible arc while rejecting occlusion chords."""
    if len(contour) < 12:
        return None
    indices = np.linspace(0, len(contour) - 1, min(18, len(contour)), dtype=int)
    best = None
    for first_pos in range(0, len(indices), 3):
        for second_pos in range(first_pos + 2, len(indices), 4):
            for third_pos in range(second_pos + 2, len(indices), 5):
                circle = _circle_from_three(contour[indices[first_pos]],
                                            contour[indices[second_pos]],
                                            contour[indices[third_pos]])
                if circle is None:
                    continue
                cx, cy, radius = circle
                if not .65 <= radius <= 2.5 * max(mask.shape):
                    continue
                residual = np.abs(np.linalg.norm(contour - (cx, cy), axis=1) - radius)
                inliers = residual <= .62
                count = int(inliers.sum())
                if count < max(8, int(.28 * len(contour))):
                    continue
                row = (count, -float(np.mean(residual[inliers])), inliers)
                if best is None or row[:2] > best[:2]:
                    best = row
    if best is None:
        return None
    fitted = _circle_primitive(contour[best[2]])
    if fitted is None:
        return None
    negatives = tuple(_fit_hole_geometry(hole) for hole in holes)
    fitted = GeometryPrimitive(
        "circle", fitted.parameters, confidence=fitted.confidence,
        evidence_rms_px=fitted.evidence_rms_px,
        provenance=fitted.provenance + ("occlusion-robust-ransac",),
    )
    return _candidate("circle", mask, (fitted,), negatives, fitted.parameters,
                      uncertainty, (fitted.evidence_rms_px ** 2,) * 3,
                      topology_penalty=.007 + (.005 if negatives else 0.0))


def _circle_from_three(first: np.ndarray, second: np.ndarray,
                       third: np.ndarray) -> tuple[float, float, float] | None:
    matrix = 2.0 * np.asarray((second - first, third - first), np.float64)
    rhs = np.asarray((np.dot(second, second) - np.dot(first, first),
                      np.dot(third, third) - np.dot(first, first)), np.float64)
    determinant = float(np.linalg.det(matrix))
    if abs(determinant) < 1e-5:
        return None
    center = np.linalg.solve(matrix, rhs)
    return float(center[0]), float(center[1]), float(np.linalg.norm(first - center))


def _fit_ellipse(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                 uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    if len(contour) < 8:
        return None
    (cx, cy), (diameter_a, diameter_b), angle = cv2.fitEllipseDirect(contour.astype(np.float32).reshape(-1, 1, 2))
    rx, ry = diameter_a * .5, diameter_b * .5
    if min(rx, ry) < 0.65:
        return None
    theta = math.radians(angle)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    local_x = cos_t * (contour[:, 0] - cx) + sin_t * (contour[:, 1] - cy)
    local_y = -sin_t * (contour[:, 0] - cx) + cos_t * (contour[:, 1] - cy)
    radial = np.sqrt((local_x / rx) ** 2 + (local_y / ry) ** 2)
    rms = float(np.sqrt(np.mean(((radial - 1.0) * min(rx, ry)) ** 2)))
    params = (float(cx), float(cy), float(rx), float(ry), float(angle))
    primitive = GeometryPrimitive("ellipse", params, confidence=float(math.exp(-rms)),
                                  evidence_rms_px=rms, provenance=("direct-ellipse-fit",))
    negatives = tuple(_fit_hole_geometry(h) for h in holes)
    return _candidate("ellipse", mask, (primitive,), negatives,
                      primitive.parameters, uncertainty, (rms * rms,) * 5,
                      topology_penalty=.003 if negatives else 0.0)


def _fit_rectangle(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                   uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    (cx, cy), (w, h), angle = cv2.minAreaRect(contour.astype(np.float32).reshape(-1, 1, 2))
    if min(w, h) < 0.75:
        return None
    negatives = tuple(_fit_hole_geometry(h) for h in holes)
    rows = []
    for expansion in (0.0, .75, 1.0, 1.25):
        params = (float(cx), float(cy), float(w + expansion),
                  float(h + expansion), float(angle))
        box = cv2.boxPoints(((cx, cy), (w + expansion, h + expansion), angle)).astype(np.float64)
        rms = _point_polygon_rms(contour, box)
        primitive = GeometryPrimitive("rect", params, points=_close_points(box),
                                      confidence=float(math.exp(-rms)), evidence_rms_px=rms,
                                      provenance=("minimum-area-rectangle",
                                                  "digital-edge-expansion"))
        rows.append(_candidate("rectangle", mask, (primitive,), negatives,
                               primitive.parameters, uncertainty, (rms * rms,) * 5))
    return min(rows, key=lambda item: item.score)


def _fit_rounded_rect(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                      uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    rows = _fit_rounded_rect_candidates(mask, contour, holes, uncertainty)
    return min(rows, key=lambda item: item.score) if rows else None


def _fit_rounded_rect_candidates(mask: np.ndarray, contour: np.ndarray,
                                 holes: tuple[np.ndarray, ...],
                                 uncertainty: np.ndarray | None) -> tuple[ShapeCandidate, ...]:
    (cx, cy), (w, h), angle = cv2.minAreaRect(contour.astype(np.float32).reshape(-1, 1, 2))
    if min(w, h) < 2.5:
        return ()
    rows = []
    negatives = tuple(_fit_hole_geometry(hole) for hole in holes)
    for expansion in (0.0, .75, 1.0, 1.25):
        expanded_w, expanded_h = w + expansion, h + expansion
        for fraction in (0.08, 0.15, 0.25, 0.4):
            radius = fraction * min(expanded_w, expanded_h)
            params = (float(cx), float(cy), float(expanded_w), float(expanded_h),
                      float(angle), float(radius))
            primitive = GeometryPrimitive(
                "rounded-rect", params, confidence=0.8,
                provenance=("rounded-rectangle-grid", "digital-edge-expansion"))
            candidate = _candidate("rounded-rectangle", mask, (primitive,),
                                   negatives, primitive.parameters, uncertainty)
            rows.append(candidate)
    rows.sort(key=lambda item: item.score)
    return tuple(rows[:8])


def _fit_triangle(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                  uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    starts = []
    approximated = _polygon_vertices(contour, 3)
    if approximated is not None:
        starts.append(approximated)
    area, triangle = cv2.minEnclosingTriangle(
        contour.astype(np.float32).reshape(-1, 1, 2))
    if triangle is not None and area > 0:
        starts.append(np.asarray(triangle, np.float64).reshape(-1, 2))
    if not starts:
        return None
    negatives = tuple(_fit_hole_geometry(h) for h in holes)
    rows = []
    for start in starts:
        points = _refine_polygon(mask, start, "triangle", negatives)
        primitive = GeometryPrimitive("triangle", points=_close_points(points),
                                      provenance=("triangle-digital-preimage",))
        rows.append(_candidate("triangle", mask, (primitive,), negatives,
                               tuple(float(v) for v in points.ravel()), uncertainty))
    return min(rows, key=lambda item: item.score)


def _fit_isosceles_triangle(mask: np.ndarray, contour: np.ndarray,
                            holes: tuple[np.ndarray, ...],
                            uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    general = _fit_triangle(mask, contour, holes, uncertainty)
    if general is None:
        return None
    points = np.asarray(general.positive[0].points, np.float64)[:3]
    apex_rows = []
    for apex_index in range(3):
        bases = [index for index in range(3) if index != apex_index]
        first = float(np.linalg.norm(points[apex_index] - points[bases[0]]))
        second = float(np.linalg.norm(points[apex_index] - points[bases[1]]))
        apex_rows.append((abs(first - second) / max(first, second, 1e-6),
                          apex_index, bases))
    relative, apex_index, base_indices = min(apex_rows)
    if relative >= 0.12:
        return None
    # Equalize the paired sides by projecting the apex onto the base bisector.
    base_a = points[base_indices[0]]
    base_b = points[base_indices[1]]
    apex = points[apex_index]
    midpoint = .5 * (base_a + base_b)
    base = base_b - base_a
    normal = np.array([-base[1], base[0]]) / max(np.linalg.norm(base), 1e-8)
    snapped_apex = midpoint + normal * np.dot(apex - midpoint, normal)
    snapped = np.asarray((base_a, base_b, snapped_apex), np.float64)
    snapped = _refine_isosceles(mask, snapped,
                                tuple(_fit_hole_geometry(h) for h in holes))
    primitive = GeometryPrimitive("triangle", points=_close_points(snapped),
                                  provenance=("isosceles-triangle-snap",))
    return _candidate("isosceles-triangle", mask, (primitive,),
                      tuple(_fit_hole_geometry(h) for h in holes),
                      tuple(float(v) for v in snapped.ravel()), uncertainty)


def _fit_quadrilateral(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                       uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    perimeter = cv2.arcLength(contour.astype(np.float32).reshape(-1, 1, 2), True)
    best_points = _polygon_vertices(contour, 4)
    if best_points is None:
        return None
    negatives = tuple(_fit_hole_geometry(h) for h in holes)
    best_points = _refine_polygon(mask, best_points, "quadrilateral", negatives)
    edges = np.linalg.norm(np.roll(best_points, -1, axis=0) - best_points, axis=1)
    if float(edges.min()) < .08 * max(float(np.median(edges)), 1e-6):
        return None
    primitive = GeometryPrimitive("quadrilateral", points=_close_points(best_points),
                                  provenance=("four-vertex-approximation",))
    return _candidate("quadrilateral", mask, (primitive,),
                      negatives,
                      tuple(float(v) for v in best_points.ravel()), uncertainty)


def _fit_star(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
              uncertainty: np.ndarray | None, point_count: int) -> ShapeCandidate | None:
    moments = cv2.moments(contour.astype(np.float32))
    if abs(moments["m00"]) < 1e-6:
        return None
    cx = moments["m10"] / moments["m00"]
    cy = moments["m01"] / moments["m00"]
    delta = contour - np.array([cx, cy])
    radii = np.linalg.norm(delta, axis=1)
    angles = np.arctan2(delta[:, 1], delta[:, 0])
    outer = float(np.percentile(radii, 92))
    inner = float(np.percentile(radii, 25))
    if outer < 2.0 or not 0.15 <= inner / max(outer, 1e-6) <= 0.82:
        return None
    # Phase tournament is cheap and prevents raster phase from choosing a jag.
    best = None
    negatives = tuple(_fit_hole_geometry(h) for h in holes)
    vertices = _polygon_vertices(contour, 2 * point_count)
    if vertices is not None:
        vertex_center = vertices.mean(axis=0)
        vertex_radii = np.linalg.norm(vertices - vertex_center, axis=1)
        outer_parity = int(np.mean(vertex_radii[1::2]) > np.mean(vertex_radii[0::2]))
        outer_rows = vertices[outer_parity::2]
        inner_rows = vertices[1 - outer_parity::2]
        vertex_outer = float(np.median(np.linalg.norm(outer_rows - vertex_center, axis=1)))
        vertex_inner = float(np.median(np.linalg.norm(inner_rows - vertex_center, axis=1)))
        phase = float(math.atan2(outer_rows[0, 1] - vertex_center[1],
                                 outer_rows[0, 0] - vertex_center[0]))
        primitive = GeometryPrimitive(
            "star", (float(vertex_center[0]), float(vertex_center[1]), vertex_outer,
                     vertex_inner, float(point_count), phase),
            points=_close_points(_star_points(vertex_center[0], vertex_center[1],
                                               vertex_outer, vertex_inner,
                                               point_count, phase)),
            provenance=("alternating-vertex-star-model",),
        )
        best = _candidate(f"star-{point_count}", mask, (primitive,), negatives,
                          primitive.parameters, uncertainty)
    for angle in np.linspace(-math.pi, math.pi, 2 * point_count, endpoint=False):
        points = _star_points(cx, cy, outer, inner, point_count, float(angle))
        primitive = GeometryPrimitive("star", (float(cx), float(cy), outer, inner,
                                                 float(point_count), float(angle)),
                                      points=_close_points(points), provenance=("radial-star-model",))
        candidate = _candidate(f"star-{point_count}", mask, (primitive,),
                               negatives,
                               primitive.parameters, uncertainty)
        if best is None or candidate.score < best.score:
            best = candidate
    if best is None:
        return None
    return best


def _fit_d_shape(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                 uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    x, y, w, h = cv2.boundingRect(contour.astype(np.float32))
    if min(w, h) < 3:
        return None
    variants = []
    for direction in (1, -1):
        points = _d_points(float(x), float(y), float(w), float(h), direction)
        primitive = GeometryPrimitive("D-shape", (float(direction),), points=_close_points(points),
                                      provenance=("D-bullet-model",))
        variants.append(_candidate("D-shape", mask, (primitive,),
                                   tuple(_fit_hole_geometry(hole) for hole in holes),
                                   (float(x), float(y), float(w), float(h), float(direction)), uncertainty))
    return min(variants, key=lambda item: item.score)


def _fit_ring(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
              uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    if len(holes) != 1:
        return None
    outer = _circle_primitive(contour)
    inner = _circle_primitive(_open_contour(holes[0]))
    if outer is None or inner is None:
        return None
    ocx, ocy, outer_r = outer.parameters
    icx, icy, inner_r = inner.parameters
    if inner_r >= outer_r or math.hypot(ocx - icx, ocy - icy) > max(0.7, 0.08 * outer_r):
        return None
    cx, cy = (ocx + icx) * .5, (ocy + icy) * .5
    cx, cy, outer_r, inner_r = _refine_ring_parameters(
        mask, np.asarray((cx, cy, outer_r, inner_r), np.float64))
    positive = (GeometryPrimitive("circle", (cx, cy, outer_r),
                                  provenance=("concentric-ring", "digital-preimage-refine")),)
    negative = ((GeometryPrimitive("circle", (cx, cy, inner_r),
                                   provenance=("concentric-ring", "digital-preimage-refine")),),)
    return _candidate("ring", mask, positive, negative,
                      (cx, cy, outer_r, inner_r), uncertainty)


def _fit_ribbon(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                uncertainty: np.ndarray | None) -> ShapeCandidate | None:
    if holes:
        return None
    interior = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    ridge = interior >= cv2.dilate(interior, np.ones((3, 3), np.float32)) - 1e-5
    values = interior[ridge & (interior > 0.5)]
    if len(values) < 8:
        return None
    median = float(np.median(values))
    if float(np.percentile(values, 90)) / max(median, 1e-6) > 1.35:
        return None
    # Keep a filled footprint for SVG compatibility but tag the semantic model.
    perimeter = cv2.arcLength(contour.astype(np.float32).reshape(-1, 1, 2), True)
    approx = cv2.approxPolyDP(contour.astype(np.float32).reshape(-1, 1, 2),
                              max(0.12, 0.0025 * perimeter), True)[:, 0, :]
    primitive = GeometryPrimitive("polyline", points=_close_points(approx),
                                  provenance=("constant-width-ribbon-footprint",))
    return _candidate("ribbon", mask, (primitive,), (), (2.0 * median,), uncertainty)


def _generic_candidate(mask: np.ndarray, contour: np.ndarray, holes: tuple[np.ndarray, ...],
                       uncertainty: np.ndarray | None) -> ShapeCandidate:
    if len(contour) < 3:
        y, x = np.nonzero(mask)
        points = np.array([[x.min(), y.min()], [x.max() + 1, y.min()],
                           [x.max() + 1, y.max() + 1], [x.min(), y.max() + 1]], np.float64) if len(x) else np.array([[0, 0], [1, 0], [1, 1]], np.float64)
    else:
        perimeter = cv2.arcLength(contour.astype(np.float32).reshape(-1, 1, 2), True)
        local_uncertainty = float(np.mean(uncertainty[mask > 0])) if uncertainty is not None and np.any(mask) else 0.25
        epsilon = max(0.22, (0.0025 + 0.008 * local_uncertainty) * perimeter)
        points = cv2.approxPolyDP(contour.astype(np.float32).reshape(-1, 1, 2), epsilon, True)[:, 0, :]
        if len(points) < 3:
            points = contour
    primitive = GeometryPrimitive("polyline", points=_close_points(points),
                                  confidence=1.0, evidence_rms_px=0.0,
                                  provenance=("uncertainty-adaptive-generic-loop",))
    negative = tuple(_fit_hole_geometry(hole) for hole in holes)
    mdl = 0.014 + 0.00035 * len(points)
    return _candidate("generic", mask, (primitive,), negative, (), uncertainty, mdl=mdl)


def _fit_hole_geometry(contour: np.ndarray) -> tuple[GeometryPrimitive, ...]:
    points = _open_contour(contour)
    circle = _circle_primitive(points)
    if circle is not None and circle.evidence_rms_px <= 0.35:
        return (circle,)
    if len(points) >= 8:
        try:
            (cx, cy), (da, db), angle = cv2.fitEllipseDirect(points.astype(np.float32).reshape(-1, 1, 2))
            rx, ry = da * .5, db * .5
            theta = math.radians(angle)
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            local_x = cos_t * (points[:, 0] - cx) + sin_t * (points[:, 1] - cy)
            local_y = -sin_t * (points[:, 0] - cx) + cos_t * (points[:, 1] - cy)
            radial = np.sqrt((local_x / max(rx, 1e-6)) ** 2
                             + (local_y / max(ry, 1e-6)) ** 2)
            rms = float(np.sqrt(np.mean(
                ((radial - 1.0) * min(rx, ry)) ** 2)))
            # Direct ellipse fitting always returns a conic, even for glyph
            # counters and angular cutouts.  Keep it only inside the native
            # edge uncertainty tube; otherwise preserve the real topology.
            if min(rx, ry) >= .65 and rms <= .45:
                primitive = GeometryPrimitive(
                    "ellipse", (cx, cy, rx, ry, angle),
                    confidence=float(math.exp(-rms)), evidence_rms_px=rms,
                    provenance=("hole-ellipse", "physical-residual-gate"))
                return (primitive,)
        except cv2.error:
            pass
    perimeter = cv2.arcLength(points.astype(np.float32).reshape(-1, 1, 2), True) if len(points) >= 3 else 0.0
    approx = cv2.approxPolyDP(points.astype(np.float32).reshape(-1, 1, 2),
                              max(.2, .006 * perimeter), True)[:, 0, :] if len(points) >= 3 else points
    return (GeometryPrimitive("polyline", points=_close_points(approx), provenance=("hole-generic",)),)


def _circle_primitive(contour: np.ndarray) -> GeometryPrimitive | None:
    if len(contour) < 6:
        return None
    x, y = contour[:, 0], contour[:, 1]
    solution, *_ = np.linalg.lstsq(np.column_stack((2 * x, 2 * y, np.ones(len(x)))), x * x + y * y, rcond=None)
    cx, cy, c = solution
    radius2 = c + cx * cx + cy * cy
    if radius2 <= 0:
        return None
    radius = math.sqrt(radius2)
    rms = float(np.sqrt(np.mean((np.linalg.norm(contour - (cx, cy), axis=1) - radius) ** 2)))
    return GeometryPrimitive("circle", (float(cx), float(cy), float(radius)),
                             confidence=float(math.exp(-rms)), evidence_rms_px=rms,
                             provenance=("circle-lsq",))


def _polygon_vertices(contour: np.ndarray, count: int) -> np.ndarray | None:
    perimeter = cv2.arcLength(contour.astype(np.float32).reshape(-1, 1, 2), True)
    rows = []
    for fraction in np.linspace(.0015, .12, 80):
        approx = cv2.approxPolyDP(contour.astype(np.float32).reshape(-1, 1, 2),
                                  float(fraction * perimeter), True)[:, 0, :]
        if len(approx) == count:
            points = approx.astype(np.float64)
            rows.append((_point_polygon_rms(contour, points), points))
    return min(rows, key=lambda row: row[0])[1] if rows else None


def _refine_polygon(mask: np.ndarray, points: np.ndarray, kind: str,
                    negatives: tuple[tuple[GeometryPrimitive, ...], ...]) -> np.ndarray:
    best_points = np.asarray(points, np.float64).copy()
    best = _polygon_mask_loss(mask, best_points, kind, negatives)
    for step in (.45, .2):
        for row in range(len(best_points)):
            for column in range(2):
                for direction in (-1.0, 1.0):
                    trial = best_points.copy()
                    trial[row, column] += direction * step
                    loss = _polygon_mask_loss(mask, trial, kind, negatives)
                    if loss + 1e-8 < best:
                        best_points, best = trial, loss
    return best_points


def _refine_ring_parameters(mask: np.ndarray,
                            parameters: np.ndarray) -> tuple[float, float, float, float]:
    def loss(values: np.ndarray) -> float:
        positive = (GeometryPrimitive("circle", tuple(values[:3])),)
        negative = ((GeometryPrimitive("circle", (values[0], values[1], values[3])),),)
        reference, rendered, _ = _local_render_pair(mask, positive, negative)
        rendered = rendered >= 128
        reference = reference > 0
        union = np.logical_or(reference, rendered)
        return float(np.count_nonzero(np.logical_xor(reference, rendered))
                     / max(np.count_nonzero(union), 1))

    values = parameters.copy()
    best = loss(values)
    steps = np.asarray((.35, .35, .45, .45))
    for shrink in (1.0, .5, .25):
        for index, step in enumerate(steps * shrink):
            for direction in (-1.0, 1.0):
                trial = values.copy(); trial[index] += direction * step
                if trial[3] <= .3 or trial[2] <= trial[3] + .3:
                    continue
                trial_loss = loss(trial)
                if trial_loss + 1e-8 < best:
                    values, best = trial, trial_loss
    return tuple(float(value) for value in values)


def _refine_isosceles(mask: np.ndarray, points: np.ndarray,
                      negatives: tuple[tuple[GeometryPrimitive, ...], ...]) -> np.ndarray:
    # Caller canonicalizes ordering as base-a, base-b, apex.
    base_a, base_b, apex = points
    midpoint = .5 * (base_a + base_b)
    vector = base_b - base_a
    angle = math.atan2(vector[1], vector[0])
    half_base = .5 * float(np.linalg.norm(vector))
    normal = np.array([-math.sin(angle), math.cos(angle)])
    height = float(np.dot(apex - midpoint, normal))
    parameters = np.asarray((midpoint[0], midpoint[1], half_base, height, angle))

    def rebuild(values):
        tangent = np.array([math.cos(values[4]), math.sin(values[4])])
        normal_row = np.array([-tangent[1], tangent[0]])
        center = values[:2]
        return np.asarray((center - values[2] * tangent,
                           center + values[2] * tangent,
                           center + values[3] * normal_row))

    best = _polygon_mask_loss(mask, rebuild(parameters), "triangle", negatives)
    axis_angle = round(parameters[4] / (math.pi * .5)) * (math.pi * .5)
    snapped = parameters.copy()
    snapped[:4] = np.round(snapped[:4] * 2.0) / 2.0
    if abs(parameters[4] - axis_angle) <= .04:
        snapped[4] = axis_angle
    snapped_loss = _polygon_mask_loss(mask, rebuild(snapped), "triangle", negatives)
    if snapped_loss < best:
        parameters, best = snapped, snapped_loss
    steps = np.asarray((.4, .4, .5, .5, .025))
    for shrink in (1.0, .4):
        for index, step in enumerate(steps * shrink):
            for direction in (-1.0, 1.0):
                trial = parameters.copy()
                trial[index] += direction * step
                if trial[2] <= .3 or abs(trial[3]) <= .3:
                    continue
                loss = _polygon_mask_loss(mask, rebuild(trial), "triangle", negatives)
                if loss + 1e-8 < best:
                    parameters, best = trial, loss
    return rebuild(parameters)


def _polygon_mask_loss(mask: np.ndarray, points: np.ndarray, kind: str,
                       negatives: tuple[tuple[GeometryPrimitive, ...], ...]) -> float:
    primitive = GeometryPrimitive(kind, points=_close_points(points))
    reference, rendered, _ = _local_render_pair(mask, (primitive,), negatives)
    rendered = rendered >= 128
    reference = reference > 0
    union = np.logical_or(reference, rendered)
    return float(np.count_nonzero(np.logical_xor(reference, rendered))
                 / max(np.count_nonzero(union), 1))


def _refine_analytic(mask: np.ndarray, primitive: GeometryPrimitive,
                     negatives: tuple[tuple[GeometryPrimitive, ...], ...]) -> GeometryPrimitive:
    """Small deterministic digital-preimage coordinate descent."""
    kind = primitive.kind
    if kind == "circle":
        steps = np.asarray((.45, .45, .45), np.float64)
    elif kind == "ellipse":
        steps = np.asarray((.45, .45, .45, .45, 2.0), np.float64)
    elif kind == "rect":
        steps = np.asarray((.45, .45, .8, .8, 2.0), np.float64)
    elif kind == "rounded-rect":
        steps = np.asarray((.45, .45, .8, .8, 2.0, .55), np.float64)
    elif kind == "star":
        steps = np.asarray((.5, .5, .8, .6, 0.0, .12), np.float64)
    else:
        return primitive
    parameters = np.asarray(primitive.parameters, np.float64)
    best = _digital_mask_loss(mask, _primitive_with_parameters(primitive, parameters), negatives)
    for shrink in (1.0, .5, .25):
        for index, step in enumerate(steps * shrink):
            if step <= 0:
                continue
            for direction in (-1.0, 1.0):
                trial = parameters.copy()
                trial[index] += direction * step
                if not _valid_parameters(kind, trial):
                    continue
                geometry = _primitive_with_parameters(primitive, trial)
                loss = _digital_mask_loss(mask, geometry, negatives)
                if loss + 1e-8 < best:
                    parameters, best = trial, loss
    return _primitive_with_parameters(primitive, parameters)


def _primitive_with_parameters(source: GeometryPrimitive,
                               parameters: np.ndarray) -> GeometryPrimitive:
    values = tuple(float(value) for value in parameters)
    points = source.points
    if source.kind == "rect":
        points = _close_points(cv2.boxPoints(((values[0], values[1]),
                                               (values[2], values[3]), values[4])))
    elif source.kind == "rounded-rect":
        points = ()
    elif source.kind == "star":
        points = _close_points(_star_points(values[0], values[1], values[2], values[3],
                                            int(round(values[4])), values[5]))
    return GeometryPrimitive(source.kind, values, points, source.confidence,
                             source.evidence_rms_px,
                             source.provenance + ("digital-preimage-refine",))


def _valid_parameters(kind: str, values: np.ndarray) -> bool:
    if not np.isfinite(values).all():
        return False
    if kind == "circle":
        return values[2] >= .4
    if kind == "ellipse":
        return min(values[2], values[3]) >= .4
    if kind in {"rect", "rounded-rect"}:
        if min(values[2], values[3]) < .5:
            return False
        return kind == "rect" or 0 <= values[5] <= .5 * min(values[2], values[3])
    if kind == "star":
        return values[2] >= 1.0 and .08 * values[2] <= values[3] <= .92 * values[2]
    return True


def _digital_mask_loss(mask: np.ndarray, primitive: GeometryPrimitive,
                       negatives: tuple[tuple[GeometryPrimitive, ...], ...]) -> float:
    reference, rendered, _ = _local_render_pair(mask, (primitive,), negatives)
    rendered = rendered >= 128
    reference = reference > 0
    support = np.logical_or(reference, rendered)
    return float(np.count_nonzero(np.logical_xor(reference, rendered))
                 / max(int(np.count_nonzero(support)), 1))


def _local_render_pair(mask: np.ndarray,
                       positive: tuple[GeometryPrimitive, ...],
                       negatives: tuple[tuple[GeometryPrimitive, ...], ...],
                       *, padding: int = 3) -> tuple[
                           np.ndarray, np.ndarray, tuple[int, int, int, int]
                       ]:
    """Return reference/render crops covering both evidence and geometry.

    Candidate fitting used to allocate a 4x full-image canvas dozens of times
    per component.  The score only depends on the union support, so an
    integer-aligned crop is mathematically equivalent and much cheaper.
    """
    height, width = mask.shape
    xs: list[float] = []
    ys: list[float] = []
    rows, columns = np.nonzero(mask)
    if len(rows):
        xs.extend((float(columns.min()), float(columns.max() + 1)))
        ys.extend((float(rows.min()), float(rows.max() + 1)))
    for geometry in (positive, *negatives):
        for primitive in geometry:
            points = primitive_points(primitive, 128)
            if len(points):
                xs.extend((float(np.min(points[:, 0])), float(np.max(points[:, 0]))))
                ys.extend((float(np.min(points[:, 1])), float(np.max(points[:, 1]))))
    if not xs or not ys:
        bbox = (0, 0, min(1, width), min(1, height))
    else:
        x0 = max(0, int(math.floor(min(xs))) - padding)
        y0 = max(0, int(math.floor(min(ys))) - padding)
        x1 = min(width, int(math.ceil(max(xs))) + padding)
        y1 = min(height, int(math.ceil(max(ys))) + padding)
        if x1 <= x0:
            x1 = min(width, x0 + 1)
        if y1 <= y0:
            y1 = min(height, y0 + 1)
        bbox = (x0, y0, x1, y1)
    x0, y0, x1, y1 = bbox
    reference = mask[y0:y1, x0:x1]
    rendered = render_geometry_mask(
        reference.shape, positive, negatives, supersample=4,
        origin=(x0, y0),
    )
    return reference, rendered, bbox


def render_geometry_mask(shape: tuple[int, int], positive: tuple[GeometryPrimitive, ...],
                         negatives: tuple[tuple[GeometryPrimitive, ...], ...] = (),
                         *, supersample: int = 4,
                         origin: tuple[int, int] = (0, 0)) -> np.ndarray:
    """Rasterize global scene geometry into a possibly bbox-local canvas.

    ``origin`` is the native-pixel coordinate of the local canvas' top-left
    corner.  Integer origins preserve the exact sampling lattice of a crop from
    a full-canvas render while avoiding O(image area) work per candidate.
    """
    canvas = np.zeros((shape[0] * supersample, shape[1] * supersample), np.uint8)
    _draw_geometry(canvas, positive, 255, supersample, origin)
    for hole in negatives:
        _draw_geometry(canvas, hole, 0, supersample, origin)
    if supersample > 1:
        canvas = cv2.resize(canvas, (shape[1], shape[0]), interpolation=cv2.INTER_AREA)
    return canvas


def primitive_points(primitive: GeometryPrimitive, samples: int = 64) -> np.ndarray:
    kind = primitive.kind
    p = primitive.parameters
    if kind == "circle":
        cx, cy, radius = p
        angles = np.linspace(0, 2 * math.pi, samples, endpoint=False)
        return np.column_stack((cx + radius * np.cos(angles), cy + radius * np.sin(angles)))
    if kind == "ellipse":
        cx, cy, rx, ry, angle = p
        t = np.linspace(0, 2 * math.pi, samples, endpoint=False)
        local = np.column_stack((rx * np.cos(t), ry * np.sin(t)))
        theta = math.radians(angle)
        rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
        return local @ rotation.T + (cx, cy)
    if kind == "circular-arc":
        cx, cy, radius, start, end = p
        t = np.linspace(start, end, samples)
        return np.column_stack((cx + radius * np.cos(t), cy + radius * np.sin(t)))
    if kind == "elliptical-arc":
        cx, cy, rx, ry, angle, start, end = p
        t = np.linspace(start, end, samples)
        local = np.column_stack((rx * np.cos(t), ry * np.sin(t)))
        theta = math.radians(angle)
        rotation = np.array([[math.cos(theta), -math.sin(theta)],
                             [math.sin(theta), math.cos(theta)]])
        return local @ rotation.T + (cx, cy)
    if kind in {"quadratic", "cubic"} and primitive.points:
        control = np.asarray(primitive.points, np.float64)
        t = np.linspace(0.0, 1.0, samples)[:, None]
        if kind == "quadratic" and len(control) >= 3:
            return ((1 - t) ** 2 * control[0] + 2 * (1 - t) * t * control[1]
                    + t ** 2 * control[2])
        if kind == "cubic" and len(control) >= 4:
            return ((1 - t) ** 3 * control[0] + 3 * (1 - t) ** 2 * t * control[1]
                    + 3 * (1 - t) * t ** 2 * control[2] + t ** 3 * control[3])
    if kind in {"rect", "rounded-rect"}:
        cx, cy, w, h, angle = p[:5]
        if kind == "rect":
            return cv2.boxPoints(((cx, cy), (w, h), angle)).astype(np.float64)
        return _rounded_rect_points(cx, cy, w, h, angle, p[5], max(4, samples // 4))
    if kind == "star":
        return _star_points(p[0], p[1], p[2], p[3], int(round(p[4])), p[5])
    if primitive.points:
        return np.asarray(primitive.points, np.float64)
    return np.empty((0, 2), np.float64)


def _draw_geometry(canvas: np.ndarray, primitives: tuple[GeometryPrimitive, ...],
                   color: int, scale: int, origin: tuple[int, int]) -> None:
    for primitive in primitives:
        if primitive.kind in {"circle", "ellipse", "rect", "rounded-rect"}:
            canvas[_analytic_mask(canvas.shape, primitive, scale, origin)] = int(color)
            continue
        points = primitive_points(primitive, max(48, int(16 * scale)))
        if len(points) >= 3:
            local = points - np.asarray(origin, np.float64)
            fixed = np.round((local * scale - .5) * 256).astype(np.int32).reshape(-1, 1, 2)
            cv2.fillPoly(canvas, [fixed], int(color), lineType=cv2.LINE_8, shift=8)


def _analytic_mask(shape: tuple[int, int], primitive: GeometryPrimitive,
                   scale: int, origin: tuple[int, int]) -> np.ndarray:
    yy, xx = np.mgrid[:shape[0], :shape[1]].astype(np.float64)
    xx = (xx + .5) / scale + float(origin[0])
    yy = (yy + .5) / scale + float(origin[1])
    p = primitive.parameters
    if primitive.kind == "circle":
        cx, cy, radius = p
        return (xx - cx) ** 2 + (yy - cy) ** 2 <= radius * radius
    cx, cy, first, second, angle = p[:5]
    theta = math.radians(angle)
    dx, dy = xx - cx, yy - cy
    local_x = math.cos(theta) * dx + math.sin(theta) * dy
    local_y = -math.sin(theta) * dx + math.cos(theta) * dy
    if primitive.kind == "ellipse":
        return ((local_x / max(first, 1e-9)) ** 2
                + (local_y / max(second, 1e-9)) ** 2 <= 1.0)
    half_width, half_height = max(first * .5, 0.0), max(second * .5, 0.0)
    if primitive.kind == "rect":
        return ((np.abs(local_x) <= half_width)
                & (np.abs(local_y) <= half_height))
    radius = min(max(float(p[5]), 0.0), half_width, half_height)
    qx = np.abs(local_x) - (half_width - radius)
    qy = np.abs(local_y) - (half_height - radius)
    signed = (np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2)
              + np.minimum(np.maximum(qx, qy), 0.0) - radius)
    return signed <= 0.0


def _boundary_chamfer(reference: np.ndarray, rendered: np.ndarray) -> float:
    ref_edge = cv2.morphologyEx((reference > 0).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    out_edge = cv2.morphologyEx((rendered > 127).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    if not ref_edge.any() or not out_edge.any():
        return 99.0 if ref_edge.any() != out_edge.any() else 0.0
    d_ref = cv2.distanceTransform(1 - ref_edge, cv2.DIST_L2, 5)
    d_out = cv2.distanceTransform(1 - out_edge, cv2.DIST_L2, 5)
    return 0.5 * (float(np.mean(d_ref[out_edge > 0])) + float(np.mean(d_out[ref_edge > 0])))


def _primitive_complexity(primitives: tuple[GeometryPrimitive, ...]) -> int:
    return sum(max(1, len(item.points)) for item in primitives)


def _point_polygon_rms(points: np.ndarray, polygon: np.ndarray) -> float:
    distances = []
    contour = polygon.astype(np.float32).reshape(-1, 1, 2)
    for point in points:
        distances.append(abs(cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), True)))
    return float(np.sqrt(np.mean(np.square(distances)))) if distances else 0.0


def _open_contour(contour: np.ndarray) -> np.ndarray:
    value = np.asarray(contour, np.float64).reshape(-1, 2)
    if len(value) > 1 and np.allclose(value[0], value[-1]):
        value = value[:-1]
    return value


def _close_points(points: np.ndarray) -> tuple[tuple[float, float], ...]:
    value = _open_contour(points)
    if len(value):
        value = np.vstack((value, value[0]))
    return tuple((float(x), float(y)) for x, y in value)


def _star_points(cx: float, cy: float, outer: float, inner: float,
                 count: int, angle: float) -> np.ndarray:
    angles = angle + np.arange(2 * count) * math.pi / count
    radii = np.where(np.arange(2 * count) % 2 == 0, outer, inner)
    return np.column_stack((cx + radii * np.cos(angles), cy + radii * np.sin(angles)))


def _rounded_rect_points(cx: float, cy: float, width: float, height: float,
                         angle: float, radius: float, steps: int) -> np.ndarray:
    radius = min(radius, width * .5, height * .5)
    centers = [(width * .5 - radius, height * .5 - radius),
               (-width * .5 + radius, height * .5 - radius),
               (-width * .5 + radius, -height * .5 + radius),
               (width * .5 - radius, -height * .5 + radius)]
    starts = (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)
    points = []
    for (x, y), start in zip(centers, starts):
        t = np.linspace(start, start + math.pi / 2, steps, endpoint=False)
        points.extend(np.column_stack((x + radius * np.cos(t), y + radius * np.sin(t))))
    points = np.asarray(points, np.float64)
    theta = math.radians(angle)
    rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    return points @ rotation.T + (cx, cy)


def _d_points(x: float, y: float, width: float, height: float, direction: int) -> np.ndarray:
    if direction > 0:
        flat_x, curve_x = x, x + width * .45
        t = np.linspace(-math.pi / 2, math.pi / 2, 24)
        arc = np.column_stack((curve_x + width * .55 * np.cos(t), y + height * .5 + height * .5 * np.sin(t)))
        return np.vstack(((flat_x, y), arc, (flat_x, y + height)))
    points = _d_points(x, y, width, height, 1).copy()
    points[:, 0] = 2 * (x + width * .5) - points[:, 0]
    return points[::-1]
