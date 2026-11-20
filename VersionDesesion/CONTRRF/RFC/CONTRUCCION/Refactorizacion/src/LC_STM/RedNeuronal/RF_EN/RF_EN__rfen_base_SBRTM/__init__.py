"""Subpaquete RF_EN__rfen_base_SBRTM: base e inicializadores de las neuronas RF."""

try:
    from .RF_EN_SBRTM_rfen_base1 import (
        LUCIA_RL_CONFIG,
        actualizar_config,
        NeuronaRefuerzoBase,
        InicializadoresRL,
        inicializar_pesos_he,
        inicializar_pesos_xavier,
        inicializar_pesos_lecun,
        inicializar_pesos_ortogonal,
        inicializar_pesos_espectral,
        inicializar_pesos_eficiente,
        _Ring,
        _dt,
        _DTYPE,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_rfen_base1", _os.path.join(_base, "RF_EN_SBRTM_rfen_base1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LUCIA_RL_CONFIG = _mod.LUCIA_RL_CONFIG
    actualizar_config = _mod.actualizar_config
    NeuronaRefuerzoBase = _mod.NeuronaRefuerzoBase
    InicializadoresRL = _mod.InicializadoresRL
    inicializar_pesos_he = _mod.inicializar_pesos_he
    inicializar_pesos_xavier = _mod.inicializar_pesos_xavier
    inicializar_pesos_lecun = _mod.inicializar_pesos_lecun
    inicializar_pesos_ortogonal = _mod.inicializar_pesos_ortogonal
    inicializar_pesos_espectral = _mod.inicializar_pesos_espectral
    inicializar_pesos_eficiente = _mod.inicializar_pesos_eficiente
    _Ring = _mod._Ring
    _dt = _mod._dt
    _DTYPE = _mod._DTYPE

__all__ = [
    "LUCIA_RL_CONFIG",
    "actualizar_config",
    "NeuronaRefuerzoBase",
    "InicializadoresRL",
    "inicializar_pesos_he",
    "inicializar_pesos_xavier",
    "inicializar_pesos_lecun",
    "inicializar_pesos_ortogonal",
    "inicializar_pesos_espectral",
    "inicializar_pesos_eficiente",
    "_Ring",
    "_dt",
    "_DTYPE",
]
