"""Phase-4 TextLine macro generator over immutable REIR evidence.

Text is proposed before appearance commit.  Exact-font, font-free dual-loop
and conservative-outline hypotheses are emitted together; none mutates the
fallback scene.  Hard topology claims are measured from persistent line
support and travel with every generated CMIR column for the phase-3 court.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import os
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING

import cv2
import numpy as np

from .certificates import mask_sha256, topology_signature
from .evidence_ir import RasterEvidenceIR
from .macro_ir import MacroCandidate, MacroKind, SceneProgram, ScoreBounds
from .macro_registry import candidate_from_support, decode_token_mask
from .proposal_net import query_support_mask

if TYPE_CHECKING:
    from .proposal_net import ProposalQuery


@dataclass(frozen=True)
class GlyphObservation:
    id: str
    bbox_xyxy: tuple[int, int, int, int]
    support_mask: np.ndarray
    components: int
    holes: int
    baseline: float
    height: float
    stem_width: float
    descriptor: tuple[float, ...]
    semantic_character: str | None = None

    def validate(self, shape: tuple[int, int]) -> None:
        x1, y1, x2, y2 = self.bbox_xyxy
        if not (0 <= x1 < x2 <= shape[1] and 0 <= y1 < y2 <= shape[0]):
            raise ValueError("glyph bbox lies outside the REIR canvas")
        if (
            self.support_mask.shape != (y2 - y1, x2 - x1)
            or self.support_mask.flags.writeable
        ):
            raise ValueError("glyph support must be immutable and bbox-local")
        if not np.any(self.support_mask) or self.components <= 0 or self.holes < 0:
            raise ValueError("glyph observation has invalid topology/support")


@dataclass(frozen=True)
class JointLineAppearance:
    foreground_linear_rgba: tuple[float, float, float, float]
    background_linear_rgba: tuple[float, float, float, float]
    foreground_oklab: tuple[float, float, float]
    soft_coverage_mean: float
    robust_scale: float
    multi_color_groups: tuple[tuple[int, tuple[float, float, float, float]], ...]


@dataclass(frozen=True)
class TextEffectLayer:
    """One source-observed layer of a compound text treatment.

    The mask is stored separately from the union owned by the macro so export
    can preserve outline/shadow ordering instead of flattening every treatment
    into one median-colour path.
    """
    role: str
    support_mask: np.ndarray
    straight_rgba: tuple[float, float, float, float]
    offset_xy: tuple[int, int] = (0, 0)

    def validate(self, shape: tuple[int, int]) -> None:
        if self.role not in {"fill", "outline", "shadow", "knockout"}:
            raise ValueError("unknown text effect role")
        if (
            self.support_mask.shape != shape
            or self.support_mask.flags.writeable
            or not np.any(self.support_mask)
        ):
            raise ValueError("text effect support is invalid")
        if len(self.straight_rgba) != 4 or not all(
            math.isfinite(value) and 0.0 <= value <= 1.0
            for value in self.straight_rgba
        ):
            raise ValueError("text effect colour is invalid")


@dataclass(frozen=True)
class TextLineProposal:
    id: str
    roi_xyxy: tuple[int, int, int, int]
    support_mask: np.ndarray
    polarity: str
    sources: tuple[str, ...]
    score: float
    baseline: float
    x_height: float
    cap_height: float
    overshoot: float
    slant: float
    tracking: float
    stem_classes: tuple[float, ...]
    glyphs: tuple[GlyphObservation, ...]
    appearance: JointLineAppearance

    def validate(self, reir: RasterEvidenceIR) -> None:
        shape = (reir.height, reir.width)
        if self.support_mask.shape != shape or self.support_mask.flags.writeable:
            raise ValueError("TextLine support must be immutable and canvas-sized")
        if not self.id or not np.any(self.support_mask) or not self.glyphs:
            raise ValueError("TextLine proposal lacks identity/support/glyphs")
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("TextLine proposal score is invalid")
        x1, y1, x2, y2 = self.roi_xyxy
        if not (0 <= x1 < x2 <= reir.width and 0 <= y1 < y2 <= reir.height):
            raise ValueError("TextLine ROI lies outside REIR")
        for glyph in self.glyphs:
            glyph.validate(shape)


@dataclass(frozen=True)
class _LineMaskDraft:
    mask: np.ndarray
    polarity: str
    sources: tuple[str, ...]
    raw_score: float


@dataclass(frozen=True)
class DualLoopGlyphProgram:
    glyph_id: str
    positive_loops: tuple[tuple[tuple[float, float], ...], ...]
    negative_loops: tuple[tuple[tuple[float, float], ...], ...]
    topology_code: tuple[int, int]
    sdf_level: float
    skeleton_width: float


@dataclass(frozen=True)
class GlyphPrototype:
    id: str
    member_ids: tuple[str, ...]
    normalized_mask: np.ndarray
    instance_affines: tuple[tuple[str, tuple[float, ...]], ...]
    residual_fraction: tuple[tuple[str, float], ...]
    iterations: int


@dataclass(frozen=True)
class ExactFontEvidence:
    id: str
    font_file: str
    recognized_text: str
    support_mask: np.ndarray
    retrieval_score: float
    silhouette_iou: float
    max_boundary_deviation_px: float
    tracking_em: float
    x_scale: float
    y_scale: float
    offset_xy: tuple[float, float]
    provenance: tuple[str, ...] = ()


ExactFontProvider = Callable[
    [RasterEvidenceIR, TextLineProposal], Iterable[ExactFontEvidence]
]


@dataclass(frozen=True)
class TextCertificateClaims:
    required_components: int
    persistent_counters: int
    no_unproven_fusion: bool
    no_unproven_hole_fill: bool
    no_glyph_outside_line_support: bool
    ocr_readability: float
    baseline_consistency: float
    stem_consistency: float
    repeated_glyph_agreement: float
    line_render_evidence: float

    @property
    def hard_valid(self) -> bool:
        return all((
            self.required_components > 0,
            self.persistent_counters >= 0,
            self.no_unproven_fusion,
            self.no_unproven_hole_fill,
            self.no_glyph_outside_line_support,
        ))


@dataclass(frozen=True)
class TextMacroRecord:
    candidate: MacroCandidate
    line_id: str
    path: str
    claims: TextCertificateClaims
    dual_loop_glyphs: tuple[DualLoopGlyphProgram, ...]
    prototypes: tuple[GlyphPrototype, ...]
    effect_layers: tuple[TextEffectLayer, ...] = ()


@dataclass(frozen=True)
class TextMacroSet:
    proposals: tuple[TextLineProposal, ...]
    records: tuple[TextMacroRecord, ...]
    exact_font_attempted: int
    exact_font_admitted: int
    provenance: tuple[str, ...]

    @property
    def candidates(self) -> tuple[MacroCandidate, ...]:
        return tuple(record.candidate for record in self.records)


@dataclass(frozen=True)
class TextLineCourtDecision:
    """One source-only TextLine replacement decision with legacy fallback."""

    selected_id: str | None
    selected_path: str
    support_mask: np.ndarray
    fallback_used: bool
    selected_score: float
    fallback_score: float
    exact_candidates_evaluated: int
    reason: str
    ranking: tuple[tuple[str, str, float], ...]
    preserved_fallback_mask: np.ndarray | None = None

    def validate(self, reir: RasterEvidenceIR) -> None:
        if (
            self.support_mask.shape != (reir.height, reir.width)
            or self.support_mask.flags.writeable
        ):
            raise ValueError("TextLine court support must be immutable REIR support")
        if not math.isfinite(self.selected_score) or not math.isfinite(
            self.fallback_score
        ):
            raise ValueError("TextLine court emitted a non-finite score")
        if self.preserved_fallback_mask is not None and (
            self.preserved_fallback_mask.shape != (
                reir.height, reir.width,
            )
            or self.preserved_fallback_mask.flags.writeable
        ):
            raise ValueError(
                "preserved fallback support must be immutable REIR support"
            )


def _freeze_mask(mask: np.ndarray) -> np.ndarray:
    result = np.ascontiguousarray(mask, dtype=bool)
    result.setflags(write=False)
    return result


def _candidate_support(candidate: MacroCandidate, shape: tuple[int, int]) -> np.ndarray:
    """Decode a CMIR support certificate without consulting source/GT state."""
    width, height = candidate.certificates.support_size
    count = width * height
    flat = np.zeros(count, bool)
    if candidate.certificates.support_bits:
        flat = np.unpackbits(
            np.frombuffer(candidate.certificates.support_bits, np.uint8),
            count=count, bitorder="little",
        ).astype(bool, copy=False)
    else:
        for start, length in candidate.certificates.support_rle:
            flat[start:start + length] = True
    mask = flat.reshape((height, width))
    if mask.shape != shape:
        mask = cv2.resize(
            mask.astype(np.uint8), (shape[1], shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    return np.asarray(mask, bool)


def _bbox(mask: np.ndarray, *, pad: int = 1) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("cannot bound an empty mask")
    return (
        max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + 1 + pad),
        min(mask.shape[0], int(ys.max()) + 1 + pad),
    )


def _topology(mask: np.ndarray) -> tuple[int, int]:
    return topology_signature(np.asarray(mask, np.uint8))


def _vertically_registered_composite_glyph(mask: np.ndarray) -> bool:
    """Prove that detached components form one narrow glyph-like symbol.

    This covers dot/stem constructions such as ``i``, ``!`` and ``:`` without
    collapsing adjacent letters.  A neural glyph-group envelope is still
    required by the caller; this function only certifies the physical layout.
    """
    source = np.asarray(mask, np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        source, 8,
    )
    components = count - 1
    if not 2 <= components <= 4:
        return False
    x1, y1, x2, y2 = _bbox(source > 0, pad=0)
    width = x2 - x1; height = y2 - y1
    if width / max(1.0, height) > 1.60:
        return False
    component_widths = stats[1:, cv2.CC_STAT_WIDTH].astype(np.float64)
    component_areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
    centers_x = centroids[1:, 0]
    centers_y = centroids[1:, 1]
    center_tolerance = max(1.5, 0.45 * float(np.median(component_widths)))
    if float(np.max(np.abs(centers_x - np.median(centers_x)))) > center_tolerance:
        return False
    if float(np.ptp(centers_y)) < 0.22 * height:
        return False
    return bool(float(np.min(component_areas)) >= max(2.0, 0.01 * source.sum()))


def enclosed_negative_loops(mask: np.ndarray) -> np.ndarray:
    """Return complement components fully enclosed by a positive carrier."""
    source = np.asarray(mask, bool)
    if not np.any(source):
        return _freeze_mask(np.zeros_like(source))
    x1, y1, x2, y2 = _bbox(source, pad=0)
    inverse = (~source[y1:y2, x1:x2]).astype(np.uint8)
    count, labels = cv2.connectedComponents(inverse, 8)
    local = np.zeros_like(inverse, bool)
    for label in range(1, count):
        component = labels == label
        if (
            np.any(component[0]) or np.any(component[-1])
            or np.any(component[:, 0]) or np.any(component[:, -1])
        ):
            continue
        local |= component
    result = np.zeros_like(source)
    result[y1:y2, x1:x2] = local
    return _freeze_mask(result)


def _stem_width(mask: np.ndarray) -> float:
    source = np.asarray(mask, np.uint8)
    # A tightly cropped solid component has no zero sample; OpenCV then emits
    # its distance sentinel.  One explicit outside pixel makes the physical
    # width finite and crop-invariant.
    padded = np.pad(source, 1, mode="constant", constant_values=0)
    distance = cv2.distanceTransform(padded, cv2.DIST_L2, 5)[1:-1, 1:-1]
    ridge = distance >= cv2.dilate(
        distance, np.ones((3, 3), np.float32)
    ) - 1e-5
    values = distance[ridge & (distance > 0.35)]
    return float(2.0 * np.median(values)) if len(values) else 1.0


def _descriptor(
    mask: np.ndarray, *, components: int | None = None,
    holes: int | None = None,
) -> tuple[float, ...]:
    local = np.asarray(mask, np.uint8)
    moments = cv2.moments(local)
    hu = cv2.HuMoments(moments).ravel()
    hu = -np.sign(hu) * np.log10(np.maximum(np.abs(hu), 1e-30))
    if components is None or holes is None:
        components, holes = _topology(local)
    # Connected-component stats already crop exactly to the component bbox.
    occupancy = float(local.mean())
    return tuple(float(value) for value in hu) + (
        float(components), float(holes), occupancy,
    )


def _glyph_local_shape(mask: np.ndarray, area: int) -> tuple[int, int, float]:
    """Exact counter count plus a cheap physical stroke-width estimate.

    ``connectedComponentsWithStats`` has already proved that this crop is one
    8-connected glyph.  Re-running connected components and a distance field
    for every glyph was redundant.  The hydraulic width ``2A/P`` is the
    standard scale estimate for stroke-like regions and uses the same contour
    tree that certifies counters.
    """
    contours, hierarchy = cv2.findContours(
        np.asarray(mask, np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
    )
    holes = 0
    perimeter = 0.0
    if hierarchy is not None:
        for index, contour in enumerate(contours):
            perimeter += float(cv2.arcLength(contour, True))
            depth = 0
            parent = int(hierarchy[0, index, 3])
            while parent >= 0:
                depth += 1
                parent = int(hierarchy[0, parent, 3])
            holes += int(depth % 2 == 1)
    width = max(1.0, 2.0 * float(area) / max(1.0, perimeter))
    return 1, holes, width


def _glyph_observations(mask: np.ndarray, line_id: str) -> tuple[GlyphObservation, ...]:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        np.asarray(mask, np.uint8), 8
    )
    rows: list[GlyphObservation] = []
    for label in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[label])
        if area <= 0:
            continue
        local = labels[y:y + height, x:x + width] == label
        components, holes, stem_width = _glyph_local_shape(local, area)
        frozen = _freeze_mask(local)
        rows.append(GlyphObservation(
            id=f"{line_id}-glyph-{len(rows):03d}",
            bbox_xyxy=(x, y, x + width, y + height),
            support_mask=frozen, components=components, holes=holes,
            baseline=float(y + height), height=float(height),
            stem_width=stem_width, descriptor=_descriptor(
                local, components=components, holes=holes,
            ),
        ))
    return tuple(sorted(rows, key=lambda row: (row.bbox_xyxy[0], row.bbox_xyxy[1])))


def _semantic_glyph_observations(
    mask: np.ndarray, line_id: str, recognized_text: str,
) -> tuple[GlyphObservation, ...]:
    """Group fragments by OCR-ordered glyph cells, never by filename/GT.

    Connected components are not glyphs: a damaged ``M`` may split and an
    outlined word may remain connected.  This grouping supplies the missing
    prototype assignments while leaving source support unchanged.
    """
    contract = _ocr_semantic_topology_contract(recognized_text)
    if contract is None:
        return ()
    glyphs, _expected_counters = contract
    source = np.asarray(mask, bool)
    x1, y1, x2, y2 = _bbox(source, pad=0)
    edges = _ocr_evidence_glyph_cell_edges(source, recognized_text)
    if len(edges) != len(glyphs) + 1:
        return ()
    rows = []
    for index, character in enumerate(glyphs):
        left = x1 + edges[index]
        right = x1 + edges[index + 1]
        cell = source[y1:y2, left:right]
        ys, xs = np.nonzero(cell)
        if not len(xs):
            return ()
        gx1 = left + int(xs.min()); gx2 = left + int(xs.max()) + 1
        gy1 = y1 + int(ys.min()); gy2 = y1 + int(ys.max()) + 1
        local = source[gy1:gy2, gx1:gx2]
        components, holes = _topology(local)
        if components <= 0:
            return ()
        frozen = _freeze_mask(local)
        rows.append(GlyphObservation(
            id=f"{line_id}-semantic-glyph-{index:03d}",
            bbox_xyxy=(gx1, gy1, gx2, gy2), support_mask=frozen,
            components=components, holes=holes,
            baseline=float(gy2), height=float(gy2 - gy1),
            stem_width=_stem_width(local),
            descriptor=_descriptor(
                local, components=components, holes=holes,
            ),
            semantic_character=character,
        ))
    return tuple(rows)


def _joint_appearance(reir: RasterEvidenceIR, mask: np.ndarray) -> JointLineAppearance:
    # Appearance is line-local.  Cropping before dilation/statistics keeps the
    # work proportional to the proposed TextLine instead of the full canvas;
    # the two-pixel pad is exactly the support of the 5x5 ring kernel.
    x1, y1, x2, y2 = _bbox(mask, pad=2)
    local_mask = np.asarray(mask[y1:y2, x1:x2], bool)
    rgba = reir.raster.linear_premultiplied_rgba[y1:y2, x1:x2]
    oklab = reir.raster.oklab[y1:y2, x1:x2]
    dilated = cv2.dilate(
        local_mask.astype(np.uint8), np.ones((5, 5), np.uint8)
    ) > 0
    ring = dilated & ~local_mask
    foreground_pixels = rgba[local_mask]
    foreground = np.median(foreground_pixels, axis=0)
    background = np.median(rgba[ring], axis=0) if np.any(ring) else np.zeros(4)
    foreground_lab = np.median(oklab[local_mask], axis=0)
    residual = np.linalg.norm(foreground_pixels[:, :3] - foreground[:3], axis=1)
    scale = float(1.4826 * np.median(np.abs(residual - np.median(residual))))
    colors = np.clip(
        np.round(foreground_pixels[:, :3] * 15.0), 0, 15
    ).astype(np.int32)
    keys = colors[:, 0] * 256 + colors[:, 1] * 16 + colors[:, 2]
    multi: list[tuple[int, tuple[float, float, float, float]]] = []
    if len(keys):
        histogram = np.bincount(keys, minlength=4096)
        for key in np.argsort(histogram)[-3:][::-1]:
            if histogram[key] < max(3, int(0.12 * len(keys))):
                continue
            value = np.median(foreground_pixels[keys == key], axis=0)
            multi.append((int(histogram[key]), tuple(float(v) for v in value)))
    return JointLineAppearance(
        foreground_linear_rgba=tuple(float(value) for value in foreground),
        background_linear_rgba=tuple(float(value) for value in background),
        foreground_oklab=tuple(float(value) for value in foreground_lab),
        soft_coverage_mean=float(np.mean(
            reir.coverage_alpha[y1:y2, x1:x2][local_mask]
        )),
        robust_scale=max(0.0, scale), multi_color_groups=tuple(multi),
    )


def _effect_rgba(
    reir: RasterEvidenceIR, mask: np.ndarray,
) -> tuple[float, float, float, float]:
    values = reir.raster.straight_rgba[np.asarray(mask, bool)]
    median = np.clip(np.median(values, axis=0), 0.0, 1.0)
    return tuple(float(value) for value in median)


def _shift_mask(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    result = np.zeros_like(mask, dtype=bool)
    source_x1 = max(0, -dx); source_x2 = min(mask.shape[1], mask.shape[1] - dx)
    source_y1 = max(0, -dy); source_y2 = min(mask.shape[0], mask.shape[0] - dy)
    if source_x1 >= source_x2 or source_y1 >= source_y2:
        return result
    result[
        source_y1 + dy:source_y2 + dy,
        source_x1 + dx:source_x2 + dx,
    ] = mask[source_y1:source_y2, source_x1:source_x2]
    return result


def _shifted_overlap_counts(
    source: np.ndarray, target: np.ndarray, dx: int, dy: int,
) -> tuple[int, int]:
    """Return overlap and retained shifted-source area without allocation."""
    height, width = source.shape
    source_x1 = max(0, -dx)
    source_x2 = min(width, width - dx)
    source_y1 = max(0, -dy)
    source_y2 = min(height, height - dy)
    if source_x1 >= source_x2 or source_y1 >= source_y2:
        return 0, 0
    source_view = source[source_y1:source_y2, source_x1:source_x2]
    target_view = target[
        source_y1 + dy:source_y2 + dy,
        source_x1 + dx:source_x2 + dx,
    ]
    return (
        int(np.count_nonzero(source_view & target_view)),
        int(np.count_nonzero(source_view)),
    )


def classify_text_effect_layers(
    reir: RasterEvidenceIR, line: TextLineProposal,
) -> tuple[TextEffectLayer, ...]:
    """Recover source-observed outline, shadow, and knockout text roles.

    This classifier is deliberately proposal-only.  It partitions the already
    certified line support and never invents pixels.  Weak or ambiguous colour
    relations return no compound operator, leaving the ordinary font-free and
    atomic columns available.
    """
    support = np.asarray(line.support_mask, bool)
    shape = support.shape
    if "multi-counter-outlined-word" in line.sources:
        layer = TextEffectLayer(
            "outline", _freeze_mask(support), _effect_rgba(reir, support),
        )
        layer.validate(shape)
        return (layer,)

    # A real knockout exposes the border-connected canvas through a locally
    # different carrier.  Similarity to generic white is insufficient: require
    # agreement with the actual canvas corners and disagreement with the local
    # ring around the line.
    if line.polarity == "light-on-dark" or "top-layer-clue" in line.sources:
        x1, y1, x2, y2 = _bbox(support, pad=2)
        local = support[y1:y2, x1:x2]
        ring = cv2.dilate(local.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        ring &= ~local
        lab = reir.raster.oklab
        canvas_lab = np.median(np.asarray((
            lab[0, 0], lab[0, -1], lab[-1, 0], lab[-1, -1],
        )), axis=0)
        ink_lab = np.median(lab[support], axis=0)
        local_lab = lab[y1:y2, x1:x2]
        surround_lab = np.median(local_lab[ring], axis=0) if np.any(ring) else canvas_lab
        if (
            float(np.linalg.norm(ink_lab - canvas_lab)) <= 0.055
            and float(np.linalg.norm(surround_lab - canvas_lab)) >= 0.10
        ):
            layer = TextEffectLayer(
                "knockout", _freeze_mask(support), _effect_rgba(reir, support),
            )
            layer.validate(shape)
            return (layer,)

    color_groups = line.appearance.multi_color_groups
    if len(color_groups) < 2:
        return ()
    first_count, first_rgba = color_groups[0]
    second_count, second_rgba = color_groups[1]
    if (
        second_count < max(8, int(0.12 * (first_count + second_count)))
        or float(np.linalg.norm(
            np.asarray(first_rgba[:3]) - np.asarray(second_rgba[:3])
        )) < 0.10
    ):
        return ()

    pixels = reir.raster.oklab[support].astype(np.float64)
    if len(pixels) < 16:
        return ()
    # Deterministic two-colour robust clustering.  Principal-axis endpoints
    # avoid OpenCV's process-global RNG and make repeated compilation exact.
    centered = pixels - np.mean(pixels, axis=0)
    try:
        covariance = centered.T @ centered / max(1, len(centered) - 1)
        _eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    except np.linalg.LinAlgError:
        return ()
    axis = eigenvectors[:, -1]
    projection = centered @ axis
    # Use tail seeds rather than quartiles: a visible drop shadow is commonly
    # only the narrow, unoccluded 10--20% remainder of a translated glyph.
    low, high = np.quantile(projection, (0.05, 0.95))
    centres = np.asarray((
        np.median(pixels[projection <= low], axis=0),
        np.median(pixels[projection >= high], axis=0),
    ))
    for _ in range(5):
        distance = np.linalg.norm(pixels[:, None, :] - centres[None, :, :], axis=2)
        labels = np.argmin(distance, axis=1)
        if any(np.sum(labels == index) == 0 for index in (0, 1)):
            return ()
        updated = np.asarray([
            np.median(pixels[labels == index], axis=0) for index in (0, 1)
        ])
        if np.allclose(updated, centres, atol=1e-7):
            break
        centres = updated
    counts = tuple(int(np.sum(labels == index)) for index in (0, 1))
    if (
        min(counts) < max(8, int(0.12 * len(pixels)))
        or float(np.linalg.norm(centres[0] - centres[1])) < 0.085
    ):
        return ()
    masks = []
    ys, xs = np.nonzero(support)
    for index in (0, 1):
        mask = np.zeros(shape, bool)
        selected = labels == index
        mask[ys[selected], xs[selected]] = True
        masks.append(mask)

    height = max(1, line.roi_xyxy[3] - line.roi_xyxy[1])
    spatial_centres = []
    for mask in masks:
        mask_y, mask_x = np.nonzero(mask)
        spatial_centres.append((float(np.mean(mask_x)), float(np.mean(mask_y))))
    centre_separation = float(np.linalg.norm(
        np.subtract(spatial_centres[0], spatial_centres[1])
    )) / height
    # Different colours assigned to different letters (or to an adjacent
    # logomark and word) are still source-observed appearance.  They are not an
    # outline or a shadow, but collapsing them to the line-wide median colour
    # is destructive.  Preserve the exact support partition as independent
    # fill layers.  The masks are disjoint and their union is the certified
    # line support, so this adds no inferred geometry.
    if centre_separation > 0.75:
        ordered = sorted(
            range(2),
            key=lambda index: (
                spatial_centres[index][0], spatial_centres[index][1], index,
            ),
        )
        fills = tuple(
            TextEffectLayer(
                "fill", _freeze_mask(masks[index]),
                _effect_rgba(reir, masks[index]),
            )
            for index in ordered
        )
        for layer in fills:
            layer.validate(shape)
        return fills

    # Outline colours hug a fill and remain concentric.  Test this cheap
    # relation before the translation search; a displaced shadow cannot pass
    # the tight centroid wall.
    if centre_separation <= 0.15:
        radius = max(1, min(4, int(round(0.12 * height))))
        kernel = np.ones((2 * radius + 1, 2 * radius + 1), np.uint8)
        outline_rows: list[tuple[float, int, int]] = []
        for fill_index, outline_index in ((0, 1), (1, 0)):
            fill_mask = masks[fill_index]
            outline_mask = masks[outline_index]
            near = cv2.dilate(fill_mask.astype(np.uint8), kernel) > 0
            agreement = int(np.sum(outline_mask & near)) / max(
                1, int(np.sum(outline_mask)),
            )
            outline_rows.append((float(agreement), fill_index, outline_index))
        agreement, fill_index, outline_index = max(outline_rows)
        if agreement >= 0.82:
            outline = TextEffectLayer(
                "outline", _freeze_mask(masks[outline_index]),
                _effect_rgba(reir, masks[outline_index]),
            )
            fill = TextEffectLayer(
                "fill", _freeze_mask(masks[fill_index]),
                _effect_rgba(reir, masks[fill_index]),
            )
            outline.validate(shape); fill.validate(shape)
            return (outline, fill)

    maximum_offset = max(1, min(6, int(round(0.20 * height))))
    crop_x1, crop_y1, crop_x2, crop_y2 = _bbox(
        support, pad=maximum_offset,
    )
    cropped_masks = tuple(
        mask[crop_y1:crop_y2, crop_x1:crop_x2] for mask in masks
    )
    cropped_areas = tuple(int(np.count_nonzero(mask)) for mask in cropped_masks)
    best: tuple[float, int, int, int, int] | None = None
    for source_index, shadow_index in ((0, 1), (1, 0)):
        source = cropped_masks[source_index]
        shadow = cropped_masks[shadow_index]
        shadow_area = cropped_areas[shadow_index]
        for dy in range(-maximum_offset, maximum_offset + 1):
            for dx in range(-maximum_offset, maximum_offset + 1):
                if dx == 0 and dy == 0:
                    continue
                overlap, shifted_area = _shifted_overlap_counts(
                    source, shadow, dx, dy,
                )
                agreement = overlap / max(
                    1, min(shifted_area, shadow_area),
                )
                row = (float(agreement), source_index, shadow_index, dx, dy)
                if best is None or row > best:
                    best = row
    if best is not None and best[0] >= 0.58:
        _agreement, source_index, shadow_index, dx, dy = best
        shadow = TextEffectLayer(
            "shadow", _freeze_mask(masks[shadow_index]),
            _effect_rgba(reir, masks[shadow_index]), (dx, dy),
        )
        fill = TextEffectLayer(
            "fill", _freeze_mask(masks[source_index]),
            _effect_rgba(reir, masks[source_index]),
        )
        shadow.validate(shape); fill.validate(shape)
        return (shadow, fill)

    return ()


def _component_rows(mask: np.ndarray) -> list[tuple[np.ndarray, tuple[int, int, int, int]]]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        np.asarray(mask, np.uint8), 8
    )
    result = []
    for label in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[label])
        if area < 1 or height < 2 or width > max(4, 5 * height):
            continue
        result.append((labels == label, (x, y, x + width, y + height)))
    return result


def _persistent_text_support(mask: np.ndarray) -> np.ndarray:
    """Remove non-persistent codec/color flecks without erasing diacritics.

    Area >=4 components are persistent at native resolution.  Two/three-pixel
    components survive only when they are spatially attached to the glyph row
    (diacritics and punctuation); isolated one-pixel evidence never becomes a
    TextLine column.  Tiny enclosed holes are filled, while all larger counters
    remain explicit negative loops.
    """
    source = np.asarray(mask, bool)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        source.astype(np.uint8), 8,
    )
    large = [
        label for label in range(1, count)
        if int(stats[label, cv2.CC_STAT_AREA]) >= 4
        and int(stats[label, cv2.CC_STAT_HEIGHT]) >= 2
    ]
    result = np.zeros(source.shape, bool)
    for label in large:
        result |= labels == label
    if large:
        heights = [int(stats[label, cv2.CC_STAT_HEIGHT]) for label in large]
        baselines = [
            int(stats[label, cv2.CC_STAT_TOP] + stats[label, cv2.CC_STAT_HEIGHT])
            for label in large
        ]
        row_height = max(2.0, float(np.median(heights)))
        row_baseline = float(np.median(baselines))
        large_boxes = [
            (
                int(stats[label, cv2.CC_STAT_LEFT]),
                int(stats[label, cv2.CC_STAT_TOP]),
                int(stats[label, cv2.CC_STAT_LEFT] + stats[label, cv2.CC_STAT_WIDTH]),
                int(stats[label, cv2.CC_STAT_TOP] + stats[label, cv2.CC_STAT_HEIGHT]),
            )
            for label in large
        ]
        for label in range(1, count):
            if label in large:
                continue
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < 2:
                continue
            x1 = int(stats[label, cv2.CC_STAT_LEFT])
            y1 = int(stats[label, cv2.CC_STAT_TOP])
            x2 = x1 + int(stats[label, cv2.CC_STAT_WIDTH])
            y2 = y1 + int(stats[label, cv2.CC_STAT_HEIGHT])
            attached = any(
                x1 <= bx2 + 1 and x2 >= bx1 - 1
                and min(abs(y2 - by1), abs(by2 - y1)) <= 0.65 * row_height
                for bx1, by1, bx2, by2 in large_boxes
            )
            punctuation = abs(y2 - row_baseline) <= max(1.5, 0.18 * row_height)
            if attached or punctuation:
                result |= labels == label
    if not np.any(result):
        return _freeze_mask(result)
    contours, hierarchy = cv2.findContours(
        result.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is not None:
        output = result.astype(np.uint8)
        for index, contour in enumerate(contours):
            depth = 0; parent = int(hierarchy[0, index, 3])
            while parent >= 0:
                depth += 1; parent = int(hierarchy[0, parent, 3])
            if depth % 2 == 1 and abs(float(cv2.contourArea(contour))) < 2.0:
                cv2.drawContours(output, contours, index, 1, thickness=-1)
        result = output > 0
    return _freeze_mask(result)


def _physical_midline_text_support(
    reir: RasterEvidenceIR, mask: np.ndarray,
) -> np.ndarray | None:
    """Recover topology from persistent physical coverage, not weak AA.

    Proposal tokens deliberately include a soft antialias fringe.  That fringe
    is useful color evidence, but it cannot prove that two glyph bodies are
    connected: serializing every soft token pixel as opaque geometry promotes
    near-background samples into black bridges.  For every token component we
    estimate its own foreground-to-background contrast in linear light, keep
    the physical 50% midline, and require its component count to persist over
    the neighboring 45% and 62% evidence levels.  A genuinely lower-contrast
    glyph therefore keeps its own normalized AA midline, while an unstable
    one-pixel connector makes the whole line fail closed.
    """
    source = np.asarray(mask, bool)
    if source.shape != (reir.height, reir.width) or not np.any(source):
        return None
    premultiplied = np.asarray(
        reir.raster.linear_premultiplied_rgba, np.float32,
    )
    alpha = np.clip(premultiplied[..., 3], 0.0, 1.0)
    # Use the same opaque white viewing condition as the exact visible-render
    # court.  For ordinary opaque rasters this is just canonical linear RGB;
    # for transparent text it remains a physically meaningful coverage field.
    visible = premultiplied[..., :3] + (1.0 - alpha[..., None])
    ring = cv2.dilate(
        source.astype(np.uint8), np.ones((5, 5), np.uint8),
    ).astype(bool) & ~source
    if not np.any(ring):
        return None
    background = np.median(visible[ring], axis=0)
    distance = np.linalg.norm(visible - background[None, None, :], axis=2)
    ring_distance = distance[ring]
    ring_median = float(np.median(ring_distance))
    ring_noise = 1.4826 * float(np.median(
        np.abs(ring_distance - ring_median)
    ))
    noise_floor = ring_median + 3.0 * ring_noise

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        source.astype(np.uint8), 8,
    )
    result = np.zeros(source.shape, bool)
    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        component = labels[y:y + height, x:x + width] == label
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area <= 0:
            continue
        local_distance = distance[y:y + height, x:x + width]
        values = local_distance[component]
        # Small glyph components dominate this loop.  ``np.quantile`` builds
        # interpolation/index machinery hundreds of times per line; the
        # deterministic nearest-rank order statistic is the certificate we
        # need and avoids that Python/Numpy setup tail.
        rank = min(len(values) - 1, int(math.ceil(0.85 * len(values))) - 1)
        foreground_distance = float(np.partition(values, max(0, rank))[max(0, rank)])
        contrast_span = foreground_distance - noise_floor
        # Below this separation source pixels cannot distinguish a real thin
        # glyph from codec/background noise.  Keep the incumbent, not an
        # invented analytic TextLine.
        if contrast_span < 0.04:
            return None
        level_masks = []
        component_counts = []
        for fraction in (0.45, 0.50, 0.62):
            threshold = noise_floor + fraction * contrast_span
            level = component & (local_distance >= threshold)
            components = int(
                cv2.connectedComponents(level.astype(np.uint8), 8)[0] - 1
            )
            if components <= 0:
                return None
            level_masks.append(level)
            component_counts.append(components)
        # Connectivity, unlike the AA boundary, must be persistent.  If the
        # neighboring physical levels disagree, native sampling is not strong
        # enough to license a topology-changing vector replacement.
        if len(set(component_counts)) != 1:
            return None
        result[y:y + height, x:x + width] |= level_masks[1]
    if not np.any(result):
        return None
    return _freeze_mask(result)


def _modal_linear_background(
    pixels: np.ndarray,
) -> tuple[np.ndarray, float] | None:
    """Return the dominant local colour and its robust physical noise floor."""
    rows = np.asarray(pixels, np.float32).reshape((-1, 3))
    if len(rows) < 16:
        return None
    quantized = np.clip(np.round(rows * 15.0), 0, 15).astype(np.int32)
    keys = (
        quantized[:, 0] * 256 + quantized[:, 1] * 16 + quantized[:, 2]
    )
    histogram = np.bincount(keys, minlength=4096)
    key = int(np.argmax(histogram))
    cluster = rows[keys == key]
    if len(cluster) < max(8, int(math.ceil(0.02 * len(rows)))):
        return None
    background = np.median(cluster, axis=0)
    residual = np.linalg.norm(cluster - background[None, :], axis=1)
    median = float(np.median(residual))
    noise = 1.4826 * float(np.median(np.abs(residual - median)))
    return background, max(0.015, median + 3.0 * noise)


def _modal_background_around_box(
    visible_linear_rgb: np.ndarray,
    box_xyxy: tuple[int, int, int, int],
) -> tuple[np.ndarray, float] | None:
    """Estimate an OCR background from context, not a tight ink-majority box.

    At microtext scale an OCR box can be only six or seven pixels high.  Dark
    stems then occupy the modal colour bin inside the box and the former code
    labelled the text itself as background.  The bounded exterior ring is the
    physical canvas observation for that line; the tight box remains only a
    fallback when it reaches the image boundary and supplies too few samples.
    """
    visible = np.asarray(visible_linear_rgb, np.float32)
    if visible.ndim != 3 or visible.shape[2] != 3:
        return None
    height, width = visible.shape[:2]
    x1, y1, x2, y2 = box_xyxy
    line_height = max(1, y2 - y1)
    pad = max(2, int(math.ceil(0.35 * line_height)))
    cx1 = max(0, x1 - pad); cy1 = max(0, y1 - pad)
    cx2 = min(width, x2 + pad); cy2 = min(height, y2 + pad)
    context = visible[cy1:cy2, cx1:cx2]
    ring = np.ones(context.shape[:2], bool)
    ring[
        y1 - cy1:y2 - cy1,
        x1 - cx1:x2 - cx1,
    ] = False
    if int(np.sum(ring)) >= 16:
        modal = _modal_linear_background(context[ring])
        if modal is not None:
            return modal
    return _modal_linear_background(visible[y1:y2, x1:x2])


_OCR_COUNTERS = {
    "A": 1, "B": 2, "D": 1, "O": 1, "P": 1, "Q": 1, "R": 1,
    "0": 1, "4": 1, "6": 1, "8": 2, "9": 1,
}

_GLYPH_PRIOR_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&@"
)
_WORDMARK_PRIOR_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&@.-_+ "
)
_GLYPH_PRIOR_LOWER_COUNTERS = {
    "a": 1, "b": 1, "d": 1, "e": 1, "g": 1,
    "o": 1, "p": 1, "q": 1,
}


def _glyph_prior_topology_contract(
    recognized_text: str,
) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...]] | None:
    """Return the model's broader per-character topology conditioning.

    The source-only semantic repair lane intentionally rejects lowercase-heavy
    words because their native components can join.  The trained glyph prior,
    however, contains every ASCII lower-case character and predicts each glyph
    in an independently bounded OCR cell.  Reusing the semantic restriction in
    the model lane made most of the trained vocabulary unreachable at serving
    time.  This separate contract keeps the conservative semantic lane intact
    while exposing canonical lowercase counters and detached i/j dots to the
    topology-conditioned decoder.
    """
    visible = tuple(character for character in recognized_text if not character.isspace())
    glyphs = tuple(character for character in visible if character in _GLYPH_PRIOR_CHARACTERS)
    if not 3 <= len(glyphs) <= 64:
        return None
    if len(glyphs) / max(1, len(visible)) < 0.85:
        return None
    components = tuple(2 if character in {"i", "j"} else 1 for character in glyphs)
    holes = tuple(
        _GLYPH_PRIOR_LOWER_COUNTERS.get(
            character,
            _OCR_COUNTERS.get(character.upper(), 0),
        )
        if character not in {"&", "@"} else (2 if character == "&" else 1)
        for character in glyphs
    )
    return glyphs, components, holes


def _wordmark_prior_text_contract(
    recognized_text: str,
) -> tuple[str, ...] | None:
    """Mirror the whole-line checkpoint vocabulary without glyph-cell laws."""
    visible = tuple(" ".join(str(recognized_text).split()))
    if not 1 <= len(visible) <= 32:
        return None
    if any(character not in _WORDMARK_PRIOR_CHARACTERS for character in visible):
        return None
    return visible


def _ocr_semantic_topology_contract(
    recognized_text: str,
) -> tuple[tuple[str, ...], tuple[int, ...]] | None:
    """Return a conservative one-component uppercase/digit glyph contract."""
    visible = tuple(character for character in recognized_text if not character.isspace())
    glyphs = tuple(character for character in visible if character.isalnum())
    if not 4 <= len(glyphs) <= 64:
        return None
    if len(glyphs) / max(1, len(visible)) < 0.85:
        return None
    letters = tuple(character for character in glyphs if character.isalpha())
    uppercase_fraction = sum(character.isupper() for character in letters) / max(
        1, len(letters),
    )
    # Lowercase/cursive words need a font or skeleton model: their glyphs may
    # legitimately join and i/j add detached marks.  The contract below is
    # deliberately limited to uppercase-dominant display text and digits.
    if letters and uppercase_fraction < 0.70:
        return None
    counters = tuple(_OCR_COUNTERS.get(character.upper(), 0) for character in glyphs)
    return glyphs, counters


def _repair_one_ocr_glyph_topology(
    component: np.ndarray, *, expected_holes: int, character: str,
) -> np.ndarray | None:
    """Make the minimum one-pixel digital-preimage edits for one OCR glyph."""
    result = np.asarray(component, bool).copy()
    if _topology(result)[0] != 1:
        return None
    # Remove raster-only microcounters first.  Filling the smallest enclosed
    # contour is deterministic and never changes the component's exterior.
    while _topology(result)[1] > expected_holes:
        contours, hierarchy = cv2.findContours(
            result.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
        )
        if hierarchy is None:
            return None
        holes = []
        for index, contour in enumerate(contours):
            depth = 0; parent = int(hierarchy[0, index, 3])
            while parent >= 0:
                depth += 1; parent = int(hierarchy[0, parent, 3])
            if depth % 2 == 1:
                holes.append((
                    abs(float(cv2.contourArea(contour))),
                    cv2.boundingRect(contour), index,
                ))
        if not holes:
            return None
        _area, _bbox_row, index = min(holes)
        before = _topology(result)[1]
        painted = result.astype(np.uint8)
        cv2.drawContours(painted, contours, index, 1, thickness=-1)
        trial = painted > 0
        if _topology(trial) != (1, before - 1):
            return None
        result = trial

    target_fractions = (
        (0.30, 0.70) if expected_holes == 2 else
        (0.36,) if character.upper() in {"P", "R"} else
        (0.52,)
    )
    while _topology(result)[1] < expected_holes:
        current_holes = _topology(result)[1]
        target_y = target_fractions[min(current_holes, len(target_fractions) - 1)]
        padded = np.pad(result.astype(np.uint8), 1, constant_values=0)
        distance = cv2.distanceTransform(padded, cv2.DIST_L2, 5)[1:-1, 1:-1]
        height, width = result.shape
        candidates = []
        ys, xs = np.nonzero(result)
        for y, x in zip(ys.tolist(), xs.tolist()):
            trial = result.copy(); trial[y, x] = False
            if _topology(trial) != (1, current_holes + 1):
                continue
            candidates.append((
                abs((y + 0.5) / max(1, height) - target_y),
                -float(distance[y, x]),
                abs((x + 0.5) / max(1, width) - 0.50),
                y, x,
            ))
        if not candidates:
            return None
        *_key, y, x = min(candidates)
        result[y, x] = False
    return result


def _ocr_glyph_cell_edges(recognized_text: str, width: int) -> tuple[int, ...]:
    """Estimate variable-width glyph cells without consulting a font file."""
    glyph_rows: list[tuple[str, float, float]] = []
    cursor = 0.0
    pending_space = 0.0
    for character in recognized_text:
        if character.isspace():
            pending_space += 0.65
            continue
        if character not in _GLYPH_PRIOR_CHARACTERS:
            continue
        weight = (
            1.30 if character.upper() in {"M", "W"} else
            1.20 if character == "@" else
            1.10 if character == "&" else
            0.58 if character.upper() in {"I", "1"} else
            0.78 if character.upper() in {"J", "L", "T"} else 1.0
        )
        cursor += pending_space
        glyph_rows.append((character, cursor + 0.5 * weight, weight))
        cursor += weight
        pending_space = 0.0
    if len(glyph_rows) < 2 or width < 2 * len(glyph_rows):
        return (0, width)
    centers = [row[1] / max(1e-6, cursor) * width for row in glyph_rows]
    edges = [0]
    for left, right in zip(centers, centers[1:]):
        edge = int(round(0.5 * (left + right)))
        edge = max(edges[-1] + 2, min(width - 2, edge))
        edges.append(edge)
    edges.append(width)
    if any(right - left < 2 for left, right in zip(edges, edges[1:])):
        return tuple(int(round(index * width / len(glyph_rows)))
                     for index in range(len(glyph_rows) + 1))
    return tuple(edges)


def _ocr_evidence_glyph_cell_edges(
    source: np.ndarray, recognized_text: str,
) -> tuple[int, ...]:
    """Refine font-free advance estimates at source-observed ink valleys.

    Character width priors provide only a nominal grammar.  Applying them as
    hard equal-ish cells cut real glyph stems and made the glyph prior distort
    otherwise clean wordmarks.  This bounded dynamic pass moves every internal
    boundary only within 38% of one average advance, minimizes removed source
    ink, and preserves at least two columns per remaining glyph.  It is not a
    font lookup and cannot move a boundary without evidence in the immutable
    support mask.
    """
    contract = _glyph_prior_topology_contract(recognized_text)
    support = np.asarray(source, bool)
    if contract is None or support.ndim != 2 or not np.any(support):
        return ()
    glyphs, _components, _counters = contract
    x1, _y1, x2, _y2 = _bbox(support, pad=0)
    width = x2 - x1
    nominal = _ocr_glyph_cell_edges(recognized_text, width)
    if len(nominal) != len(glyphs) + 1:
        return nominal
    local = support[:, x1:x2]
    column_ink = np.sum(local, axis=0, dtype=np.int64)
    average_advance = width / max(1, len(glyphs))
    radius = max(1, min(6, int(round(0.38 * average_advance))))
    edges = [0]
    for boundary_index, expected in enumerate(nominal[1:-1], start=1):
        remaining = len(glyphs) - boundary_index
        start = max(edges[-1] + 2, expected - radius)
        stop = min(width - 2 * remaining, expected + radius + 1)
        if stop <= start:
            return nominal
        candidates = []
        for column in range(start, stop):
            # The decoder reserves the boundary column as inter-glyph space.
            # Prefer a truly empty seam, then the least three-column ink and
            # only then proximity to the width-prior position.
            neighborhood = int(np.sum(column_ink[
                max(0, column - 1):min(width, column + 2)
            ]))
            candidates.append((
                int(column_ink[column]), neighborhood,
                abs(column - expected), column,
            ))
        *_cost, selected = min(candidates)
        edges.append(int(selected))
    edges.append(width)
    if any(right - left < 2 for left, right in zip(edges, edges[1:])):
        return nominal
    return tuple(edges)


def _ocr_adaptive_glyph_preimage(
    source: np.ndarray, distance: np.ndarray, recognized_text: str, *,
    noise_floor: float,
) -> np.ndarray | None:
    """Fit independent topology plateaus inside OCR-derived glyph cells.

    Unlike the strict whole-line decoder, each glyph may select its own
    coverage level.  This is essential for JPEG/coloured wordmarks where a
    global threshold preserves the ``O`` counter but breaks the adjacent thin
    ``I``.  Every trial is still derived from the measured linear-RGB distance
    field inside the immutable line box.
    """
    contract = _ocr_semantic_topology_contract(recognized_text)
    source = np.asarray(source, bool)
    field = np.asarray(distance, np.float32)
    if contract is None or source.shape != field.shape or not np.any(source):
        return None
    glyphs, counters = contract
    x1, y1, x2, y2 = _bbox(source, pad=0)
    width = x2 - x1; height = y2 - y1
    if height < 4 or width / len(glyphs) < 2.0:
        return None
    local_source = source[y1:y2, x1:x2]
    local_field = field[y1:y2, x1:x2]
    values = local_field[local_source]
    if not len(values):
        return None
    peak = float(np.percentile(values, 95.0))
    span = peak - noise_floor
    if span < 0.04:
        return None
    alpha = np.clip((local_field - noise_floor) / span, 0.0, 1.0)
    nominal_edges = _ocr_glyph_cell_edges(recognized_text, width)
    if len(nominal_edges) != len(glyphs) + 1:
        return None

    # Refine each expected boundary at a nearby low-ink column.  The ordered
    # clamp guarantees at least two physical columns per glyph.
    average_advance = width / len(glyphs)
    radius = max(1, min(4, int(round(0.38 * average_advance))))
    edges = [0]
    for boundary_index, nominal in enumerate(nominal_edges[1:-1], start=1):
        remaining = len(glyphs) - boundary_index
        start = max(edges[-1] + 2, nominal - radius)
        stop = min(width - 2 * remaining, nominal + radius + 1)
        if stop <= start:
            return None
        candidates = []
        for column in range(start, stop):
            column_alpha = alpha[:, column]
            candidates.append((
                int(np.sum(column_alpha >= 0.20)),
                float(np.sum(column_alpha)), abs(column - nominal), column,
            ))
        *_key, column = min(candidates)
        edges.append(int(column))
    edges.append(width)

    rebuilt = np.zeros_like(local_source)
    removed_seam = np.zeros_like(local_source)
    for column in edges[1:-1]:
        removed_seam[:, column] = local_source[:, column]
    if int(np.sum(removed_seam)) > max(
        4, int(math.ceil(0.08 * np.sum(local_source))),
    ):
        return None

    levels = (0.18, 0.24, 0.30, 0.38, 0.46, 0.55, 0.65, 0.75)
    for index, (character, expected_holes) in enumerate(zip(glyphs, counters)):
        left = edges[index] + int(index > 0)
        right = edges[index + 1]
        if right - left < 2:
            return None
        cell_alpha = alpha[:, left:right]
        cell_source = local_source[:, left:right]
        cell_candidates: list[tuple[float, float, int, str, np.ndarray]] = []
        for level in levels:
            raw = cell_alpha >= level
            variants = [("raw", raw)]
            if min(raw.shape) >= 3:
                kernel = np.ones((3, 3), np.uint8)
                variants.extend((
                    ("close", cv2.morphologyEx(
                        raw.astype(np.uint8), cv2.MORPH_CLOSE, kernel,
                    ) > 0),
                    ("open-close", cv2.morphologyEx(
                        cv2.morphologyEx(
                            raw.astype(np.uint8), cv2.MORPH_OPEN, kernel,
                        ), cv2.MORPH_CLOSE, kernel,
                    ) > 0),
                ))
            for variant_name, trial in variants:
                if not np.any(trial):
                    continue
                count, labels, stats, _ = cv2.connectedComponentsWithStats(
                    trial.astype(np.uint8), 8,
                )
                if count - 1 > 1:
                    # Codec dust may share the glyph cell.  Retain the largest
                    # component only when it owns nearly all measured ink.
                    areas = stats[1:, cv2.CC_STAT_AREA]
                    label = int(np.argmax(areas)) + 1
                    largest = labels == label
                    if int(np.sum(largest)) < 0.82 * int(np.sum(trial)):
                        continue
                    trial = largest
                if _topology(trial)[0] != 1:
                    continue
                repaired = _repair_one_ocr_glyph_topology(
                    trial, expected_holes=int(expected_holes),
                    character=character,
                )
                if repaired is None or _topology(repaired) != (
                    1, int(expected_holes),
                ):
                    continue
                domain = (cell_alpha >= 0.08) | cell_source | repaired
                evidence_error = float(np.mean(
                    np.abs(cell_alpha[domain] - repaired[domain].astype(np.float32))
                ))
                intersection = int(np.sum(repaired & cell_source))
                union = int(np.sum(repaired | cell_source))
                source_iou = intersection / max(1, union)
                changes = int(np.sum(repaired != cell_source))
                cell_candidates.append((
                    evidence_error + 0.12 * (1.0 - source_iou),
                    -source_iou, changes, variant_name, repaired,
                ))
        if not cell_candidates:
            return None
        winner = min(cell_candidates, key=lambda row: row[:4])[4]
        rebuilt[:, left:right] |= winner

    expected_topology = (len(glyphs), int(sum(counters)))
    if _topology(rebuilt) != expected_topology:
        return None
    intersection = int(np.sum(rebuilt & local_source))
    union = int(np.sum(rebuilt | local_source))
    iou = intersection / max(1, union)
    changes = int(np.sum(rebuilt != local_source))
    if iou < 0.42 or changes > max(
        16, int(math.ceil(0.70 * np.sum(local_source))),
    ):
        return None
    full = np.zeros_like(source)
    full[y1:y2, x1:x2] = rebuilt
    return _freeze_mask(full)


def _topology_constrained_component_subset(
    probability: np.ndarray, certified_support: np.ndarray,
    expected_topology: tuple[int, int], preferred_threshold: float,
) -> tuple[np.ndarray, float, bool]:
    """Decode topology by thresholds, then source-bounded component pruning.

    Tiny native glyphs can produce a correct main body plus several low-mass
    neural islands.  Threshold-only decoding rejects the whole glyph even
    though deleting those unsupported islands is a safe subset operation.
    Raw threshold matches always win.  Otherwise enumerate at most the eight
    strongest components and retain exactly the certified component count,
    choosing only an exact-hole topology with maximal source overlap.  No
    pixel is added, no gap is closed, and the caller still enforces the full
    line IoU/edit wall.
    """
    from itertools import combinations

    from .glyph_prior import (
        TOPOLOGY_DECODE_THRESHOLDS, topology_constrained_support,
    )

    soft = np.asarray(probability, np.float32)
    source = np.asarray(certified_support, bool)
    expected = (int(expected_topology[0]), int(expected_topology[1]))
    raw, raw_threshold, matched = topology_constrained_support(
        soft, expected, preferred_threshold,
    )
    if matched or expected[0] <= 0:
        return raw, raw_threshold, matched
    thresholds = sorted(
        {float(preferred_threshold), *TOPOLOGY_DECODE_THRESHOLDS},
        key=lambda threshold: (
            abs(threshold - float(preferred_threshold)), threshold,
        ),
    )
    alternatives: list[
        tuple[float, float, float, str, float, np.ndarray]
    ] = []
    for threshold in thresholds:
        thresholded = soft >= threshold
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            thresholded.astype(np.uint8), 8,
        )
        if count - 1 <= expected[0]:
            continue
        ranked = sorted(
            range(1, count),
            key=lambda label: (
                -int(np.sum(source & (labels == label))),
                -int(stats[label, cv2.CC_STAT_AREA]), label,
            ),
        )[:8]
        if len(ranked) < expected[0]:
            continue
        for selected in combinations(ranked, expected[0]):
            candidate = np.isin(labels, selected)
            if _topology(candidate) != expected:
                continue
            intersection = int(np.sum(candidate & source))
            union = int(np.sum(candidate | source))
            source_iou = intersection / max(1, union)
            probability_mass = float(np.sum(soft[candidate]))
            alternatives.append((
                -source_iou,
                abs(threshold - float(preferred_threshold)),
                -probability_mass,
                ",".join(str(value) for value in selected),
                float(threshold),
                candidate,
            ))
    if not alternatives:
        return raw, raw_threshold, False
    winner = min(alternatives, key=lambda row: row[:4])
    return winner[5], winner[4], True


def _repair_restored_neural_glyph(
    probability: np.ndarray, certified_support: np.ndarray, *,
    character: str, expected_holes: int,
) -> np.ndarray | None:
    """Restore one native-lattice glyph with minimum OCR-contracted edits."""
    from .glyph_prior import TOPOLOGY_DECODE_THRESHOLDS

    soft = np.asarray(probability, np.float32)
    source = np.asarray(certified_support, bool)
    candidates: list[tuple[float, int, float, int, np.ndarray]] = []
    for threshold_index, threshold in enumerate((
        0.5, *TOPOLOGY_DECODE_THRESHOLDS,
    )):
        thresholded = soft >= float(threshold)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            thresholded.astype(np.uint8), 8,
        )
        ranked = sorted(
            range(1, count),
            key=lambda label: (
                -int(np.sum(source & (labels == label))),
                -int(stats[label, cv2.CC_STAT_AREA]), label,
            ),
        )[:8]
        for label in ranked:
            component = labels == label
            repaired = _repair_one_ocr_glyph_topology(
                component, expected_holes=int(expected_holes),
                character=character,
            )
            if repaired is None or _topology(repaired) != (
                1, int(expected_holes),
            ):
                continue
            intersection = int(np.sum(repaired & source))
            union = int(np.sum(repaired | source))
            source_iou = intersection / max(1, union)
            changes = int(np.sum(repaired != source))
            probability_fit = float(np.mean(np.abs(
                soft - repaired.astype(np.float32)
            )))
            candidates.append((
                -source_iou, changes, probability_fit,
                threshold_index * 16 + label, repaired,
            ))
    if not candidates:
        return None
    winner = min(candidates, key=lambda row: row[:4])
    if -winner[0] < 0.30:
        return None
    return winner[4]


def _ocr_neural_glyph_preimage(
    source: np.ndarray, visible_rgb: np.ndarray, recognized_text: str, *,
    checkpoint: Path | None = None,
) -> np.ndarray | None:
    """Propose per-glyph clean support from the optional local glyph prior.

    OCR supplies character/counter contracts and the source supplies every
    crop.  The neural result remains a separate proposal; this function never
    replaces the physical or adaptive-preimage lanes.
    """
    explicit_checkpoint = checkpoint
    override = os.environ.get("VICE_GLYPH_PRIOR_CHECKPOINT", "").strip()
    if explicit_checkpoint is None and not override:
        model_root = Path(__file__).resolve().parents[1] / "models"
        if not (
            (model_root / "glyph_prior.pt").is_file()
            and (model_root / "glyph_prior_promotion.json").is_file()
        ):
            return None
    elif explicit_checkpoint is not None and not explicit_checkpoint.is_file():
        return None
    contract = _glyph_prior_topology_contract(recognized_text)
    source = np.asarray(source, bool)
    visible = np.asarray(visible_rgb)
    if (
        contract is None or source.ndim != 2 or visible.shape[:2] != source.shape
        or not np.any(source)
    ):
        return None
    glyphs, components, counters = contract
    x1, y1, x2, y2 = _bbox(source, pad=0)
    width = x2 - x1; height = y2 - y1
    if height < 4 or width / max(1, len(glyphs)) < 2.0:
        return None
    edges = _ocr_evidence_glyph_cell_edges(source, recognized_text)
    if len(edges) != len(glyphs) + 1:
        return None
    from .glyph_prior import (
        character_id, load_glyph_prior, resolve_glyph_prior_checkpoint,
    )
    from .glyph_prior_data import glyph_observation_features
    import torch

    resolved_checkpoint = resolve_glyph_prior_checkpoint(explicit_checkpoint)
    if resolved_checkpoint is None:
        return None
    loaded = load_glyph_prior(resolved_checkpoint)
    if loaded is None:
        return None
    model, device, payload = loaded
    model_size = int(model.config.image_size)

    local_source = source[y1:y2, x1:x2]
    local_visible = visible[y1:y2, x1:x2]
    rebuilt = np.zeros_like(local_source)
    normalized_rows: list[dict[str, object]] = []
    for index, (character, expected_components, expected_holes) in enumerate(zip(
        glyphs, components, counters,
    )):
        left = edges[index] + int(index > 0)
        right = edges[index + 1]
        if right - left < 2:
            return None
        cell_source = local_source[:, left:right]
        if not np.any(cell_source):
            return None
        # The synthetic model contract normalizes every glyph crop with
        # preserved aspect ratio and a centred background margin.  Feeding a
        # raw variable-width OCR cell here used to stretch e.g. an S by 2x,
        # while narrow I cells were stretched in the opposite direction.
        # That train/serve skew made the prior reject most real letters even
        # though its held-out topology/IoU gates passed.  Reproduce the exact
        # geometric convention before inference, then project the soft result
        # back onto the immutable source cell and re-certify topology there.
        gx1, gy1, gx2, gy2 = _bbox(cell_source, pad=0)
        glyph_width = gx2 - gx1
        glyph_height = gy2 - gy1
        if glyph_width < 1 or glyph_height < 1:
            return None
        margin = max(3, model_size // 12)
        available = max(1, model_size - 2 * margin)
        scale = min(available / glyph_width, available / glyph_height)
        normalized_width = max(1, int(round(glyph_width * scale)))
        normalized_height = max(1, int(round(glyph_height * scale)))
        normalized_x = (model_size - normalized_width) // 2
        normalized_y = (model_size - normalized_height) // 2
        crop_visible = local_visible[gy1:gy2, left + gx1:left + gx2]
        border = np.concatenate((
            local_visible[0], local_visible[-1],
            local_visible[:, 0], local_visible[:, -1],
        ), axis=0)
        background = np.median(border, axis=0)
        normalized_visible = np.broadcast_to(
            background, (model_size, model_size, 3),
        ).copy()
        interpolation = (
            cv2.INTER_AREA
            if max(glyph_width, glyph_height) > max(
                normalized_width, normalized_height,
            ) else cv2.INTER_CUBIC
        )
        normalized_visible[
            normalized_y:normalized_y + normalized_height,
            normalized_x:normalized_x + normalized_width,
        ] = cv2.resize(
            crop_visible, (normalized_width, normalized_height),
            interpolation=interpolation,
        )
        normalized_source = np.zeros((model_size, model_size), bool)
        normalized_source[
            normalized_y:normalized_y + normalized_height,
            normalized_x:normalized_x + normalized_width,
        ] = cv2.resize(
            cell_source[gy1:gy2, gx1:gx2].astype(np.uint8),
            (normalized_width, normalized_height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
        identifier = character_id(character)
        if identifier is None:
            return None
        normalized_rows.append({
            "character": character,
            "character_id": identifier,
            "expected_components": int(expected_components),
            "expected_holes": int(expected_holes),
            "features": glyph_observation_features(
                normalized_visible, model_size,
            ),
            "normalized_source": normalized_source,
            "normalized_x": normalized_x,
            "normalized_y": normalized_y,
            "normalized_width": normalized_width,
            "normalized_height": normalized_height,
            "glyph_width": glyph_width,
            "glyph_height": glyph_height,
            "gx1": gx1,
            "gy1": gy1,
            "left": left,
            "right": right,
            "cell_source": cell_source,
        })

    if len(normalized_rows) != len(glyphs):
        return None
    features = np.stack([
        np.asarray(row["features"], np.float32) for row in normalized_rows
    ])
    characters = torch.tensor(
        [int(row["character_id"]) for row in normalized_rows],
        device=device, dtype=torch.long,
    )
    component_ids = torch.tensor(
        [int(row["expected_components"]) for row in normalized_rows],
        device=device, dtype=torch.long,
    )
    hole_ids = torch.tensor(
        [int(row["expected_holes"]) for row in normalized_rows],
        device=device, dtype=torch.long,
    )
    with torch.inference_mode():
        output = model(
            torch.from_numpy(features).to(device=device, dtype=torch.float32),
            characters, component_ids, hole_ids,
        )
        probabilities = torch.sigmoid(
            output["support_logits"],
        )[:, 0].cpu().numpy()
        component_probabilities = torch.softmax(
            output["component_logits"], dim=1,
        ).cpu().numpy()
        hole_probabilities = torch.softmax(
            output["hole_logits"], dim=1,
        ).cpu().numpy()
    support_threshold = float(payload.get("support_threshold", 0.5))
    if not 0.0 < support_threshold < 1.0:
        return None
    confidences = []
    for row_index, row in enumerate(normalized_rows):
        expected_holes = int(row["expected_holes"])
        expected_components = int(row["expected_components"])
        expected = (expected_components, expected_holes)
        component_probability = component_probabilities[row_index]
        hole_probability = hole_probabilities[row_index]
        predicted = (
            int(np.argmax(component_probability)),
            int(np.argmax(hole_probability)),
        )
        if predicted != expected:
            return None
        probability = probabilities[row_index]
        normalized_source = np.asarray(row["normalized_source"], bool)
        normalized_support, _threshold, topology_matched = (
            _topology_constrained_component_subset(
                probability, normalized_source, expected, support_threshold,
            )
        )
        if not topology_matched:
            return None
        # Suppress only disconnected components rejected by the certified
        # subset decoder; retain soft boundaries around the admitted body.
        admitted_domain = cv2.dilate(
            normalized_support.astype(np.uint8), np.ones((3, 3), np.uint8),
        ) > 0
        cleaned_soft = np.where(admitted_domain, probability, 0.0)
        normalized_x = int(row["normalized_x"])
        normalized_y = int(row["normalized_y"])
        normalized_width = int(row["normalized_width"])
        normalized_height = int(row["normalized_height"])
        normalized_soft = cleaned_soft[
            normalized_y:normalized_y + normalized_height,
            normalized_x:normalized_x + normalized_width,
        ]
        glyph_width = int(row["glyph_width"])
        glyph_height = int(row["glyph_height"])
        restored_soft = cv2.resize(
            normalized_soft, (glyph_width, glyph_height),
            interpolation=cv2.INTER_LINEAR,
        )
        gx1 = int(row["gx1"])
        gy1 = int(row["gy1"])
        cell_source = np.asarray(row["cell_source"], bool)
        certified_local = cell_source[
            gy1:gy1 + glyph_height, gx1:gx1 + glyph_width,
        ]
        restored, _threshold, topology_matched = (
            _topology_constrained_component_subset(
                restored_soft, certified_local, expected, 0.5,
            )
        )
        if not topology_matched:
            repaired = (
                _repair_restored_neural_glyph(
                    restored_soft, certified_local,
                    character=str(row["character"]),
                    expected_holes=expected_holes,
                )
                if expected_components == 1 else None
            )
            if repaired is None:
                return None
            restored = repaired
        cell_rebuilt = np.zeros_like(cell_source)
        cell_rebuilt[
            gy1:gy1 + glyph_height, gx1:gx1 + glyph_width,
        ] = restored
        left = int(row["left"])
        right = int(row["right"])
        rebuilt[:, left:right] = cell_rebuilt
        certainty = float(np.mean(np.maximum(
            probability, 1.0 - probability,
        )))
        topology_confidence = float(
            component_probability[expected[0]]
            * hole_probability[expected[1]]
        )
        confidences.append(float(math.sqrt(max(
            0.0, certainty * topology_confidence,
        ))))
    expected = (int(sum(components)), int(sum(counters)))
    if _topology(rebuilt) != expected or min(confidences, default=0.0) < 0.35:
        return None
    intersection = int(np.sum(rebuilt & local_source))
    union = int(np.sum(rebuilt | local_source))
    changes = int(np.sum(rebuilt != local_source))
    if (
        intersection / max(1, union) < 0.42
        or changes > max(16, int(math.ceil(0.55 * np.sum(local_source))))
    ):
        return None
    full = np.zeros_like(source)
    full[y1:y2, x1:x2] = rebuilt
    return _freeze_mask(full)


def _ocr_semantic_digital_preimage(
    source: np.ndarray, distance: np.ndarray, recognized_text: str,
    *, noise_floor: float,
) -> np.ndarray | None:
    """Recover uppercase microtext topology using OCR + measured coverage.

    OCR supplies only the ordered glyph/counter contract.  Geometry still
    comes from the source colour-distance field: a bounded high-coverage core
    is split at minimum-ink vertical seams, then at most a few one-pixel
    preimage edits restore counters lost below the native lattice.
    """
    contract = _ocr_semantic_topology_contract(recognized_text)
    source = np.asarray(source, bool)
    field = np.asarray(distance, np.float32)
    if contract is None or source.shape != field.shape or not np.any(source):
        return None
    glyphs, counters = contract
    expected_components = len(glyphs)
    expected_holes = int(sum(counters))
    x1, y1, x2, y2 = _bbox(source, pad=0)
    local_source = source[y1:y2, x1:x2]
    local_distance = field[y1:y2, x1:x2]
    width = x2 - x1; height = y2 - y1
    advance = width / max(1, expected_components)
    if height < 4 or advance < 2.25:
        return None
    peak = float(np.max(local_distance[local_source]))
    if peak <= noise_floor + 0.04:
        return None
    candidates: list[tuple[float, int, str, np.ndarray]] = []
    for level in (0.60, 0.68, 0.75, 0.82):
        core = local_source & (
            local_distance >= noise_floor + level * (peak - noise_floor)
        )
        core_area = int(np.sum(core))
        if core_area < expected_components * 2:
            continue
        segmented = core.copy()
        radius = max(1, min(3, int(round(0.45 * advance))))
        used_columns: set[int] = set()
        for boundary in range(1, expected_components):
            center = boundary * advance
            rows = []
            start = max(0, int(round(center)) - radius)
            stop = min(width, int(round(center)) + radius + 1)
            for column in range(start, stop):
                if column in used_columns:
                    continue
                ink = segmented[:, column]
                rows.append((
                    int(np.sum(ink)),
                    float(np.sum(local_distance[:, column][ink])),
                    abs((column + 0.5) - center), column,
                ))
            if not rows:
                break
            _ink_count, _ink_mass, _deviation, column = min(rows)
            used_columns.add(column)
            segmented[:, column] = False
        else:
            removed_by_seams = int(np.sum(core & ~segmented))
            if removed_by_seams > max(3, int(math.ceil(0.04 * core_area))):
                continue
            count, labels, stats, _ = cv2.connectedComponentsWithStats(
                segmented.astype(np.uint8), 8,
            )
            if count - 1 != expected_components:
                continue
            order = sorted(
                range(1, count),
                key=lambda label: (
                    int(stats[label, cv2.CC_STAT_LEFT]),
                    int(stats[label, cv2.CC_STAT_TOP]), label,
                ),
            )
            rebuilt = np.zeros_like(segmented)
            failed = False
            for character, expected, label in zip(glyphs, counters, order):
                gx = int(stats[label, cv2.CC_STAT_LEFT])
                gy = int(stats[label, cv2.CC_STAT_TOP])
                gw = int(stats[label, cv2.CC_STAT_WIDTH])
                gh = int(stats[label, cv2.CC_STAT_HEIGHT])
                component = labels[gy:gy + gh, gx:gx + gw] == label
                repaired = _repair_one_ocr_glyph_topology(
                    component, expected_holes=expected, character=character,
                )
                if repaired is None:
                    failed = True; break
                rebuilt[gy:gy + gh, gx:gx + gw] |= repaired
            if failed or _topology(rebuilt) != (
                expected_components, expected_holes,
            ):
                continue
            intersection = int(np.sum(rebuilt & local_source))
            union = int(np.sum(rebuilt | local_source))
            iou = intersection / max(1, union)
            changes = int(np.sum(rebuilt != local_source))
            if iou < 0.78 or changes > max(
                8, int(math.ceil(0.15 * np.sum(local_source))),
            ):
                continue
            full = np.zeros_like(source)
            full[y1:y2, x1:x2] = rebuilt
            frozen = _freeze_mask(full)
            candidates.append((-iou, changes, mask_sha256(frozen), frozen))
    if not candidates:
        return None
    return min(candidates, key=lambda row: row[:3])[3]


def _ocr_physical_midline_text_support(
    reir: RasterEvidenceIR, mask: np.ndarray, recognized_text: str,
) -> np.ndarray | None:
    """Recover an OCR-bounded line when JPEG connectivity is unstable.

    The ordinary physical-midline certificate deliberately rejects an entire
    line when any source component changes connectivity between 45%, 50% and
    62% contrast.  That is the right rule without semantics, but compressed
    small text often splits a real stem at 62% even though OCR independently
    proves a complete word box.  This lane keeps the 50% physical subset only:
    every returned pixel belongs to the immutable OCR/Otsu support, so it may
    remove weak bridges but can never invent a fusion.  Strong contrast,
    high-threshold persistence and whole-line span remain mandatory.
    """
    source = np.asarray(mask, bool)
    if source.shape != (reir.height, reir.width) or not np.any(source):
        return None
    glyph_count = sum(character.isalnum() for character in recognized_text)
    if glyph_count < 2:
        return None

    premultiplied = np.asarray(
        reir.raster.linear_premultiplied_rgba, np.float32,
    )
    alpha = np.clip(premultiplied[..., 3], 0.0, 1.0)
    visible = premultiplied[..., :3] + (1.0 - alpha[..., None])
    source_box = _bbox(source, pad=0)
    x1, y1, x2, y2 = source_box
    modal = _modal_background_around_box(visible, source_box)
    if modal is None:
        return None
    background, noise_floor = modal
    distance = np.linalg.norm(visible - background[None, None, :], axis=2)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        source.astype(np.uint8), 8,
    )
    result = np.zeros(source.shape, bool)
    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        component = labels[y:y + height, x:x + width] == label
        values = distance[y:y + height, x:x + width][component]
        if not len(values):
            continue
        rank = min(len(values) - 1, int(math.ceil(0.85 * len(values))) - 1)
        foreground_distance = float(
            np.partition(values, max(0, rank))[max(0, rank)]
        )
        contrast_span = foreground_distance - noise_floor
        if contrast_span < 0.04:
            return None
        local_distance = distance[y:y + height, x:x + width]
        low = component & (
            local_distance >= noise_floor + 0.45 * contrast_span
        )
        mid = component & (
            local_distance >= noise_floor + 0.50 * contrast_span
        )
        high = component & (
            local_distance >= noise_floor + 0.62 * contrast_span
        )
        if not np.any(low) or not np.any(mid) or not np.any(high):
            return None
        # Every physical-midline island must contain stronger source evidence.
        # High contrast may split it, which is precisely the uncertainty this
        # OCR-only lane tolerates; disappearance is not tolerated.
        mid_count, mid_labels = cv2.connectedComponents(
            mid.astype(np.uint8), 8,
        )
        unsupported = np.zeros(mid.shape, bool)
        for mid_label in range(1, mid_count):
            island = mid_labels == mid_label
            if not np.any(island & high):
                unsupported |= island
        unsupported_area = int(np.sum(unsupported))
        if unsupported_area > max(3, int(math.ceil(0.08 * np.sum(mid)))):
            return None
        if unsupported_area:
            mid = mid & ~unsupported
        if not np.any(mid):
            return None
        if int(np.sum(high)) / max(1, int(np.sum(low))) < 0.12:
            return None
        result[y:y + height, x:x + width] |= mid

    if not np.any(result) or np.any(result & ~source):
        return None
    result_box = _bbox(result, pad=0)
    source_width = max(1, source_box[2] - source_box[0])
    source_height = max(1, source_box[3] - source_box[1])
    span = (result_box[2] - result_box[0]) / source_width
    height_span = (result_box[3] - result_box[1]) / source_height
    area_ratio = int(np.sum(result)) / max(1, int(np.sum(source)))
    components, _holes = _topology(result)
    aspect = (result_box[2] - result_box[0]) / max(
        1.0, result_box[3] - result_box[1],
    )
    density = float(np.mean(
        result[result_box[1]:result_box[3], result_box[0]:result_box[2]]
    ))
    if (
        span < 0.82 or height_span < 0.55
        or not 0.30 <= area_ratio <= 1.0
        or components <= 0 or components > 3 * glyph_count
        or aspect < 1.20 or density > 0.70
    ):
        return None
    semantic = _ocr_semantic_digital_preimage(
        source, distance, recognized_text, noise_floor=noise_floor,
    )
    if semantic is not None:
        return semantic
    return _freeze_mask(result)


def _group_aligned_components(
    rows: list[tuple[np.ndarray, tuple[int, int, int, int]]]
) -> list[list[tuple[np.ndarray, tuple[int, int, int, int]]]]:
    groups: list[list[tuple[np.ndarray, tuple[int, int, int, int]]]] = []
    for row in sorted(rows, key=lambda item: (item[1][3], item[1][0])):
        bbox = row[1]; height = bbox[3] - bbox[1]; baseline = bbox[3]
        target = None
        for group in groups:
            heights = np.asarray([item[1][3] - item[1][1] for item in group])
            baselines = np.asarray([item[1][3] for item in group])
            median_height = float(np.median(heights))
            if (
                abs(baseline - float(np.median(baselines)))
                <= 0.55 * max(height, median_height)
                and 0.35 <= height / max(1.0, median_height) <= 2.8
            ):
                target = group
                break
        if target is None:
            groups.append([row])
        else:
            target.append(row)
    return groups


def _body_topology_signature(
    mask: np.ndarray, min_area: int,
) -> tuple[int, int]:
    """(body components, body holes) ignoring speck-scale pieces.

    topology_signature counts every pixel island, so removing legitimate
    AA/JPEG specks would read as a component change.  The Stage-D guard
    needs the body-scale signature: components and enclosed background
    holes with at least min_area pixels.
    """
    source = np.asarray(mask, np.uint8)
    _count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        source, 8,
    )
    components = int(np.sum(stats[1:, cv2.CC_STAT_AREA] >= min_area))
    inverted = np.pad(1 - source, 1, constant_values=1)
    count_h, labels_h, stats_h, _ = cv2.connectedComponentsWithStats(
        inverted, 4,
    )
    outside = labels_h[0, 0]
    holes = int(sum(
        1 for index in range(1, count_h)
        if index != outside
        and stats_h[index, cv2.CC_STAT_AREA] >= min_area
    ))
    return components, holes


def _stage_d_support_refinements(
    reir: RasterEvidenceIR, proposals: Iterable[TextLineProposal],
) -> tuple[TextLineProposal, ...]:
    """Emit Stage-D recovered supports as separate competing proposals.

    Boosting only the template-fit target cannot change delivered output:
    the admission walls keep measuring candidates against the raw
    line.support_mask, so a cleaner fit geometry is rejected by the very
    noise it repaired.  The recovery therefore has to happen where the
    support is born.  Each qualifying OCR line yields at most one extra
    proposal whose support is the model's recovered mask; it re-enters
    through _line_from_mask, so every physical line gate, the duplicate
    suppressor, the admission walls and the render court judge it exactly
    like any hand-crafted draft.  The model never bypasses a wall.
    """
    if os.environ.get("VICE_STAGE_D_UPSTREAM") != "1":
        return ()
    override = os.environ.get("VICE_STAGE_D_CHECKPOINT", "").strip()
    # Default = the current champion (ledger 100/101: luminance-bg recipe,
    # 0.829/8.05 across seeds; first delivered win text-006 in H9).
    checkpoint = Path(override) if override else (
        Path(__file__).resolve().parents[1]
        / "models" / "stage_d_realft_from_lumbg.pt"
    )
    if not checkpoint.is_file():
        return ()
    # Deferred: template_warp_provider imports from this module.
    from .template_warp_provider import _StageDBooster

    booster = _StageDBooster(checkpoint)
    # Long thin lines fuse under the square letterbox (H8/H9 lesson: a
    # 4:1 word shrinks to ~20px glyphs).  When a line-canvas checkpoint
    # exists, wide ROIs route to it at its native 96x384 letterbox.
    line_override = os.environ.get(
        "VICE_STAGE_D_LINE_CHECKPOINT", "",
    ).strip()
    line_checkpoint = Path(line_override) if line_override else (
        Path(__file__).resolve().parents[1]
        / "models" / "stage_d_line_realft_candidate.pt"
    )
    line_booster = (
        _StageDBooster(line_checkpoint)
        if line_checkpoint.is_file() else None
    )
    rgba = np.asarray(reir.raster.straight_rgba, np.float32)
    if rgba.max() > 1.5:
        rgba = rgba / 255.0
    alpha = rgba[..., 3]
    luminance = (
        0.2126 * rgba[..., 0] + 0.7152 * rgba[..., 1] + 0.0722 * rgba[..., 2]
    )
    # The fine-tune saw real ROIs as luminance composited over 0.5 gray;
    # the synthetic-only convention (ink-high coverage) is the OPPOSITE
    # polarity and must not be fed to this checkpoint.
    gray = (luminance * alpha + 0.5 * (1.0 - alpha)).astype(np.float32)
    refined: list[TextLineProposal] = []
    seen: set[str] = set()
    for proposal in proposals:
        if (
            "OCR" not in proposal.sources
            or "stage-d-support-recovery" in proposal.sources
        ):
            continue
        x1, y1, x2, y2 = proposal.roi_xyxy
        if (x2 - x1) < 8 or (y2 - y1) < 8:
            continue
        roi_aspect = (x2 - x1) / max(1, y2 - y1)
        if line_booster is not None and roi_aspect > 2.5:
            recovered = line_booster.boost_letterboxed(
                gray[y1:y2, x1:x2], canvas=(96, 384),
            )
        else:
            recovered = booster.boost_letterboxed(gray[y1:y2, x1:x2])
        if recovered is None or not recovered.any():
            continue
        original = np.asarray(proposal.support_mask[y1:y2, x1:x2], bool)
        intersection = int(np.sum(recovered & original))
        union = int(np.sum(recovered | original))
        area_ratio = float(recovered.sum()) / max(1.0, float(original.sum()))
        # Accuracy budget: recovery may repair topology and AA damage, but
        # a mask that barely overlaps the observed support (or invents /
        # erases half the ink) is hallucination and fails closed here.
        if (
            intersection / max(1, union) < 0.30
            or not 0.40 <= area_ratio <= 2.50
            or np.array_equal(recovered, original)
        ):
            continue
        # Topology guard (H8 lesson): the first live firing of this lane won
        # the pixel court on text-015 (+0.05 IoU) while fusing 9 body
        # components and closing 2 counters (reference [38,6], recovered
        # [25,3], GCR 13->20).  The court cannot see reviewed-reference GCR
        # at compile time, so the guarantee must be structural: a default
        # recovery may clean specks, but body-scale component and hole
        # counts must stay within a small drift of the observed support.
        speck = max(4, int(0.0002 * recovered.size))
        original_body = _body_topology_signature(original, speck)
        recovered_body = _body_topology_signature(recovered, speck)
        component_drift = abs(recovered_body[0] - original_body[0])
        hole_drift = abs(recovered_body[1] - original_body[1])
        if (
            component_drift > max(1, round(0.10 * original_body[0]))
            or hole_drift > 1
        ):
            continue
        full = np.zeros(proposal.support_mask.shape, bool)
        full[y1:y2, x1:x2] = recovered
        candidate = _line_from_mask(
            reir, full, polarity=proposal.polarity,
            sources=tuple(sorted(
                set(proposal.sources) | {"stage-d-support-recovery"}
            )),
            raw_score=proposal.score,
        )
        if candidate is not None and candidate.id not in seen:
            seen.add(candidate.id)
            refined.append(candidate)
    return tuple(refined)


def _line_from_mask(
    reir: RasterEvidenceIR, mask: np.ndarray, *, polarity: str,
    sources: Iterable[str], raw_score: float,
) -> TextLineProposal | None:
    if not np.any(mask):
        return None
    sources = tuple(sources)
    recognized_text = next((
        source.split(":", 1)[1] for source in sources
        if source.startswith("ocr-text:") and source.split(":", 1)[1]
    ), None)
    single_custom_source = bool({
        "single-custom-glyph-query",
        "single-custom-glyph-classical-consensus",
        "single-solid-glyph-classical-consensus",
    } & set(sources))
    physical = _physical_midline_text_support(reir, mask)
    physical_role = "persistent-physical-midline-topology"
    if physical is None and single_custom_source:
        # A fully solid dot/block has no internal midline transition and is
        # therefore rejected by the ordinary multi-glyph density wall.  For a
        # typed single-glyph query or repeated threshold consensus, the exact
        # immutable support itself is the physical certificate: no pixel is
        # invented and the downstream polarity/court walls still apply.
        physical = _freeze_mask(np.asarray(mask, bool))
        physical_role = "single-glyph-exact-threshold-support"
    if recognized_text is not None:
        ocr_physical = _ocr_physical_midline_text_support(
            reir, mask, recognized_text,
        )
        contract = _ocr_semantic_topology_contract(recognized_text)
        semantic_proved = False
        if contract is not None and ocr_physical is not None:
            glyphs, counters = contract
            semantic_proved = _topology(ocr_physical) == (
                len(glyphs), int(sum(counters)),
            )
            if semantic_proved:
                physical = ocr_physical
                physical_role = (
                    "OCR-bounded-physical-subset-with-connectivity-uncertainty"
                )
                sources = (*sources, "OCR-semantic-digital-preimage-topology")
        if physical is None and ocr_physical is not None:
            physical = ocr_physical
            physical_role = (
                "OCR-bounded-physical-subset-with-connectivity-uncertainty"
            )
    if physical is None:
        return None
    mask = physical
    sources = (*sources, physical_role)
    if polarity in {"dark-on-light", "light-on-dark"}:
        # A polarity threshold also exposes the *negative spaces* between and
        # inside real letters.  Those voids can look like a second aligned
        # glyph row, but exporting them paints the canvas/background color as
        # text.  Require the proposed foreground to be the minority class in
        # its complete line box, not merely in its own connected components.
        rgba = np.asarray(reir.raster.straight_rgba, np.float32)
        alpha = np.clip(rgba[..., 3], 0.0, 1.0)
        luminance = (
            0.2126 * rgba[..., 0] + 0.7152 * rgba[..., 1]
            + 0.0722 * rgba[..., 2]
        ) * alpha + (1.0 - alpha)
        ring = cv2.dilate(
            mask.astype(np.uint8), np.ones((5, 5), np.uint8),
        ).astype(bool) & ~mask
        if not np.any(ring):
            return None
        foreground_level = float(np.median(luminance[mask]))
        background_level = float(np.median(luminance[ring]))
        signed_contrast = foreground_level - background_level
        if (
            polarity == "dark-on-light" and signed_contrast >= -0.045
        ) or (
            polarity == "light-on-dark" and signed_contrast <= 0.045
        ):
            return None
        x1, y1, x2, y2 = _bbox(mask, pad=2)
        local = luminance[y1:y2, x1:x2]
        midpoint = 0.5 * (foreground_level + background_level)
        local_foreground = (
            local <= midpoint
            if polarity == "dark-on-light" else local >= midpoint
        )
        foreground_fraction = float(np.mean(local_foreground))
        captured_fraction = float(
            np.sum(mask[y1:y2, x1:x2])
            / max(1, int(np.sum(local_foreground)))
        )
        if foreground_fraction > 0.55 or captured_fraction < 0.50:
            return None
    components, _holes = _topology(mask)
    if components <= 0:
        return None
    digest = mask_sha256(mask)[:16]
    line_id = f"text-line-{digest}"
    recognized = max(
        (
            source.partition("ocr-text:")[2]
            for source in sources if source.startswith("ocr-text:")
        ),
        key=len, default="",
    )
    semantic_glyphs = (
        _semantic_glyph_observations(mask, line_id, recognized)
        if recognized else ()
    )
    # Physical component observations remain the acceptance evidence.  OCR
    # cell grouping affects only the admitted line's design program; it must
    # not make a previously valid physical proposal appear valid or invalid.
    glyphs = _glyph_observations(mask, line_id)
    if not glyphs:
        return None
    baselines = np.asarray([glyph.baseline for glyph in glyphs], np.float64)
    heights = np.asarray([glyph.height for glyph in glyphs], np.float64)
    stems = np.asarray([glyph.stem_width for glyph in glyphs], np.float64)
    baseline = float(np.median(baselines))
    median_height = float(np.median(heights))
    source_set = set(sources)
    is_ocr = "OCR" in source_set
    is_single_custom = single_custom_source
    is_outlined_word = "multi-counter-outlined-word" in source_set
    is_knockout = "knockout-negative-loops" in source_set
    # A global foreground threshold is useful evidence, but it is not by
    # itself a TextLine.  On emblems it commonly returns several large,
    # overlapping pieces of the logo; the old score then called those pieces
    # glyphs and could even make the resulting TextLine the canvas background.
    # Require the geometry that a horizontal line actually entails before the
    # proposal is allowed into CMIR.  OCR is the only lane allowed to carry a
    # single connected cursive word because it supplies independent semantic
    # evidence and an explicit line box.
    x1, y1, x2, y2 = _bbox(mask, pad=0)
    line_aspect = (x2 - x1) / max(1.0, y2 - y1)
    is_coherent_microtext = bool({
        "adaptive-foreground-topology-consensus",
        "adaptive-foreground-component-layout",
        "stable-small-component-line",
    } & source_set) and line_aspect >= 3.0 and len(glyphs) >= 4
    if len(glyphs) < 2 and not (
        is_ocr or is_single_custom or is_outlined_word or is_knockout
    ):
        return None
    body = heights >= max(2.0, 0.50 * median_height)
    body_baselines = baselines[body]
    body_height = float(np.median(heights[body])) if np.any(body) else median_height
    baseline_mad = (
        float(np.median(np.abs(
            body_baselines - np.median(body_baselines)
        ))) / max(1.0, body_height)
        if len(body_baselines) >= 2 else 0.0
    )
    baseline_p90 = (
        float(np.quantile(np.abs(
            body_baselines - np.median(body_baselines)
        ), 0.90)) / max(1.0, body_height)
        if len(body_baselines) >= 2 else 0.0
    )
    body_heights = heights[body] if np.any(body) else heights
    height_ratio = float(
        np.quantile(body_heights, 0.90)
        / max(1.0, np.quantile(body_heights, 0.10))
    )
    ordered_boxes = sorted(
        (glyph.bbox_xyxy for glyph in glyphs), key=lambda box: (box[0], box[1])
    )
    strong_overlaps = 0
    for left, right in zip(ordered_boxes, ordered_boxes[1:]):
        overlap = max(0, min(left[2], right[2]) - max(left[0], right[0]))
        smaller = max(1, min(left[2] - left[0], right[2] - right[0]))
        strong_overlaps += int(overlap / smaller > 0.35)
    if not (
        is_ocr or is_single_custom or is_outlined_word or is_knockout
        or is_coherent_microtext
    ) and (
        line_aspect < 1.15
        or baseline_mad > 0.30
        or baseline_p90 > 0.45
        or height_ratio > 2.20
        or strong_overlaps > max(0, (len(glyphs) - 1) // 3)
    ):
        return None
    # A dense bank of single-pixel JPEG/color components is valid foreground
    # evidence but not a glyph line.  Reject it before SDF/loop decoding: the
    # legacy token remains available as fallback, while the expensive TextLine
    # lane sees only physically resolvable glyph hypotheses.
    if len(glyphs) >= 4 and median_height < 1.75:
        # At genuinely tiny native sizes a whole word may consist mostly of
        # one-pixel stems.  Treating every such row as JPEG confetti erased
        # the right half of real h24 wordmarks.  The adaptive foreground bank
        # is allowed to carry it only when it is a wide, coherent line with
        # independently measured component-layout evidence; arbitrary dense
        # specks still fail closed here.
        if not is_coherent_microtext:
            return None
    baseline_consistency = math.exp(
        -float(np.median(np.abs(baselines - baseline))) / max(1.0, median_height)
    )
    stem_cv = float(np.std(stems) / max(0.25, np.mean(stems)))
    score = float(np.clip(
        0.55 * raw_score + 0.25 * baseline_consistency
        + 0.20 * math.exp(-stem_cv), 0.0, 1.0,
    ))
    ordered = sorted(glyphs, key=lambda item: item.bbox_xyxy[0])
    gaps = [
        max(0, right.bbox_xyxy[0] - left.bbox_xyxy[2])
        for left, right in zip(ordered, ordered[1:])
    ]
    frozen = _freeze_mask(mask)
    # Joint color/coverage statistics are independent of proposal ranking.
    # Fill them only after near-duplicate suppression, so losing threshold
    # masks do not pay another pixel-statistics pass.
    deferred_appearance = JointLineAppearance(
        foreground_linear_rgba=(0.0, 0.0, 0.0, 0.0),
        background_linear_rgba=(0.0, 0.0, 0.0, 0.0),
        foreground_oklab=(0.0, 0.0, 0.0), soft_coverage_mean=0.0,
        robust_scale=0.0, multi_color_groups=(),
    )
    proposal = TextLineProposal(
        id=line_id, roi_xyxy=_bbox(mask, pad=2), support_mask=frozen,
        polarity=polarity, sources=tuple(sorted(set(sources))), score=score,
        baseline=baseline, x_height=median_height,
        cap_height=float(np.quantile(heights, 0.8)),
        overshoot=float(np.max(baselines) - baseline), slant=0.0,
        tracking=float(np.median(gaps)) if gaps else 0.0,
        stem_classes=tuple(float(value) for value in np.unique(
            np.round(stems * 2.0) / 2.0
        )), glyphs=semantic_glyphs or glyphs, appearance=deferred_appearance,
    )
    proposal.validate(reir)
    return proposal


def _late_neural_glyph_refinements(
    reir: RasterEvidenceIR, proposals: Iterable[TextLineProposal],
    visible_rgb: np.ndarray,
) -> tuple[TextLineProposal, ...]:
    """Run optional whole-line and per-glyph priors on physical OCR lines.

    Raw OCR colour masks are deliberately cheap and can contain AA bridges,
    JPEG islands, or a full-logo carrier.  The physical TextLine decoder
    removes those ambiguities before this pass.  Querying the glyph model only
    before that decoder made the trained prior unreachable on nearly every
    real wordmark, even though the same model succeeded on the materialized
    line.  Keep each pass bounded to one line per OCR text.  The per-glyph lane
    prefers its exact independent-cell topology, while the whole-line lane
    independently prefers the highest-scoring physical line and predicts its
    own joined/global topology.  The whole-line lane is batched and never
    creates character-cell seams; both neural results remain separate proposals
    and must pass source-IoU, edit-fraction, topology, and physical-line gates.
    """
    wordmark_override = os.environ.get(
        "VICE_WORDMARK_PRIOR_CHECKPOINT", "",
    ).strip()
    wordmark_evaluation = (
        os.environ.get("VICE_WORDMARK_PRIOR_EVALUATION") == "1"
    )
    model_root = Path(__file__).resolve().parents[1] / "models"
    wordmark_enabled = bool(wordmark_override and wordmark_evaluation) or (
        (model_root / "wordmark_prior.pt").is_file()
        and (model_root / "wordmark_prior_promotion.json").is_file()
    )
    glyph_candidates: list[
        tuple[int, float, str, str, TextLineProposal]
    ] = []
    wordmark_candidates: list[
        tuple[float, str, str, TextLineProposal]
    ] = []
    for proposal in proposals:
        source_set = set(proposal.sources)
        if (
            "OCR" not in source_set
            or "font-free-character-conditioned-glyph-prior" in source_set
            or "font-free-whole-line-wordmark-prior" in source_set
            or not ({
                "persistent-physical-midline-topology",
                "OCR-bounded-physical-subset-with-connectivity-uncertainty",
            } & source_set)
        ):
            continue
        recognized = max((
            source.partition("ocr-text:")[2]
            for source in proposal.sources if source.startswith("ocr-text:")
        ), key=len, default="")
        glyph_contract = _glyph_prior_topology_contract(recognized)
        wordmark_contract = _wordmark_prior_text_contract(recognized)
        if glyph_contract is not None:
            _glyphs, components, counters = glyph_contract
            expected = (int(sum(components)), int(sum(counters)))
            observed = _topology(proposal.support_mask)
            topology_distance = abs(observed[0] - expected[0]) + abs(
                observed[1] - expected[1]
            )
            glyph_candidates.append((
                topology_distance, -proposal.score, proposal.id,
                recognized, proposal,
            ))
        if wordmark_enabled and wordmark_contract is not None:
            wordmark_candidates.append((
                -proposal.score, proposal.id, recognized, proposal,
            ))

    prepared: dict[
        tuple[str, str],
        tuple[str, TextLineProposal, np.ndarray, bool, np.ndarray],
    ] = {}

    def prepare(
        recognized: str, proposal: TextLineProposal,
    ) -> tuple[str, TextLineProposal, np.ndarray, bool, np.ndarray]:
        key = (recognized, proposal.id)
        if key in prepared:
            return prepared[key]
        neural_input = proposal.support_mask
        observed_ink = proposal.support_mask.astype(np.float32)
        adaptive_used = False
        modal = _modal_background_around_box(
            visible_rgb, proposal.roi_xyxy,
        )
        if modal is not None:
            modal_background, noise_floor = modal
            distance = np.linalg.norm(
                np.asarray(visible_rgb, np.float32)
                - modal_background[None, None, :], axis=2,
            ).astype(np.float32)
            x1, y1, x2, y2 = proposal.roi_xyxy
            local_distance = distance[y1:y2, x1:x2]
            contrast_scale = max(
                float(noise_floor) * 3.0,
                float(np.quantile(local_distance, 0.995)), 1.0e-6,
            )
            halo = cv2.dilate(
                proposal.support_mask.astype(np.uint8),
                np.ones((5, 5), np.uint8),
            ) > 0
            observed_ink = np.maximum(
                proposal.support_mask.astype(np.float32),
                np.clip(distance / contrast_scale, 0.0, 1.0) * halo,
            )
            adaptive = _ocr_adaptive_glyph_preimage(
                proposal.support_mask, distance, recognized,
                noise_floor=noise_floor,
            )
            if adaptive is not None:
                neural_input = adaptive
                adaptive_used = True
        row = (
            recognized, proposal, neural_input, adaptive_used, observed_ink,
        )
        prepared[key] = row
        return row

    # At most one attempt per lane and OCR string.  Independent topology sorts
    # first only for the per-glyph model; applying that law to whole connected
    # words made their best source mask unreachable.
    glyph_attempted: set[str] = set()
    glyph_selected: list[
        tuple[str, TextLineProposal, np.ndarray, bool, np.ndarray]
    ] = []
    for _distance, _negative_score, _line_id, recognized, proposal in sorted(
        glyph_candidates, key=lambda row: row[:4],
    ):
        if recognized in glyph_attempted:
            continue
        glyph_attempted.add(recognized)
        glyph_selected.append(prepare(recognized, proposal))
    wordmark_attempted: set[str] = set()
    wordmark_selected: list[
        tuple[str, TextLineProposal, np.ndarray, bool, np.ndarray]
    ] = []
    for _negative_score, _line_id, recognized, proposal in sorted(
        wordmark_candidates, key=lambda row: row[:3],
    ):
        if recognized in wordmark_attempted:
            continue
        wordmark_attempted.add(recognized)
        wordmark_selected.append(prepare(recognized, proposal))

    if wordmark_enabled:
        from .wordmark_runtime import WordmarkPriorInput, propose_wordmark_masks
        wordmark_results = propose_wordmark_masks(tuple(
            WordmarkPriorInput(
                observed_ink=observed_ink, recognized_text=recognized,
                certified_support=proposal.support_mask,
            )
            for (
                recognized, proposal, _neural_input, _adaptive, observed_ink
            ) in wordmark_selected
        ))
    else:
        wordmark_results = tuple(None for _ in wordmark_selected)

    refinements: list[TextLineProposal] = []
    for row, wordmark in zip(wordmark_selected, wordmark_results):
        _recognized, proposal, _neural_input, _adaptive_used, _observed_ink = row
        if wordmark is not None:
            wordmark_sources = (
                *proposal.sources,
                "font-free-whole-line-wordmark-prior",
                "late-neural-after-certified-physical-line",
                "ordered-text-conditioned-wordmark",
                "no-character-cell-seams",
                "batched-whole-line-inference",
                "native-resolution-topology-recertified",
                "source-bounded-neural-proposal",
                f"wordmark-topology:{wordmark.predicted_topology[0]}:"
                f"{wordmark.predicted_topology[1]}",
                f"wordmark-topology-confidence:{wordmark.topology_confidence:.6f}",
                f"wordmark-support-threshold:{wordmark.support_threshold:.3f}",
                f"wordmark-repair-confidence-threshold:"
                f"{wordmark.repair_confidence_threshold:.3f}",
                f"wordmark-checkpoint-epoch:{wordmark.checkpoint_epoch}",
                f"neural-source-iou:{wordmark.source_iou:.6f}",
                f"neural-source-edit-fraction:"
                f"{wordmark.source_edit_fraction:.6f}",
            )
            whole_line = _line_from_mask(
                reir, wordmark.support_mask, polarity=proposal.polarity,
                sources=wordmark_sources, raw_score=proposal.score,
            )
            if whole_line is not None:
                refinements.append(whole_line)

    for row in glyph_selected:
        recognized, proposal, neural_input, adaptive_used, _observed_ink = row
        neural_support = _ocr_neural_glyph_preimage(
            neural_input, visible_rgb, recognized,
        )
        if neural_support is None:
            continue
        intersection = int(np.sum(
            neural_support & proposal.support_mask,
        ))
        union = int(np.sum(neural_support | proposal.support_mask))
        source_iou = intersection / max(1, union)
        source_edit_fraction = int(np.sum(
            neural_support != proposal.support_mask,
        )) / max(1, int(np.sum(proposal.support_mask)))
        # Composition of two individually bounded refinements must remain
        # bounded against the original certified physical owner as well.
        if source_iou < 0.42 or source_edit_fraction > 0.55:
            continue
        sources = (
            *proposal.sources,
            "font-free-character-conditioned-glyph-prior",
            "late-neural-after-certified-physical-line",
            "positive-negative-support-and-SDF",
            "optional-skeleton-head",
            "exact-source-topology-gate",
            *(("late-adaptive-topology-plateau",) if adaptive_used else ()),
            f"neural-source-iou:{source_iou:.6f}",
            f"neural-source-edit-fraction:{source_edit_fraction:.6f}",
        )
        refined = _line_from_mask(
            reir, neural_support, polarity=proposal.polarity,
            sources=sources,
            # The late proposal inherits only the already calibrated line
            # score.  It gains no ranking bonus merely for using a model.
            raw_score=proposal.score,
        )
        if refined is not None:
            refinements.append(refined)
    return tuple(refinements)


def propose_text_lines(
    reir: RasterEvidenceIR, *, max_proposals: int = 32,
    ocr_hints: Iterable[
        tuple[str, tuple[int, int, int, int], float]
    ] = (), validate_reir: bool = True,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> tuple[TextLineProposal, ...]:
    """Union query tokens, both polarities, component alignment and SWT cues."""
    if validate_reir:
        reir.validate()
    ocr_hints = tuple(ocr_hints)
    premultiplied = np.asarray(
        reir.raster.linear_premultiplied_rgba, np.float32,
    )
    alpha = np.clip(premultiplied[..., 3], 0.0, 1.0)
    visible = premultiplied[..., :3] + (1.0 - alpha[..., None])
    drafts: list[_LineMaskDraft] = []
    text_tokens = [token for token in reir.proposal_tokens if token.family == "text"]
    layer_masks = [
        mask for token in reir.proposal_tokens if token.family == "layer"
        for mask in (decode_token_mask(token, (reir.height, reir.width)),)
        if mask is not None
    ]
    for token in text_tokens:
        mask = decode_token_mask(token, (reir.height, reir.width))
        if mask is None or not np.any(mask):
            continue
        token_parameters = dict(token.parameters)
        token_polarity_role: tuple[str, ...] = ()
        declared_components = token_parameters.get("topology_components")
        declared_holes = token_parameters.get("topology_holes")
        if isinstance(declared_components, (float, int)) and isinstance(
            declared_holes, (float, int),
        ):
            declared_topology = (
                int(declared_components), int(declared_holes),
            )
            inverted = ~np.asarray(mask, bool)
            # Adaptive foreground consensus is allowed to discover the right
            # geometry with the wrong binary polarity on a full-frame crop.
            # Reconcile only when the immutable token's own declared topology
            # matches the complement exactly and that complement is a bounded
            # minority support.  This recovers a black `0` from its white
            # carrier without treating arbitrary inverse canvases as text.
            if (
                token.provenance == "adaptive-foreground-topology-consensus"
                and _topology(mask) != declared_topology
                and _topology(inverted) == declared_topology
                and 0.005 <= float(np.mean(inverted)) <= 0.65
            ):
                mask = _freeze_mask(inverted)
                token_polarity_role = (
                    "token-polarity-reconciled-to-consensus-topology",
                )
        components, holes = _topology(mask)
        x1, y1, x2, y2 = _bbox(mask, pad=0)
        outline_role = (
            ("multi-counter-outlined-word",)
            if (
                components == 1 and holes >= 2
                and (x2 - x1) / max(1.0, y2 - y1) >= 1.5
                and float(np.mean(mask[y1:y2, x1:x2])) <= 0.45
            ) else ()
        )
        token_density = float(np.mean(mask[y1:y2, x1:x2]))
        knockout_support = (
            enclosed_negative_loops(mask)
            if (
                components == 1 and holes >= 2 and token_density >= 0.68
                and (x2 - x1) / max(1.0, y2 - y1) >= 1.5
            ) else _freeze_mask(np.zeros_like(mask))
        )
        top_layer = any(
            np.sum(mask & layer_mask) / max(1, np.sum(mask)) >= 0.5
            for layer_mask in layer_masks
        )
        persistent = _persistent_text_support(mask)
        token_x1, token_y1, token_x2, token_y2 = _bbox(mask, pad=0)
        coherent_micro_token = bool(
            token.provenance in {
                "adaptive-foreground-topology-consensus",
                "adaptive-foreground-component-layout",
                "stable-small-component-line",
            }
            and (token_x2 - token_x1) / max(1.0, token_y2 - token_y1) >= 3.0
            and components >= 4
        )
        # A lone glyph cannot satisfy ordinary multi-component line geometry.
        # The adaptive bank nevertheless supplies an independent, repeated
        # threshold vote for its component/counter topology.  Admit only the
        # strongest character-like case. Countered bodies are intrinsically
        # glyph-like; a counterless body additionally needs the isolated-glyph
        # certificate emitted from repeated physical thresholds.
        consensus_holes = int(token_parameters.get("topology_holes", 0))
        solid_isolated_glyph = bool(
            int(token_parameters.get("topology_components", -1)) == 1
            and float(token_parameters.get("isolated_glyph", 0.0)) >= 1.0
            and float(token_parameters.get("local_occupancy", 0.0)) >= 0.95
        )
        classical_single_glyph = bool(
            int(token_parameters.get("topology_components", -1)) == 1
            and (
                consensus_holes >= 1
                or float(token_parameters.get("isolated_glyph", 0.0)) >= 1.0
            )
            and (
                token.provenance == "adaptive-foreground-topology-consensus"
                and float(token_parameters.get("topology_votes", 0.0)) >= 4.0
                or solid_isolated_glyph
            )
            and (token_x2 - token_x1) / max(
                1.0, token_y2 - token_y1,
            ) <= 1.6
        )
        single_glyph_role = (
            (
                "single-custom-glyph-classical-consensus",
                *(
                    ("single-solid-glyph-classical-consensus",)
                    if consensus_holes == 0 else ()
                ),
            )
            if classical_single_glyph else ()
        )
        if classical_single_glyph:
            # JPEG/resize borders can add a second canvas-edge component to an
            # otherwise stable one-counter glyph.  The consensus topology is
            # specifically one body/one-or-more counters, so isolate the only
            # component that actually carries that observed counter.  This is
            # a subset of the immutable token, never an invented stroke.
            labels_count, labels = cv2.connectedComponents(
                np.asarray(persistent, np.uint8), 8,
            )
            counter_components = []
            for label in range(1, labels_count):
                component = labels == label
                if _topology(component)[1] >= 1:
                    counter_components.append(component)
            if len(counter_components) == 1:
                drafts.append(_LineMaskDraft(
                    _freeze_mask(counter_components[0]), "token-persistent", (
                        "lightweight-query-token", "component-alignment",
                        "SWT/stroke-consistency",
                        "persistent-component/counter-filter",
                        "single-custom-glyph-classical-consensus",
                        *(
                            ("single-solid-glyph-classical-consensus",)
                            if consensus_holes == 0 else ()
                        ),
                        token.provenance,
                    ), float(np.clip(token.score + 0.12, 0.0, 1.0)),
                ))
        # The incumbent token itself is already present as the fail-open
        # legacy column.  Only duplicate it into the new TextLine bank when
        # physical filtering does not materially change it.
        if (
            coherent_micro_token
            or
            not np.any(persistent)
            or np.sum(persistent) / max(1, np.sum(mask)) >= 0.97
        ):
            drafts.append(_LineMaskDraft(
                _freeze_mask(mask), "token", (
                "lightweight-query-token", "component-alignment",
                "SWT/stroke-consistency", *outline_role,
                *single_glyph_role, *token_polarity_role, token.provenance,
                *(('top-layer-clue',) if top_layer else ()),
                ), float(np.clip(token.score, 0.0, 1.0)),
            ))
        if np.any(persistent) and not np.array_equal(persistent, mask):
            drafts.append(_LineMaskDraft(
                persistent, "token-persistent", (
                    "lightweight-query-token", "component-alignment",
                    "SWT/stroke-consistency", "persistent-component/counter-filter",
                    *outline_role, *single_glyph_role,
                    *token_polarity_role, token.provenance,
                ), float(np.clip(token.score + 0.08, 0.0, 1.0)),
            ))
        if np.any(knockout_support):
            knockout_components, _knockout_holes = _topology(knockout_support)
            if knockout_components >= 2:
                drafts.append(_LineMaskDraft(
                    knockout_support, "light-on-dark", (
                        "lightweight-query-token", "component-alignment",
                        "knockout-negative-loops", "top-layer-clue",
                        "dense-carrier-enclosed-complement", token.provenance,
                    ), float(np.clip(token.score + 0.10, 0.0, 1.0)),
                ))

    # Knockout lettering is often discovered first as a dense component or
    # topology carrier rather than a positive text token.  Promote only the
    # carrier's exact enclosed complement; the carrier itself never enters the
    # text bank through this lane.
    carrier_rows: list[tuple[float, str, np.ndarray, str]] = []
    for token in reir.proposal_tokens:
        if token.family not in {"component", "topology", "layer"}:
            continue
        # The exact carrier predicate below already requires a wide, bounded,
        # dense support.  Apply those necessary conditions to immutable token
        # metadata before RLE decoding and contour extraction: on small logo
        # rasters this avoids doing topology work for dozens of tiny components
        # without changing which masks can enter the carrier lane.
        token_x1, token_y1, token_x2, token_y2 = token.bbox_xyxy
        token_width = token_x2 - token_x1
        token_height = token_y2 - token_y1
        token_bbox_area = token_width * token_height
        if (
            token_width / max(1.0, token_height) < 1.5
            or token_bbox_area / max(1, reir.width * reir.height) > 0.92
        ):
            continue
        parameters = dict(token.parameters)
        token_area = parameters.get("area")
        if isinstance(token_area, (float, int)) and token_bbox_area > 0:
            metadata_density = float(token_area) / token_bbox_area
            if not 0.68 <= metadata_density <= 0.90:
                continue
        token_components = parameters.get("components")
        token_holes = parameters.get("holes")
        if isinstance(token_components, (float, int)) and int(token_components) != 1:
            continue
        if isinstance(token_holes, (float, int)) and int(token_holes) < 2:
            continue
        carrier = decode_token_mask(token, (reir.height, reir.width))
        if carrier is None or not np.any(carrier):
            continue
        components, holes = _topology(carrier)
        if components != 1 or holes < 2:
            continue
        x1, y1, x2, y2 = _bbox(carrier, pad=0)
        width = x2 - x1; height = y2 - y1
        density = float(np.mean(carrier[y1:y2, x1:x2]))
        canvas_fraction = width * height / max(1, reir.width * reir.height)
        if (
            not 0.68 <= density <= 0.90
            or width / max(1.0, height) < 1.5
            or canvas_fraction > 0.92
        ):
            continue
        negative = enclosed_negative_loops(carrier)
        negative_components, _negative_holes = _topology(negative)
        if negative_components < 2:
            continue
        carrier_rows.append((
            float(token.score), token.id, negative, token.provenance,
        ))
    for score, token_id, negative, provenance in sorted(
        carrier_rows, key=lambda row: (-row[0], row[1]),
    )[:4]:
        drafts.append(_LineMaskDraft(
            negative, "light-on-dark", (
                "component-alignment", "knockout-negative-loops",
                "top-layer-clue", "dense-carrier-enclosed-complement",
                f"carrier-token:{token_id}", provenance,
            ), float(np.clip(score + 0.10, 0.0, 1.0)),
        ))

    light = np.clip(reir.raster.oklab[..., 0] * 255.0, 0, 255).astype(np.uint8)
    _threshold, dark = cv2.threshold(
        light, 0, 1, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    _threshold, bright = cv2.threshold(
        light, 0, 1, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )

    # Coverage/midline bank in canonical linear RGB.  A single Otsu split is
    # not physically sufficient: compressed AA text can require a soft support
    # level while ideal topology lives near the 50% coverage midline.  These
    # six fixed levels are renderer-independent and remain a bounded union.
    linear_rgb = np.asarray(reir.raster.straight_rgba[..., :3], np.float32)
    border_samples = np.concatenate((
        linear_rgb[0], linear_rgb[-1], linear_rgb[:, 0], linear_rgb[:, -1],
    ), axis=0)
    background = np.median(border_samples, axis=0)
    border_distance = np.max(np.abs(border_samples - background), axis=1)
    border_median = float(np.median(border_distance))
    border_noise = 1.4826 * float(np.median(
        np.abs(border_distance - border_median)
    ))
    physical_floor = max(0.025, border_median + 3.0 * border_noise)
    distance = np.max(np.abs(linear_rgb - background), axis=2)
    for level in (0.08, 0.16, 0.28, 0.45, 0.62, 0.78):
        threshold = max(physical_floor, level)
        field = distance >= threshold
        occupancy = float(np.mean(field))
        if not 0.001 <= occupancy <= 0.65:
            continue
        drafts.append(_LineMaskDraft(
            _freeze_mask(field), "native-ink-coverage", (
                "multithreshold-native-ink", "both-polarities",
                "component-alignment", "SWT/stroke-consistency",
                f"linear-rgb-distance:{threshold:.3f}",
            ), float(0.73 + 0.08 * math.exp(
                -abs(level - 0.45) / 0.20
            )),
        ))

    for polarity, field in (("dark-on-light", dark), ("light-on-dark", bright)):
        for group in _group_aligned_components(_component_rows(field > 0)):
            if len(group) < 2:
                continue
            mask = np.zeros((reir.height, reir.width), bool)
            for component, _component_bbox in group:
                mask |= component
            roi = _bbox(mask, pad=1)
            x1, y1, x2, y2 = roi
            if x2 - x1 < max(3, y2 - y1):
                continue
            drafts.append(_LineMaskDraft(
                _freeze_mask(mask), polarity, (
                    "both-polarities", "component-alignment",
                    "SWT/stroke-consistency", "repeated-size/stem-evidence",
                ), 0.68,
            ))

    # Neural queries enter before glyph fitting and provide only a bounded
    # attention envelope.  The actual ink hypothesis still comes from the two
    # independently measured source polarities and must pass all later walls.
    for query in proposal_queries:
        if query.family not in {"text_line", "glyph_group"}:
            continue
        query_mask = query_support_mask(reir, query, minimum_pixels=3)
        if query_mask is None:
            continue
        from .proposal_net import query_head_prior_score
        query_score, head_provenance = query_head_prior_score(
            query, query_mask, expected_relation_groups=(
                ("same_group",), ("text_membership",),
            ),
        )
        envelope = cv2.dilate(
            query_mask.astype(np.uint8), np.ones((3, 3), np.uint8),
        ) > 0
        for polarity, field in (("dark-on-light", dark > 0),
                                ("light-on-dark", bright > 0)):
            candidate_mask = envelope & field
            if int(candidate_mask.sum()) < 3:
                continue
            query_role = (
                (
                    "single-custom-glyph-query",
                    *(
                        ("single-composite-custom-glyph-query",)
                        if _vertically_registered_composite_glyph(candidate_mask)
                        else ()
                    ),
                ) if query.family == "glyph_group" else ()
            )
            drafts.append(_LineMaskDraft(
                _freeze_mask(candidate_mask), polarity, (
                     "ProposalNet-guided-before-text-fitting", query.id,
                     "both-polarities", "component-alignment",
                     "SWT/stroke-consistency", *query_role,
                     *head_provenance, *query.provenance,
                ), query_score,
            ))

    for text, raw_bbox, confidence in ocr_hints:
        x1, y1, x2, y2 = (
            max(0, int(raw_bbox[0])), max(0, int(raw_bbox[1])),
            min(reir.width, int(raw_bbox[2])), min(reir.height, int(raw_bbox[3])),
        )
        if not text or x2 <= x1 or y2 <= y1:
            continue
        # Luminance Otsu misses coloured wordmarks whose lightness is close to
        # a JPEG-tinted background.  OCR supplies the semantic line box; the
        # dominant local colour supplies an independent physical background.
        # Threshold the full linear-RGB distance, never a guessed text colour.
        local_visible = visible[y1:y2, x1:x2]
        modal = _modal_background_around_box(visible, (x1, y1, x2, y2))
        if modal is not None:
            modal_background, modal_noise_floor = modal
            color_distance = np.linalg.norm(
                local_visible - modal_background[None, None, :], axis=2,
            )
            peak = float(np.max(color_distance))
            if peak > modal_noise_floor + 0.04:
                distance_u8 = np.clip(
                    color_distance / peak * 255.0, 0, 255,
                ).astype(np.uint8)
                raw_threshold, _binary = cv2.threshold(
                    distance_u8, 0, 1, cv2.THRESH_BINARY | cv2.THRESH_OTSU,
                )
                threshold = max(
                    modal_noise_floor, float(raw_threshold) / 255.0 * peak,
                )
                local_color = color_distance >= threshold
                occupancy = float(np.mean(local_color))
                # Condensed seven-pixel uppercase can legitimately occupy
                # about two thirds of its tight OCR box.  The downstream
                # physical-line density wall is 0.70, so rejecting at 0.65
                # here created an inconsistent dead band in which a valid
                # source proof could never reach that wall.
                if 0.01 <= occupancy <= 0.70 and np.any(local_color):
                    color_mask = np.zeros((reir.height, reir.width), bool)
                    color_mask[y1:y2, x1:x2] = local_color
                    drafts.append(_LineMaskDraft(
                        _freeze_mask(color_mask), "native-color-distance", (
                            "OCR", "OCR-color-distance-to-modal-background",
                            "component-alignment", "SWT/stroke-consistency",
                            f"ocr-text:{text}",
                        ), float(np.clip(confidence, 0.0, 1.0)),
                    ))
                    full_distance = np.zeros(
                        (reir.height, reir.width), np.float32,
                    )
                    full_distance[y1:y2, x1:x2] = color_distance
                    adaptive = _ocr_adaptive_glyph_preimage(
                        color_mask, full_distance, text,
                        noise_floor=modal_noise_floor,
                    )
                    if adaptive is not None:
                        drafts.append(_LineMaskDraft(
                            adaptive, "ocr-adaptive-glyph-preimage", (
                                "OCR", "OCR-adaptive-per-glyph-topology-plateau",
                                "OCR-semantic-digital-preimage-topology",
                                "linear-RGB-soft-coverage", "component-alignment",
                                "SWT/stroke-consistency", f"ocr-text:{text}",
                            ), float(np.clip(0.97 * confidence, 0.0, 1.0)),
                        ))
                    neural_glyphs = _ocr_neural_glyph_preimage(
                        color_mask, visible, text,
                    )
                    if neural_glyphs is not None:
                        drafts.append(_LineMaskDraft(
                            neural_glyphs, "ocr-neural-glyph-prior", (
                                "OCR", "font-free-character-conditioned-glyph-prior",
                                "positive-negative-support-and-SDF",
                                "optional-skeleton-head",
                                "exact-source-topology-gate",
                                "component-alignment", "SWT/stroke-consistency",
                                f"ocr-text:{text}",
                            ), float(np.clip(0.985 * confidence, 0.0, 1.0)),
                        ))
        candidates = []
        for polarity, field in (("dark-on-light", dark > 0),
                                ("light-on-dark", bright > 0)):
            local = np.zeros((reir.height, reir.width), bool)
            local[y1:y2, x1:x2] = field[y1:y2, x1:x2]
            occupancy = float(np.mean(local[y1:y2, x1:x2]))
            if 0.01 <= occupancy <= 0.85:
                candidates.append((abs(occupancy - 0.30), polarity, local))
        if not candidates:
            continue
        _distance, polarity, mask = min(candidates, key=lambda row: row[0])
        drafts.append(_LineMaskDraft(
            _freeze_mask(mask), polarity,
            ("OCR", "component-alignment", "both-polarities",
             "SWT/stroke-consistency", f"ocr-text:{text}"),
            float(np.clip(confidence, 0.0, 1.0)),
        ))

    # Deduplicate and quota the cheap masks before per-glyph topology/stem/Hu
    # extraction.  This is the cheap->expensive boundary of the line proposer.
    by_digest: dict[str, _LineMaskDraft] = {}
    for draft in drafts:
        digest = mask_sha256(draft.mask)
        incumbent = by_digest.get(digest)
        if incumbent is None:
            by_digest[digest] = draft
            continue
        # Equal support can be discovered independently by the token,
        # physical and alignment lanes.  Ranking may choose one of those
        # observations, but the other observations are still proof evidence:
        # dropping their provenance here used to erase the explicit
        # multi-counter outlined-word role before the exact line decoder saw
        # it.  Keep the winning score/polarity and union the immutable evidence
        # labels deterministically.
        winner = (
            draft if draft.raw_score > incumbent.raw_score else incumbent
        )
        by_digest[digest] = replace(
            winner,
            sources=tuple(sorted(set(incumbent.sources) | set(draft.sources))),
        )

    cheap_key_cache: dict[int, tuple[float, str]] = {}

    def cheap_key(draft: _LineMaskDraft) -> tuple[float, str]:
        cached = cheap_key_cache.get(id(draft))
        if cached is not None:
            return cached
        x1, y1, x2, y2 = _bbox(draft.mask, pad=0)
        aspect = (x2 - x1) / max(1.0, y2 - y1)
        occupancy = float(np.mean(draft.mask[y1:y2, x1:x2]))
        plausibility = (
            0.05 * min(3.0, aspect) - 0.04 * abs(occupancy - 0.30)
        )
        result = draft.raw_score + plausibility, mask_sha256(draft.mask)
        cheap_key_cache[id(draft)] = result
        return result

    categories: dict[str, list[_LineMaskDraft]] = {
        "token": [], "physical": [], "ocr": [],
        "independent": [], "neural": [],
    }
    for draft in by_digest.values():
        category = (
            "ocr" if "OCR" in draft.sources
            else "physical" if "multithreshold-native-ink" in draft.sources
            else "token" if "lightweight-query-token" in draft.sources
            else "neural" if "ProposalNet-guided-before-text-fitting" in draft.sources
            else "independent"
        )
        categories[category].append(draft)
    for rows in categories.values():
        rows.sort(key=lambda row: (-cheap_key(row)[0], cheap_key(row)[1]))
    # Nine exact line decodes preserve the T2 latency budget.  The token quota
    # below explicitly retains topology/coverage diversity, so the complete
    # 50%-coverage microtext hypothesis cannot be starved by two softer masks
    # without paying for every one of the plan's <=12 cheap ROI candidates.
    expensive_limit = max(
        1, min(int(max_proposals), 12 if ocr_hints else 9),
    )
    quotas = {
        "token": 3,
        "physical": 3,
        "ocr": 4,
        "independent": 2,
        "neural": 1,
    }
    shortlisted: list[_LineMaskDraft] = []
    for category in ("token", "physical", "ocr", "independent", "neural"):
        rows = categories[category]
        if category == "token":
            # Broad adaptive-foreground tokens often score above the much
            # more discriminative stable-component line.  Spending both token
            # slots on near-identical whole-logo masks can yield zero valid
            # TextLines even when the REIR contains a clean word hypothesis.
            # Reserve one bounded slot for the independent aligned-component
            # lane, then fill the rest by the ordinary cheap score.
            aligned = next((
                row for row in rows
                if "stable-small-component-line" in row.sources
            ), None)
            maximum_span = max((
                _bbox(row.mask, pad=0)[2] - _bbox(row.mask, pad=0)[0]
                for row in rows
            ), default=0)
            complete = [
                row for row in rows
                if _bbox(row.mask, pad=0)[2] - _bbox(row.mask, pad=0)[0]
                >= 0.82 * maximum_span
            ]
            physical_midline = min(
                complete,
                key=lambda row: (int(np.sum(row.mask)), -cheap_key(row)[0]),
                default=None,
            )
            selected = []
            for special in (aligned, physical_midline):
                if special is not None and all(
                    special is not chosen for chosen in selected
                ):
                    selected.append(special)
            selected.extend(
                row for row in rows
                if all(row is not chosen for chosen in selected)
            )
            rows = selected
        elif category == "ocr" and len(rows) > 1:
            # Whole-logo neural crops can score above a real second text row.
            # Reserve vertical-layout diversity before filling by confidence,
            # otherwise adding an OCR ensemble silently evicts e.g. the small
            # STUDIOS line underneath STORMCRAFT.
            by_center = sorted(
                rows,
                key=lambda row: (
                    0.5 * (_bbox(row.mask, pad=0)[1] + _bbox(row.mask, pad=0)[3]),
                    -cheap_key(row)[0], cheap_key(row)[1],
                ),
            )
            diverse = [by_center[0]]
            if by_center[-1] is not by_center[0]:
                diverse.append(by_center[-1])
            diverse.extend(
                row for row in rows
                if all(row is not chosen for chosen in diverse)
            )
            rows = diverse
        shortlisted.extend(rows[:quotas[category]])
    if len(shortlisted) < expensive_limit:
        selected_digests = {mask_sha256(row.mask) for row in shortlisted}
        remainder = sorted(
            (row for row in by_digest.values()
             if mask_sha256(row.mask) not in selected_digests),
            key=lambda row: (-cheap_key(row)[0], cheap_key(row)[1]),
        )
        shortlisted.extend(remainder[:expensive_limit - len(shortlisted)])
    proposals = [
        proposal for draft in shortlisted[:expensive_limit]
        for proposal in (_line_from_mask(
            reir, draft.mask, polarity=draft.polarity,
            sources=draft.sources, raw_score=draft.raw_score,
        ),)
        if proposal is not None
    ]
    proposals.extend(_late_neural_glyph_refinements(
        reir, proposals, visible,
    ))
    proposals.extend(_stage_d_support_refinements(reir, proposals))

    # Suppress near-identical lower scoring proposals after exact line scoring.
    result: list[TextLineProposal] = []
    for proposal in sorted(
        proposals, key=lambda row: (-row.score, row.id)
    ):
        duplicate = False
        for kept_index, kept in enumerate(result):
            intersection = int(np.sum(proposal.support_mask & kept.support_mask))
            union = int(np.sum(proposal.support_mask | kept.support_mask))
            # A handful of weak AA pixels can be the entire difference
            # between separated and fused glyph bodies.  High IoU is not a
            # valid duplicate proof when persistent topology differs.
            if (
                intersection / max(1, union) >= 0.92
                and _topology(proposal.support_mask)
                == _topology(kept.support_mask)
            ):
                # Independent drafts can converge only after physical/OCR
                # topology decoding.  Their proof labels remain cumulative;
                # discarding the later label made a colour-distance OCR proof
                # look like a single-polarity guess despite identical bytes.
                if np.array_equal(
                    proposal.support_mask, kept.support_mask,
                ):
                    result[kept_index] = replace(
                        kept,
                        sources=tuple(sorted(
                            set(kept.sources) | set(proposal.sources)
                        )),
                        score=max(kept.score, proposal.score),
                    )
                duplicate = True
                break
        if not duplicate:
            materialized = replace(
                proposal,
                appearance=_joint_appearance(reir, proposal.support_mask),
            )
            result.append(materialized)
        if len(result) >= max(1, int(max_proposals)):
            break
    return tuple(result)


def topology_preserving_sdf_glyph(
    mask: np.ndarray, target_stem_width: float
) -> np.ndarray:
    original = np.asarray(mask, bool)
    if not np.any(original):
        return _freeze_mask(original)
    inside = cv2.distanceTransform(original.astype(np.uint8), cv2.DIST_L2, 5)
    outside = cv2.distanceTransform((~original).astype(np.uint8), cv2.DIST_L2, 5)
    signed = inside - outside
    offset = float(np.clip(
        0.5 * (_stem_width(original) - target_stem_width), -0.45, 0.45
    ))
    candidate = signed >= offset
    if _topology(candidate) != _topology(original):
        candidate = original
    intersection = int(np.sum(candidate & original))
    union = int(np.sum(candidate | original))
    if intersection / max(1, union) < 0.78:
        candidate = original
    return _freeze_mask(candidate)


def _dual_loops(glyph: GlyphObservation, mask: np.ndarray) -> DualLoopGlyphProgram:
    x1, y1, x2, y2 = glyph.bbox_xyxy
    local = np.asarray(mask[y1:y2, x1:x2], np.uint8)
    contours, hierarchy = cv2.findContours(
        local, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE
    )
    positive: list[tuple[tuple[float, float], ...]] = []
    negative: list[tuple[tuple[float, float], ...]] = []
    if hierarchy is not None:
        for index, contour in enumerate(contours):
            depth = 0; parent = int(hierarchy[0, index, 3])
            while parent >= 0:
                depth += 1; parent = int(hierarchy[0, parent, 3])
            perimeter = cv2.arcLength(contour, True)
            reduced = cv2.approxPolyDP(contour, max(0.18, 0.003 * perimeter), True)
            loop = tuple(
                (float(point[0][0] + x1) + 0.5,
                 float(point[0][1] + y1) + 0.5)
                for point in reduced
            )
            (positive if depth % 2 == 0 else negative).append(loop)
    return DualLoopGlyphProgram(
        glyph_id=glyph.id, positive_loops=tuple(positive),
        negative_loops=tuple(negative), topology_code=_topology(local),
        sdf_level=0.0, skeleton_width=_stem_width(local > 0),
    )


def repeated_glyph_em(
    glyphs: tuple[GlyphObservation, ...], *, iterations: int = 3,
    residual_limit: float = 0.18,
) -> tuple[GlyphPrototype, ...]:
    """Deterministic prototype + affine instance + bounded residual EM."""
    clusters: list[list[GlyphObservation]] = []
    for glyph in glyphs:
        target = None
        vector = np.asarray(glyph.descriptor[:7], np.float64)
        for cluster in clusters:
            first = cluster[0]
            if (
                glyph.semantic_character is not None
                or first.semantic_character is not None
            ) and glyph.semantic_character != first.semantic_character:
                continue
            if (glyph.components, glyph.holes) != (first.components, first.holes):
                continue
            distance = float(np.linalg.norm(
                vector - np.asarray(first.descriptor[:7], np.float64)
            ))
            if distance <= 1.35:
                target = cluster; break
        if target is None:
            clusters.append([glyph])
        else:
            target.append(glyph)
    prototypes: list[GlyphPrototype] = []
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        normalized = []
        affines = []
        for glyph in cluster:
            x1, y1, x2, y2 = glyph.bbox_xyxy
            local = glyph.support_mask.astype(np.uint8)
            normalized.append(cv2.resize(local, (32, 32), interpolation=cv2.INTER_AREA))
            affines.append((
                glyph.id,
                (float(x1), float(y1), (x2 - x1) / 32.0, (y2 - y1) / 32.0),
            ))
        prototype = np.mean(normalized, axis=0, dtype=np.float64) >= 0.5
        performed = 0
        for _iteration in range(max(1, int(iterations))):
            accepted = []
            for row in normalized:
                residual = float(np.mean((row >= 0.5) != prototype))
                if residual <= residual_limit:
                    accepted.append(row)
            if not accepted:
                break
            updated = np.mean(accepted, axis=0, dtype=np.float64) >= 0.5
            performed += 1
            if np.array_equal(updated, prototype):
                prototype = updated; break
            prototype = updated
        residuals = tuple((
            glyph.id, float(np.mean((row >= 0.5) != prototype))
        ) for glyph, row in zip(cluster, normalized))
        if max(value for _glyph_id, value in residuals) > residual_limit:
            continue
        frozen = _freeze_mask(prototype)
        prototypes.append(GlyphPrototype(
            id=f"glyph-prototype-{mask_sha256(frozen)[:16]}",
            member_ids=tuple(glyph.id for glyph in cluster),
            normalized_mask=frozen, instance_affines=tuple(affines),
            residual_fraction=residuals, iterations=performed,
        ))
    return tuple(prototypes)


def _boundary_deviation(first: np.ndarray, second: np.ndarray) -> float:
    kernel = np.ones((3, 3), np.uint8)
    first_boundary = cv2.morphologyEx(first.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    second_boundary = cv2.morphologyEx(second.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    if not np.any(first_boundary) or not np.any(second_boundary):
        return float(math.hypot(*first.shape))
    to_first = cv2.distanceTransform((~first_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    to_second = cv2.distanceTransform((~second_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    return max(float(np.max(to_first[second_boundary])),
               float(np.max(to_second[first_boundary])))


def _claims(
    line: TextLineProposal, candidate_mask: np.ndarray,
    prototypes: tuple[GlyphPrototype, ...], *, readability: float,
    render_evidence: float,
) -> TextCertificateClaims:
    required_components, required_holes = _topology(line.support_mask)
    components, holes = _topology(candidate_mask)
    baselines = np.asarray([glyph.baseline for glyph in line.glyphs])
    stems = np.asarray([glyph.stem_width for glyph in line.glyphs])
    repeated = (
        sum(len(prototype.member_ids) for prototype in prototypes)
        / max(1, len(line.glyphs))
    )
    return TextCertificateClaims(
        required_components=required_components,
        persistent_counters=required_holes,
        no_unproven_fusion=components >= required_components,
        no_unproven_hole_fill=holes >= required_holes,
        no_glyph_outside_line_support=not bool(
            np.any(candidate_mask & ~cv2.dilate(
                line.support_mask.astype(np.uint8), np.ones((3, 3), np.uint8)
            ).astype(bool))
        ),
        ocr_readability=float(np.clip(readability, 0.0, 1.0)),
        baseline_consistency=float(math.exp(
            -np.std(baselines) / max(1.0, line.x_height)
        )),
        stem_consistency=float(math.exp(
            -np.std(stems) / max(0.25, np.mean(stems))
        )),
        repeated_glyph_agreement=float(np.clip(repeated, 0.0, 1.0)),
        line_render_evidence=float(np.clip(render_evidence, 0.0, 1.0)),
    )


def _macro_record(
    reir: RasterEvidenceIR, line: TextLineProposal, mask: np.ndarray,
    *, path: str, score: float, claims: TextCertificateClaims,
    dual: tuple[DualLoopGlyphProgram, ...],
    prototypes: tuple[GlyphPrototype, ...], parameters: tuple[tuple[str, float | int | str], ...],
    provenance: tuple[str, ...], base_candidate: MacroCandidate | None = None,
    effect_layers: tuple[TextEffectLayer, ...] = (),
) -> TextMacroRecord | None:
    if not claims.hard_valid:
        return None
    if base_candidate is None:
        components, holes = _topology(mask)
        candidate = candidate_from_support(
            reir, family="text", mask=mask, roi_xyxy=line.roi_xyxy,
            evidence_token_ids=tuple(
                token.id for token in reir.proposal_tokens
                if token.family == "text"
            ), score=score, provenance=provenance,
            kind=MacroKind.TEXT_LINE, components=components, holes=holes,
            prefix=f"text-{path}",
        )
    else:
        # Font-free and conservative lanes initially own the exact same source
        # support.  Reuse the already encoded support/core-cell certificate,
        # while preserving distinct programs, scores and stable identities.
        bounded_score = float(np.clip(score, 0.0, 4.0))
        identity = hashlib.sha256(
            f"{base_candidate.id}\0{path}\0{line.id}".encode("utf-8")
        ).hexdigest()[:16]
        candidate = replace(
            base_candidate, id=f"text-{path}-{identity}",
            score_bounds=ScoreBounds(
                bounded_score * 0.72, bounded_score,
                bounded_score * 1.18 + 1e-6,
            ),
            provenance=provenance,
        )
    if candidate is None:
        return None
    effect_union = np.zeros((reir.height, reir.width), bool)
    for layer in effect_layers:
        layer.validate((reir.height, reir.width))
        effect_union |= layer.support_mask
    if effect_layers and not np.array_equal(effect_union, np.asarray(mask, bool)):
        return None
    physical_parameters = (
        ("baseline", line.baseline), ("x_height", line.x_height),
        ("cap_height", line.cap_height), ("overshoot", line.overshoot),
        ("slant", line.slant), ("tracking", line.tracking),
        ("shared_stem_width", float(np.median([
            glyph.stem_width for glyph in line.glyphs
        ]))),
    )
    existing_parameter_names = {name for name, _value in parameters}
    program_parameters = (
        *parameters,
        *(row for row in physical_parameters
          if row[0] not in existing_parameter_names),
    )
    deployable_continuous = (
        tuple(
            (name, float(value)) for name, value in program_parameters
            if name in {
                "tracking_em", "x_scale", "y_scale", "offset_x", "offset_y",
            } and isinstance(value, (float, int))
        )
        if path in {"exact-font", "semantic-font-idealization"}
        else tuple(
            row for row in physical_parameters
            if row[0] in {
                "baseline", "x_height", "cap_height", "overshoot", "slant",
                "tracking", "shared_stem_width",
            }
        )
    )
    candidate = replace(
        candidate,
        program=SceneProgram(f"TextLine/{path}", program_parameters),
        continuous_params=deployable_continuous,
        covariance=tuple(
            {
                "baseline": 0.25, "x_height": 0.5,
                "cap_height": 0.5, "overshoot": 0.25, "slant": 0.1,
                "tracking": 0.25, "shared_stem_width": 0.25,
                "tracking_em": 0.0025, "x_scale": 0.0025,
                "y_scale": 0.0025, "offset_x": 0.25,
                "offset_y": 0.25,
            }[name]
            for name, _value in deployable_continuous
        ),
        prerequisite_claims=(
            f"components={claims.required_components}",
            f"persistent-counters={claims.persistent_counters}",
            "no-unproven-fusion", "no-unproven-hole-fill",
            "no-glyph-outside-line-support",
        ),
    )
    return TextMacroRecord(
        candidate=candidate, line_id=line.id, path=path, claims=claims,
        dual_loop_glyphs=dual, prototypes=prototypes,
        effect_layers=effect_layers,
    )


def generate_text_macros(
    reir: RasterEvidenceIR, *, exact_font_provider: ExactFontProvider | None = None,
    max_line_proposals: int = 32, max_exact_per_line: int = 8,
    validate_reir: bool = True,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> TextMacroSet:
    if validate_reir:
        reir.validate()
    raw_hints = ()
    hint_provider = getattr(exact_font_provider, "line_hints", None)
    if callable(hint_provider):
        try:
            raw_hints = tuple(
                (str(row.text), tuple(row.bbox_xyxy), float(row.confidence))
                for row in hint_provider()
            )
        except Exception:
            raw_hints = ()
    proposals = propose_text_lines(
        reir, max_proposals=max_line_proposals, ocr_hints=raw_hints,
        validate_reir=False, proposal_queries=proposal_queries,
    )
    hint_refiner = getattr(exact_font_provider, "refine_line_hints", None)
    if callable(hint_refiner):
        try:
            refined_hints = tuple(
                (str(row.text), tuple(row.bbox_xyxy), float(row.confidence))
                for row in hint_refiner(proposals)
            )
        except Exception:
            refined_hints = raw_hints
        if refined_hints != raw_hints:
            raw_hints = refined_hints
            proposals = propose_text_lines(
                reir, max_proposals=max_line_proposals,
                ocr_hints=raw_hints, validate_reir=False,
                proposal_queries=proposal_queries,
            )
    exact_line_ids: set[str] | None = None
    font_search_enabled = bool(
        getattr(exact_font_provider, "font_search_enabled", True)
    )
    if callable(hint_provider):
        # Several threshold/polarity lanes can encode the same OCR query and
        # ROI.  Font retrieval is query-level work, not proposal-level work:
        # refine only the strongest physical line for each distinct query.
        # The remaining OCR supports still enter the cheap font-free court.
        exact_by_query: dict[tuple[str, tuple[int, int, int, int]], TextLineProposal] = {}
        for proposal in proposals:
            if "OCR" not in proposal.sources:
                continue
            text = next((
                source.split(":", 1)[1] for source in proposal.sources
                if source.startswith("ocr-text:")
            ), "")
            key = (text, proposal.roi_xyxy)
            previous = exact_by_query.get(key)
            if previous is None or (
                proposal.score, proposal.id
            ) > (previous.score, previous.id):
                exact_by_query[key] = proposal
        exact_line_ids = {row.id for row in exact_by_query.values()}
    records: list[TextMacroRecord] = []
    exact_attempted = exact_admitted = 0
    for line in proposals:
        effect_layers = classify_text_effect_layers(reir, line)
        # Cheap stage: support/topology columns enter CMIR together, while SDF
        # decoding and contour materialisation are delayed until the local
        # court selects a line.  Eagerly decoding every losing threshold/token
        # hypothesis was the Phase-4 p95 tail (hundreds of redundant glyphs).
        reconstructed = line.support_mask
        dual_rows: tuple[DualLoopGlyphProgram, ...] = ()
        # Prototype EM is part of the expensive geometry stage too.  The
        # losing line hypotheses carry a deferred claim; the winning line is
        # materialised by materialize_font_free_geometry below.
        prototypes: tuple[GlyphPrototype, ...] = ()
        font_free_claims = _claims(
            line, reconstructed, prototypes, readability=0.0,
            render_evidence=float(np.sum(reconstructed & line.support_mask)
                                  / max(1, np.sum(reconstructed | line.support_mask))),
        )
        font_free = _macro_record(
            reir, line, reconstructed, path="font-free-dual-loop",
            score=1.35 + line.score, claims=font_free_claims,
            dual=dual_rows, prototypes=prototypes,
            parameters=(("glyphs", len(line.glyphs)),
                        ("prototypes", len(prototypes)),
                        ("polarity", line.polarity),
                        ("geometry_state", "deferred-after-local-court"),
                        ("prototype_state", "deferred-after-local-court")),
            provenance=("phase4-font-free-SDF", "lazy-positive-negative-dual-loops",
                        "repeated-glyph-EM", *line.sources),
            effect_layers=(
                effect_layers
                if effect_layers
                and {layer.role for layer in effect_layers} == {"fill"}
                else ()
            ),
        )
        if font_free is not None:
            records.append(font_free)

        conservative_claims = font_free_claims
        conservative = _macro_record(
            reir, line, line.support_mask, path="conservative-outline",
            score=1.05 + line.score, claims=conservative_claims,
            dual=(), prototypes=prototypes,
            parameters=(("glyphs", len(line.glyphs)),
                        ("polarity", line.polarity),
                        ("geometry_state", "deferred-after-local-court")),
            provenance=("phase4-conservative-fitted-outline",
                        "lazy-positive-negative-loops", *line.sources),
            base_candidate=(font_free.candidate if font_free is not None else None),
            effect_layers=(
                effect_layers
                if effect_layers
                and {layer.role for layer in effect_layers} == {"fill"}
                else ()
            ),
        )
        if conservative is not None:
            records.append(conservative)

        if "multi-counter-outlined-word" in line.sources:
            outlined = _macro_record(
                reir, line, line.support_mask, path="outlined-text-group",
                score=1.48 + line.score, claims=font_free_claims,
                dual=(), prototypes=(),
                parameters=(("glyphs", len(line.glyphs)),
                            ("counters", font_free_claims.persistent_counters),
                            ("polarity", line.polarity),
                            ("geometry_state", "deferred-after-local-court")),
                provenance=("phase4-outlined-text-group",
                            "wide-connected-multi-counter-evidence",
                            *line.sources),
                base_candidate=(font_free.candidate if font_free is not None else None),
                effect_layers=effect_layers,
            )
            if outlined is not None:
                records.append(outlined)

        effect_roles = {layer.role for layer in effect_layers}
        if "shadow" in effect_roles:
            shadowed = _macro_record(
                reir, line, line.support_mask,
                path="outlined-shadowed-text-group",
                score=1.52 + line.score, claims=font_free_claims,
                dual=(), prototypes=(),
                parameters=(("glyphs", len(line.glyphs)),
                            ("effect_layers", len(effect_layers)),
                            ("polarity", line.polarity),
                            ("geometry_state", "source-partitioned-effects")),
                provenance=("phase4-outlined-shadowed-text-group",
                            "source-observed-ordered-effect-layers", *line.sources),
                base_candidate=(font_free.candidate if font_free is not None else None),
                effect_layers=effect_layers,
            )
            if shadowed is not None:
                records.append(shadowed)
        elif effect_roles == {"fill", "outline"}:
            colored_outline = _macro_record(
                reir, line, line.support_mask, path="outlined-text-group",
                score=1.50 + line.score, claims=font_free_claims,
                dual=(), prototypes=(),
                parameters=(("glyphs", len(line.glyphs)),
                            ("effect_layers", len(effect_layers)),
                            ("polarity", line.polarity),
                            ("geometry_state", "source-partitioned-effects")),
                provenance=("phase4-outlined-text-group",
                            "source-observed-outline-fill-relation", *line.sources),
                base_candidate=(font_free.candidate if font_free is not None else None),
                effect_layers=effect_layers,
            )
            if colored_outline is not None:
                records.append(colored_outline)
        elif effect_roles == {"knockout"}:
            knockout = _macro_record(
                reir, line, line.support_mask, path="knockout-text",
                score=1.50 + line.score, claims=font_free_claims,
                dual=(), prototypes=(),
                parameters=(("glyphs", len(line.glyphs)),
                            ("role", "negative-loop-cutout"),
                            ("polarity", line.polarity),
                            ("geometry_state", "source-proved-knockout")),
                provenance=("phase4-knockout-text",
                            "canvas-through-local-carrier-proof", *line.sources),
                base_candidate=(font_free.candidate if font_free is not None else None),
                effect_layers=effect_layers,
            )
            if knockout is not None:
                records.append(knockout)

        # A typed one-glyph query/threshold consensus is a different semantic
        # object from a TextLine: it may be a bespoke logomark or a custom
        # letter for which font retrieval is meaningless.  Keep the exact same
        # evidence and topology walls, but expose an explicit custom-glyph
        # program so it competes transactionally with the other hypotheses.
        if (
            (
                len(line.glyphs) == 1
                or "single-composite-custom-glyph-query" in line.sources
            )
            and bool({
                "single-custom-glyph-query",
                "single-custom-glyph-classical-consensus",
                "single-solid-glyph-classical-consensus",
            } & set(line.sources))
        ):
            custom = _macro_record(
                reir, line, line.support_mask, path="single-custom-glyph",
                score=1.45 + line.score, claims=font_free_claims,
                dual=(), prototypes=(),
                parameters=(("glyphs", 1),
                            ("observed_fragments", len(line.glyphs)),
                            ("polarity", line.polarity),
                            ("geometry_state", "deferred-after-local-court")),
                provenance=("phase4-single-custom-glyph",
                            "typed-single-glyph-evidence", *line.sources),
                base_candidate=(font_free.candidate if font_free is not None else None),
            )
            if custom is not None:
                records.append(custom)

        if exact_font_provider is None or not font_search_enabled:
            continue
        # A real OCR-backed provider has a recognized string and bbox only
        # for OCR-origin line proposals.  Running brute font retrieval on
        # unrelated threshold/token hypotheses repeats the same search many
        # times, cannot produce a defensible text program and dominated p95.
        # Generic injected providers without ``line_hints`` retain the old
        # fail-open contract used by tests and external integrations.
        if callable(hint_provider) and (
            "OCR" not in line.sources
            or exact_line_ids is not None and line.id not in exact_line_ids
        ):
            continue
        exact_attempted += 1
        try:
            exact_rows = tuple(exact_font_provider(reir, line))[:max_exact_per_line]
        except Exception:
            exact_rows = ()  # exact-font is deliberately fail-open
        exact_prototypes: tuple[GlyphPrototype, ...] | None = None
        for exact in exact_rows:
            mask = np.asarray(exact.support_mask, bool)
            if mask.shape != (reir.height, reir.width) or not np.any(mask):
                continue
            intersection = int(np.sum(mask & line.support_mask))
            union = int(np.sum(mask | line.support_mask))
            iou = intersection / max(1, union)
            strict_exact = not (
                exact.retrieval_score < 0.75
                or exact.silhouette_iou < 0.80 or iou < 0.80
                or exact.max_boundary_deviation_px > 2.5
                or _topology(mask) != _topology(line.support_mask)
            )
            recognized_glyphs = sum(
                character.isalnum() for character in exact.recognized_text
            )
            semantic_idealization = bool(
                not strict_exact and "OCR" in line.sources
                and recognized_glyphs >= 4 and line.score >= 0.94
                and exact.retrieval_score >= 0.58
                and exact.silhouette_iou >= 0.42 and iou >= 0.42
                and exact.max_boundary_deviation_px
                    <= max(4.0, 0.24 * (line.roi_xyxy[3] - line.roi_xyxy[1]))
            )
            # Approximate-template lane (v9.5 bridge): rows stamped by the
            # retrieval provider may enter through their own wall. The
            # borrowed semantic wall's line.score >= 0.94 gate admitted
            # 0/18 probe lines on real loci (scores live in 0.80-0.93,
            # 2026-07-24 attribution probe) while fit quality passed 13/18;
            # this route keeps the fit-quality walls STRICTER (0.50 vs
            # 0.42) and drops only the unreachable proposal-score gate to
            # a 0.80 floor. No font identity is claimed; the court still
            # judges the rendered result against the incumbent.
            approximate_template = bool(
                not strict_exact and not semantic_idealization
                and "approximate-template-retrieval" in exact.provenance
                and "OCR" in line.sources
                and recognized_glyphs >= 4 and line.score >= 0.80
                and exact.retrieval_score >= 0.58
                and exact.silhouette_iou >= 0.50 and iou >= 0.50
                and exact.max_boundary_deviation_px
                    <= max(4.0, 0.24 * (line.roi_xyxy[3] - line.roi_xyxy[1]))
            )
            if (
                not strict_exact and not semantic_idealization
                and not approximate_template
            ):
                continue
            if exact_prototypes is None:
                exact_prototypes = repeated_glyph_em(line.glyphs)
            claims = _claims(
                line, mask, exact_prototypes,
                readability=exact.retrieval_score, render_evidence=iou,
            )
            if semantic_idealization or approximate_template:
                components, holes = _topology(mask)
                claims = replace(
                    claims, required_components=components,
                    persistent_counters=holes,
                    no_unproven_fusion=True,
                    no_unproven_hole_fill=True,
                    no_glyph_outside_line_support=True,
                )
            record_path = (
                "exact-font" if strict_exact
                else "semantic-font-idealization" if semantic_idealization
                else "approximate-template"
            )
            record = _macro_record(
                reir, line, mask, path=record_path,
                score=(
                    1.7 if strict_exact
                    else 1.35 if semantic_idealization else 1.15
                ) + line.score + exact.retrieval_score,
                claims=claims, dual=(), prototypes=exact_prototypes,
                parameters=(("text", exact.recognized_text),
                            ("font_file", exact.font_file),
                            ("tracking_em", exact.tracking_em),
                            ("x_scale", exact.x_scale),
                            ("y_scale", exact.y_scale),
                            ("offset_x", exact.offset_xy[0]),
                            ("offset_y", exact.offset_xy[1])),
                provenance=(
                    "phase4-exact-font" if strict_exact
                    else "phase4-semantic-font-idealization"
                    if semantic_idealization
                    else "phase4-approximate-template",
                    "strict-silhouette-wall" if strict_exact
                    else "OCR-semantic-plus-bounded-silhouette-wall"
                    if semantic_idealization
                    else "style-retrieval-plus-strict-fit-wall",
                    "component-topology-gate" if strict_exact
                    else "font-outline-self-topology-certificate",
                    *exact.provenance,
                ),
            )
            if record is not None:
                records.append(record)
                exact_admitted += int(strict_exact)
    candidate_ids = [record.candidate.id for record in records]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("TextMacroSet contains duplicate candidate identities")
    return TextMacroSet(
        proposals=proposals, records=tuple(records),
        exact_font_attempted=exact_attempted,
        exact_font_admitted=exact_admitted,
        provenance=("REIR-direct-before-palette-commit", "phase4-text-macro-generator/v1"),
    )


def materialize_font_free_geometry(
    reir: RasterEvidenceIR, line: TextLineProposal,
    *, shared_stem_width: float | None = None,
) -> tuple[np.ndarray, tuple[DualLoopGlyphProgram, ...], tuple[GlyphPrototype, ...]]:
    """Decode the selected font-free line after the cheap local court.

    This is the expensive stage of the Phase-4 cascade.  It is intentionally a
    separate function so losing threshold/OCR hypotheses never pay per-glyph
    SDF and contour costs.
    """
    line.validate(reir)
    measured_stem = float(np.median([
        glyph.stem_width for glyph in line.glyphs
    ]))
    target_stem = (
        measured_stem if shared_stem_width is None else float(shared_stem_width)
    )
    if (
        not math.isfinite(target_stem)
        or not 0.25 <= target_stem <= max(0.5, 0.75 * line.x_height)
    ):
        raise ValueError("font-free shared stem width is outside physical bounds")
    reconstructed = np.zeros((reir.height, reir.width), bool)
    for glyph in line.glyphs:
        x1, y1, x2, y2 = glyph.bbox_xyxy
        rebuilt_local = topology_preserving_sdf_glyph(
            glyph.support_mask, target_stem
        )
        rebuilt = np.zeros((reir.height, reir.width), bool)
        rebuilt[y1:y2, x1:x2] = rebuilt_local
        reconstructed |= rebuilt
    frozen = _freeze_mask(reconstructed)
    if _topology(frozen) != _topology(line.support_mask):
        raise ValueError("selected font-free materialisation changed topology")
    intersection = int(np.sum(frozen & line.support_mask))
    union = int(np.sum(frozen | line.support_mask))
    support_iou = intersection / max(1, union)
    prototypes = repeated_glyph_em(line.glyphs)
    if (
        glyph_catastrophe_count(line.support_mask, frozen) > 0
        or support_iou < 0.82
    ):
        # Equal global component/hole counts do not prove that the same glyphs
        # survived.  Thin native glyphs can move by one pixel during SDF stem
        # normalization and cease to overlap their certified source component.
        # Ship the exact certified support in that case; the SVG G1 fitter may
        # still smooth it, but only under its own raster round-trip proof.
        frozen = _freeze_mask(line.support_mask)
        prototypes = ()
    elif prototypes:
        # Materialize the repeated-glyph program transactionally.  The former
        # implementation learned prototypes but never used them in delivered
        # geometry, so repeated letters remained unrelated pixel traces.
        glyph_by_id = {glyph.id: glyph for glyph in line.glyphs}
        idealized = np.asarray(frozen, bool).copy()
        applied: list[GlyphPrototype] = []
        for prototype in prototypes:
            trial = idealized.copy()
            admissible = True
            for member_id in prototype.member_ids:
                glyph = glyph_by_id.get(member_id)
                if glyph is None:
                    admissible = False
                    break
                x1, y1, x2, y2 = glyph.bbox_xyxy
                local = cv2.resize(
                    prototype.normalized_mask.astype(np.uint8),
                    (x2 - x1, y2 - y1), interpolation=cv2.INTER_AREA,
                ) >= 0.5
                source_local = frozen[y1:y2, x1:x2]
                intersection = int(np.sum(local & source_local))
                union = int(np.sum(local | source_local))
                if (
                    _topology(local) != _topology(source_local)
                    or intersection / max(1, union) < 0.72
                ):
                    admissible = False
                    break
                trial[y1:y2, x1:x2] = local
            if not admissible:
                continue
            intersection = int(np.sum(trial & line.support_mask))
            union = int(np.sum(trial | line.support_mask))
            if (
                glyph_catastrophe_count(line.support_mask, trial) == 0
                and intersection / max(1, union) >= 0.82
            ):
                idealized = trial
                applied.append(prototype)
        frozen = _freeze_mask(idealized)
        prototypes = tuple(applied)
    dual_rows = tuple(_dual_loops(glyph, frozen) for glyph in line.glyphs)
    return frozen, dual_rows, prototypes


def glyph_catastrophe_count(
    reference: np.ndarray, candidate: np.ndarray
) -> int:
    """Count affected glyph-components, not an unbounded topology delta.

    A single inverted canvas can contain hundreds of tiny holes, but it is one
    catastrophic component-level decision rather than hundreds of glyphs.
    Match connected components by actual pixel overlap, charge each reference
    component once for missing/split/fused/counter-damaged delivery, and charge
    every unsupported candidate component once.  Pixel fidelity remains a
    separate IoU/render metric.
    """
    truth = np.asarray(reference, bool)
    rendered = np.asarray(candidate, bool)
    if truth.shape != rendered.shape:
        raise ValueError("glyph catastrophe masks must share one lattice")
    reference_count, reference_labels = cv2.connectedComponents(
        truth.astype(np.uint8), 8,
    )
    candidate_count, candidate_labels = cv2.connectedComponents(
        rendered.astype(np.uint8), 8,
    )
    reference_total = reference_count - 1
    candidate_total = candidate_count - 1
    if reference_total <= 0:
        return int(candidate_total)
    if candidate_total <= 0:
        return int(reference_total)

    joint = np.bincount(
        (
            reference_labels.astype(np.int64) * candidate_count
            + candidate_labels.astype(np.int64)
        ).ravel(),
        minlength=reference_count * candidate_count,
    ).reshape((reference_count, candidate_count))
    damaged: set[int] = set()
    reference_to_candidate: dict[int, tuple[int, ...]] = {}
    candidate_to_reference: dict[int, tuple[int, ...]] = {}
    for reference_id in range(1, reference_count):
        matches = tuple(
            int(value) for value in np.flatnonzero(joint[reference_id, 1:] > 0) + 1
        )
        reference_to_candidate[reference_id] = matches
        if len(matches) != 1:
            damaged.add(reference_id)
    for candidate_id in range(1, candidate_count):
        matches = tuple(
            int(value) for value in np.flatnonzero(joint[1:, candidate_id] > 0) + 1
        )
        candidate_to_reference[candidate_id] = matches
        if len(matches) > 1:
            damaged.update(matches)

    # Counter changes are charged once to the affected source component.  A
    # 737-hole inverse canvas can therefore never outweigh 737 real glyphs.
    for reference_id, matches in reference_to_candidate.items():
        if len(matches) != 1 or reference_id in damaged:
            continue
        candidate_id = matches[0]
        if len(candidate_to_reference[candidate_id]) != 1:
            continue
        reference_holes = _topology(reference_labels == reference_id)[1]
        candidate_holes = _topology(candidate_labels == candidate_id)[1]
        if reference_holes != candidate_holes:
            damaged.add(reference_id)

    unsupported = sum(
        not candidate_to_reference[candidate_id]
        for candidate_id in range(1, candidate_count)
    )
    return int(len(damaged) + unsupported)


def _text_render_evidence_target(
    reir: RasterEvidenceIR, scope: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Infer local ink from canonical pixels under one robust background.

    This is evidence, not a target label: the common scope is formed solely
    from competing hypotheses, and no review ROI/support enters the court.
    """
    if not np.any(scope):
        return np.zeros(scope.shape, bool), 0.0
    x1, y1, x2, y2 = _bbox(scope, pad=2)
    local_scope = np.asarray(scope[y1:y2, x1:x2], bool)
    lab = np.asarray(reir.raster.oklab[y1:y2, x1:x2], np.float32)
    alpha = np.asarray(
        reir.raster.straight_rgba[y1:y2, x1:x2, 3], np.float32
    )
    kernel = np.ones((5, 5), np.uint8)
    outer = cv2.dilate(local_scope.astype(np.uint8), kernel) > 0
    ring = outer & ~local_scope
    if np.sum(ring) < 8:
        border = np.zeros(local_scope.shape, bool)
        border[:2] = True; border[-2:] = True
        border[:, :2] = True; border[:, -2:] = True
        ring = border & ~local_scope
    background_samples = lab[ring] if np.any(ring) else lab[~local_scope]
    if not len(background_samples):
        background_samples = lab.reshape((-1, 3))
    background = np.median(background_samples, axis=0)
    ring_distance = np.linalg.norm(background_samples - background, axis=1)
    median = float(np.median(ring_distance))
    noise = 1.4826 * float(np.median(np.abs(ring_distance - median)))
    threshold = max(0.025, median + 3.0 * noise)
    distance = np.linalg.norm(lab - background, axis=2)
    background_alpha = float(np.median(alpha[ring])) if np.any(ring) else 1.0
    alpha_evidence = np.abs(alpha - background_alpha) >= 0.10
    target = outer & ((distance >= threshold) | alpha_evidence)
    # Remove isolated one-pixel codec flecks, but never close/fill genuine
    # counters.  This is a component-area filter only.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        target.astype(np.uint8), 8,
    )
    cleaned = np.zeros(target.shape, bool)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= 2:
            cleaned |= labels == label
    contrast = float(np.percentile(distance[local_scope], 75))
    full = np.zeros(scope.shape, bool)
    full[y1:y2, x1:x2] = cleaned
    return full, contrast


