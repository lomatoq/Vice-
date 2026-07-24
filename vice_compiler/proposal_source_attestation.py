"""Version an externally owned raster/vector corpus without copying payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "pcdc-external-raster-vector-corpus-attestation/v2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_attestation_source_sha256() -> str:
    return _sha256(Path(__file__))


def _origin_attestation(origin: Path) -> Path:
    for name in ("report.json", "summary.json"):
        candidate = origin / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("external corpus has no report.json or summary.json")


def create_source_attestation(
    origin: Path, output: Path, *, origin_generator_source: Path,
    renderer_prefix: str,
) -> dict:
    """Hash the complete external corpus and emit a local immutable wrapper."""

    from .proposal_mixed_corpus import _payload_digest, _rows

    resolved = origin.resolve()
    rows = _rows(resolved)
    payload_count, payload_sha256 = _payload_digest(rows)
    pairs = resolved / "pairs.jsonl"
    original = _origin_attestation(resolved)
    generator_source = origin_generator_source.resolve()
    if not generator_source.is_file():
        raise FileNotFoundError(generator_source)
    renderer = str(renderer_prefix).strip().rstrip("/")
    if not renderer or any(character.isspace() for character in renderer):
        raise ValueError("external renderer prefix must be a nonempty token")
    report = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "origin_root": str(resolved),
        "origin_attestation": original.name,
        "origin_attestation_sha256": _sha256(original),
        "pairs_jsonl_sha256": _sha256(pairs),
        "pair_count": len(rows),
        "payload_file_count": payload_count,
        "payload_content_sha256": payload_sha256,
        "attestation_source_sha256": source_attestation_source_sha256(),
        "origin_generator_source": str(generator_source),
        "origin_generator_source_sha256": _sha256(generator_source),
        "renderer_prefix": renderer,
        "policy": "absolute-read-only-origin/full-payload-content-bound",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    temporary.replace(output)
    return report


def validate_source_attestation(
    path: Path, origin: Path, *, pair_sha256: str,
) -> dict:
    payload = json.loads(path.read_text("utf-8"))
    resolved = origin.resolve()
    original = _origin_attestation(resolved)
    generator_source = Path(str(payload.get("origin_generator_source", "")))
    expected = {
        "schema": SCHEMA,
        "origin_root": str(resolved),
        "origin_attestation": original.name,
        "origin_attestation_sha256": _sha256(original),
        "pairs_jsonl_sha256": pair_sha256,
        "attestation_source_sha256": source_attestation_source_sha256(),
        "origin_generator_source_sha256": (
            _sha256(generator_source) if generator_source.is_file() else None
        ),
    }
    mismatches = {
        key: {"expected": value, "actual": payload.get(key)}
        for key, value in expected.items() if payload.get(key) != value
    }
    if (
        int(payload.get("pair_count", 0)) <= 0
        or int(payload.get("payload_file_count", 0)) <= 0
        or len(str(payload.get("payload_content_sha256", ""))) != 64
        or not generator_source.is_file()
        or not str(payload.get("renderer_prefix", "")).strip()
    ):
        mismatches["payload"] = "missing complete payload identity"
    if mismatches:
        raise ValueError(
            "external corpus attestation mismatch: "
            + json.dumps(mismatches, sort_keys=True)
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--origin-generator-source", type=Path, required=True)
    parser.add_argument("--renderer-prefix", required=True)
    args = parser.parse_args()
    print(json.dumps(
        create_source_attestation(
            args.origin, args.out,
            origin_generator_source=args.origin_generator_source,
            renderer_prefix=args.renderer_prefix,
        ),
        indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
