"""Subpaquete RF_EN_SBRTM_RFEN1_RN_9: Rainbow DQN Multi-Metodo (RF_EN · SBRTM)."""
try:
    from .RF_EN_SBRTM_RFEN1_RN_9_1 import NeuronaRefuerzoRainbowDQN
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_9_1",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_9_1.py"),
    )
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        NeuronaRefuerzoRainbowDQN = _mod.NeuronaRefuerzoRainbowDQN
    else:
        NeuronaRefuerzoRainbowDQN = None

__all__ = ["NeuronaRefuerzoRainbowDQN"]