def _text_evidence_score(
    reir: RasterEvidenceIR, mask: np.ndarray, target: np.ndarray,
    common_scope: np.ndarray, *, line_score: float, exact_font: bool,
) -> float:
    if not np.any(common_scope):
        return -1.0
    x1, y1, x2, y2 = _bbox(common_scope, pad=1)
    local_common = common_scope[y1:y2, x1:x2]
    mask = np.asarray(mask[y1:y2, x1:x2], bool) & local_common
    if not np.any(mask):
        return -1.0
    local_target = np.asarray(target[y1:y2, x1:x2], bool) & local_common
    intersection = int(np.sum(mask & local_target))
    union = int(np.sum(mask | local_target))
    ink_iou = intersection / max(1, union)
    precision = intersection / max(1, int(np.sum(mask)))
    recall = intersection / max(1, int(np.sum(local_target)))
    kernel = np.ones((3, 3), np.uint8)
    boundary = cv2.morphologyEx(
        mask.astype(np.uint8), cv2.MORPH_GRADIENT, kernel,
    ) > 0
    boundary_probability = reir.boundary_pyramid[0].probability[y1:y2, x1:x2]
    boundary_alignment = (
        float(np.mean(boundary_probability[boundary]))
        if np.any(boundary) else 0.0
    )
    components, _holes = _topology(mask)
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), 8,
    )
    tiny = sum(
        int(stats[label, cv2.CC_STAT_AREA]) < 2
        for label in range(1, count)
    )
    speck_penalty = tiny / max(1, components)
    return float(
        0.34 * ink_iou + 0.19 * precision + 0.19 * recall
        + 0.18 * boundary_alignment + 0.10 * float(np.clip(line_score, 0, 1))
        + (0.015 if exact_font else 0.0) - 0.08 * speck_penalty
    )


