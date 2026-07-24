#!/usr/bin/env python3
"""Structural clean-room audit for SVG outputs.

The script does not attempt to identify a proprietary implementation. It reports
observable SVG structure that is useful for comparing vectorizers:

* element and path-command vocabulary;
* positive/negative-loop clues (multiple subpaths and fill rules);
* native parameterized elements (circle/ellipse/rect/etc.);
* grouping, transforms, clipping, layers and draw order;
* repeated path geometry up to exact ``d`` normalization;
* potential non-scaling gap-filler strokes;
* coordinate precision and style cohorts;
* a conservative cutout-vs-stacked heuristic.

Usage:
    python vectorizer_ai_svg_forensics.py one.svg two.svg --out report.md
    python vectorizer_ai_svg_forensics.py folder_with_svgs --json report.json

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

COMMAND_RE = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]")
NUMBER_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
SPACE_RE = re.compile(r"\s+")
STYLE_SPLIT_RE = re.compile(r"\s*;\s*")

GRAPHIC_TAGS = {
    "path", "circle", "ellipse", "rect", "polygon", "polyline", "line",
    "text", "image", "use",
}
PARAMETRIC_TAGS = {"circle", "ellipse", "rect", "polygon", "polyline", "line"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_path_d(value: str) -> str:
    value = value.strip()
    value = re.sub(r",", " ", value)
    value = SPACE_RE.sub(" ", value)
    # Normalize spaces around commands without changing numeric precision.
    value = re.sub(r"\s*([A-Za-z])\s*", r"\1", value)
    return value


def parse_style(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    style = element.attrib.get("style", "")
    for item in STYLE_SPLIT_RE.split(style.strip()):
        if not item or ":" not in item:
            continue
        key, value = item.split(":", 1)
        result[key.strip()] = value.strip()
    for key in (
        "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
        "stroke-opacity", "vector-effect", "opacity", "clip-path",
        "mask", "display", "visibility",
    ):
        if key in element.attrib:
            result[key] = element.attrib[key]
    return result


def numeric_precision(value: str) -> list[int]:
    precisions: list[int] = []
    for token in NUMBER_RE.findall(value):
        mantissa = token.lower().split("e", 1)[0]
        if "." in mantissa:
            precisions.append(len(mantissa.split(".", 1)[1]))
        else:
            precisions.append(0)
    return precisions


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    match = NUMBER_RE.search(value)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def iter_input_svgs(inputs: Sequence[str]) -> list[Path]:
    found: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(path.rglob("*.svg")))
        elif path.is_file() and path.suffix.lower() == ".svg":
            found.append(path)
        else:
            print(f"warning: skipped non-SVG input: {path}", file=sys.stderr)
    # Stable de-duplication.
    unique: dict[str, Path] = {}
    for path in found:
        unique[str(path.resolve())] = path
    return list(unique.values())


@dataclass
class DrawElement:
    index: int
    tag: str
    element_id: str | None
    group_path: tuple[str, ...]
    transform: str | None
    style: dict[str, str]
    path_commands: dict[str, int] = field(default_factory=dict)
    subpaths: int = 0
    path_signature: str | None = None
    coordinate_precision: list[int] = field(default_factory=list)


@dataclass
class SvgAudit:
    file: str
    sha256: str
    bytes: int
    root_width: str | None
    root_height: str | None
    view_box: str | None
    element_counts: dict[str, int]
    graphic_count: int
    group_count: int
    max_group_depth: int
    command_counts: dict[str, int]
    fill_rule_counts: dict[str, int]
    style_cohorts: dict[str, int]
    native_parametric_counts: dict[str, int]
    multi_subpath_fill_paths: int
    repeated_path_groups: list[dict]
    likely_gap_fillers: list[dict]
    clip_or_mask_count: int
    transform_count: int
    coordinate_precision: dict[str, float | int | None]
    draw_order_head: list[dict]
    draw_order_tail: list[dict]
    heuristic_export_mode: str
    heuristic_notes: list[str]


def style_signature(style: dict[str, str]) -> str:
    keys = (
        "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
        "stroke-opacity", "vector-effect", "opacity", "clip-path", "mask",
    )
    return "|".join(f"{key}={style.get(key, '')}" for key in keys)


def short_element(item: DrawElement) -> dict:
    return {
        "index": item.index,
        "tag": item.tag,
        "id": item.element_id,
        "groups": list(item.group_path),
        "fill": item.style.get("fill"),
        "stroke": item.style.get("stroke"),
        "stroke_width": item.style.get("stroke-width"),
        "vector_effect": item.style.get("vector-effect"),
        "subpaths": item.subpaths,
        "commands": item.path_commands,
        "transform": item.transform,
    }


def audit_svg(path: Path) -> SvgAudit:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"invalid SVG XML: {exc}") from exc

    counts: collections.Counter[str] = collections.Counter()
    command_counts: collections.Counter[str] = collections.Counter()
    fill_rules: collections.Counter[str] = collections.Counter()
    style_cohorts: collections.Counter[str] = collections.Counter()
    parametric: collections.Counter[str] = collections.Counter()
    draws: list[DrawElement] = []
    max_depth = 0
    clip_or_mask_count = 0
    transform_count = 0
    all_precision: list[int] = []

    def walk(element: ET.Element, groups: tuple[str, ...]) -> None:
        nonlocal max_depth, clip_or_mask_count, transform_count
        tag = local_name(element.tag)
        counts[tag] += 1
        next_groups = groups
        if tag == "g":
            label = (
                element.attrib.get("id")
                or element.attrib.get("{http://www.inkscape.org/namespaces/inkscape}label")
                or f"g@{counts[tag]}"
            )
            next_groups = groups + (label,)
            max_depth = max(max_depth, len(next_groups))

        style = parse_style(element)
        if "clip-path" in style or "mask" in style or tag in {"clipPath", "mask"}:
            clip_or_mask_count += 1
        transform = element.attrib.get("transform")
        if transform:
            transform_count += 1
            all_precision.extend(numeric_precision(transform))

        if tag in PARAMETRIC_TAGS:
            parametric[tag] += 1

        if tag in GRAPHIC_TAGS:
            commands: collections.Counter[str] = collections.Counter()
            subpaths = 0
            signature = None
            precision: list[int] = []
            if tag == "path":
                d = element.attrib.get("d", "")
                signature = normalize_path_d(d)
                commands.update(command.upper() for command in COMMAND_RE.findall(d))
                subpaths = commands.get("M", 0)
                command_counts.update(commands)
                precision.extend(numeric_precision(d))
            else:
                # Native shape attributes also expose coordinate precision.
                for key, value in element.attrib.items():
                    if key in {"id", "class", "style", "transform"}:
                        continue
                    precision.extend(numeric_precision(value))
            all_precision.extend(precision)
            if style:
                style_cohorts[style_signature(style)] += 1
                fill_rules[style.get("fill-rule", "default/nonzero")] += 1
            draws.append(
                DrawElement(
                    index=len(draws),
                    tag=tag,
                    element_id=element.attrib.get("id"),
                    group_path=next_groups,
                    transform=transform,
                    style=style,
                    path_commands=dict(commands),
                    subpaths=subpaths,
                    path_signature=signature,
                    coordinate_precision=precision,
                )
            )

        for child in list(element):
            walk(child, next_groups)

    walk(root, tuple())

    repeated: dict[str, list[DrawElement]] = collections.defaultdict(list)
    for item in draws:
        if item.path_signature:
            repeated[item.path_signature].append(item)
    repeated_groups: list[dict] = []
    for signature, items in repeated.items():
        if len(items) < 2:
            continue
        repeated_groups.append(
            {
                "count": len(items),
                "indices": [item.index for item in items],
                "ids": [item.element_id for item in items],
                "transforms": [item.transform for item in items],
                "signature_sha1": hashlib.sha1(signature.encode("utf-8")).hexdigest(),
                "signature_prefix": signature[:160],
            }
        )
    repeated_groups.sort(key=lambda row: (-row["count"], row["indices"][0]))

    gap_fillers: list[dict] = []
    for item in draws:
        fill = (item.style.get("fill") or "").strip().lower()
        stroke = (item.style.get("stroke") or "").strip().lower()
        vector_effect = (item.style.get("vector-effect") or "").strip().lower()
        width = parse_float(item.style.get("stroke-width"))
        is_stroke_only = fill in {"", "none", "transparent"} and stroke not in {"", "none", "transparent"}
        early = item.index <= max(4, int(0.25 * max(1, len(draws))))
        narrow = width is None or width <= 5.0
        if is_stroke_only and narrow and ("non-scaling" in vector_effect or early):
            gap_fillers.append(short_element(item))

    multi_subpath_fill = 0
    for item in draws:
        fill = (item.style.get("fill") or "").strip().lower()
        if item.tag == "path" and item.subpaths >= 2 and fill not in {"", "none", "transparent"}:
            multi_subpath_fill += 1

    notes: list[str] = []
    if gap_fillers:
        notes.append("Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.")
    if repeated_groups:
        notes.append("Exact repeated path-data signatures exist. They may indicate reused glyphs/symbols or duplicated geometry with transforms.")
    if sum(parametric.values()):
        notes.append("Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.")
    if multi_subpath_fill:
        notes.append("Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.")
    if max_depth >= 2:
        notes.append("Nested groups may expose parent/layer/color export grouping, but group names and draw order must be inspected.")

    # Conservative heuristic only; report ambiguity rather than overclaim.
    cutout_score = multi_subpath_fill + 0.5 * fill_rules.get("evenodd", 0)
    stacked_score = max_depth + 0.5 * len({item.group_path for item in draws if item.group_path})
    if cutout_score >= max(3.0, 1.5 * stacked_score):
        export_mode = "cutout-like (heuristic)"
    elif stacked_score >= max(3.0, 1.5 * cutout_score):
        export_mode = "stacked/layered-like (heuristic)"
    else:
        export_mode = "ambiguous/mixed (heuristic)"

    if all_precision:
        precision_stats: dict[str, float | int | None] = {
            "count": len(all_precision),
            "min": min(all_precision),
            "median": statistics.median(all_precision),
            "p90": sorted(all_precision)[min(len(all_precision) - 1, math.ceil(0.9 * len(all_precision)) - 1)],
            "max": max(all_precision),
        }
    else:
        precision_stats = {"count": 0, "min": None, "median": None, "p90": None, "max": None}

    return SvgAudit(
        file=str(path),
        sha256=sha,
        bytes=len(data),
        root_width=root.attrib.get("width"),
        root_height=root.attrib.get("height"),
        view_box=root.attrib.get("viewBox"),
        element_counts=dict(counts.most_common()),
        graphic_count=len(draws),
        group_count=counts.get("g", 0),
        max_group_depth=max_depth,
        command_counts=dict(command_counts.most_common()),
        fill_rule_counts=dict(fill_rules.most_common()),
        style_cohorts=dict(style_cohorts.most_common()),
        native_parametric_counts=dict(parametric.most_common()),
        multi_subpath_fill_paths=multi_subpath_fill,
        repeated_path_groups=repeated_groups[:50],
        likely_gap_fillers=gap_fillers[:100],
        clip_or_mask_count=clip_or_mask_count,
        transform_count=transform_count,
        coordinate_precision=precision_stats,
        draw_order_head=[short_element(item) for item in draws[:12]],
        draw_order_tail=[short_element(item) for item in draws[-12:]],
        heuristic_export_mode=export_mode,
        heuristic_notes=notes,
    )


def render_markdown(audits: Sequence[SvgAudit]) -> str:
    lines: list[str] = [
        "# SVG structural forensics report",
        "",
        "> Heuristics are deliberately conservative. A structural pattern is evidence about an export, not proof of the proprietary internal implementation.",
        "",
    ]
    for audit in audits:
        lines.extend([
            f"## `{audit.file}`",
            "",
            f"- SHA-256: `{audit.sha256}`",
            f"- Bytes: {audit.bytes}",
            f"- Root size: `{audit.root_width}` × `{audit.root_height}`; viewBox `{audit.view_box}`",
            f"- Graphics: {audit.graphic_count}; groups: {audit.group_count}; max group depth: {audit.max_group_depth}",
            f"- Export-mode clue: **{audit.heuristic_export_mode}**",
            f"- Multi-subpath filled paths: {audit.multi_subpath_fill_paths}",
            f"- Clip/mask references or definitions: {audit.clip_or_mask_count}",
            f"- Transformed elements: {audit.transform_count}",
            f"- Coordinate precision: `{json.dumps(audit.coordinate_precision, ensure_ascii=False)}`",
            "",
            "### Element vocabulary",
            "",
            "```json",
            json.dumps(audit.element_counts, ensure_ascii=False, indent=2),
            "```",
            "",
            "### Path commands",
            "",
            "```json",
            json.dumps(audit.command_counts, ensure_ascii=False, indent=2),
            "```",
            "",
            "### Native parameterized elements",
            "",
            "```json",
            json.dumps(audit.native_parametric_counts, ensure_ascii=False, indent=2),
            "```",
            "",
            "### Fill-rule counts",
            "",
            "```json",
            json.dumps(audit.fill_rule_counts, ensure_ascii=False, indent=2),
            "```",
            "",
        ])
        if audit.heuristic_notes:
            lines.append("### Notes")
            lines.append("")
            lines.extend(f"- {note}" for note in audit.heuristic_notes)
            lines.append("")
        lines.extend([
            "### Exact repeated path groups",
            "",
            "```json",
            json.dumps(audit.repeated_path_groups, ensure_ascii=False, indent=2),
            "```",
            "",
            "### Potential gap-filler strokes",
            "",
            "```json",
            json.dumps(audit.likely_gap_fillers, ensure_ascii=False, indent=2),
            "```",
            "",
            "### First draw-order elements",
            "",
            "```json",
            json.dumps(audit.draw_order_head, ensure_ascii=False, indent=2),
            "```",
            "",
            "### Last draw-order elements",
            "",
            "```json",
            json.dumps(audit.draw_order_tail, ensure_ascii=False, indent=2),
            "```",
            "",
        ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="SVG file(s) or directories")
    parser.add_argument("--out", type=Path, help="Write Markdown report")
    parser.add_argument("--json", type=Path, help="Write machine-readable JSON")
    args = parser.parse_args(argv)

    paths = iter_input_svgs(args.inputs)
    if not paths:
        parser.error("no SVG files found")

    audits: list[SvgAudit] = []
    failed = False
    for path in paths:
        try:
            audits.append(audit_svg(path))
        except (OSError, ValueError) as exc:
            failed = True
            print(f"error: {path}: {exc}", file=sys.stderr)

    if not audits:
        return 2

    markdown = render_markdown(audits)
    if args.out:
        args.out.write_text(markdown, encoding="utf-8")
        print(f"wrote Markdown: {args.out}")
    else:
        print(markdown)

    if args.json:
        args.json.write_text(
            json.dumps([asdict(audit) for audit in audits], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"wrote JSON: {args.json}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())


