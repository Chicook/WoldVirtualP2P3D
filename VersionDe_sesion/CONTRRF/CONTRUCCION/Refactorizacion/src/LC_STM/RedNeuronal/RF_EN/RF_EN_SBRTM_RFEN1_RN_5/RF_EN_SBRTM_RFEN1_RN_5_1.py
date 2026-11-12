"""RF_EN_SBRTM_RFEN1_RN_5_1.py
Neurona de Configuración y Orquestación Distribuida A3C (RF_EN · SBRTM · RN_5).

Estructura de arquitectura:
  - `NeuronaDeComfiguracion` (Clase Principal):
      Especializada en los cálculos matemáticos, algoritmos de configuración, optimización de hiperparámetros
      (learning rates adaptativos, factores de descuento, escalado espectral, sincronización federada/asíncrona),
      validación de estabilidad y orquestación de la topología distribuida.
      
      Clases anidadas unificadas:
        * `NeuronaDeComfiguracion.BufferExperiencia`: Buffer circular acotado de alta velocidad para activaciones y ventajas.
        * `NeuronaDeComfiguracion.InicializadorConfigurado`: Motor de inicialización y control espectral.
        * `NeuronaDeComfiguracion.MotorA3CDistribuido`: Motor de ejecución A3C multi-worker asíncrono y thread-safe.
"""

from __future__ import annotations

import copy
import logging
import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .._rfen_base import (
        LUCIA_RL_CONFIG,
        _dt,
        _Ring,
        NeuronaRefuerzoBase,
        InicializadoresRL,
        inicializar_pesos_he,
        inicializar_pesos_xavier,
        inicializar_pesos_lecun,
        inicializar_pesos_ortogonal,
        inicializar_pesos_espectral,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_rfen_base", _os.path.join(_base, "_rfen_base.py")
    )
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        LUCIA_RL_CONFIG = _mod.LUCIA_RL_CONFIG
        _dt = _mod._dt
        _Ring = _mod._Ring
        NeuronaRefuerzoBase = _mod.NeuronaRefuerzoBase
        InicializadoresRL = _mod.InicializadoresRL
        inicializar_pesos_he = _mod.inicializar_pesos_he
        inicializar_pesos_xavier = _mod.inicializar_pesos_xavier
        inicializar_pesos_lecun = _mod.inicializar_pesos_lecun
        inicializar_pesos_ortogonal = _mod.inicializar_pesos_ortogonal
        inicializar_pesos_espectral = _mod.inicializar_pesos_espectral
    else:
        # Fallback de contingencia
        LUCIA_RL_CONFIG = {'precision': 'float32', 'random_seed': 42, 'default_learning_rate': 0.002}

        class _Ring:  # type: ignore[no-redef]
            def __init__(self, cap: int = 512):
                self.cap = cap
                self._d: List[Any] = []
            def append(self, x: Any) -> None:
                self._d.append(x)
                if len(self._d) > self.cap:
                    del self._d[0:len(self._d) - self.cap]
            def __len__(self) -> int: return len(self._d)
            def tail(self, n: int) -> List[Any]: return self._d[-n:]
            def clear(self) -> None: self._d.clear()

        def _dt() -> np.dtype:  # type: ignore[no-redef]
            return np.dtype(np.float32)

        class NeuronaRefuerzoBase:  # type: ignore[no-redef]
            def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaBase"):
                self.input_size = int(input_size)
                self.output_size = int(output_size)
                self.nombre = str(nombre)
                self.pesos = None
                self.sesgo = None
                self.historial_activaciones: List[np.ndarray] = []
                self.historial_gradientes: List[Dict[str, Any]] = []
                self.pasos = 0

            def resetear_historial(self):
                self.historial_activaciones = []
                self.historial_gradientes = []

        def inicializar_pesos_he(shape, fan_in=1, seed=42):
            return np.random.default_rng(seed).normal(0.0, math.sqrt(2.0 / max(1, fan_in)), shape).astype(np.float32)

        def inicializar_pesos_xavier(shape, fan_in=1, fan_out=1, seed=42):
            lim = math.sqrt(6.0 / max(1, fan_in + fan_out))
            return np.random.default_rng(seed).uniform(-lim, lim, shape).astype(np.float32)

        def inicializar_pesos_lecun(shape, fan_in=1, seed=42):
            return np.random.default_rng(seed).normal(0.0, math.sqrt(1.0 / max(1, fan_in)), shape).astype(np.float32)

        def inicializar_pesos_ortogonal(shape, seed=42, ganancia=1.0):
            a = np.random.default_rng(seed).normal(0, 1, shape)
            q, _ = np.linalg.qr(a) if shape[0] >= shape[1] else np.linalg.qr(a.T)
            q = q if shape[0] >= shape[1] else q.T
            return (q[:, :shape[1]] * ganancia).astype(np.float32)

        def inicializar_pesos_espectral(shape, seed=42):
            w = np.random.default_rng(seed).normal(0, 1, shape)
            s = np.linalg.svd(w, compute_uv=False)
            return (w / max(1e-12, s[0])).astype(np.float32)