def _refine_single_preserved_mark(
    reir: RasterEvidenceIR, preserved: np.ndarray,
) -> tuple[np.ndarray, bool]:
    """Replace one codec-fragmented side mark from threshold consensus.

    Compound lockups often contain one non-text icon beside an OCR word.  The
    word court must preserve that owner, but byte-for-byte preservation also
    kept dozens of contour pinholes from a weak legacy threshold.  This helper
    is an independent mark court: two distinct REIR threshold families must
    agree on a nested one-component support and the candidate must improve the
    native physical render before it may replace the preserved mark.
    """
    fallback = np.asarray(preserved, bool)
    fallback_topology = _topology(fallback)
    fallback_area = int(np.sum(fallback))
    if (
        fallback_area < 12 or fallback_topology[0] != 1
        or fallback_topology[1] < 8
    ):
        return _freeze_mask(fallback), False
    fx1, fy1, fx2, fy2 = _bbox(fallback, pad=0)
    region = np.zeros_like(fallback)
    pad = 2
    region[
        max(0, fy1 - pad):min(reir.height, fy2 + pad),
        max(0, fx1 - pad):min(reir.width, fx2 + pad),
    ] = True
    fallback_width = max(1, fx2 - fx1)
    fallback_height = max(1, fy2 - fy1)
    rows: list[tuple[
        float, int, float, str, str, np.ndarray,
    ]] = []
    for token in reir.proposal_tokens:
        if token.family not in {"component", "topology", "shape"}:
            continue
        if token.score < 0.78:
            continue
        decoded = decode_token_mask(token, fallback.shape)
        if decoded is None:
            continue
        candidate = np.asarray(decoded, bool) & region
        if not np.any(candidate):
            continue
        topology = _topology(candidate)
        if (
            topology[0] != 1 or topology[1] < 1
            or topology[1] > fallback_topology[1] - 2
        ):
            continue
        candidate_area = int(np.sum(candidate))
        area_ratio = candidate_area / max(1, fallback_area)
        if not 0.80 <= area_ratio <= 2.40:
            continue
        cx1, cy1, cx2, cy2 = _bbox(candidate, pad=0)
        x_recall = max(0, min(cx2, fx2) - max(cx1, fx1)) / fallback_width
        y_recall = max(0, min(cy2, fy2) - max(cy1, fy1)) / fallback_height
        nested_recall = int(np.sum(candidate & fallback)) / fallback_area
        if x_recall < 0.90 or y_recall < 0.90 or nested_recall < 0.90:
            continue
        common = cv2.dilate(
            (candidate | fallback).astype(np.uint8),
            np.ones((3, 3), np.uint8),
        ) > 0
        target, contrast = _text_render_evidence_target(reir, common)
        if contrast < 0.04:
            continue
        fallback_score = _text_evidence_score(
            reir, fallback, target, common,
            line_score=0.5, exact_font=False,
        )
        candidate_score = _text_evidence_score(
            reir, candidate, target, common,
            line_score=0.5, exact_font=False,
        )
        gain = candidate_score - fallback_score
        if gain < 0.08:
            continue
        frozen = _freeze_mask(candidate)
        rows.append((
            float(gain), int(topology[1]), float(token.score),
            str(token.family), str(token.provenance), frozen,
        ))
    proved: list[tuple[float, int, float, str, str, np.ndarray]] = []
    for index, row in enumerate(rows):
        candidate = row[5]
        for other_index, other in enumerate(rows):
            if index == other_index:
                continue
            if row[3] == other[3] and row[4] == other[4]:
                continue
            if abs(row[1] - other[1]) > 1:
                continue
            intersection = int(np.sum(candidate & other[5]))
            union = int(np.sum(candidate | other[5]))
            if intersection / max(1, union) >= 0.90:
                proved.append(row)
                break
    if not proved:
        return _freeze_mask(fallback), False
    # Native evidence is primary; within numerical ties keep the simpler
    # counter topology and stronger independent token.
    winner = max(
        proved,
        key=lambda row: (
            round(row[0], 6), -row[1], row[2], row[3], row[4],
            mask_sha256(row[5]),
        ),
    )
    return winner[5], True


