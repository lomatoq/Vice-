"""Phase-7 sparse continuous refinement with frozen discrete structure."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from typing import TYPE_CHECKING

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

from .certificates import topology_signature
from .evidence_ir import RasterEvidenceIR
from .layer_solver import LayeredScene, _render_typed_shape
from .macro_ir import CandidateMacroIR, MacroCandidate, MacroKind, SceneProgram
from .visible_scene import VisibleSceneIR

if TYPE_CHECKING:
    from .phase5_macros import Phase5MacroBundle
    from .text_macros import TextMacroSet


@dataclass(frozen=True)
class ContinuousVariable:
    index: int
    macro_id: str
    name: str
    initial: float
    lower: float
    upper: float
    prior_sigma: float


@dataclass(frozen=True)
class FactorAudit:
    kind: str
    macro_ids: tuple[str, ...]
    variable_indices: tuple[int, ...]
    residual_count: int
    physical_measure: float


@dataclass(frozen=True)
class RefinedMacro:
    macro_id: str
    original_program: SceneProgram
    refined_program: SceneProgram
    original_params: tuple[tuple[str, float], ...]
    refined_params: tuple[tuple[str, float], ...]
    covariance: tuple[float, ...]
    committed: bool
    rollback_reason: str | None
    native_error_before: float | None
    native_error_after: float | None


@dataclass(frozen=True)
class ContinuousRefinementResult:
    selected_ids: tuple[str, ...]
    owner_digest_before: str
    owner_digest_after: str
    layer_order_before: tuple[str, ...]
    layer_order_after: tuple[str, ...]
    variables: tuple[ContinuousVariable, ...]
    factors: tuple[FactorAudit, ...]
    macros: tuple[RefinedMacro, ...]
    iterations: int
    function_evaluations: int
    initial_cost: float
    final_cost: float
    native_render_error_before: float
    native_render_error_after: float
    committed: bool
    rollback_reason: str | None
    solver: str
    provenance: tuple[str, ...]

    def validate(self) -> None:
        if self.owner_digest_before != self.owner_digest_after:
            raise ValueError("continuous refinement changed visible owners")
        if self.layer_order_before != self.layer_order_after:
            raise ValueError("continuous refinement changed layer order")
        if self.native_render_error_after > self.native_render_error_before + 1e-9:
            raise ValueError("refinement committed a worse native rerender")
        if self.iterations < 0 or self.function_evaluations < 0:
            raise ValueError("negative refinement iteration count")
        if tuple(row.index for row in self.variables) != tuple(
            range(len(self.variables))
        ):
            raise ValueError("continuous-variable indices are not canonical")
        if len({
            (row.macro_id, row.name) for row in self.variables
        }) != len(self.variables):
            raise ValueError("duplicate continuous variable")
        for row in self.macros:
            if len(row.covariance) != len(row.refined_params):
                raise ValueError("refined covariance/parameter mismatch")
            if any(
                not math.isfinite(value) or value < 0.0
                for value in row.covariance
            ):
                raise ValueError("refined covariance is not finite PSD diagonal")


@dataclass(frozen=True)
class _LinearFactor:
    kind: str
    indices: tuple[int, ...]
    coefficients: tuple[float, ...]
    target: float
    weight: float
    macro_ids: tuple[str, ...]


@dataclass(frozen=True)
class _ShapeFactor:
    kind: str
    primitive: str
    indices: tuple[int, ...]
    points_xy: np.ndarray
    physical_weights: np.ndarray
    macro_id: str


@dataclass(frozen=True)
class _AreaFactor:
    kind: str
    primitive: str
    names: tuple[str, ...]
    indices: tuple[int, ...]
    target_area: float
    weight: float
    macro_id: str


@dataclass(frozen=True)
class _CurveEvidenceFactor:
    kind: str
    indices: tuple[int, ...]
    points_xy: np.ndarray
    physical_weights: np.ndarray
    physical_measure: float
    macro_id: str


@dataclass(frozen=True)
class _CurveRegularityFactor:
    kind: str
    indices: tuple[int, ...]
    physical_measure: float
    weight: float
    macro_id: str


_Factor = _LinearFactor | _ShapeFactor | _AreaFactor | _CurveEvidenceFactor | _CurveRegularityFactor


def owner_partition_digest(owners: tuple[str, ...]) -> str:
    """Hash ownership partitions without binding the hash to macro IDs.

    Continuous refinement may re-key an immutable macro after its program
    changes.  That is not a discrete ownership change when every leaf keeps
    the same equivalence-class owner, so the audit digest canonicalizes owner
    labels by first occurrence.
    """
    digest = hashlib.sha256()
    canonical: dict[str, int] = {}
    for owner in owners:
        label = canonical.setdefault(owner, len(canonical))
        digest.update(int(label).to_bytes(8, "little", signed=False))
    return digest.hexdigest()


_owner_digest = owner_partition_digest


def _owner_masks(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
) -> dict[str, np.ndarray]:
    labels = reir.hierarchy.leaf_labels
    if len(scene.owner_by_leaf) == reir.hierarchy.leaf_count:
        result = {}
        for leaf_id, owner in enumerate(scene.owner_by_leaf):
            result.setdefault(owner, np.zeros(labels.shape, bool))
            result[owner] |= labels == leaf_id
        return result
    lookup = cmir.by_id(); result = {}
    for owner in scene.selected_macro_ids:
        candidate = lookup[owner]; certificate = candidate.certificates
        count = reir.width * reir.height
        if certificate.support_bits:
            mask = np.unpackbits(
                np.frombuffer(certificate.support_bits, np.uint8), count=count,
                bitorder="little",
            ).astype(bool).reshape((reir.height, reir.width))
        elif certificate.support_rle:
            flat = np.zeros(count, bool)
            for start, length in certificate.support_rle:
                flat[int(start):int(start) + int(length)] = True
            mask = flat.reshape((reir.height, reir.width))
        else:
            leaves = [
                leaf for leaf in range(reir.hierarchy.leaf_count)
                if candidate.core_bits & (1 << leaf)
            ]
            mask = np.isin(labels, leaves)
        result[owner] = np.asarray(mask, bool)
    return result


def _parameter_bounds(
    name: str, value: float, sigma: float, reir: RasterEvidenceIR,
) -> tuple[float, float]:
    maximum = float(max(reir.width, reir.height) * 2)
    if name in {"cx", "x", "inner_cx"} or name.endswith("_x"):
        return -1.0, float(reir.width)
    if name in {"cy", "y", "inner_cy", "baseline"} or name.endswith("_y"):
        return -1.0, float(reir.height)
    if name in {"radius", "inner_radius", "rx", "ry", "width", "height",
                "x_height", "cap_height", "shared_scale", "x_scale",
                "y_scale", "shared_gap", "shared_stem_width"}:
        return 0.25, maximum
    if name == "curve_tension":
        return 0.25, 1.75
    if name == "tracking_em":
        return -0.25, 0.75
    if name == "tracking":
        return -maximum, maximum
    if name == "offset_x":
        return -float(reir.width), float(reir.width)
    if name == "offset_y":
        return -float(reir.height), float(reir.height)
    if name in {"alpha", "opacity"}:
        return 0.0, 1.0
    if "oklab_l" in name:
        return 0.0, 1.0
    if "oklab_a" in name or "oklab_b" in name:
        return -0.65, 0.65
    if "angle" in name:
        return value - 180.0, value + 180.0
    span = max(1.0, 4.0 * sigma)
    return value - span, value + span


def _variables(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
) -> tuple[ContinuousVariable, ...]:
    lookup = cmir.by_id(); rows = []
    deployable_shape_operators = {
        "Shape/circle", "Shape/ring", "Shape/ellipse", "Shape/rectangle",
        "Shape/rounded_rectangle", "Shape/D_bullet", "Shape/triangle",
        "Shape/quadrilateral", "Shape/star",
    }
    for macro_id in scene.selected_macro_ids:
        candidate = lookup[macro_id]
        operator = candidate.program.operator
        if operator in deployable_shape_operators:
            primitive = operator.split("/", 1)[1]
            allowed = {
                "circle": {"cx", "cy", "radius"},
                "ring": {
                    "cx", "cy", "radius", "inner_cx", "inner_cy",
                    "inner_radius",
                },
                "ellipse": {"cx", "cy", "rx", "ry", "angle"},
                "rectangle": {"x", "y", "width", "height"},
                "rounded_rectangle": {
                    "x", "y", "width", "height", "radius",
                },
                "D_bullet": {"x", "y", "width", "height"},
                "triangle": {
                    name for name, _value in candidate.continuous_params
                    if name.startswith("p") and name.endswith(("_x", "_y"))
                },
                "quadrilateral": {
                    name for name, _value in candidate.continuous_params
                    if name.startswith("p") and name.endswith(("_x", "_y"))
                },
                "star": {
                    name for name, _value in candidate.continuous_params
                    if name.startswith("p") and name.endswith(("_x", "_y"))
                },
            }[primitive]
        elif operator == "Shape/free_curve":
            allowed = {
                name for name, _value in candidate.continuous_params
                if name == "curve_tension" or (
                    name.startswith("curve_p")
                    and name.endswith(("_x", "_y"))
                )
            }
        elif operator.startswith("RepeatGroup/"):
            allowed = {"shared_scale", "shared_gap"}
        elif candidate.kind is MacroKind.STROKE_NETWORK:
            allowed = {"width"}
        elif operator in {
            "Appearance/solid", "Appearance/translucent_solid",
        }:
            allowed = {"oklab_l", "oklab_a", "oklab_b", "alpha"}
        elif operator in {
            "Appearance/linear_gradient", "Appearance/translucent_gradient",
        }:
            allowed = {"angle_deg"}
        elif operator in {
            "Appearance/radial_gradient",
            "Appearance/translucent_radial_gradient",
        }:
            allowed = {"cx", "cy"}
        elif operator.startswith("TextLine/"):
            allowed = (
                {"tracking_em", "x_scale", "y_scale", "offset_x", "offset_y"}
                if operator.endswith(("exact-font", "semantic-font-idealization"))
                else {
                    "baseline", "x_height", "cap_height", "overshoot", "slant",
                    "tracking", "shared_stem_width",
                }
            )
        else:
            allowed = set()
        covariance_by_name = {
            name: candidate.covariance[offset]
            for offset, (name, _value) in enumerate(candidate.continuous_params)
            if offset < len(candidate.covariance)
        }
        for name, value in candidate.program.parameters:
            if name not in allowed or not isinstance(value, (float, int)):
                continue
            variance = covariance_by_name.get(name, 1.0)
            sigma = max(1e-3, math.sqrt(max(0.0, float(variance))))
            lower, upper = _parameter_bounds(name, float(value), sigma, reir)
            initial = float(np.clip(value, lower, upper))
            rows.append(ContinuousVariable(
                index=len(rows), macro_id=macro_id, name=name,
                initial=initial, lower=lower, upper=upper, prior_sigma=sigma,
            ))
    return tuple(rows)


def _sample_contour(
    mask: np.ndarray, count: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    contours, _hierarchy = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE,
    )
    if not contours:
        return np.empty((0, 2), np.float64), np.empty(0, np.float64), 0.0
    contour = max(contours, key=lambda row: cv2.arcLength(row, True))
    points = contour.reshape((-1, 2)).astype(np.float64)
    if len(points) < 2:
        return points, np.ones(len(points)), float(len(points))
    closed = np.vstack((points, points[0]))
    lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    perimeter = float(cumulative[-1])
    if perimeter <= 1e-9:
        return points[:1], np.ones(1), 1.0
    sample_count = max(8, min(1024, int(count)))
    positions = np.linspace(0.0, perimeter, sample_count, endpoint=False)
    indices = np.minimum(np.searchsorted(cumulative, positions, side="right") - 1, len(points) - 1)
    fractions = (positions - cumulative[indices]) / np.maximum(lengths[indices], 1e-9)
    samples = closed[indices] + fractions[:, None] * (closed[indices + 1] - closed[indices])
    # Squared residuals integrate physical arclength, independent of how many
    # samples were requested.
    weights = np.full(sample_count, math.sqrt(perimeter / sample_count), np.float64)
    return samples, weights, perimeter


def _front_masks(
    layered: LayeredScene | None, owner_masks: dict[str, np.ndarray], macro_id: str,
) -> np.ndarray | None:
    if layered is None:
        return None
    result = np.zeros(next(iter(owner_masks.values())).shape, bool)
    for edge in layered.order_graph.edges:
        if edge.back_id == macro_id:
            result |= owner_masks[edge.front_id]
    return result


def _shape_area(
    primitive: str, names: tuple[str, ...], values: np.ndarray,
) -> float:
    parameters = dict(zip(names, (float(value) for value in values)))
    if primitive == "circle":
        return math.pi * parameters["radius"] ** 2
    if primitive == "ring":
        return math.pi * max(
            0.0,
            parameters["radius"] ** 2 - parameters["inner_radius"] ** 2,
        )
    if primitive == "ellipse":
        return math.pi * parameters["rx"] * parameters["ry"]
    if primitive in {"rectangle", "D_bullet"}:
        if primitive == "D_bullet":
            radius = 0.5 * parameters["height"]
            return max(
                0.0,
                parameters["height"] * (parameters["width"] - radius)
                + 0.5 * math.pi * radius ** 2,
            )
        return parameters["width"] * parameters["height"]
    if primitive == "rounded_rectangle":
        radius = min(
            parameters["radius"],
            0.5 * parameters["width"],
            0.5 * parameters["height"],
        )
        return (
            parameters["width"] * parameters["height"]
            - (4.0 - math.pi) * radius ** 2
        )
    point_prefix = "curve_p" if primitive == "free_curve" else "p"
    points = []
    for index in range(64):
        x = parameters.get(f"{point_prefix}{index}_x")
        y = parameters.get(f"{point_prefix}{index}_y")
        if x is None or y is None:
            break
        points.append((x, y))
    if len(points) < 3:
        return 0.0
    polygon = np.asarray(points, np.float64)
    return 0.5 * abs(float(np.sum(
        polygon[:, 0] * np.roll(polygon[:, 1], -1)
        - polygon[:, 1] * np.roll(polygon[:, 0], -1)
    )))


def _polyline_distances(points: np.ndarray, anchors: np.ndarray) -> np.ndarray:
    if not len(points) or len(anchors) < 2:
        return np.zeros(len(points), np.float64)
    starts = anchors
    ends = np.roll(anchors, -1, axis=0)
    segments = ends - starts
    denominator = np.maximum(
        np.sum(segments * segments, axis=1), 1e-12,
    )
    relative = points[:, None, :] - starts[None, :, :]
    fractions = np.clip(
        np.sum(relative * segments[None, :, :], axis=2)
        / denominator[None, :],
        0.0, 1.0,
    )
    projections = (
        starts[None, :, :] + fractions[..., None] * segments[None, :, :]
    )
    return np.sqrt(np.min(np.sum(
        np.square(points[:, None, :] - projections), axis=2,
    ), axis=1))


def _boundary_expression(
    candidate: MacroCandidate, variables: tuple[ContinuousVariable, ...],
    owner_mask: np.ndarray, *, axis: str, target: float,
) -> tuple[tuple[int, ...], tuple[float, ...]] | None:
    by_name = {
        row.name: row for row in variables if row.macro_id == candidate.id
    }
    if not by_name:
        return None
    values = dict(candidate.program.parameters)
    ys, xs = np.nonzero(owner_mask)
    if not len(xs):
        return None
    center = float(np.mean(xs if axis == "x" else ys))
    high_side = center < target
    primitive = (
        candidate.program.operator.split("/", 1)[1]
        if candidate.program.operator.startswith("Shape/") else ""
    )
    if primitive in {"rectangle", "rounded_rectangle", "D_bullet"}:
        origin = axis
        extent = "width" if axis == "x" else "height"
        if origin not in by_name:
            return None
        indices = [by_name[origin].index]
        coefficients = [1.0]
        if high_side and extent in by_name:
            indices.append(by_name[extent].index)
            coefficients.append(1.0)
        return tuple(indices), tuple(coefficients)
    if primitive in {"circle", "ring", "ellipse"}:
        origin = "cx" if axis == "x" else "cy"
        extent = (
            "radius" if primitive in {"circle", "ring"}
            else "rx" if axis == "x" else "ry"
        )
        if origin not in by_name or extent not in by_name:
            return None
        return (
            (by_name[origin].index, by_name[extent].index),
            (1.0, 1.0 if high_side else -1.0),
        )
    prefix = "curve_p" if primitive == "free_curve" else "p"
    point_rows = []
    for index in range(64):
        name = f"{prefix}{index}_{axis}"
        value = values.get(name)
        if name not in by_name or not isinstance(value, (float, int)):
            if index:
                break
            continue
        point_rows.append((by_name[name].index, float(value)))
    if not point_rows:
        return None
    extreme = max(value for _index, value in point_rows) if high_side else min(
        value for _index, value in point_rows
    )
    selected = [
        index for index, value in point_rows if abs(value - extreme) <= 1.0
    ]
    return (
        tuple(selected), tuple(1.0 / len(selected) for _ in selected),
    )


def _factor_row_count(factor: _Factor) -> int:
    if isinstance(factor, (_LinearFactor, _AreaFactor)):
        return 1
    if isinstance(factor, _ShapeFactor):
        return len(factor.points_xy)
    if isinstance(factor, _CurveEvidenceFactor):
        return len(factor.points_xy) + len(factor.indices) // 2
    return len(factor.indices)


def _build_factors(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    layered: LayeredScene | None, variables: tuple[ContinuousVariable, ...],
    samples_per_shape: int,
) -> tuple[tuple[_Factor, ...], tuple[FactorAudit, ...]]:
    lookup = cmir.by_id(); owner_masks = _owner_masks(reir, cmir, scene)
    index = {(row.macro_id, row.name): row.index for row in variables}
    factors: list[_Factor] = []
    audits = []
    for variable in variables:
        # Weak interval/prior evidence keeps unobserved dimensions physical.
        factor = _LinearFactor(
            "evidence_interval", (variable.index,), (1.0,), variable.initial,
            0.08 / max(0.05, variable.prior_sigma), (variable.macro_id,),
        )
        factors.append(factor)
        audits.append(FactorAudit(
            factor.kind, factor.macro_ids, factor.indices, 1, 1.0,
        ))

    for macro_id in scene.selected_macro_ids:
        candidate = lookup[macro_id]
        primitive = (
            candidate.program.operator.split("/", 1)[1]
            if candidate.program.operator.startswith("Shape/") else ""
        )
        names = {name for owner, name in index if owner == macro_id}
        required = {
            "circle": ("cx", "cy", "radius"),
            "ring": ("cx", "cy", "radius"),
            "ellipse": ("cx", "cy", "rx", "ry", "angle"),
        }.get(primitive)
        if required and all(name in names for name in required):
            evidence = owner_masks[macro_id].copy()
            front = _front_masks(layered, owner_masks, macro_id)
            if front is not None:
                uncertain = cv2.dilate(front.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
                boundary = cv2.morphologyEx(
                    evidence.astype(np.uint8), cv2.MORPH_GRADIENT,
                    np.ones((3, 3), np.uint8),
                ) > 0
                evidence[boundary & uncertain] = False
            points, weights, perimeter = _sample_contour(evidence, samples_per_shape)
            if len(points) >= 8:
                indices = tuple(index[(macro_id, name)] for name in required)
                factor = _ShapeFactor(
                    "SDF+render_residual", primitive, indices,
                    points, weights, macro_id,
                )
                factors.append(factor)
                audits.append(FactorAudit(
                    factor.kind, (macro_id,), indices, len(points), perimeter,
                ))
        if primitive == "ring" and all(
            name in names for name in ("inner_cx", "inner_cy", "inner_radius")
        ):
            contours, hierarchy = cv2.findContours(
                owner_masks[macro_id].astype(np.uint8),
                cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE,
            )
            children = [] if hierarchy is None else [
                contour for contour, relation in zip(contours, hierarchy[0])
                if int(relation[3]) >= 0
            ]
            if children:
                hole_line = np.zeros_like(owner_masks[macro_id], np.uint8)
                cv2.drawContours(hole_line, children, -1, 1, 1)
                points, weights, perimeter = _sample_contour(
                    hole_line > 0, samples_per_shape,
                )
                if len(points) >= 8:
                    indices = tuple(index[(macro_id, name)] for name in (
                        "inner_cx", "inner_cy", "inner_radius",
                    ))
                    factor = _ShapeFactor(
                        "SDF_inner_counter_evidence", "circle", indices,
                        points, weights, macro_id,
                    )
                    factors.append(factor)
                    audits.append(FactorAudit(
                        factor.kind, (macro_id,), indices, len(points),
                        perimeter,
                    ))

        area_names = {
            "circle": ("radius",),
            "ring": ("radius", "inner_radius"),
            "ellipse": ("rx", "ry"),
            "rectangle": ("width", "height"),
            "rounded_rectangle": ("width", "height", "radius"),
            "D_bullet": ("width", "height"),
        }.get(primitive)
        if primitive in {"triangle", "quadrilateral", "star"}:
            area_names = tuple(sorted(
                names, key=lambda value: (
                    int(value[1:].split("_", 1)[0]), value.endswith("_y"),
                ),
            ))
        elif primitive == "free_curve":
            area_names = tuple(sorted(
                (name for name in names if name.startswith("curve_p")),
                key=lambda value: (
                    int(value[7:].split("_", 1)[0]), value.endswith("_y"),
                ),
            ))
        if area_names and all(name in names for name in area_names):
            indices = tuple(index[(macro_id, name)] for name in area_names)
            target_area = float(np.sum(owner_masks[macro_id]))
            factor = _AreaFactor(
                "coverage_render_residual", primitive, area_names, indices,
                target_area, 0.20 / max(1.0, target_area), macro_id,
            )
            factors.append(factor)
            audits.append(FactorAudit(
                factor.kind, (macro_id,), indices, 1, target_area,
            ))

        if primitive == "free_curve":
            curve_names = []
            for point_index in range(64):
                x_name = f"curve_p{point_index}_x"
                y_name = f"curve_p{point_index}_y"
                if x_name not in names or y_name not in names:
                    break
                curve_names.extend((x_name, y_name))
            if len(curve_names) >= 6:
                points, weights, perimeter = _sample_contour(
                    owner_masks[macro_id], samples_per_shape,
                )
                indices = tuple(
                    index[(macro_id, name)] for name in curve_names
                )
                if len(points) >= 8:
                    evidence_factor = _CurveEvidenceFactor(
                        "curve_control_point_SDF", indices, points, weights,
                        perimeter, macro_id,
                    )
                    factors.append(evidence_factor)
                    audits.append(FactorAudit(
                        evidence_factor.kind, (macro_id,), indices,
                        _factor_row_count(evidence_factor), perimeter,
                    ))
                    regularity = _CurveRegularityFactor(
                        "curve_G1_structural+G2_curvature", indices,
                        perimeter, 0.025, macro_id,
                    )
                    factors.append(regularity)
                    audits.append(FactorAudit(
                        regularity.kind, (macro_id,), indices,
                        _factor_row_count(regularity), perimeter,
                    ))

        symmetry_primitives = {
            "circle", "ring", "ellipse", "rectangle",
            "rounded_rectangle", "D_bullet", "star",
        }
        symmetry_evidence = primitive in symmetry_primitives or any(
            token.family == "symmetry"
            for token in reir.proposal_tokens
            if token.id in candidate.soft_evidence
        )
        if symmetry_evidence and primitive:
            ys, xs = np.nonzero(owner_masks[macro_id])
            if len(xs):
                target_x = 0.5 * (float(np.min(xs)) + float(np.max(xs)))
                target_y = 0.5 * (float(np.min(ys)) + float(np.max(ys)))
                expressions = []
                if "cx" in names:
                    expressions.append(("x", ("cx",), (1.0,), target_x))
                elif {"x", "width"}.issubset(names):
                    expressions.append(
                        ("x", ("x", "width"), (1.0, 0.5), target_x)
                    )
                if "cy" in names:
                    expressions.append(("y", ("cy",), (1.0,), target_y))
                elif {"y", "height"}.issubset(names):
                    expressions.append(
                        ("y", ("y", "height"), (1.0, 0.5), target_y)
                    )
                for axis, factor_names, coefficients, target in expressions:
                    indices = tuple(
                        index[(macro_id, name)] for name in factor_names
                    )
                    factor = _LinearFactor(
                        f"symmetry_{axis}_axis_evidence", indices,
                        coefficients, target, 0.25, (macro_id,),
                    )
                    factors.append(factor)
                    audits.append(FactorAudit(
                        factor.kind, factor.macro_ids, indices, 1,
                        float(np.sum(owner_masks[macro_id])),
                    ))
        if candidate.kind is MacroKind.STROKE_NETWORK and "width" in names:
            distance = cv2.distanceTransform(owner_masks[macro_id].astype(np.uint8), cv2.DIST_L2, 5)
            ridge = distance >= cv2.dilate(distance, np.ones((3, 3), np.float32)) - 1e-5
            # The fallback is the selected program's physical width.  Returning
            # the optimization-vector index here silently pulled empty-ridge
            # strokes toward an unrelated integer parameter slot.
            target = (
                float(np.median(np.maximum(1.0, 2.0 * distance[ridge] - 1.0)))
                if np.any(ridge)
                else float(dict(candidate.continuous_params)["width"])
            )
            factor = _LinearFactor(
                "stroke_width+shared_interface", (index[(macro_id, "width")],),
                (1.0,), target, 1.0, (macro_id,),
            )
            factors.append(factor); audits.append(FactorAudit(
                factor.kind, factor.macro_ids, factor.indices, 1,
                float(np.sum(owner_masks[macro_id])),
            ))
        if candidate.kind is MacroKind.TEXT_LINE:
            if {"x_height", "cap_height"}.issubset(names):
                # A soft grammar factor anchors cap-height >= x-height without
                # inventing glyph loops or changing line ownership.
                factor = _LinearFactor(
                    "text_line_grammar", (
                        index[(macro_id, "cap_height")], index[(macro_id, "x_height")],
                    ), (1.0, -1.0), max(0.0, dict(candidate.continuous_params)["cap_height"]
                                               - dict(candidate.continuous_params)["x_height"]),
                    0.35, (macro_id,),
                )
                factors.append(factor); audits.append(FactorAudit(
                    factor.kind, factor.macro_ids, factor.indices, 1, 1.0,
                ))
            text_support = owner_masks[macro_id]
            ys, _xs = np.nonzero(text_support)
            if len(ys) >= 4:
                top = float(np.quantile(ys, 0.02))
                bottom = float(np.quantile(ys, 0.98))
                measured_height = max(0.25, bottom - top + 1.0)
                targets = {
                    "baseline": bottom,
                    "x_height": measured_height,
                    "cap_height": measured_height,
                }
                count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
                    text_support.astype(np.uint8), 8,
                )
                component_rows = [
                    tuple(int(value) for value in stats[label])
                    for label in range(1, count)
                    if int(stats[label, cv2.CC_STAT_AREA]) > 0
                ]
                if component_rows:
                    component_heights = np.asarray([
                        row[cv2.CC_STAT_HEIGHT] for row in component_rows
                    ], np.float64)
                    median_component_height = float(np.median(component_heights))
                    body_rows = [
                        row for row in component_rows
                        if row[cv2.CC_STAT_HEIGHT]
                        >= max(2.0, 0.50 * median_component_height)
                    ] or component_rows
                    bottoms = np.asarray([
                        row[cv2.CC_STAT_TOP] + row[cv2.CC_STAT_HEIGHT]
                        for row in body_rows
                    ], np.float64)
                    targets["overshoot"] = float(
                        np.max(bottoms) - np.median(bottoms)
                    )
                    ordered = sorted(
                        body_rows, key=lambda row: row[cv2.CC_STAT_LEFT],
                    )
                    gaps = [
                        max(
                            0,
                            right[cv2.CC_STAT_LEFT]
                            - left[cv2.CC_STAT_LEFT]
                            - left[cv2.CC_STAT_WIDTH],
                        )
                        for left, right in zip(ordered, ordered[1:])
                    ]
                    if gaps:
                        targets["tracking"] = float(np.median(gaps))
                distance = cv2.distanceTransform(
                    text_support.astype(np.uint8), cv2.DIST_L2, 5,
                )
                ridge = distance >= (
                    cv2.dilate(distance, np.ones((3, 3), np.float32)) - 1e-5
                )
                if np.any(ridge):
                    targets["shared_stem_width"] = float(np.median(
                        np.maximum(0.25, 2.0 * distance[ridge] - 1.0)
                    ))
                for name, target in targets.items():
                    if name not in names:
                        continue
                    factor = _LinearFactor(
                        f"text_{name}_evidence", (index[(macro_id, name)],),
                        (1.0,), target, 0.25, (macro_id,),
                    )
                    factors.append(factor); audits.append(FactorAudit(
                        factor.kind, factor.macro_ids, factor.indices, 1,
                        measured_height,
                    ))
        if candidate.program.operator.startswith("Appearance/"):
            mask = owner_masks[macro_id]
            area = float(np.sum(mask))
            if area > 0:
                target_values = {
                    "oklab_l": float(np.median(reir.raster.oklab[..., 0][mask])),
                    "oklab_a": float(np.median(reir.raster.oklab[..., 1][mask])),
                    "oklab_b": float(np.median(reir.raster.oklab[..., 2][mask])),
                    "alpha": float(np.median(
                        reir.raster.straight_rgba[..., 3][mask]
                    )),
                }
                for name, target in target_values.items():
                    if name not in names:
                        continue
                    factor = _LinearFactor(
                        "appearance_color+alpha_area_residual",
                        (index[(macro_id, name)],), (1.0,), target,
                        0.50, (macro_id,),
                    )
                    factors.append(factor); audits.append(FactorAudit(
                        factor.kind, factor.macro_ids, factor.indices, 1, area,
                    ))
            if "angle_deg" in names and int(np.sum(mask)) >= 8:
                light = np.asarray(reir.raster.oklab[..., 0], np.float64)
                gx = cv2.Sobel(light, cv2.CV_64F, 1, 0, ksize=3)[mask]
                gy = cv2.Sobel(light, cv2.CV_64F, 0, 1, ksize=3)[mask]
                tensor = np.asarray((
                    (float(np.sum(gx * gx)), float(np.sum(gx * gy))),
                    (float(np.sum(gx * gy)), float(np.sum(gy * gy))),
                ))
                values, vectors = np.linalg.eigh(tensor)
                direction = vectors[:, int(np.argmax(values))]
                observed_angle = math.degrees(math.atan2(
                    float(direction[1]), float(direction[0]),
                ))
                initial_angle = dict(candidate.program.parameters)["angle_deg"]
                while observed_angle - float(initial_angle) > 90.0:
                    observed_angle -= 180.0
                while observed_angle - float(initial_angle) < -90.0:
                    observed_angle += 180.0
                factor = _LinearFactor(
                    "appearance_gradient_direction", (
                        index[(macro_id, "angle_deg")],
                    ), (1.0,), observed_angle, 0.30, (macro_id,),
                )
                factors.append(factor); audits.append(FactorAudit(
                    factor.kind, factor.macro_ids, factor.indices, 1, area,
                ))
        if candidate.program.operator.startswith("RepeatGroup/"):
            shared = [
                row for row in variables
                if row.macro_id == macro_id
                and row.name in {"shared_scale", "shared_gap"}
            ]
            for shared_variable in shared:
                factor = _LinearFactor(
                    "equal_radius_width_gap+group_ADMM_consensus",
                    (shared_variable.index,), (1.0,), shared_variable.initial,
                    0.75, (macro_id,),
                )
                factors.append(factor); audits.append(FactorAudit(
                    factor.kind, factor.macro_ids, factor.indices, 1, 1.0,
                ))

    # Couple the actual boundary coordinates of adjacent selected programs.
    # This is a pairwise sparse factor; an audit label alone is not enough.
    for interface in reir.interfaces.interfaces:
        if interface.id >= len(cmir.interface_endpoints):
            continue
        leaf_a, leaf_b = cmir.interface_endpoints[interface.id]
        if leaf_a >= len(scene.owner_by_leaf) or leaf_b >= len(scene.owner_by_leaf):
            continue
        first_id = scene.owner_by_leaf[leaf_a]
        second_id = scene.owner_by_leaf[leaf_b]
        if first_id == second_id or (
            first_id not in lookup or second_id not in lookup
        ):
            continue
        x1, y1, x2, y2 = interface.bbox_xyxy
        axis = "x" if y2 - y1 >= x2 - x1 else "y"
        target = 0.5 * ((x1 + x2) if axis == "x" else (y1 + y2))
        first = _boundary_expression(
            lookup[first_id], variables, owner_masks[first_id],
            axis=axis, target=target,
        )
        second = _boundary_expression(
            lookup[second_id], variables, owner_masks[second_id],
            axis=axis, target=target,
        )
        if first is None or second is None:
            continue
        first_indices, first_coefficients = first
        second_indices, second_coefficients = second
        indices = (*first_indices, *second_indices)
        coefficients = (*first_coefficients, *(
            -value for value in second_coefficients
        ))
        factor = _LinearFactor(
            "pairwise_shared_interface", indices, coefficients, 0.0,
            max(0.05, min(0.50, interface.length_px / 128.0)),
            (first_id, second_id),
        )
        factors.append(factor)
        audits.append(FactorAudit(
            factor.kind, factor.macro_ids, factor.indices, 1,
            float(interface.length_px),
        ))
    return tuple(factors), tuple(audits)


def _factor_residual(factor: _Factor, values: np.ndarray) -> np.ndarray:
    if isinstance(factor, _LinearFactor):
        estimate = sum(coefficient * values[index]
                       for coefficient, index in zip(factor.coefficients, factor.indices))
        return np.asarray([(estimate - factor.target) * math.sqrt(factor.weight)], np.float64)
    if isinstance(factor, _AreaFactor):
        area = _shape_area(
            factor.primitive, factor.names, values[list(factor.indices)],
        )
        return np.asarray([
            (area - factor.target_area) * math.sqrt(factor.weight)
        ], np.float64)
    if isinstance(factor, _CurveEvidenceFactor):
        anchors = values[list(factor.indices)].reshape((-1, 2))
        evidence_to_curve = _polyline_distances(
            factor.points_xy, anchors,
        ) * factor.physical_weights
        curve_to_evidence = np.sqrt(np.min(np.sum(
            np.square(
                anchors[:, None, :] - factor.points_xy[None, :, :]
            ), axis=2,
        ), axis=1))
        curve_to_evidence *= math.sqrt(
            factor.physical_measure / max(1, len(anchors))
        )
        return np.concatenate((evidence_to_curve, curve_to_evidence))
    if isinstance(factor, _CurveRegularityFactor):
        anchors = values[list(factor.indices)].reshape((-1, 2))
        second = (
            np.roll(anchors, 1, axis=0) - 2.0 * anchors
            + np.roll(anchors, -1, axis=0)
        )
        curvature_change = np.roll(second, -1, axis=0) - second
        scale = math.sqrt(
            factor.weight * factor.physical_measure / max(1, len(anchors))
        )
        return (curvature_change * scale).reshape(-1)
    parameters = values[list(factor.indices)]
    x = factor.points_xy[:, 0]; y = factor.points_xy[:, 1]
    if factor.primitive in {"circle", "ring"}:
        cx, cy, radius = parameters
        residual = np.hypot(x - cx, y - cy) - radius
    else:
        cx, cy, rx, ry, angle = parameters
        radians = math.radians(float(angle)); cosine = math.cos(radians); sine = math.sin(radians)
        dx, dy = x - cx, y - cy
        local_x = cosine * dx + sine * dy
        local_y = -sine * dx + cosine * dy
        residual = (
            np.sqrt(np.square(local_x / max(0.25, rx))
                    + np.square(local_y / max(0.25, ry))) - 1.0
        ) * math.sqrt(max(0.25, rx * ry))
    return residual * factor.physical_weights


def _program_with_values(
    candidate: MacroCandidate, values: dict[str, float],
) -> SceneProgram:
    seen = set()
    parameters = []
    for name, value in candidate.program.parameters:
        if name in values and isinstance(value, (float, int)):
            parameters.append((name, float(values[name]))); seen.add(name)
        else:
            parameters.append((name, value))
    for name, value in values.items():
        if name not in seen and name not in dict(candidate.program.parameters):
            parameters.append((name, float(value)))
    return SceneProgram(candidate.program.operator, tuple(parameters))


def _visible_program_mask(
    reir: RasterEvidenceIR, candidate: MacroCandidate, program: SceneProgram,
    shape: tuple[int, int], front: np.ndarray | None,
    phase5_bundle: "Phase5MacroBundle | None",
    text_macros: "TextMacroSet | None",
) -> np.ndarray | None:
    delivered_program = program
    if (
        program != candidate.program
        and "refined_source_id" not in dict(program.parameters)
    ):
        delivered_program = SceneProgram(
            program.operator,
            (*program.parameters, ("refined_source_id", candidate.id)),
        )
    updated = replace(candidate, program=delivered_program)
    rendered = _render_typed_shape(updated, shape)
    if rendered is None:
        # Local import avoids the export_writer -> design_program ->
        # continuous_refine module cycle while still proving the exact
        # production fragments for every non-shape parameter transaction.
        from .export_writer import (
            render_appearance_delivery, render_group_delivery,
            render_shape_delivery, render_stroke_delivery,
            render_text_delivery,
        )
        rgba = None
        if program.operator == "Shape/free_curve":
            rgba = render_shape_delivery(reir, updated)
        elif phase5_bundle is not None and program.operator.startswith(
            "RepeatGroup/"
        ):
            rgba = render_group_delivery(reir, updated, phase5_bundle)
        elif (
            phase5_bundle is not None
            and candidate.kind is MacroKind.STROKE_NETWORK
        ):
            rgba = render_stroke_delivery(reir, updated, phase5_bundle)
        elif phase5_bundle is not None and program.operator.startswith(
            "Appearance/"
        ):
            source_id = candidate.id
            record = next((
                row for row in phase5_bundle.appearances.records
                if row.candidate.id == source_id
            ), None)
            if record is not None:
                rgba = render_appearance_delivery(reir, record, updated)
        elif text_macros is not None and candidate.kind is MacroKind.TEXT_LINE:
            rgba = render_text_delivery(reir, updated, text_macros)
        if rgba is not None:
            rendered = np.asarray(rgba)[..., 3] >= 128
    if rendered is None:
        return None
    return rendered & ~front if front is not None else rendered


def _mask_error(reference: np.ndarray, rendered: np.ndarray) -> float:
    return float(np.sum(reference ^ rendered) / max(1, np.sum(reference | rendered)))


def refine_selected_scene(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    *, layered: LayeredScene | None = None, max_iterations: int = 16,
    samples_per_shape: int = 64,
    phase5_bundle: "Phase5MacroBundle | None" = None,
    text_macros: "TextMacroSet | None" = None,
) -> ContinuousRefinementResult:
    reir.validate(); cmir.validate(); scene.validate(cmir)
    if layered is not None:
        layered.validate(reir, cmir)
        if layered.visible_scene.owner_by_leaf != scene.owner_by_leaf:
            raise ValueError("layered scene belongs to a different VSIR")
    owner_before = _owner_digest(scene.owner_by_leaf)
    order_before = (
        layered.order_graph.back_to_front if layered is not None
        else tuple(scene.selected_macro_ids)
    )
    variables = _variables(reir, cmir, scene)
    factors, audits = _build_factors(
        reir, cmir, scene, layered, variables, samples_per_shape,
    )
    initial = np.asarray([row.initial for row in variables], np.float64)
    lower = np.asarray([row.lower for row in variables], np.float64)
    upper = np.asarray([row.upper for row in variables], np.float64)

    def residual(values: np.ndarray) -> np.ndarray:
        if not factors:
            return np.zeros(1, np.float64)
        return np.concatenate([_factor_residual(factor, values) for factor in factors])

    initial_residual = residual(initial)
    if variables and factors and max_iterations > 0:
        residual_rows = sum(_factor_row_count(factor) for factor in factors)
        sparsity = lil_matrix((residual_rows, len(variables)), dtype=np.int8)
        row = 0
        for factor in factors:
            count = _factor_row_count(factor)
            for index in factor.indices:
                sparsity[row:row + count, index] = 1
            row += count
        optimized = least_squares(
            residual, initial, bounds=(lower, upper), jac_sparsity=sparsity.tocsr(),
            loss="huber", f_scale=1.0, method="trf",
            max_nfev=max(2, int(max_iterations)),
            xtol=1e-8, ftol=1e-8, gtol=1e-8,
        )
        proposed = optimized.x
        evaluations = int(optimized.nfev)
        iterations = max(0, evaluations - 1)
        jacobian = optimized.jac.toarray() if hasattr(optimized.jac, "toarray") else np.asarray(optimized.jac)
        information = jacobian.T @ jacobian
        covariance_matrix = np.linalg.pinv(information + np.eye(len(variables)) * 1e-9)
        variances = np.maximum(0.0, np.diag(covariance_matrix))
    else:
        proposed = initial.copy(); evaluations = 0; iterations = 0
        variances = np.asarray([row.prior_sigma ** 2 for row in variables])

    lookup = cmir.by_id(); owner_masks = _owner_masks(reir, cmir, scene)
    by_macro: dict[str, list[ContinuousVariable]] = {}
    for variable in variables:
        by_macro.setdefault(variable.macro_id, []).append(variable)
    refined = []; final_values = proposed.copy()
    native_before = 0.0; native_after = 0.0
    for macro_id in scene.selected_macro_ids:
        candidate = lookup[macro_id]
        rows = by_macro.get(macro_id, [])
        values = {row.name: float(proposed[row.index]) for row in rows}
        program = _program_with_values(candidate, values)
        front = _front_masks(layered, owner_masks, macro_id)
        before_mask = _visible_program_mask(
            reir, candidate, candidate.program, owner_masks[macro_id].shape,
            front, phase5_bundle, text_macros,
        )
        after_mask = _visible_program_mask(
            reir, candidate, program, owner_masks[macro_id].shape, front,
            phase5_bundle, text_macros,
        )
        before_error = after_error = None
        committed = bool(rows) and program != candidate.program
        reason = None if committed else (
            "no-parameter-change" if rows else "no-continuous-variables"
        )
        if before_mask is not None and after_mask is not None:
            before_error = _mask_error(owner_masks[macro_id], before_mask)
            after_error = _mask_error(owner_masks[macro_id], after_mask)
            native_before += before_error; native_after += after_error
            claimed = (
                candidate.certificates.components, candidate.certificates.holes,
            )
            if committed and topology_signature(after_mask) != claimed:
                committed = False; reason = "certificate-topology-violation"
            elif committed and after_error > before_error + 1e-9:
                committed = False; reason = "native-rerender-worse"
        if not committed:
            for row in rows:
                final_values[row.index] = row.initial
            program = candidate.program; after_error = before_error
            native_after -= (native_after - native_before) if len(scene.selected_macro_ids) == 1 else 0.0
        refined.append(RefinedMacro(
            macro_id=macro_id, original_program=candidate.program,
            refined_program=program,
            original_params=tuple((row.name, row.initial) for row in rows),
            refined_params=tuple((row.name, float(final_values[row.index])) for row in rows),
            covariance=tuple(float(variances[row.index]) for row in rows),
            committed=committed, rollback_reason=reason,
            native_error_before=before_error, native_error_after=after_error,
        ))

    # Recompute the exact native support transaction after per-macro rollbacks.
    native_before = 0.0; native_after = 0.0
    for row in refined:
        if row.native_error_before is not None:
            native_before += row.native_error_before
            native_after += row.native_error_after or 0.0
    global_valid = native_after <= native_before + 1e-9
    global_commit = global_valid and any(row.committed for row in refined)
    rollback_reason = None if global_commit else "no-continuous-delivery-change"
    if not global_valid:
        rollback_reason = "full-scene-native-rerender-worse"
        native_after = native_before
        refined = [replace(
            row, refined_program=row.original_program,
            refined_params=row.original_params, committed=False,
            rollback_reason=rollback_reason,
            native_error_after=row.native_error_before,
        ) for row in refined]
        final_values = initial.copy()

    result = ContinuousRefinementResult(
        selected_ids=scene.selected_macro_ids,
        owner_digest_before=owner_before,
        owner_digest_after=_owner_digest(scene.owner_by_leaf),
        layer_order_before=order_before, layer_order_after=order_before,
        variables=variables, factors=audits, macros=tuple(refined),
        iterations=iterations, function_evaluations=evaluations,
        initial_cost=float(0.5 * np.sum(np.square(initial_residual))),
        final_cost=float(0.5 * np.sum(np.square(residual(final_values)))),
        native_render_error_before=native_before,
        native_render_error_after=native_after,
        committed=global_commit,
        rollback_reason=rollback_reason,
        solver="sparse-trust-region-Gauss-Newton+Huber",
        provenance=(
            "fixed-selected-topology", "fixed-owner-cells", "fixed-layer-order",
            "physical-arclength-weighted-integrals",
            "strict-iteration-budget", "exact-native-rerender-before-commit",
            "certificate-violation-rollback",
        ),
    )
    result.validate()
    return result
