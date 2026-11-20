"""Subpaquete EN6: neurona de entrada con Dropout (RN1)."""

from .sbrtm_EN6_RN1 import (
    LUCIA_CONFIG,
    NeuronaEntradaBase,
    NeuronaEntradaDropout,
    _DTYPE_MAP,
    _dtype,
    _now,
    actualizar_config,
)

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaDropout",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]
