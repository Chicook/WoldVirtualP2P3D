"""Subpaquete SBRTM_EN1_RN: neurona de entrada densa y herramientas (EN1)."""

try:
    from .sbrtm_EN1_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaBasica,
        _DTYPE_MAP,
        _dtype,
        _now,
    )
    from .sbrtm_EN1_RN2 import NeuronaHerramientas
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))

    def _cargar(_nombre):
        _spec = _ilu.spec_from_file_location(
            _nombre, _os.path.join(_base, _nombre + ".py"))
        _modulo = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_modulo)
        return _modulo

    _rn1 = _cargar("sbrtm_EN1_RN1")
    _rn2 = _cargar("sbrtm_EN1_RN2")
    LUCIA_CONFIG = _rn1.LUCIA_CONFIG
    NeuronaEntradaBase = _rn1.NeuronaEntradaBase
    NeuronaEntradaBasica = _rn1.NeuronaEntradaBasica
    _DTYPE_MAP = _rn1._DTYPE_MAP
    _dtype = _rn1._dtype
    _now = _rn1._now
    NeuronaHerramientas = _rn2.NeuronaHerramientas

__all__ = [
    "LUCIA_CONFIG",
    "NeuronaEntradaBase",
    "NeuronaEntradaBasica",
    "NeuronaHerramientas",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]
