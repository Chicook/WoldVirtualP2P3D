"""Subpaquete RF_EN_SBRTM_RFEN1_RN_1: neurona Q-Learning (RF_EN · SBRTM)."""

try:
    from .RF_EN_SBRTM_RFEN1_RN_1_1 import NeuronaRefuerzoQLearning
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_1_1",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_1_1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaRefuerzoQLearning = _mod.NeuronaRefuerzoQLearning

__all__ = ["NeuronaRefuerzoQLearning"]
