"""Build the blinded, native-scale human court for PCDC Experiment 4.

The court is source-only: both sides are generated before frozen review
support is consulted.  Private ``candidate_side`` labels stay in the dataset
manifest and are stripped by the preview server.  Every displayed hypothesis
is a live SVG with the same native viewBox as the source crop.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

from PIL import Image, ImageOps

from .certificates import mask_sha256
from .evidence_ir import EvidenceCache
from .experiment4_textline import (
    CORPUS, TextLineReviewArtifacts, _glyph_prior_identity, evaluate_locus,
)
from .experiment_inputs import (
    font_catalog_input_identity, real_locus_input_identity,
    trocr_model_input_identity,
)


PROJECT = Path(__file__).resolve().parents[1]
WARM_DATASET = PROJECT / "datasets" / "pcdc_textline_pairs_v1"
EXACT_DATASET = PROJECT / "datasets" / "pcdc_textline_pairs_v2"
WARM_ASSETS = PROJECT / "web_preview" / "textline_review_assets"
EXACT_ASSETS = PROJECT / "web_preview" / "textline_review_assets_v2"


def _source_crop(
    source: Path, roi: tuple[int, int, int, int], target: Path,
) -> tuple[int, int]:
    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGBA")
        x1, y1, x2, y2 = roi
        crop = image.crop((x1, y1, x2, y2))
        crop.save(target, format="PNG", optimize=True)
        return crop.size


def _case(
    index: int, locus: dict[str, Any], review: dict[str, Any],
    cache: EvidenceCache, *, exact: bool, assets: Path,
    public_assets_name: str,
) -> dict[str, Any]:
    artifacts: list[TextLineReviewArtifacts] = []
    row = evaluate_locus(
        locus, review, cache, exact_font=exact,
        review_artifacts=artifacts,
    )
    if len(artifacts) != 1:
        raise RuntimeError("Experiment 4 did not return one review artifact")
    artifact = artifacts[0]
    source_roi = artifact.source_roi
    legacy_mask = artifact.legacy_mask
    candidate_mask = artifact.candidate_mask
    legacy_svg = artifact.legacy_svg
    candidate_svg = artifact.candidate_svg

    stem = f"textline_{index + 1:03d}"
    source_target = assets / f"{stem}_source.png"
    a_target = assets / f"{stem}_a.svg"
    b_target = assets / f"{stem}_b.svg"
    native_size = _source_crop(
        Path(locus["source"]["path"]), source_roi, source_target,
    )
    digest = hashlib.sha256(
        f"{locus['id']}\0pcdc-textline-blind/{'exact-v2' if exact else 'warm-v1'}".encode("utf-8")
    ).digest()
    candidate_side = "A" if digest[0] & 1 else "B"
    candidate_mask_digest = mask_sha256(candidate_mask)
    legacy_mask_digest = mask_sha256(legacy_mask)
    a_target.write_text(
        candidate_svg if candidate_side == "A" else legacy_svg, "utf-8",
    )
    b_target.write_text(
        candidate_svg if candidate_side == "B" else legacy_svg, "utf-8",
    )
    return {
        "id": str(locus["id"]),
        "category": locus["source"].get("category"),
        "native_size": [int(native_size[0]), int(native_size[1])],
        "source_url": f"/{public_assets_name}/{source_target.name}",
        "a_url": f"/{public_assets_name}/{a_target.name}",
        "b_url": f"/{public_assets_name}/{b_target.name}",
        "candidate_side": candidate_side,
        "candidate_mask_digest": candidate_mask_digest,
        "legacy_mask_digest": legacy_mask_digest,
        "candidate_svg_digest": hashlib.sha256(
            candidate_svg.encode("utf-8")
        ).hexdigest(),
        "legacy_svg_digest": hashlib.sha256(
            legacy_svg.encode("utf-8")
        ).hexdigest(),
        "candidate_path": row["candidate_solution"]["selected_path"],
        "candidate_reason": row["candidate_solution"]["reason"],
        "legacy_exact_cover": bool(row["legacy_solution"]["exact_cover"]),
        "candidate_mask_matches_experiment4": bool(
            candidate_mask_digest == row["candidate_mask_digest"]
        ),
        "candidate_svg_matches_experiment4": bool(
            hashlib.sha256(candidate_svg.encode("utf-8")).hexdigest()
            == row["candidate_svg_digest"]
        ),
        "render_contract": "same native crop; live SVG; identical viewBox",
    }


def build(*, exact: bool = False) -> dict[str, Any]:
    dataset = EXACT_DATASET if exact else WARM_DATASET
    assets_base = EXACT_ASSETS if exact else WARM_ASSETS
    build_id = uuid.uuid4().hex[:16]
    assets = assets_base.with_name(f"{assets_base.name}_{build_id}.building")
    published_assets = assets_base.with_name(f"{assets_base.name}_{build_id}")
    input_identity = real_locus_input_identity(CORPUS)
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    reviews = json.loads((CORPUS / "review.json").read_text("utf-8"))["reviews"]
    loci = [
        row for row in manifest["loci"]
        if row.get("semantic_class") == "text"
        and row["id"] in reviews
        and reviews[row["id"]].get("status") in {
            "ground_truth_derived", "evidence_reviewed", "complete",
        }
    ]
    if not 100 <= len(loci) <= 200:
        raise ValueError(f"Experiment 4 requires 100-200 lines, got {len(loci)}")
    dataset.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=False)
    cache = EvidenceCache()
    cases = [_case(
        index, row, reviews[row["id"]], cache,
        exact=exact, assets=assets,
        public_assets_name=published_assets.name,
    )
             for index, row in enumerate(loci)]
    payload = {
        "schema": (
            "pcdc-textline-human-court/v2"
            if exact else "pcdc-textline-human-court/v1"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_mode": "exact-ocr-glyph-prior" if exact else "warm-font-free",
        "glyph_prior_checkpoint": _glyph_prior_identity() if exact else None,
        "input_identity": input_identity,
        "font_catalog_identity": font_catalog_input_identity() if exact else None,
        "ocr_model_identity": trocr_model_input_identity() if exact else None,
        "asset_directory": str(published_assets.resolve()),
        "total": len(cases), "required": len(cases),
        "blind_contract": (
            "candidate side deterministic and withheld by server; source and "
            "both SVGs share the native crop/viewBox"
        ),
        "cases": cases,
    }
    assets.replace(published_assets)
    manifest_path = dataset / "human_manifest.json"
    manifest_tmp = manifest_path.with_suffix(".json.tmp")
    manifest_tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    manifest_tmp.replace(manifest_path)
    review_path = dataset / "review.json"
    if not review_path.is_file():
        review_path.write_text(json.dumps({
            "schema": (
                "pcdc-textline-human-review/v2"
                if exact else "pcdc-textline-human-review/v1"
            ),
            "required": len(cases), "answers": {}, "complete_count": 0,
        }, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return payload


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exact", action="store_true",
        help="build the exact/OCR/glyph-prior v2 court",
    )
    args = parser.parse_args()
    payload = build(exact=args.exact)
    dataset = EXACT_DATASET if args.exact else WARM_DATASET
    print(json.dumps({
        "status": "built", "total": payload["total"],
        "mode": payload["candidate_mode"],
        "manifest": str(dataset / "human_manifest.json"),
        "assets": payload["asset_directory"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
