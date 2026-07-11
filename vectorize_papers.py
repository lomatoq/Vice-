"""Two paper-inspired line drawing vectorizers.

Pipeline:
  RGB image -> foreground shapes -> 1 px black boundary -> vectorization ->
  SVG/PNG black result and SVG/PNG result recolored from the source image.

The implementations reproduce the central algorithmic ideas of:
  [1] Favreau, Lafarge, Bousseau, 2016 (global fidelity/simplicity energy)
  [2] Bessmeltsev, Solomon, 2019 (multi-direction tracing at junctions)

Only NumPy and Pillow are required.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


Point = tuple[float, float]


@dataclass
class Curve:
    degree: int
    control: np.ndarray
    color: tuple[int, int, int] = (0, 0, 0)
    # optional provenance, e.g. ("arc", run_id, center_xy, radius): lets Sec-6 regularization
    # treat an arc's bezier run as ONE circular unit (co-circular clustering, rigid mapping)
    meta: object = None


def otsu(values: np.ndarray) -> float:
    values = np.clip(values.astype(np.float64), 0, 255)
    hist, _ = np.histogram(values, bins=256, range=(0, 256))
    prob = hist / max(1, hist.sum())
    omega = np.cumsum(prob)
    mu = np.cumsum(prob * np.arange(256))
    total = mu[-1]
    score = (total * omega - mu) ** 2 / np.maximum(omega * (1 - omega), 1e-12)
    return float(np.argmax(score))


def neighbors8(mask: np.ndarray) -> np.ndarray:
    p = np.pad(mask, 1, constant_values=False)
    out = np.zeros(mask.shape, dtype=np.uint8)
    for dy in range(3):
        for dx in range(3):
            if dx != 1 or dy != 1:
                out += p[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return out


def erode(mask: np.ndarray) -> np.ndarray:
    p = np.pad(mask, 1, constant_values=False)
    out = np.ones(mask.shape, dtype=bool)
    for dy in range(3):
        for dx in range(3):
            out &= p[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return out


def dilate(mask: np.ndarray) -> np.ndarray:
    p = np.pad(mask, 1, constant_values=False)
    out = np.zeros(mask.shape, dtype=bool)
    for dy in range(3):
        for dx in range(3):
            out |= p[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return out


def remove_small(mask: np.ndarray, min_size: int = 8) -> np.ndarray:
    h, w = mask.shape
    seen = np.zeros_like(mask)
    result = np.zeros_like(mask)
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack = [(int(y), int(x))]
        seen[y, x] = True
        comp: list[tuple[int, int]] = []
        while stack:
            cy, cx = stack.pop()
            comp.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if (dy or dx) and 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(comp) >= min_size:
            yy, xx = zip(*comp)
            result[np.array(yy), np.array(xx)] = True
    return result


def connected_components(mask: np.ndarray, min_size: int = 1) -> list[np.ndarray]:
    """Return 8-connected components as masks, including very small logo details."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    result: list[np.ndarray] = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack = [(int(y), int(x))]
        seen[y, x] = True
        comp: list[tuple[int, int]] = []
        while stack:
            cy, cx = stack.pop()
            comp.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if (dy or dx) and 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(comp) >= min_size:
            out = np.zeros_like(mask)
            yy, xx = zip(*comp)
            out[np.asarray(yy), np.asarray(xx)] = True
            result.append(out)
    return result


def _rgb_with_clean_alpha(image: Image.Image) -> np.ndarray:
    """Composite transparent pixels on white instead of trusting their hidden RGB."""
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    white.alpha_composite(rgba)
    return np.asarray(white.convert("RGB"), dtype=np.uint8)


