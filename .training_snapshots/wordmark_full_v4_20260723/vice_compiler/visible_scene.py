"""Visible Scene IR produced by phase-2 exact ownership extraction."""

from __future__ import annotations

from dataclasses import dataclass

from .macro_ir import CandidateMacroIR, MacroCandidate
from .master_problem import MasterSolution


@dataclass(frozen=True)
class InterfaceGeometryAssignment:
    """The single geometry variable assigned to one internal interface."""

    interface_id: int
    cell_a: int
    cell_b: int
    owner_a: str
    owner_b: str
    geometry_id: str
    active_boundary: bool


@dataclass(frozen=True)
class CellPaintOwnership:
    """Opaque exact owner or a bounded ordered translucent contribution list."""

    cell_id: int
    opaque_owner: str | None
    translucent_contributors: tuple[str, ...]
    background_id: str | None
    contribution_limit: int


def _geometry_id(
    interface_id: int, owner_a: str, owner_b: str,
) -> str:
    mode = "boundary" if owner_a != owner_b else "continuation"
    return f"interface:{interface_id}:{mode}:{owner_a}:{owner_b}"


def _translucent_contributor_ids(candidate: MacroCandidate) -> tuple[str, ...]:
    if candidate.alpha_bounds[0] >= 0.9995:
        return ()
    parameters = dict(candidate.program.parameters)
    if candidate.program.operator == "Appearance/ordered_translucent_stack":
        try:
            count = int(parameters.get("layer_count", 0))
        except (TypeError, ValueError):
            count = 0
        if not 2 <= count <= 3:
            raise ValueError("ordered translucent macro has invalid bounded K")
        return tuple(f"{candidate.id}#layer-{index}" for index in range(count))
    return (candidate.id,)


@dataclass(frozen=True)
class VisibleSceneIR:
    source_sha256: str
    selected_macro_ids: tuple[str, ...]
    owner_by_leaf: tuple[str, ...]
    paint_ownership_by_leaf: tuple[CellPaintOwnership, ...]
    interface_geometry: tuple[InterfaceGeometryAssignment, ...]
    utility: float
    exact_cover: bool
    fallback_always_feasible: bool
    provenance: tuple[str, ...]

    def validate(self, cmir: CandidateMacroIR) -> None:
        if len(self.owner_by_leaf) != cmir.leaf_count:
            raise ValueError("VSIR owner vector size mismatch")
        if any(not owner for owner in self.owner_by_leaf):
            raise ValueError("VSIR has an unowned core cell")
        if len(self.paint_ownership_by_leaf) != cmir.leaf_count:
            raise ValueError("VSIR paint ownership vector size mismatch")
        if not self.exact_cover:
            raise ValueError("VSIR is not an exact visible cover")
        if len(self.interface_geometry) != cmir.interface_count:
            raise ValueError("VSIR interface geometry count mismatch")
        if len({row.geometry_id for row in self.interface_geometry}) != len(
            self.interface_geometry
        ):
            raise ValueError("VSIR assigns one geometry to multiple interfaces")
        lookup = cmir.by_id()
        for cell_id, paint in enumerate(self.paint_ownership_by_leaf):
            owner = self.owner_by_leaf[cell_id]
            if paint.cell_id != cell_id:
                raise ValueError("VSIR paint ownership cell id mismatch")
            alpha_min, _alpha_max = lookup[owner].alpha_bounds
            if alpha_min >= 0.9995:
                if (
                    paint.opaque_owner != owner
                    or paint.translucent_contributors
                    or paint.background_id is not None
                    or paint.contribution_limit != 0
                ):
                    raise ValueError("opaque cell has an invalid paint stack")
            else:
                expected_contributors = _translucent_contributor_ids(
                    lookup[owner]
                )
                if (
                    paint.opaque_owner is not None
                    or paint.translucent_contributors != expected_contributors
                    or not paint.background_id
                    or paint.contribution_limit != len(expected_contributors)
                ):
                    raise ValueError("translucent cell lacks a bounded paint stack")
        for interface_id, ((cell_a, cell_b), geometry) in enumerate(zip(
            cmir.interface_endpoints, self.interface_geometry,
        )):
            owner_a = self.owner_by_leaf[cell_a]
            owner_b = self.owner_by_leaf[cell_b]
            if (
                geometry.interface_id != interface_id
                or (geometry.cell_a, geometry.cell_b) != (cell_a, cell_b)
                or (geometry.owner_a, geometry.owner_b) != (owner_a, owner_b)
                or geometry.active_boundary != (owner_a != owner_b)
                or geometry.geometry_id
                != _geometry_id(interface_id, owner_a, owner_b)
            ):
                raise ValueError("VSIR interface geometry assignment mismatch")
            claims = (
                interface_id in lookup[owner_a].boundary_interfaces,
                interface_id in lookup[owner_b].boundary_interfaces,
            )
            if owner_a != owner_b and claims != (True, True):
                raise ValueError("active interface lacks symmetric geometry claims")
            if owner_a == owner_b and claims != (False, False):
                raise ValueError("absorbed interface was counted as a boundary")


def build_visible_scene(
    cmir: CandidateMacroIR, solution: MasterSolution
) -> VisibleSceneIR:
    if not solution.feasible or not solution.exact_cover:
        raise ValueError("cannot build VSIR from an infeasible master solution")
    lookup = cmir.by_id()
    owners = [""] * cmir.leaf_count
    for candidate_id in solution.selected_ids:
        candidate = lookup[candidate_id]
        bits = candidate.core_bits
        while bits:
            low = bits & -bits
            leaf = low.bit_length() - 1
            if owners[leaf]:
                raise ValueError("selected macros overlap in visible ownership")
            owners[leaf] = candidate_id
            bits ^= low
    interface_geometry = tuple(
        InterfaceGeometryAssignment(
            interface_id=interface_id,
            cell_a=cell_a,
            cell_b=cell_b,
            owner_a=owners[cell_a],
            owner_b=owners[cell_b],
            geometry_id=_geometry_id(
                interface_id, owners[cell_a], owners[cell_b],
            ),
            active_boundary=owners[cell_a] != owners[cell_b],
        )
        for interface_id, (cell_a, cell_b) in enumerate(
            cmir.interface_endpoints
        )
    )
    paint_ownership = tuple(
        CellPaintOwnership(
            cell_id=cell_id,
            opaque_owner=(
                owner if lookup[owner].alpha_bounds[0] >= 0.9995 else None
            ),
            translucent_contributors=(
                _translucent_contributor_ids(lookup[owner])
            ),
            background_id=(
                None
                if lookup[owner].alpha_bounds[0] >= 0.9995
                else "canvas-background"
            ),
            contribution_limit=(
                len(_translucent_contributor_ids(lookup[owner]))
            ),
        )
        for cell_id, owner in enumerate(owners)
    )
    scene = VisibleSceneIR(
        source_sha256=cmir.source_sha256,
        selected_macro_ids=solution.selected_ids,
        owner_by_leaf=tuple(owners),
        paint_ownership_by_leaf=paint_ownership,
        interface_geometry=interface_geometry,
        utility=solution.utility,
        exact_cover=solution.exact_cover,
        fallback_always_feasible=solution.fallback_always_feasible,
        provenance=(
            "phase2-global-extraction", "visible-before-hidden",
            "one-geometry-variable-per-internal-interface",
            "opaque-or-bounded-ordered-translucent-K<=3-plus-background",
        ),
    )
    scene.validate(cmir)
    return scene
