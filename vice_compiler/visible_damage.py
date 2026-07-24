"""Exact-render structural damage meters used by the shipping court.

These are deliberately aligned with the blind ``benchmark_vai`` meters.  A
whole-image average can improve while one counter, terminal, or short boundary
is destroyed; the measurements below keep those failures visible to the
transactional runtime gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class VisibleDamageMetrics:
    catastrophic_locus_count: int
    catastrophic_locus_rate: float
    worst_locus_severity: float
    boundary_cvar10: float
    boundary_p99: float
    detail_de_cvar10: float
    persistent_beta0_error: float
    persistent_beta1_error: float
    persistent_components_lost: float
    persistent_holes_lost: float
    persistent_holes_gained: float
    any_counter_failure: bool


def _background(image: np.ndarray) -> np.ndarray:
    border = np.concatenate((image[0], image[-1], image[:, 0], image[:, -1]))
    return np.median(border, axis=0)


def _delta_e_map(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """CIEDE2000 with the benchmark's deterministic Lab fallback."""
    first_u8 = np.clip(first, 0, 255).astype(np.uint8)
    second_u8 = np.clip(second, 0, 255).astype(np.uint8)
    try:
        from skimage.color import deltaE_ciede2000, rgb2lab

        return np.asarray(
            deltaE_ciede2000(rgb2lab(first_u8), rgb2lab(second_u8)),
            np.float32,
        )
    except Exception:
        first_lab = cv2.cvtColor(first_u8, cv2.COLOR_RGB2LAB).astype(np.float32)
        second_lab = cv2.cvtColor(second_u8, cv2.COLOR_RGB2LAB).astype(np.float32)
        return np.linalg.norm(first_lab - second_lab, axis=2)


def _ink_from_background(
    image: np.ndarray, background: np.ndarray, threshold: float,
) -> np.ndarray:
    rgb = np.clip(image, 0, 255).astype(np.uint8)
    bg = np.broadcast_to(np.asarray(background, np.uint8), rgb.shape)
    return _delta_e_map(rgb, bg) >= float(threshold)


def _clean_ink(mask: np.ndarray, area_floor: int) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        np.asarray(mask, np.uint8), connectivity=8,
    )
    clean = np.zeros(mask.shape, np.uint8)
    for component in range(1, count):
        if int(stats[component, cv2.CC_STAT_AREA]) >= int(area_floor):
            clean[labels == component] = 1
    return clean.astype(bool)


