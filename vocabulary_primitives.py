"""Rebuild closed image contours using a primitive vocabulary CSV.

L = line, Q = quadratic Bezier, A = circular arc, C = cubic Bezier.
The CSV supplies the target mixture; local geometry selects where each type fits.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from vectorize_papers import (
    Curve,
    circular_beziers,
    eval_curve,
    extract_boundary,
    extract_shape_masks,
    fit_circle,
    fit_curve,
    interpolate_ring,
    mask_loops,
    point_line_distance,
    render,
    signed_area,
    source_color,
    taubin_smooth_ring,
)


TYPE_COLORS = {
    "L": (38, 99, 235),
    "Q": (22, 163, 74),
    "A": (245, 145, 30),
    "C": (196, 57, 173),
}
SHAPE_COLORS = {"circle": (0, 160, 190), "rect": (225, 50, 50), "ellipse": (115, 70, 205)}


@dataclass
class Piece:
    loop_id: int
    order: int
    points: np.ndarray
    line_error: float
    local_line_error: float
    arc_score: float
    bend: float
    kind: str = "C"
    curve: Curve | None = None


def read_vocabulary(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for row in rows:
        converted = {"file": row["file"]}
        for key, value in row.items():
            if key == "file":
                continue
            converted[key] = float(value or 0)
        result[row["file"]] = converted
    return result


def choose_profile(stem: str, vocabulary: dict[str, dict]) -> dict:
    aliases = {
        "penspiral_in": "penspiral_in_vai",
        "sassy-text-6557ld": "your_logo_vai",
    }
    candidates = [aliases.get(stem, ""), f"{stem}_vai", stem]
    for key in candidates:
        if key in vocabulary:
            return vocabulary[key]
    raise KeyError(f"No vocabulary profile for {stem}; tried {candidates}")


def perimeter(loop: np.ndarray) -> float:
    return float(np.sum(np.linalg.norm(np.diff(loop, axis=0), axis=1)))


def allocate_counts(lengths: list[float], total: int) -> list[int]:
    weights = np.asarray(lengths) / max(sum(lengths), 1e-9)
    raw = weights * total
    counts = np.floor(raw).astype(int)
    counts = np.maximum(counts, 1)
    while counts.sum() < total:
        i = int(np.argmax(raw - counts))
        counts[i] += 1
    while counts.sum() > total:
        candidates = np.where(counts > 1)[0]
        i = int(candidates[np.argmax(counts[candidates] - raw[candidates])])
        counts[i] -= 1
    return counts.tolist()


def sample_chunk(loop: np.ndarray, start: float, end: float, samples: int = 9) -> np.ndarray:
    distance = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(loop, axis=0), axis=1))))
    target = np.linspace(start * distance[-1], end * distance[-1], samples)
    return np.column_stack([np.interp(target, distance, loop[:, k]) for k in range(2)])


def make_pieces(loops: list[np.ndarray], counts: list[int]) -> list[Piece]:
    pieces: list[Piece] = []
    for loop_id, (loop, count) in enumerate(zip(loops, counts)):
        for i in range(count):
            points = sample_chunk(loop, i / count, (i + 1) / count)
            line_error = float(np.sqrt(np.mean(point_line_distance(points, points[0], points[-1]) ** 2)))
            circle = fit_circle(points)
            if circle is None:
                arc_score = 1e6
                bend = 0.0
            else:
                _, radius, residual = circle
                bend = float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)) / max(radius, 1e-6))
                arc_score = residual + (0.35 if bend < 0.025 else 0.0)
            pieces.append(Piece(loop_id, i, points, line_error, line_error, arc_score, bend))

    # Judge straightness on a neighbourhood, not on a microscopic individual
    # chunk.  This makes a long side read as one straight run instead of many
    # randomly coloured tiny lines.
    by_loop: dict[int, list[Piece]] = {}
    for piece in pieces:
        by_loop.setdefault(piece.loop_id, []).append(piece)
    for group in by_loop.values():
        group.sort(key=lambda piece: piece.order)
        if len(group) < 2:
            continue
        for i, piece in enumerate(group):
            neighbourhood = np.vstack((group[i - 1].points[:-1], piece.points, group[(i + 1) % len(group)].points[1:]))
            centered = neighbourhood - np.mean(neighbourhood, axis=0)
            try:
                direction = np.linalg.svd(centered, full_matrices=False)[2][0]
                normal = np.array([-direction[1], direction[0]])
                piece.line_error = float(np.sqrt(np.mean((centered @ normal) ** 2)))
            except np.linalg.LinAlgError:
                pass
    return pieces


def assign_types(pieces: list[Piece], profile: dict, force_geometry: bool = False) -> None:
    requested = {kind: int(profile[kind]) for kind in ("L", "Q", "A", "C")}
    total = len(pieces)
    source_total = max(1, sum(requested.values()))
    quotas = {k: int(round(total * requested[k] / source_total)) for k in requested}
    quotas["C"] += total - sum(quotas.values())
    unused = set(range(total))
    forced_lines = {
        i
        for i in unused
        if force_geometry and pieces[i].local_line_error <= 0.02 and pieces[i].line_error <= 0.35
    }
    for idx in forced_lines:
        pieces[idx].kind = "L"
        unused.remove(idx)
    remaining_lines = max(0, quotas["L"] - len(forced_lines))
    for idx in sorted(unused, key=lambda i: pieces[i].line_error)[:remaining_lines]:
        pieces[idx].kind = "L"
        unused.remove(idx)
    for idx in sorted(unused, key=lambda i: pieces[i].arc_score)[: quotas["A"]]:
        pieces[idx].kind = "A"
        unused.remove(idx)
    # Quadratics handle smooth single-bend sections; cubics keep complex waves.
    for idx in sorted(unused, key=lambda i: (pieces[i].bend, pieces[i].arc_score))[: quotas["Q"]]:
        pieces[idx].kind = "Q"
        unused.remove(idx)
    for idx in unused:
        pieces[idx].kind = "C"


def regularize_line_runs(pieces: list[Piece]) -> None:
    """Project neighbouring L pieces onto one shared line."""
    by_loop: dict[int, list[Piece]] = {}
    for piece in pieces:
        by_loop.setdefault(piece.loop_id, []).append(piece)
    for group in by_loop.values():
        group.sort(key=lambda piece: piece.order)
        start = 0
        while start < len(group):
            if group[start].kind != "L":
                start += 1
                continue
            end = start + 1
            while end < len(group) and group[end].kind == "L":
                end += 1
            run = group[start:end]
            if len(run) >= 2:
                points = np.vstack([piece.points[:-1] for piece in run] + [run[-1].points[-1:]])
                center = np.mean(points, axis=0)
                centered = points - center
                try:
                    direction = np.linalg.svd(centered, full_matrices=False)[2][0]
                    for piece in run:
                        piece.points = center + np.outer((piece.points - center) @ direction, direction)
                except np.linalg.LinAlgError:
                    pass
            start = end


def fit_pieces(pieces: list[Piece]) -> None:
    for piece in pieces:
        pts = piece.points
        if piece.kind == "L":
            piece.curve = Curve(1, np.vstack((pts[0], pts[-1])))
        elif piece.kind == "Q":
            control, _ = fit_curve(pts, 2)
            piece.curve = Curve(2, control)
        elif piece.kind == "A":
            circle = fit_circle(pts)
            if circle is None:
                control, _ = fit_curve(pts, 2)
                piece.curve = Curve(2, control)
                piece.kind = "Q"
            else:
                center, radius, _ = circle
                arcs = circular_beziers(pts[0], pts[-1], center, radius, pts)
                piece.curve = arcs[0] if arcs else Curve(1, np.vstack((pts[0], pts[-1])))
        else:
            control, _ = fit_curve(pts, 3)
            piece.curve = Curve(3, control)


def loop_shape_scores(loop: np.ndarray) -> dict[str, float]:
    p = loop[:-1]
    x0, y0 = p.min(axis=0)
    x1, y1 = p.max(axis=0)
    width, height = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    area = abs(signed_area(loop))
    peri = perimeter(loop)
    circularity = 4 * math.pi * area / max(peri * peri, 1e-9)
    aspect = min(width, height) / max(width, height)
    rect_fill = area / (width * height)
    center = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    normalized = (p - center) / np.array([width / 2, height / 2])
    ellipse_error = float(np.mean(np.abs(np.sum(normalized**2, axis=1) - 1)))
    return {
        "circle": circularity * aspect,
        "rect": rect_fill,
        "ellipse": 1.0 / (0.05 + ellipse_error) * (1 - 0.35 * aspect),
    }


def detect_shapes(loops: list[np.ndarray], profile: dict) -> dict[int, str]:
    labels: dict[int, str] = {}
    available = set(range(len(loops)))
    scores = [loop_shape_scores(loop) for loop in loops]
    for kind in ("circle", "rect", "ellipse"):
        count = min(int(profile[kind]), len(available))
        chosen = sorted(available, key=lambda i: scores[i][kind], reverse=True)[:count]
        for i in chosen:
            labels[i] = kind
            available.remove(i)
    return labels


def render_map(pieces: list[Piece], loops: list[np.ndarray], labels: dict[int, str], size: tuple[int, int]) -> Image.Image:
    scale = 4
    canvas = Image.new("RGB", (size[0] * scale, size[1] * scale), "white")
    draw = ImageDraw.Draw(canvas)
    for piece in pieces:
        pts = eval_curve(piece.curve, 18) * scale
        draw.line([tuple(p) for p in pts], fill=TYPE_COLORS[piece.kind], width=2 * scale, joint="curve")
    for loop_id, kind in labels.items():
        center = np.mean(loops[loop_id][:-1], axis=0) * scale
        draw.ellipse((center[0] - 8, center[1] - 8, center[0] + 8, center[1] + 8), fill=SHAPE_COLORS[kind])
        draw.text((center[0] + 10, center[1] - 7), kind[0].upper(), fill=SHAPE_COLORS[kind])
    canvas = canvas.resize(size, Image.Resampling.LANCZOS)
    legend = ImageDraw.Draw(canvas)
    x = 6
    for kind, label in (("L", "line"), ("Q", "quadratic"), ("A", "arc"), ("C", "cubic")):
        legend.rectangle((x, 5, x + 8, 13), fill=TYPE_COLORS[kind])
        legend.text((x + 11, 3), label, fill=(20, 20, 20))
        x += 62 if kind != "Q" else 82
    return canvas


def render_contour(boundary: np.ndarray) -> Image.Image:
    return Image.fromarray(np.where(boundary[..., None], 0, 255).astype(np.uint8).repeat(3, axis=2))


def curve_svg(curve: Curve, include_move: bool = True) -> str:
    p = curve.control
    move = f"M {p[0,0]:.3f},{p[0,1]:.3f} " if include_move else ""
    if curve.degree == 1:
        return f"{move}L {p[1,0]:.3f},{p[1,1]:.3f}"
    if curve.degree == 2:
        return f"{move}Q {p[1,0]:.3f},{p[1,1]:.3f} {p[2,0]:.3f},{p[2,1]:.3f}"
    return f"{move}C {p[1,0]:.3f},{p[1,1]:.3f} {p[2,0]:.3f},{p[2,1]:.3f} {p[3,0]:.3f},{p[3,1]:.3f}"


def write_svgs(case_dir: Path, pieces: list[Piece], loops: list[np.ndarray], groups: list[list[Curve]], size: tuple[int, int]) -> None:
    width, height = size
    head = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n<rect width="100%" height="100%" fill="white"/>'
    map_rows = [head]
    for piece in pieces:
        color = TYPE_COLORS[piece.kind]
        map_rows.append(
            f'<path data-type="{piece.kind}" d="{curve_svg(piece.curve)}" fill="none" '
            f'stroke="rgb{color}" stroke-width="1.5" stroke-linecap="round"/>'
        )
    map_rows.append("</svg>")
    (case_dir / "02_primitive_map.svg").write_text("\n".join(map_rows), encoding="utf-8")

    fill_rows = [head]
    order = sorted(range(len(groups)), key=lambda i: abs(signed_area(loops[i])), reverse=True)
    for loop_id in order:
        curves = groups[loop_id]
        if not curves:
            continue
        commands = [curve_svg(curve, include_move=(i == 0)) for i, curve in enumerate(curves)]
        color = curves[0].color if signed_area(loops[loop_id]) > 0 else (255, 255, 255)
        fill_rows.append(
            f'<path data-contour="{loop_id}" d="{" ".join(commands)} Z" fill="rgb{color}" stroke="none"/>'
        )
    fill_rows.append("</svg>")
    (case_dir / "03_rebuilt_filled.svg").write_text("\n".join(fill_rows), encoding="utf-8")


def contact_sheet(contour: Image.Image, primitive_map: Image.Image, rebuilt: Image.Image, profile_name: str) -> Image.Image:
    w, h = contour.size
    header = 28
    sheet = Image.new("RGB", (w * 3, h + header), "white")
    draw = ImageDraw.Draw(sheet)
    titles = ("1. contour", f"2. vocabulary: {profile_name}", "3. rebuilt + filled")
    for i, (image, title) in enumerate(zip((contour, primitive_map, rebuilt), titles)):
        sheet.paste(image, (i * w, header))
        draw.text((i * w + 6, 7), title, fill=(20, 20, 20))
    return sheet


def process(
    image_path: Path,
    vocabulary_path: Path,
    output: Path,
    profile_name: str | None = None,
    max_primitives: int = 1200,
    smoothing: str = "corner",
    extractor: str = "palette",
) -> dict:
    vocabulary = read_vocabulary(vocabulary_path)
    profile = vocabulary[profile_name] if profile_name else choose_profile(image_path.stem, vocabulary)
    image = Image.open(image_path)
    rgb_source, source_masks, boundary_source, bg_source, source_threshold = extract_shape_masks(image)
    extractor_used = extractor
    analysis_scale = 1
    if extractor == "mininet" and max(image.size) <= 256:
        from subpixel_mininet import deblur_4x

        analysis_image = deblur_4x(image)
        rgb_analysis, shape_masks, boundary, bg_analysis, threshold = extract_shape_masks(analysis_image)
        analysis_scale = 4
    else:
        if extractor == "mininet":
            extractor_used = "palette-large-fallback"
        rgb_analysis, shape_masks, boundary, bg_analysis, threshold = (
            rgb_source,
            source_masks,
            boundary_source,
            bg_source,
            source_threshold,
        )
    raw_loops = [
        loop / analysis_scale
        for mask in shape_masks
        for loop in mask_loops(mask)
        if perimeter(loop) >= 4.0 * analysis_scale
    ]
    loops = [interpolate_ring(loop, smoothing) for loop in raw_loops]
    source_total = int(sum(profile[k] for k in ("L", "Q", "A", "C")))
    lengths = [perimeter(loop) for loop in loops]
    # Keep visible spans substantial.  A fixed vocabulary count on a tiny icon
    # creates hundreds of 1-2 px fragments and looks like noise.
    segment_length = max(10.0, min(18.0, min(image.size) * 0.03))
    natural_total = max(len(loops), int(round(sum(lengths) / segment_length)))
    total = max(len(loops), min(source_total, max_primitives, natural_total))
    counts = allocate_counts(lengths, total)
    pieces = make_pieces(loops, counts)
    assign_types(pieces, profile, force_geometry=(smoothing == "cad"))
    regularize_line_runs(pieces)
    fit_pieces(pieces)
    labels = detect_shapes(loops, profile)

    groups: list[list[Curve]] = [[] for _ in loops]
    for piece in pieces:
        color = source_color(piece.points, rgb_source, boundary_source, bg_source)
        piece.curve.color = color
        groups[piece.loop_id].append(piece.curve)
    contour_image = render_contour(boundary)
    contour_sheet = contour_image.resize(image.size, Image.Resampling.LANCZOS) if analysis_scale > 1 else contour_image
    map_image = render_map(pieces, loops, labels, image.size)
    rebuilt = render(groups, image.size, colored=True, supersample=4)

    case_dir = output / image_path.stem
    case_dir.mkdir(parents=True, exist_ok=True)
    contour_image.save(case_dir / "01_contour.png")
    map_image.save(case_dir / "02_primitive_map.png")
    rebuilt.save(case_dir / "03_rebuilt_filled.png")
    write_svgs(case_dir, pieces, loops, groups, image.size)
    contact_sheet(contour_sheet, map_image, rebuilt, profile["file"]).save(case_dir / "00_contact_sheet.png")

    actual = {kind: sum(p.kind == kind for p in pieces) for kind in TYPE_COLORS}
    report = {
        "input": image_path.name,
        "profile": profile["file"],
        "source_primitive_count": source_total,
        "rendered_primitive_count": total,
        "target": {k: profile[k] for k in ("L", "Q", "A", "C", "circle", "rect", "ellipse")},
        "actual": actual,
        "detected_shapes": {kind: sum(v == kind for v in labels.values()) for kind in SHAPE_COLORS},
        "closed_contours": len(loops),
        "threshold": threshold,
        "smoothing": smoothing,
        "segment_length": round(segment_length, 2),
        "extractor_requested": extractor,
        "extractor_used": extractor_used,
        "analysis_scale": analysis_scale,
    }
    (case_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--vocabulary", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/vocabulary_primitives"))
    args = parser.parse_args()
    reports = [process(image, args.vocabulary, args.output) for image in args.images]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
