"""Design Program IR (DPIR) and bounded Export IR adapters."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .continuous_refine import ContinuousRefinementResult
from .layer_solver import LayeredScene
from .macro_ir import CandidateMacroIR, MacroKind, SceneProgram
from .visible_scene import VisibleSceneIR


SCHEMA = "pcdc-dpir/v1"


@dataclass(frozen=True)
class ProgramAnalysis:
    bbox_xyxy: tuple[int, int, int, int]
    components: int | None
    holes: int | None
    render_digest: str
    parameter_group: str | None
    editable_score: float
    native_primitive: bool


@dataclass(frozen=True)
class ProgramNode:
    id: str
    operator: str
    parameters: tuple[tuple[str, float | int | str], ...]
    children: tuple[str, ...]
    source_macro_ids: tuple[str, ...]
    analysis: ProgramAnalysis
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class DesignProgramIR:
    schema: str
    source_sha256: str
    nodes: tuple[ProgramNode, ...]
    root_id: str
    selected_macro_ids: tuple[str, ...]
    layer_order: tuple[str, ...]
    visible_owner_digest: str
    program_digest: str
    provenance: tuple[str, ...]

    def by_id(self) -> dict[str, ProgramNode]:
        return {row.id: row for row in self.nodes}

    def reachable_ids(self) -> tuple[str, ...]:
        lookup = self.by_id(); seen = set(); stack = [self.root_id]
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id); stack.extend(lookup[node_id].children)
        return tuple(sorted(seen))

    def validate(self) -> None:
        if self.schema != SCHEMA:
            raise ValueError("unsupported Design Program IR schema")
        lookup = self.by_id()
        if len(lookup) != len(self.nodes) or self.root_id not in lookup:
            raise ValueError("invalid or duplicate DPIR node identity")
        for node in self.nodes:
            if any(child not in lookup for child in node.children):
                raise ValueError("DPIR node references a missing child")
        # Selected visible macros remain represented exactly once as leaves;
        # abstraction may add wrappers later but cannot lose source ownership.
        reachable = set(self.reachable_ids())
        represented = [
            macro_id for node in self.nodes if node.id in reachable
            for macro_id in node.source_macro_ids
            if macro_id in self.selected_macro_ids
        ]
        if set(represented) != set(self.selected_macro_ids):
            raise ValueError("DPIR lost a selected visible macro")
        expected = _program_digest(
            self.source_sha256, self.nodes, self.root_id,
            self.selected_macro_ids, self.layer_order,
            self.visible_owner_digest, self.provenance,
        )
        if self.program_digest != expected:
            raise ValueError("DPIR digest mismatch")


@dataclass(frozen=True)
class ExportNode:
    id: str
    operator: str
    parameters: tuple[tuple[str, float | int | str], ...]
    children: tuple[str, ...]
    source_program_node: str


@dataclass(frozen=True)
class ExportIR:
    schema: str
    target: str
    mode: str
    nodes: tuple[ExportNode, ...]
    root_id: str
    warnings: tuple[str, ...]
    source_program_digest: str
    provenance: tuple[str, ...]

    def validate(self) -> None:
        lookup = {row.id: row for row in self.nodes}
        if self.root_id not in lookup or len(lookup) != len(self.nodes):
            raise ValueError("invalid Export IR node graph")
        if any(child not in lookup for row in self.nodes for child in row.children):
            raise ValueError("Export IR references a missing child")


def _owner_digest(owners: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for owner in owners:
        digest.update(owner.encode("utf-8")); digest.update(b"\0")
    return digest.hexdigest()


def _stable_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _program_digest(
    source_sha256: str, nodes: tuple[ProgramNode, ...], root_id: str,
    selected: tuple[str, ...], order: tuple[str, ...], owner_digest: str,
    provenance: tuple[str, ...],
) -> str:
    payload = {
        "schema": SCHEMA, "source": source_sha256, "root": root_id,
        "selected": selected, "order": order, "owners": owner_digest,
        "nodes": [row.__dict__ for row in nodes], "provenance": provenance,
    }
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()


def _render_digest(candidate) -> str:
    digest = hashlib.sha256()
    digest.update(str(candidate.core_bits).encode("ascii"))
    digest.update(repr(candidate.certificates.support_rle).encode("ascii"))
    digest.update(candidate.certificates.support_bits)
    digest.update(repr((candidate.certificates.components,
                        candidate.certificates.holes)).encode("ascii"))
    return digest.hexdigest()


def _design_operator(program: SceneProgram, kind: MacroKind) -> str:
    operator = program.operator
    if operator.startswith("Shape/"):
        primitive = operator.split("/", 1)[1]
        return {
            "circle": "Circle", "ring": "Ring", "ellipse": "Ellipse",
            "rectangle": "Rectangle", "rounded_rectangle": "RoundedRect",
            "triangle": "Triangle", "quadrilateral": "Quadrilateral",
            "star": "Star", "D_bullet": "DBullet", "free_curve": "FreeCurve",
        }.get(primitive, primitive)
    if operator.startswith("Stroke/"):
        return "StrokeNetwork"
    if operator.startswith("TextLine/"):
        text_path = operator.split("/", 1)[1]
        return {
            "single-custom-glyph": "CustomGlyph",
            "knockout-text": "KnockoutText",
            "outlined-text-group": "OutlinedTextGroup",
            "outlined-shadowed-text-group": "ShadowedTextGroup",
        }.get(text_path, "TextLine")
    if operator.startswith("Appearance/"):
        return operator.split("/", 1)[1]
    if operator.startswith("RepeatGroup/"):
        return "RepeatGroup"
    return {
        MacroKind.ATOMIC_FALLBACK: "RasterFallback",
        MacroKind.LEGACY_REGION: "LegacyRegion",
        MacroKind.HIERARCHY_REGION: "Region",
        MacroKind.SOLID_REGION: "Solid",
        MacroKind.GRADIENT: "Gradient",
        MacroKind.CODEC_DETAIL: "CodecDetail",
    }.get(kind, operator)


def _editable_score(operator: str) -> float:
    if operator in {"Circle", "Ring", "Ellipse", "Rectangle", "RoundedRect",
                    "StrokeNetwork", "TextLine", "CustomGlyph", "KnockoutText",
                    "OutlinedTextGroup", "ShadowedTextGroup", "Repeat", "Mirror"}:
        return 1.0
    if operator in {"Triangle", "Quadrilateral", "Star", "DBullet", "Gradient"}:
        return 0.86
    if operator in {"FreeCurve", "Region"}:
        return 0.52
    return 0.25


def build_design_program(
    cmir: CandidateMacroIR, scene: VisibleSceneIR, *,
    layered: LayeredScene | None = None,
    refinement: ContinuousRefinementResult | None = None,
) -> DesignProgramIR:
    cmir.validate(); scene.validate(cmir)
    if layered is not None:
        layered.order_graph.validate()
        if layered.visible_scene.owner_by_leaf != scene.owner_by_leaf:
            raise ValueError("layered scene belongs to another visible program")
    if refinement is not None:
        refinement.validate()
        if refinement.selected_ids != scene.selected_macro_ids:
            raise ValueError("refinement belongs to another selected program")
    refined = {
        row.macro_id: row.refined_program for row in refinement.macros
    } if refinement is not None else {}
    lookup = cmir.by_id(); nodes = []; macro_nodes = {}
    for macro_id in scene.selected_macro_ids:
        candidate = lookup[macro_id]
        program = refined.get(macro_id, candidate.program)
        operator = _design_operator(program, candidate.kind)
        node_id = _stable_id("dp", {
            "macro": macro_id, "operator": operator,
            "parameters": program.parameters,
        })
        macro_nodes[macro_id] = node_id
        group = next((
            value for name, value in program.parameters
            if name in {"prototype", "member_ids", "shared_scale"}
        ), None)
        nodes.append(ProgramNode(
            id=node_id, operator=operator, parameters=program.parameters,
            children=(), source_macro_ids=(macro_id,),
            analysis=ProgramAnalysis(
                bbox_xyxy=candidate.roi_xyxy,
                components=candidate.certificates.components,
                holes=candidate.certificates.holes,
                render_digest=_render_digest(candidate),
                parameter_group=str(group) if group is not None else None,
                editable_score=_editable_score(operator),
                native_primitive=operator in {
                    "Circle", "Ring", "Ellipse", "Rectangle", "RoundedRect",
                    "StrokeNetwork", "TextLine", "CustomGlyph", "KnockoutText",
                    "OutlinedTextGroup", "ShadowedTextGroup", "Solid", "Gradient",
                },
            ),
            provenance=("selected-CMIR-macro", *candidate.provenance),
        ))

    order = (
        layered.order_graph.back_to_front if layered is not None
        else tuple(scene.selected_macro_ids)
    )
    hidden_ids = []
    if layered is not None:
        for completion in layered.hidden_completions:
            node_id = _stable_id("hidden", {
                "source": completion.source_macro_id,
                "front": completion.occluder_macro_id,
                "primitive": completion.primitive,
            })
            hidden_ids.append(node_id)
            source_node = macro_nodes[completion.source_macro_id]
            source_analysis = next(row.analysis for row in nodes if row.id == source_node)
            nodes.append(ProgramNode(
                id=node_id, operator="HiddenCompletion",
                parameters=(("occluder", completion.occluder_macro_id),
                            ("confidence", completion.confidence)),
                children=(source_node,), source_macro_ids=(),
                analysis=ProgramAnalysis(
                    bbox_xyxy=source_analysis.bbox_xyxy,
                    components=source_analysis.components,
                    holes=source_analysis.holes,
                    render_digest=hashlib.sha256(
                        completion.hidden_mask.tobytes()
                    ).hexdigest(),
                    parameter_group=None, editable_score=0.90,
                    native_primitive=True,
                ),
                provenance=completion.provenance,
            ))
    root_children = tuple(macro_nodes[macro_id] for macro_id in order) + tuple(hidden_ids)
    root_id = _stable_id("layer-stack", root_children)
    canvas_bbox = (
        min((row.analysis.bbox_xyxy[0] for row in nodes), default=0),
        min((row.analysis.bbox_xyxy[1] for row in nodes), default=0),
        max((row.analysis.bbox_xyxy[2] for row in nodes), default=0),
        max((row.analysis.bbox_xyxy[3] for row in nodes), default=0),
    )
    scene_render = hashlib.sha256(
        repr(tuple((row.id, row.analysis.render_digest) for row in nodes)).encode("ascii")
    ).hexdigest()
    nodes.append(ProgramNode(
        id=root_id, operator="LayerStack", parameters=(
            ("background", layered.selected_background.kind if layered else "visible-owner"),
        ), children=root_children, source_macro_ids=(),
        analysis=ProgramAnalysis(
            bbox_xyxy=canvas_bbox, components=None, holes=None,
            render_digest=scene_render, parameter_group=None,
            editable_score=0.82, native_primitive=True,
        ),
        provenance=("post-selection-design-root", "acyclic-layer-order"),
    ))
    frozen_nodes = tuple(nodes)
    provenance = (
        "built-after-global-selection", "fixed-visible-ownership",
        "refined-continuous-parameters" if refinement else "selected-parameters",
        "layer-hierarchy" if layered else "flat-visible-order",
    )
    owner_digest = _owner_digest(scene.owner_by_leaf)
    program = DesignProgramIR(
        schema=SCHEMA, source_sha256=cmir.source_sha256,
        nodes=frozen_nodes, root_id=root_id,
        selected_macro_ids=scene.selected_macro_ids,
        layer_order=order, visible_owner_digest=owner_digest,
        program_digest=_program_digest(
            cmir.source_sha256, frozen_nodes, root_id,
            scene.selected_macro_ids, order, owner_digest, provenance,
        ),
        provenance=provenance,
    )
    program.validate()
    return program


def adapt_export_ir(
    program: DesignProgramIR, *, target: str, mode: str = "native",
) -> ExportIR:
    program.validate()
    target = target.lower()
    if target not in {"svg", "eps", "pdf", "dxf", "png"}:
        raise ValueError("unsupported export target")
    if mode not in {"native", "flattened", "cutout", "stacked", "gap-filler"}:
        raise ValueError("unsupported export mode")
    native_svg = {"Circle", "Ring", "Ellipse", "Rectangle", "RoundedRect",
                  "TextLine", "CustomGlyph", "KnockoutText",
                  "OutlinedTextGroup", "ShadowedTextGroup",
                  "StrokeNetwork", "Solid", "Gradient",
                  "LayerStack", "Repeat", "Mirror", "Symbol", "Reference"}
    geometric = {"Circle", "Ring", "Ellipse", "Rectangle", "RoundedRect",
                 "Triangle", "Quadrilateral", "Star", "DBullet",
                 "FreeCurve", "StrokeNetwork"}
    rows = []; warnings = []
    for node in program.nodes:
        operator = node.operator
        export_operator = operator
        if mode == "flattened" and operator not in {"LayerStack", "HiddenCompletion"}:
            export_operator = "FlattenedCurve"
        elif target == "svg" and mode == "native" and operator not in native_svg:
            export_operator = "SVGPath"
        elif target in {"eps", "pdf"} and operator not in {"LayerStack", "Solid"}:
            export_operator = "PostScriptPath"
        elif target == "dxf" and operator not in geometric | {"LayerStack"}:
            export_operator = "DXFFlattenedGeometry"
            warnings.append(f"{node.id}:{operator} flattened for DXF")
        elif target == "png":
            export_operator = "RasterRenderNode"
        if mode == "gap-filler" and operator == "StrokeNetwork":
            export_operator = "GapFillerStroke"
        if mode in {"cutout", "stacked"} and operator == "LayerStack":
            export_operator = "CutoutStack" if mode == "cutout" else "StackedLayers"
        rows.append(ExportNode(
            id=node.id, operator=export_operator, parameters=node.parameters,
            children=node.children, source_program_node=node.id,
        ))
    result = ExportIR(
        schema="pcdc-xir/v1", target=target, mode=mode,
        nodes=tuple(rows), root_id=program.root_id,
        warnings=tuple(sorted(set(warnings))),
        source_program_digest=program.program_digest,
        provenance=(
            "one-DPIR-many-export-IRs", f"target:{target}", f"mode:{mode}",
        ),
    )
    result.validate()
    return result
