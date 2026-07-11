"""Build a reproducible visual/metric page for the corner-postprocess logo A/B."""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity


ROOT = Path(__file__).resolve().parent
RUN_ROOT = ROOT / "test_runs" / "corner_postprocess_logo_ab"
MODES = ("production", "tiny_safe", "letter_safe")
ROWS = (
    ("Adidas", "18_icon_group_2_3_src.png", "18_icon_group_2_3_src"),
    ("IKEA", "89_icon_group_4_58_src.png", "89_icon_group_4_58_src"),
    ("Script text", "sassy-text-6557ld.png", "sassy-text-6557ld"),
    ("Lacoste", "117_icon_group_6_src.png", "117_icon_group_6_src"),
    ("Mastercard", "13_icon_group_1_src.png", "13_icon_group_1_src"),
    ("Mobil", "20_icon_group_2_5_src.png", "20_icon_group_2_5_src"),
    ("NBC", "22_icon_group_3_src.png", "22_icon_group_3_src"),
)


def _rgb(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(path)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    elif image.shape[2] == 4:
        bgr, alpha = image[:, :, :3].astype(np.float32), image[:, :, 3:4].astype(np.float32) / 255.0
        bgr = bgr * alpha + 255.0 * (1.0 - alpha)
        image = cv2.cvtColor(np.clip(bgr, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)
    else:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image


def image_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float | int]:
    if reference.shape != candidate.shape:
        raise ValueError(f"image shape mismatch: {reference.shape} vs {candidate.shape}")
    first = reference.astype(np.float32)
    second = candidate.astype(np.float32)
    absolute = np.abs(first - second)
    changed = np.any(absolute > 0.5, axis=2)
    mse = float(np.mean((first - second) ** 2))
    return {
        "changed_pixels": int(changed.sum()),
        "changed_fraction": round(float(changed.mean()), 6),
        "mae_rgb": round(float(absolute.mean()), 4),
        "psnr_db": round(20.0 * math.log10(255.0 / math.sqrt(max(mse, 1e-12))), 4),
        "ssim": round(float(structural_similarity(
            reference, candidate, data_range=255, channel_axis=2,
        )), 6),
    }


def _mode_dir(mode: str, stem: str) -> Path:
    return RUN_ROOT / mode / "paper-regions" / stem


def build_summary() -> dict:
    rows = []
    for title, source_name, stem in ROWS:
        source = _rgb(ROOT / "web_preview" / "uploads" / source_name)
        rebuilt = {
            mode: _rgb(_mode_dir(mode, stem) / "03_rebuilt_filled.png")
            for mode in MODES
        }
        reports = {
            mode: json.loads((_mode_dir(mode, stem) / "report.json").read_text(encoding="utf-8"))
            for mode in MODES
        }
        modes = {}
        for mode in MODES:
            report = reports[mode]
            modes[mode] = {
                "primitives": int(report["rendered_primitive_count"]),
                "primitive_types": report.get("actual", {}),
                "source_similarity": image_metrics(source, rebuilt[mode]),
                "versus_production": image_metrics(rebuilt["production"], rebuilt[mode]),
            }
        rows.append({
            "title": title,
            "source": source_name,
            "stem": stem,
            "modes": modes,
        })
    return {
        "schema_version": 1,
        "policies": {
            "production": "legacy recenter/collapse/removal + fixed IoU fallback",
            "tiny_safe": "raw small-loop candidates; production fit fallback",
            "letter_safe": "CNN recenter(1,2), no collapse, acc=0.7 + deviation-aware text fit fallback",
        },
        "metric_warning": (
            "Source similarity measures raster agreement, not perceived vector quality; "
            "JPEG ringing and antialiasing can reward an objectively uglier trace."
        ),
        "rows": rows,
    }


def _html(summary: dict) -> str:
    payload = json.dumps(summary, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Corner cleanup · logo A/B</title><style>
:root{{color-scheme:dark;--bg:#0e141b;--panel:#17212b;--line:#344454;--muted:#9db0c1;--good:#7ee787}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:#eef5fb;font:14px/1.4 system-ui,sans-serif}}
header{{position:sticky;top:0;z-index:2;padding:16px 22px;background:#0e141bf2;border-bottom:1px solid var(--line)}}
h1{{margin:0 0 5px;font-size:21px}}.muted,.metric{{color:var(--muted)}}main{{padding:16px;display:grid;gap:16px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:11px;overflow:hidden}}h2{{margin:0;padding:11px 13px;font-size:16px;border-bottom:1px solid var(--line)}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}}.cell{{padding:10px;border-right:1px solid var(--line)}}.cell:last-child{{border:0}}
.label{{display:flex;justify-content:space-between;gap:8px;margin-bottom:7px}}.candidate{{color:var(--good)}}img{{width:100%;height:220px;object-fit:contain;background:white;display:block}}
.metric{{font-size:12px;margin-top:6px}}details{{border-top:1px solid var(--line);padding:9px 11px}}details .grid{{margin-top:9px}}
@media(max-width:1000px){{.grid{{grid-template-columns:repeat(2,1fr)}}.cell{{border-bottom:1px solid var(--line)}}}}@media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>Corner cleanup · 7-logo A/B</h1><div class="muted">Same extractor + CNN · only cleanup/final fallback changes · production unchanged</div></header><main id="cards"></main>
<script type="application/json" id="payload">{payload}</script><script>
const data=JSON.parse(document.querySelector('#payload').textContent);const cards=document.querySelector('#cards');
const labels={{production:'Current production',tiny_safe:'Tiny-safe corners',letter_safe:'Letter-safe + fit'}};
const file=(mode,stem,name)=>`/dataset-preview/corner_postprocess_logo_ab/${{mode}}/paper-regions/${{stem}}/${{name}}`;
for(const row of data.rows){{const card=document.createElement('section');card.className='card';let cells=`<div class="cell"><div class="label">Source</div><img src="/uploads/${{row.source}}"><div class="metric">visual reference</div></div>`;
 for(const mode of ['production','tiny_safe','letter_safe']){{const m=row.modes[mode],d=m.versus_production;cells+=`<div class="cell"><div class="label ${{mode==='production'?'':'candidate'}}">${{labels[mode]}} <span>${{m.primitives}} prims</span></div><img src="${{file(mode,row.stem,'03_rebuilt_filled.png')}}"><div class="metric">vs prod: ${{(100*d.changed_fraction).toFixed(2)}}% px · SSIM ${{d.ssim}}</div></div>`}}
 card.innerHTML=`<h2>${{row.title}}</h2><div class="grid">${{cells}}</div><details><summary>Corner and primitive maps</summary><div class="grid"><div class="cell"><div class="label">Production corners</div><img src="${{file('production',row.stem,'04_corners.png')}}"></div><div class="cell"><div class="label">Letter-safe corners</div><img src="${{file('letter_safe',row.stem,'04_corners.png')}}"></div><div class="cell"><div class="label">Production primitives</div><img src="${{file('production',row.stem,'02_primitive_map.svg')}}"></div><div class="cell"><div class="label">Letter-safe primitives</div><img src="${{file('letter_safe',row.stem,'02_primitive_map.svg')}}"></div></div></details>`;cards.append(card)}}
</script></body></html>"""


def main() -> None:
    summary = build_summary()
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    (RUN_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (RUN_ROOT / "index.html").write_text(_html(summary), encoding="utf-8")
    print(json.dumps({
        "out": str(RUN_ROOT.resolve()),
        "rows": len(summary["rows"]),
    }, indent=2))


if __name__ == "__main__":
    main()
