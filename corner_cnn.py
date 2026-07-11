"""Cutting-edge corner detector: a 1D convolutional network over the boundary's TURNING
sequence (Hoshyari Sec 4, but a CNN instead of a Random Forest).

Why this can beat the RF, especially at small resolutions:
  * Input is the SIGNED per-step turning dtheta of the closed boundary at several ±px windows
    (rotation-invariant; CCW-normalised).  A corner is a concentration of turning; the CNN
    learns that shape at MANY scales via dilated convolutions with a PIXEL-sized receptive
    field, so its notion of "corner" is resolution-consistent (a fixed RF window is not).
  * Circular padding respects the closed loop.
  * Per-vertex sigmoid; class-weighted BCE.
Trains on GPU (torch); reuses the corner_classifier data generators for loops + labels.
"""
from __future__ import annotations

import math
import random
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
CNN_PATH = ROOT / "models" / "corner_cnn.pt"
TURN_WINDOWS = (1, 2, 3, 5, 8, 13, 21)   # ± px windows for the input turning channels
NEIGHBORHOOD = 14
# A loop shorter than this is TILED (signal repeated k× along L) before the conv stack — exact
# for circular convolutions, and it lets the CNN see SHORT loops (small letters in wordmarks:
# 23% of human corners sit on <67-vertex loops, which capped recall at ~0.75 when skipped).
MIN_CNN_LEN = 3 * max(TURN_WINDOWS) + 4
MIN_LOOP = 10                             # absolute floor: below this a loop is a few-px blob
PAPER_LETTER_FONT = r"C:/Windows/Fonts/arial.ttf"
PAPER_LETTER_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
PAPER_LETTER_RES = (12, 16, 20, 24, 32, 48, 64, 96, 128)


def signal(loop: np.ndarray) -> np.ndarray:
    """(C, L) input: signed turning of the loop accumulated over each ±w window (radians)."""
    n = len(loop)
    chans = []
    for w in TURN_WINDOWS:
        a = loop - np.roll(loop, w, axis=0)
        b = np.roll(loop, -w, axis=0) - loop
        cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
        dot = a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1]
        chans.append(np.arctan2(cross, dot))          # signed turn in (-pi, pi]
    return np.stack(chans, axis=0).astype(np.float32)  # (C, L)


# ----------------------------------------------------------------------------- data
def _labels_for(loop, corners, snap=3.0, tol=1.0):
    y = np.zeros(len(loop), np.float32)
    pts = np.asarray(corners, float).reshape(-1, 2)
    for p in pts:
        d = np.linalg.norm(loop - p, axis=1)
        i = int(np.argmin(d))
        if d[i] <= snap:
            y[i] = 1.0
            y[d <= tol] = 1.0
    return y


