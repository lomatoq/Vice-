"""Proper diagram SVGs for the challenge pack: nesting, long chains, charts.

The synthetic_geometry arrows alone are too easy — this adds what the user
asked for: nested containers, LONG flowcharts, axis charts with gridlines,
trees with orthogonal connectors.  Pure shapes (no fonts), deterministic.
"""
from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack/diagrams")

INK = "#2b3a55"
ACCENT = "#c0392b"
FILL = "#dbe4f0"
FILL2 = "#f2e3c6"
GREEN = "#2e8b57"


def arrow(x1, y1, x2, y2, color=INK, w=3):
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 10
    p1 = (x2 - ah * math.cos(ang - 0.42), y2 - ah * math.sin(ang - 0.42))
    p2 = (x2 - ah * math.cos(ang + 0.42), y2 - ah * math.sin(ang + 0.42))
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"/>'
            f'<polygon points="{x2},{y2} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="{color}"/>')


def rrect(x, y, w, h, r=10, fill=FILL, stroke=INK, sw=3):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def diamond(cx, cy, w, h, fill=FILL2):
    return (f'<polygon points="{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}" '
            f'fill="{fill}" stroke="{INK}" stroke-width="3"/>')


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>{body}</svg>')


def flowchart_long():
    parts = []
    y = 70
    xs = [40 + i * 150 for i in range(8)]
    for i, x in enumerate(xs):
        if i == 3:
            parts.append(diamond(x + 55, y + 27, 110, 86))
        else:
            parts.append(rrect(x, y, 110, 55))
        if i:
            parts.append(arrow(xs[i - 1] + 110 + (0 if i - 1 != 3 else 0), y + 27, x - 4, y + 27))
    # feedback loop from box 6 back to box 1 (long orthogonal connector)
    parts.append(f'<path d="M {xs[6]+55} {y+55} V {y+120} H {xs[1]+55} V {y+62}" '
                 f'fill="none" stroke="{ACCENT}" stroke-width="3" stroke-dasharray="8 5"/>')
    parts.append(arrow(xs[1] + 55, y + 70, xs[1] + 55, y + 60, ACCENT))
    return svg(1240, 220, "".join(parts)), "flowchart_long"


def nested_containers():
    parts = [rrect(20, 20, 560, 380, 16, "#eef2f8")]
    parts.append(rrect(50, 60, 230, 300, 12, "#ffffff"))
    parts.append(rrect(320, 60, 230, 140, 12, "#ffffff"))
    parts.append(rrect(320, 230, 230, 130, 12, "#ffffff"))
    for k in range(3):
        parts.append(rrect(75, 90 + k * 90, 180, 60, 8, FILL))
    parts.append(rrect(345, 90, 180, 60, 8, FILL2))
    parts.append(rrect(345, 255, 82, 70, 8, FILL))
    parts.append(rrect(443, 255, 82, 70, 8, FILL))
    parts.append(arrow(255, 120, 341, 120))
    parts.append(arrow(255, 300, 320, 292))
    parts.append(arrow(435, 200, 435, 226))
    return svg(600, 420, "".join(parts)), "nested_containers"


def tree_diagram():
    parts = [rrect(260, 20, 120, 50, 10, FILL2)]
    l1 = [(80, 130), (260, 130), (440, 130)]
    for x, y in l1:
        parts.append(rrect(x, y, 120, 46, 8))
        parts.append(f'<path d="M 320 70 V 100 H {x+60} V {y-4}" fill="none" stroke="{INK}" stroke-width="3"/>')
        parts.append(arrow(x + 60, y - 12, x + 60, y - 4))
    l2 = [(20, 230), (150, 230), (395, 230), (520, 230)]
    parents = [140, 140, 500, 500]
    for (x, y), px in zip(l2, parents):
        parts.append(rrect(x, y, 105, 42, 8, "#ffffff"))
        parts.append(f'<path d="M {px} 176 V 205 H {x+52} V {y-4}" fill="none" stroke="{INK}" stroke-width="2.5"/>')
        parts.append(arrow(x + 52, y - 11, x + 52, y - 4, INK, 2.5))
    return svg(650, 300, "".join(parts)), "tree_diagram"


