"""Coverage-field template league for tiny loops (METHOD_ICE 3.5 / Stage 2.2).

At <=24px extent the crack polyline carries almost no shape evidence, but the
ANTI-ALIASED coverage map carries plenty: a 6px rounded square and a 6px circle
have visibly different alpha patterns even though their crack chains are nearly
identical.  Every design on the panel independently converged on fitting
analytic templates DIRECTLY to the observed per-pixel coverage.

League: axis-rect, rotated rect, rounded-rect, ellipse (rotated), diamond,
circle.  Coverage surrogate: alpha = clip(0.5 - sdf(p; params) / w, 0, 1) on a
3x3-supersampled grid (red-team: superellipse-class shapes have no closed-form
pixel coverage; the smooth SDF surrogate is differentiable and unbiased at the
0.5 level set).  Optimizer: Nelder-Mead per template (3-7 params, tiny grids),
winner by coverage-MAE with an MDL nudge; acceptance gated by BOTH coverage-MAE
and the classic crack-chain Hausdorff so a wrong template can never ship.
"""
from __future__ import annotations

import math

import numpy as np

# ------------------------------------------------------------------ SDFs
def _rot(p: np.ndarray, ang: float) -> np.ndarray:
    c, s = math.cos(-ang), math.sin(-ang)
    return p @ np.array([[c, -s], [s, c]]).T


def sdf_rect(p: np.ndarray, cx, cy, hw, hh, ang=0.0) -> np.ndarray:
    q = np.abs(_rot(p - np.array([cx, cy]), ang)) - np.array([hw, hh])
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
    inside = np.minimum(np.maximum(q[:, 0], q[:, 1]), 0.0)
    return outside + inside


def sdf_rrect(p: np.ndarray, cx, cy, hw, hh, r, ang=0.0) -> np.ndarray:
    r = float(np.clip(r, 0.0, max(0.0, min(hw, hh) - 1e-3)))
    return sdf_rect(p, cx, cy, hw - r, hh - r, ang) - r


def sdf_ellipse(p: np.ndarray, cx, cy, a, b, ang=0.0) -> np.ndarray:
    q = _rot(p - np.array([cx, cy]), ang)
    # scaled-space approximation, exact at the boundary, adequate at +-1px
    k = np.linalg.norm(q / np.array([max(a, 1e-3), max(b, 1e-3)]), axis=1)
    grad = np.linalg.norm(q / np.array([max(a, 1e-3) ** 2, max(b, 1e-3) ** 2]), axis=1)
    return (k - 1.0) * k / np.maximum(grad, 1e-6)


def sdf_circle(p: np.ndarray, cx, cy, r) -> np.ndarray:
    return np.linalg.norm(p - np.array([cx, cy]), axis=1) - max(r, 1e-3)


def sdf_diamond(p: np.ndarray, cx, cy, hw, hh, ang=0.0) -> np.ndarray:
    q = np.abs(_rot(p - np.array([cx, cy]), ang))
    hw = max(hw, 1e-3); hh = max(hh, 1e-3)
    # normalized L1 approximation of the rhombus SDF
    d = (q[:, 0] / hw + q[:, 1] / hh - 1.0)
    scale = 1.0 / math.hypot(1.0 / hw, 1.0 / hh)
    return d * scale


TEMPLATES = [
    # (name, sdf, n_params, init from (cx, cy, ex, ey), bounds scale, mdl_bits)
    ("circle",  lambda p, th: sdf_circle(p, th[0], th[1], th[2]), 3,
     lambda cx, cy, ex, ey: [cx, cy, 0.5 * (ex + ey) / 2.0], 2.0),
    ("ellipse", lambda p, th: sdf_ellipse(p, th[0], th[1], th[2], th[3], th[4]), 5,
     lambda cx, cy, ex, ey: [cx, cy, ex / 2.0, ey / 2.0, 0.0], 3.0),
    ("rect",    lambda p, th: sdf_rect(p, th[0], th[1], th[2], th[3], th[4]), 5,
     lambda cx, cy, ex, ey: [cx, cy, ex / 2.0, ey / 2.0, 0.0], 3.0),
    ("rrect",   lambda p, th: sdf_rrect(p, th[0], th[1], th[2], th[3], th[4], th[5]), 6,
     lambda cx, cy, ex, ey: [cx, cy, ex / 2.0, ey / 2.0, 0.2 * min(ex, ey), 0.0], 3.5),
    ("diamond", lambda p, th: sdf_diamond(p, th[0], th[1], th[2], th[3], th[4]), 5,
     lambda cx, cy, ex, ey: [cx, cy, ex / 2.0, ey / 2.0, 0.0], 3.0),
]


def _coverage_from_sdf(d: np.ndarray, width: float = 0.9) -> np.ndarray:
    return np.clip(0.5 - d / width, 0.0, 1.0)