def extract_shape_masks(image: Image.Image) -> tuple[np.ndarray, list[np.ndarray], np.ndarray, tuple[int, int, int], float]:
    """Segment flat artwork into closed colour regions.

    A single distance-from-background threshold loses inner shapes (for example,
    the letters inside a small logo).  Palette regions preserve those details,
    while component filtering prevents JPEG speckles becoming contours.
    """
    rgb = _rgb_with_clean_alpha(image)
    h, w = rgb.shape[:2]
    area = h * w
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    bg = np.median(border, axis=0)

    # A tiny median pass is useful for JPEG chroma noise, but is skipped when it
    # would be a large fraction of a very small image feature.
    source = Image.fromarray(rgb)
    quant_source = source.filter(ImageFilter.MedianFilter(3)) if min(h, w) >= 64 else source
    quantized = quant_source.quantize(colors=8, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    labels = np.asarray(quantized, dtype=np.int16)
    palette = np.asarray(quantized.getpalette(), dtype=np.uint8).reshape(-1, 3)
    used = np.unique(labels)

    # Merge palette entries that merely represent antialiasing/JPEG drift.
    parent = {int(i): int(i) for i in used}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for ia, a in enumerate(used):
        for b in used[ia + 1 :]:
            if np.linalg.norm(palette[int(a)].astype(float) - palette[int(b)].astype(float)) < 30.0:
                union(int(a), int(b))

    # Tiny palette entries are normally antialias/JPEG transition colours, not
    # independent shapes.  Attach them to the nearest substantial colour.
    root_counts: dict[int, int] = {}
    root_sums: dict[int, np.ndarray] = {}
    for label, count in zip(*np.unique(labels, return_counts=True)):
        root = find(int(label))
        root_counts[root] = root_counts.get(root, 0) + int(count)
        root_sums[root] = root_sums.get(root, np.zeros(3)) + palette[int(label)].astype(float) * int(count)
    root_colors = {root: root_sums[root] / root_counts[root] for root in root_counts}
    substantial = [root for root, count in root_counts.items() if count >= max(8, int(area * 0.02))]
    if not substantial:
        substantial = [max(root_counts, key=root_counts.get)]
    for root in list(root_counts):
        if root in substantial:
            continue
        nearest = min(substantial, key=lambda target: np.linalg.norm(root_colors[root] - root_colors[target]))
        parent[root] = nearest

    merged = np.vectorize(lambda value: find(int(value)), otypes=[np.int16])(labels)
    min_component = max(3, area // 100000)
    masks: list[np.ndarray] = []
    for label in np.unique(merged):
        region = merged == label
        pixels = rgb[region]
        color = np.median(pixels, axis=0) if len(pixels) else palette[int(label)]
        # Background-coloured islands are holes of another region; their loops
        # are already represented there and should not be duplicated.
        if np.linalg.norm(color.astype(float) - bg) < 34.0:
            continue
        for component in connected_components(region, min_component):
            yy, xx = np.nonzero(component)
            if len(xx) < min_component:
                continue
            # Reject isolated 1-pixel compression flecks, but keep thin strokes.
            if len(xx) <= 3 and (xx.max() == xx.min() or yy.max() == yy.min()):
                continue
            masks.append(component)

    # If quantisation found no useful region, retain a robust binary fallback.
    distance = np.sqrt(np.sum((rgb.astype(float) - bg) ** 2, axis=2))
    threshold = max(4.0, otsu(np.clip(distance, 0, 255)))
    if not masks:
        fallback = remove_small(distance > threshold, min_size=min_component)
        if fallback.any():
            masks = [fallback]

    boundary = np.zeros((h, w), dtype=bool)
    for mask in masks:
        boundary |= mask & ~erode(mask)
    return rgb, masks, boundary, tuple(int(x) for x in bg), threshold


def extract_boundary(image: Image.Image) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, int, int], float]:
    rgb, masks, boundary, bg, threshold = extract_shape_masks(image)
    foreground = np.zeros(boundary.shape, dtype=bool)
    for mask in masks:
        foreground |= mask
    return rgb, foreground, boundary, bg, threshold


def mask_loops(mask: np.ndarray) -> list[np.ndarray]:
    """Extract guaranteed-closed polygon loops along the binary-mask cell edges.

    Outer loops are clockwise (positive image-coordinate area), hole loops are
    counter-clockwise. Unlike a skeleton graph, these edges cannot end halfway.
    """
    h, w = mask.shape
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for y, x in zip(*np.nonzero(mask)):
        y, x = int(y), int(x)
        if y == 0 or not mask[y - 1, x]:
            edges.add(((x, y), (x + 1, y)))
        if x == w - 1 or not mask[y, x + 1]:
            edges.add(((x + 1, y), (x + 1, y + 1)))
        if y == h - 1 or not mask[y + 1, x]:
            edges.add(((x + 1, y + 1), (x, y + 1)))
        if x == 0 or not mask[y, x - 1]:
            edges.add(((x, y + 1), (x, y)))

    outgoing: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for a, b in edges:
        outgoing.setdefault(a, []).append(b)
    unused = set(edges)
    loops: list[np.ndarray] = []
    direction = {(1, 0): 0, (0, 1): 1, (-1, 0): 2, (0, -1): 3}
    while unused:
        start_edge = min(unused)
        start, current = start_edge
        unused.remove(start_edge)
        loop = [start, current]
        previous = start
        guard = 0
        while current != start and guard <= len(edges):
            guard += 1
            candidates = [q for q in outgoing.get(current, []) if (current, q) in unused]
            if not candidates:
                break
            old_dir = direction[(current[0] - previous[0], current[1] - previous[1])]
            # At a diagonal-touch ambiguity, turn right before going straight;
            # this keeps the two shapes as two independent closed loops.
            priority = {1: 0, 0: 1, 3: 2, 2: 3}
            candidates.sort(key=lambda q: priority[(direction[(q[0] - current[0], q[1] - current[1])] - old_dir) % 4])
            nxt = candidates[0]
            unused.remove((current, nxt))
            loop.append(nxt)
            previous, current = current, nxt
        if current == start and len(loop) >= 5:
            loops.append(np.asarray(loop, dtype=float))
    return loops


