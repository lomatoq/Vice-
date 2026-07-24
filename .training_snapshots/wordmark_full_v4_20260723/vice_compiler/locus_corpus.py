"""Build the class-balanced 300-item Real Locus Corpus required by Phase 0.

Only owned/local raster sources are admitted.  Vectorizer.AI outputs are
explicitly excluded.  Machine suggestions never become human ground truth:
every new locus starts as ``pending_review`` and reviews live in a separate
file so regenerating the deterministic manifest cannot overwrite them.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


PROJECT = Path(__file__).resolve().parents[1]
PICTURES = Path(r"C:/Users/nirrt/Toolset/v-ice pictures")
CHALLENGE = PICTURES / "challenge_pack"
PROBLEM_SMALL = PICTURES / "problem cases" / "Small"
DEFAULT_OUT = PROJECT / "datasets" / "pcdc_real_loci_v1"

TARGETS: tuple[tuple[str, int], ...] = (
    ("text", 100),
    ("small_shape", 60),
    ("layer_knockout", 40),
    ("stroke_diagram", 40),
    ("gradient", 30),
    ("codec_detail", 30),
)
RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass(frozen=True)
class Candidate:
    path: Path
    origin: str
    source_category: str
    source_kind: str
    source_asset: str | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _challenge_candidates() -> list[Candidate]:
    manifest_path = CHALLENGE / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("challenge manifest must be a JSON array")
    candidates: list[Candidate] = []
    for row in payload:
        relative = Path(str(row.get("file", "")))
        path = CHALLENGE / relative
        if (
            path.suffix.lower() not in RASTER_SUFFIXES
            or not path.is_file()
            or "vai" in {part.lower() for part in relative.parts}
        ):
            continue
        candidates.append(
            Candidate(
                path=path.resolve(),
                origin="owned_challenge_pack",
                source_category=str(row.get("category", "unknown")),
                source_kind=str(row.get("kind", "unknown")),
                source_asset=(
                    str(row["source"]) if row.get("source") else None
                ),
            )
        )
    return candidates


def _problem_candidates() -> list[Candidate]:
    return [
        Candidate(
            path=path.resolve(),
            origin="user_problem_case_source",
            source_category="problem_case",
            source_kind="source_raster",
        )
        for path in sorted(PROBLEM_SMALL.glob("*_src.*"))
        if path.suffix.lower() in RASTER_SUFFIXES
    ]


def _image_shape(path: Path) -> tuple[int, int, str, bool]:
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
        has_alpha = mode in {"RGBA", "LA"} or "transparency" in image.info
    return width, height, mode, has_alpha


def _stable_order(candidates: Iterable[Candidate], salt: str) -> list[Candidate]:
    return sorted(
        candidates,
        key=lambda item: hashlib.sha256(
            (salt + "\0" + str(item.path).lower()).encode("utf-8")
        ).hexdigest(),
    )


def _select(
    pool: Iterable[Candidate],
    count: int,
    semantic_class: str,
    used_hashes: set[str],
) -> list[tuple[Candidate, str]]:
    selected: list[tuple[Candidate, str]] = []
    for candidate in _stable_order(pool, semantic_class):
        digest = _sha256(candidate.path)
        if digest in used_hashes:
            continue
        selected.append((candidate, digest))
        used_hashes.add(digest)
        if len(selected) == count:
            break
    return selected


def _problem_rank(
    candidates: Iterable[Candidate], semantic_class: str
) -> list[Candidate]:
    shaped: list[tuple[tuple[float, ...], Candidate]] = []
    for candidate in candidates:
        width, height, _mode, has_alpha = _image_shape(candidate.path)
        aspect = max(width, height) / max(1, min(width, height))
        area = width * height
        if semantic_class == "text":
            key = (-aspect, area)
        elif semantic_class == "layer_knockout":
            key = (-float(has_alpha), -area, aspect)
        elif semantic_class == "stroke_diagram":
            key = (-aspect, -area)
        else:
            key = (area, aspect)
        shaped.append((key, candidate))
    return [candidate for _key, candidate in sorted(
        shaped, key=lambda pair: (pair[0], str(pair[1].path).lower())
    )]


def build_manifest() -> dict[str, Any]:
    challenge = _challenge_candidates()
    problem = _problem_candidates()
    by_category: dict[str, list[Candidate]] = {}
    for candidate in challenge:
        by_category.setdefault(candidate.source_category, []).append(candidate)

    primary: dict[str, list[Candidate]] = {
        "text": by_category.get("small_text", []),
        "small_shape": (
            by_category.get("ui_icons", []) + by_category.get("logos", [])
        ),
        "layer_knockout": by_category.get("transparency", []),
        "stroke_diagram": by_category.get("diagrams", []),
        "gradient": by_category.get("gradients", []),
        "codec_detail": [
            candidate
            for candidate in challenge
            if candidate.source_category == "jpeg_dirty"
            or candidate.source_kind in {"jpeg", "jpeg-copy"}
        ],
    }

    used_hashes: set[str] = set()
    rows: list[dict[str, Any]] = []
    for semantic_class, target_count in TARGETS:
        selected = _select(
            primary[semantic_class], target_count, semantic_class, used_hashes
        )
        if len(selected) < target_count:
            supplement = _select(
                _problem_rank(problem, semantic_class),
                target_count - len(selected),
                semantic_class + ":problem",
                used_hashes,
            )
            selected.extend(supplement)
        if len(selected) != target_count:
            raise RuntimeError(
                f"{semantic_class}: required {target_count}, found {len(selected)} "
                "unique owned raster sources"
            )
        for class_index, (candidate, digest) in enumerate(selected):
            width, height, mode, has_alpha = _image_shape(candidate.path)
            locus_id = (
                f"{semantic_class}-{class_index:03d}-{digest[:12]}"
            )
            rows.append(
                {
                    "id": locus_id,
                    "semantic_class": semantic_class,
                    "class_index": class_index,
                    "source": {
                        "path": str(candidate.path),
                        "sha256": digest,
                        "origin": candidate.origin,
                        "category": candidate.source_category,
                        "kind": candidate.source_kind,
                        "source_asset": candidate.source_asset,
                        "license_scope": "local-owned-or-project-legal-source",
                        "vai_output": False,
                    },
                    "image": {
                        "width": width,
                        "height": height,
                        "mode": mode,
                        "has_alpha": has_alpha,
                    },
                    "machine_suggestion": {
                        "roi_xyxy": [0, 0, width, height],
                        "macro_family": semantic_class,
                        "text_line_membership": (
                            "yes" if semantic_class == "text" else "unknown"
                        ),
                    },
                    "annotation_status": "pending_review",
                }
            )

    counts = {
        semantic_class: sum(
            row["semantic_class"] == semantic_class for row in rows
        )
        for semantic_class, _count in TARGETS
    }
    return {
        "schema": "pcdc-real-locus-corpus/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection": "deterministic-class-balanced-sha256-deduplicated",
        "ground_truth_policy": (
            "machine_suggestion is never ground truth; only review.json entries "
            "with status=ground_truth_derived, evidence_reviewed, or complete count "
            "toward Experiment 1; ground_truth_derived requires an owned source asset "
            "and a recorded conservative alignment proof; status=complete additionally "
            "requires a later candidate preference"
        ),
        "forbidden_sources": ["Vectorizer.AI outputs", "challenge_pack/vai"],
        "targets": dict(TARGETS),
        "counts": counts,
        "total": len(rows),
        "loci": rows,
    }


def validate_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rows = payload.get("loci")
    if not isinstance(rows, list):
        return ["loci must be a list"]
    if len(rows) != sum(count for _name, count in TARGETS):
        errors.append(f"expected 300 loci, got {len(rows)}")
    ids = [row.get("id") for row in rows]
    hashes = [row.get("source", {}).get("sha256") for row in rows]
    if len(set(ids)) != len(ids):
        errors.append("locus ids are not unique")
    if len(set(hashes)) != len(hashes):
        errors.append("source SHA-256 values are not unique")
    for semantic_class, expected in TARGETS:
        actual = sum(row.get("semantic_class") == semantic_class for row in rows)
        if actual != expected:
            errors.append(
                f"{semantic_class}: expected {expected}, got {actual}"
            )
    for row in rows:
        source = row.get("source", {})
        path = Path(str(source.get("path", "")))
        if not path.is_file():
            errors.append(f"missing source: {path}")
        if bool(source.get("vai_output")) or "\\vai\\" in str(path).lower():
            errors.append(f"forbidden VAI source: {path}")
        if row.get("annotation_status") != "pending_review":
            errors.append(f"new locus not pending review: {row.get('id')}")
    return errors


def write_corpus(out_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    payload = build_manifest()
    errors = validate_manifest(payload)
    if errors:
        raise RuntimeError("; ".join(errors[:20]))
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    review_path = out_dir / "review.json"
    if not review_path.exists():
        review_path.write_text(
            json.dumps(
                {
                    "schema": "pcdc-real-locus-review/v1",
                    "corpus_schema": payload["schema"],
                    "reviews": {},
                    "complete_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        payload = json.loads((args.out / "manifest.json").read_text("utf-8"))
        errors = validate_manifest(payload)
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
        return int(bool(errors))
    payload = write_corpus(args.out)
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(args.out / "manifest.json"),
                "total": payload["total"],
                "counts": payload["counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
