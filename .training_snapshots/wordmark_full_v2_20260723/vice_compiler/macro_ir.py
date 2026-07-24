"""Candidate Macro IR (CMIR) contracts for PCDC phase 2.

The module is deliberately renderer- and solver-agnostic.  Every candidate
owns an exact bitset of REIR core cells and carries bounded score/resource
claims.  Full render/court certificates are added in phase 3; phase 2 keeps
the support/topology part machine-checkable so extraction can never operate
on an unscoped proposal.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import math
from typing import Any, Iterable

from .certificates import CertificateBundle


SCHEMA = "pcdc-cmir/v2"


class MacroKind(str, Enum):
    ATOMIC_FALLBACK = "atomic_fallback"
    LEGACY_REGION = "legacy_region"
    HIERARCHY_REGION = "hierarchy_region"
    SOLID_REGION = "solid_region"
    GENERIC_REGION = "generic_region"
    SHAPE = "shape"
    TEXT_LINE = "text_line"
    STROKE_NETWORK = "stroke_network"
    LAYER = "layer"
    GRADIENT = "gradient"
    CODEC_DETAIL = "codec_detail"
    ORACLE = "oracle"


BASE_KINDS = frozenset({
    MacroKind.ATOMIC_FALLBACK,
    MacroKind.LEGACY_REGION,
    MacroKind.HIERARCHY_REGION,
})


@dataclass(frozen=True)
class SceneProgram:
    operator: str
    parameters: tuple[tuple[str, float | int | str], ...] = ()


@dataclass(frozen=True)
class ScoreBounds:
    lower: float
    expected: float
    upper: float

    def validate(self) -> None:
        values = (self.lower, self.expected, self.upper)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("macro score bounds must be finite")
        if not self.lower <= self.expected <= self.upper:
            raise ValueError("macro score bounds are not ordered")


@dataclass(frozen=True)
class ResourceEstimate:
    fitting_ms: float
    render_pixels: int
    memory_bytes: int
    solver_variables: int

    def validate(self) -> None:
        if (
            not math.isfinite(self.fitting_ms) or self.fitting_ms < 0
            or self.render_pixels < 0 or self.memory_bytes < 0
            or self.solver_variables < 0
        ):
            raise ValueError("invalid macro resource estimate")


@dataclass(frozen=True)
class MacroCertificates:
    """Phase-2 support/topology certificate carried by every column."""

    valid: bool
    support_source: str
    support_size: tuple[int, int]
    support_rle: tuple[tuple[int, int], ...] = ()
    support_bits: bytes = b""
    components: int | None = None
    holes: int | None = None
    evidence_token_ids: tuple[int, ...] = ()
    notes: tuple[str, ...] = ()

    def validate(self) -> None:
        width, height = self.support_size
        if width < 0 or height < 0:
            raise ValueError("negative support lattice")
        previous_end = 0
        for start, length in self.support_rle:
            end = start + length
            if (
                start < previous_end or length <= 0
                or end > width * height
            ):
                raise ValueError("invalid macro support RLE")
            previous_end = end
        if self.support_bits:
            expected = (width * height + 7) // 8
            if len(self.support_bits) != expected:
                raise ValueError("invalid macro bit-packed support")
        if self.components is not None and self.components < 0:
            raise ValueError("negative component count")
        if self.holes is not None and self.holes < 0:
            raise ValueError("negative hole count")


@dataclass(frozen=True)
class MacroCandidate:
    id: str
    registry_index: int
    kind: MacroKind
    family: str
    roi_xyxy: tuple[int, int, int, int]
    core_bits: int
    alpha_bounds: tuple[float, float]
    boundary_interfaces: tuple[int, ...]
    soft_evidence: tuple[int, ...]
    hidden_geometry: tuple[tuple[str, Any], ...] | None
    program: SceneProgram
    continuous_params: tuple[tuple[str, float], ...]
    covariance: tuple[float, ...]
    certificates: MacroCertificates
    conflict_bits: int
    prerequisite_claims: tuple[str, ...]
    score_bounds: ScoreBounds
    resource_estimate: ResourceEstimate
    provenance: tuple[str, ...]
    proof_bundle: CertificateBundle | None = None

    @property
    def cell_count(self) -> int:
        return self.core_bits.bit_count()

    @property
    def is_base(self) -> bool:
        return self.kind in BASE_KINDS

    def validate(
        self, *, leaf_count: int, interface_count: int,
        candidate_count: int | None = None,
    ) -> None:
        if not self.id:
            raise ValueError("macro id is empty")
        if self.registry_index < 0:
            raise ValueError("macro registry index is negative")
        if self.core_bits <= 0:
            raise ValueError("visible macro must own at least one core cell")
        if self.core_bits >> leaf_count:
            raise ValueError("macro owns a core cell outside REIR")
        x1, y1, x2, y2 = self.roi_xyxy
        if not (x1 <= x2 and y1 <= y2):
            raise ValueError("macro ROI is invalid")
        alpha_min, alpha_max = self.alpha_bounds
        if not (
            math.isfinite(alpha_min) and math.isfinite(alpha_max)
            and 0.0 <= alpha_min <= alpha_max <= 1.0
        ):
            raise ValueError("macro alpha bounds are invalid")
        if any(index < 0 or index >= interface_count
               for index in self.boundary_interfaces):
            raise ValueError("macro references an invalid interface")
        if candidate_count is not None and self.conflict_bits >> candidate_count:
            raise ValueError("macro conflict bitset exceeds registry")
        if self.conflict_bits & (1 << self.registry_index):
            raise ValueError("macro conflicts with itself")
        if any(not math.isfinite(value) for _name, value in self.continuous_params):
            raise ValueError("macro has a non-finite continuous parameter")
        if any(not math.isfinite(value) or value < 0 for value in self.covariance):
            raise ValueError("macro covariance must be finite and non-negative")
        self.score_bounds.validate()
        self.resource_estimate.validate()
        self.certificates.validate()
        if not self.certificates.valid:
            raise ValueError("invalid candidate cannot enter CMIR")
        if self.proof_bundle is not None:
            self.proof_bundle.validate()
            if not self.proof_bundle.valid:
                raise ValueError("invalid proof bundle cannot enter CMIR")
            if self.proof_bundle.candidate_id != self.id:
                raise ValueError("proof bundle belongs to another candidate")
            if self.proof_bundle.support.core_bits != self.core_bits:
                raise ValueError("proof bundle/core ownership mismatch")
            if self.proof_bundle.support.support_size != self.certificates.support_size:
                raise ValueError("proof bundle/support lattice mismatch")
            if tuple(sorted(self.proof_bundle.support.interface_ids)) != tuple(
                sorted(self.boundary_interfaces)
            ):
                raise ValueError("proof bundle/interface ownership mismatch")
            if (
                self.certificates.components is not None
                and self.proof_bundle.topology.components
                != self.certificates.components
            ):
                raise ValueError("proof bundle/component claim mismatch")
            if (
                self.certificates.holes is not None
                and self.proof_bundle.topology.holes != self.certificates.holes
            ):
                raise ValueError("proof bundle/hole claim mismatch")

    @property
    def is_proof_carrying(self) -> bool:
        return self.proof_bundle is not None and self.proof_bundle.valid

    def with_proof_bundle(self, bundle: CertificateBundle) -> "MacroCandidate":
        """Return a candidate whose court proof is bound to its CMIR identity."""
        bundle.validate()
        if not bundle.valid or bundle.candidate_id != self.id:
            raise ValueError("proof bundle does not certify this candidate")
        if bundle.support.core_bits != self.core_bits:
            raise ValueError("proof bundle/core ownership mismatch")
        if bundle.support.support_size != self.certificates.support_size:
            raise ValueError("proof bundle/support lattice mismatch")
        if tuple(sorted(bundle.support.interface_ids)) != tuple(
            sorted(self.boundary_interfaces)
        ):
            raise ValueError("proof bundle/interface ownership mismatch")
        if (
            self.certificates.components is not None
            and bundle.topology.components != self.certificates.components
        ):
            raise ValueError("proof bundle/component claim mismatch")
        if (
            self.certificates.holes is not None
            and bundle.topology.holes != self.certificates.holes
        ):
            raise ValueError("proof bundle/hole claim mismatch")
        certified = replace(self, proof_bundle=bundle)
        # A court certifies an immutable draft before registry admission.  Full
        # registry-index/conflict validation runs immediately in
        # ``extend_registry``; already registered candidates can be checked
        # eagerly here as well.
        if certified.registry_index >= 0:
            certified.validate(
                leaf_count=max(1, certified.core_bits.bit_length()),
                interface_count=max(
                    (*certified.boundary_interfaces, *bundle.support.interface_ids),
                    default=-1,
                ) + 1,
            )
        return certified


@dataclass(frozen=True)
class CandidateMacroIR:
    schema: str
    source_sha256: str
    leaf_count: int
    interface_count: int
    interface_endpoints: tuple[tuple[int, int], ...]
    candidates: tuple[MacroCandidate, ...]
    atomic_ids: tuple[str, ...]
    legacy_ids: tuple[str, ...]
    registry_hash: str
    provenance: tuple[str, ...]

    def by_id(self) -> dict[str, MacroCandidate]:
        return {candidate.id: candidate for candidate in self.candidates}

    def validate(self) -> None:
        if self.schema != SCHEMA:
            raise ValueError("unsupported CMIR schema")
        if self.leaf_count <= 0:
            raise ValueError("CMIR has no core cells")
        if self.interface_count < 0:
            raise ValueError("CMIR has a negative interface count")
        if len(self.interface_endpoints) != self.interface_count:
            raise ValueError("CMIR interface endpoint count mismatch")
        if len(set(self.interface_endpoints)) != self.interface_count:
            raise ValueError("CMIR contains duplicate interfaces")
        for first, second in self.interface_endpoints:
            if not (0 <= first < second < self.leaf_count):
                raise ValueError("CMIR interface endpoints are invalid")
        if len({candidate.id for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate macro id")
        if tuple(candidate.registry_index for candidate in self.candidates) != tuple(
            range(len(self.candidates))
        ):
            raise ValueError("CMIR registry indices must be contiguous")
        atomic = [candidate for candidate in self.candidates
                  if candidate.kind is MacroKind.ATOMIC_FALLBACK]
        if len(atomic) != self.leaf_count:
            raise ValueError("CMIR requires one atomic fallback per core cell")
        atomic_cover = 0
        for candidate in atomic:
            if candidate.cell_count != 1:
                raise ValueError("atomic fallback owns more than one core cell")
            atomic_cover |= candidate.core_bits
        if atomic_cover != (1 << self.leaf_count) - 1:
            raise ValueError("atomic fallback does not cover every core cell")
        count = len(self.candidates)
        for candidate in self.candidates:
            candidate.validate(
                leaf_count=self.leaf_count,
                interface_count=self.interface_count,
                candidate_count=count,
            )
            expected_interfaces = tuple(
                interface_id
                for interface_id, (first, second) in enumerate(
                    self.interface_endpoints
                )
                if bool(candidate.core_bits & (1 << first))
                != bool(candidate.core_bits & (1 << second))
            )
            if tuple(sorted(set(candidate.boundary_interfaces))) != expected_interfaces:
                raise ValueError(
                    "macro interface claims do not match its exact core boundary"
                )
            for other_index in iter_set_bits(candidate.conflict_bits):
                other = self.candidates[other_index]
                if not (other.conflict_bits & (1 << candidate.registry_index)):
                    raise ValueError("macro conflict relation is not symmetric")
                if not (candidate.core_bits & other.core_bits):
                    raise ValueError("phase-2 conflict lacks shared core ownership")
        expected_hash = registry_digest(
            self.candidates, self.interface_endpoints,
        )
        if self.registry_hash != expected_hash:
            raise ValueError("CMIR registry hash mismatch")


def iter_set_bits(bits: int) -> Iterable[int]:
    value = int(bits)
    while value:
        low = value & -value
        yield low.bit_length() - 1
        value ^= low


def stable_macro_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), default=str,
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:16]}"


def registry_digest(
    candidates: Iterable[MacroCandidate],
    interface_endpoints: Iterable[tuple[int, int]] = (),
) -> str:
    digest = hashlib.sha256()
    digest.update(b"pcdc-cmir-registry+interfaces/v2\n")
    for first, second in interface_endpoints:
        digest.update(f"i:{int(first)}:{int(second)}\n".encode("ascii"))
    for candidate in candidates:
        digest.update(candidate.id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(candidate.core_bits).encode("ascii"))
        digest.update(b"\0")
        digest.update(
            (
                f"{candidate.alpha_bounds[0]:.9g},"
                f"{candidate.alpha_bounds[1]:.9g}"
            ).encode("ascii")
        )
        digest.update(b"\0")
        digest.update(
            ",".join(map(str, candidate.boundary_interfaces)).encode("ascii")
        )
        digest.update(b"\0")
        digest.update(str(candidate.conflict_bits).encode("ascii"))
        digest.update(b"\0")
        digest.update(
            candidate.proof_bundle.digest.encode("ascii")
            if candidate.proof_bundle is not None else b"uncertified"
        )
        digest.update(b"\n")
    return digest.hexdigest()
