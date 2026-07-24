"""Fast N2 contract checks for the deblur-4x joint-corner harness."""
from __future__ import annotations

import inspect

from eval_joint_corners import joint_corner_positions
from shadow_rf_corners import synth_counts_db4


def main() -> int:
    sig = inspect.signature(joint_corner_positions)
    assert sig.parameters["lattice_scale"].default == 1
    report = synth_counts_db4()
    if not report["pass"]:
        raise AssertionError(f"dp4x equivalence RED: {report}")
    print("dp4x equivalence PASS", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
