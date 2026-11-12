"""Subpaquete RF_EN_SBRTM_RFEN1_RN_8: Twin Delayed DDPG (TD3) (RF_EN · SBRTM)."""
try:
    from .RF_EN_SBRTM_RFEN1_RN_8_1 import NeuronaRefuerzoTD3
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_8_1",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_8_1.py"),
    )
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        NeuronaRefuerzoTD3 = _mod.NeuronaRefuerzoTD3
    else:
        NeuronaRefuerzoTD3 = None

__all__ = ["NeuronaRefuerzoTD3"]
