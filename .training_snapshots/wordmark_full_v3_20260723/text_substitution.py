"""Stage 2.6b (METHOD_ICE 3.7): text as a first-class citizen.

Chain: Windows built-in OCR (winocr, no external binaries) detects text lines
-> font_match retrieves the best catalog/system font for each line -> TWO iron
gates (font_match's own conservative gate AND a stricter whole-line 0.90 IoU
at 4x supersample with component-count agreement) -> the winning font's TRUE
vector outlines replace the fitted letter regions as the TOP layer of the
painter's stack.  Any failure at any step leaves the faithful geometric fit
untouched — substitution is a bonus, never a gamble.

The glyph placement replicates font_match.render_tracked_text/compose_candidate
math exactly (per-char advance + tracking at 192pt, tight-bbox crop, base scale
to target ink height, x/y scale, centering + dx/dy) so the vector outlines land
where the raster search proved the fit.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFont

MIN_LINE_CHARS = 3
# Area IoU is boundary-band-dominated on thin letter stems (the EXACT font at
# perfect placement reads ~0.88 on a 7px-stem wordmark), so the lookalike wall
# is a BOUNDARY metric: max bidirectional silhouette distance at 4x, in native
# px.  An exact font sits sub-pixel; Arial-vs-Segoe letterform differences are
# >=1.5px somewhere on the outline.
LINE_IOU_SANITY = 0.80
# Measured on the Arial-Bold probe (40px cap height): exact font 1.91px
# (pure 1x binarization quantization), nearest lookalike (Arial regular)
# 4.61px, Segoe 6.68px — 2.5 passes truth with margin and rejects every
# impostor by >=1.8x.  Tiny text self-rejects earlier via the IoU sanity
# (thin stems read <0.8 even for the exact font) — conservative by design.
BOUNDARY_GATE_PX = 2.5
SUPERSAMPLE = 4

_SYSTEM_FONTS = [
    ("Arial", r"C:\Windows\Fonts\arial.ttf"),
    ("Arial Bold", r"C:\Windows\Fonts\arialbd.ttf"),
    ("Segoe UI", r"C:\Windows\Fonts\segoeui.ttf"),
    ("Segoe UI Bold", r"C:\Windows\Fonts\segoeuib.ttf"),
    ("Tahoma", r"C:\Windows\Fonts\tahoma.ttf"),
    ("Verdana", r"C:\Windows\Fonts\verdana.ttf"),
    ("Times New Roman", r"C:\Windows\Fonts\times.ttf"),
    ("Georgia", r"C:\Windows\Fonts\georgia.ttf"),
    ("Calibri", r"C:\Windows\Fonts\calibri.ttf"),
    ("Impact", r"C:\Windows\Fonts\impact.ttf"),
]


def ocr_lines(image: Image.Image) -> list[dict]:
    """Windows OCR lines: [{text, bbox=(x0,y0,x1,y1)}] in image pixels."""
    try:
        import winocr
        op = winocr.recognize_pil(image.convert("RGB"), "en")
        result = op.get() if hasattr(op, "get") else None
        if result is None:
            return []
    except Exception:
        return []
    lines = []
    for line in getattr(result, "lines", []) or []:
        words = list(getattr(line, "words", []) or [])
        if not words:
            continue
        text = "".join(ch for ch in line.text if ch.isprintable()).strip()
        alnum = sum(ch.isalnum() for ch in text)
        if len(text) < MIN_LINE_CHARS or alnum < max(3, 0.6 * len(text)):
            continue
        xs0 = [w.bounding_rect.x for w in words]
        ys0 = [w.bounding_rect.y for w in words]
        xs1 = [w.bounding_rect.x + w.bounding_rect.width for w in words]
        ys1 = [w.bounding_rect.y + w.bounding_rect.height for w in words]
        lines.append({"text": text,
                      "bbox": (min(xs0), min(ys0), max(xs1), max(ys1))})
    return lines


def _font_records():
    import font_match as fm
    records = []
    seen = set()
    for name, path in _SYSTEM_FONTS:
        p = Path(path)
        if p.is_file() and p.as_posix().lower() not in seen:
            seen.add(p.as_posix().lower())
            records.append(fm.FontRecord(name=name, path=str(p)))
    try:
        for rec in fm.load_or_build_catalog():
            key = Path(rec.path).as_posix().lower()
            if key not in seen and Path(rec.path).is_file():
                seen.add(key)
                records.append(rec)
    except Exception:
        pass
    return records


def _glyph_curves(font_path: str, text: str, tracking_em: float,
                  transform: tuple[float, float, float, float]) -> list[list]:
    """Vector outlines of `text`, mapped by the compose transform.

    transform = (sx, sy, tx, ty): p_target = (p_render * (sx, sy)) + (tx, ty)
    where p_render lives in the same coordinates as render_tracked_text's
    tightly-cropped raster (font_size=192, anchor='ls')."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.misc.transform import Transform
    from svgpathtools import parse_path
    from vectorize_papers import Curve

    size = 192
    pil_font = ImageFont.truetype(font_path, size)
    ascent, _descent = pil_font.getmetrics()
    tt = TTFont(font_path, fontNumber=0)
    upem = tt["head"].unitsPerEm
    cmap = tt.getBestCmap()
    glyph_set = tt.getGlyphSet()
    scale_font = size / float(upem)

    # 1) analytic outlines at draw coordinates (y down, baseline at `ascent`)
    paths = []
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for i, ch in enumerate(text):
        if ch == " " or ord(ch) not in cmap:
            continue
        x_pos = pil_font.getlength(text[:i]) + i * tracking_em * size
        pen = SVGPathPen(glyph_set)
        tpen = TransformPen(pen, Transform(scale_font, 0, 0, -scale_font,
                                           x_pos, float(ascent)))
        glyph_set[cmap[ord(ch)]].draw(tpen)
        d = pen.getCommands()
        if not d:
            continue
        path = parse_path(d)
        if not len(path):
            continue
        x0, x1, y0, y1 = path.bbox()
        min_x, max_x = min(min_x, x0), max(max_x, x1)
        min_y, max_y = min(min_y, y0), max(max_y, y1)
        paths.append(path)
    if not paths or not np.isfinite([min_x, min_y]).all():
        return []

    sx, sy, tx, ty = transform

    def map_pt(z: complex) -> np.ndarray:
        # tight-crop shift (render_tracked_text crops to nonzero bbox) + affine
        return np.array([(z.real - min_x) * sx + tx, (z.imag - min_y) * sy + ty])

    loops: list[list] = []
    for path in paths:
        for sub in path.continuous_subpaths():
            curves = []
            for seg in sub:
                kind = type(seg).__name__
                if kind == "Line":
                    curves.append(Curve(1, np.vstack((map_pt(seg.start), map_pt(seg.end)))))
                elif kind == "QuadraticBezier":
                    curves.append(Curve(2, np.vstack((map_pt(seg.start), map_pt(seg.control), map_pt(seg.end)))))
                elif kind == "CubicBezier":
                    curves.append(Curve(3, np.vstack((map_pt(seg.start), map_pt(seg.control1), map_pt(seg.control2), map_pt(seg.end)))))
                else:  # Arc — sample as cubic-ish polyline pieces
                    pts = [map_pt(seg.point(t)) for t in np.linspace(0, 1, 8)]
                    for a, b in zip(pts, pts[1:]):
                        curves.append(Curve(1, np.vstack((a, b))))
            if curves:
                loops.append(curves)
    return loops


