"""Phase-6 visible-support-first layer and occlusion solver.

The solver is intentionally downstream of exact visible extraction.  It may
orient front/back relations and propose typed hidden geometry, but it never
changes VSIR core ownership.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import itertools
import math

import cv2
import numpy as np

from .certificates import topology_signature
from .evidence_ir import RasterEvidenceIR
from .macro_ir import CandidateMacroIR, MacroCandidate, MacroKind
from .renderer_posterior import freeze_renderer_posterior
from .visible_scene import VisibleSceneIR


@dataclass(frozen=True)
class LayerOrderCue:
    back_id: str
    front_id: str
    confidence: float
    cue: str
    evidence_interfaces: tuple[int, ...] = ()


@dataclass(frozen=True)
class LayerOrderEdge:
    back_id: str
    front_id: str
    confidence: float
    cues: tuple[str, ...]
    evidence_interfaces: tuple[int, ...]


@dataclass(frozen=True)
class LayerOrderGraph:
    nodes: tuple[str, ...]
    edges: tuple[LayerOrderEdge, ...]
    rejected_cycle_edges: tuple[LayerOrderEdge, ...]
    back_to_front: tuple[str, ...]
    local_alternative_components: int
    orientation_objective: float

    def validate(self) -> None:
        positions = {node: index for index, node in enumerate(self.back_to_front)}
        if set(positions) != set(self.nodes) or len(positions) != len(self.nodes):
            raise ValueError("layer order is not a permutation of selected owners")
        for edge in self.edges:
            if positions[edge.back_id] >= positions[edge.front_id]:
                raise ValueError("layer graph is cyclic or topological order is invalid")
        if self.local_alternative_components < 0:
            raise ValueError("negative layer alternative count")
        if not math.isfinite(self.orientation_objective) or abs(
            self.orientation_objective
            - sum(edge.confidence for edge in self.edges)
        ) > 1e-9:
            raise ValueError("layer orientation objective is inconsistent")


@dataclass(frozen=True)
class HiddenShapeCompletion:
    source_macro_id: str
    occluder_macro_id: str
    primitive: str
    full_mask: np.ndarray
    hidden_mask: np.ndarray
    confidence: float
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class BackgroundProposal:
    kind: str
    owner_macro_id: str | None
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class FullLayerRenderCheck:
    valid: bool
    rendered_premultiplied_rgba: np.ndarray
    rmse: float
    baseline_rmse: float
    max_abs_error: float
    source_topology: tuple[int, int]
    baseline_topology: tuple[int, int]
    rendered_topology: tuple[int, int]
    posterior_digest: str
    owner_digest_before: str
    owner_digest_after: str
    opaque_occlusion_proof: bool
    hidden_pixels: int


@dataclass(frozen=True)
class LayeredScene:
    visible_scene: VisibleSceneIR
    order_graph: LayerOrderGraph
    order_cues: tuple[LayerOrderCue, ...]
    hidden_completions: tuple[HiddenShapeCompletion, ...]
    background_proposals: tuple[BackgroundProposal, ...]
    selected_background: BackgroundProposal
    render_check: FullLayerRenderCheck
    provenance: tuple[str, ...]

    def validate(self, reir: RasterEvidenceIR, cmir: CandidateMacroIR) -> None:
        self.visible_scene.validate(cmir)
        self.order_graph.validate()
        digest = _owner_digest(self.visible_scene.owner_by_leaf)
        if digest != self.render_check.owner_digest_before:
            raise ValueError("layer solver did not bind the input VSIR ownership")
        if digest != self.render_check.owner_digest_after:
            raise ValueError("layer solver mutated visible ownership")
        if not self.render_check.valid:
            raise ValueError("full layered render does not reproduce visible evidence")
        if self.hidden_completions and not self.render_check.opaque_occlusion_proof:
            raise ValueError("hidden completion lacks an opaque-occluder proof")
        for row in self.hidden_completions:
            if row.full_mask.shape != (reir.height, reir.width):
                raise ValueError("hidden completion is off the native lattice")
            if row.full_mask.flags.writeable or row.hidden_mask.flags.writeable:
                raise ValueError("hidden completion masks must be immutable")
            source = cmir.by_id()[row.source_macro_id]
            if source.kind is not MacroKind.SHAPE:
                raise ValueError("hidden completion is not a typed whole shape")


def _freeze(array: np.ndarray, dtype: np.dtype | type | None = None) -> np.ndarray:
    result = np.ascontiguousarray(array, dtype=dtype)
    result.setflags(write=False)
    return result


def _owner_digest(owners: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for owner in owners:
        digest.update(owner.encode("utf-8")); digest.update(b"\0")
    return digest.hexdigest()


def _owner_masks(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
) -> dict[str, np.ndarray]:
    labels = reir.hierarchy.leaf_labels
    if len(scene.owner_by_leaf) == reir.hierarchy.leaf_count:
        result = {}
        for leaf_id, owner in enumerate(scene.owner_by_leaf):
            result.setdefault(owner, np.zeros(labels.shape, bool))
            result[owner] |= labels == leaf_id
        return result
    result: dict[str, np.ndarray] = {}
    lookup = cmir.by_id()
    for owner in scene.selected_macro_ids:
        candidate = lookup[owner]
        certificate = candidate.certificates
        count = reir.width * reir.height
        if certificate.support_bits:
            mask = np.unpackbits(
                np.frombuffer(certificate.support_bits, np.uint8),
                count=count, bitorder="little",
            ).astype(bool).reshape((reir.height, reir.width))
        elif certificate.support_rle:
            flat = np.zeros(count, bool)
            for start, length in certificate.support_rle:
                flat[int(start):int(start) + int(length)] = True
            mask = flat.reshape((reir.height, reir.width))
        else:
            leaves = [
                leaf for leaf in range(reir.hierarchy.leaf_count)
                if candidate.core_bits & (1 << leaf)
            ]
            mask = np.isin(labels, leaves)
        result[owner] = np.asarray(mask, bool)
    return result


def _render_typed_shape(candidate: MacroCandidate, shape: tuple[int, int]) -> np.ndarray | None:
    if candidate.kind is not MacroKind.SHAPE or not candidate.program.operator.startswith("Shape/"):
        return None
    primitive = candidate.program.operator.split("/", 1)[1]
    values = dict(candidate.program.parameters)
    result = np.zeros(shape, np.uint8)

    def point(index: int) -> tuple[int, int] | None:
        x, y = values.get(f"p{index}_x"), values.get(f"p{index}_y")
        return None if x is None or y is None else (int(round(float(x))), int(round(float(y))))

    if primitive in {"circle", "ring"}:
        center = (int(round(float(values["cx"]))), int(round(float(values["cy"]))))
        cv2.circle(result, center, max(1, int(round(float(values["radius"])))), 1, -1, cv2.LINE_AA)
        if primitive == "ring":
            inner = (
                int(round(float(values["inner_cx"]))),
                int(round(float(values["inner_cy"]))),
            )
            cv2.circle(result, inner, max(1, int(round(float(values["inner_radius"])))), 0, -1, cv2.LINE_AA)
    elif primitive == "ellipse":
        cv2.ellipse(
            result,
            (int(round(float(values["cx"]))), int(round(float(values["cy"])))),
            (max(1, int(round(float(values["rx"])))), max(1, int(round(float(values["ry"]))))),
            float(values.get("angle", 0.0)), 0, 360, 1, -1, cv2.LINE_AA,
        )
    elif primitive in {"rectangle", "rounded_rectangle", "D_bullet"}:
        x = int(round(float(values["x"]))); y = int(round(float(values["y"])))
        width = max(1, int(round(float(values["width"]))))
        height = max(1, int(round(float(values["height"]))))
        if primitive == "rectangle":
            cv2.rectangle(result, (x, y), (x + width - 1, y + height - 1), 1, -1)
        elif primitive == "rounded_rectangle":
            radius = max(1, int(round(float(values["radius"]))))
            radius = min(radius, width // 2, height // 2)
            cv2.rectangle(result, (x + radius, y), (x + width - radius - 1, y + height - 1), 1, -1)
            cv2.rectangle(result, (x, y + radius), (x + width - 1, y + height - radius - 1), 1, -1)
            for cx, cy in ((x + radius, y + radius), (x + width - radius - 1, y + radius),
                           (x + radius, y + height - radius - 1),
                           (x + width - radius - 1, y + height - radius - 1)):
                cv2.circle(result, (cx, cy), radius, 1, -1, cv2.LINE_AA)
        else:
            radius = max(1, height // 2)
            side = str(values.get("round_side", "left"))
            if side == "left":
                center = (x + radius, y + (height - 1) // 2)
                cv2.rectangle(result, center, (x + width - 1, y + height - 1), 1, -1)
            else:
                center = (x + width - radius - 1, y + (height - 1) // 2)
                cv2.rectangle(result, (x, y), center, 1, -1)
            cv2.circle(result, center, radius, 1, -1, cv2.LINE_AA)
    elif primitive in {"triangle", "quadrilateral", "star"}:
        points = []
        for index in range(32):
            row = point(index)
            if row is None:
                break
            points.append(row)
        if len(points) >= 3:
            cv2.fillPoly(result, [np.asarray(points, np.int32)], 1, cv2.LINE_AA)
    else:
        return None
    return result > 0 if np.any(result) else None


def _interface_owner_pairs(
    cmir: CandidateMacroIR, scene: VisibleSceneIR,
) -> dict[tuple[str, str], list[int]]:
    pairs: dict[tuple[str, str], list[int]] = {}
    owners = scene.owner_by_leaf
    if len(owners) != cmir.leaf_count:
        raise ValueError("layer solver received a mismatched visible lattice")
    for interface_id, (cell_a, cell_b) in enumerate(cmir.interface_endpoints):
        first, second = owners[cell_a], owners[cell_b]
        if first == second:
            continue
        key = tuple(sorted((first, second)))
        pairs.setdefault(key, []).append(interface_id)
    return pairs


def propose_layer_order(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    owner_masks: dict[str, np.ndarray],
) -> tuple[LayerOrderCue, ...]:
    lookup = cmir.by_id()
    cues = []
    pairs = _interface_owner_pairs(cmir, scene)

    # Typed analytic overlap is direct occlusion evidence: the full shape
    # continues behind the currently visible owner.
    for source_id in scene.selected_macro_ids:
        source = lookup[source_id]
        full = _render_typed_shape(source, (reir.height, reir.width))
        if full is None:
            continue
        visible = owner_masks[source_id]
        hidden = full & ~visible
        for front_id, front_mask in owner_masks.items():
            overlap = int(np.sum(hidden & front_mask))
            if front_id != source_id and overlap >= 2:
                confidence = float(np.clip(0.82 + 0.16 * overlap / max(2, hidden.sum()), 0, 0.98))
                cues.append(LayerOrderCue(
                    source_id, front_id, confidence, "typed-contour-continuation",
                ))

    # Pairwise evidence from the finalized visible cells only.
    border = np.zeros((reir.height, reir.width), bool)
    border[[0, -1], :] = True; border[:, [0, -1]] = True
    original_endpoints = tuple(
        (row.cell_a, row.cell_b) for row in reir.interfaces.interfaces
    )
    for (first_id, second_id), interface_ids in pairs.items():
        first = lookup[first_id]; second = lookup[second_id]
        first_area = int(owner_masks[first_id].sum())
        second_area = int(owner_masks[second_id].sum())
        if first.kind is MacroKind.TEXT_LINE and second.kind is not MacroKind.TEXT_LINE:
            cues.append(LayerOrderCue(second_id, first_id, 0.90, "text-top-layer-prior", tuple(interface_ids)))
        elif second.kind is MacroKind.TEXT_LINE and first.kind is not MacroKind.TEXT_LINE:
            cues.append(LayerOrderCue(first_id, second_id, 0.90, "text-top-layer-prior", tuple(interface_ids)))
        first_border = int(np.sum(owner_masks[first_id] & border))
        second_border = int(np.sum(owner_masks[second_id] & border))
        if first_border > 0 and second_border == 0 and first_area >= second_area:
            cues.append(LayerOrderCue(first_id, second_id, 0.66, "border-connectivity", tuple(interface_ids)))
        elif second_border > 0 and first_border == 0 and second_area >= first_area:
            cues.append(LayerOrderCue(second_id, first_id, 0.66, "border-connectivity", tuple(interface_ids)))
        observations = (
            [reir.interfaces.interfaces[index] for index in interface_ids]
            if cmir.interface_endpoints == original_endpoints else []
        )
        boundary = float(np.mean([
            row.mean_boundary_probability for row in observations
        ])) if observations else 0.0
        uncertainty = float(np.mean([
            row.uncertainty for row in observations
        ])) if observations else 1.0
        if observations and boundary >= 0.38 and uncertainty <= 0.70:
            # Smaller uniform islands are a bounded T-junction/top-layer cue;
            # it remains soft and can lose to typed continuation or text.
            if first_area != second_area:
                back, front = (
                    (first_id, second_id) if first_area > second_area
                    else (second_id, first_id)
                )
                cues.append(LayerOrderCue(
                    back, front, float(np.clip(0.48 + 0.22 * boundary, 0, 0.72)),
                    "T-junction+uniform-appearance", tuple(interface_ids),
                ))
    return tuple(cues)


def _aggregate_cues(cues: tuple[LayerOrderCue, ...]) -> tuple[LayerOrderEdge, ...]:
    groups: dict[tuple[str, str], list[LayerOrderCue]] = {}
    for cue in cues:
        if cue.back_id != cue.front_id:
            groups.setdefault((cue.back_id, cue.front_id), []).append(cue)
    rows = []
    for (back, front), values in groups.items():
        confidence = 1.0 - math.prod(1.0 - row.confidence for row in values)
        rows.append(LayerOrderEdge(
            back, front, float(confidence),
            tuple(sorted({row.cue for row in values})),
            tuple(sorted({index for row in values for index in row.evidence_interfaces})),
        ))
    return tuple(sorted(rows, key=lambda row: (-row.confidence, row.back_id, row.front_id)))


def _would_cycle(adjacency: dict[str, set[str]], back: str, front: str) -> bool:
    stack = [front]; seen = set()
    while stack:
        node = stack.pop()
        if node == back:
            return True
        if node not in seen:
            seen.add(node); stack.extend(adjacency[node])
    return False


def solve_layer_order(
    selected_ids: tuple[str, ...], cues: tuple[LayerOrderCue, ...],
) -> LayerOrderGraph:
    nodes = tuple(sorted(selected_ids))
    node_set = set(nodes)
    evidence = tuple(
        edge for edge in _aggregate_cues(cues)
        if edge.back_id in node_set and edge.front_id in node_set
    )
    undirected = {node: set() for node in nodes}
    for edge in evidence:
        undirected[edge.back_id].add(edge.front_id)
        undirected[edge.front_id].add(edge.back_id)
    components: list[tuple[str, ...]] = []
    unseen = set(nodes)
    while unseen:
        seed = min(unseen); stack = [seed]; members = set()
        while stack:
            node = stack.pop()
            if node in members:
                continue
            members.add(node); unseen.discard(node)
            stack.extend(sorted(undirected[node] - members, reverse=True))
        components.append(tuple(sorted(members)))

    accepted: list[LayerOrderEdge] = []
    rejected: list[LayerOrderEdge] = []
    local_alternatives = 0
    for component in components:
        members = set(component)
        edges = tuple(
            edge for edge in evidence
            if edge.back_id in members and edge.front_id in members
        )
        if len(component) <= 8:
            best_order = component
            best_score = -1.0
            # Sparse layer components are deliberately tiny.  Exhaustive
            # local order search is deterministic and finds the maximum
            # confidence DAG instead of making cycle resolution depend on the
            # first greedy edge that happened to be inserted.
            for order in itertools.permutations(component):
                positions = {node: index for index, node in enumerate(order)}
                score = sum(
                    edge.confidence for edge in edges
                    if positions[edge.back_id] < positions[edge.front_id]
                )
                if score > best_score + 1e-12 or (
                    abs(score - best_score) <= 1e-12 and order < best_order
                ):
                    best_score = score; best_order = order
            positions = {node: index for index, node in enumerate(best_order)}
            kept = [
                edge for edge in edges
                if positions[edge.back_id] < positions[edge.front_id]
            ]
            dropped = [edge for edge in edges if edge not in kept]
            accepted.extend(kept); rejected.extend(dropped)
            local_alternatives += int(bool(dropped))
            continue

        # Hard bounded fallback for an unusually large interaction component.
        adjacency = {node: set() for node in component}
        for edge in edges:
            if _would_cycle(adjacency, edge.back_id, edge.front_id):
                rejected.append(edge)
            else:
                adjacency[edge.back_id].add(edge.front_id); accepted.append(edge)

    accepted.sort(key=lambda row: (-row.confidence, row.back_id, row.front_id))
    rejected.sort(key=lambda row: (-row.confidence, row.back_id, row.front_id))
    adjacency = {node: set() for node in nodes}
    for edge in accepted:
        adjacency[edge.back_id].add(edge.front_id)
    indegree = {node: 0 for node in nodes}
    for followers in adjacency.values():
        for node in followers:
            indegree[node] += 1
    ready = sorted(node for node, value in indegree.items() if value == 0)
    ordered = []
    while ready:
        node = ready.pop(0); ordered.append(node)
        for follower in sorted(adjacency[node]):
            indegree[follower] -= 1
            if indegree[follower] == 0:
                ready.append(follower); ready.sort()
    graph = LayerOrderGraph(
        nodes=nodes, edges=tuple(accepted), rejected_cycle_edges=tuple(rejected),
        back_to_front=tuple(ordered),
        local_alternative_components=local_alternatives,
        orientation_objective=float(sum(row.confidence for row in accepted)),
    )
    graph.validate()
    return graph


def _hidden_completions(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR,
    graph: LayerOrderGraph, owner_masks: dict[str, np.ndarray],
) -> tuple[HiddenShapeCompletion, ...]:
    lookup = cmir.by_id(); rows = []
    for edge in graph.edges:
        source = lookup[edge.back_id]
        front = lookup[edge.front_id]
        # A hierarchy/base colour cell is not an authored foreground layer;
        # using it as an occluder can expose a hidden carrier through omitted
        # background-colour subregions in the SVG writer.  Only an explicitly
        # typed, proof-carrying, opaque front macro can seal hidden geometry.
        if front.is_base:
            continue
        front_alpha = reir.raster.straight_rgba[..., 3][owner_masks[edge.front_id]]
        if not len(front_alpha) or float(np.min(front_alpha)) < 0.9995:
            continue
        full = _render_typed_shape(source, (reir.height, reir.width))
        if full is None:
            continue
        hidden = full & owner_masks[edge.front_id] & ~owner_masks[edge.back_id]
        if int(hidden.sum()) < 2:
            continue
        rows.append(HiddenShapeCompletion(
            source_macro_id=edge.back_id, occluder_macro_id=edge.front_id,
            primitive=source.program.operator.split("/", 1)[1],
            full_mask=_freeze(full, bool), hidden_mask=_freeze(hidden, bool),
            confidence=edge.confidence,
            provenance=("typed-shape-only", "after-visible-exact-cover", *edge.cues),
        ))
    return tuple(rows)


def _backgrounds(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    owner_masks: dict[str, np.ndarray],
) -> tuple[BackgroundProposal, ...]:
    rows = []
    alpha = reir.raster.straight_rgba[..., 3]
    corners = alpha[np.ix_([0, reir.height - 1], [0, reir.width - 1])]
    if float(np.mean(corners)) < 0.08:
        rows.append(BackgroundProposal(
            "transparent_canvas", None, 0.98,
            ("transparent-corners", "alpha-inclusion-tree"),
        ))
    border = np.zeros((reir.height, reir.width), bool)
    border[[0, -1], :] = True; border[:, [0, -1]] = True
    # A canvas is an appearance-supported connected region, not whichever
    # selected owner happens to touch the most edge pixels.  Estimate the
    # corner color, keep its connected components that reach a corner, and
    # register the canvas independently of the fragmented visible owners.
    lab = np.asarray(reir.raster.oklab, np.float32)
    corner_values = np.asarray((
        lab[0, 0], lab[0, -1], lab[-1, 0], lab[-1, -1],
    ))
    corner_color = np.median(corner_values, axis=0)
    canvas_seed = np.linalg.norm(lab - corner_color, axis=2) <= 0.045
    count, labels = cv2.connectedComponents(canvas_seed.astype(np.uint8), 8)
    corner_labels = {
        int(labels[y, x]) for y, x in (
            (0, 0), (0, reir.width - 1),
            (reir.height - 1, 0), (reir.height - 1, reir.width - 1),
        ) if int(labels[y, x]) > 0
    }
    canvas = np.isin(labels, tuple(corner_labels)) if corner_labels else np.zeros_like(border)
    canvas_border_fraction = float(np.sum(canvas & border) / max(1, np.sum(border)))
    canvas_corner_count = sum(bool(canvas[y, x]) for y, x in (
        (0, 0), (0, reir.width - 1),
        (reir.height - 1, 0), (reir.height - 1, reir.width - 1),
    ))
    if canvas_corner_count >= 3 and canvas_border_fraction >= 0.45:
        rows.append(BackgroundProposal(
            "uniform_border_connected_canvas", None,
            float(np.clip(0.80 + 0.18 * canvas_border_fraction, 0, 0.98)),
            (
                "corner-color-connectivity",
                f"border_fraction={canvas_border_fraction:.6f}",
                f"corner_count={canvas_corner_count}",
            ),
        ))
    ranked = sorted(
        ((int(np.sum(mask & border)), int(mask.sum()), owner) for owner, mask in owner_masks.items()),
        reverse=True,
    )
    if ranked and ranked[0][0] / max(1, int(border.sum())) >= 0.50:
        touches, area, owner = ranked[0]
        rows.append(BackgroundProposal(
            "uniform_border_connected_canvas", owner,
            float(np.clip(0.56 + 0.38 * touches / max(1, int(border.sum())), 0, 0.96)),
            ("border-connectivity", f"area={area}"),
        ))
    for owner, mask in owner_masks.items():
        touches = (
            np.any(mask[0]), np.any(mask[-1]), np.any(mask[:, 0]), np.any(mask[:, -1])
        )
        owner_border_fraction = float(np.sum(mask & border) / max(1, np.sum(border)))
        owner_corners = sum(bool(mask[y, x]) for y, x in (
            (0, 0), (0, reir.width - 1),
            (reir.height - 1, 0), (reir.height - 1, reir.width - 1),
        ))
        if all(touches) and (
            owner_border_fraction >= 0.75 or owner_corners >= 3
        ):
            rows.append(BackgroundProposal(
                "edge_to_edge_bottom_shape", owner, 0.78,
                (
                    "touches-all-canvas-edges",
                    f"border_fraction={owner_border_fraction:.6f}",
                    f"corner_count={owner_corners}",
                ),
            ))
        candidate = cmir.by_id()[owner]
        if (candidate.certificates.holes or 0) > 0:
            rows.append(BackgroundProposal(
                "local_knockout", owner, 0.62,
                ("typed-visible-hole", "knockout-not-eraser"),
            ))
    if not rows:
        rows.append(BackgroundProposal(
            "uniform_border_connected_canvas", ranked[0][2] if ranked else None,
            0.40, ("bounded-default-background-hypothesis",),
        ))
    return tuple(sorted(rows, key=lambda row: (-row.confidence, row.kind, row.owner_macro_id or "")))


def _full_render_check(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR,
    scene: VisibleSceneIR, graph: LayerOrderGraph,
    owner_masks: dict[str, np.ndarray], completions: tuple[HiddenShapeCompletion, ...],
) -> FullLayerRenderCheck:
    observed = reir.raster.linear_premultiplied_rgba
    lookup = cmir.by_id()
    full_by_owner: dict[str, np.ndarray] = {}
    for row in completions:
        previous = full_by_owner.get(row.source_macro_id)
        if previous is None:
            full_by_owner[row.source_macro_id] = row.full_mask

    def certificate_mask(candidate: MacroCandidate) -> np.ndarray:
        certificate = candidate.certificates
        count = reir.width * reir.height
        if certificate.support_bits:
            return np.unpackbits(
                np.frombuffer(certificate.support_bits, np.uint8),
                count=count, bitorder="little",
            ).astype(bool).reshape((reir.height, reir.width))
        if certificate.support_rle:
            flat = np.zeros(count, bool)
            for start, length in certificate.support_rle:
                flat[int(start):int(start) + int(length)] = True
            return flat.reshape((reir.height, reir.width))
        return owner_masks[candidate.id]

    def over(canvas: np.ndarray, mask: np.ndarray, color: np.ndarray) -> None:
        if not np.any(mask):
            return
        source = np.asarray(color, np.float32)
        alpha = float(np.clip(source[3], 0.0, 1.0))
        canvas[mask, :3] = source[:3] + canvas[mask, :3] * (1.0 - alpha)
        canvas[mask, 3] = alpha + canvas[mask, 3] * (1.0 - alpha)

    border_values = np.concatenate((
        observed[0], observed[-1], observed[:, 0], observed[:, -1],
    ), axis=0)
    background = np.median(border_values, axis=0)
    labels = reir.hierarchy.leaf_labels

    def compose(*, hidden: bool) -> np.ndarray:
        canvas = np.empty_like(observed)
        canvas[...] = background
        carriers = tuple(full_by_owner) if hidden else ()
        carrier_set = set(carriers)
        order = carriers + tuple(
            candidate_id for candidate_id in scene.selected_macro_ids
            if candidate_id not in carrier_set
        )
        for candidate_id in order:
            candidate = lookup[candidate_id]
            if candidate.kind in {
                MacroKind.ATOMIC_FALLBACK, MacroKind.LEGACY_REGION,
                MacroKind.HIERARCHY_REGION,
            }:
                if candidate.program.operator == "AtomicRefinedFallback":
                    mask = certificate_mask(candidate)
                    if np.any(mask):
                        over(canvas, mask, np.median(observed[mask], axis=0))
                    continue
                bits = candidate.core_bits
                while bits:
                    low = bits & -bits; leaf = low.bit_length() - 1; bits ^= low
                    mask = labels == leaf
                    if np.any(mask):
                        over(canvas, mask, np.median(observed[mask], axis=0))
                continue
            visible = certificate_mask(candidate)
            paint_mask = full_by_owner.get(candidate_id, visible) if hidden else visible
            if np.any(visible):
                over(canvas, paint_mask, np.median(observed[visible], axis=0))
        return canvas

    baseline = compose(hidden=False)
    rendered = compose(hidden=True)
    delta = observed - rendered
    rmse = float(np.sqrt(np.mean(np.square(delta))))
    baseline_rmse = float(np.sqrt(np.mean(np.square(observed - baseline))))
    maximum = float(np.max(np.abs(delta)))

    def ink_topology(premultiplied: np.ndarray) -> tuple[int, int]:
        alpha = np.clip(premultiplied[..., 3], 0.0, 1.0)
        straight_linear = np.zeros_like(premultiplied[..., :3])
        valid_alpha = alpha > 1e-6
        straight_linear[valid_alpha] = (
            premultiplied[..., :3][valid_alpha] / alpha[valid_alpha, None]
        )
        srgb = np.where(
            straight_linear <= 0.0031308,
            12.92 * straight_linear,
            1.055 * np.power(np.clip(straight_linear, 0.0, 1.0), 1 / 2.4) - 0.055,
        )
        border = np.concatenate((srgb[0], srgb[-1], srgb[:, 0], srgb[:, -1]))
        bg = np.median(border, axis=0)
        distance = np.linalg.norm(srgb - bg, axis=2)
        alpha_bg = float(np.median(alpha[[0, -1]][:, [0, -1]]))
        ink = (distance >= 0.12) | (np.abs(alpha - alpha_bg) >= 0.10)
        return topology_signature(ink)

    source_topology = ink_topology(observed)
    baseline_topology = ink_topology(baseline)
    rendered_topology = ink_topology(rendered)
    baseline_topology_error = sum(
        abs(a - b) for a, b in zip(baseline_topology, source_topology)
    )
    rendered_topology_error = sum(
        abs(a - b) for a, b in zip(rendered_topology, source_topology)
    )
    valid = bool(
        rmse <= baseline_rmse + 0.0025
        and rendered_topology_error <= baseline_topology_error
    )
    digest = _owner_digest(scene.owner_by_leaf)
    opaque_proof = all(
        (
            not lookup[row.occluder_macro_id].is_base
            and float(np.min(
                reir.raster.straight_rgba[..., 3][
                    owner_masks[row.occluder_macro_id]
                ]
            )) >= 0.9995
        )
        for row in completions
    )
    posterior = freeze_renderer_posterior(reir)
    return FullLayerRenderCheck(
        valid=valid,
        rendered_premultiplied_rgba=_freeze(rendered, np.float32),
        rmse=rmse, baseline_rmse=baseline_rmse, max_abs_error=maximum,
        source_topology=source_topology,
        baseline_topology=baseline_topology,
        rendered_topology=rendered_topology,
        posterior_digest=posterior.digest,
        owner_digest_before=digest, owner_digest_after=_owner_digest(scene.owner_by_leaf),
        opaque_occlusion_proof=bool(opaque_proof),
        hidden_pixels=int(sum(np.sum(row.hidden_mask) for row in completions)),
    )


def build_layered_scene(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
) -> LayeredScene:
    reir.validate(); cmir.validate(); scene.validate(cmir)
    owners_before = _owner_digest(scene.owner_by_leaf)
    owner_masks = _owner_masks(reir, cmir, scene)
    cues = propose_layer_order(reir, cmir, scene, owner_masks)
    graph = solve_layer_order(scene.selected_macro_ids, cues)
    completions = _hidden_completions(reir, cmir, graph, owner_masks)
    backgrounds = _backgrounds(reir, cmir, scene, owner_masks)
    render = _full_render_check(reir, cmir, scene, graph, owner_masks, completions)
    if owners_before != _owner_digest(scene.owner_by_leaf):
        raise RuntimeError("layer inference mutated finalized visible support")
    result = LayeredScene(
        visible_scene=scene, order_graph=graph, order_cues=cues,
        hidden_completions=completions, background_proposals=backgrounds,
        selected_background=backgrounds[0], render_check=render,
        provenance=(
            "visible-support-finalized-first", "confidence-weighted-sparse-DAG",
            "typed-hidden-shapes-only", "full-layer-render-checked",
        ),
    )
    result.validate(reir, cmir)
    return result


def rekey_layered_scene(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR,
    layered: LayeredScene, scene: VisibleSceneIR,
    id_map: dict[str, str],
) -> LayeredScene:
    """Rebind an unchanged layer proof after immutable macro re-keying.

    The visible leaf partition and all layer evidence stay fixed.  A refined
    source that owns a hidden completion is deliberately rejected here: its
    new full geometry requires a fresh full-layer court, not identifier
    substitution.
    """
    if any(row.source_macro_id in id_map for row in layered.hidden_completions):
        raise ValueError("refined hidden carrier requires a fresh layer court")

    def key(value: str) -> str:
        return id_map.get(value, value)

    graph = replace(
        layered.order_graph,
        nodes=tuple(key(value) for value in layered.order_graph.nodes),
        edges=tuple(replace(
            row, back_id=key(row.back_id), front_id=key(row.front_id),
        ) for row in layered.order_graph.edges),
        rejected_cycle_edges=tuple(replace(
            row, back_id=key(row.back_id), front_id=key(row.front_id),
        ) for row in layered.order_graph.rejected_cycle_edges),
        back_to_front=tuple(
            key(value) for value in layered.order_graph.back_to_front
        ),
    )
    cues = tuple(replace(
        row, back_id=key(row.back_id), front_id=key(row.front_id),
    ) for row in layered.order_cues)
    completions = tuple(replace(
        row, source_macro_id=key(row.source_macro_id),
        occluder_macro_id=key(row.occluder_macro_id),
    ) for row in layered.hidden_completions)
    backgrounds = tuple(replace(
        row,
        owner_macro_id=(
            key(row.owner_macro_id) if row.owner_macro_id is not None else None
        ),
    ) for row in layered.background_proposals)
    selected_background = replace(
        layered.selected_background,
        owner_macro_id=(
            key(layered.selected_background.owner_macro_id)
            if layered.selected_background.owner_macro_id is not None else None
        ),
    )
    digest = _owner_digest(scene.owner_by_leaf)
    render_check = replace(
        layered.render_check,
        owner_digest_before=digest, owner_digest_after=digest,
    )
    result = replace(
        layered, visible_scene=scene, order_graph=graph, order_cues=cues,
        hidden_completions=completions, background_proposals=backgrounds,
        selected_background=selected_background, render_check=render_check,
        provenance=(*layered.provenance, "immutable-macro-id-rekey"),
    )
    result.validate(reir, cmir)
    return result
