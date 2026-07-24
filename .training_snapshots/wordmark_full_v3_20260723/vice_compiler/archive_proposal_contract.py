"""Archive the exact source bytes bound into a ProposalNet label contract."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil


PROJECT = Path(__file__).resolve().parents[1]
CONTRACT_SOURCES = (
    PROJECT / "vice_compiler" / "train_proposal_net_large.py",
    PROJECT / "vice_compiler" / "proposal_net.py",
    PROJECT / "vice_compiler" / "proposal_instance_labels.py",
    PROJECT / "vice_compiler" / "explicit_svg_owners.py",
    PROJECT / "vice_compiler" / "proposal_data_contract.py",
    PROJECT / "vice_compiler" / "proposal_replay.py",
    PROJECT / "vice_compiler" / "proposal_mixed_corpus.py",
    PROJECT / "vice_compiler" / "proposal_filter_cache.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(out: Path, checkpoint: Path | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in CONTRACT_SOURCES:
        target = out / source.name
        shutil.copy2(source, target)
        source_hash = _sha256(source)
        if _sha256(target) != source_hash:
            raise RuntimeError("archived contract source changed during copy")
        rows.append({
            "source": str(source.resolve()), "archive": target.name,
            "sha256": source_hash,
        })
    from .train_proposal_net_large import (
        LABEL_CONTRACT_VERSION, _label_contract_sha256,
    )
    report = {
        "schema": "pcdc-proposal-label-contract-archive/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label_contract_version": LABEL_CONTRACT_VERSION,
        "label_contract_sha256": _label_contract_sha256(),
        "sources": rows,
    }
    if checkpoint is not None:
        import torch

        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        if (
            payload.get("label_contract_version") != LABEL_CONTRACT_VERSION
            or payload.get("label_contract_sha256") != report["label_contract_sha256"]
        ):
            raise ValueError("checkpoint does not match the archived label contract")
        report["checkpoint"] = {
            "path": str(checkpoint.resolve()), "sha256": _sha256(checkpoint),
            "epoch": int(payload.get("epoch", -1)),
            "selection_key": payload.get("calibration_selection_key"),
        }
    (out / "manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), "utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    print(json.dumps(
        archive(args.out, checkpoint=args.checkpoint), indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