def try_substitute_lines(image: Image.Image, regions: list) -> list[dict]:
    """Attempt gated font substitution for every OCR line.  Returns a list of
    substitution dicts: {bbox, ink_color, loops(FittedLoop-ready curve lists),
    font, text, iou}; empty on any global failure.  Pure function over the
    ORIGINAL raster — the caller decides how to splice regions."""
    try:
        import font_match as fm
        import cv2
    except Exception:
        return []
    flat = image.convert("RGB")
    subs: list[dict] = []
    lines = ocr_lines(flat)
    if not lines:
        # winocr is blind below ~30px line height — the consensus probe's
        # lasting find.  Detect on a 3x upscale, map boxes back: this opens
        # font substitution to the h24 challenge text that never even
        # reached the retrieval gate before.
        up = 3
        big = flat.resize((flat.width * up, flat.height * up), Image.LANCZOS)
        lines = [{"text": l["text"],
                  "bbox": tuple(v / up for v in l["bbox"])} for l in ocr_lines(big)]
    if not lines:
        return []
    records = _font_records()
    if not records:
        return []
    W, H = flat.size
    for line in lines:
        try:
            x0, y0, x1, y1 = line["bbox"]
            pad_x = max(2, int(0.10 * (x1 - x0)))
            pad_y = max(2, int(0.18 * (y1 - y0)))
            bx0, by0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
            bx1, by1 = min(W, x1 + pad_x), min(H, y1 + pad_y)
            if bx1 - bx0 < 12 or by1 - by0 < 6:
                continue
            bbox = (bx0, by0, bx1 - bx0, by1 - by0)
            target, roi, polarity = fm.extract_target_mask(
                flat, bbox, expected_text=line["text"])
            if target is None or target.sum() < 30:
                continue
            matches = fm.match_fonts(target, line["text"], records,
                                     top_k=3, refine_rounds=2)
            if not matches:
                continue
            best, best_alpha = matches[0]
            runner = matches[1][0].score if len(matches) > 1 else 0.0
            # Gate 1: font_match's own conservative gate
            if not (best.score >= 0.75 and best.iou >= 0.55
                    and best.topology_similarity >= 0.75
                    and (best.score - runner) >= 0.012):
                continue
            # Gate 2 (red-team): near-exact silhouette — lookalike fonts and
            # custom letterforms must NOT pass.  match_fonts already returns
            # the composed candidate mask at the best parameters.
            comp = np.asarray(best_alpha) > 0
            if comp.shape != target.shape:
                continue
            inter = float(np.logical_and(comp, target).sum())
            union = float(np.logical_or(comp, target).sum())
            iou = inter / union if union else 0.0
            n_t, _ = cv2.connectedComponents(target.astype(np.uint8), connectivity=8)
            n_c, _ = cv2.connectedComponents(comp.astype(np.uint8), connectivity=8)
            if iou < LINE_IOU_SANITY or n_t != n_c:
                continue
            # Boundary wall at 4x: silhouettes must agree everywhere.
            # (np.repeat, not cv2.resize: OpenCV 5.0 asserts on these arrays)
            up = SUPERSAMPLE
            t_hi = np.repeat(np.repeat(np.ascontiguousarray(target, np.uint8), up, 0), up, 1)
            c_hi = np.repeat(np.repeat(np.ascontiguousarray(comp, np.uint8), up, 0), up, 1)
            k3 = np.ones((3, 3), np.uint8)
            tb = (t_hi > 0) & ~(cv2.erode(t_hi, k3) > 0)
            cb = (c_hi > 0) & ~(cv2.erode(c_hi, k3) > 0)
            if not tb.any() or not cb.any():
                continue
            dt_t = cv2.distanceTransform((~tb).astype(np.uint8), cv2.DIST_L2, 3)
            dt_c = cv2.distanceTransform((~cb).astype(np.uint8), cv2.DIST_L2, 3)
            boundary_px = max(float(dt_t[cb].max()), float(dt_c[tb].max())) / up
            if boundary_px > BOUNDARY_GATE_PX:
                continue
            # Replicate compose_candidate's transform EXACTLY for the vector
            # outlines: base scale from ink_bbox height, centering on the ink
            # BBOX CENTER (not the centroid — that read as a whole-line shift).
            render = fm.render_tracked_text(best.font_file, line["text"], best.tracking_em)
            tx0, ty0, tx1, ty1 = fm.ink_bbox(target)
            r_h, r_w = float(render.shape[0]), float(render.shape[1])
            base = (ty1 - ty0) / r_h if r_h else 1.0
            sx = base * best.x_scale
            sy = base * best.y_scale
            tx = bx0 + 0.5 * (tx0 + tx1) + best.dx_px - 0.5 * r_w * sx
            ty = by0 + 0.5 * (ty0 + ty1) + best.dy_px - 0.5 * r_h * sy
            loops = _glyph_curves(best.font_file, line["text"], best.tracking_em,
                                  (sx, sy, tx, ty))
            if not loops:
                continue
            ink_pixels = np.asarray(roi.convert("RGB"), float)[target > 0]
            ink = tuple(int(v) for v in np.median(ink_pixels, axis=0))
            subs.append({"bbox": (bx0, by0, bx1, by1), "ink": ink,
                         "loops": loops, "font": best.font,
                         "text": line["text"], "iou": round(iou, 4)})
        except Exception:
            continue
    return subs


