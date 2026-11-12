"""RFEN1_RN_6.py - Neurona de Refuerzo PPO (refactor modular).

Delega la arquitectura e implementacion avanzada a:
  RF_EN_SBRTM_RFEN1_RN_6/RF_EN_SBRTM_RFEN1_RN_6_1.py
    -> NeuronaRefuerzoPPO (con BufferTrayectoria y OptimizadorPPO anidados)
"""
import numpy as np
import math
import time
import logging
import threading
import random
from typing import Tuple, Optional, Dict, Any, List
from collections import deque

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
# Submodulo especializado RN_6: NeuronaRefuerzoPPO
# ---------------------------------------------------------------------------
try:
    from .RF_EN_SBRTM_RFEN1_RN_6.RF_EN_SBRTM_RFEN1_RN_6_1 import (
        NeuronaRefuerzoPPO,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _sbrtm6_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_6",
        "RF_EN_SBRTM_RFEN1_RN_6_1.py",
    )
    _spec6 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_6_1", _sbrtm6_path)
    if _spec6 and _spec6.loader:
        _mod6 = _ilu.module_from_spec(_spec6)
        _spec6.loader.exec_module(_mod6)
        NeuronaRefuerzoPPO = _mod6.NeuronaRefuerzoPPO
    else:
        raise ImportError(
            f"No se pudo cargar RF_EN_SBRTM_RFEN1_RN_6_1 desde {_sbrtm6_path}"
        )

logger = logging.getLogger('RFENRN1.RFEN1_RN_6')

# ---------------------------------------------------------------------------
# Funciones de fabrica y utilidad del modulo
# ---------------------------------------------------------------------------

def crear_neurona_ppo(input_size: int, output_size: int,
                      configuracion: Optional[Dict[str, Any]] = None) -> NeuronaRefuerzoPPO:
    """Crea y devuelve una instancia configurada de NeuronaRefuerzoPPO."""
    c = configuracion or {}
    return NeuronaRefuerzoPPO(
        input_size=input_size,
        output_size=output_size,
        nombre=c.get('nombre', 'NeuronaRefuerzoPPO'),
        learning_rate=c.get('learning_rate', 0.0003),
        gamma=c.get('gamma', 0.99),
        lambda_gae=c.get('lambda_gae', 0.95),
        clip_ratio=c.get('clip_ratio', 0.2),
        clip_ratio_adaptativo=c.get('clip_ratio_adaptativo', True),
        entropy_coef=c.get('entropy_coef', 0.01),
        value_coef=c.get('value_coef', 0.5),
        max_grad_norm=c.get('max_grad_norm', 0.5),
        usar_ortogonal=c.get('usar_ortogonal', True),
        epochs_ppo=c.get('epochs_ppo', 4),
    )


def analizar_ppo(neurona: NeuronaRefuerzoPPO) -> Dict[str, Any]:
    """Retorna estadisticas diagnosticas y evaluacion de estabilidad de la neurona."""
    return {
        'estadisticas': neurona.obtener_estadisticas_ppo(),
        'estable': neurona.verificar_estabilidad(),
    }


# ---------------------------------------------------------------------------
# Configuracion publica del modulo
# ---------------------------------------------------------------------------
RFEN6_CONFIG: Dict[str, Any] = {
    'inicializacion_preferida': 'ortogonal',
    'learning_rate_default': 0.0003,
    'gamma_default': 0.99,
    'lambda_gae_default': 0.95,
    'clip_ratio_default': 0.2,
    'clip_ratio_adaptativo_default': True,
    'entropy_coef_default': 0.01,
    'value_coef_default': 0.5,
    'max_grad_norm_default': 0.5,
    'epochs_ppo_default': 4,
    'umbral_kl_divergencia_min': 0.01,
    'umbral_kl_divergencia_max': 0.02,
}

logger.info("RFEN1_RN_6.py cargado correctamente - Neurona de Refuerzo PPO Adaptativo [delegado a RF_EN_SBRTM_RFEN1_RN_6_1]")
