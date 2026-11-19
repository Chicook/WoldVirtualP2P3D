"""RFEN1_RN_5.py - Neurona de Refuerzo A3C Distribuida (refactor modular).

Delega toda la logica interna a:
  RF_EN_SBRTM_RFEN1_RN_5/RF_EN_SBRTM_RFEN1_RN_5_1.py
    -> NeuronaDeComfiguracion  (clase principal A3C con clases anidadas)
    -> NeuronaRefuerzoA3C      (alias publico)
"""
import numpy as np
import math
import time
import logging
import threading
import random
from typing import Tuple, Optional, Dict, Any, List

# ---------------------------------------------------------------------------
# Base compartida (_rfen_base)
# ---------------------------------------------------------------------------
try:
    from ._rfen_base import (
        LUCIA_RL_CONFIG, _dt, NeuronaRefuerzoBase, InicializadoresRL,
        inicializar_pesos_he, inicializar_pesos_xavier, inicializar_pesos_lecun,
        inicializar_pesos_ortogonal, inicializar_pesos_espectral, _Ring,
    )
except ImportError:
    import importlib.util as _ilu_base, os as _os_base
    _base_path = _os_base.path.join(
        _os_base.path.dirname(_os_base.path.abspath(__file__)), "_rfen_base.py"
    )
    _spec_base = _ilu_base.spec_from_file_location("RF_EN_rfen_base", _base_path)
    if _spec_base and _spec_base.loader:
        _mod_base = _ilu_base.module_from_spec(_spec_base)
        _spec_base.loader.exec_module(_mod_base)
        LUCIA_RL_CONFIG        = _mod_base.LUCIA_RL_CONFIG
        _dt                    = _mod_base._dt
        NeuronaRefuerzoBase    = _mod_base.NeuronaRefuerzoBase
        InicializadoresRL      = _mod_base.InicializadoresRL
        inicializar_pesos_he       = _mod_base.inicializar_pesos_he
        inicializar_pesos_xavier   = _mod_base.inicializar_pesos_xavier
        inicializar_pesos_lecun    = _mod_base.inicializar_pesos_lecun
        inicializar_pesos_ortogonal = _mod_base.inicializar_pesos_ortogonal
        inicializar_pesos_espectral = _mod_base.inicializar_pesos_espectral
        _Ring                  = _mod_base._Ring
    else:
        raise ImportError(f"No se pudo cargar _rfen_base desde {_base_path}")

# ---------------------------------------------------------------------------
# Submodulo especializado RN_5: NeuronaDeComfiguracion / NeuronaRefuerzoA3C
# ---------------------------------------------------------------------------
try:
    from .RF_EN_SBRTM_RFEN1_RN_5.RF_EN_SBRTM_RFEN1_RN_5_1 import (
        NeuronaDeComfiguracion,
        NeuronaRefuerzoA3C,
    )
except ImportError:
    import importlib.util as _ilu, os as _os
    _sbrtm5_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_5",
        "RF_EN_SBRTM_RFEN1_RN_5_1.py",
    )
    _spec5 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_5_1", _sbrtm5_path)
    if _spec5 and _spec5.loader:
        _mod5 = _ilu.module_from_spec(_spec5)
        _spec5.loader.exec_module(_mod5)
        NeuronaDeComfiguracion = _mod5.NeuronaDeComfiguracion
        NeuronaRefuerzoA3C     = _mod5.NeuronaRefuerzoA3C
    else:
        raise ImportError(
            f"No se pudo cargar RF_EN_SBRTM_RFEN1_RN_5_1 desde {_sbrtm5_path}"
        )

logger = logging.getLogger('RFENRN1.RFEN1_RN_5')

# ---------------------------------------------------------------------------
# Funciones de fabrica y utilidad del modulo
# ---------------------------------------------------------------------------

def crear_neurona_a3c(input_size: int, output_size: int,
                      configuracion: Optional[Dict[str, Any]] = None) -> NeuronaDeComfiguracion:
    """Crea y devuelve una instancia de NeuronaDeComfiguracion (A3C)."""
    c = configuracion or {}
    return NeuronaDeComfiguracion(
        input_size=input_size,
        output_size=output_size,
        nombre=c.get('nombre', 'NeuronaRefuerzoA3C'),
        learning_rate_actor=c.get('learning_rate_actor', 0.001),
        learning_rate_critic=c.get('learning_rate_critic', 0.002),
        gamma=c.get('gamma', 0.99),
        lambda_gae=c.get('lambda_gae', 0.95),
        num_workers=c.get('num_workers', 4),
        update_frequency=c.get('update_frequency', 20),
        usar_ortogonal=c.get('usar_ortogonal', True),
        entropy_coef=c.get('entropy_coef', 0.01),
    )


def analizar_a3c(neurona: NeuronaDeComfiguracion) -> Dict[str, Any]:
    """Devuelve estadisticas y verificacion de estabilidad de la neurona A3C."""
    return {
        'estadisticas': neurona.obtener_estadisticas_a3c(),
        'estable': neurona.verificar_estabilidad(),
    }


# ---------------------------------------------------------------------------
# Configuracion publica del modulo
# ---------------------------------------------------------------------------
RFEN5_CONFIG: Dict[str, Any] = {
    'inicializacion_preferida':     'ortogonal',
    'learning_rate_actor_default':   0.001,
    'learning_rate_critic_default':  0.002,
    'gamma_default':                 0.99,
    'lambda_gae_default':            0.95,
    'num_workers_default':           4,
    'update_frequency_default':      20,
    'entropy_coef_default':          0.01,
    'umbral_convergencia':           0.7,
    'umbral_estabilidad':            0.7,
}

logger.info(
    "RFEN1_RN_5.py cargado correctamente - Neurona de Refuerzo A3C Distribuida "
    "[delegado a RF_EN_SBRTM_RFEN1_RN_5_1 -> NeuronaDeComfiguracion]"
)