#!/usr/bin/env python3
"""Cross-platform launcher for the VAI web-preview UI.

Starts the local preview server and opens the browser so you can drop images
in and play with extractor / smoothing modes, exactly like before.

    python preview.py                 # serve on 8877 and open the browser
    python preview.py --port 9000      # different port
    python preview.py --no-browser     # just serve
    python preview.py --python PATH    # force the interpreter used for the server

This script itself only uses the standard library, so it runs under any Python
(Windows, macOS, Linux). It finds a separate interpreter that has the pipeline
dependencies (OpenCV, Pillow, NumPy; ideally also torch) to run the server.
On Windows use Start-Preview.ps1, on macOS start-preview.command — both just
call this file.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "web_preview" / "server.py"

# Hard requirements to import the pipeline; torch is only needed for the
# MiniNet / perceptual modes, so it is preferred but not mandatory.
REQUIRED = ("cv2", "PIL", "numpy")
PROBE = (
    "import cv2, PIL, numpy\n"
    "try:\n"
    "    import torch; print('TORCH')\n"
    "except Exception:\n"
    "    print('NOTORCH')\n"
)


def candidate_interpreters(override: str | None) -> list[str]:
    names: list[str] = []
    if override:
        names.append(override)
    if os.environ.get("PREVIEW_PYTHON"):
        names.append(os.environ["PREVIEW_PYTHON"])
    names.append(sys.executable)  # the interpreter running this script
    if os.name == "nt":
        names += [r"C:\Python312\python.exe", r"C:\Python311\python.exe", "python", "py"]
    else:
        names += [
            "python3",
            "/opt/homebrew/bin/python3",  # Apple-silicon Homebrew
            "/usr/local/bin/python3",     # Intel Homebrew
            "/usr/bin/python3",
            "python",
        ]
    return names


def probe(py: str) -> bool | None:
    """Return True/False (has torch) if `py` can import the pipeline, else None."""
    try:
        result = subprocess.run([py, "-c", PROBE], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return "TORCH" in result.stdout


def find_interpreter(override: str | None) -> tuple[str | None, bool]:
    seen: set[str] = set()
    with_required: tuple[str, bool] | None = None
    for name in candidate_interpreters(override):
        key = str(Path(name)) if os.path.sep in name or name.endswith(".exe") else name
        if key in seen:
            continue
        seen.add(key)
        has_torch = probe(name)
        if has_torch is None:
            continue
        if has_torch:
            return name, True  # best case: everything present
        if with_required is None:
            with_required = (name, False)
    return with_required if with_required else (None, False)


def _watched_files() -> list[Path]:
    """Python files whose change requires a server restart (the server caches
    imports at start; HTML/CSS/JS are read from disk per request, so not here)."""
    return list(ROOT.glob("*.py")) + list((ROOT / "web_preview").glob("*.py"))


def _snapshot() -> dict[Path, float]:
    snap: dict[Path, float] = {}
    for path in _watched_files():
        try:
            snap[path] = path.stat().st_mtime
        except OSError:
            pass
    return snap


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the VAI web-preview UI.")
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--no-reload", action="store_true", help="do not auto-restart the server when a .py file changes")
    parser.add_argument("--python", help="interpreter to run the server with (needs cv2/PIL/numpy, ideally torch)")
    args = parser.parse_args()

    try:  # never let a non-ASCII status line crash the launcher on a cp1252 console
        sys.stdout.reconfigure(errors="replace", line_buffering=True)
    except Exception:
        pass

    if not SERVER.is_file():
        sys.exit(f"Server not found: {SERVER}")

    python, has_torch = find_interpreter(args.python)
    if python is None:
        sys.exit(
            "No Python with the pipeline dependencies was found.\n"
            "Install them into a Python and pass it via --python or $PREVIEW_PYTHON:\n"
            "    pip install torch opencv-python pillow numpy"
        )
    if not has_torch:
        print("! Note: torch not found in that interpreter — palette mode works, but MiniNet / perceptual will error.")

    url = f"http://127.0.0.1:{args.port}"
    print(f"VAI preview UI: {url}")
    print(f"(server interpreter: {python})")
    print("Press Ctrl+C to stop." if args.no_reload
          else "Auto-reload ON - editing any .py restarts the server automatically. Ctrl+C to stop.")

    if not args.no_browser:
        # Open once the server has had a moment to bind the port.
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    command = [python, str(SERVER), "--port", str(args.port)]
    if args.no_reload:
        try:
            subprocess.run(command)
        except KeyboardInterrupt:
            print("\nStopped.")
        return

    proc = subprocess.Popen(command)
    snapshot = _snapshot()
    try:
        while True:
            time.sleep(1.0)
            if proc.poll() is not None:
                print("Server exited.")
                return
            current = _snapshot()
            changed = sorted(p.name for p in set(current) | set(snapshot) if current.get(p) != snapshot.get(p))
            if changed:
                print(f"[reload] {', '.join(changed)} changed - restarting server...")
                _stop(proc)
                proc = subprocess.Popen(command)
                snapshot = _snapshot()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        _stop(proc)
    print("Stopped.")


if __name__ == "__main__":
    main()
