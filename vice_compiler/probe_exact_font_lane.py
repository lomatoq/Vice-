"""Bounded real-corpus probe for the Phase-4 exact-font lane.

This probe is deliberately separate from the active blinded font-free court.
It measures OCR availability, strict exact-font admissions and end-to-end
source-only runtime without changing any human-review asset or answer.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
from typing import Iterable

import numpy as np

from .evidence_ir import EvidenceCache
from .exact_font_provider import ReirExactFontProvider
from .text_macros import generate_text_macros


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = (
    PROJECT / "benchmarks" / "pcdc_experiment4" / "exact_font_probe.json"
)


def _percentile(values: Iterable[float], value: float) -> float:
    rows = tuple(float(item) for item in values)
    return float(np.percentile(rows, value)) if rows else float("nan")


def probe(
    *, limit: int = 10, max_fonts: int = 4, top_k: int = 2,
    refine_rounds: int = 0, allow_upscale_ocr: bool = False,
) -> dict:
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    loci = [
        row for row in manifest["loci"]
        if row.get("semantic_class") == "text"
    ][:max(1, min(100, int(limit)))]
    cache = EvidenceCache()
    rows = []
    for locus in loci:
        reir, cache_hit = cache.get_or_build(locus["source"]["path"])
        started = time.perf_counter()
        provider = ReirExactFontProvider(
            reir, max_fonts=max_fonts, top_k=top_k,
            refine_rounds=refine_rounds,
            allow_upscale_ocr=allow_upscale_ocr,
        )
        provider_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        generated = generate_text_macros(
            reir, exact_font_provider=provider, max_line_proposals=9,
            validate_reir=False,
        )
        generation_ms = (time.perf_counter() - started) * 1000.0
        rows.append({
            "id": locus["id"],
            "cache_hit": bool(cache_hit),
            "processing_size": [reir.width, reir.height],
            "provider_ms": provider_ms,
            "generation_ms": generation_ms,
            "total_ms": provider_ms + generation_ms,
            "ocr_hints": [asdict(hint) for hint in provider.line_hints()],
            "proposals": [
                {
                    "id": proposal.id,
                    "roi_xyxy": list(proposal.roi_xyxy),
                    "score": proposal.score,
                    "sources": list(proposal.sources),
                }
                for proposal in generated.proposals
            ],
            "line_proposals": len(generated.proposals),
            "exact_font_attempted": generated.exact_font_attempted,
            "exact_font_admitted": generated.exact_font_admitted,
            "audits": [asdict(audit) for audit in provider.audits],
        })
    totals = [row["total_ms"] for row in rows]
    hints = sum(len(row["ocr_hints"]) for row in rows)
    attempts = sum(row["exact_font_attempted"] for row in rows)
    admissions = sum(row["exact_font_admitted"] for row in rows)
    return {
        "schema": "pcdc-experiment4-exact-font-probe/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection_blinding": "source-only; frozen reviews are never loaded",
        "configuration": {
            "limit": len(rows), "max_fonts": max_fonts, "top_k": top_k,
            "refine_rounds": refine_rounds,
            "allow_upscale_ocr": allow_upscale_ocr,
        },
        "metrics": {
            "rows": len(rows), "rows_with_ocr": sum(
                bool(row["ocr_hints"]) for row in rows
            ),
            "ocr_hints": hints,
            "exact_font_attempted": attempts,
            "exact_font_admitted": admissions,
            "admission_rate_per_attempt": admissions / max(1, attempts),
            "mean_ms": statistics.fmean(totals) if totals else float("nan"),
            "p50_ms": _percentile(totals, 50),
            "p95_ms": _percentile(totals, 95),
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-fonts", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--refine-rounds", type=int, default=0)
    parser.add_argument("--allow-upscale-ocr", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = probe(
        limit=args.limit, max_fonts=args.max_fonts, top_k=args.top_k,
        refine_rounds=args.refine_rounds,
        allow_upscale_ocr=args.allow_upscale_ocr,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
