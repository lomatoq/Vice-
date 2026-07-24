"""Frozen local DINOv2 perceptual backend for worst-tile arbitration.

DreamSim is not installed on the benchmark host, but a stronger DINOv2-L/14
register model and its official repository are already cached.  Loading is
strictly local: this module never downloads weights during a benchmark run.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_NAME = "dinov2_vitl14_reg"
HUB_REPO = Path.home() / ".cache" / "torch" / "hub" / "facebookresearch_dinov2_main"
CHECKPOINT = Path.home() / ".cache" / "torch" / "hub" / "checkpoints" / "dinov2_vitl14_reg4_pretrain.pth"


def backend_status() -> dict:
    import torch
    return {
        "backend": "dinov2-l14-reg-local",
        "model": MODEL_NAME,
        "repo_present": HUB_REPO.is_dir(),
        "checkpoint_present": CHECKPOINT.is_file(),
        "checkpoint_bytes": CHECKPOINT.stat().st_size if CHECKPOINT.is_file() else 0,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "ready": HUB_REPO.is_dir() and CHECKPOINT.is_file(),
    }


@lru_cache(maxsize=1)
def _load_model():
    import torch
    status = backend_status()
    if not status["ready"]:
        raise RuntimeError(f"local DINOv2 backend unavailable: {status}")
    model = torch.hub.load(str(HUB_REPO), MODEL_NAME, source="local", pretrained=True)
    device = torch.device(status["device"])
    model = model.eval().to(device)
    return model, device


def embed_tiles(images: list[Image.Image], size: int = 224,
                batch_size: int = 8) -> np.ndarray:
    """Return L2-normalized embeddings for RGB tiles, in one GPU batch."""
    import torch
    import torch.nn.functional as F

    if not images:
        return np.zeros((0, 1024), np.float32)
    arrays = []
    mean = np.asarray([0.485, 0.456, 0.406], np.float32)
    std = np.asarray([0.229, 0.224, 0.225], np.float32)
    for image in images:
        arr = np.asarray(image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS),
                         np.float32) / 255.0
        arrays.append(((arr - mean) / std).transpose(2, 0, 1))
    model, device = _load_model()
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(arrays), max(1, batch_size)):
            batch = torch.from_numpy(np.stack(arrays[start:start + batch_size])).to(
                device=device, dtype=torch.float32)
            if device.type == "cuda":
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    features = model(batch)
            else:
                features = model(batch)
            outputs.append(F.normalize(features.float(), dim=1).cpu().numpy())
    return np.concatenate(outputs).astype(np.float32)


def cosine_distances(reference: list[Image.Image], candidates: list[Image.Image]) -> np.ndarray:
    """Paired cosine distances; 0 is perceptually identical in feature space."""
    if len(reference) != len(candidates):
        raise ValueError("reference and candidate tile counts differ")
    count = len(reference)
    embedded = embed_tiles(reference + candidates)
    return 1.0 - np.sum(embedded[:count] * embedded[count:], axis=1)


def worst_tile_distances(source: Image.Image, candidates: list[Image.Image],
                         window_px: int = 32, stride_px: int = 8,
                         batch_size: int = 8) -> list[dict]:
    """Max-pooled DINO distance on a shared sliding-window grid."""
    source = source.convert("RGB")
    width, height = source.size
    normalized = [candidate.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
                  for candidate in candidates]
    wh, ww = min(window_px, height), min(window_px, width)
    ys = list(range(0, max(1, height - wh + 1), max(1, stride_px)))
    xs = list(range(0, max(1, width - ww + 1), max(1, stride_px)))
    if ys[-1] != height - wh:
        ys.append(height - wh)
    if xs[-1] != width - ww:
        xs.append(width - ww)
    boxes = [(x, y, x + ww, y + wh) for y in ys for x in xs]
    source_tiles = [source.crop(box) for box in boxes]
    source_features = embed_tiles(source_tiles, batch_size=batch_size)
    reports = []
    for candidate in normalized:
        features = embed_tiles([candidate.crop(box) for box in boxes], batch_size=batch_size)
        distances = 1.0 - np.sum(source_features * features, axis=1)
        worst = int(np.argmax(distances))
        reports.append({
            "dino_tile_max": round(float(distances[worst]), 6),
            "dino_tile_p95": round(float(np.percentile(distances, 95)), 6),
            "dino_tile_x": int(boxes[worst][0] + ww // 2),
            "dino_tile_y": int(boxes[worst][1] + wh // 2),
            "dino_tile_window": [int(ww), int(wh)],
            "dino_tiles": len(boxes),
        })
    return reports


def main() -> int:
    status = backend_status()
    if not status["ready"]:
        print(json.dumps(status, indent=2))
        return 1
    plain = Image.new("RGB", (32, 32), "white")
    marked = plain.copy()
    marked.paste((0, 0, 0), (8, 8, 24, 24))
    distances = cosine_distances([plain, plain], [plain, marked])
    status["smoke_same"] = round(float(distances[0]), 6)
    status["smoke_different"] = round(float(distances[1]), 6)
    status["smoke_pass"] = bool(abs(float(distances[0])) < 1e-4
                                and float(distances[1]) > float(distances[0]) + 1e-3)
    print(json.dumps(status, indent=2))
    return 0 if status["smoke_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
