"""
rendimiento_neuronal.py - Motor de Autoconciencia Neuronal LucIA (STM_PRCS 2026)
=================================================================================
Recibe TODO el rendimiento del sistema WoldVirtualP2P3D, lo representa en
estructura matemático-numérica densa compatible con la red neuronal de LucIA
(50 neuronas: ENRN x10, RF_EN x10, RF_SL x10, RNP x10, SLRN x10),
y actualiza los pesos en tiempo de ejecución mediante Hebbian + AdamW online.

Arquitectura:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  FUENTES DE RENDIMIENTO        VECTOR Φ(t) ∈ ℝ⁵⁰     CAPAS NEURONALES │
  │  ─────────────────────────     ─────────────────     ──────────────── │
  │  CPU / RAM / disco / latencia  →  Φ[0..9]       →   ENRN  (W₁ ∈ ℝ¹⁰) │
  │  Blockchain / bloques / PoNL   →  Φ[10..19]     →   RF_EN (W₂ ∈ ℝ¹⁰) │
  │  Sesión P2P / turnos / modelo  →  Φ[20..29]     →   RF_SL (W₃ ∈ ℝ¹⁰) │
  │  Optimizadores RNP / pérdidas  →  Φ[30..39]     →   RNP   (W₄ ∈ ℝ¹⁰) │
  │  Supervisado SLRN / entropia   →  Φ[40..49]     →   SLRN  (W₅ ∈ ℝ¹⁰) │
  └─────────────────────────────────────────────────────────────────────────┘

Regla de actualización online (AdamW + Hebbian):
  mₜ = β₁·mₜ₋₁ + (1-β₁)·∇L
  vₜ = β₂·vₜ₋₁ + (1-β₂)·∇L²
  ŵₜ = wₜ - α·m̂ₜ/(√v̂ₜ + ε) - λ·wₜ          [Regularización L2 desacoplada]
  ΔwHebb = η·(Φᵢ·σᵢ - wᵢ·||σᵢ||²)             [Regla de Hebb normalizada]

Uso:
    from LC_STM.STM_PRCS.rendimiento_neuronal import MotorRendimientoNeuronal
    motor = MotorRendimientoNeuronal()
    motor.ingerir_metrica("cpu_pct", 45.3)
    motor.ciclo_aprendizaje()
    snapshot = motor.snapshot_matematico()
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Metadatos
# ---------------------------------------------------------------------------
__version__: Final[str] = "2026.1.0"
__module_name__: Final[str] = "STM_PRCS.rendimiento_neuronal"
logger = logging.getLogger("WoldVirtualP2P3D.STM_PRCS.RendimientoNeuronal")
logging.getLogger("WoldVirtualP2P3D.STM_PRCS").setLevel(logging.CRITICAL)

# ---------------------------------------------------------------------------
# Rutas raíz (tolerante a imports relativos o absolutos)
# ---------------------------------------------------------------------------
_THIS_DIR: Final[Path] = Path(__file__).resolve().parent
_STM_PRCS_DIR: Final[Path] = _THIS_DIR
_LC_STM_DIR: Final[Path] = _THIS_DIR.parent
_SRC_DIR: Final[Path] = _LC_STM_DIR.parent
_PSNRL_CHECKPOINT: Final[Path] = _SRC_DIR / "STM_CH" / "PSNRL" / "stm_prcs_pesos.json"

# ---------------------------------------------------------------------------
# Constantes del motor neuronal
# ---------------------------------------------------------------------------
N_NEURONAS: Final[int] = 50          # 5 capas × 10
N_POR_CAPA: Final[int] = 10
CAPAS: Final[Tuple[str, ...]] = ("ENRN", "RF_EN", "RF_SL", "RNP", "SLRN")

# Hiperparámetros AdamW online
LR: Final[float]       = 0.003        # η  tasa de aprendizaje
BETA1: Final[float]    = 0.9          # β₁ momento de primer orden
BETA2: Final[float]    = 0.999        # β₂ momento de segundo orden
EPS: Final[float]      = 1e-8         # ε  estabilidad numérica
WD: Final[float]       = 0.01         # λ  weight decay desacoplado
ETA_HEBB: Final[float] = 0.002        # η_Hebb  tasa regla Hebb

# Ventana de historial para señal de error interna
WINDOW_ERR: Final[int] = 64

# ---------------------------------------------------------------------------
# Índices del vector Φ(t) ∈ ℝ⁵⁰ — semántica de cada dimensión
# ---------------------------------------------------------------------------
IDX: Final[Dict[str, int]] = {
    # Capa 0 — ENRN: métricas del sistema operativo
    "cpu_pct":           0,   # CPU % del proceso
    "ram_mb":            1,   # RAM del proceso en MB
    "ram_pct":           2,   # RAM % del sistema
    "disco_io_mb":       3,   # I/O disco MB/s estimado
    "latencia_ms":       4,   # latencia de respuesta ms
    "thrpt_tokens_s":    5,   # throughput tokens/s del LLM
    "threads_activos":   6,   # hilos Python activos
    "swap_mb":           7,   # Swap usado MB
    "gc_colecciones":    8,   # nº recolecciones GC
    "uptime_s":          9,   # uptime del proceso en segundos
    # Capa 1 — RF_EN: blockchain / BKSVCB
    "bk_bloques":        10,  # total de bloques en cadena
    "bk_transacciones":  11,  # transacciones pendientes
    "bk_hash_entropía":  12,  # entropía del hash del último bloque [0,1]
    "bk_dificultad":     13,  # dificultad PoNL actual
    "bk_nonce":          14,  # nonce normalizado del último bloque
    "bk_merkle_bits":    15,  # bits de Merkle root normalizados
    "bk_time_minar_ms":  16,  # tiempo de minado del último bloque ms
    "bk_cid_presente":   17,  # 1.0 si CID IPFS presente, 0.0 si no
    "bk_deriva_acum":    18,  # deriva acumulada del conversor
    "bk_pasos_sesion":   19,  # pasos de sesión acumulados
    # Capa 2 — RF_SL: sesión P2P y diálogo
    "sb_session_active": 20,  # 1.0=sesión activa, 0.0=inactiva
    "sb_turnos":         21,  # total de turnos de diálogo
    "sb_sesiones_total": 22,  # nº de sesiones lanzadas
    "sb_checkpoint_age": 23,  # segundos desde último checkpoint
    "modelo_id_hash":    24,  # hash normalizado del id del modelo activo
    "tokens_prompt_avg": 25,  # tokens promedio por prompt
    "tokens_resp_avg":   26,  # tokens promedio por respuesta
    "ratio_error_resp":  27,  # ratio de respuestas con error [0,1]
    "costo_acum_usd":    28,  # costo acumulado USD normalizado
    "voz_activa":        29,  # 1.0=voz activa, 0.0=no
    # Capa 3 — RNP: optimizadores de pesos neuronales
    "rnp_loss_actual":   30,  # pérdida actual del optimizador RNP
    "rnp_loss_delta":    31,  # Δpérdida respecto al ciclo anterior
    "rnp_grad_norm":     32,  # norma del gradiente ||∇L||
    "rnp_weight_norm":   33,  # norma de pesos ||W||
    "rnp_lr_efectivo":   34,  # learning rate efectivo (con scheduler)
    "rnp_momentum_mag":  35,  # magnitud del momento (m̂)
    "rnp_var_mag":       36,  # magnitud de varianza acumulada (v̂)
    "rnp_iter_global":   37,  # iteración global normalizada
    "rnp_switch_sgd":    38,  # 1.0 si SWATS en fase SGD, 0.0 Adam
    "rnp_score_global":  39,  # puntuación global del optimizador
    # Capa 4 — SLRN: aprendizaje supervisado y entropía
    "sl_loss_bp":        40,  # pérdida backprop
    "sl_shannon_entr":   41,  # entropía de Shannon de la distribución de salida
    "sl_muon_drift":     42,  # deriva del operador Muon NS
    "sl_gsnr":           43,  # Gradient Signal-to-Noise Ratio normalizado
    "sl_cosine_sim":     44,  # similitud coseno gradiente actual vs anterior
    "sl_weight_decay_e": 45,  # eficiencia del weight decay [0,1]
    "sl_cond_estimate":  46,  # estimación del número de condición de la Hessiana
    "sl_update_eff":     47,  # eficiencia de actualización [0,1]
    "sl_prec_score":     48,  # puntuación de precisión
    "sl_iter_sl":        49,  # iteraciones del supervisado normalizadas
}

# ---------------------------------------------------------------------------
# Normalización de cada dimensión — escalas de referencia
# ---------------------------------------------------------------------------
_NORM_SCALE: Final[Dict[str, float]] = {
    "cpu_pct":           100.0,
    "ram_mb":            1024.0,
    "ram_pct":           100.0,
    "disco_io_mb":       100.0,
    "latencia_ms":       5000.0,
    "thrpt_tokens_s":    200.0,
    "threads_activos":   64.0,
    "swap_mb":           512.0,
    "gc_colecciones":    1000.0,
    "uptime_s":          86400.0,
    "bk_bloques":        1000.0,
    "bk_transacciones":  100.0,
    "bk_hash_entropía":  1.0,
    "bk_dificultad":     8.0,
    "bk_nonce":          500000.0,
    "bk_merkle_bits":    256.0,
    "bk_time_minar_ms":  60000.0,
    "bk_cid_presente":   1.0,
    "bk_deriva_acum":    1.0,
    "bk_pasos_sesion":   10000.0,
    "sb_session_active": 1.0,
    "sb_turnos":         1000.0,
    "sb_sesiones_total": 100.0,
    "sb_checkpoint_age": 3600.0,
    "modelo_id_hash":    1.0,
    "tokens_prompt_avg": 2000.0,
    "tokens_resp_avg":   4000.0,
    "ratio_error_resp":  1.0,
    "costo_acum_usd":    10.0,
    "voz_activa":        1.0,
    "rnp_loss_actual":   10.0,
    "rnp_loss_delta":    5.0,
    "rnp_grad_norm":     10.0,
    "rnp_weight_norm":   50.0,
    "rnp_lr_efectivo":   0.1,
    "rnp_momentum_mag":  1.0,
    "rnp_var_mag":       1.0,
    "rnp_iter_global":   10000.0,
    "rnp_switch_sgd":    1.0,
    "rnp_score_global":  1.0,
    "sl_loss_bp":        10.0,
    "sl_shannon_entr":   math.log(50 + 1),
    "sl_muon_drift":     1.0,
    "sl_gsnr":           10.0,
    "sl_cosine_sim":     2.0,       # range [-1,1] → shift +1 / 2
    "sl_weight_decay_e": 1.0,
    "sl_cond_estimate":  1000.0,
    "sl_update_eff":     1.0,
    "sl_prec_score":     1.0,
    "sl_iter_sl":        10000.0,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class SnapshotNeuronal:
    """Instantánea completa del estado matemático de la red neuronal de rendimiento."""
    timestamp: float = 0.0
    ciclo: int = 0
    # Vector de entrada normalizado  Φ(t) ∈ ℝ⁵⁰
    phi: List[float] = field(default_factory=lambda: [0.0] * N_NEURONAS)
    # Pesos por neurona (50 escalares)
    pesos: List[float] = field(default_factory=lambda: [0.0] * N_NEURONAS)
    # Activaciones σ = tanh(W·Φ)
    activaciones: List[float] = field(default_factory=lambda: [0.0] * N_NEURONAS)
    # Gradiente interno ∇L (señal de error Hebbian)
    gradiente: List[float] = field(default_factory=lambda: [0.0] * N_NEURONAS)
    # Métricas de convergencia por capa
    perdida_por_capa: Dict[str, float] = field(default_factory=dict)
    norma_pesos: float = 0.0
    norma_gradiente: float = 0.0
    entropia_activaciones: float = 0.0
    drift_sináptico: float = 0.0
    # Métricas del optimizador AdamW online
    lr_efectivo: float = LR
    momento_m: List[float] = field(default_factory=lambda: [0.0] * N_NEURONAS)
    varianza_v: List[float] = field(default_factory=lambda: [0.0] * N_NEURONAS)
    # Legibilidad
    capa_dominante: str = "ENRN"
    conciencia_global: float = 0.0   # score compuesto [0,1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "ciclo": self.ciclo,
            "phi": self.phi,
            "pesos": self.pesos,
            "activaciones": self.activaciones,
            "gradiente": self.gradiente,
            "perdida_por_capa": self.perdida_por_capa,
            "norma_pesos": self.norma_pesos,
            "norma_gradiente": self.norma_gradiente,
            "entropia_activaciones": self.entropia_activaciones,
            "drift_sináptico": self.drift_sináptico,
            "lr_efectivo": self.lr_efectivo,
            "momento_m": self.momento_m,
            "varianza_v": self.varianza_v,
            "capa_dominante": self.capa_dominante,
            "conciencia_global": self.conciencia_global,
        }


# ---------------------------------------------------------------------------
# Clase principal: MotorRendimientoNeuronal
# ---------------------------------------------------------------------------
class MotorRendimientoNeuronal:
    """
    Motor de autoconciencia de rendimiento de LucIA.

    Recibe métricas brutas de cualquier subsistema, las normaliza al vector
    Φ(t) ∈ ℝ⁵⁰, calcula activaciones σ = tanh(W·Φ), estima un gradiente
    interno de señal de error Hebbian y actualiza los pesos W mediante
    AdamW online en tiempo de ejecución.

    La red es capaz de:
      1. Representar el rendimiento completo del sistema en forma matemática.
      2. Detectar degradación por anomalía en las activaciones.
      3. Auto-ajustar pesos neuronales para "aprender" del rendimiento propio.
      4. Persistir el estado al PSNRL vía checkpoint JSON.
    """

    def __init__(
        self,
        lr: float = LR,
        beta1: float = BETA1,
        beta2: float = BETA2,
        eps: float = EPS,
        wd: float = WD,
        eta_hebb: float = ETA_HEBB,
        checkpoint_path: Optional[Path] = None,
        auto_checkpoint_ciclos: int = 100,
    ) -> None:
        # Hiperparámetros
        self.lr = float(lr)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.eps = float(eps)
        self.wd = float(wd)
        self.eta_hebb = float(eta_hebb)
        self.auto_checkpoint_ciclos = max(1, int(auto_checkpoint_ciclos))
        self.checkpoint_path = checkpoint_path or _PSNRL_CHECKPOINT

        # Estado central — pesos W ∈ ℝ⁵⁰ inicializados con LeCun
        self._W: np.ndarray = self._init_pesos()
        # Momento y varianza Adam  mₜ, vₜ ∈ ℝ⁵⁰
        self._m: np.ndarray = np.zeros(N_NEURONAS, dtype=np.float64)
        self._v: np.ndarray = np.zeros(N_NEURONAS, dtype=np.float64)
        # Vector de entrada normalizado  Φ(t) ∈ ℝ⁵⁰
        self._phi: np.ndarray = np.zeros(N_NEURONAS, dtype=np.float64)
        # Buffer de error para señal interna
        self._err_buffer: List[float] = []
        # Métricas crudas entrantes {nombre_dim: valor_bruto}
        self._metricas_crudas: Dict[str, float] = {}
        # Contadores
        self._ciclo: int = 0
        self._t_adam: int = 0        # paso del optimizador Adam
        self._ultimo_snapshot: Optional[SnapshotNeuronal] = None
        self._t_arranque: float = time.time()
        # Hooks de post-ciclo externos
        self._hooks: List[Callable[[SnapshotNeuronal], None]] = []
        # Hilo de recolección automática del SO
        self._colector_activo: bool = False
        self._lock: threading.RLock = threading.RLock()
        # Intentar cargar checkpoint previo
        self._cargar_checkpoint()
        logger.debug("[STM_PRCS] MotorRendimientoNeuronal inicializado v%s", __version__)

    # ------------------------------------------------------------------
    # Inicialización de pesos (LeCun normal)
    # ------------------------------------------------------------------
    @staticmethod
    def _init_pesos() -> np.ndarray:
        """W ~ N(0, 1/√50) — inicialización LeCun para evitar saturación de tanh."""
        rng = np.random.default_rng(2026)
        sigma = math.sqrt(1.0 / N_NEURONAS)
        return rng.normal(0.0, sigma, N_NEURONAS)

    # ------------------------------------------------------------------
    # API pública: ingesta de métricas
    # ------------------------------------------------------------------
    def ingerir_metrica(self, nombre: str, valor: float) -> None:
        """Registra una métrica bruta por nombre semántico.

        Args:
            nombre: Clave semántica (ver IDX), p.ej. "cpu_pct", "bk_bloques".
            valor:  Valor numérico en unidades naturales.
        """
        with self._lock:
            self._metricas_crudas[nombre] = float(valor)

    def ingerir_lote(self, metricas: Dict[str, float]) -> None:
        """Ingesta un dict completo de métricas de una sola vez."""
        with self._lock:
            for k, v in metricas.items():
                self._metricas_crudas[k] = float(v)

    def ingerir_desde_sbstm(self, estado_sbstm: Dict[str, Any]) -> None:
        """Extrae automáticamente las métricas del dict de estado SBSTM."""
        m: Dict[str, float] = {}
        m["sb_session_active"] = 1.0 if estado_sbstm.get("session_active") else 0.0
        m["sb_turnos"]         = float(estado_sbstm.get("total_dialog_turns", 0))
        m["sb_sesiones_total"] = float(estado_sbstm.get("total_sessions_launched", 0))
        age = time.time() - float(estado_sbstm.get("last_checkpoint_timestamp", time.time()))
        m["sb_checkpoint_age"] = max(0.0, age)
        self.ingerir_lote(m)

    def ingerir_desde_bksvcb(self, info_bks: Dict[str, Any]) -> None:
        """Extrae métricas del dict de BKSVCB / blockchain."""
        m: Dict[str, float] = {}
        m["bk_bloques"]       = float(info_bks.get("total_bloques", 0))
        m["bk_transacciones"] = float(info_bks.get("tx_pendientes", 0))
        m["bk_dificultad"]    = float(info_bks.get("dificultad", 2))
        m["bk_deriva_acum"]   = float(info_bks.get("deriva_acumulada", 0.0))
        m["bk_pasos_sesion"]  = float(info_bks.get("pasos_sesion", 0))
        m["bk_cid_presente"]  = 1.0 if info_bks.get("cid_ipfs") else 0.0
        # Calcular entropía del hash del último bloque
        hash_str: str = info_bks.get("ultimo_hash", "")
        if hash_str:
            m["bk_hash_entropía"] = self._entropia_string(hash_str)
        self.ingerir_lote(m)

    def ingerir_desde_rnp(self, metricas_rnp: Dict[str, Any]) -> None:
        """Extrae métricas de NeuralWeightOptimizationMetrics del paquete RNP."""
        m: Dict[str, float] = {}
        m["rnp_loss_actual"]  = float(metricas_rnp.get("final_loss", 0.0))
        m["rnp_grad_norm"]    = float(metricas_rnp.get("gradient_norm", 0.0))
        m["rnp_weight_norm"]  = float(metricas_rnp.get("weight_norm", 0.0))
        m["rnp_score_global"] = float(metricas_rnp.get("overall_score", 0.0))
        m["rnp_lr_efectivo"]  = float(metricas_rnp.get("lr_efectivo", LR))
        m["rnp_cosine"]       = float(metricas_rnp.get("cosine_similarity", 0.0))
        m["rnp_switch_sgd"]   = 1.0 if metricas_rnp.get("phase") == "sgd" else 0.0
        self.ingerir_lote(m)

    # ------------------------------------------------------------------
    # Recolección automática del SO (RAM/CPU/hilos)
    # ------------------------------------------------------------------
    def recolectar_so(self) -> None:
        """Recolecta métricas del SO sin dependencias externas obligatorias."""
        m: Dict[str, float] = {}
        m["uptime_s"] = time.time() - self._t_arranque
        import threading as _th
        m["threads_activos"] = float(_th.active_count())
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            mi = proc.memory_info()
            m["ram_mb"] = mi.rss / 1_048_576
            m["cpu_pct"] = proc.cpu_percent(interval=0.0)
            vm = psutil.virtual_memory()
            m["ram_pct"] = vm.percent
            sw = psutil.swap_memory()
            m["swap_mb"] = sw.used / 1_048_576
        except Exception:
            # Fallback sin psutil
            m.setdefault("ram_mb", 0.0)
            m.setdefault("cpu_pct", 0.0)
            m.setdefault("ram_pct", 0.0)
            m.setdefault("swap_mb", 0.0)
        try:
            import gc
            counts = gc.get_count()
            m["gc_colecciones"] = float(sum(counts))
        except Exception:
            m["gc_colecciones"] = 0.0
        self.ingerir_lote(m)

    # ------------------------------------------------------------------
    # Núcleo matemático: ciclo de aprendizaje
    # ------------------------------------------------------------------
    def ciclo_aprendizaje(self) -> SnapshotNeuronal:
        """Ejecuta un ciclo completo de aprendizaje neuronal sobre el rendimiento.

        Pasos internos:
          1. Construir  Φ(t) ∈ ℝ⁵⁰  desde métricas normalizadas
          2. Forward:   σ = tanh(W ⊙ Φ)                     [elementwise]
          3. Error:     δ = Φ - σ                            [señal de predicción]
          4. Gradiente: ∇L = -σ·(1-σ²)·δ                    [grad tanh Hebbian]
          5. AdamW:     Actualizar W con m, v
          6. Hebb:      ΔW += η_H·(Φ·σ - W·||σ||²)
          7. Clip:      ||W||₂ < 10                          [estabilidad]
          8. Checkpoint automático cada N ciclos

        Returns:
            SnapshotNeuronal con el estado matemático completo.
        """
        with self._lock:
            self._ciclo += 1
            self._t_adam += 1

            # --- Paso 1: Construir Φ(t) ---
            phi = self._construir_phi()
            self._phi = phi

            # --- Paso 2: Forward ---
            pre_act = self._W * phi         # activación pre-tanh, elemento a elemento
            sigma = np.tanh(pre_act)        # σ ∈ (-1, 1)^50

            # --- Paso 3: Error / señal de predicción ---
            delta = phi - sigma             # δ: diferencia entre entrada y activación

            # --- Paso 4: Gradiente Hebbian ---
            d_tanh = 1.0 - sigma ** 2      # derivada tanh
            grad = -d_tanh * delta          # ∇L   (negativo → descender pérdida)

            # Clipping de gradiente  ||∇L||₂ ≤ 1.0
            grad_norm = float(np.linalg.norm(grad))
            if grad_norm > 1.0:
                grad = grad / grad_norm

            # --- Paso 5: AdamW online ---
            self._m = BETA1 * self._m + (1.0 - BETA1) * grad
            self._v = BETA2 * self._v + (1.0 - BETA2) * (grad ** 2)
            t = self._t_adam
            m_hat = self._m / (1.0 - BETA1 ** t)
            v_hat = self._v / (1.0 - BETA2 ** t)
            lr_t  = self.lr * math.sqrt(1.0 - BETA2 ** t) / (1.0 - BETA1 ** t + 1e-30)
            update_adam = lr_t * m_hat / (np.sqrt(v_hat) + self.eps)
            self._W -= update_adam
            self._W -= self.wd * self.lr * self._W   # regularización L2 desacoplada

            # --- Paso 6: Regla de Hebb normalizada ---
            sig_norm_sq = float(np.dot(sigma, sigma))
            delta_hebb = self.eta_hebb * (phi * sigma - self._W * sig_norm_sq)
            self._W += delta_hebb

            # --- Paso 7: Clip estabilizador ---
            w_norm = float(np.linalg.norm(self._W))
            if w_norm > 10.0:
                self._W = self._W * (10.0 / w_norm)

            # --- Pérdida interna L = ½·||δ||²  por capa ---
            perdida_por_capa: Dict[str, float] = {}
            for i, capa in enumerate(CAPAS):
                sl = slice(i * N_POR_CAPA, (i + 1) * N_POR_CAPA)
                perdida_por_capa[capa] = float(0.5 * np.sum(delta[sl] ** 2))

            # --- Entropía de Shannon de las activaciones ---
            probs = (np.abs(sigma) + 1e-10) / (np.sum(np.abs(sigma)) + 1e-10 * N_NEURONAS)
            entropia = float(-np.sum(probs * np.log(probs + 1e-30)))

            # --- Drift sináptico (∇ norma del ajuste) ---
            drift = float(np.linalg.norm(update_adam + delta_hebb))

            # --- Capa dominante (mayor activación media) ---
            act_por_capa = [float(np.mean(np.abs(sigma[i*N_POR_CAPA:(i+1)*N_POR_CAPA])))
                            for i in range(len(CAPAS))]
            capa_dom = CAPAS[int(np.argmax(act_por_capa))]

            # --- Conciencia global ∈ [0,1] ---
            conciencia = float(np.clip(
                (1.0 - sum(perdida_por_capa.values()) / (N_NEURONAS + 1e-6))
                * (entropia / (math.log(N_NEURONAS) + 1e-6)),
                0.0, 1.0
            ))

            snapshot = SnapshotNeuronal(
                timestamp=time.time(),
                ciclo=self._ciclo,
                phi=phi.tolist(),
                pesos=self._W.tolist(),
                activaciones=sigma.tolist(),
                gradiente=grad.tolist(),
                perdida_por_capa=perdida_por_capa,
                norma_pesos=float(np.linalg.norm(self._W)),
                norma_gradiente=float(np.linalg.norm(grad)),
                entropia_activaciones=entropia,
                drift_sináptico=drift,
                lr_efectivo=float(lr_t),
                momento_m=self._m.tolist(),
                varianza_v=self._v.tolist(),
                capa_dominante=capa_dom,
                conciencia_global=conciencia,
            )
            self._ultimo_snapshot = snapshot

            # Disparar hooks externos
            for hook in self._hooks:
                try:
                    hook(snapshot)
                except Exception:
                    pass

            # Checkpoint automático
            if self._ciclo % self.auto_checkpoint_ciclos == 0:
                self._guardar_checkpoint(snapshot)

            return snapshot

    # ------------------------------------------------------------------
    # Construcción de Φ(t) ∈ ℝ⁵⁰
    # ------------------------------------------------------------------
    def _construir_phi(self) -> np.ndarray:
        """Convierte métricas crudas en el vector normalizado Φ(t) ∈ ℝ⁵⁰."""
        phi = np.zeros(N_NEURONAS, dtype=np.float64)
        for nombre, idx in IDX.items():
            val_bruto = self._metricas_crudas.get(nombre, 0.0)
            escala = _NORM_SCALE.get(nombre, 1.0)
            phi[idx] = float(np.clip(val_bruto / max(escala, 1e-30), -3.0, 3.0))
        return phi

    # ------------------------------------------------------------------
    # Snapshot matemático (acceso externo sin ciclo)
    # ------------------------------------------------------------------
    def snapshot_matematico(self) -> Optional[SnapshotNeuronal]:
        """Devuelve el último snapshot calculado, o None si aún no hay ciclos."""
        with self._lock:
            return self._ultimo_snapshot

    def representacion_matricial(self) -> Dict[str, Any]:
        """Devuelve la representación matricial completa en formato JSON-serializable.

        Estructura:
          W  ∈ ℝ⁵ˣ¹⁰    — matriz de pesos por capa
          Φ  ∈ ℝ⁵ˣ¹⁰    — vector de entrada por capa
          σ  ∈ ℝ⁵ˣ¹⁰    — activaciones por capa
          ∇L ∈ ℝ⁵ˣ¹⁰    — gradiente por capa
          m  ∈ ℝ⁵ˣ¹⁰    — momento Adam por capa
          v  ∈ ℝ⁵ˣ¹⁰    — varianza Adam por capa
        """
        with self._lock:
            snap = self._ultimo_snapshot
            if snap is None:
                return {"estado": "sin_ciclos"}
            resultado: Dict[str, Any] = {
                "version": __version__,
                "ciclo": snap.ciclo,
                "timestamp": snap.timestamp,
                "conciencia_global": round(snap.conciencia_global, 6),
                "capa_dominante": snap.capa_dominante,
                "norma_pesos": round(snap.norma_pesos, 6),
                "norma_gradiente": round(snap.norma_gradiente, 6),
                "entropia_activaciones": round(snap.entropia_activaciones, 6),
                "drift_sináptico": round(snap.drift_sináptico, 8),
                "lr_efectivo": round(snap.lr_efectivo, 8),
                "capas": {},
            }
            for i, capa in enumerate(CAPAS):
                sl = slice(i * N_POR_CAPA, (i + 1) * N_POR_CAPA)
                resultado["capas"][capa] = {
                    "W":    [round(x, 6) for x in snap.pesos[sl]],
                    "Phi":  [round(x, 6) for x in snap.phi[sl]],
                    "sigma":[round(x, 6) for x in snap.activaciones[sl]],
                    "grad": [round(x, 6) for x in snap.gradiente[sl]],
                    "m":    [round(x, 6) for x in snap.momento_m[sl]],
                    "v":    [round(x, 8) for x in snap.varianza_v[sl]],
                    "perdida": round(snap.perdida_por_capa.get(capa, 0.0), 8),
                    "neuronas": [
                        {
                            "id": f"{capa}{j+1}",
                            "W":     round(snap.pesos[i*N_POR_CAPA + j], 6),
                            "Phi":   round(snap.phi[i*N_POR_CAPA + j], 6),
                            "sigma": round(snap.activaciones[i*N_POR_CAPA + j], 6),
                            "grad":  round(snap.gradiente[i*N_POR_CAPA + j], 6),
                        }
                        for j in range(N_POR_CAPA)
                    ],
                }
            return resultado

    # ------------------------------------------------------------------
    # Render matemático en ASCII para consola (formato numérico)
    # ------------------------------------------------------------------
    def render_consola(self) -> str:
        """Genera una representación ASCII matemática del estado neuronal actual."""
        with self._lock:
            snap = self._ultimo_snapshot
            if snap is None:
                return "[!] Sin ciclos de aprendizaje ejecutados aun."

        lineas: List[str] = []
        sep = "-" * 72
        lineas.append(sep)
        lineas.append(f"  LucIA STM_PRCS - Autoconciencia Neuronal  "
                      f"[ciclo={snap.ciclo}  t={snap.timestamp:.2f}]")
        lineas.append(sep)
        lineas.append(f"  Conciencia global Xi = {snap.conciencia_global:.6f}   "
                      f"Capa dominante: {snap.capa_dominante}")
        lineas.append(f"  ||W||2 = {snap.norma_pesos:.6f}   "
                      f"||dL||2 = {snap.norma_gradiente:.6f}   "
                      f"H(sigma) = {snap.entropia_activaciones:.6f}   "
                      f"eta_t = {snap.lr_efectivo:.2e}")
        lineas.append(f"  Drift sinaptico delta_syn = {snap.drift_sináptico:.2e}")
        lineas.append(sep)
        lineas.append(f"  {'CAPA':<8} | {'W (10 pesos)':<42} | {'L/capa':>8}")
        lineas.append(f"  {'='*8}-+-{'='*42}-+-{'='*8}")
        for i, capa in enumerate(CAPAS):
            sl = slice(i * N_POR_CAPA, (i + 1) * N_POR_CAPA)
            pesos_str = " ".join(f"{w:+.3f}" for w in snap.pesos[sl])
            perdida = snap.perdida_por_capa.get(capa, 0.0)
            lineas.append(f"  {capa:<8} | {pesos_str:<42} | {perdida:8.6f}")
        lineas.append(sep)
        lineas.append(f"  Phi(t) = [{', '.join(f'{v:.4f}' for v in snap.phi[:10])} ...]")
        lineas.append(f"  sigma  = [{', '.join(f'{v:.4f}' for v in snap.activaciones[:10])} ...]")
        lineas.append(sep)
        return "\n".join(lineas)

    # ------------------------------------------------------------------
    # Hooks externos
    # ------------------------------------------------------------------
    def registrar_hook(self, fn: Callable[[SnapshotNeuronal], None]) -> None:
        """Registra una función invocada tras cada ciclo de aprendizaje."""
        with self._lock:
            if fn not in self._hooks:
                self._hooks.append(fn)

    # ------------------------------------------------------------------
    # Persistencia (checkpoint PSNRL)
    # ------------------------------------------------------------------
    def _guardar_checkpoint(self, snap: SnapshotNeuronal) -> None:
        """Serializa el estado del motor al checkpoint JSON en PSNRL."""
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            estado = {
                "version": __version__,
                "ciclo": self._ciclo,
                "t_adam": self._t_adam,
                "W": self._W.tolist(),
                "m": self._m.tolist(),
                "v": self._v.tolist(),
                "timestamp": time.time(),
                "ultimo_snapshot": snap.to_dict(),
            }
            tmp = self.checkpoint_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.checkpoint_path)
        except Exception as e:
            logger.debug("[STM_PRCS] checkpoint fallido: %s", e)

    def _cargar_checkpoint(self) -> None:
        """Carga el estado previo desde el checkpoint JSON si existe."""
        try:
            if not self.checkpoint_path.exists():
                return
            raw = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            self._ciclo  = int(raw.get("ciclo", 0))
            self._t_adam = int(raw.get("t_adam", 0))
            w = raw.get("W")
            if w and len(w) == N_NEURONAS:
                self._W = np.array(w, dtype=np.float64)
            m = raw.get("m")
            if m and len(m) == N_NEURONAS:
                self._m = np.array(m, dtype=np.float64)
            v = raw.get("v")
            if v and len(v) == N_NEURONAS:
                self._v = np.array(v, dtype=np.float64)
            logger.debug("[STM_PRCS] Checkpoint cargado: ciclo=%d", self._ciclo)
        except Exception as e:
            logger.debug("[STM_PRCS] No se pudo cargar checkpoint: %s", e)

    def guardar_checkpoint_manual(self) -> Dict[str, Any]:
        """Fuerza un guardado inmediato del estado."""
        with self._lock:
            snap = self._ultimo_snapshot
            if snap is None:
                snap = SnapshotNeuronal(timestamp=time.time(), ciclo=self._ciclo,
                                        pesos=self._W.tolist(), momento_m=self._m.tolist(),
                                        varianza_v=self._v.tolist())
            self._guardar_checkpoint(snap)
            return {"exito": True, "ciclo": self._ciclo, "ruta": str(self.checkpoint_path)}

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    @staticmethod
    def _entropia_string(s: str) -> float:
        """Entropía de Shannon normalizada [0,1] de los bytes de un string."""
        if not s:
            return 0.0
        b = s.encode("utf-8")
        total = len(b)
        conteo: Dict[int, int] = {}
        for byte in b:
            conteo[byte] = conteo.get(byte, 0) + 1
        h = -sum((c / total) * math.log2(c / total + 1e-30) for c in conteo.values())
        return float(np.clip(h / 8.0, 0.0, 1.0))   # 8 bits máximo → normalizar


# ---------------------------------------------------------------------------
# Instancia singleton del motor (perezosa)
# ---------------------------------------------------------------------------
_motor_singleton: Optional[MotorRendimientoNeuronal] = None
_motor_lock: threading.Lock = threading.Lock()


def get_motor() -> MotorRendimientoNeuronal:
    """Devuelve (o crea) la instancia singleton del MotorRendimientoNeuronal."""
    global _motor_singleton
    if _motor_singleton is None:
        with _motor_lock:
            if _motor_singleton is None:
                _motor_singleton = MotorRendimientoNeuronal()
    return _motor_singleton


def ingerir_y_aprender(metricas: Dict[str, float]) -> SnapshotNeuronal:
    """Atajo: ingesta un dict de métricas y ejecuta un ciclo de aprendizaje."""
    motor = get_motor()
    motor.ingerir_lote(metricas)
    motor.recolectar_so()
    return motor.ciclo_aprendizaje()
