"""Contingent N1/N2 worst-tile embedding battery on blind round-1 pairs."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

import benchmark_vai as bv
from dino_perceptual import backend_status, worst_tile_distances

ROOT = Path(__file__).parent
PACK = Path(r"C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack")
EVAL = PACK / "eval"
PREFERENCE = ROOT / "benchmarks" / "preference_round1.json"
OUTPUT = ROOT / "benchmarks" / "worst_tile_dino_battery.json"


def _ours_svg(item: int) -> Path:
    matches = sorted((EVAL / "ours" / f"item{item:03d}").glob("**/03_rebuilt_filled.svg"))
    if len(matches) != 1:
        raise FileNotFoundError(f"item{item:03d}: expected one OURS SVG, got {len(matches)}")
    return matches[0]


def main() -> int:
    status = backend_status()
    if not status["ready"]:
        raise RuntimeError(status)
    answers = json.loads(PREFERENCE.read_text(encoding="utf-8"))["answers"]
    rows = []
    for index, answer in enumerate(answers, 1):
        item = int(answer["item"])
        source = Image.open(EVAL / "crops" / f"item{item:03d}.png").convert("RGB")
        ours = bv.render_svg(_ours_svg(item), source.width).resize(source.size, Image.Resampling.LANCZOS)
        vai = bv.render_svg(EVAL / "items" / f"item{item:03d}_vai.svg", source.width).resize(
            source.size, Image.Resampling.LANCZOS)
        ours_meter, vai_meter = worst_tile_distances(source, [ours, vai])
        delta = round(ours_meter["dino_tile_max"] - vai_meter["dino_tile_max"], 6)
        row = {"item": item, "winner": answer["winner"], "delta": delta,
               "ours": ours_meter, "vai": vai_meter}
        rows.append(row)
        print(f"[{index:02}/{len(answers)}] item{item:03}: {delta:+.5f}", flush=True)

    wins = [row["delta"] for row in rows if row["winner"] == "ours"]
    losses = [row["delta"] for row in rows if row["winner"] == "vai"]
    ceiling = max(wins)
    separated = sum(delta > ceiling for delta in losses)
    sign_correct = sum(row["delta"] > 0 for row in rows if row["winner"] == "vai") + sum(
        row["delta"] < 0 for row in rows if row["winner"] == "ours")
    report = {
        "backend": status,
        "source": str(PREFERENCE),
        "n": len(rows),
        "losses_above_all_wins": separated,
        "losses_total": len(losses),
        "win_ceiling": round(float(ceiling), 6),
        "direction_correct_non_ties": sign_correct,
        "gate_9_of_11": "PASS" if separated >= 9 else "FAIL",
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    print("->", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
