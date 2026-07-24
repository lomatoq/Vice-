"""Council N3 glyph fold forensics (measurement only, no production switch)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import geometry_vectorizer as gv
from subpixel_mininet import compact_palette
from text_substitution import ocr_lines

ROOT = Path(__file__).parent
EVAL = Path(r"C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\eval")
ITEMS = (53, 114, 27, 81)


def sanctuary_boxes(image: Image.Image) -> list[tuple[float, float, float, float]]:
    """Exact process() sanctuary detector, returned in source coordinates."""
    mult = 1
    lines = ocr_lines(image.convert("RGB"))
    if not lines and min(image.size) < 200:
        mult = 3
        lines = ocr_lines(image.convert("RGB").resize(
            (image.width * 3, image.height * 3), Image.Resampling.LANCZOS))
    gray = np.asarray(image.convert("L"))
    boxes = []
    for line in lines or []:
        x0, y0, x1, y1 = [float(value) / mult for value in line["bbox"]]
        height = y1 - y0
        if not (3.0 <= height <= 28.0 and (x1 - x0) >= 1.5 * height):
            continue
        crop = gray[max(0, int(y0)):int(y1) + 1, max(0, int(x0)):int(x1) + 1]
        if crop.size < 12:
            continue
        _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        count, _, stats, _ = cv2.connectedComponentsWithStats((binary > 0).astype(np.uint8), 8)
        heights = [stats[index, cv2.CC_STAT_HEIGHT] for index in range(1, count)
                   if stats[index, cv2.CC_STAT_AREA] >= 3]
        if not heights or float(np.median(heights)) > 8.0:
            continue
        boxes.append((x0 - 1.0, y0 - 1.0, x1 + 1.0, y1 + 1.0))
    return boxes


def main() -> int:
    rows = []
    for item in ITEMS:
        path = EVAL / "crops" / f"item{item:03d}.png"
        image = Image.open(path).convert("RGB")
        boxes = sanctuary_boxes(image)
        audit: list[dict] = []
        noise = gv.measure_image_noise(image)
        anchors = compact_palette(image, thick_core_veto=noise < 0.27,
                                  audit=audit, audit_boxes=boxes)
        hits = [event for event in audit if event["sanctuary_mass"] > 0]
        crossed = [event for event in hits if event["delta_e"] is not None]
        row = {
            "item": item,
            "source": str(path),
            "noise": round(float(noise), 4),
            "sanctuary_boxes": [[round(value, 2) for value in box] for box in boxes],
            "anchors": [[round(float(value), 2) for value in anchor] for anchor in anchors],
            "fold_events": len(audit),
            "sanctuary_fold_events": len(hits),
            "sanctuary_folded_mass": sum(event["sanctuary_mass"] for event in hits),
            "max_crossed_delta_e": max((event["delta_e"] for event in crossed), default=None),
            "events": audit,
        }
        rows.append(row)
        print(f"item{item:03}: boxes={len(boxes)} folds={len(audit)} "
              f"sanctuary={len(hits)}/{row['sanctuary_folded_mass']}px "
              f"max_dE={row['max_crossed_delta_e']}")
    palette_implicated = any(row["sanctuary_folded_mass"] > 0 for row in rows if row["item"] in (53, 114))
    report = {"items": list(ITEMS),
              "phase_a_verdict": "PALETTE_SIDE_IMPLICATED" if palette_implicated
                  else "ASSIGNMENT_SIDE_ONLY",
              "rows": rows}
    out = ROOT / "benchmarks" / "glyph_fold_probe.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("verdict:", report["phase_a_verdict"])
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
