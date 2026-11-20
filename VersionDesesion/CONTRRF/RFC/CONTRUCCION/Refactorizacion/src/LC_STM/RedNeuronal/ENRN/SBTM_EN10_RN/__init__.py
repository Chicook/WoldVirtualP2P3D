"""Subpaquete EN10: neurona de entrada con activacion Sigmoide (RN1)."""

from .sbrtm_EN10_RN1 import (
    LUCIA_CONFIG,
    NeuronaEntradaBase,
    NeuronaEntradaSigmoid,
    _DTYPE_MAP,
    _dtype,
    _now,
    actualizar_config,
)

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaSigmoid",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]
