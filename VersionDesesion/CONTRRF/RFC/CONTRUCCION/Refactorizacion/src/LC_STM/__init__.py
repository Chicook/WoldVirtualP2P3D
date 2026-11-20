"""LC_STM - nucleo de la red neuronal del sistema WoldVirtual P2P3D.

Punto de entrada del paquete. La red neuronal completa vive en
``LC_STM.RedNeuronal`` y se importa de forma perezosa para no cargar todos
los subpaquetes (ENRN, RF_EN, RF_SL, RNP, SLRN, CELEBRO) al importar LC_STM.
"""

from __future__ import annotations

from typing import Any, List

__version__ = "2026.1.0"
__author__ = "WoldVirtualP2P3D Team"

_SUBMODULOS = ("RedNeuronal", "red_neuronal", "LCBS_NEURONAL", "LCBS")


def __getattr__(nombre: str) -> Any:
    if nombre in ("RedNeuronal", "red_neuronal"):
        import importlib

        return importlib.import_module(f"{__name__}.RedNeuronal")
    if nombre in ("LCBS_NEURONAL", "LCBS"):
        import importlib

        return importlib.import_module(f"{__name__}.LCBS_NEURONAL")
    if nombre == "RedNeuronalCompleta":
        import importlib

        return importlib.import_module(
            f"{__name__}.LCBS_NEURONAL"
        ).RedNeuronal
    raise AttributeError(
        f"El modulo {__name__!r} no tiene el atributo {nombre!r}"
    )


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_SUBMODULOS))


__all__ = [
    "RedNeuronal",
    "red_neuronal",
    "LCBS_NEURONAL",
    "LCBS",
    "RedNeuronalCompleta",
    "__version__",
    "__author__",
]