def barchart_long():
    parts = [f'<line x1="50" y1="20" x2="50" y2="240" stroke="{INK}" stroke-width="3"/>',
             f'<line x1="50" y1="240" x2="1180" y2="240" stroke="{INK}" stroke-width="3"/>']
    for gy in range(60, 240, 45):
        parts.append(f'<line x1="50" y1="{gy}" x2="1180" y2="{gy}" stroke="#c8cfda" stroke-width="1.5" stroke-dasharray="6 6"/>')
    heights = [60, 110, 85, 150, 175, 120, 95, 190, 140, 70, 165, 100, 130, 185]
    for i, hh in enumerate(heights):
        x = 75 + i * 78
        color = ACCENT if i == 7 else GREEN
        parts.append(f'<rect x="{x}" y="{240-hh}" width="46" height="{hh}" rx="4" fill="{color}"/>')
    return svg(1240, 270, "".join(parts)), "barchart_long"


def linechart():
    pts = [(60, 200), (140, 150), (220, 170), (300, 90), (380, 120), (460, 60), (540, 95), (620, 40)]
    body = [f'<line x1="50" y1="20" x2="50" y2="230" stroke="{INK}" stroke-width="3"/>',
            f'<line x1="50" y1="230" x2="660" y2="230" stroke="{INK}" stroke-width="3"/>']
    for gy in (60, 115, 170):
        body.append(f'<line x1="50" y1="{gy}" x2="660" y2="{gy}" stroke="#c8cfda" stroke-width="1.5" stroke-dasharray="5 6"/>')
    d = "M " + " L ".join(f"{x} {y}" for x, y in pts)
    body.append(f'<path d="{d}" fill="none" stroke="{ACCENT}" stroke-width="4" stroke-linejoin="round"/>')
    for x, y in pts:
        body.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#ffffff" stroke="{ACCENT}" stroke-width="3.5"/>')
    return svg(700, 260, "".join(body)), "linechart"


def swimlanes():
    parts = []
    for k in range(3):
        parts.append(f'<rect x="20" y="{20+k*110}" width="760" height="100" fill="{"#f4f6fa" if k%2 else "#eaeef5"}" stroke="{INK}" stroke-width="2"/>')
    boxes = [(60, 45, 0), (260, 45, 0), (260, 155, 1), (470, 155, 1), (470, 265, 2), (660, 45, 0)]
    for x, y, _lane in boxes:
        parts.append(rrect(x, y, 110, 50, 8))
    parts.append(arrow(170, 70, 256, 70))
    parts.append(arrow(315, 95, 315, 151))
    parts.append(arrow(370, 180, 466, 180))
    parts.append(arrow(525, 205, 525, 261))
    parts.append(f'<path d="M 580 290 H 715 V 99" fill="none" stroke="{ACCENT}" stroke-width="3" stroke-dasharray="7 5"/>')
    parts.append(arrow(715, 105, 715, 97, ACCENT))
    return svg(800, 350, "".join(parts)), "swimlanes"


def main() -> int:
    sys.path.insert(0, str(Path(__file__).parent))
    from build_challenge_pack import render_svg_h
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for maker in (flowchart_long, nested_containers, tree_diagram,
                  barchart_long, linechart, swimlanes):
        content, name = maker()
        svg_p = OUT / f"gen_{name}.svg"
        svg_p.write_text(content, encoding="utf-8")
        for h in (140, 260):
            img = render_svg_h(svg_p, h)
            if img is not None:
                img.save(OUT / f"gen_{name}__h{h}.png")
        img = render_svg_h(svg_p, 200)
        if img is not None:
            img.save(OUT / f"gen_{name}__h200_q45.jpg", "JPEG", quality=45, subsampling=2)
        made.append(name)
    print("diagrams generated:", made)
    return 0


if __name__ == "__main__":
    sys.exit(main())
