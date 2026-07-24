"""Recover the OCR metric that the frozen aggregate defined but never called."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import benchmark_vai as bv


ROOT = Path(__file__).resolve().parent
DEFAULT_ROOT = ROOT / "benchmarks" / "scene_validation" / "33bc0d63e4b82734" / "challenge115_bounded"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    report_path = args.root / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = []
    for item in report.get("rows", []):
        if item.get("category") != "small_text" or item.get("status") != "completed":
            continue
        index = int(item["item"])
        crop = args.root / "crops" / f"item{index:03}.png"
        ours_svg = (args.root / "ours" / f"item{index:03}" / f"item{index:03}"
                    / "03_rebuilt_filled.svg")
        vai_svg = args.root / "vai_items" / f"item{index:03}_vai.svg"
        source = Image.open(crop).convert("RGB")
        ours_render = bv.render_svg(ours_svg, source.width)
        vai_render = bv.render_svg(vai_svg, source.width)
        if ours_render.size != source.size:
            ours_render = ours_render.resize(source.size, Image.Resampling.LANCZOS)
        if vai_render.size != source.size:
            vai_render = vai_render.resize(source.size, Image.Resampling.LANCZOS)
        ours = bv.ocr_legibility_meter(source, ours_render)
        vai = bv.ocr_legibility_meter(source, vai_render)
        rows.append({"item": index, "source": item.get("source"),
                     "size": item.get("size"), "ours": ours, "vai": vai})
        print(f"item{index:03}: source-lines={ours['ocr_source_lines']} "
              f"ours={ours['ocr_legibility']} vai={vai['ocr_legibility']}", flush=True)
    comparable = [row for row in rows
                  if row["ours"].get("ocr_legibility") is not None
                  and row["vai"].get("ocr_legibility") is not None]
    ours_values = [float(row["ours"]["ocr_legibility"]) for row in comparable]
    vai_values = [float(row["vai"]["ocr_legibility"]) for row in comparable]
    payload = {
        "schema": "vice-scene-frozen-ocr-audit/1",
        "reason": "ocr_legibility_meter existed but was not called by raster_meters",
        "completed_small_text_items": len(rows),
        "ocr_comparable_items": len(comparable),
        "aggregate": {
            "ours_wins": sum(a < b for a, b in zip(ours_values, vai_values)),
            "ties": sum(a == b for a, b in zip(ours_values, vai_values)),
            "ours_median_loss": round(float(np.median(ours_values)), 4) if ours_values else None,
            "vai_median_loss": round(float(np.median(vai_values)), 4) if vai_values else None,
        },
        "rows": rows,
    }
    output = args.root / "ocr_audit.json"
    _write(output, payload)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

