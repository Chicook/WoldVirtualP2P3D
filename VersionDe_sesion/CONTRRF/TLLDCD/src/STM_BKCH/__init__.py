"""STM_BKCH — sección oficial ``stm_bkch1`` (blockchain BKSVCB)."""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent
_SECCION = _DIR / "stm_bkch1"
__path__ = [str(_SECCION)] + list(__path__) if _SECCION.is_dir() else list(__path__)
