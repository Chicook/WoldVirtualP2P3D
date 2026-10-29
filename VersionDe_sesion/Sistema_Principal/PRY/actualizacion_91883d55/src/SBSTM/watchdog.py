"""watchdog.py — Watchdog Adaptativo de Subsistemas LucIA (Fase 6)
=================================================================
Hilo daemon que monitoriza en background:
  - RAM del proceso (usando _ram_proceso_mb del autodiagnostico)
  - Heartbeat de la red neuronal (50 neuronas)
  - Estado de la blockchain (validez de cadena)

Si algún umbral se supera, registra una alerta en GestorErroresSistema.
Se arranca como daemon: no bloquea el cierre del proceso principal.

API pública:
  arrancar_watchdog(intervalo_s=60) -> WatchdogSistema
  detener_watchdog()
  estado_watchdog() -> Dict[str, Any]
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

_RAM_UMBRAL_MB: float = 150.0
_MAX_CICLOS: int = 50


class WatchdogSistema:
    """Monitor en background de salud de subsistemas LucIA."""

    def __init__(self, intervalo_s: float = 60.0) -> None:
        self.intervalo_s: float = max(5.0, float(intervalo_s))
        self._activo: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._hilo: Optional[threading.Thread] = None
        self._ciclos: int = 0
        self._alertas: int = 0
        self._ultimo_estado: Dict[str, Any] = {}

    def arrancar(self) -> None:
        """Lanza el hilo daemon si no está ya activo."""
        with self._lock:
            if self._activo:
                return
            self._activo = True
        self._hilo = threading.Thread(
            target=self._bucle,
            name="WatchdogLucIA",
            daemon=True,
        )
        self._hilo.start()

    def detener(self) -> None:
        """Solicita la detención del hilo (máximo 1 ciclo de espera)."""
        with self._lock:
            self._activo = False

    def estado(self) -> Dict[str, Any]:
        """Devuelve el último snapshot de estado del watchdog."""
        with self._lock:
            return {
                "activo": self._activo,
                "ciclos": self._ciclos,
                "alertas_emitidas": self._alertas,
                "ultimo_estado": dict(self._ultimo_estado),
                "intervalo_s": self.intervalo_s,
            }

    def _bucle(self) -> None:
        while True:
            with self._lock:
                if not self._activo:
                    break
            self._ciclo_inspeccion()
            restante = self.intervalo_s
            while restante > 0:
                with self._lock:
                    if not self._activo:
                        return
                time.sleep(min(1.0, restante))
                restante -= 1.0

    def _ciclo_inspeccion(self) -> None:
        with self._lock:
            self._ciclos += 1
        ram_ok = self._comprobar_ram()
        neural_ok = self._comprobar_neural()
        bkch_ok = self._comprobar_blockchain()
        snapshot: Dict[str, Any] = {
            "ts": time.time(),
            "ciclo": self._ciclos,
            "ram_ok": ram_ok,
            "neural_ok": neural_ok,
            "bkch_ok": bkch_ok,
        }
        with self._lock:
            self._ultimo_estado = snapshot

    def _comprobar_ram(self) -> bool:
        try:
            from SBSTM.autodiagnostico import _ram_proceso_mb
            mb = _ram_proceso_mb()
            if 0 <= mb and mb > _RAM_UMBRAL_MB:
                self._emitir_alerta(
                    f"RAM proceso: {mb} MB supera umbral de {_RAM_UMBRAL_MB} MB",
                    "WATCHDOG_RAM", "ADVERTENCIA",
                )
                return False
            return True
        except Exception:
            return True

    def _comprobar_neural(self) -> bool:
        try:
            from STM_BKCH.compat_local import get_conversor_pesos
            conv = get_conversor_pesos()
            if len(conv.neuronas) < 50:
                self._emitir_alerta(
                    f"Transductor neuronal: solo {len(conv.neuronas)} neuronas activas",
                    "WATCHDOG_NEURAL", "ERROR",
                )
                return False
            return True
        except Exception as exc:
            self._emitir_alerta(str(exc)[:120], "WATCHDOG_NEURAL", "ERROR")
            return False

    def _comprobar_blockchain(self) -> bool:
        try:
            from STM_BKCH.BKSVCB import CelebroBlockchain
            bks = CelebroBlockchain()
            valida, err = bks.validar_cadena()
            if not valida:
                self._emitir_alerta(f"Cadena inválida: {err}", "WATCHDOG_BKCH", "CRITICO")
                return False
            return True
        except Exception as exc:
            self._emitir_alerta(str(exc)[:120], "WATCHDOG_BKCH", "ERROR")
            return False

    def _emitir_alerta(self, mensaje: str, contexto: str, severidad: str) -> None:
        with self._lock:
            self._alertas += 1
        try:
            from SBSTM.gestor_errores import GestorErroresSistema
            ges = GestorErroresSistema()
            entrada = ges.capturar(excepcion=None, contexto=f"[WATCHDOG] {contexto}", severidad=severidad)
            with ges._lock:
                if ges._errores:
                    ges._errores[-1]["mensaje"] = mensaje
        except Exception:
            pass


_watchdog_global: Optional[WatchdogSistema] = None
_wdog_lock: threading.Lock = threading.Lock()


def arrancar_watchdog(intervalo_s: float = 60.0) -> WatchdogSistema:
    """Inicia o devuelve el watchdog global del sistema."""
    global _watchdog_global
    with _wdog_lock:
        if _watchdog_global is None:
            _watchdog_global = WatchdogSistema(intervalo_s=intervalo_s)
        _watchdog_global.arrancar()
    return _watchdog_global


def detener_watchdog() -> None:
    """Detiene el watchdog global si está activo."""
    global _watchdog_global
    with _wdog_lock:
        if _watchdog_global is not None:
            _watchdog_global.detener()


def estado_watchdog() -> Dict[str, Any]:
    """Devuelve el estado actual del watchdog global."""
    global _watchdog_global
    with _wdog_lock:
        if _watchdog_global is None:
            return {"activo": False, "ciclos": 0, "alertas_emitidas": 0}
        return _watchdog_global.estado()


__all__ = [
    "WatchdogSistema",
    "arrancar_watchdog",
    "detener_watchdog",
    "estado_watchdog",
]
