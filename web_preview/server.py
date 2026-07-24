from __future__ import annotations

import base64
import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT))

from vice_compiler.proposal_real_labels import PROPOSAL_FAMILIES  # noqa: E402
from vice_compiler.proposal_data_contract import (  # noqa: E402
    RELATION_CONTRACT_SCHEMA, RELATION_TYPES,
)

RESULTS = ROOT / "results"
UPLOADS = ROOT / "uploads"
DATASET_PREVIEWS = PROJECT / "test_runs"
LOCUS_CORPUS = Path(os.environ.get(
    "V_ICE_LOCUS_CORPUS",
    str(PROJECT / "datasets" / "pcdc_real_loci_v1"),
)).resolve()
CERTIFICATE_CORPUS = PROJECT / "datasets" / "pcdc_certificate_pairs_v1"
TEXTLINE_CORPUS = PROJECT / "datasets" / "pcdc_textline_pairs_v1"
TEXTLINE_EXACT_CORPUS = PROJECT / "datasets" / "pcdc_textline_pairs_v2"
PHASE12_BLIND_ROOT = (
    PROJECT / "benchmarks" / "pcdc_experiment12" / "blind_vai_court"
)
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.RLock()
# One native-heavy worker at a time: concurrent Torch/OpenCV jobs were the
# source of memory pressure and opaque browser-level "Failed to fetch" errors.
JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vice-job")


def _job_snapshot(job_id: str) -> dict | None:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None
        return {key: value for key, value in job.items()
                if key not in {"process", "future", "upload", "job_root"}}


def _update_job(job_id: str, **values) -> None:
    with JOB_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(values)
            JOBS[job_id]["updated_at"] = time.time()


def _execute_job(job_id: str) -> None:
    with JOB_LOCK:
        job = JOBS[job_id]
        if job.get("cancel_requested"):
            job.update(status="cancelled", progress=1.0, updated_at=time.time())
            return
        upload = Path(job["upload"])
        job_root = Path(job["job_root"])
        smoothing = job["smoothing"]
        extractor = job["extractor"]
        route = job["route"]
        job.update(status="running", progress=.08, started_at=time.time(),
                   updated_at=time.time())

    result_json = job_root / "worker-result.json"
    worker = ROOT / "worker.py"
    command = [
        sys.executable, str(worker), "--input", str(upload),
        "--output-root", str(job_root), "--result-json", str(result_json),
        "--smoothing", smoothing, "--extractor", extractor, "--route", route,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    time_limit = 45 if smoothing == "cad" else 180
    stdout_path = job_root / "worker.stdout.log"
    stderr_path = job_root / "worker.stderr.log"
    try:
        job_root.mkdir(parents=True, exist_ok=True)
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
                "w", encoding="utf-8") as stderr:
            process = subprocess.Popen(
                command, cwd=PROJECT, stdout=stdout, stderr=stderr,
                text=True, creationflags=creationflags,
            )
            with JOB_LOCK:
                JOBS[job_id]["process"] = process
            deadline = time.monotonic() + time_limit
            while process.poll() is None:
                with JOB_LOCK:
                    cancelled = bool(JOBS[job_id].get("cancel_requested"))
                if cancelled:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    _update_job(job_id, status="cancelled", progress=1.0,
                                finished_at=time.time())
                    return
                if time.monotonic() >= deadline:
                    process.kill()
                    process.wait(timeout=5)
                    raise RuntimeError(
                        f"Resource gate: {smoothing} exceeded {time_limit} seconds")
                time.sleep(.2)
        payload = None
        if result_json.is_file():
            try:
                payload = json.loads(result_json.read_text(encoding="utf-8"))
            except Exception:
                payload = None
        if process.returncode != 0 or not payload or not payload.get("ok"):
            detail = (payload or {}).get("error")
            if not detail and stderr_path.is_file():
                detail = stderr_path.read_text(encoding="utf-8", errors="replace")[-1200:].strip()
            raise RuntimeError(detail or f"Worker exited with code {process.returncode}")

        staged = job_root / upload.stem
        if not staged.is_dir():
            raise RuntimeError("Worker completed without SVG assets")
        _update_job(job_id, status="publishing", progress=.94)
        RESULTS.mkdir(parents=True, exist_ok=True)
        result_key = f"{upload.stem}-{job_id[:10]}"
        published = RESULTS / result_key
        # Unique destination + same-volume rename gives atomic publication.
        staged.replace(published)
        base = f"/results/{result_key}"
        assets = {
            "contour": f"{base}/01_contour.png",
            "primitiveMap": f"{base}/02_primitive_map.svg",
            "rebuilt": f"{base}/03_rebuilt_filled.svg",
        }
        if (published / "04_corners.png").exists():
            assets["corners"] = f"{base}/04_corners.png"
        _update_job(job_id, status="completed", progress=1.0,
                    report=payload["report"], assets=assets,
                    result_key=result_key, finished_at=time.time())
    except BaseException as exc:
        _update_job(job_id, status="failed", progress=1.0,
                    error=f"{type(exc).__name__}: {exc}"[:1500],
                    finished_at=time.time())
    finally:
        with JOB_LOCK:
            if job_id in JOBS:
                JOBS[job_id].pop("process", None)
        shutil.rmtree(job_root, ignore_errors=True)
        shutil.rmtree(upload.parent, ignore_errors=True)


