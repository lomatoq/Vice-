"""Versioned evidence-tensor cache with atomic publication."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np

from .evidence_model import EvidenceBundle, EvidenceTensorLevel


class EvidenceCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, key: str, *, source_hash: str,
             model_version: str) -> EvidenceBundle | None:
        metadata_path = self.root / f"{key}.json"
        tensors_path = self.root / f"{key}.npz"
        if not metadata_path.is_file() or not tensors_path.is_file():
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("source_hash") != source_hash or metadata.get("model_version") != model_version:
                return None
            archive = np.load(tensors_path, allow_pickle=False)
            levels = []
            for index, scale in enumerate(metadata["scales"]):
                heads = {name: np.asarray(archive[f"l{index}__{name}"], np.float32)
                         for name in metadata["heads"][index]}
                levels.append(EvidenceTensorLevel(float(scale), heads))
            bundle = EvidenceBundle(source_hash, model_version, tuple(levels))
            bundle.validate()
            return bundle
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def store(self, key: str, bundle: EvidenceBundle) -> None:
        bundle.validate()
        self.root.mkdir(parents=True, exist_ok=True)
        arrays = {}
        heads: list[list[str]] = []
        for index, level in enumerate(bundle.levels):
            names = sorted(level.heads)
            heads.append(names)
            for name in names:
                arrays[f"l{index}__{name}"] = level.heads[name]
        metadata = {
            "schema": "vice-evidence-cache/1", "source_hash": bundle.source_hash,
            "model_version": bundle.model_version,
            "scales": [level.scale for level in bundle.levels], "heads": heads,
        }
        fd, temp_name = tempfile.mkstemp(prefix=f"{key}.", suffix=".npz", dir=self.root)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            np.savez_compressed(temp_path, **arrays)
            temp_meta = temp_path.with_suffix(".json")
            temp_meta.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
            temp_path.replace(self.root / f"{key}.npz")
            temp_meta.replace(self.root / f"{key}.json")
        finally:
            if temp_path.exists():
                temp_path.unlink()
            temp_meta = temp_path.with_suffix(".json")
            if temp_meta.exists():
                temp_meta.unlink()
