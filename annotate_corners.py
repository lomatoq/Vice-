"""Human corner-annotation tool (the perceptual ground truth the paper has and we lack).

You annotate on the REAL FILLED ICON, rendered in TRUE COLOUR by resvg (gradients, strokes,
clip-paths, proper fill rule — so the ~24% of logos whose even-odd mask came out as a solid
block are now readable), ONCE per logo, in resolution-independent NORMALISED coordinates;
training then PROJECTS your corners onto every resolution (16/64/256...) and snaps them to
that resolution's boundary — one comfortable annotation yields multi-resolution labels.

Two synced panels: LEFT = annotate (colour icon + thin outline + your dots); RIGHT = a clean
colour reference (same view, zoom synced) so you can eyeball whether a corner is missing.

  * LEFT-CLICK  -> ADD a corner. With snap ON it lands on the nearest CORNER (local turning
                   maximum, the paper's criterion); a click on flat/interior/outside stays free.
  * RIGHT-CLICK -> REMOVE the nearest corner (dedicated, so adds never remove by accident)
  * HOLD button + drag = brush (add/remove continuously under the cursor)
  * t  toggle corner-snap on/off     MOUSE WHEEL -> zoom (both panels)     f -> fit / reset zoom
  * n / Right   next logo    p / Left  previous
  * s  save now    r  (re)load consistent PROPOSALS    c  clear all    q  save + quit

New logos are pre-filled with proposals from the paper-trained model (consistent corners); you
just prune the wrong ones and nudge — much faster and more consistent than marking from scratch.

The queue is the 365 GT logos plus ~100 diverse corpus icons (--corpus N) so coverage is not
only wordmarks.

Saves (resumable) to corner_annotations.json as { logo_stem: {file, corners_norm:[[nx,ny]..]} }.
Old per-(logo,res) entries are auto-migrated and never overwritten.
"""
from __future__ import annotations
import argparse, glob, json, re, sys, warnings
from io import BytesIO
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).resolve().parent))

GT = r"C:/Users/nirrt/Toolset/v-ice pictures/ground truth/Default"
CORPUS = r"C:/Users/nirrt/Toolset/v-ize train/dataset/icons/iconify"
OUT = Path(__file__).resolve().parent / "corner_annotations.json"
DISP = 384          # display + snapping resolution (clean, comfortable); coords stored NORMALISED
# guided "snap to corner" (paper criterion): a click near the boundary is pulled to the nearest
# LOCAL TURNING MAXIMUM, and a click on near-straight boundary is NOT snapped (kept free).
GUIDE_NEAR = 7.0    # px: only snap a click within this of the boundary
GUIDE_WIN = 4       # vertices: +/- window to find the local turning max
GUIDE_TURN = 25.0   # deg: minimum turn to accept a corner snap (below = treat as straight)
TURN_W = 4          # turning-angle window (px)
PROPOSE_MODEL = "corner_rf_paperonly.joblib"   # consistent (paper-trained) corner proposer


# ----------------------------------------------------------------- frame + colour rendering
def _frame_params(svg_path, target=DISP, margin_frac=0.06):
    """Reproduce EXACTLY the frame svg_region_masks builds (path-bbox based) so stored
    normalised corners stay valid.  Returns (xmin, ymin, scale, margin, W, H) or None."""
    from svgpathtools import svg2paths
    paths, _ = svg2paths(svg_path)
    boxes = []
    for p in paths:
        try:
            boxes.append(p.bbox())
        except Exception:
            pass
    if not boxes:
        return None
    xmin = min(b[0] for b in boxes); xmax = max(b[1] for b in boxes)
    ymin = min(b[2] for b in boxes); ymax = max(b[3] for b in boxes)
    span = max(xmax - xmin, ymax - ymin, 1e-6); scale = target / span; margin = target * margin_frac
    W = max(8, int(round((xmax - xmin) * scale + 2 * margin)))
    H = max(8, int(round((ymax - ymin) * scale + 2 * margin)))
    return xmin, ymin, scale, margin, W, H


def _viewbox(svg_path):
    head = open(svg_path, encoding="utf-8", errors="ignore").read(2000)
    m = re.search(r'viewBox\s*=\s*["\']([-\d.eE ,]+)["\']', head)
    if not m:
        return None
    v = [float(x) for x in re.split(r"[ ,]+", m.group(1).strip())]
    return v if len(v) == 4 else None


