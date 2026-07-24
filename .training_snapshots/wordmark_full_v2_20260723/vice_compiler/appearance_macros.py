"""Phase-5 proof-carrying appearance model generator.

Appearance is selected late and jointly with geometry.  Solid, linear,
radial, translucent and flat-albedo/smooth-shade hypotheses all compete on
the same immutable REIR support; no early palette quantization is performed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations, permutations
import math
from typing import Iterable, TYPE_CHECKING

import cv2
import numpy as np

from .certificates import mask_sha256, topology_signature
from .evidence_ir import RasterEvidenceIR, _linear_rgb_to_oklab
from .macro_ir import MacroCandidate, MacroKind, ResourceEstimate, SceneProgram
from .macro_registry import (
    candidate_from_support, decode_token_mask, descendant_leaf_bits,
    leaf_bits_mask, rekey_draft_candidate,
)
from .proposal_net import query_support_mask

if TYPE_CHECKING:
    from .proposal_net import ProposalQuery


def oklab_alpha_to_linear_premultiplied(values: np.ndarray) -> np.ndarray:
    """Convert Oklab + straight alpha to finite linear-premultiplied RGBA."""
    source = np.asarray(values, np.float64)
    if source.shape[-1] != 4:
        raise ValueError("appearance field must have Oklab+alpha channels")
    light, axis_a, axis_b = (
        source[..., 0], source[..., 1], source[..., 2]
    )
    l_root = light + 0.3963377774 * axis_a + 0.2158037573 * axis_b
    m_root = light - 0.1055613458 * axis_a - 0.0638541728 * axis_b
    s_root = light - 0.0894841775 * axis_a - 1.2914855480 * axis_b
    l_value = l_root ** 3; m_value = m_root ** 3; s_value = s_root ** 3
    red = 4.0767416621 * l_value - 3.3077115913 * m_value + 0.2309699292 * s_value
    green = -1.2684380046 * l_value + 2.6097574011 * m_value - 0.3413193965 * s_value
    blue = -0.0041960863 * l_value - 0.7034186147 * m_value + 1.7076147010 * s_value
    alpha = np.clip(source[..., 3], 0.0, 1.0)
    linear = np.clip(np.stack((red, green, blue), axis=-1), 0.0, 1.0)
    result = np.concatenate((linear * alpha[..., None], alpha[..., None]), axis=-1)
    return np.ascontiguousarray(result, np.float32)


@dataclass(frozen=True)
class OrderedTranslucentLayer:
    """One evidence-fitted layer in a bounded back-to-front stack."""

    support_mask: np.ndarray
    linear_premultiplied_rgba: tuple[float, float, float, float]
    support_digest: str


@dataclass(frozen=True)
class AppearanceFitRecord:
    candidate: MacroCandidate
    model: str
    support_mask: np.ndarray
    fit_mask: np.ndarray
    rendered_oklab_alpha: np.ndarray
    parameters: tuple[tuple[str, float | int | str], ...]
    residual_rmse: float
    residual_p95: float
    improvement_over_solid: float
    directional_alignment: float
    continuity: float
    source_token_ids: tuple[int, ...]
    stack_layers: tuple[OrderedTranslucentLayer, ...] = ()

    def validate(self, reir: RasterEvidenceIR) -> None:
        shape = (reir.height, reir.width)
        if self.support_mask.shape != shape or self.fit_mask.shape != shape:
            raise ValueError("appearance support is outside the REIR lattice")
        if self.rendered_oklab_alpha.shape != (*shape, 4):
            raise ValueError("appearance render has invalid channel shape")
        if any(row.flags.writeable for row in (
            self.support_mask, self.fit_mask, self.rendered_oklab_alpha,
        )):
            raise ValueError("appearance evidence must be immutable")
        if self.model == "ordered_translucent_stack":
            if not 2 <= len(self.stack_layers) <= 3:
                raise ValueError("ordered translucent stack exceeds bounded K")
            for layer in self.stack_layers:
                if (
                    layer.support_mask.shape != shape
                    or layer.support_mask.flags.writeable
                    or not np.any(layer.support_mask)
                    or np.any(layer.support_mask & ~self.support_mask)
                    or mask_sha256(layer.support_mask) != layer.support_digest
                ):
                    raise ValueError("ordered translucent layer support is invalid")
                rgba = layer.linear_premultiplied_rgba
                if (
                    len(rgba) != 4
                    or not all(math.isfinite(value) for value in rgba)
                    or not 0.0 < rgba[3] < 0.9995
                    or any(value < 0.0 or value > rgba[3] + 1e-6 for value in rgba[:3])
                ):
                    raise ValueError("ordered translucent layer paint is invalid")
        elif self.stack_layers:
            raise ValueError("non-stack appearance carries translucent layers")
        if not all(math.isfinite(value) and value >= 0 for value in (
            self.residual_rmse, self.residual_p95,
        )):
            raise ValueError("appearance residual is invalid")
        replace(self.candidate, registry_index=0, conflict_bits=0).validate(
            leaf_count=reir.hierarchy.leaf_count,
            interface_count=len(reir.interfaces.interfaces), candidate_count=1,
        )


@dataclass(frozen=True)
class AppearanceMacroSet:
    records: tuple[AppearanceFitRecord, ...]
    rois_considered: int
    candidates_pruned: int
    provenance: tuple[str, ...]

    @property
    def candidates(self) -> tuple[MacroCandidate, ...]:
        return tuple(row.candidate for row in self.records)


def _freeze(array: np.ndarray, *, dtype: np.dtype | type | None = None) -> np.ndarray:
    result = np.ascontiguousarray(array, dtype=dtype)
    result.setflags(write=False)
    return result


def _bbox(mask: np.ndarray, pad: int = 0) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("cannot bound empty appearance support")
    return (
        max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + 1 + pad),
        min(mask.shape[0], int(ys.max()) + 1 + pad),
    )


def _fit_mask(reir: RasterEvidenceIR, support: np.ndarray) -> np.ndarray:
    interior = cv2.erode(support.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    boundary = reir.boundary_pyramid[0]
    reliable = (
        (boundary.probability < 0.42)
        & (boundary.uncertainty < 0.72)
    )
    fit = interior & reliable
    minimum = max(6, min(64, int(0.12 * support.sum())))
    if int(fit.sum()) < minimum:
        fit = interior if int(interior.sum()) >= 4 else support
    return fit


def _coordinates(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.indices(mask.shape, dtype=np.float64)
    x1, y1, x2, y2 = _bbox(mask)
    xn = (x - 0.5 * (x1 + x2 - 1)) / max(1.0, x2 - x1)
    yn = (y - 0.5 * (y1 + y2 - 1)) / max(1.0, y2 - y1)
    return xn, yn


def _least_squares(
    basis: np.ndarray, signal: np.ndarray, fit: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    matrix = basis[fit]
    values = signal[fit]
    coefficients, _residuals, _rank, _singular = np.linalg.lstsq(
        matrix, values, rcond=1e-7,
    )
    rendered = np.tensordot(basis, coefficients, axes=([2], [0]))
    rendered[..., :3] = np.clip(rendered[..., :3], (0.0, -0.6, -0.6), (1.0, 0.6, 0.6))
    rendered[..., 3] = np.clip(rendered[..., 3], 0.0, 1.0)
    return coefficients, rendered


def _least_squares_fit_only(
    basis: np.ndarray, signal: np.ndarray, fit: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit and evaluate only court pixels before an exact render is earned."""
    matrix = basis[fit]
    values = signal[fit]
    coefficients, _residuals, _rank, _singular = np.linalg.lstsq(
        matrix, values, rcond=1e-7,
    )
    predicted = matrix @ coefficients
    predicted[..., :3] = np.clip(
        predicted[..., :3], (0.0, -0.6, -0.6), (1.0, 0.6, 0.6),
    )
    predicted[..., 3] = np.clip(predicted[..., 3], 0.0, 1.0)
    return coefficients, predicted


