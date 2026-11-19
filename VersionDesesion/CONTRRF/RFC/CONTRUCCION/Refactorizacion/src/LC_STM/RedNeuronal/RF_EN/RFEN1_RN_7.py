"""RFEN1_RN_7.py - Neurona de Refuerzo SAC (refactor modular).

Delega la logica interna, distribuciones estocasticas y motores de calculo a:
  RF_EN_SBRTM_RFEN1_RN_7/RF_EN_SBRTM_RFEN1_RN_7_1.py
    -> NeuronaRefuerzoSAC (con BufferExperienciaSAC, DistribucionGaussianaSAC y MotorCalculoSAC)
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
# Submodulo especializado RN_7: NeuronaRefuerzoSAC
# ---------------------------------------------------------------------------
try:
    from .RF_EN_SBRTM_RFEN1_RN_7.RF_EN_SBRTM_RFEN1_RN_7_1 import (
        NeuronaRefuerzoSAC,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _sbrtm7_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_7",
        "RF_EN_SBRTM_RFEN1_RN_7_1.py",
    )
    _spec7 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_7_1", _sbrtm7_path)
    if _spec7 and _spec7.loader:
        _mod7 = _ilu.module_from_spec(_spec7)
        _spec7.loader.exec_module(_mod7)
        NeuronaRefuerzoSAC = _mod7.NeuronaRefuerzoSAC
    else:
        raise ImportError(
            f"No se pudo cargar RF_EN_SBRTM_RFEN1_RN_7_1 desde {_sbrtm7_path}"
        )

logger = logging.getLogger('RFENRN1.RFEN1_RN_7')

# ---------------------------------------------------------------------------
# Funciones de fabrica y utilidad del modulo
# ---------------------------------------------------------------------------

def crear_neurona_sac(input_size: int, output_size: int,
                      configuracion: Optional[Dict[str, Any]] = None) -> NeuronaRefuerzoSAC:
    """Crea y devuelve una instancia configurada de NeuronaRefuerzoSAC."""
    c = configuracion or {}
    return NeuronaRefuerzoSAC(
        input_size=input_size,
        output_size=output_size,
        nombre=c.get('nombre', 'NeuronaRefuerzoSAC'),
        learning_rate=c.get('learning_rate', 0.0003),
        gamma=c.get('gamma', 0.99),
        tau=c.get('tau', 0.005),
        alpha=c.get('alpha', 0.2),
        alpha_auto=c.get('alpha_auto', True),
        buffer_size=c.get('buffer_size', 1000000),
        batch_size=c.get('batch_size', 256),
        usar_he=c.get('usar_he', True),
        target_entropy=c.get('target_entropy', None),
    )


def analizar_sac(neurona: NeuronaRefuerzoSAC) -> Dict[str, Any]:
    """Retorna estadisticas y comprobacion de estabilidad de la neurona SAC."""
    return {
        'estadisticas': neurona.obtener_estadisticas_sac(),
        'estable': neurona.verificar_estabilidad(),
    }


# ---------------------------------------------------------------------------
# Configuracion publica del modulo
# ---------------------------------------------------------------------------
RFEN7_CONFIG: Dict[str, Any] = {
    'inicializacion_preferida': 'he',
    'learning_rate_default': 0.0003,
    'gamma_default': 0.99,
    'tau_default': 0.005,
    'alpha_default': 0.2,
    'alpha_auto_default': True,
    'buffer_size_default': 1000000,
    'batch_size_default': 256,
    'target_entropy_default': None,
    'umbral_alpha_min': 0.001,
    'umbral_alpha_max': 1.0,
}

logger.info("RFEN1_RN_7.py cargado correctamente - Neurona de Refuerzo SAC con Entropia Maxima [delegado a RF_EN_SBRTM_RFEN1_RN_7_1]")
