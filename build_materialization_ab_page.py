"""Materialization v2 — side-by-side viewer for the eye (not a blind court).

The machine numbers are identical by construction (the delivered MASK does
not change), so the only place the difference lives is on screen at zoom:
a fair program is arcs and lines, the incumbent is a pixel staircase.
This builds one HTML page with, per locus: the source crop, the CURRENT
delivery, and the Materialization v2 delivery, at a zoom the user controls.

It is deliberately NOT blind and NOT a promotion artifact - the blind
digest-bound court stays the only thing that can move the human gate.

Usage:
  C:\\Python312\\python.exe build_materialization_ab_page.py --limit 12
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "datasets" / "pcdc_real_loci_v1"
REPORT = ROOT / "benchmarks" / "pcdc_pre_v14" / "experiment4_m2v2b_report.json"
OUT = ROOT / "web_preview" / "materialization_ab.html"


def _source_data_uri(path: Path, roi, scale: int = 1) -> tuple[str, int, int]:
    with Image.open(path) as image:
        crop = image.convert("RGBA").crop(roi)
        if scale > 1:
            crop = crop.resize(
                (crop.width * scale, crop.height * scale), Image.NEAREST,
            )
        buffer = io.BytesIO()
        crop.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}", crop.width, crop.height


def _svg_with_viewbox(svg: str, roi) -> str:
    """Reframe a canvas-sized delivery document onto the locus ROI."""
    x1, y1, x2, y2 = roi
    body = svg
    start = body.find(">", body.find("<svg"))
    end = body.rfind("</svg>")
    inner = body[start + 1:end] if start != -1 and end != -1 else body
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{x1} {y1} {x2 - x1} {y2 - y1}" '
        f'preserveAspectRatio="xMidYMid meet">{inner}</svg>'
    )


def _run_locus(locus, review, cache, *, v2: bool):
    from vice_compiler.experiment4_textline import (
        TextLineReviewArtifacts, evaluate_locus,
    )

    previous = os.environ.get("VICE_TEXT_MATERIALIZATION_V2")
    os.environ["VICE_TEXT_MATERIALIZATION_V2"] = "1" if v2 else "0"
    artifacts: list[TextLineReviewArtifacts] = []
    started = time.perf_counter()
    try:
        row = evaluate_locus(
            locus, review, cache, exact_font=True, template_lane=True,
            review_artifacts=artifacts,
        )
    finally:
        if previous is None:
            os.environ.pop("VICE_TEXT_MATERIALIZATION_V2", None)
        else:
            os.environ["VICE_TEXT_MATERIALIZATION_V2"] = previous
    elapsed = (time.perf_counter() - started) * 1000.0
    if not artifacts:
        return None
    return row, artifacts[0], elapsed


def build(limit: int, only_fair: bool) -> Path:
    from vice_compiler.evidence_ir import EvidenceCache

    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    reviews = json.loads((CORPUS / "review.json").read_text("utf-8"))["reviews"]
    wanted: set[str] | None = None
    if only_fair and REPORT.is_file():
        report = json.loads(REPORT.read_text("utf-8"))
        wanted = {
            row["id"] for row in report["rows"]
            if (row.get("delivered_materialization") or {}).get("family")
            == "fair-primitive-hybrid"
        }
    cache = EvidenceCache()
    cards: list[str] = []
    used = 0
    for locus in manifest["loci"]:
        if used >= limit:
            break
        locus_id = str(locus["id"])
        review = reviews.get(locus_id)
        if not review or (wanted is not None and locus_id not in wanted):
            continue
        try:
            baseline = _run_locus(locus, review, cache, v2=False)
            candidate = _run_locus(locus, review, cache, v2=True)
        except Exception as error:            # a locus may legitimately fail
            print(f"  {locus_id}: skipped ({error})")
            continue
        if baseline is None or candidate is None:
            continue
        base_row, base_art, base_ms = baseline
        v2_row, v2_art, v2_ms = candidate
        roi = tuple(int(value) for value in base_art.source_roi)
        try:
            source_uri, width, height = _source_data_uri(
                Path(locus["source"]["path"]), roi,
            )
        except Exception as error:
            print(f"  {locus_id}: no source crop ({error})")
            continue
        same_pixels = (
            v2_row.get("candidate_mask_digest")
            == base_row.get("candidate_mask_digest")
        )
        base_commands = sum(
            base_art.candidate_svg.count(letter) for letter in "MLCAHV"
        )
        v2_commands = sum(
            v2_art.candidate_svg.count(letter) for letter in "MLCAHV"
        )
        cards.append(f"""
    <section class="card">
      <h2>{html.escape(locus_id)}</h2>
      <div class="meta">
        native {width}x{height} &middot;
        path commands <b>{base_commands}</b> &rarr; <b>{v2_commands}</b> &middot;
        delivered pixels {"identical" if same_pixels else "CHANGED"} &middot;
        GCR {base_row.get('candidate_gcr')} &rarr; {v2_row.get('candidate_gcr')} &middot;
        {base_ms:.0f} ms &rarr; {v2_ms:.0f} ms
      </div>
      <div class="row">
        <figure><figcaption>крыніца</figcaption>
          <img src="{source_uri}" alt="source"/></figure>
        <figure><figcaption>цяпер (v1)</figcaption>
          <div class="svgbox">{_svg_with_viewbox(base_art.candidate_svg, roi)}</div>
        </figure>
        <figure><figcaption>Materialization v2</figcaption>
          <div class="svgbox">{_svg_with_viewbox(v2_art.candidate_svg, roi)}</div>
        </figure>
      </div>
    </section>""")
        used += 1
        print(f"  {locus_id}: {base_commands} -> {v2_commands} commands")
    page = f"""<!doctype html>