def signed_area(points: np.ndarray) -> float:
    p = points[:-1] if len(points) > 1 and np.allclose(points[0], points[-1]) else points
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))


def pixel_graph(boundary: np.ndarray) -> dict[tuple[int, int], list[tuple[int, int]]]:
    points = set(zip(*np.nonzero(boundary)))
    graph: dict[tuple[int, int], list[tuple[int, int]]] = {p: [] for p in points}
    for y, x in points:
        for dy, dx in ((-1, 0), (0, -1), (0, 1), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            q = (y + dy, x + dx)
            if q not in points:
                continue
            # Suppress diagonal shortcuts when an orthogonal bridge exists.
            if dy and dx and ((y + dy, x) in points or (y, x + dx) in points):
                continue
            graph[(y, x)].append(q)
    return graph


def trace_graph(graph: dict[tuple[int, int], list[tuple[int, int]]]) -> list[np.ndarray]:
    used: set[frozenset[tuple[int, int]]] = set()
    paths: list[np.ndarray] = []

    def walk(start: tuple[int, int], nxt: tuple[int, int]) -> list[tuple[int, int]]:
        path = [start, nxt]
        used.add(frozenset((start, nxt)))
        prev, cur = start, nxt
        while True:
            candidates = [q for q in graph[cur] if frozenset((cur, q)) not in used]
            if not candidates or (len(graph[cur]) != 2 and cur != start):
                break
            # Continue in the straightest available direction: the local frame-field rule.
            vin = np.array([cur[1] - prev[1], cur[0] - prev[0]], dtype=float)
            candidates.sort(key=lambda q: -float(np.dot(vin, [q[1] - cur[1], q[0] - cur[0]])))
            q = candidates[0]
            used.add(frozenset((cur, q)))
            path.append(q)
            prev, cur = cur, q
            if cur == start:
                break
        return path

    critical = [p for p, ns in graph.items() if len(ns) != 2]
    for p in critical:
        for q in graph[p]:
            if frozenset((p, q)) not in used:
                raw = walk(p, q)
                if len(raw) > 1:
                    paths.append(np.array([(x, y) for y, x in raw], dtype=float))
    for p, ns in graph.items():
        for q in ns:
            if frozenset((p, q)) not in used:
                raw = walk(p, q)
                if len(raw) > 1:
                    paths.append(np.array([(x, y) for y, x in raw], dtype=float))
    return paths


def resample(points: np.ndarray, spacing: float = 2.0) -> np.ndarray:
    if len(points) < 2:
        return points
    d = np.sqrt(np.sum(np.diff(points, axis=0) ** 2, axis=1))
    s = np.concatenate(([0.0], np.cumsum(d)))
    if s[-1] == 0:
        return points[:1]
    target = np.linspace(0, s[-1], max(2, int(s[-1] / spacing) + 1))
    return np.column_stack([np.interp(target, s, points[:, k]) for k in range(2)])


def fit_curve(points: np.ndarray, degree: int) -> tuple[np.ndarray, float]:
    if len(points) == 2 or degree == 1:
        control = np.array([points[0], points[-1]])
        t = np.linspace(0, 1, len(points))[:, None]
        pred = (1 - t) * control[0] + t * control[1]
        return control, float(np.mean(np.sum((pred - points) ** 2, axis=1)))
    seg = np.sqrt(np.sum(np.diff(points, axis=0) ** 2, axis=1))
    t = np.concatenate(([0.0], np.cumsum(seg)))
    t = t / max(t[-1], 1e-9)
    if degree == 2:
        a = (2 * (1 - t) * t)[:, None]
        fixed = ((1 - t) ** 2)[:, None] * points[0] + (t**2)[:, None] * points[-1]
        middle = np.linalg.lstsq(a, points - fixed, rcond=None)[0][0]
        control = np.array([points[0], middle, points[-1]])
        pred = fixed + a * middle
    else:
        a = np.column_stack((3 * (1 - t) ** 2 * t, 3 * (1 - t) * t**2))
        fixed = ((1 - t) ** 3)[:, None] * points[0] + (t**3)[:, None] * points[-1]
        middle = np.linalg.lstsq(a, points - fixed, rcond=None)[0]
        control = np.vstack((points[0], middle, points[-1]))
        pred = fixed + a @ middle
    return control, float(np.mean(np.sum((pred - points) ** 2, axis=1)))


def favreau_global_fit(points: np.ndarray, tolerance: float = 1.35, complexity: float = 0.32) -> list[Curve]:
    """Dynamic-programming minimization of fidelity + curve count/degree."""
    pts = resample(points, 2.0)
    n = len(pts)
    if n < 2:
        return []
    inf = float("inf")
    dp = [inf] * n
    prev: list[tuple[int, int, np.ndarray] | None] = [None] * n
    dp[0] = 0.0
    for j in range(1, n):
        for i in range(max(0, j - 55), j):
            sample = pts[i : j + 1]
            for degree in (1, 2, 3):
                if len(sample) <= degree:
                    continue
                control, mse = fit_curve(sample, degree)
                fidelity = mse / (tolerance * tolerance)
                simplicity = complexity * (1.0 + 0.22 * degree)
                cost = dp[i] + fidelity + simplicity
                if cost < dp[j]:
                    dp[j] = cost
                    prev[j] = (i, degree, control)
    curves: list[Curve] = []
    j = n - 1
    while j > 0 and prev[j] is not None:
        i, degree, control = prev[j]
        curves.append(Curve(degree, control))
        j = i
    curves.reverse()
    return curves


def point_line_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    den = float(np.dot(ab, ab))
    if den < 1e-12:
        return np.sqrt(np.sum((p - a) ** 2, axis=1))
    t = np.clip(((p - a) @ ab) / den, 0, 1)
    return np.sqrt(np.sum((p - (a + t[:, None] * ab)) ** 2, axis=1))


def rdp(points: np.ndarray, epsilon: float) -> np.ndarray:
    if len(points) <= 2:
        return points
    dist = point_line_distance(points[1:-1], points[0], points[-1])
    idx = int(np.argmax(dist)) if len(dist) else 0
    if len(dist) and dist[idx] > epsilon:
        left = rdp(points[: idx + 2], epsilon)
        right = rdp(points[idx + 1 :], epsilon)
        return np.vstack((left[:-1], right))
    return np.vstack((points[0], points[-1]))


def rdp_closed(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Douglas-Peucker for a ring, preserving a real ring instead of a seam."""
    ring = points[:-1] if np.allclose(points[0], points[-1]) else points
    if len(ring) <= 4:
        return np.vstack((ring, ring[0]))
    a = int(np.argmin(ring[:, 0] + ring[:, 1]))
    b = int(np.argmax(np.sum((ring - ring[a]) ** 2, axis=1)))
    if a > b:
        a, b = b, a
    first = rdp(ring[a : b + 1], epsilon)
    second_raw = np.vstack((ring[b:], ring[: a + 1]))
    second = rdp(second_raw, epsilon)
    simplified = np.vstack((first[:-1], second[:-1]))
    return np.vstack((simplified, simplified[0]))


def taubin_smooth_ring(points: np.ndarray, passes: int = 5) -> np.ndarray:
    """Low-pass smooth a ring while the negative pass prevents shrinkage."""
    ring = points[:-1].copy() if np.allclose(points[0], points[-1]) else points.copy()
    for _ in range(passes):
        lap = 0.5 * (np.roll(ring, 1, axis=0) + np.roll(ring, -1, axis=0)) - ring
        ring += 0.42 * lap
        lap = 0.5 * (np.roll(ring, 1, axis=0) + np.roll(ring, -1, axis=0)) - ring
        ring -= 0.43 * lap
    return np.vstack((ring, ring[0]))


def resample_ring(points: np.ndarray, spacing: float = 1.0) -> np.ndarray:
    """Uniform arclength samples prevent pixel-density changes affecting smoothing."""
    ring = points[:-1] if np.allclose(points[0], points[-1]) else points
    closed = np.vstack((ring, ring[0]))
    distance = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))))
    count = max(8, int(round(distance[-1] / max(spacing, 0.25))))
    target = np.linspace(0.0, distance[-1], count, endpoint=False)
    sampled = np.column_stack([np.interp(target, distance, closed[:, k]) for k in range(2)])
    return np.vstack((sampled, sampled[0]))


def chaikin_smooth_ring(points: np.ndarray, passes: int = 2) -> np.ndarray:
    """Corner-cutting interpolation: very smooth, intentionally rounds corners."""
    ring = points[:-1] if np.allclose(points[0], points[-1]) else points
    for _ in range(passes):
        nxt = np.roll(ring, -1, axis=0)
        q = 0.75 * ring + 0.25 * nxt
        r = 0.25 * ring + 0.75 * nxt
        ring = np.column_stack((q, r)).reshape(-1, 2)
    return resample_ring(np.vstack((ring, ring[0])), 1.0)


def bspline_smooth_ring(points: np.ndarray, passes: int = 4) -> np.ndarray:
    """Uniform cubic B-spline-like low pass; strongest smoothing of the modes."""
    ring = resample_ring(points, 1.0)[:-1]
    for _ in range(passes):
        ring = (np.roll(ring, 1, axis=0) + 4.0 * ring + np.roll(ring, -1, axis=0)) / 6.0
    return np.vstack((ring, ring[0]))


def cad_regularize_ring(points: np.ndarray) -> np.ndarray:
    """Smooth subpixel jitter, then make supported straight runs collinear.

    Unlike a global blur this only modifies intervals that remain linear over a
    sizeable neighbourhood. Curves and unsupported corner neighbourhoods keep
    their Taubin-smoothed geometry.
    """
    smooth = taubin_smooth_ring(resample_ring(points, 0.75), passes=6)
    ring = smooth[:-1].copy()
    n = len(ring)
    if n < 16:
        return smooth
    half = max(4, min(10, n // 24))
    straight = np.zeros(n, dtype=bool)
    for i in range(n):
        indices = (np.arange(i - half, i + half + 1) % n).astype(int)
        window = ring[indices]
        centered = window - np.mean(window, axis=0)
        try:
            direction = np.linalg.svd(centered, full_matrices=False)[2][0]
        except np.linalg.LinAlgError:
            continue
        normal = np.array([-direction[1], direction[0]])
        residual = float(np.sqrt(np.mean((centered @ normal) ** 2)))
        travel = float(np.sum(np.linalg.norm(np.diff(window, axis=0), axis=1)))
        span = float(np.linalg.norm(window[-1] - window[0]))
        straight[i] = residual <= 0.24 and travel <= span * 1.03 + 1e-6

    # Rotate to a known false point so ordinary run extraction also handles the
    # run crossing the closed-ring seam.
    if straight.all():
        runs = [np.arange(n)]
    elif not straight.any():
        runs = []
    else:
        offset = int(np.flatnonzero(~straight)[0])
        rotated = np.roll(straight, -offset)
        runs = []
        start = None
        for j, value in enumerate(np.r_[rotated, False]):
            if value and start is None:
                start = j
            elif not value and start is not None:
                if j - start >= max(6, half):
                    runs.append((np.arange(start, j) + offset) % n)
                start = None

    for indices in runs:
        points_run = ring[indices]
        center = np.mean(points_run, axis=0)
        centered = points_run - center
        try:
            direction = np.linalg.svd(centered, full_matrices=False)[2][0]
        except np.linalg.LinAlgError:
            continue
        ring[indices] = center + np.outer(centered @ direction, direction)
    return np.vstack((ring, ring[0]))


def interpolate_ring(points: np.ndarray, mode: str = "corner") -> np.ndarray:
    """Apply the selected pre-primitive contour interpolation mode."""
    uniform = resample_ring(points, 1.0)
    if mode == "none":
        return uniform
    if mode == "chaikin":
        return chaikin_smooth_ring(uniform, passes=2)
    if mode == "bspline":
        return bspline_smooth_ring(uniform, passes=5)
    if mode == "cad":
        return cad_regularize_ring(points)
    # Taubin is the default because it damps stair-steps without shrinking arcs.
    return taubin_smooth_ring(uniform, passes=8)


def catmull_rom_ring(points: np.ndarray, tangent_scale: float = 0.92) -> list[Curve]:
    ring = points[:-1] if np.allclose(points[0], points[-1]) else points
    if len(ring) < 3:
        return [Curve(1, np.array([ring[0], ring[-1]]))]
    curves: list[Curve] = []
    for i in range(len(ring)):
        p0 = ring[(i - 1) % len(ring)]
        p1 = ring[i]
        p2 = ring[(i + 1) % len(ring)]
        p3 = ring[(i + 2) % len(ring)]
        c1 = p1 + tangent_scale * (p2 - p0) / 6.0
        c2 = p2 - tangent_scale * (p3 - p1) / 6.0
        curves.append(Curve(3, np.vstack((p1, c1, c2, p2))))
    return curves


def fit_circle(points: np.ndarray) -> tuple[np.ndarray, float, float] | None:
    """Taubin circle fit (Taubin, PAMI 1991) and its radial RMS residual.

    The naive algebraic (Kåsa) fit — minimising sum((x^2+y^2) - 2cx*x - 2cy*y - k)^2 —
    is heavily biased toward a SMALL radius when the points span only a short arc (it
    under-weights the far side of the circle), so a gentle lens edge was estimated ~10%
    too tight and rejected as an arc, collapsing to a cubic.  Taubin's method normalises
    by the gradient and is essentially unbiased for short arcs, at the same O(n) cost."""
    if len(points) < 4:
        return None
    x = points[:, 0]; y = points[:, 1]
    mx = float(x.mean()); my = float(y.mean())
    u = x - mx; v = y - my
    z = u * u + v * v
    Mz = float(z.mean())
    Mxx = float((u * u).mean()); Myy = float((v * v).mean()); Mxy = float((u * v).mean())
    Mxz = float((u * z).mean()); Myz = float((v * z).mean()); Mzz = float((z * z).mean())
    Cov_xy = Mxx * Myy - Mxy * Mxy
    Var_z = Mzz - Mz * Mz
    A3 = 4.0 * Mz
    A2 = -3.0 * Mz * Mz - Mzz
    A1 = Var_z * Mz + 4.0 * Cov_xy * Mz - Mxz * Mxz - Myz * Myz
    A0 = Mxz * (Mxz * Myy - Myz * Mxy) + Myz * (Myz * Mxx - Mxz * Mxy) - Var_z * Cov_xy
    A22 = A2 + A2; A33 = A3 + A3 + A3
    xnew = 0.0; ynew = A0
    for _ in range(99):                              # Newton root of the char. polynomial
        dy = A1 + xnew * (A22 + A33 * xnew)
        if abs(dy) < 1e-12:
            break
        xprev, yprev = xnew, ynew
        xnew = xprev - yprev / dy
        ynew = A0 + xnew * (A1 + xnew * (A2 + xnew * A3))
        if xnew == xprev or not math.isfinite(xnew) or abs(ynew) >= abs(yprev):
            xnew = xprev
            break
    det = xnew * xnew - xnew * Mz + Cov_xy
    if abs(det) < 1e-12:
        # degenerate (near-collinear) — fall back to the algebraic solve
        a = np.column_stack((2 * x, 2 * y, np.ones(len(points))))
        b = z + mx * mx + my * my + 2 * mx * u + 2 * my * v
        try:
            sol = np.linalg.lstsq(a, np.sum(points * points, axis=1), rcond=None)[0]
        except np.linalg.LinAlgError:
            return None
        center = sol[:2]
        radius2 = float(sol[2] + np.dot(center, center))
        if radius2 <= 0:
            return None
        radius = math.sqrt(radius2)
    else:
        cx = (Mxz * (Myy - xnew) - Myz * Mxy) / det / 2.0
        cy = (Myz * (Mxx - xnew) - Mxz * Mxy) / det / 2.0
        center = np.array([cx + mx, cy + my])
        radius2 = cx * cx + cy * cy + Mz
        if radius2 <= 0:
            return None
        radius = math.sqrt(radius2)
    residual = float(np.sqrt(np.mean((np.linalg.norm(points - center, axis=1) - radius) ** 2)))
    return center, radius, residual


def circular_beziers(p1: np.ndarray, p2: np.ndarray, old_center: np.ndarray, radius: float, arc: np.ndarray) -> list[Curve]:
    """Exact-tangent cubic approximation of a circular arc (at most 90° each)."""
    chord = p2 - p1
    length = float(np.linalg.norm(chord))
    if length < 1e-6:
        return []
    radius = max(radius, length * 0.5001)
    midpoint = 0.5 * (p1 + p2)
    normal = np.array([-chord[1], chord[0]]) / length
    offset = math.sqrt(max(0.0, radius * radius - 0.25 * length * length))
    choices = (midpoint + normal * offset, midpoint - normal * offset)
    center = min(choices, key=lambda c: float(np.linalg.norm(c - old_center)))
    angles = np.unwrap(np.arctan2(arc[:, 1] - old_center[1], arc[:, 0] - old_center[0]))
    sign = 1.0 if angles[-1] >= angles[0] else -1.0
    a1 = math.atan2(p1[1] - center[1], p1[0] - center[0])
    a2 = math.atan2(p2[1] - center[1], p2[0] - center[0])
    ccw = (a2 - a1) % (2 * math.pi)
    delta = ccw if sign > 0 else ccw - 2 * math.pi
    if abs(delta) > math.pi:
        delta += -2 * math.pi if delta > 0 else 2 * math.pi
    count = max(1, int(math.ceil(abs(delta) / (math.pi / 2))))
    curves: list[Curve] = []
    for j in range(count):
        start = a1 + delta * j / count
        end = a1 + delta * (j + 1) / count
        step = end - start
        q1 = center + radius * np.array([math.cos(start), math.sin(start)])
        q2 = center + radius * np.array([math.cos(end), math.sin(end)])
        k = 4.0 / 3.0 * math.tan(step / 4.0)
        c1 = q1 + k * radius * np.array([-math.sin(start), math.cos(start)])
        c2 = q2 - k * radius * np.array([-math.sin(end), math.cos(end)])
        curves.append(Curve(3, np.vstack((q1, c1, c2, q2))))
    return curves


def primitive_fit_ring(dense: np.ndarray, simplified: np.ndarray) -> list[Curve]:
    """Classify pieces as exact lines, regular circular arcs, or free curves."""
    ring = dense[:-1] if np.allclose(dense[0], dense[-1]) else dense
    vertices = simplified[:-1] if np.allclose(simplified[0], simplified[-1]) else simplified
    if len(vertices) < 3:
        return catmull_rom_ring(simplified)
    indices = [int(np.argmin(np.sum((ring - p) ** 2, axis=1))) for p in vertices]
    pieces: list[dict] = []
    for i, p1 in enumerate(vertices):
        p2 = vertices[(i + 1) % len(vertices)]
        a, b = indices[i], indices[(i + 1) % len(vertices)]
        arc = ring[a : b + 1] if b > a else np.vstack((ring[a:], ring[: b + 1]))
        line_error = float(np.max(point_line_distance(arc, p1, p2))) if len(arc) else 0.0
        if line_error <= 0.20:
            pieces.append({"kind": "line", "p1": p1, "p2": p2, "arc": arc})
            continue
        circle = fit_circle(arc)
        if circle is not None:
            center, radius, residual = circle
            sweep = float(np.sum(np.linalg.norm(np.diff(arc, axis=0), axis=1)) / max(radius, 1e-6))
            if residual <= 0.24 and 0.12 <= sweep <= math.pi * 1.1 and radius < 1000:
                pieces.append({"kind": "arc", "p1": p1, "p2": p2, "arc": arc, "center": center, "radius": radius})
                continue
        pieces.append({"kind": "wave", "p1": p1, "p2": p2, "arc": arc})

    # Similar arcs in one shape normally come from the same design radius.
    arc_ids = [i for i, p in enumerate(pieces) if p["kind"] == "arc"]
    remaining = set(arc_ids)
    while remaining:
        seed = remaining.pop()
        base = pieces[seed]["radius"]
        cluster = [seed]
        for i in list(remaining):
            if abs(pieces[i]["radius"] - base) / max(base, pieces[i]["radius"]) <= 0.14:
                cluster.append(i)
                remaining.remove(i)
        if len(cluster) >= 2:
            shared = float(np.median([pieces[i]["radius"] for i in cluster]))
            for i in cluster:
                pieces[i]["radius"] = shared

    curves: list[Curve] = []
    n = len(vertices)
    for i, piece in enumerate(pieces):
        if piece["kind"] == "line":
            curves.append(Curve(1, np.vstack((piece["p1"], piece["p2"]))))
        elif piece["kind"] == "arc":
            curves.extend(circular_beziers(piece["p1"], piece["p2"], piece["center"], piece["radius"], piece["arc"]))
        else:
            p0 = vertices[(i - 1) % n]
            p1 = vertices[i]
            p2 = vertices[(i + 1) % n]
            p3 = vertices[(i + 2) % n]
            c1 = p1 + 0.92 * (p2 - p0) / 6.0
            c2 = p2 - 0.92 * (p3 - p1) / 6.0
            curves.append(Curve(3, np.vstack((p1, c1, c2, p2))))
    return curves


def polyvector_fit(points: np.ndarray, tolerance: float = 0.68) -> list[Curve]:
    """Fidelity-oriented smooth cubic tracing of a closed frame-field path."""
    pts = resample(points, 0.7)
    if len(pts) < 2:
        return []
    closed = np.linalg.norm(pts[0] - pts[-1]) < 2.0
    if closed:
        smooth = taubin_smooth_ring(pts, passes=11)
        simplified = rdp_closed(smooth, tolerance)
        return primitive_fit_ring(smooth, simplified)
    smooth = pts.copy()
    for _ in range(4):
        smooth[1:-1] = 0.2 * smooth[:-2] + 0.6 * smooth[1:-1] + 0.2 * smooth[2:]
    simplified = rdp(smooth, tolerance)
    return [Curve(1, np.array([simplified[i], simplified[i + 1]])) for i in range(len(simplified) - 1)]


def eval_curve(curve: Curve, count: int = 24) -> np.ndarray:
    t = np.linspace(0, 1, count)[:, None]
    c = curve.control
    if curve.degree == 1:
        return (1 - t) * c[0] + t * c[1]
    if curve.degree == 2:
        return (1 - t) ** 2 * c[0] + 2 * (1 - t) * t * c[1] + t**2 * c[2]
    return (1 - t) ** 3 * c[0] + 3 * (1 - t) ** 2 * t * c[1] + 3 * (1 - t) * t**2 * c[2] + t**3 * c[3]


def source_color(points: np.ndarray, rgb: np.ndarray, boundary: np.ndarray, bg: tuple[int, int, int]) -> tuple[int, int, int]:
    colors = []
    h, w = boundary.shape
    for x, y in points[:: max(1, len(points) // 40)]:
        ix, iy = int(round(x)), int(round(y))
        y0, y1 = max(0, iy - 2), min(h, iy + 3)
        x0, x1 = max(0, ix - 2), min(w, ix + 3)
        patch = rgb[y0:y1, x0:x1]
        dist = np.sqrt(np.sum((patch.astype(float) - np.array(bg)) ** 2, axis=2))
        chosen = patch[dist > 12]
        if len(chosen):
            colors.extend(chosen.tolist())
    if not colors:
        return (0, 0, 0)
    samples = np.asarray(colors, dtype=float)
    distances = np.sqrt(np.sum((samples - np.asarray(bg, dtype=float)) ** 2, axis=1))
    # Anti-aliased edge pixels are mixtures with white. Keep the more saturated
    # half of the samples so a JPEG edge does not turn orange into pale beige.
    cutoff = np.percentile(distances, 55)
    saturated = samples[distances >= cutoff]
    return tuple(int(v) for v in np.median(saturated, axis=0))


def group_points(curves: list[Curve]) -> np.ndarray:
    chunks = [eval_curve(c, 32) for c in curves]
    if not chunks:
        return np.empty((0, 2))
    return np.vstack([chunk if i == 0 else chunk[1:] for i, chunk in enumerate(chunks)])


def render(curve_groups: list[list[Curve]], size: tuple[int, int], colored: bool, width: int = 2, supersample: int = 4) -> Image.Image:
    scale = max(1, supersample)
    canvas = Image.new("RGB", (size[0] * scale, size[1] * scale), "white")
    draw = ImageDraw.Draw(canvas)
    # Large outer contours first; smaller contours and holes are painted above.
    ordered = sorted(curve_groups, key=lambda g: abs(signed_area(group_points(g))), reverse=True)
    for curves in ordered:
        pts = group_points(curves)
        if len(pts) < 2:
            continue
        xy = [tuple(map(float, p * scale)) for p in pts]
        if colored:
            fill = curves[0].color if signed_area(pts) > 0 else (255, 255, 255)
            draw.polygon(xy, fill=fill)
        else:
            draw.line(xy, fill=(0, 0, 0), width=width * scale, joint="curve")
    if scale > 1:
        canvas = canvas.resize(size, Image.Resampling.LANCZOS)
    return canvas


def svg(curve_groups: list[list[Curve]], size: tuple[int, int], colored: bool) -> str:
    w, h = size
    rows = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">', '<rect width="100%" height="100%" fill="white"/>']
    ordered = sorted(curve_groups, key=lambda g: abs(signed_area(group_points(g))), reverse=True)
    for curves in ordered:
        commands = []
        for i, c in enumerate(curves):
            p = c.control
            move = f"M {p[0,0]:.2f},{p[0,1]:.2f} " if i == 0 else ""
            if c.degree == 1:
                commands.append(f"{move}L {p[1,0]:.2f},{p[1,1]:.2f}")
            elif c.degree == 2:
                commands.append(f"{move}Q {p[1,0]:.2f},{p[1,1]:.2f} {p[2,0]:.2f},{p[2,1]:.2f}")
            else:
                commands.append(f"{move}C {p[1,0]:.2f},{p[1,1]:.2f} {p[2,0]:.2f},{p[2,1]:.2f} {p[3,0]:.2f},{p[3,1]:.2f}")
        if not commands:
            continue
        d = " ".join(commands) + " Z"
        area = signed_area(group_points(curves))
        if colored:
            color = curves[0].color if area > 0 else (255, 255, 255)
            rows.append(f'<path d="{d}" fill="rgb{color}" stroke="none"/>')
        else:
            rows.append(f'<path d="{d}" fill="none" stroke="rgb(0, 0, 0)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    rows.append("</svg>")
    return "\n".join(rows)


def process(input_path: Path, output_dir: Path) -> dict:
    image = Image.open(input_path).convert("RGB")
    rgb, foreground, boundary, bg, threshold = extract_boundary(image)
    stem = input_path.stem
    case_dir = output_dir / stem
    case_dir.mkdir(parents=True, exist_ok=True)
    contour = Image.fromarray(np.where(boundary[..., None], 0, 255).astype(np.uint8).repeat(3, axis=2))
    contour.save(case_dir / "01_black_contour.png")
    # Cell-edge extraction guarantees that every shape and every hole is a
    # mathematically closed path before either paper-inspired fit is applied.
    paths = mask_loops(foreground)

    algorithms = {
        "favreau_global": lambda p: favreau_global_fit(p),
        "polyvector_field": lambda p: polyvector_fit(p),
    }
    stats = {"input": input_path.name, "background": bg, "threshold": threshold, "boundary_pixels": int(boundary.sum()), "paths": len(paths), "algorithms": {}}
    for name, fn in algorithms.items():
        groups: list[list[Curve]] = []
        for path in paths:
            curves = fn(path)
            color = source_color(path, rgb, boundary, bg)
            for c in curves:
                c.color = color
            if curves:
                groups.append(curves)
        prefix = "02" if name == "favreau_global" else "03"
        render(groups, image.size, False).save(case_dir / f"{prefix}_{name}_black.png")
        render(groups, image.size, True).save(case_dir / f"{prefix}_{name}_color.png")
        (case_dir / f"{prefix}_{name}_black.svg").write_text(svg(groups, image.size, False), encoding="utf-8")
        (case_dir / f"{prefix}_{name}_color.svg").write_text(svg(groups, image.size, True), encoding="utf-8")
        stats["algorithms"][name] = {"curve_groups": len(groups), "curve_segments": sum(len(g) for g in groups)}
    (case_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    all_stats = [process(p, args.output) for p in args.images]
    (args.output / "summary.json").write_text(json.dumps(all_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(all_stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
