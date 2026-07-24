"""Hash-bound accepted/rejected row cache for ProposalNet corpus preflight."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import inspect
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def _ids_sha256(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def filter_semantics_sha256() -> str:
    from . import train_proposal_net_large as trainer

    digest = hashlib.sha256(b"pcdc-proposal-filter-semantics/v1")
    for function in (
        trainer._read_svg_text, trainer._uses_svg_owner_labels,
        trainer._foreground_support, trainer._validate_filter_row,
        trainer._validate_filter_chunk, trainer._filter_supervisable_pairs,
    ):
        digest.update(function.__name__.encode("utf-8"))
        digest.update(inspect.getsource(function).encode("utf-8"))
    for filename in (
        "proposal_instance_labels.py", "explicit_svg_owners.py",
        "proposal_data_contract.py",
    ):
        digest.update(filename.encode("utf-8"))
        digest.update((PROJECT / "vice_compiler" / filename).read_bytes())
    return digest.hexdigest()


def build_filter_cache(
    pair_root: Path, training_report: Path, out: Path,
) -> dict:
    report = json.loads(training_report.read_text("utf-8"))
    if report.get("schema") != "pcdc-proposal-large-training/v2-honest-top5":
        raise ValueError("filter cache requires a completed large-training report")
    rows = [
        json.loads(line) for line in
        (pair_root / "pairs.jsonl").read_text("utf-8").splitlines()
        if line.strip()
    ]
    identifiers = [str(row["id"]) for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("filter cache input pair ids are not unique")
    if len(rows) != int(report.get("raw_pair_count", -1)):
        raise ValueError("training report raw count does not match pair root")
    rejected_rows = list(report.get("rejected_pairs", []))
    rejected_ids = [str(row["id"]) for row in rejected_rows]
    if len(rejected_ids) != len(set(rejected_ids)):
        raise ValueError("training report has duplicate rejected ids")
    unknown = set(rejected_ids) - set(identifiers)
    if unknown:
        raise ValueError(f"training report rejects unknown pair: {min(unknown)}")
    accepted_ids = [value for value in identifiers if value not in set(rejected_ids)]
    if len(accepted_ids) != int(report.get("pair_count", -1)):
        raise ValueError("training report accepted count is inconsistent")
    corpus_contract = corpus_data_contract_sha256(pair_root)
    reported_contract = report.get("corpus_data_contract_sha256")
    if reported_contract is not None and reported_contract != corpus_contract:
        raise ValueError("training report belongs to another corpus contract")
    return _write_cache(
        pair_root=pair_root, out=out, rows=rows, accepted_ids=accepted_ids,
        rejected_rows=rejected_rows, corpus_contract=corpus_contract,
    )


def build_filter_cache_from_scan(pair_root: Path, out: Path) -> dict:
    """Materialize the immutable pre-training filter without a model run."""
    from .proposal_mixed_corpus import validate_mixed_corpus
    from .train_proposal_net_large import (
        _filter_supervisable_pairs, _read_pairs,
    )

    report = pair_root / "report.json"
    if report.is_file():
        payload = json.loads(report.read_text("utf-8"))
        if payload.get("schema") == "pcdc-proposal-mixed-corpus/v1":
            validate_mixed_corpus(pair_root)
    rows = _read_pairs(pair_root, None)
    identifiers = [str(row["id"]) for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("filter cache input pair ids are not unique")
    accepted, rejected = _filter_supervisable_pairs(rows, pair_root)
    return _write_cache(
        pair_root=pair_root, out=out, rows=rows,
        accepted_ids=[str(row["id"]) for row in accepted],
        rejected_rows=list(rejected),
        corpus_contract=corpus_data_contract_sha256(pair_root),
    )


def validate_filter_cache(
    cache_path: Path, rows: list[dict], *, training_data_contract_sha256: str,
) -> tuple[list[dict], tuple[dict, ...]]:
    payload = json.loads(cache_path.read_text("utf-8"))
    schema = payload.get("schema")
    if schema not in {
        "pcdc-proposal-filter-cache/v1", "pcdc-proposal-filter-cache/v2",
    }:
        raise ValueError("unsupported ProposalNet filter cache")
    contract_field = (
        "corpus_data_contract_sha256"
        if schema == "pcdc-proposal-filter-cache/v2" else
        "training_data_contract_sha256"
    )
    if payload.get(contract_field) != training_data_contract_sha256:
        raise ValueError("filter cache belongs to another data contract")
    if payload.get("filter_semantics_sha256") != filter_semantics_sha256():
        raise ValueError("filter cache belongs to another filter implementation")
    identifiers = [str(row["id"]) for row in rows]
    if (
        len(rows) != int(payload.get("raw_pair_count", -1))
        or _ids_sha256(identifiers) != payload.get("raw_ids_sha256")
    ):
        raise ValueError("filter cache belongs to another raw row set")
    accepted_ids = list(payload.get("accepted_ids", []))
    if (
        len(accepted_ids) != int(payload.get("accepted_pair_count", -1))
        or _ids_sha256(accepted_ids) != payload.get("accepted_ids_sha256")
    ):
        raise ValueError("filter cache accepted rows are corrupted")
    accepted_set = set(accepted_ids)
    accepted = [row for row in rows if str(row["id"]) in accepted_set]
    if len(accepted) != len(accepted_ids):
        raise ValueError("filter cache accepted ids are absent from the pair root")
    return accepted, tuple(payload.get("rejected_pairs", []))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--training-report", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = (
        build_filter_cache(args.pair_root, args.training_report, args.out)
        if args.training_report is not None else
        build_filter_cache_from_scan(args.pair_root, args.out)
    )
    print(json.dumps({
        key: value for key, value in payload.items()
        if key not in {"accepted_ids", "rejected_pairs"}
    }, indent=2, sort_keys=True))


def corpus_data_contract_sha256(pair_root: Path) -> str:
    digest = hashlib.sha256((pair_root / "pairs.jsonl").read_bytes())
    report = pair_root / "report.json"
    if report.is_file():
        try:
            payload = json.loads(report.read_text("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        if payload.get("schema") == "pcdc-proposal-mixed-corpus/v1":
            digest.update(report.read_bytes())
    return digest.hexdigest()


def _write_cache(
    *, pair_root: Path, out: Path, rows: list[dict], accepted_ids: list[str],
    rejected_rows: list[dict], corpus_contract: str,
) -> dict:
    identifiers = [str(row["id"]) for row in rows]
    payload = {
        "schema": "pcdc-proposal-filter-cache/v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_root": str(pair_root.resolve()),
        "corpus_data_contract_sha256": corpus_contract,
        "filter_semantics_sha256": filter_semantics_sha256(),
        "raw_pair_count": len(rows), "accepted_pair_count": len(accepted_ids),
        "raw_ids_sha256": _ids_sha256(identifiers),
        "accepted_ids_sha256": _ids_sha256(accepted_ids),
        "accepted_ids": accepted_ids, "rejected_pairs": rejected_rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    return payload


if __name__ == "__main__":
    main()
