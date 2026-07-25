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


def _run_pcdc(
    input_path: Path, output_root: Path, *, materialization_v2: bool,
) -> dict:
    """Run the PCDC compiler and publish the interface's asset triple.

    The upload UI already knows how to show 01_contour.png,
    02_primitive_map.svg and 03_rebuilt_filled.svg, so the PCDC lane
    writes exactly those instead of growing a second interface.
    """
    import io as _io
    import re as _re
    import time as _time

    os.environ["VICE_TEXT_MATERIALIZATION_V2"] = (
        "1" if materialization_v2 else "0"
    )
    from PIL import Image

    from vice_compiler.export_writer import scene_to_svg
    from vice_compiler.runtime_service import PersistentCompilerService

    output = output_root / input_path.stem
    output.mkdir(parents=True, exist_ok=True)
    service = PersistentCompilerService()
    started = _time.perf_counter()
    try:
        result = service.compile(input_path, mode="balanced")
        document, native, fallback = scene_to_svg(
            result.reir, result.cmir, result.visible_scene,
            phase5_bundle=result.phase5_bundle,
            text_macros=result.text_macros,
            layered_scene=result.layered_scene,
            design_program=result.design_program,
        )
    finally:
        close = getattr(service, "close", None)
        if callable(close):
            close()
    elapsed_ms = (_time.perf_counter() - started) * 1000.0

    (output / "03_rebuilt_filled.svg").write_text(document, encoding="utf-8")
    (output / "02_primitive_map.svg").write_text(document, encoding="utf-8")
    try:
        import resvg_py

        payload = resvg_py.svg_to_bytes(
            svg_string=document, width=int(result.reir.width),
        )
        with _io.BytesIO(bytes(payload)) as stream:
            with Image.open(stream) as rendered:
                rendered.convert("RGBA").save(output / "01_contour.png")
    except Exception:
        with Image.open(input_path) as image:
            image.convert("RGBA").save(output / "01_contour.png")

    families = sorted(set(_re.findall(
        r'data-pcdc-text-geometry="([^"]+)"', document,
    )))
    commands = sum(document.count(letter) for letter in "MLCAHVQSTZ")
    return {
        "schema": "vice-pcdc-preview/1",
        "engine": "pcdc",
        "materialization_v2": bool(materialization_v2),
        "actual": {
            "path commands": commands,
            "native macros": int(native),
            "fallbacks": int(fallback),
            "ms": int(elapsed_ms),
        },
        "templates": {
            "text geometry": ", ".join(families) if families else "—",
            "mode": "balanced",
        },
        "text_geometry_families": families,
        "warnings": list(result.warnings),
    }


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
        if args.smoothing in ("pcdc", "pcdc-v2"):
            report = _run_pcdc(
                Path(args.input), Path(args.output_root),
                materialization_v2=args.smoothing == "pcdc-v2",
            )
        elif args.smoothing == "scene":
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
