"""Wave B / Stage-3 seed: BLIND pairwise preference sheet (human judgement).

Builds a single self-contained HTML file: for each chosen challenge item the
SOURCE crop sits between two anonymised renders (ours vs VAI, sides
shuffled per item).  The user clicks A / tie / B and optionally comments;
the Export button serialises all answers to JSON for pasting back.  The
A/B mapping is stored separately (benchmarks/preference_manifest.json) so
answers stay decodable while the sheet itself remains blind.

Item mix: the worst-kinks items (where judgement matters most) plus one
random item per category (seeded - reproducible).

Usage: preference_collector.py [--n-worst 8]
Output: benchmarks/preference_sheet.html + preference_manifest.json
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent
EVAL = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack/eval")
OUT_HTML = ROOT / "benchmarks" / "preference_sheet.html"
OUT_MAN = ROOT / "benchmarks" / "preference_manifest.json"


def to_b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-worst", type=int, default=8)
    args = ap.parse_args()

    import importlib.util
    spec = importlib.util.spec_from_file_location("bv", ROOT / "benchmark_vai.py")
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)
    from PIL import Image

    rep = json.loads((EVAL / "report.json").read_text(encoding="utf-8"))
    rows = [r for r in rep["rows"] if r.get("ours")]
    worst = sorted(rows, key=lambda r: -(r["ours"].get("kinks_per_100px") or 0))[: args.n_worst]
    rng = random.Random(7)
    cats: dict[str, list] = {}
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    picks = {r["item"]: r for r in worst}
    for cat in sorted(cats):
        r = rng.choice(cats[cat])
        picks.setdefault(r["item"], r)

    blocks = []
    manifest = []
    for item_id in sorted(picks):
        r = picks[item_id]
        tag = f"item{item_id:03d}"
        src_p = EVAL / "crops" / f"{tag}.png"
        ours_svg = EVAL / "ours" / tag / tag / "03_rebuilt_filled.svg"
        vai_svg = EVAL / "items" / f"{tag}_vai.svg"
        if not (src_p.is_file() and ours_svg.is_file() and vai_svg.is_file()):
            continue
        src = Image.open(src_p).convert("RGB")
        W = min(480, src.width * 3)
        scale = W / src.width
        H = int(src.height * scale)
        try:
            ours = bv.render_svg(ours_svg, W).convert("RGB")
            vai = bv.render_svg(vai_svg, W).convert("RGB")
        except Exception as exc:
            print(f"skip {tag}: {exc}")
            continue
        src_big = src.resize((W, H), Image.Resampling.NEAREST)
        if ours.size != (W, H):
            ours = ours.resize((W, H))
        if vai.size != (W, H):
            vai = vai.resize((W, H))
        flip = rng.random() < 0.5
        a_img, b_img = (vai, ours) if flip else (ours, vai)
        manifest.append({"item": item_id, "category": r["category"],
                         "A": "vai" if flip else "ours",
                         "B": "ours" if flip else "vai"})
        blocks.append(f"""
<div class="block" data-item="{item_id}">
  <h3>#{item_id} <span class="cat">{r['category']}</span></h3>
  <div class="tri">
    <figure><img src="{to_b64(a_img)}"><figcaption>A</figcaption></figure>
    <figure class="src"><img src="{to_b64(src_big)}"><figcaption>КРЫНІЦА</figcaption></figure>
    <figure><img src="{to_b64(b_img)}"><figcaption>B</figcaption></figure>
  </div>
  <div class="vote">
    <label><input type="radio" name="v{item_id}" value="A">A лепш</label>
    <label><input type="radio" name="v{item_id}" value="tie">роўна</label>
    <label><input type="radio" name="v{item_id}" value="B">B лепш</label>
    <input type="text" class="note" placeholder="камент (не абавязкова)">
  </div>
</div>""")

    html = f"""<!doctype html><meta charset="utf-8">
<title>Сляпыя парныя пераванні — {len(blocks)} items</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 20px; background: #fafafa; }}
.block {{ background: #fff; border: 1px solid #ddd; border-radius: 10px;
         padding: 14px 18px; margin-bottom: 26px; }}
.tri {{ display: flex; gap: 14px; align-items: flex-start; }}
figure {{ margin: 0; text-align: center; }}
figure img {{ max-width: 100%; border: 1px solid #ccc; image-rendering: pixelated; }}
figure.src img {{ border-color: #888; }}
figcaption {{ font-weight: 600; margin-top: 4px; }}
.cat {{ color: #888; font-weight: 400; font-size: 0.8em; }}
.vote {{ margin-top: 10px; display: flex; gap: 18px; align-items: center; }}
.note {{ flex: 1; padding: 4px 8px; }}
#export {{ position: sticky; bottom: 10px; background: #fff; border: 2px solid #444;
          border-radius: 10px; padding: 12px; }}
textarea {{ width: 100%; height: 90px; }}
</style>
<h1>Хто лепш аднавіў крыніцу? (сляпы тэст, {len(blocks)} пар)</h1>
<p>Пасярэдзіне — арыгінальны растр. A і B — два вектарныя аднаўленні ў
выпадковым парадку. Глядзі на гладкасць ліній, захаванасць дэталяў,
чысціню формаў. Пасля — «Сабраць адказы» і даслаць мне JSON.</p>
{''.join(blocks)}
<div id="export">
  <button onclick="collect()" style="font-size:1.1em;padding:8px 22px">Сабраць адказы</button>
  <textarea id="out" placeholder="тут з'явіцца JSON — скапіюй і дашлі"></textarea>
</div>
<script>
function collect() {{
  const res = [];
  document.querySelectorAll('.block').forEach(b => {{
    const id = b.dataset.item;
    const sel = b.querySelector('input[type=radio]:checked');
    const note = b.querySelector('.note').value;
    res.push({{item: +id, choice: sel ? sel.value : null, note: note}});
  }});
  document.getElementById('out').value = JSON.stringify(res, null, 1);
}}
</script>"""
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_MAN.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"{len(blocks)} pairs -> {OUT_HTML}")
    print(f"mapping -> {OUT_MAN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
