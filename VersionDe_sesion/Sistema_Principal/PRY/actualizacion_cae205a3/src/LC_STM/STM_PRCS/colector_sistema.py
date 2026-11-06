"""
colector_sistema.py - Colector de Rendimiento del Sistema para STM_PRCS (2026)
===============================================================================
Recolecta en tiempo real métricas de TODOS los subsistemas de LucIA y las
entrega al MotorRendimientoNeuronal para su procesamiento automático.

Subsistemas monitorizados:
  ┌──────────────┬────────────────────────────────────────────────────────┐
  │ Subsistema   │ Métricas extraídas                                     │
  ├──────────────┼────────────────────────────────────────────────────────┤
  │ SO / Proceso │ CPU %, RAM MB/%, Swap MB, GC, Hilos, I/O disco        │
  │ BKSVCB       │ Bloques, TX pendientes, dificultad, hash entropía      │
  │ SBSTM        │ Sesión activa, turnos, sesiones, checkpoint age        │
  │ RNP          │ Pérdida, gradiente, pesos, score, lr efectivo          │
  │ SLRN         │ Backprop loss, entropía Shannon, GSNR, Muon drift      │
  │ ENRN         │ Activaciones, gradientes de entrada                    │
  │ Watchdog     │ Ciclos, alertas emitidas, intervalo                    │
  └──────────────┴────────────────────────────────────────────────────────┘

Uso:
    from LC_STM.STM_PRCS.colector_sistema import ColectorSistema
    colector = ColectorSistema()
    colector.arrancar()           # inicia hilo de recolección continua
    snapshot = colector.snapshot_actual()
    colector.detener()
"""
from __future__ import annotations

import os
import sys
import threading
import time
import logging
import json
from pathlib import Path
from typing import Any, Dict, Final, List, Optional

logger = logging.getLogger("WoldVirtualP2P3D.STM_PRCS.ColectorSistema")

_THIS_DIR: Final[Path] = Path(__file__).resolve().parent
_SRC_DIR: Final[Path] = _THIS_DIR.parent.parent

# Intentar importar el motor de rendimiento neuronal (mismo paquete)
try:
    from LC_STM.STM_PRCS.rendimiento_neuronal import (
        MotorRendimientoNeuronal, SnapshotNeuronal, get_motor, ingerir_y_aprender
    )
except ImportError:
    try:
        from rendimiento_neuronal import (
            MotorRendimientoNeuronal, SnapshotNeuronal, get_motor, ingerir_y_aprender
        )
    except ImportError:
        MotorRendimientoNeuronal = None   # type: ignore[misc,assignment]
        SnapshotNeuronal = None           # type: ignore[misc,assignment]
        get_motor = None                  # type: ignore[misc,assignment]
        ingerir_y_aprender = None         # type: ignore[misc,assignment]


