"""Subpaquete EN8: neurona de entrada con activacion ReLU y variantes (RN1)."""

from .sbrtm_EN8_RN1 import (
    LUCIA_CONFIG,
    NeuronaEntradaBase,
    NeuronaEntradaReLU,
    _DTYPE_MAP,
    _dtype,
    _now,
    actualizar_config,
)

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaReLU",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]
