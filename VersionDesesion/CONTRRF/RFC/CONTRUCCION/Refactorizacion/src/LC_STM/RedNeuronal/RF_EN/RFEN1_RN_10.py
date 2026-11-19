"""RFEN1_RN_10.py - Neurona de Refuerzo IMPALA (refactor modular).

Delega la arquitectura distribuida Actor-Learner, V-trace y buffers multicanal a:
  RF_EN_SBRTM_RFEN1_RN_10/RF_EN_SBRTM_RFEN1_RN_10_1.py
    -> NeuronaRefuerzoIMPALA (con BufferActoresIMPALA y MotorCalculoVTrace)
"""
import numpy as np
import math
import logging
import threading
import time
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
# Submodulo especializado RN_10: NeuronaRefuerzoIMPALA
# ---------------------------------------------------------------------------
try:
    from .RF_EN_SBRTM_RFEN1_RN_10.RF_EN_SBRTM_RFEN1_RN_10_1 import (
        NeuronaRefuerzoIMPALA,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _sbrtm10_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_10",
        "RF_EN_SBRTM_RFEN1_RN_10_1.py",
    )
    _spec10 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_10_1", _sbrtm10_path)
    if _spec10 and _spec10.loader:
        _mod10 = _ilu.module_from_spec(_spec10)
        _spec10.loader.exec_module(_mod10)
        NeuronaRefuerzoIMPALA = _mod10.NeuronaRefuerzoIMPALA
    else:
        raise ImportError(
            f"No se pudo cargar RF_EN_SBRTM_RFEN1_RN_10_1 desde {_sbrtm10_path}"
        )

logger = logging.getLogger('RFENRN1.RFEN1_RN_10')

# ---------------------------------------------------------------------------
# Funciones de fabrica y utilidad del modulo
# ---------------------------------------------------------------------------

def crear_neurona_impala(input_size: int, output_size: int,
                         configuracion: Optional[Dict[str, Any]] = None) -> NeuronaRefuerzoIMPALA:
    """Crea y devuelve una instancia configurada de NeuronaRefuerzoIMPALA."""
    c = configuracion or {}
    return NeuronaRefuerzoIMPALA(
        input_size=input_size,
        output_size=output_size,
        nombre=c.get('nombre', 'NeuronaRefuerzoIMPALA'),
        learning_rate=c.get('learning_rate', 0.0003),
        gamma=c.get('gamma', 0.99),
        lambda_gae=c.get('lambda_gae', 0.95),
        num_actors=c.get('num_actors', 8),
        num_learners=c.get('num_learners', 2),
        batch_size=c.get('batch_size', 32),
        sequence_length=c.get('sequence_length', 20),
        usar_ortogonal=c.get('usar_ortogonal', True),
        entropy_coef=c.get('entropy_coef', 0.01),
        value_coef=c.get('value_coef', 0.5),
        max_grad_norm=c.get('max_grad_norm', 0.5),
        update_frequency=c.get('update_frequency', 100),
    )


def _impala_advantage_batch(estados: Any, acciones: Any, recompensas: List[float],
                           gamma: float, lambda_gae: float) -> np.ndarray:
    """Cálculo vectorizado de ventajas para minibatches de IMPALA."""
    rews = np.array(recompensas, dtype=np.float64)
    n = len(rews)
    adv = np.zeros(n, dtype=np.float64)
    a = 0.0
    for t in range(n - 1, -1, -1):
        nv = 0.0
        delta = rews[t] + gamma * nv
        a = delta + gamma * lambda_gae * a
        adv[t] = a
    return adv


# ---------------------------------------------------------------------------
# Configuracion publica del modulo
# ---------------------------------------------------------------------------
RFEN10_CONFIG: Dict[str, Any] = {
    'inicializacion_preferida': 'ortogonal',
    'learning_rate_default': 0.0003,
    'gamma_default': 0.99,
    'lambda_gae_default': 0.95,
    'num_actors_default': 8,
    'num_learners_default': 2,
    'batch_size_default': 32,
    'sequence_length_default': 20,
    'entropy_coef_default': 0.01,
    'value_coef_default': 0.5,
    'max_grad_norm_default': 0.5,
    'update_frequency_default': 100,
    'umbral_convergencia': 0.7,
    'umbral_estabilidad': 0.7,
}

logger.info("RFEN1_RN_10.py cargado - Neurona IMPALA Distribuida [delegado a RF_EN_SBRTM_RFEN1_RN_10_1]")
