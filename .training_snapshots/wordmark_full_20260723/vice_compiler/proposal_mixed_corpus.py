"""Build an immutable mixed raster/vector manifest without copying payloads."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .proposal_data_contract import split_group, typed_macro_families


_FACTORY_SOURCE_BY_SCHEMA = {
    "pcdc-proposal-text-data-factory/v2": "proposal_text_data_factory.py",
    "pcdc-proposal-structure-data-factory/v1": "proposal_structure_data_factory.py",
    "pcdc-proposal-structure-data-factory/v2": "proposal_structure_data_factory.py",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rows(root: Path) -> list[dict]:
    manifest = root / "pairs.jsonl"
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    result = []
    for line_number, line in enumerate(manifest.read_text("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        for field in ("id", "source_id", "input_png", "target_svg"):
            if not row.get(field):
                raise ValueError(f"{manifest}:{line_number} lacks {field}")
        payload = dict(row)
        payload["input_png"] = str((root / row["input_png"]).resolve())
        payload["target_svg"] = str((root / row["target_svg"]).resolve())
        if not Path(payload["input_png"]).is_file():
            raise FileNotFoundError(payload["input_png"])
        if not Path(payload["target_svg"]).is_file():
            raise FileNotFoundError(payload["target_svg"])
        payload["pair_origin"] = str(root.resolve())
        result.append(payload)
    return result


def _payload_digest(rows: list[dict]) -> tuple[int, str]:
    paths = sorted({
        str(Path(row[field]).resolve())
        for row in rows for field in ("input_png", "target_svg")
    })
    digest = hashlib.sha256()
    for value in paths:
        path = Path(value)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return len(paths), digest.hexdigest()


def _stable_split(group: str) -> str:
    value = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if value < 80 else "calibration" if value < 90 else "test"


def _verify_attestation(attestation: Path, pair_sha256: str) -> dict:
    try:
        payload = json.loads(attestation.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"invalid corpus attestation: {attestation}") from error
    schema = str(payload.get("schema", "unversioned"))
    if schema in _FACTORY_SOURCE_BY_SCHEMA:
        if payload.get("pair_rows_sha256") != pair_sha256:
            raise ValueError(f"factory pair digest mismatch: {attestation}")
        factory_source = Path(__file__).with_name(_FACTORY_SOURCE_BY_SCHEMA[schema])
        if payload.get("factory_source_sha256") != _sha256(factory_source):
            raise ValueError(f"factory source digest mismatch: {attestation}")
        if schema in {
            "pcdc-proposal-structure-data-factory/v1",
            "pcdc-proposal-structure-data-factory/v2",
        }:
            shared_source = Path(__file__).with_name("proposal_text_data_factory.py")
            if payload.get("shared_augmentation_source_sha256") != _sha256(shared_source):
                raise ValueError(
                    f"shared augmentation source digest mismatch: {attestation}"
                )
    return {"schema": schema}


def split_audit(rows: list[dict]) -> dict:
    source_rows: Counter[tuple[str, str]] = Counter()
    family_rows: Counter[tuple[str, str]] = Counter()
    groups = {name: set() for name in ("train", "calibration", "test")}
    for row in rows:
        group = split_group(row)
        split = _stable_split(group)
        groups[split].add(group)
        source = str(row.get("source", "unknown"))
        source_rows[(source, split)] += 1
        if source == "synthetic-open-text":
            family_rows[("text_line", split)] += 1
            family_rows[("glyph_group", split)] += 1
        typed = typed_macro_families(row)
        if typed is not None:
            for family in typed:
                family_rows[(family, split)] += 1
    overlap = (
        (groups["train"] & groups["calibration"])
        | (groups["train"] & groups["test"])
        | (groups["calibration"] & groups["test"])
    )
    if overlap:
        raise RuntimeError("mixed corpus split groups overlap")
    return {
        "policy": "sha256-group-80/10/10",
        "group_overlap": False,
        "group_counts": {name: len(value) for name, value in groups.items()},
        "source_pair_counts": {
            f"{source}|{split}": count
            for (source, split), count in sorted(source_rows.items())
        },
        "declared_supplement_target_counts": {
            f"{family}|{split}": count
            for (family, split), count in sorted(family_rows.items())
        },
    }


def validate_mixed_corpus(root: Path) -> dict:
    """Revalidate a persisted mixed manifest and all bound input attestations."""
    report_path = root / "report.json"
    pair_path = root / "pairs.jsonl"
    report = json.loads(report_path.read_text("utf-8"))
    if report.get("schema") != "pcdc-proposal-mixed-corpus/v1":
        raise ValueError("pair root is not a proof-bound mixed corpus")
    if report.get("builder_source_sha256") != _sha256(Path(__file__)):
        raise ValueError("mixed corpus builder source digest mismatch")
    data_contract = Path(__file__).with_name("proposal_data_contract.py")
    if report.get("data_contract_source_sha256") != _sha256(data_contract):
        raise ValueError("mixed corpus data-contract digest mismatch")
    if _sha256(pair_path) != report.get("pairs_jsonl_sha256"):
        raise ValueError("mixed pair manifest digest mismatch")
    for row in report.get("inputs", []):
        origin = Path(str(row["root"]))
        origin_pairs = origin / "pairs.jsonl"
        pair_sha256 = _sha256(origin_pairs)
        if pair_sha256 != row.get("pairs_jsonl_sha256"):
            raise ValueError(f"mixed origin pair digest mismatch: {origin}")
        attestation_name = row.get("attestation")
        if attestation_name:
            attestation = origin / str(attestation_name)
            if _sha256(attestation) != row.get("attestation_sha256"):
                raise ValueError(f"mixed origin attestation digest mismatch: {origin}")
            _verify_attestation(attestation, pair_sha256)
        origin_rows = _rows(origin)
        payload_count, payload_sha256 = _payload_digest(origin_rows)
        if (
            payload_count != row.get("payload_file_count")
            or payload_sha256 != row.get("payload_content_sha256")
        ):
            raise ValueError(f"mixed origin payload digest mismatch: {origin}")
    return report


def build_mixed_corpus(roots: tuple[Path, ...], out: Path) -> dict:
    if len(roots) < 2:
        raise ValueError("mixed corpus requires a base and at least one supplement")
    resolved = tuple(root.resolve() for root in roots)
    if len(set(resolved)) != len(resolved):
        raise ValueError("mixed corpus roots must be unique")
    rows: list[dict] = []
    inputs = []
    identifiers: set[str] = set()
    for root in resolved:
        part = _rows(root)
        duplicate = identifiers & {str(row["id"]) for row in part}
        if duplicate:
            raise ValueError(f"duplicate pair id across roots: {min(duplicate)}")
        identifiers.update(str(row["id"]) for row in part)
        rows.extend(part)
        pair_path = root / "pairs.jsonl"
        pair_sha256 = _sha256(pair_path)
        payload_count, payload_sha256 = _payload_digest(part)
        input_record = {
            "root": str(root), "pairs": len(part),
            "pairs_jsonl_sha256": pair_sha256,
            "payload_file_count": payload_count,
            "payload_content_sha256": payload_sha256,
        }
        attestation = root / "report.json"
        if not attestation.is_file():
            attestation = root / "summary.json"
        if attestation.is_file():
            input_record.update({
                "attestation": attestation.name,
                "attestation_sha256": _sha256(attestation),
                **_verify_attestation(attestation, pair_sha256),
            })
        inputs.append(input_record)
    rows.sort(key=lambda row: str(row["id"]))
    out.mkdir(parents=True, exist_ok=True)
    pair_path = out / "pairs.jsonl"
    pair_path.write_text("".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ), "utf-8")
    report = {
        "schema": "pcdc-proposal-mixed-corpus/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "builder_source_sha256": _sha256(Path(__file__)),
        "data_contract_source_sha256": _sha256(
            Path(__file__).with_name("proposal_data_contract.py")
        ),
        "inputs": inputs, "pair_count": len(rows),
        "pairs_jsonl_sha256": _sha256(pair_path),
        "payload_policy": "absolute-read-only-references/no-copy",
        "split_audit": split_audit(rows),
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), "utf-8",
    )
    validate_mixed_corpus(out)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(
        build_mixed_corpus(tuple(arguments.root), arguments.out),
        indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
