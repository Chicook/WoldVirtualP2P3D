"""Paquete STM_LC_CONSTRUCTOR_MD: constructor y parser de LucIA.

La API se expone de forma perezosa (PEP 562): importar el paquete no carga
``STM_MD1`` ni ``STM_MD2`` hasta que se pide uno de sus símbolos. Así se
evitan importaciones circulares y el aviso de ``runpy`` al ejecutar
``python -m ...STM_MD1``.

- ``STM_MD1``: descubrimiento de carpetas, red neuronal y creación.
- ``STM_MD2``: interpretación de órdenes (texto, JSON o dict).
"""

from __future__ import annotations

from typing import Any

_SIMBOLOS_MD1 = frozenset({
    "ConstructorJerarquia",
    "SUBCARPETAS_SRC",
    "SUBCARPETAS_SRC_BASE",
    "RUTA_FUENTE_PREDETERMINADA",
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
})

_SIMBOLOS_MD2 = frozenset({
    "InterpreteOrden",
    "interpretar_orden",
    "COMANDO_CARPETA",
    "COMANDO_RED",
    "COMANDO_MTBGT",
    "COMANDO_TODO",
    "COMANDOS",
    "NOMBRE_PREDETERMINADO",
    "NOMBRE_RED_PREDETERMINADO",
    "NOMBRE_MTBGT_PREDETERMINADO",
    "SUBCARPETAS_RED",
    "SUBCARPETAS_MTBGT",
})

__all__ = [nombre for nombre in sorted(_SIMBOLOS_MD1 | _SIMBOLOS_MD2)]


def __getattr__(nombre: str) -> Any:
    """Resuelve los símbolos públicos bajo demanda según su módulo."""
    if nombre in _SIMBOLOS_MD1:
        from . import STM_MD1

        return getattr(STM_MD1, nombre)
    if nombre in _SIMBOLOS_MD2:
        from . import STM_MD2

        return getattr(STM_MD2, nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def __dir__() -> list[str]:
    """Lista los símbolos públicos del paquete."""
    return sorted(__all__)