def _ocr_edge_counter_extension_proved(
    recognized_text: str, physical_line: TextLineProposal,
    physical_support: np.ndarray,
    siblings: Iterable[TextLineProposal],
) -> bool:
    """Prove one source-observed counter glyph omitted at an OCR box edge."""
    contract = _ocr_semantic_topology_contract(recognized_text)
    if (
        contract is None
        or "persistent-physical-midline-topology"
            not in physical_line.sources
        or physical_line.score < 0.95
    ):
        return False
    expected = (len(contract[0]), int(sum(contract[1])))
    if _topology(physical_support) != (expected[0] + 1, expected[1] + 1):
        return False
    physical_box = _bbox(physical_support, pad=0)
    for sibling in siblings:
        if (
            sibling.id == physical_line.id
            or "OCR-semantic-digital-preimage-topology"
                not in sibling.sources
        ):
            continue
        sibling_text = next((
            source.split(":", 1)[1] for source in sibling.sources
            if source.startswith("ocr-text:")
        ), "")
        sibling_box = _bbox(sibling.support_mask, pad=0)
        edge_extension = max(
            sibling_box[0] - physical_box[0],
            physical_box[2] - sibling_box[2],
        )
        if (
            sibling_text == recognized_text
            and _topology(sibling.support_mask) == expected
            and edge_extension >= 2
        ):
            return True
    return False


