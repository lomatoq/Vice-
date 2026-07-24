"""Fail-closed row contracts shared by ProposalNet data factories/training."""

from __future__ import annotations


EXPLICIT_OWNER_SCHEMA = "explicit-svg-groups/v1"
TYPED_GENERATOR_SCHEMA = "typed-generator/v1"
TYPED_STRUCTURE_FAMILIES = frozenset({
    "stroke_network", "appearance_model", "layer_relation",
    "symmetry_repeat_group",
})


def uses_explicit_owner_labels(row: dict) -> bool:
    contract = row.get("owner_contract")
    return bool(
        isinstance(contract, dict)
        and contract.get("schema") == EXPLICIT_OWNER_SCHEMA
        and isinstance(contract.get("owner_ids"), list)
        and contract["owner_ids"]
        and len(contract["owner_ids"]) == len(set(contract["owner_ids"]))
    )


def typed_macro_families(row: dict) -> tuple[str, ...] | None:
    if str(row.get("source", "")) != "synthetic-structure-v2":
        return None
    contract = row.get("macro_family_contract")
    if not isinstance(contract, dict) or contract.get("schema") != TYPED_GENERATOR_SCHEMA:
        raise ValueError("typed structure row lacks its family contract")
    raw = contract.get("families")
    if not isinstance(raw, list) or len(raw) != 1:
        raise ValueError("typed structure row must declare exactly one family")
    family = str(raw[0])
    if family not in TYPED_STRUCTURE_FAMILIES:
        raise ValueError("typed structure row declares an unsupported family")
    return (family,)


def split_group(row: dict) -> str:
    """Return the strongest known data-leakage boundary for one pair."""
    source = str(row.get("source", ""))
    source_id = str(row.get("source_id", ""))
    parts = source_id.split(":")
    if source == "synthetic-open-text":
        family = str(row.get("font_family", "")).strip()
        font_sha = str(row.get("font_sha256", "")).strip()
        if not family or len(font_sha) != 64 or not uses_explicit_owner_labels(row):
            raise ValueError("open-text row lacks font or owner identity")
        return f"font-family:{family}"
    if source == "synthetic-structure-v2":
        typed_macro_families(row)
        if not source_id:
            raise ValueError("typed structure row lacks source identity")
        return f"typed-structure-source:{source_id}"
    if source == "synthetic-text" and len(parts) >= 2:
        return f"font-family:{parts[1]}"
    if source == "iconify":
        return f"icon-library:{row.get('collection', 'unknown')}"
    if source == "local" and parts:
        return f"local-asset-family:{parts[-1]}"
    if not source_id:
        raise ValueError("proposal pair lacks source identity")
    return f"source-asset:{source_id}"
