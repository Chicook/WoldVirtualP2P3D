"""STM_JSON — sección oficial ``STM_LC`` (registro JSON de LucIA)."""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent
_SECCION = _DIR / "STM_LC"
__path__ = [str(_SECCION)] + list(__path__) if _SECCION.is_dir() else list(__path__)
