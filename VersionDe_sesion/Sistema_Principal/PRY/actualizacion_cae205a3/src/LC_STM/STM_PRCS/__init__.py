"""
__init__.py - STM_PRCS: Sistema de Procesamiento de Rendimiento Neuronal LucIA
===============================================================================
Sistema de Autoconciencia de Rendimiento para LucIA (WoldVirtualP2P3D 2026).

Recibe el rendimiento completo de todos los subsistemas, lo representa en
formato matemático-numérico en una estructura neuronal de 50 dimensiones
(5 capas × 10 neuronas), actualiza los pesos neuronales en tiempo de
ejecución, y permite a LucIA tener plena conciencia de su propio sistema.

Subsistemas de este paquete:
  ┌────────────────────────────────┬──────────────────────────────────────┐
  │ Módulo                         │ Función                              │
  ├────────────────────────────────┼──────────────────────────────────────┤
  │ rendimiento_neuronal.py        │ Motor principal: Φ(t), W, AdamW+Hebb│
  │ colector_sistema.py            │ Recolecta métricas de todos los STM  │
  │ visualizador_matematico.py     │ Render matemático / ASCII / JSON     │
  │ actualizador_pesos_rt.py       │ Propaga W a conversor + PSNRL + BKS  │
  └────────────────────────────────┴──────────────────────────────────────┘

Uso mínimo::

    from LC_STM.STM_PRCS import inicializar_stm_prcs, ciclo_conciencia
    contexto = inicializar_stm_prcs()
    snap = ciclo_conciencia()
    print(contexto_lucia())

Matemáticas del sistema:
  Φ(t) ∈ ℝ⁵⁰        — vector de rendimiento normalizado
  W    ∈ ℝ⁵⁰        — pesos neuronales del sistema
  σ    = tanh(W⊙Φ)  — activaciones
  δ    = Φ - σ       — señal de error (Hebbian)
  ∇L   = -σ·(1-σ²)·δ — gradiente
  W_t  ← AdamW(W_{t-1}, ∇L)  +  η_H·(Φ·σ - W·‖σ‖²)
  Ξ    ∈ [0,1]       — índice de conciencia global
"""
from __future__ import annotations

__version__: str = "2026.1.0"
__author__: str = "WoldVirtualP2P3D — Equipo Celebro"
__package_name__: str = "STM_PRCS"
__status__: str = "Production"

import logging
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional

logger = logging.getLogger("WoldVirtualP2P3D.STM_PRCS")

# ---------------------------------------------------------------------------
# Importaciones internas (tolerantes: relativas o absolutas)
# ---------------------------------------------------------------------------
try:
    from LC_STM.STM_PRCS.rendimiento_neuronal import (
        MotorRendimientoNeuronal,
        SnapshotNeuronal,
        get_motor,
        ingerir_y_aprender,
        N_NEURONAS,
        CAPAS,
        IDX,
        LR, BETA1, BETA2, EPS, WD, ETA_HEBB,
    )
    from LC_STM.STM_PRCS.colector_sistema import (
        ColectorSistema,
        get_colector,
        arrancar_colector,
    )
    from LC_STM.STM_PRCS.visualizador_matematico import (
        VisualizadorMatematico,
        get_visualizador,
        render_consola_completo,
        descripcion_lucia,
    )
    from LC_STM.STM_PRCS.actualizador_pesos_rt import (
        ActualizadorPesosRT,
        get_actualizador,
        inicializar_actualizador,
    )
