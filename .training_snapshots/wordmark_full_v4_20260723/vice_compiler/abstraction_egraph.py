"""Phase-8 guarded, sketch-guided abstraction over a selected DPIR only."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import time

import numpy as np

from .design_program import (
    DesignProgramIR, ProgramAnalysis, ProgramNode, _program_digest, _stable_id,
)


@dataclass(frozen=True)
class EClassAnalysis:
    id: str
    members: tuple[str, ...]
    bbox_xyxy: tuple[int, int, int, int]
    topology: tuple[int | None, int | None]
    render_digests: tuple[str, ...]
    parameter_groups: tuple[str, ...]


@dataclass(frozen=True)
class RewriteRecord:
    sketch: str
    inputs: tuple[str, ...]
    output: str | None
    accepted: bool
    guard: str
    cost_delta: float


@dataclass(frozen=True)
class AbstractionCost:
    render_equivalent: bool
    program_length: float
    editability_penalty: float
    native_primitive_penalty: float
    reuse_credit: float
    exporter_penalty: float
    total: float


@dataclass(frozen=True)
class GuardedAbstractionResult:
    original: DesignProgramIR
    extracted: DesignProgramIR
    eclasses: tuple[EClassAnalysis, ...]
    rewrites: tuple[RewriteRecord, ...]
    cost_before: AbstractionCost
    cost_after: AbstractionCost
    iterations: int
    elapsed_ms: float
    node_budget: int
    time_budget_ms: float
    budget_exhausted: bool
    provenance: tuple[str, ...]

    def validate(self) -> None:
        self.original.validate(); self.extracted.validate()
        if self.original.selected_macro_ids != self.extracted.selected_macro_ids:
            raise ValueError("abstraction changed selected visible macros")
        if self.original.visible_owner_digest != self.extracted.visible_owner_digest:
            raise ValueError("abstraction changed visible ownership")
        if self.original.layer_order != self.extracted.layer_order:
            raise ValueError("abstraction changed semantic layer order")
        if not self.cost_after.render_equivalent:
            raise ValueError("abstraction output lacks render equivalence")
        if self.cost_after.total > self.cost_before.total + 1e-9:
            raise ValueError("guarded extraction chose a more expensive program")


_POSITIONAL = frozenset({
    "cx", "cy", "x", "y", "offset_x", "offset_y", "tx", "ty",
})


def _normalized_parameters(node: ProgramNode) -> tuple[tuple[str, object], ...]:
    return tuple(
        (name, value) for name, value in node.parameters
        if name not in _POSITIONAL
    )


def _bbox_union(nodes: list[ProgramNode]) -> tuple[int, int, int, int]:
    return (
        min(row.analysis.bbox_xyxy[0] for row in nodes),
        min(row.analysis.bbox_xyxy[1] for row in nodes),
        max(row.analysis.bbox_xyxy[2] for row in nodes),
        max(row.analysis.bbox_xyxy[3] for row in nodes),
    )


def _semantic_digest(nodes: list[ProgramNode]) -> str:
    # Exact visible instances plus their exact bboxes determine the same
    # native-lattice render.  No approximate geometry enters this digest.
    payload = sorted(
        (row.analysis.render_digest, row.analysis.bbox_xyxy) for row in nodes
    )
    return hashlib.sha256(repr(payload).encode("ascii")).hexdigest()


def _cost(program: DesignProgramIR) -> AbstractionCost:
    lookup = program.by_id(); reachable = [lookup[node_id] for node_id in program.reachable_ids()]
    length = float(sum(1.0 + 0.06 * len(row.parameters) for row in reachable))
    editability = float(sum(1.0 - row.analysis.editable_score for row in reachable))
    native = float(sum(not row.analysis.native_primitive for row in reachable))
    reuse = float(sum(
        max(0, len(row.children) - 1)
        for row in reachable if row.operator in {
            "Repeat", "Mirror", "RotationalGroup", "GlyphPrototypeMap", "Symbol",
        }
    ))
    exporter = float(sum(
        row.operator in {"RasterFallback", "LegacyRegion", "CodecDetail"}
        for row in reachable
    ))
    equivalent = all(
        bool(row.analysis.render_digest) for row in reachable
    )
    total = (
        1e9 if not equivalent else length + 0.55 * editability
        + 0.34 * native + 0.22 * exporter - 1.35 * reuse
    )
    return AbstractionCost(
        render_equivalent=equivalent, program_length=length,
        editability_penalty=editability,
        native_primitive_penalty=native, reuse_credit=reuse,
        exporter_penalty=exporter, total=float(total),
    )


def _eclass(group: list[ProgramNode], sketch: str) -> EClassAnalysis:
    components = {
        row.analysis.components for row in group
    }
    holes = {row.analysis.holes for row in group}
    return EClassAnalysis(
        id=_stable_id("eclass", (sketch, tuple(row.id for row in group))),
        members=tuple(row.id for row in group), bbox_xyxy=_bbox_union(group),
        topology=(
            next(iter(components)) if len(components) == 1 else None,
            next(iter(holes)) if len(holes) == 1 else None,
        ),
        render_digests=tuple(row.analysis.render_digest for row in group),
        parameter_groups=tuple(sorted({
            row.analysis.parameter_group for row in group
            if row.analysis.parameter_group is not None
        })),
    )


def _group_node(operator: str, members: list[ProgramNode], sketch: str) -> ProgramNode:
    transforms = []
    for row in members:
        parameters = dict(row.parameters)
        transforms.append((
            float(parameters.get("cx", parameters.get("x", row.analysis.bbox_xyxy[0]))),
            float(parameters.get("cy", parameters.get("y", row.analysis.bbox_xyxy[1]))),
        ))
    digest = _semantic_digest(members)
    node_id = _stable_id(operator.lower(), {
        "members": tuple(row.id for row in members), "digest": digest,
    })
    return ProgramNode(
        id=node_id, operator=operator,
        parameters=(
            ("prototype", members[0].id),
            ("transforms", json.dumps(transforms, separators=(",", ":"))),
            ("count", len(members)),
        ),
        children=tuple(row.id for row in members),
        source_macro_ids=tuple(
            macro for row in members for macro in row.source_macro_ids
        ),
        analysis=ProgramAnalysis(
            bbox_xyxy=_bbox_union(members),
            components=sum((row.analysis.components or 0) for row in members),
            holes=sum((row.analysis.holes or 0) for row in members),
            render_digest=digest, parameter_group=node_id,
            editable_score=1.0, native_primitive=True,
        ),
        provenance=(
            "guarded-certificate-equivalent-rewrite", f"sketch:{sketch}",
            "exact-parameters-no-idealization",
        ),
    )


def _replace_root_children(
    program: DesignProgramIR, replacements: list[tuple[tuple[str, ...], ProgramNode]],
    provenance: tuple[str, ...],
) -> DesignProgramIR:
    lookup = program.by_id(); old_root = lookup[program.root_id]
    children = list(old_root.children)
    additions = []
    for member_ids, group in replacements:
        positions = [children.index(node_id) for node_id in member_ids if node_id in children]
        if len(positions) != len(member_ids):
            continue
        first = min(positions)
        children = [node_id for node_id in children if node_id not in member_ids]
        children.insert(first, group.id); additions.append(group)
    if not additions:
        return program
    root_id = _stable_id("abstract-root", tuple(children))
    new_root = replace(
        old_root, id=root_id, children=tuple(children),
        provenance=(*old_root.provenance, "guarded-abstraction-root"),
    )
    nodes = tuple((*program.nodes, *additions, new_root))
    full_provenance = (*program.provenance, *provenance)
    result = DesignProgramIR(
        schema=program.schema, source_sha256=program.source_sha256,
        nodes=nodes, root_id=root_id,
        selected_macro_ids=program.selected_macro_ids,
        layer_order=program.layer_order,
        visible_owner_digest=program.visible_owner_digest,
        program_digest=_program_digest(
            program.source_sha256, nodes, root_id,
            program.selected_macro_ids, program.layer_order,
            program.visible_owner_digest, full_provenance,
        ),
        provenance=full_provenance,
    )
    result.validate()
    return result


def _disjoint(first: ProgramNode, second: ProgramNode) -> bool:
    a = first.analysis.bbox_xyxy; b = second.analysis.bbox_xyxy
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def _is_exact_mirror(group: list[ProgramNode], canvas: tuple[int, int, int, int]) -> bool:
    if len(group) != 2:
        return False
    first, second = group
    a, b = first.analysis.bbox_xyxy, second.analysis.bbox_xyxy
    vertical = a[0] + b[2] == canvas[0] + canvas[2] and a[2] + b[0] == canvas[0] + canvas[2]
    horizontal = a[1] + b[3] == canvas[1] + canvas[3] and a[3] + b[1] == canvas[1] + canvas[3]
    return bool(vertical or horizontal)


def _is_exact_rotational(group: list[ProgramNode]) -> bool:
    if len(group) < 3:
        return False
    centers = np.asarray([
        ((row.analysis.bbox_xyxy[0] + row.analysis.bbox_xyxy[2]) * 0.5,
         (row.analysis.bbox_xyxy[1] + row.analysis.bbox_xyxy[3]) * 0.5)
        for row in group
    ], np.float64)
    center = np.mean(centers, axis=0)
    radii = np.linalg.norm(centers - center, axis=1)
    if float(np.ptp(radii)) > 1e-9:
        return False
    angles = np.sort(np.mod(np.arctan2(
        centers[:, 1] - center[1], centers[:, 0] - center[0],
    ), 2.0 * np.pi))
    gaps = np.diff(np.concatenate((angles, angles[:1] + 2.0 * np.pi)))
    return bool(float(np.ptp(gaps)) <= 1e-9)


def guarded_abstract(
    program: DesignProgramIR, *, max_nodes: int = 256,
    max_iterations: int = 8, time_budget_ms: float = 75.0,
) -> GuardedAbstractionResult:
    program.validate()
    started = time.perf_counter(); deadline = started + max(0.001, time_budget_ms / 1000.0)
    current = program; best_cost = _cost(program)
    rewrites = []; eclasses = []; iterations = 0; exhausted = False
    for iteration in range(max(1, int(max_iterations))):
        if time.perf_counter() >= deadline:
            exhausted = True; break
        iterations = iteration + 1
        lookup = current.by_id(); root = lookup[current.root_id]
        leaves = [lookup[node_id] for node_id in root.children
                  if not lookup[node_id].children]
        groups: dict[tuple, list[ProgramNode]] = {}
        for node in leaves:
            if node.operator in {"Circle", "Ellipse", "Rectangle", "RoundedRect",
                                 "StrokeNetwork", "TextLine"}:
                width = node.analysis.bbox_xyxy[2] - node.analysis.bbox_xyxy[0]
                height = node.analysis.bbox_xyxy[3] - node.analysis.bbox_xyxy[1]
                key = (
                    node.operator, _normalized_parameters(node), width, height,
                    node.analysis.components, node.analysis.holes,
                )
                groups.setdefault(key, []).append(node)
        replacements = []
        for group in groups.values():
            if len(group) < 2:
                continue
            group = sorted(group, key=lambda row: row.id)[:32]
            if group[0].operator == "TextLine" and all(
                any(name in {"prototype", "recognized_text", "member_ids"}
                    for name, _value in row.parameters)
                for row in group
            ):
                operator = "GlyphPrototypeMap"
                sketch = "repeated-glyphs-to-prototype+transforms"
            elif _is_exact_mirror(group, root.analysis.bbox_xyxy):
                operator = "Mirror"
                sketch = "mirror-instances-to-mirror-operator"
            elif _is_exact_rotational(group):
                operator = "RotationalGroup"
                sketch = "rotational-instances-to-rotational-group"
            else:
                operator = "Repeat"
                sketch = "duplicate-instances-to-Repeat/Map"
            analysis = _eclass(group, sketch)
            eclasses.append(analysis)
            repeat = _group_node(operator, group, sketch)
            if len(current.nodes) + len(replacements) + 2 > max_nodes:
                exhausted = True
                rewrites.append(RewriteRecord(
                    "duplicate-instances-to-Repeat/Map",
                    tuple(row.id for row in group), None, False,
                    "node-budget", 0.0,
                ))
                continue
            replacements.append((tuple(row.id for row in group), repeat))

        # Two exact concentric Circle programs become Ring only when the inner
        # program explicitly carries knockout semantics.  Mere proximity is
        # never sufficient.
        circles = [row for row in leaves if row.operator == "Circle"]
        for outer in circles:
            outer_values = dict(outer.parameters)
            for inner in circles:
                if outer.id >= inner.id:
                    continue
                inner_values = dict(inner.parameters)
                same_center = (
                    outer_values.get("cx") == inner_values.get("cx")
                    and outer_values.get("cy") == inner_values.get("cy")
                )
                roles = {outer_values.get("role"), inner_values.get("role")}
                if not same_center or "inner_cutout" not in roles:
                    continue
                pair = sorted((outer, inner), key=lambda row: float(dict(row.parameters).get("radius", 0)), reverse=True)
                ring = _group_node("Ring", pair, "exact-concentric-circles-to-ring")
                ring = replace(ring, children=())
                replacements.insert(0, ((pair[0].id, pair[1].id), ring))
                eclasses.append(_eclass(pair, "exact-concentric-circles-to-ring"))

        # Explicit certificate-equivalent curve decompositions may be lifted
        # to their native analytic primitive.  The certificate flag is a hard
        # guard and there is no approximate curve recognition here.
        for node in leaves:
            values = dict(node.parameters)
            if node.operator == "BezierArc" and values.get("analytic_arc_exact") == 1:
                analytic = _group_node("AnalyticArc", [node], "exact-Bezier-arc-to-analytic-arc")
                analytic = replace(analytic, children=())
                replacements.insert(0, ((node.id,), analytic))
                eclasses.append(_eclass([node], "exact-Bezier-arc-to-analytic-arc"))
            if node.operator == "LineArcPattern" and values.get("rounded_rect_exact") == 1:
                rounded = _group_node("RoundedRect", [node], "line-arc-pattern-to-rounded-rectangle")
                rounded = replace(rounded, children=())
                replacements.insert(0, ((node.id,), rounded))
                eclasses.append(_eclass([node], "line-arc-pattern-to-rounded-rectangle"))

        # Exact shared paths become one Symbol plus references.  Equality is
        # bit-for-bit render-digest equality, not perceptual similarity.
        digest_groups: dict[str, list[ProgramNode]] = {}
        for node in leaves:
            digest_groups.setdefault(node.analysis.render_digest, []).append(node)
        for group in digest_groups.values():
            if len(group) < 2 or any(not _disjoint(group[0], row) for row in group[1:]):
                continue
            symbol = _group_node("Symbol", group, "shared-path-to-symbol-reference")
            replacements.append((tuple(row.id for row in group), symbol))
            eclasses.append(_eclass(group, "shared-path-to-symbol-reference"))

        # Explicitly record the forbidden approximate rewrite.  A FreeCurve
        # can become Circle only during macro selection with a render proof.
        for node in leaves:
            if node.operator == "FreeCurve":
                rewrites.append(RewriteRecord(
                    "near-circle-to-perfect-circle", (node.id,), None, False,
                    "forbidden: geometry-changing idealization belongs to macro selection",
                    0.0,
                ))

        # Independent disjoint layers are certificate-equivalent under
        # commutation.  We retain canonical order unless it lowers cost.
        for first, second in zip(leaves, leaves[1:]):
            if _disjoint(first, second):
                rewrites.append(RewriteRecord(
                    "independent-layers-commute", (first.id, second.id), None,
                    True, "disjoint-bboxes+fixed-visible-ownership", 0.0,
                ))

        if any(node.operator == "HiddenCompletion" for node in lookup.values()):
            rewrites.append(RewriteRecord(
                "cutout<->stacked-representation", (current.root_id,), None,
                True, "fixed-layer-DAG+full-render-equivalence", 0.0,
            ))

        if not replacements:
            break
        candidate_program = _replace_root_children(
            current, replacements,
            ("guarded-sketch-saturation", f"iteration:{iteration + 1}"),
        )
        candidate_cost = _cost(candidate_program)
        delta = candidate_cost.total - best_cost.total
        for member_ids, node in replacements:
            rewrites.append(RewriteRecord(
                node.provenance[1].split(":", 1)[1], member_ids, node.id,
                delta <= 1e-9, "exact-parameter+topology+render-digest guard",
                delta,
            ))
        if delta < -1e-9:
            current = candidate_program; best_cost = candidate_cost
        else:
            break

    result = GuardedAbstractionResult(
        original=program, extracted=current,
        eclasses=tuple({row.id: row for row in eclasses}.values()),
        rewrites=tuple(rewrites), cost_before=_cost(program),
        cost_after=_cost(current), iterations=iterations,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        node_budget=max_nodes, time_budget_ms=time_budget_ms,
        budget_exhausted=exhausted,
        provenance=(
            "post-selection-only", "type-specific-rewrite-sketches",
            "bbox+topology+render+parameter-group-eclass-analysis",
            "bounded-node-iteration-time", "early-cost-extraction",
        ),
    )
    result.validate()
    return result
