"""Tiny 4x de-antialiasing network trained on synthetic CAD-style clip art.

The network reconstructs a sharp, higher-resolution raster.  Vectorization is
still performed by the deterministic contour/primitive pipeline afterwards.
"""

from __future__ import annotations

import argparse
import colorsys
import io
import json
import math
import random
from pathlib import Path

import numpy as np
import cv2
from PIL import Image, ImageDraw

try:
    from skimage.color import deltaE_ciede2000
except ImportError:  # Fall back to Euclidean Lab on minimal installations.
    deltaE_ciede2000 = None

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:  # Keep the non-ML vectorizer usable without torch.
    torch = None
    nn = None
    F = None


ROOT = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = ROOT / "models" / "subpixel_mininet_4x.pt"


class ResidualBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1),
        )

    def forward(self, x):
        return x + 0.2 * self.body(x)


class MiniSubpixelNet(nn.Module):
    """Small residual CNN with two PixelShuffle stages (about 230k params)."""

    def __init__(self, channels: int = 32, blocks: int = 4) -> None:
        super().__init__()
        self.head = nn.Conv2d(3, channels, 3, padding=1)
        self.body = nn.Sequential(*[ResidualBlock(channels) for _ in range(blocks)])
        self.up1 = nn.Sequential(nn.Conv2d(channels, channels * 4, 3, padding=1), nn.PixelShuffle(2), nn.ReLU(inplace=True))
        self.up2 = nn.Sequential(nn.Conv2d(channels, channels * 4, 3, padding=1), nn.PixelShuffle(2), nn.ReLU(inplace=True))
        self.tail = nn.Sequential(
            nn.Conv2d(channels, 24, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(24, 3, 3, padding=1),
        )

    def forward(self, x):
        base = F.interpolate(x, scale_factor=4, mode="nearest")
        features = self.body(F.relu(self.head(x), inplace=True))
        delta = 0.55 * torch.tanh(self.tail(self.up2(self.up1(features))))
        return torch.clamp(base + delta, 0.0, 1.0)


def _contrast_color(rng: random.Random, others: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    for _ in range(30):
        color = tuple(rng.randint(0, 255) for _ in range(3))
        if all(np.linalg.norm(np.asarray(color, float) - np.asarray(old, float)) > 105 for old in others):
            return color
    return (rng.choice((10, 245)), rng.choice((15, 240)), rng.choice((20, 235)))


def _regular_points(cx: float, cy: float, radius: float, count: int, angle: float, inner: float | None = None):
    points = []
    steps = count if inner is None else count * 2
    for i in range(steps):
        r = radius if inner is None or i % 2 == 0 else inner
        a = angle + 2 * math.pi * i / steps
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return points


def synthetic_pair(seed: int, low_size: int = 40, scale: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Generate anti-aliased low-res input and sharp 4x CAD-style target."""
    rng = random.Random(seed)
    size = low_size * scale
    background = tuple(rng.randint(225, 255) for _ in range(3)) if rng.random() < 0.8 else _contrast_color(rng, [])
    colors = [background]
    for _ in range(rng.randint(1, 3)):
        colors.append(_contrast_color(rng, colors))
    target = Image.new("RGB", (size, size), background)
    draw = ImageDraw.Draw(target)

    for layer in range(rng.randint(1, 4)):
        color = colors[1 + layer % (len(colors) - 1)]
        margin = rng.uniform(0.07, 0.2) * size
        x0 = rng.uniform(margin, size * 0.45)
        y0 = rng.uniform(margin, size * 0.45)
        x1 = rng.uniform(size * 0.55, size - margin)
        y1 = rng.uniform(size * 0.55, size - margin)
        shape = rng.choice(("ellipse", "circle", "rect", "rounded", "stadium", "ring", "ring_segment", "polygon", "star"))
        if shape == "circle":
            side = min(x1 - x0, y1 - y0)
            x1, y1 = x0 + side, y0 + side
            draw.ellipse((x0, y0, x1, y1), fill=color)
        elif shape == "ellipse":
            draw.ellipse((x0, y0, x1, y1), fill=color)
        elif shape == "rect":
            draw.rectangle((x0, y0, x1, y1), fill=color)
        elif shape in {"rounded", "stadium"}:
            radius = min(x1 - x0, y1 - y0) * (0.5 if shape == "stadium" else rng.uniform(0.1, 0.3))
            draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=color)
        elif shape == "ring":
            draw.ellipse((x0, y0, x1, y1), fill=color)
            thickness = rng.uniform(0.12, 0.32) * min(x1 - x0, y1 - y0)
            draw.ellipse((x0 + thickness, y0 + thickness, x1 - thickness, y1 - thickness), fill=background)
        elif shape == "ring_segment":
            start = rng.randint(0, 260)
            sweep = rng.randint(60, 260)
            draw.pieslice((x0, y0, x1, y1), start=start, end=start + sweep, fill=color)
            thickness = rng.uniform(0.13, 0.3) * min(x1 - x0, y1 - y0)
            draw.ellipse((x0 + thickness, y0 + thickness, x1 - thickness, y1 - thickness), fill=background)
        else:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            radius = 0.5 * min(x1 - x0, y1 - y0)
            count = rng.randint(3, 9)
            points = _regular_points(cx, cy, radius, count, rng.random() * math.pi, radius * rng.uniform(0.35, 0.62) if shape == "star" else None)
            draw.polygon(points, fill=color)

    low = target.resize((low_size, low_size), Image.Resampling.LANCZOS)
    if rng.random() < 0.45:
        buffer = io.BytesIO()
        low.save(buffer, format="JPEG", quality=rng.randint(55, 94), subsampling=rng.choice((0, 1, 2)))
        low = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")
    low_array = np.asarray(low, dtype=np.float32) / 255.0
    if rng.random() < 0.35:
        noise = np.random.default_rng(seed).normal(0.0, rng.uniform(0.002, 0.012), low_array.shape)
        low_array = np.clip(low_array + noise, 0.0, 1.0).astype(np.float32)
    target_array = np.asarray(target, dtype=np.float32) / 255.0
    return low_array, target_array


def _batch(step: int, batch_size: int, low_size: int, device):
    pairs = [synthetic_pair(step * batch_size + i, low_size) for i in range(batch_size)]
    x = torch.from_numpy(np.stack([p[0] for p in pairs])).permute(0, 3, 1, 2).to(device)
    y = torch.from_numpy(np.stack([p[1] for p in pairs])).permute(0, 3, 1, 2).to(device)
    return x, y


def _edges(x):
    gray = x.mean(dim=1, keepdim=True)
    kx = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=x.dtype, device=x.device).view(1, 1, 3, 3) / 4
    ky = kx.transpose(2, 3)
    return torch.cat((F.conv2d(gray, kx, padding=1), F.conv2d(gray, ky, padding=1)), dim=1)


def _boundary_weight(target):
    magnitude = _edges(target).abs().sum(dim=1, keepdim=True)
    magnitude = F.max_pool2d(magnitude, 5, stride=1, padding=2).clamp(0.0, 1.0)
    return 1.0 + 7.0 * magnitude


def _weighted_l1(prediction, target):
    weight = _boundary_weight(target)
    return (torch.abs(prediction - target) * weight).sum() / (weight.sum() * target.shape[1])


def evaluate(model, device, sizes: tuple[int, ...] = (24, 32, 40, 48, 56, 64)) -> dict:
    rows = []
    model.eval()
    with torch.no_grad():
        for low_size in sizes:
            x, y = _batch(700000 + low_size * 100, 12, low_size, device)
            prediction = model(x)
            nearest = F.interpolate(x, scale_factor=4, mode="nearest")
            rows.append({
                "size": low_size,
                "validation_l1": float(F.l1_loss(prediction, y)),
                "nearest_l1": float(F.l1_loss(nearest, y)),
                "validation_boundary_l1": float(_weighted_l1(prediction, y)),
                "nearest_boundary_l1": float(_weighted_l1(nearest, y)),
                "validation_edge_l1": float(F.l1_loss(_edges(prediction), _edges(y))),
                "nearest_edge_l1": float(F.l1_loss(_edges(nearest), _edges(y))),
            })
    keys = [key for key in rows[0] if key != "size"]
    result = {key: float(np.mean([row[key] for row in rows])) for key in keys}
    result["validation_by_size"] = rows
    return result


def train(
    weights: Path = DEFAULT_WEIGHTS,
    steps: int = 1200,
    batch_size: int = 10,
    low_size: int = 40,
    initial_weights: Path | None = None,
) -> dict:
    if torch is None:
        raise RuntimeError("PyTorch is required to train MiniNet")
    torch.manual_seed(17)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MiniSubpixelNet().to(device)
    trained_steps = 0
    if initial_weights is not None:
        checkpoint = torch.load(initial_weights, map_location=device, weights_only=True)
        model.load_state_dict(checkpoint["state_dict"])
        trained_steps = int(checkpoint.get("trained_steps", 0))
    start_lr = 1e-4 if initial_weights is not None else 2e-4
    optimizer = torch.optim.AdamW(model.parameters(), lr=start_lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, steps, eta_min=1e-5)
    history = []
    model.train()
    for step in range(steps):
        current_size = low_size or (24, 32, 40, 48, 56, 64)[(step * 5 + step // 7) % 6]
        x, y = _batch(trained_steps + step + 10000, batch_size, current_size, device)
        prediction = model(x)
        pixel = _weighted_l1(prediction, y)
        edge = F.l1_loss(_edges(prediction), _edges(y))
        consistency = F.l1_loss(F.interpolate(prediction, size=x.shape[-2:], mode="area"), x)
        loss = pixel + 0.55 * edge + 0.05 * consistency
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        if step % 50 == 0 or step == steps - 1:
            row = {"step": step + 1, "loss": float(loss), "pixel": float(pixel), "edge": float(edge)}
            history.append(row)
            print(json.dumps(row), flush=True)

    metrics = evaluate(model, device)
    weights.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "scale": 4, "channels": 32, "blocks": 4, "trained_steps": trained_steps + steps, "metrics": metrics}, weights)
    report = {"weights": str(weights), "initial_weights": str(initial_weights) if initial_weights else None, "trained_steps": trained_steps + steps, "device": str(device), "parameters": sum(p.numel() for p in model.parameters()), **metrics, "history": history}
    weights.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


_MODEL_CACHE = {}


def compact_palette(image: Image.Image, colors: int = 16,
                    thick_core_veto: bool = True) -> np.ndarray:
    """Infer flat design colours without deleting small, real colour regions.

    Quantization alone confuses a narrow anti-aliasing band with a small logo
    part.  Hue-family grouping removes duplicate shades, while the thickness
    test keeps compact petals/dots and rejects one-pixel transition ribbons.
    """
    has_alpha = image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info)
    if has_alpha:
        # convert("RGB") reads garbage RGB under alpha=0 — composite on white
        # (deblur_4x's own convention) so anchors come from visible pixels only.
        rgba = image.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        canvas.alpha_composite(rgba)
        rgb = canvas.convert("RGB")
    else:
        rgb = image.convert("RGB")
    quantized = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    labels = np.asarray(quantized)
    palette = np.asarray(quantized.getpalette(), dtype=np.uint8).reshape(-1, 3)
    used, counts = np.unique(labels, return_counts=True)
    parent = {int(i): int(i) for i in used}

    def find(i):
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    for ia, a in enumerate(used):
        for b in used[ia + 1 :]:
            if np.linalg.norm(palette[int(a)].astype(float) - palette[int(b)].astype(float)) < 10:
                parent[find(int(b))] = find(int(a))
    grouped: dict[int, list[tuple[int, np.ndarray, int]]] = {}
    for label, count in zip(used, counts):
        grouped.setdefault(find(int(label)), []).append((int(label), palette[int(label)].astype(float), int(count)))
    entries = []
    for values in grouped.values():
        total = sum(count for _, _, count in values)
        mean = sum(color * count for _, color, count in values) / total
        entries.append(
            {
                "color": mean,
                "count": total,
                "labels": [label for label, _, _ in values],
                "candidates": [(color, count) for _, color, count in values],
            }
        )

    def hsv(color: np.ndarray) -> tuple[float, float, float]:
        return colorsys.rgb_to_hsv(*(color / 255.0))

    def perceptual_distance(first: np.ndarray, second: np.ndarray) -> float:
        colors = np.asarray((first, second), dtype=np.float32).reshape(1, 2, 3) / 255.0
        lab_colors = cv2.cvtColor(colors, cv2.COLOR_RGB2LAB).reshape(2, 3)
        if deltaE_ciede2000 is not None:
            return float(deltaE_ciede2000(lab_colors[0], lab_colors[1]))
        return float(np.linalg.norm(lab_colors[0] - lab_colors[1]))

    def entry_thickness(entry: dict) -> float:
        mask = np.isin(labels, entry["labels"]).astype(np.uint8)
        return float(cv2.distanceTransform(mask, cv2.DIST_L2, 3).max())

    # Merge anti-aliased shades that have the same hue.  Value is deliberately
    # ignored for saturated colours: an orange edge and orange interior belong
    # to one ink even when the edge was blended with white.
    families: list[dict] = []
    for entry in sorted(entries, key=lambda item: item["count"], reverse=True):
        eh, es, ev = hsv(entry["color"])
        for family in families:
            fh, fs, fv = hsv(family["color"])
            hue_distance = min(abs(eh - fh), 1.0 - abs(eh - fh))
            # Hue alone is insufficient: Mastercard's dark text inherits a
            # reddish JPEG tint and its overlap is a distinct nearby orange.
            # Keep large value changes and perceptibly different hues apart;
            # thin AA families are removed later by the spatial test.
            # Equal hue does not imply equal ink: logos often use a dark
            # outline and a lighter fill from the same hue family (Rumba).
            # A narrow value gate still groups antialias shades into their
            # nearest core, while preserving deliberate light/dark layers.
            same_colour = es > 0.18 and fs > 0.18 and hue_distance < 0.030 and abs(ev - fv) < 0.24
            same_neutral = es <= 0.22 and fs <= 0.22 and abs(ev - fv) < 0.20
            # RGB noise makes almost-black pixels report an arbitrary HSV hue
            # and high saturation (e.g. [0, 1, 2]).  Detect dark neutral ink
            # from channel spread instead, so its grey antialiasing does not
            # become a second set of vector regions.
            entry_dark_neutral = float(np.max(entry["color"])) < 85 and float(np.ptp(entry["color"])) < 20
            family_dark_neutral = float(np.max(family["color"])) < 85 and float(np.ptp(family["color"])) < 20
            same_dark_neutral = entry_dark_neutral and family_dark_neutral
            # Blind-pack lesson (nested_containers h140: pastel fills covering
            # 27% and 15% of the frame were swallowed by same_neutral, the
            # extractor emitted ZERO regions).  The RAG stage below already
            # holds the principle "two clusters with their own thick cores
            # remain distinct" — apply it here too: a colour-space merge of
            # two families that BOTH own a thick core and are globally
            # distinguishable (dE >= the RAG's own 3.8) is not an AA cleanup,
            # it is deleting artwork.  Dark neutrals are exempt: JPEG chroma
            # noise in the dark range routinely exceeds dE 3.8 on one ink.
            # thick_core_veto=False on q30-class inputs (post-blind lesson,
            # items 031/082: codec halos there are THICK — a 2-3px ring around
            # every shape — so 'owns a thick core' stops meaning 'deliberate
            # artwork' and the veto shipped split blades and dark rims,
            # kinks 2.6->8.7 / 0.8->6.6.  Clean and mild inputs (nested
            # pastels, q45) keep the veto and their zero-output cure.
            if thick_core_veto and (same_colour or same_neutral) and not same_dark_neutral:
                if (perceptual_distance(entry["color"], family["color"]) >= 3.8
                        and entry.setdefault("thickness", entry_thickness(entry)) >= 1.9
                        and family.setdefault("thickness", entry_thickness(family)) >= 1.9):
                    continue
            if same_colour or same_neutral or same_dark_neutral:
                total = family["count"] + entry["count"]
                family["color"] = (family["color"] * family["count"] + entry["color"] * entry["count"]) / total
                family["count"] = total
                family["labels"].extend(entry["labels"])
                family["candidates"].extend(entry["candidates"])
                family.pop("thickness", None)
                break
        else:
            families.append(dict(entry))

    def family_geometry(family: dict) -> tuple[np.ndarray, float, float]:
        mask = np.isin(labels, family["labels"]).astype(np.uint8)
        thickness = float(cv2.distanceTransform(mask, cv2.DIST_L2, 3).max())
        return mask, thickness, float(mask.mean())

    # Perceptual region-adjacency graph.  Very close colours are globally the
    # same ink.  A looser merge is allowed only across a real shared boundary
    # when at least one cluster is an edge-only AA/JPEG ribbon.  Two clusters
    # with their own thick cores remain distinct (dark outline + light fill).
    graph_kernel = np.ones((3, 3), np.uint8)

    def _hole_interior(mask: np.ndarray) -> np.ndarray:
        """Pixels enclosed by `mask` (its topological holes)."""
        inv = (mask == 0).astype(np.uint8)
        h, w = inv.shape
        border = np.concatenate((
            np.column_stack((np.zeros(w, int), np.arange(w))),
            np.column_stack((np.full(w, h - 1), np.arange(w))),
            np.column_stack((np.arange(h), np.zeros(h, int))),
            np.column_stack((np.arange(h), np.full(h, w - 1))),
        ))
        ff = np.zeros((h + 2, w + 2), np.uint8)
        for y, x in border:
            if inv[y, x] == 1:
                cv2.floodFill(inv, ff, (int(x), int(y)), 2)
                break
        return inv == 1

    def contact_tortuosity(left_mask: np.ndarray, right_mask: np.ndarray) -> float:
        """How fractal the shared boundary is.  A real two-ink boundary is a
        smooth curve: its 2px contact band has area ~= 2x its span, ratio ~1.
        A JPEG boundary between two shades of ONE ink zigzags through the
        artwork: area >> span.  Aggregated per connected contact component so
        a boundary scattered across letters is not mistaken for a long one."""
        contact = (cv2.dilate(left_mask, graph_kernel, iterations=1).astype(bool)
                   & right_mask.astype(bool)).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(contact, connectivity=8)
        area_sum, diag_sum = 0.0, 0.0
        for component in range(1, count):
            area = float(stats[component, cv2.CC_STAT_AREA])
            if area < 8:
                continue
            width = float(stats[component, cv2.CC_STAT_WIDTH])
            height = float(stats[component, cv2.CC_STAT_HEIGHT])
            area_sum += area
            diag_sum += math.hypot(width, height)
        if diag_sum <= 0:
            return 0.0
        return area_sum / (2.0 * diag_sum)

    while len(families) > 1:
        geometry = [family_geometry(family) for family in families]
        best_pair: tuple[int, int] | None = None
        best_score = float("inf")
        for left in range(len(families)):
            left_mask, left_thickness, left_share = geometry[left]
            for right in range(left + 1, len(families)):
                right_mask, right_thickness, right_share = geometry[right]
                delta_e = perceptual_distance(families[left]["color"], families[right]["color"])
                globally_indistinguishable = delta_e < 3.8
                touching = int(
                    np.count_nonzero(
                        cv2.dilate(left_mask, graph_kernel, iterations=1).astype(bool)
                        & right_mask.astype(bool)
                    )
                )
                contact_ratio = touching / max(1.0, min(float(left_mask.sum()), float(right_mask.sum())))
                left_edge_only = left_thickness < 1.45
                right_edge_only = right_thickness < 1.45
                edge_transition = (
                    touching > 0
                    and contact_ratio >= 0.10
                    and (left_edge_only or right_edge_only)
                    and delta_e < 12.0
                )
                weak_small_variant = (
                    touching > 0
                    and delta_e < 7.0
                    and min(left_share, right_share) < 0.012
                    and min(left_thickness, right_thickness) < 1.9
                )
                # Blind kink lesson (7MOJOS q30 sheet): two thick anchors of
                # ONE gradient ink fight inside the letters along a ragged
                # JPEG boundary — the fitter then chases that boundary and
                # ships the kink tail.  A real two-ink boundary is a smooth
                # curve (tortuosity ~1); JPEG shade boundaries are fractal.
                # Concentric layouts (a disc inside its ring) are exempt:
                # their contact is legitimately closed, not ragged.
                tortuous_same_ink = False
                if (touching >= 24 and delta_e < 24.0
                        and not globally_indistinguishable
                        and min(left_share, right_share) >= 0.005):
                    left_bool = left_mask.astype(bool)
                    right_bool = right_mask.astype(bool)
                    r_in_l = float(np.count_nonzero(right_bool & _hole_interior(left_mask))) / max(1.0, float(right_bool.sum()))
                    l_in_r = float(np.count_nonzero(left_bool & _hole_interior(right_mask))) / max(1.0, float(left_bool.sum()))
                    if max(r_in_l, l_in_r) < 0.85:
                        tort = contact_tortuosity(left_mask, right_mask)
                        # Post-blind measurement lesson (q30 logos 031/082/041:
                        # kinks 2.6->8.7, 0.8->6.6, 3.3->7.5): the thick-core
                        # veto stopped same_neutral from swallowing dE 14-24
                        # shade pairs, and their ragged codec boundary then ate
                        # the fitter.  A REAL two-ink boundary never reaches
                        # tortuosity 3.0 (measured: design contacts 0.9-1.6) —
                        # only block ringing does — so extreme raggedness may
                        # merge up to dE 24 while moderate stays at dE 14.
                        tortuous_same_ink = (tort >= 2.0 if delta_e < 14.0
                                             else tort >= 3.0)
                if (globally_indistinguishable or edge_transition or weak_small_variant
                        or tortuous_same_ink) and delta_e < best_score:
                    best_pair = left, right
                    best_score = delta_e
        if best_pair is None:
            break
        left, right = best_pair
        total = families[left]["count"] + families[right]["count"]
        families[left]["color"] = (
            families[left]["color"] * families[left]["count"]
            + families[right]["color"] * families[right]["count"]
        ) / total
        families[left]["count"] = total
        families[left]["labels"].extend(families[right]["labels"])
        families[left]["candidates"].extend(families[right]["candidates"])
        families.pop(right)

    anchors = []
    minimum = max(3, int(labels.size * 0.0015))
    full_lab_l = cv2.cvtColor(np.asarray(rgb, dtype=np.uint8), cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
    ring_kernel = np.ones((3, 3), np.uint8)
    for family in families:
        if family["count"] < minimum:
            continue
        mask = np.isin(labels, family["labels"]).astype(np.uint8)
        thickness = float(cv2.distanceTransform(mask, cv2.DIST_L2, 3).max())
        _, saturation, value = hsv(family["color"])
        share = family["count"] / labels.size
        # A thin low-chroma band is almost always AA/JPEG interpolation.  A
        # small but thick or strongly saturated patch is real artwork.
        # Very dark coherent ink is an important exception (small black text
        # beside a large coloured logo); deleting it caused Billabong's wordmark
        # to inherit the red symbol colour.
        dark_ink = value < 0.35 and share >= 0.001
        if share < 0.08 and thickness < 1.45 and saturation < 0.55 and not dark_ink:
            # Blind-pack lesson (nested_containers h140: 1px frames/arrows are
            # AA-diluted to value 0.435, dark_ink stays silent, the diagram's
            # whole line-work is dropped).  Mechanism, not a threshold tweak:
            # an AA/JPEG ribbon is a TRANSITION — it always lies between its
            # two neighbours' lightness values — while stroke ink is an
            # EXTREMUM, darker than practically ALL of its surroundings.  So a
            # thin family survives iff its median L* sits below the 10th
            # percentile of its ring (a halo around dark text fails this: the
            # text itself anchors the ring's P10 at black).
            component = mask.astype(bool)
            ring = cv2.dilate(mask, ring_kernel, iterations=2).astype(bool) & ~component
            if share >= 0.004 and ring.any():
                l_family = float(np.median(full_lab_l[component]))
                l_ring_low = float(np.percentile(full_lab_l[ring], 10))
                if l_family <= l_ring_low - 8.0:
                    canonical = max(
                        family["candidates"],
                        key=lambda item: item[1] * (0.35 + hsv(item[0])[1]),
                    )[0]
                    anchors.append(canonical)
                    continue
            continue
        # Use a real quantizer core instead of an average contaminated by edge
        # blends.  Saturation is a useful tie-breaker for coloured artwork.
        canonical = max(
            family["candidates"],
            key=lambda item: item[1] * (0.35 + hsv(item[0])[1]),
        )[0]
        anchors.append(canonical)
    if not anchors:
        anchors = [max(families, key=lambda item: item["count"])["color"]]
    anchors_array = np.asarray(anchors, dtype=np.float32)
    source_rgb = np.asarray(rgb, dtype=np.uint8)
    source_pixels = source_rgb.reshape(-1, 3)

    # Median-cut allocates colours by population and can completely miss a
    # tiny but perceptually essential accent (the red Lacoste mouth is 0.37%
    # of its image).  Search coherent saturated hue islands independently.
    source_hsv = cv2.cvtColor(source_rgb, cv2.COLOR_RGB2HSV)
    hue, saturation_map, value_map = [source_hsv[..., channel] for channel in range(3)]
    salient = (saturation_map >= 105) & (value_map >= 35)
    minimum_accent = max(8, int(labels.size * 0.001))
    for start in range(0, 180, 8):
        hue_mask = salient & (hue >= start) & (hue < min(180, start + 8))
        count = int(hue_mask.sum())
        if count < 20:
            continue
        components, _, stats, centroids = cv2.connectedComponentsWithStats(hue_mask.astype(np.uint8), connectivity=8)
        # Dashed accent (swimlanes red feedback line, post-blind eye-proof):
        # a dashed stroke is MANY small, similar components with regular
        # gaps — it fails the population gate (each dash is tiny) and the
        # dominant-component gate (no dash dominates) by construction.  The
        # signature is population-free: >=4 dashes of 4..80px each, sizes
        # within a 0.8 CV, nearest-neighbour gaps regular (p90 <= 2x median,
        # median gap 3..25px).  Shape of the dashed PATH is irrelevant (an
        # L-bend stays a dashed line).
        dashed = False
        areas = stats[1:, cv2.CC_STAT_AREA].astype(float)
        # clean/mild inputs only: q30 codec sparkle is ALSO many small
        # similar blobs with regular gaps (probe: item075 palette grew
        # 8 -> 11 anchors before this gate)
        if thick_core_veto and len(areas) >= 4:
            dash_sel = (areas >= 4) & (areas <= 80)
            if int(dash_sel.sum()) >= 4:
                d_areas = areas[dash_sel]
                cents = centroids[1:][dash_sel]
                if float(np.std(d_areas)) <= 0.8 * float(np.mean(d_areas)):
                    dd = np.linalg.norm(cents[:, None, :] - cents[None, :, :], axis=2)
                    np.fill_diagonal(dd, np.inf)
                    nn = np.min(dd, axis=1)
                    med_gap = float(np.median(nn))
                    if 3.0 <= med_gap <= 25.0 and float(np.percentile(nn, 90)) <= 2.0 * med_gap:
                        dashed = float(np.sum(d_areas)) >= 20.0
        if not dashed:
            if count < minimum_accent:
                continue
            if components <= 1 or int(stats[1:, cv2.CC_STAT_AREA].max()) < max(6, int(count * 0.22)):
                continue
            if float(cv2.distanceTransform(hue_mask.astype(np.uint8), cv2.DIST_L2, 3).max()) < 1.1:
                continue
        accent_pixels = source_rgb[hue_mask]
        accent_saturation = saturation_map[hue_mask]
        core = accent_pixels[accent_saturation >= np.percentile(accent_saturation, 50)]
        accent = np.median(core if len(core) else accent_pixels, axis=0).astype(np.float32)
        # Compare in real CIE Lab units.  OpenCV's uint8 Lab encoding scales
        # and offsets the channels, which made a brighter antialiased shade
        # look farther away than it is perceptually (and split one ink into
        # multiple regions).  A close hue + modest Delta-E is the same ink;
        # a genuinely different small accent, such as Lacoste red against
        # green, remains very far away and is retained.
        candidate_lab = cv2.cvtColor(
            (accent.clip(0, 255) / 255.0).astype(np.float32).reshape(1, 1, 3),
            cv2.COLOR_RGB2LAB,
        ).reshape(3)
        current_lab = cv2.cvtColor(
            (anchors_array.clip(0, 255) / 255.0).astype(np.float32).reshape(1, -1, 3),
            cv2.COLOR_RGB2LAB,
        ).reshape(-1, 3)
        delta_e = np.linalg.norm(current_lab - candidate_lab, axis=1)
        accent_h, accent_s, accent_v = hsv(accent)
        same_ink = False
        for anchor, perceptual_distance in zip(anchors_array, delta_e):
            anchor_h, anchor_s, anchor_v = hsv(anchor)
            hue_distance = min(abs(accent_h - anchor_h), 1.0 - abs(accent_h - anchor_h))
            if (
                accent_s > 0.28
                and anchor_s > 0.28
                and hue_distance < 0.025
                and perceptual_distance < 22.0
                and abs(accent_v - anchor_v) < 0.28
            ):
                same_ink = True
                break
        if not same_ink and float(delta_e.min()) >= 20.0:
            anchors_array = np.vstack((anchors_array, accent))

    spread = source_pixels.max(axis=1) - source_pixels.min(axis=1)
    neutral_dark_mask = ((source_pixels.max(axis=1) < 80) & (spread < 18)).reshape(source_rgb.shape[:2])
    neutral_dark = source_rgb[neutral_dark_mask]
    neutral_thickness = float(
        cv2.distanceTransform(neutral_dark_mask.astype(np.uint8), cv2.DIST_L2, 3).max()
    )
    # Only a coherent neutral stroke may canonicalize a dark anchor.  Sparse
    # near-black JPEG pixels around a brown logo are edge noise, not black ink.
    if len(neutral_dark) >= max(3, int(labels.size * 0.0005)) and neutral_thickness >= 1.35:
        neutral = np.median(neutral_dark, axis=0).astype(np.float32)
        nearest = int(np.argmin(np.linalg.norm(anchors_array - neutral, axis=1)))
        if float(np.linalg.norm(anchors_array[nearest] - neutral)) < 90 and float(anchors_array[nearest].max()) < 110:
            anchors_array[nearest] = neutral

    # A neutral-dashed rescue (grey chart gridlines) was probed 2026-07-14 and
    # REVERTED: the component signature never caught the 105 grid (dashes fuse
    # in pairs at chart scale) while the extra mid-grey anchor cost iou on 105
    # (-0.019) and 023 (-0.02).  Two queued lessons: dashed grids need a
    # LINE-LEVEL grouping (Hough along the row), and the probe's item106 side
    # effect (+0.066 iou from a mid-grey anchor alone!) marks a separate
    # 'mid-grey anchor rescue for diagrams' opportunity (NEXT_STRIKES).
    return anchors_array


def snap_to_palette(image: Image.Image, source: Image.Image) -> Image.Image:
    palette = compact_palette(source)
    pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
    distance = np.sum((pixels[..., None, :] - palette[None, None, :, :]) ** 2, axis=3)
    labels = np.argmin(distance, axis=2).astype(np.uint8)
    snapped = palette[labels].clip(0, 255).astype(np.uint8)
    return Image.fromarray(snapped, "RGB")


def deblur_4x(
    image: Image.Image,
    weights: Path = DEFAULT_WEIGHTS,
    device: str | None = None,
    snap_palette: bool = True,
) -> Image.Image:
    if torch is None:
        raise RuntimeError("PyTorch is required for MiniNet inference")
    if not weights.is_file():
        raise FileNotFoundError(f"MiniNet weights not found: {weights}. Run subpixel_mininet.py --train")
    target_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    key = (str(weights.resolve()), str(target_device))
    if key not in _MODEL_CACHE:
        checkpoint = torch.load(weights, map_location=target_device, weights_only=True)
        model = MiniSubpixelNet(checkpoint.get("channels", 32), checkpoint.get("blocks", 4)).to(target_device)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        _MODEL_CACHE[key] = model
    rgba = image.convert("RGBA")
    canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    canvas.alpha_composite(rgba)
    rgb = np.asarray(canvas.convert("RGB"), dtype=np.float32) / 255.0
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(target_device)
    with torch.inference_mode():
        output = _MODEL_CACHE[key](tensor)[0].permute(1, 2, 0).clamp(0, 1).cpu().numpy()
    result = Image.fromarray(np.round(output * 255).astype(np.uint8), "RGB")
    return snap_to_palette(result, image) if snap_palette else result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--size", type=int, default=40)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--init", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.train:
        print(json.dumps(train(args.weights, args.steps, args.batch_size, args.size, args.init), indent=2))
    elif args.input and args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        deblur_4x(Image.open(args.input), args.weights).save(args.output)
    else:
        parser.error("Use --train or provide --input and --output")


if __name__ == "__main__":
    main()
