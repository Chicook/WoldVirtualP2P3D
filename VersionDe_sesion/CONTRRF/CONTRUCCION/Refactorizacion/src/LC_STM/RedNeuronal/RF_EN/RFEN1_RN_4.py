"""RFEN1_RN_4.py - Neurona de Refuerzo con DQN (refactor eficiente)."""
import numpy as np
import math
import time
import logging
from typing import Tuple, Optional, Dict, Any, List

try:
    from ._rfen_base import (
        LUCIA_RL_CONFIG,
        _dt,
        NeuronaRefuerzoBase,
        InicializadoresRL,
        inicializar_pesos_he,
        inicializar_pesos_xavier,
        inicializar_pesos_lecun,
        inicializar_pesos_ortogonal,
        inicializar_pesos_espectral,
        _Ring,
    )
except ImportError:
    import importlib.util as _ilu_base
    import os as _os_base

    _base_path = _os_base.path.join(
        _os_base.path.dirname(_os_base.path.abspath(__file__)),
        "_rfen_base.py",
    )
    _spec_base = _ilu_base.spec_from_file_location("RF_EN_rfen_base", _base_path)
    if _spec_base and _spec_base.loader:
        _mod_base = _ilu_base.module_from_spec(_spec_base)
        _spec_base.loader.exec_module(_mod_base)
        LUCIA_RL_CONFIG = _mod_base.LUCIA_RL_CONFIG
        _dt = _mod_base._dt
        NeuronaRefuerzoBase = _mod_base.NeuronaRefuerzoBase
        InicializadoresRL = _mod_base.InicializadoresRL
        inicializar_pesos_he = _mod_base.inicializar_pesos_he
        inicializar_pesos_xavier = _mod_base.inicializar_pesos_xavier
        inicializar_pesos_lecun = _mod_base.inicializar_pesos_lecun
        inicializar_pesos_ortogonal = _mod_base.inicializar_pesos_ortogonal
        inicializar_pesos_espectral = _mod_base.inicializar_pesos_espectral
        _Ring = _mod_base._Ring
    else:
        raise ImportError(f"No se pudo cargar _rfen_base desde {_base_path}")

try:
    from .RF_EN_SBRTM_RFEN1_RN_4.RF_EN_SBRTM_RFEN1_RN_4_1 import (
        NeuronaRefuerzoDQN,
        ReplayBuffer,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _sbrtm4_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_4",
        "RF_EN_SBRTM_RFEN1_RN_4_1.py",
    )
    _spec4 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_4_1", _sbrtm4_path)
    if _spec4 and _spec4.loader:
        _mod4 = _ilu.module_from_spec(_spec4)
        _spec4.loader.exec_module(_mod4)
        NeuronaRefuerzoDQN = _mod4.NeuronaRefuerzoDQN
        ReplayBuffer = _mod4.ReplayBuffer
    else:
        raise ImportError(f"No se pudo cargar RF_EN_SBRTM_RFEN1_RN_4_1 desde {_sbrtm4_path}")

logger = logging.getLogger('RFENRN1.RFEN1_RN_4')


def crear_neurona_dqn(input_size: int, output_size: int,
                      configuracion: Optional[Dict[str, Any]] = None) -> NeuronaRefuerzoDQN:
    cfg = configuracion or {}
    return NeuronaRefuerzoDQN(
        input_size=input_size,
        output_size=output_size,
        nombre=cfg.get('nombre', 'NeuronaRefuerzoDQN'),
        learning_rate=cfg.get('learning_rate', 0.001),
        gamma=cfg.get('gamma', 0.99),
        epsilon=cfg.get('epsilon', 0.2),
        usar_doble=cfg.get('usar_doble', True),
    )


def analizar_dqn(neurona: NeuronaRefuerzoDQN) -> Dict[str, Any]:
    return {
        'estadisticas': neurona.obtener_estadisticas_dqn(),
        'estable': neurona.verificar_estabilidad(),
    }


RFEN4_CONFIG = {
    'inicializacion_preferida': 'he',
    'learning_rate_default': 0.001,
    'gamma_default': 0.99,
    'epsilon_default': 0.2,
    'doble_default': True,
    'sync_default': 100,
    'batch_default': 32,
    'umbral_convergencia': 0.7,
}

logger.info("RFEN1_RN_4.py cargado correctamente - Neurona de Refuerzo DQN")
