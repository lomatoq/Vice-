"""Separate the variable- and constant-width stroke-lane regression causes."""

from __future__ import annotations

import json
from pathlib import Path

import benchmark_stages as stages
import geometry_vectorizer as gv


ROOT = Path(__file__).resolve().parent


def main() -> int:
    targets = {
        "bars_clean": ROOT / "benchmarks" / "work" / "bars_clean.png",
        "cross": ROOT / "benchmarks" / "work" / "cross.png",
    }
    snapshot = json.loads((ROOT / "benchmarks" / "stage_snapshot.json").read_text(
        encoding="utf-8"))
    original_variable = gv._detect_variable_strokes
    original_constant = gv._detect_stroke
    rows = []
    try:
        for variant in ("no-variable", "no-constant"):
            gv._detect_variable_strokes = (lambda mask, analysis_scale: None) \
                if variant == "no-variable" else original_variable
            gv._detect_stroke = (lambda mask, analysis_scale: None) \
                if variant == "no-constant" else original_constant
            for name, source in targets.items():
                candidate = stages.fit_case(f"{name}_{variant}", source,
                                            smoothing="paper")
                rows.append({
                    "name": name,
                    "variant": variant,
                    "current": snapshot["synthetic"][name],
                    "candidate": candidate,
                })
    finally:
        gv._detect_variable_strokes = original_variable
        gv._detect_stroke = original_constant
    output = ROOT / "benchmarks" / "legacy_stroke_lane_split_ablation.json"
    output.write_text(json.dumps({
        "schema": "vice-legacy-stroke-lane-split-ablation/1",
        "rows": rows,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in rows:
        current, candidate = row["current"], row["candidate"]
        print(row["variant"], row["name"],
              f"regions {current['regions']}->{candidate['regions']}",
              f"prims {current['prims']}->{candidate['prims']}",
              f"iou {current['raster_iou']}->{candidate['raster_iou']}",
              f"seconds {current['secs']}->{candidate['secs']}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