<meta charset="utf-8">
<title>Materialization v2 — A/B</title>
<style>
 body {{ background:#101216; color:#e8e8ea; font:14px/1.5 system-ui, sans-serif;
        margin:0; padding:24px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .hint {{ color:#9aa0aa; margin-bottom:20px; }}
 .card {{ border:1px solid #262a33; border-radius:10px; padding:14px;
          margin-bottom:18px; background:#15181e; }}
 h2 {{ font-size:14px; margin:0 0 4px; color:#cfd3da; }}
 .meta {{ color:#8d94a0; font-size:12px; margin-bottom:10px; }}
 .row {{ display:flex; gap:16px; align-items:flex-start; flex-wrap:wrap; }}
 figure {{ margin:0; }}
 figcaption {{ font-size:11px; color:#8d94a0; margin-bottom:6px; }}
 img, .svgbox {{ background:#fff; border-radius:6px; display:block; }}
 .svgbox svg, img {{ width:calc(var(--zoom) * 1px * var(--w, 200));
                     height:auto; image-rendering:pixelated; }}
 .controls {{ position:sticky; top:0; background:#101216; padding:10px 0 16px;
              z-index:5; }}
 input[type=range] {{ width:280px; vertical-align:middle; }}
</style>
<h1>Materialization v2 — тое ж дастаўленае поле пікселяў, іншая геаметрыя</h1>
<div class="hint">
  Розніца бачная толькі на маштабаванні: злева піксельная лесвіца, справа
  дугі і прамыя. Маска дастаўкі не змянілася ні на адным радку, таму
  машынныя лічбы аднолькавыя — судзіць можа толькі вока.
</div>
<div class="controls">
  маштаб <input id="zoom" type="range" min="1" max="12" step="1" value="4">
  <span id="zoomLabel">4x</span>
</div>
<div id="cards">{''.join(cards)}</div>
<script>
 const root = document.documentElement;
 const zoom = document.getElementById('zoom');
 const label = document.getElementById('zoomLabel');
 function apply() {{
   label.textContent = zoom.value + 'x';
   document.querySelectorAll('.card').forEach(card => {{
     card.querySelectorAll('img, .svgbox svg').forEach(node => {{
       const base = node.dataset.base || node.getAttribute('width') ||
         (node.naturalWidth || node.viewBox?.baseVal?.width || 200);
       node.dataset.base = base;
       node.style.width = (base * zoom.value) + 'px';
       node.style.height = 'auto';
     }});
   }});
 }}
 zoom.addEventListener('input', apply);
 window.addEventListener('load', apply);
</script>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    return OUT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument(
        "--all-rows", action="store_true",
        help="do not restrict to loci where the fair program actually won",
    )
    args = parser.parse_args()
    print("building A/B page...")
    path = build(args.limit, only_fair=not args.all_rows)
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
