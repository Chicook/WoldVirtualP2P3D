"""Subpaquete SBTM_EN2_RN: neurona de entrada Xavier unificada (EN2).

Modulos registrados:
  - sbrtm_EN2_RN1 : NeuronaEntradaBase, NeuronaEntradaXavier, LUCIA_CONFIG,
                    _dtype, _now
  - sbrtm_EN2_RN2 : NeuronaCreativa
"""

# ---------------------------------------------------------------------------
# sbrtm_EN2_RN1 : base Xavier + helpers de tipo/tiempo
# ---------------------------------------------------------------------------
try:
    from .sbrtm_EN2_RN1 import (
        NeuronaEntradaBase,
        NeuronaEntradaXavier,
        LUCIA_CONFIG,
        _dtype,
        _now,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        'sbrtm_EN2_RN1', _os.path.join(_base, 'sbrtm_EN2_RN1.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaEntradaBase = _mod.NeuronaEntradaBase
    NeuronaEntradaXavier = _mod.NeuronaEntradaXavier
    LUCIA_CONFIG = _mod.LUCIA_CONFIG
    _dtype = _mod._dtype
    _now = _mod._now

# ---------------------------------------------------------------------------
# sbrtm_EN2_RN2 : NeuronaCreativa (matematica Xavier + maquina RFPRMN)
# ---------------------------------------------------------------------------
try:
    from .sbrtm_EN2_RN2 import NeuronaCreativa
except ImportError:
    import importlib.util as _ilu2
    import os as _os2
    _base2 = _os2.path.dirname(_os2.path.abspath(__file__))
    _spec2 = _ilu2.spec_from_file_location(
        'sbrtm_EN2_RN2', _os2.path.join(_base2, 'sbrtm_EN2_RN2.py'))
    _mod2 = _ilu2.module_from_spec(_spec2)
    _spec2.loader.exec_module(_mod2)
    NeuronaCreativa = _mod2.NeuronaCreativa

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaXavier",
    "LUCIA_CONFIG",
    "_dtype",
    "_now",
    "NeuronaCreativa",
]
