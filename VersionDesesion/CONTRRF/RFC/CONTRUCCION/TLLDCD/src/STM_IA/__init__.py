"""STM_IA — sección oficial ``STM_Informacion`` (modelos y conocimiento)."""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent
_SECCION = _DIR / "STM_Informacion"
__path__ = [str(_SECCION)] + list(__path__) if _SECCION.is_dir() else list(__path__)
