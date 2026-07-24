"""Build a deterministic, resolution-honest blind V-ICE/VAI crop court.

The candidates remain SVG all the way to the browser.  The source is stored at
native crop resolution, and the UI offers 0.5x/1x/2x plus an explicit 4x
nearest-neighbour diagnostic.  A manifest pins the exact snapshot, SVG hashes,
crop viewBoxes, repository revision and selection policy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import benchmark_vai as bv


ROOT = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = ROOT / "benchmarks" / "vai_snapshot_production_fresh50_final.json"
WORK = ROOT / "benchmarks" / "vai_work" / "paper-regions"
COURT_HTML = ROOT / "web_preview" / "court.html"
ASSET_DIR = ROOT / "web_preview" / "court_assets"
MANIFEST = ROOT / "benchmarks" / "vai_crop_court_manifest.json"


def _metric(row: dict, side: str, name: str, fallback: float = 0.0) -> float:
    value = row.get(side, {}).get(name)
    return fallback if value is None else float(value)


def perceptual_gap(row: dict) -> float:
    """Legacy diagnostic only; positive means VAI is closer to the raster."""
    return (
        10.0 * (_metric(row, "vai", "ssim") - _metric(row, "ours", "ssim"))
        + 4.0 * (_metric(row, "vai", "ink_iou") - _metric(row, "ours", "ink_iou"))
        + (_metric(row, "ours", "mae") - _metric(row, "vai", "mae")) / 25.0
    )


def choose_rows(rows: list[dict], count: int, seed: int,
                selection: str = "representative") -> list[dict]:
    """Choose either an unbiased deterministic sample or a separate hard tail."""
    viable = [row for row in rows if row.get("ours") and row.get("vai")]
    if selection == "hard-tail":
        def risk(row: dict) -> float:
            structural = max(
                _metric(row, "ours", "catastrophic_locus_rate") -
                _metric(row, "vai", "catastrophic_locus_rate"),
                _metric(row, "ours", "persistent_beta1_error") -
                _metric(row, "vai", "persistent_beta1_error"),
                _metric(row, "ours", "group_regularity_violation") -
                _metric(row, "vai", "group_regularity_violation"),
                0.0,
            )
            return structural * 100.0 + abs(perceptual_gap(row))
        return sorted(viable, key=risk, reverse=True)[:count]
    return sorted(
        viable,
        key=lambda row: hashlib.sha256(
            f"{seed}:{row['stem']}".encode("utf-8")).digest(),
    )[:count]


def find_ours_svg(stem: str) -> Path | None:
    stem_dir = WORK / stem
    if not stem_dir.is_dir():
        return None
    candidates = sorted(stem_dir.glob("*/03_rebuilt_filled.svg"))
    return candidates[-1] if candidates else None


def render_pair(row: dict) -> tuple[Image.Image, Image.Image, Image.Image, Path, Path, Path]:
    stem = row["stem"]
    source_path = bv.find_source(stem)
    ours_path = find_ours_svg(stem)
    vai_path = bv.VAI_DIR / f"{stem}_vai.svg"
    if source_path is None or ours_path is None or not vai_path.is_file():
        raise FileNotFoundError(f"incomplete benchmark triplet for {stem}")
    source = Image.open(source_path).convert("RGB")
    ours = bv.render_svg(ours_path, source.width).convert("RGB")
    vai = bv.render_svg(vai_path, source.width).convert("RGB")
    if ours.size != source.size:
        ours = ours.resize(source.size, Image.Resampling.LANCZOS)
    if vai.size != source.size:
        vai = vai.resize(source.size, Image.Resampling.LANCZOS)
    return source, ours, vai, source_path, ours_path, vai_path


def strongest_window(delta: np.ndarray, window: int,
                     stride: int = 8) -> tuple[int, int, float]:
    height, width = delta.shape
    wh, ww = min(window, height), min(window, width)
    ys = list(range(0, max(1, height - wh + 1), max(1, stride)))
    xs = list(range(0, max(1, width - ww + 1), max(1, stride)))
    if ys[-1] != height - wh:
        ys.append(height - wh)
    if xs[-1] != width - ww:
        xs.append(width - ww)
    integral = cv2.integral(delta.astype(np.float32), sdepth=cv2.CV_64F)
    y = np.asarray(ys, dtype=int)[:, None]
    x = np.asarray(xs, dtype=int)[None, :]
    sums = (integral[y + wh, x + ww] - integral[y, x + ww]
            - integral[y + wh, x] + integral[y, x])
    means = sums / float(wh * ww)
    iy, ix = np.unravel_index(int(np.argmax(means)), means.shape)
    return int(xs[ix] + ww // 2), int(ys[iy] + wh // 2), float(means[iy, ix])


def crop_box(size: tuple[int, int], center: tuple[int, int],
             extent: int) -> tuple[int, int, int, int]:
    width, height = size
    crop_width, crop_height = min(extent, width), min(extent, height)
    x0 = min(max(0, center[0] - crop_width // 2), width - crop_width)
    y0 = min(max(0, center[1] - crop_height // 2), height - crop_height)
    return x0, y0, x0 + crop_width, y0 + crop_height


def stable_flip(stem: str, seed: int) -> bool:
    digest = hashlib.sha256(f"{seed}:{stem}".encode("utf-8")).digest()
    return bool(digest[0] & 1)


def _number(value: str | None, fallback: float) -> float:
    if value is None:
        return fallback
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value)
    return float(match.group(0)) if match else fallback


def cropped_svg(source_svg: Path, source_size: tuple[int, int],
                box: tuple[int, int, int, int], target: Path) -> list[float]:
    """Write a live SVG whose viewBox is the requested native-pixel crop."""
    text = source_svg.read_text(encoding="utf-8", errors="replace")
    root = re.search(r"<svg\b([^>]*)>", text, flags=re.IGNORECASE | re.DOTALL)
    if root is None:
        raise ValueError(f"missing SVG root: {source_svg}")
    attrs = root.group(1)
    viewbox = re.search(r"\bviewBox\s*=\s*['\"]([^'\"]+)['\"]", attrs,
                        flags=re.IGNORECASE)
    if viewbox:
        values = [float(value) for value in re.findall(
            r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",
            viewbox.group(1))]
        if len(values) != 4:
            raise ValueError(f"invalid viewBox: {source_svg}")
        vx, vy, vw, vh = values
    else:
        vx = vy = 0.0
        vw = _number(re.search(r"\bwidth\s*=\s*['\"]([^'\"]+)", attrs,
                               flags=re.IGNORECASE).group(1)
                     if re.search(r"\bwidth\s*=\s*['\"]([^'\"]+)", attrs,
                                  flags=re.IGNORECASE) else None, float(source_size[0]))
        vh = _number(re.search(r"\bheight\s*=\s*['\"]([^'\"]+)", attrs,
                               flags=re.IGNORECASE).group(1)
                     if re.search(r"\bheight\s*=\s*['\"]([^'\"]+)", attrs,
                                  flags=re.IGNORECASE) else None, float(source_size[1]))

    width, height = source_size
    x0, y0, x1, y1 = box
    crop_vb = [vx + vw * x0 / width, vy + vh * y0 / height,
               vw * (x1 - x0) / width, vh * (y1 - y0) / height]
    cleaned = re.sub(r"\s+(?:viewBox|width|height|preserveAspectRatio)\s*=\s*(['\"]).*?\1",
                     "", attrs, flags=re.IGNORECASE | re.DOTALL)
    if not re.search(r"\bxmlns\s*=", cleaned, flags=re.IGNORECASE):
        cleaned += ' xmlns="http://www.w3.org/2000/svg"'
    new_root = (
        f'<svg{cleaned} width="{x1 - x0}" height="{y1 - y0}" '
        f'viewBox="{crop_vb[0]:.8g} {crop_vb[1]:.8g} '
        f'{crop_vb[2]:.8g} {crop_vb[3]:.8g}" preserveAspectRatio="none">')
    target.write_text(text[:root.start()] + new_root + text[root.end():],
                      encoding="utf-8")
    return [round(float(value), 8) for value in crop_vb]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_revision() -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.run(["git", "diff", "--quiet"], cwd=ROOT,
                               check=False).returncode != 0
        return {"commit": commit, "dirty": dirty}
    except Exception:
        return {"commit": None, "dirty": None}


def build_html(items: list[dict], court_id: str) -> str:
    cards = []
    for item in items:
        number = item["case"]
        width, height = item["crop_size"]
        cards.append(f"""
    <article class="case" data-case="{number}" style="--native-w:{width};--native-h:{height}">
      <div class="case-head"><span>КЕЙС {number:02d}</span><span class="saved">не ацэнены</span></div>
      <div class="triptych">
        <figure><div class="viewport"><img class="art candidate" src="court_assets/case_{number:02d}_a.svg" alt="Варыянт A"></div><figcaption>A · LIVE SVG</figcaption></figure>
        <figure class="source"><div class="viewport"><img class="art source-art" src="court_assets/case_{number:02d}_source.png" alt="Крыніца"></div><figcaption>КРЫНІЦА · NATIVE PNG</figcaption></figure>
        <figure><div class="viewport"><img class="art candidate" src="court_assets/case_{number:02d}_b.svg" alt="Варыянт B"></div><figcaption>B · LIVE SVG</figcaption></figure>
      </div>
      <div class="vote" role="group" aria-label="Ацэнка кейса {number}">
        <button type="button" data-choice="A">A лепш</button>
        <button type="button" data-choice="tie">роўна</button>
        <button type="button" data-choice="B">B лепш</button>
      </div>
      <input class="note" type="text" placeholder="Што вырашыла выбар: форма, тэкст, шво, колер…">
    </article>""")

    return f"""<!doctype html>
