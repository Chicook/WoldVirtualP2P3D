"""
actualizador_pesos_rt.py - Actualizador de Pesos Neuronales en Tiempo Real
===========================================================================
Puente entre el MotorRendimientoNeuronal (STM_PRCS) y el ConversorRespuestaPesos
(BKSVCB / compat_local) para propagar actualizaciones de pesos en tiempo de
ejecución a las 50 neuronas del sistema LucIA.

Flujo de propagación:
  MotorRendimientoNeuronal (W_prcs ∈ ℝ⁵⁰)
        │  ciclo_aprendizaje() → SnapshotNeuronal
        ▼
  ActualizadorPesosRT
        │  _propagar_a_conversor()  ──► ConversorRespuestaPesos.neuronas[i].peso
        │  _propagar_a_psnrl()      ──► PSNRL/stm_prcs_pesos.json (disco)
        │  _notificar_bksvcb()      ──► POST /transaction al servidor BKSVCB
        ▼
  Red neuronal de LucIA con pesos actualizados ✓

La regla de propagación combina los pesos del motor de rendimiento con los
pesos existentes de cada neurona mediante interpolación exponencial (EMA):

  w_new = α·W_prcs[i] + (1-α)·w_old       α ∈ (0, 1]  (tasa de fusión)

Esto permite que el sistema de rendimiento "enseñe" gradualmente a la red
sin perturbar el aprendizaje de sesión existente.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Final, List, Optional

logger = logging.getLogger("WoldVirtualP2P3D.STM_PRCS.ActualizadorPesosRT")

_THIS_DIR: Final[Path] = Path(__file__).resolve().parent
_SRC_DIR: Final[Path] = _THIS_DIR.parent.parent

# Importación tolerante
try:
    from LC_STM.STM_PRCS.rendimiento_neuronal import (
        MotorRendimientoNeuronal, SnapshotNeuronal, CAPAS, N_POR_CAPA, get_motor
    )
except ImportError:
    try:
        from rendimiento_neuronal import (
            MotorRendimientoNeuronal, SnapshotNeuronal, CAPAS, N_POR_CAPA, get_motor
        )
    except ImportError:
        MotorRendimientoNeuronal = None   # type: ignore
        SnapshotNeuronal = None           # type: ignore
        CAPAS = ("ENRN", "RF_EN", "RF_SL", "RNP", "SLRN")
        N_POR_CAPA = 10
        get_motor = None                  # type: ignore

BKSVCB_PORT: int = 8765
ALPHA_FUSION: float = 0.05        # tasa de fusión EMA de pesos
_PSNRL_DIR: Final[Path] = _SRC_DIR / "STM_CH" / "PSNRL"


class ActualizadorPesosRT:
    """
    Propaga en tiempo real los pesos del motor de rendimiento a las 50 neuronas
    de LucIA usando una fusión EMA suave para no perturbar el aprendizaje activo.

    Puede actuar:
      A) Como hook registrado en el motor (cada ciclo_aprendizaje()).
      B) Como hilo daemon autónomo a intervalo configurable.
    """

    def __init__(
        self,
        motor: Optional["MotorRendimientoNeuronal"] = None,
        alpha_fusion: float = ALPHA_FUSION,
        bksvcb_port: int = BKSVCB_PORT,
        propagar_bksvcb: bool = True,
        propagar_psnrl: bool = True,
        propagar_conversor: bool = True,
    ) -> None:
        self._motor = motor
        if self._motor is None and get_motor is not None:
            self._motor = get_motor()
        self.alpha = float(max(0.001, min(1.0, alpha_fusion)))
        self.bksvcb_port = int(bksvcb_port)
        self.propagar_bksvcb = bool(propagar_bksvcb)
        self.propagar_psnrl = bool(propagar_psnrl)
        self.propagar_conversor = bool(propagar_conversor)
        # Referencia al conversor de pesos (inyectada o buscada en BKSVCB)
        self._conversor: Optional[Any] = None
        self._activo: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._hilo: Optional[threading.Thread] = None
        self._propagaciones: int = 0
        self._errores_prop: int = 0
        # Registrar como hook en el motor si está disponible
        if self._motor is not None:
            self._motor.registrar_hook(self._on_ciclo)

    # ------------------------------------------------------------------
    # Hook invocado tras cada ciclo_aprendizaje()
    # ------------------------------------------------------------------
    def _on_ciclo(self, snap: "SnapshotNeuronal") -> None:
        """Callback invocado automáticamente por el motor tras cada ciclo."""
        try:
            self._propagar(snap)
        except Exception as e:
            with self._lock:
                self._errores_prop += 1
            logger.debug("[ActualizadorPesosRT] Error en hook: %s", e)

    # ------------------------------------------------------------------
    # Núcleo de propagación
    # ------------------------------------------------------------------
    def _propagar(self, snap: "SnapshotNeuronal") -> None:
        """Propaga los pesos del snapshot a todos los destinos configurados."""
        pesos_prcs: List[float] = snap.pesos   # W ∈ ℝ⁵⁰ del motor

        if self.propagar_conversor:
            self._propagar_a_conversor(pesos_prcs)
        if self.propagar_psnrl:
            self._propagar_a_psnrl(snap)
        if self.propagar_bksvcb:
            self._notificar_bksvcb(snap)

        with self._lock:
            self._propagaciones += 1

    def _propagar_a_conversor(self, pesos_prcs: List[float]) -> None:
        """Fusiona los pesos W_prcs en el ConversorRespuestaPesos mediante EMA."""
        conversor = self._obtener_conversor()
        if conversor is None:
            return
        try:
            neuronas = conversor.neuronas
            for i, neurona in enumerate(neuronas):
                if i >= len(pesos_prcs):
                    break
                w_old = float(neurona.get("peso", 0.0))
                w_new = self.alpha * pesos_prcs[i] + (1.0 - self.alpha) * w_old
                neurona["peso"] = round(w_new, 6)
        except Exception as e:
            logger.debug("[ActualizadorPesosRT] Error conversor: %s", e)

    def _propagar_a_psnrl(self, snap: "SnapshotNeuronal") -> None:
        """Escribe el snapshot de pesos en el directorio PSNRL."""
        try:
            _PSNRL_DIR.mkdir(parents=True, exist_ok=True)
            ruta = _PSNRL_DIR / "rendimiento_pesos.json"
            # Formato compatible con PSNRL: lista de neuronas con peso
            neuronas_psnrl: List[Dict[str, Any]] = []
            for i, capa in enumerate(CAPAS):
                for j in range(N_POR_CAPA):
                    idx_global = i * N_POR_CAPA + j
                    neuronas_psnrl.append({
                        "id": f"{capa}{j+1}",
                        "capa": capa,
                        "peso": round(snap.pesos[idx_global], 6),
                        "activacion": round(snap.activaciones[idx_global], 6),
                        "gradiente": round(snap.gradiente[idx_global], 6),
                        "phi": round(snap.phi[idx_global], 6),
                    })
            estado = {
                "version": "2026.1.0",
                "ciclo": snap.ciclo,
                "timestamp": snap.timestamp,
                "conciencia_global": round(snap.conciencia_global, 6),
                "capa_dominante": snap.capa_dominante,
                "norma_pesos": round(snap.norma_pesos, 6),
                "norma_gradiente": round(snap.norma_gradiente, 6),
                "entropia": round(snap.entropia_activaciones, 6),
                "drift": round(snap.drift_sináptico, 8),
                "neuronas": neuronas_psnrl,
                "perdida_por_capa": {k: round(v, 8)
                                     for k, v in snap.perdida_por_capa.items()},
            }
            tmp = ruta.with_suffix(".tmp")
            tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            tmp.replace(ruta)
        except Exception as e:
            logger.debug("[ActualizadorPesosRT] Error PSNRL: %s", e)

    def _notificar_bksvcb(self, snap: "SnapshotNeuronal") -> None:
        """Envía una transacción de aprendizaje al servidor BKSVCB (HTTP POST)."""
        try:
            payload = {
                "tipo": "AUTOCONCIENCIA_RENDIMIENTO",
                "emisor": "STM_PRCS",
                "receptor": "BKSVCB",
                "datos": {
                    "ciclo": snap.ciclo,
                    "conciencia_global": round(snap.conciencia_global, 6),
                    "capa_dominante": snap.capa_dominante,
                    "norma_pesos": round(snap.norma_pesos, 6),
                    "perdida_total": round(sum(snap.perdida_por_capa.values()), 6),
                    "entropia": round(snap.entropia_activaciones, 6),
                    "drift": round(snap.drift_sináptico, 8),
                    "pesos_muestra": [round(w, 4) for w in snap.pesos[:10]],
                },
            }
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.bksvcb_port}/transaction",
                data=raw,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=0.3):
                pass
        except Exception:
            pass   # BKSVCB puede no estar activo — silencioso

    # ------------------------------------------------------------------
    # Acceso al conversor (lazy, tolerante)
    # ------------------------------------------------------------------
    def _obtener_conversor(self) -> Optional[Any]:
        """Obtiene el ConversorRespuestaPesos desde BKSVCB si está disponible."""
        if self._conversor is not None:
            return self._conversor
        try:
            src_str = str(_SRC_DIR)
            if src_str not in sys.path:
                sys.path.insert(0, src_str)
            from STM_BKCH.compat_local import get_conversor_pesos
            self._conversor = get_conversor_pesos()
        except Exception:
            try:
                from STM_BKCH.compat_local import ConversorRespuestaPesos
                self._conversor = ConversorRespuestaPesos()
            except Exception:
                self._conversor = None
        return self._conversor

    def inyectar_conversor(self, conversor: Any) -> None:
        """Permite inyectar un conversor externo (p.ej. desde mainLCSTM)."""
        self._conversor = conversor

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def estado(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "propagaciones": self._propagaciones,
                "errores": self._errores_prop,
                "alpha_fusion": self.alpha,
                "propagar_bksvcb": self.propagar_bksvcb,
                "propagar_psnrl": self.propagar_psnrl,
                "propagar_conversor": self.propagar_conversor,
                "tiene_conversor": self._conversor is not None,
            }

    def forzar_propagacion(self) -> Dict[str, Any]:
        """Fuerza una propagación inmediata del último snapshot disponible."""
        if self._motor is None:
            return {"exito": False, "error": "Motor no disponible"}
        snap = self._motor.snapshot_matematico()
        if snap is None:
            return {"exito": False, "error": "Sin ciclos de aprendizaje ejecutados"}
        try:
            self._propagar(snap)
            return {"exito": True, "ciclo": snap.ciclo,
                    "conciencia": snap.conciencia_global}
        except Exception as e:
            return {"exito": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Instancia singleton
# ---------------------------------------------------------------------------
_actualizador_singleton: Optional[ActualizadorPesosRT] = None
_actualizador_lock: threading.Lock = threading.Lock()


def get_actualizador(
    alpha_fusion: float = ALPHA_FUSION,
    propagar_bksvcb: bool = True,
    propagar_psnrl: bool = True,
    propagar_conversor: bool = True,
) -> ActualizadorPesosRT:
    """Devuelve (o crea) la instancia singleton del ActualizadorPesosRT."""
    global _actualizador_singleton
    if _actualizador_singleton is None:
        with _actualizador_lock:
            if _actualizador_singleton is None:
                _actualizador_singleton = ActualizadorPesosRT(
                    alpha_fusion=alpha_fusion,
                    propagar_bksvcb=propagar_bksvcb,
                    propagar_psnrl=propagar_psnrl,
                    propagar_conversor=propagar_conversor,
                )
    return _actualizador_singleton


def inicializar_actualizador(
    alpha_fusion: float = ALPHA_FUSION,
    propagar_bksvcb: bool = True,
    propagar_psnrl: bool = True,
) -> ActualizadorPesosRT:
    """Inicializa el actualizador singleton y lo enlaza al motor."""
    return get_actualizador(
        alpha_fusion=alpha_fusion,
        propagar_bksvcb=propagar_bksvcb,
        propagar_psnrl=propagar_psnrl,
    )
