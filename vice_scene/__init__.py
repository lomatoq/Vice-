"""Scene-first inverse-graphics engine for V-ICE.

The legacy geometry vectorizer remains available as a proposal generator and
fallback.  This package owns the canonical raster/scene contracts and never
imports the legacy monolith at module import time.
"""

from .config import EngineConfig
from .pipeline import process_scene

__all__ = ["EngineConfig", "process_scene"]
__version__ = "0.1.0"