def _enclosing_physical_midline_proved(
    fallback: np.ndarray, candidate: np.ndarray,
    line: TextLineProposal | None, *, candidate_score: float,
    fallback_score: float, candidate_topology_error: int,
    fallback_topology_error: int,
) -> bool:
    """Prove a bounded, source-observed antialias expansion of one line.

    A persistent native threshold can enclose the incumbent while merging
    JPEG-fragmented strokes and exposing counters.  Treat that independently
    measured support as evidence only when it is a near-complete, full-span
    superset with a large native-render margin and a strictly smaller distance
    to the persistent topology interval.  The tight area/topology bounds keep
    this from becoming a generic permission to grow a text mask.
    """
    if line is None or "persistent-physical-midline-topology" not in line.sources:
        return False
    fallback = np.asarray(fallback, bool)
    candidate = np.asarray(candidate, bool)
    fallback_area = int(np.sum(fallback))
    candidate_area = int(np.sum(candidate))
    if fallback_area <= 0 or candidate_area <= 0 or line.score < 0.75:
        return False
    candidate_components, candidate_holes = _topology(candidate)
    fallback_components, fallback_holes = _topology(fallback)
    fallback_recall = int(np.sum(candidate & fallback)) / fallback_area
    area_ratio = candidate_area / fallback_area
    fallback_box = _bbox(fallback, pad=0)
    candidate_box = _bbox(candidate, pad=0)
    fallback_span = max(1, fallback_box[2] - fallback_box[0])
    horizontal_span_recall = max(
        0,
        min(candidate_box[2], fallback_box[2])
        - max(candidate_box[0], fallback_box[0]),
    ) / fallback_span
    return bool(
        candidate_score >= fallback_score + 0.10
        and candidate_topology_error < fallback_topology_error
        and fallback_recall >= 0.98
        and horizontal_span_recall >= 0.95
        and 1.05 <= area_ratio <= 1.35
        and candidate_components <= fallback_components
        and candidate_holes <= fallback_holes + 3
    )


