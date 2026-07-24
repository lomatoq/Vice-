"""Family-disjoint splits for the uber corpus (audit S11.3).

The shipped splits are complexity/source-based; the audit requires splits
disjoint by font family and upstream project. Units of disjointness:

- synthetic-text: FONT FAMILY via an explicit face->family map of the 45
  Windows faces (21 families; unknown faces become their own family);
- iconify: COLLECTION (upstream project);
- synthetic-geometry: procedural, no family concept - id-hash split,
  recorded as such;
- local: entirely TEST (the closest thing to real loci in the corpus).

Deterministic greedy quota fill (70/15/15 within each source segment) over
sha-ordered units. Output: dataset/splits/family_disjoint/ next to the
shipped splits, plus a summary with rules, counts and family rosters.

Honest finding recorded: text_shapes carries only 21 font families while
the Stage-A probe saturates near ~600 - Stage A/B text data should be
REGENERATED from the google-fonts v2 bank before the full run.

Usage:
  C:\\Python312\\python.exe build_family_disjoint_splits.py
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

UBER = Path(r"C:\Users\nirrt\Toolset\v-ize train\dataset")
OUT = UBER / "splits" / "family_disjoint"
FRACTIONS = (("train", 0.70), ("calibration", 0.15), ("test", 0.15))

FACE_TO_FAMILY = {
    "arial": "arial", "arialbd": "arial", "ariali": "arial",
    "ariblk": "arial",
    "bahnschrift": "bahnschrift",
    "calibri": "calibri", "calibrib": "calibri", "calibril": "calibri",
    "cambria": "cambria", "cambriab": "cambria",
    "candara": "candara", "candarab": "candara",
    "consola": "consolas", "consolab": "consolas",
    "constan": "constantia", "constanb": "constantia",
    "corbel": "corbel", "corbelb": "corbel",
    "cour": "courier", "courbd": "courier",
    "framd": "franklin-gothic",
    "georgia": "georgia", "georgiab": "georgia",
    "impact": "impact",
    "leelauib": "leelawadee", "leelawui": "leelawadee",
    "malgun": "malgun", "malgunbd": "malgun",
    "micross": "ms-sans-serif",
    "pala": "palatino", "palab": "palatino",
    "segoeui": "segoe", "segoeuib": "segoe", "segoeuil": "segoe",
    "segoeuisl": "segoe", "seguisb": "segoe", "seguisym": "segoe",
    "tahoma": "tahoma", "tahomabd": "tahoma",
    "times": "times", "timesbd": "times",
    "trebuc": "trebuchet", "trebucbd": "trebuchet",
    "verdana": "verdana", "verdanab": "verdana",
}


def _unit_order(names) -> list[str]:
    return sorted(
        names,
        key=lambda name: hashlib.sha256(
            ("family-disjoint\0" + name).encode("utf-8")
        ).hexdigest(),
    )


def _assign_units(unit_sizes: dict[str, int]) -> dict[str, str]:
    total = sum(unit_sizes.values())
    quotas = {name: total * fraction for name, fraction in FRACTIONS}
    filled = {name: 0 for name, _fraction in FRACTIONS}
    assignment: dict[str, str] = {}
    for unit in _unit_order(unit_sizes):
        # Greedy: the split with the largest remaining relative deficit.
        target = max(
            (name for name, _f in FRACTIONS),
            key=lambda name: (quotas[name] - filled[name]) / max(1.0, quotas[name]),
        )
        assignment[unit] = target
        filled[target] += unit_sizes[unit]
    return assignment


def main() -> None:
    started = time.perf_counter()
    records: list[tuple[str, str, str]] = []  # (id, source, unit)
    with open(UBER / "full_corpus_with_text.jsonl", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            source = row.get("source")
            record_id = str(row["id"])
            if source == "synthetic-text":
                face = str(row.get("font", "unknown"))
                unit = "font:" + FACE_TO_FAMILY.get(face, f"face:{face}")
            elif source == "iconify":
                unit = "collection:" + str(row.get("collection", "unknown"))
            elif source == "synthetic-geometry":
                bucket = int(
                    hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:8],
                    16,
                ) % 100
                unit = (
                    "geohash:train" if bucket < 70 else
                    "geohash:calibration" if bucket < 85 else "geohash:test"
                )
            else:  # local
                unit = "local:all"
            records.append((record_id, source, unit))

    unit_sizes: dict[str, int] = {}
    for _record_id, source, unit in records:
        if unit.startswith(("geohash:", "local:")):
            continue
        unit_sizes[unit] = unit_sizes.get(unit, 0) + 1
    assignment = _assign_units(unit_sizes)
    assignment.update({
        "geohash:train": "train",
        "geohash:calibration": "calibration",
        "geohash:test": "test",
        "local:all": "test",
    })

    splits: dict[str, list[str]] = {name: [] for name, _f in FRACTIONS}
    per_source: dict[str, dict[str, int]] = {}
    for record_id, source, unit in records:
        split = assignment[unit]
        splits[split].append(record_id)
        per_source.setdefault(source, {}).setdefault(split, 0)
        per_source[source][split] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    for name, ids in splits.items():
        (OUT / f"{name}_ids.txt").write_text(
            "\n".join(ids) + "\n", encoding="utf-8",
        )
    rosters = {
        name: sorted(
            unit for unit, split in assignment.items()
            if split == name and not unit.startswith(("geohash:", "local:"))
        )
        for name, _f in FRACTIONS
    }
    summary = {
        "schema": "vice-family-disjoint-splits/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rules": {
            "synthetic-text": "font family (explicit 45-face -> 21-family map)",
            "iconify": "collection = upstream project",
            "synthetic-geometry": "procedural, id-hash 70/15/15 (no family)",
            "local": "entirely test",
        },
        "fractions": dict(FRACTIONS),
        "counts": {name: len(ids) for name, ids in splits.items()},
        "per_source": per_source,
        "unit_rosters": rosters,
        "honest_gap": (
            "text_shapes spans only 21 font families; the Stage-A probe "
            "saturates near ~600 - regenerate Stage A/B text data from the "
            "google-fonts v2 bank before the full run"
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8",
    )
    print(json.dumps({
        "counts": summary["counts"], "per_source": per_source,
    }, indent=1))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
