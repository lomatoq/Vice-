"""Generate a parameterised paper-style SVG corpus for corner learning.

The corpus is a grammar of boundary events, not a bag of large icons:

* smooth: circles, ellipses, rings, rounded rectangles and round-cap arc ribbons
  (zero C0 corners, including extrema and tangent joins);
* structural: polygons, thin quads, chevrons, zigzags, notches, steps and crosses;
* mixed: line/arc shapes containing both tangent joins and genuine C0 corners;
* occlusion: overlapping coloured primitives and multi-region junctions.

Every SVG is path-only, transform-free and directly consumable by
``build_corner_dataset.py``.  One source file is rasterised at every requested
resolution, so no scale variant can leak into another split.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


CANVAS = 256.0
COLORS = ("#16191f", "#e62939", "#ffad22", "#156fbd", "#14a65a", "#7e58b5")


@dataclass
class PrimitiveExample:
    family: str
    event_class: str
    paths: list[tuple[str, str, str]]  # d, fill, fill-rule
    parameters: dict


def _f(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _p(point) -> str:
    return f"{_f(point[0])} {_f(point[1])}"


def _point(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _poly(points: list[tuple[float, float]]) -> str:
    return "M " + " L ".join(_p(point) for point in points) + " Z"


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> str:
    return (f"M {_p((cx + rx, cy))} "
            f"A {_f(rx)} {_f(ry)} 0 1 1 {_p((cx - rx, cy))} "
            f"A {_f(rx)} {_f(ry)} 0 1 1 {_p((cx + rx, cy))} Z")


def _rounded_rect(x0: float, y0: float, x1: float, y1: float, radius: float) -> str:
    r = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
    return (f"M {_p((x0 + r, y0))} L {_p((x1 - r, y0))} "
            f"A {_f(r)} {_f(r)} 0 0 1 {_p((x1, y0 + r))} "
            f"L {_p((x1, y1 - r))} A {_f(r)} {_f(r)} 0 0 1 {_p((x1 - r, y1))} "
            f"L {_p((x0 + r, y1))} A {_f(r)} {_f(r)} 0 0 1 {_p((x0, y1 - r))} "
            f"L {_p((x0, y0 + r))} A {_f(r)} {_f(r)} 0 0 1 {_p((x0 + r, y0))} Z")


def _arc_ribbon(cx: float, cy: float, radius: float, width: float,
                start: float, sweep_angle: float) -> str:
    """Constant-width circular ribbon with two round caps and no C0 joins."""
    end = start + sweep_angle
    outer, inner, cap = radius + width / 2, max(1.0, radius - width / 2), width / 2
    sweep = 1 if sweep_angle >= 0 else 0
    reverse = 1 - sweep
    large = 1 if abs(sweep_angle) > math.pi else 0
    os = _point(cx, cy, outer, start)
    oe = _point(cx, cy, outer, end)
    ie = _point(cx, cy, inner, end)
    ins = _point(cx, cy, inner, start)
    return (f"M {_p(os)} A {_f(outer)} {_f(outer)} 0 {large} {sweep} {_p(oe)} "
            f"A {_f(cap)} {_f(cap)} 0 0 {sweep} {_p(ie)} "
            f"A {_f(inner)} {_f(inner)} 0 {large} {reverse} {_p(ins)} "
            f"A {_f(cap)} {_f(cap)} 0 0 {sweep} {_p(os)} Z")


def _regular_polygon(cx: float, cy: float, radius: float, count: int,
                     angle: float) -> list[tuple[float, float]]:
    return [_point(cx, cy, radius, angle + 2 * math.pi * index / count)
            for index in range(count)]


def _smooth_ellipse(rng: random.Random) -> PrimitiveExample:
    rx, ry = rng.uniform(28, 94), rng.uniform(22, 88)
    return PrimitiveExample("smooth_ellipse", "smooth", [(_ellipse(128, 128, rx, ry), COLORS[0], "evenodd")],
                            {"rx": rx, "ry": ry})


def _smooth_ring(rng: random.Random) -> PrimitiveExample:
    rx, ry = rng.uniform(48, 96), rng.uniform(42, 92)
    thickness = rng.uniform(5, min(rx, ry) * 0.38)
    d = _ellipse(128, 128, rx, ry) + " " + _ellipse(128, 128, rx - thickness, ry - thickness)
    return PrimitiveExample("smooth_ring", "smooth", [(d, COLORS[0], "evenodd")],
                            {"rx": rx, "ry": ry, "thickness": thickness})


def _smooth_roundrect(rng: random.Random) -> PrimitiveExample:
    width, height = rng.uniform(80, 210), rng.uniform(28, 180)
    x0, y0 = (256 - width) / 2, (256 - height) / 2
    radius = rng.uniform(min(width, height) * 0.18, min(width, height) * 0.5)
    return PrimitiveExample("smooth_roundrect", "smooth",
                            [(_rounded_rect(x0, y0, x0 + width, y0 + height, radius), COLORS[0], "evenodd")],
                            {"width": width, "height": height, "radius": radius})


def _smooth_arc(rng: random.Random) -> PrimitiveExample:
    radius = rng.uniform(36, 88)
    width = rng.uniform(4, min(30, radius * 0.48))
    angle = math.radians(rng.uniform(25, 325)) * rng.choice((-1, 1))
    start = rng.uniform(-math.pi, math.pi)
    return PrimitiveExample("smooth_arc_ribbon", "smooth",
                            [(_arc_ribbon(128, 128, radius, width, start, angle), COLORS[0], "evenodd")],
                            {"radius": radius, "width": width,
                             "start_deg": math.degrees(start), "sweep_deg": math.degrees(angle)})


def _polygon(rng: random.Random) -> PrimitiveExample:
    count = rng.randint(3, 10)
    points = _regular_polygon(128, 128, rng.uniform(52, 105), count, rng.uniform(-math.pi, math.pi))
    # Break perfect regularity without changing the exact corner definition.
    points = [(128 + (x - 128) * rng.uniform(0.78, 1.08),
               128 + (y - 128) * rng.uniform(0.78, 1.08)) for x, y in points]
    return PrimitiveExample("polygon", "structural", [(_poly(points), COLORS[0], "evenodd")], {"vertices": count})


def _star(rng: random.Random) -> PrimitiveExample:
    rays = rng.randint(3, 10)
    outer, inner = rng.uniform(70, 108), rng.uniform(22, 62)
    angle = rng.uniform(-math.pi, math.pi)
    points = [_point(128, 128, outer if index % 2 == 0 else inner,
                     angle + math.pi * index / rays) for index in range(2 * rays)]
    return PrimitiveExample("star_saw", "structural", [(_poly(points), COLORS[0], "evenodd")],
                            {"rays": rays, "inner": inner, "outer": outer})


def _thin_quad(rng: random.Random) -> PrimitiveExample:
    length, width = rng.uniform(90, 220), rng.uniform(2.0, 18.0)
    angle = rng.uniform(-math.pi, math.pi)
    u = (math.cos(angle) * length / 2, math.sin(angle) * length / 2)
    v = (-math.sin(angle) * width / 2, math.cos(angle) * width / 2)
    points = [(128 - u[0] - v[0], 128 - u[1] - v[1]),
              (128 + u[0] - v[0], 128 + u[1] - v[1]),
              (128 + u[0] + v[0], 128 + u[1] + v[1]),
              (128 - u[0] + v[0], 128 - u[1] + v[1])]
    return PrimitiveExample("thin_quad", "structural", [(_poly(points), COLORS[0], "evenodd")],
                            {"length": length, "width": width, "angle": math.degrees(angle)})


def _zigzag(rng: random.Random) -> PrimitiveExample:
    teeth = rng.randint(2, 8)
    x0, x1 = 24.0, 232.0
    center = rng.uniform(105, 151)
    amplitude = rng.uniform(22, 78)
    thickness = rng.uniform(3, 20)
    top, bottom = [], []
    for index in range(teeth * 2 + 1):
        x = x0 + (x1 - x0) * index / (teeth * 2)
        y = center + (amplitude if index % 2 else -amplitude)
        top.append((x, y - thickness / 2))
        bottom.append((x, y + thickness / 2))
    points = top + list(reversed(bottom))
    return PrimitiveExample("zigzag", "structural", [(_poly(points), COLORS[0], "evenodd")],
                            {"teeth": teeth, "amplitude": amplitude, "thickness": thickness})


def _chevron(rng: random.Random) -> PrimitiveExample:
    width = rng.uniform(5, 28)
    y0, y1 = rng.uniform(25, 65), rng.uniform(185, 230)
    x0, x1, cx = rng.uniform(18, 55), rng.uniform(201, 238), rng.uniform(105, 151)
    points = [(x0, y0), (cx, y1), (x1, y0), (x1 - width, y0),
              (cx, y1 - 2.8 * width), (x0 + width, y0)]
    return PrimitiveExample("chevron", "structural", [(_poly(points), COLORS[0], "evenodd")],
                            {"thickness": width})


def _notch(rng: random.Random) -> PrimitiveExample:
    depth, half = rng.uniform(24, 92), rng.uniform(12, 45)
    points = [(28, 35), (128 - half, 35), (128 - half, 35 + depth),
              (128 + half, 35 + depth), (128 + half, 35), (228, 35),
              (228, 221), (28, 221)]
    return PrimitiveExample("concave_notch", "structural", [(_poly(points), COLORS[0], "evenodd")],
                            {"depth": depth, "width": 2 * half})


def _step_cross(rng: random.Random) -> PrimitiveExample:
    if rng.random() < 0.5:
        x, y = rng.uniform(75, 115), rng.uniform(75, 115)
        points = [(25, 25), (x, 25), (x, y), (231, y), (231, 231), (25, 231)]
        family = "step_L"
    else:
        t = rng.uniform(24, 68)
        a, b = 128 - t / 2, 128 + t / 2
        points = [(a, 20), (b, 20), (b, a), (236, a), (236, b), (b, b),
                  (b, 236), (a, 236), (a, b), (20, b), (20, a), (a, a)]
        family = "cross"
    return PrimitiveExample(family, "structural", [(_poly(points), COLORS[0], "evenodd")], {})


def _half_disc(rng: random.Random) -> PrimitiveExample:
    radius = rng.uniform(48, 102)
    cx, cy = 128.0, 138.0
    d = (f"M {_p((cx - radius, cy))} "
         f"A {_f(radius)} {_f(radius)} 0 0 1 {_p((cx + radius, cy))} "
         f"L {_p((cx - radius, cy))} Z")
    return PrimitiveExample("half_disc", "mixed", [(d, COLORS[0], "evenodd")], {"radius": radius})


def _d_shape(rng: random.Random) -> PrimitiveExample:
    x0, xm = rng.uniform(28, 65), rng.uniform(92, 132)
    y0, y1 = rng.uniform(25, 55), rng.uniform(201, 231)
    radius = (y1 - y0) / 2
    d = (f"M {_p((x0, y0))} L {_p((xm, y0))} "
         f"A {_f(radius)} {_f(radius)} 0 0 1 {_p((xm, y1))} "
         f"L {_p((x0, y1))} Z")
    return PrimitiveExample("D_tangent_arc", "mixed", [(d, COLORS[0], "evenodd")], {})


def _flat_capsule(rng: random.Random) -> PrimitiveExample:
    x0, x1 = rng.uniform(20, 55), rng.uniform(195, 236)
    y0, y1 = rng.uniform(70, 105), rng.uniform(151, 190)
    radius = (y1 - y0) / 2
    d = (f"M {_p((x0, y0))} L {_p((x1 - radius, y0))} "
         f"A {_f(radius)} {_f(radius)} 0 0 1 {_p((x1 - radius, y1))} "
         f"L {_p((x0, y1))} Z")
    return PrimitiveExample("flat_capsule", "mixed", [(d, COLORS[0], "evenodd")], {})


def _teardrop(rng: random.Random) -> PrimitiveExample:
    tip_y = rng.uniform(18, 55)
    bottom = rng.uniform(205, 238)
    spread = rng.uniform(55, 98)
    # Smooth at the bottom, C0 cusp at the top.
    d = (f"M 128 {_f(tip_y)} "
         f"C {_f(128 + spread)} {_f(70)} {_f(128 + spread)} {_f(bottom - 25)} 128 {_f(bottom)} "
         f"C {_f(128 - spread)} {_f(bottom - 25)} {_f(128 - spread)} 70 128 {_f(tip_y)} Z")
    return PrimitiveExample("teardrop_cusp", "mixed", [(d, COLORS[0], "evenodd")], {})


def _occlusion_circles(rng: random.Random) -> PrimitiveExample:
    radius = rng.uniform(54, 91)
    gap = rng.uniform(30, radius * 1.25)
    paths = [(_ellipse(128 - gap / 2, 128, radius, radius), COLORS[1], "evenodd"),
             (_ellipse(128 + gap / 2, 128, radius, radius), COLORS[2], "evenodd")]
    return PrimitiveExample("overlap_circles", "occlusion", paths, {"radius": radius, "offset": gap})


def _occlusion_bar(rng: random.Random) -> PrimitiveExample:
    circle = _ellipse(128, 128, rng.uniform(60, 96), rng.uniform(50, 90))
    angle = rng.uniform(-math.pi, math.pi)
    length, width = 250, rng.uniform(10, 42)
    u = (math.cos(angle) * length / 2, math.sin(angle) * length / 2)
    v = (-math.sin(angle) * width / 2, math.cos(angle) * width / 2)
    bar = _poly([(128 - u[0] - v[0], 128 - u[1] - v[1]),
                 (128 + u[0] - v[0], 128 + u[1] - v[1]),
                 (128 + u[0] + v[0], 128 + u[1] + v[1]),
                 (128 - u[0] + v[0], 128 - u[1] + v[1])])
    return PrimitiveExample("circle_bar_occlusion", "occlusion",
                            [(circle, COLORS[3], "evenodd"), (bar, COLORS[1], "evenodd")], {})


def _junction(rng: random.Random) -> PrimitiveExample:
    vertical = _rounded_rect(105, 18, 151, 238, rng.uniform(4, 18))
    horizontal = _rounded_rect(18, 92, 238, 148, rng.uniform(4, 22))
    return PrimitiveExample("T_X_junction", "occlusion",
                            [(vertical, COLORS[3], "evenodd"), (horizontal, COLORS[2], "evenodd")], {})


def _fan(rng: random.Random) -> PrimitiveExample:
    count = rng.randint(3, 7)
    paths = []
    for index in range(count):
        angle = math.radians(-155 + 130 * index / max(1, count - 1))
        tip = (128.0, 174.0)
        far = _point(128, 174, rng.uniform(90, 135), angle)
        normal = (-math.sin(angle), math.cos(angle))
        width = rng.uniform(12, 30)
        points = [tip, (far[0] + normal[0] * width, far[1] + normal[1] * width),
                  (far[0] - normal[0] * width, far[1] - normal[1] * width)]
        paths.append((_poly(points), COLORS[index % len(COLORS)], "evenodd"))
    return PrimitiveExample("multi_region_fan", "occlusion", paths, {"petals": count})


GENERATORS = [
    (_smooth_ellipse, 12), (_smooth_ring, 10), (_smooth_roundrect, 12), (_smooth_arc, 22),
    (_polygon, 7), (_star, 5), (_thin_quad, 8), (_zigzag, 9), (_chevron, 6),
    (_notch, 5), (_step_cross, 7), (_half_disc, 4), (_d_shape, 5),
    (_flat_capsule, 5), (_teardrop, 4), (_occlusion_circles, 4),
    (_occlusion_bar, 3), (_junction, 3), (_fan, 2),
]


def _pick(rng: random.Random):
    total = sum(weight for _, weight in GENERATORS)
    value = rng.uniform(0, total)
    for generator, weight in GENERATORS:
        value -= weight
        if value <= 0:
            return generator
    return GENERATORS[-1][0]


def _split(key: str) -> str:
    value = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if value < 80 else "val" if value < 90 else "test"


def _svg(example: PrimitiveExample) -> str:
    paths = "\n".join(
        f'  <path d="{d}" fill="{fill}" fill-rule="{rule}"/>'
        for d, fill, rule in example.paths)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" '
            f'viewBox="0 0 256 256">\n{paths}\n</svg>\n')


def generate(out: Path, count: int, seed: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    records = []
    families = Counter()
    classes = Counter()
    splits = Counter()
    for index in range(count):
        generator = _pick(rng)
        example = generator(rng)
        key = f"{seed}:{index}:{example.family}"
        split = _split(key)
        target = out / split / example.family / f"{index:06d}_{example.family}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_svg(example), encoding="utf-8")
        records.append({"id": key, "path": str(target.relative_to(out)).replace("\\", "/"),
                        "split": split, **asdict(example) | {"paths": len(example.paths)}})
        families[example.family] += 1
        classes[example.event_class] += 1
        splits[split] += 1
    manifest = {"generator": "paper-primitive-grammar-v1", "seed": seed, "count": count,
                "canvas": int(CANVAS), "families": dict(sorted(families.items())),
                "event_classes": dict(sorted(classes.items())), "splits": dict(sorted(splits.items())),
                "records": records}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    return {key: value for key, value in manifest.items() if key != "records"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("datasets/primitive_svg_v1"))
    parser.add_argument("--count", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260711)
    args = parser.parse_args()
    print(json.dumps(generate(args.out, args.count, args.seed), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
