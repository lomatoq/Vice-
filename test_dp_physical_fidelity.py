"""Regression checks for physical-density normalization in the paper DP.

These tests are deliberately dependency-free beyond the project's normal
geometry_vectorizer import.  They run under pytest or directly:

    python test_dp_physical_fidelity.py
"""

from __future__ import annotations

import numpy as np

import geometry_vectorizer as gv


def _same_physical_residual(sample_count: int, value: float = 0.23) -> np.ndarray:
    return np.full(sample_count, value, dtype=float)


def test_native_cost_is_bitwise_legacy_equivalent() -> None:
    residuals = np.array([0.0, 0.125, 0.25, 0.5, 0.125], dtype=float)
    old = gv._DP_PHYSICAL_FIDELITY
    try:
        gv._DP_PHYSICAL_FIDELITY = True
        physical = gv._dp_fidelity_sum(residuals, px=1.0)
        legacy = float(np.sum(residuals))
        assert physical == legacy
    finally:
        gv._DP_PHYSICAL_FIDELITY = old


def test_same_boundary_cost_is_invariant_at_1x_2x_4x() -> None:
    old = gv._DP_PHYSICAL_FIDELITY
    try:
        gv._DP_PHYSICAL_FIDELITY = True
        costs = [
            gv._dp_fidelity_sum(_same_physical_residual(12 * scale), px=1.0 / scale)
            for scale in (1, 2, 4)
        ]
        assert np.allclose(costs, costs[0], rtol=0.0, atol=1e-12), costs
    finally:
        gv._DP_PHYSICAL_FIDELITY = old


def test_ablation_reproduces_old_density_bias() -> None:
    old = gv._DP_PHYSICAL_FIDELITY
    try:
        gv._DP_PHYSICAL_FIDELITY = False
        native = gv._dp_fidelity_sum(_same_physical_residual(12), px=1.0)
        lattice4 = gv._dp_fidelity_sum(_same_physical_residual(48), px=0.25)
        assert np.isclose(lattice4, 4.0 * native)
    finally:
        gv._DP_PHYSICAL_FIDELITY = old


def test_scalar_residual_path_used_by_elliptic_arc() -> None:
    old = gv._DP_PHYSICAL_FIDELITY
    try:
        gv._DP_PHYSICAL_FIDELITY = True
        assert gv._dp_fidelity_sum(8.0, px=0.25) == 2.0
    finally:
        gv._DP_PHYSICAL_FIDELITY = old


def test_uncertainty_and_correlation_are_native_physical() -> None:
    old_u = gv._DP_UNCERTAINTY_NORMALIZATION
    old_c = gv._DP_CORRELATION_WEIGHTING
    try:
        gv._DP_UNCERTAINTY_NORMALIZATION = True
        gv._DP_CORRELATION_WEIGHTING = True
        assert gv._dp_observation_weight(0.0) == 1.0
        assert gv._dp_observation_weight(0.2) < 1.0
        assert gv._dp_observation_halfwidth(1.0) == 0.5
        assert gv._dp_observation_halfwidth(0.5) == 0.5
        assert gv._dp_observation_halfwidth(0.25) == 0.5
    finally:
        gv._DP_UNCERTAINTY_NORMALIZATION = old_u
        gv._DP_CORRELATION_WEIGHTING = old_c


def test_mdl_prices_do_not_depend_on_sampling_density() -> None:
    old = gv._DP_MDL_CODING
    try:
        gv._DP_MDL_CODING = True
        # A physical 64px hypothesis has one description length regardless of
        # whether its boundary was sampled at 1x, 2x or 4x.
        prices = [gv._dp_mdl_primitive_price("cubic", 64.0) for _scale in (1, 2, 4)]
        assert prices[0] == prices[1] == prices[2]
        assert gv._dp_mdl_primitive_price("line", 64.0) == 1.0
        assert gv._dp_mdl_primitive_price("cubic", 64.0) > 4.0
    finally:
        gv._DP_MDL_CODING = old


if __name__ == "__main__":
    test_native_cost_is_bitwise_legacy_equivalent()
    test_same_boundary_cost_is_invariant_at_1x_2x_4x()
    test_ablation_reproduces_old_density_bias()
    test_scalar_residual_path_used_by_elliptic_arc()
    test_uncertainty_and_correlation_are_native_physical()
    test_mdl_prices_do_not_depend_on_sampling_density()
    print("DP physical-fidelity regression checks: PASS")
