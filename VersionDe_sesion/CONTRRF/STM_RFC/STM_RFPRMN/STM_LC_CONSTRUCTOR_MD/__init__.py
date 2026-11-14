"""Paquete STM_LC_CONSTRUCTOR_MD: constructor de jerarquías para LucIA.

La API se expone de forma perezosa (PEP 562): importar el paquete no carga
``STM_MD1`` hasta que se pide uno de sus símbolos. Así se evitan importaciones
circulares y el aviso de ``runpy`` al ejecutar ``python -m ...STM_MD1``.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ConstructorJerarquia",
    "SUBCARPETAS_SRC",
    "SUBCARPETAS_SRC_BASE",
    "RUTA_FUENTE_PREDETERMINADA",
    "NOMBRE_PREDETERMINADO",
    "DIM_ENTRADA",
    "DIM_SALIDA",
    "descubrir_subcarpetas_src",
    "descubrir_jerarquia_src",
    "cargar_modulo_red",
    "cargar_lcbs_neuronal",
    "localizar_red_neuronal",
    "localizar_lcbs_neuronal",
    "obtener_clase_constructiva",
    "silencio",
    "crear_jerarquia",
]


def __getattr__(nombre: str) -> Any:
    """Resuelve los símbolos públicos desde ``STM_MD1`` bajo demanda."""
    if nombre in __all__:
        from . import STM_MD1

        return getattr(STM_MD1, nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def __dir__() -> list[str]:
    """Lista los símbolos públicos del paquete."""
    return sorted(__all__)
