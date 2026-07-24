"""Immutable contracts, coordinate units, and scene serialization.

Coordinates are always expressed in native input pixels unless an explicit
``coordinate_space`` says otherwise.  Pixel centres are at ``(x + .5, y + .5)``.
This module deliberately contains no NumPy arrays so scene files remain stable,
portable, and reviewable.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class CoordinateSpace(str, Enum):
    SOURCE = "source-pixel"
    NATIVE = "native-pixel"
    NORMALIZED = "normalized"


class AlphaConvention(str, Enum):
    STRAIGHT = "straight"
    PREMULTIPLIED = "premultiplied"


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def validate(self) -> None:
        if not all(math.isfinite(v) for v in (self.x0, self.y0, self.x1, self.y1)):
            raise ValueError("rectangle coordinates must be finite")
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("rectangle bounds are reversed")


IDENTITY_MATRIX3 = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


@dataclass(frozen=True)
class RasterSource:
    source_hash: str
    format: str
    encoded_size: int
    source_width: int
    source_height: int
    native_width: int
    native_height: int
    frame_index: int = 0
    exif_transform: tuple[float, ...] = IDENTITY_MATRIX3
    crop_rect_source: Rect = field(default_factory=lambda: Rect(0.0, 0.0, 0.0, 0.0))
    canonical_from_source: tuple[float, ...] = IDENTITY_MATRIX3
    icc_policy: str = "preserve"
    alpha_mode: str = AlphaConvention.STRAIGHT.value
    decoder: str = "Pillow"
    decoder_version: str = "unknown"
    dpi: tuple[float, float] | None = None

    def validate(self) -> None:
        if len(self.source_hash) != 64:
            raise ValueError("source_hash must be a SHA-256 hex digest")
        if self.encoded_size < 0 or min(self.source_width, self.source_height,
                                        self.native_width, self.native_height) <= 0:
            raise ValueError("raster dimensions and encoded size are invalid")
        if len(self.exif_transform) != 9 or len(self.canonical_from_source) != 9:
            raise ValueError("raster transforms must be 3x3 matrices")
        self.crop_rect_source.validate()


@dataclass(frozen=True)
class Distribution:
    values: tuple[float, ...]
    probabilities: tuple[float, ...]

    def validate(self) -> None:
        if not self.values or len(self.values) != len(self.probabilities):
            raise ValueError("distribution values/probabilities mismatch")
        if any((not math.isfinite(p) or p < 0.0) for p in self.probabilities):
            raise ValueError("distribution probabilities must be finite and non-negative")
        if abs(sum(self.probabilities) - 1.0) > 1e-5:
            raise ValueError("distribution probabilities must sum to one")


@dataclass(frozen=True)
class EvidenceRef:
    name: str
    version: str
    cache_key: str
    shape: tuple[int, ...]
    dtype: str
    coordinate_space: str = CoordinateSpace.NATIVE.value
    pixel_size_native: float = 1.0
    confidence_semantics: str = "probability"


@dataclass(frozen=True)
class EvidenceLevel:
    scale: float
    heads: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class EvidencePyramid:
    model_version: str
    levels: tuple[EvidenceLevel, ...]
    source_hash: str


@dataclass(frozen=True)
class RasterProfile:
    artwork_prob: float
    photo_prob: float
    aa_mode_probs: tuple[float, ...]
    blur_sigma_distribution: Distribution
    gamma_distribution: Distribution
    jpeg_quality_distribution: Distribution | None
    palette_complexity: Distribution
    text_probability: float
    diagram_probability: float
    gradient_probability: float
    transparency_probability: float
    local_confidence_ref: EvidenceRef | None = None

    def validate(self) -> None:
        for value in (self.artwork_prob, self.photo_prob, self.text_probability,
                      self.diagram_probability, self.gradient_probability,
                      self.transparency_probability, *self.aa_mode_probs):
            if not 0.0 <= value <= 1.0:
                raise ValueError("profile probabilities must be in [0, 1]")
        self.blur_sigma_distribution.validate()
        self.gamma_distribution.validate()
        self.palette_complexity.validate()
        if self.jpeg_quality_distribution is not None:
            self.jpeg_quality_distribution.validate()


@dataclass(frozen=True)
class GradientStop:
    offset: float
    rgba_linear: tuple[float, float, float, float]


@dataclass(frozen=True)
class Appearance:
    id: str
    kind: str  # solid, linear-gradient, radial-gradient
    rgba_linear: tuple[float, float, float, float]
    parameters: tuple[float, ...] = ()
    stops: tuple[GradientStop, ...] = ()
    confidence: float = 1.0
    covariance: tuple[float, ...] = ()
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeometryPrimitive:
    """Analytic primitive with optional sampled support/provenance.

    ``kind`` is line/circle/ellipse/rect/rounded-rect/quadratic/cubic/polyline.
    ``parameters`` use the canonical conventions documented by shape_models.py;
    ``points`` are native-pixel coordinates and remain available for fallback.
    """

    kind: str
    parameters: tuple[float, ...] = ()
    points: tuple[tuple[float, float], ...] = ()
    confidence: float = 1.0
    evidence_rms_px: float = 0.0
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoopNode:
    id: str
    primitives: tuple[GeometryPrimitive, ...]
    orientation: int = 1
    signed_area: float = 0.0
    coordinate_space: str = CoordinateSpace.NATIVE.value
    pixel_size_native: float = 1.0


@dataclass(frozen=True)
class ShapeNode:
    id: str
    topology_id: str
    appearance_id: str
    positive_loop: str
    negative_loops: tuple[str, ...] = ()
    parent: str | None = None
    layer: int = 0
    model_family: str = "generic"
    model_params: tuple[float, ...] = ()
    confidence: float = 1.0
    provenance: tuple[str, ...] = ()
    semantic_group: str | None = None


@dataclass(frozen=True)
class InterfaceEdge:
    id: str
    left_shape: str | None
    right_shape: str | None
    geometry: tuple[GeometryPrimitive, ...]
    corner_nodes: tuple[str, ...] = ()
    confidence_profile: tuple[float, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CornerNode:
    id: str
    position: tuple[float, float]
    covariance: tuple[float, float, float]
    incident_interfaces: tuple[str, ...]
    continuity: str = "C0"
    role: str = "unknown"
    confidence: float = 1.0


@dataclass(frozen=True)
class ConstraintEdge:
    id: str
    kind: str
    members: tuple[str, ...]
    weight_or_hardness: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class LayerEdge:
    below: str
    above: str


@dataclass(frozen=True)
class SceneGraph:
    width: int
    height: int
    appearances: tuple[Appearance, ...]
    loops: tuple[LoopNode, ...]
    shapes: tuple[ShapeNode, ...]
    interfaces: tuple[InterfaceEdge, ...] = ()
    corners: tuple[CornerNode, ...] = ()
    constraints: tuple[ConstraintEdge, ...] = ()
    layer_edges: tuple[LayerEdge, ...] = ()
    coordinate_space: str = CoordinateSpace.NATIVE.value
    pixel_size_native: float = 1.0
    schema_version: str = "vice-scene/1"

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0 or self.pixel_size_native <= 0:
            raise ValueError("invalid scene dimensions/units")
        appearance_ids = _unique_ids(self.appearances, "appearance")
        loop_ids = _unique_ids(self.loops, "loop")
        shape_ids = _unique_ids(self.shapes, "shape")
        interface_ids = _unique_ids(self.interfaces, "interface")
        corner_ids = _unique_ids(self.corners, "corner")
        _unique_ids(self.constraints, "constraint")
        for loop in self.loops:
            if not loop.primitives:
                raise ValueError(f"loop {loop.id!r} has no geometry")
            if loop.orientation not in {-1, 1}:
                raise ValueError(f"loop {loop.id!r} has invalid orientation")
        for shape in self.shapes:
            if shape.appearance_id not in appearance_ids:
                raise ValueError(f"shape {shape.id!r} has unknown appearance")
            if shape.positive_loop not in loop_ids:
                raise ValueError(f"shape {shape.id!r} has unknown positive loop")
            if any(loop_id not in loop_ids for loop_id in shape.negative_loops):
                raise ValueError(f"shape {shape.id!r} has unknown negative loop")
            if shape.parent is not None and shape.parent not in shape_ids:
                raise ValueError(f"shape {shape.id!r} has unknown parent")
            if shape.parent == shape.id:
                raise ValueError(f"shape {shape.id!r} cannot parent itself")
        for edge in self.interfaces:
            if edge.left_shape is not None and edge.left_shape not in shape_ids:
                raise ValueError(f"interface {edge.id!r} has unknown left shape")
            if edge.right_shape is not None and edge.right_shape not in shape_ids:
                raise ValueError(f"interface {edge.id!r} has unknown right shape")
            if edge.left_shape == edge.right_shape:
                raise ValueError(f"interface {edge.id!r} borders one shape twice")
            if any(corner_id not in corner_ids for corner_id in edge.corner_nodes):
                raise ValueError(f"interface {edge.id!r} references an unknown corner")
        for corner in self.corners:
            if any(interface_id not in interface_ids
                   for interface_id in corner.incident_interfaces):
                raise ValueError(f"corner {corner.id!r} references an unknown interface")
        for constraint in self.constraints:
            if not constraint.members:
                raise ValueError(f"constraint {constraint.id!r} has no members")
            if any(member not in shape_ids for member in constraint.members):
                raise ValueError(f"constraint {constraint.id!r} references an unknown shape")
            if not math.isfinite(constraint.weight_or_hardness):
                raise ValueError(f"constraint {constraint.id!r} has non-finite weight")
        _validate_parent_tree(self.shapes)
        _validate_acyclic(shape_ids, self.layer_edges)
        if len(interface_ids) != len(self.interfaces):
            raise ValueError("duplicate interfaces")

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self, *, indent: int | None = 2) -> str:
        self.validate()
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent,
                          sort_keys=True, allow_nan=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneGraph":
        appearances = tuple(_appearance_from_dict(row) for row in data["appearances"])
        loops = tuple(_loop_from_dict(row) for row in data["loops"])
        shapes = tuple(ShapeNode(**_tuplify_fields(row, {
            "negative_loops", "model_params", "provenance"})) for row in data["shapes"])
        interfaces = tuple(_interface_from_dict(row) for row in data.get("interfaces", ()))
        corners = tuple(CornerNode(**_tuplify_fields(row, {
            "position", "covariance", "incident_interfaces"}))
                        for row in data.get("corners", ()))
        constraints = tuple(ConstraintEdge(**_tuplify_fields(row, {"members", "evidence"}))
                            for row in data.get("constraints", ()))
        layer_edges = tuple(LayerEdge(**row) for row in data.get("layer_edges", ()))
        scene = cls(
            width=int(data["width"]), height=int(data["height"]),
            appearances=appearances, loops=loops, shapes=shapes,
            interfaces=interfaces, corners=corners, constraints=constraints,
            layer_edges=layer_edges,
            coordinate_space=data.get("coordinate_space", CoordinateSpace.NATIVE.value),
            pixel_size_native=float(data.get("pixel_size_native", 1.0)),
            schema_version=data.get("schema_version", "vice-scene/1"),
        )
        scene.validate()
        return scene

    @classmethod
    def from_json(cls, value: str) -> "SceneGraph":
        return cls.from_dict(json.loads(value))


@dataclass(frozen=True)
class RenderModel:
    name: str = "clean-aa"
    supersample: int = 4
    gamma: float = 2.2
    blur_sigma: float = 0.0
    jpeg_quality: int | None = None
    background_linear: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.0)


@dataclass(frozen=True)
class ScoreBreakdown:
    render_nll: float = 0.0
    mdl: float = 0.0
    topology: float = 0.0
    regularity: float = 0.0
    semantics: float = 0.0
    unsupported_evidence: float = 0.0

    @property
    def total(self) -> float:
        return (self.render_nll + self.mdl + self.topology + self.regularity
                + self.semantics + self.unsupported_evidence)


@dataclass(frozen=True)
class SceneHypothesis:
    id: str
    graph: SceneGraph
    render_model: RenderModel
    evidence_refs: tuple[str, ...]
    score_breakdown: ScoreBreakdown
    provenance: tuple[str, ...] = ()


def _unique_ids(items: Iterable[Any], kind: str) -> set[str]:
    ids = [str(item.id) for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {kind} ids")
    return set(ids)


def _validate_acyclic(shape_ids: set[str], edges: tuple[LayerEdge, ...]) -> None:
    outgoing: dict[str, list[str]] = {item: [] for item in shape_ids}
    indegree = {item: 0 for item in shape_ids}
    for edge in edges:
        if edge.below not in shape_ids or edge.above not in shape_ids:
            raise ValueError("layer edge references an unknown shape")
        outgoing[edge.below].append(edge.above)
        indegree[edge.above] += 1
    queue = [key for key, value in indegree.items() if value == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in outgoing[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(shape_ids):
        raise ValueError("draw-order graph contains a cycle")


def _validate_parent_tree(shapes: tuple[ShapeNode, ...]) -> None:
    """Validate the containment parent relation independently of draw order."""
    parents = {shape.id: shape.parent for shape in shapes}
    for start in parents:
        seen: set[str] = set()
        node: str | None = start
        while node is not None:
            if node in seen:
                raise ValueError("shape parent graph contains a cycle")
            seen.add(node)
            node = parents[node]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def _tuplify_fields(row: dict[str, Any], names: set[str]) -> dict[str, Any]:
    return {key: (tuple(value) if key in names else value) for key, value in row.items()}


def _primitive_from_dict(row: dict[str, Any]) -> GeometryPrimitive:
    return GeometryPrimitive(
        kind=row["kind"], parameters=tuple(row.get("parameters", ())),
        points=tuple(tuple(float(v) for v in point) for point in row.get("points", ())),
        confidence=float(row.get("confidence", 1.0)),
        evidence_rms_px=float(row.get("evidence_rms_px", 0.0)),
        provenance=tuple(row.get("provenance", ())),
    )


def _loop_from_dict(row: dict[str, Any]) -> LoopNode:
    return LoopNode(
        id=row["id"], primitives=tuple(_primitive_from_dict(p) for p in row["primitives"]),
        orientation=int(row.get("orientation", 1)),
        signed_area=float(row.get("signed_area", 0.0)),
        coordinate_space=row.get("coordinate_space", CoordinateSpace.NATIVE.value),
        pixel_size_native=float(row.get("pixel_size_native", 1.0)),
    )


def _appearance_from_dict(row: dict[str, Any]) -> Appearance:
    return Appearance(
        id=row["id"], kind=row["kind"], rgba_linear=tuple(row["rgba_linear"]),
        parameters=tuple(row.get("parameters", ())),
        stops=tuple(GradientStop(float(s["offset"]), tuple(s["rgba_linear"]))
                    for s in row.get("stops", ())),
        confidence=float(row.get("confidence", 1.0)),
        covariance=tuple(row.get("covariance", ())),
        provenance=tuple(row.get("provenance", ())),
    )


def _interface_from_dict(row: dict[str, Any]) -> InterfaceEdge:
    return InterfaceEdge(
        id=row["id"], left_shape=row.get("left_shape"), right_shape=row.get("right_shape"),
        geometry=tuple(_primitive_from_dict(p) for p in row.get("geometry", ())),
        corner_nodes=tuple(row.get("corner_nodes", ())),
        confidence_profile=tuple(row.get("confidence_profile", ())),
        evidence_refs=tuple(row.get("evidence_refs", ())),
    )


def write_scene(path: Path, scene: SceneGraph) -> None:
    path.write_text(scene.to_json() + "\n", encoding="utf-8")


def read_scene(path: Path) -> SceneGraph:
    return SceneGraph.from_json(path.read_text(encoding="utf-8"))
