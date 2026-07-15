"""D2 320-tree confirmation of the step-2 verdict on the PROMOTED models.

Runs the identical step-2 protocol (v2 data, position scoring, same folds)
at the production tree count for only A (reference), C_q30 (candidate for
the 64/128 buckets) and C_db4 (candidate for the deblur-4x lane), skipping
res 32 (verdict there: augments buy nothing, bucket stays on the current
model).  CRITERION: the 160-tree deltas must reproduce within +-0.01.
Output: benchmarks/retrain_rf_step3_confirm.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import retrain_corner_rf_step2 as s2  # noqa: E402

s2.TREES = 320
s2.OUT_JSON = ROOT / "benchmarks" / "retrain_rf_step3_confirm.json"
s2.MODEL_DEFS = {"A": ("orig",), "C_q30": ("orig", "q30"),
                 "C_db4": ("orig", "db4")}
s2.RES_LIST = (64, 128)

if __name__ == "__main__":
    sys.exit(s2.main())
