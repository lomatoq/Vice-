"""Shared-interface gap-filler adapter for SVG renderers."""

from __future__ import annotations

from .contracts import SceneGraph
from .ingest import linear_to_srgb

import numpy as np


def gap_filler_rows(scene: SceneGraph, path_for_geometry, *, width_px: float = .35) -> list[str]:
    appearance = {item.id: item for item in scene.appearances}
    shape = {item.id: item for item in scene.shapes}
    rows = []
    for edge in scene.interfaces:
        if edge.left_shape is None or edge.right_shape is None or not edge.geometry:
            continue
        left = appearance[shape[edge.left_shape].appearance_id].rgba_linear
        right = appearance[shape[edge.right_shape].appearance_id].rgba_linear
        rgb = linear_to_srgb(np.asarray([(np.asarray(left[:3]) + np.asarray(right[:3])) * .5], np.float32))[0]
        color = "#" + "".join(f"{int(round(v * 255)):02x}" for v in rgb)
        d = path_for_geometry(edge.geometry, close=False)
        if d:
            rows.append(
                f'<path data-role="gap-filler" d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{width_px:.3f}" vector-effect="non-scaling-stroke" '
                'stroke-linejoin="round" stroke-linecap="round"/>'
            )
    return rows
