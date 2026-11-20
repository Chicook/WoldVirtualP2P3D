"""Subpaquete EN9: neurona de entrada con activacion Tanh (RN1)."""

from .sbrtm_EN9_RN1 import (
    LUCIA_CONFIG,
    NeuronaEntradaBase,
    NeuronaEntradaTanh,
    _DTYPE_MAP,
    _dtype,
    _now,
    actualizar_config,
)

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaTanh",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]