def _component_holes(mask: np.ndarray) -> int:
    contours, hierarchy = cv2.findContours(
        np.asarray(mask, np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None or not contours:
        return 0
    return int(np.count_nonzero(hierarchy[0, :, 3] >= 0))


def _betti_numbers(mask: np.ndarray, area_floor: int) -> tuple[int, int]:
    clean = _clean_ink(mask, area_floor)
    count, _ = cv2.connectedComponents(clean.astype(np.uint8), connectivity=8)
    return max(0, int(count) - 1), _component_holes(clean)


def _cvar(values: np.ndarray | list[float], fraction: float = 0.10) -> float:
    samples = np.asarray(values, np.float64).reshape(-1)
    samples = samples[np.isfinite(samples)]
    if not len(samples):
        return 0.0
    count = max(1, int(math.ceil(len(samples) * float(fraction))))
    return float(np.mean(np.partition(samples, len(samples) - count)[-count:]))


def visible_damage_metrics(
    rendered_rgb: np.ndarray, source_rgb: np.ndarray,
) -> VisibleDamageMetrics:
    """Measure persistent topology and worst-locus boundary damage.

    Both arrays are opaque RGB in source-native resolution.  The source border
    defines the immutable background for both images, matching the external
    blind benchmark rather than letting a candidate move its own goalposts.
    """
    rendered = np.clip(rendered_rgb, 0, 255).astype(np.uint8)
    source = np.clip(source_rgb, 0, 255).astype(np.uint8)
    if rendered.shape != source.shape or rendered.ndim != 3 or rendered.shape[2] != 3:
        raise ValueError("visible damage inputs must be same-sized RGB arrays")

    background = _background(source)
    levels = (2.3, 4.6, 9.2, 18.4)
    area_floor = max(2, int(round(source.shape[0] * source.shape[1] / 32768.0)))
    source_curve: list[tuple[int, int]] = []
    render_curve: list[tuple[int, int]] = []
    for level in levels:
        source_curve.append(_betti_numbers(
            _ink_from_background(source, background, level), area_floor,
        ))
        render_curve.append(_betti_numbers(
            _ink_from_background(rendered, background, level), area_floor,
        ))
    beta0_delta = [abs(a[0] - b[0]) for a, b in zip(source_curve, render_curve)]
    beta1_delta = [abs(a[1] - b[1]) for a, b in zip(source_curve, render_curve)]
    lost_components = [max(0, a[0] - b[0]) for a, b in zip(source_curve, render_curve)]
    lost_holes = [max(0, a[1] - b[1]) for a, b in zip(source_curve, render_curve)]
    gained_holes = [max(0, b[1] - a[1]) for a, b in zip(source_curve, render_curve)]

    source_ink = _clean_ink(
        _ink_from_background(source, background, 4.6), 2,
    )
    render_ink = _clean_ink(
        _ink_from_background(rendered, background, 4.6), 2,
    )
    kernel = np.ones((3, 3), np.uint8)
    source_edge = source_ink & ~cv2.erode(
        source_ink.astype(np.uint8), kernel, iterations=1,
    ).astype(bool)
    render_edge = render_ink & ~cv2.erode(
        render_ink.astype(np.uint8), kernel, iterations=1,
    ).astype(bool)
    distances: list[np.ndarray] = []
    damage_map = np.zeros(source_ink.shape, np.float32)
    if source_edge.any() and render_edge.any():
        to_render = cv2.distanceTransform(
            (~render_edge).astype(np.uint8), cv2.DIST_L2, 5,
        )
        to_source = cv2.distanceTransform(
            (~source_edge).astype(np.uint8), cv2.DIST_L2, 5,
        )
        distances.extend((to_render[source_edge], to_source[render_edge]))
        damage_map[source_edge] = to_render[source_edge]
        damage_map[render_edge] = np.maximum(
            damage_map[render_edge], to_source[render_edge],
        )
    elif source_edge.any() or render_edge.any():
        diagonal = float(math.hypot(*source_ink.shape))
        edge = source_edge | render_edge
        damage_map[edge] = diagonal
        distances.append(np.full(int(edge.sum()), diagonal, np.float32))
    boundary_distances = (
        np.concatenate(distances) if distances else np.zeros(1, np.float32)
    )
    catastrophic = damage_map > 1.0
    locus_count = 0
    worst_locus = 0.0
    if catastrophic.any():
        grown = cv2.dilate(catastrophic.astype(np.uint8), kernel, iterations=1)
        count, labels = cv2.connectedComponents(grown, connectivity=8)
        locus_count = max(0, int(count) - 1)
        for label in range(1, count):
            support = labels == label
            values = damage_map[support & (damage_map > 0)]
            if len(values):
                worst_locus = max(worst_locus, float(np.percentile(values, 95)))

    de = _delta_e_map(rendered, source)
    salient = source_ink | render_ink | source_edge | render_edge
    salient_de = de[salient] if salient.any() else de.reshape(-1)
    boundary_total = max(1, int(np.count_nonzero(source_edge | render_edge)))
    return VisibleDamageMetrics(
        catastrophic_locus_count=int(locus_count),
        catastrophic_locus_rate=round(
            float(np.count_nonzero(catastrophic)) / boundary_total, 5,
        ),
        worst_locus_severity=round(float(worst_locus), 4),
        boundary_cvar10=round(_cvar(boundary_distances), 4),
        boundary_p99=round(float(np.percentile(boundary_distances, 99)), 4),
        detail_de_cvar10=round(_cvar(salient_de), 4),
        persistent_beta0_error=round(float(np.mean(beta0_delta)), 4),
        persistent_beta1_error=round(float(np.mean(beta1_delta)), 4),
        persistent_components_lost=round(float(np.mean(lost_components)), 4),
        persistent_holes_lost=round(float(np.mean(lost_holes)), 4),
        persistent_holes_gained=round(float(np.mean(gained_holes)), 4),
        any_counter_failure=bool(sum(value > 0 for value in lost_holes) >= 2),
    )


def damage_regressed(
    candidate: VisibleDamageMetrics,
    baseline: VisibleDamageMetrics | None,
) -> bool:
    """Strict structural non-regression against the frozen incumbent."""
    if baseline is None:
        return False
    return bool(
        candidate.catastrophic_locus_count > baseline.catastrophic_locus_count
        or (candidate.any_counter_failure and not baseline.any_counter_failure)
        or candidate.persistent_components_lost > baseline.persistent_components_lost
        or candidate.persistent_holes_lost > baseline.persistent_holes_lost
        or candidate.persistent_holes_gained > baseline.persistent_holes_gained
    )
