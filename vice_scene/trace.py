"""Complete decision provenance for scene construction and ablations."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DecisionRecord:
    sequence: int
    stage: str
    action: str
    accepted: bool
    reason: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    score_before: float | None = None
    score_after: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


class DecisionTrace:
    def __init__(self, source_hash: str, config_hash: str) -> None:
        self.source_hash = source_hash
        self.config_hash = config_hash
        self.started_monotonic = time.perf_counter()
        self.records: list[DecisionRecord] = []
        self.stage_seconds: dict[str, float] = {}

    def add(self, stage: str, action: str, *, accepted: bool = True,
            reason: str = "", inputs: tuple[str, ...] = (),
            outputs: tuple[str, ...] = (), score_before: float | None = None,
            score_after: float | None = None, **details: Any) -> DecisionRecord:
        record = DecisionRecord(
            sequence=len(self.records), stage=stage, action=action,
            accepted=accepted, reason=reason, inputs=inputs, outputs=outputs,
            score_before=score_before, score_after=score_after, details=details,
        )
        self.records.append(record)
        return record

    def account(self, stage: str, seconds: float) -> None:
        self.stage_seconds[stage] = self.stage_seconds.get(stage, 0.0) + float(seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "vice-decision-trace/1",
            "source_hash": self.source_hash,
            "config_hash": self.config_hash,
            "elapsed_seconds": time.perf_counter() - self.started_monotonic,
            "stage_seconds": dict(sorted(self.stage_seconds.items())),
            "records": [asdict(item) for item in self.records],
        }

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2,
                                   sort_keys=True, allow_nan=False) + "\n",
                        encoding="utf-8")


class timed_stage:
    def __init__(self, trace: DecisionTrace, stage: str) -> None:
        self.trace = trace
        self.stage = stage
        self.started = 0.0

    def __enter__(self) -> "timed_stage":
        self.started = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.trace.account(self.stage, time.perf_counter() - self.started)
