"""Licensed, source-disjoint multi-row/glyph ProposalNet data factory.

The output uses the same recorded physical augmentation contract consumed by
``proposal_instance_labels``.  Every row is an explicit SVG owner group, so a
later label pass never has to guess line identity from degraded pixels.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import random
import re

from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath
import numpy as np
from PIL import Image, ImageFilter
import resvg_py

from .font_license_manifest import validate_manifest


SEED = 20260722
WORDS = tuple("""
anchor apex arcade atlas aurora beacon bloom blue bold bridge byte canvas cedar
circle cloud code comet core craft crown crystal data delta design digital echo
edge ember engine field flow forge frame fresh galaxy game glow glyph graph grid
halo harbor icon ideal iris jade layer light line logic logo loop lunar matrix
metro micro mint model motion native neon node nova orbit origin path pixel prism
pulse quantum rapid render river rocket round scene sharp signal silver sky solar
spark spectrum star studio swift symbol sync vector vertex vivid wave wire zen
""".split())
TAGLINES = tuple("""
creative systems digital studio games global interactive labs live network
original play solutions technology works
""".split())
GLYPHS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&@+#%")
BACKGROUNDS = (
    ("transparent", (0, 0, 0, 0), "#111827"),
    ("white", (255, 255, 255, 255), "#111827"),
    ("paper", (245, 244, 239, 255), "#1f2937"),
    ("dark", (17, 24, 39, 255), "#f9fafb"),
)


@dataclass(frozen=True)
class LicensedFont:
    family: str
    path: Path
    sha256: str
    license: str


def _slug(value: str, maximum: int = 60) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (result or "text")[:maximum].rstrip("-")


def _digest_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_licensed_fonts(manifest_path: Path) -> tuple[dict, tuple[LicensedFont, ...]]:
    manifest = json.loads(manifest_path.read_text("utf-8"))
    validate_manifest(manifest)
    root = Path(manifest["root"])
    fonts = tuple(LicensedFont(
        family=str(row["family"]), path=root / row["font_path"],
        sha256=str(row["font_sha256"]), license=str(row["license"]),
    ) for row in manifest["fonts"])
    return manifest, fonts


def _path_d(text: str, font: LicensedFont, size: int) -> tuple[str, float, float] | None:
    path = TextPath(
        (0, 0), text, size=size,
        prop=FontProperties(fname=str(font.path)),
    )
    vertices = path.vertices
    if not len(vertices):
        return None
    min_x = float(vertices[:, 0].min()); max_x = float(vertices[:, 0].max())
    min_y = float(vertices[:, 1].min()); max_y = float(vertices[:, 1].max())
    pad = max(2.0, size * 0.05)

    def point(x: float, y: float) -> str:
        return f"{x - min_x + pad:.3f} {max_y - y + pad:.3f}"

    commands = []
    for values, code in path.iter_segments(curves=True, simplify=False):
        if code == MplPath.MOVETO:
            commands.append(f"M {point(values[0], values[1])}")
        elif code == MplPath.LINETO:
            commands.append(f"L {point(values[0], values[1])}")
        elif code == MplPath.CURVE3:
            commands.append(
                f"Q {point(values[0], values[1])} {point(values[2], values[3])}"
            )
        elif code == MplPath.CURVE4:
            commands.append(
                "C " + " ".join((
                    point(values[0], values[1]),
                    point(values[2], values[3]),
                    point(values[4], values[5]),
                ))
            )
        elif code == MplPath.CLOSEPOLY:
            commands.append("Z")
    width = max(1.0, max_x - min_x + 2 * pad)
    height = max(1.0, max_y - min_y + 2 * pad)
    return " ".join(commands), width, height


def _text_rows(rng: random.Random, kind: str) -> tuple[str, ...]:
    if kind == "glyph-crop":
        count = rng.choice((1, 1, 2, 3))
        return ("".join(rng.choice(GLYPHS) for _ in range(count)),)
    first = rng.choice(WORDS)
    if rng.random() < 0.65:
        first = first.upper()
    second = rng.choice(TAGLINES)
    rows = [first, second]
    if kind == "three-row":
        rows.append(rng.choice(("EST. 2026", "PLAY NOW", "DIGITAL LAB", "NO. 24")))
    return tuple(rows)


def build_source_svg(
    font: LicensedFont, rows: tuple[str, ...], *, seed: int,
) -> tuple[str, tuple[str, ...], tuple[int, int]]:
    rng = random.Random(seed)
    rendered = []
    for index, text in enumerate(rows):
        size = rng.choice((34, 40, 48, 56, 64, 72, 84))
        if index:
            size = max(24, int(round(size * rng.uniform(0.45, 0.78))))
        path = _path_d(text, font, size)
        if path is None:
            raise ValueError("font produced an empty text outline")
        rendered.append((text, *path))
    width = max(row[2] for row in rendered) + 12.0
    gap = max(3.0, 0.08 * max(row[3] for row in rendered))
    height = sum(row[3] for row in rendered) + gap * (len(rendered) - 1) + 12.0
    y = 6.0
    groups = []
    owner_ids = []
    align = rng.choice(("left", "center", "center"))
    for index, (text, d, row_width, row_height) in enumerate(rendered):
        x = 6.0 if align == "left" else 0.5 * (width - row_width)
        owner_id = f"text-row-{index}"
        owner_ids.append(owner_id)
        groups.append(
            f'<g data-pcdc-owner="text-line" data-pcdc-owner-id="{owner_id}" '
            f'transform="translate({x:.3f} {y:.3f})">'
            f'<path fill="currentColor" d="{d}"/></g>'
        )
        y += row_height + gap
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
        f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}" '
        f'data-pcdc-owner-contract="explicit-groups/v1">'
        f'{"".join(groups)}</svg>'
    )
    return svg, tuple(owner_ids), (int(round(width)), int(round(height)))


def build_sources(
    fonts: tuple[LicensedFont, ...], *, count: int, seed: int = SEED,
) -> tuple[dict, ...]:
    if count <= 0 or not fonts:
        raise ValueError("source factory requires fonts and positive count")
    result = []
    per_family = max(1, int(np.ceil(count / len({font.family for font in fonts}))))
    by_family: dict[str, list[LicensedFont]] = {}
    for font in fonts:
        by_family.setdefault(font.family, []).append(font)
    for family in sorted(by_family):
        for local_index in range(per_family):
            if len(result) >= count:
                break
            rng = random.Random(f"{seed}|{family}|{local_index}")
            font = rng.choice(by_family[family])
            kind = rng.choices(
                ("two-row", "three-row", "glyph-crop"),
                weights=(0.58, 0.22, 0.20), k=1,
            )[0]
            rows = _text_rows(rng, kind)
            asset_key = f"{font.sha256}|{kind}|{'|'.join(rows)}|{local_index}"
            digest = hashlib.sha256(asset_key.encode()).hexdigest()[:16]
            svg, owner_ids, dimensions = build_source_svg(
                font, rows, seed=int(digest[:8], 16),
            )
            result.append({
                "id": f"open-text:{_slug(family)}:{digest}",
                "source": "synthetic-open-text",
                "collection": "licensed-text-compounds",
                "kind": kind, "font_family": family,
                "font_sha256": font.sha256, "font_license": font.license,
                "rows": rows, "owner_ids": owner_ids,
                "width": dimensions[0], "height": dimensions[1], "svg": svg,
            })
    return tuple(result)


def _inject_color(svg: str, color: str) -> str:
    return re.sub(r"<svg\b", f'<svg color="{color}"', svg, count=1)


def _add_noise(image: Image.Image, sigma: float, rng: random.Random) -> Image.Image:
    if sigma <= 0:
        return image
    array = np.asarray(image, np.int16).copy()
    noise = np.random.default_rng(rng.randrange(2**32)).normal(
        0.0, sigma, array[..., :3].shape,
    )
    array[..., :3] = np.clip(array[..., :3] + noise, 0, 255)
    return Image.fromarray(array.astype(np.uint8), "RGBA")


def _jpeg_roundtrip(
    image: Image.Image, quality: int, background: tuple[int, int, int, int],
) -> Image.Image:
    base = Image.new("RGBA", image.size, background)
    base.alpha_composite(image)
    buffer = io.BytesIO()
    base.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=False)
    buffer.seek(0)
    return Image.open(buffer).convert("RGBA")


def build_pair(
    source: dict, variant: int, out: Path, *, seed: int = SEED,
) -> dict:
    rng = random.Random(f"{seed}|{source['id']}|{variant}")
    size = rng.choice((64, 96, 128, 192, 256))
    scale = rng.uniform(0.48, 0.92)
    background_name, background, ink = rng.choice(BACKGROUNDS)
    shift_x = rng.randint(-max(1, size // 16), max(1, size // 16))
    shift_y = rng.randint(-max(1, size // 16), max(1, size // 16))
    rotate = rng.choice((0.0, 0.0, rng.uniform(-5.0, 5.0)))
    blur = rng.choice((0.0, 0.0, rng.uniform(0.25, 1.0)))
    noise = rng.choice((0.0, 0.0, rng.uniform(1.0, 7.0)))
    jpeg_quality = rng.choice((None, None, 94, 86, 76, 64))
    aspect = float(source["width"]) / max(1.0, float(source["height"]))
    extent = max(8, int(size * scale))
    if aspect >= 1.0:
        render_width = extent; render_height = max(1, int(extent / aspect))
    else:
        render_height = extent; render_width = max(1, int(extent * aspect))
    payload = resvg_py.svg_to_bytes(
        svg_string=_inject_color(source["svg"], ink),
        width=render_width, height=render_height,
    )
    rendered = Image.open(io.BytesIO(payload)).convert("RGBA")
    if rotate:
        rendered = rendered.rotate(
            rotate, resample=Image.Resampling.BICUBIC, expand=True,
        )
    canvas = Image.new("RGBA", (size, size), background)
    left = (size - rendered.width) // 2 + shift_x
    top = (size - rendered.height) // 2 + shift_y
    canvas.alpha_composite(rendered, (left, top))
    if blur:
        canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    canvas = _add_noise(canvas, noise, rng)
    if jpeg_quality is not None:
        jpeg_background = background if background[3] else (255, 255, 255, 255)
        canvas = _jpeg_roundtrip(canvas, jpeg_quality, jpeg_background)
    stem = _slug(source["id"])
    vector_relative = Path("vectors") / f"{stem}.svg"
    image_relative = Path("images") / str(size) / f"{stem}-v{variant}.png"
    vector = out / vector_relative; image = out / image_relative
    vector.parent.mkdir(parents=True, exist_ok=True)
    image.parent.mkdir(parents=True, exist_ok=True)
    if not vector.exists():
        vector.write_text(source["svg"], "utf-8")
    canvas.save(image)
    return {
        "id": f"pair:{source['id']}:{variant}",
        "source_id": source["id"], "source": source["source"],
        "collection": source["collection"],
        "font_family": source["font_family"],
        "font_sha256": source["font_sha256"],
        "owner_contract": {
            "schema": "explicit-svg-groups/v1",
            "owner_ids": list(source["owner_ids"]),
        },
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
    manifest_path: Path, out: Path, *, source_count: int,
    variants: int, workers: int, seed: int = SEED,
) -> dict:
    manifest, fonts = load_licensed_fonts(manifest_path)
    sources = build_sources(fonts, count=source_count, seed=seed)
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
        "schema": "pcdc-proposal-text-data-factory/v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed, "source_count": len(sources), "pair_count": len(pairs),
        "variants_per_source": max(1, variants),
        "font_manifest_sha256": manifest["content_sha256"],
        "font_family_count": len({row["font_family"] for row in sources}),
        "kind_counts": {
            kind: sum(row["kind"] == kind for row in sources)
            for kind in ("two-row", "three-row", "glyph-crop")
        },
        "source_rows_sha256": _digest_bytes(source_path),
        "pair_rows_sha256": _digest_bytes(pair_path),
        "factory_source_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "owner_contract": "explicit-svg-groups/v1",
        "split_contract": "font-family-disjoint-required-by-trainer",
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), "utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sources", type=int, default=12_000)
    parser.add_argument("--variants", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    report = generate(
        args.font_manifest, args.out, source_count=args.sources,
        variants=args.variants, workers=args.workers, seed=args.seed,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
