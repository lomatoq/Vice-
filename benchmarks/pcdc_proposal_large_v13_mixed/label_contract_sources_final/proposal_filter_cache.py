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
        trainer._foreground_support, trainer._filter_supervisable_pairs,
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
    payload = {
        "schema": "pcdc-proposal-filter-cache/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_root": str(pair_root.resolve()),
        "training_data_contract_sha256": report["training_data_contract_sha256"],
        "filter_semantics_sha256": filter_semantics_sha256(),
        "raw_pair_count": len(rows), "accepted_pair_count": len(accepted_ids),
        "raw_ids_sha256": _ids_sha256(identifiers),
        "accepted_ids_sha256": _ids_sha256(accepted_ids),
        "accepted_ids": accepted_ids, "rejected_pairs": rejected_rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    return payload


def validate_filter_cache(
    cache_path: Path, rows: list[dict], *, training_data_contract_sha256: str,
) -> tuple[list[dict], tuple[dict, ...]]:
    payload = json.loads(cache_path.read_text("utf-8"))
    if payload.get("schema") != "pcdc-proposal-filter-cache/v1":
        raise ValueError("unsupported ProposalNet filter cache")
    if payload.get("training_data_contract_sha256") != training_data_contract_sha256:
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
    parser.add_argument("--training-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = build_filter_cache(
        args.pair_root, args.training_report, args.out,
    )
    print(json.dumps({
        key: value for key, value in payload.items()
        if key not in {"accepted_ids", "rejected_pairs"}
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