def safe_name(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower() or ".png"
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stem).strip("._") or "image"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        suffix = ".png"
    return stem + suffix


def _locus_payload() -> tuple[dict, dict]:
    manifest_path = LOCUS_CORPUS / "manifest.json"
    review_path = LOCUS_CORPUS / "review.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "PCDC corpus is not built; run python -m vice_compiler.locus_corpus"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = (
        json.loads(review_path.read_text(encoding="utf-8"))
        if review_path.is_file()
        else {"schema": "pcdc-real-locus-review/v1", "reviews": {}}
    )
    return manifest, review


def _locus_index() -> dict[str, dict]:
    manifest, _review = _locus_payload()
    return {
        str(row["id"]): row
        for row in manifest.get("loci", [])
        if isinstance(row, dict) and row.get("id")
    }


def _certificate_review_payload() -> tuple[dict, dict]:
    manifest_path = CERTIFICATE_CORPUS / "human_manifest.json"
    review_path = CERTIFICATE_CORPUS / "review.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "Certificate court is not built; run "
            "python -m vice_compiler.build_certificate_review"
        )
    private = json.loads(manifest_path.read_text(encoding="utf-8"))
    public = dict(private)
    public["cases"] = [
        {key: value for key, value in row.items() if key != "correct_side"}
        for row in private.get("cases", [])
    ]
    public["blind_contract"] = "construction labels withheld by server"
    review = (
        json.loads(review_path.read_text(encoding="utf-8"))
        if review_path.is_file()
        else {
            "schema": "pcdc-certificate-human-review/v1",
            "answers": {}, "complete_count": 0,
        }
    )
    return public, review


def _textline_corpus(mode: str) -> Path:
    if mode == "exact":
        return TEXTLINE_EXACT_CORPUS
    if mode == "warm":
        return TEXTLINE_CORPUS
    raise ValueError("TextLine court must be 'warm' or 'exact'")


