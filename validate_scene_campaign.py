"""Run the single post-BUILD_FREEZE validation campaign.

This runner is intentionally a recorder, not a tuner.  It verifies the frozen
inputs before every campaign, streams every subprocess to an immutable log,
continues after red sections so failures cannot hide other failures, and writes
one machine-readable report plus a compact Markdown summary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

from vice_scene.freeze import DEFAULT_FREEZE, verify_freeze


ROOT = Path(__file__).resolve().parent
BENCHMARKS = ROOT / "benchmarks"
REGRESSION_TESTS = (
    "test_dp_physical_fidelity.py",
    "test_native_density_contract.py",
    "test_dp4x_contract.py",
    "test_digital_circle_court.py",
    "test_glyph_repair.py",
    "test_text_evidence_shield.py",
    "test_stroke_seams.py",
    "test_structural_diagram_lane.py",
    "test_jpeg_grid.py",
    "test_codec_legitimacy.py",
    "test_eye_metrics.py",
    "test_strike0_metrics.py",
)
ABLATIONS: dict[str, tuple[str, ...]] = {
    "baseline": (),
    "no-evidence": ("evidence",),
    "no-appearance": ("appearance",),
    "no-topology": ("topology",),
    "no-shapes": ("whole_shapes",),
    "no-shared-boundaries": ("shared_boundaries",),
    "no-text": ("text_scene", "exact_font_path"),
    "no-exact-font": ("exact_font_path",),
    "no-forward-court": ("forward_court",),
    "no-idealization": ("idealization",),
    "no-residual-repair": ("residual_repair",),
    "no-gap-filler": ("gap_filler",),
    "pair-no-text-shapes": ("text_scene", "exact_font_path", "whole_shapes"),
    "pair-no-geometry": ("whole_shapes", "shared_boundaries", "idealization"),
    "pair-no-court-ideal": ("forward_court", "idealization"),
    "pair-no-evidence-topology": ("evidence", "topology"),
    "pair-no-repair-fill": ("residual_repair", "gap_filler"),
}


class Campaign:
    def __init__(self, root: Path, freeze_hash: str):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.logs = self.root / "logs"
        self.logs.mkdir(exist_ok=True)
        self.report_path = self.root / "campaign.json"
        self.markdown_path = self.root / "campaign.md"
        self.payload = {
            "schema": "vice-scene-validation-campaign/1",
            "freeze_hash": freeze_hash,
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "policy": "record-only after freeze; no parameter tuning",
            "runs": [],
            "artifacts": {},
        }
        self._flush()

    def run(self, name: str, command: Iterable[object], *, cwd: Path = ROOT,
            timeout_seconds: int = 14_400) -> dict:
        argv = [str(item) for item in command]
        log = self.logs / f"{len(self.payload['runs']) + 1:02d}_{_safe(name)}.log"
        print(f"\n=== {name} ===", flush=True)
        print(subprocess.list2cmdline(argv), flush=True)
        started = time.perf_counter()
        return_code = -999
        error = None
        with log.open("w", encoding="utf-8", errors="replace") as stream:
            stream.write(subprocess.list2cmdline(argv) + "\n\n")
            try:
                process = subprocess.Popen(
                    argv, cwd=str(cwd), stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                    errors="replace", env={**os.environ, "PYTHONUTF8": "1"},
                )
                assert process.stdout is not None
                deadline = time.monotonic() + timeout_seconds
                while True:
                    line = process.stdout.readline()
                    if line:
                        print(line, end="", flush=True)
                        stream.write(line)
                    elif process.poll() is not None:
                        break
                    if time.monotonic() > deadline:
                        process.kill()
                        error = f"timeout after {timeout_seconds}s"
                        break
                return_code = process.wait()
            except Exception as exc:  # keep the remainder of the court visible
                error = f"{type(exc).__name__}: {exc}"
                stream.write(error + "\n")
        row = {
            "name": name, "command": argv, "return_code": return_code,
            "passed": return_code == 0 and error is None,
            "seconds": round(time.perf_counter() - started, 3),
            "log": str(log.relative_to(ROOT)), "error": error,
        }
        self.payload["runs"].append(row)
        self._flush()
        return row

    def artifact(self, name: str, path: Path) -> None:
        self.payload["artifacts"][name] = str(path)
        self._flush()

    def finish(self) -> None:
        self.payload["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        runs = self.payload["runs"]
        self.payload["machine_sections_green"] = bool(runs) and all(
            row["passed"] for row in runs)
        # A machine metric may reject promotion, but it may never approve the
        # unresolved human comparison required by the plan.
        self.payload["promotion"] = {
            "approved": False,
            "human_court": "pending-current-freeze",
            "reason": ("human court is a mandatory promotion gate; Best remains incumbent"
                       if self.payload["machine_sections_green"] else
                       "one or more machine validation sections are red"),
        }
        self._flush()

    def _flush(self) -> None:
        self.report_path.write_text(
            json.dumps(self.payload, ensure_ascii=False, indent=2,
                       sort_keys=True) + "\n", encoding="utf-8")
        lines = [
            "# V-ICE Scene frozen validation campaign", "",
            f"- Freeze: `{self.payload['freeze_hash']}`",
            f"- Policy: {self.payload['policy']}", "",
            "| Section | Status | Seconds | Log |", "|---|---:|---:|---|",
        ]
        for row in self.payload["runs"]:
            status = "PASS" if row["passed"] else "FAIL"
            lines.append(f"| {row['name']} | {status} | {row['seconds']} | `{row['log']}` |")
        if "promotion" in self.payload:
            lines.extend(["", "## Promotion", "",
                          f"**Not promoted.** {self.payload['promotion']['reason']}."])
        self.markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ablations(campaign: Campaign, python: str, stems: tuple[str, ...]) -> Path:
    root = campaign.root / "ablations"
    root.mkdir(exist_ok=True)
    import benchmark_vai as benchmark
    rows = []
    for variant, modules in ABLATIONS.items():
        for stem in stems:
            source = benchmark.find_source(stem)
            if source is None:
                rows.append({"variant": variant, "stem": stem,
                             "error": "validated source not found"})
                continue
            destination = root / variant
            command = [python, "-X", "utf8", "-m", "vice_scene", source,
                       "--out", destination]
            for module in modules:
                command.extend(("--ablate", module))
            run = campaign.run(f"ablation:{variant}:{stem}", command,
                               timeout_seconds=1_800)
            report_path = destination / source.stem / "report.json"
            if report_path.is_file():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                rows.append({
                    "variant": variant, "ablations": list(modules), "stem": stem,
                    "passed": run["passed"], "render_nll": report.get("render_nll"),
                    "regions": report.get("regions"),
                    "primitives": report.get("rendered_primitive_count"),
                    "wall_seconds": report.get("resource", {}).get("wall_seconds"),
                    "abstained": report.get("abstained"),
                })
            else:
                rows.append({"variant": variant, "ablations": list(modules),
                             "stem": stem, "passed": False,
                             "error": "report.json missing"})
    baseline = {row["stem"]: row for row in rows if row["variant"] == "baseline"}
    for row in rows:
        base = baseline.get(row["stem"])
        if (base and row.get("render_nll") is not None
                and base.get("render_nll") is not None):
            row["render_nll_delta"] = row["render_nll"] - base["render_nll"]
    report_path = root / "ablation_matrix.json"
    report_path.write_text(json.dumps({
        "schema": "vice-scene-ablation-matrix/1", "stems": list(stems),
        "variants": {key: list(value) for key, value in ABLATIONS.items()},
        "rows": rows,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--vai-count", type=int, default=50)
    parser.add_argument("--challenge-limit", type=int, default=115)
    parser.add_argument("--ablation-count", type=int, default=3)
    args = parser.parse_args()
    okay, errors = verify_freeze(args.freeze)
    if not okay:
        for error in errors:
            print(f"BUILD_FREEZE error: {error}", file=sys.stderr)
        return 2
    frozen = json.loads(args.freeze.read_text(encoding="utf-8"))
    freeze_hash = frozen["freeze_hash"]
    root = BENCHMARKS / "scene_validation" / freeze_hash[:16]
    if (root / "campaign.json").exists():
        print(f"refusing to overwrite an existing frozen campaign: {root}", file=sys.stderr)
        return 3
    campaign = Campaign(root, freeze_hash)
    python = sys.executable

    campaign.run("scene synthetic/build oracle suite",
                 [python, "-X", "utf8", "test_scene_engine.py"])
    synthetic_report = campaign.root / "synthetic" / "synthetic_validation.json"
    campaign.run("synthetic renderer holdout and selector calibration", [
        python, "-X", "utf8", "validate_scene_synthetic.py", "--out",
        campaign.root / "synthetic",
    ])
    campaign.artifact("synthetic_validation", synthetic_report)
    for test in REGRESSION_TESTS:
        if (ROOT / test).is_file():
            campaign.run(f"regression:{Path(test).stem}",
                         [python, "-X", "utf8", test])
    campaign.run("current stage regression suite",
                 [python, "-X", "utf8", "benchmark_stages.py"])

    vai_snapshot = BENCHMARKS / "scene_vai50_freeze.json"
    campaign.run("VAI50 equal-input external comparison", [
        python, "-X", "utf8", "benchmark_vai.py", "--mode", "scene",
        "--n", args.vai_count, "--snapshot", vai_snapshot.name,
        "--vai-cache", "vai_snapshot_production_fresh50_final.json",
    ])
    campaign.artifact("vai50", vai_snapshot)

    campaign.run("115-item blind challenge pack", [
        python, "-X", "utf8", "challenge_eval.py", "--plates", "1,2,3,4",
        "--limit", args.challenge_limit, "--mode", "scene",
    ], timeout_seconds=28_800)
    challenge_report = Path(
        r"C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\eval\report.json")
    campaign.artifact("challenge115", challenge_report)

    import benchmark_vai as benchmark
    stems = tuple(benchmark.frozen_stems(args.ablation_count))
    ablation_report = run_ablations(campaign, python, stems)
    campaign.artifact("ablation_matrix", ablation_report)
    campaign.run("legacy-only ablation", [
        python, "-X", "utf8", "benchmark_vai.py", "--mode", "paper-regions",
        "--stems", ",".join(stems), "--snapshot", "scene_ablation_legacy.json",
        "--vai-cache", "vai_snapshot_production_fresh50_final.json",
    ])
    oracle_root = campaign.root / "oracle_diagnostics"
    campaign.run("proposal-oracle and selector-oracle ablations", [
        python, "-X", "utf8", "-m", "vice_scene.oracle_diagnostics",
        "--out", oracle_root,
    ])
    campaign.artifact("oracle_diagnostics", oracle_root / "oracle_diagnostics.json")

    forensics_md = campaign.root / "svg_forensics.md"
    forensics_json = campaign.root / "svg_forensics.json"
    campaign.run("structural SVG forensics", [
        python, "-X", "utf8", "vectorizer_ai_svg_forensics.py",
        BENCHMARKS / "vai_work" / "scene",
        Path(r"C:\Users\nirrt\Toolset\v-ice pictures\vai"),
        "--out", forensics_md, "--json", forensics_json,
    ])
    campaign.artifact("svg_forensics", forensics_json)

    campaign.run("resolution-honest blind crop court", [
        python, "-X", "utf8", "build_vai_crop_court.py", "--snapshot",
        vai_snapshot, "--count", "12", "--selection", "hard-tail",
        "--work-mode", "scene",
    ])
    campaign.artifact("blind_court", ROOT / "web_preview" / "court.html")
    campaign.artifact("blind_manifest", BENCHMARKS / "vai_crop_court_manifest.json")
    campaign.finish()
    print(f"\nCampaign report -> {campaign.report_path}")
    print(f"Campaign summary -> {campaign.markdown_path}")
    return 0 if campaign.payload["machine_sections_green"] else 1


def _safe(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "_"
                   for character in value)[:110]


if __name__ == "__main__":
    raise SystemExit(main())
