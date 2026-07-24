"""Deterministic source-stratum replay weights for ProposalNet training."""

from __future__ import annotations

import numpy as np


def rebalance_source_share(
    rows: list[dict], weights: np.ndarray, *, source: str, share: float,
) -> np.ndarray:
    """Make ``source`` carry the requested expected sampler mass.

    Existing within-source weights are preserved, so rare-family and degraded
    example emphasis remains intact.  The function uses no held-out outcomes.
    """
    result = np.asarray(weights, np.float64).copy()
    if len(rows) != len(result) or np.any(~np.isfinite(result)) or np.any(result <= 0):
        raise ValueError("replay weights must be positive and aligned with rows")
    if not 0.0 < float(share) < 1.0:
        raise ValueError("replay share must be strictly between zero and one")
    selected = np.asarray([
        str(row.get("source", "")) == str(source) for row in rows
    ], bool)
    if not np.any(selected) or np.all(selected):
        raise ValueError("replay rebalance requires both source strata")
    selected_mass = float(np.sum(result[selected]))
    other_mass = float(np.sum(result[~selected]))
    factor = (float(share) / (1.0 - float(share))) * other_mass / selected_mass
    result[selected] *= factor
    return result


def expected_source_share(
    rows: list[dict], weights: np.ndarray, *, source: str,
) -> float:
    values = np.asarray(weights, np.float64)
    selected = np.asarray([
        str(row.get("source", "")) == str(source) for row in rows
    ], bool)
    return float(np.sum(values[selected]) / np.sum(values))


def rebalance_source_shares(
    rows: list[dict], weights: np.ndarray, *, shares: dict[str, float],
) -> np.ndarray:
    """Set several source masses at once and leave the remainder for replay."""
    result = np.asarray(weights, np.float64).copy()
    if len(rows) != len(result) or np.any(~np.isfinite(result)) or np.any(result <= 0):
        raise ValueError("replay weights must be positive and aligned with rows")
    requested = {str(source): float(share) for source, share in shares.items()}
    if (
        not requested or any(not 0.0 < share < 1.0 for share in requested.values())
        or sum(requested.values()) >= 1.0
    ):
        raise ValueError("requested source shares must leave positive replay mass")
    source_values = np.asarray([str(row.get("source", "")) for row in rows])
    selected_union = np.zeros(len(rows), bool)
    masks: dict[str, np.ndarray] = {}
    for source in requested:
        mask = source_values == source
        if not np.any(mask):
            raise ValueError(f"requested replay source is absent: {source}")
        masks[source] = mask
        selected_union |= mask
    remainder = ~selected_union
    if not np.any(remainder):
        raise ValueError("requested replay shares leave no baseline rows")
    remainder_share = 1.0 - sum(requested.values())
    remainder_mass = float(np.sum(result[remainder]))
    result[remainder] *= remainder_share / remainder_mass
    for source, share in requested.items():
        mass = float(np.sum(result[masks[source]]))
        result[masks[source]] *= share / mass
    return result