except ImportError:
    try:
        from rendimiento_neuronal import (
            MotorRendimientoNeuronal, SnapshotNeuronal, get_motor,
            ingerir_y_aprender, N_NEURONAS, CAPAS, IDX,
            LR, BETA1, BETA2, EPS, WD, ETA_HEBB,
        )
        from colector_sistema import ColectorSistema, get_colector, arrancar_colector
        from visualizador_matematico import (
            VisualizadorMatematico, get_visualizador,
            render_consola_completo, descripcion_lucia,
        )
        from actualizador_pesos_rt import (
            ActualizadorPesosRT, get_actualizador, inicializar_actualizador,
        )
    except ImportError as _err:
        logger.warning("[STM_PRCS] Importaciones parciales: %s", _err)
        MotorRendimientoNeuronal = None     # type: ignore
        SnapshotNeuronal = None             # type: ignore
        ColectorSistema = None              # type: ignore
        VisualizadorMatematico = None       # type: ignore
        ActualizadorPesosRT = None          # type: ignore
        get_motor = None                    # type: ignore
        get_colector = None                 # type: ignore
        get_visualizador = None             # type: ignore
        get_actualizador = None             # type: ignore
        ingerir_y_aprender = None           # type: ignore
        arrancar_colector = None            # type: ignore
        render_consola_completo = None      # type: ignore
        descripcion_lucia = None            # type: ignore
        inicializar_actualizador = None     # type: ignore
        N_NEURONAS = 50
        CAPAS = ("ENRN", "RF_EN", "RF_SL", "RNP", "SLRN")
        IDX = {}
        LR = 0.003; BETA1 = 0.9; BETA2 = 0.999; EPS = 1e-8; WD = 0.01; ETA_HEBB = 0.002


# ---------------------------------------------------------------------------
# Estado del paquete STM_PRCS
# ---------------------------------------------------------------------------
_STM_PRCS_STATE: Dict[str, Any] = {
    "inicializado": False,
    "motor_activo": False,
    "colector_activo": False,
    "actualizador_enlazado": False,
    "total_ciclos": 0,
    "timestamp_inicio": 0.0,
}
_STATE_LOCK: threading.Lock = threading.Lock()