def _textline_review_payload(corpus: Path = TEXTLINE_CORPUS) -> tuple[dict, dict]:
    manifest_path = corpus / "human_manifest.json"
    review_path = corpus / "review.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "TextLine court is not built; run "
            "python -m vice_compiler.build_textline_review"
            + (" --exact" if corpus == TEXTLINE_EXACT_CORPUS else "")
        )
    private = json.loads(manifest_path.read_text(encoding="utf-8"))
    hidden = {"candidate_side", "candidate_path", "candidate_reason"}
    public = dict(private)
    public["cases"] = [
        {key: value for key, value in row.items() if key not in hidden}
        for row in private.get("cases", [])
    ]
    public["blind_contract"] = (
        "candidate/legacy labels and construction reasons withheld by server"
    )
    review = (
        json.loads(review_path.read_text(encoding="utf-8"))
        if review_path.is_file()
        else {
            "schema": "pcdc-textline-human-review/v1",
            "required": int(private.get("required", len(private.get("cases", [])))),
            "answers": {}, "complete_count": 0,
        }
    )
    # Never return the normalized candidate/legacy label during a blind run.
    digest_keys = {
        "candidate_mask_digest", "legacy_mask_digest",
        "candidate_svg_digest", "legacy_svg_digest",
    }
    case_by_id = {
        str(row.get("id")): row for row in private.get("cases", [])
    }
    current_answers = {
        case_id: answer for case_id, answer in review.get("answers", {}).items()
        if case_id in case_by_id and all(
            answer.get(key) == case_by_id[case_id].get(key)
            and bool(answer.get(key))
            for key in digest_keys
        )
    }
    public_answers = {
        case_id: {
            key: value for key, value in answer.items()
            if key not in {"choice", "candidate_side", *digest_keys}
        }
        for case_id, answer in current_answers.items()
    }
    public_review = dict(review)
    public_review["answers"] = public_answers
    public_review["complete_count"] = len(public_answers)
    return public, public_review


def _phase12_blind_payload() -> tuple[dict, dict]:
    manifest_path = PHASE12_BLIND_ROOT / "human_manifest.json"
    review_path = PHASE12_BLIND_ROOT / "review.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "Phase-12 court is not built; run "
            "python -m vice_compiler.build_phase12_blind_court"
        )
    private = json.loads(manifest_path.read_text("utf-8"))
    hidden = {"ours_side", "ours_sha256", "vai_sha256"}
    public = dict(private)
    public["cases"] = [
        {key: value for key, value in row.items() if key not in hidden}
        for row in private.get("cases", [])
    ]
    public["blind_contract"] = (
        "ours/VAI mapping and candidate hashes withheld by server"
    )
    review = (
        json.loads(review_path.read_text("utf-8"))
        if review_path.is_file() else {
            "schema": "pcdc-phase12-blind-vai-court/v1",
            "court_id": private["court_id"], "locked": True,
            "expected_count": int(private.get("expected_count", 0)),
            "display_contract": private["display_contract"],
            "answers": {}, "complete_count": 0,
        }
    )
    public_review = dict(review)
    public_review["answers"] = {
        case_id: {
            key: value for key, value in answer.items()
            if key not in {"choice", "ours_side"}
        }
        for case_id, answer in review.get("answers", {}).items()
    }
    return public, public_review


