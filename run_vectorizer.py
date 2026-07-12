"""Command-line launcher for the geometry-first vectorizer.

Run one or more image files (or folders / globs) through ``process`` without the
web server, choose the extractor and one or more smoothing modes, and get a
side-by-side contact sheet (source | contour | rebuilt) for quick A/B review.

Examples
--------
    # single file, perceptual colour pipeline
    python run_vectorizer.py web_preview/uploads/117_icon_group_6_src.png

    # compare two modes on the same file -> one contact sheet per file
    python run_vectorizer.py my_logo.png --smoothing perceptual,cad

    # every image in a folder, custom output tag, open the folder afterwards
    python run_vectorizer.py ./web_preview/uploads --tag batch1 --open

On Windows just use Run-Vectorizer.ps1, which picks the right interpreter.
"""

from __future__ import annotations

import argparse
import glob as globlib
import sys
import traceback
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from geometry_vectorizer import process  # noqa: E402

# The modes the underlying pipeline actually understands (mirrors server.py).
SMOOTHING_MODES = ["none", "corner", "chaikin", "bspline", "cad", "uncertainty",
                   "perceptual", "perceptual-icm", "perceptual-merge", "paper",
                   "paper-native", "paper-perc", "paper-perres", "paper-regions"]
EXTRACTORS = ["mininet", "palette"]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PANEL_HEIGHT = 260  # contact-sheet row height in pixels


def collect_inputs(raw: list[str]) -> list[Path]:
    """Expand files, directories and glob patterns into a de-duplicated list."""
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen and resolved.suffix.lower() in IMAGE_SUFFIXES and resolved.is_file():
            seen.add(resolved)
            found.append(resolved)

    for item in raw:
        candidate = Path(item)
        if candidate.is_dir():
            for child in sorted(candidate.iterdir()):
                add(child)
        elif candidate.is_file():
            add(candidate)
        else:
            # Treat as a glob (handles absolute patterns and ** on Windows).
            matches = sorted(globlib.glob(item, recursive=True))
            if not matches:
                print(f"  ! no match for '{item}'", file=sys.stderr)
            for match in matches:
                add(Path(match))
    return found


def load_rgb(path: Path) -> Image.Image:
    """Open any image and flatten transparency onto white, like the pipeline."""
    image = Image.open(path).convert("RGBA")
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image)
    return canvas.convert("RGB")


def _fit(image: Image.Image, height: int) -> Image.Image:
    scale = height / image.height
    width = max(1, round(image.width * scale))
    # Crisp pixels when upscaling small icons; smooth when shrinking big ones.
    resample = Image.Resampling.NEAREST if scale >= 1 else Image.Resampling.LANCZOS
    return image.resize((width, height), resample)


def _caption(width: int, text: str) -> Image.Image:
    strip = Image.new("RGB", (width, 20), (245, 245, 247))
    draw = ImageDraw.Draw(strip)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    draw.text((4, 3), text, fill=(30, 30, 34), font=font)
    return strip


def contact_sheet(panels: list[tuple[str, Image.Image]], gap: int = 8) -> Image.Image:
    """Horizontally tile captioned panels, all normalised to one row height."""
    tiles: list[Image.Image] = []
    for label, image in panels:
        fitted = _fit(image, PANEL_HEIGHT)
        tile = Image.new("RGB", (fitted.width, PANEL_HEIGHT + 20), (255, 255, 255))
        tile.paste(fitted, (0, 0))
        tile.paste(_caption(fitted.width, label), (0, PANEL_HEIGHT))
        tiles.append(tile)
    total_width = sum(tile.width for tile in tiles) + gap * (len(tiles) + 1)
    sheet = Image.new("RGB", (total_width, PANEL_HEIGHT + 20 + gap * 2), (255, 255, 255))
    x = gap
    for tile in tiles:
        sheet.paste(tile, (x, gap))
        x += tile.width + gap
    return sheet


