"""Paper Sec 7: the REGION BOUNDARY GRAPH (Kopf-Lischinski framework).

From a per-pixel label map, extract:
  * EDGES  — maximal crack chains separating exactly two labels (junction to junction, or
             closed interface loops);
  * VERTICES (junctions) — pixel-corner points where >=3 labels meet;
  * K-L saddles — 2-label checkerboard points, resolved by connecting the SPARSER label's
    diagonal (Kopf-Lischinski sparse-pixels heuristic) so the tracer never crosses itself.

Each region's closed boundary cycles are then assembled as sequences of oriented edge
references — every interface is stored ONCE and shared by both regions, which is what makes
seamless fit-once vectorization possible (paper Sec 7 / He-Kang-Morel curve-elements).

Coordinates are pixel-corner (x, y) like mask_loops, so downstream fitting is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

OUTSIDE = -1


@dataclass
class GraphEdge:
    pair: tuple[int, int]              # unordered label pair (a < b), OUTSIDE allowed
    points: np.ndarray                 # (N,2) pixel-corner polyline, ordered
    closed: bool                       # True = interface loop with no junctions
    left_label: int                    # label on the LEFT when walking points in order


@dataclass
class RegionCycle:
    label: int
    steps: list[tuple[int, bool]]      # (edge_index, forward?) — forward keeps label on left


@dataclass
class RegionGraph:
    labels: np.ndarray
    edges: list[GraphEdge] = field(default_factory=list)
    junctions: np.ndarray | None = None            # (K,2) junction points
    cycles: dict[int, list[RegionCycle]] = field(default_factory=dict)


def _label_at(labels: np.ndarray, row: int, col: int) -> int:
    if 0 <= row < labels.shape[0] and 0 <= col < labels.shape[1]:
        return int(labels[row, col])
    return OUTSIDE


def build_region_graph(labels: np.ndarray) -> RegionGraph:
    H, W = labels.shape
    lab = labels

    # ---- boundary cracks ----------------------------------------------------------------
    # horizontal crack at corner-point (x,y)->(x+1,y): separates pixel (y-1,x) above and
    # (y,x) below; vertical crack (x,y)->(x,y+1): separates (y,x-1) left and (y,x) right.
    padded = np.full((H + 2, W + 2), OUTSIDE, dtype=np.int32)
    padded[1:-1, 1:-1] = lab
    hor = padded[:-1, 1:-1] != padded[1:, 1:-1]     # (H+1, W): crack y in 0..H, x in 0..W-1
    ver = padded[1:-1, :-1] != padded[1:-1, 1:]     # (H, W+1): crack y in 0..H-1, x in 0..W

    # ---- classify corner points ----------------------------------------------------------
    # degree of each corner point (x in 0..W, y in 0..H) = number of incident boundary cracks
    deg = np.zeros((H + 1, W + 1), dtype=np.int8)
    deg[:, :-1] += hor.astype(np.int8)              # crack to the right of the point
    deg[:, 1:] += hor.astype(np.int8)               # crack to the left
    deg[:-1, :] += ver.astype(np.int8)              # crack below
    deg[1:, :] += ver.astype(np.int8)               # crack above

    tl = padded[:-1, :-1]
    tr = padded[:-1, 1:]
    bl = padded[1:, :-1]
    br = padded[1:, 1:]
    saddle = (deg == 4) & (tl == br) & (tr == bl) & (tl != tr)
    # K-L sparse-pixels vote: the SPARSER label connects through its diagonal
    counts = {}
    vals, cnts = np.unique(lab, return_counts=True)
    for v, c in zip(vals, cnts):
        counts[int(v)] = int(c)
    counts[OUTSIDE] = 10 ** 9
    # connect_tlbr[y,x]: at a saddle, does the TL/BR label connect diagonally?
    tl_sparser = np.zeros_like(saddle)
    ys, xs = np.nonzero(saddle)
    for y, x in zip(ys, xs):
        a, b = int(tl[y, x]), int(tr[y, x])
        tl_sparser[y, x] = counts.get(a, 0) <= counts.get(b, 0)
    junction_mask = (deg >= 3) & ~saddle
    jys, jxs = np.nonzero(junction_mask)
    junctions = np.stack([jxs, jys], axis=1).astype(float) if len(jys) else np.zeros((0, 2))

    # ---- trace edges ----------------------------------------------------------------------
    # A DIRECTED half-crack keeps a specific label on its LEFT.  Directions: 0=+x 1=+y 2=-x 3=-y.
    # crack id: horizontal (y, x, 'h') traversed +x keeps ABOVE label (y-1,x) on left... in
    # image coords (y down), walking +x means left side is SMALLER y (above).
    visited_h = np.zeros_like(hor, dtype=np.uint8)   # bit1 = traversed +x, bit2 = -x
    visited_v = np.zeros_like(ver, dtype=np.uint8)   # bit1 = traversed +y, bit2 = -y

    def crack_labels_h(y: int, x: int) -> tuple[int, int]:   # (above, below)
        return _label_at(lab, y - 1, x), _label_at(lab, y, x)

    def crack_labels_v(y: int, x: int) -> tuple[int, int]:   # (left, right)
        return _label_at(lab, y, x - 1), _label_at(lab, y, x)

    def out_steps(px: int, py: int):
        """Directed boundary half-cracks leaving corner point (px,py): (kind,y,x,dirbit,left_label,end_point)."""
        steps = []
        if px <= W - 1 and hor[py, px]:              # +x along horizontal crack (y=py, x=px)
            above, below = crack_labels_h(py, px)
            steps.append(("h", py, px, 1, above, (px + 1, py)))
        if px >= 1 and hor[py, px - 1]:              # -x
            above, below = crack_labels_h(py, px - 1)
            steps.append(("h", py, px - 1, 2, below, (px - 1, py)))
        if py <= H - 1 and ver[py, px]:              # +y along vertical crack (y=py, x=px)
            left, right = crack_labels_v(py, px)
            steps.append(("v", py, px, 1, right, (px, py + 1)))
        if py >= 1 and ver[py - 1, px]:              # -y
            left, right = crack_labels_v(py - 1, px)
            steps.append(("v", py - 1, px, 2, left, (px, py - 1)))
        return steps

    def take(kind: str, y: int, x: int, dirbit: int) -> bool:
        # an undirected crack belongs to exactly ONE edge; mark both directions so the same
        # chain is never traced twice (the reverse orientation is derived when assembling)
        arr = visited_h if kind == "h" else visited_v
        if arr[y, x]:
            return False
        arr[y, x] = 3
        return True

    def next_step(px: int, py: int, left_label: int, came_from):
        """Continue keeping `left_label` on the left.  At saddles the K-L decision picks the
        turn; elsewhere the continuation with the same left label is unique."""
        cands = [s for s in out_steps(px, py)
                 if s[4] == left_label and (s[0], s[1], s[2]) != came_from]
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        # SADDLE: the K-L diagonal decision fixes a SYMMETRIC crack pairing at this point:
        # if the TL/BR label connects diagonally, the walls are (T-R) and (B-L); otherwise
        # (T-L) and (B-R).  The pairing is independent of walk direction/label, so both
        # regions trace identical geometry through the point.
        def slot_out(step):
            kind_s, y_s, x_s = step[0], step[1], step[2]
            if kind_s == "h":
                return "R" if x_s == px else "L"
            return "B" if y_s == py else "T"

        def slot_in(came):
            kind_c, y_c, x_c = came
            if kind_c == "h":
                return "L" if px == x_c + 1 else "R"
            return "T" if py == y_c + 1 else "B"

        pair_map = ({"T": "R", "R": "T", "B": "L", "L": "B"} if tl_sparser[py, px]
                    else {"T": "L", "L": "T", "B": "R", "R": "B"})
        want = pair_map[slot_in(came_from)] if came_from is not None else None
        for s2 in cands:
            if want is None or slot_out(s2) == want:
                return s2
        return cands[0]

    edges: list[GraphEdge] = []
    is_junction = junction_mask

    def trace_from(px: int, py: int, first) -> None:
        kind, y, x, dirbit, left_label, end = first
        if not take(kind, y, x, dirbit):
            return
        pts = [(px, py), end]
        came = (kind, y, x)
        cx, cy = end
        while not is_junction[cy, cx]:
            nxt = next_step(cx, cy, left_label, came)
            if nxt is None:
                break
            kind, y, x, dirbit, _, end = nxt
            if not take(kind, y, x, dirbit):
                break
            pts.append(end)
            came = (kind, y, x)
            cx, cy = end
            if (cx, cy) == (px, py) and not is_junction[cy, cx]:
                break                                  # closed interface loop
        arr = np.asarray(pts, dtype=float)
        closed = bool((arr[0] == arr[-1]).all()) and len(arr) > 3
        other = None
        # label on the right = the pair partner
        if kind == "h":
            above, below = crack_labels_h(y, x)
            other = below if left_label == above else above
        else:
            left, right = crack_labels_v(y, x)
            other = left if left_label == right else right
        pair = (min(left_label, other), max(left_label, other))
        edges.append(GraphEdge(pair=pair, points=arr, closed=closed, left_label=left_label))

    # junction-anchored edges first
    for y, x in zip(*np.nonzero(is_junction)):
        for s in out_steps(int(x), int(y)):
            trace_from(int(x), int(y), s)
    # remaining cracks belong to closed interface loops
    ys, xs = np.nonzero(hor)
    for y, x in zip(ys, xs):
        if not visited_h[y, x] & 1:
            above, below = crack_labels_h(int(y), int(x))
            trace_from(int(x), int(y), ("h", int(y), int(x), 1, above, (int(x) + 1, int(y))))
        if not visited_h[y, x] & 2:
            above, below = crack_labels_h(int(y), int(x))
            trace_from(int(x) + 1, int(y), ("h", int(y), int(x), 2, below, (int(x), int(y))))
    ys, xs = np.nonzero(ver)
    for y, x in zip(ys, xs):
        if not visited_v[y, x] & 1:
            left, right = crack_labels_v(int(y), int(x))
            trace_from(int(x), int(y), ("v", int(y), int(x), 1, right, (int(x), int(y) + 1)))
        if not visited_v[y, x] & 2:
            left, right = crack_labels_v(int(y), int(x))
            trace_from(int(x), int(y) + 1, ("v", int(y), int(x), 2, left, (int(x), int(y))))

    graph = RegionGraph(labels=lab, edges=edges, junctions=junctions)
    graph.cycles = _assemble_cycles(graph)
    return graph


def _assemble_cycles(graph: RegionGraph) -> dict[int, list[RegionCycle]]:
    """Per region: order its incident (edge, orientation) references into closed cycles.
    Each directed edge (label on left) is used exactly once by that label's region."""
    start_of: dict[tuple[float, float, int], list[tuple[int, bool]]] = {}
    for ei, e in enumerate(graph.edges):
        a, b = e.pair
        # forward direction keeps e.left_label on the left; reverse keeps the partner
        fwd_label = e.left_label
        rev_label = a if fwd_label == b else b
        key_f = (float(e.points[0][0]), float(e.points[0][1]), fwd_label)
        start_of.setdefault(key_f, []).append((ei, True))
        key_r = (float(e.points[-1][0]), float(e.points[-1][1]), rev_label)
        start_of.setdefault(key_r, []).append((ei, False))

    used: set[tuple[int, bool]] = set()
    cycles: dict[int, list[RegionCycle]] = {}
    for ei, e in enumerate(graph.edges):
        for forward in (True, False):
            if (ei, forward) in used:
                continue
            label = e.left_label if forward else (e.pair[0] if e.left_label == e.pair[1] else e.pair[1])
            if label == OUTSIDE:
                used.add((ei, forward))
                continue
            steps: list[tuple[int, bool]] = []
            cur = (ei, forward)
            guard = 0
            while cur not in used and guard < 100000:
                guard += 1
                used.add(cur)
                steps.append(cur)
                ce, cf = cur
                pts = graph.edges[ce].points
                endp = pts[-1] if cf else pts[0]
                key = (float(endp[0]), float(endp[1]), label)
                nxts = [s for s in start_of.get(key, []) if s not in used]
                if not nxts:
                    break
                # unique continuation for this label at a junction (valence-3/4); if the
                # label appears twice (pinch), prefer the edge that is NOT the reverse of
                # the one we came on
                nxts.sort(key=lambda s: (s[0] == ce))
                cur = nxts[0]
            if steps:
                cycles.setdefault(label, []).append(RegionCycle(label=label, steps=steps))
    return cycles


