"""Phase-0 benchmark inventory with explicit rows for every required item.

This module does not claim quality.  It proves that the frozen VAI50 and
Challenge115 campaigns contain exactly the expected source/reference/result
rows and that no difficult case was silently dropped.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image


PROJECT = Path(__file__).resolve().parents[1]
PICTURES = Path(r"C:/Users/nirrt/Toolset/v-ice pictures")
VAI_DIR = PICTURES / "vai"
PROBLEM_SMALL = PICTURES / "problem cases" / "Small"
CHALLENGE = PICTURES / "challenge_pack"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_phase0" / "completeness_report.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _image_ok(path: Path) -> tuple[bool, str | None]:
    if not path.is_file():
        return False, "missing"
    try:
        with Image.open(path) as image:
            image.verify()
        return True, None
    except Exception as exc:
        return False, f"invalid image: {type(exc).__name__}: {exc}"


def _svg_ok(path: Path) -> tuple[bool, str | None]:
    if not path.is_file():
        return False, "missing"
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except Exception as exc:
        return False, f"unreadable SVG: {type(exc).__name__}: {exc}"
    if "<svg" not in text or not re.search(r"viewBox\s*=", text, re.I):
        return False, "SVG lacks <svg> or viewBox"
    return True, None


def _source_index() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in sorted(PROBLEM_SMALL.glob("*_src.png")):
        match = re.match(r"^\d+_(.+)_src$", path.stem)
        key = match.group(1) if match else path.stem.removesuffix("_src")
        result.setdefault(key, path.resolve())
    return result


def audit_vai50() -> dict[str, Any]:
    snapshot = PROJECT / "benchmarks" / "vai_snapshot_production_fresh50_final.json"
    payload = _read_json(snapshot)
    raw_rows = payload.get("rows", []) if isinstance(payload, dict) else []
    index = _source_index()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position in range(50):
        source_row = raw_rows[position] if position < len(raw_rows) else {}
        stem = str(source_row.get("stem", ""))
        errors: list[str] = []
        if not stem:
            errors.append("missing snapshot row/stem")
        if stem in seen:
            errors.append("duplicate stem")
        seen.add(stem)
        source = index.get(stem) or index.get(stem + "_vai")
        reference = VAI_DIR / f"{stem}_vai.svg"
        if source is None:
            errors.append("missing validated source raster")
        else:
            ok, detail = _image_ok(source)
            if not ok:
                errors.append(f"source {detail}")
        ref_ok, detail = _svg_ok(reference)
        if not ref_ok:
            errors.append(f"reference {detail}")
        if source_row.get("error"):
            errors.append(f"snapshot error: {source_row['error']}")
        if not isinstance(source_row.get("ours"), dict):
            errors.append("missing ours metrics")
        if not isinstance(source_row.get("vai"), dict):
            errors.append("missing VAI metrics")
        rows.append(
            {
                "position": position,
                "stem": stem or None,
                "source": str(source) if source else None,
                "reference": str(reference),
                "status": "complete" if not errors else "failed",
                "errors": errors,
            }
        )
    if len(raw_rows) != 50:
        rows.append(
            {
                "position": None,
                "stem": None,
                "status": "failed",
                "errors": [f"snapshot row count is {len(raw_rows)}, expected 50"],
            }
        )
    failed = sum(row["status"] != "complete" for row in rows)
    return {
        "name": "VAI50",
        "expected": 50,
        "observed_snapshot_rows": len(raw_rows),
        "complete_rows": sum(row["status"] == "complete" for row in rows),
        "failed_rows": failed,
        "complete": len(raw_rows) == 50 and failed == 0,
        "rows": rows,
    }


def audit_challenge115() -> dict[str, Any]:
    layout_path = CHALLENGE / "plates" / "plate_layout.json"
    layout = _read_json(layout_path)
    if not isinstance(layout, list):
        layout = []
    frozen_report_path = CHALLENGE / "eval" / "report_blind_FROZEN.json"
    frozen_report = _read_json(frozen_report_path)
    report_rows = frozen_report.get("rows", [])
    report_by_item = {
        int(row["item"]): row
        for row in report_rows
        if isinstance(row, dict) and isinstance(row.get("item"), int)
    }
    rows: list[dict[str, Any]] = []
    for item in range(115):
        errors: list[str] = []
        layout_row = layout[item] if item < len(layout) else None
        crop = CHALLENGE / "eval" / "crops" / f"item{item:03d}.png"
        reference = CHALLENGE / "eval" / "items" / f"item{item:03d}_vai.svg"
        source = (
            CHALLENGE / str(layout_row.get("source", ""))
            if isinstance(layout_row, dict)
            else None
        )
        for label, path in (("source", source), ("crop", crop)):
            if path is None:
                errors.append(f"missing {label} mapping")
                continue
            ok, detail = _image_ok(path)
            if not ok:
                errors.append(f"{label} {detail}")
        ref_ok, detail = _svg_ok(reference)
        if not ref_ok:
            errors.append(f"reference {detail}")
        measured = report_by_item.get(item)
        if measured is None:
            errors.append("missing frozen benchmark row")
        elif not isinstance(measured.get("ours"), dict):
            errors.append("missing ours metrics")
        elif not isinstance(measured.get("vai"), dict):
            errors.append("missing VAI metrics")
        rows.append(
            {
                "item": item,
                "category": (
                    layout_row.get("category")
                    if isinstance(layout_row, dict)
                    else None
                ),
                "source": str(source) if source else None,
                "crop": str(crop),
                "reference": str(reference),
                "status": "complete" if not errors else "failed",
                "errors": errors,
            }
        )
    structural_errors: list[str] = []
    if len(layout) != 115:
        structural_errors.append(f"layout has {len(layout)} rows, expected 115")
    if len(report_rows) != 115:
        structural_errors.append(
            f"frozen report has {len(report_rows)} rows, expected 115"
        )
    failed = sum(row["status"] != "complete" for row in rows)
    return {
        "name": "Challenge115",
        "expected": 115,
        "observed_layout_rows": len(layout),
        "observed_report_rows": len(report_rows),
        "complete_rows": 115 - failed,
        "failed_rows": failed,
        "structural_errors": structural_errors,
        "complete": failed == 0 and not structural_errors,
        "rows": rows,
    }


def production_route_audit() -> dict[str, Any]:
    index = (PROJECT / "web_preview" / "index.html").read_text(
        encoding="utf-8"
    )
    best_selected = bool(
        re.search(
            r'<option\s+value="paper-regions"\s+selected>V-ICE Best', index
        )
    )
    scene_archived = "Scene Engine · archived experiment" in index
    return {
        "production_default": "paper-regions",
        "best_selected": best_selected,
        "scene_archived_label": scene_archived,
        "complete": best_selected and scene_archived,
    }


def build_report() -> dict[str, Any]:
    vai50 = audit_vai50()
    challenge115 = audit_challenge115()
    route = production_route_audit()
    return {
        "schema": "pcdc-phase0-completeness/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": "every expected item has an explicit success/failure row",
        "production_route": route,
        "campaigns": {"vai50": vai50, "challenge115": challenge115},
        "complete": vai50["complete"] and challenge115["complete"] and route["complete"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "ok": report["complete"],
        "path": str(args.out),
        "production_route": report["production_route"],
        "vai50": {
            key: report["campaigns"]["vai50"][key]
            for key in ("expected", "complete_rows", "failed_rows", "complete")
        },
        "challenge115": {
            key: report["campaigns"]["challenge115"][key]
            for key in ("expected", "complete_rows", "failed_rows", "complete")
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())