logger = logging.getLogger(__name__)


class NeuronaDeComfiguracion(NeuronaRefuerzoBase):
    """Clase principal especializada en cálculos matemáticos, calibración y orquestación de A3C.

    Gestiona la configuración paramétrica, el escalado espectral, la adaptación de hiperparámetros
    y orquesta a los workers a través de sus subcomponentes anidados.
    """

    class BufferExperiencia:
        """Buffer circular rápido para activaciones, recompensas y ventajas."""

        def __init__(self, capacidad: int = 512):
            self.capacidad = max(16, int(capacidad))
            self.datos: List[Any] = []

        def __len__(self) -> int:
            return len(self.datos)

        def append(self, x: Any) -> None:
            self.datos.append(x)
            if len(self.datos) > self.capacidad:
                del self.datos[0:len(self.datos) - self.capacidad]

        def tail(self, n: int) -> List[Any]:
            return self.datos[-n:]

        def clear(self) -> None:
            self.datos.clear()

    class InicializadorConfigurado:
        """Motor matemático para inicialización, acondicionamiento y normalización espectral."""

        @staticmethod
        def potencia_singular(w: np.ndarray, iters: int = 4) -> float:
            wf = w.astype(np.float64)
            rng = np.random.default_rng(0)
            v = rng.normal(0, 1, (wf.shape[1], 1))
            v /= max(1e-12, float(np.linalg.norm(v)))
            u = np.zeros((wf.shape[0], 1), dtype=np.float64)
            for _ in range(iters):
                u = wf @ v
                u /= max(1e-12, float(np.linalg.norm(u)))
                v = wf.T @ u
                v /= max(1e-12, float(np.linalg.norm(v)))
            return float((u.T @ wf @ v)[0, 0])

        @classmethod
        def aplicar_espectral(cls, w: np.ndarray, usar_espectral: bool = True) -> np.ndarray:
            if not usar_espectral:
                return w
            sigma = cls.potencia_singular(w)
            return (w.astype(np.float64) / max(1e-12, sigma)).astype(_dt())

        @classmethod
        def inicializar_par_ac(
            cls,
            input_size: int,
            output_size: int,
            modo: str = "ortogonal",
            semilla: int = 42,
        ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
            shp_a = (input_size, output_size)
            shp_c = (input_size, 1)
            m = modo.lower()

            if m == 'ortogonal':
                pa = inicializar_pesos_ortogonal(shp_a, seed=semilla)
                pc = inicializar_pesos_ortogonal(shp_c, seed=semilla)
            elif m == 'espectral':
                pa = inicializar_pesos_espectral(shp_a, seed=semilla)
                pc = inicializar_pesos_espectral(shp_c, seed=semilla)
            elif m == 'xavier':
                pa = inicializar_pesos_xavier(shp_a, input_size, output_size, seed=semilla)
                pc = inicializar_pesos_xavier(shp_c, input_size, 1, seed=semilla)
            elif m == 'he':
                pa = inicializar_pesos_he(shp_a, input_size, seed=semilla)
                pc = inicializar_pesos_he(shp_c, input_size, seed=semilla)
            elif m == 'lecun':
                pa = inicializar_pesos_lecun(shp_a, input_size, seed=semilla)
                pc = inicializar_pesos_lecun(shp_c, input_size, seed=semilla)
            else:
                pa = np.zeros(shp_a, dtype=_dt())
                pc = np.zeros(shp_c, dtype=_dt())

            sa = np.zeros((1, output_size), dtype=_dt())
            sc = np.zeros((1, 1), dtype=_dt())
            return (
                np.ascontiguousarray(pa, dtype=_dt()),
                sa,
                np.ascontiguousarray(pc, dtype=_dt()),
                sc,
            )

    class MotorA3CDistribuido:
        """Motor de ejecución asíncrono y sincronización entre workers."""

        def __init__(self, owner: NeuronaDeComfiguracion):
            self.owner = owner

        @staticmethod
        def softmax_estable(logits: np.ndarray) -> np.ndarray:
            z = logits - np.max(logits, axis=-1, keepdims=True)
            e = np.exp(np.clip(z, -30.0, 30.0))
            return e / np.maximum(np.sum(e, axis=-1, keepdims=True), 1e-12)

        def calcular_gae_vectorizado(
            self, recompensas: List[float], valores: List[float], gamma: float, lambda_gae: float
        ) -> List[float]:
            r = np.asarray(recompensas, dtype=np.float64)
            v = np.asarray(valores, dtype=np.float64)
            n = len(r)
            adv = np.zeros(n, dtype=np.float64)
            acc = 0.0
            descuento = gamma * lambda_gae
            for t in range(n - 1, -1, -1):
                siguiente_val = 0.0 if t == n - 1 else v[t + 1]
                delta = r[t] + gamma * siguiente_val - v[t]
                acc = delta + descuento * acc
                adv[t] = acc
            if n > 1:
                adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            return adv.tolist()

    def __init__(
        self,
        input_size: int = 10,
        output_size: int = 4,
        nombre: str = "NeuronaDeComfiguracion",
        learning_rate_actor: float = 0.001,
        learning_rate_critic: float = 0.002,
        gamma: float = 0.99,
        lambda_gae: float = 0.95,
        num_workers: int = 4,
        update_frequency: int = 20,
        usar_ortogonal: bool = True,
        entropy_coef: float = 0.01,
        grad_clip: float = 5.0,
        epsilon: float = 1.0,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.995,
        semilla: int = 42,
        capacidad_historial: int = 512,
    ):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate_actor = float(learning_rate_actor)
        self.learning_rate_critic = float(learning_rate_critic)
        self.gamma = float(gamma)
        self.lambda_gae = float(lambda_gae)
        self.num_workers = max(1, int(num_workers))
        self.update_frequency = max(1, int(update_frequency))
        self.usar_ortogonal = bool(usar_ortogonal)
        self.entropy_coef = float(entropy_coef)
        self.grad_clip = float(grad_clip)
        self.epsilon = float(epsilon)
        self.epsilon_min = float(epsilon_min)
        self.epsilon_decay = float(epsilon_decay)
        self.semilla = int(semilla)
        self.rng = np.random.default_rng(self.semilla)

        # Componentes anidados
        self.inicializador = self.InicializadorConfigurado()
        self.motor = self.MotorA3CDistribuido(self)

        # Estado global compartido
        self.pesos_actor_global: Optional[np.ndarray] = None
        self.sesgo_actor_global: Optional[np.ndarray] = None
        self.pesos_critic_global: Optional[np.ndarray] = None
        self.sesgo_critic_global: Optional[np.ndarray] = None

        # Copias locales por worker
        self.pesos_actor_locales: Dict[int, np.ndarray] = {}
        self.sesgo_actor_locales: Dict[int, np.ndarray] = {}
        self.pesos_critic_locales: Dict[int, np.ndarray] = {}
        self.sesgo_critic_locales: Dict[int, np.ndarray] = {}

        self.pesos_lock = threading.Lock()
        self.buffer: List[Any] = []

        # Buffers circulares
        self.historial_qvalues = self.BufferExperiencia(capacidad_historial)
        self.historial_epsilon = self.BufferExperiencia(capacidad_historial)
        self.historial_advantages = self.BufferExperiencia(capacidad_historial * 4)
        self.historial_policy = self.BufferExperiencia(capacidad_historial)
        self.historial_sincronizaciones: List[float] = []

        self.tiempo_fwd: float = 0.0
        self.tiempo_upd: float = 0.0
        self.pasos: int = 0
        self._loss_ema: float = 0.0

        self.estadisticas_a3c: Dict[str, Any] = {
            'convergencia_actor_global': 0.0,
            'convergencia_critic_global': 0.0,
            'estabilidad_actor_global': 0.0,
            'estabilidad_critic_global': 0.0,
            'sincronizaciones': 0,
            'updates_globales': 0,
            'advantage_media': 0.0,
            'advantage_std': 0.0,
            'entropia_media': 0.0,
            'workers_activos': self.num_workers,
            'loss_media': 0.0,
            'q_max': 0.0,
            'q_min': 0.0,
            'q_media': 0.0,
            'q_std': 0.0,
            'exploracion_rate': 0,
            'exploitacion_rate': 0,
            't_medio_fwd_us': 0.0,
            't_medio_upd_us': 0.0,
            'buffer_len': 0,
            'valor_error_medio': 0.0,
            'policy_loss_medio': 0.0,
        }

        self.historial_actor_loss_global: List[float] = []
        self.historial_critic_loss_global: List[float] = []
        self.historial_advantages_global: List[float] = []
        self.historial_entropias_global: List[float] = []

        logger.info(f"NeuronaDeComfiguracion inicializada: {self.nombre}")

    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        """Inicializa pesos globales y locales con la configuración establecida."""
        m = (modo or ('ortogonal' if self.usar_ortogonal else 'xavier')).lower()
        pa, sa, pc, sc = self.inicializador.inicializar_par_ac(
            self.input_size, self.output_size, modo=m, semilla=self.semilla
        )
        self.pesos_actor_global = pa
        self.sesgo_actor_global = sa
        self.pesos_critic_global = pc
        self.sesgo_critic_global = sc
        self.pesos = self.pesos_actor_global

        with self.pesos_lock:
            for wid in range(self.num_workers):
                self.pesos_actor_locales[wid] = self.pesos_actor_global.copy()
                self.sesgo_actor_locales[wid] = self.sesgo_actor_global.copy()
                self.pesos_critic_locales[wid] = self.pesos_critic_global.copy()
                self.sesgo_critic_locales[wid] = self.sesgo_critic_global.copy()

        logger.info(f"Pesos A3C inicializados ({m}) para {self.num_workers} workers")

    def _asegurar(self) -> None:
        if self.pesos_actor_global is None or self.pesos_critic_global is None:
            self.inicializar_pesos()

    def _prep(self, estado: np.ndarray) -> np.ndarray:
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimensión de estado {x.shape[1]} != input {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    def calcular_entropy(self, prob: np.ndarray) -> float:
        p = np.asarray(prob, dtype=np.float64)
        p = p / max(1e-12, float(np.sum(p)))
        return float(-np.sum(p * np.log(p + 1e-8)))

    def forward_actor(self, estado: np.ndarray, worker_id: int = 0) -> np.ndarray:
        t0 = time.perf_counter()
        self._asegurar()
        w = self.pesos_actor_locales.get(worker_id, self.pesos_actor_global)
        b = self.sesgo_actor_locales.get(worker_id, self.sesgo_actor_global)
        x = self._prep(estado)
        wa = self.inicializador.aplicar_espectral(w, self.usar_ortogonal)
        logits = np.dot(x, wa).astype(np.float64) + b.astype(np.float64)
        probs = self.motor.softmax_estable(logits).astype(_dt(), copy=False)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(probs, dtype=_dt())

    def forward_critic(self, estado: np.ndarray, worker_id: int = 0) -> np.ndarray:
        t0 = time.perf_counter()
        self._asegurar()
        w = self.pesos_critic_locales.get(worker_id, self.pesos_critic_global)
        b = self.sesgo_critic_locales.get(worker_id, self.sesgo_critic_global)
        x = self._prep(estado)
        wc = self.inicializador.aplicar_espectral(w, self.usar_ortogonal)
        v = (np.dot(x, wc).astype(np.float64) + b.astype(np.float64)).astype(_dt(), copy=False)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(v, dtype=_dt())

    def forward(self, estado: np.ndarray, worker_id: int = 0) -> Tuple[np.ndarray, np.ndarray]:
        return self.forward_actor(estado, worker_id), self.forward_critic(estado, worker_id)

    def forward_batch(
        self, estados: np.ndarray, worker_id: int = 0
    ) -> Tuple[np.ndarray, np.ndarray]:
        self._asegurar()
        w_a = self.pesos_actor_locales.get(worker_id, self.pesos_actor_global)
        b_a = self.sesgo_actor_locales.get(worker_id, self.sesgo_actor_global)
        w_c = self.pesos_critic_locales.get(worker_id, self.pesos_critic_global)
        b_c = self.sesgo_critic_locales.get(worker_id, self.sesgo_critic_global)
        s = np.asarray(estados, dtype=np.float64)
        logits = s @ w_a.astype(np.float64) + b_a.astype(np.float64)
        probs = self.motor.softmax_estable(logits).astype(_dt())
        vals = (s @ w_c.astype(np.float64) + b_c.astype(np.float64)).astype(_dt())
        return probs, vals

    def seleccionar_accion(self, estado: np.ndarray, worker_id: int = 0) -> Tuple[int, float, float]:
        prob, val = self.forward(estado, worker_id)
        if self.epsilon > self.rng.random():
            accion = int(self.rng.integers(0, self.output_size))
            self.estadisticas_a3c['exploracion_rate'] += 1
        else:
            p = np.asarray(prob[0], dtype=np.float64)
            p = p / max(1e-12, float(np.sum(p)))
            accion = int(self.rng.choice(self.output_size, p=p))
            self.estadisticas_a3c['exploitacion_rate'] += 1
        return accion, float(prob[0, accion]), float(val[0, 0])

    def calcular_gae_advantages(self, recompensas: List[float], valores: List[float]) -> List[float]:
        adv = self.motor.calcular_gae_vectorizado(recompensas, valores, self.gamma, self.lambda_gae)
        self.estadisticas_a3c['advantage_media'] = float(np.mean(adv))
        self.estadisticas_a3c['advantage_std'] = float(np.std(adv))
        self.historial_advantages.append(adv)
        return adv

    def calcular_gradientes_worker(
        self,
        worker_id: int,
        estados: List[np.ndarray],
        acciones: List[int],
        advantages: List[float],
        valores_objetivo: List[float],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Calcula los gradientes locales del worker con bonus de entropía y recorte L2."""
        self._asegurar()
        X = np.vstack([self._prep(s) for s in estados]).astype(np.float64)
        A = np.asarray(acciones, dtype=np.int64) % self.output_size
        Adv = np.asarray(advantages, dtype=np.float64)
        Vt = np.asarray(valores_objetivo, dtype=np.float64).reshape(-1, 1)
        n = max(1, len(X))

        w_a = self.pesos_actor_locales.get(worker_id, self.pesos_actor_global).astype(np.float64)
        b_a = self.sesgo_actor_locales.get(worker_id, self.sesgo_actor_global).astype(np.float64)
        w_c = self.pesos_critic_locales.get(worker_id, self.pesos_critic_global).astype(np.float64)
        b_c = self.sesgo_critic_locales.get(worker_id, self.sesgo_critic_global).astype(np.float64)

        logits = X @ w_a + b_a
        probs = self.motor.softmax_estable(logits)
        vals = X @ w_c + b_c

        # Actor: ascenso por gradiente con entropía
        oh = np.zeros_like(probs)
        oh[np.arange(n), A] = 1.0
        dlogits = (oh - probs) * Adv[:, None] / n
        gap = X.T @ dlogits
        gas = dlogits.sum(axis=0, keepdims=True)

        ent = float(np.mean(-np.sum(probs * np.log(probs + 1e-8), axis=1)))
        if self.entropy_coef > 0:
            ent_grad = -(np.log(probs + 1e-8) + 1.0) * probs
            coef = self.entropy_coef / n
            gap += (X.T @ ent_grad) * coef
            gas += ent_grad.sum(axis=0, keepdims=True) * coef

        # Crítico: error cuadrático medio
        err = (Vt - vals) / n
        gcp = X.T @ err
        gcs = err.sum(axis=0, keepdims=True)

        # Recorte conjunto por norma L2
        norma = float(np.sqrt(np.sum(gap ** 2) + np.sum(gas ** 2) + np.sum(gcp ** 2) + np.sum(gcs ** 2)))
        if self.grad_clip > 0 and norma > self.grad_clip:
            f = self.grad_clip / (norma + 1e-12)
            gap *= f
            gas *= f
            gcp *= f
            gcs *= f

        self.estadisticas_a3c['entropia_media'] = ent * self.entropy_coef
        self.estadisticas_a3c['policy_loss_medio'] = float(np.mean(-np.log(probs[np.arange(n), A] + 1e-8) * Adv))
        self.estadisticas_a3c['valor_error_medio'] = float(np.mean((Vt - vals) ** 2))

        return gap.astype(_dt()), gas.astype(_dt()), gcp.astype(_dt()), gcs.astype(_dt())

    def actualizar_pesos_worker(
        self,
        worker_id: int,
        gap: np.ndarray,
        gas: np.ndarray,
        gcp: np.ndarray,
        gcs: np.ndarray,
    ) -> None:
        """Aplica gradientes asíncronos directamente sobre los pesos globales y sincroniza el worker."""
        with self.pesos_lock:
            t0 = time.perf_counter()
            lr_a = self.learning_rate_actor
            lr_c = self.learning_rate_critic

            # Ascenso para el Actor, descenso para el Crítico
            self.pesos_actor_global = np.ascontiguousarray(
                (self.pesos_actor_global.astype(np.float64) + lr_a * gap.astype(np.float64)).astype(_dt())
            )
            self.sesgo_actor_global = np.ascontiguousarray(
                (self.sesgo_actor_global.astype(np.float64) + lr_a * gas.astype(np.float64)).astype(_dt())
            )
            self.pesos_critic_global = np.ascontiguousarray(
                (self.pesos_critic_global.astype(np.float64) + lr_c * gcp.astype(np.float64)).astype(_dt())
            )
            self.sesgo_critic_global = np.ascontiguousarray(
                (self.sesgo_critic_global.astype(np.float64) + lr_c * gcs.astype(np.float64)).astype(_dt())
            )
            self.pesos = self.pesos_actor_global

            # Sincronización inmediata del worker local
            self.pesos_actor_locales[worker_id] = self.pesos_actor_global.copy()
            self.sesgo_actor_locales[worker_id] = self.sesgo_actor_global.copy()
            self.pesos_critic_locales[worker_id] = self.pesos_critic_global.copy()
            self.sesgo_critic_locales[worker_id] = self.sesgo_critic_global.copy()

            self.estadisticas_a3c['updates_globales'] += 1
            dt_us = (time.perf_counter() - t0) * 1e6
            self.estadisticas_a3c['t_medio_upd_us'] = (
                0.95 * self.estadisticas_a3c.get('t_medio_upd_us', 0.0) + 0.05 * dt_us
            )

    def sincronizar_pesos_globales(self) -> None:
        """Promedia y sincroniza los pesos locales de todos los workers hacia el modelo global."""
        with self.pesos_lock:
            pa = np.zeros_like(self.pesos_actor_global, dtype=np.float64)
            sa = np.zeros_like(self.sesgo_actor_global, dtype=np.float64)
            pc = np.zeros_like(self.pesos_critic_global, dtype=np.float64)
            sc = np.zeros_like(self.sesgo_critic_global, dtype=np.float64)

            w_count = max(1, self.num_workers)
            for wid in range(self.num_workers):
                pa += self.pesos_actor_locales.get(wid, self.pesos_actor_global).astype(np.float64)
                sa += self.sesgo_actor_locales.get(wid, self.sesgo_actor_global).astype(np.float64)
                pc += self.pesos_critic_locales.get(wid, self.pesos_critic_global).astype(np.float64)
                sc += self.sesgo_critic_locales.get(wid, self.sesgo_critic_global).astype(np.float64)

            self.pesos_actor_global = np.ascontiguousarray((pa / w_count).astype(_dt()))
            self.sesgo_actor_global = np.ascontiguousarray((sa / w_count).astype(_dt()))
            self.pesos_critic_global = np.ascontiguousarray((pc / w_count).astype(_dt()))
            self.sesgo_critic_global = np.ascontiguousarray((sc / w_count).astype(_dt()))
            self.pesos = self.pesos_actor_global

            for wid in range(self.num_workers):
                self.pesos_actor_locales[wid] = self.pesos_actor_global.copy()
                self.sesgo_actor_locales[wid] = self.sesgo_actor_global.copy()
                self.pesos_critic_locales[wid] = self.pesos_critic_global.copy()
                self.sesgo_critic_locales[wid] = self.sesgo_critic_global.copy()

            self.estadisticas_a3c['sincronizaciones'] += 1
            self.historial_sincronizaciones.append(time.time())

    def sincronizar_worker(self, worker_id: int) -> None:
        """Copia los pesos globales hacia la instancia local del worker."""
        with self.pesos_lock:
            self._asegurar()
            assert self.pesos_actor_global is not None and self.pesos_critic_global is not None
            self.pesos_actor_locales[worker_id] = self.pesos_actor_global.copy()
            self.sesgo_actor_locales[worker_id] = self.sesgo_actor_global.copy()
            self.pesos_critic_locales[worker_id] = self.pesos_critic_global.copy()
            self.sesgo_critic_locales[worker_id] = self.sesgo_critic_global.copy()

    def entrenar_episodio_worker(
        self,
        worker_id: int,
        estados: List[np.ndarray],
        acciones: List[int],
        recompensas: List[float],
        valores: List[float],
    ) -> Dict[str, float]:
        advantages = self.calcular_gae_advantages(recompensas, valores)
        valores_objetivo = (np.asarray(advantages, dtype=np.float64) + np.asarray(valores, dtype=np.float64)).tolist()
        gap, gas, gcp, gcs = self.calcular_gradientes_worker(
            worker_id, estados, acciones, advantages, valores_objetivo
        )
        self.actualizar_pesos_worker(worker_id, gap, gas, gcp, gcs)
        self.pasos += len(estados)
        if self.epsilon > self.epsilon_min:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        return {
            'recompensa_total': float(np.sum(recompensas)),
            'ventaja_media': float(np.mean(advantages)),
            'pasos': float(self.pasos),
        }

    def calcular_estabilidad_global(self) -> Tuple[float, float]:
        ea = ec = 0.0
        if self.pesos_actor_global is not None and len(self.pesos_actor_locales) > 1:
            diffs_a = [
                float(np.mean((self.pesos_actor_locales[wid].astype(np.float64) - self.pesos_actor_global.astype(np.float64)) ** 2))
                for wid in range(self.num_workers)
            ]
            diffs_c = [
                float(np.mean((self.pesos_critic_locales[wid].astype(np.float64) - self.pesos_critic_global.astype(np.float64)) ** 2))
                for wid in range(self.num_workers)
            ]
            ea = 1.0 / (1.0 + float(np.mean(diffs_a)))
            ec = 1.0 / (1.0 + float(np.mean(diffs_c)))
        self.estadisticas_a3c['estabilidad_actor_global'] = ea
        self.estadisticas_a3c['estabilidad_critic_global'] = ec
        return ea, ec

    def obtener_estadisticas_a3c(self) -> Dict[str, Any]:
        ea, ec = self.calcular_estabilidad_global()
        stats: Dict[str, Any] = {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'num_workers': self.num_workers,
            'learning_rate_actor': self.learning_rate_actor,
            'learning_rate_critic': self.learning_rate_critic,
            'gamma': self.gamma,
            'lambda_gae': self.lambda_gae,
            'epsilon': self.epsilon,
            'entropy_coef': self.entropy_coef,
            'sincronizaciones': self.estadisticas_a3c['sincronizaciones'],
            'updates_globales': self.estadisticas_a3c['updates_globales'],
            'estabilidad_actor_global': ea,
            'estabilidad_critic_global': ec,
            'advantage_media': self.estadisticas_a3c['advantage_media'],
            'advantage_std': self.estadisticas_a3c['advantage_std'],
            'entropia_media': self.estadisticas_a3c['entropia_media'],
            'policy_loss_medio': self.estadisticas_a3c['policy_loss_medio'],
            'valor_error_medio': self.estadisticas_a3c['valor_error_medio'],
            't_medio_fwd_us': self.tiempo_fwd / max(1, self.pasos + 1) * 1e6,
            't_medio_upd_us': self.estadisticas_a3c.get('t_medio_upd_us', 0.0),
        }
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        ea, ec = self.calcular_estabilidad_global()
        est = {
            'actor_estable': ea > 0.6,
            'critic_estable': ec > 0.6,
            'epsilon_ok': self.epsilon_min <= self.epsilon <= 1.0,
            'workers_activos_ok': len(self.pesos_actor_locales) == self.num_workers,
        }
        if self.pesos_actor_global is not None and self.pesos_critic_global is not None:
            est['pesos_actor_no_explosivos'] = float(np.max(np.abs(self.pesos_actor_global))) < 20.0
            est['pesos_critic_no_explosivos'] = float(np.max(np.abs(self.pesos_critic_global))) < 20.0
            est['sin_nan'] = bool(not np.isnan(self.pesos_actor_global).any() and not np.isnan(self.pesos_critic_global).any())
        else:
            est.update({'pesos_actor_no_explosivos': True, 'pesos_critic_no_explosivos': True, 'sin_nan': True})
        return est

    def reinicializar_con_parametros(
        self,
        learning_rate_actor: Optional[float] = None,
        learning_rate_critic: Optional[float] = None,
        gamma: Optional[float] = None,
        lambda_gae: Optional[float] = None,
        num_workers: Optional[int] = None,
    ) -> None:
        if learning_rate_actor is not None:
            self.learning_rate_actor = float(learning_rate_actor)
        if learning_rate_critic is not None:
            self.learning_rate_critic = float(learning_rate_critic)
        if gamma is not None:
            self.gamma = float(gamma)
        if lambda_gae is not None:
            self.lambda_gae = float(lambda_gae)
        if num_workers is not None:
            self.num_workers = max(1, int(num_workers))
        self.inicializar_pesos()
        self.resetear_historial()
        self.historial_actor_loss_global.clear()
        self.historial_critic_loss_global.clear()
        self.historial_advantages_global.clear()
        self.historial_entropias_global.clear()
        self.historial_sincronizaciones.clear()
        self.estadisticas_a3c['sincronizaciones'] = 0
        self.estadisticas_a3c['updates_globales'] = 0
        self.pasos = 0
        logger.info(f"Neurona A3C reinicializada: lr_actor={self.learning_rate_actor}, workers={self.num_workers}")

    def resetear_historial(self) -> None:
        super().resetear_historial()
        self.historial_qvalues.clear()
        self.historial_epsilon.clear()
        self.historial_advantages.clear()
        self.historial_policy.clear()

    def a_dict(self) -> Dict[str, Any]:
        return {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'lr_actor': self.learning_rate_actor,
            'lr_critic': self.learning_rate_critic,
            'gamma': self.gamma,
            'lambda_gae': self.lambda_gae,
            'num_workers': self.num_workers,
            'pesos_actor': self.pesos_actor_global.tolist() if self.pesos_actor_global is not None else None,
            'sesgo_actor': self.sesgo_actor_global.tolist() if self.sesgo_actor_global is not None else None,
            'pesos_critic': self.pesos_critic_global.tolist() if self.pesos_critic_global is not None else None,
            'sesgo_critic': self.sesgo_critic_global.tolist() if self.sesgo_critic_global is not None else None,
        }

    def guardar(self, ruta: str) -> None:
        import json
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.a_dict(), f)

    def cargar(self, ruta: str) -> None:
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.inicializar_pesos()
        if d.get('pesos_actor') is not None:
            self.pesos_actor_global = np.asarray(d['pesos_actor'], dtype=_dt())
        if d.get('sesgo_actor') is not None:
            self.sesgo_actor_global = np.asarray(d['sesgo_actor'], dtype=_dt())
        if d.get('pesos_critic') is not None:
            self.pesos_critic_global = np.asarray(d['pesos_critic'], dtype=_dt())
        if d.get('sesgo_critic') is not None:
            self.sesgo_critic_global = np.asarray(d['sesgo_critic'], dtype=_dt())

        with self.pesos_lock:
            for wid in range(self.num_workers):
                self.pesos_actor_locales[wid] = self.pesos_actor_global.copy()
                self.sesgo_actor_locales[wid] = self.sesgo_actor_global.copy()
                self.pesos_critic_locales[wid] = self.pesos_critic_global.copy()
                self.sesgo_critic_locales[wid] = self.sesgo_critic_global.copy()

    def __str__(self) -> str:
        return (
            f"NeuronaDeComfiguracion(in={self.input_size}, out={self.output_size}, "
            f"lr_a={self.learning_rate_actor}, lr_c={self.learning_rate_critic}, workers={self.num_workers})"
        )

    def __repr__(self) -> str:
        return self.__str__()


# Alias de retrocompatibilidad
NeuronaRefuerzoA3C = NeuronaDeComfiguracion

__all__ = [
    "NeuronaDeComfiguracion",
    "NeuronaRefuerzoA3C",
]
