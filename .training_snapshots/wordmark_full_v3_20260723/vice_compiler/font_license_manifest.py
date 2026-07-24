"""Immutable license/hash manifest for clean-room font training inputs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


FONT_SUFFIXES = frozenset({".ttf", ".otf", ".ttc"})
LICENSE_BY_COLLECTION = {
    "ofl": "OFL-1.1",
    "apache": "Apache-2.0",
    "ufl": "Ubuntu-Font-License-1.0",
}
LICENSE_NAMES = (
    "OFL.txt", "LICENSE.txt", "LICENCE.txt", "UFL.txt",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _license_path(font: Path, root: Path) -> Path:
    current = font.parent
    while current == root or root in current.parents:
        for name in LICENSE_NAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        if current == root:
            break
        current = current.parent
    raise ValueError(f"font lacks an adjacent redistributable license: {font}")


def build_manifest(root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    try:
        revision = subprocess.run(
            [
                "git", "-c", f"safe.directory={root.as_posix()}",
                "-C", str(root), "rev-parse", "HEAD",
            ],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unversioned"
    rows = []
    for font in sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in FONT_SUFFIXES
    ):
        relative = font.relative_to(root)
        collection = relative.parts[0].lower() if relative.parts else ""
        license_id = LICENSE_BY_COLLECTION.get(collection)
        if license_id is None:
            raise ValueError(
                f"font collection has no closed license mapping: {relative}"
            )
        license_path = _license_path(font, root)
        rows.append({
            "family": font.parent.name,
            "font_path": relative.as_posix(),
            "font_sha256": _sha256(font),
            "bytes": font.stat().st_size,
            "license": license_id,
            "license_path": license_path.relative_to(root).as_posix(),
            "license_sha256": _sha256(license_path),
        })
    if not rows:
        raise RuntimeError("font manifest would be empty")
    manifest = {
        "schema": "pcdc-font-license-manifest/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://github.com/google/fonts",
        "source_revision": revision,
        "root": str(root),
        "font_count": len(rows),
        "family_count": len({row["family"] for row in rows}),
        "fonts": rows,
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["content_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    return manifest


def validate_manifest(manifest: dict, *, root: Path | None = None) -> None:
    if manifest.get("schema") != "pcdc-font-license-manifest/v1":
        raise ValueError("unsupported font manifest schema")
    rows = manifest.get("fonts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("font manifest is empty")
    payload = dict(manifest)
    expected = str(payload.pop("content_sha256", ""))
    actual = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    if expected != actual:
        raise ValueError("font manifest content digest mismatch")
    base = (root or Path(str(manifest["root"]))).resolve()
    for row in rows:
        font = base / row["font_path"]
        license_path = base / row["license_path"]
        if row["license"] not in set(LICENSE_BY_COLLECTION.values()):
            raise ValueError("font has an unapproved training license")
        if not font.is_file() or _sha256(font) != row["font_sha256"]:
            raise ValueError(f"font bytes differ from manifest: {font}")
        if not license_path.is_file() or _sha256(license_path) != row["license_sha256"]:
            raise ValueError(f"font license differs from manifest: {license_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    manifest = build_manifest(args.root)
    validate_manifest(manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "out": str(args.out.resolve()),
        "families": manifest["family_count"],
        "fonts": manifest["font_count"],
        "content_sha256": manifest["content_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
