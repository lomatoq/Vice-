from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT))


def _suppress_native_crash_dialogs() -> None:
    """Let the parent server observe a crash instead of blocking on a WER dialog."""
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        current = int(kernel32.GetErrorMode())
        # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
        kernel32.SetErrorMode(current | 0x0001 | 0x0002 | 0x8000)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--result-json", required=True)
    parser.add_argument("--smoothing", required=True)
    parser.add_argument("--extractor", required=True)
    parser.add_argument("--route", default="auto")
    args = parser.parse_args()

    _suppress_native_crash_dialogs()
    result_path = Path(args.result_json)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.smoothing == "scene":
            from vice_scene.pipeline import process_scene

            report = process_scene(
                Path(args.input), Path(args.output_root), route=args.route
            )
        else:
            from geometry_vectorizer import process

            report = process(
                Path(args.input),
                Path(args.output_root),
                smoothing=args.smoothing,
                extractor=args.extractor,
                route=args.route,
            )
        payload = {"ok": True, "report": report}
        result_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return 0
    except BaseException as exc:
        payload = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}"[:1000],
            "traceback": traceback.format_exc(limit=20)[-8000:],
        }
        try:
            result_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
