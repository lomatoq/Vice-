"""Exact owner masks for clean SVGs carrying the explicit-owner contract.

The licensed text data factory wraps every semantic text row in a named SVG
group.  Those names are ground truth: recovering the rows with connected
component heuristics would throw the very supervision the factory exists to
provide away.  This module isolates and renders each declared group while
retaining the original SVG coordinate system and definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import io
import re
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image


OWNER_CONTRACT = "explicit-groups/v1"
_OWNER_FAMILIES = {
    "text-line": "text_line",
    "glyph-group": "glyph_group",
    "whole-shape": "whole_shape",
}


def _number(value: str | None, default: float) -> float:
    match = re.match(r"\s*([-+0-9.eE]+)", str(value or ""))
    try:
        return float(match.group(1)) if match else float(default)
    except ValueError:
        return float(default)


def _aspect(root: ET.Element) -> float:
    values = str(root.attrib.get("viewBox", "")).replace(",", " ").split()
    if len(values) == 4:
        width = _number(values[2], 1.0)
        height = _number(values[3], 1.0)
    else:
        width = _number(root.attrib.get("width"), 256.0)
        height = _number(root.attrib.get("height"), 256.0)
    return max(1e-3, width / max(1e-3, height))


def _freeze(mask: np.ndarray) -> np.ndarray:
    result = np.ascontiguousarray(mask, dtype=bool)
    result.setflags(write=False)
    return result


def _render(root: ET.Element, *, width: int) -> np.ndarray:
    import resvg_py

    render_width = max(64, int(width))
    render_height = max(16, int(round(render_width / _aspect(root))))
    svg = ET.tostring(root, encoding="unicode")
    payload = resvg_py.svg_to_bytes(
        svg_string=svg, width=render_width, height=render_height,
    )
    with io.BytesIO(payload) as stream:
        with Image.open(stream) as rendered:
            with rendered.convert("RGBA") as converted:
                alpha = np.asarray(converted)[..., 3].copy()
    return alpha >= 48


@dataclass(frozen=True)
class ExplicitSvgOwner:
    owner_id: str
    family: str
    mask: np.ndarray


@dataclass(frozen=True)
class ExplicitSvgOwners:
    full_mask: np.ndarray
    owners: tuple[ExplicitSvgOwner, ...]

    def validate(self) -> None:
        if self.full_mask.ndim != 2 or self.full_mask.flags.writeable:
            raise ValueError("explicit SVG full mask must be immutable")
        if not np.any(self.full_mask) or not self.owners:
            raise ValueError("explicit SVG owner contract is empty")
        identifiers = [row.owner_id for row in self.owners]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("explicit SVG owner ids must be unique")
        union = np.zeros_like(self.full_mask)
        for owner in self.owners:
            if (
                not owner.owner_id or owner.family not in _OWNER_FAMILIES.values()
                or owner.mask.shape != self.full_mask.shape
                or owner.mask.flags.writeable or not np.any(owner.mask)
            ):
                raise ValueError("explicit SVG owner mask is malformed")
            if np.any(owner.mask & ~self.full_mask):
                raise ValueError("explicit SVG owner exceeds full support")
            union |= owner.mask
        uncovered = int(np.sum(self.full_mask & ~union))
        if uncovered > max(2, int(round(0.001 * np.sum(self.full_mask)))):
            raise ValueError("explicit SVG owners do not cover full support")


def has_explicit_owner_contract(svg: str) -> bool:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return False
    return root.attrib.get("data-pcdc-owner-contract") == OWNER_CONTRACT


def explicit_svg_owners(
    svg: str, *, render_width: int = 512,
) -> ExplicitSvgOwners:
    """Render each declared owner group under the original SVG transforms."""
    root = ET.fromstring(svg)
    if root.attrib.get("data-pcdc-owner-contract") != OWNER_CONTRACT:
        raise ValueError("SVG does not carry the explicit owner contract")
    declarations: list[tuple[str, str]] = []
    for element in root.iter():
        raw_family = element.attrib.get("data-pcdc-owner")
        if raw_family is None:
            continue
        family = _OWNER_FAMILIES.get(raw_family)
        owner_id = str(element.attrib.get("data-pcdc-owner-id", "")).strip()
        if family is None or not owner_id:
            raise ValueError("unsupported or unnamed explicit SVG owner")
        declarations.append((owner_id, family))
    if len({row[0] for row in declarations}) != len(declarations):
        raise ValueError("explicit SVG owner ids must be unique")

    full = _render(root, width=render_width)
    owners: list[ExplicitSvgOwner] = []
    for wanted_id, family in declarations:
        isolated = copy.deepcopy(root)
        for element in isolated.iter():
            if "data-pcdc-owner" not in element.attrib:
                continue
            if element.attrib.get("data-pcdc-owner-id") != wanted_id:
                element.set("display", "none")
        mask = _render(isolated, width=render_width)
        owners.append(ExplicitSvgOwner(wanted_id, family, _freeze(mask)))
    result = ExplicitSvgOwners(_freeze(full), tuple(owners))
    result.validate()
    return result
