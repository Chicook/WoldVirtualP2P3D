"""Subpaquete SBTM_EN3_RN: neurona de entrada LeCun (EN3).

Modulos registrados:
  - sbrtm_EN3_RN1 : NeuronaEntradaBase, NeuronaEntradaLeCun, LUCIA_CONFIG,
                    _dtype, _now
  - sbrtm_EN3_RN2 : NeuronaCodigo (matematica LeCun + maquina RFPRMN)
"""

# ---------------------------------------------------------------------------
# sbrtm_EN3_RN1 : base LeCun + helpers de tipo/tiempo
# ---------------------------------------------------------------------------
try:
    from .sbrtm_EN3_RN1 import (
        NeuronaEntradaBase,
        NeuronaEntradaLeCun,
        LUCIA_CONFIG,
        _dtype,
        _now,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "sbrtm_EN3_RN1", _os.path.join(_base, "sbrtm_EN3_RN1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaEntradaBase = _mod.NeuronaEntradaBase
    NeuronaEntradaLeCun = _mod.NeuronaEntradaLeCun
    LUCIA_CONFIG = _mod.LUCIA_CONFIG
    _dtype = _mod._dtype
    _now = _mod._now

# ---------------------------------------------------------------------------
# sbrtm_EN3_RN2 : NeuronaCodigo (matematica LeCun + maquina RFPRMN)
# ---------------------------------------------------------------------------
try:
    from .sbrtm_EN3_RN2 import NeuronaCodigo
except ImportError:
    import importlib.util as _ilu2
    import os as _os2
    _base2 = _os2.path.dirname(_os2.path.abspath(__file__))
    _spec2 = _ilu2.spec_from_file_location(
        "sbrtm_EN3_RN2", _os2.path.join(_base2, "sbrtm_EN3_RN2.py"))
    _mod2 = _ilu2.module_from_spec(_spec2)
    _spec2.loader.exec_module(_mod2)
    NeuronaCodigo = _mod2.NeuronaCodigo

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaLeCun",
    "LUCIA_CONFIG",
    "_dtype",
    "_now",
    "NeuronaCodigo",
]