def run_one(source: Path, out_root: Path, modes: list[str], extractor: str, make_sheet: bool) -> None:
    print(f"\n> {source.name}")
    panels: list[tuple[str, Image.Image]] = [("source", load_rgb(source))]
    for mode in modes:
        mode_root = out_root / mode
        try:
            report = process(source, mode_root, extractor=extractor, smoothing=mode)
        except Exception as exc:  # keep going with the remaining modes / files
            print(f"    [{mode:11}] FAILED: {exc}")
            traceback.print_exc()
            continue
        stem_dir = mode_root / source.stem
        regions = report.get("regions")
        contours = report.get("closed_contours")
        prims = report.get("rendered_primitive_count")
        used = report.get("extractor_used", extractor)
        print(f"    [{mode:11}] regions={regions} contours={contours} prims={prims} "
              f"extractor={used}  -> {stem_dir}")
        if make_sheet:
            rebuilt = stem_dir / "03_rebuilt_filled.png"
            if rebuilt.is_file():
                panels.append((f"{mode} · {regions}r/{contours}c", Image.open(rebuilt).convert("RGB")))
    if make_sheet and len(panels) > 1:
        sheet_path = out_root / f"{source.stem}__contact.png"
        contact_sheet(panels).save(sheet_path)
        print(f"    contact sheet -> {sheet_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the geometry-first vectorizer on files from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("inputs", nargs="+", help="image files, folders or glob patterns")
    parser.add_argument("--smoothing", "-s", default="paper-regions",
                        help=f"one or more comma-separated modes ({', '.join(SMOOTHING_MODES)}); "
                             "default paper-regions (the flagship Hoshyari pipeline + shared-interface graph)")
    parser.add_argument("--extractor", "-e", default="mininet", choices=EXTRACTORS,
                        help="mask extractor (default mininet)")
    parser.add_argument("--corner-model", type=Path, default=None,
                        help="optional CNN checkpoint for an isolated A/B run")
    parser.add_argument("--corner-threshold", type=float, default=None,
                        help="optional CNN threshold for an isolated A/B run")
    parser.add_argument(
        "--corner-postprocess",
        choices=["production", "tiny-safe", "cnn-conservative"],
        default="production",
        help="isolated corner postprocess A/B policy (default: production)",
    )
    parser.add_argument(
        "--paper-fit-profile",
        choices=["production", "text-safe"],
        default="production",
        help="isolated final-fit fallback policy (default: production)",
    )
    parser.add_argument("--debug-corner-routing", action="store_true")
    parser.add_argument("--out", "-o", default=str(ROOT / "test_runs"),
                        help="output root directory (default ./test_runs)")
    parser.add_argument("--tag", "-t", default="manual",
                        help="subfolder under --out for this run (default 'manual')")
    parser.add_argument("--no-contact", action="store_true", help="skip contact-sheet generation")
    parser.add_argument("--open", action="store_true", help="open the output folder when finished (Windows)")
    args = parser.parse_args()

    if args.corner_model is not None:
        if not args.corner_model.is_file():
            parser.error(f"corner checkpoint does not exist: {args.corner_model}")
        import corner_cnn
        corner_cnn.CNN_PATH = args.corner_model.resolve()
        corner_cnn._MODELS.clear()
        import geometry_vectorizer as gv
        gv._CNN_HYBRID_MODEL_PATH = args.corner_model.resolve()
        gv._CNN_HYBRID_CUTOFF = 0.0
        print(f"Corner CNN override: {corner_cnn.CNN_PATH}")
    if args.corner_threshold is not None:
        if not 0.0 < args.corner_threshold < 1.0:
            parser.error("--corner-threshold must be in (0, 1)")
        import geometry_vectorizer as gv
        gv._CNN_LAX_THRESHOLD = float(args.corner_threshold)
        gv._CNN_HYBRID_THRESHOLD = float(args.corner_threshold)
        print(f"Corner threshold override: {gv._CNN_LAX_THRESHOLD:.3f}")
    if args.corner_postprocess != "production":
        import geometry_vectorizer as gv
        gv._CORNER_POSTPROCESS_POLICY = args.corner_postprocess
        print(f"Corner postprocess override: {gv._CORNER_POSTPROCESS_POLICY}")
    if args.paper_fit_profile != "production":
        import geometry_vectorizer as gv
        gv._PAPER_FIT_PROFILE = args.paper_fit_profile
        print(f"Paper fit profile override: {gv._PAPER_FIT_PROFILE}")
    if args.debug_corner_routing:
        import geometry_vectorizer as gv
        gv._DEBUG_CORNER_ROUTING = True

    modes = [m.strip() for m in args.smoothing.split(",") if m.strip()]
    unknown = [m for m in modes if m not in SMOOTHING_MODES]
    if unknown:
        parser.error(f"unknown smoothing mode(s): {', '.join(unknown)}. Valid: {', '.join(SMOOTHING_MODES)}")

    inputs = collect_inputs(args.inputs)
    if not inputs:
        parser.error("no readable image files matched the given inputs")

    out_root = Path(args.out) / args.tag
    out_root.mkdir(parents=True, exist_ok=True)
    print(f"Vectorizer launcher: {len(inputs)} file(s), modes={modes}, extractor={args.extractor}")
    print(f"Output: {out_root}")

    for source in inputs:
        run_one(source, out_root, modes, args.extractor, make_sheet=not args.no_contact)

    print(f"\nDone. Results in {out_root}")
    if args.open:
        try:
            import os
            os.startfile(out_root)  # type: ignore[attr-defined]  # Windows only
        except Exception:
            print(f"(could not auto-open {out_root})")


if __name__ == "__main__":
    main()
