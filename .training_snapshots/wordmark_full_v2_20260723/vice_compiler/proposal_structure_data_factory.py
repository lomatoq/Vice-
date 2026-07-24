"""Proof-bound rare-family data factory for ProposalNet.

The harvested corpus contains too few stroke, gradient, layer and repeat
examples to train those query heads.  Every source produced here is generated
from a typed construction and carries that construction as immutable family
supervision; degradations alter only the observed raster, never the target.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import random

from PIL import Image, ImageFilter
import resvg_py

from .proposal_text_data_factory import _add_noise, _jpeg_roundtrip, _slug
from .proposal_data_contract import (
    RELATION_CONTRACT_SCHEMA, RELATION_TYPES, TYPED_GENERATOR_SCHEMA,
)


SEED = 20260723
FAMILIES = (
    "stroke_network", "appearance_model", "layer_relation",
    "symmetry_repeat_group",
)
BACKGROUNDS = (
    ("transparent", (0, 0, 0, 0), "#111827"),
    ("white", (255, 255, 255, 255), "#172033"),
    ("paper", (245, 244, 239, 255), "#192235"),
    ("dark", (17, 24, 39, 255), "#f8fafc"),
)
PALETTE = (
    "#ef4444", "#f59e0b", "#22c55e", "#06b6d4", "#3b82f6",
    "#8b5cf6", "#ec4899", "#111827",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stroke_svg(rng: random.Random) -> tuple[str, str]:
    prototype = rng.choice(("polyline", "network", "orbit", "dash-train"))
    width = rng.uniform(2.0, 10.0)
    dash = ""
    if prototype == "dash-train":
        dash = f' stroke-dasharray="{rng.uniform(5, 18):.2f} {rng.uniform(3, 12):.2f}"'
    if prototype == "orbit":
        geometry = (
            f'<ellipse cx="128" cy="128" rx="{rng.uniform(62, 100):.2f}" '
            f'ry="{rng.uniform(42, 92):.2f}"/>'
        )
    else:
        count = rng.randint(4, 9)
        points = " ".join(
            f"{rng.uniform(25, 231):.2f},{rng.uniform(25, 231):.2f}"
            for _ in range(count)
        )
        geometry = f'<polyline points="{points}"/>'
        if prototype == "network":
            geometry += "".join(
                f'<line x1="128" y1="128" x2="{rng.uniform(20,236):.2f}" '
                f'y2="{rng.uniform(20,236):.2f}"/>' for _ in range(3)
            )
    # Put paint directly on every primitive.  The legacy harvested-corpus
    # labeler does not resolve inherited group styles; the typed contract will
    # supersede that heuristic, but the source remains unambiguous either way.
    paint = (
        f' fill="none" stroke="currentColor" stroke-width="{width:.2f}" '
        f'stroke-linecap="{rng.choice(("round", "square"))}" '
        f'stroke-linejoin="{rng.choice(("round", "bevel"))}"{dash}'
    )
    geometry = geometry.replace("/>", f"{paint}/>")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
        f'{geometry}</svg>'
    )
    return svg, prototype


def _gradient_svg(rng: random.Random) -> tuple[str, str]:
    radial = rng.random() < 0.45
    prototype = "radial" if radial else "linear"
    colors = rng.sample(PALETTE, rng.choice((2, 3, 4)))
    stops = "".join(
        f'<stop offset="{index / (len(colors) - 1):.4f}" stop-color="{color}"/>'
        for index, color in enumerate(colors)
    )
    if radial:
        definition = (
            f'<radialGradient id="paint" cx="{rng.uniform(.3,.7):.3f}" '
            f'cy="{rng.uniform(.3,.7):.3f}" r="{rng.uniform(.45,.8):.3f}">{stops}'
            '</radialGradient>'
        )
    else:
        definition = (
            f'<linearGradient id="paint" x1="{rng.random():.3f}" y1="{rng.random():.3f}" '
            f'x2="{rng.random():.3f}" y2="{rng.random():.3f}">{stops}'
            '</linearGradient>'
        )
    if rng.random() < 0.5:
        geometry = (
            f'<rect x="{rng.uniform(20,55):.2f}" y="{rng.uniform(20,55):.2f}" '
            f'width="{rng.uniform(155,210):.2f}" height="{rng.uniform(155,210):.2f}" '
            f'rx="{rng.uniform(0,48):.2f}" fill="url(#paint)"/>'
        )
    else:
        geometry = (
            f'<ellipse cx="128" cy="128" rx="{rng.uniform(70,110):.2f}" '
            f'ry="{rng.uniform(55,108):.2f}" fill="url(#paint)"/>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
        f'<defs>{definition}</defs>{geometry}</svg>', prototype,
    )


def _layer_svg(rng: random.Random) -> tuple[str, str]:
    prototype = rng.choice(("circles", "cards", "mixed"))
    count = rng.choice((2, 2, 3))
    rows = []
    colors = rng.sample(PALETTE, count)
    for index in range(count):
        opacity = rng.uniform(0.55, 0.92)
        cx = 85 + index * (86 / max(1, count - 1)) + rng.uniform(-10, 10)
        cy = 128 + rng.uniform(-22, 22)
        if prototype == "cards" or (prototype == "mixed" and index % 2):
            rows.append(
                f'<rect x="{cx - 62:.2f}" y="{cy - 55:.2f}" width="124" '
                f'height="110" rx="{rng.uniform(6,28):.2f}" fill="{colors[index]}" '
                f'opacity="{opacity:.3f}"/>'
            )
        else:
            rows.append(
                f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rng.uniform(52,72):.2f}" '
                f'ry="{rng.uniform(48,70):.2f}" fill="{colors[index]}" '
                f'opacity="{opacity:.3f}"/>'
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
        f'{"".join(rows)}</svg>', prototype,
    )


def _repeat_svg(rng: random.Random) -> tuple[str, str]:
    prototype = rng.choice(("grid", "radial", "row", "mirror"))
    sides = rng.randint(3, 8)
    points = []
    for index in range(sides):
        angle = -math.pi / 2 + index * math.tau / sides
        radius = rng.uniform(8, 15)
        points.append(f"{math.cos(angle) * radius:.2f},{math.sin(angle) * radius:.2f}")
    symbol = f'<polygon id="unit" points="{" ".join(points)}"/>'
    uses = []
    count = 2 if prototype == "mirror" else rng.randint(4, 9)
    mirror_scale = rng.uniform(0.80, 1.25) if prototype == "mirror" else None
    for index in range(count):
        if prototype == "mirror":
            x = 82 if index == 0 else 174
            y = 128
        elif prototype == "radial":
            angle = index * math.tau / count
            x = 128 + math.cos(angle) * rng.uniform(55, 88)
            y = 128 + math.sin(angle) * rng.uniform(55, 88)
        elif prototype == "grid":
            columns = 3
            x = 55 + (index % columns) * 72
            y = 70 + (index // columns) * 68
        else:
            x = 35 + index * 186 / max(1, count - 1)
            y = 128 + rng.uniform(-8, 8)
        scale = mirror_scale if mirror_scale is not None else rng.uniform(0.80, 1.25)
        scale_x = -scale if prototype == "mirror" and index == 1 else scale
        uses.append(
            f'<use href="#unit" transform="translate({x:.2f} {y:.2f}) '
            f'scale({scale_x:.3f} {scale:.3f})"/>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
        f'<defs>{symbol}</defs><g fill="currentColor">{"".join(uses)}</g></svg>',
        prototype,
    )


_BUILDERS = {
    "stroke_network": _stroke_svg,
    "appearance_model": _gradient_svg,
    "layer_relation": _layer_svg,
    "symmetry_repeat_group": _repeat_svg,
}


def _relation_contract(family: str, prototype: str) -> dict:
    if family == "stroke_network":
        positive = ("same_group", "stroke_membership")
    elif family == "appearance_model":
        # An appearance query describes one fitted paint field.  It is not by
        # itself evidence that several object queries belong to one group.
        positive = ("same_appearance",)
    elif family == "layer_relation":
        # One layer-relation query represents the complete ordered overlap
        # group, which necessarily contains both a front and a behind role.
        positive = ("same_group", "front_of", "behind")
    elif family == "symmetry_repeat_group" and prototype == "mirror":
        positive = ("same_group", "mirror")
    elif family == "symmetry_repeat_group":
        positive = ("same_group", "repeat")
    else:
        raise ValueError(f"unsupported typed relation family: {family}")
    return {
        "schema": RELATION_CONTRACT_SCHEMA,
        "family": family,
        "positive": list(positive),
        "observable": list(RELATION_TYPES),
    }


def build_sources(*, count: int, seed: int = SEED) -> tuple[dict, ...]:
    if count < len(FAMILIES):
        raise ValueError("structure factory count must cover every family")
    rows = []
    for index in range(count):
        family = FAMILIES[index % len(FAMILIES)]
        rng = random.Random(f"{seed}|{family}|{index}")
        svg, prototype = _BUILDERS[family](rng)
        digest = hashlib.sha256(
            f"{family}|{prototype}|{index}|{svg}".encode("utf-8")
        ).hexdigest()[:16]
        rows.append({
            "id": f"structure-v2:{family}:{prototype}:{digest}",
            "source": "synthetic-structure-v2",
            "collection": "typed-structure-factory",
            "family": family, "prototype": prototype,
            "macro_family_contract": {
                "schema": TYPED_GENERATOR_SCHEMA, "families": [family],
            },
            "relation_contract": _relation_contract(family, prototype),
            "width": 256, "height": 256, "svg": svg,
        })
    return tuple(rows)


def _inject_color(svg: str, color: str) -> str:
    return svg.replace("<svg ", f'<svg color="{color}" ', 1)


def build_pair(source: dict, variant: int, out: Path, *, seed: int = SEED) -> dict:
    rng = random.Random(f"{seed}|{source['id']}|{variant}")
    size = rng.choice((64, 96, 128, 192, 256))
    scale = rng.uniform(0.50, 0.92)
    background_name, background, ink = rng.choice(BACKGROUNDS)
    shift_x = rng.randint(-max(1, size // 16), max(1, size // 16))
    shift_y = rng.randint(-max(1, size // 16), max(1, size // 16))
    rotate = rng.choice((0.0, 0.0, rng.uniform(-8.0, 8.0)))
    blur = rng.choice((0.0, 0.0, rng.uniform(0.25, 1.1)))
    noise = rng.choice((0.0, 0.0, rng.uniform(1.0, 8.0)))
    jpeg_quality = rng.choice((None, None, 94, 86, 76, 64))
    extent = max(8, int(round(size * scale)))
    payload = resvg_py.svg_to_bytes(
        svg_string=_inject_color(source["svg"], ink),
        width=extent, height=extent,
    )
    rendered = Image.open(io.BytesIO(payload)).convert("RGBA")
    if rotate:
        rendered = rendered.rotate(
            rotate, resample=Image.Resampling.BICUBIC, expand=True,
        )
    canvas = Image.new("RGBA", (size, size), background)
    canvas.alpha_composite(rendered, (
        (size - rendered.width) // 2 + shift_x,
        (size - rendered.height) // 2 + shift_y,
    ))
    if blur:
        canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    canvas = _add_noise(canvas, noise, rng)
    if jpeg_quality is not None:
        canvas = _jpeg_roundtrip(
            canvas, jpeg_quality,
            background if background[3] else (255, 255, 255, 255),
        )
    stem = _slug(source["id"])
    vector_relative = Path("vectors") / f"{stem}.svg"
    image_relative = Path("images") / str(size) / f"{stem}-v{variant}.png"
    vector = out / vector_relative
    image = out / image_relative
    vector.parent.mkdir(parents=True, exist_ok=True)
    image.parent.mkdir(parents=True, exist_ok=True)
    if not vector.exists():
        vector.write_text(source["svg"], "utf-8")
    canvas.save(image)
    return {
        "id": f"pair:{source['id']}:{variant}",
        "source_id": source["id"], "source": source["source"],
        "collection": source["collection"],
        "prototype": source["prototype"],
        "macro_family_contract": source["macro_family_contract"],
        "relation_contract": source["relation_contract"],
        "input_png": image_relative.as_posix(),
        "target_svg": vector_relative.as_posix(), "size": size,
        "augmentation": {
            "scale": round(scale, 6), "background": background_name,
            "shift_x": shift_x, "shift_y": shift_y,
            "rotate_degrees": round(rotate, 6),
            "blur_radius": round(blur, 6), "noise_sigma": round(noise, 6),
            "jpeg_quality": jpeg_quality, "renderer": "resvg-pillow/v1",
        },
    }


def generate(
    out: Path, *, source_count: int, variants: int, workers: int,
    seed: int = SEED,
) -> dict:
    sources = build_sources(count=source_count, seed=seed)
    out.mkdir(parents=True, exist_ok=True)
    source_path = out / "sources.jsonl"
    source_path.write_text("".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in sources
    ), "utf-8")
    futures = []
    pairs = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        for source in sources:
            for variant in range(max(1, variants)):
                futures.append(executor.submit(
                    build_pair, source, variant, out, seed=seed,
                ))
        for future in as_completed(futures):
            pairs.append(future.result())
    pairs.sort(key=lambda row: row["id"])
    pair_path = out / "pairs.jsonl"
    pair_path.write_text("".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in pairs
    ), "utf-8")
    report = {
        "schema": "pcdc-proposal-structure-data-factory/v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed, "source_count": len(sources), "pair_count": len(pairs),
        "variants_per_source": max(1, variants),
        "family_source_counts": {
            family: sum(row["family"] == family for row in sources)
            for family in FAMILIES
        },
        "source_rows_sha256": _sha256(source_path),
        "pair_rows_sha256": _sha256(pair_path),
        "factory_source_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "shared_augmentation_source_sha256": hashlib.sha256(
            Path(__file__).with_name("proposal_text_data_factory.py").read_bytes()
        ).hexdigest(),
        "family_contract": TYPED_GENERATOR_SCHEMA,
        "relation_contract": RELATION_CONTRACT_SCHEMA,
        "split_contract": "source-svg-and-augmentation-disjoint-required-by-trainer",
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), "utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sources", type=int, default=4000)
    parser.add_argument("--variants", type=int, default=4)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    print(json.dumps(generate(
        args.out, source_count=args.sources, variants=args.variants,
        workers=args.workers, seed=args.seed,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
