"""CELEBRO - orquestacion e integracion neuronal (BLOK1).

Expone de forma perezosa ``BLOK1`` y sus clases principales para no cargar
las 20 redes de ENRN/RF_EN ni el servidor hasta que se soliciten.
"""

from __future__ import annotations

import importlib
from typing import Any, List

__version__ = "2026.1.0"
__author__ = "WoldVirtualP2P3D Team"

_SUBMODULOS = ("BLOK1",)


def __getattr__(nombre: str) -> Any:
    if nombre == "BLOK1":
        return importlib.import_module(f"{__name__}.BLOK1")
    if nombre in ("BaseNeuronal1", "ServidorNeuronal"):
        bloque = importlib.import_module(f"{__name__}.BLOK1")
        return getattr(bloque, nombre)
    raise AttributeError(
        f"El paquete {__name__!r} no tiene el atributo {nombre!r}"
    )


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_SUBMODULOS))


__all__ = [
    'BLOK1',
    'BaseNeuronal1',
    'ServidorNeuronal',
    '__version__',
    '__author__',
]
