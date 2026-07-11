"""Generate an exact vector glyph corpus with rotation and subpixel phase.

Every output sample is still a transform-free, filled-path SVG that can be
passed directly to ``build_corner_dataset.py``.  Rotation and translation are
baked into the glyph outline with ``TransformPen`` *before* rasterisation.

``visible_svg_regions`` normally normalises an SVG to the painted path bounds.
That is desirable for ordinary artwork, but it would cancel a whole-glyph
subpixel translation.  Each generated path therefore contains two zero-area
anchor subpaths at opposite canvas corners.  They paint no pixels and create no
corner labels, while keeping a stable vector coordinate frame.  A phase of
``0.25`` consequently means exactly one quarter pixel when the dataset builder
uses ``--resolutions`` equal to ``--reference-resolution`` (and scales linearly
at other resolutions).

Example::

    python generate_rotated_glyph_pilot.py \
      --font C:/Windows/Fonts/arial.ttf \
      --chars ABCDEFGHIJKLMNOPQRSTUVWXYZaego \
      --angles=-30,-15,0,15,30 \
      --phases "0:0,0.25:0,0:0.25,0.5:0.5" \
      --reference-resolution 32
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Sequence
from xml.sax.saxutils import escape as xml_escape

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parent
DEFAULT_FONT = Path(r"C:/Windows/Fonts/arial.ttf")
DEFAULT_OUT = ROOT / "datasets" / "text_glyph_rotated_subpixel_pilot_sources"
DEFAULT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZaego"
DEFAULT_ANGLES = (-30.0, -15.0, 0.0, 15.0, 30.0)
DEFAULT_PHASES = ((0.0, 0.0), (0.25, 0.0), (0.0, 0.25), (0.5, 0.5))


def _canonical_float(value: float) -> str:
    """Stable, compact decimal representation for JSON, XML and filenames."""
    value = 0.0 if abs(value) < 5e-13 else float(value)
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _filename_number(value: float) -> str:
    text = _canonical_float(value)
    sign = "m" if text.startswith("-") else "p"
    return sign + text.lstrip("-").replace(".", "d")


def _unique(values: Iterable) -> list:
    out = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def parse_angles(spec: str) -> list[float]:
    values = _unique(float(item.strip()) for item in spec.split(",") if item.strip())
    if not values or any(not math.isfinite(value) for value in values):
        raise argparse.ArgumentTypeError("angles must be a non-empty list of finite degrees")
    return values


def parse_phases(spec: str) -> list[tuple[float, float]]:
    values: list[tuple[float, float]] = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        pieces = item.split(":")
        if len(pieces) != 2:
            raise argparse.ArgumentTypeError(
                "phases must use x:y pairs, for example 0:0,0.25:0.5"
            )
        pair = (float(pieces[0]), float(pieces[1]))
        if not all(math.isfinite(value) for value in pair):
            raise argparse.ArgumentTypeError("phase coordinates must be finite")
        values.append(pair)
    values = _unique(values)
    if not values:
        raise argparse.ArgumentTypeError("at least one phase pair is required")
    return values


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _font_names(font: TTFont) -> dict[str, str | None]:
    name = font["name"]
    return {
        "family": name.getDebugName(1),
        "subfamily": name.getDebugName(2),
        "full_name": name.getDebugName(4),
        "postscript_name": name.getDebugName(6),
    }


def _glyph_bounds(glyph, glyph_set) -> tuple[float, float, float, float] | None:
    pen = BoundsPen(glyph_set)
    glyph.draw(pen)
    return tuple(map(float, pen.bounds)) if pen.bounds is not None else None


def _matrix_for(
    bounds: tuple[float, float, float, float],
    canvas: float,
    angle_deg: float,
    phase_x: float,
    phase_y: float,
    reference_resolution: int,
) -> tuple[float, float, float, float, float, float]:
    """Return fontTools affine matrix: y-flip, vector rotate, then phase."""
    xmin, ymin, xmax, ymax = bounds
    cx, cy = (xmin + xmax) * 0.5, (ymin + ymax) * 0.5
    radians = math.radians(angle_deg)
    cosine, sine = math.cos(radians), math.sin(radians)
    shift_x = phase_x * canvas / reference_resolution
    shift_y = phase_y * canvas / reference_resolution
    center = canvas * 0.5

    # fontTools order is (xx, xy, yx, yy, dx, dy), i.e.
    # x' = xx*x + yx*y + dx and y' = xy*x + yy*y + dy.
    return (
        cosine,
        sine,
        sine,
        -cosine,
        center + shift_x - cosine * cx - sine * cy,
        center + shift_y - sine * cx + cosine * cy,
    )


def _canvas_for(
    bounds: tuple[float, float, float, float],
    phases: Sequence[tuple[float, float]],
    reference_resolution: int,
) -> float:
    """Square frame that fits every rotation and configured phase."""
    xmin, ymin, xmax, ymax = bounds
    diagonal = max(math.hypot(xmax - xmin, ymax - ymin), 1.0)
    guard = max(24.0, 0.10 * diagonal)
    max_phase = max(abs(value) for pair in phases for value in pair)
    denominator = 1.0 - 2.0 * max_phase / reference_resolution
    if denominator <= 0.1:
        raise ValueError(
            "phase is too large for the reference resolution; use subpixel values below half the resolution"
        )
    return (diagonal + 2.0 * guard) / denominator


def _transformed_bounds(glyph, glyph_set, matrix) -> tuple[float, float, float, float]:
    pen = BoundsPen(glyph_set)
    glyph.draw(TransformPen(pen, matrix))
    if pen.bounds is None:
        raise ValueError("transformed glyph has no bounds")
    return tuple(map(float, pen.bounds))


def _split_for(font_sha256: str, codepoint: int) -> str:
    # All angle/phase variants of one glyph must remain in one partition.
    token = f"{font_sha256}:{codepoint}".encode("ascii")
    bucket = int(hashlib.sha1(token).hexdigest()[:8], 16) % 100
    return "train" if bucket < 80 else "val" if bucket < 90 else "test"


def _prepare_output(out: Path) -> None:
    """Remove only files owned by an earlier manifest; reject mixed roots."""
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot safely reuse output with invalid manifest: {manifest_path}") from exc
        if previous.get("kind") != "exact-vector-rotated-subpixel-glyph-pilot":
            raise ValueError(f"refusing to mix generated glyphs with another dataset: {out}")
        resolved_out = out.resolve()
        for record in previous.get("records", []):
            relative = Path(str(record.get("file", "")))
            candidate = (out / relative).resolve()
            if (relative.suffix.lower() == ".svg" and candidate.is_relative_to(resolved_out)
                    and candidate.is_file()):
                candidate.unlink()
    leftovers = sorted(out.rglob("*.svg"))
    if leftovers:
        raise ValueError(
            f"output contains {len(leftovers)} untracked SVG file(s); choose a clean --out directory"
        )


def _svg(
    path_data: str,
    canvas: float,
    sample_metadata: dict,
) -> str:
    canvas_text = _canonical_float(canvas)
    metadata = xml_escape(json.dumps(sample_metadata, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")))
    # These zero-length subpaths only pin the analytic bbox.  They have no
    # filled area, so the dataset builder sees precisely one glyph region.
    anchors = f" M 0 0 L 0 0 M {canvas_text} {canvas_text} L {canvas_text} {canvas_text}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{canvas_text}" height="{canvas_text}" '
        f'viewBox="0 0 {canvas_text} {canvas_text}" '
        f'data-generator="exact-rotated-subpixel-glyph-v1">\n'
        f'  <metadata>{metadata}</metadata>\n'
        f'  <path fill="#111111" fill-rule="nonzero" d="{path_data}{anchors}"/>\n'
        f'</svg>\n'
    )


def generate(
    font_path: Path,
    out: Path,
    chars: str = DEFAULT_CHARS,
    angles: Sequence[float] = DEFAULT_ANGLES,
    phases: Sequence[tuple[float, float]] = DEFAULT_PHASES,
    reference_resolution: int = 32,
) -> dict:
    """Generate the corpus and return its deterministic manifest."""
    font_path = Path(font_path).resolve()
    out = Path(out)
    if reference_resolution < 8:
        raise ValueError("reference_resolution must be at least 8 pixels")
    angles = _unique(float(value) for value in angles)
    phases = _unique((float(x), float(y)) for x, y in phases)
    if not angles or not phases:
        raise ValueError("angles and phases must both be non-empty")
    if any(not math.isfinite(value) for value in angles):
        raise ValueError("angles must be finite")
    if any(not math.isfinite(value) for pair in phases for value in pair):
        raise ValueError("phases must be finite")
    chars = "".join(_unique(chars))
    if not chars:
        raise ValueError("chars must contain at least one character")

    _prepare_output(out)
    font_sha256 = _sha256(font_path)
    font = TTFont(font_path)
    try:
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap() or {}
        units_per_em = int(font["head"].unitsPerEm)
        font_info = {
            "path": str(font_path),
            "sha256": font_sha256,
            "units_per_em": units_per_em,
            **_font_names(font),
        }
        records: list[dict] = []
        skipped: list[dict] = []
        sample_index = 0

        for char_index, char in enumerate(chars):
            codepoint = ord(char)
            glyph_name = cmap.get(codepoint)
            if glyph_name is None:
                skipped.append({"char": char, "codepoint": codepoint, "reason": "missing-cmap"})
                continue
            glyph = glyph_set[glyph_name]
            bounds = _glyph_bounds(glyph, glyph_set)
            if bounds is None:
                skipped.append({"char": char, "codepoint": codepoint, "glyph": glyph_name,
                                "reason": "empty-outline"})
                continue
            canvas = _canvas_for(bounds, phases, reference_resolution)
            split = _split_for(font_sha256, codepoint)
            split_dir = out / split
            split_dir.mkdir(parents=True, exist_ok=True)

            for angle in angles:
                for phase_x, phase_y in phases:
                    matrix = _matrix_for(bounds, canvas, angle, phase_x, phase_y,
                                         reference_resolution)
                    transformed_bounds = _transformed_bounds(glyph, glyph_set, matrix)
                    txmin, tymin, txmax, tymax = transformed_bounds
                    if (txmin < -1e-5 or tymin < -1e-5 or
                            txmax > canvas + 1e-5 or tymax > canvas + 1e-5):
                        raise ValueError(
                            f"glyph U+{codepoint:04X} clips its fixed canvas at angle={angle}, "
                            f"phase=({phase_x},{phase_y})"
                        )

                    pen = SVGPathPen(glyph_set)
                    glyph.draw(TransformPen(pen, matrix))
                    path_data = pen.getCommands()
                    filename = (
                        f"{char_index:04d}_u{codepoint:06x}_"
                        f"a{_filename_number(angle)}_"
                        f"x{_filename_number(phase_x)}_y{_filename_number(phase_y)}.svg"
                    )
                    relative = Path(split) / filename
                    sample_metadata = {
                        "schema": "exact-rotated-subpixel-glyph-v1",
                        "font_sha256": font_sha256,
                        "font_postscript_name": font_info["postscript_name"],
                        "char": char,
                        "codepoint": codepoint,
                        "glyph": glyph_name,
                        "angle_deg_clockwise_svg": float(angle),
                        "phase_px_at_reference": [float(phase_x), float(phase_y)],
                        "reference_resolution": reference_resolution,
                        "split": split,
                    }
                    (out / relative).write_text(
                        _svg(path_data, canvas, sample_metadata), encoding="utf-8"
                    )
                    records.append({
                        "index": sample_index,
                        "char_index": char_index,
                        "char": char,
                        "codepoint": codepoint,
                        "glyph": glyph_name,
                        "file": relative.as_posix(),
                        "split": split,
                        "angle_deg_clockwise_svg": float(angle),
                        "phase_x_px": float(phase_x),
                        "phase_y_px": float(phase_y),
                        "reference_resolution": reference_resolution,
                        "canvas_units": float(canvas),
                        "affine_font_to_svg": [float(value) for value in matrix],
                        "transformed_glyph_bounds": [float(value) for value in transformed_bounds],
                    })
                    sample_index += 1
    finally:
        font.close()

    manifest = {
        "schema_version": 1,
        "kind": "exact-vector-rotated-subpixel-glyph-pilot",
        "generator": Path(__file__).name,
        "font": font_info,
        "characters": chars,
        "angles_deg_clockwise_svg": [float(value) for value in angles],
        "phases_px_at_reference": [[float(x), float(y)] for x, y in phases],
        "reference_resolution": reference_resolution,
        "phase_scaling": "phase_at_target = phase_px * target_resolution / reference_resolution",
        "split_policy": "sha1(font_sha256:codepoint), 80/10/10; variants grouped by glyph",
        "count": len(records),
        "skipped": skipped,
        "records": records,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--chars", default=DEFAULT_CHARS)
    parser.add_argument(
        "--angles", type=parse_angles,
        default=list(DEFAULT_ANGLES),
        metavar="DEG,DEG,...",
        help="clockwise SVG-space vector rotations",
    )
    parser.add_argument(
        "--phases", type=parse_phases,
        default=list(DEFAULT_PHASES),
        metavar="X:Y,X:Y,...",
        help="pixel phases at --reference-resolution",
    )
    parser.add_argument("--reference-resolution", type=int, default=32)
    args = parser.parse_args()
    result = generate(
        args.font, args.out, args.chars, args.angles, args.phases,
        args.reference_resolution,
    )
    print(json.dumps({
        "out": str(args.out.resolve()),
        "count": result["count"],
        "font": result["font"]["full_name"],
        "reference_resolution": result["reference_resolution"],
        "skipped": len(result["skipped"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