def _render_basis(basis: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    rendered = np.tensordot(basis, coefficients, axes=([2], [0]))
    rendered[..., :3] = np.clip(
        rendered[..., :3], (0.0, -0.6, -0.6), (1.0, 0.6, 0.6),
    )
    rendered[..., 3] = np.clip(rendered[..., 3], 0.0, 1.0)
    return rendered


def _residual_values(observed: np.ndarray, rendered: np.ndarray) -> tuple[float, float]:
    delta = observed - rendered
    perceptual = np.sqrt(
        np.sum(np.square(delta[:, :3]), axis=1) + 0.35 * np.square(delta[:, 3])
    )
    return (
        float(np.sqrt(np.mean(np.square(perceptual)))),
        float(np.quantile(perceptual, 0.95)),
    )


def _residual(
    signal: np.ndarray, rendered: np.ndarray, fit: np.ndarray,
) -> tuple[float, float]:
    delta = signal[fit] - rendered[fit]
    perceptual = np.sqrt(
        np.sum(np.square(delta[:, :3]), axis=1) + 0.35 * np.square(delta[:, 3])
    )
    return float(np.sqrt(np.mean(np.square(perceptual)))), float(np.quantile(perceptual, 0.95))


def _endpoint_rgba(
    reir: RasterEvidenceIR, support: np.ndarray, coordinate: np.ndarray,
) -> tuple[str, str]:
    values = coordinate[support]
    rgba = reir.raster.straight_rgba[support]
    low = rgba[values <= np.quantile(values, 0.12)]
    high = rgba[values >= np.quantile(values, 0.88)]

    def encode(rows: np.ndarray) -> str:
        color = np.clip(np.mean(rows, axis=0) if len(rows) else np.zeros(4), 0, 1)
        return "#" + "".join(f"{int(round(value * 255)):02x}" for value in color)

    return encode(low), encode(high)


def _direction_alignment(reir: RasterEvidenceIR, fit: np.ndarray, direction: np.ndarray) -> float:
    light = reir.raster.oklab[..., 0]
    gx = cv2.Sobel(light, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(light, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.hypot(gx, gy)
    valid = fit & (magnitude > np.quantile(magnitude[fit], 0.35) if np.any(fit) else False)
    if not np.any(valid) or np.linalg.norm(direction) < 1e-9:
        return 0.0
    unit = direction / np.linalg.norm(direction)
    cosine = np.abs((gx[valid] * unit[0] + gy[valid] * unit[1]) / magnitude[valid])
    return float(np.mean(cosine))


def _model_fits(
    reir: RasterEvidenceIR, support: np.ndarray, fit: np.ndarray,
    signal: np.ndarray,
) -> list[tuple[str, tuple[tuple[str, float | int | str], ...], np.ndarray, float, float]]:
    xn, yn = _coordinates(support)
    ones = np.ones_like(xn)
    rows: list[tuple[str, tuple[tuple[str, float | int | str], ...], np.ndarray, float, float]] = []

    solid_basis = ones[..., None]
    solid_coef, solid = _least_squares(solid_basis, signal, fit)
    rows.append(("translucent_solid" if solid_coef[0, 3] < 0.985 else "solid", (
        ("oklab_l", float(solid_coef[0, 0])),
        ("oklab_a", float(solid_coef[0, 1])),
        ("oklab_b", float(solid_coef[0, 2])),
        ("alpha", float(solid_coef[0, 3])),
    ), solid, 0.0, 1.0))

    linear_basis = np.stack((ones, xn, yn), axis=-1)
    linear_coef, linear = _least_squares(linear_basis, signal, fit)
    gradients = linear_coef[1:3, :3]
    strength = np.linalg.norm(gradients, axis=0)
    direction = gradients[:, int(np.argmax(strength))]
    angle = float(math.degrees(math.atan2(float(direction[1]), float(direction[0]))) % 360.0)
    projection = xn * math.cos(math.radians(angle)) + yn * math.sin(math.radians(angle))
    start, end = _endpoint_rgba(reir, support, projection)
    alignment = _direction_alignment(reir, fit, direction)
    alpha_variable = float(np.ptp(linear[..., 3][support])) > 0.025
    rows.append(("translucent_gradient" if alpha_variable else "linear_gradient", (
        ("angle_deg", angle), ("start_rgba", start), ("end_rgba", end),
        ("alpha_gradient", int(alpha_variable)),
    ), linear, alignment, 1.0))

    ys, xs = np.nonzero(fit)
    center_x = float(np.mean(xs)); center_y = float(np.mean(ys))
    support_bbox = _bbox(support)
    support_width = max(1, support_bbox[2] - support_bbox[0])
    support_height = max(1, support_bbox[3] - support_bbox[1])
    grid_y, grid_x = np.indices(support.shape)
    observed_fit = signal[fit]
    best_radial = None
    for dx, dy in ((0.0, 0.0), (-0.22, 0.0), (0.22, 0.0),
                   (0.0, -0.22), (0.0, 0.22)):
        cx = center_x + dx * support_width
        cy = center_y + dy * support_height
        radius = np.hypot(
            (grid_x - cx) / max(1, support.shape[1]),
            (grid_y - cy) / max(1, support.shape[0]),
        )
        radial_basis = np.stack((ones, radius), axis=-1)
        radial_coef, radial_fit = _least_squares_fit_only(
            radial_basis, signal, fit,
        )
        rmse, _p95 = _residual_values(observed_fit, radial_fit)
        entry = (rmse, cx, cy, radius, radial_coef)
        if best_radial is None or entry[0] < best_radial[0]:
            best_radial = entry
    assert best_radial is not None
    _rmse, cx, cy, radius, radial_coef = best_radial
    radial = _render_basis(np.stack((ones, radius), axis=-1), radial_coef)
    start, end = _endpoint_rgba(reir, support, radius)
    radial_alpha = float(np.ptp(radial[..., 3][support])) > 0.025
    rows.append(("translucent_radial_gradient" if radial_alpha else "radial_gradient", (
        ("cx", cx), ("cy", cy), ("start_rgba", start), ("end_rgba", end),
        ("alpha_gradient", int(radial_alpha)),
    ), radial, 0.0, 1.0))

    # Flat chroma is the albedo; a quadratic lightness field is the smooth shade.
    shade_basis = np.stack((ones, xn, yn, xn * xn, xn * yn, yn * yn), axis=-1)
    shade_coef, shade = _least_squares(shade_basis, signal, fit)
    shade[..., 1] = float(np.mean(signal[..., 1][fit]))
    shade[..., 2] = float(np.mean(signal[..., 2][fit]))
    shade[..., 3] = float(np.mean(signal[..., 3][fit]))
    rows.append(("flat_albedo_smooth_shade", (
        ("albedo_a", float(shade[fit][0, 1])),
        ("albedo_b", float(shade[fit][0, 2])),
        ("shade_order", 2),
    ), shade, _direction_alignment(reir, fit, shade_coef[1:3, 0]), 1.0))
    return rows


def _source_rois(
    reir: RasterEvidenceIR, max_rois: int,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> list[tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]]:
    rows = []
    visible = reir.raster.straight_rgba[..., 3] > 0.01
    if int(visible.sum()) >= 12:
        light = reir.raster.oklab[..., 0]
        gx = cv2.Sobel(light, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(light, cv2.CV_32F, 0, 1, ksize=3)
        smooth = float(np.exp(-4.0 * np.quantile(np.hypot(gx, gy)[visible], 0.75)))
        rows.append((
            _freeze(visible, dtype=bool), (), 0.55 + 0.35 * smooth,
            ("visible-canvas-appearance-query",),
        ))
    for token in reir.proposal_tokens:
        if token.family not in {"gradient", "component", "shape", "topology"}:
            continue
        mask = decode_token_mask(token, (reir.height, reir.width))
        if mask is None or int(mask.sum()) < 12:
            continue
        if token.family == "gradient":
            rows.append((_freeze(mask, dtype=bool), (token.id,), token.score,
                         (token.provenance, "gradient-query")))
            continue
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), 8,
        )
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            width = int(stats[label, cv2.CC_STAT_WIDTH])
            height = int(stats[label, cv2.CC_STAT_HEIGHT])
            if 12 <= area <= int(0.85 * mask.size) and min(width, height) >= 3:
                rows.append((_freeze(labels == label, dtype=bool), (token.id,), token.score,
                             (token.provenance, f"component:{label}")))
    leaf_bits = descendant_leaf_bits(reir)
    for node in sorted(
        (row for row in reir.hierarchy.nodes if row.left is not None),
        key=lambda row: (-row.merge_level, row.area, row.id),
    )[:12]:
        mask = leaf_bits_mask(reir, leaf_bits[node.id])
        if 12 <= int(mask.sum()) <= int(0.85 * mask.size):
            rows.append((_freeze(mask, dtype=bool), (), float(1.0 - node.merge_level),
                         ("ucm-region-appearance", f"node:{node.id}")))
    for query in proposal_queries:
        if query.family not in {"appearance_model", "layer_relation"}:
            continue
        mask = query_support_mask(reir, query, minimum_pixels=12)
        if mask is None or int(mask.sum()) > int(0.90 * mask.size):
            continue
        from .proposal_net import query_head_prior_score
        query_score, head_provenance = query_head_prior_score(
            query, mask, expected_relation_groups=(
                (("same_group",), ("front_of",), ("behind",))
                if query.family == "layer_relation" else
                (("same_appearance",),)
            ),
        )
        rows.append((
            mask, (), query_score,
            ("ProposalNet-guided-before-appearance-fitting", query.id,
             *head_provenance, *query.provenance),
        ))
    unique = {}
    for row in rows:
        digest = mask_sha256(row[0])
        old = unique.get(digest)
        if old is None or row[2] > old[2]:
            unique[digest] = row
    return sorted(
        unique.values(), key=lambda row: (-row[2], -int(row[0].sum()), mask_sha256(row[0])),
    )[:max(1, min(48, int(max_rois)))]


def _records_for_source(
    reir: RasterEvidenceIR, support: np.ndarray, token_ids: tuple[int, ...],
    source_score: float, provenance: tuple[str, ...], max_models: int,
    signal: np.ndarray,
) -> tuple[list[AppearanceFitRecord], int]:
    fit = _fit_mask(reir, support)
    if int(fit.sum()) < 4:
        return [], 0
    models = _model_fits(reir, support, fit, signal)
    measured = []
    for model, parameters, rendered, alignment, continuity in models:
        rmse, p95 = _residual(signal, rendered, fit)
        measured.append((model, parameters, rendered, alignment, continuity, rmse, p95))
    solid_rmse = measured[0][5]
    accepted = []
    support_bbox = _bbox(support)
    support_topology = topology_signature(support)
    support_pixels = int(support.sum())
    for model, parameters, rendered, alignment, continuity, rmse, p95 in measured:
        improvement = float((solid_rmse - rmse) / max(1e-6, solid_rmse))
        complex_model = model not in {"solid", "translucent_solid"}
        if complex_model and not (
            improvement >= 0.035 or rmse <= 0.018
            or ("gradient" in model and alignment >= 0.72 and source_score >= 0.45)
        ):
            continue
        complexity = {
            "solid": 1, "translucent_solid": 2,
            "linear_gradient": 4, "translucent_gradient": 5,
            "radial_gradient": 5, "translucent_radial_gradient": 6,
            "flat_albedo_smooth_shade": 7,
        }[model]
        continuity = float(np.clip(1.0 - p95 / 0.18, 0.0, 1.0))
        score = float(np.clip(
            0.56 * math.exp(-rmse / 0.08) + 0.16 * math.exp(-p95 / 0.12)
            + 0.10 * max(0.0, improvement) + 0.07 * alignment
            + 0.06 * continuity + 0.05 * source_score - 0.009 * complexity,
            0.0, 1.5,
        ))
        kind = MacroKind.SOLID_REGION if model in {"solid", "translucent_solid"} else MacroKind.GRADIENT
        candidate = candidate_from_support(
            reir, family="gradient" if kind is MacroKind.GRADIENT else "component",
            mask=support, roi_xyxy=support_bbox, evidence_token_ids=token_ids,
            score=score, kind=kind, components=support_topology[0],
            holes=support_topology[1], prefix=f"appearance-{model}",
            provenance=("phase5-appearance-model", f"model:{model}", *provenance),
        )
        if candidate is None:
            continue
        candidate = replace(
            candidate, program=SceneProgram(f"Appearance/{model}", parameters),
            alpha_bounds=(
                float(np.min(rendered[..., 3][support])),
                float(np.max(rendered[..., 3][support])),
            ),
            continuous_params=tuple(
                (name, float(value)) for name, value in parameters
                if isinstance(value, (float, int))
            ),
            covariance=tuple(max(1e-4, rmse * rmse) for _ in parameters),
            certificates=replace(candidate.certificates, notes=(
                *candidate.certificates.notes, "edge-mixture-excluded",
                f"residual_rmse={rmse:.8f}", f"residual_p95={p95:.8f}",
                f"solid_improvement={improvement:.8f}",
                f"directional_alignment={alignment:.8f}",
                "native-lattice-appearance-rerender",
            )),
            prerequisite_claims=(
                "region-support-evidence", "edge-mixture-excluded",
                "continuity-evidence", "model-complexity-penalized",
                "palette-late-constraint-not-early-quantized",
                "layer-interaction-explicit-alpha",
            ),
            resource_estimate=ResourceEstimate(
                fitting_ms=0.10 + 0.025 * complexity,
                render_pixels=support_pixels, memory_bytes=1024,
                solver_variables=complexity,
            ),
        )
        candidate = rekey_draft_candidate(
            candidate, prefix=f"appearance-{model}",
        )
        accepted.append(AppearanceFitRecord(
            candidate=candidate, model=model,
            support_mask=_freeze(support, dtype=bool),
            fit_mask=_freeze(fit, dtype=bool),
            rendered_oklab_alpha=_freeze(rendered, dtype=np.float32),
            parameters=parameters, residual_rmse=rmse, residual_p95=p95,
            improvement_over_solid=improvement,
            directional_alignment=alignment, continuity=continuity,
            source_token_ids=token_ids,
        ))
    accepted.sort(key=lambda row: (
        -row.candidate.score_bounds.lower, row.residual_rmse, row.model,
    ))
    limit = max(1, min(7, int(max_models)))
    return accepted[:limit], max(0, len(accepted) - limit)


def _linear_premultiplied_to_oklab_alpha(values: np.ndarray) -> np.ndarray:
    source = np.asarray(values, np.float32)
    alpha = np.clip(source[..., 3], 0.0, 1.0)
    straight = np.zeros_like(source[..., :3])
    np.divide(
        source[..., :3], np.maximum(alpha[..., None], 1e-8),
        out=straight, where=alpha[..., None] > 1e-8,
    )
    result = np.dstack((_linear_rgb_to_oklab(
        np.clip(straight, 0.0, 1.0),
    ), alpha)).astype(np.float32, copy=False)
    return result


def _ordered_translucent_stack_records(
    reir: RasterEvidenceIR,
    sources: Iterable[tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]],
    *, max_records: int = 8,
) -> tuple[AppearanceFitRecord, ...]:
    """Fit bounded two/three-layer Porter-Duff stacks from evidence.

    A stack is one global-extractor column, so exact visible ownership remains
    a set partition while the column owns at most three ordered paint
    contributions.  Each layer colour/alpha is identified only from pixels
    exclusive to that layer; every multiply-covered pixel is held out as the
    physical composition check.  A three-layer proposal additionally requires
    a real triple-overlap witness.  This prevents arbitrary alpha
    factorizations from entering CMIR.
    """
    source_rows = []
    seen: set[str] = set()
    signal = np.asarray(reir.raster.linear_premultiplied_rgba, np.float32)
    for support, token_ids, source_score, provenance in sources:
        digest = mask_sha256(support)
        if digest in seen or int(np.sum(support)) < 12:
            continue
        seen.add(digest)
        support_alpha = signal[..., 3][support]
        # Cheap translucency screen before the O(N^2) overlap stage.  Opaque
        # artwork pays no stack-pair allocations at all.
        median_alpha = float(np.median(support_alpha))
        translucent_fraction = float(np.mean(
            (support_alpha >= 0.03) & (support_alpha < 0.985)
        ))
        if not 0.03 <= median_alpha < 0.985 or translucent_fraction < 0.35:
            continue
        source_rows.append((support, token_ids, source_score, provenance, digest))
        if len(source_rows) >= 12:
            break
    candidates: list[AppearanceFitRecord] = []
    # Pair search retains the previous bound.  Triple search is deliberately
    # tighter: C(8, 3) * 3! = 336 cheap order checks at most per ROI bundle.
    for layer_count, bounded_rows in ((2, source_rows), (3, source_rows[:8])):
        for source_group in combinations(bounded_rows, layer_count):
            masks = tuple(row[0] for row in source_group)
            union = np.logical_or.reduce(masks)
            membership_count = np.sum(np.stack(masks, axis=0), axis=0)
            held_out = membership_count >= 2
            triple_overlap = membership_count == 3
            if int(held_out.sum()) < 6:
                continue
            if layer_count == 3 and int(triple_overlap.sum()) < 6:
                continue
            exclusive_masks = tuple(
                mask & (membership_count == 1) for mask in masks
            )
            if min(int(mask.sum()) for mask in exclusive_masks) < 6:
                continue
            paints = tuple(
                np.median(signal[exclusive], axis=0).astype(np.float32)
                for exclusive in exclusive_masks
            )
            if any(
                not 0.03 <= float(paint[3]) < 0.985 for paint in paints
            ):
                continue
            observed = signal[union]
            constant = np.median(observed, axis=0)
            constant_error = np.linalg.norm(observed - constant, axis=1)
            constant_rmse = float(np.sqrt(np.mean(constant_error ** 2)))
            token_ids = tuple(sorted(set(
                token_id
                for row in source_group for token_id in row[1]
            )))
            source_score = min(row[2] for row in source_group)
            source_provenance = tuple(
                item for row in source_group for item in row[3]
            )
            digests = tuple(row[4] for row in source_group)
            for order in permutations(range(layer_count)):
                ordered = tuple(
                    (masks[index], paints[index], digests[index])
                    for index in order
                )
                predicted_values = np.zeros((int(union.sum()), 4), np.float32)
                for mask, paint, _digest in ordered:
                    active = mask[union]
                    alpha = float(paint[3])
                    predicted_values[active, :3] = (
                        paint[:3]
                        + predicted_values[active, :3] * (1.0 - alpha)
                    )
                    predicted_values[active, 3] = (
                        alpha
                        + predicted_values[active, 3] * (1.0 - alpha)
                    )
                error = np.linalg.norm(predicted_values - observed, axis=1)
                rmse = float(np.sqrt(np.mean(error ** 2)))
                p95 = float(np.quantile(error, 0.95))
                improvement = float(
                    (constant_rmse - rmse) / max(1e-6, constant_rmse)
                )
                held_out_in_union = held_out[union]
                held_out_error = float(np.sqrt(np.mean(np.linalg.norm(
                    predicted_values[held_out_in_union] - signal[held_out],
                    axis=1,
                ) ** 2)))
                triple_error = held_out_error
                if layer_count == 3:
                    triple_in_union = triple_overlap[union]
                    triple_error = float(np.sqrt(np.mean(np.linalg.norm(
                        predicted_values[triple_in_union]
                        - signal[triple_overlap], axis=1,
                    ) ** 2)))
                # The overlap, not the exclusive fitting pixels, must prove
                # the source-over order.  A weak or wrong order stays out.
                if (
                    improvement < 0.10 or rmse > 0.06
                    or held_out_error > 0.055 or triple_error > 0.055
                ):
                    continue
                support_bbox = _bbox(union)
                components, holes = topology_signature(union)
                score = float(np.clip(
                    0.70 * math.exp(-rmse / 0.045)
                    + 0.18 * max(0.0, improvement)
                    + 0.12 * source_score
                    - 0.015 * (layer_count - 2),
                    0.0, 1.5,
                ))
                position_names = (
                    ("back", "front") if layer_count == 2
                    else ("back", "middle", "front")
                )
                parameter_rows: list[tuple[str, float | int | str]] = [
                    ("layer_count", layer_count),
                    ("composition", "porter-duff-source-over"),
                ]
                for position, (_mask, paint, digest) in zip(
                    position_names, ordered,
                ):
                    parameter_rows.extend((
                        (f"{position}_support", digest),
                        (f"{position}_rgba", ",".join(
                            f"{float(value):.9g}" for value in paint
                        )),
                    ))
                parameters = tuple(parameter_rows)
                candidate = candidate_from_support(
                    reir, family="gradient", mask=union,
                    roi_xyxy=support_bbox,
                    evidence_token_ids=token_ids, score=score,
                    kind=MacroKind.GRADIENT,
                    components=components, holes=holes,
                    prefix="appearance-ordered-translucent-stack",
                    provenance=(
                        "phase5-bounded-ordered-translucent-stack",
                        f"ordered-contribution-count={layer_count}",
                        "exclusive-pixels-fit-overlap-held-out",
                        *(("triple-overlap-held-out",)
                          if layer_count == 3 else ()),
                        *source_provenance,
                    ),
                )
                if candidate is None:
                    continue
                alpha_values = predicted_values[..., 3]
                certificate_notes = [
                    *candidate.certificates.notes,
                    "edge-mixture-excluded",
                    f"residual_rmse={rmse:.8f}",
                    f"residual_p95={p95:.8f}",
                    f"solid_improvement={improvement:.8f}",
                    f"overlap_rmse={held_out_error:.8f}",
                ]
                if layer_count == 3:
                    certificate_notes.append(
                        f"triple_overlap_rmse={triple_error:.8f}"
                    )
                certificate_notes.extend((
                    "native-lattice-appearance-rerender",
                    f"ordered-contribution-count={layer_count}",
                ))
                candidate = replace(
                    candidate,
                    program=SceneProgram(
                        "Appearance/ordered_translucent_stack", parameters,
                    ),
                    alpha_bounds=(
                        float(np.min(alpha_values)), float(np.max(alpha_values)),
                    ),
                    continuous_params=tuple(
                        (f"{position}_alpha", float(layer[1][3]))
                        for position, layer in zip(position_names, ordered)
                    ),
                    covariance=(max(1e-4, rmse * rmse),) * layer_count,
                    certificates=replace(
                        candidate.certificates,
                        notes=tuple(certificate_notes),
                    ),
                    prerequisite_claims=(
                        "region-support-evidence", "edge-mixture-excluded",
                        "continuity-evidence", "model-complexity-penalized",
                        "palette-late-constraint-not-early-quantized",
                        "layer-interaction-explicit-alpha",
                    ),
                    resource_estimate=ResourceEstimate(
                        fitting_ms=0.20 + 0.075 * layer_count,
                        render_pixels=int(union.sum()), memory_bytes=1024 * layer_count,
                        solver_variables=4 * layer_count,
                    ),
                )
                candidate = rekey_draft_candidate(
                    candidate, prefix="appearance-ordered-translucent-stack",
                )
                predicted = np.zeros_like(signal)
                predicted[union] = predicted_values
                layers = tuple(
                    OrderedTranslucentLayer(
                        support_mask=_freeze(mask, dtype=bool),
                        linear_premultiplied_rgba=tuple(float(v) for v in paint),
                        support_digest=digest,
                    )
                    for mask, paint, digest in ordered
                )
                candidates.append(AppearanceFitRecord(
                    candidate=candidate,
                    model="ordered_translucent_stack",
                    support_mask=_freeze(union, dtype=bool),
                    fit_mask=_freeze(union, dtype=bool),
                    rendered_oklab_alpha=_freeze(
                        _linear_premultiplied_to_oklab_alpha(predicted),
                        dtype=np.float32,
                    ),
                    parameters=parameters,
                    residual_rmse=rmse, residual_p95=p95,
                    improvement_over_solid=improvement,
                    directional_alignment=1.0,
                    continuity=float(np.clip(1.0 - p95 / 0.18, 0.0, 1.0)),
                    source_token_ids=token_ids,
                    stack_layers=layers,
                ))
    candidates.sort(key=lambda row: (
        row.residual_rmse, -row.candidate.score_bounds.lower, row.candidate.id,
    ))
    return tuple(candidates[:max(0, int(max_records))])


def generate_appearance_macros(
    reir: RasterEvidenceIR, *, max_rois: int = 32, max_models_per_roi: int = 4,
    validate_reir: bool = True,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> AppearanceMacroSet:
    if validate_reir:
        reir.validate()
    sources = _source_rois(reir, max_rois, proposal_queries)
    signal = np.dstack((
        reir.raster.oklab, reir.raster.straight_rgba[..., 3],
    ))
    records = []
    pruned = 0
    for support, token_ids, source_score, provenance in sources:
        fitted, removed = _records_for_source(
            reir, support, token_ids, source_score, provenance,
            max_models_per_roi, signal,
        )
        records.extend(fitted); pruned += removed
    stack_records = _ordered_translucent_stack_records(
        reir, sources, max_records=max(2, min(8, max_rois // 4)),
    )
    records.extend(stack_records)
    unique: dict[tuple[str, str], AppearanceFitRecord] = {}
    for row in records:
        key = (row.model, mask_sha256(row.support_mask))
        old = unique.get(key)
        if old is None or row.candidate.score_bounds.lower > old.candidate.score_bounds.lower:
            unique[key] = row
    record_budget = max(1, int(max_rois) * max(1, int(max_models_per_roi)))
    ranked = sorted(unique.values(), key=lambda row: (
        -row.candidate.score_bounds.lower, row.residual_rmse,
        row.candidate.id,
    ))
    pruned += max(0, len(ranked) - record_budget)
    final = tuple(sorted(
        ranked[:record_budget],
        key=lambda row: (row.candidate.roi_xyxy, row.model, row.candidate.id),
    ))
    for row in final:
        row.validate(reir)
    return AppearanceMacroSet(
        records=final, rois_considered=len(sources), candidates_pruned=pruned,
        provenance=(
            "color-residual-after-edge-mixture",
            "phase5-appearance-generator/v1", "late-palette-constraint",
        ),
    )