<html lang="be">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>V-ICE · resolution-honest blind court</title>
  <style>
    :root {{ color-scheme:dark; --bg:#0a0d11; --card:#141920; --line:#2a333e; --text:#f3f6f8; --muted:#8e9aa7; --accent:#ff6b35; --court-scale:2 }}
    * {{ box-sizing:border-box }}
    body {{ margin:0; background:radial-gradient(circle at 20% 0,#182330 0,transparent 30%),var(--bg); color:var(--text); font-family:Inter,Segoe UI,sans-serif }}
    header {{ position:sticky; top:0; z-index:5; display:flex; justify-content:space-between; gap:18px; align-items:center; padding:15px 24px; background:#0a0d11ee; border-bottom:1px solid var(--line); backdrop-filter:blur(14px) }}
    h1 {{ margin:0; font-size:22px }} header p {{ margin:4px 0 0; color:var(--muted); font-size:12px }}
    .actions,.scales {{ display:flex; flex-wrap:wrap; gap:7px; align-items:center }} a,button {{ border:1px solid var(--line); border-radius:8px; background:#202732; color:var(--text); padding:8px 11px; font-weight:700; text-decoration:none; cursor:pointer }} button.selected,#export {{ background:var(--accent); border-color:var(--accent) }}
    main {{ width:min(1500px,calc(100% - 24px)); margin:20px auto 80px; display:grid; gap:20px }} .instructions {{ color:#bdc6cf; font-size:13px; line-height:1.55; max-width:980px }}
    .case {{ border:1px solid var(--line); border-radius:14px; overflow:hidden; background:var(--card); box-shadow:0 14px 40px #0004 }} .case-head {{ display:flex; justify-content:space-between; padding:10px 14px; font-size:10px; letter-spacing:.12em; color:var(--muted) }} .case.answered .saved {{ color:#77d899 }}
    .triptych {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1px; background:var(--line) }} figure {{ margin:0; min-width:0; background:#0d1116; text-align:center }} figure.source {{ background:#171d24 }}
    .viewport {{ height:360px; overflow:auto; display:grid; place-items:center; padding:20px; background:linear-gradient(45deg,#e8ebee 25%,transparent 25%),linear-gradient(-45deg,#e8ebee 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#e8ebee 75%),linear-gradient(-45deg,transparent 75%,#e8ebee 75%),#f7f8f9; background-size:20px 20px; background-position:0 0,0 10px,10px -10px,-10px 0 }}
    body.dark-art .viewport {{ background:#171b20 }}
    .art {{ display:block; flex:none; width:calc(var(--native-w) * var(--court-scale) * 1px); height:calc(var(--native-h) * var(--court-scale) * 1px); max-width:none; max-height:none }}
    body.pixel-debug .source-art {{ image-rendering:pixelated }} figcaption {{ padding:8px; color:#c4ccd4; font-size:10px; letter-spacing:.1em }}
    .vote {{ display:flex; gap:8px; justify-content:center; padding:13px 14px 7px }} .note {{ display:block; width:calc(100% - 28px); margin:0 14px 14px; padding:10px; border:1px solid var(--line); border-radius:8px; background:#0c1015; color:var(--text) }} #progress {{ font:700 12px ui-monospace,monospace; white-space:nowrap }}
    @media(max-width:820px) {{ header {{ position:relative; align-items:flex-start; padding:13px; flex-direction:column }} main {{ width:calc(100% - 12px); margin-top:10px }} .triptych {{ grid-template-columns:1fr }} }}
  </style>
</head>
<body>
  <header>
    <div><h1>Blind court · V-ICE vs VAI</h1><p>Live SVG · native source · зафіксаваны build · без LANCZOS-панэляў</p></div>
    <div class="actions"><span id="progress">0 / {len(items)}</span><div class="scales"><button data-scale=".5">0.5×</button><button data-scale="1">1× native</button><button class="selected" data-scale="2">2× compare</button><button data-scale="4" data-pixels="1">4× pixels</button></div><button id="background" type="button">фон</button><a href="/">← Vectorizer</a><button id="reset" type="button">Скінуць</button><button id="export" type="button">Экспартаваць JSON</button></div>
  </header>
  <main>
    <p class="instructions">Па змаўчанні 2× compare: A, native-крыніца і B адначасова бачныя ў аднолькавым памеры. 1× native правярае рэальны display scale, а 4× pixels — форму SVG супраць піксельнай структуры растра без згладжвання. A і B заўсёды застаюцца жывымі SVG.</p>
    {''.join(cards)}
  </main>
  <script>
    const storageKey={json.dumps(court_id)}, total={len(items)};
    let answers=JSON.parse(localStorage.getItem(storageKey)||'{{}}');
    function save() {{ localStorage.setItem(storageKey,JSON.stringify(answers)); render(); }}
    function render() {{
      document.querySelectorAll('.case').forEach(card => {{ const key=card.dataset.case, answer=answers[key]||{{}}; card.classList.toggle('answered',Boolean(answer.choice)); card.querySelector('.saved').textContent=answer.choice?`захавана · ${{answer.choice}}`:'не ацэнены'; card.querySelectorAll('[data-choice]').forEach(button=>button.classList.toggle('selected',button.dataset.choice===answer.choice)); const note=card.querySelector('.note'); if(document.activeElement!==note) note.value=answer.note||''; }});
      document.getElementById('progress').textContent=`${{Object.values(answers).filter(x=>x.choice).length}} / ${{total}}`;
    }}
    document.querySelectorAll('[data-scale]').forEach(button=>button.addEventListener('click',()=>{{ document.documentElement.style.setProperty('--court-scale',button.dataset.scale); document.body.classList.toggle('pixel-debug',Boolean(button.dataset.pixels)); document.querySelectorAll('[data-scale]').forEach(item=>item.classList.toggle('selected',item===button)); }}));
    document.getElementById('background').addEventListener('click',()=>document.body.classList.toggle('dark-art'));
    document.querySelectorAll('.case').forEach(card => {{ card.querySelectorAll('[data-choice]').forEach(button=>button.addEventListener('click',()=>{{ const key=card.dataset.case; answers[key]={{...(answers[key]||{{}}),choice:button.dataset.choice}}; save(); }})); card.querySelector('.note').addEventListener('input',event=>{{ const key=card.dataset.case; answers[key]={{...(answers[key]||{{}}),note:event.target.value}}; localStorage.setItem(storageKey,JSON.stringify(answers)); }}); }});
    document.getElementById('reset').addEventListener('click',()=>{{ answers={{}}; localStorage.removeItem(storageKey); render(); }});
    document.getElementById('export').addEventListener('click',()=>{{ const payload={{court:{json.dumps(court_id)},exported_at:new Date().toISOString(),answers}}, blob=new Blob([JSON.stringify(payload,null,2)],{{type:'application/json'}}), link=document.createElement('a'); link.href=URL.createObjectURL(blob); link.download='v-ice-crop-court-answers.json'; link.click(); setTimeout(()=>URL.revokeObjectURL(link.href),5000); }});
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--selection", choices=("representative", "hard-tail"),
                        default="representative")
    parser.add_argument("--crop", type=int, default=112)
    parser.add_argument("--focus-window", type=int, default=48)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--work-mode", default=None,
                        help="benchmark_vai work directory; defaults to snapshot mode")
    args = parser.parse_args()

    report = json.loads(args.snapshot.read_text(encoding="utf-8"))
    global WORK
    WORK = ROOT / "benchmarks" / "vai_work" / (args.work_mode or report.get("mode", "paper-regions"))
    rows = choose_rows(report["rows"], args.count, args.seed, args.selection)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    manifest_items: list[dict] = []
    for row in rows:
        stem = row["stem"]
        try:
            source, ours, vai, source_path, ours_path, vai_path = render_pair(row)
        except (FileNotFoundError, ValueError) as exc:
            print(f"skip {stem}: {exc}")
            continue

        source_arr = np.asarray(source)
        ours_de = bv._delta_e_map(np.asarray(ours), source_arr)
        vai_de = bv._delta_e_map(np.asarray(vai), source_arr)
        cx, cy, local_gap = strongest_window(
            np.abs(ours_de - vai_de), args.focus_window)
        box = crop_box(source.size, (cx, cy), args.crop)
        case = len(manifest_items) + 1
        flipped = stable_flip(stem, args.seed)
        a_path, b_path = (vai_path, ours_path) if flipped else (ours_path, vai_path)

        source_asset = ASSET_DIR / f"case_{case:02d}_source.png"
        a_asset = ASSET_DIR / f"case_{case:02d}_a.svg"
        b_asset = ASSET_DIR / f"case_{case:02d}_b.svg"
        source.crop(box).save(source_asset, optimize=True)
        a_viewbox = cropped_svg(a_path, source.size, box, a_asset)
        b_viewbox = cropped_svg(b_path, source.size, box, b_asset)
        manifest_items.append({
            "case": case, "stem": stem,
            "A": "vai" if flipped else "ours",
            "B": "ours" if flipped else "vai",
            "selection": args.selection,
            "legacy_perceptual_gap": round(perceptual_gap(row), 6),
            "absolute_local_de_gap": round(local_gap, 4),
            "focus": [cx, cy], "crop_box": list(box),
            "crop_size": [box[2] - box[0], box[3] - box[1]],
            "source": str(source_path), "ours_svg": str(ours_path),
            "vai_svg": str(vai_path),
            "source_sha256": _sha256(source_path),
            "ours_sha256": _sha256(ours_path), "vai_sha256": _sha256(vai_path),
            "A_crop_viewbox": a_viewbox, "B_crop_viewbox": b_viewbox,
            "metrics": {"ours": row["ours"], "vai": row["vai"]},
        })
        print(f"{case:02d} {stem:30s} {args.selection:14s} "
              f"A={manifest_items[-1]['A']}")

    if not manifest_items:
        raise RuntimeError("no complete benchmark triplets were found")
    snapshot_hash = _sha256(args.snapshot)
    court_id = f"v-ice-vai-crop-v2-{args.selection}-{snapshot_hash[:12]}"
    COURT_HTML.write_text(build_html(manifest_items, court_id), encoding="utf-8")
    MANIFEST.write_text(json.dumps({
        "version": 2, "court": court_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "snapshot": str(args.snapshot), "snapshot_sha256": snapshot_hash,
        "repository": _repo_revision(),
        "selection": {"policy": args.selection, "count": args.count,
                      "seed": args.seed},
        "display_contract": {"candidate": "live SVG", "source": "native PNG",
                             "default_scale": 2.0,
                             "scales": [0.5, 1.0, 2.0],
                             "pixel_diagnostic_scale": 4.0,
                             "candidate_prerasterization": False},
        "items": manifest_items,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(manifest_items)} cases -> {COURT_HTML}")
    print(f"blind mapping -> {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
