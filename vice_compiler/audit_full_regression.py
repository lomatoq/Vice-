"""Run and bind the complete unittest regression gate to compiler sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .build_identity import compiler_source_sha256, native_runtime_identity

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_pre_v14" / "full_tests.json"


def regression_suite_source_sha256() -> str:
    """Bind the runner and every test module discovered from the project root."""
    digest = hashlib.sha256(b"pcdc-full-regression-source/v1\0")
    paths = (Path(__file__).resolve(), *sorted(PROJECT.glob("test*.py")))
    for path in paths:
        digest.update(path.relative_to(PROJECT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_report() -> dict:
    started = time.perf_counter()
    process = subprocess.run(
        [sys.executable, "-m", "unittest", "discover"],
        cwd=PROJECT, text=True, capture_output=True, check=False,
    )
    output = process.stdout + process.stderr
    match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    tests_run = int(match.group(1)) if match else 0
    passed = process.returncode == 0 and tests_run > 0 and "OK" in output
    return {
        "schema": "pcdc-full-regression-suite/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_source_sha256": compiler_source_sha256(),
        "evaluation_source_sha256": regression_suite_source_sha256(),
        "native_runtime_identity": native_runtime_identity(),
        "passed": passed,
        "tests_run": tests_run,
        "return_code": process.returncode,
        "elapsed_seconds": time.perf_counter() - started,
        "command": [sys.executable, "-m", "unittest", "discover"],
        "output_tail": output[-4000:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    print(json.dumps({
        "passed": report["passed"], "tests_run": report["tests_run"],
        "out": str(args.out.resolve()),
    }, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
