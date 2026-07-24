"""Resolve frozen V-ICE Best artifacts for proof-carrying fallback.

The PCDC plan requires the real production baseline to remain an always-valid
scene.  A REIR recolouring is not that baseline.  This module deliberately
only imports a completed, vector-only V-ICE Best SVG whose case/source identity
and native canvas agree with the current request.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from .evidence_ir import RasterEvidenceIR


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (PROJECT / "benchmarks" / "vai_work" / "paper-regions",)


@dataclass(frozen=True)
class LegacyBestArtifact:
    path: Path
    sha256: str
    width: int
    height: int
    source_name: str


def canonical_case_stem(source: Path) -> str:
    stem = source.stem
    stem = re.sub(r"^\d+_", "", stem)
    stem = re.sub(r"_src$", "", stem)
    return stem


def _svg_canvas(payload: str) -> tuple[int, int] | None:
    opening = re.search(r"<svg\b[^>]*>", payload, flags=re.IGNORECASE)
    if opening is None:
        return None
    tag = opening.group(0)
    view_box = re.search(
        r"\bviewBox\s*=\s*['\"]\s*[-+0-9.eE]+\s+[-+0-9.eE]+\s+"
        r"([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*['\"]",
        tag, flags=re.IGNORECASE,
    )
    if view_box is not None:
        return int(round(float(view_box.group(1)))), int(round(float(view_box.group(2))))
    width = re.search(r"\bwidth\s*=\s*['\"]([0-9.]+)", tag, flags=re.IGNORECASE)
    height = re.search(r"\bheight\s*=\s*['\"]([0-9.]+)", tag, flags=re.IGNORECASE)
    if width is None or height is None:
        return None
    return int(round(float(width.group(1)))), int(round(float(height.group(1))))


class LegacyBestResolver:
    """Content-checked lookup for already frozen production artifacts.

    Lookup is O(number of configured roots), never a recursive corpus scan.
    Unknown inputs fail closed to the atomic PCDC fallback; the production web
    route remains V-ICE Best until Phase 12 promotion.
    """

    def __init__(self, roots: tuple[Path, ...] = DEFAULT_ROOTS) -> None:
        self.roots = tuple(Path(root) for root in roots)

    def resolve(
        self, source: Path, reir: RasterEvidenceIR,
    ) -> LegacyBestArtifact | None:
        case = canonical_case_stem(source)
        candidates = [
            root / case / source.stem / "03_rebuilt_filled.svg"
            for root in self.roots
        ]
        # Challenge115 keeps its frozen V-ICE Best next to ``eval/crops`` in
        # ``eval/ours/itemNNN/itemNNN``.  This is an explicit deterministic
        # layout, not a recursive search or a best-looking artifact choice.
        if source.parent.name == "crops" and source.parent.parent.name == "eval":
            candidates.append(
                source.parent.parent / "ours" / source.stem / source.stem
                / "03_rebuilt_filled.svg"
            )
        for svg in candidates:
            report = svg.with_name("report.json")
            if not svg.is_file() or not report.is_file():
                continue
            try:
                report_text = report.read_text("utf-8")
                if f'"input": "{source.name}"' not in report_text:
                    continue
                raw = svg.read_bytes()
                text = raw.decode("utf-8")
                if re.search(r"<image\b", text, flags=re.IGNORECASE):
                    continue
                canvas = _svg_canvas(text)
                if canvas != (reir.width, reir.height):
                    continue
                return LegacyBestArtifact(
                    path=svg.resolve(), sha256=hashlib.sha256(raw).hexdigest(),
                    width=canvas[0], height=canvas[1], source_name=source.name,
                )
            except (OSError, UnicodeError, ValueError):
                continue
        return None