class ColectorSistema:
    """
    Recolector automático de métricas de rendimiento de LucIA.

    Lanza un hilo daemon que cada `intervalo_s` segundos:
      1. Recoge métricas del SO (CPU, RAM, hilos, GC).
      2. Consulta BKSVCB vía HTTP si está activo (port 8765).
      3. Consulta el estado SBSTM en memoria si hay instancia activa.
      4. Alimenta el MotorRendimientoNeuronal y ejecuta ciclo_aprendizaje().
      5. Almacena el snapshot más reciente para consulta externa.
    """

    BKSVCB_PORT: int = 8765

    def __init__(
        self,
        intervalo_s: float = 15.0,
        motor: Optional["MotorRendimientoNeuronal"] = None,
    ) -> None:
        self.intervalo_s = max(2.0, float(intervalo_s))
        self._motor = motor
        self._activo: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._hilo: Optional[threading.Thread] = None
        self._ultimo_snapshot: Optional["SnapshotNeuronal"] = None
        self._ciclos_colector: int = 0
        self._errores_colector: int = 0
        self._t_arranque: float = time.time()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def arrancar(self) -> None:
        """Lanza el hilo daemon de recolección continua."""
        with self._lock:
            if self._activo:
                return
            self._activo = True
        # Obtener/crear el motor si no fue inyectado
        if self._motor is None and get_motor is not None:
            self._motor = get_motor()
        self._hilo = threading.Thread(
            target=self._bucle,
            name="ColectorSTM_PRCS",
            daemon=True,
        )
        self._hilo.start()
        logger.info("[ColectorSistema] Iniciado — intervalo %.1fs", self.intervalo_s)

    def detener(self) -> None:
        """Solicita la detención del hilo de recolección."""
        with self._lock:
            self._activo = False

    def snapshot_actual(self) -> Optional["SnapshotNeuronal"]:
        """Devuelve el último snapshot neuronal calculado."""
        with self._lock:
            return self._ultimo_snapshot

    def estado(self) -> Dict[str, Any]:
        """Resumen del estado del colector."""
        with self._lock:
            return {
                "activo": self._activo,
                "ciclos": self._ciclos_colector,
                "errores": self._errores_colector,
                "intervalo_s": self.intervalo_s,
                "uptime_s": time.time() - self._t_arranque,
                "tiene_motor": self._motor is not None,
                "ultimo_snapshot_ciclo": (
                    self._ultimo_snapshot.ciclo if self._ultimo_snapshot else None
                ),
            }

    # ------------------------------------------------------------------
    # Bucle de recolección
    # ------------------------------------------------------------------
    def _bucle(self) -> None:
        """Hilo interno: recoge métricas y ejecuta ciclos de aprendizaje."""
        while True:
            with self._lock:
                if not self._activo:
                    break
            try:
                self._ciclo_recoleccion()
            except Exception as e:
                with self._lock:
                    self._errores_colector += 1
                logger.debug("[ColectorSistema] Error en ciclo: %s", e)
            # Espera fraccionada para responder a detener() rápidamente
            restante = self.intervalo_s
            while restante > 0:
                with self._lock:
                    if not self._activo:
                        return
                time.sleep(min(1.0, restante))
                restante -= 1.0

    def _ciclo_recoleccion(self) -> None:
        """Un ciclo completo de recolección → ingestión → aprendizaje."""
        metricas: Dict[str, float] = {}

        # 1. Métricas del SO
        metricas.update(self._recoger_so())

        # 2. Métricas BKSVCB (HTTP)
        metricas.update(self._recoger_bksvcb())

        # 3. Métricas SBSTM (en memoria)
        metricas.update(self._recoger_sbstm())

        # 4. Alimentar el motor y ejecutar ciclo
        if self._motor is not None:
            self._motor.ingerir_lote(metricas)
            snap = self._motor.ciclo_aprendizaje()
            with self._lock:
                self._ultimo_snapshot = snap
                self._ciclos_colector += 1

    # ------------------------------------------------------------------
    # Recolectores por subsistema
    # ------------------------------------------------------------------
    def _recoger_so(self) -> Dict[str, float]:
        """Recolecta métricas del SO sin dependencias obligatorias externas."""
        m: Dict[str, float] = {}
        m["uptime_s"] = time.time() - self._t_arranque
        import threading as _th
        m["threads_activos"] = float(_th.active_count())
        try:
            import gc
            m["gc_colecciones"] = float(sum(gc.get_count()))
        except Exception:
            m["gc_colecciones"] = 0.0
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            mi = proc.memory_info()
            m["ram_mb"]  = mi.rss / 1_048_576
            m["cpu_pct"] = proc.cpu_percent(interval=0.0)
            vm = psutil.virtual_memory()
            m["ram_pct"] = vm.percent
            sw = psutil.swap_memory()
            m["swap_mb"] = sw.used / 1_048_576
            # I/O disco (si disponible)
            try:
                io = psutil.disk_io_counters()
                if io:
                    m["disco_io_mb"] = (io.read_bytes + io.write_bytes) / 1_048_576
            except Exception:
                pass
        except ImportError:
            pass
        except Exception:
            pass
        return m

    def _recoger_bksvcb(self) -> Dict[str, float]:
        """Consulta el servidor BKSVCB por HTTP para obtener métricas blockchain."""
        m: Dict[str, float] = {}
        try:
            import urllib.request
            import urllib.error
            url = f"http://127.0.0.1:{self.BKSVCB_PORT}/status"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                datos: Dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            m["bk_bloques"]    = float(datos.get("total_bloques", 0))
            ultimo = datos.get("ultimo_bloque", {})
            m["bk_dificultad"] = float(ultimo.get("dificultad", 2))
            m["bk_nonce"]      = float(ultimo.get("nonce", 0))
            hash_str: str = str(ultimo.get("hash_bloque", ""))
            if hash_str and self._motor is not None:
                m["bk_hash_entropía"] = self._motor._entropia_string(hash_str)
            txs = ultimo.get("total_transacciones", 0)
            m["bk_transacciones"] = float(txs)
        except Exception:
            pass
        # Consultar /transform para deriva y pasos
        try:
            import urllib.request
            url2 = f"http://127.0.0.1:{self.BKSVCB_PORT}/transform"
            with urllib.request.urlopen(url2, timeout=0.5) as resp2:
                datos2: Dict[str, Any] = json.loads(resp2.read().decode("utf-8"))
            conversor = datos2.get("conversor", {})
            m["bk_deriva_acum"]  = float(conversor.get("deriva_acumulada", 0.0))
            m["bk_pasos_sesion"] = float(conversor.get("pasos_sesion", 0))
            cid = datos2.get("cid_ipfs", None)
            m["bk_cid_presente"] = 1.0 if cid else 0.0
        except Exception:
            pass
        return m

    def _recoger_sbstm(self) -> Dict[str, float]:
        """Extrae métricas del estado SBSTM en memoria si está disponible."""
        m: Dict[str, float] = {}
        try:
            # Intentar importar sin provocar crash si no está disponible
            sbstm_path = str(_SRC_DIR)
            if sbstm_path not in sys.path:
                sys.path.insert(0, sbstm_path)
            import importlib
            sbstm = importlib.import_module("SBSTM")
            estado = sbstm.obtener_estado_subsistema()
            m["sb_session_active"] = 1.0 if estado.get("session_active") else 0.0
            m["sb_turnos"]         = float(estado.get("total_dialog_turns", 0))
            m["sb_sesiones_total"] = float(estado.get("total_sessions_launched", 0))
            age = time.time() - float(estado.get("last_checkpoint_timestamp", time.time()))
            m["sb_checkpoint_age"] = max(0.0, age)
        except Exception:
            pass
        return m


# ---------------------------------------------------------------------------
# Instancia singleton del colector
# ---------------------------------------------------------------------------
_colector_singleton: Optional[ColectorSistema] = None
_colector_lock: threading.Lock = threading.Lock()


def get_colector(intervalo_s: float = 15.0) -> ColectorSistema:
    """Devuelve (o crea) la instancia singleton del ColectorSistema."""
    global _colector_singleton
    if _colector_singleton is None:
        with _colector_lock:
            if _colector_singleton is None:
                _colector_singleton = ColectorSistema(intervalo_s=intervalo_s)
    return _colector_singleton


def arrancar_colector(intervalo_s: float = 15.0) -> ColectorSistema:
    """Atajo: obtiene el colector singleton y lo arranca si no está activo."""
    c = get_colector(intervalo_s)
    c.arrancar()
    return c
