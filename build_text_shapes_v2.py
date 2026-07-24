"""text_shapes v2: the family-rich regeneration (closes the 21-family gap).

Same output schema and SVG-path pipeline as the user's proven
v-ize train/tools/build_text_shapes.py, with the one change that matters:
fonts come from the google-fonts v2 bank (~2000 families, capped at 2 faces
per family) instead of 45 Windows faces from 21 families. Records carry an
explicit `family` field so family-disjoint splits (audit S11.3) are exact,
not heuristic. The Stage-A probe saturates near ~600 families; this corpus
crosses that point with margin.

Output: v-ize train/dataset/text_shapes_v2/ (v1 untouched).

Usage:
  C:\\Python312\\python.exe build_text_shapes_v2.py --target 150000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

ROOT = Path(__file__).resolve().parent
BANK_MANIFEST = ROOT / "fonts" / "google-fonts-manifest-v2-full.json"
UBER = Path(r"C:\Users\nirrt\Toolset\v-ize train\dataset")
OUT_DIR = UBER / "text_shapes_v2"
SVG_DIR = OUT_DIR / "svg"
JSONL_PATH = OUT_DIR / "text_shapes_v2.jsonl"
SUMMARY_PATH = OUT_DIR / "summary.json"
SEED = 20260724
MAX_FACES_PER_FAMILY = 2

BASE_WORDS = """
able about access action active adapt admin advanced agent alpha analog anchor
apex archive arena arrow asset atlas audio auto azure badge balance basic beacon
beta binary black blade block bloom blue board boost box brave bridge bright
build burst cache camera canvas cargo cedar chain charm chart check cherry chip
circle city clean clear client cloud code coin color comet core craft create
crisp crown cube cursor data delta design desk detail device dial digital direct
disk domain drive echo edge editor engine event export fiber field filter fire
flash flow focus forge form frame fresh galaxy gamma garden gate gear globe graph
green grid group guide halo harbor health hero icon idea image import index input
iris ivory jade jet key kinetic label layer lens level light link logic logo loop
lotus lunar magnet map matrix media memory menu metro micro mint model module
motion native neon node nova object ocean omega orbit origin output panel path
pixel planet portal prime prism pulse quick radar radio rapid raster raven record
render repair reply report river rocket route safe scale scene scout search seed
server shadow shape sharp shift signal silver simple sky slate smart solar solid
spark sphere stack star static stream studio summit swift symbol sync table target
tempo token trace train vector vertex vivid wave white widget window wire wizard
world yellow zen zero zone
""".split()

SHORT_LABELS = [
    "AI", "API", "App", "Beta", "Cloud", "Code", "Data", "Dev", "Go", "ID",
    "Lab", "Live", "Max", "New", "OS", "Pay", "Pro", "Run", "SDK", "UI",
    "UX", "VIP", "Web", "X2", "XL", "24", "365", "2FA", "4K", "8K",
]
PUNCTUATION = list("&%$+#@.-_/!?")
DIGITS = list("0123456789")
LATIN_CHARS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")


@dataclass(frozen=True)
class FontInfo:
    name: str
    family: str
    path: Path
    chars: frozenset[int]


def slug(value: str, max_len: int = 80) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = value.strip("-") or "text"
    return value[:max_len].strip("-") or "text"


def font_chars(path: Path) -> frozenset[int]:
    chars: set[int] = set()
    try:
        font = TTFont(path, fontNumber=0, lazy=True)
        for table in font["cmap"].tables:
            chars.update(table.cmap.keys())
        font.close()
    except Exception:
        return frozenset()
    return frozenset(chars)


BASIC = frozenset(ord(c) for c in "abcdefghijklmnopqrstuvwxyz"
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def load_bank_fonts() -> list[FontInfo]:
    bank = json.loads(BANK_MANIFEST.read_text(encoding="utf-8"))
    fonts: list[FontInfo] = []
    per_family: dict[str, int] = {}
    for face in bank["faces"]:
        family = face["family"]
        if per_family.get(family, 0) >= MAX_FACES_PER_FAMILY:
            continue
        path = ROOT / face["path"]
        chars = font_chars(path)
        # Require full basic-latin coverage: text pool is latin/digit-heavy
        # and partial faces waste attempts.
        if not chars or not BASIC <= chars:
            continue
        per_family[family] = per_family.get(family, 0) + 1
        fonts.append(FontInfo(Path(path).stem.lower(), family, path, chars))
    if len(per_family) < 400:
        raise RuntimeError(
            f"only {len(per_family)} usable families - bank problem?"
        )
    print(f"bank fonts: {len(fonts)} faces / {len(per_family)} families",
          flush=True)
    return fonts


def all_chars_supported(text: str, font: FontInfo) -> bool:
    return all(ord(char) in font.chars for char in text if char not in "\n\r\t")


def path_d(text_path: TextPath, pad: float = 4.0):
    vertices = text_path.vertices
    if len(vertices) == 0:
        return None
    xs = vertices[:, 0]
    ys = vertices[:, 1]
    min_x, max_x = float(xs.min()), float(xs.max())
    min_y, max_y = float(ys.min()), float(ys.max())
    width = max(max_x - min_x + pad * 2, 1.0)
    height = max(max_y - min_y + pad * 2, 1.0)

    def point(x: float, y: float) -> str:
        sx = x - min_x + pad
        sy = max_y - y + pad
        return f"{sx:.2f} {sy:.2f}"

    commands = []
    for values, code in text_path.iter_segments(curves=True, simplify=False):
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
                f"C {point(values[0], values[1])} {point(values[2], values[3])} "
                f"{point(values[4], values[5])}"
            )
        elif code == MplPath.CLOSEPOLY:
            commands.append("Z")
    return " ".join(commands), width, height


def make_svg(text: str, font: FontInfo, size: int, tracking: int):
    rendered = text if tracking == 0 else (" " * tracking).join(text)
    text_path = TextPath(
        (0, 0), rendered, size=size, prop=FontProperties(fname=str(font.path)),
    )
    converted = path_d(text_path)
    if converted is None:
        return None
    d, width, height = converted
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" '
        f'height="{height:.2f}" viewBox="0 0 {width:.2f} {height:.2f}">'
        f'<path fill="currentColor" d="{d}"/></svg>'
    )
    return svg, width, height


def text_pool() -> list[tuple[str, str]]:
    pool: list[tuple[str, str]] = []
    pool.extend((word, "latin-word") for word in BASE_WORDS)
    pool.extend((label, "short-label") for label in SHORT_LABELS)
    pool.extend((char, "latin-char") for char in LATIN_CHARS)
    pool.extend((digit, "digit") for digit in DIGITS)
    pool.extend((symbol, "symbol") for symbol in PUNCTUATION)
    for left in BASE_WORDS[:90]:
        for right in BASE_WORDS[90:130:5]:
            pool.append((f"{left} {right}", "two-word"))
    for word in BASE_WORDS[:120]:
        pool.append((f"{word}{random.choice(DIGITS)}", "word-digit"))
        pool.append((f"{word}-{random.choice(SHORT_LABELS)}", "mixed-label"))
    return pool


def variants(text: str) -> list[str]:
    values = {text}
    if len(text) > 1:
        values.add(text.upper())
        values.add(text.lower())
        values.add(text.title())
    return sorted(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=150_000)
    args = parser.parse_args()

    started = time.perf_counter()
    random.seed(SEED)
    fonts = load_bank_fonts()
    pool = text_pool()
    random.shuffle(pool)
    SVG_DIR.mkdir(parents=True, exist_ok=True)

    records = 0
    seen_ids: set[str] = set()
    attempts = 0
    family_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    target_count = args.target

    with JSONL_PATH.open("w", encoding="utf-8", newline="\n") as jsonl:
        while records < target_count and attempts < target_count * 30:
            attempts += 1
            text, kind = random.choice(pool)
            text = random.choice(variants(text))
            font = random.choice(fonts)
            size = random.choice([32, 40, 48, 56, 64, 72, 84, 96])
            tracking = random.choice([0, 0, 0, 1])
            if not all_chars_supported(text, font):
                continue
            try:
                rendered = make_svg(text, font, size, tracking)
            except Exception:
                continue
            if rendered is None:
                continue
            svg, width, height = rendered
            if width < 4 or height < 4:
                continue
            key = f"{font.name}|{size}|{tracking}|{kind}|{text}"
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
            record_id = f"text-shape-v2:{font.name}:{slug(text, 36)}:{digest}"
            if record_id in seen_ids:
                continue
            seen_ids.add(record_id)
            rel_path = (
                Path("svg") / slug(font.family) /
                f"{slug(text, 36)}-{digest}.svg"
            )
            out_path = OUT_DIR / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(svg, encoding="utf-8", newline="\n")
            jsonl.write(json.dumps({
                "id": record_id,
                "source": "synthetic-text",
                "collection": "text-shapes-v2",
                "kind": kind,
                "text": text,
                "font": font.name,
                "family": font.family,
                "font_file": str(font.path),
                "font_size": size,
                "tracking_spaces": tracking,
                "width": round(width, 2),
                "height": round(height, 2),
                "svg": svg,
                "relative_path": str(rel_path).replace("\\", "/"),
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
            records += 1
            family_counts[font.family] = family_counts.get(font.family, 0) + 1
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            if records % 10000 == 0:
                print(f"generated {records}/{target_count}", flush=True)

    if records < target_count:
        raise RuntimeError(
            f"generated only {records} records after {attempts} attempts"
        )
    summary = {
        "total": records,
        "target": target_count,
        "attempts": attempts,
        "families": len(family_counts),
        "kinds": dict(sorted(kind_counts.items())),
        "seed": SEED,
        "bank_manifest": str(BANK_MANIFEST),
        "jsonl": str(JSONL_PATH),
        "svg_dir": str(SVG_DIR),
        "note": (
            "family-rich regeneration for v10 Stage A/B; all SVGs are "
            "path-based; records carry an explicit family field for "
            "family-disjoint splits"
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: summary[k] for k in
                      ("total", "families", "elapsed_seconds")}, indent=1))


if __name__ == "__main__":
    main()