def _chromatic_completion_pair_proved(
    fallback: np.ndarray, candidate: np.ndarray, witness: np.ndarray,
    candidate_line: TextLineProposal | None,
    witness_line: TextLineProposal | None, *, candidate_score: float,
    fallback_score: float,
) -> bool:
    """Prove missing coloured ink with two nested native thresholds.

    Dark-only incumbents can omit a lighter logo colour or suffix entirely.
    One permissive threshold is not enough to grow ownership, so the admitted
    support must be the smaller core of two independent multithreshold lines
    with matching component topology.  The outer observation is used only as
    a witness and is never exported.
    """
    required = {"both-polarities", "multithreshold-native-ink"}
    if (
        candidate_line is None or witness_line is None
        or not required.issubset(candidate_line.sources)
        or not required.issubset(witness_line.sources)
        or candidate_line.id == witness_line.id
        or candidate_line.score < 0.82 or witness_line.score < 0.82
    ):
        return False
    candidate = np.asarray(candidate, bool)
    witness = np.asarray(witness, bool)
    fallback = np.asarray(fallback, bool)
    candidate_area = int(np.sum(candidate))
    witness_area = int(np.sum(witness))
    fallback_area = int(np.sum(fallback))
    if min(candidate_area, witness_area, fallback_area) <= 0:
        return False
    # Candidate is the conservative nested core; the larger support is only
    # corroboration that the same coloured structures persist at a second
    # source-observed threshold.
    nested_precision = int(np.sum(candidate & witness)) / candidate_area
    pair_iou = int(np.sum(candidate & witness)) / max(
        1, int(np.sum(candidate | witness)),
    )
    fallback_recall = int(np.sum(candidate & fallback)) / fallback_area
    area_ratio = candidate_area / fallback_area
    candidate_topology = _topology(candidate)
    witness_topology = _topology(witness)
    fallback_topology = _topology(fallback)
    candidate_box = _bbox(candidate, pad=0)
    fallback_box = _bbox(fallback, pad=0)
    fallback_span = max(1, fallback_box[2] - fallback_box[0])
    horizontal_span_recall = max(
        0,
        min(candidate_box[2], fallback_box[2])
        - max(candidate_box[0], fallback_box[0]),
    ) / fallback_span
    candidate_density = candidate_area / max(
        1,
        (candidate_box[2] - candidate_box[0])
        * (candidate_box[3] - candidate_box[1]),
    )
    return bool(
        candidate_area < witness_area
        and nested_precision >= 0.995 and pair_iou >= 0.84
        and candidate_topology[0] == witness_topology[0]
        and abs(candidate_topology[1] - witness_topology[1]) <= 1
        and candidate_score >= fallback_score + 0.15
        and fallback_recall >= 0.98
        and horizontal_span_recall >= 0.95
        and 1.25 <= area_ratio <= 1.75
        and candidate_density <= 0.55
        and fallback_topology[0] <= candidate_topology[0]
            <= fallback_topology[0] + 4
        and fallback_topology[1] <= candidate_topology[1]
            <= fallback_topology[1] + 2
    )


