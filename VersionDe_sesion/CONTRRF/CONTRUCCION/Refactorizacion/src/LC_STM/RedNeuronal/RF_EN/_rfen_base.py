"""_rfen_base.py - Base compartida e inicializadores para el paquete RF_EN.

Centraliza:
- LUCIA_RL_CONFIG
- _dt
- NeuronaRefuerzoBase
- InicializadoresRL y funciones inicializar_pesos_*
- _Ring buffer

Las utilidades viven en RF_EN__rfen_base_SBRTM; este módulo las reexporta
junto con las funciones adicionales (actualizar_config, inicializar_pesos_eficiente).
"""
import logging

try:
    from .RF_EN__rfen_base_SBRTM import (
        LUCIA_RL_CONFIG,
        _DTYPE,
        _dt,
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
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_rfen_base1",
        _os.path.join(_base, "RF_EN__rfen_base_SBRTM", "RF_EN_SBRTM_rfen_base1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LUCIA_RL_CONFIG = _mod.LUCIA_RL_CONFIG
    _DTYPE = _mod._DTYPE
    _dt = _mod._dt
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

logger = logging.getLogger(__name__)

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
