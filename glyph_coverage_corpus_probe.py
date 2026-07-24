"""N12 corpus gate for the default-off direct glyph coverage candidate."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import benchmark_vai as bv
import geometry_vectorizer as gv


ROOT = Path(__file__).parent
SCHEMA = 7
OUT_ROOT = ROOT / "benchmarks" / f"n12_corpus_v{SCHEMA}"
REPORT = ROOT / "benchmarks" / "glyph_coverage_corpus.json"
CHALLENGE = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack/eval/crops")
PROBLEM = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/problem cases/Small")


def _meters(svg: Path, source: Path) -> dict:
    width = Image.open(source).size[0]
    row = {}
    row.update(bv.geometry_meters(svg, width))
    row.update(bv.roundness_meter(svg, width))
    row.update(bv.raster_meters(svg, source))
    return row


def _detect(source: Path) -> list[dict]:
    image = Image.open(source).convert("RGB")
    if max(image.size) > 512:
        return []
    gv._GLYPH_COVERAGE_DIRECT[0] = True
    gv._GLYPH_COVERAGE_BOXES[0] = None
    gv.extract_perceptual_masks(
        image, use_icm=True, merge=True, deblur=max(image.size) <= 512,
        sanctuary=None, palette_thick_veto=gv.measure_image_noise(image) < 0.27)
    eligible = set()
    for spec in gv._GLYPH_REPAIR_REGIONS:
        counts = []
        scale = int(spec["scale"])
        for raw in gv.mask_loops(np.asarray(spec["mask"], bool)):
            if gv.perimeter(raw) < 4 * scale:
                continue
            full = raw / float(scale)
            counts.append(len(cv2.approxPolyDP(
                full.astype(np.float32).reshape(-1, 1, 2),
                0.35, True).reshape(-1, 2)))
        counter_word = bool(spec.get("counter_word", False))
        max_budget = 96 if counter_word else 24
        mean_budget = 15.0 if counter_word else 9.0
        if (counts and max(counts) <= max_budget
                and float(np.mean(counts)) <= mean_budget):
            eligible.add(tuple(round(float(value), 3) for value in spec["bbox"]))
    return [dict(row) for row in gv._GLYPH_REPAIR_AUDIT
            if row.get("accepted") and tuple(row.get("bbox", ())) in eligible]


def _run_pair(name: str, source: Path) -> dict:
    base_root = OUT_ROOT / "baseline" / name
    candidate_root = OUT_ROOT / "candidate" / name
    base_svg = base_root / source.stem / "03_rebuilt_filled.svg"
    candidate_svg = candidate_root / source.stem / "03_rebuilt_filled.svg"
    base_report = base_root / source.stem / "report.json"
    candidate_report = candidate_root / source.stem / "report.json"
    if not (base_svg.exists() and base_report.exists()):
        gv._GLYPH_COVERAGE_DIRECT[0] = False
        gv._GLYPH_COVERAGE_BOXES[0] = None
        gv.process(source, base_root, smoothing="paper-regions", route="auto")
    if not (candidate_svg.exists() and candidate_report.exists()):
        gv._GLYPH_COVERAGE_DIRECT[0] = True
        gv.process(source, candidate_root, smoothing="paper-regions", route="auto")
    return {"baseline": _meters(base_svg, source),
            "candidate": _meters(candidate_svg, source),
            "candidate_report": json.loads(candidate_report.read_text(encoding="utf-8"))}


def main() -> int:
    sources = [(f"challenge_{index:03d}", CHALLENGE / f"item{index:03d}.png")
               for index in (27, 43, 53, 81)]
    sources.append(("problem_114_bank", PROBLEM / "114_icon_group_4_80_src.png"))
    sources.extend((f"vai_{stem}", bv.find_source(stem)) for stem in bv.frozen_stems(50))
    prior = {}
    if REPORT.exists():
        try:
            saved = json.loads(REPORT.read_text(encoding="utf-8"))
            if not saved.get("complete", True) and saved.get("schema") == SCHEMA:
                prior = {row["name"]: row for row in saved.get("rows", [])}
        except Exception:
            prior = {}
    rows = []
    for number, (name, source) in enumerate(sources, 1):
        if source is None or not Path(source).exists():
            rows.append({"name": name, "error": "missing source"})
            continue
        if name in prior:
            rows.append(prior[name])
            print(f"[{number:02d}/{len(sources)}] {name}: resume", flush=True)
            continue
        accepted = _detect(Path(source))
        row = {"name": name, "source": str(source), "accepted": accepted}
        print(f"[{number:02d}/{len(sources)}] {name}: accepted={len(accepted)}", flush=True)
        if accepted:
            row.update(_run_pair(name, Path(source)))
        rows.append(row)
        REPORT.write_text(json.dumps({"schema": SCHEMA, "complete": False, "rows": rows}, indent=2),
                          encoding="utf-8")

    measured = [row for row in rows if "baseline" in row]
    meters = ["wobble", "g2_steps", "kinks_per_100px", "micro_segs",
              "roundness", "mae", "ink_iou", "ssim", "seam_px",
              "boundary_f", "hausdorff95", "region_de2000_p95",
              "de_region_max"]
    deltas = {}
    for meter in meters:
        vals = [float(row["candidate"][meter]) - float(row["baseline"][meter])
                for row in measured
                if meter in row["candidate"] and meter in row["baseline"]
                and row["candidate"][meter] is not None
                and row["baseline"][meter] is not None]
        if vals:
            vals.sort()
            deltas[meter] = {"median": vals[len(vals) // 2],
                             "min": min(vals), "max": max(vals)}
    damaging = []
    for row in measured:
        base, cand = row["baseline"], row["candidate"]
        if (cand["ink_iou"] < base["ink_iou"] - 0.003
                or cand["ssim"] < base["ssim"] - 0.003
                or cand["wobble"] > base["wobble"] + 0.05
                or cand["kinks_per_100px"] > base["kinks_per_100px"] + 0.05):
            damaging.append(row["name"])
    result = {"schema": SCHEMA, "complete": True, "scanned": len(rows), "accepted_count": len(measured),
              "accepted_names": [row["name"] for row in measured],
              "deltas_candidate_minus_baseline": deltas,
              "damaging": damaging,
              "verdict": "PROMOTE" if measured and not damaging else
                         ("NO_TRIGGER" if not measured else "REJECT"),
              "rows": rows}
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("scanned", "accepted_count", "accepted_names", "damaging", "verdict")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
