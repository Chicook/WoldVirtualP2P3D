"""Subpaquete RF_EN_SBRTM_RFEN1_RN_2: Policy Gradient + comunicación (RF_EN · SBRTM)."""

try:
    from .RF_EN_SBRTM_RFEN1_RN_2_1 import (
        NeuronaRefuerzoPolicyGradient,
        NeuronaDeComunicacionPolicyGradient,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_2_1",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_2_1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaRefuerzoPolicyGradient = _mod.NeuronaRefuerzoPolicyGradient
    NeuronaDeComunicacionPolicyGradient = _mod.NeuronaDeComunicacionPolicyGradient

__all__ = ["NeuronaRefuerzoPolicyGradient", "NeuronaDeComunicacionPolicyGradient"]
