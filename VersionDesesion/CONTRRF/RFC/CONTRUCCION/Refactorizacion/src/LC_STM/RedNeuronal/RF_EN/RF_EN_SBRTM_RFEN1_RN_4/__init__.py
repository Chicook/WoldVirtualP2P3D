"""Subpaquete RF_EN_SBRTM_RFEN1_RN_4: Deep Q-Network (DQN) y Replay Buffer (RF_EN · SBRTM)."""

try:
    from .RF_EN_SBRTM_RFEN1_RN_4_1 import (
        NeuronaRefuerzoDQN,
        ReplayBuffer,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_4_1",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_4_1.py"),
    )
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        NeuronaRefuerzoDQN = _mod.NeuronaRefuerzoDQN
        ReplayBuffer = _mod.ReplayBuffer
    else:
        NeuronaRefuerzoDQN = None  # type: ignore[assignment]
        ReplayBuffer = None  # type: ignore[assignment]

__all__ = [
    "NeuronaRefuerzoDQN",
    "ReplayBuffer",
]