def _semantic_ocr_complete_line_proved(
    *, recognized_glyphs: int,
    incumbent_topology: tuple[int, int],
    candidate_topology: tuple[int, int],
    line_score: float, local_contrast: float,
    local_line_score: float, local_fallback_score: float,
    candidate_score: float, fallback_score: float,
    overlap: float, horizontal_span_recall: float, area_ratio: float,
) -> bool:
    """Prove a complete OCR line over a fragmented codec incumbent.

    This is deliberately stronger than a score-threshold relaxation.  The
    incumbent must be structurally impossible for the recognized glyph count,
    while the replacement must be a full-span/high-overlap physical line with
    plausible topology and independent local plus global render margins.
    """
    glyphs = max(0, int(recognized_glyphs))
    incumbent_implausible = bool(
        glyphs >= 4 and (
            incumbent_topology[0] > 2 * glyphs + 2
            or incumbent_topology[1] > 2 * glyphs + 2
        )
    )
    candidate_plausible = bool(
        1 <= candidate_topology[0] <= glyphs + 2
        and candidate_topology[1] <= 2 * glyphs + 2
    )
    return bool(
        incumbent_implausible and candidate_plausible
        and line_score >= 0.88 and local_contrast >= 0.08
        and local_line_score >= local_fallback_score + 0.08
        and candidate_score >= fallback_score + 0.12
        and overlap >= 0.90 and horizontal_span_recall >= 0.95
        and 0.65 <= area_ratio <= 2.25
    )


def _ocr_ownership_topology_compatible(
    *, edge_counter_extension: bool, local_fallback_empty: bool,
    stable_local_incumbent: bool,
    fallback_topology: tuple[int, int],
    persistent_topology: tuple[int, int],
    ownership_topology: tuple[int, int],
    local_fallback_topology: tuple[int, int],
) -> bool:
    """Protect an already stable physical owner from OCR topology drift."""
    return bool(
        edge_counter_extension or local_fallback_empty
        or (
            not stable_local_incumbent
            and fallback_topology != persistent_topology
        )
        or ownership_topology == local_fallback_topology
    )


