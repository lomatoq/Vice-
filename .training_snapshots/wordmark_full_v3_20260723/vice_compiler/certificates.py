"""Machine-checkable certificate bundle for proof-carrying macros."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from typing import Iterable

import cv2
import numpy as np


SCHEMA = "pcdc-certificate-bundle/v1"


@dataclass(frozen=True)
class ValidityCertificate:
    valid: bool
    finite_parameters: bool
    legal_paths: bool
    no_prohibited_self_intersections: bool
    legal_positive_negative_loops: bool
    holes_contained: bool
    layer_order_acyclic: bool
    hidden_geometry_bounded: bool
    no_canvas_scale_residual_eraser: bool
    violations: tuple[str, ...] = ()

    def validate(self) -> None:
        claims = (
            self.finite_parameters, self.legal_paths,
            self.no_prohibited_self_intersections,
            self.legal_positive_negative_loops, self.holes_contained,
            self.layer_order_acyclic, self.hidden_geometry_bounded,
            self.no_canvas_scale_residual_eraser,
        )
        if self.valid != (all(claims) and not self.violations):
            raise ValueError("validity certificate truth value is inconsistent")


@dataclass(frozen=True)
class SupportCertificate:
    valid: bool
    roi_xyxy: tuple[int, int, int, int]
    support_sha256: str
    support_size: tuple[int, int]
    support_pixels: int
    scored_pixels: int
    core_bits: int
    interface_ids: tuple[int, ...]
    no_score_outside_support: bool
    provenance: tuple[str, ...]

    def validate(self) -> None:
        width, height = self.support_size
        x1, y1, x2, y2 = self.roi_xyxy
        if width <= 0 or height <= 0 or not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("invalid support certificate lattice/ROI")
        if len(self.support_sha256) != 64 or self.support_pixels <= 0:
            raise ValueError("support certificate lacks a nonempty digest")
        if self.scored_pixels < 0 or self.scored_pixels > self.support_pixels:
            raise ValueError("support certificate scores unclaimed pixels")
        if self.valid != self.no_score_outside_support:
            raise ValueError("support certificate validity is inconsistent")


@dataclass(frozen=True)
class TopologyCertificate:
    valid: bool
    components: int
    holes: int
    containment: tuple[tuple[int, int], ...]
    contact_graph: tuple[tuple[int, int], ...]
    text_counter_identities: tuple[str, ...]
    junction_degrees: tuple[int, ...]
    persistent_evidence_matched: bool
    expected_components: int | None
    expected_holes: int | None
    hard_requirement: bool

    def validate(self) -> None:
        if self.components < 0 or self.holes < 0:
            raise ValueError("negative topology count")
        matched = (
            (self.expected_components is None
             or self.components == self.expected_components)
            and (self.expected_holes is None or self.holes == self.expected_holes)
            and self.persistent_evidence_matched
        )
        if self.hard_requirement and self.valid != matched:
            raise ValueError("hard topology certificate is inconsistent")
        if not self.hard_requirement and not self.valid:
            raise ValueError("soft topology certificate cannot be invalid")


@dataclass(frozen=True)
class GeometryCertificate:
    valid: bool
    directional_interval_feasible: bool
    max_boundary_deviation_px: float
    p95_boundary_deviation_px: float
    sdf_lower_bound: float
    corner_tangent_compatible: bool
    foreign_ink_trespass: float
    digital_preimage_feasible: bool
    parameter_condition_number: float
    unsupported_extrapolation_pixels: int
    tolerance_px: float

    def validate(self) -> None:
        values = (
            self.max_boundary_deviation_px, self.p95_boundary_deviation_px,
            self.sdf_lower_bound, self.foreign_ink_trespass,
            self.parameter_condition_number, self.tolerance_px,
        )
        if not all(math.isfinite(value) and value >= 0.0 for value in values):
            raise ValueError("geometry certificate contains invalid bounds")
        claims = (
            self.directional_interval_feasible,
            self.corner_tangent_compatible,
            self.digital_preimage_feasible,
            self.unsupported_extrapolation_pixels == 0,
        )
        if self.valid != all(claims):
            raise ValueError("geometry certificate validity is inconsistent")


@dataclass(frozen=True)
class RenderEvidenceCertificate:
    valid: bool
    posterior_digest: str
    posterior_mean_delta_logp: float
    posterior_variance: float
    conservative_lower_bound: float
    model_deltas: tuple[tuple[str, float], ...]
    score_components: tuple[tuple[str, float], ...]
    exact_rendered_pixel_budget: int

    def validate(self) -> None:
        values = (
            self.posterior_mean_delta_logp, self.posterior_variance,
            self.conservative_lower_bound,
            *(value for _name, value in self.model_deltas),
            *(value for _name, value in self.score_components),
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("render certificate contains non-finite values")
        if self.posterior_variance < 0.0 or self.exact_rendered_pixel_budget <= 0:
            raise ValueError("render certificate has invalid variance/budget")
        if len(self.posterior_digest) != 64 or not self.model_deltas:
            raise ValueError("render certificate lacks posterior evidence")


@dataclass(frozen=True)
class StructuralCertificate:
    valid: bool
    text_line_consistency: float
    repeated_glyph_support: float
    symmetry_support: float
    equal_radius_support: float
    stroke_width_support: float
    layer_order_support: float
    semantic_class_confidence: float
    score: float

    def validate(self) -> None:
        values = (
            self.text_line_consistency, self.repeated_glyph_support,
            self.symmetry_support, self.equal_radius_support,
            self.stroke_width_support, self.layer_order_support,
            self.semantic_class_confidence,
        )
        if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values):
            raise ValueError("invalid structural support")
        if not math.isfinite(self.score):
            raise ValueError("invalid structural score")


@dataclass(frozen=True)
class ComplexityCertificate:
    valid: bool
    primitive_type_code_bits: float
    parameter_precision_bits: float
    exception_count: int
    topology_complexity_bits: float
    layer_complexity_bits: float
    group_abstraction_savings_bits: float
    editability_cost_bits: float
    total_code_bits: float

    def validate(self) -> None:
        values = (
            self.primitive_type_code_bits, self.parameter_precision_bits,
            self.topology_complexity_bits, self.layer_complexity_bits,
            self.group_abstraction_savings_bits, self.editability_cost_bits,
            self.total_code_bits,
        )
        if self.exception_count < 0 or not all(math.isfinite(value) for value in values):
            raise ValueError("invalid complexity certificate")
        expected = (
            self.primitive_type_code_bits + self.parameter_precision_bits
            + self.exception_count * 8.0 + self.topology_complexity_bits
            + self.layer_complexity_bits + self.editability_cost_bits
            - self.group_abstraction_savings_bits
        )
        if abs(self.total_code_bits - max(0.0, expected)) > 1e-7:
            raise ValueError("complexity code length is inconsistent")


@dataclass(frozen=True)
class ResourceCertificate:
    valid: bool
    fitting_ms: float
    render_pixels: int
    memory_bytes: int
    font_trials: int
    solver_variables: int
    within_job_budget: bool

    def validate(self) -> None:
        if (
            not math.isfinite(self.fitting_ms) or self.fitting_ms < 0.0
            or min(self.render_pixels, self.memory_bytes, self.font_trials,
                   self.solver_variables) < 0
        ):
            raise ValueError("invalid resource certificate")
        if self.valid != self.within_job_budget:
            raise ValueError("resource certificate validity is inconsistent")


@dataclass(frozen=True)
class CertificateBundle:
    schema: str
    candidate_id: str
    validity: ValidityCertificate
    support: SupportCertificate
    topology: TopologyCertificate
    geometry: GeometryCertificate
    render_evidence: RenderEvidenceCertificate
    structural: StructuralCertificate
    complexity: ComplexityCertificate
    resource: ResourceCertificate
    digest: str
    provenance: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return all((
            self.validity.valid, self.support.valid, self.topology.valid,
            self.geometry.valid, self.render_evidence.valid,
            self.structural.valid, self.complexity.valid, self.resource.valid,
        ))

    def validate(self) -> None:
        if self.schema != SCHEMA or not self.candidate_id:
            raise ValueError("invalid certificate bundle identity")
        self.validity.validate(); self.support.validate()
        self.topology.validate(); self.geometry.validate()
        self.render_evidence.validate(); self.structural.validate()
        self.complexity.validate(); self.resource.validate()
        if self.digest != certificate_bundle_digest(self):
            raise ValueError("certificate bundle digest mismatch")


def _jsonable_bundle(bundle: CertificateBundle) -> dict[str, object]:
    payload = asdict(bundle)
    payload["digest"] = ""
    return payload


def certificate_bundle_digest(bundle: CertificateBundle) -> str:
    encoded = json.dumps(
        _jsonable_bundle(bundle), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def seal_bundle(bundle: CertificateBundle) -> CertificateBundle:
    sealed = replace(bundle, digest=certificate_bundle_digest(bundle))
    sealed.validate()
    return sealed


def mask_sha256(mask: np.ndarray) -> str:
    packed = np.packbits(np.asarray(mask, bool), axis=None, bitorder="little")
    return hashlib.sha256(packed.tobytes()).hexdigest()


def topology_signature(mask: np.ndarray) -> tuple[int, int]:
    binary = np.asarray(mask, np.uint8)
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )
    if hierarchy is None or not contours:
        return 0, 0
    parents = hierarchy[0, :, 3]
    depth = np.zeros(len(parents), dtype=np.int32)
    for index in range(len(parents)):
        parent = int(parents[index])
        while parent >= 0:
            depth[index] += 1
            parent = int(parents[parent])
    return int(np.sum(depth % 2 == 0)), int(np.sum(depth % 2 == 1))


def build_validity_certificate(
    *, kind: str, parameters: Iterable[tuple[str, object]],
    roi_xyxy: tuple[int, int, int, int], canvas_size: tuple[int, int],
    legal_paths: bool = True, no_self_intersections: bool = True,
    legal_loops: bool = True, holes_contained: bool = True,
    layer_order_acyclic: bool = True, hidden_geometry_bounded: bool = True,
) -> ValidityCertificate:
    finite = all(
        not isinstance(value, (float, int)) or math.isfinite(float(value))
        for _name, value in parameters
    )
    width, height = canvas_size
    canvas_eraser = kind == "eraser" and roi_xyxy == (0, 0, width, height)
    claims = {
        "finite-parameters": finite,
        "legal-paths": legal_paths,
        "no-prohibited-self-intersections": no_self_intersections,
        "legal-loops": legal_loops,
        "holes-contained": holes_contained,
        "acyclic-layers": layer_order_acyclic,
        "bounded-hidden-geometry": hidden_geometry_bounded,
        "no-canvas-residual-eraser": not canvas_eraser,
    }
    violations = tuple(name for name, passed in claims.items() if not passed)
    certificate = ValidityCertificate(
        valid=not violations, finite_parameters=finite,
        legal_paths=legal_paths,
        no_prohibited_self_intersections=no_self_intersections,
        legal_positive_negative_loops=legal_loops,
        holes_contained=holes_contained,
        layer_order_acyclic=layer_order_acyclic,
        hidden_geometry_bounded=hidden_geometry_bounded,
        no_canvas_scale_residual_eraser=not canvas_eraser,
        violations=violations,
    )
    certificate.validate()
    return certificate


def build_support_certificate(
    mask: np.ndarray, *, roi_xyxy: tuple[int, int, int, int],
    scored_mask: np.ndarray | None = None, core_bits: int = 0,
    interface_ids: tuple[int, ...] = (), provenance: tuple[str, ...] = (),
) -> SupportCertificate:
    support = np.asarray(mask, bool)
    scored = support if scored_mask is None else np.asarray(scored_mask, bool)
    if scored.shape != support.shape:
        raise ValueError("scored/support mask shape mismatch")
    no_outside = not bool(np.any(scored & ~support))
    certificate = SupportCertificate(
        valid=no_outside, roi_xyxy=roi_xyxy,
        support_sha256=mask_sha256(support),
        support_size=(support.shape[1], support.shape[0]),
        support_pixels=int(support.sum()), scored_pixels=int(scored.sum()),
        core_bits=int(core_bits), interface_ids=tuple(interface_ids),
        no_score_outside_support=no_outside, provenance=provenance,
    )
    certificate.validate()
    return certificate


def _junction_degrees(mask: np.ndarray) -> tuple[int, ...]:
    binary = np.asarray(mask, np.uint8)
    if hasattr(cv2, "ximgproc") and hasattr(cv2.ximgproc, "thinning"):
        skeleton = cv2.ximgproc.thinning(binary * 255) > 0
    else:
        skeleton = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT) > 0
    neighbors = cv2.filter2D(
        skeleton.astype(np.uint8), cv2.CV_16S,
        np.ones((3, 3), np.int16), borderType=cv2.BORDER_CONSTANT,
    ) - skeleton.astype(np.int16)
    return tuple(sorted(int(value) for value in neighbors[skeleton & (neighbors >= 3)]))


def build_topology_certificate(
    mask: np.ndarray, *, expected_components: int | None = None,
    expected_holes: int | None = None, hard_requirement: bool = False,
    persistent_evidence_matched: bool = True,
    contact_graph: tuple[tuple[int, int], ...] = (),
) -> TopologyCertificate:
    binary = np.asarray(mask, np.uint8)
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )
    components, holes = topology_signature(binary)
    containment: list[tuple[int, int]] = []
    counters: list[str] = []
    if hierarchy is not None:
        for index, parent in enumerate(hierarchy[0, :, 3].tolist()):
            if int(parent) >= 0:
                containment.append((index, int(parent)))
                moments = cv2.moments(contours[index])
                if abs(moments["m00"]) > 1e-9:
                    counters.append(
                        f"counter@{moments['m10']/moments['m00']:.3f},"
                        f"{moments['m01']/moments['m00']:.3f}"
                    )
    matched = (
        (expected_components is None or components == expected_components)
        and (expected_holes is None or holes == expected_holes)
        and persistent_evidence_matched
    )
    certificate = TopologyCertificate(
        valid=matched if hard_requirement else True,
        components=components, holes=holes,
        containment=tuple(containment), contact_graph=tuple(contact_graph),
        text_counter_identities=tuple(counters),
        junction_degrees=_junction_degrees(binary),
        persistent_evidence_matched=persistent_evidence_matched,
        expected_components=expected_components, expected_holes=expected_holes,
        hard_requirement=hard_requirement,
    )
    certificate.validate()
    return certificate


def _boundary(mask: np.ndarray) -> np.ndarray:
    return cv2.morphologyEx(
        np.asarray(mask, np.uint8), cv2.MORPH_GRADIENT,
        np.ones((3, 3), np.uint8),
    ) > 0


def _bounded_signed_distance(mask: np.ndarray) -> np.ndarray:
    """Return an ROI-bounded signed distance field in physical pixels.

    Padding supplies an explicit finite outside boundary, so a full-frame
    foreground cannot trigger OpenCV's no-zero sentinel.  Positive values
    are outside the design and negative values are inside it.
    """
    foreground = np.asarray(mask, np.uint8)

    def distance_to_zero(binary: np.ndarray) -> np.ndarray:
        padded = np.pad(binary, 1, mode="constant", constant_values=0)
        field = cv2.distanceTransform(padded, cv2.DIST_L2, 5)
        return field[1:-1, 1:-1]

    inside = distance_to_zero(foreground)
    outside = distance_to_zero(1 - foreground)
    return outside.astype(np.float64) - inside.astype(np.float64)


def build_geometry_certificate(
    evidence_mask: np.ndarray, rendered_alpha: np.ndarray,
    claimed_support: np.ndarray, *, tolerance_px: float = 2.0,
    parameter_condition_number: float = 1.0,
    corner_tangent_compatible: bool = True,
) -> GeometryCertificate:
    evidence = np.asarray(evidence_mask, bool)
    rendered = np.asarray(rendered_alpha, np.float32) >= 0.5
    claimed = np.asarray(claimed_support, bool)
    if evidence.shape != rendered.shape or evidence.shape != claimed.shape:
        raise ValueError("geometry certificate mask shapes differ")
    evidence_boundary = _boundary(evidence)
    rendered_boundary = _boundary(rendered)
    if np.any(evidence_boundary) and np.any(rendered_boundary):
        to_evidence = cv2.distanceTransform(
            (~evidence_boundary).astype(np.uint8), cv2.DIST_L2, 5
        )
        to_rendered = cv2.distanceTransform(
            (~rendered_boundary).astype(np.uint8), cv2.DIST_L2, 5
        )
        deviations = np.concatenate((
            to_evidence[rendered_boundary], to_rendered[evidence_boundary]
        )).astype(np.float64, copy=False)
        max_deviation = float(np.max(deviations))
        p95_deviation = float(np.quantile(deviations, 0.95))
        evidence_sdf = _bounded_signed_distance(evidence)
        rendered_sdf = _bounded_signed_distance(rendered)
        # The union of both finite supports is the exact locus on which this
        # macro can change the scene.  This is a real SDF discrepancy bound,
        # not an alias for a boundary Chamfer statistic.
        sdf_locus = evidence | rendered
        sdf_bound = float(np.mean(
            np.abs(evidence_sdf[sdf_locus] - rendered_sdf[sdf_locus]),
            dtype=np.float64,
        ))
    elif np.any(evidence_boundary) or np.any(rendered_boundary):
        # The directed distance to an empty boundary is unbounded in an
        # infinite plane.  On the finite ROI the exact conservative upper
        # bound is its diagonal; never leak OpenCV's FLT_MAX sentinel.
        diagonal = math.hypot(*evidence.shape)
        max_deviation = p95_deviation = sdf_bound = float(diagonal)
    else:
        max_deviation = p95_deviation = sdf_bound = 0.0
    outside_evidence = int(np.sum(rendered & ~evidence))
    foreign = outside_evidence / max(1, int(rendered.sum()))
    unsupported = int(np.sum(rendered & ~claimed))
    intersection = int(np.sum(rendered & evidence))
    preimage = bool(intersection > 0 or (not np.any(rendered) and not np.any(evidence)))
    directional = bool(p95_deviation <= max(0.0, float(tolerance_px)))
    claims = (
        directional, bool(corner_tangent_compatible), preimage,
        unsupported == 0,
    )
    certificate = GeometryCertificate(
        valid=all(claims), directional_interval_feasible=directional,
        max_boundary_deviation_px=max_deviation,
        p95_boundary_deviation_px=p95_deviation,
        sdf_lower_bound=sdf_bound,
        corner_tangent_compatible=bool(corner_tangent_compatible),
        foreign_ink_trespass=float(foreign),
        digital_preimage_feasible=preimage,
        parameter_condition_number=max(0.0, float(parameter_condition_number)),
        unsupported_extrapolation_pixels=unsupported,
        tolerance_px=max(0.0, float(tolerance_px)),
    )
    certificate.validate()
    return certificate


def build_structural_certificate(
    *, text_line: float = 0.0, repeated_glyph: float = 0.0,
    symmetry: float = 0.0, equal_radius: float = 0.0,
    stroke_width: float = 0.0, layer_order: float = 0.0,
    semantic_confidence: float = 0.0,
) -> StructuralCertificate:
    values = tuple(float(np.clip(value, 0.0, 1.0)) for value in (
        text_line, repeated_glyph, symmetry, equal_radius, stroke_width,
        layer_order, semantic_confidence,
    ))
    score = float(np.mean(values))
    certificate = StructuralCertificate(True, *values, score)
    certificate.validate()
    return certificate


def build_complexity_certificate(
    *, parameter_count: int, exception_count: int = 0,
    components: int = 1, holes: int = 0, layers: int = 1,
    group_savings_bits: float = 0.0, editability_cost_bits: float = 0.0,
) -> ComplexityCertificate:
    primitive_bits = 4.0
    parameter_bits = max(0, int(parameter_count)) * 12.0
    topology_bits = math.log2(max(1, components + holes + 1)) * 4.0
    layer_bits = math.log2(max(1, layers + 1)) * 3.0
    expected = (
        primitive_bits + parameter_bits + max(0, int(exception_count)) * 8.0
        + topology_bits + layer_bits + max(0.0, editability_cost_bits)
        - max(0.0, group_savings_bits)
    )
    certificate = ComplexityCertificate(
        valid=True, primitive_type_code_bits=primitive_bits,
        parameter_precision_bits=parameter_bits,
        exception_count=max(0, int(exception_count)),
        topology_complexity_bits=topology_bits,
        layer_complexity_bits=layer_bits,
        group_abstraction_savings_bits=max(0.0, group_savings_bits),
        editability_cost_bits=max(0.0, editability_cost_bits),
        total_code_bits=max(0.0, expected),
    )
    certificate.validate()
    return certificate


def build_resource_certificate(
    *, fitting_ms: float, render_pixels: int, memory_bytes: int,
    font_trials: int = 0, solver_variables: int = 1,
    max_fitting_ms: float = 100.0, max_render_pixels: int = 262_144,
    max_memory_bytes: int = 64 * 1024 * 1024,
) -> ResourceCertificate:
    within = bool(
        fitting_ms <= max_fitting_ms
        and render_pixels <= max_render_pixels
        and memory_bytes <= max_memory_bytes
    )
    certificate = ResourceCertificate(
        valid=within, fitting_ms=max(0.0, float(fitting_ms)),
        render_pixels=max(0, int(render_pixels)),
        memory_bytes=max(0, int(memory_bytes)),
        font_trials=max(0, int(font_trials)),
        solver_variables=max(0, int(solver_variables)),
        within_job_budget=within,
    )
    certificate.validate()
    return certificate
