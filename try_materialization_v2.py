"""Try Materialization v2 on YOUR OWN picture.

Compiles one image twice through the PCDC runtime - once with the current
delivery, once with Materialization v2 - and writes a side-by-side page
with a zoom control, because the whole difference lives at zoom: the
delivered pixels are the same, the geometry is not.

Usage:
  C:\\Python312\\python.exe try_materialization_v2.py --input "C:\\path\\to\\your.png"
  C:\\Python312\\python.exe try_materialization_v2.py --input a.png --mode max --open
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import os
import shutil
import tempfile
import time
import webbrowser
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "web_preview" / "my_materialization_ab.html"


def _svg_of(result) -> str:
    from vice_compiler.export_writer import scene_to_svg

    # scene_to_svg returns (document, native_count, fallback_count).
    document, _native, _fallback = scene_to_svg(
        result.reir, result.cmir, result.visible_scene,
        phase5_bundle=result.phase5_bundle, text_macros=result.text_macros,
        layered_scene=result.layered_scene,
        design_program=result.design_program,
    )
    return document


def _compile_once(path: Path, mode: str, *, v2: bool):
    """One isolated compile.

    A fresh service per run on a uniquely named copy of the input: the
    persistent service caches by source, so reusing it silently returned
    the FIRST result for the second run and made the two deliveries look
    identical when they were not.
    """
    from vice_compiler.runtime_service import PersistentCompilerService

    previous = os.environ.get("VICE_TEXT_MATERIALIZATION_V2")
    os.environ["VICE_TEXT_MATERIALIZATION_V2"] = "1" if v2 else "0"
    started = time.perf_counter()
    service = PersistentCompilerService()
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / (
            f"{'v2' if v2 else 'v1'}-{path.name}"
        )
        shutil.copyfile(path, copy)
        try:
            result = service.compile(copy, mode=mode)
            svg = _svg_of(result)
        finally:
            close = getattr(service, "close", None)
            if callable(close):
                close()
            if previous is None:
                os.environ.pop("VICE_TEXT_MATERIALIZATION_V2", None)
            else:
                os.environ["VICE_TEXT_MATERIALIZATION_V2"] = previous
    return svg, (time.perf_counter() - started) * 1000.0, result


def _source_uri(path: Path) -> tuple[str, int, int]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        buffer = io.BytesIO()
        rgba.save(buffer, format="PNG")
        size = rgba.size
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}", size[0], size[1]


def _commands(svg: str) -> int:
    return sum(svg.count(letter) for letter in "MLCAHVQSTZ")


def _families(svg: str) -> str:
    import re

    found = sorted(set(re.findall(
        r'data-pcdc-text-geometry="([^"]+)"', svg,
    )))
    return ", ".join(found) if found else "—"


def build(input_path: Path, mode: str) -> Path:
    source_uri, width, height = _source_uri(input_path)
    print("compiling (current delivery)...")
    svg_v1, ms_v1, _result_v1 = _compile_once(input_path, mode, v2=False)
    print("compiling (materialization v2)...")
    svg_v2, ms_v2, _result_v2 = _compile_once(input_path, mode, v2=True)

    identical = svg_v1 == svg_v2
    page = f"""<!doctype html>
<meta charset="utf-8">
<title>{html.escape(input_path.name)} — Materialization v2</title>
<style>
 body {{ background:#101216; color:#e8e8ea; font:14px/1.5 system-ui, sans-serif;
        margin:0; padding:20px; }}
 h1 {{ font-size:17px; margin:0 0 6px; }}
 .meta {{ color:#8d94a0; font-size:12px; margin-bottom:14px; }}
 .controls {{ position:sticky; top:0; background:#101216; padding:10px 0;
              z-index:5; }}
 input[type=range] {{ width:300px; vertical-align:middle; }}
 .row {{ display:flex; gap:18px; align-items:flex-start; flex-wrap:wrap; }}
 figure {{ margin:0; }}
 figcaption {{ font-size:12px; color:#9aa0aa; margin-bottom:6px; }}
 .box {{ background:#fff; border-radius:8px; overflow:auto;
         border:1px solid #262a33; }}
 .box svg, .box img {{ display:block; image-rendering:pixelated; }}
 .warn {{ color:#f0b866; }}
</style>
<h1>{html.escape(input_path.name)} — цяпер супраць Materialization v2</h1>
<div class="meta">
  {width}&times;{height} &middot; рэжым {html.escape(mode)} &middot;
  path-камандаў <b>{_commands(svg_v1)}</b> &rarr; <b>{_commands(svg_v2)}</b>
  &middot; геаметрыя тэксту: {html.escape(_families(svg_v1))} &rarr;
  {html.escape(_families(svg_v2))} &middot;
  {ms_v1:.0f} ms &rarr; {ms_v2:.0f} ms
  {'<span class="warn">&middot; вынік не змяніўся: на гэтай карцінцы маршрут v2 не спрацаваў</span>' if identical else ''}
</div>
<div class="controls">
  маштаб <input id="zoom" type="range" min="1" max="16" step="1" value="3">
  <span id="zoomLabel">3x</span>
</div>
<div class="row">
  <figure><figcaption>крыніца</figcaption>
    <div class="box"><img id="src" src="{source_uri}" width="{width}"/></div>
  </figure>
  <figure><figcaption>цяпер (v1)</figcaption>
    <div class="box" id="boxA">{svg_v1}</div>
  </figure>
  <figure><figcaption>Materialization v2</figcaption>
    <div class="box" id="boxB">{svg_v2}</div>
  </figure>
</div>
<script>
 const zoom = document.getElementById('zoom');
 const label = document.getElementById('zoomLabel');
 const baseWidth = {width};
 function apply() {{
   label.textContent = zoom.value + 'x';
   const px = baseWidth * zoom.value;
   document.querySelectorAll('.box svg, .box img').forEach(node => {{
     node.style.width = px + 'px';
     node.style.height = 'auto';
     node.removeAttribute('height');
   }});
 }}
 zoom.addEventListener('input', apply);
 window.addEventListener('load', apply);
</script>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"v1: {_commands(svg_v1)} commands, {ms_v1:.0f} ms")
    print(f"v2: {_commands(svg_v2)} commands, {ms_v2:.0f} ms")
    if identical:
        print("NOTE: identical output - the v2 route did not fire here")
    return OUT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--mode", default="balanced", choices=("fast", "balanced", "max"),
    )
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"no such file: {args.input}")
    path = build(args.input, args.mode)
    print(f"-> {path}")
    if args.open:
        webbrowser.open(path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
