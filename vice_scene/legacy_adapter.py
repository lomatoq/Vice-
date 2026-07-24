"""Explicit, lazy legacy V-ICE candidate/fallback adapters."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .ingest import CanonicalRaster


@dataclass(frozen=True)
class LegacyResult:
    report: dict
    output_directory: Path
    mode: str


def run_legacy(image_path: Path, output_root: Path, *, mode: str = "paper-regions",
               extractor: str = "mininet", route: str = "auto") -> LegacyResult:
    from geometry_vectorizer import process

    report = process(image_path, output_root, smoothing=mode,
                     extractor=extractor, route=route)
    return LegacyResult(report, output_root / image_path.stem, mode)


def legacy_exact_font_available() -> bool:
    # Availability checks must not import svgpathtools/scipy on every non-text
    # image; that cold import alone used to add several seconds to a 32px job.
    return all(importlib.util.find_spec(name) is not None
               for name in ("fontTools", "svgpathtools", "text_substitution"))


def exact_font_substitutions(raster: CanonicalRaster) -> list[dict]:
    """Run the existing strict OCR/font-retrieval Path A on canonical pixels."""
    if not legacy_exact_font_available():
        return []
    import text_substitution

    rgba = (np.clip(raster.rgba_srgb_straight, 0.0, 1.0) * 255 + .5).astype(np.uint8)
    image = Image.fromarray(rgba, "RGBA")
    return text_substitution.try_substitute_lines(image, [])
