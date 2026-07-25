"""M0: support x materializer oracle (plan M0, S9 Experiment M0).

The question this answers before any further investment:

    is the remaining failure a SUPPORT problem or a MATERIALIZATION
    problem?

For each selected locus the reviewed human support is fed to both
materializers - the current smooth fitter (with its pixel fallback) and
the Materialization v2 race - so support quality is held constant and the
only variable is how the geometry is produced.

Case selection is driven by the human court itself (ledger 105): the rows
where the judge preferred legacy ("A pixelated, B crooked"), the rows the
candidate won, the both-bad ties, and controls.

Usage:
  C:\\Python312\\python.exe -m vice_compiler.experiment_materialization_oracle
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from .certificates import topology_signature
from .experiment1_evidence_coverage import decode_support_rle
from .materialization_certificates import component_correspondence
from .svg_fragment_renderer import render_fragment, render_program
from .text_materialization import generate_legacy_smooth_program
from .text_vector_court import race_materializations
from .wobble_metrics import turning_density

PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
COURT = PROJECT / "datasets" / "pcdc_textline_pairs_v2"
DEFAULT_OUT = (
    PROJECT / "benchmarks" / "pcdc_pre_v14"
    / "experiment_materialization_oracle.json"
)
BLACK = (0.0, 0.0, 0.0, 1.0)


def _load_reviewed_supports(limit: int | None = None):
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    reviews = json.loads((CORPUS / "review.json").read_text("utf-8"))["reviews"]
    rows = []
    for locus in manifest["loci"]:
        review = reviews.get(locus["id"])
        if not review or not review.get("support_rle"):
            continue
        width, height = (int(v) for v in review["support_size"])
        support = decode_support_rle(review["support_rle"], width, height)
        x1, y1, x2, y2 = (int(v) for v in review["roi_xyxy"])
        pad = 4
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2 = min(support.shape[1], x2 + pad)
        y2 = min(support.shape[0], y2 + pad)
        crop = support[y1:y2, x1:x2]
        if crop.shape[0] < 12 or crop.shape[1] < 12 or not crop.any():
            continue
        rows.append({
            "id": locus["id"], "category": locus.get("category", ""),
            "support": np.ascontiguousarray(crop),
            "source_path": str(locus["source"]["path"]),
            "roi": (x1, y1, x2, y2),
            "support_size": (width, height),
        })
        if limit and len(rows) >= limit:
            break
    return rows


def _human_choices() -> dict[str, str]:
    path = COURT / "review.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text("utf-8"))
    return {
        locus_id: answer.get("choice", "")
        for locus_id, answer in payload.get("answers", {}).items()
    }


def _legacy_delivery(support: np.ndarray, straight_rgba):
    """The current route: fitted G1 path, else the exact pixel fallback."""
    height, width = support.shape
    program = generate_legacy_smooth_program(
        support, program_id="legacy", source_line_id="line",
        straight_rgba=straight_rgba, density_proof=True,
    )
    if program is not None:
        rendered = render_program(program, width=width, height=height)
        return program, rendered, "legacy-current-smooth"
    from .export_writer import _paint, _pixel_run_path

    data = _pixel_run_path(support)
    if not data:
        return None, None, "none"
    fragment = (
        f'<path d="{data}" fill-rule="evenodd" {_paint((0, 0, 0, 1.0))}/>'
    )
    rendered = render_fragment(fragment, width=width, height=height)
    return None, rendered, "legacy-pixel-fallback"


def _metrics(delivered: np.ndarray, reference: np.ndarray) -> dict:
    intersection = int(np.sum(delivered & reference))
    union = int(np.sum(delivered | reference))
    correspondence = component_correspondence(reference, delivered)
    return {
        "iou": intersection / max(1, union),
        "topology": list(topology_signature(delivered)),
        "reference_topology": list(topology_signature(reference)),
        "correspondence_valid": bool(correspondence.valid),
        "correspondence_violations": list(correspondence.violations),
    }


def _source_coverage(row: dict, support: np.ndarray) -> np.ndarray:
    """Real ink coverage of the source crop (plan M3.1).

    Judging a materializer against the BINARY support makes the pixel-cell
    copy optimal by definition - the only honest reference is the raster
    the support came from.
    """
    from .coverage_evidence import robust_two_color_coverage

    try:
        raw = cv2.imread(row["source_path"], cv2.IMREAD_UNCHANGED)
        if raw is None:
            return support.astype(np.float32)
        if raw.ndim == 3 and raw.shape[2] == 4:
            alpha = raw[..., 3:4].astype(np.float32) / 255.0
            rgb = raw[..., :3].astype(np.float32) / 255.0
            rgb = rgb * alpha + 1.0 * (1.0 - alpha)
        elif raw.ndim == 3:
            rgb = raw[..., :3].astype(np.float32) / 255.0
        else:
            rgb = np.repeat(
                raw[..., None].astype(np.float32) / 255.0, 3, axis=2,
            )
        width, height = row["support_size"]
        if rgb.shape[:2] != (height, width):
            rgb = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_AREA)
        linear = np.where(
            rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4,
        ).astype(np.float32)
        x1, y1, x2, y2 = row["roi"]
        crop = linear[y1:y2, x1:x2]
        if crop.shape[:2] != support.shape:
            return support.astype(np.float32)
        estimate = robust_two_color_coverage(crop, support)
        if estimate.separable:
            return estimate.alpha
    except Exception:
        pass
    return support.astype(np.float32)


def run_case(row: dict) -> dict:
    support = np.asarray(row["support"], bool)
    height, width = support.shape
    started = time.perf_counter()
    legacy_program, legacy_render, legacy_family = _legacy_delivery(
        support, BLACK,
    )
    legacy_ms = (time.perf_counter() - started) * 1000.0
    legacy_mask = (
        legacy_render.alpha_mask if legacy_render is not None
        else np.zeros_like(support)
    )
    started = time.perf_counter()
    coverage = _source_coverage(row, support)
    race = race_materializations(
        support, record_id=row["id"], line_id="line", straight_rgba=BLACK,
        coverage=coverage,
    )
    v2_ms = (time.perf_counter() - started) * 1000.0
    if race is None:
        return {
            "id": row["id"], "category": row.get("category", ""),
            "status": "no-v2-program",
            "legacy": {"family": legacy_family, **_metrics(legacy_mask, support)},
        }
    winner = race.winner
    v2_mask = np.asarray(winner.ownership_support, bool)
    legacy_spans = (
        sum(len(path.spans) for path in legacy_program.paths)
        if legacy_program is not None else int(np.sum(
            np.abs(np.diff(np.pad(support.astype(np.int8), ((0, 0), (1, 1))),
                           axis=1)) == 1,
        )) * 4
    )
    return {
        "id": row["id"], "category": row.get("category", ""),
        "status": "ok",
        "legacy": {
            "family": legacy_family, "spans": int(legacy_spans),
            "turning_density": (
                float(turning_density(legacy_program))
                if legacy_program is not None else None
            ),
            "milliseconds": legacy_ms,
            **_metrics(legacy_mask, support),
        },
        "v2": {
            "family": winner.program.geometry_family,
            "spans": int(winner.resource_estimate.span_count),
            "turning_density": float(turning_density(winner.program)),
            "milliseconds": v2_ms,
            "decisions": [
                {
                    "candidate": decision.candidate_id,
                    "selected": decision.candidate_selected,
                    "reason": decision.reason,
                    "render_delta": decision.render_delta,
                    "fairness_delta": decision.fairness_delta,
                }
                for decision in race.decisions
            ],
            **_metrics(v2_mask, support),
        },
    }


def build_report(limit: int | None = None) -> dict:
    choices = _human_choices()
    rows = _load_reviewed_supports(limit=limit)
    results = [run_case(row) for row in rows]
    usable = [row for row in results if row["status"] == "ok"]
    def mean(key: str, side: str) -> float:
        values = [
            float(row[side][key]) for row in usable
            if row[side].get(key) is not None
        ]
        return float(np.mean(values)) if values else 0.0

    families: dict[str, int] = {}
    for row in usable:
        family = row["v2"]["family"]
        families[family] = families.get(family, 0) + 1
    v2_better_topology = sum(
        1 for row in usable
        if row["v2"]["correspondence_valid"]
        and not row["legacy"]["correspondence_valid"]
    )
    legacy_better_topology = sum(
        1 for row in usable
        if row["legacy"]["correspondence_valid"]
        and not row["v2"]["correspondence_valid"]
    )
    return {
        "schema": "pcdc-materialization-oracle/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": (
            "with the human support held constant, does the fair "
            "materializer deliver better geometry than the current one?"
        ),
        "cases": len(results), "usable": len(usable),
        "human_choice_counts": {
            choice: sum(1 for value in choices.values() if value == choice)
            for choice in ("legacy", "candidate", "tie")
        },
        "summary": {
            "legacy_mean_iou": mean("iou", "legacy"),
            "v2_mean_iou": mean("iou", "v2"),
            "legacy_mean_spans": mean("spans", "legacy"),
            "v2_mean_spans": mean("spans", "v2"),
            "legacy_mean_turning_density": mean("turning_density", "legacy"),
            "v2_mean_turning_density": mean("turning_density", "v2"),
            "legacy_p50_ms": float(np.percentile(
                [row["legacy"]["milliseconds"] for row in usable], 50,
            )) if usable else 0.0,
            "v2_p50_ms": float(np.percentile(
                [row["v2"]["milliseconds"] for row in usable], 50,
            )) if usable else 0.0,
            "v2_p95_ms": float(np.percentile(
                [row["v2"]["milliseconds"] for row in usable], 95,
            )) if usable else 0.0,
            "v2_family_counts": families,
            "v2_fixes_topology": v2_better_topology,
            "v2_breaks_topology": legacy_better_topology,
        },
        "rows": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    report = build_report(limit=args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
