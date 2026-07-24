"""Exact synthetic evidence labels derived from source scenes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .contracts import SceneGraph
from .ingest import linear_rgb_to_oklab, srgb_to_linear
from .render_models import render_scene
from .shape_models import primitive_points


SHAPE_CLASS = {"circle": 0, "ellipse": 0, "rectangle": 1,
               "rounded-rectangle": 1, "rect": 1, "glyph": 2,
               "glyph-font": 2, "ribbon": 2}


def exact_evidence_labels(scene: SceneGraph) -> dict[str, np.ndarray]:
    rgba = render_scene(scene).astype(np.float32) / 255.0
    linear = srgb_to_linear(rgba[..., :3])
    lab = linear_rgb_to_oklab(linear)
    alpha = rgba[..., 3]
    gray = lab[..., 0]
    gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
    magnitude = np.sqrt(gx * gx + gy * gy)
    boundary = np.clip(magnitude / max(float(np.percentile(magnitude, 99)), 1e-6), 0, 1)
    normal = np.stack((gx, gy), axis=2)
    normal /= np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1e-6)
    corner = np.zeros((scene.height, scene.width), np.float32)
    shape_class = np.zeros((scene.height, scene.width, 4), np.float32)
    text = np.zeros_like(corner)
    glyph = np.zeros_like(corner)
    symmetry = np.zeros_like(corner)
    loops = {loop.id: loop for loop in scene.loops}
    for shape in scene.shapes:
        mask = np.zeros_like(corner, np.uint8)
        points = []
        for primitive in loops[shape.positive_loop].primitives:
            sampled = primitive_points(primitive, 128)
            points.extend(sampled.tolist())
            if primitive.kind in {"rect", "rounded-rect", "triangle", "quadrilateral", "star"}:
                for x, y in sampled[::max(1, len(sampled) // 12)]:
                    cv2.circle(corner, (int(round(x)), int(round(y))), 1, 1.0, -1)
        if len(points) >= 3:
            cv2.fillPoly(mask, [np.round(points).astype(np.int32)], 1)
        for loop_id in shape.negative_loops:
            hole_points = []
            for primitive in loops[loop_id].primitives:
                hole_points.extend(primitive_points(primitive, 128).tolist())
            if len(hole_points) >= 3:
                cv2.fillPoly(mask, [np.round(hole_points).astype(np.int32)], 0)
        class_index = SHAPE_CLASS.get(shape.model_family, 3)
        shape_class[mask > 0, class_index] = 1.0
        if shape.model_family.startswith("glyph"):
            text[mask > 0] = 1.0
            glyph[mask > 0] = 1.0
        if shape.model_family in {"circle", "ellipse", "rectangle", "rounded-rectangle"}:
            symmetry[mask > 0] = 1.0
    ink = alpha > .5
    distance = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 5)
    ridge = distance >= cv2.dilate(distance, np.ones((3, 3), np.float32)) - 1e-5
    uncertainty = np.clip(1.0 - boundary, .05, .95).astype(np.float32)
    return {
        "region_embedding": lab.astype(np.float32),
        "color_logits": np.concatenate((lab, alpha[..., None]), axis=2).astype(np.float32),
        "boundary_prob": boundary.astype(np.float32),
        "boundary_normal": normal.astype(np.float32),
        "subpixel_offset": np.zeros((*boundary.shape, 2), np.float32),
        "coverage_alpha": alpha.astype(np.float32),
        "corner_prob": corner,
        "corner_type": np.stack((corner, np.zeros_like(corner), np.zeros_like(corner)), axis=2),
        "junction_prob": np.zeros_like(corner),
        "shape_class_logits": shape_class,
        "text_line_prob": text,
        "glyph_occupancy": glyph,
        "stroke_centerline_prob": (ridge & ink).astype(np.float32),
        "stroke_half_width": distance.astype(np.float32),
        "symmetry_evidence": symmetry,
        "uncertainty": uncertainty,
    }


def exact_scene_labels(scene: SceneGraph) -> dict:
    """Non-raster oracle labels kept beside every evidence training sample."""
    shape_index = {shape.id: index for index, shape in enumerate(scene.shapes)}
    return {
        "schema": "vice-synthetic-labels/1",
        "width": scene.width,
        "height": scene.height,
        "topology": {
            "shape_ids": [shape.id for shape in scene.shapes],
            "positive_loops": [shape.positive_loop for shape in scene.shapes],
            "negative_loops": [list(shape.negative_loops) for shape in scene.shapes],
            "parents": [shape_index.get(shape.parent, -1) for shape in scene.shapes],
        },
        "shape_classes": [shape.model_family for shape in scene.shapes],
        "shape_parameters": [list(shape.model_params) for shape in scene.shapes],
        "interfaces": [
            {"id": edge.id, "left": edge.left_shape, "right": edge.right_shape,
             "geometry": [primitive.kind for primitive in edge.geometry]}
            for edge in scene.interfaces
        ],
        "corners": [
            {"id": corner.id, "position": list(corner.position),
             "role": corner.role, "continuity": corner.continuity}
            for corner in scene.corners
        ],
        "constraints": [
            {"kind": edge.kind, "members": list(edge.members),
             "hardness": edge.weight_or_hardness}
            for edge in scene.constraints
        ],
        "draw_order": [shape.id for shape in sorted(scene.shapes,
                                                     key=lambda item: (item.layer, item.id))],
        "semantic_groups": [shape.semantic_group for shape in scene.shapes],
    }


def write_training_sample(path: Path, scene: SceneGraph, *,
                          input_rgba: np.ndarray | None = None,
                          renderer: str = "vice-analytic",
                          degradation_manifest: tuple[dict, ...] = ()) -> None:
    rgba = render_scene(scene) if input_rgba is None else np.asarray(input_rgba, np.uint8)
    if rgba.shape != (scene.height, scene.width, 4):
        raise ValueError("training input must be native-size RGBA")
    labels = exact_evidence_labels(scene)
    scene_json = scene.to_json(indent=None)
    metadata = {
        "schema": "vice-training-sample/1",
        "scene_sha256": hashlib.sha256(scene_json.encode("utf-8")).hexdigest(),
        "input_sha256": hashlib.sha256(rgba.tobytes()).hexdigest(),
        "renderer": renderer,
        "degradations": list(degradation_manifest),
        "labels": exact_scene_labels(scene),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, input_rgba=rgba,
                        scene_json=np.asarray(scene_json),
                        metadata_json=np.asarray(json.dumps(metadata, sort_keys=True,
                                                            separators=(",", ":"))),
                        **labels)
