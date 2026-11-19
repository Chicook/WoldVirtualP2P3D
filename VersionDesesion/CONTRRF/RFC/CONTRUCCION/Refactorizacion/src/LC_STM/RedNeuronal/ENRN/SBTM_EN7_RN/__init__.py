"""Subpaquete EN7: neurona de entrada con BatchNorm (RN1)."""

from .sbrtm_EN7_RN1 import (
    LUCIA_CONFIG,
    NeuronaEntradaBase,
    NeuronaEntradaBatchNorm,
    _DTYPE_MAP,
    _dtype,
    _now,
    actualizar_config,
)

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaBatchNorm",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]
