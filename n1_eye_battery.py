"""Council N1: eye-aligned metric battery on the cached blind preference set.

No vectorization is performed.  The script reuses the exact source crops and
OURS/VAI SVGs that the user judged in preference round 1, then writes a compact
decomposition report to benchmarks/n1_eye_battery.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import benchmark_vai as bv

ROOT = Path(__file__).resolve().parent
PACK = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack")
EVAL = PACK / "eval"
PREFERENCE = ROOT / "benchmarks" / "preference_round1.json"
OUTPUT = ROOT / "benchmarks" / "n1_eye_battery.json"
METRIC_KEYS = ("local_de_max", "ocr_legibility", "census_errors", "sym_break",
               "region_de2000_p95", "de_region_max", "rot90_sym_break")


def _ours_svg(item: int) -> Path:
    matches = sorted((EVAL / "ours" / f"item{item:03d}").glob("**/03_rebuilt_filled.svg"))
    if len(matches) != 1:
        raise FileNotFoundError(f"item{item:03d}: expected one OURS SVG, found {len(matches)}")
    return matches[0]


def _delta(ours: dict, vai: dict, key: str) -> float | None:
    first, second = ours.get(key), vai.get(key)
    if first is None or second is None:
        return None
    return round(float(first) - float(second), 4)


def _diagnosis(row: dict) -> list[str]:
    tags: list[str] = []
    deltas = row["deltas"]
    ours = row["ours"]
    if deltas.get("ocr_legibility") is not None and deltas["ocr_legibility"] > 0.05:
        tags.append("glyph_legibility")
    if deltas.get("census_errors") is not None and deltas["census_errors"] > 0:
        tags.append("component_topology")
    if deltas.get("sym_break") is not None and deltas["sym_break"] > 0.02:
        tags.append("symmetry")
    if deltas.get("rot90_sym_break") is not None and deltas["rot90_sym_break"] > 0.02:
        tags.append("rot90_symmetry")
    if deltas.get("de_region_max") is not None and deltas["de_region_max"] > 2.3:
        tags.append("categorical_colour")
    if deltas.get("local_de_max") is not None and deltas["local_de_max"] > 0:
        tags.append("local_raster")
    if ours.get("holes_lost", 0) > 0:
        tags.append("counter_loss")
    return tags or ["unexplained"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    preference = json.loads(PREFERENCE.read_text(encoding="utf-8"))
    rows = []
    for answer in preference["answers"]:
        item = int(answer["item"])
        crop = EVAL / "crops" / f"item{item:03d}.png"
        vai_svg = EVAL / "items" / f"item{item:03d}_vai.svg"
        ours_svg = _ours_svg(item)
        if not crop.is_file() or not vai_svg.is_file():
            raise FileNotFoundError(f"missing cached blind assets for item{item:03d}")
        print(f"item{item:03d}: eye meters...", flush=True)
        ours = bv.eye_meters(ours_svg, crop)
        vai = bv.eye_meters(vai_svg, crop)
        deltas = {key: _delta(ours, vai, key) for key in METRIC_KEYS}
        row = {"item": item, "winner": answer["winner"],
               "category": answer.get("category"), "note": answer.get("note", ""),
               "ours": ours, "vai": vai, "deltas": deltas}
        row["diagnosis"] = _diagnosis(row)
        rows.append(row)

    losses = [row for row in rows if row["winner"] == "vai"]
    wins = [row for row in rows if row["winner"] == "ours"]
    separation = {}
    control_ceilings = {}
    for key in METRIC_KEYS:
        win_values = [row["deltas"][key] for row in wins if row["deltas"][key] is not None]
        loss_values = [row["deltas"][key] for row in losses if row["deltas"][key] is not None]
        if not win_values or not loss_values:
            separation[key] = None
            continue
        win_ceiling = max(win_values)
        control_ceilings[key] = win_ceiling
        separation[key] = {"losses_above_all_wins": sum(v > win_ceiling for v in loss_values),
                           "losses_total": len(loss_values),
                           "win_ceiling": round(float(win_ceiling), 4)}

    # This is a decomposition of the already-judged round, not a promoted
    # classifier: each loss receives the meters on which it sits outside the
    # complete OURS-win control envelope.  It answers which blind failures the
    # N1 battery can explain while retaining the plan's per-meter kill rules.
    for row in rows:
        row["outside_win_envelope"] = [
            key for key, ceiling in control_ceilings.items()
            if row["deltas"].get(key) is not None and row["deltas"][key] > ceiling
        ]
    explained_losses = sum(bool(row["outside_win_envelope"]) for row in losses)

    report = {"source": str(PREFERENCE), "n": len(rows),
              "human": {"ours": len(wins), "vai": len(losses),
                        "tie": sum(row["winner"] == "tie" for row in rows)},
              "separation": separation,
              "combined_decomposition": {
                  "explained_losses": explained_losses,
                  "losses_total": len(losses),
                  "note": "diagnostic union outside the OURS-win envelope; not a trained gate"
              },
              "plan_verdict": {
                  "local_defeat_gate": "FAIL" if separation.get("local_de_max", {}).get(
                      "losses_above_all_wins", 0) < 9 else "PASS",
                  "worst_tile_embedding": "QUEUED" if separation.get("local_de_max", {}).get(
                      "losses_above_all_wins", 0) < 9 else "NOT_NEEDED",
                  "component_census": "DIAGNOSTIC_ONLY"
              },
              "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== N1 separation (positive delta = OURS worse) ===")
    for key, result in separation.items():
        print(f"{key:18} {result}")
    print(f"combined           {explained_losses}/{len(losses)} losses outside win envelope")
    print("local gate         ", report["plan_verdict"]["local_defeat_gate"],
          "-> worst-tile", report["plan_verdict"]["worst_tile_embedding"])
    print("report ->", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