def _clean_locus_review(locus: dict, raw: dict) -> dict:
    image = locus["image"]
    width, height = int(image["width"]), int(image["height"])
    roi = raw.get("roi_xyxy")
    if not (
        isinstance(roi, list)
        and len(roi) == 4
        and all(isinstance(value, int) for value in roi)
        and 0 <= roi[0] < roi[2] <= width
        and 0 <= roi[1] < roi[3] <= height
    ):
        raise ValueError("ROI must be four in-bounds integer x1,y1,x2,y2 values")
    components = raw.get("components")
    holes = raw.get("holes")
    if not isinstance(components, int) or components < 0:
        raise ValueError("components must be a non-negative integer")
    if not isinstance(holes, int) or holes < 0:
        raise ValueError("holes must be a non-negative integer")
    macro_family = str(raw.get("macro_family", "")).strip()
    proposal_family = str(raw.get("proposal_family", "")).strip()
    if proposal_family and proposal_family not in PROPOSAL_FAMILIES:
        raise ValueError("invalid ProposalNet family")
    acceptable_support = str(raw.get("acceptable_support", "")).strip()
    support_rle = raw.get("support_rle")
    if not isinstance(support_rle, list):
        raise ValueError("acceptable support mask RLE is required")
    previous_end = 0
    support_area = 0
    clean_rle: list[list[int]] = []
    for run in support_rle:
        if not (
            isinstance(run, list) and len(run) == 2
            and all(isinstance(value, int) for value in run)
        ):
            raise ValueError("support RLE runs must be [start,length] integers")
        start, run_length = run
        end = start + run_length
        if start < previous_end or run_length <= 0 or end > width * height:
            raise ValueError("support RLE is out of bounds or overlaps")
        clean_rle.append([start, run_length])
        previous_end = end
        support_area += run_length
    layer_relation = str(raw.get("layer_relation", "")).strip()
    preferred_candidate = str(raw.get("preferred_candidate", "")).strip()
    text_membership = str(raw.get("text_line_membership", ""))
    if text_membership not in {"yes", "no", "not_applicable"}:
        raise ValueError("invalid text-line membership")
    requested_status = str(raw.get("status", "evidence_reviewed"))
    if requested_status not in {"pending_review", "evidence_reviewed", "complete"}:
        raise ValueError("invalid review status")
    evidence_ready = bool(macro_family and layer_relation and support_area > 0)
    if requested_status in {"evidence_reviewed", "complete"} and not evidence_ready:
        raise ValueError(
            "reviewed loci require support, macro family, and layer relation"
        )
    if requested_status == "complete" and not preferred_candidate:
        raise ValueError(
            "complete review requires a human candidate preference"
        )
    reviewer = str(raw.get("reviewer", "local-human")).strip()[:120]
    clean = {
        "status": requested_status,
        "roi_xyxy": roi,
        "acceptable_support": acceptable_support,
        "support_rle": clean_rle,
        "support_area": support_area,
        "support_size": [width, height],
        "components": components,
        "holes": holes,
        "macro_family": macro_family,
        "proposal_family": proposal_family,
        "text_line_membership": text_membership,
        "layer_relation": layer_relation,
        "preferred_candidate": preferred_candidate,
        "notes": str(raw.get("notes", "")).strip()[:4000],
        "reviewer": reviewer or "local-human",
        "updated_at": time.time(),
    }
    raw_instances = raw.get("proposal_instances")
    if raw_instances is not None:
        if not isinstance(raw_instances, list) or not raw_instances:
            raise ValueError("proposal_instances must be a non-empty list")
        clean_instances = []
        used_ids: set[str] = set()
        for index, raw_instance in enumerate(raw_instances):
            if not isinstance(raw_instance, dict):
                raise ValueError("each ProposalNet instance must be an object")
            instance_id = str(
                raw_instance.get("id", f"{index:03d}")
            ).strip()[:120]
            if not instance_id or instance_id in used_ids:
                raise ValueError("ProposalNet instance ids must be unique")
            used_ids.add(instance_id)
            merged = dict(clean)
            merged.update(raw_instance)
            merged.pop("proposal_instances", None)
            instance = _clean_locus_review(locus, merged)
            if not instance["proposal_family"]:
                raise ValueError("each ProposalNet instance requires a family")
            if instance["components"] < 1:
                raise ValueError("each ProposalNet instance requires visible support")
            relation = _clean_relation_contract(
                raw_instance.get("relation_contract"),
                instance["proposal_family"],
            )
            clean_instances.append({
                "id": instance_id,
                "status": instance["status"],
                "roi_xyxy": instance["roi_xyxy"],
                "support_rle": instance["support_rle"],
                "support_area": instance["support_area"],
                "support_size": instance["support_size"],
                "components": instance["components"],
                "holes": instance["holes"],
                "proposal_family": instance["proposal_family"],
                "text_line_membership": instance["text_line_membership"],
                "layer_relation": instance["layer_relation"],
                "relation_contract": relation,
                "notes": instance["notes"],
            })
        clean["proposal_instances"] = clean_instances
    return clean


