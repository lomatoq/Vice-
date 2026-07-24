"""Open (append-only) real-locus corpus v2 - the review-queue expansion.

v1 is frozen: 300 class-balanced loci, fully reviewed, hash-bound into
every experiment report. v2 is the GROWTH corpus for the 2k-5k target
(audit S11.6): every owned challenge-pack raster that is NOT already in v1
becomes a pending_review locus.

Differences from v1, each fixing a growth hazard found in the ingest map:

- IDs are content-stable: f"{class}-{sha12}" (no positional class_index in
  the id), so adding sources NEVER reshuffles existing ids and reviews
  keyed by id survive any rebuild;
- no fixed-size validation: counts are recorded, not enforced;
- review.json is only initialized when absent - rebuilds never touch it;
- v1 sources are excluded by sha256, so the two corpora never overlap.

Serve it with:  $env:V_ICE_LOCUS_CORPUS = "<repo>/datasets/pcdc_real_loci_v2"

Usage:
  C:\\Python312\\python.exe build_locus_corpus_v2.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V1 = ROOT / "datasets" / "pcdc_real_loci_v1"
OUT = ROOT / "datasets" / "pcdc_real_loci_v2"

CATEGORY_TO_CLASS = {
    "small_text": "text",
    "ui_icons": "small_shape",
    "logos": "small_shape",
    "transparency": "layer_knockout",
    "diagrams": "stroke_diagram",
    "gradients": "gradient",
    "jpeg_dirty": "codec_detail",
}
JPEG_KINDS = {"jpeg", "jpeg-copy"}


def _aspect_class(width: int, height: int) -> str:
    """Best-effort class for unlabeled sources; the reviewer is the judge."""
    return "text" if width >= 2.4 * height else "small_shape"


def collect_sources(root: Path, out_dir: Path) -> list[dict]:
    """All owned sources: manifest rows, disk scans, problem cases, and
    ground-truth SVG renders (source_asset set -> auto-GT derivable)."""
    import io
    import sys

    sys.path.insert(0, str(ROOT))
    import resvg_py
    from PIL import Image
    from vice_compiler.locus_corpus import (
        RASTER_SUFFIXES,
        _challenge_candidates,
        _sha256,
    )

    pictures = root
    challenge = pictures / "challenge_pack"
    entries: list[dict] = []
    manifest_paths: set[str] = set()
    for candidate in _challenge_candidates():
        manifest_paths.add(str(candidate.path).lower())
        if candidate.source_kind in JPEG_KINDS:
            semantic_class = "codec_detail"
        else:
            semantic_class = CATEGORY_TO_CLASS.get(candidate.source_category)
        if semantic_class is None:
            continue
        entries.append({
            "path": candidate.path, "class": semantic_class,
            "origin": candidate.origin,
            "category": candidate.source_category,
            "kind": candidate.source_kind,
            "source_asset": candidate.source_asset,
        })
    # Disk-scan: pack rasters beyond the pack manifest (variants etc.).
    for path in sorted(challenge.rglob("*")):
        if (
            path.suffix.lower() not in RASTER_SUFFIXES
            or not path.is_file()
            or "vai" in {part.lower() for part in path.parts}
            or str(path.resolve()).lower() in manifest_paths
        ):
            continue
        category = path.relative_to(challenge).parts[0]
        semantic_class = CATEGORY_TO_CLASS.get(category)
        if semantic_class is None:
            continue
        entries.append({
            "path": path.resolve(), "class": semantic_class,
            "origin": "owned_challenge_pack_scan",
            "category": category, "kind": "disk-scan",
            "source_asset": None,
        })
    # Problem cases: every raster, class by aspect heuristic.
    problem_root = pictures / "problem cases"
    for path in sorted(problem_root.rglob("*")):
        if (
            path.suffix.lower() not in RASTER_SUFFIXES
            or not path.is_file()
            or "vai" in {part.lower() for part in path.parts}
        ):
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except OSError:
            continue
        entries.append({
            "path": path.resolve(), "class": _aspect_class(width, height),
            "origin": "user_problem_case_source",
            "category": "problem_case", "kind": "source_raster",
            "source_asset": None,
        })
    # Ground-truth SVGs: render height-160 rasters with source_asset set,
    # making every one auto-GT derivable (audit ground-truth policy).
    render_dir = out_dir / "rendered_sources"
    render_dir.mkdir(parents=True, exist_ok=True)
    gt_root = pictures / "ground truth"
    render_failures = 0
    for svg_path in sorted(gt_root.rglob("*.svg")):
        if "vai" in {part.lower() for part in svg_path.parts}:
            continue
        try:
            svg_digest = _sha256(svg_path)
            target = render_dir / f"{svg_digest[:16]}.png"
            if not target.is_file():
                rendered = resvg_py.svg_to_bytes(
                    svg_string=svg_path.read_text(
                        encoding="utf-8", errors="strict",
                    ),
                    height=160,
                )
                with Image.open(io.BytesIO(bytes(rendered))) as image:
                    image.save(target)
            with Image.open(target) as image:
                width, height = image.size
        except Exception:
            render_failures += 1
            continue
        entries.append({
            "path": target.resolve(), "class": _aspect_class(width, height),
            "origin": "owned_ground_truth_svg",
            "category": "ground_truth", "kind": "svg-render-h160",
            "source_asset": str(svg_path.resolve()),
        })
    print(f"collected {len(entries)} sources ({render_failures} SVG render failures)")
    return entries


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    from vice_compiler.locus_corpus import (
        PICTURES,
        _image_shape,
        _sha256,
    )

    v1_manifest = json.loads(
        (V1 / "manifest.json").read_text(encoding="utf-8")
    )
    v1_hashes = {row["source"]["sha256"] for row in v1_manifest["loci"]}

    rows = []
    seen: set[str] = set(v1_hashes)
    class_counters: dict[str, int] = {}
    skipped_unmapped = 0
    for entry in collect_sources(PICTURES, OUT):
        semantic_class = entry["class"]
        digest = _sha256(entry["path"])
        if digest in seen:
            continue
        seen.add(digest)
        width, height, mode, has_alpha = _image_shape(entry["path"])
        class_index = class_counters.get(semantic_class, 0)
        class_counters[semantic_class] = class_index + 1
        rows.append({
            # Content-stable id: growth never reshuffles existing ids.
            "id": f"{semantic_class}-{digest[:12]}",
            "semantic_class": semantic_class,
            "class_index": class_index,
            "source": {
                "path": str(entry["path"]),
                "sha256": digest,
                "origin": entry["origin"],
                "category": entry["category"],
                "kind": entry["kind"],
                "source_asset": entry["source_asset"],
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
        })

    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("duplicate content-stable ids (sha collision?)")

    manifest = {
        "schema": "pcdc-real-locus-corpus/v2-open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection": (
            "append-only-open: every owned challenge-pack raster not in v1; "
            "content-stable ids; counts recorded, never enforced"
        ),
        "ground_truth_policy": v1_manifest["ground_truth_policy"],
        "forbidden_sources": v1_manifest["forbidden_sources"],
        "v1_exclusion_hashes": len(v1_hashes),
        "skipped_unmapped_categories": skipped_unmapped,
        "counts": class_counters,
        "total": len(rows),
        "loci": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
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
        f"v2 corpus: {len(rows)} pending loci "
        f"(classes {class_counters}, {skipped_unmapped} unmapped skipped)"
    )
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
