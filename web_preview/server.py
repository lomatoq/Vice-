from __future__ import annotations

import base64
import argparse
import json
import mimetypes
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
RESULTS = ROOT / "results"
UPLOADS = ROOT / "uploads"
DATASET_PREVIEWS = PROJECT / "test_runs"
sys.path.insert(0, str(PROJECT))


def safe_name(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower() or ".png"
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stem).strip("._") or "image"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        suffix = ".png"
    return stem + suffix


class Handler(BaseHTTPRequestHandler):
    server_version = "VAI-Preview/1.0"

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/corner-review":
            dataset = parse_qs(parsed.query).get("dataset", [""])[0]
            if not re.fullmatch(r"[a-zA-Z0-9_.-]+", dataset):
                self.send_json({"error": "Invalid dataset"}, 400)
                return
            target = (PROJECT / "datasets" / dataset / "review.json").resolve()
            datasets = (PROJECT / "datasets").resolve()
            if datasets not in target.parents:
                self.send_json({"error": "Invalid dataset path"}, 400)
            elif target.is_file():
                self.send_json(json.loads(target.read_text(encoding="utf-8")))
            else:
                self.send_json({})
            return
        if path.startswith("/results/"):
            relative = Path(unquote(path.removeprefix("/results/")))
            target = (RESULTS / relative).resolve()
            if RESULTS.resolve() not in target.parents or not target.is_file():
                self.send_error(404)
                return
            self.send_file(target)
            return
        if path.startswith("/dataset-preview/"):
            relative = Path(unquote(path.removeprefix("/dataset-preview/")))
            target = (DATASET_PREVIEWS / relative).resolve()
            base = DATASET_PREVIEWS.resolve()
            if target.is_dir():
                target = (target / "index.html").resolve()
            if base not in target.parents or not target.is_file():
                self.send_error(404)
                return
            self.send_file(target)
            return
        target = ROOT / ("index.html" if path == "/" else unquote(path.lstrip("/")))
        target = target.resolve()
        if target.is_dir():
            target = (target / "index.html").resolve()
        if ROOT.resolve() not in target.parents and target != ROOT.resolve():
            self.send_error(403)
        elif target.is_file():
            self.send_file(target)
        else:
            self.send_error(404)

    def send_file(self, target: Path) -> None:
        body = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/corner-review":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 10 * 1024 * 1024:
                    raise ValueError("Review is too large")
                payload = json.loads(self.rfile.read(length))
                dataset = str(payload.get("dataset", ""))
                if not re.fullmatch(r"[a-zA-Z0-9_.-]+", dataset):
                    raise ValueError("Invalid dataset")
                target = (PROJECT / "datasets" / dataset / "review.json").resolve()
                datasets = (PROJECT / "datasets").resolve()
                if datasets not in target.parents or not target.parent.is_dir():
                    raise ValueError("Unknown dataset")
                clean = {
                    "dataset": dataset,
                    "decisions": payload.get("decisions", {}),
                    "corrections": payload.get("corrections", {}),
                    "edges": payload.get("edges", {}),
                    "updated_at": payload.get("updated_at"),
                }
                target.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
                self.send_json({"ok": True, "path": str(target)})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path != "/api/process":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 25 * 1024 * 1024:
                raise ValueError("Файл слишком большой (максимум 25 MB)")
            payload = json.loads(self.rfile.read(length))
            filename = safe_name(payload["filename"])
            smoothing = payload.get("smoothing", "cad")
            extractor = payload.get("extractor", "mininet")
            if smoothing not in {"none", "corner", "chaikin", "bspline", "cad", "uncertainty", "perceptual", "perceptual-icm", "perceptual-merge", "paper", "paper-native", "paper-perc", "paper-perres", "paper-regions"}:
                raise ValueError("Unknown contour interpolation mode")
            if extractor not in {"palette", "mininet"}:
                raise ValueError("Unknown contour extractor")
            encoded = payload["data"].split(",", 1)[-1]
            data = base64.b64decode(encoded, validate=True)
            UPLOADS.mkdir(parents=True, exist_ok=True)
            RESULTS.mkdir(parents=True, exist_ok=True)
            upload = UPLOADS / filename
            upload.write_bytes(data)
            # Keep dataset/report browsing lightweight.  The vectorizer (and
            # its Torch models) is only needed for an actual processing POST.
            from geometry_vectorizer import process

            report = process(upload, RESULTS, smoothing=smoothing, extractor=extractor)
            stem = upload.stem
            base = f"/results/{stem}"
            assets = {
                "contour": f"{base}/01_contour.png",
                "primitiveMap": f"{base}/02_primitive_map.svg",
                "rebuilt": f"{base}/03_rebuilt_filled.svg",
            }
            if (RESULTS / stem / "04_corners.png").exists():
                assets["corners"] = f"{base}/04_corners.png"
            self.send_json({"report": report, "assets": assets})
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()
    host, port = "127.0.0.1", args.port
    print(f"VAI preview: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
