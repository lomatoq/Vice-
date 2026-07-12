"""Run benchmark_stages with text-safe/tiny-safe profile overrides (A/B driver)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import geometry_vectorizer as gv

gv._PAPER_FIT_PROFILE = "text-safe"
gv._CORNER_POSTPROCESS_POLICY = "tiny-safe"
print(f"OVERRIDES: fit_profile={gv._PAPER_FIT_PROFILE} corner_policy={gv._CORNER_POSTPROCESS_POLICY}")

sys.argv = ["benchmark_stages.py", "--fast"]
exec(compile(Path("benchmark_stages.py").read_text(encoding="utf-8"),
             "benchmark_stages.py", "exec"))
