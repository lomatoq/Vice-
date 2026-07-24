"""Experiment 5: bounded complexity stress for the integrated Phase-5 lanes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tempfile
import time
from typing import Callable

import cv2
import numpy as np

from .build_identity import bind_report
from PIL import Image, ImageDraw

from .evidence_ir import build_reir
from .macro_extractor import extract_visible_scene
from .macro_ir import MacroKind
from .macro_registry import build_base_registry, candidate_from_support, extend_registry
from .phase5_macros import Phase5Budgets, generate_phase5_macros


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment5" / "report.json"


def _tiny_components(path: Path, count: int = 500) -> None:
    image = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(image)
    columns = 25
    for index in range(count):
        x = 5 + (index % columns) * 20
        y = 5 + (index // columns) * 24
        draw.rectangle((x, y, x + 2, y + 2), fill=(12, 18, 28))
    image.save(path)


def _glyph_fragments(path: Path, count: int = 200) -> None:
    image = Image.new("RGB", (512, 320), "white")
    draw = ImageDraw.Draw(image)
    for index in range(count):
        group = index // 4
        part = index % 4
        gx = 5 + (group % 25) * 20
        gy = 8 + (group // 25) * 70
        if part == 0:
            draw.rectangle((gx, gy, gx + 3, gy + 22), fill="black")
        elif part == 1:
            draw.rectangle((gx + 4, gy, gx + 11, gy + 3), fill="black")
        elif part == 2:
            draw.rectangle((gx + 4, gy + 10, gx + 11, gy + 13), fill="black")
        else:
            draw.rectangle((gx + 4, gy + 19, gx + 11, gy + 22), fill="black")
    image.save(path)


def _nested_containers(path: Path, count: int = 30) -> None:
    image = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(image)
    for index in range(count):
        inset = 5 + index * 7
        if inset >= 250:
            break
        draw.rectangle(
            (inset, inset, 511 - inset, 511 - inset),
            outline=(15 + index * 3, 25 + index * 2, 40 + index * 2), width=2,
        )
    image.save(path)


def _dashed_segments(path: Path, count: int = 100) -> None:
    image = Image.new("RGB", (512, 256), "white")
    draw = ImageDraw.Draw(image)
    columns = 25
    for index in range(count):
        x = 6 + (index % columns) * 20
        y = 18 + (index // columns) * 55
        draw.line((x, y, x + 11, y), fill="black", width=3)
    image.save(path)


def _overlap_canvas(path: Path) -> None:
    image = Image.new("RGB", (384, 384), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((70, 70, 314, 314), fill=(35, 90, 170))
    draw.ellipse((125, 125, 259, 259), fill="white")
    image.save(path)


def _gradient_bands(path: Path) -> None:
    height, width = 256, 512
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    band = np.floor(x * 63.0) / 63.0
    rgb = np.zeros((height, width, 3), np.uint8)
    rgb[..., 0] = np.tile((22 + 215 * band).astype(np.uint8), (height, 1))
    rgb[..., 1] = np.tile((45 + 125 * band).astype(np.uint8), (height, 1))
    rgb[..., 2] = np.tile((210 - 145 * band).astype(np.uint8), (height, 1))
    Image.fromarray(rgb, "RGB").save(path)


def _q30_confetti(path: Path) -> None:
    rng = np.random.default_rng(20260721)
    image = Image.new("RGB", (384, 384), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((42, 52, 342, 330), radius=48, fill=(28, 72, 158))
    for x, y in rng.integers(0, 384, size=(350, 2)):
        value = int(rng.integers(70, 210))
        draw.point((int(x), int(y)), fill=(value, value, value))
    image.save(path, quality=30, subsampling=2)


def _overlap_candidates(reir, count: int) -> tuple:
    rows = []
    height, width = reir.height, reir.width
    for index in range(count):
        angle = 2.0 * math.pi * index / max(1, count)
        cx = 0.5 * width + math.cos(angle) * 0.08 * width
        cy = 0.5 * height + math.sin(angle) * 0.08 * height
        radius = (0.24 + 0.002 * index) * min(width, height)
        mask = np.zeros((height, width), np.uint8)
        cv2.circle(mask, (int(round(cx)), int(round(cy))), int(round(radius)), 1, -1)
        candidate = candidate_from_support(
            reir, family="shape", mask=mask > 0,
            roi_xyxy=(
                max(0, int(cx - radius)), max(0, int(cy - radius)),
                min(width, int(cx + radius + 1)), min(height, int(cy + radius + 1)),
            ),
            evidence_token_ids=(), score=0.50 + 0.002 * index,
            provenance=("experiment5-overlap-stressor",),
            kind=MacroKind.SHAPE, components=1, holes=0,
            prefix="experiment5-overlap",
        )
        if candidate is not None:
            rows.append(candidate)
    return tuple(rows)


def _evaluate_case(
    case_id: str, path: Path, *, overlap_count: int = 0,
    budget: Phase5Budgets | None = None,
) -> dict:
    limits = budget or Phase5Budgets()
    started = time.perf_counter()
    try:
        reir_started = time.perf_counter()
        reir = build_reir(path, max_dim=512)
        reir_ms = (time.perf_counter() - reir_started) * 1000.0

        bundle = generate_phase5_macros(reir, budget=limits, parallel=True)
        extras = _overlap_candidates(reir, overlap_count)
        registry_started = time.perf_counter()
        cmir = extend_registry(
            reir, build_base_registry(reir), bundle.candidates + extras,
        )
        registry_ms = (time.perf_counter() - registry_started) * 1000.0
        solution = extract_visible_scene(
            cmir, reir.hierarchy, exact_component_limit=18,
            time_budget_ms=1500.0,
        )
        timed_out = bool(
            solution.fallback_reason and "time" in solution.fallback_reason.lower()
        )
        structural_units = (
            len(reir.hierarchy.nodes) + len(reir.interfaces.interfaces)
        )
        return {
            "id": case_id, "status": "ok", "error": None,
            "processing_size": [reir.width, reir.height],
            "pixels": reir.width * reir.height,
            "hierarchy_nodes": len(reir.hierarchy.nodes),
            "interfaces": len(reir.interfaces.interfaces),
            "proposal_tokens": len(reir.proposal_tokens),
            "structural_units": structural_units,
            "phase5_counts": bundle.counts,
            "phase5_maximum_columns": limits.maximum_columns,
            "extra_overlapping_proposals": len(extras),
            "candidate_limits_respected": (
                bundle.counts["total"] <= limits.maximum_columns
                and len(extras) <= overlap_count
            ),
            "cmir_candidates": len(cmir.candidates),
            "reir_ms": reir_ms,
            "phase5_ms": bundle.elapsed_ms,
            "phase5_lane_ms": dict(bundle.lane_ms),
            "registry_ms": registry_ms,
            "solve_ms": solution.solve_ms,
            "total_ms": (time.perf_counter() - started) * 1000.0,
            "feasible": solution.feasible,
            "exact_cover": solution.exact_cover,
            "fallback_valid": solution.fallback_always_feasible,
            "timed_out": timed_out,
            "fallback_reason": solution.fallback_reason,
        }
    except MemoryError as error:
        return {
            "id": case_id, "status": "oom", "error": str(error),
            "candidate_limits_respected": False, "fallback_valid": False,
            "timed_out": False,
            "total_ms": (time.perf_counter() - started) * 1000.0,
        }
    except Exception as error:  # Experiment report must preserve the failing case.
        return {
            "id": case_id, "status": "error",
            "error": f"{type(error).__name__}: {error}",
            "candidate_limits_respected": False, "fallback_valid": False,
            "timed_out": False,
            "total_ms": (time.perf_counter() - started) * 1000.0,
        }


def _scale_probe(half: dict, full: dict) -> dict:
    if half.get("status") != "ok" or full.get("status") != "ok":
        return {"half": half["id"], "full": full["id"], "near_linear": False}
    unit_ratio = full["structural_units"] / max(1, half["structural_units"])
    time_ratio = full["phase5_ms"] / max(1e-6, half["phase5_ms"])
    bound = max(2.75, 2.20 * unit_ratio)
    return {
        "half": half["id"], "full": full["id"],
        "unit_ratio": unit_ratio, "phase5_time_ratio": time_ratio,
        "allowed_ratio": bound, "near_linear": time_ratio <= bound,
    }


def build_report() -> dict:
    builders: tuple[tuple[str, Callable[[Path], None], int], ...] = (
        ("500_tiny_components", lambda path: _tiny_components(path, 500), 0),
        ("200_glyph_fragments", lambda path: _glyph_fragments(path, 200), 0),
        ("nested_containers", lambda path: _nested_containers(path, 30), 0),
        ("100_dashed_segments", lambda path: _dashed_segments(path, 100), 0),
        ("50_overlapping_proposals", _overlap_canvas, 50),
        ("heavy_gradient_bands", _gradient_bands, 0),
        ("q30_confetti", _q30_confetti, 0),
    )
    rows = []
    probe_rows = []
    with tempfile.TemporaryDirectory(prefix="pcdc-exp5-") as directory:
        root = Path(directory)
        for case_id, builder, overlap_count in builders:
            suffix = ".jpg" if case_id == "q30_confetti" else ".png"
            path = root / f"{case_id}{suffix}"
            builder(path)
            rows.append(_evaluate_case(case_id, path, overlap_count=overlap_count))

        half_builders: tuple[tuple[str, Callable[[Path], None], str], ...] = (
            ("250_tiny_components", lambda path: _tiny_components(path, 250), "500_tiny_components"),
            ("nested_containers_half", lambda path: _nested_containers(path, 15), "nested_containers"),
            ("50_dashed_segments", lambda path: _dashed_segments(path, 50), "100_dashed_segments"),
        )
        by_id = {row["id"]: row for row in rows}
        for case_id, builder, full_id in half_builders:
            path = root / f"{case_id}.png"
            builder(path)
            half = _evaluate_case(case_id, path)
            probe_rows.append(_scale_probe(half, by_id[full_id]))

    no_timeout_oom = all(
        row.get("status") == "ok" and not row.get("timed_out", False)
        for row in rows
    )
    limits = all(bool(row.get("candidate_limits_respected")) for row in rows)
    fallback = all(bool(row.get("fallback_valid")) for row in rows)
    near_linear = all(bool(row.get("near_linear")) for row in probe_rows)
    gate = no_timeout_oom and limits and fallback and near_linear
    return {
        "schema": "pcdc-experiment5/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if gate else "failed",
        "gate_pass": gate,
        "gate": {
            "no_timeout_or_oom": no_timeout_oom,
            "candidate_limits_respected": limits,
            "runtime_near_linear_in_hierarchy_interfaces": near_linear,
            "fallback_valid": fallback,
        },
        "cases": rows, "scale_probes": probe_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = bind_report(build_report())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "status": report["status"], "gate": report["gate"],
        "out": str(args.out),
    }, indent=2))


if __name__ == "__main__":
    main()
