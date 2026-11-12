"""RFEN1_RN_8.py - Neurona de Refuerzo TD3 (refactor modular).

Delega la logica interna, policy smoothing y motores de calculo a:
  RF_EN_SBRTM_RFEN1_RN_8/RF_EN_SBRTM_RFEN1_RN_8_1.py
    -> NeuronaRefuerzoTD3 (con BufferExperienciaTD3 y MotorCalculoTD3)
"""
import numpy as np
import math
import time
import logging
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
# Submodulo especializado RN_8: NeuronaRefuerzoTD3
# ---------------------------------------------------------------------------
try:
    from .RF_EN_SBRTM_RFEN1_RN_8.RF_EN_SBRTM_RFEN1_RN_8_1 import (
        NeuronaRefuerzoTD3,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _sbrtm8_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_8",
        "RF_EN_SBRTM_RFEN1_RN_8_1.py",
    )
    _spec8 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_8_1", _sbrtm8_path)
    if _spec8 and _spec8.loader:
        _mod8 = _ilu.module_from_spec(_spec8)
        _spec8.loader.exec_module(_mod8)
        NeuronaRefuerzoTD3 = _mod8.NeuronaRefuerzoTD3
    else:
        raise ImportError(
            f"No se pudo cargar RF_EN_SBRTM_RFEN1_RN_8_1 desde {_sbrtm8_path}"
        )

logger = logging.getLogger('RFENRN1.RFEN1_RN_8')

# ---------------------------------------------------------------------------
# Funciones de fabrica y utilidad del modulo
# ---------------------------------------------------------------------------

def crear_neurona_td3(input_size: int, output_size: int,
                      configuracion: Optional[Dict[str, Any]] = None) -> NeuronaRefuerzoTD3:
    """Crea y devuelve una instancia configurada de NeuronaRefuerzoTD3."""
    c = configuracion or {}
    return NeuronaRefuerzoTD3(
        input_size=input_size,
        output_size=output_size,
        nombre=c.get('nombre', 'NeuronaRefuerzoTD3'),
        learning_rate_actor=c.get('learning_rate_actor', 0.001),
        learning_rate_critic=c.get('learning_rate_critic', 0.001),
        gamma=c.get('gamma', 0.99),
        tau=c.get('tau', 0.005),
        policy_noise=c.get('policy_noise', 0.2),
        noise_clip=c.get('noise_clip', 0.5),
        policy_delay=c.get('policy_delay', 2),
        buffer_size=c.get('buffer_size', 1000000),
        batch_size=c.get('batch_size', 256),
        usar_he=c.get('usar_he', True),
    )


def analizar_td3(neurona: NeuronaRefuerzoTD3) -> Dict[str, Any]:
    """Retorna estadisticas y comprobacion de estabilidad de la neurona TD3."""
    return {
        'estadisticas': neurona.obtener_estadisticas_td3(),
        'estable': neurona.verificar_estabilidad(),
    }


# ---------------------------------------------------------------------------
# Configuracion publica del modulo
# ---------------------------------------------------------------------------
RFEN8_CONFIG: Dict[str, Any] = {
    'inicializacion_preferida': 'he',
    'learning_rate_actor_default': 0.001,
    'learning_rate_critic_default': 0.001,
    'gamma_default': 0.99,
    'tau_default': 0.005,
    'policy_noise_default': 0.2,
    'noise_clip_default': 0.5,
    'policy_delay_default': 2,
    'buffer_size_default': 1000000,
    'batch_size_default': 256,
    'umbral_sobreestimacion': 10.0,
}

logger.info("RFEN1_RN_8.py cargado correctamente - Neurona de Refuerzo TD3 con Doble Critica [delegado a RF_EN_SBRTM_RFEN1_RN_8_1]")
