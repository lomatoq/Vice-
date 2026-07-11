"""Combine the paper's immutable human GT with the reviewed multi-scale SVG extension.

The two layers remain identifiable in the manifest:
  * paper-human  -- the released human annotations, copied without reinterpretation;
  * svg-extended -- diverse icons/logos rendered from SVG, including occlusion labels.

The resulting shards use the same compact format as build_corner_dataset.py and can be
loaded by svg_corner_gt.iter_shard_examples or corner_cnn.py --svg-gt.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw

import paper_data
from build_corner_dataset import ShardWriter, _write_review
from svg_corner_gt import (
    EVENT_SHORT_SPAN,
    LABEL_OCCLUSION,
    LABEL_STRUCTURAL,
    infer_corner_events,
    iter_shard_examples,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_SVG = ROOT / "datasets" / "corner_gt_v4_svg_events"
DEFAULT_SVG_PREVIEW = ROOT / "web_preview" / "corner-dataset-v4-svg"
DEFAULT_OUT = ROOT / "datasets" / "corner_gt_v4_perceptual_events"
DEFAULT_PREVIEW = ROOT / "web_preview" / "corner-dataset-v4"


def _split(key: str) -> str:
    value = int(hashlib.sha1(key.lower().encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if value < 80 else "val" if value < 90 else "test"


def _safe(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def _paper_key(resolution: int, name: str) -> tuple[str, str]:
    if "/" in name:
        _, base = name.split("/", 1)
        base = base.removesuffix("_boundary")
        return f"small-{resolution}-{base}", f"small {resolution}px / {base}"
    return name, name


def _paper_image(resolution: int, name: str) -> Path:
    if "/" in name:
        _, base = name.split("/", 1)
        base = base.removesuffix("_boundary")
        return paper_data.ROOT / "small-res" / str(resolution) / f"{base}_image.png"
    folder = paper_data.ROOT / "decent-res" / name
    # The released archive uses both conventions, sometimes within one family.
    candidates = (folder / f"{resolution}_image.png", folder / f"{name}_{resolution}.png")
    direct = next((path for path in candidates if path.exists()), None)
    if direct is not None:
        return direct
    fallback = sorted(folder.glob(f"*_{resolution}.png"))
    return fallback[0] if fallback else candidates[0]


def _exact_labels(loop: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Restore the paper's index labels exactly (nearest is only a float-IO safeguard)."""
    labels = np.zeros(len(loop), np.uint8)
    for corner in np.asarray(corners, float).reshape(-1, 2):
        labels[int(np.argmin(np.linalg.norm(loop - corner, axis=1)))] = LABEL_STRUCTURAL
    return labels


def _paper_preview(loop: np.ndarray, padding: int = 4) -> tuple[Image.Image, np.ndarray]:
    """Render the released boundary itself instead of guessing a PNG coordinate transform.

    The archive PNGs are not in one coordinate convention: some have 5px padding, some use
    a flipped Cartesian Y axis, and filenames/canvas sizes vary.  Using one transform for both
    the filled preview and annotation points makes the review overlay exact by construction.
    """
    points = np.asarray(loop, float).copy()
    lo, hi = points.min(axis=0), points.max(axis=0)
    shown = np.empty_like(points)
    shown[:, 0] = points[:, 0] - lo[0] + padding
    shown[:, 1] = hi[1] - points[:, 1] + padding
    width = max(1, int(np.ceil(hi[0] - lo[0])) + 2 * padding + 1)
    height = max(1, int(np.ceil(hi[1] - lo[1])) + 2 * padding + 1)
    image = Image.new("RGB", (width, height), (10, 13, 18))
    ImageDraw.Draw(image).polygon([tuple(point) for point in shown], fill=(250, 250, 250))
    return image, shown


def _copy_svg_preview(source: Path, target: Path) -> list[dict]:
    manifest_path = source / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for folder in ("images", "annotations", "sources"):
        src = source / folder
        if src.exists():
            shutil.copytree(src, target / folder, dirs_exist_ok=True)
    entries = manifest.get("entries", [])
    for entry in entries:
        entry["source_layer"] = "svg-extended"
    return entries


