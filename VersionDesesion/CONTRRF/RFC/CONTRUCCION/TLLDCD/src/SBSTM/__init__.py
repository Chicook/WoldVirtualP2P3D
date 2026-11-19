"""SBSTM — paquete raíz; la sección oficial vive en ``SistemasLC``.

El ``__path__`` incluye ``SistemasLC`` y sus tres secciones para que las rutas
históricas ``SBSTM.<modulo>`` y ``SBSTM.STM_SBTM_n`` sigan funcionando.
"""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent
_SISTEMAS = _DIR / "SistemasLC"
_SECCIONES = (
    _SISTEMAS,
    _SISTEMAS / "STM_SBTM_1",
    _SISTEMAS / "STM_SBTM_2",
    _SISTEMAS / "STM_SBTM_3",
)
__path__ = [str(p) for p in _SECCIONES if p.is_dir()] + list(__path__)

from .SistemasLC import *  # noqa: E402,F401,F403
from .SistemasLC import (  # noqa: E402,F401
    __author__,
    __status__,
    __version__,
)
