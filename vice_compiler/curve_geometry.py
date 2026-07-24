"""Shared parametric curve geometry for CMIR, court, and SVG delivery."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def curve_control_points(
    parameters: Iterable[tuple[str, float | int | str]],
) -> np.ndarray:
    """Decode the bounded closed-curve anchors carried by a SceneProgram."""
    values = dict(parameters)
    declared = values.get("curve_point_count", 0)
    try:
        count = max(0, min(64, int(declared)))
    except (TypeError, ValueError):
        return np.empty((0, 2), np.float64)
    points = []
    for index in range(count):
        x = values.get(f"curve_p{index}_x")
        y = values.get(f"curve_p{index}_y")
        if not isinstance(x, (float, int)) or not isinstance(y, (float, int)):
            return np.empty((0, 2), np.float64)
        points.append((float(x), float(y)))
    return np.asarray(points, np.float64).reshape((-1, 2))


def closed_catmull_rom_svg_path(
    parameters: Iterable[tuple[str, float | int | str]],
) -> str:
    """Emit one C1 closed cubic path from the program's curve anchors.

    The same immutable parameters are consumed by optimization and production
    export.  Tangents are shared at every knot, so G1 continuity is structural;
    the Phase-7 factor graph regularizes curvature variation (the G2 term).
    """
    rows = tuple(parameters)
    points = curve_control_points(rows)
    if len(points) < 3 or not np.all(np.isfinite(points)):
        return ""
    values = dict(rows)
    tension = values.get("curve_tension", 1.0)
    if not isinstance(tension, (float, int)):
        return ""
    tangent_scale = float(np.clip(float(tension), 0.25, 1.75)) / 6.0
    path = [f"M{points[0, 0]:.12g},{points[0, 1]:.12g}"]
    count = len(points)
    for index in range(count):
        previous = points[(index - 1) % count]
        start = points[index]
        end = points[(index + 1) % count]
        following = points[(index + 2) % count]
        control_a = start + (end - previous) * tangent_scale
        control_b = end - (following - start) * tangent_scale
        path.append(
            f"C{control_a[0]:.12g},{control_a[1]:.12g} "
            f"{control_b[0]:.12g},{control_b[1]:.12g} "
            f"{end[0]:.12g},{end[1]:.12g}"
        )
    path.append("Z")
    return " ".join(path)
