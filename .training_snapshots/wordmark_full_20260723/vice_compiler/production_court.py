"""Production adapter from typed macro records to the exact local court.

Only a candidate whose *delivered* representation can be rendered here is
admitted.  Unsupported programs fail open to the base master; they are not
allowed to carry a certificate for a different preview.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import cv2
import numpy as np

from .atlas_renderer import ExactRoiAtlas, RoiRenderRequest
from .cell_complex import CellRefinementTransaction, plan_local_refinement
from .certificates import topology_signature
from .evidence_ir import RasterEvidenceIR
from .export_writer import (
    render_appearance_delivery, render_codec_delivery, render_shape_delivery,
    render_group_delivery, render_stroke_delivery, render_text_delivery,
)
from .local_court import (
    CourtCandidate, CourtDecision, PreferenceTiebreaker, bind_selected_proof,
    compare_in_local_court,
)
from .macro_ir import MacroCandidate
from .phase5_macros import Phase5MacroBundle
from .renderer_posterior import freeze_renderer_posterior
from .shape_macros import materialize_repeated_group_members
from .text_macros import TextMacroSet
from .layer_solver import _render_typed_shape


@dataclass(frozen=True)
class ProductionCourtAudit:
    considered: int
    certified: int
    rejected: int
    unsupported_delivery: int
    pruned_before_exact: int
    approximate_render_requests: int
    exact_render_requests: int
    approximate_render_pixels: int
    exact_render_pixels: int
    local_refinements_planned: int
    local_refinements_accepted: int
    decisions: tuple[CourtDecision, ...]
    marginals: tuple["CourtMarginalDelta", ...]


@dataclass(frozen=True)
class CourtMarginalDelta:
    candidate_id: str
    candidate_error: float
    fallback_error: float
    pixel_error_delta: float
    evidence_iou: float
    topology_error: int
    score_margin: float


def _candidate_support(reir: RasterEvidenceIR, candidate: MacroCandidate) -> np.ndarray:
    certificate = candidate.certificates
    width, height = certificate.support_size
    count = width * height
    if certificate.support_bits:
        mask = np.unpackbits(
            np.frombuffer(certificate.support_bits, np.uint8), count=count,
            bitorder="little",
        ).astype(bool).reshape((height, width))
    elif certificate.support_rle:
        flat = np.zeros(count, bool)
        for start, length in certificate.support_rle:
            flat[int(start):int(start) + int(length)] = True
        mask = flat.reshape((height, width))
    else:
        leaves = [
            leaf for leaf in range(reir.hierarchy.leaf_count)
            if candidate.core_bits & (1 << leaf)
        ]
        mask = np.isin(reir.hierarchy.leaf_labels, leaves)
    if mask.shape != (reir.height, reir.width):
        mask = cv2.resize(
            mask.astype(np.uint8), (reir.width, reir.height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    return np.asarray(mask, bool)


def _bbox(mask: np.ndarray, *, pad: int = 2) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("cannot court an empty delivered macro")
    return (
        max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + 1 + pad),
        min(mask.shape[0], int(ys.max()) + 1 + pad),
    )


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    values = np.asarray(rgb, np.float32)
    return np.where(
        values <= 0.04045, values / 12.92,
        np.power((values + 0.055) / 1.055, 2.4),
    ).astype(np.float32)


def _rgba8_linear_premultiplied(rgba8: np.ndarray) -> np.ndarray:
    straight = np.asarray(rgba8, np.float32) / 255.0
    alpha = np.clip(straight[..., 3], 0.0, 1.0)
    macro = np.zeros_like(straight, np.float32)
    macro[..., :3] = _srgb_to_linear(straight[..., :3]) * alpha[..., None]
    macro[..., 3] = alpha
    return np.ascontiguousarray(macro, np.float32)


def _solid_render(
    reir: RasterEvidenceIR, mask: np.ndarray,
    *, sample_mask: np.ndarray | None = None,
) -> np.ndarray:
    color_support = mask if sample_mask is None else np.asarray(sample_mask, bool)
    rgba = np.asarray(reir.raster.straight_rgba[color_support], np.float32)
    if not len(rgba):
        return np.zeros((reir.height, reir.width, 4), np.float32)
    color = np.clip(np.median(rgba, axis=0), 0.0, 1.0)
    alpha = float(color[3]) * np.asarray(mask, np.float32)
    result = np.zeros((reir.height, reir.width, 4), np.float32)
    result[..., :3] = _srgb_to_linear(color[:3])[None, None, :] * alpha[..., None]
    result[..., 3] = alpha
    return result


def _atomic_render(reir: RasterEvidenceIR) -> np.ndarray:
    observed = np.asarray(reir.raster.linear_premultiplied_rgba, np.float32)
    labels = reir.hierarchy.leaf_labels
    result = np.zeros_like(observed)
    for leaf in range(reir.hierarchy.leaf_count):
        mask = labels == leaf
        if np.any(mask):
            result[mask] = np.median(observed[mask], axis=0)
    return result


def _over(source: np.ndarray, destination: np.ndarray) -> np.ndarray:
    """Porter-Duff source-over for premultiplied linear RGBA."""
    alpha = np.asarray(source[..., 3:4], np.float32)
    result = np.empty_like(destination, dtype=np.float32)
    result[..., :3] = source[..., :3] + destination[..., :3] * (1.0 - alpha)
    result[..., 3:4] = alpha + destination[..., 3:4] * (1.0 - alpha)
    return np.clip(result, 0.0, 1.0)


def _canvas_background_pixel(reir: RasterEvidenceIR) -> np.ndarray:
    """Return the export canvas paint as one premultiplied-linear pixel."""
    straight = np.asarray(reir.raster.straight_rgba, np.float32)
    border = np.concatenate((
        straight[0], straight[-1], straight[:, 0], straight[:, -1],
    ))
    background = np.clip(np.median(border, axis=0), 0.0, 1.0)
    alpha = float(background[3])
    return np.asarray((
        *(_srgb_to_linear(background[:3]) * alpha), alpha,
    ), np.float32)


def _paint_canvas_background(
    destination: np.ndarray, mask: np.ndarray, background: np.ndarray,
) -> np.ndarray:
    """Paint the SVG canvas background over a replacement ownership cut.

    The production SVG clears an incumbent by painting the inferred canvas
    background before emitting the typed macro.  Treating that cut as RGBA
    zero makes opaque source backgrounds transparent in court and assigns a
    large, entirely artificial colour/alpha penalty to clean text and shapes.
    This is source-over (rather than assignment) so translucent canvas paint
    has the same semantics as the serialized SVG.
    """
    result = np.asarray(destination, np.float32).copy()
    owned = np.asarray(mask, bool)
    pixel = np.asarray(background, np.float32)
    if pixel.shape != (4,):
        raise ValueError("canvas background must be one premultiplied RGBA pixel")
    if not np.any(owned):
        return result
    alpha = float(np.clip(pixel[3], 0.0, 1.0))
    result[owned, :3] = pixel[:3] + result[owned, :3] * (1.0 - alpha)
    result[owned, 3] = alpha + result[owned, 3] * (1.0 - alpha)
    return np.clip(result, 0.0, 1.0)


class RuntimeMacroCourt:
    """Stateful bounded certifier used directly by pricing rounds."""

    def __init__(
        self, reir: RasterEvidenceIR, phase5: Phase5MacroBundle,
        text: TextMacroSet, *, atlas: ExactRoiAtlas,
        exact_request_limit: int,
        fallback_premultiplied_linear_rgba: np.ndarray | None = None,
        preference_tiebreaker: PreferenceTiebreaker | None = None,
    ) -> None:
        self.reir = reir; self.phase5 = phase5; self.text = text
        self.atlas = atlas; self.exact_request_limit = max(0, int(exact_request_limit))
        self.preference_tiebreaker = preference_tiebreaker
        self.posterior = freeze_renderer_posterior(reir)
        fallback = (
            _atomic_render(reir) if fallback_premultiplied_linear_rgba is None
            else np.asarray(fallback_premultiplied_linear_rgba, np.float32)
        )
        if fallback.shape != (reir.height, reir.width, 4):
            raise ValueError("production court fallback render shape mismatch")
        if not np.all(np.isfinite(fallback)):
            raise ValueError("production court fallback render is non-finite")
        self.fallback = np.ascontiguousarray(np.clip(fallback, 0.0, 1.0))
        self.canvas_background = _canvas_background_pixel(reir)
        source = np.asarray(reir.raster.straight_rgba, np.float32)
        source_opaque = source[..., :3] * source[..., 3:4] + (
            1.0 - source[..., 3:4]
        )
        border = np.concatenate((
            source_opaque[0], source_opaque[-1],
            source_opaque[:, 0], source_opaque[:, -1],
        ))
        self._ink_background = np.median(border, axis=0)
        self._source_ink = np.sum(
            np.abs(source_opaque - self._ink_background), axis=2,
        ) > (90.0 / 255.0)
        self._source_topology = topology_signature(self._source_ink)
        self._shape = {row.candidate.id: row for row in phase5.shapes.records}
        self._groups = {row.candidate.id: row for row in phase5.shapes.groups}
        self._stroke = {row.candidate.id: row for row in phase5.strokes.records}
        self._appearance = {
            row.candidate.id: row for row in phase5.appearances.records
        }
        self._cleanup = {
            row.candidate.id: row for row in phase5.cleanup.records
        }
        self._text = {row.candidate.id: row for row in text.records}
        self._lines = {row.id: row for row in text.proposals}
        self._decisions: list[CourtDecision] = []
        self._outcomes: dict[str, MacroCandidate | None] = {}
        self._delivery_masks: dict[str, np.ndarray] = {}
        self._ownership_masks: dict[str, np.ndarray] = {}
        self._rollback_masks: dict[str, np.ndarray] = {}
        self._marginals: dict[str, CourtMarginalDelta] = {}
        self._refinement_transactions: dict[str, CellRefinementTransaction] = {}
        self.considered = self.certified = self.rejected = 0
        self.unsupported_delivery = self.pruned = 0
        self.refinement_planned = 0
        self.approximate_requests = self.exact_requests = 0
        self.approximate_pixels = self.exact_pixels = 0

    def _scene_topology_error(self, linear_premult: np.ndarray) -> int:
        rgba = np.asarray(linear_premult, np.float32)
        alpha = np.clip(rgba[..., 3:4], 0.0, 1.0)
        linear = np.clip(rgba[..., :3] + (1.0 - alpha), 0.0, 1.0)
        srgb = np.where(
            linear <= 0.0031308, 12.92 * linear,
            1.055 * np.power(linear, 1.0 / 2.4) - 0.055,
        )
        ink = np.sum(np.abs(srgb - self._ink_background), axis=2) > (
            90.0 / 255.0
        )
        rendered = topology_signature(ink)
        return sum(
            abs(first - second)
            for first, second in zip(self._source_topology, rendered)
        )

    def _delivered_masks(
        self, candidate: MacroCandidate,
        *, source_candidate_id: str | None = None,
    ) -> tuple[
        np.ndarray, np.ndarray, float, tuple[tuple[str, float], ...],
        np.ndarray | None,
    ] | None:
        support = _candidate_support(self.reir, candidate)
        source_id = source_candidate_id or candidate.id
        shape = self._shape.get(source_id)
        if shape is not None:
            exact_macro: np.ndarray | None = None
            if candidate.hidden_geometry is not None:
                # Hidden carriers enter the visible master only as their
                # observed fragments.  Their full analytic geometry belongs
                # to the downstream layer proof and must not influence this
                # local visible-support court.
                delivered = np.asarray(shape.source_mask, bool)
            elif source_candidate_id is not None:
                if shape.primitive == "free_curve":
                    try:
                        rgba8 = render_shape_delivery(self.reir, candidate)
                    except Exception:
                        return None
                    if rgba8 is None:
                        return None
                    exact_macro = _rgba8_linear_premultiplied(rgba8)
                    delivered = exact_macro[..., 3] >= 0.50
                else:
                    delivered = _render_typed_shape(
                        candidate, (self.reir.height, self.reir.width),
                    )
                    if delivered is None:
                        return None
            else:
                delivered = (
                    shape.rendered_mask if shape.primitive in {
                    "circle", "ring", "ellipse", "rectangle",
                    "rounded_rectangle", "triangle", "quadrilateral", "star",
                    } else support
                )
            if (
                shape.primitive == "free_curve"
                and source_candidate_id is None
            ):
                try:
                    rgba8 = render_shape_delivery(self.reir, candidate)
                except Exception:
                    return None
                if rgba8 is None:
                    return None
                straight = np.asarray(rgba8, np.float32) / 255.0
                alpha = np.clip(straight[..., 3], 0.0, 1.0)
                exact_macro = np.zeros_like(straight, np.float32)
                exact_macro[..., :3] = (
                    _srgb_to_linear(straight[..., :3]) * alpha[..., None]
                )
                exact_macro[..., 3] = alpha
                delivered = alpha >= 0.50
            return (
                np.asarray(shape.source_mask, bool), np.asarray(delivered, bool),
                max(1.25, shape.boundary_p95_px + 0.75),
                (("symmetry", shape.angular_coverage),
                 ("semantic_confidence", min(1.0, shape.candidate.score_bounds.expected))),
                (
                    np.ascontiguousarray(exact_macro, np.float32)
                    if exact_macro is not None else None
                ),
            )
        group = self._groups.get(source_id)
        if group is not None:
            exact_macro = None
            if source_candidate_id is not None:
                rgba8 = render_group_delivery(
                    self.reir, candidate, self.phase5,
                )
                if rgba8 is None:
                    return None
                exact_macro = _rgba8_linear_premultiplied(rgba8)
                delivered = exact_macro[..., 3] >= 0.50
            else:
                delivered = np.zeros((self.reir.height, self.reir.width), bool)
                members = materialize_repeated_group_members(
                    group, self.phase5.shapes.records,
                )
                if not members:
                    return None
                for member in members:
                    rendered = _render_typed_shape(
                        member, (self.reir.height, self.reir.width),
                    )
                    if rendered is None:
                        return None
                    delivered |= rendered
            return (
                support, delivered, 2.0,
                (("equal_radius", 1.0), ("symmetry", 0.8)),
                exact_macro,
            )
        stroke = self._stroke.get(source_id)
        if stroke is not None:
            exact_macro = None
            delivered = np.asarray(stroke.rendered_mask, bool)
            if source_candidate_id is not None:
                rgba8 = render_stroke_delivery(
                    self.reir, candidate, self.phase5,
                )
                if rgba8 is None:
                    return None
                exact_macro = _rgba8_linear_premultiplied(rgba8)
                delivered = exact_macro[..., 3] >= 0.50
            return (
                np.asarray(stroke.source_mask, bool),
                delivered,
                max(1.5, stroke.boundary_p95_px + 0.75),
                (("stroke_width", float(np.exp(-stroke.width_cv))),
                 ("semantic_confidence", min(1.0, stroke.candidate.score_bounds.expected))),
                exact_macro,
            )
        text = self._text.get(source_id)
        if text is not None:
            line = self._lines.get(text.line_id)
            if line is None:
                return None
            try:
                rgba8 = render_text_delivery(self.reir, candidate, self.text)
            except Exception:
                return None
            if rgba8 is None:
                return None
            macro = _rgba8_linear_premultiplied(rgba8)
            alpha = macro[..., 3]
            delivered = alpha >= 0.50
            return (
                np.asarray(line.support_mask, bool), np.asarray(delivered, bool), 2.5,
                (("text_line", text.claims.baseline_consistency),
                 ("repeated_glyph", text.claims.repeated_glyph_agreement),
                 ("semantic_confidence", text.claims.ocr_readability)),
                np.ascontiguousarray(macro, np.float32),
            )
        appearance = self._appearance.get(source_id)
        if appearance is not None:
            rgba8 = render_appearance_delivery(
                self.reir, appearance,
                candidate if source_candidate_id is not None else None,
            )
            if rgba8 is None:
                return None
            macro = _rgba8_linear_premultiplied(rgba8)
            alpha = macro[..., 3]
            delivered = alpha > (1.0 / 1024.0)
            return (
                np.asarray(appearance.support_mask, bool), delivered, 1.5,
                (("semantic_confidence", min(
                    1.0, appearance.candidate.score_bounds.expected,
                )),),
                np.ascontiguousarray(macro, np.float32),
            )
        cleanup = self._cleanup.get(source_id)
        if cleanup is not None:
            rgba8 = render_codec_delivery(self.reir, cleanup)
            if rgba8 is None:
                return None
            straight = np.asarray(rgba8, np.float32) / 255.0
            alpha = np.clip(straight[..., 3], 0.0, 1.0)
            macro = np.zeros_like(straight, np.float32)
            macro[..., :3] = _srgb_to_linear(straight[..., :3]) * alpha[..., None]
            macro[..., 3] = alpha
            delivered = alpha > (1.0 / 1024.0)
            return (
                np.asarray(cleanup.support_mask, bool), delivered, 0.75,
                (
                    ("semantic_confidence", min(
                        1.0, cleanup.candidate.score_bounds.expected,
                    )),
                    ("codec_counterfactual", 1.0),
                ),
                np.ascontiguousarray(macro, np.float32),
            )
        return None

    def _certify(
        self, candidate: MacroCandidate, *, source_candidate_id: str | None = None,
        incumbent_candidate: MacroCandidate | None = None,
    ) -> MacroCandidate | None:
        if candidate.id in self._outcomes:
            return self._outcomes[candidate.id]
        self.considered += 1
        masks = self._delivered_masks(
            candidate, source_candidate_id=source_candidate_id,
        )
        if masks is None or (
            candidate.hidden_geometry is not None
            and candidate.id not in self._shape
        ):
            self.unsupported_delivery += 1; self.rejected += 1
            self._outcomes[candidate.id] = None
            return None
        evidence, delivered, tolerance, structural, exact_macro = masks
        if not np.any(evidence) or not np.any(delivered):
            self.rejected += 1
            self._outcomes[candidate.id] = None
            return None
        incumbent_masks = (
            self._delivered_masks(incumbent_candidate)
            if incumbent_candidate is not None else None
        )
        if incumbent_candidate is not None and incumbent_masks is None:
            self.rejected += 1
            self._outcomes[candidate.id] = None
            return None
        incumbent_delivered = (
            incumbent_masks[1] if incumbent_masks is not None else None
        )
        # Text replaces the observed stroke plus its one-pixel AA fringe.
        # Owning only the binary midline leaves the incumbent's quantized edge
        # bands underneath the clean glyph path, producing ghost components
        # and false counters in the final SVG.  Geometry and replacement
        # ownership remain distinct: only ``delivered`` is painted as ink.
        ownership_delivery = np.asarray(delivered, bool)
        text_record = self._text.get(source_candidate_id or candidate.id)
        if text_record is not None:
            line = self._lines.get(text_record.line_id)
            if line is not None:
                ownership_delivery = cv2.dilate(
                    np.asarray(evidence | delivered, np.uint8),
                    np.ones((3, 3), np.uint8),
                ).astype(bool)
                x1, y1, x2, y2 = line.roi_xyxy
                bounded = np.zeros_like(ownership_delivery)
                bounded[y1:y2, x1:x2] = ownership_delivery[y1:y2, x1:x2]
                ownership_delivery = bounded
        refinement: CellRefinementTransaction | None = None
        if source_candidate_id is None:
            try:
                boundary = cv2.morphologyEx(
                    ownership_delivery.astype(np.uint8), cv2.MORPH_GRADIENT,
                    np.ones((3, 3), np.uint8),
                ) > 0
                refinement = plan_local_refinement(
                    self.reir.cells, boundary, _bbox(ownership_delivery),
                    minimum_support=(1 if text_record is not None else 2),
                    provenance=(
                        "production-court:typed-delivery-boundary:"
                        + candidate.id
                    ),
                )
            except (ValueError, cv2.error):
                refinement = None
        if refinement is not None:
            self.refinement_planned += 1
        source_refined = (
            source_candidate_id is not None
            and source_candidate_id in self._refinement_transactions
        )
        ownership = (
            np.asarray(
                ownership_delivery | (
                    incumbent_delivered
                    if incumbent_delivered is not None
                    else np.zeros_like(delivered)
                ),
                bool,
            )
            if source_refined
            else np.asarray(ownership_delivery, bool)
        )
        # A visible macro must own every pixel its production delivery can
        # repaint.  Falling back to the old coarse ``core_bits`` here let the
        # master assign (for example) seven pixels to an ellipse while the SVG
        # writer painted its full 1,358-pixel geometry over atomic owners.  The
        # local court has already scored this exact delivery; the derived
        # lattice below either materialises this ownership or drops the column
        # fail-closed when its bounded cell budget cannot represent it.
        # The master removes every incumbent owner in ``core_bits``.  Court
        # must therefore score every pixel that can change, including owned
        # pixels the candidate fails to repaint.  Scoring only
        # evidence|delivery let a fragment earn credit while silently erasing
        # the rest of a coarse cell.
        claimed = evidence | delivered | ownership
        if incumbent_delivered is not None:
            claimed |= incumbent_delivered
        frozen_delivery = np.ascontiguousarray(delivered, bool)
        frozen_delivery.setflags(write=False)
        self._delivery_masks[candidate.id] = frozen_delivery
        frozen_ownership = np.ascontiguousarray(ownership, bool)
        frozen_ownership.setflags(write=False)
        self._ownership_masks[candidate.id] = frozen_ownership
        rollback_mask = np.ascontiguousarray(delivered | ownership, bool)
        rollback_mask.setflags(write=False)
        self._rollback_masks[candidate.id] = rollback_mask
        if not np.any(claimed):
            self.rejected += 1
            self._outcomes[candidate.id] = None
            return None
        roi = _bbox(claimed)
        x1, y1, x2, y2 = roi
        macro_full = (
            _solid_render(self.reir, delivered, sample_mask=evidence)
            if exact_macro is None else exact_macro
        )
        fallback_full = self.fallback
        fallback_alpha_mask = evidence
        if incumbent_masks is not None:
            (
                incumbent_evidence, incumbent_delivered, _incumbent_tolerance,
                _incumbent_structural, incumbent_exact_macro,
            ) = incumbent_masks
            incumbent_macro = (
                _solid_render(
                    self.reir, incumbent_delivered,
                    sample_mask=incumbent_evidence,
                )
                if incumbent_exact_macro is None else incumbent_exact_macro
            )
            fallback_full = _paint_canvas_background(
                self.fallback, ownership, self.canvas_background,
            )
            fallback_full = _over(incumbent_macro, fallback_full)
            fallback_alpha_mask = incumbent_delivered
        candidate_full = _paint_canvas_background(
            self.fallback, ownership, self.canvas_background,
        )
        # A typed macro replaces the incumbent owners of its exact core cells;
        # export first paints those cells with the canvas background, then any
        # fitted extension is composited over the remaining scene.
        candidate_full = _over(macro_full, candidate_full)
        # Topology belongs to the visible composite, not to the macro's alpha
        # silhouette in isolation.  A red/orange support can preserve its own
        # binary components while erasing white text counters in the actual
        # scene.  Reject that interaction in the cheap cascade before it can
        # consume an exact atlas request or enter the global master.
        if self._scene_topology_error(candidate_full) > self._scene_topology_error(
            fallback_full
        ):
            self.pruned += 1
            self.rejected += 1
            self._outcomes[candidate.id] = None
            return None
        candidate_patch = np.ascontiguousarray(candidate_full[y1:y2, x1:x2], np.float32)
        fallback_patch = np.ascontiguousarray(fallback_full[y1:y2, x1:x2], np.float32)
        candidate_patch.setflags(write=False); fallback_patch.setflags(write=False)
        expected_components = candidate.certificates.components
        expected_holes = candidate.certificates.holes
        candidate_court = CourtCandidate(
            id=candidate.id,
            request=RoiRenderRequest(
                id=f"{candidate.id}:candidate", roi_xyxy=roi, kind="raster",
                raster_premultiplied_linear_rgba=candidate_patch, supersample=4,
            ),
            claimed_support=claimed,
            certificate_alpha_mask=delivered,
            expected_components=expected_components, expected_holes=expected_holes,
            hard_topology=True, boundary_tolerance_px=tolerance,
            structural_claims=structural,
            risk=max(0.0, candidate.score_bounds.upper - candidate.score_bounds.lower),
            parameter_condition_number=max(candidate.covariance, default=1.0),
            core_bits=candidate.core_bits,
            interface_ids=candidate.boundary_interfaces,
            provenance=(*candidate.provenance, "production-delivery-court"),
        )
        fallback_court = CourtCandidate(
            id=f"{candidate.id}:atomic-fallback",
            request=RoiRenderRequest(
                id=f"{candidate.id}:fallback-render", roi_xyxy=roi, kind="raster",
                raster_premultiplied_linear_rgba=fallback_patch, supersample=4,
            ),
            claimed_support=claimed, hard_topology=False,
            certificate_alpha_mask=fallback_alpha_mask,
            boundary_tolerance_px=max(2.5, tolerance), core_bits=candidate.core_bits,
            interface_ids=candidate.boundary_interfaces,
            provenance=("atomic-leaf-median-fallback",),
        )
        # Two exact requests are required if the cheap cascade does not prune.
        if self.exact_requests + 2 > self.exact_request_limit:
            self.rejected += 1
            self._outcomes[candidate.id] = None
            return None
        decision = compare_in_local_court(
            self.reir.raster.linear_premultiplied_rgba, evidence,
            candidate_court, fallback_court, self.posterior,
            atlas=self.atlas, preference_tiebreaker=self.preference_tiebreaker,
        )
        self._decisions.append(decision)
        score_mask = np.asarray(claimed[y1:y2, x1:x2], bool)
        observed_patch = np.asarray(
            self.reir.raster.linear_premultiplied_rgba[y1:y2, x1:x2],
            np.float32,
        )
        candidate_error = float(np.mean(
            np.abs(candidate_patch[score_mask] - observed_patch[score_mask])
        ))
        fallback_error = float(np.mean(
            np.abs(fallback_patch[score_mask] - observed_patch[score_mask])
        ))
        evidence_union = int(np.sum(evidence | delivered))
        evidence_iou = float(
            np.sum(evidence & delivered) / max(1, evidence_union)
        )
        candidate_topology = (
            int(candidate.certificates.components or 0),
            int(candidate.certificates.holes or 0),
        )
        evidence_topology = (
            int(decision.candidate_bundle.topology.components),
            int(decision.candidate_bundle.topology.holes),
        )
        self._marginals[candidate.id] = CourtMarginalDelta(
            candidate_id=candidate.id,
            candidate_error=candidate_error,
            fallback_error=fallback_error,
            pixel_error_delta=candidate_error - fallback_error,
            evidence_iou=evidence_iou,
            topology_error=sum(
                abs(first - second)
                for first, second in zip(candidate_topology, evidence_topology)
            ),
            score_margin=decision.candidate_score - decision.fallback_score,
        )
        if not decision.candidate_selected:
            candidate_structure = decision.candidate_bundle.structural.score
            fallback_structure = decision.fallback_bundle.structural.score
            # The court certifies a bounded local Pareto *column pool*; the
            # faithful/balanced/idealized master chooses among those columns.
            # Requiring every idealized primitive to beat the raster-faithful
            # incumbent under one scalar weight made the idealized profile
            # empty by construction.  This exception is deliberately narrow:
            # hard proofs must pass, pixel loss is bounded, support remains
            # strong and there must be a measured structural gain.
            local_pareto = bool(
                decision.candidate_bundle.valid
                and decision.candidate_bundle.topology.valid
                and decision.candidate_bundle.geometry.valid
                and decision.candidate_score >= -0.50
                and candidate_error - fallback_error <= 0.020
                and evidence_iou >= 0.84
                and candidate_structure >= fallback_structure + 0.05
            )
            if local_pareto:
                stages = tuple(
                    (name, "local-pareto-column")
                    if name == "tie-policy" else (name, value)
                    for name, value in decision.stages
                )
                decision = replace(
                    decision, selected_id=candidate.id,
                    candidate_selected=True,
                    reason="local-pareto-column-admission",
                    stages=stages,
                    cascade=(*decision.cascade, (
                        "profile-pareto-admission",
                        "bounded-render-loss+structural-gain",
                    )),
                )
                self._decisions[-1] = decision
        self.approximate_requests += 2
        self.approximate_pixels += decision.approximate_render_pixels
        if decision.cascade_pruned_before_exact:
            self.pruned += 1
        else:
            self.exact_requests += 2
            self.exact_pixels += decision.exact_render_pixels
        if not decision.candidate_selected:
            self.rejected += 1
            self._outcomes[candidate.id] = None
            return None
        certified = bind_selected_proof(candidate, decision)
        if refinement is not None and refinement.accepted:
            self._refinement_transactions[candidate.id] = refinement
        self.certified += 1
        self._outcomes[candidate.id] = certified
        return certified

    def certify(self, candidate: MacroCandidate) -> MacroCandidate | None:
        return self._certify(candidate)

    def certify_refined(
        self, source_candidate_id: str, candidate: MacroCandidate,
    ) -> MacroCandidate | None:
        if source_candidate_id == candidate.id:
            raise ValueError("refined candidate must have a new immutable identity")
        source_record = next((
            rows[source_candidate_id]
            for rows in (
                self._shape, self._groups, self._stroke,
                self._appearance, self._text,
            )
            if source_candidate_id in rows
        ), None)
        if source_record is None:
            return None
        incumbent = source_record.candidate
        return self._certify(
            candidate, source_candidate_id=source_candidate_id,
            incumbent_candidate=incumbent,
        )

    def selection_compatible(
        self, selected: tuple[MacroCandidate, ...], candidate: MacroCandidate,
    ) -> bool:
        """Reject pixel-space conflicts hidden by coarse disjoint core bits."""
        candidate_text = self._text.get(candidate.id)
        candidate_line = (
            self._lines.get(candidate_text.line_id)
            if candidate_text is not None else None
        )
        if candidate_line is not None:
            cx1, cy1, cx2, cy2 = candidate_line.roi_xyxy
            candidate_width = max(1, cx2 - cx1)
            candidate_height = max(1, cy2 - cy1)
            for previous in selected:
                previous_text = self._text.get(previous.id)
                previous_line = (
                    self._lines.get(previous_text.line_id)
                    if previous_text is not None else None
                )
                if previous_line is None:
                    continue
                if previous_text.line_id == candidate_text.line_id:
                    return False
                px1, py1, px2, py2 = previous_line.roi_xyxy
                horizontal = max(0, min(cx2, px2) - max(cx1, px1))
                vertical = max(0, min(cy2, py2) - max(cy1, py1))
                same_lane = (
                    abs(candidate_line.baseline - previous_line.baseline)
                    <= 0.75 * max(
                        1.0, candidate_line.x_height,
                        previous_line.x_height,
                    )
                    and vertical / max(1, min(candidate_height, py2 - py1))
                    >= 0.35
                )
                # TextLine hypotheses spanning the same lane are alternatives,
                # not two paint layers.  Pixel-only conflicts miss this when
                # threshold variants contain complementary glyph fragments.
                if (
                    same_lane
                    and horizontal / max(1, min(candidate_width, px2 - px1))
                    >= 0.25
                ):
                    return False
        candidate_mask = self._ownership_masks.get(candidate.id)
        if candidate_mask is None:
            return False
        kernel = np.ones((3, 3), np.uint8)
        candidate_boundary = cv2.morphologyEx(
            candidate_mask.astype(np.uint8), cv2.MORPH_GRADIENT, kernel,
        ) > 0
        for previous in selected:
            previous_mask = self._ownership_masks.get(previous.id)
            if previous_mask is None:
                return False
            overlap = candidate_mask & previous_mask
            if not np.any(overlap):
                continue
            previous_boundary = cv2.morphologyEx(
                previous_mask.astype(np.uint8), cv2.MORPH_GRADIENT, kernel,
            ) > 0
            # One-pixel AA contact may be shared by adjacent vector regions;
            # any interior double paint is an incompatible visible program.
            interior_overlap = overlap & ~(candidate_boundary & previous_boundary)
            if np.any(interior_overlap):
                return False
        return True

    def rollback_mask(self, candidate_id: str) -> np.ndarray | None:
        return self._rollback_masks.get(candidate_id)

    def delivery_mask(self, candidate_id: str) -> np.ndarray | None:
        return self._delivery_masks.get(candidate_id)

    def ownership_mask(self, candidate_id: str) -> np.ndarray | None:
        return self._ownership_masks.get(candidate_id)

    def refinement_transaction(
        self, candidate_id: str,
    ) -> CellRefinementTransaction | None:
        return self._refinement_transactions.get(candidate_id)

    def marginal_blame_order(
        self, selected_ids: tuple[str, ...], *, topology_regressed: bool,
        support_regressed: bool, pixels_regressed: bool,
        complexity_regressed: bool,
    ) -> tuple[str, ...]:
        rows = [
            self._marginals[candidate_id]
            for candidate_id in selected_ids
            if candidate_id in self._marginals
        ]
        def blame(row: CourtMarginalDelta) -> tuple[float, str]:
            value = 0.0
            if topology_regressed:
                value += 100.0 * row.topology_error
            if support_regressed:
                value += 12.0 * max(0.0, 1.0 - row.evidence_iou)
            if pixels_regressed:
                value += 24.0 * max(0.0, row.pixel_error_delta)
            if complexity_regressed:
                value += 1.0 / max(1e-6, 1.0 + max(0.0, row.score_margin))
            # Always provide a deterministic weakest-link order when the
            # global artifact is an interaction not visible in one metric.
            value += 0.05 * max(0.0, 1.0 - row.evidence_iou)
            value += 0.01 / max(1e-6, 1.0 + max(0.0, row.score_margin))
            return value, row.candidate_id
        return tuple(
            row.candidate_id for row in sorted(
                rows, key=lambda row: (-blame(row)[0], blame(row)[1]),
            )
        )

    def rollback_closure(
        self, selected_ids: tuple[str, ...], seeds: tuple[str, ...],
    ) -> tuple[str, ...]:
        selected = tuple(
            candidate_id for candidate_id in selected_ids
            if candidate_id in self._rollback_masks
        )
        closure = set(seeds)
        changed = True
        while changed:
            changed = False
            union = np.zeros((self.reir.height, self.reir.width), bool)
            for candidate_id in closure:
                mask = self._rollback_masks.get(candidate_id)
                if mask is not None:
                    union |= mask
            for candidate_id in selected:
                if candidate_id in closure:
                    continue
                delivered = self._delivery_masks[candidate_id]
                if np.any(union & delivered):
                    closure.add(candidate_id); changed = True
        return tuple(sorted(closure))

    def audit(self) -> ProductionCourtAudit:
        return ProductionCourtAudit(
            considered=self.considered, certified=self.certified,
            rejected=self.rejected, unsupported_delivery=self.unsupported_delivery,
            pruned_before_exact=self.pruned,
            approximate_render_requests=self.approximate_requests,
            exact_render_requests=self.exact_requests,
            approximate_render_pixels=self.approximate_pixels,
            exact_render_pixels=self.exact_pixels,
            local_refinements_planned=self.refinement_planned,
            local_refinements_accepted=len(self._refinement_transactions),
            decisions=tuple(self._decisions),
            marginals=tuple(sorted(
                self._marginals.values(), key=lambda row: row.candidate_id,
            )),
        )