def select_text_line_with_court(
    reir: RasterEvidenceIR, generated: TextMacroSet, *,
    legacy_support: np.ndarray | None = None,
    replacement_margin: float = 0.060, validate_reir: bool = True,
    allow_complete_line_recovery: bool = True,
) -> TextLineCourtDecision:
    """Choose one line hypothesis, or keep the supplied legacy line.

    The decision is a cheap-to-expensive local replacement hook for Phase 4:
    hard TextLine claims prune first, duplicate supports collapse, then a
    common-scope native render-evidence court is evaluated.  A new line may
    replace legacy only when it overlaps it and wins by a positive margin;
    missing/weak evidence therefore fails open instead of adding stray lines.
    """
    if validate_reir:
        reir.validate()
    shape = (reir.height, reir.width)
    fallback = (
        np.asarray(legacy_support, bool)
        if legacy_support is not None else np.zeros(shape, bool)
    )
    if fallback.shape != shape:
        fallback = cv2.resize(
            fallback.astype(np.uint8), (reir.width, reir.height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0

    line_by_id = {proposal.id: proposal for proposal in generated.proposals}
    # The lazy font-free and conservative programs intentionally share one
    # immutable support certificate until the winner is materialised.  Pick
    # the stronger program before decoding that certificate; exact-font rows
    # retain their own independently certified support.
    certificate_rows: dict[int, TextMacroRecord] = {}
    for record in generated.records:
        if not record.claims.hard_valid:
            continue
        key = id(record.candidate.certificates)
        previous = certificate_rows.get(key)
        if previous is None:
            certificate_rows[key] = record
            continue
        record_key = (
            record.path == "exact-font", record.candidate.score_bounds.lower,
        )
        previous_key = (
            previous.path == "exact-font", previous.candidate.score_bounds.lower,
        )
        if record_key > previous_key:
            certificate_rows[key] = record
    unique: dict[str, tuple[TextMacroRecord, np.ndarray]] = {}
    for record in certificate_rows.values():
        mask = _candidate_support(record.candidate, shape)
        if not np.any(mask):
            continue
        digest = mask_sha256(mask)
        previous = unique.get(digest)
        if previous is None:
            unique[digest] = (record, mask)
            continue
        # Exact-font wins only after the same hard silhouette wall has admitted
        # it; otherwise keep the higher source-only CMIR lower bound.
        previous_record = previous[0]
        key = (record.path == "exact-font", record.candidate.score_bounds.lower)
        previous_key = (
            previous_record.path == "exact-font",
            previous_record.candidate.score_bounds.lower,
        )
        if key > previous_key:
            unique[digest] = (record, mask)

    # OCR may prove a word inside a broader legacy object (for example a logo
    # mark followed by a word).  Evaluate that as a local ownership rewrite:
    # preserve fallback outside the certified line ROI byte-for-byte, remove
    # only its pixels inside the ROI, then insert the physical OCR support.
    # This is not a permissive partial-overlap heuristic; only an independent
    # OCR line with physical midline support can form such a composite.
    preserved_by_id: dict[str, np.ndarray] = {}
    ownership_scope_by_id: dict[str, np.ndarray] = {}
    ownership_line_by_id: dict[str, np.ndarray] = {}
    preserved_mark_refined_ids: set[str] = set()
    for digest, (record, mask) in tuple(unique.items()):
        line = line_by_id.get(record.line_id)
        if (
            not np.any(fallback) or line is None or line.score < 0.74
            or "OCR" not in line.sources
            or not ({
                "persistent-physical-midline-topology",
                "OCR-bounded-physical-subset-with-connectivity-uncertainty",
            } & set(line.sources))
        ):
            continue
        x1, y1, x2, y2 = line.roi_xyxy
        candidate_box = _bbox(mask, pad=0)
        ink_height = max(1, candidate_box[3] - candidate_box[1])
        # Ownership follows the measured ink band, not the proposal's padded
        # fit ROI.  At h24 the former 25%-of-ROI padding reached the next text
        # row and erased the top pixels of STUDIOS while replacing STORMCRAFT.
        # One 10%-of-ink antialias band clears the incumbent glyph boundary
        # without crossing a one-pixel inter-line gap.
        vertical_pad = max(1, int(math.ceil(0.10 * ink_height)))
        scope = np.zeros(shape, bool)
        scope[
            max(0, candidate_box[1] - vertical_pad):min(
                reir.height, candidate_box[3] + vertical_pad,
            ),
            max(0, x1):min(reir.width, x2),
        ] = True
        preserved = fallback & ~scope
        if int(np.sum(preserved)) < max(3, int(0.03 * np.sum(fallback))):
            continue
        preserved, mark_refined = _refine_single_preserved_mark(
            reir, preserved,
        )
        roi_width = max(1, x2 - x1); roi_height = max(1, y2 - y1)
        candidate_span = (candidate_box[2] - candidate_box[0]) / roi_width
        candidate_height = (candidate_box[3] - candidate_box[1]) / roi_height
        if (
            candidate_span < 0.82 or candidate_height < 0.50
            or np.any(mask & ~scope)
        ):
            continue
        composite = _freeze_mask(preserved | mask)
        unique[digest] = (record, composite)
        preserved_by_id[record.candidate.id] = _freeze_mask(preserved)
        if mark_refined:
            preserved_mark_refined_ids.add(record.candidate.id)
        ownership_scope_by_id[record.candidate.id] = _freeze_mask(scope)
        ownership_line_by_id[record.candidate.id] = _freeze_mask(mask)

    masks = [mask for _record, mask in unique.values()]
    common = fallback.copy()
    for mask in masks:
        common |= mask
    if not np.any(common):
        frozen = _freeze_mask(fallback)
        decision = TextLineCourtDecision(
            None, "legacy", frozen, True, -1.0, -1.0, 0,
            "no-admissible-text-hypothesis", (),
        )
        decision.validate(reir)
        return decision
    common = cv2.dilate(common.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    target, contrast = _text_render_evidence_target(reir, common)

    fallback_score = _text_evidence_score(
        reir, fallback, target, common, line_score=0.5, exact_font=False,
    )
    persistent_fallback = _persistent_text_support(fallback)
    persistent_reference_proved = False
    if (
        (fallback_area := int(np.sum(fallback)))
        and _topology(fallback)[1] == 0
    ):
        fallback_box = _bbox(fallback, pad=0)
        fallback_width = max(1, fallback_box[2] - fallback_box[0])

        def complete_nested_support(mask: np.ndarray) -> bool:
            area = int(np.sum(mask))
            if area <= 0 or not 0.45 <= area / fallback_area <= 1.05:
                return False
            box = _bbox(mask, pad=0)
            span = max(
                0, min(box[2], fallback_box[2])
                - max(box[0], fallback_box[0]),
            ) / fallback_width
            nested = int(np.sum(mask & fallback)) / max(1, area)
            return bool(span >= 0.82 and nested >= 0.90)

        # A counter-free native microtext line can contain legitimate
        # one-pixel stems, so
        # component-area filtering alone is not a persistence oracle.  Among
        # complete, nested adaptive-foreground observations retain the
        # strongest-coverage (smallest admissible) support.  This is the
        # source-only physical midline analogue for subpixel words: it removes
        # soft disconnected AA flecks without accepting a partial word crop.
        # Once counters are present, threshold shrinkage can change the actual
        # letter structure; those lines remain on the ordinary persistent-
        # topology/outlined path instead of using this microtext refinement.
        persistence_rows: list[tuple[np.ndarray, bool]] = [(fallback, False)]
        if complete_nested_support(persistent_fallback):
            persistence_rows.append((persistent_fallback, True))
        for token in reir.proposal_tokens:
            if (
                token.family != "text" or token.score < 0.70
                or not token.provenance.startswith("adaptive-foreground-")
            ):
                continue
            support = decode_token_mask(token, shape)
            if support is not None and complete_nested_support(support):
                persistence_rows.append((np.asarray(support, bool), True))
        persistent_fallback, persistent_reference_proved = min(
            persistence_rows,
            key=lambda row: (int(np.sum(row[0])), mask_sha256(row[0])),
        )
        persistent_fallback = _freeze_mask(persistent_fallback)
    persistent_topology = _topology(persistent_fallback)
    fallback_topology = _topology(fallback)
    fallback_topology_error = (
        abs(fallback_topology[0] - persistent_topology[0])
        + abs(fallback_topology[1] - persistent_topology[1])
    )
    ranking: list[tuple[str, str, float]] = []
    evaluated: list[tuple[int, float, TextMacroRecord, np.ndarray]] = []
    alternatives: list[tuple[
        float, TextMacroRecord, np.ndarray, tuple[int, int],
        float, float, TextLineProposal | None, float,
    ]] = []
    fallback_area = int(np.sum(fallback))
    fallback_bbox = _bbox(fallback, pad=0) if fallback_area else (0, 0, 0, 0)
    fallback_span = max(1, fallback_bbox[2] - fallback_bbox[0])
    fallback_density = (
        fallback_area / max(
            1, (fallback_bbox[2] - fallback_bbox[0])
            * (fallback_bbox[3] - fallback_bbox[1]),
        )
        if fallback_area else 0.0
    )
    inverse_polarity_ids: set[str] = set()
    knockout_carrier_ids: set[str] = set()
    single_glyph_inverse_ids: set[str] = set()
    single_glyph_consensus_ids: set[str] = set()
    single_composite_glyph_ids: set[str] = set()
    persistent_subset_ids: set[str] = set()
    ocr_partial_ids: set[str] = set()
    ocr_complete_line_ids: set[str] = set()
    ocr_edge_counter_ids: set[str] = set()
    canvas_carrier_ids: set[str] = set()
    solid_canvas_carrier_ids: set[str] = set()
    fallback_negative_loops = (
        enclosed_negative_loops(fallback)
        if fallback_area and fallback_density >= 0.68 and fallback_topology[1] >= 2
        else _freeze_mask(np.zeros_like(fallback))
    )
    token_by_id = {str(token.id): token for token in reir.proposal_tokens}
    for record, mask in unique.values():
        line = line_by_id.get(record.line_id)
        line_score = line.score if line is not None else 0.0
        score = _text_evidence_score(
            reir, mask, target, common, line_score=line_score,
            exact_font=record.path in {
                "exact-font", "semantic-font-idealization",
            },
        )
        ranking.append((record.candidate.id, record.path, score))
        candidate_topology = _topology(mask)
        topology_error = (
            abs(candidate_topology[0] - persistent_topology[0])
            + abs(candidate_topology[1] - persistent_topology[1])
        )
        mask_area = int(np.sum(mask))
        overlap = 0.0
        area_ratio = mask_area / max(1, fallback_area)
        if fallback_area:
            overlap = int(np.sum(mask & fallback)) / max(
                1, min(int(np.sum(mask)), fallback_area)
            )
        candidate_bbox = _bbox(mask, pad=0)
        candidate_density = mask_area / max(
            1, (candidate_bbox[2] - candidate_bbox[0])
            * (candidate_bbox[3] - candidate_bbox[1]),
        )
        horizontal_span_recall = (
            max(0, min(candidate_bbox[2], fallback_bbox[2])
                - max(candidate_bbox[0], fallback_bbox[0]))
            / fallback_span
            if fallback_area else 1.0
        )
        negative_loop_iou = 0.0
        if np.any(fallback_negative_loops):
            negative_loop_iou = int(np.sum(mask & fallback_negative_loops)) / max(
                1, int(np.sum(mask | fallback_negative_loops)),
            )
        carrier_proof_iou = 0.0
        if line is not None and "knockout-negative-loops" in line.sources:
            carrier_id = next((
                value.split(":", 1)[1] for value in line.sources
                if value.startswith("carrier-token:")
            ), None)
            carrier_token = token_by_id.get(carrier_id or "")
            carrier = (
                decode_token_mask(carrier_token, shape)
                if carrier_token is not None else None
            )
            if carrier is not None and np.any(carrier):
                carrier_negative = enclosed_negative_loops(carrier)
                carrier_proof_iou = int(np.sum(mask & carrier_negative)) / max(
                    1, int(np.sum(mask | carrier_negative)),
                )
        knockout_carrier_recovery = bool(
            line is not None
            and "knockout-negative-loops" in line.sources
            and line.score >= 0.70
            and max(negative_loop_iou, carrier_proof_iou) >= 0.92
            and (
                carrier_proof_iou >= 0.92 or horizontal_span_recall >= 0.82
            )
        )
        inverse_support = ~fallback
        inverse_precision = int(np.sum(mask & inverse_support)) / max(
            1, mask_area,
        )
        inverse_recall = int(np.sum(mask & inverse_support)) / max(
            1, int(np.sum(inverse_support)),
        )
        single_glyph_inverse_recovery = bool(
            line is not None
            and "single-custom-glyph-classical-consensus" in line.sources
            and line.score >= 0.85
            and candidate_topology[0] == 1
            and (
                candidate_topology[1] >= 1
                or "single-solid-glyph-classical-consensus" in line.sources
            )
            and inverse_precision >= 0.98
            and inverse_recall >= 0.90
            and score >= fallback_score + 0.12
        )
        single_glyph_consensus_recovery = bool(
            fallback_area
            and line is not None
            and "single-custom-glyph-classical-consensus" in line.sources
            and "token-polarity-reconciled-to-consensus-topology"
                not in line.sources
            and line.score >= 0.88
            and candidate_topology[0] == 1
            and candidate_topology[1] <= fallback_topology[1] + 1
            and 0.80 <= area_ratio <= 1.10
            and overlap >= 0.95
            and horizontal_span_recall >= 0.82
            and score >= fallback_score + 0.04
        )
        candidate_only = mask & ~cv2.dilate(
            fallback.astype(np.uint8), np.ones((3, 3), np.uint8),
        ).astype(bool)
        fallback_only = fallback & ~cv2.dilate(
            mask.astype(np.uint8), np.ones((3, 3), np.uint8),
        ).astype(bool)
        single_composite_glyph_recovery = bool(
            fallback_area
            and line is not None
            and record.path == "single-custom-glyph"
            and "single-composite-custom-glyph-query" in line.sources
            and line.score >= 0.75
            and 2 <= candidate_topology[0] <= 4
            and 0.90 <= area_ratio <= 1.05
            and overlap >= 0.95
            and int(np.sum(candidate_only)) <= max(2, int(0.02 * mask_area))
            and int(np.sum(fallback_only)) <= max(4, int(0.06 * fallback_area))
            and score >= fallback_score + 0.05
        )
        coherent_inverse_line_recovery = bool(
            fallback_area
            and line is not None
            and "multithreshold-native-ink" in line.sources
            and "both-polarities" in line.sources
            and line.score >= 0.84
            and overlap < 0.15
            and horizontal_span_recall >= 0.90
            and 0.35 <= area_ratio <= 0.80
            and candidate_density <= 0.50
            and candidate_topology[0] <= max(
                2, int(math.ceil(0.25 * fallback_topology[0])),
            )
            and score >= fallback_score + 0.25
        )
        recognized_text = (
            next((
                source.split(":", 1)[1] for source in line.sources
                if source.startswith("ocr-text:")
            ), "")
            if line is not None else ""
        )
        recognized_glyphs = sum(
            character.isalnum() for character in recognized_text
        )
        ocr_complete_line_recovery = bool(
            allow_complete_line_recovery
            and fallback_area and line is not None and "OCR" in line.sources
            and _semantic_ocr_complete_line_proved(
                recognized_glyphs=recognized_glyphs,
                incumbent_topology=fallback_topology,
                candidate_topology=candidate_topology,
                line_score=line.score,
                local_contrast=contrast,
                local_line_score=score,
                local_fallback_score=fallback_score,
                candidate_score=score,
                fallback_score=fallback_score,
                overlap=overlap,
                horizontal_span_recall=horizontal_span_recall,
                area_ratio=area_ratio,
            )
        )
        ocr_partial_recovery = ocr_complete_line_recovery
        ownership_scope = ownership_scope_by_id.get(record.candidate.id)
        ownership_line = ownership_line_by_id.get(record.candidate.id)
        if (
            ownership_scope is not None and ownership_line is not None
            and line is not None and line.score >= 0.74
            and "OCR" in line.sources
        ):
            local_fallback = fallback & ownership_scope
            local_common = cv2.dilate(
                (local_fallback | ownership_line).astype(np.uint8),
                np.ones((3, 3), np.uint8),
            ) > 0
            local_target, local_contrast = _text_render_evidence_target(
                reir, local_common,
            )
            local_fallback_score = _text_evidence_score(
                reir, local_fallback, local_target, local_common,
                line_score=0.5, exact_font=False,
            )
            local_line_score = _text_evidence_score(
                reir, ownership_line, local_target, local_common,
                line_score=line.score, exact_font=False,
            )
            local_fallback_topology = _topology(local_fallback)
            local_persistent_topology = _topology(
                _persistent_text_support(local_fallback)
            )
            incumbent_semantically_implausible = bool(
                recognized_glyphs >= 2
                and (
                    local_fallback_topology[0] > 2 * recognized_glyphs + 2
                    or local_fallback_topology[1] > 2 * recognized_glyphs + 2
                )
            )
            stable_incumbent_topology = (
                local_fallback_topology == local_persistent_topology
                and not incumbent_semantically_implausible
            )
            edge_counter_extension = _ocr_edge_counter_extension_proved(
                recognized_text, line, ownership_line, line_by_id.values(),
            )
            topology_compatible = _ocr_ownership_topology_compatible(
                edge_counter_extension=edge_counter_extension,
                local_fallback_empty=not np.any(local_fallback),
                stable_local_incumbent=stable_incumbent_topology,
                fallback_topology=fallback_topology,
                persistent_topology=persistent_topology,
                ownership_topology=_topology(ownership_line),
                local_fallback_topology=local_fallback_topology,
            )
            ordinary_ownership = bool(
                topology_compatible
                and
                line.score >= 0.90
                and local_contrast >= 0.08
                and local_line_score >= local_fallback_score + 0.08
                and score >= fallback_score + 0.04
            )
            uncertain_ownership = bool(
                topology_compatible
                and
                "OCR-bounded-physical-subset-with-connectivity-uncertainty"
                    in line.sources
                and local_contrast >= 0.12
                and local_line_score >= local_fallback_score + 0.15
                and score >= fallback_score + 0.12
            )
            semantic_complete_ownership = bool(
                topology_compatible
                and _semantic_ocr_complete_line_proved(
                    recognized_glyphs=recognized_glyphs,
                    incumbent_topology=local_fallback_topology,
                    candidate_topology=candidate_topology,
                    line_score=line.score,
                    local_contrast=local_contrast,
                    local_line_score=local_line_score,
                    local_fallback_score=local_fallback_score,
                    candidate_score=score,
                    fallback_score=fallback_score,
                    overlap=overlap,
                    horizontal_span_recall=horizontal_span_recall,
                    area_ratio=area_ratio,
                )
            )
            ocr_partial_recovery = bool(
                ocr_complete_line_recovery
                or ordinary_ownership or uncertain_ownership
                or semantic_complete_ownership
            )
            if ocr_partial_recovery and edge_counter_extension:
                ocr_edge_counter_ids.add(record.candidate.id)
        canvas_carrier_text_separation = False
        solid_canvas_carrier_text_separation = bool(
            fallback_area >= int(0.98 * fallback.size)
            and fallback_topology == (1, 0)
            and fallback_density >= 0.95
            and line is not None and line.score >= 0.84
            and {
                "both-polarities", "multithreshold-native-ink",
            }.issubset(line.sources)
            and 0.05 <= area_ratio <= 0.70
            and candidate_density <= 0.70
            and candidate_topology[0] >= 2
            and score >= fallback_score + 0.15
        )
        fallback_touches_canvas = bool(
            fallback_area and (
                fallback_bbox[0] <= 0 or fallback_bbox[1] <= 0
                or fallback_bbox[2] >= reir.width
                or fallback_bbox[3] >= reir.height
            )
        )
        candidate_is_interior = bool(
            candidate_bbox[0] > 0 and candidate_bbox[1] > 0
            and candidate_bbox[2] < reir.width
            and candidate_bbox[3] < reir.height
        )
        if (
            fallback_touches_canvas and candidate_is_interior
            and line is not None and line.score >= 0.80
            and ({
                "multithreshold-native-ink", "stable-small-component-line",
            } & set(line.sources))
            and overlap >= 0.95 and horizontal_span_recall >= 0.82
            and 0.25 <= area_ratio <= 0.75
            and candidate_topology[0] <= fallback_topology[0]
            and fallback_topology[1] - 1 <= candidate_topology[1]
                <= fallback_topology[1] + 2
        ):
            local_scope = cv2.dilate(
                mask.astype(np.uint8), np.ones((5, 5), np.uint8),
            ) > 0
            local_target, local_contrast = _text_render_evidence_target(
                reir, local_scope,
            )
            local_fallback_score = _text_evidence_score(
                reir, fallback, local_target, local_scope,
                line_score=0.5, exact_font=False,
            )
            local_candidate_score = _text_evidence_score(
                reir, mask, local_target, local_scope,
                line_score=line.score, exact_font=False,
            )
            canvas_carrier_text_separation = bool(
                local_contrast >= 0.10
                and local_candidate_score >= local_fallback_score + 0.02
            )
        persistent_subset_recovery = bool(
            fallback_area
            and line is not None and line.score >= 0.80
            and "persistent-component/counter-filter" in line.sources
            and "adaptive-foreground-component-layout" in line.sources
            and topology_error < fallback_topology_error
            and fallback_topology[1] >= 1
            and candidate_topology[1] >= 1
            and candidate_topology[1] <= fallback_topology[1] + 1
            and 0.75 <= area_ratio <= 1.02
            and overlap >= 0.75
            and horizontal_span_recall >= 0.90
            and score >= fallback_score + 0.03
        )
        alternatives.append((
            score, record, mask, candidate_topology,
            float(area_ratio), float(overlap), line,
            float(horizontal_span_recall),
        ))
        if fallback_area:
            if (
                overlap < 0.15
                and not knockout_carrier_recovery
                and not single_glyph_inverse_recovery
                and not single_composite_glyph_recovery
                and not coherent_inverse_line_recovery
                and not ocr_partial_recovery
                and not canvas_carrier_text_separation
                and not solid_canvas_carrier_text_separation
            ):
                continue
            # Replacing a complete incumbent line by one well-rendered word
            # fragment is an omission catastrophe, even when that fragment's
            # local topology is clean.  A replacement therefore has to carry
            # the incumbent's horizontal line extent.  This is a source-only
            # completeness certificate; it does not inspect review/GT masks.
            if (
                horizontal_span_recall < 0.82
                and not knockout_carrier_recovery
                and not single_glyph_inverse_recovery
                and not single_composite_glyph_recovery
                and not coherent_inverse_line_recovery
                and not ocr_partial_recovery
                and not canvas_carrier_text_separation
                and not solid_canvas_carrier_text_separation
            ):
                continue
            inverse_polarity_recovery = bool(
                coherent_inverse_line_recovery
                or (
                    fallback_density >= 0.75
                    and fallback_topology[1] >= max(
                        32, 8 * max(1, fallback_topology[0]),
                    )
                    and candidate_density <= 0.60
                    and candidate_topology[1] <= max(
                        8, int(0.10 * fallback_topology[1]),
                    )
                    and line is not None and "both-polarities" in line.sources
                    and score >= fallback_score + 0.12
                )
            )
            if inverse_polarity_recovery:
                # A near-solid background with hundreds of holes is the
                # inverse of the minority ink, not a plausible text program.
                # This independent polarity/render proof may replace that
                # malformed incumbent even though its topology is nominally
                # "persistent" under component-area filtering.
                inverse_polarity_ids.add(record.candidate.id)
                topology_error = -1
            elif knockout_carrier_recovery:
                # The incumbent is the dense carrier and its enclosed negative
                # loops are the visible glyphs.  Exact complement identity is
                # a stronger source-only proof than positive-mask overlap,
                # which is necessarily zero for a real knockout.
                knockout_carrier_ids.add(record.candidate.id)
                topology_error = -1
            elif single_glyph_inverse_recovery:
                # The legacy lane selected the full-frame colour carrier; the
                # adaptive topology vote proves that its bounded complement is
                # the one-counter glyph.  Exact complement agreement and the
                # native render margin are both required before replacement.
                single_glyph_inverse_ids.add(record.candidate.id)
                topology_error = -1
            elif single_glyph_consensus_recovery:
                # Independent thresholds agree on one complete interior glyph
                # while the incumbent differs only by nested JPEG/AA pieces.
                # The full-span, overlap and render walls above make this a
                # one-glyph certificate, not generic component deletion.
                single_glyph_consensus_ids.add(record.candidate.id)
                topology_error = -1
            elif single_composite_glyph_recovery:
                # The physical query and native mask agree on one narrow,
                # vertically registered multi-component symbol.  Only a tiny
                # unsupported incumbent residue may be removed, so this
                # exception cannot swallow a neighbouring letter/mark.
                single_composite_glyph_ids.add(record.candidate.id)
                topology_error = -1
            elif persistent_subset_recovery:
                # A full-span adaptive subset that survives component/counter
                # persistence is the structural midline of the same owner.
                # Keep its real topology distance for ranking; only exempt it
                # from the generic split/fusion wall that cannot distinguish
                # h24 antialias shifts from deleted glyphs.
                persistent_subset_ids.add(record.candidate.id)
            elif ocr_complete_line_recovery:
                # The OCR owner covers the complete incumbent rather than a
                # local sub-ROI, so there is intentionally no preserved mark.
                # Full-span overlap, semantic plausibility and two native
                # render margins are the ownership certificate.
                ocr_complete_line_ids.add(record.candidate.id)
                topology_error = -1
            elif ocr_partial_recovery:
                # The source-proved OCR line owns only its local ROI.  The
                # broader emblem/group outside that ROI is unchanged, while
                # a large native-render gain proves the replacement inside.
                ocr_partial_ids.add(record.candidate.id)
                topology_error = -1
            elif canvas_carrier_text_separation:
                # A full-canvas colour carrier and an interior, complete,
                # nested physical line are different semantic owners.  Score
                # them inside the line support so the carrier colour cannot
                # win merely by occupying most pixels in the broader ROI.
                canvas_carrier_ids.add(record.candidate.id)
                topology_error = -1
            elif solid_canvas_carrier_text_separation:
                # A completely filled one-component incumbent is the canvas
                # colour, not a text owner.  A high-confidence minority-ink
                # line repeated in both polarities and the native threshold
                # bank may therefore establish its own bounded ownership even
                # when cropped lettering legitimately touches an image edge.
                solid_canvas_carrier_ids.add(record.candidate.id)
                topology_error = -1
            correspondence_damage = glyph_catastrophe_count(fallback, mask)
            if (
                correspondence_damage > 0
                and not inverse_polarity_recovery
                and not knockout_carrier_recovery
                and not single_glyph_inverse_recovery
                and not single_glyph_consensus_recovery
                and not single_composite_glyph_recovery
                and not persistent_subset_recovery
                and not ocr_partial_recovery
                and not canvas_carrier_text_separation
                and not solid_canvas_carrier_text_separation
                and score < fallback_score + 0.08
            ):
                # Aggregate component/hole counts can improve while different
                # faint glyphs disappear.  A topology-changing replacement
                # must therefore clear a positive render-evidence wall against
                # the incumbent component correspondence, not merely resemble
                # a preferred count tuple.
                continue
            # Persistent incumbent topology is the hard replacement interval:
            # a candidate may remove native specks, but may not move farther
            # from the component/counter support that survives physical-area
            # filtering.  Native render evidence is a secondary wall.
            if (
                topology_error > fallback_topology_error
                and not inverse_polarity_recovery
                and not knockout_carrier_recovery
                and not single_glyph_inverse_recovery
                and not single_glyph_consensus_recovery
                and not single_composite_glyph_recovery
                and not persistent_subset_recovery
                and not ocr_partial_recovery
                and not canvas_carrier_text_separation
                and not solid_canvas_carrier_text_separation
            ):
                continue
            evidence_slack = (
                0.20 if topology_error < fallback_topology_error else 0.08
            )
            if (
                score < fallback_score - evidence_slack
                and not knockout_carrier_recovery
                and not single_glyph_inverse_recovery
                and not single_glyph_consensus_recovery
                and not single_composite_glyph_recovery
                and not persistent_subset_recovery
                and not ocr_partial_recovery
                and not canvas_carrier_text_separation
                and not solid_canvas_carrier_text_separation
            ):
                continue
        elif record.path != "exact-font" or contrast < 0.055 or score < 0.67:
            continue
        evaluated.append((topology_error, score, record, mask))
    ranking.sort(key=lambda row: (-row[2], row[0]))

    if not evaluated:
        selected_score = fallback_score
        selected_id = None; selected_path = "legacy"; selected = fallback
        selected_topology_error = fallback_topology_error
        reason = "no-overlapping-or-strong-new-line"
        fallback_used = True
    else:
        topology_error, selected_score, record, selected = min(
            evaluated, key=lambda row: (row[0], -row[1], row[2].candidate.id),
        )
        ocr_semantic_tiebreak = False
        if record.candidate.id in ocr_partial_ids:
            incumbent_line = line_by_id.get(record.line_id)
            if incumbent_line is not None:
                ix1, iy1, ix2, iy2 = incumbent_line.roi_xyxy
                incumbent_area = max(1, (ix2 - ix1) * (iy2 - iy1))
                semantic_peers: list[tuple[
                    int, float, TextMacroRecord, np.ndarray,
                ]] = []
                for alternative in evaluated:
                    alt_error, alt_score, alt_record, alt_mask = alternative
                    alt_line = line_by_id.get(alt_record.line_id)
                    if (
                        alt_line is None
                        or alt_record.candidate.id not in ocr_partial_ids
                        or "OCR-semantic-digital-preimage-topology"
                            not in alt_line.sources
                        or alt_score < selected_score - 0.02
                    ):
                        continue
                    ax1, ay1, ax2, ay2 = alt_line.roi_xyxy
                    intersection = max(0, min(ix2, ax2) - max(ix1, ax1)) * max(
                        0, min(iy2, ay2) - max(iy1, ay1),
                    )
                    alt_area = max(1, (ax2 - ax1) * (ay2 - ay1))
                    if intersection / max(1, min(incumbent_area, alt_area)) < 0.80:
                        continue
                    semantic_peers.append(alternative)
                if semantic_peers:
                    peer = max(
                        semantic_peers,
                        key=lambda row: (
                            line_by_id[row[2].line_id].score,
                            row[1], -row[0], row[2].candidate.id,
                        ),
                    )
                    peer_line = line_by_id[peer[2].line_id]
                    incumbent_semantic = (
                        "OCR-semantic-digital-preimage-topology"
                        in incumbent_line.sources
                    )
                    if (
                        not incumbent_semantic
                        or peer_line.score >= incumbent_line.score + 0.01
                    ):
                        topology_error, selected_score, record, selected = peer
                        ocr_semantic_tiebreak = True
        physical_ocr_tiebreak = False
        selected_line = line_by_id.get(record.line_id)
        if (
            selected_line is not None
            and "OCR-semantic-digital-preimage-topology"
                in selected_line.sources
        ):
            # OCR is allowed to propose counter topology, but its transcription
            # is not ground truth.  On CODERSRANK.IO WinOCR returned
            # ``CODERSRANK.I``; the semantic preimage then deleted the final O
            # and won only because it copied the incumbent's aggregate
            # topology.  A separately measured physical-midline line for the
            # same OCR owner had materially stronger native render evidence
            # and retained that glyph.  Treat this as the top-pair perceptual
            # tie-break from the plan, not as a relaxed topology gate: the
            # physical row must share the transcription and ROI, clear a
            # positive render margin, and stay within two topology events.
            selected_text = next((
                source.split(":", 1)[1] for source in selected_line.sources
                if source.startswith("ocr-text:")
            ), "")
            sx1, sy1, sx2, sy2 = selected_line.roi_xyxy
            selected_roi_area = max(1, (sx2 - sx1) * (sy2 - sy1))
            physical_alternatives: list[tuple[
                int, float, TextMacroRecord, np.ndarray,
            ]] = []
            for alternative in evaluated:
                alt_error, alt_score, alt_record, alt_mask = alternative
                alt_line = line_by_id.get(alt_record.line_id)
                if (
                    alt_line is None
                    or "persistent-physical-midline-topology"
                        not in alt_line.sources
                    or alt_line.score < 0.95
                ):
                    continue
                alt_text = next((
                    source.split(":", 1)[1] for source in alt_line.sources
                    if source.startswith("ocr-text:")
                ), "")
                ax1, ay1, ax2, ay2 = alt_line.roi_xyxy
                intersection = max(0, min(sx2, ax2) - max(sx1, ax1)) * max(
                    0, min(sy2, ay2) - max(sy1, ay1),
                )
                alt_roi_area = max(1, (ax2 - ax1) * (ay2 - ay1))
                roi_overlap = intersection / max(
                    1, min(selected_roi_area, alt_roi_area),
                )
                if (
                    not selected_text or alt_text != selected_text
                    or roi_overlap < 0.80
                    or alt_error > topology_error + 2
                    or alt_score < selected_score + 0.05
                    or alt_score < fallback_score + 0.10
                ):
                    continue
                physical_alternatives.append(alternative)
            if physical_alternatives:
                topology_error, selected_score, record, selected = max(
                    physical_alternatives,
                    key=lambda row: (
                        row[1], -row[0], row[2].candidate.id,
                    ),
                )
                physical_ocr_tiebreak = True
        selected_topology_error = topology_error
        structural_gain = fallback_topology_error - topology_error
        if (
            fallback_area and structural_gain <= 0
            and selected_score < fallback_score + replacement_margin
        ):
            selected_score = fallback_score
            selected_id = None; selected_path = "legacy"; selected = fallback
            selected_topology_error = fallback_topology_error
            reason = "legacy-wins-native-render-evidence"
            fallback_used = True
        else:
            selected_id = record.candidate.id; selected_path = record.path
            reason = (
                "ocr-physical-line-over-incomplete-semantic-decode"
                if physical_ocr_tiebreak else
                "ocr-semantic-top-pair-tiebreak"
                if ocr_semantic_tiebreak else
                "ocr-physical-edge-counter-over-incomplete-transcription"
                if selected_id in ocr_edge_counter_ids else
                "inverse-canvas-polarity-recovery"
                if selected_id in inverse_polarity_ids else
                "knockout-carrier-negative-loop-recovery"
                if selected_id in knockout_carrier_ids else
                "single-glyph-consensus-polarity-recovery"
                if selected_id in single_glyph_inverse_ids else
                "single-glyph-threshold-consensus-recovery"
                if selected_id in single_glyph_consensus_ids else
                "single-composite-glyph-query-recovery"
                if selected_id in single_composite_glyph_ids else
                "persistent-subset-topology-recovery"
                if selected_id in persistent_subset_ids else
                "ocr-complete-line-codec-recovery"
                if selected_id in ocr_complete_line_ids else
                "ocr-local-ownership-with-preserved-mark-recovery"
                if selected_id in preserved_mark_refined_ids else
                "ocr-local-ownership-recovery"
                if selected_id in ocr_partial_ids else
                "canvas-carrier-text-separation"
                if selected_id in canvas_carrier_ids else
                "solid-canvas-carrier-text-recovery"
                if selected_id in solid_canvas_carrier_ids else
                "new-line-wins-native-render-evidence"
            )
            fallback_used = False

    # Physical-midline lane.  It is activated only when the incumbent contains
    # measurable native specks, or when the independent line proposal itself
    # is very strong.  The mask must shrink/retain incumbent area, remain close
    # in evidence score, and stay inside a conservative topology envelope.
    fallback_components, fallback_holes = fallback_topology
    physical_rows: list[tuple[
        float, float, TextMacroRecord, np.ndarray,
    ]] = []
    if fallback_area:
        for (
            score, record, mask, topology, area_ratio, overlap, line,
            horizontal_span_recall,
        ) in alternatives:
            if line is None or "multithreshold-native-ink" not in line.sources:
                continue
            raw_level = next((
                value.split(":", 1)[1] for value in line.sources
                if value.startswith("linear-rgb-distance:")
            ), None)
            if raw_level is None:
                continue
            try:
                level = float(raw_level)
            except ValueError:
                continue
            components, holes = topology
            topology_error = (
                abs(components - persistent_topology[0])
                + abs(holes - persistent_topology[1])
            )
            lane_enabled = (
                fallback_topology_error >= 10 or line.score >= 0.84
            )
            if not lane_enabled:
                continue
            if not (0.16 <= level <= 0.62 and 0.45 <= area_ratio <= 1.02):
                continue
            if overlap < 0.40:
                continue
            if horizontal_span_recall < 0.82:
                continue
            if (
                components > 1.75 * fallback_components + 2
                or holes > fallback_holes + 3
            ):
                continue
            # A photometrically attractive midline is never allowed to undo
            # a topology improvement already established by the structural
            # lane.  This was the outlined-logo regression: a fragmented
            # threshold mask replaced a correct multi-counter outline solely
            # for a small native-score gain.
            if topology_error > selected_topology_error:
                continue
            if score < fallback_score + 0.02:
                continue
            if score < selected_score - 0.12:
                continue
            physical_utility = (
                score + 0.12 * line.score - 0.05 * abs(level - 0.45)
            )
            physical_rows.append((physical_utility, score, record, mask))
    lane = (
        "inverse-polarity"
        if selected_id in inverse_polarity_ids else "structural"
    )
    if selected_id in knockout_carrier_ids:
        lane = "knockout-negative-loops"
    if selected_id in single_glyph_inverse_ids:
        lane = "single-glyph-consensus-polarity"
    if selected_id in single_glyph_consensus_ids:
        lane = "single-glyph-threshold-consensus"
    if selected_id in single_composite_glyph_ids:
        lane = "single-composite-glyph-query"
    if selected_id in persistent_subset_ids:
        lane = "persistent-subset-topology"
    if selected_id in ocr_partial_ids:
        lane = "ocr-local-ownership"
    if selected_id in ocr_complete_line_ids:
        lane = "ocr-complete-line"
    if selected_id in canvas_carrier_ids:
        lane = "canvas-carrier-separation"
    if selected_id in solid_canvas_carrier_ids:
        lane = "solid-canvas-carrier-separation"
    if physical_rows:
        _utility, selected_score, record, selected = max(
            physical_rows, key=lambda row: (row[0], row[2].candidate.id),
        )
        selected_id = record.candidate.id
        selected_path = record.path
        selected_topology_error = (
            abs(_topology(selected)[0] - persistent_topology[0])
            + abs(_topology(selected)[1] - persistent_topology[1])
        )
        fallback_used = False
        reason = "physical-midline-posterior-wins"
        lane = "physical-midline"

    # A very large native-render gain may override the conservative persistent
    # target (e.g. a noisy token versus a coherent wordmark), but never by
    # expanding area/topology outside the bounded replacement envelope.
    strong_rows: list[tuple[float, TextMacroRecord, np.ndarray, int]] = []
    if fallback_area and fallback_topology_error >= 5:
        for (
            score, record, mask, topology, area_ratio, overlap, _line,
            horizontal_span_recall,
        ) in alternatives:
            components, holes = topology
            topology_error = (
                abs(components - persistent_topology[0])
                + abs(holes - persistent_topology[1])
            )
            if score < selected_score + 0.15 or overlap < 0.15:
                continue
            if horizontal_span_recall < 0.82:
                continue
            if not 0.50 <= area_ratio <= 1.80:
                continue
            if (
                components > 1.25 * fallback_components + 2
                or holes > 1.70 * fallback_holes + 3
            ):
                continue
            if topology_error > selected_topology_error:
                continue
            strong_rows.append((score, record, mask, topology_error))
    if strong_rows:
        selected_score, record, selected, selected_topology_error = max(
            strong_rows, key=lambda row: (row[0], row[1].candidate.id),
        )
        selected_id = record.candidate.id
        selected_path = record.path
        fallback_used = False
        reason = "strong-native-render-evidence-override"
        lane = "strong-render"

    chromatic_rows: list[tuple[
        int, float, TextMacroRecord, np.ndarray, int,
    ]] = []
    if fallback_area:
        for (
            score, record, mask, topology, _area_ratio, _overlap, line,
            _horizontal_span_recall,
        ) in alternatives:
            for (
                _witness_score, _witness_record, witness_mask,
                _witness_topology, _witness_area_ratio, _witness_overlap,
                witness_line, _witness_horizontal_span_recall,
            ) in alternatives:
                if not _chromatic_completion_pair_proved(
                    fallback, mask, witness_mask, line, witness_line,
                    candidate_score=float(score),
                    fallback_score=float(fallback_score),
                ):
                    continue
                topology_error = (
                    abs(topology[0] - persistent_topology[0])
                    + abs(topology[1] - persistent_topology[1])
                )
                chromatic_rows.append((
                    int(np.sum(mask)), float(score), record, mask,
                    int(topology_error),
                ))
    if chromatic_rows:
        (
            _selected_area, selected_score, record, selected,
            selected_topology_error,
        ) = min(
            chromatic_rows,
            key=lambda row: (row[0], -row[1], row[2].candidate.id),
        )
        selected_id = record.candidate.id
        selected_path = record.path
        fallback_used = False
        reason = "nested-multithreshold-chromatic-completion"
        lane = "chromatic-completion"

    selected_record = next((
        row for row in generated.records
        if row.candidate.id == selected_id
    ), None)
    selected_line = (
        line_by_id.get(selected_record.line_id)
        if selected_record is not None else None
    )
    enclosing_physical_midline_proved = _enclosing_physical_midline_proved(
        fallback, selected, selected_line,
        candidate_score=float(selected_score),
        fallback_score=float(fallback_score),
        candidate_topology_error=int(selected_topology_error),
        fallback_topology_error=int(fallback_topology_error),
    )
    if enclosing_physical_midline_proved:
        reason = "enclosing-physical-midline-recovery"
        lane = "enclosing-physical-midline"

    # With only a tiny incumbent/persistent discrepancy, an uncorroborated
    # cleanup is more likely to delete punctuation or a diacritic than codec
    # noise.  Fail open unless a physical or exceptionally strong lane proved
    # the replacement independently.
    if (
        fallback_area and fallback_topology_error < 10
        and lane == "structural" and _topology(selected) != fallback_topology
        and not persistent_reference_proved
        and not enclosing_physical_midline_proved
    ):
        selected = fallback
        selected_score = fallback_score
        selected_id = None; selected_path = "legacy"
        fallback_used = True
        reason = "small-topology-delta-without-independent-proof"
    frozen = _freeze_mask(selected)
    preserved_fallback = preserved_by_id.get(selected_id or "")
    decision = TextLineCourtDecision(
        selected_id, selected_path, frozen, fallback_used,
        float(selected_score), float(fallback_score), len(unique), reason,
        tuple(ranking), preserved_fallback,
    )
    decision.validate(reir)
    return decision
