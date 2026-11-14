"""SBSTM — paquete raíz de las secciones STM_SBTM_1/2/3.

Mantiene compatibilidad con las rutas históricas ``SBSTM.<modulo>``: el
``__path__`` del paquete incluye las tres secciones, de modo que
``SBSTM.accesores`` o ``SBSTM.memoria_sesion`` siguen resolviendo al archivo
correcto aunque vivan en una subsección.
"""
from __future__ import annotations

from .STM_SBTM_1 import *  # noqa: E402,F401,F403
from .STM_SBTM_1 import (  # noqa: E402,F401
    __author__,
    __status__,
    __version__,
)
