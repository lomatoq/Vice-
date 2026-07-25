"""M3: coverage field and subpixel boundary observations (plan S3.3, M3).

The current fitter treats the pixel-centre staircase as if it were the real
curve, so every span inherits the lattice's ripple - the "crooked" half of
the human verdict.  This module recovers what the raster actually says:

    two-colour coverage alpha  ->  marching-squares boundary at alpha=0.5
    ->  arclength resampling  ->  normals  ->  per-sample uncertainty
        halfwidth  ->  physical ds weights

The halfwidth is the corridor a candidate curve must stay inside (M4), and
the physical weights make the cost density-free: the same boundary sampled
at 1x and 4x must not pay a different price (plan S13.2).

Hard requirement (plan M3): boundary extraction may not change topology.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from .certificates import topology_signature

#: Resampling step in native pixels; below ~0.5 the samples stop carrying
#: independent evidence because the coverage field itself is band limited.
DEFAULT_SAMPLE_STEP_PX = 0.35
#: A boundary sample is never trusted tighter than this: antialiasing,
#: gamma and JPEG all move the 0.5 level set by a fraction of a pixel.
MINIMUM_HALFWIDTH_PX = 0.30
MAXIMUM_HALFWIDTH_PX = 2.50
#: With a hard binary support the true boundary is only known to within half
#: a cell, so the corridor must admit that or every straight edge is rejected
#: as "not straight enough" and the program degenerates into a staircase.
BINARY_HALFWIDTH_PX = 0.62


@dataclass(frozen=True)
class CoverageEstimate:
    alpha: np.ndarray                  # HxW float32 in [0, 1]
    uncertainty: np.ndarray            # HxW float32, alpha-domain sigma
    foreground_rgb: tuple[float, float, float]
    background_rgb: tuple[float, float, float]
    separable: bool
    residual_p95: float


@dataclass(frozen=True)
class BoundaryObservation:
    """Plan S3.3: one closed subpixel boundary with its evidence corridor."""

    points_xy: np.ndarray              # Nx2 float64, subpixel samples
    normals_xy: np.ndarray             # Nx2 float64, outward unit normals
    halfwidth_px: np.ndarray           # N float64, per-sample corridor
    physical_weights: np.ndarray       # N float64, ds weights (sum = length)
    confidence: np.ndarray             # N float64 in (0, 1]
    closed: bool
    source_component_id: str
    source_hole_id: str | None = None

    def validate(self) -> None:
        count = len(self.points_xy)
        if count < 4:
            raise ValueError("boundary observation needs at least four samples")
        for name, array in (
            ("normals", self.normals_xy), ("halfwidth", self.halfwidth_px),
            ("weights", self.physical_weights), ("confidence", self.confidence),
        ):
            if len(array) != count:
                raise ValueError(f"{name} length does not match the samples")
            if not np.all(np.isfinite(array)):
                raise ValueError(f"{name} contains non-finite values")
        if np.any(self.halfwidth_px <= 0.0):
            raise ValueError("halfwidth must be positive")
        if np.any(self.physical_weights < 0.0):
            raise ValueError("physical weights must be non-negative")

    @property
    def length_px(self) -> float:
        return float(np.sum(self.physical_weights))


def robust_two_color_coverage(
    linear_rgb: np.ndarray, support: np.ndarray, *,
    background_ring_px: int = 3,
) -> CoverageEstimate:
    """Estimate ink coverage alpha for a single-ink region (plan M3.1).

    ``linear_rgb`` is HxWx3 in [0, 1].  Returns coverage plus a per-pixel
    uncertainty derived from the residual to the two-colour model, so a
    region that is not two-colour (gradient, multi-ink) is reported as
    ``separable=False`` and the caller must not fit a single boundary.
    """
    rgb = np.asarray(linear_rgb, np.float32)
    mask = np.asarray(support, bool)
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError("linear_rgb must be HxWx3")
    if mask.shape != rgb.shape[:2]:
        raise ValueError("support shape differs from the raster")
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(
        mask.astype(np.uint8), kernel, iterations=max(1, background_ring_px),
    ).astype(bool)
    ring = dilated & ~mask
    core = cv2.erode(mask.astype(np.uint8), kernel, iterations=1).astype(bool)
    if not ring.any():
        ring = ~mask
    if not core.any():
        core = mask
    background = np.median(rgb[..., :3][ring], axis=0)
    foreground = np.median(rgb[..., :3][core], axis=0)
    direction = foreground - background
    denominator = float(direction @ direction)
    if denominator <= 1.0e-6:
        alpha = mask.astype(np.float32)
        return CoverageEstimate(
            alpha=alpha,
            uncertainty=np.full(alpha.shape, 0.5, np.float32),
            foreground_rgb=tuple(float(v) for v in foreground),
            background_rgb=tuple(float(v) for v in background),
            separable=False, residual_p95=1.0,
        )
    projected = ((rgb[..., :3] - background) @ direction) / denominator
    alpha = np.clip(projected, 0.0, 1.0).astype(np.float32)
    model = (
        background[None, None, :]
        + alpha[..., None] * direction[None, None, :]
    )
    residual = np.linalg.norm(rgb[..., :3] - model, axis=2).astype(np.float32)
    scale = math.sqrt(denominator)
    uncertainty = np.clip(residual / max(scale, 1.0e-6), 0.0, 1.0)
    band = dilated
    residual_p95 = float(np.percentile(residual[band], 95)) if band.any() else 0.0
    return CoverageEstimate(
        alpha=alpha, uncertainty=uncertainty.astype(np.float32),
        foreground_rgb=tuple(float(v) for v in foreground),
        background_rgb=tuple(float(v) for v in background),
        separable=bool(residual_p95 <= 0.22 * max(scale, 1.0e-6) + 0.02),
        residual_p95=residual_p95,
    )


# --------------------------------------------------------------------------
# marching squares at alpha = level
# --------------------------------------------------------------------------

_EDGE_POINTS = {
    0: ((0, 0), (1, 0)),   # top    edge between (x,y)   and (x+1,y)
    1: ((1, 0), (1, 1)),   # right  edge between (x+1,y) and (x+1,y+1)
    2: ((0, 1), (1, 1)),   # bottom edge
    3: ((0, 0), (0, 1)),   # left   edge
}

#: Standard marching-squares connectivity: for each of the 16 corner masks,
#: the list of (entry edge, exit edge) segments.  Corner bit order is
#: TL=1, TR=2, BR=4, BL=8 and "inside" means value >= level.
_SEGMENTS: dict[int, tuple[tuple[int, int], ...]] = {
    0: (), 15: (),
    1: ((3, 0),), 14: ((0, 3),),
    2: ((0, 1),), 13: ((1, 0),),
    3: ((3, 1),), 12: ((1, 3),),
    4: ((1, 2),), 11: ((2, 1),),
    6: ((0, 2),), 9: ((2, 0),),
    7: ((3, 2),), 8: ((2, 3),),
    5: ((3, 0), (1, 2)),
    10: ((0, 1), (2, 3)),
}


def _interpolate(
    field: np.ndarray, x: int, y: int, edge: int, level: float,
) -> tuple[float, float]:
    (ax, ay), (bx, by) = _EDGE_POINTS[edge]
    va = float(field[y + ay, x + ax])
    vb = float(field[y + by, x + bx])
    denominator = vb - va
    t = 0.5 if abs(denominator) < 1.0e-12 else (level - va) / denominator
    t = min(1.0, max(0.0, t))
    return (
        x + ax + (bx - ax) * t,
        y + ay + (by - ay) * t,
    )


def marching_squares(
    field: np.ndarray, *, level: float = 0.5,
) -> list[np.ndarray]:
    """Closed subpixel contours of ``field`` at ``level`` (plan M3.2).

    Deterministic and topology-faithful.  Segments are built per cell with
    a consistent orientation (interior on the left), then CONSUMED while
    walking, so a ring is only closed when the walk returns to its start -
    a visited-set walk fragments rings at saddles and shared vertices, and
    a fragmented ring renders as a self-cancelling even-odd path.
    """
    values = np.asarray(field, np.float64)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 2:
        return []
    inside = values >= level
    corner_mask = (
        inside[:-1, :-1].astype(np.uint8)
        | (inside[:-1, 1:].astype(np.uint8) << 1)
        | (inside[1:, 1:].astype(np.uint8) << 2)
        | (inside[1:, :-1].astype(np.uint8) << 3)
    )
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = {}
    height, width = corner_mask.shape
    for y in range(height):
        row = corner_mask[y]
        for x in np.flatnonzero((row != 0) & (row != 15)).tolist():
            code = int(row[x])
            pairs = _SEGMENTS[code]
            if code in (5, 10):
                cell_mean = 0.25 * float(
                    values[y, x] + values[y, x + 1]
                    + values[y + 1, x] + values[y + 1, x + 1]
                )
                if (cell_mean >= level) != (code == 5):
                    pairs = tuple((b, a) for a, b in pairs)
            for entry, exit_edge in pairs:
                head = _interpolate(values, x, y, entry, level)
                tail = _interpolate(values, x, y, exit_edge, level)
                key = (round(head[0], 6), round(head[1], 6))
                adjacency.setdefault(key, []).append(
                    (round(tail[0], 6), round(tail[1], 6)),
                )
    contours: list[np.ndarray] = []
    while adjacency:
        start_key = next(iter(adjacency))
        ring: list[tuple[float, float]] = []
        current = start_key
        while True:
            options = adjacency.get(current)
            if not options:
                break
            following = options.pop()
            if not options:
                del adjacency[current]
            ring.append(current)
            current = following
            if current == start_key:
                break
            if len(ring) > 4 * values.size:
                break
        if len(ring) >= 4:
            contours.append(np.asarray(ring, np.float64))
    return contours


def _outward_normals(points: np.ndarray) -> np.ndarray:
    """Unit normals pointing away from the enclosed area."""
    following = np.roll(points, -1, axis=0)
    previous = np.roll(points, 1, axis=0)
    tangent = following - previous
    lengths = np.linalg.norm(tangent, axis=1)
    lengths[lengths < 1.0e-9] = 1.0
    tangent = tangent / lengths[:, None]
    normals = np.column_stack((tangent[:, 1], -tangent[:, 0]))
    area = 0.5 * float(np.sum(
        points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1],
    ))
    if area > 0.0:
        normals = -normals
    return normals


def _sample_bilinear(field: np.ndarray, points: np.ndarray) -> np.ndarray:
    height, width = field.shape
    x = np.clip(points[:, 0], 0.0, width - 1.0)
    y = np.clip(points[:, 1], 0.0, height - 1.0)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    fx = x - x0
    fy = y - y0
    top = field[y0, x0] * (1 - fx) + field[y0, x1] * fx
    bottom = field[y1, x0] * (1 - fx) + field[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def boundary_observations(
    alpha: np.ndarray, *, uncertainty: np.ndarray | None = None,
    component_id: str = "component-0",
    step_px: float = DEFAULT_SAMPLE_STEP_PX, level: float = 0.5,
) -> list[BoundaryObservation]:
    """Subpixel boundary observations of a coverage field (plan M3.2)."""
    from shared_primitive_fitting import resample_by_arclength

    field = np.asarray(alpha, np.float64)
    # A field with (almost) no intermediate coverage carries no subpixel
    # evidence: its 0.5 level set is the cell staircase itself.
    interior = field[(field > 0.02) & (field < 0.98)]
    binary_source = interior.size < max(8, int(0.01 * field.size))
    floor = BINARY_HALFWIDTH_PX if binary_source else MINIMUM_HALFWIDTH_PX
    rings = marching_squares(field, level=level)
    observations: list[BoundaryObservation] = []
    for index, ring in enumerate(rings):
        points = resample_by_arclength(ring, step=step_px, closed=True)
        if len(points) < 8:
            continue
        normals = _outward_normals(points)
        following = np.roll(points, -1, axis=0)
        previous = np.roll(points, 1, axis=0)
        weights = 0.5 * np.linalg.norm(following - previous, axis=1)
        if uncertainty is not None:
            local = _sample_bilinear(
                np.asarray(uncertainty, np.float64), points,
            )
        else:
            local = np.zeros(len(points))
        gradient_x = _sample_bilinear(
            np.abs(cv2.Sobel(field.astype(np.float32), cv2.CV_32F, 1, 0, 3)),
            points,
        )
        gradient_y = _sample_bilinear(
            np.abs(cv2.Sobel(field.astype(np.float32), cv2.CV_32F, 0, 1, 3)),
            points,
        )
        slope = np.hypot(gradient_x, gradient_y) / 4.0
        # A shallow coverage ramp localizes the 0.5 level poorly; the
        # corridor widens exactly where the evidence is weak.
        halfwidth = np.clip(
            floor + 0.5 * local / np.maximum(slope, 0.08),
            floor, MAXIMUM_HALFWIDTH_PX,
        )
        observation = BoundaryObservation(
            points_xy=points, normals_xy=normals, halfwidth_px=halfwidth,
            physical_weights=weights,
            confidence=1.0 / (1.0 + halfwidth),
            closed=True,
            source_component_id=f"{component_id}-ring-{index}",
        )
        observation.validate()
        observations.append(observation)
    return observations


def observations_preserve_topology(
    alpha: np.ndarray, observations: list[BoundaryObservation], *,
    level: float = 0.5,
) -> bool:
    """Plan M3 hard requirement: extraction must not change topology."""
    binary = np.asarray(alpha >= level, np.uint8)
    expected = topology_signature(binary)
    return len(observations) == expected[0] + expected[1]


def coverage_from_support(support: np.ndarray) -> np.ndarray:
    """Binary fallback coverage when the colour model is not separable."""
    return np.asarray(support, bool).astype(np.float32)