def observed_alpha(analysis: np.ndarray, mask: np.ndarray, bbox, scale: int,
                   ink: np.ndarray, bg: np.ndarray):
    """Per-NATIVE-pixel coverage of the tiny region, unmixed along ink-bg."""
    x0, y0, x1, y1 = bbox
    axis = ink - bg
    denom = float(axis @ axis)
    if denom < 900.0:                     # <30/255 contrast: no usable coverage
        return None
    win = analysis[y0 * scale:(y1 + 1) * scale, x0 * scale:(x1 + 1) * scale].astype(float)
    a = np.clip(((win - bg) @ axis) / denom, 0.0, 1.0)
    if scale > 1:                          # average to native pixel grid
        h, w = a.shape
        h0, w0 = h // scale, w // scale
        a = a[:h0 * scale, :w0 * scale].reshape(h0, scale, w0, scale).mean(axis=(1, 3))
    return a


def fit_tiny_template(alpha: np.ndarray, origin_xy: tuple[float, float]):
    """Fit every template to the observed coverage; return the winner or None.

    Returns (name, params_world, mae) — params in NATIVE px world coordinates.
    """
    try:
        from scipy.optimize import minimize
    except Exception:
        return None
    h, w = alpha.shape
    ys, xs = np.mgrid[0:h, 0:w]
    pts = np.column_stack((xs.ravel() + 0.5, ys.ravel() + 0.5)).astype(float)
    target = alpha.ravel()
    m = target > 0.5
    if int(m.sum()) < 2:
        return None
    cx, cy = float(pts[m, 0].mean()), float(pts[m, 1].mean())
    ex = max(1.0, float(pts[m, 0].max() - pts[m, 0].min()) + 1.0)
    ey = max(1.0, float(pts[m, 1].max() - pts[m, 1].min()) + 1.0)

    best = None
    for name, sdf, nparams, init, mdl in TEMPLATES:
        theta0 = np.array(init(cx, cy, ex, ey), float)

        def loss(th):
            return float(np.mean(np.abs(_coverage_from_sdf(sdf(pts, th)) - target)))

        try:
            res = minimize(loss, theta0, method="Nelder-Mead",
                           options={"maxiter": 220 * nparams, "xatol": 1e-3,
                                    "fatol": 1e-5})
        except Exception:
            continue
        mae = float(res.fun)
        score = mae + 0.004 * mdl          # MDL nudge: simpler wins near-ties
        if best is None or score < best[0]:
            best = (score, name, res.x.copy(), mae)
    if best is None:
        return None
    _, name, th, mae = best
    th = th.copy()
    th[0] += origin_xy[0]
    th[1] += origin_xy[1]
    return name, th, mae


def template_outline(name: str, th: np.ndarray, samples: int = 96) -> np.ndarray:
    """Dense closed outline of the fitted template in world px (last != first)."""
    t = np.linspace(0.0, 2.0 * math.pi, samples, endpoint=False)
    if name == "circle":
        pts = np.column_stack((np.cos(t), np.sin(t))) * max(th[2], 0.05)
        ang = 0.0; c = th[:2]
    elif name == "ellipse":
        pts = np.column_stack((np.cos(t) * max(th[2], 0.05), np.sin(t) * max(th[3], 0.05)))
        ang = th[4]; c = th[:2]
    elif name == "rect":
        pts = _rect_outline(max(th[2], 0.05), max(th[3], 0.05), 0.0, samples)
        ang = th[4]; c = th[:2]
    elif name == "rrect":
        r = float(np.clip(th[4], 0.0, max(0.0, min(th[2], th[3]) - 1e-3)))
        pts = _rect_outline(max(th[2], 0.05), max(th[3], 0.05), r, samples)
        ang = th[5]; c = th[:2]
    elif name == "diamond":
        hw, hh = max(th[2], 0.05), max(th[3], 0.05)
        base = np.array([[hw, 0.0], [0.0, hh], [-hw, 0.0], [0.0, -hh]])
        per = max(8, samples // 4)
        segs = [np.linspace(base[i], base[(i + 1) % 4], per, endpoint=False) for i in range(4)]
        pts = np.vstack(segs)
        ang = th[4]; c = th[:2]
    else:
        return None
    co, si = math.cos(ang), math.sin(ang)
    rot = np.array([[co, -si], [si, co]])
    return pts @ rot.T + np.asarray(c)


def _rect_outline(hw: float, hh: float, r: float, samples: int) -> np.ndarray:
    """Rounded-rect outline centered at origin, radius r (0 = sharp)."""
    r = float(np.clip(r, 0.0, min(hw, hh)))
    core_w, core_h = hw - r, hh - r
    pts = []
    per_side = max(3, samples // 8)
    per_arc = max(3, samples // 8)
    corners = [(core_w, core_h, 0.0), (-core_w, core_h, 0.5 * math.pi),
               (-core_w, -core_h, math.pi), (core_w, -core_h, 1.5 * math.pi)]
    for i, (ccx, ccy, a0) in enumerate(corners):
        if r > 1e-6:
            arc = a0 + np.linspace(0.0, 0.5 * math.pi, per_arc, endpoint=False)
            pts.append(np.column_stack((ccx + r * np.cos(arc), ccy + r * np.sin(arc))))
        nxt = corners[(i + 1) % 4]
        start = np.array([ccx + r * math.cos(a0 + 0.5 * math.pi),
                          ccy + r * math.sin(a0 + 0.5 * math.pi)])
        end = np.array([nxt[0] + r * math.cos(nxt[2]), nxt[1] + r * math.sin(nxt[2])])
        pts.append(np.linspace(start, end, per_side, endpoint=False))
    return np.vstack(pts)
