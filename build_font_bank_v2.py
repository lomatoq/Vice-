"""Expanded font bank v2 manifest (audit S11.2).

Scans the full google-fonts checkout at its pinned upstream revision and
emits a v2 manifest for the RETRIEVAL/v10 lane. The attested 241-face
runtime bank (fonts/google-fonts-manifest.json) is untouched: the two banks
coexist, and every proof bound to the old bank stays valid.

Licenses are taken from the repository layout (ofl/ = SIL OFL, ufl/ =
Ubuntu Font License, apache/ = Apache-2.0) - the same convention the
attested bank used.

Usage:
  C:\\Python312\\python.exe build_font_bank_v2.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANK = ROOT / "fonts" / "google-fonts"
OUT = ROOT / "fonts" / "google-fonts-manifest-v2-full.json"
LICENSES = {"ofl": "OFL-1.1", "ufl": "UFL-1.0", "apache": "Apache-2.0"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    started = time.perf_counter()
    revision = subprocess.run(
        ["git", "-C", str(BANK), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    faces = []
    families = set()
    for license_dir, license_name in LICENSES.items():
        base = BANK / license_dir
        if not base.is_dir():
            continue
        for family_dir in sorted(base.iterdir()):
            if not family_dir.is_dir():
                continue
            ttfs = sorted(family_dir.glob("*.ttf"))
            if not ttfs:
                continue
            families.add(family_dir.name)
            for ttf in ttfs:
                faces.append({
                    "family": family_dir.name,
                    "path": str(ttf.relative_to(ROOT)).replace("\\", "/"),
                    "sha256": _sha256(ttf),
                    "license": license_name,
                })
    payload = {
        "schema": "vice-font-bank/v2-full",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "upstream_revision": revision,
        "family_count": len(families),
        "face_count": len(faces),
        "faces": faces,
        "note": (
            "Retrieval/v10 bank. The attested runtime bank "
            "(google-fonts-manifest.json) is separate and unchanged."
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }
    content = json.dumps(payload, indent=1)
    payload["content_sha256"] = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(
        f"{len(families)} families, {len(faces)} faces, "
        f"{payload['elapsed_seconds']:.0f}s -> {OUT}"
    )


if __name__ == "__main__":
    main()
