"""Content identities for external evidence consumed by canonical gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from .font_license_manifest import validate_manifest


PROJECT = Path(__file__).resolve().parents[1]


def file_sha256(path: Path) -> str:
    resolved = Path(path).resolve()
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_set_identity(
    artifacts: Mapping[str, Path], *, schema: str = "pcdc-experiment-inputs/v1",
) -> dict:
    digest = hashlib.sha256()
    rows = {}
    for role, path in sorted(artifacts.items()):
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"missing experiment input {role}: {resolved}")
        sha = file_sha256(resolved)
        digest.update(role.encode("utf-8")); digest.update(b"\0")
        digest.update(sha.encode("ascii")); digest.update(b"\0")
        rows[role] = {
            "path": str(resolved), "sha256": sha,
            "bytes": resolved.stat().st_size,
        }
    return {"schema": schema, "sha256": digest.hexdigest(), "artifacts": rows}


def real_locus_input_identity(corpus: Path) -> dict:
    """Bind annotations and the actual source/owned-reference bytes.

    The corpus manifest declares hashes for raster inputs, but the experiments
    open the paths directly.  Verifying those bytes here prevents a replaced
    JPEG from inheriting a report generated for the old file.  Owned SVGs are
    also sealed because Experiment 4 uses them as density-invariant topology
    references.
    """
    root = Path(corpus).resolve()
    base_paths = {
        "manifest": root / "manifest.json",
        "review": root / "review.json",
    }
    derivation = root / "gt_derivation_report.json"
    if derivation.is_file():
        base_paths["gt_derivation_report"] = derivation
    base = artifact_set_identity(
        base_paths, schema="pcdc-real-locus-inputs-base/v1",
    )
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    loci = manifest.get("loci")
    if not isinstance(loci, list) or not loci:
        raise ValueError("real-locus manifest is empty")

    raster_rows: dict[str, tuple[Path, str]] = {}
    owned_rows: dict[str, Path] = {}
    for locus in loci:
        locus_id = str(locus.get("id", ""))
        source = locus.get("source", {})
        path = Path(str(source.get("path", ""))).resolve()
        expected = str(source.get("sha256", ""))
        if not locus_id or len(expected) != 64 or not path.is_file():
            raise ValueError(f"invalid source contract for locus {locus_id!r}")
        key = str(path).casefold()
        previous = raster_rows.get(key)
        if previous is not None and previous[1] != expected:
            raise ValueError(f"one source has conflicting declared hashes: {path}")
        raster_rows[key] = (path, expected)
        owned = str(source.get("source_asset") or "").strip()
        if owned:
            owned_path = Path(owned).resolve()
            if not owned_path.is_file():
                raise FileNotFoundError(
                    f"missing owned topology reference for {locus_id}: {owned_path}"
                )
            owned_rows[str(owned_path).casefold()] = owned_path

    digest = hashlib.sha256()
    digest.update(base["sha256"].encode("ascii")); digest.update(b"\0")
    source_entries = []
    for _key, (path, expected) in sorted(raster_rows.items()):
        actual = file_sha256(path)
        if actual != expected:
            raise ValueError(
                f"real-locus source differs from declared hash: {path}"
            )
        digest.update(b"source\0"); digest.update(actual.encode("ascii"))
        digest.update(b"\0")
        source_entries.append(actual)
    owned_entries = []
    for _key, path in sorted(owned_rows.items()):
        actual = file_sha256(path)
        digest.update(b"owned-reference\0")
        digest.update(actual.encode("ascii")); digest.update(b"\0")
        owned_entries.append(actual)
    return {
        "schema": "pcdc-real-locus-experiment-inputs/v1",
        "sha256": digest.hexdigest(),
        "base": base,
        "source_file_count": len(source_entries),
        "owned_reference_count": len(owned_entries),
        "source_content_sha256": hashlib.sha256(
            "".join(source_entries).encode("ascii")
        ).hexdigest(),
        "owned_reference_content_sha256": hashlib.sha256(
            "".join(owned_entries).encode("ascii")
        ).hexdigest(),
    }


def certificate_court_input_identity(dataset: Path) -> dict:
    root = Path(dataset).resolve()
    return artifact_set_identity({
        "human_manifest": root / "human_manifest.json",
        "review": root / "review.json",
    }, schema="pcdc-certificate-court-inputs/v1")


def font_catalog_input_identity() -> dict:
    manifest_path = PROJECT / "fonts/google-fonts-manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    font_root = PROJECT / "fonts/google-fonts"
    validate_manifest(manifest, root=font_root)
    manifest_sha = file_sha256(manifest_path)
    digest = hashlib.sha256(b"pcdc-font-catalog-inputs/v1\0")
    digest.update(manifest_sha.encode("ascii")); digest.update(b"\0")
    digest.update(str(manifest["content_sha256"]).encode("ascii"))
    return {
        "schema": "pcdc-font-catalog-inputs/v1",
        "sha256": digest.hexdigest(),
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": manifest_sha,
        "content_sha256": manifest["content_sha256"],
        "source_revision": manifest.get("source_revision"),
        "font_count": int(manifest["font_count"]),
        "family_count": int(manifest["family_count"]),
    }


def trocr_model_input_identity() -> dict:
    from .neural_ocr import resolve_local_trocr_snapshot

    snapshot = resolve_local_trocr_snapshot()
    digest = hashlib.sha256(b"pcdc-trocr-model-inputs/v1\0")
    if snapshot is None:
        digest.update(b"disabled\0")
        return {
            "schema": "pcdc-trocr-model-inputs/v1",
            "sha256": digest.hexdigest(), "mode": "disabled",
            "snapshot": None, "revision": None, "artifacts": {},
        }
    files = sorted(path for path in snapshot.iterdir() if path.is_file())
    artifacts = {}
    for path in files:
        sha = file_sha256(path)
        digest.update(path.name.encode("utf-8")); digest.update(b"\0")
        digest.update(sha.encode("ascii")); digest.update(b"\0")
        artifacts[path.name] = {
            "path": str(path.resolve()), "sha256": sha,
            "bytes": path.stat().st_size,
        }
    return {
        "schema": "pcdc-trocr-model-inputs/v1",
        "sha256": digest.hexdigest(), "mode": "local-pinned-snapshot",
        "snapshot": str(snapshot), "revision": snapshot.name,
        "artifacts": artifacts,
    }
