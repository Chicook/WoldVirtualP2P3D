"""SBSTM — paquete raíz de las secciones STM_SBTM_1/2/3.

Mantiene compatibilidad con las rutas históricas ``SBSTM.<modulo>``: el
``__path__`` del paquete incluye las tres secciones, de modo que
``SBSTM.accesores`` o ``SBSTM.memoria_sesion`` siguen resolviendo al archivo
correcto aunque vivan en una subsección.
"""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent
_SECCIONES = ("STM_SBTM_1", "STM_SBTM_2", "STM_SBTM_3")
__path__ = [str(_DIR / seccion) for seccion in _SECCIONES
            if (_DIR / seccion).is_dir()] + list(__path__)

from .STM_SBTM_1 import *  # noqa: E402,F401,F403
from .STM_SBTM_1 import (  # noqa: E402,F401
    __author__,
    __status__,
    __version__,
)