def cycle_polyline(graph: RegionGraph, cycle: RegionCycle) -> np.ndarray:
    """Concatenated pixel-corner polyline of a cycle (closed; last point == first omitted)."""
    parts = []
    for ei, forward in cycle.steps:
        pts = graph.edges[ei].points
        seg = pts if forward else pts[::-1]
        parts.append(seg[:-1])
    return np.vstack(parts)


# ================================ Sec-7 vectorization =================================
def vectorize_region_graph(labels: np.ndarray, analysis_scale: float,
                           px: float = 1.0, label_lab: dict | None = None):
    """Fit the region graph ONCE and share every interface between its two regions.

    alpha (Sec 5.1 accuracy weight) is computed PER POLYLINE from its own extent —
    the paper's rs is the raster resolution of the SHAPE being fit, and on a shared
    canvas that is each cycle/edge, never the image size.

    Returns ({label: [FittedLoop,...]}, corner_dots) — corner_dots in native coords for the
    debug asset.  Paper Sec 7 steps:
      1. corners per REGION cycle (the detector sees closed staircase loops — in-domain);
      2. corner CONSENSUS on internal edges: kept only if BOTH regions detect within 1.5px
         (edges against the outside keep the single side's corners);
      3. junction rules: best straight-through pair of edge-ends (>=135 deg continuation,
         no consensus corner within 1px) becomes G1; valence-4 may take two disjoint
         pairs; every other incidence stays C0;
      4. each edge fitted ONCE (corner-split fit_segment_midpoints; closed interfaces via
         fit_loop_paper); both regions reuse the same curves (reversed for one side), so
         seams are impossible by construction."""
    import math
    from geometry_vectorizer import (FittedLoop, fit_segment_midpoints, fit_loop_paper,
                                     paper_corner_positions, _enforce_g1_chain,
                                     _corner_intersection, _intersect_supports, _support_of,
                                     _shift_curve_start, _shift_curve_end,
                                     _tangent_in, _tangent_out, _tag_arcs)
    from vectorize_papers import Curve, fit_circle, point_line_distance

    g = build_region_graph(labels)
    inv = 1.0 / float(analysis_scale)

    # ---- 1) per-region corners --------------------------------------------------------
    region_pts: dict[int, np.ndarray] = {}
    for label, cys in g.cycles.items():
        pts_all = []
        for cy in cys:
            poly = cycle_polyline(g, cy) * inv
            if len(poly) < 24:
                continue
            coarse = poly[:: max(1, int(analysis_scale))]
            got = paper_corner_positions(coarse)
            if len(got):
                pts_all.append(np.asarray(got, float))
        region_pts[label] = np.vstack(pts_all) if pts_all else np.zeros((0, 2))

    # ---- 2) consensus per edge --------------------------------------------------------
    edge_corners: list[np.ndarray] = []
    for e in g.edges:
        a, b = e.pair
        pts = e.points * inv
        pa = region_pts.get(a, np.zeros((0, 2)))
        pb = region_pts.get(b, np.zeros((0, 2)))

        def near_edge(P):
            if not len(P):
                return np.zeros((0, 2))
            d = np.min(np.linalg.norm(P[:, None, :] - pts[None, :, :], axis=2), axis=1)
            return P[d <= 1.0]

        na, nb = near_edge(pa), near_edge(pb)
        if a == OUTSIDE or b == OUTSIDE:
            cands = list(nb if a == OUTSIDE else na)
        else:
            cands = []
            for p in na:                        # both regions must agree within 1.5px
                if len(nb):
                    dmin = np.linalg.norm(nb - p, axis=1)
                    j = int(np.argmin(dmin))
                    if float(dmin[j]) <= 1.5:
                        cands.append(0.5 * (p + nb[j]))
        dedup: list[np.ndarray] = []
        for p in cands:
            if all(float(np.linalg.norm(p - q)) > 1.5 for q in dedup):
                dedup.append(np.asarray(p, float))
        edge_corners.append(np.asarray(dedup, float).reshape(-1, 2))

    # ---- 3) junction map (the G1 PAIR CHOICE moves after fitting: paper picks
    # continuity from the independently FITTED primitives, not raw crack tangents) ----
    jmap: dict[tuple[float, float], list[tuple[int, bool]]] = {}
    for ei, e in enumerate(g.edges):
        if e.closed:
            continue
        jmap.setdefault((float(e.points[0][0]), float(e.points[0][1])), []).append((ei, False))
        jmap.setdefault((float(e.points[-1][0]), float(e.points[-1][1])), []).append((ei, True))

    # ---- 4) fit each edge ONCE ----------------------------------------------------------
    def _alpha_for(pts: np.ndarray) -> float:
        # paper Sec 5.1: alpha = 32 / rs, rs = the fitted polyline's own raster extent
        return 32.0 / max(16.0, float(np.ptp(pts[:, 0]) + np.ptp(pts[:, 1])) / 2)

    def _edge_px(e) -> float:
        # Contrast-calibrated tube (form-field diagnosis, items 068/059: the
        # kink tail lives on RAGGED LOW-CONTRAST boundaries between bands of
        # one ramp — a linear/radial fill cannot express the content, but the
        # boundary POSITION between near-equal colours is genuinely less
        # certain, so the interval may widen).  dE >= 25: crisp ink boundary,
        # tube unchanged; below that the half-width grows up to 1.8x.
        if label_lab is None:
            return px
        a, b = e.pair
        ca, cb = label_lab.get(a), label_lab.get(b)
        if ca is None or cb is None:
            return px
        de = float(np.linalg.norm(np.asarray(ca, float) - np.asarray(cb, float)))
        if de >= 25.0:
            return px
        return px * min(1.8, 1.0 + (25.0 - de) / 20.0)

    edge_curves: list[list] = []
    for ei, e in enumerate(g.edges):
        pts = e.points * inv
        corners = edge_corners[ei]
        px_e = _edge_px(e)
        if e.closed:
            loop_pts = pts[:-1] if np.allclose(pts[0], pts[-1]) else pts
            fitted = fit_loop_paper(loop_pts, _alpha_for(loop_pts), corner_positions=corners, px=px_e)
            edge_curves.append(list(fitted.curves))
            continue
        if len(corners):
            order = []
            for p in corners:
                idx = int(np.argmin(np.linalg.norm(pts - p, axis=1)))
                if 3 <= idx <= len(pts) - 4:
                    order.append(idx)
            cuts = [0] + sorted(set(order)) + [len(pts) - 1]
        else:
            cuts = [0, len(pts) - 1]
        # fit each corner-bounded piece UNSNAPPED (the corner-vertex pin tilts long
        # LSQ lines by raster quantization), then close the piece joins at the
        # intersection of the adjacent primitives' supports — same rule as loops.
        chains: list[list] = []
        for a2, b2 in zip(cuts[:-1], cuts[1:]):
            if b2 - a2 < 1:
                continue
            piece = pts[a2:b2 + 1]
            if len(piece) < 3:
                chains.append([Curve(1, np.vstack((piece[0], piece[-1])))])
            else:
                chain = fit_segment_midpoints(piece, _alpha_for(piece), px_e, snap_ends=False)
                chains.append(chain if chain else [Curve(1, np.vstack((piece[0], piece[-1])))])
        # GRAPH-CRITIC (kink-map lesson, items 068/075/082: the tail lives on
        # consensus-cut joints — every cut ships a C0 even when the 'corner'
        # was AA/codec noise, and no merge pass ever crosses a cut).  A weak
        # joint (end-tangent break < 28 deg) triggers a surgical refit of the
        # MERGED piece; accepted only if the refit needs no more primitives
        # than the pair it replaces and carries no internal break > 20 deg —
        # a real corner survives because its merged refit must zigzag.
        piece_bounds = [(a2, b2) for a2, b2 in zip(cuts[:-1], cuts[1:]) if b2 - a2 >= 1]
        if len(chains) >= 2:
            k = 0
            while k < len(chains) - 1 and len(chains) >= 2:
                ca, cb = chains[k], chains[k + 1]
                if not ca or not cb:
                    k += 1
                    continue
                ta = _tangent_out(ca[-1])
                tb = _tangent_in(cb[0])
                ang = float(np.degrees(np.arccos(np.clip(float(ta @ tb), -1.0, 1.0))))
                if ang >= 28.0:
                    k += 1
                    continue
                a_lo, _ = piece_bounds[k]
                _, b_hi = piece_bounds[k + 1]
                merged = pts[a_lo:b_hi + 1]
                refit = fit_segment_midpoints(merged, _alpha_for(merged), px_e, snap_ends=False)
                ok = bool(refit) and len(refit) <= len(ca) + len(cb) - 1
                if ok:
                    for t2 in range(len(refit) - 1):
                        t_a = _tangent_out(refit[t2])
                        t_b = _tangent_in(refit[t2 + 1])
                        a2d = float(np.degrees(np.arccos(np.clip(float(t_a @ t_b), -1.0, 1.0))))
                        if a2d > 20.0:
                            ok = False
                            break
                if ok:
                    # Residual court on the SAME evidence (first-ship lesson:
                    # a widened contrast-tube let a straight line through a
                    # rounded panel corner pass feasibility — swimlanes iou
                    # 0.739 -> 0.178).  The refit must explain the merged
                    # points essentially as well as the pair it replaces.
                    from geometry_vectorizer import eval_curve as _ec
                    mid_m = 0.5 * (merged[:-1] + merged[1:])
                    def _p90(cs):
                        drawn = np.vstack([_ec(c, 10) for c in cs])
                        dm = np.linalg.norm(mid_m[:, None, :] - drawn[None, :, :], axis=2)
                        return float(np.percentile(np.min(dm, axis=1), 90))
                    if _p90(refit) > _p90(ca + cb) + 0.05:
                        ok = False
                if ok:
                    chains[k:k + 2] = [refit]
                    piece_bounds[k:k + 2] = [(a_lo, b_hi)]
                else:
                    k += 1
        # NB: after critic merges, `cuts` is stale — the live joint vertices
        # are the piece_bounds seams (first-ship v2 lesson: sewing to stale
        # cut indices tore swimlanes panels apart, iou 0.739 -> 0.56).
        joint_verts = ([pts[b] for (_, b) in piece_bounds[:-1]]
                       if len(piece_bounds) == len(chains)
                       else [pts[cuts[k + 1]] for k in range(len(chains) - 1)])
        for k in range(len(chains) - 1):
            if not chains[k] or not chains[k + 1]:
                continue
            vertex = joint_verts[k]
            p = _corner_intersection(chains[k][-1], chains[k + 1][0], vertex)
            _shift_curve_end(chains[k][-1], p)
            _shift_curve_start(chains[k + 1][0], p)
        edge_curves.append([c for chain in chains for c in chain])

    # ---- 4.25) shared CO-CIRCULAR supports across graph edges --------------------------
    # A circle cut by colour-overlap junctions becomes several open graph edges.  Fitting
    # those independently lets short pieces win as lines/free cubics, producing the tiny
    # blue slivers visible in the Mastercard primitive map.  Recover a common analytic
    # circle from raw edge midpoints, cluster compatible supports, and rebuild every
    # eligible edge as <=90deg exact-tangent cubics BEFORE junction welding.  This is Sec-6
    # circle reuse at the graph scope; the later circle/circle support intersection keeps
    # shared junctions watertight.
    def _circle_chain(points: np.ndarray, center: np.ndarray, radius: float):
        radial = points - center
        angles = np.unwrap(np.arctan2(radial[:, 1], radial[:, 0]))
        delta = float(angles[-1] - angles[0])
        if abs(delta) < math.radians(8.0) or abs(delta) > 2.0 * math.pi * 1.05:
            return []
        start = float(angles[0])
        count = max(1, int(math.ceil(abs(delta) / (math.pi / 2.0))))
        curves = []
        for index in range(count):
            a0 = start + delta * index / count
            a1 = start + delta * (index + 1) / count
            step = a1 - a0
            p0 = center + radius * np.array([math.cos(a0), math.sin(a0)])
            p1 = center + radius * np.array([math.cos(a1), math.sin(a1)])
            k = 4.0 / 3.0 * math.tan(step / 4.0)
            c0 = p0 + k * radius * np.array([-math.sin(a0), math.cos(a0)])
            c1 = p1 - k * radius * np.array([-math.sin(a1), math.cos(a1)])
            curves.append(Curve(3, np.vstack((p0, c0, c1, p1))))
        return _tag_arcs(curves, center, radius)

    circle_candidates = []
    for ei, e in enumerate(g.edges):
        if e.closed or len(e.points) < 10:
            continue
        pts = e.points * inv
        mid = 0.5 * (pts[:-1] + pts[1:])
        fitted_circle = fit_circle(mid)
        if fitted_circle is None:
            continue
        center, radius, _ = fitted_circle
        if radius < 3.0:
            continue
        radial_error = np.abs(np.linalg.norm(mid - center, axis=1) - radius)
        tolerance = max(0.72, 0.012 * radius)
        if float(radial_error.max()) > tolerance:
            continue
        angles = np.unwrap(np.arctan2(mid[:, 1] - center[1], mid[:, 0] - center[0]))
        sweep = abs(float(angles[-1] - angles[0]))
        sagitta = float(point_line_distance(mid, pts[0], pts[-1]).max())
        if sweep < math.radians(18.0) or sagitta < 0.65:
            continue                              # near-line circle fit is degenerate
        circle_candidates.append((ei, np.asarray(center, float), float(radius), sweep, len(mid)))

    unused = set(range(len(circle_candidates)))
    while unused:
        seed_index = unused.pop()
        cluster = [seed_index]
        _ei0, c0, r0, _s0, _n0 = circle_candidates[seed_index]
        for other in list(unused):
            _ei1, c1, r1, _s1, _n1 = circle_candidates[other]
            rref = max(r0, r1)
            if (float(np.linalg.norm(c0 - c1)) <= max(2.0, 0.025 * rref)
                    and abs(r0 - r1) <= max(1.5, 0.03 * rref)):
                cluster.append(other)
                unused.remove(other)
        total_weight = sum(circle_candidates[index][4] for index in cluster)
        center = sum(circle_candidates[index][1] * circle_candidates[index][4]
                     for index in cluster) / max(1, total_weight)
        radius = sum(circle_candidates[index][2] * circle_candidates[index][4]
                     for index in cluster) / max(1, total_weight)
        for index in cluster:
            ei, _old_center, _old_radius, sweep, _count = circle_candidates[index]
            if len(cluster) < 2 and sweep < math.radians(70.0):
                continue                          # only strong standalone arcs are rewritten
            pts = g.edges[ei].points * inv
            mid = 0.5 * (pts[:-1] + pts[1:])
            common_error = np.abs(np.linalg.norm(mid - center, axis=1) - radius)
            if float(common_error.max()) > max(0.82, 0.015 * radius):
                continue
            rebuilt = _circle_chain(pts, center, radius)
            if rebuilt:
                edge_curves[ei] = rebuilt

    # ---- 4.5) pin every junction to ONE shared point (watertight) -----------------------
    # With unsnapped fits the incident drawn ends sit within ~1px of the crack
    # junction; the shared point is the SUPPORT INTERSECTION of the straightest
    # incident pair (valence 2: the corner between two edges), capped near the
    # crack pixel — all incident edges then meet EXACTLY there.
    def _end_curve(ei: int, at_end: bool):
        chain = edge_curves[ei]
        return (chain[-1] if at_end else chain[0]) if chain else None

    def _arriving_tangent(ei: int, at_end: bool) -> np.ndarray:
        c = _end_curve(ei, at_end)
        if c is None:
            return np.array([1.0, 0.0])
        return _tangent_out(c) if at_end else -_tangent_in(c)

    for jpt, ends in jmap.items():
        incident = [(ei, at_end) for ei, at_end in ends if _end_curve(ei, at_end) is not None]
        if not incident:
            continue
        jp = np.array(jpt, float) * inv
        shared = None
        if len(incident) >= 2:
            best = None
            for i in range(len(incident)):
                for j in range(i + 1, len(incident)):
                    straight = -float(_arriving_tangent(*incident[i]) @ _arriving_tangent(*incident[j]))
                    if best is None or straight > best[0]:
                        best = (straight, incident[i], incident[j])
            if best is not None:
                sa = _support_of(_end_curve(*best[1]))
                sb = _support_of(_end_curve(*best[2]))
                if sa is not None and sb is not None and best[0] < math.cos(math.radians(20.0)):
                    # a genuine corner/junction between the two: intersect supports
                    shared = _intersect_supports(sa, sb, jp)
        if shared is None or float(np.linalg.norm(shared - jp)) > 1.5:
            drawn_ends = [(_end_curve(ei, at_end).control[-1 if at_end else 0]) for ei, at_end in incident]
            shared = np.mean(np.asarray(drawn_ends, float), axis=0)
            if float(np.linalg.norm(shared - jp)) > 1.5:
                shared = jp
        for ei, at_end in incident:
            c = _end_curve(ei, at_end)
            if at_end:
                _shift_curve_end(c, shared)
            else:
                _shift_curve_start(c, shared)

    # ---- 4.6) junction continuity pairs from the FITTED tangents ------------------------
    g1_pairs: list[tuple[tuple[int, bool], tuple[int, bool]]] = []
    for jpt, ends in jmap.items():
        if len(ends) < 3:
            continue
        jp = np.array(jpt, float) * inv
        eligible = []
        for ei, at_end in ends:
            if _end_curve(ei, at_end) is None:
                continue
            ec = edge_corners[ei]
            if len(ec) and float(np.min(np.linalg.norm(ec - jp, axis=1))) <= 1.0:
                continue                        # paper: corner within 1px -> stays a corner
            eligible.append((ei, at_end))
        scored = []
        for i in range(len(eligible)):
            for j in range(i + 1, len(eligible)):
                straight = -float(_arriving_tangent(*eligible[i]) @ _arriving_tangent(*eligible[j]))
                if straight > math.cos(math.radians(45.0)):
                    scored.append((straight, eligible[i], eligible[j]))
        scored.sort(reverse=True, key=lambda t: t[0])
        taken: set = set()
        budget = 2 if len(ends) >= 4 else 1     # valence-4: two crossing pairs allowed
        for straight, ea, eb in scored:
            if budget <= 0 or ea in taken or eb in taken:
                continue
            g1_pairs.append((ea, eb))
            taken.add(ea)
            taken.add(eb)
            budget -= 1

    # ---- 5) junction G1 (shared curves mutate for BOTH regions) -------------------------
    for (ea, a_end), (eb, b_end) in g1_pairs:
        ca, cb = edge_curves[ea], edge_curves[eb]
        if not ca or not cb:
            continue
        A = ca[-1] if a_end else ca[0]
        B = cb[-1] if b_end else cb[0]
        first = A if a_end else Curve(A.degree, np.ascontiguousarray(A.control[::-1]), meta=A.meta)
        second = Curve(B.degree, np.ascontiguousarray(B.control[::-1]), meta=B.meta) if b_end else B
        newA, newB = _enforce_g1_chain([first, second], max_angle_deg=45.0)
        if not a_end:
            newA = Curve(newA.degree, np.ascontiguousarray(newA.control[::-1]), meta=newA.meta)
        if b_end:
            newB = Curve(newB.degree, np.ascontiguousarray(newB.control[::-1]), meta=newB.meta)
        ca[-1 if a_end else 0] = newA
        cb[-1 if b_end else 0] = newB

    # ---- 6) assemble per-region loops from the SHARED curves ----------------------------
    def reversed_curve(c):
        return Curve(c.degree, np.ascontiguousarray(c.control[::-1]), meta=c.meta)

    out: dict[int, list] = {}
    corner_dots = [ec for ec in edge_corners if len(ec)]
    for label, cys in g.cycles.items():
        if label == OUTSIDE:
            continue
        loops = []
        for cy in cys:
            poly = cycle_polyline(g, cy) * inv
            curves = []
            for ei, forward in cy.steps:
                ecs = edge_curves[ei]
                if forward:
                    curves.extend(ecs)
                else:
                    curves.extend(reversed_curve(c) for c in reversed(ecs))
            if curves:
                fl = FittedLoop(poly, curves, "paper-regions")
                # Small-shape court for ISOLATED loops (single closed edge, no
                # junctions — the interface belongs to this region and its one
                # neighbour, so replacing our copy cannot tear a shared chain;
                # the later-painted region covers the sub-pixel disagreement).
                # This is where the loop-path's circle/rect tournament finally
                # reaches graph-path content: alarm hammers (item057) and the
                # graph-path roundness tail lived exactly here.
                # (A <=3-edge 'touching shapes' admission was probed
                # 2026-07-14 and removed as DEAD code: item057's hammer
                # cycles never entered even at 30% minor-contact — their
                # step structure needs instrumenting before the next try.)
                court_ok = len(cy.steps) == 1
                if court_ok and len(poly) >= 10 and len(curves) >= 2:
                    extent = float(max(np.ptp(poly[:, 0]), np.ptp(poly[:, 1])))
                    if extent <= 24.0:
                        import geometry_vectorizer as _gv
                        closed_lp = poly if bool(np.all(poly[0] == poly[-1])) else np.vstack((poly, poly[:1]))
                        court = _gv._relative_circle_court(closed_lp, curves, px)
                        if court is not None:
                            fl = FittedLoop(poly, court, "paper-regions-court")
                loops.append(fl)
        if loops:
            out[label] = loops
    return out, corner_dots


if __name__ == "__main__":
    # tiny self-test: 3 vertical stripes + a disc
    lab = np.zeros((40, 60), np.int32)
    lab[:, 20:40] = 1
    lab[:, 40:] = 2
    yy, xx = np.mgrid[0:40, 0:60]
    lab[(yy - 20) ** 2 + (xx - 30) ** 2 < 81] = 3
    g = build_region_graph(lab)
    print(f"edges={len(g.edges)} junctions={len(g.junctions)} regions={sorted(g.cycles)}")
    for label, cys in sorted(g.cycles.items()):
        for cy in cys:
            poly = cycle_polyline(g, cy)
            print(f"  region {label}: cycle of {len(cy.steps)} edges, {len(poly)} pts")