def consensus_align_lines(image, regions, exclude_bboxes=None) -> int:
    """Glyph consensus v1 (NEXT_STRIKES p.7): lines the retrieval gate REFUSED
    still get a shared LINE GRID — per-glyph fits jitter baseline/cap by a
    sub-pixel each, and that jitter reads as wobble at small sizes (114_bank,
    h24 challenge text).  Median baseline and cap-height over the line's glyph
    loops; every loop whose bottom (or top) sits within +-0.6 native px of the
    grid is shifted VERTICALLY as a whole (budgeted idealization; descenders
    and dots miss the budget by construction and stay).  Stem-width consensus
    is deliberately v2.  Returns the number of loops moved."""
    import numpy as np
    lines = ocr_lines(image)
    if not lines:
        # winocr is blind below ~30px line height (h24 challenge crops return
        # NOTHING) — upscale for detection only, map boxes back down
        up = 3
        big = image.resize((image.width * up, image.height * up), Image.LANCZOS)
        lines = [{"text": l["text"],
                  "bbox": tuple(v / up for v in l["bbox"])} for l in ocr_lines(big)]
    if not lines:
        return 0
    excl = [tuple(b) for b in (exclude_bboxes or [])]
    moved_total = 0
    for line in lines:
        bx0, by0, bx1, by1 = line["bbox"]
        if any(abs(bx0 - e[0]) < 4 and abs(by0 - e[1]) < 4 for e in excl):
            continue
        pad = 2.5
        line_h = by1 - by0
        glyph_loops = []
        for region in regions:
            if region.stroke is not None or not region.loops:
                continue
            for fl in region.loops:
                if not len(fl.source):
                    continue
                xs = fl.source[:, 0]
                ys = fl.source[:, 1]
                if (xs.min() >= bx0 - pad and xs.max() <= bx1 + pad
                        and ys.min() >= by0 - pad and ys.max() <= by1 + pad
                        and (ys.max() - ys.min()) <= 1.4 * line_h):
                    glyph_loops.append(fl)
        if len(glyph_loops) < 4:
            continue
        bottoms = np.array([float(max(c.control[:, 1].max() for c in fl.curves))
                            for fl in glyph_loops])
        tops_all = np.array([float(min(c.control[:, 1].min() for c in fl.curves))
                             for fl in glyph_loops])
        heights = bottoms - tops_all
        tall = heights >= 0.55 * float(np.median(heights))
        baseline = float(np.median(bottoms))
        cap = float(np.median(tops_all[tall])) if int(tall.sum()) >= 3 else None
        for fl, bot, top in zip(glyph_loops, bottoms, tops_all):
            shift = None
            db = baseline - bot
            if abs(db) <= 0.6 and abs(db) > 1e-4:
                shift = db
            elif cap is not None:
                dt = cap - top
                if abs(dt) <= 0.6 and abs(dt) > 1e-4:
                    shift = dt
            if shift is None:
                continue
            for c in fl.curves:
                c.control = c.control + np.array([0.0, shift])
            fl.source = fl.source + np.array([0.0, shift])
            moved_total += 1
    return moved_total
