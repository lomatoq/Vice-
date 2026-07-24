"""Build the blind, resolution-honest human subset for Experiment 3."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .atlas_renderer import RoiRenderRequest
from .experiment3_certificate_discrimination import (
    DATASET, PAIR_TYPES, REQUIRED_HUMAN_REVIEWS, build_cases,
)


PROJECT = Path(__file__).resolve().parents[1]
WEB = PROJECT / "web_preview"
ASSETS = WEB / "certificate_review_assets"
PRIVATE_MANIFEST = DATASET / "human_manifest.json"
REVIEW = DATASET / "review.json"


def _fmt(value: float) -> str:
    return f"{float(value):.5f}".rstrip("0").rstrip(".")


def _hex_color(linear: tuple[float, float, float, float]) -> tuple[str, float]:
    rgb = np.power(np.clip(np.asarray(linear[:3]), 0.0, 1.0), 1.0 / 2.2)
    value = "#" + "".join(f"{int(round(channel * 255)):02x}" for channel in rgb)
    return value, float(np.clip(linear[3], 0.0, 1.0))


def _mask_path(mask: np.ndarray) -> str:
    binary = np.asarray(mask, np.uint8)
    contours, _hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )
    rows: list[str] = []
    for contour in contours:
        points = contour.reshape(-1, 2)
        if len(points) < 3:
            continue
        rows.append(f"M{_fmt(points[0,0])},{_fmt(points[0,1])}")
        rows.extend(f"L{_fmt(x)},{_fmt(y)}" for x, y in points[1:])
        rows.append("Z")
    return " ".join(rows)


def _request_support(request: RoiRenderRequest) -> np.ndarray | None:
    if request.support_mask is None:
        return None
    mask = np.asarray(request.support_mask, bool)
    return mask if mask.shape == (64, 64) else cv2.resize(
        mask.astype(np.uint8), (64, 64), interpolation=cv2.INTER_NEAREST
    ).astype(bool)


def request_svg(request: RoiRenderRequest) -> str:
    p = request.parameter_map()
    color, opacity = _hex_color(request.color0_linear)
    style = f'fill="{color}" fill-opacity="{_fmt(opacity)}"'
    support = _request_support(request)
    kind = request.kind
    defs = ""
    if kind == "circle":
        body = (
            f'<circle cx="{_fmt(p["cx"])}" cy="{_fmt(p["cy"])}" '
            f'r="{_fmt(p["radius"])}" {style}/>'
        )
    elif kind == "jagged_circle":
        points = []
        for index in range(256):
            angle = 2.0 * math.pi * index / 256
            radius = float(p["radius"]) + float(p.get("amplitude", 0.8)) * math.sin(
                int(p.get("lobes", 12)) * angle + float(p.get("phase", 0.0))
            )
            points.append((
                float(p["cx"]) + radius * math.cos(angle),
                float(p["cy"]) + radius * math.sin(angle),
            ))
        path = "M" + " L".join(f"{_fmt(x)},{_fmt(y)}" for x, y in points) + " Z"
        body = f'<path d="{path}" {style}/>'
    elif kind == "stroke":
        body = (
            f'<line x1="{_fmt(p["x1"])}" y1="{_fmt(p["y1"])}" '
            f'x2="{_fmt(p["x2"])}" y2="{_fmt(p["y2"])}" '
            f'stroke="{color}" stroke-opacity="{_fmt(opacity)}" '
            f'stroke-width="{_fmt(p["width"])}" stroke-linecap="round"/>'
        )
    elif kind in {"gradient", "band_stack"}:
        path = _mask_path(support if support is not None else np.ones((64, 64), bool))
        color1, opacity1 = _hex_color(request.color1_linear or request.color0_linear)
        if kind == "gradient":
            stops = (
                f'<stop offset="0" stop-color="{color}" stop-opacity="{_fmt(opacity)}"/>'
                f'<stop offset="1" stop-color="{color1}" stop-opacity="{_fmt(opacity1)}"/>'
            )
        else:
            bands = max(2, int(p.get("bands", 5)))
            rows = []
            for index in range(bands):
                t = index / (bands - 1)
                rgb0 = np.asarray(request.color0_linear[:3])
                rgb1 = np.asarray((request.color1_linear or request.color0_linear)[:3])
                mixed = tuple((rgb0 * (1 - t) + rgb1 * t).tolist()) + (1.0,)
                band_color, band_opacity = _hex_color(mixed)
                lo = 0.0 if index == 0 else (index - 0.5) / (bands - 1)
                hi = 1.0 if index == bands - 1 else (index + 0.5) / (bands - 1)
                rows.append(f'<stop offset="{_fmt(lo)}" stop-color="{band_color}" stop-opacity="{_fmt(band_opacity)}"/>')
                rows.append(f'<stop offset="{_fmt(hi)}" stop-color="{band_color}" stop-opacity="{_fmt(band_opacity)}"/>')
            stops = "".join(rows)
        defs = (
            '<defs><linearGradient id="g" gradientUnits="userSpaceOnUse" '
            f'x1="{_fmt(p.get("x0",0))}" y1="{_fmt(p.get("y0",0))}" '
            f'x2="{_fmt(p.get("x1",64))}" y2="{_fmt(p.get("y1",0))}">'
            f'{stops}</linearGradient></defs>'
        )
        body = f'<path d="{path}" fill="url(#g)" fill-rule="evenodd"/>'
    elif kind == "eraser":
        body = ""
    else:
        path = _mask_path(support if support is not None else np.ones((64, 64), bool))
        body = f'<path d="{path}" {style} fill-rule="evenodd"/>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
        f'viewBox="0 0 64 64">{defs}{body}</svg>\n'
    )


def _save_source(path: Path, premultiplied_linear: np.ndarray) -> None:
    image = np.asarray(premultiplied_linear, np.float32)
    alpha = np.clip(image[..., 3:4], 0.0, 1.0)
    straight = np.where(
        alpha > 1e-8, image[..., :3] / np.maximum(alpha, 1e-8), 0.0
    )
    srgb = np.power(np.clip(straight, 0.0, 1.0), 1.0 / 2.2)
    composite = srgb * alpha + (1.0 - alpha)
    Image.fromarray(
        np.clip(composite * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGB"
    ).save(path)


def build() -> dict[str, object]:
    cases = build_cases()
    # Choose the first five stable variants of every named type without
    # sampling from the court result.
    selected = [
        case for pair_type in PAIR_TYPES
        for case in [row for row in cases if row.pair_type == pair_type][:5]
    ]
    if len(selected) != REQUIRED_HUMAN_REVIEWS:
        raise RuntimeError("human review subset size mismatch")
    ASSETS.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, case in enumerate(selected):
        correct_is_a = (index * 17 + 3) % 2 == 0
        request_a = case.correct.request if correct_is_a else case.competitor.request
        request_b = case.competitor.request if correct_is_a else case.correct.request
        stem = f"case_{index + 1:02d}"
        source_name = f"{stem}_source.png"
        a_name = f"{stem}_a.svg"; b_name = f"{stem}_b.svg"
        _save_source(ASSETS / source_name, case.observed)
        (ASSETS / a_name).write_text(request_svg(request_a), "utf-8")
        (ASSETS / b_name).write_text(request_svg(request_b), "utf-8")
        rows.append({
            "id": case.id, "pair_type": case.pair_type,
            "native_size": [64, 64],
            "a_url": f"/certificate_review_assets/{a_name}",
            "b_url": f"/certificate_review_assets/{b_name}",
            "source_url": f"/certificate_review_assets/{source_name}",
            "correct_side": "A" if correct_is_a else "B",
        })
    manifest = {
        "schema": "pcdc-certificate-human-court/v1",
        "total": len(rows), "cases": rows,
        "blind_contract": "server strips correct_side before serving UI",
    }
    DATASET.mkdir(parents=True, exist_ok=True)
    PRIVATE_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    if not REVIEW.exists():
        REVIEW.write_text(json.dumps({
            "schema": "pcdc-certificate-human-review/v1",
            "answers": {}, "complete_count": 0,
        }, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    manifest = build()
    print(json.dumps({
        "total": manifest["total"], "manifest": str(PRIVATE_MANIFEST),
        "assets": str(ASSETS), "review": str(REVIEW),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
