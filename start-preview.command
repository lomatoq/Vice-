#!/bin/bash
# Launch the VAI web-preview UI on macOS / Linux.
# On macOS you can double-click this file (make it executable once with:
#   chmod +x start-preview.command). It runs preview.py, which starts the
# server and opens your browser. preview.py needs any python3; the pipeline
# itself needs cv2 + Pillow + numpy (and torch for MiniNet/perceptual).
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "No python found. Install Python 3.10+ (e.g. 'brew install python')." >&2
    exit 1
fi

exec "$PY" preview.py "$@"
