"""Subpaquete EN5: neurona de entrada con regularizacion L1/L2/elastica (RN1)."""

from .sbrtm_EN5_RN1 import (
    LUCIA_CONFIG,
    NeuronaEntradaBase,
    NeuronaEntradaRegularizada,
    _DTYPE_MAP,
    _dtype,
    _now,
    actualizar_config,
)

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaRegularizada",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]
