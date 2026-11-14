"""RFEN1_RN_9.py - Neurona de Refuerzo Rainbow DQN (refactor modular).

Delega la logica interna, Dueling, C51, PER y Noisy Networks a:
  RF_EN_SBRTM_RFEN1_RN_9/RF_EN_SBRTM_RFEN1_RN_9_1.py
    -> NeuronaRefuerzoRainbowDQN (con BufferPriorizadoRainbow y MotorCalculoRainbow)
"""
import numpy as np
import math
import logging
from typing import Tuple, Optional, Dict, Any, List
from collections import deque
import random

# ---------------------------------------------------------------------------
# Base compartida (_rfen_base)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Submodulo especializado RN_9: NeuronaRefuerzoRainbowDQN
# ---------------------------------------------------------------------------
try:
    from .RF_EN_SBRTM_RFEN1_RN_9.RF_EN_SBRTM_RFEN1_RN_9_1 import (
        NeuronaRefuerzoRainbowDQN,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _sbrtm9_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_9",
        "RF_EN_SBRTM_RFEN1_RN_9_1.py",
    )
    _spec9 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_9_1", _sbrtm9_path)
    if _spec9 and _spec9.loader:
        _mod9 = _ilu.module_from_spec(_spec9)
        _spec9.loader.exec_module(_mod9)
        NeuronaRefuerzoRainbowDQN = _mod9.NeuronaRefuerzoRainbowDQN
    else:
        raise ImportError(
            f"No se pudo cargar RF_EN_SBRTM_RFEN1_RN_9_1 desde {_sbrtm9_path}"
        )

logger = logging.getLogger('RFENRN1.RFEN1_RN_9')

# ---------------------------------------------------------------------------
# Funciones de fabrica y utilidad del modulo
# ---------------------------------------------------------------------------

def crear_neurona_rainbow_dqn(input_size: int, output_size: int,
                              configuracion: Optional[Dict[str, Any]] = None) -> NeuronaRefuerzoRainbowDQN:
    """Crea y devuelve una instancia configurada de NeuronaRefuerzoRainbowDQN."""
    c = configuracion or {}
    return NeuronaRefuerzoRainbowDQN(
        input_size=input_size,
        output_size=output_size,
        nombre=c.get('nombre', 'NeuronaRefuerzoRainbowDQN'),
        learning_rate=c.get('learning_rate', 0.00025),
        gamma=c.get('gamma', 0.99),
        epsilon=c.get('epsilon', 0.1),
        epsilon_decay=c.get('epsilon_decay', 0.995),
        epsilon_min=c.get('epsilon_min', 0.01),
        tau=c.get('tau', 0.005),
        buffer_size=c.get('buffer_size', 1000000),
        batch_size=c.get('batch_size', 32),
        usar_he=c.get('usar_he', True),
        usar_dueling=c.get('usar_dueling', True),
        usar_prioritized=c.get('usar_prioritized', True),
        usar_multi_step=c.get('usar_multi_step', True),
        usar_distributional=c.get('usar_distributional', True),
        usar_noisy=c.get('usar_noisy', True),
        n_atoms=c.get('n_atoms', 51),
        v_min=c.get('v_min', -10.0),
        v_max=c.get('v_max', 10.0),
        n_steps=c.get('n_steps', 3),
        alpha_prioritized=c.get('alpha_prioritized', 0.6),
        beta_prioritized=c.get('beta_prioritized', 0.4),
    )


# ---------------------------------------------------------------------------
# Configuracion publica del modulo
# ---------------------------------------------------------------------------
RFEN9_CONFIG: Dict[str, Any] = {
    'inicializacion_preferida': 'he',
    'learning_rate_default': 0.00025,
    'gamma_default': 0.99,
    'epsilon_default': 0.1,
    'epsilon_decay_default': 0.995,
    'epsilon_min_default': 0.01,
    'tau_default': 0.005,
    'buffer_size_default': 1000000,
    'batch_size_default': 32,
    'usar_dueling_default': True,
    'usar_prioritized_default': True,
    'usar_multi_step_default': True,
    'usar_distributional_default': True,
    'usar_noisy_default': True,
    'n_atoms_default': 51,
    'v_min_default': -10.0,
    'v_max_default': 10.0,
    'n_steps_default': 3,
    'alpha_prioritized_default': 0.6,
    'beta_prioritized_default': 0.4,
    'umbral_convergencia': 0.8,
    'umbral_estabilidad': 0.7,
}

logger.info("RFEN1_RN_9.py cargado - Rainbow DQN Multi-Metodo [delegado a RF_EN_SBRTM_RFEN1_RN_9_1]")
