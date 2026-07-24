"""Uber-dataset verification queue (v3): the review the user actually does.

The v-ize train uber corpus feeds v10 training, and its REAL vector records
(iconify collections + local ground truth) are the ones that need a human
supervision pass - synthetic text/geometry are correct by construction.
This builder turns the brand/logo-class records into review loci for the
existing web_preview mask-review tool: clean height-160 render as the
raster, the owned SVG as source_asset (so alignment/GT proofs can bind).

Priority batch: local + logos + simple-icons + token-branded (~9k loci).
Grow with --collections (comma list) or --all-iconify later; ids are
content-stable so growth never reshuffles reviews.

Usage:
  C:\\Python312\\python.exe build_locus_corpus_v3_uber.py
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UBER = Path(r"C:\Users\nirrt\Toolset\v-ize train\dataset")
VECTORS = UBER / "raster_vector_pairs_full_x2" / "vectors"
OUT = ROOT / "datasets" / "pcdc_uber_verify_v3"
DEFAULT_COLLECTIONS = ("logos", "simple-icons", "token-branded")
RENDER_HEIGHT = 160


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    import resvg_py
    from PIL import Image

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collections", type=str, default=",".join(DEFAULT_COLLECTIONS),
    )
    parser.add_argument("--all-iconify", action="store_true")
    args = parser.parse_args()
    wanted = {name.strip() for name in args.collections.split(",") if name}

    render_dir = OUT / "rendered_sources"
    render_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    seen: set[str] = set()
    counters: dict[str, int] = {}
    skipped = {"missing_svg": 0, "render_failed": 0, "duplicate": 0}
    with open(UBER / "metadata" / "corpus_metadata.jsonl",
              encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            source = record.get("source")
            collection = record.get("collection")
            if source == "local":
                pass
            elif source == "iconify" and (
                args.all_iconify or collection in wanted
            ):
                pass
            else:
                continue
            record_id = str(record["id"])
            svg_path = VECTORS / (
                f"{source}-{record_id.replace(':', '-')}.svg"
            )
            if not svg_path.is_file():
                skipped["missing_svg"] += 1
                continue
            try:
                svg_digest = _file_sha256(svg_path)
                target = render_dir / f"{svg_digest[:16]}.png"
                if not target.is_file():
                    rendered = resvg_py.svg_to_bytes(
                        svg_string=svg_path.read_text(
                            encoding="utf-8", errors="strict",
                        ),
                        height=RENDER_HEIGHT,
                    )
                    with Image.open(io.BytesIO(bytes(rendered))) as image:
                        image.save(target)
                with Image.open(target) as image:
                    width, height = image.size
                    mode = image.mode
                    has_alpha = mode in {"RGBA", "LA"}
            except Exception:
                skipped["render_failed"] += 1
                continue
            digest = _file_sha256(target)
            if digest in seen:
                skipped["duplicate"] += 1
                continue
            seen.add(digest)
            semantic_class = (
                "text" if source == "local" and width >= 2.4 * height
                else "small_shape"
            )
            class_index = counters.get(semantic_class, 0)
            counters[semantic_class] = class_index + 1
            rows.append({
                "id": f"{semantic_class}-{digest[:12]}",
                "semantic_class": semantic_class,
                "class_index": class_index,
                "source": {
                    "path": str(target.resolve()),
                    "sha256": digest,
                    "origin": f"uber-{source}",
                    "category": collection or "local",
                    "kind": f"svg-render-h{RENDER_HEIGHT}",
                    "source_asset": str(svg_path.resolve()),
                    "license_scope": "local-owned-or-project-legal-source",
                    "vai_output": False,
                },
                "image": {
                    "width": width, "height": height,
                    "mode": mode, "has_alpha": has_alpha,
                },
                "machine_suggestion": {
                    "roi_xyxy": [0, 0, width, height],
                    "macro_family": semantic_class,
                    "text_line_membership": (
                        "yes" if semantic_class == "text" else "unknown"
                    ),
                },
                "annotation_status": "pending_review",
                "uber_record_id": record_id,
            })
            if len(rows) % 1000 == 0:
                print(f"prepared {len(rows)} loci...", flush=True)

    # The user's own ground truth first, then collections alphabetically:
    # review time goes to the most valuable records before anything else.
    rows.sort(key=lambda row: (
        0 if row["source"]["origin"] == "uber-local" else 1,
        row["source"]["category"], row["id"],
    ))
    manifest = {
        "schema": "pcdc-real-locus-corpus/v3-uber-verification",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection": (
            "uber-dataset supervision review: local + brand/logo iconify "
            "collections; content-stable ids; append-only growth"
        ),
        "uber_root": str(UBER),
        "collections": sorted(wanted) + (
            ["<all-iconify>"] if args.all_iconify else []
        ),
        "ground_truth_policy": (
            "source_asset is the owned SVG target of the training pair; "
            "human review confirms the record is worthy supervision "
            "(support/topology sane, not junk); machine_suggestion is "
            "never ground truth"
        ),
        "forbidden_sources": ["Vectorizer.AI outputs"],
        "counts": counters,
        "skipped": skipped,
        "total": len(rows),
        "loci": rows,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8",
    )
    review_path = OUT / "review.json"
    if not review_path.is_file():
        review_path.write_text(json.dumps({
            "schema": "pcdc-real-locus-review/v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reviews": {},
        }, indent=1), encoding="utf-8")
    print(
        f"v3 uber-verify queue: {len(rows)} pending loci "
        f"(classes {counters}, skipped {skipped})"
    )
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
