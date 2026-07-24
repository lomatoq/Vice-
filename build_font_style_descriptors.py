"""Style-descriptor bank for template retrieval (v9.5 lane groundwork).

For every face in the licensed google-fonts bank, renders a probe string and
measures cheap geometric style features. The bank powers approximate
font/template retrieval (audit S9.1 step 2 / S8.6): given a degraded line,
retrieve the top-K nearest faces by style before layout fitting.

Features per face (all resolution-normalized):
- stroke_width_norm   2 x median distance-transform over ink / cap height
- stroke_contrast     p90/p10 of the distance transform (thick/thin modulation)
- density             ink fraction of the probe bbox
- slant               ink second-moment shear mu11/mu02
- x_height_ratio      lowercase x height / uppercase H height
- width_ratio         probe advance width / cap height

Output: benchmarks/pcdc_pre_v14/font_style_descriptors.json, keyed by face
sha256, bound to the font-manifest content hash.

Usage:
  C:\\Python312\\python.exe build_font_style_descriptors.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "benchmarks" / "pcdc_pre_v14" / "font_style_descriptors.json"
PROBE = "Handgs024xHOo"
FONT_SIZE = 128


def _render(font: ImageFont.FreeTypeFont, text: str) -> np.ndarray | None:
    bounds = font.getbbox(text)
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return None
    pad = 8
    canvas = Image.new(
        "L", (bounds[2] - bounds[0] + 2 * pad, bounds[3] - bounds[1] + 2 * pad), 0,
    )
    ImageDraw.Draw(canvas).text(
        (pad - bounds[0], pad - bounds[1]), text, font=font, fill=255,
    )
    alpha = np.asarray(canvas, np.uint8)
    if not np.any(alpha):
        return None
    ys, xs = np.nonzero(alpha)
    return alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _ink_height(font: ImageFont.FreeTypeFont, text: str) -> float | None:
    rendered = _render(font, text)
    if rendered is None:
        return None
    return float(rendered.shape[0])


def describe_face(font_path: str) -> dict[str, float] | None:
    # The full repository contains faces PIL/Raqm cannot lay out (complex
    # shaping, colour tables): a pathological face is a skipped face.
    try:
        return _describe_face_unsafe(font_path)
    except (OSError, ValueError, ZeroDivisionError):
        return None


def _describe_face_unsafe(font_path: str) -> dict[str, float] | None:
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE)
    except OSError:
        return None
    probe = _render(font, PROBE)
    if probe is None:
        return None
    mask = (probe >= 128).astype(np.uint8)
    if int(mask.sum()) < 64:
        return None
    cap_height = _ink_height(font, "H")
    x_height = _ink_height(font, "x")
    if not cap_height:
        return None
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    ink_distance = distance[mask > 0]
    moments = cv2.moments(mask, binaryImage=True)
    slant = (
        moments["mu11"] / moments["mu02"] if moments["mu02"] > 1e-6 else 0.0
    )
    return {
        "stroke_width_norm": float(
            2.0 * np.median(ink_distance) / cap_height
        ),
        "stroke_contrast": float(
            np.percentile(ink_distance, 90)
            / max(0.5, np.percentile(ink_distance, 10))
        ),
        "density": float(mask.mean()),
        "slant": float(slant),
        "x_height_ratio": float((x_height or cap_height) / cap_height),
        "width_ratio": float(probe.shape[1] / cap_height),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bank-v2", type=Path, default=None,
        help="read faces from a v2-full bank manifest instead of the "
        "attested runtime bank",
    )
    parser.add_argument(
        "--max-faces-per-family", type=int, default=4,
        help="v2 mode only: cap faces per family to keep the retrieval "
        "bank style-balanced",
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "vice_compiler"))
    sys.path.insert(0, str(ROOT))

    started = time.perf_counter()
    if args.bank_v2 is not None:
        bank = json.loads(args.bank_v2.read_text(encoding="utf-8"))
        records = []
        per_family: dict[str, int] = {}
        for face in bank["faces"]:
            count = per_family.get(face["family"], 0)
            if count >= args.max_faces_per_family:
                continue
            per_family[face["family"]] = count + 1
            records.append((
                face["family"], ROOT / face["path"], face["sha256"],
            ))
        manifest = {"content_sha256": bank["content_sha256"]}
    else:
        from vice_compiler.glyph_prior_data import load_font_records

        fonts, manifest = load_font_records(
            ROOT / "fonts" / "google-fonts-manifest.json",
            font_root=ROOT / "fonts" / "google-fonts",
        )
        records = [
            (record.family, record.path, record.sha256) for record in fonts
        ]
    faces: dict[str, dict] = {}
    skipped: list[str] = []
    for family, path, sha in records:
        features = describe_face(str(path))
        if features is None:
            skipped.append(family)
            continue
        faces[sha] = {
            "family": family,
            "path": str(Path(path).relative_to(ROOT)),
            "features": features,
        }
    feature_names = sorted(next(iter(faces.values()))["features"])
    table = np.array([
        [face["features"][name] for name in feature_names]
        for face in faces.values()
    ])
    normalization = {
        name: {
            "mean": float(table[:, column].mean()),
            "std": float(max(1e-6, table[:, column].std())),
        }
        for column, name in enumerate(feature_names)
    }
    payload = {
        "schema": "vice-font-style-descriptors/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "probe": PROBE,
        "font_size": FONT_SIZE,
        "feature_names": feature_names,
        "normalization": normalization,
        "faces": faces,
        "skipped_families": skipped,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(
        f"{len(faces)} faces described, {len(skipped)} skipped, "
        f"{payload['elapsed_seconds']:.1f}s -> {args.out}"
    )


if __name__ == "__main__":
    main()