def build(svg_dataset: Path, svg_preview: Path, out: Path, preview: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    preview.mkdir(parents=True, exist_ok=True)
    for old in out.glob("shard_*.npz"):
        old.unlink()
    writer = ShardWriter(out)
    files: list[dict] = []
    totals = Counter()
    by_source: dict[str, Counter] = defaultdict(Counter)
    by_resolution: dict[int, Counter] = defaultdict(Counter)

    paper_records: dict[str, int] = {}
    paper_entries: dict[str, dict] = {}
    (preview / "images").mkdir(parents=True, exist_ok=True)
    (preview / "annotations").mkdir(parents=True, exist_ok=True)
    (preview / "sources").mkdir(parents=True, exist_ok=True)

    # Human annotations are copied first and are never passed through the SVG heuristic.
    for loop, corners, resolution, raw_name in paper_data.paper_examples():
        family, display_name = _paper_key(resolution, raw_name)
        record_id = f"paper_{_safe(family)}"
        if family not in paper_records:
            paper_records[family] = len(files)
            image_path = _paper_image(resolution, raw_name)
            files.append({
                "id": record_id,
                "name": display_name,
                "path": str(image_path),
                "split": _split(f"paper/{family}"),
                "source_layer": "paper-human",
                "annotation": "released-human-gold",
            })
            paper_entries[family] = {
                "id": record_id, "name": f"[paper] {display_name}", "views": [],
                "loops": 0, "structural": 0, "occlusion": 0,
                "events": 0, "short_spans": 0,
                "zero_corner": False, "source_layer": "paper-human",
            }
        file_index = paper_records[family]
        labels = _exact_labels(loop, corners)
        event_ids, event_kinds = infer_corner_events(loop, labels)
        writer.add(loop, labels, file_index, resolution, 0, 0, event_ids, event_kinds)
        positive = int(np.count_nonzero(labels))
        events = len(set(event_ids[event_ids >= 0].tolist()))
        spans = len(set(event_ids[event_kinds == EVENT_SHORT_SPAN].tolist()))
        values = dict(loops=1, vertices=len(loop), structural=positive,
                      events=events, short_spans=spans)
        totals.update(values)
        by_source["paper-human"].update(values)
        by_resolution[resolution].update(values)

        image_path = _paper_image(resolution, raw_name)
        image_name = f"images/{record_id}_{resolution}.png"
        annotation_name = f"annotations/{record_id}_{resolution}.json"
        source_name = f"sources/{record_id}_{resolution}_original.png"
        shutil.copy2(image_path, preview / source_name)
        image, preview_loop = _paper_preview(loop)
        image.save(preview / image_name)
        width, height = image.size
        annotation = {
            "width": width, "height": height, "fill_from_loops": True,
            "loops": [{
                "points": np.round(preview_loop, 3).tolist(),
                "labels": [[int(index), int(label)] for index, label in enumerate(labels) if label],
                "events": [
                    [int(event_id), int(event_kinds[np.flatnonzero(event_ids == event_id)[0]]),
                     np.flatnonzero(event_ids == event_id).astype(int).tolist()]
                    for event_id in sorted(set(event_ids[event_ids >= 0].tolist()))
                ],
            }],
        }
        (preview / annotation_name).write_text(
            json.dumps(annotation, separators=(",", ":")), encoding="utf-8"
        )
        entry = paper_entries[family]
        entry["views"].append({
            "id": f"{record_id}@{resolution}", "res": resolution,
            "image": image_name, "annotation": annotation_name, "corners": positive,
            "events": events,
        })
        entry["loops"] += 1
        entry["structural"] += positive
        entry["events"] += events
        entry["short_spans"] += spans
        entry.setdefault("source", source_name)

    for entry in paper_entries.values():
        entry["views"].sort(key=lambda view: view["res"])
        entry["zero_corner"] = entry["structural"] == 0

    # Reviewed SVG labels are read through the public loader, therefore saved manual
    # corrections and rejected cards are respected before the combined shards are written.
    svg_manifest = json.loads((svg_dataset / "manifest.json").read_text(encoding="utf-8"))
    svg_files = svg_manifest["files"]
    svg_index: dict[int, int] = {}
    for loop, labels, meta in iter_shard_examples(svg_dataset):
        old_index = int(meta["file_index"])
        if old_index not in svg_index:
            old = svg_files[old_index]
            svg_index[old_index] = len(files)
            files.append({
                **old,
                "source_layer": "svg-extended",
                "annotation": "analytic-plus-review",
            })
        file_index = svg_index[old_index]
        writer.add(loop, labels, file_index, int(meta["resolution"]),
                   int(meta["region_index"]), int(meta["loop_index"]),
                   meta.get("event_ids"), meta.get("event_kinds"))
        structural = int(np.count_nonzero(labels == LABEL_STRUCTURAL))
        occlusion = int(np.count_nonzero(labels == LABEL_OCCLUSION))
        zero = int(structural + occlusion == 0)
        event_ids = np.asarray(meta["event_ids"])
        event_kinds = np.asarray(meta["event_kinds"])
        events = len(set(event_ids[event_ids >= 0].tolist()))
        spans = len(set(event_ids[event_kinds == EVENT_SHORT_SPAN].tolist()))
        values = dict(loops=1, vertices=len(loop), structural=structural,
                      occlusion=occlusion, zero_corner_loops=zero,
                      events=events, short_spans=spans)
        totals.update(values)
        by_source["svg-extended"].update(values)
        by_resolution[int(meta["resolution"])].update(values)

    writer.flush()
    totals["negative_vertices"] = totals["vertices"] - totals["structural"] - totals["occlusion"]
    summary = {
        "version": 4,
        "definition": "paper-compatible vertex GT + perceptual point/span/occlusion corner events",
        "files": len(files),
        "paper_families": len(paper_records),
        "svg_files": len(svg_index),
        **{key: int(value) for key, value in totals.items()},
        "by_source": {key: dict(value) for key, value in by_source.items()},
        "by_resolution": {str(key): dict(value) for key, value in sorted(by_resolution.items())},
    }
    manifest = {"dataset": out.name, "summary": summary, "files": files, "shards": writer.shards}
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    source_review = svg_dataset / "review.json"
    if source_review.exists():
        shutil.copy2(source_review, out / "review.json")
    svg_entries = _copy_svg_preview(svg_preview, preview)
    entries = list(paper_entries.values()) + svg_entries
    _write_review(preview, entries, summary, out.name)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-dataset", type=Path, default=DEFAULT_SVG)
    parser.add_argument("--svg-preview", type=Path, default=DEFAULT_SVG_PREVIEW)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    args = parser.parse_args()
    print(json.dumps(build(args.svg_dataset, args.svg_preview, args.out, args.preview),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
