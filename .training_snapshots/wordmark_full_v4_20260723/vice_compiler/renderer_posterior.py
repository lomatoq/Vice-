"""Immutable image-formation posterior used by the phase-3 local court.

The posterior is frozen once from REIR and is shared by every candidate and
its fallback.  A candidate may therefore not win by selecting a friendlier
renderer after its geometry is known.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from typing import Any

import cv2
import numpy as np
from PIL import Image


SCHEMA = "pcdc-renderer-posterior/v1"


@dataclass(frozen=True)
class FixedRendererModel:
    id: str
    weight: float
    pixel_phase_xy: tuple[float, float]
    blur_sigma: float
    gamma: float
    jpeg_quality: int | None
    chroma_subsampling: str
    resize_chain: str
    alpha_mode: str
    noise_sigma: float

    def validate(self) -> None:
        values = (*self.pixel_phase_xy, self.weight, self.blur_sigma,
                  self.gamma, self.noise_sigma)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("renderer model contains a non-finite value")
        if self.weight <= 0.0 or self.blur_sigma < 0.0:
            raise ValueError("renderer model has an invalid weight/blur")
        if self.gamma <= 0.0 or self.noise_sigma <= 0.0:
            raise ValueError("renderer model has an invalid gamma/noise")
        if self.jpeg_quality is not None and not 1 <= self.jpeg_quality <= 100:
            raise ValueError("renderer JPEG quality is outside [1,100]")


@dataclass(frozen=True)
class FixedRendererPosterior:
    schema: str
    source_sha256: str
    models: tuple[FixedRendererModel, ...]
    digest: str
    provenance: tuple[str, ...]

    def validate(self) -> None:
        if self.schema != SCHEMA:
            raise ValueError("unsupported renderer posterior schema")
        if not 1 <= len(self.models) <= 8:
            raise ValueError("renderer posterior must contain 1..8 models")
        for model in self.models:
            model.validate()
        if len({model.id for model in self.models}) != len(self.models):
            raise ValueError("renderer posterior model ids are not unique")
        if abs(sum(model.weight for model in self.models) - 1.0) > 1e-8:
            raise ValueError("renderer posterior weights are not normalized")
        if self.digest != posterior_digest(
            self.source_sha256, self.models, self.provenance
        ):
            raise ValueError("renderer posterior digest mismatch")


@dataclass(frozen=True)
class ModelLikelihood:
    model_id: str
    log_likelihood: float
    mean_robust_nll: float
    pixel_count: int


@dataclass(frozen=True)
class PairwiseRenderEvidence:
    """Auditable fixed-posterior summary for one candidate/fallback pair.

    The renderer state is conditioned on the fallback likelihood only.  It is
    therefore fixed before the candidate hypothesis is inspected, while still
    implementing the actual marginal Bayes factor instead of averaging
    conditional log Bayes factors under the unconditioned prior.
    """

    posterior_mean_delta_logp: float
    posterior_variance: float
    conservative_lower_bound: float
    marginal_log_bayes_factor: float
    model_deltas: tuple[tuple[str, float], ...]
    reference_model_weights: tuple[tuple[str, float], ...]


def _logsumexp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + math.log(float(np.sum(np.exp(values - maximum))))


def summarize_pairwise_render_evidence(
    posterior: FixedRendererPosterior,
    candidate_likelihoods: tuple[ModelLikelihood, ...],
    fallback_likelihoods: tuple[ModelLikelihood, ...],
    *,
    confidence_z: float,
) -> PairwiseRenderEvidence:
    """Summarize a candidate-vs-fallback render Bayes factor conservatively.

    For fixed renderer prior ``w_m`` and paired likelihoods, define the
    candidate-independent reference posterior

        q_F(m) = w_m p(I | F, m) / p(I | F).

    Then the exact marginal Bayes factor is

        log BF(H:F) = log E_qF[exp(delta_m)].

    Jensen gives ``E_qF[delta_m] <= log BF``.  Consequently
    ``mean - z*std`` under this fixed reference posterior is a conservative
    lower bound on the *marginal* evidence.  Weighting deltas by the original
    unconditioned prior is not this Bayes factor and can let renderer models
    that make the common fallback astronomically unlikely dominate the LCB.
    """
    posterior.validate()
    if not math.isfinite(confidence_z) or confidence_z < 0.0:
        raise ValueError("render confidence z must be finite/nonnegative")
    candidate_by_id = {row.model_id: row for row in candidate_likelihoods}
    fallback_by_id = {row.model_id: row for row in fallback_likelihoods}
    expected_ids = tuple(model.id for model in posterior.models)
    if (
        len(candidate_by_id) != len(candidate_likelihoods)
        or len(fallback_by_id) != len(fallback_likelihoods)
        or set(candidate_by_id) != set(expected_ids)
        or set(fallback_by_id) != set(expected_ids)
    ):
        raise ValueError("pairwise render likelihood ids do not match posterior")
    candidate_values = np.asarray([
        candidate_by_id[model.id].log_likelihood for model in posterior.models
    ], np.float64)
    fallback_values = np.asarray([
        fallback_by_id[model.id].log_likelihood for model in posterior.models
    ], np.float64)
    if not np.all(np.isfinite(candidate_values)) or not np.all(np.isfinite(fallback_values)):
        raise ValueError("pairwise render likelihood is non-finite")
    log_prior = np.log(np.asarray(
        [model.weight for model in posterior.models], np.float64,
    ))
    fallback_joint = log_prior + fallback_values
    fallback_log_evidence = _logsumexp(fallback_joint)
    reference_weights = np.exp(fallback_joint - fallback_log_evidence)
    deltas = candidate_values - fallback_values
    mean = float(np.sum(reference_weights * deltas))
    variance = float(np.sum(reference_weights * np.square(deltas - mean)))
    lower = float(mean - confidence_z * math.sqrt(max(0.0, variance)))
    marginal = float(
        _logsumexp(log_prior + candidate_values) - fallback_log_evidence
    )
    # This is a mathematical invariant, not a tunable acceptance threshold.
    # Allow only floating-point roundoff around Jensen's inequality.
    if lower > marginal + 1e-8 * max(1.0, abs(marginal)):
        raise ValueError("render lower bound exceeds marginal Bayes factor")
    return PairwiseRenderEvidence(
        posterior_mean_delta_logp=mean,
        posterior_variance=max(0.0, variance),
        conservative_lower_bound=lower,
        marginal_log_bayes_factor=marginal,
        model_deltas=tuple(
            (model.id, float(delta))
            for model, delta in zip(posterior.models, deltas.tolist())
        ),
        reference_model_weights=tuple(
            (model.id, float(weight))
            for model, weight in zip(posterior.models, reference_weights.tolist())
        ),
    )


def posterior_digest(
    source_sha256: str,
    models: tuple[FixedRendererModel, ...],
    provenance: tuple[str, ...],
) -> str:
    payload = {
        "schema": SCHEMA,
        "source_sha256": source_sha256,
        "models": [model.__dict__ for model in models],
        "provenance": provenance,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def freeze_renderer_posterior(
    reir: Any, *, max_models: int = 8
) -> FixedRendererPosterior:
    rows = sorted(
        reir.formation_posterior.hypotheses,
        key=lambda item: (-float(item.weight), item.family),
    )[:max(1, min(8, int(max_models)))]
    if not rows:
        rows = [None]
    raw_weights = np.asarray([
        max(1e-9, float(row.weight)) if row is not None else 1.0
        for row in rows
    ], dtype=np.float64)
    raw_weights /= float(raw_weights.sum())
    models: list[FixedRendererModel] = []
    for index, (row, weight) in enumerate(zip(rows, raw_weights.tolist())):
        if row is None:
            phase = (0.0, 0.0); blur = 0.0; gamma = 2.2
            quality = None; chroma = "none"; resize = "native"
            alpha_mode = "straight"
        else:
            phase = tuple(float(value) for value in row.pixel_phase_xy)
            blur = float(sum(row.blur_sigma_range) * 0.5)
            gamma = float(sum(row.gamma_range) * 0.5)
            quality = (
                int(round(sum(row.jpeg_quality_range) * 0.5))
                if row.jpeg_quality_range is not None else None
            )
            chroma = str(row.chroma_subsampling)
            resize = str(row.resize_chain)
            alpha_mode = str(row.alpha_mode)
        noise = 0.010 + 0.004 * min(2.0, blur)
        if quality is not None:
            noise += 0.018 * (1.0 - quality / 100.0)
        model = FixedRendererModel(
            id=f"formation-{index:02d}-{getattr(row, 'family', 'clean')}",
            weight=float(weight), pixel_phase_xy=phase,
            blur_sigma=max(0.0, blur), gamma=max(0.1, gamma),
            jpeg_quality=quality, chroma_subsampling=chroma,
            resize_chain=resize, alpha_mode=alpha_mode,
            noise_sigma=float(noise),
        )
        models.append(model)
    provenance = (
        "fixed-before-candidate-scoring",
        str(reir.formation_posterior.estimator),
        f"uncertainty={float(reir.formation_posterior.uncertainty):.8f}",
    )
    frozen_models = tuple(models)
    posterior = FixedRendererPosterior(
        schema=SCHEMA, source_sha256=str(reir.source_sha256),
        models=frozen_models,
        digest=posterior_digest(str(reir.source_sha256), frozen_models, provenance),
        provenance=provenance,
    )
    posterior.validate()
    return posterior


def synthetic_renderer_posterior(
    *, source_id: str = "synthetic", blur_sigma: float = 0.35
) -> FixedRendererPosterior:
    models = (
        FixedRendererModel(
            id="clean-aa", weight=0.62, pixel_phase_xy=(0.0, 0.0),
            blur_sigma=0.0, gamma=2.2, jpeg_quality=None,
            chroma_subsampling="none", resize_chain="native",
            alpha_mode="straight", noise_sigma=0.010,
        ),
        FixedRendererModel(
            id="soft-aa", weight=0.38, pixel_phase_xy=(0.125, -0.125),
            blur_sigma=max(0.0, float(blur_sigma)), gamma=2.2,
            jpeg_quality=None, chroma_subsampling="none",
            resize_chain="native", alpha_mode="straight",
            noise_sigma=0.013,
        ),
    )
    provenance = ("synthetic-fixed-posterior",)
    posterior = FixedRendererPosterior(
        schema=SCHEMA, source_sha256=source_id, models=models,
        digest=posterior_digest(source_id, models, provenance),
        provenance=provenance,
    )
    posterior.validate()
    return posterior


def apply_formation(
    premultiplied_linear_rgba: np.ndarray,
    model: FixedRendererModel,
) -> np.ndarray:
    """Apply one frozen formation model to premultiplied linear RGBA."""
    image = np.asarray(premultiplied_linear_rgba, dtype=np.float32)
    if image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("formation input must be HxWx4")
    result = image.copy()
    dx, dy = model.pixel_phase_xy
    if abs(dx) > 1e-9 or abs(dy) > 1e-9:
        matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float32)
        result = cv2.warpAffine(
            result, matrix, (result.shape[1], result.shape[0]),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0.0, 0.0, 0.0, 0.0),
        )
    if model.blur_sigma > 1e-9:
        result = cv2.GaussianBlur(
            result, (0, 0), model.blur_sigma,
            borderType=cv2.BORDER_REPLICATE,
        )
    result = np.clip(result, 0.0, 1.0)
    if abs(model.gamma - 2.2) > 1e-6:
        alpha = result[..., 3:4]
        straight = np.where(
            alpha > 1e-8, result[..., :3] / np.maximum(alpha, 1e-8), 0.0
        )
        straight = np.power(
            np.clip(straight, 0.0, 1.0), 2.2 / model.gamma
        )
        result[..., :3] = straight * alpha
    if model.jpeg_quality is not None:
        alpha = result[..., 3:4]
        straight = np.where(
            alpha > 1e-8, result[..., :3] / np.maximum(alpha, 1e-8), 0.0
        )
        srgb = np.power(np.clip(straight, 0.0, 1.0), 1.0 / 2.2)
        composite = srgb * alpha + (1.0 - alpha)
        buffer = io.BytesIO()
        Image.fromarray(
            np.clip(composite * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGB"
        ).save(buffer, format="JPEG", quality=model.jpeg_quality, subsampling=2)
        decoded = np.asarray(
            Image.open(io.BytesIO(buffer.getvalue())).convert("RGB"),
            dtype=np.float32,
        ) / 255.0
        linear = np.power(np.clip(decoded, 0.0, 1.0), 2.2)
        result[..., :3] = linear * alpha
    return np.clip(result, 0.0, 1.0)


def score_log_likelihood(
    observed_premultiplied_linear_rgba: np.ndarray,
    rendered_premultiplied_linear_rgba: np.ndarray,
    model: FixedRendererModel,
    *, support: np.ndarray | None = None,
) -> ModelLikelihood:
    observed = np.asarray(observed_premultiplied_linear_rgba, np.float32)
    formed = apply_formation(rendered_premultiplied_linear_rgba, model)
    if observed.shape != formed.shape:
        raise ValueError("observed/rendered likelihood shapes differ")
    residual = observed - formed
    if support is not None:
        mask = np.asarray(support, bool)
        if mask.shape != observed.shape[:2]:
            raise ValueError("likelihood support shape mismatch")
        values = residual[mask]
    else:
        values = residual.reshape(-1, 4)
    pixel_count = int(len(values))
    if pixel_count <= 0:
        return ModelLikelihood(model.id, 0.0, 0.0, 0)
    sigma = max(1e-5, float(model.noise_sigma))
    # Student-t(3) is robust to isolated codec flecks while remaining a proper
    # fixed likelihood for candidate and fallback alike.
    scaled = values / sigma
    robust = 2.0 * np.log1p(np.square(scaled) / 3.0)
    mean_nll = float(np.mean(robust))
    normalization = math.log(sigma * math.sqrt(3.0 * math.pi))
    log_likelihood = -float(np.sum(robust + normalization))
    return ModelLikelihood(
        model_id=model.id, log_likelihood=log_likelihood,
        mean_robust_nll=mean_nll, pixel_count=pixel_count,
    )
