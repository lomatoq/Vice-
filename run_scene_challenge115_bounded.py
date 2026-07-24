"""Resolution-honest 115-item blind court with per-item resource accounting."""

from __future__ import annotations

import argparse
import html
import io
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

import benchmark_vai as bv
from run_scene_vai50_bounded import _run_monitored
from vice_scene.freeze import verify_freeze


ROOT = Path(__file__).resolve().parent
PACK = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack")
PLATES = PACK / "plates"
CAMPAIGN = ROOT / "benchmarks" / "scene_validation" / "33bc0d63e4b82734"
OUT = CAMPAIGN / "challenge115_bounded"
FREEZE = ROOT / "BUILD_FREEZE.json"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _number(element: str, name: str, default: float = 0.0) -> float:
    match = re.search(rf'\b{name}="([+-]?(?:\d+(?:\.\d*)?|\.\d+))', element)
    return float(match.group(1)) if match else default


def _transform_point(x: float, y: float, transform: str) -> tuple[float, float]:
    """Apply the simple transforms emitted by the supplied VAI plate SVGs."""
    operations = re.findall(r'(translate|rotate)\s*\(([^)]*)\)', transform)
    # SVG transform lists multiply matrices left-to-right, so a column-vector
    # point sees the rightmost operation first.  In VAI's common
    # ``translate(cx,cy) rotate(a)`` form this keeps a local origin at (cx,cy).
    for name, arguments in reversed(operations):
        values = [float(value) for value in re.findall(
            r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', arguments)]
        if name == "translate" and values:
            x += values[0]
            y += values[1] if len(values) > 1 else 0.0
        elif name == "rotate" and values:
            angle = math.radians(values[0])
            cx = values[1] if len(values) > 2 else 0.0
            cy = values[2] if len(values) > 2 else 0.0
            dx, dy = x - cx, y - cy
            x = cx + math.cos(angle) * dx - math.sin(angle) * dy
            y = cy + math.sin(angle) * dx + math.cos(angle) * dy
    return x, y


def _element_bbox(element: str) -> tuple[float, float, float, float] | None:
    from svgpathtools import parse_path

    tag_match = re.match(r'<([A-Za-z]+)\b', element)
    if not tag_match:
        return None
    tag = tag_match.group(1).lower()
    transform_match = re.search(r'\btransform="([^"]*)"', element)
    transform = html.unescape(transform_match.group(1)) if transform_match else ""
    if tag == "path":
        data = re.search(r'\bd="([^"]+)"', element)
        if not data:
            return None
        path = parse_path(html.unescape(data.group(1)))
        if not len(path):
            return None
        x0, x1, y0, y1 = path.bbox()
        corners = [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]
    elif tag == "circle":
        cx, cy, radius = _number(element, "cx"), _number(element, "cy"), _number(element, "r")
        corners = [(cx - radius, cy - radius), (cx + radius, cy + radius)]
    elif tag == "ellipse":
        cx, cy = _number(element, "cx"), _number(element, "cy")
        rx, ry = _number(element, "rx"), _number(element, "ry")
        corners = [(cx + sx * rx, cy + sy * ry)
                   for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)]
    elif tag == "rect":
        x, y = _number(element, "x"), _number(element, "y")
        width, height = _number(element, "width"), _number(element, "height")
        corners = [(x, y), (x + width, y), (x, y + height), (x + width, y + height)]
    elif tag == "line":
        corners = [(_number(element, "x1"), _number(element, "y1")),
                   (_number(element, "x2"), _number(element, "y2"))]
    elif tag in {"polygon", "polyline"}:
        points_match = re.search(r'\bpoints="([^"]+)"', element)
        if not points_match:
            return None
        values = [float(value) for value in re.findall(
            r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', points_match.group(1))]
        corners = list(zip(values[0::2], values[1::2]))
    else:
        return None
    if not corners:
        return None
    transformed = [_transform_point(float(x), float(y), transform) for x, y in corners]
    xs, ys = zip(*transformed)
    return min(xs), min(ys), max(xs), max(ys)


def split_vai_local(plate_no: int, layout: list[dict], destination: Path) -> tuple[dict[int, dict[str, Path]], dict]:
    source = PLATES / f"plate_{plate_no:02}_vai.svg"
    if not source.is_file():
        return {}, {"plate": plate_no, "status": "missing-plate", "graphics": 0,
                    "assigned": 0, "unassigned": 0, "coverage": 0.0}
    text = source.read_text(encoding="utf-8", errors="replace")
    viewbox_match = re.search(
        r'\bviewBox="([+-]?[\d.]+)[ ,]+([+-]?[\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)"',
        text,
    )
    if not viewbox_match:
        raise ValueError(f"plate {plate_no} has no numeric viewBox")
    vx, vy, vw, vh = (float(value) for value in viewbox_match.groups())
    # Keep every graphics kind used by the supplied VAI files, in document
    # order.  The previous path-only splitter silently deleted native circles,
    # ellipses and rectangles and therefore biased the court against VAI.
    element_pattern = re.compile(
        r"<(?:path|circle|ellipse|rect|line|polygon|polyline)\b[^>]*/>"
        r"|<(?:path|circle|ellipse|rect|line|polygon|polyline)\b[^>]*>.*?</(?:path|circle|ellipse|rect|line|polygon|polyline)>",
        flags=re.S,
    )
    group_match = re.search(r'<g\b([^>]*)>(.*?)</g>', text, flags=re.S)
    group_attributes = group_match.group(1) if group_match else ""
    group_span = (group_match.start(2), group_match.end(2)) if group_match else (-1, -1)
    elements = [(match.group(0), group_span[0] <= match.start() < group_span[1])
                for match in element_pattern.finditer(text)]
    cells = [(index, item) for index, item in enumerate(layout)
             if int(item["plate"]) == plate_no]
    assigned: dict[int, list[tuple[str, bool]]] = {index: [] for index, _ in cells}
    unassigned: list[tuple[str, bool, tuple[float, float, float, float] | None]] = []
    for element, in_group in elements:
        try:
            bbox = _element_bbox(element)
        except Exception:
            bbox = None
        if bbox is None:
            unassigned.append((element, in_group, None))
            continue
        x0, y0, x1, y1 = bbox
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        area = max(1e-6, (x1 - x0) * (y1 - y0))
        found = False
        for index, item in cells:
            bx0, by0, bx1, by1 = item["bbox"]
            if bx0 - 6 <= cx <= bx1 + 6 and by0 - 6 <= cy <= by1 + 6:
                if area > 4.0 * (bx1 - bx0) * (by1 - by0):
                    break
                assigned[index].append((element, in_group))
                found = True
                break
        if not found:
            unassigned.append((element, in_group, bbox))
    # VAI's cutout export contains one plate-sized compound white path: outer
    # background plus negative loops for all shapes.  It is visually essential
    # and must be present in every viewBox crop, but must be excluded from the
    # path-space geometry meters because it also contains all other cells.
    shared = []
    leftovers = []
    for element, in_group, bbox in unassigned:
        if (bbox is not None and not in_group
                and bbox[0] <= vx + 1.0 and bbox[1] <= vy + 1.0
                and bbox[2] >= vx + vw - 1.0 and bbox[3] >= vy + vh - 1.0):
            shared.append(element)
        else:
            leftovers.append((element, in_group, bbox))
    destination.mkdir(parents=True, exist_ok=True)
    result = {}
    for index, item in cells:
        if not assigned[index]:
            continue
        bx0, by0, bx1, by1 = item["bbox"]
        width, height = bx1 - bx0, by1 - by0
        grouped = "".join(element for element, in_group in assigned[index] if in_group)
        ungrouped = "".join(element for element, in_group in assigned[index] if not in_group)
        inherited = f'<g{group_attributes}>{grouped}</g>' if grouped else ""
        root = (f'<svg xmlns="http://www.w3.org/2000/svg" '
               f'viewBox="{bx0} {by0} {width} {height}" width="{width}" height="{height}">'
               f'<rect x="{bx0}" y="{by0}" width="{width}" height="{height}" fill="#ffffff"/>')
        raster_svg = root + inherited + "".join(shared) + ungrouped + "</svg>"
        geometry_svg = root + inherited + ungrouped + "</svg>"
        output = destination / f"item{index:03}_vai.svg"
        geometry_output = destination / f"item{index:03}_vai_geometry.svg"
        output.write_text(raster_svg, encoding="utf-8")
        geometry_output.write_text(geometry_svg, encoding="utf-8")
        result[index] = {"raster": output, "geometry": geometry_output}
    assigned_count = sum(len(value) for value in assigned.values())
    accounted_count = assigned_count + len(shared)
    coverage = accounted_count / len(elements) if elements else 0.0
    audit = {
        "plate": plate_no,
        "status": "complete" if coverage >= 0.995 else "incomplete",
        "graphics": len(elements),
        "assigned_to_cells": assigned_count,
        "shared_plate_compound_paths": len(shared),
        "unassigned": len(leftovers),
        "coverage": round(coverage, 6),
        "cells": len(cells),
        "cells_with_graphics": len(result),
    }
    return result, audit


def validate_split_rasters(layout: list[dict], items: dict[int, dict[str, Path]]) -> dict:
    """Prove that isolated SVG cells reproduce crops of the original VAI plates."""
    import resvg_py

    plate_renders = {}
    for plate_no in (1, 2, 3, 4):
        source = PLATES / f"plate_{plate_no:02}_vai.svg"
        encoded = resvg_py.svg_to_bytes(
            svg_string=source.read_text(encoding="utf-8"), width=1620)
        rgba = Image.open(io.BytesIO(bytes(encoded))).convert("RGBA")
        rgb = Image.new("RGB", rgba.size, "white")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        plate_renders[plate_no] = rgb
    maes = []
    rows = []
    for index, item in enumerate(layout):
        bx0, by0, bx1, by1 = (int(value) for value in item["bbox"])
        width = bx1 - bx0
        encoded = resvg_py.svg_to_bytes(
            svg_string=items[index]["raster"].read_text(encoding="utf-8"), width=width)
        rgba = Image.open(io.BytesIO(bytes(encoded))).convert("RGBA")
        isolated = Image.new("RGB", rgba.size, "white")
        isolated.paste(rgba, mask=rgba.getchannel("A"))
        reference = plate_renders[int(item["plate"])].crop((bx0, by0, bx1, by1))
        delta = np.abs(np.asarray(isolated, np.int16) - np.asarray(reference, np.int16))
        mae = float(np.mean(delta))
        maes.append(mae)
        rows.append({"item": index, "mae": round(mae, 6),
                     "max_channel_delta": int(np.max(delta))})
    p95 = float(np.percentile(maes, 95)) if maes else float("inf")
    maximum = max(maes, default=float("inf"))
    passed = bool(maes) and float(np.mean(maes)) <= 0.10 and p95 <= 0.25 and maximum <= 0.50
    return {
        "status": "PASS" if passed else "FAIL",
        "items": len(rows),
        "mae_mean": round(float(np.mean(maes)), 6) if maes else None,
        "mae_p95": round(p95, 6) if maes else None,
        "mae_max": round(maximum, 6) if maes else None,
        "exact_items": sum(row["max_channel_delta"] == 0 for row in rows),
        "worst": sorted(rows, key=lambda row: row["mae"], reverse=True)[:10],
    }


def _aggregate_category(rows: list[dict]) -> dict:
    output = {}
    for meter in bv.KEY_METERS:
        ours_values, vai_values, wins, ties = [], [], 0, 0
        for row in rows:
            ours = row.get("ours", {}).get(meter)
            vai = row.get("vai", {}).get(meter)
            if ours is None or vai is None:
                continue
            ours_values.append(float(ours))
            vai_values.append(float(vai))
            if abs(float(ours) - float(vai)) < 1e-9:
                ties += 1
            elif (float(ours) < float(vai)) == (meter in bv.LOWER_BETTER):
                wins += 1
        if ours_values:
            output[meter] = {
                "wins": f"{wins}+{ties}t/{len(ours_values)}",
                "median": [round(float(np.median(ours_values)), 4),
                           round(float(np.median(vai_values)), 4)],
                "p95": [round(float(np.percentile(ours_values, 95)), 4),
                        round(float(np.percentile(vai_values, 95)), 4)],
            }
    return output


def _report(rows: list[dict], expected: int, budget_seconds: float) -> dict:
    categories = sorted({str(row.get("category")) for row in rows})
    status_counts = {}
    for row in rows:
        status = str(row.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema": "vice-scene-bounded-challenge115/1",
        "freeze_hash": json.loads(FREEZE.read_text(encoding="utf-8"))["freeze_hash"],
        "expected": expected,
        "accounted": len(rows),
        "budget_seconds": budget_seconds,
        "status_counts": status_counts,
        "overall_completed_pairs": _aggregate_category(rows),
        "per_category": {
            category: _aggregate_category(
                [row for row in rows if str(row.get("category")) == category])
            for category in categories
        },
        "rows": rows,
        "promotion_gate": "PASS" if len(rows) == expected and status_counts == {"completed": expected}
        else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-seconds", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=115)
    args = parser.parse_args()
    okay, errors = verify_freeze(FREEZE)
    if not okay:
        raise SystemExit("BUILD_FREEZE invalid: " + "; ".join(errors))

    layout = json.loads((PLATES / "plate_layout.json").read_text(encoding="utf-8"))
    selected = [(index, item) for index, item in enumerate(layout)
                if int(item["plate"]) in {1, 2, 3, 4}][:args.limit]
    vai_items = {}
    split_audit = []
    for plate in (1, 2, 3, 4):
        plate_items, audit = split_vai_local(plate, layout, OUT / "vai_items")
        vai_items.update(plate_items)
        split_audit.append(audit)
    split_fidelity = validate_split_rasters(layout, vai_items)
    _write(OUT / "split_audit.json", {"schema": "vice-vai-plate-split-audit/1",
                                       "plates": split_audit,
                                       "raster_fidelity": split_fidelity})
    bad_splits = [row for row in split_audit if row["status"] != "complete"]
    if bad_splits:
        raise SystemExit("VAI plate split coverage guard failed: " + json.dumps(bad_splits))
    if split_fidelity["status"] != "PASS":
        raise SystemExit("VAI plate split raster-fidelity guard failed: "
                         + json.dumps(split_fidelity))

    report_path = OUT / "report.json"
    prior_rows = json.loads(report_path.read_text(encoding="utf-8")).get("rows", []) \
        if report_path.is_file() else []
    rows_by_item = {int(row["item"]): row for row in prior_rows}
    crops = OUT / "crops"
    ours_root = OUT / "ours"
    crops.mkdir(parents=True, exist_ok=True)
    ours_root.mkdir(parents=True, exist_ok=True)

    for sequence, (index, item) in enumerate(selected, 1):
        if index in rows_by_item:
            print(f"[{sequence:03}/{len(selected)}] item{index:03}: resume "
                  f"{rows_by_item[index]['status']}", flush=True)
            continue
        bx0, by0, bx1, by1 = (int(value) for value in item["bbox"])
        crop_path = crops / f"item{index:03}.png"
        plate_image = Image.open(PLATES / f"plate_{int(item['plate']):02}.png").convert("RGB")
        plate_image.crop((bx0, by0, bx1, by1)).save(crop_path)
        row = {
            "item": index, "category": item["category"], "source": item["source"],
            "plate": int(item["plate"]), "size": [bx1 - bx0, by1 - by0],
        }
        vai_artifacts = vai_items.get(index)
        if vai_artifacts is None:
            row.update({"status": "missing-vai", "ours": {"error": "not run"},
                        "vai": {"error": "no paths assigned to cell"}})
            rows_by_item[index] = row
            _write(report_path, _report(list(rows_by_item.values()), len(selected),
                                        args.budget_seconds))
            print(f"[{sequence:03}/{len(selected)}] item{index:03}: MISSING VAI", flush=True)
            continue

        command = [sys.executable, "-X", "utf8", str(ROOT / "eval_one_item.py"),
                   str(crop_path), str(ours_root / f"item{index:03}"),
                   str(bx1 - bx0), "scene"]
        completed = _run_monitored(command, args.budget_seconds)
        elapsed = float(completed["seconds"])
        if not completed["timed_out"]:
            try:
                ours = json.loads(completed["stdout"].strip().splitlines()[-1])
            except Exception:
                ours = {"error": (completed["stderr"] or completed["stdout"] or
                                   f"return code {completed['return_code']}")[-500:]}
            status = "completed" if completed["return_code"] == 0 and not ours.get("error") \
                else "benchmark-error"
        else:
            ours = {"error": f"timeout after {args.budget_seconds:g}s"}
            status = "timeout"

        vai = {}
        try:
            vai.update(bv.geometry_meters(vai_artifacts["geometry"], bx1 - bx0))
            vai.update(bv.roundness_meter(vai_artifacts["geometry"], bx1 - bx0))
            vai.update(bv.raster_meters(vai_artifacts["raster"], crop_path))
        except Exception as error:
            vai = {"error": f"{type(error).__name__}: {error}"[:300]}
        row.update({"status": status, "wall_seconds": round(elapsed, 3),
                    "peak_rss_mib": round(float(completed["peak_rss_mib"]), 3),
                    "ours": ours, "vai": vai})
        rows_by_item[index] = row
        _write(report_path, _report(list(rows_by_item.values()), len(selected),
                                    args.budget_seconds))
        print(f"[{sequence:03}/{len(selected)}] item{index:03}: {status} "
              f"{elapsed:.1f}s", flush=True)

    final_rows = [rows_by_item[index] for index, _ in selected if index in rows_by_item]
    payload = _report(final_rows, len(selected), args.budget_seconds)
    _write(report_path, payload)
    print(f"report={report_path}")
    print(f"accounted={payload['accounted']}/{payload['expected']} "
          f"statuses={payload['status_counts']}")
    return 0 if payload["accounted"] == payload["expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