def gather(n_shapes: int, n_corpus: int, n_text: int, n_neg: int, seed: int = 0, human_repeat: int = 0,
           paper_repeat: int = 0, svg_gt: str | list[str] | tuple[str, ...] | None = None,
           svg_gt_repeat: int = 1,
           paper_letters: int = 0, text_corpus: int = 0):
    """Return a list of (signal (C,L), labels (L,)) training examples from the same sources
    the RF uses: synthetic shapes (known corners), corpus icons + text (structural path
    corners, resolution-validated), and small smooth negatives (all-zero labels)."""
    import corner_classifier as cc
    from svg_corners import svg_region_masks
    rng = random.Random(seed)
    data = []
    cur_tag = "synth"                             # source tag: enables cached ablations /
                                                  # honest held-out training without re-gather

    def add_loop(loop, corners):
        if loop is None or len(loop) < MIN_LOOP:
            return
        loop = cc._to_ccw(loop.astype(np.float64))
        sig, lab = signal(loop), _labels_for(loop, corners)
        L = len(loop)
        if L < MIN_CNN_LEN:                       # tile short loops (exact for circular convs)
            k = -(-MIN_CNN_LEN // L)
            sig, lab = np.tile(sig, (1, k)), np.tile(lab, k)
        data.append((sig, lab, cur_tag))

    def add_labeled_loop(loop, labels):
        """Add exact per-vertex labels without the legacy metric re-snapping."""
        if loop is None or len(loop) < MIN_LOOP:
            return
        loop = loop.astype(np.float64)
        labels = (np.asarray(labels) > 0).astype(np.float32)
        x, y = loop[:, 0], loop[:, 1]
        area = float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
        if area < 0:
            loop = loop[::-1]
            labels = labels[::-1].copy()
        sig = signal(loop)
        L = len(loop)
        if L < MIN_CNN_LEN:
            k = -(-MIN_CNN_LEN // L)
            sig, labels = np.tile(sig, (1, k)), np.tile(labels, k)
        data.append((sig, labels, cur_tag))

    # synthetic shapes (known corners)
    for _ in range(n_shapes):
        res = rng.choice(cc.TRAIN_RES)
        mask, corners = cc._synth_shape(rng, res)
        add_loop(cc.outer_loop(mask), corners)
    # small smooth negatives (0 corners) — draw the shape, take its loop
    cur_tag = "neg"
    for _ in range(n_neg):
        res = rng.choice([12, 16, 20, 24, 32, 40, 48, 64, 96, 128])
        mask = cc._synth_smooth_mask(rng, res)
        for loop in cc.mask_loops(mask):
            if len(loop) > 1 and np.allclose(loop[0], loop[-1]): loop = loop[:-1]
            add_loop(loop.astype(float), np.empty((0, 2)))
    # corpus icons
    if n_corpus > 0:
        cur_tag = "corpus"
        cfiles = cc._corpus_files(n_corpus, seed=7)
        for f in cfiles:
            res = rng.choice(cc.CORPUS_RES)
            try: regions = svg_region_masks(str(f), target=res)
            except Exception: continue
            for mask, corners in regions:
                for loop in cc.mask_loops(mask):
                    if len(loop) > 1 and np.allclose(loop[0], loop[-1]): loop = loop[:-1]
                    lp = cc._to_ccw(loop.astype(np.float64))
                    v = cc._validate_svg_corners(lp, corners)
                    if cc._region_too_dense(lp, v): continue
                    add_loop(loop.astype(float), v)
    # The repository already contains 150k path-clean wordmark SVGs in 45 font
    # families.  Keep this separate from --corpus: the old icon-only glob stops
    # after iconify and therefore never reached text_shapes/svg.
    if text_corpus > 0:
        cur_tag = "text-corpus"
        tfiles = cc._text_corpus_files(text_corpus, seed=17, split="train")
        ntext_files = 0
        for f in tfiles:
            res = rng.choice(cc.CORPUS_RES)
            try:
                regions = svg_region_masks(str(f), target=res)
            except Exception:
                continue
            accepted = False
            for mask, corners in regions:
                for loop in cc.mask_loops(mask):
                    if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                        loop = loop[:-1]
                    lp = cc._to_ccw(loop.astype(np.float64))
                    v = cc._validate_svg_corners(lp, corners)
                    if cc._region_too_dense(lp, v):
                        continue
                    add_loop(loop.astype(float), v)
                    accepted = True
            ntext_files += int(accepted)
        print(f"text-corpus: {ntext_files}/{len(tfiles)} SVGs accepted from text_shapes/svg", flush=True)
    # Exact SVG C0/occlusion ground truth produced by build_corner_dataset.py.
    # File-level splits are already fixed in its manifest; only TRAIN enters
    # gathering, so other scales of a val/test icon cannot leak into training.
    if svg_gt:
        from svg_corner_gt import iter_shard_examples
        ngt = 0
        roots = [svg_gt] if isinstance(svg_gt, (str, Path)) else list(svg_gt)
        for gt_root in roots:
            dataset_tag = Path(gt_root).name
            for loop, exact_labels, meta in iter_shard_examples(gt_root, splits={"train"}):
                layer = meta.get("source_layer", "svg-extended")
                prefix = "paper" if layer == "paper-human" else "svg-gt"
                cur_tag = f"{prefix}:{dataset_tag}:{Path(meta['path']).stem}"
                for _ in range(max(1, svg_gt_repeat)):
                    before = len(data)
                    add_labeled_loop(loop, exact_labels)
                    ngt += len(data) - before
        print(f"svg-gt: {ngt} loop-instances (repeat={svg_gt_repeat})", flush=True)
    # synthetic words
    cur_tag = "text"
    for _ in range(n_text):
        out = cc._synth_text(rng, rng.choice(cc._TEXT_RES))
        if out is None: continue
        mask, corners = out
        for loop in cc.mask_loops(mask):
            if len(loop) > 1 and np.allclose(loop[0], loop[-1]): loop = loop[:-1]
            lp = cc._to_ccw(loop.astype(np.float64))
            v = cc._validate_svg_corners(lp, corners)
            if cc._region_too_dense(lp, v): continue
            add_loop(loop.astype(float), v)
    # Focused, deterministic extension of the paper-style set: every single glyph
    # in one known font, projected through all difficult tiny resolutions.  This is
    # intentionally small and exact; it improves coverage without asking a human to
    # annotate another giant logo.  Repeat controls its weight relative to the corpus.
    if paper_letters > 0 and Path(PAPER_LETTER_FONT).exists():
        nletter = 0
        for rep in range(paper_letters):
            for char in PAPER_LETTER_CHARS:
                for res in PAPER_LETTER_RES:
                    cur_tag = f"paper-letter:arial:{char}"
                    out = cc._synth_text(rng, res, text=char, font_path=PAPER_LETTER_FONT)
                    if out is None:
                        continue
                    mask, corners = out
                    for loop in cc.mask_loops(mask):
                        if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                            loop = loop[:-1]
                        lp = cc._to_ccw(loop.astype(np.float64))
                        validated = cc._validate_svg_corners(lp, corners)
                        if cc._region_too_dense(lp, validated):
                            continue
                        before = len(data)
                        add_loop(loop.astype(float), validated)
                        nletter += len(data) - before
        print(f"paper-letters: {nletter} loop-instances (repeat={paper_letters}, font=Arial)", flush=True)
    # HUMAN-annotated gold corners (normalised), projected to several resolutions & upweighted
    if human_repeat > 0 and cc.HUMAN_ANN.exists():
        import json
        ann = json.loads(cc.HUMAN_ANN.read_text()); nh = 0
        new_stems = {k for k, v in ann.items() if "corners_norm" in v}   # dedup: new-format wins
        for k, rec in ann.items():
            file = rec.get("file")
            if not file: continue
            if "corners_norm" in rec:
                norm = np.asarray(rec["corners_norm"], float).reshape(-1, 2); res_l = cc._HUMAN_PROJ_RES
            elif "corners" in rec and rec.get("W"):
                if k.split("@")[0] in new_stems: continue
                norm = np.asarray(rec["corners"], float).reshape(-1, 2) / [rec["W"], rec["H"]]
                res_l = [int(rec.get("res", 200))]
            else:
                continue
            cur_tag = f"human:{k.split('@')[0]}"     # per-logo tag -> honest held-out from cache
            for res in res_l:
                try: regions = svg_region_masks(file, target=res)
                except Exception: continue
                for mask, _ in regions:
                    H2, W2 = mask.shape
                    corners = norm * [W2, H2] if len(norm) else norm
                    for loop in cc.mask_loops(mask):
                        if len(loop) > 1 and np.allclose(loop[0], loop[-1]): loop = loop[:-1]
                        lp = loop.astype(np.float64)
                        clean = cc._clean_corners_on_loop(cc._to_ccw(lp), corners) if len(corners) else corners
                        for _ in range(human_repeat):
                            add_loop(lp, clean); nh += 1
        print(f"human: {nh} loop-instances (repeat={human_repeat})", flush=True)
    # PAPER human GT (Hoshyari 2018): boundary+corner-index examples, clean per-resolution
    # labels.  Loops shorter than the CNN receptive field are skipped by add_loop.
    if paper_repeat > 0:
        try:
            import paper_data
            npx = 0
            for loop, cxy, res, name in paper_data.paper_examples():
                cur_tag = f"paper:{name}"
                for _ in range(paper_repeat):
                    before = len(data)
                    add_loop(loop.astype(float), cxy)
                    npx += len(data) - before
            print(f"paper: {npx} loop-instances (repeat={paper_repeat})", flush=True)
        except Exception as e:
            print("paper load failed:", e, flush=True)
    rng.shuffle(data)
    return data


# ----------------------------------------------------------------------------- model
def _make_model():
    import torch
    import torch.nn as nn

    class CircConv(nn.Module):
        def __init__(self, cin, cout, k, dil):
            super().__init__()
            self.pad = (k - 1) // 2 * dil
            self.conv = nn.Conv1d(cin, cout, k, dilation=dil)
            self.bn = nn.BatchNorm1d(cout)

        def forward(self, x, lengths=None):
            import torch.nn.functional as F
            if lengths is None:
                x = F.pad(x, (self.pad, self.pad), mode="circular")
            else:
                # Exact per-example circular padding for a variable-length padded
                # batch.  Only positions < lengths[b] are consumed by the masked
                # loss / next layer; their receptive field is bit-for-bit the same
                # as running that loop alone.
                width = x.shape[-1]
                positions = torch.arange(-self.pad, width + self.pad, device=x.device)
                indexes = torch.remainder(positions[None, :], lengths[:, None])
                indexes = indexes[:, None, :].expand(-1, x.shape[1], -1)
                x = torch.gather(x, 2, indexes)
            return F.relu(self.bn(self.conv(x)))

    class CornerCNN(nn.Module):
        def __init__(self, cin=len(TURN_WINDOWS), ch=48):
            super().__init__()
            self.l1 = CircConv(cin, ch, 7, 1)
            self.l2 = CircConv(ch, ch, 7, 2)
            self.l3 = CircConv(ch, ch, 7, 4)
            self.l4 = CircConv(ch, ch, 7, 8)
            self.l5 = CircConv(ch, ch, 5, 16)
            self.head = nn.Conv1d(ch, 1, 1)

        def forward(self, x, lengths=None):
            x = self.l1(x, lengths); x = self.l2(x, lengths); x = self.l3(x, lengths)
            x = self.l4(x, lengths); x = self.l5(x, lengths)
            return self.head(x).squeeze(1)   # (B, L) logits

    return CornerCNN()


def _training_source(tag: str) -> str:
    if tag.startswith("svg-gt:primitive_corner"):
        return "primitive"
    if tag.startswith("svg-gt:") or tag.startswith("human:"):
        return "reviewed"
    if tag.startswith("text-corpus") or tag.startswith("text") or tag.startswith("paper-letter"):
        return "text"
    if tag.startswith("neg"):
        return "smooth-neg"
    if tag.startswith("synth"):
        return "synth"
    return "aux"


def _primitive_family(tag: str) -> str:
    stem = tag.rsplit(":", 1)[-1]
    head, sep, tail = stem.partition("_")
    return tail if sep and head.isdigit() else stem


def _epoch_order(data: list, rng: random.Random, balanced: bool) -> list[int]:
    """One deterministic epoch, optionally balanced hierarchically by source.

    The raw cache is 57% primitive loops and only 5% smooth negatives.  Equal
    shuffling therefore taught the first candidate to preserve nearly every turn
    but increased smooth false positives.  Source quotas keep reviewed V4 and
    smooth negatives material; primitive families are then sampled uniformly so
    zigzags cannot drown out the rarer occlusion/fan examples.
    """
    if not balanced:
        order = list(range(len(data)))
        rng.shuffle(order)
        return order
    sources: dict[str, list[int]] = {}
    primitive_families: dict[str, list[int]] = {}
    for index, item in enumerate(data):
        tag = item[2] if len(item) > 2 else "unknown"
        source = _training_source(tag)
        sources.setdefault(source, []).append(index)
        if source == "primitive":
            primitive_families.setdefault(_primitive_family(tag), []).append(index)
    policy = {"primitive": 0.30, "reviewed": 0.30, "text": 0.15,
              "smooth-neg": 0.15, "synth": 0.05, "aux": 0.05}
    available = {key: weight for key, weight in policy.items() if sources.get(key)}
    scale = sum(available.values()) or 1.0
    order: list[int] = []
    family_names = sorted(primitive_families)
    remaining = len(data)
    for position, (source, weight) in enumerate(available.items()):
        count = remaining if position == len(available) - 1 else round(len(data) * weight / scale)
        remaining -= count
        if source == "primitive" and family_names:
            for _ in range(count):
                family = rng.choice(family_names)
                order.append(rng.choice(primitive_families[family]))
        else:
            order.extend(rng.choice(sources[source]) for _ in range(count))
    rng.shuffle(order)
    return order


def _bucket_batches(data: list, order: list[int], batch_size: int,
                    rng: random.Random) -> list[list[int]]:
    buckets: dict[int, list[int]] = {}
    for index in order:
        length = int(data[index][0].shape[1])
        bucket = 1 << max(0, length - 1).bit_length()
        buckets.setdefault(bucket, []).append(index)
    batches = []
    for values in buckets.values():
        rng.shuffle(values)
        batches.extend(values[start:start + batch_size]
                       for start in range(0, len(values), batch_size))
    rng.shuffle(batches)
    return batches


def train(out_path: Path = CNN_PATH, n_shapes=3000, n_corpus=15000, n_text=5000, n_neg=6000,
          epochs=12, seed=0, human_repeat=0, paper_repeat=0, cache: str | None = None,
          exclude_tags: tuple = (), svg_gt: str | list[str] | tuple[str, ...] | None = None,
          svg_gt_repeat: int = 1,
          paper_letters: int = 0, text_corpus: int = 0,
          init_path: Path | None = None, lr: float | None = None,
          pos_weight_scale: float = 0.5, batch_size: int = 1,
          balanced_sampling: bool = False, freeze_bn: bool = False):
    import torch
    import torch.nn.functional as F
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    # Dataset CACHE: gathering re-renders ~15k corpus SVGs (~40 min) every run.  With a cache
    # file, iteration drops to seconds.  Entries carry a SOURCE TAG ("corpus", "human:<stem>",
    # "paper:<name>", ...) so ablations / honest held-out training can FILTER the cached set
    # (exclude_tags) without re-gathering.  Delete the cache after re-annotating logos.
    if cache and Path(cache).exists():
        import pickle
        print(f"loading cached dataset {cache}...", flush=True)
        data = pickle.load(open(cache, "rb"))
    else:
        print(f"gathering data (device={dev})...", flush=True)
        data = gather(n_shapes, n_corpus, n_text, n_neg, seed, human_repeat=human_repeat,
                      paper_repeat=paper_repeat, svg_gt=svg_gt, svg_gt_repeat=svg_gt_repeat,
                      paper_letters=paper_letters, text_corpus=text_corpus)
        if cache:
            import pickle
            pickle.dump(data, open(cache, "wb"), protocol=4)
            print(f"cached dataset -> {cache}", flush=True)
    if exclude_tags:
        before = len(data)
        data = [d for d in data if not any((d[2] if len(d) > 2 else "").startswith(t) for t in exclude_tags)]
        print(f"excluded tags {exclude_tags}: {before} -> {len(data)} examples", flush=True)
    pos = sum(float(d[1].sum()) for d in data); tot = sum(len(d[1]) for d in data)
    weight_order = (_epoch_order(data, random.Random(seed + 101), True)
                    if balanced_sampling else list(range(len(data))))
    effective_pos = sum(float(data[index][1].sum()) for index in weight_order)
    effective_tot = sum(len(data[index][1]) for index in weight_order)
    print(f"examples={len(data)} vertices={tot} pos_rate={pos/max(1,tot):.4f} "
          f"effective_pos_rate={effective_pos/max(1,effective_tot):.4f}", flush=True)
    # reflection augmentation: reversing a loop negates the signed turn
    model = _make_model().to(dev)
    if init_path is not None:
        checkpoint = torch.load(init_path, map_location=dev, weights_only=False)
        model.load_state_dict(checkpoint["state"])
        print(f"initialized from {init_path}", flush=True)
    effective_lr = float(lr if lr is not None else (5e-4 if init_path is not None else 2e-3))
    opt = torch.optim.Adam(model.parameters(), lr=effective_lr, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    pos_weight_value = min(30.0, effective_tot / max(1.0, effective_pos) * float(pos_weight_scale))
    pos_weight = torch.tensor([pos_weight_value], device=dev)
    print(f"positive loss weight={pos_weight_value:.4f} (scale={pos_weight_scale:.3f})", flush=True)
    rng = random.Random(1)
    for ep in range(epochs):
        model.train()
        if freeze_bn or batch_size > 1:
            for module in model.modules():
                if isinstance(module, torch.nn.BatchNorm1d):
                    module.eval()                  # retain production checkpoint statistics
        order = _epoch_order(data, rng, balanced_sampling)
        batches = _bucket_batches(data, order, max(1, batch_size), rng)
        if ep == 0:
            mix = Counter(_training_source(data[index][2] if len(data[index]) > 2 else "unknown")
                          for index in order)
            print(f"epoch source mix={dict(mix)} batches={len(batches)} batch_size={batch_size}", flush=True)
        tl = 0.0; nb = 0
        for batch in batches:
            rows = []
            for idx in batch:
                sig, lab = data[idx][0], data[idx][1]
                if rng.random() < 0.5:              # reflect: reverse + negate turn
                    sig = -sig[:, ::-1].copy(); lab = lab[::-1].copy()
                rows.append((np.ascontiguousarray(sig), np.ascontiguousarray(lab)))
            lengths_np = np.asarray([row[0].shape[1] for row in rows], np.int64)
            width = int(lengths_np.max())
            x_np = np.zeros((len(rows), rows[0][0].shape[0], width), np.float32)
            y_np = np.zeros((len(rows), width), np.float32)
            mask_np = np.zeros((len(rows), width), np.float32)
            for bi, (sig, lab) in enumerate(rows):
                length = sig.shape[1]
                x_np[bi, :, :length] = sig
                y_np[bi, :length] = lab
                mask_np[bi, :length] = 1.0
            x = torch.from_numpy(x_np).to(dev)
            y = torch.from_numpy(y_np).to(dev)
            mask = torch.from_numpy(mask_np).to(dev)
            lengths = torch.from_numpy(lengths_np).to(dev)
            logit = model(x, lengths=lengths)
            raw = F.binary_cross_entropy_with_logits(logit, y, pos_weight=pos_weight, reduction="none")
            loss = ((raw * mask).sum(dim=1) / lengths.float()).mean()
            opt.zero_grad(); loss.backward(); opt.step()
            tl += float(loss); nb += 1
        sched.step()
        print(f"epoch {ep+1}/{epochs} loss={tl/max(1,nb):.4f}", flush=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tag_counts = Counter((d[2] if len(d) > 2 else "unknown").split(":", 1)[0] for d in data)
    config = {
        "n_shapes": n_shapes, "n_corpus": n_corpus, "n_text": n_text, "n_neg": n_neg,
        "epochs": epochs, "seed": seed, "human_repeat": human_repeat,
        "paper_repeat": paper_repeat, "paper_letters": paper_letters,
        "text_corpus": text_corpus,
        "svg_gt": ([str(svg_gt)] if isinstance(svg_gt, (str, Path)) else
                   [str(value) for value in svg_gt] if svg_gt else []),
        "svg_gt_repeat": svg_gt_repeat,
        "exclude_tags": list(exclude_tags), "init_path": str(init_path) if init_path else None,
        "lr": effective_lr, "pos_weight_scale": float(pos_weight_scale),
        "batch_size": int(batch_size), "balanced_sampling": bool(balanced_sampling),
        "freeze_bn": bool(freeze_bn or batch_size > 1),
    }
    torch.save({"state": model.state_dict(), "windows": TURN_WINDOWS,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "config": config, "tag_counts": dict(tag_counts),
                "examples": len(data), "vertices": int(tot),
                "pos_rate": pos / max(1, tot)}, out_path)
    print(f"saved {out_path}", flush=True)
    return {"path": str(out_path), "examples": len(data), "pos_rate": pos / max(1, tot)}


# ----------------------------------------------------------------------------- inference
_MODELS: dict[str, tuple] = {}


def _load(model_path: Path | str | None = None):
    path = Path(model_path or CNN_PATH).resolve()
    key = str(path)
    if key not in _MODELS:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        m = _make_model().to(dev)
        m.load_state_dict(torch.load(path, map_location=dev, weights_only=False)["state"])
        m.eval()
        _MODELS[key] = (m, dev)
    return _MODELS[key]


def predict_prob(loop: np.ndarray, model_path: Path | str | None = None) -> np.ndarray:
    import torch
    m, dev = _load(model_path)
    # Normalize winding to CCW exactly like training (gather -> cc._to_ccw): hole loops arrive
    # CW from mask_loops, which INVERTS the signed turning signal — out-of-domain for the model
    # (residual cap false-positives on e.g. spotify's bar holes).  Map probs back afterwards.
    x, y = loop[:, 0], loop[:, 1]
    area = float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    rev = area < 0
    if rev:
        loop = loop[::-1]
    sig = signal(loop)
    L, k = sig.shape[1], 1
    if L < MIN_CNN_LEN:                           # tile short loops (exact for circular convs)
        k = -(-MIN_CNN_LEN // L)
        sig = np.tile(sig, (1, k))
    with torch.no_grad():
        x = torch.from_numpy(sig).unsqueeze(0).to(dev)
        p = torch.sigmoid(m(x)).squeeze(0).cpu().numpy()
    if k > 1:
        p = p.reshape(k, L).mean(axis=0)          # copies are equivalent by symmetry
    return p[::-1].copy() if rev else p           # back to the caller's vertex order


def predict_corners(loop: np.ndarray, threshold: float = 0.5, nms_px: float = 2.5,
                    model_path: Path | str | None = None) -> np.ndarray:
    """Boolean per-vertex corner mask: prob>=threshold with greedy NMS by probability."""
    n = len(loop)
    if n < MIN_LOOP:
        return np.zeros(n, bool)
    prob = predict_prob(loop.astype(np.float64), model_path=model_path)
    order = np.argsort(-prob)
    chosen = []
    out = np.zeros(n, bool)
    for i in order:
        if prob[i] < threshold:
            break
        if all(np.hypot(*(loop[i] - loop[c])) >= nms_px for c in chosen):
            chosen.append(int(i))
    out[chosen] = True
    return out


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--corpus", type=int, default=15000)
    ap.add_argument("--text", type=int, default=5000)
    ap.add_argument("--text-corpus", type=int, default=0,
                    help="sample this many SVGs from dataset/text_shapes/svg (45 font families)")
    ap.add_argument("--shapes", type=int, default=3000)
    ap.add_argument("--neg", type=int, default=6000)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--out", type=Path, default=CNN_PATH, help="checkpoint output path")
    ap.add_argument("--init", type=Path, default=None, help="optional checkpoint to fine-tune")
    ap.add_argument("--lr", type=float, default=None, help="learning rate (default 5e-4 for fine-tune)")
    ap.add_argument("--pos-weight-scale", type=float, default=0.5,
                    help="positive BCE weight multiplier relative to inverse positive rate")
    ap.add_argument("--batch-size", type=int, default=1,
                    help="length-bucketed variable-loop batch size")
    ap.add_argument("--balanced-sampling", action="store_true",
                    help="balance primitive/reviewed/text/smooth-negative sources each epoch")
    ap.add_argument("--freeze-bn", action="store_true",
                    help="freeze BatchNorm running statistics during fine-tuning")
    ap.add_argument("--human", type=int, default=0, help="upweight (repeat Nx) human-annotated corners")
    ap.add_argument("--paper", type=int, default=0, help="upweight (repeat Nx) the Hoshyari 2018 paper GT")
    ap.add_argument("--svg-gt", type=str, action="append", default=None,
                    help="dataset made by build_corner_dataset.py; repeat to combine reviewed and generated sets")
    ap.add_argument("--svg-gt-repeat", type=int, default=1,
                    help="repeat exact SVG-GT loops this many times")
    ap.add_argument("--paper-letters", type=int, default=0,
                    help="repeat deterministic Arial single-glyph bank at 12..128px")
    ap.add_argument("--cache", type=str, default=None,
                    help="dataset cache file: load if exists, else gather+save (delete after re-annotating)")
    ap.add_argument("--exclude", type=str, default="",
                    help="comma-separated tag prefixes to drop from the cached set, e.g. 'human:x,corpus'")
    a = ap.parse_args()
    if a.train:
        print(json.dumps(train(out_path=a.out, n_shapes=a.shapes, n_corpus=a.corpus, n_text=a.text, n_neg=a.neg,
                               epochs=a.epochs, human_repeat=a.human, paper_repeat=a.paper,
                               cache=a.cache, exclude_tags=tuple(t for t in a.exclude.split(",") if t),
                               svg_gt=a.svg_gt, svg_gt_repeat=a.svg_gt_repeat,
                               paper_letters=a.paper_letters, text_corpus=a.text_corpus,
                               init_path=a.init, lr=a.lr, pos_weight_scale=a.pos_weight_scale,
                               batch_size=a.batch_size, balanced_sampling=a.balanced_sampling,
                               freeze_bn=a.freeze_bn)))