def render_color_resvg(svg_path, xmin, ymin, scale, margin, W, H):
    """TRUE-colour render (resvg) resampled into the svg_region_masks frame via the exact
    viewBox->frame affine.  GT icons have a viewBox and no transforms, so path-space ==
    viewBox-space and this is pixel-exact.  Returns (rgb uint8 HxWx3, alpha bool HxW) or None."""
    try:
        import resvg_py
    except Exception:
        return None
    vb = _viewbox(svg_path)
    if vb is None:
        return None
    vbx, vby, vbw, vbh = vb
    try:
        png = resvg_py.svg_to_bytes(svg_path=svg_path, width=1400)
    except Exception:
        return None
    from PIL import Image
    rgba = Image.open(BytesIO(bytes(png))).convert("RGBA")
    if vbw <= 0:
        return None
    Kr = rgba.size[0] / vbw                                   # resvg px per path/viewBox unit
    a = Kr / scale                                            # output-px -> resvg-px
    c = (xmin - vbx) * Kr - margin * a
    f = (ymin - vby) * Kr - margin * a
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    comp = Image.alpha_composite(bg, rgba).convert("RGB")
    col = comp.transform((W, H), Image.AFFINE, (a, 0, c, 0, a, f),
                         resample=Image.BILINEAR, fillcolor=(255, 255, 255))
    al = rgba.getchannel("A").transform((W, H), Image.AFFINE, (a, 0, c, 0, a, f),
                                        resample=Image.BILINEAR, fillcolor=0)
    return np.asarray(col), np.asarray(al) > 40


# ---- legacy solid-colour fallback (even-odd fills; used only if resvg is unavailable) ----
_NAMED = {"black": (0, 0, 0), "white": (245, 245, 245), "red": (220, 40, 40), "green": (40, 160, 60),
          "blue": (40, 90, 220), "yellow": (230, 200, 40), "gray": (128, 128, 128), "grey": (128, 128, 128)}


def _parse_fill(f):
    f = (f or "#000").strip()
    if f in ("none", ""):
        return None
    if f == "currentColor":
        return (25, 25, 30)
    if f.startswith("#"):
        h = f[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) >= 6:
            try:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            except ValueError:
                pass
    return _NAMED.get(f.lower(), (25, 25, 30))


def render_color(svg_path, target=DISP, margin_frac=0.06):
    """Fallback: each path filled with its own solid colour (even-odd holes) in the frame."""
    from svgpathtools import svg2paths
    from PIL import Image, ImageDraw
    from svg_corners import _sample_subpath
    fr = _frame_params(svg_path, target, margin_frac)
    if fr is None:
        return None
    xmin, ymin, scale, margin, W, H = fr
    paths, attrs = svg2paths(svg_path)
    to_px = lambda z: ((z.real - xmin) * scale + margin, (z.imag - ymin) * scale + margin)
    img = np.full((H, W, 3), 255, np.uint8)
    for p, at in zip(paths, attrs):
        col = _parse_fill(at.get("fill", "#000"))
        if col is None:
            continue
        acc = np.zeros((H, W), np.uint8)
        for sub in p.continuous_subpaths():
            poly = [to_px(z) for z in _sample_subpath(sub, scale)]
            if len(poly) >= 3:
                layer = Image.new("1", (W, H), 0)
                ImageDraw.Draw(layer).polygon(poly, fill=1)
                acc ^= np.asarray(layer, np.uint8)
        img[acc.astype(bool)] = col
    return img


# diverse corpus categories (monochrome / brand-colour / flat / gradient / file-type / flags /
# dev / emoji) so annotation coverage is not just gaming wordmarks.
_CORPUS_CATS = ["simple-icons", "logos", "flat-color-icons", "cryptocurrency-color",
                "vscode-icons", "material-icon-theme", "circle-flags", "devicon",
                "twemoji", "fluent-color"]


def _clean_svg(path):
    """svg2paths (used for the mask + frame) ignores transforms, so only queue icons that have
    a viewBox and NO geometry transform — otherwise the shown shape would not match the clicks."""
    try:
        head = open(path, encoding="utf-8", errors="ignore").read(60000)
    except Exception:
        return False
    return ("viewBox" in head) and ("transform=" not in head)