def _clean_relation_contract(raw: object, family: str) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("relation_contract must be an object")
    if raw.get("schema") != RELATION_CONTRACT_SCHEMA:
        raise ValueError("invalid relation contract schema")
    if raw.get("family") != family:
        raise ValueError("relation contract family mismatch")
    positive = raw.get("positive")
    observable = raw.get("observable")
    if not isinstance(positive, list) or not isinstance(observable, list):
        raise ValueError("relation tokens must be explicit lists")
    positive_tokens = [str(value) for value in positive]
    observable_tokens = [str(value) for value in observable]
    if (
        len(positive_tokens) != len(set(positive_tokens))
        or len(observable_tokens) != len(set(observable_tokens))
        or not set(positive_tokens).issubset(observable_tokens)
        or not set(observable_tokens).issubset(RELATION_TYPES)
    ):
        raise ValueError("invalid positive/observable relation tokens")
    return {
        "schema": RELATION_CONTRACT_SCHEMA,
        "family": family,
        "positive": positive_tokens,
        "observable": observable_tokens,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "VAI-Preview/1.0"

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # A browser tab may be closed while a long worker is finishing.
            # That must never take the HTTP server down.
            return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/certificate-review":
            try:
                manifest, review = _certificate_review_payload()
                self.send_json({"manifest": manifest, "review": review})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return
        if path == "/api/textline-review":
            try:
                query = parse_qs(parsed.query)
                corpus = _textline_corpus(query.get("court", ["warm"])[0])
                manifest, review = _textline_review_payload(corpus)
                self.send_json({"manifest": manifest, "review": review})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return
        if path == "/api/phase12-blind-review":
            try:
                manifest, review = _phase12_blind_payload()
                self.send_json({"manifest": manifest, "review": review})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return
        if path == "/api/locus-corpus":
            try:
                manifest, review = _locus_payload()
                query = parse_qs(parsed.query)
                semantic_class = query.get("class", [""])[0]
                offset = max(0, int(query.get("offset", ["0"])[0]))
                limit = min(300, max(1, int(query.get("limit", ["300"])[0])))
                rows = manifest.get("loci", [])
                if semantic_class:
                    rows = [
                        row for row in rows
                        if row.get("semantic_class") == semantic_class
                    ]
                public_rows = []
                reviews = review.get("reviews", {})
                for row in rows[offset:offset + limit]:
                    public = dict(row)
                    public["source"] = {
                        key: value for key, value in row.get("source", {}).items()
                        if key != "path"
                    }
                    public["source_url"] = f"/locus-source/{row['id']}"
                    public["review"] = reviews.get(row["id"])
                    public_rows.append(public)
                counts = {
                    "pending_review": 0, "ground_truth_derived": 0,
                    "evidence_reviewed": 0, "complete": 0,
                }
                for row in manifest.get("loci", []):
                    status = reviews.get(row["id"], {}).get("status", "pending_review")
                    counts[status] = counts.get(status, 0) + 1
                self.send_json({
                    "schema": manifest.get("schema"),
                    "total": manifest.get("total"),
                    "targets": manifest.get("targets"),
                    "review_counts": counts,
                    "filtered_total": len(rows),
                    "offset": offset,
                    "loci": public_rows,
                })
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return
        locus_match = re.fullmatch(
            r"/locus-source/([a-zA-Z0-9_.-]+)", path
        )
        if locus_match:
            try:
                locus = _locus_index().get(locus_match.group(1))
                if locus is None:
                    self.send_error(404)
                    return
                target = Path(locus["source"]["path"]).resolve()
                if not target.is_file():
                    self.send_error(404)
                    return
                self.send_file(target)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return
        job_match = re.fullmatch(r"/api/jobs/([0-9a-f]{32})", path)
        if job_match:
            snapshot = _job_snapshot(job_match.group(1))
            if snapshot is None:
                self.send_json({"error": "Unknown job"}, 404)
                return
            started = snapshot.get("started_at")
            stopped = snapshot.get("finished_at") or time.time()
            snapshot["elapsed_seconds"] = round(
                max(0.0, stopped - started), 1) if started else 0.0
            self.send_json({"job": snapshot})
            return
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
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/phase12-blind-review":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 64 * 1024:
                    raise ValueError("Phase-12 review payload is too large")
                payload = json.loads(self.rfile.read(length))
                case_id = str(payload.get("id", ""))
                blind_choice = str(payload.get("choice", ""))
                note = str(payload.get("note", "")).strip()[:1000]
                if blind_choice not in {"A", "B", "tie"}:
                    raise ValueError("Choice must be A, B, or tie")
                manifest_path = PHASE12_BLIND_ROOT / "human_manifest.json"
                private = json.loads(manifest_path.read_text("utf-8"))
                cases = {
                    str(row.get("id")): row for row in private.get("cases", [])
                }
                case = cases.get(case_id)
                if case is None:
                    raise ValueError("Unknown Phase-12 case id")
                ours_side = str(case["ours_side"])
                normalized = (
                    "tie" if blind_choice == "tie"
                    else "ours" if blind_choice == ours_side else "vai"
                )
                public_answer = {
                    "blind_choice": blind_choice, "note": note,
                    "reviewer": "local-human", "updated_at": time.time(),
                }
                if bool(payload.get("dry_run", False)):
                    self.send_json({
                        "ok": True, "dry_run": True, "id": case_id,
                        "answer": public_answer, "total": len(cases),
                    })
                    return
                target = PHASE12_BLIND_ROOT / "review.json"
                review = (
                    json.loads(target.read_text("utf-8"))
                    if target.is_file() else {
                        "schema": "pcdc-phase12-blind-vai-court/v1",
                        "court_id": private["court_id"], "locked": True,
                        "expected_count": len(cases),
                        "display_contract": private["display_contract"],
                        "answers": {}, "complete_count": 0,
                    }
                )
                if review.get("court_id") != private.get("court_id"):
                    raise ValueError("review belongs to another locked court")
                answers = review.setdefault("answers", {})
                answers[case_id] = {
                    **public_answer, "choice": normalized,
                    "ours_side": ours_side, "slice": str(case["slice"]),
                }
                review["updated_at"] = time.time()
                review["complete_count"] = len(answers)
                review["expected_count"] = len(cases)
                review["locked"] = True
                review["display_contract"] = private["display_contract"]
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary.replace(target)
                self.send_json({
                    "ok": True, "id": case_id, "answer": public_answer,
                    "complete_count": review["complete_count"],
                    "total": len(cases),
                })
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/textline-review":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 64 * 1024:
                    raise ValueError("TextLine review payload is too large")
                payload = json.loads(self.rfile.read(length))
                query = parse_qs(parsed.query)
                court_mode = str(
                    payload.get("court") or query.get("court", ["warm"])[0]
                )
                textline_corpus = _textline_corpus(court_mode)
                case_id = str(payload.get("id", ""))
                blind_choice = str(payload.get("choice", ""))
                note = str(payload.get("note", "")).strip()[:1000]
                if blind_choice not in {"A", "B", "tie"}:
                    raise ValueError("Choice must be A, B, or tie")
                manifest_path = textline_corpus / "human_manifest.json"
                private = json.loads(manifest_path.read_text(encoding="utf-8"))
                cases = {
                    str(row.get("id")): row for row in private.get("cases", [])
                }
                case = cases.get(case_id)
                if case is None:
                    raise ValueError("Unknown TextLine case id")
                candidate_side = str(case["candidate_side"])
                normalized = (
                    "tie" if blind_choice == "tie" else
                    "candidate" if blind_choice == candidate_side else "legacy"
                )
                public_answer = {
                    "blind_choice": blind_choice, "note": note,
                    "reviewer": "local-human", "updated_at": time.time(),
                }
                if bool(payload.get("dry_run", False)):
                    self.send_json({
                        "ok": True, "dry_run": True, "id": case_id,
                        "answer": public_answer, "total": len(cases),
                    })
                    return
                target = textline_corpus / "review.json"
                review = (
                    json.loads(target.read_text(encoding="utf-8"))
                    if target.is_file() else {
                        "schema": "pcdc-textline-human-review/v1",
                        "required": int(private.get("required", len(cases))),
                        "answers": {},
                    }
                )
                answers = review.setdefault("answers", {})
                answers[case_id] = {
                    **public_answer, "choice": normalized,
                    "candidate_side": candidate_side,
                    **{
                        key: case[key] for key in (
                            "candidate_mask_digest", "legacy_mask_digest",
                            "candidate_svg_digest", "legacy_svg_digest",
                        )
                    },
                }
                review["updated_at"] = time.time()
                review["complete_count"] = len(answers)
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary.replace(target)
                self.send_json({
                    "ok": True, "id": case_id, "answer": public_answer,
                    "complete_count": review["complete_count"],
                    "total": len(cases),
                })
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/certificate-review":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 64 * 1024:
                    raise ValueError("Certificate review payload is too large")
                payload = json.loads(self.rfile.read(length))
                case_id = str(payload.get("id", ""))
                choice = str(payload.get("choice", ""))
                note = str(payload.get("note", "")).strip()[:1000]
                manifest_path = CERTIFICATE_CORPUS / "human_manifest.json"
                private = json.loads(manifest_path.read_text(encoding="utf-8"))
                ids = {str(row.get("id")) for row in private.get("cases", [])}
                if case_id not in ids:
                    raise ValueError("Unknown certificate case id")
                if choice not in {"A", "B", "tie"}:
                    raise ValueError("Choice must be A, B, or tie")
                if bool(payload.get("dry_run", False)):
                    self.send_json({
                        "ok": True, "dry_run": True, "id": case_id,
                        "answer": {"choice": choice, "note": note},
                        "total": len(ids),
                    })
                    return
                target = CERTIFICATE_CORPUS / "review.json"
                review = (
                    json.loads(target.read_text(encoding="utf-8"))
                    if target.is_file() else {
                        "schema": "pcdc-certificate-human-review/v1",
                        "answers": {},
                    }
                )
                answers = review.setdefault("answers", {})
                answers[case_id] = {
                    "choice": choice, "note": note,
                    "reviewer": "local-human", "updated_at": time.time(),
                }
                review["updated_at"] = time.time()
                review["complete_count"] = len(answers)
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary.replace(target)
                self.send_json({
                    "ok": True, "id": case_id,
                    "answer": answers[case_id],
                    "complete_count": review["complete_count"],
                    "total": len(ids),
                })
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/locus-review":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 4 * 1024 * 1024:
                    raise ValueError("Review payload is too large")
                payload = json.loads(self.rfile.read(length))
                locus_id = str(payload.get("id", ""))
                index = _locus_index()
                locus = index.get(locus_id)
                if locus is None:
                    raise ValueError("Unknown locus id")
                clean = _clean_locus_review(
                    locus, payload.get("review", {})
                )
                if bool(payload.get("dry_run")):
                    self.send_json({
                        "ok": True,
                        "dry_run": True,
                        "id": locus_id,
                        "review": clean,
                    })
                    return
                manifest, review = _locus_payload()
                reviews = review.setdefault("reviews", {})
                reviews[locus_id] = clean
                review["updated_at"] = time.time()
                review["complete_count"] = sum(
                    item.get("status") == "complete"
                    for item in reviews.values()
                )
                review["ground_truth_derived_count"] = sum(
                    item.get("status") == "ground_truth_derived"
                    for item in reviews.values()
                )
                review["evidence_reviewed_count"] = sum(
                    item.get("status") in {
                        "ground_truth_derived", "evidence_reviewed", "complete"
                    }
                    for item in reviews.values()
                )
                target = LOCUS_CORPUS / "review.json"
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary.replace(target)
                self.send_json({
                    "ok": True,
                    "id": locus_id,
                    "review": clean,
                    "complete_count": review["complete_count"],
                    "evidence_reviewed_count": review["evidence_reviewed_count"],
                    "review_counts": {
                        "ground_truth_derived": review["ground_truth_derived_count"],
                        "evidence_reviewed": sum(
                            item.get("status") == "evidence_reviewed"
                            for item in reviews.values()
                        ),
                        "complete": review["complete_count"],
                        "pending_review": int(manifest.get("total", 0))
                        - review["evidence_reviewed_count"],
                    },
                    "corpus_total": manifest.get("total"),
                })
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
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
            if length > 36 * 1024 * 1024:
                raise ValueError("Запыт завялікі (максімум 25 MB для файла)")
            payload = json.loads(self.rfile.read(length))
            filename = safe_name(payload["filename"])
            smoothing = payload.get("smoothing", "paper-regions")
            extractor = payload.get("extractor", "mininet")
            route = payload.get("route", "auto")
            if smoothing not in {"scene", "none", "corner", "chaikin", "bspline", "cad", "uncertainty", "perceptual", "perceptual-icm", "perceptual-merge", "paper", "paper-native", "paper-perc", "paper-perres", "paper-regions"}:
                raise ValueError("Unknown contour interpolation mode")
            if extractor not in {"palette", "mininet"}:
                raise ValueError("Unknown contour extractor")
            if route not in {"auto", "preview", "diagram", "native"}:
                raise ValueError("Unknown route")
            encoded = payload["data"].split(",", 1)[-1]
            data = base64.b64decode(encoded, validate=True)
            if len(data) > 25 * 1024 * 1024:
                raise ValueError("Файл завялікі (максімум 25 MB)")
            UPLOADS.mkdir(parents=True, exist_ok=True)
            RESULTS.mkdir(parents=True, exist_ok=True)
            job_id = uuid.uuid4().hex
            upload_dir = UPLOADS / job_id
            upload_dir.mkdir(parents=True, exist_ok=False)
            upload = upload_dir / filename
            upload.write_bytes(data)
            created = time.time()
            job_root = RESULTS / ".jobs" / job_id
            with JOB_LOCK:
                JOBS[job_id] = {
                    "id": job_id, "filename": filename, "status": "queued",
                    "progress": 0.0, "smoothing": smoothing,
                    "extractor": extractor, "route": route,
                    "created_at": created, "updated_at": created,
                    "cancel_requested": False, "upload": str(upload),
                    "job_root": str(job_root),
                }
            future = JOB_EXECUTOR.submit(_execute_job, job_id)
            with JOB_LOCK:
                JOBS[job_id]["future"] = future
            self.send_json({"job": _job_snapshot(job_id)}, 202)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/jobs/([0-9a-f]{32})", path)
        if not match:
            self.send_error(404)
            return
        job_id = match.group(1)
        cleanup: tuple[Path, Path] | None = None
        with JOB_LOCK:
            job = JOBS.get(job_id)
            if job is None:
                self.send_json({"error": "Unknown job"}, 404)
                return
            if job.get("status") in {"completed", "failed", "cancelled"}:
                self.send_json({"job": _job_snapshot(job_id)})
                return
            job["cancel_requested"] = True
            job["updated_at"] = time.time()
            future = job.get("future")
            process = job.get("process")
            if future is not None and future.cancel():
                job.update(status="cancelled", progress=1.0,
                           finished_at=time.time())
                cleanup = (Path(job["upload"]).parent, Path(job["job_root"]))
            elif process is not None and process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
        if cleanup is not None:
            upload_dir, job_root = cleanup
            if UPLOADS.resolve() in upload_dir.resolve().parents:
                shutil.rmtree(upload_dir, ignore_errors=True)
            jobs_root = (RESULTS / ".jobs").resolve()
            if jobs_root in job_root.resolve().parents:
                shutil.rmtree(job_root, ignore_errors=True)
        self.send_json({"job": _job_snapshot(job_id)}, 202)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()
    host, port = "127.0.0.1", args.port
    print(f"VAI preview: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
