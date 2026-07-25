"""Exact rendering of a materialization fragment (plan S5, S8.2).

The court and the exporter must agree on the delivered pixels, so both go
through this module: a fragment is wrapped in a canonical document, rendered
by the production renderer, and the result is digest-bound.  Nothing here
chooses geometry; it only renders what a program already decided.

Kept dependency-light on purpose: ``export_writer`` imports the compiler's
materialization stack, so the renderer must not import ``export_writer``.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .vector_program import (
    TextVectorProgram,
    fragment_to_document,
    serialize_text_vector_program,
)

RENDERER_VERSION = "resvg_py/document-roundtrip/1"


@dataclass(frozen=True)
class ExactFragmentRender:
    fragment: str
    fragment_sha256: str
    rgba: np.ndarray            # (H, W, 4) uint8, straight sRGB
    rgba_sha256: str
    width: int
    height: int
    supersample: int

    @property
    def alpha_mask(self) -> np.ndarray:
        return np.asarray(self.rgba[..., 3] >= 128, bool)


def render_document(svg: str, *, width: int) -> np.ndarray:
    """Production renderer roundtrip: (H, W, 4) uint8 straight sRGB."""
    import resvg_py

    payload = resvg_py.svg_to_bytes(svg_string=svg, width=int(width))
    with io.BytesIO(bytes(payload)) as stream:
        with Image.open(stream) as rendered:
            with rendered.convert("RGBA") as converted:
                return np.asarray(converted).copy()


def render_fragment(
    fragment: str, *, width: int, height: int, supersample: int = 1,
) -> ExactFragmentRender:
    """Render a fragment exactly; supersample renders at N× canvas width."""
    factor = max(1, int(supersample))
    document = fragment_to_document(fragment, width=width, height=height)
    rgba = render_document(document, width=int(width) * factor)
    return ExactFragmentRender(
        fragment=fragment,
        fragment_sha256=hashlib.sha256(fragment.encode("utf-8")).hexdigest(),
        rgba=rgba,
        rgba_sha256=hashlib.sha256(
            np.ascontiguousarray(rgba).tobytes(),
        ).hexdigest(),
        width=int(rgba.shape[1]), height=int(rgba.shape[0]),
        supersample=factor,
    )


def render_program(
    program: TextVectorProgram, *, width: int, height: int,
    supersample: int = 1,
) -> ExactFragmentRender:
    """Render the program's own serialization - never a re-derived string."""
    fragment = serialize_text_vector_program(program)
    if program.exact_fragment_sha256:
        digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
        if digest != program.exact_fragment_sha256:
            raise ValueError(
                "program fragment digest does not match its serialization",
            )
    return render_fragment(
        fragment, width=width, height=height, supersample=supersample,
    )