def _corpus_picks(n_corpus):
    import random
    rng = random.Random(7)
    per = max(1, -(-n_corpus // len(_CORPUS_CATS)))         # ceil per category
    picks = []
    for c in _CORPUS_CATS:
        cf = sorted(glob.glob(f"{CORPUS}/{c}/*.svg"))
        rng.shuffle(cf)
        taken = 0
        for cand in cf:
            if taken >= per:
                break
            if _clean_svg(cand):
                picks.append(cand); taken += 1
    rng.shuffle(picks)
    return picks[:n_corpus]


def build_queue(n_corpus=100, gt_undone=50):
    """Queue = every GT casino logo you have ALREADY annotated, plus `gt_undone` fresh ones,
    plus `n_corpus` diverse corpus icons.  Keeps the working set small: the ~150 not-yet-touched
    GT logos beyond the first `gt_undone` are dropped (they come back as you finish the batch)."""
    gt = sorted(glob.glob(f"{GT}/*.svg"))
    ann = json.loads(OUT.read_text()) if OUT.exists() else {}

    def done(f):
        s = Path(f).stem
        return s in ann or any(k.startswith(s + "@") for k in ann)

    done_gt = [f for f in gt if done(f)]
    undone_gt = [f for f in gt if not done(f)]
    corpus = _corpus_picks(n_corpus) if n_corpus else []
    return undone_gt[:gt_undone] + corpus + done_gt        # fresh work first, finished ones last


class Annotator:
    def __init__(self, files):
        from svg_corners import svg_region_masks
        from corner_classifier import mask_loops, predict_corners, _corner_turn, _to_ccw
        import geometry_vectorizer as gv
        self.svg_region_masks = svg_region_masks
        self.mask_loops = mask_loops
        self._corner_turn = _corner_turn
        self._to_ccw = _to_ccw
        self._rf_predict = predict_corners
        self.gv = gv
        self.files = files
        self.i = 0
        self.ann = json.loads(OUT.read_text()) if OUT.exists() else {}
        self.dragging = None                             # brush: which button is held
        self.snap = True                                 # snap adds to nearest CORNER (toggle: t)
        # consistent corner PROPOSER: paper-trained RF (falls back to the CNN pipeline)
        self.propose = None
        try:
            import joblib
            b = joblib.load(Path(__file__).resolve().parent / "models" / PROPOSE_MODEL)
            self.propose = (b["model"], int(b.get("s", 14))) if isinstance(b, dict) else (b, 14)
        except Exception as e:
            print("propose model unavailable, using pipeline:", e)
        self.fig, (self.axL, self.axR) = plt.subplots(1, 2, figsize=(16, 8.6), sharex=True, sharey=True)
        self.fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.02, wspace=0.04)
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.fig.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.load()
        plt.show()

    def key(self):
        return Path(self.files[self.i]).stem

    def _migrate(self, k):
        """Convert an old {stem}@{res} entry (corners in the res frame) to normalised."""
        for old, rec in self.ann.items():
            if old.startswith(k + "@") and "corners" in rec and rec.get("W"):
                W, H = rec["W"], rec["H"]
                return [[c[0] / W, c[1] / H] for c in rec["corners"]]
        return None

    def _silhouette_loops(self, alpha):
        loops = []
        for loop in self.mask_loops(alpha.astype(np.uint8)):
            lp = loop.astype(float)
            if len(lp) > 1 and np.allclose(lp[0], lp[-1]):
                lp = lp[:-1]
            if len(lp) >= 12:
                loops.append(lp)
        return loops

    def load(self):
        f = self.files[self.i]
        fr = _frame_params(f, target=DISP)
        if fr is None:
            print("skip", f); self.i = (self.i + 1) % len(self.files); return self.load()
        xmin, ymin, scale, margin, W, H = fr
        self.W, self.H = W, H
        # TRUE colour via resvg, aligned to the frame; correct silhouette from its alpha.
        rc = render_color_resvg(f, *fr)
        if rc is not None:
            col, alpha = rc
        else:                                            # resvg missing/failed -> mask fallback
            try:
                regions = self.svg_region_masks(f, target=DISP)
            except Exception as e:
                print("skip", f, e); self.i = (self.i + 1) % len(self.files); return self.load()
            alpha = np.zeros((H, W), bool)
            for m, _ in regions:
                alpha |= m.astype(bool)
            col = render_color(f, target=DISP)
            if col is None or col.shape[:2] != (H, W):
                col = np.where(alpha[:, :, None], np.uint8(140), np.uint8(255)) * np.ones(3, np.uint8)
        self.alpha = alpha                               # filled silhouette (for interior clicks)
        self.verts = self._silhouette_loops(alpha)
        self.verts_all = np.vstack(self.verts) if self.verts else np.zeros((0, 2))
        self.turns = [np.array([self._corner_turn(lp, i, TURN_W) for i in range(len(lp))])
                      for lp in self.verts]               # per-vertex turn (for corner-snap)

        for ax, outline in ((self.axL, True), (self.axR, False)):
            ax.clear()
            ax.imshow(col, interpolation="bilinear")
            if outline:
                for lp in self.verts:
                    ax.plot(*np.vstack([lp, lp[:1]]).T, "-", color=(0, 0, 0, 0.35), lw=0.6)
            ax.set_aspect("equal"); ax.axis("off")
        self.full_xlim = self.axL.get_xlim(); self.full_ylim = self.axL.get_ylim()

        k = self.key()
        if k in self.ann:                                          # resume (normalised)
            self.corners = [(nx * self.W, ny * self.H) for nx, ny in self.ann[k]["corners_norm"]]
        else:
            mig = self._migrate(k)
            if mig is not None:                                    # migrate old per-res work
                self.corners = [(nx * self.W, ny * self.H) for nx, ny in mig]
            else:                                                  # pre-populate with model
                self.corners = self._model_corners()
        self.redraw()

    def _model_corners(self):
        """Consistent corner proposals to pre-fill a NEW logo: the paper-trained RF if present
        (it encodes the paper's consistent corner concept), else the CNN pipeline."""
        if self.propose is not None:
            model, s = self.propose
            out = []
            for lp in self.verts:
                loop = self._to_ccw(lp.astype(np.float64))
                try:
                    mask = self._rf_predict(loop, model, s=s, threshold=0.45, nms_radius=2.5)
                    out += [(float(loop[i][0]), float(loop[i][1])) for i in np.flatnonzero(mask)]
                except Exception:
                    pass
            return out
        return [(float(c[0]), float(c[1]))
                for lp in self.verts for c in self.gv.paper_corner_positions(lp)]

    def _snap_to_corner(self, p):
        """Pull a click to the nearest LOCAL TURNING MAXIMUM (a real corner) if one is close and
        actually sharp; return None if the click is not near a corner (-> keep it free)."""
        if not self.verts:
            return None
        best = (1e9, -1, -1)
        for li, lp in enumerate(self.verts):
            d = np.linalg.norm(lp - p, axis=1); i = int(d.argmin())
            if d[i] < best[0]:
                best = (d[i], li, i)
        dist, li, i0 = best
        if dist > GUIDE_NEAR:                            # click is out in free space -> no snap
            return None
        lp, t, n = self.verts[li], self.turns[li], len(self.verts[li])
        cand = [(i0 + dd) % n for dd in range(-GUIDE_WIN, GUIDE_WIN + 1)]
        j = max(cand, key=lambda q: t[q])
        return lp[j] if t[j] >= GUIDE_TURN else None

    def redraw(self):
        for ax in (self.axL, self.axR):
            for c in list(ax.collections):
                c.remove()
        if self.corners:
            arr = np.array(self.corners)
            self.axL.scatter(arr[:, 0], arr[:, 1], s=70, facecolors="none", edgecolors="#0c0",
                             linewidths=2.2, zorder=5)
            self.axR.scatter(arr[:, 0], arr[:, 1], s=42, facecolors="none", edgecolors="#0a0",
                             linewidths=1.4, zorder=5)
        saved = self.key() in self.ann
        done = sum(1 for f in self.files if Path(f).stem in self.ann)
        self.fig.suptitle(
            f"[{self.i+1}/{len(self.files)}]  {self.key()}   corners={len(self.corners)}"
            f"   {'[SAVED]' if saved else '(new)'}   corner-snap:{'ON' if self.snap else 'OFF'}"
            f"   (done {done}/{len(self.files)})\n"
            f"LEFT=add (snaps to nearest CORNER; free if none near)  RIGHT=remove  HOLD+drag=brush"
            f"  WHEEL=zoom f=fit  t=snap  r=proposals  n/p  s=save c=clear q=quit",
            fontsize=9, color=("#0a0" if saved else "#a00"))
        self.fig.canvas.draw_idle()

    def _apply(self, p, button):
        """Add (left) / remove (right) a corner at point p. Returns True if something changed."""
        if button == 3:                                            # REMOVE nearest within brush
            if self.corners:
                d = np.linalg.norm(np.array(self.corners) - p, axis=1)
                if d.min() <= 0.03 * self.W:
                    del self.corners[int(d.argmin())]; return True
            return False
        # ADD: with snap ON, pull the click to the nearest CORNER (local turning max, paper
        # criterion) when one is close and sharp; otherwise drop exactly where clicked so
        # interior/outside/flat points are still free.  Snap fully off with 't'.
        v = p
        if self.snap:
            c = self._snap_to_corner(p)
            if c is not None:
                v = c
        if not self.corners or min(np.hypot(v[0]-c[0], v[1]-c[1]) for c in self.corners) > 1.5:
            self.corners.append((float(v[0]), float(v[1]))); return True
        return False

    def on_click(self, ev):
        if ev.inaxes not in (self.axL, self.axR) or ev.xdata is None:
            return
        self.dragging = ev.button                                  # start brush
        if self._apply(np.array([ev.xdata, ev.ydata]), ev.button):
            self.redraw()

    def on_motion(self, ev):                                       # BRUSH: button held + move
        if self.dragging is None or ev.inaxes not in (self.axL, self.axR) or ev.xdata is None:
            return
        if self._apply(np.array([ev.xdata, ev.ydata]), self.dragging):
            self.redraw()

    def on_release(self, ev):
        self.dragging = None

    def on_scroll(self, ev):
        if ev.inaxes not in (self.axL, self.axR) or ev.xdata is None:
            return
        fac = 0.8 if ev.button == "up" else 1.25
        x, y = ev.xdata, ev.ydata
        ev.inaxes.set_xlim([x + (l - x) * fac for l in ev.inaxes.get_xlim()])  # shared -> both
        ev.inaxes.set_ylim([y + (l - y) * fac for l in ev.inaxes.get_ylim()])
        self.fig.canvas.draw_idle()

    def save(self):
        self.ann[self.key()] = {"file": self.files[self.i],
                                "corners_norm": [[round(x / self.W, 4), round(y / self.H, 4)]
                                                 for x, y in self.corners]}
        OUT.write_text(json.dumps(self.ann, indent=1))

    def on_key(self, ev):
        if ev.key in ("n", " ", "right"):
            self.save(); self.i = (self.i + 1) % len(self.files); self.load()
        elif ev.key in ("p", "left"):
            self.save(); self.i = (self.i - 1) % len(self.files); self.load()
        elif ev.key == "s":
            self.save(); self.redraw()
        elif ev.key == "f":
            self.axL.set_xlim(self.full_xlim); self.axL.set_ylim(self.full_ylim); self.fig.canvas.draw_idle()
        elif ev.key == "r":
            self.corners = self._model_corners(); self.redraw()
        elif ev.key == "c":
            self.corners = []; self.redraw()
        elif ev.key == "t":
            self.snap = not self.snap; self.redraw()
        elif ev.key == "q":
            self.save(); print(f"saved {len(self.ann)} annotations -> {OUT}"); plt.close(self.fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=int, default=100, help="also queue this many diverse corpus icons")
    ap.add_argument("--gt-undone", type=int, default=50, help="how many not-yet-done GT logos to include")
    a = ap.parse_args()
    files = build_queue(a.corpus, a.gt_undone)
    ann = json.loads(OUT.read_text()) if OUT.exists() else {}
    done_n = len(files) - a.corpus - a.gt_undone
    print(f"{len(files)} queued = {max(done_n,0)} already-done GT + {a.gt_undone} fresh GT + "
          f"{a.corpus} diverse corpus icons.  Fresh work is first.  saved -> {OUT}")
    Annotator(files)
