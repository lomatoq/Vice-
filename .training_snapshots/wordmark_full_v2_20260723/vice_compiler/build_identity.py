"""Stable identity of the complete Python compiler implementation."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
PRODUCTION_EXTERNAL_MODULES = (
    PROJECT / "font_match.py",
    PROJECT / "text_substitution.py",
)
PRODUCTION_ENTRY_MODULES = ("runtime_service.py",)


def production_compiler_sources() -> tuple[Path, ...]:
    """Return the static local import closure of the production compiler.

    The old identity hashed every helper under ``vice_compiler``.  Editing a
    read-only audit, experiment harness, trainer, or report generator therefore
    invalidated all production experiments even though no delivered SVG byte
    could change.  Conversely, the two external modules used by the runtime had
    to be maintained in a separate hand list.

    Start from the actual persistent production service and follow every local
    relative import, including imports inside functions.  This binds all code
    that can execute on the delivery path while excluding tooling that merely
    observes it.  External project modules remain explicit because Python's
    absolute-import semantics do not identify which third-party modules are
    local.
    """
    package = PROJECT / "vice_compiler"
    pending = list(PRODUCTION_ENTRY_MODULES)
    visited: set[str] = set()
    paths: list[Path] = []
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        path = package / name
        if not path.is_file():
            raise RuntimeError(f"production compiler module is missing: {path}")
        visited.add(name); paths.append(path)
        try:
            tree = ast.parse(path.read_text("utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError) as error:
            raise RuntimeError(
                f"cannot derive production compiler identity from {path}"
            ) from error
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level <= 0:
                continue
            if node.module:
                child = node.module.split(".", 1)[0] + ".py"
                if (package / child).is_file() and child not in visited:
                    pending.append(child)
            else:
                for alias in node.names:
                    child = alias.name.split(".", 1)[0] + ".py"
                    if (package / child).is_file() and child not in visited:
                        pending.append(child)
    return tuple(sorted((*paths, *PRODUCTION_EXTERNAL_MODULES)))


def compiler_source_sha256() -> str:
    """Bind reports only to code reachable from production delivery."""
    digest = hashlib.sha256(b"pcdc-production-source-identity/v2\0")
    for path in production_compiler_sources():
        digest.update(str(path.relative_to(PROJECT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def bind_report(report: dict) -> dict:
    report["compiler_source_sha256"] = compiler_source_sha256()
    report["native_runtime_identity"] = native_runtime_identity()
    return report


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def native_runtime_identity() -> dict[str, Any]:
    """Bind the optional Rust implementation used by production hot paths."""
    paths = (
        PROJECT / "native/pcdc_native_core/Cargo.toml",
        PROJECT / "native/pcdc_native_core/src/lib.rs",
        PROJECT / "native/pcdc_native_core/target/release/pcdc_native_core.dll",
    )
    digest = hashlib.sha256(b"pcdc-native-runtime-identity/v1\0")
    artifacts = {}
    complete = True
    for path in paths:
        relative = str(path.relative_to(PROJECT)).replace("\\", "/")
        if not path.is_file():
            complete = False
            digest.update(relative.encode("utf-8")); digest.update(b"\0missing\0")
            artifacts[relative] = {"path": str(path.resolve()), "exists": False}
            continue
        sha = _file_sha256(path)
        digest.update(relative.encode("utf-8")); digest.update(b"\0")
        digest.update(sha.encode("ascii")); digest.update(b"\0")
        artifacts[relative] = {
            "path": str(path.resolve()), "exists": True,
            "sha256": sha, "bytes": path.stat().st_size,
        }
    return {
        "schema": "pcdc-native-runtime-identity/v1",
        "sha256": digest.hexdigest(), "complete": complete,
        "artifacts": artifacts,
    }


def runtime_model_identity(
    *, proposal_checkpoint: Path | None = None,
    proposal_manifest: Path | None = None,
) -> dict[str, Any]:
    """Identity of every external model that can affect compiler output."""
    from .runtime_service import (
        DEFAULT_PROPOSAL_CHECKPOINT, _proposal_promotion_manifest,
        _validate_proposal_candidate_evaluation, _validate_proposal_promotion,
    )
    from .glyph_prior import (
        DEFAULT_GLYPH_PRIOR_CHECKPOINT, DEFAULT_GLYPH_PRIOR_PROMOTION,
        validate_glyph_prior_promotion,
    )
    from .wordmark_runtime import (
        DEFAULT_WORDMARK_PRIOR_CHECKPOINT, DEFAULT_WORDMARK_PRIOR_PROMOTION,
        validate_wordmark_prior_promotion,
    )
    from .experiment_inputs import trocr_model_input_identity

    if (proposal_checkpoint is None) != (proposal_manifest is None):
        raise ValueError("proposal candidate checkpoint and manifest must be paired")
    artifacts: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256(b"pcdc-runtime-model-identity/v2\0")

    if proposal_checkpoint is not None and proposal_manifest is not None:
        checkpoint = proposal_checkpoint.resolve(); manifest = proposal_manifest.resolve()
        _validate_proposal_candidate_evaluation(checkpoint, manifest)
        proposal_mode = "candidate-evaluation"
        proposal_paths = (checkpoint, manifest)
    else:
        checkpoint = DEFAULT_PROPOSAL_CHECKPOINT.resolve()
        manifest = _proposal_promotion_manifest(checkpoint).resolve()
        try:
            _validate_proposal_promotion(checkpoint, manifest)
            proposal_mode = "production"
            proposal_paths = (checkpoint, manifest)
        except Exception:
            proposal_mode = "disabled"
            proposal_paths = ()
    digest.update(f"proposal:{proposal_mode}\0".encode("ascii"))
    for path in proposal_paths:
        sha = _file_sha256(path)
        digest.update(path.name.encode("utf-8")); digest.update(sha.encode("ascii"))
        artifacts[f"proposal:{path.name}"] = {
            "path": str(path), "sha256": sha, "bytes": path.stat().st_size,
        }

    try:
        validate_glyph_prior_promotion(
            DEFAULT_GLYPH_PRIOR_CHECKPOINT, DEFAULT_GLYPH_PRIOR_PROMOTION,
        )
        glyph_mode = "production"
        glyph_paths = (
            DEFAULT_GLYPH_PRIOR_CHECKPOINT.resolve(),
            DEFAULT_GLYPH_PRIOR_PROMOTION.resolve(),
        )
    except Exception:
        glyph_mode = "disabled"
        glyph_paths = ()
    digest.update(f"glyph:{glyph_mode}\0".encode("ascii"))
    for path in glyph_paths:
        sha = _file_sha256(path)
        digest.update(path.name.encode("utf-8")); digest.update(sha.encode("ascii"))
        artifacts[f"glyph:{path.name}"] = {
            "path": str(path), "sha256": sha, "bytes": path.stat().st_size,
        }
    try:
        validate_wordmark_prior_promotion(
            DEFAULT_WORDMARK_PRIOR_CHECKPOINT,
            DEFAULT_WORDMARK_PRIOR_PROMOTION,
        )
        wordmark_mode = "production"
        wordmark_paths = (
            DEFAULT_WORDMARK_PRIOR_CHECKPOINT.resolve(),
            DEFAULT_WORDMARK_PRIOR_PROMOTION.resolve(),
        )
    except Exception:
        wordmark_mode = "disabled"
        wordmark_paths = ()
    digest.update(f"wordmark:{wordmark_mode}\0".encode("ascii"))
    for path in wordmark_paths:
        sha = _file_sha256(path)
        digest.update(path.name.encode("utf-8"))
        digest.update(sha.encode("ascii"))
        artifacts[f"wordmark:{path.name}"] = {
            "path": str(path), "sha256": sha, "bytes": path.stat().st_size,
        }
    trocr = trocr_model_input_identity()
    digest.update(f"trocr:{trocr['mode']}\0".encode("ascii"))
    digest.update(trocr["sha256"].encode("ascii"))
    for name, row in trocr["artifacts"].items():
        artifacts[f"trocr:{name}"] = dict(row)
    return {
        "schema": "pcdc-runtime-model-identity/v2",
        "sha256": digest.hexdigest(),
        "proposal_mode": proposal_mode, "glyph_mode": glyph_mode,
        "wordmark_mode": wordmark_mode,
        "trocr_mode": trocr["mode"], "trocr": trocr,
        "artifacts": artifacts,
    }