# ---------------------------------------------------------------------------
# Función de inicialización completa
# ---------------------------------------------------------------------------
def inicializar_stm_prcs(
    intervalo_colector_s: float = 15.0,
    alpha_fusion: float = 0.05,
    arrancar_colector_auto: bool = True,
    propagar_bksvcb: bool = True,
    propagar_psnrl: bool = True,
    conversor_externo: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Inicializa el sistema completo STM_PRCS de autoconciencia de rendimiento.

    Pasos:
      1. Crea/obtiene el MotorRendimientoNeuronal (singleton).
      2. Crea/obtiene el ActualizadorPesosRT y lo enlaza al motor.
      3. Opcionalmente arranca el ColectorSistema en hilo daemon.
      4. Crea el VisualizadorMatematico.

    Args:
        intervalo_colector_s: Intervalo de recolección automática en segundos.
        alpha_fusion: Tasa EMA de fusión de pesos al conversor [0.001, 1.0].
        arrancar_colector_auto: Si True, arranca el hilo colector automáticamente.
        propagar_bksvcb: Si True, notifica BKSVCB en cada ciclo.
        propagar_psnrl: Si True, escribe checkpoint PSNRL en cada ciclo.
        conversor_externo: ConversorRespuestaPesos externo (del mainLCSTM).

    Returns:
        Dict con el estado de inicialización y referencias a los componentes.
    """
    import time as _time
    with _STATE_LOCK:
        if _STM_PRCS_STATE["inicializado"]:
            return {"ya_inicializado": True, **_STM_PRCS_STATE}

    resultado: Dict[str, Any] = {}

    # Motor neuronal
    if get_motor is not None:
        motor = get_motor()
        resultado["motor"] = motor
        with _STATE_LOCK:
            _STM_PRCS_STATE["motor_activo"] = True
    else:
        resultado["motor"] = None
        resultado["error_motor"] = "MotorRendimientoNeuronal no disponible"

    # Actualizador de pesos
    if get_actualizador is not None:
        actualizador = get_actualizador(
            alpha_fusion=alpha_fusion,
            propagar_bksvcb=propagar_bksvcb,
            propagar_psnrl=propagar_psnrl,
        )
        if conversor_externo is not None:
            actualizador.inyectar_conversor(conversor_externo)
        resultado["actualizador"] = actualizador
        with _STATE_LOCK:
            _STM_PRCS_STATE["actualizador_enlazado"] = True
    else:
        resultado["actualizador"] = None

    # Colector del sistema
    if arrancar_colector_auto and arrancar_colector is not None:
        colector = arrancar_colector(intervalo_s=intervalo_colector_s)
        resultado["colector"] = colector
        with _STATE_LOCK:
            _STM_PRCS_STATE["colector_activo"] = True
    else:
        resultado["colector"] = None

    # Visualizador
    if get_visualizador is not None:
        resultado["visualizador"] = get_visualizador()
    else:
        resultado["visualizador"] = None

    with _STATE_LOCK:
        _STM_PRCS_STATE["inicializado"] = True
        _STM_PRCS_STATE["timestamp_inicio"] = _time.time()

    resultado["estado"] = dict(_STM_PRCS_STATE)
    resultado["version"] = __version__
    logger.info("[STM_PRCS] Sistema inicializado v%s", __version__)
    return resultado


# ---------------------------------------------------------------------------
# API de alto nivel
# ---------------------------------------------------------------------------
def ciclo_conciencia(metricas: Optional[Dict[str, float]] = None) -> Optional["SnapshotNeuronal"]:
    """
    Ejecuta un ciclo completo de autoconciencia:
      1. Recolecta métricas del SO.
      2. Ingesta métricas adicionales si se pasan.
      3. Ejecuta ciclo_aprendizaje() en el motor.
      4. Propaga pesos automáticamente (vía hooks del actualizador).

    Returns:
        SnapshotNeuronal con el estado matemático completo, o None si el motor
        no está disponible.
    """
    if get_motor is None:
        return None
    motor = get_motor()
    motor.recolectar_so()
    if metricas:
        motor.ingerir_lote(metricas)
    return motor.ciclo_aprendizaje()


def contexto_lucia(verbose: bool = False) -> str:
    """
    Genera el texto de autoconciencia de rendimiento para inyectar en el
    prompt de LucIA. Incluye valores numéricos del estado neuronal actual.

    Returns:
        String listo para anteponer al prompt del modelo.
    """
    if descripcion_lucia is not None:
        return descripcion_lucia(verbose=verbose)
    return "[STM_PRCS] No disponible."


def estado_paquete() -> Dict[str, Any]:
    """Devuelve el estado actual del paquete STM_PRCS."""
    with _STATE_LOCK:
        base = dict(_STM_PRCS_STATE)
    if get_motor is not None:
        try:
            snap = get_motor().snapshot_matematico()
            if snap:
                base["ultimo_ciclo"] = snap.ciclo
                base["conciencia_global"] = snap.conciencia_global
                base["capa_dominante"] = snap.capa_dominante
        except Exception:
            pass
    return base


def render_estado() -> str:
    """Render ASCII matemático del estado neuronal actual."""
    if render_consola_completo is not None:
        return render_consola_completo()
    return "[STM_PRCS] Visualizador no disponible."


# ---------------------------------------------------------------------------
# Exportaciones públicas
# ---------------------------------------------------------------------------
__all__: List[str] = [
    # Clases
    "MotorRendimientoNeuronal",
    "SnapshotNeuronal",
    "ColectorSistema",
    "VisualizadorMatematico",
    "ActualizadorPesosRT",
    # Singletons
    "get_motor",
    "get_colector",
    "get_visualizador",
    "get_actualizador",
    # API de alto nivel
    "inicializar_stm_prcs",
    "ciclo_conciencia",
    "contexto_lucia",
    "estado_paquete",
    "render_estado",
    # Atajos
    "ingerir_y_aprender",
    "arrancar_colector",
    "render_consola_completo",
    "descripcion_lucia",
    "inicializar_actualizador",
    # Constantes
    "N_NEURONAS",
    "CAPAS",
    "IDX",
    "LR", "BETA1", "BETA2", "EPS", "WD", "ETA_HEBB",
    # Metadatos
    "__version__",
    "__author__",
    "__package_name__",
]
