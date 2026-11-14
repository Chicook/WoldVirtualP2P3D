"""Subpaquete SBTM_EN4_RN: neurona de entrada normalizada (EN4/RN1).

Modulos registrados:
  - sbrtm_EN4_RN1 : NeuronaEntradaBase, NeuronaEntradaNormalizada,
                    LUCIA_CONFIG, _dtype, _now
"""

try:
    from .sbrtm_EN4_RN1 import (
        NeuronaEntradaBase,
        NeuronaEntradaNormalizada,
        LUCIA_CONFIG,
        _dtype,
        _now,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "sbrtm_EN4_RN1", _os.path.join(_base, "sbrtm_EN4_RN1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaEntradaBase = _mod.NeuronaEntradaBase
    NeuronaEntradaNormalizada = _mod.NeuronaEntradaNormalizada
    LUCIA_CONFIG = _mod.LUCIA_CONFIG
    _dtype = _mod._dtype
    _now = _mod._now

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaNormalizada",
    "LUCIA_CONFIG",
    "_dtype",
    "_now",
]
