"""Named-stage profiling and hard runtime-budget accounting for PCDC.

The profiler is deliberately independent from any compiler stage so every
future implementation can use the same wall/CPU/memory schema.  A stage is
always recorded, including when it raises, which prevents failed or timed-out
items from disappearing from benchmark summaries.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import threading
import time
import tracemalloc
from typing import Any, Iterator


@dataclass(frozen=True)
class StageBudget:
    wall_ms: float | None = None
    peak_python_bytes: int | None = None


@dataclass(frozen=True)
class StageRecord:
    name: str
    wall_ms: float
    cpu_ms: float
    peak_python_bytes: int
    ok: bool
    budget_ok: bool
    error: str | None = None
    metadata: dict[str, Any] | None = None


class StageProfiler:
    """Thread-safe append-only profiler with optional per-stage hard budgets."""

    def __init__(
        self,
        budgets: dict[str, StageBudget] | None = None,
        *,
        track_python_memory: bool = False,
    ) -> None:
        self.budgets = dict(budgets or {})
        self.track_python_memory = bool(track_python_memory)
        self.records: list[StageRecord] = []
        self._lock = threading.RLock()

    @contextmanager
    def stage(self, name: str, **metadata: Any) -> Iterator[None]:
        if not name or not isinstance(name, str):
            raise ValueError("stage name must be a non-empty string")
        already_tracing = tracemalloc.is_tracing()
        started_tracing = self.track_python_memory and not already_tracing
        if started_tracing:
            tracemalloc.start()
        if self.track_python_memory or already_tracing:
            before_current, before_peak = tracemalloc.get_traced_memory()
        else:
            before_current = before_peak = 0
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        error: BaseException | None = None
        try:
            yield
        except BaseException as exc:
            error = exc
            raise
        finally:
            wall_ms = (time.perf_counter() - wall_start) * 1000.0
            cpu_ms = (time.process_time() - cpu_start) * 1000.0
            if self.track_python_memory or already_tracing:
                current, peak = tracemalloc.get_traced_memory()
                peak_delta = max(0, peak - max(before_current, before_peak))
            else:
                peak_delta = 0
            if started_tracing:
                tracemalloc.stop()
            budget = self.budgets.get(name, StageBudget())
            budget_ok = (
                (budget.wall_ms is None or wall_ms <= budget.wall_ms)
                and (
                    budget.peak_python_bytes is None
                    or peak_delta <= budget.peak_python_bytes
                )
            )
            record = StageRecord(
                name=name,
                wall_ms=round(wall_ms, 4),
                cpu_ms=round(cpu_ms, 4),
                peak_python_bytes=peak_delta,
                ok=error is None,
                budget_ok=budget_ok,
                error=(
                    None
                    if error is None
                    else f"{type(error).__name__}: {error}"[:1500]
                ),
                metadata=dict(metadata) or None,
            )
            with self._lock:
                self.records.append(record)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            records = list(self.records)
        by_stage: dict[str, dict[str, Any]] = {}
        for record in records:
            aggregate = by_stage.setdefault(
                record.name,
                {
                    "count": 0,
                    "failures": 0,
                    "budget_failures": 0,
                    "wall_ms_total": 0.0,
                    "wall_ms_max": 0.0,
                    "cpu_ms_total": 0.0,
                    "peak_python_bytes_max": 0,
                },
            )
            aggregate["count"] += 1
            aggregate["failures"] += int(not record.ok)
            aggregate["budget_failures"] += int(not record.budget_ok)
            aggregate["wall_ms_total"] += record.wall_ms
            aggregate["wall_ms_max"] = max(
                aggregate["wall_ms_max"], record.wall_ms
            )
            aggregate["cpu_ms_total"] += record.cpu_ms
            aggregate["peak_python_bytes_max"] = max(
                aggregate["peak_python_bytes_max"], record.peak_python_bytes
            )
        for aggregate in by_stage.values():
            count = max(1, int(aggregate["count"]))
            aggregate["wall_ms_mean"] = round(
                aggregate["wall_ms_total"] / count, 4
            )
            aggregate["cpu_ms_mean"] = round(
                aggregate["cpu_ms_total"] / count, 4
            )
            aggregate["wall_ms_total"] = round(
                aggregate["wall_ms_total"], 4
            )
            aggregate["cpu_ms_total"] = round(
                aggregate["cpu_ms_total"], 4
            )
        return {
            "schema": "pcdc-stage-profile/v1",
            "complete": all(r.ok and r.budget_ok for r in records),
            "record_count": len(records),
            "by_stage": by_stage,
            "records": [asdict(record) for record in records],
        }

    def write_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.summary(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return target
