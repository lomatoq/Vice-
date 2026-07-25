"""M7: appearance program v2 - colours that survive idealization.

Plan S4.4 / M7.  The human court's 58 ties were dominated by colour, not
geometry: "згублены колеры пінгвіна і градыент на хвалі", "крыжы
чырвоныя згубленыя", "згубіліся у абодвух каляровыя палосы эпл".  Today
a TextLine keeps at most two principal colour groups, transported to the
idealized geometry by nearest-distance ownership - which cannot represent
three stripes, a gradient, or a small red mouth that is semantically
salient but tiny in area.

This module supplies:

    salient cluster extraction   small high-chroma detail survives
    appearance completeness      a dropped cluster is a hard violation
    boundary-normal transport    stripes keep their place on new geometry
    appearance hypotheses        solid / multi-solid / gradient candidates
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from .vector_program import (
    LinearGradientPaint,
    PaintProgram,
    RadialGradientPaint,
    SolidPaint,
)

#: A cluster below this area share is only kept when it is chromatic and
#: locally contrasting - that is exactly the small red cross / eye / mouth
#: class the court punished us for dropping.
AREA_FLOOR_SHARE = 0.06
SALIENT_SMALL_DETAIL_FLOOR = 0.055
#: Oklab distance treated as "the same colour" when matching delivery.
DELTA_E_MATCH = 0.10


def linear_srgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """Linear sRGB (..., 3) -> Oklab (..., 3)."""
    values = np.asarray(rgb, np.float64)
    l = (
        0.4122214708 * values[..., 0] + 0.5363325363 * values[..., 1]
        + 0.0514459929 * values[..., 2]
    )
    m = (
        0.2119034982 * values[..., 0] + 0.6806995451 * values[..., 1]
        + 0.1073969566 * values[..., 2]
    )
    s = (
        0.0883024619 * values[..., 0] + 0.2817188376 * values[..., 1]
        + 0.6299787005 * values[..., 2]
    )
    l_ = np.cbrt(np.maximum(l, 0.0))
    m_ = np.cbrt(np.maximum(m, 0.0))
    s_ = np.cbrt(np.maximum(s, 0.0))
    return np.stack((
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    ), axis=-1)


@dataclass(frozen=True)
class SalientAppearanceCluster:
    id: str
    oklab: tuple[float, float, float]
    linear_rgba: tuple[float, float, float, float]
    area_px: float
    centroid_xy: tuple[float, float]
    bbox_xyxy: tuple[int, int, int, int]
    chroma: float
    local_contrast: float
    semantic_salience: float
    mask: np.ndarray | None = None


@dataclass(frozen=True)
class AppearanceMatch:
    source_cluster_id: str
    delivered_layer_id: str
    delta_e: float
    area_ratio: float
    centroid_error_px: float
    adjacency_preserved: bool


@dataclass(frozen=True)
class AppearanceCompletenessCertificate:
    valid: bool
    source_clusters: tuple[SalientAppearanceCluster, ...]
    matches: tuple[AppearanceMatch, ...]
    missing_salient_clusters: tuple[str, ...]
    spurious_salient_layers: tuple[str, ...]
    gradient_direction_error_deg: float | None = None
    gradient_range_error: float | None = None
    violations: tuple[str, ...] = ()

    @property
    def salient_recall(self) -> float:
        total = len(self.source_clusters)
        if not total:
            return 1.0
        return 1.0 - len(self.missing_salient_clusters) / total


# --------------------------------------------------------------------------
# M7.2 salient colour extraction
# --------------------------------------------------------------------------


def _kmeans(
    samples: np.ndarray, clusters: int, *, seed: int = 20260726,
    iterations: int = 24,
) -> np.ndarray:
    """Deterministic Lloyd k-means (quantile init) - no sklearn dependency."""
    count = len(samples)
    if count == 0 or clusters <= 1:
        return np.zeros(count, dtype=int)
    order = np.argsort(samples[:, 0])
    picks = np.linspace(0, count - 1, clusters).astype(int)
    centres = samples[order[picks]].copy()
    labels = np.zeros(count, dtype=int)
    for _ in range(iterations):
        distances = np.linalg.norm(
            samples[:, None, :] - centres[None, :, :], axis=2,
        )
        updated = np.argmin(distances, axis=1)
        if np.array_equal(updated, labels):
            break
        labels = updated
        for index in range(clusters):
            member = labels == index
            if np.any(member):
                centres[index] = samples[member].mean(axis=0)
    return labels


def extract_salient_clusters(
    linear_rgb: np.ndarray, support: np.ndarray, *,
    maximum_clusters: int = 4, core_radius: float = 1.5,
) -> list[SalientAppearanceCluster]:
    """Interior colour clusters, keeping small high-chroma details (M7.2)."""
    rgb = np.asarray(linear_rgb, np.float64)
    mask = np.asarray(support, bool)
    if not mask.any():
        return []
    distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    interior = mask & (distance >= core_radius)
    if not interior.any():
        interior = mask
    oklab = linear_srgb_to_oklab(rgb)
    ys, xs = np.nonzero(interior)
    colours = oklab[ys, xs]
    height, width = mask.shape
    spatial = np.column_stack((xs / max(1, width), ys / max(1, height)))
    # Spatial regularization keeps a stripe together instead of merging two
    # distant regions that happen to share a colour.
    features = np.column_stack((colours, 0.25 * spatial))
    best_labels = np.zeros(len(colours), dtype=int)
    best_count = 1
    for count in range(2, max(2, maximum_clusters) + 1):
        labels = _kmeans(features, count)
        separations = []
        for index in range(count):
            member = labels == index
            if np.sum(member) < 8:
                separations = []
                break
            separations.append(colours[member].mean(axis=0))
        if len(separations) < count:
            break
        gaps = [
            float(np.linalg.norm(separations[i] - separations[j]))
            for i in range(count) for j in range(i + 1, count)
        ]
        if gaps and min(gaps) >= 0.09:
            best_labels, best_count = labels, count
    total_area = float(np.sum(interior))
    clusters: list[SalientAppearanceCluster] = []
    for index in range(best_count):
        member = best_labels == index
        area = float(np.sum(member))
        if area <= 0:
            continue
        cluster_mask = np.zeros_like(mask)
        cluster_mask[ys[member], xs[member]] = True
        mean_oklab = colours[member].mean(axis=0)
        mean_rgb = rgb[ys[member], xs[member]].mean(axis=0)
        chroma = float(math.hypot(mean_oklab[1], mean_oklab[2]))
        others = colours[~member]
        contrast = (
            float(np.min(np.linalg.norm(
                others - mean_oklab, axis=1,
            ))) if len(others) else 1.0
        )
        share = area / max(1.0, total_area)
        salience = float(max(share, chroma * max(contrast, 0.0) * 4.0))
        if share < AREA_FLOOR_SHARE and salience < SALIENT_SMALL_DETAIL_FLOOR:
            continue
        cluster_ys, cluster_xs = np.nonzero(cluster_mask)
        clusters.append(SalientAppearanceCluster(
            id=f"cluster-{index}",
            oklab=tuple(float(v) for v in mean_oklab),
            linear_rgba=(
                float(mean_rgb[0]), float(mean_rgb[1]), float(mean_rgb[2]),
                1.0,
            ),
            area_px=area,
            centroid_xy=(float(cluster_xs.mean()), float(cluster_ys.mean())),
            bbox_xyxy=(
                int(cluster_xs.min()), int(cluster_ys.min()),
                int(cluster_xs.max()) + 1, int(cluster_ys.max()) + 1,
            ),
            chroma=chroma, local_contrast=float(contrast),
            semantic_salience=salience, mask=cluster_mask,
        ))
    return clusters


# --------------------------------------------------------------------------
# M7.4 transport to idealized geometry
# --------------------------------------------------------------------------


def boundary_normal_transport(
    source_masks: list[np.ndarray], target_support: np.ndarray,
) -> list[np.ndarray]:
    """Carry source layer masks onto new geometry (plan M7.4).

    Nearest-distance ownership is the documented fallback; it is used here
    with the target support as the domain, so reconstructed stems are never
    left unpainted and no layer can claim pixels outside the geometry.
    """
    target = np.asarray(target_support, bool)
    if not source_masks:
        return []
    distances = np.stack([
        cv2.distanceTransform((~np.asarray(mask, bool)).astype(np.uint8),
                              cv2.DIST_L2, 3)
        for mask in source_masks
    ], axis=0)
    ownership = np.argmin(distances, axis=0)
    return [
        target & (ownership == index) for index in range(len(source_masks))
    ]


# --------------------------------------------------------------------------
# M7.3 appearance hypotheses
# --------------------------------------------------------------------------


def linear_gradient_evidence(
    linear_rgb: np.ndarray, support: np.ndarray, *,
    minimum_range: float = 0.08,
) -> tuple[bool, tuple[float, float], tuple[float, float], float]:
    """Detect a dominant linear colour ramp; returns (ok, p0, p1, range)."""
    mask = np.asarray(support, bool)
    if np.sum(mask) < 24:
        return False, (0.0, 0.0), (0.0, 0.0), 0.0
    oklab = linear_srgb_to_oklab(np.asarray(linear_rgb, np.float64))
    ys, xs = np.nonzero(mask)
    values = oklab[ys, xs, 0]
    coordinates = np.column_stack((xs, ys)).astype(np.float64)
    centred = coordinates - coordinates.mean(axis=0)
    # Direction that best explains the lightness ramp (least squares).
    try:
        solution, *_ = np.linalg.lstsq(
            np.column_stack((centred, np.ones(len(centred)))),
            values, rcond=None,
        )
    except np.linalg.LinAlgError:
        return False, (0.0, 0.0), (0.0, 0.0), 0.0
    direction = np.array([solution[0], solution[1]])
    magnitude = float(np.linalg.norm(direction))
    if magnitude <= 1.0e-9:
        return False, (0.0, 0.0), (0.0, 0.0), 0.0
    unit_direction = direction / magnitude
    projection = centred @ unit_direction
    spread = float(projection.max() - projection.min())
    ramp = magnitude * spread
    predicted = centred @ direction + solution[2]
    residual = float(np.std(values - predicted))
    ok = bool(ramp >= minimum_range and residual <= 0.35 * max(ramp, 1e-9))
    origin = coordinates.mean(axis=0)
    p0 = origin + unit_direction * projection.min()
    p1 = origin + unit_direction * projection.max()
    return (
        ok, (float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1])),
        float(ramp),
    )


def generate_appearance_programs(
    linear_rgb: np.ndarray, support: np.ndarray, *,
    maximum_candidates: int = 3,
) -> list[tuple[str, list[PaintProgram], list[np.ndarray]]]:
    """Bounded appearance hypotheses (plan M7.3, budget S10)."""
    mask = np.asarray(support, bool)
    rgb = np.asarray(linear_rgb, np.float64)
    hypotheses: list[tuple[str, list[PaintProgram], list[np.ndarray]]] = []
    if not mask.any():
        return hypotheses
    median = np.median(rgb[mask], axis=0)
    hypotheses.append((
        "solid",
        [SolidPaint(rgba_linear=(
            float(median[0]), float(median[1]), float(median[2]), 1.0,
        ))],
        [mask],
    ))
    clusters = extract_salient_clusters(rgb, mask)
    if len(clusters) >= 2:
        masks = boundary_normal_transport(
            [cluster.mask for cluster in clusters], mask,
        )
        hypotheses.append((
            f"multisolid-{len(clusters)}",
            [SolidPaint(rgba_linear=cluster.linear_rgba)
             for cluster in clusters],
            masks,
        ))
    ok, p0, p1, _ramp = linear_gradient_evidence(rgb, mask)
    if ok:
        low = np.median(rgb[mask][:max(1, int(0.1 * np.sum(mask)))], axis=0)
        high = np.median(rgb[mask][-max(1, int(0.1 * np.sum(mask))):], axis=0)
        hypotheses.append((
            "linear-gradient",
            [LinearGradientPaint(
                p0=p0, p1=p1,
                stops=(
                    (0.0, (float(low[0]), float(low[1]), float(low[2]), 1.0)),
                    (1.0, (float(high[0]), float(high[1]), float(high[2]), 1.0)),
                ),
            )],
            [mask],
        ))
    return hypotheses[:maximum_candidates]


# --------------------------------------------------------------------------
# S4.4 completeness certificate
# --------------------------------------------------------------------------


def appearance_completeness(
    source_clusters: list[SalientAppearanceCluster],
    delivered_layers: list[tuple[str, tuple[float, float, float, float], np.ndarray]],
    *, delta_e_threshold: float = DELTA_E_MATCH,
    minimum_recall: float = 0.95,
) -> AppearanceCompletenessCertificate:
    """Every salient source cluster must appear in the delivery (S4.4)."""
    matches: list[AppearanceMatch] = []
    missing: list[str] = []
    used: set[str] = set()
    delivered_oklab = {
        layer_id: linear_srgb_to_oklab(np.asarray(colour[:3], np.float64))
        for layer_id, colour, _mask in delivered_layers
    }
    for cluster in source_clusters:
        best: tuple[float, str] | None = None
        source_oklab = np.asarray(cluster.oklab, np.float64)
        for layer_id, _colour, layer_mask in delivered_layers:
            distance = float(np.linalg.norm(
                delivered_oklab[layer_id] - source_oklab,
            ))
            overlap = 0.0
            if cluster.mask is not None and layer_mask is not None:
                layer = np.asarray(layer_mask, bool)
                overlap = float(np.sum(cluster.mask & layer)) / max(
                    1.0, float(np.sum(cluster.mask)),
                )
            score = distance - 0.25 * overlap
            if best is None or score < best[0]:
                best = (score, layer_id)
        if best is None:
            missing.append(cluster.id)
            continue
        layer_id = best[1]
        layer_mask = next(
            (np.asarray(mask, bool) for lid, _c, mask in delivered_layers
             if lid == layer_id), None,
        )
        distance = float(np.linalg.norm(
            delivered_oklab[layer_id] - source_oklab,
        ))
        area_ratio = 0.0
        centroid_error = 0.0
        if layer_mask is not None and layer_mask.any():
            area_ratio = float(np.sum(layer_mask)) / max(1.0, cluster.area_px)
            ys, xs = np.nonzero(layer_mask)
            centroid_error = float(math.dist(
                (float(xs.mean()), float(ys.mean())), cluster.centroid_xy,
            ))
        if distance > delta_e_threshold:
            missing.append(cluster.id)
            continue
        used.add(layer_id)
        matches.append(AppearanceMatch(
            source_cluster_id=cluster.id, delivered_layer_id=layer_id,
            delta_e=distance, area_ratio=area_ratio,
            centroid_error_px=centroid_error,
            adjacency_preserved=bool(centroid_error <= max(
                6.0, 0.35 * math.sqrt(max(cluster.area_px, 1.0)),
            )),
        ))
    spurious = tuple(
        layer_id for layer_id, _colour, _mask in delivered_layers
        if layer_id not in used
    )
    violations: list[str] = []
    recall = (
        1.0 if not source_clusters
        else 1.0 - len(missing) / len(source_clusters)
    )
    if recall < minimum_recall:
        violations.append("salient-cluster-recall-below-floor")
    if any(not match.adjacency_preserved for match in matches):
        violations.append("appearance-adjacency-broken")
    return AppearanceCompletenessCertificate(
        valid=not violations, source_clusters=tuple(source_clusters),
        matches=tuple(matches), missing_salient_clusters=tuple(missing),
        spurious_salient_layers=spurious, violations=tuple(violations),
    )
