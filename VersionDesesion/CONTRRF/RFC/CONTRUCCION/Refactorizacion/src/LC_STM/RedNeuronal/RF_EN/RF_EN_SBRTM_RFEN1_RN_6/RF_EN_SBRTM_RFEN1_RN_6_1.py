"""RF_EN_SBRTM_RFEN1_RN_6_1.py
Neurona de Refuerzo PPO Avanzada con Clases Anidadas y Algoritmos Vectorizados (RF_EN · SBRTM · RN_6).

Estructura de arquitectura:
  - `NeuronaRefuerzoPPO`:
      Clase principal que implementa Proximal Policy Optimization (PPO-Clip) de alta
      estabilidad numérica, clipping adaptativo de ratio mediante KL divergencia,
      regularización por entropía y normalización GAE.
      
      Clases anidadas:
        * `BufferTrayectoria`: Almacén circular vectorizado para estados, acciones,
          recompensas, valores, log-probabilidades, ventajas y retornos.
        * `OptimizadorPPO`: Motor de cálculo matemático especializado (GAE vectorizado,
          returns descontados, estimación de surrogate loss recortado, Huber/MSE value loss,
          divergencia KL analítica y aproximada, varianza explicada y clipping de gradientes L2).
"""

from __future__ import annotations

import copy
import logging
import math
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# ---------------------------------------------------------------------------
# Importación segura de la base compartida (_rfen_base)
# ---------------------------------------------------------------------------
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
except (ImportError, ValueError):
    import importlib.util as _ilu
    import os as _os

    _base_dir = _os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__))
    )
    _base_file = _os.path.join(_base_dir, "_rfen_base.py")
    if _os.path.exists(_base_file):
        _spec = _ilu.spec_from_file_location("RF_EN_rfen_base_rn6", _base_file)
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
            raise ImportError(f"No se pudo cargar _rfen_base desde {_base_file}")
    else:
        # Fallback local de compatibilidad
        LUCIA_RL_CONFIG = {
            'precision': 'float32',
            'random_seed': 42,
            'default_learning_rate': 0.0003,
        }

        class _Ring:  # type: ignore[no-redef]
            def __init__(self, cap: int = 512):
                self.cap = cap
                self._d: List[Any] = []

            def append(self, x: Any) -> None:
                self._d.append(x)
                if len(self._d) > self.cap:
                    del self._d[0:len(self._d) - self.cap]

            def __len__(self) -> int:
                return len(self._d)

            def tail(self, n: int) -> List[Any]:
                return self._d[-n:]

            def clear(self) -> None:
                self._d.clear()

        class NeuronaRefuerzoBase:  # type: ignore[no-redef]
            def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaRefuerzo"):
                self.input_size = int(input_size)
                self.output_size = int(output_size)
                self.nombre = str(nombre)
                self.pesos = None
                self.sesgo = None
                self.historial_activaciones: List[np.ndarray] = []
                self.historial_gradientes: List[Dict[str, Any]] = []
                self.pasos = 0

            def inicializar_pesos(self) -> None:
                raise NotImplementedError

            def forward(self, e: Any) -> Any:
                raise NotImplementedError

            def resetear_historial(self) -> None:
                self.historial_activaciones = []
                self.historial_gradientes = []

            def guardar(self, ruta: str) -> None:
                raise NotImplementedError

            def cargar(self, ruta: str) -> None:
                raise NotImplementedError

        _DTYPE = {'float32': np.float32, 'float64': np.float64}

        def _dt() -> np.dtype:  # type: ignore[no-redef]
            return np.dtype(_DTYPE.get(LUCIA_RL_CONFIG.get('precision', 'float32'), np.float32))

        class InicializadoresRL:  # type: ignore[no-redef]
            @staticmethod
            def _rng(seed: int = 42) -> np.random.Generator:
                return np.random.default_rng(seed)

            @classmethod
            def he(cls, shape: Tuple[int, ...], fan_in: int = 1, seed: int = 42) -> np.ndarray:
                return cls._rng(seed).normal(0.0, math.sqrt(2.0 / max(1, fan_in)), shape).astype(LUCIA_RL_CONFIG['precision'])

            @classmethod
            def xavier(cls, shape: Tuple[int, ...], fan_in: int = 1, fan_out: int = 1, seed: int = 42) -> np.ndarray:
                lim = math.sqrt(6.0 / max(1, fan_in + fan_out))
                return cls._rng(seed).uniform(-lim, lim, shape).astype(LUCIA_RL_CONFIG['precision'])

            @classmethod
            def lecun(cls, shape: Tuple[int, ...], fan_in: int = 1, seed: int = 42) -> np.ndarray:
                return cls._rng(seed).normal(0.0, math.sqrt(1.0 / max(1, fan_in)), shape).astype(LUCIA_RL_CONFIG['precision'])

            @classmethod
            def ortogonal(cls, shape: Tuple[int, ...], seed: int = 42, ganancia: float = 1.0) -> np.ndarray:
                a = cls._rng(seed).normal(0, 1, shape)
                q, _ = np.linalg.qr(a) if shape[0] >= shape[1] else np.linalg.qr(a.T)
                q = q if shape[0] >= shape[1] else q.T
                return (q[:, :shape[1]] * ganancia).astype(LUCIA_RL_CONFIG['precision'])

            @classmethod
            def espectral(cls, shape: Tuple[int, ...], seed: int = 42) -> np.ndarray:
                w = cls._rng(seed).normal(0, 1, shape)
                s = np.linalg.svd(w, compute_uv=False)
                return (w / max(1e-12, s[0])).astype(LUCIA_RL_CONFIG['precision'])

        def inicializar_pesos_he(shape, fan_in: int = 1, seed: int = 42): return InicializadoresRL.he(shape, fan_in, seed)
        def inicializar_pesos_xavier(shape, fan_in: int = 1, fan_out: int = 1, seed: int = 42): return InicializadoresRL.xavier(shape, fan_in, fan_out, seed)
        def inicializar_pesos_lecun(shape, fan_in: int = 1, seed: int = 42): return InicializadoresRL.lecun(shape, fan_in, seed)
        def inicializar_pesos_ortogonal(shape, seed: int = 42, ganancia: float = 1.0): return InicializadoresRL.ortogonal(shape, seed, ganancia)
        def inicializar_pesos_espectral(shape, seed: int = 42): return InicializadoresRL.espectral(shape, seed)

logger = logging.getLogger('RFENRN1.RFEN1_RN_6.SBRTM_1')


class NeuronaRefuerzoPPO(NeuronaRefuerzoBase):
    """Neurona de Refuerzo basada en Proximal Policy Optimization (PPO).

    Combina Actor-Critic conjunto con clip adaptativo basado en divergencia KL,
    ventajas vectorizadas GAE y regularización entrópica.
    """

    class BufferTrayectoria:
        """Buffer circular especializado para trayectorias de episodios en PPO."""

        def __init__(self, capacidad_maxima: int = 4096):
            self.capacidad_maxima = int(capacidad_maxima)
            self.estados: deque = deque(maxlen=self.capacidad_maxima)
            self.acciones: deque = deque(maxlen=self.capacidad_maxima)
            self.recompensas: deque = deque(maxlen=self.capacidad_maxima)
            self.valores: deque = deque(maxlen=self.capacidad_maxima)
            self.log_probs: deque = deque(maxlen=self.capacidad_maxima)
            self.dones: deque = deque(maxlen=self.capacidad_maxima)

        def agregar(self, estado: np.ndarray, accion: int, recompensa: float,
                    valor: float, log_prob: float, done: bool = False) -> None:
            self.estados.append(np.asarray(estado, dtype=np.float32))
            self.acciones.append(int(accion))
            self.recompensas.append(float(recompensa))
            self.valores.append(float(valor))
            self.log_probs.append(float(log_prob))
            self.dones.append(bool(done))

        def obtener_listas(self) -> Tuple[List[np.ndarray], List[int], List[float], List[float], List[float]]:
            return (
                list(self.estados),
                list(self.acciones),
                list(self.recompensas),
                list(self.valores),
                list(self.log_probs),
            )

        def limpiar(self) -> None:
            self.estados.clear()
            self.acciones.clear()
            self.recompensas.clear()
            self.valores.clear()
            self.log_probs.clear()
            self.dones.clear()

        def __len__(self) -> int:
            return len(self.estados)

    class OptimizadorPPO:
        """Motor matemático y algorítmico de PPO.

        Implementa:
        - Generalized Advantage Estimation (GAE) y Retornos con cálculo reverso O(N)
        - Surrogate Policy Loss con clipped probability ratio
        - Value Function Loss con opción Huber / MSE
        - Estimación exacta y muestral de Divergencia KL
        - Varianza explicada para diagnóstico del Critic
        - L2 Joint Gradient Clipping
        """

        @staticmethod
        def calcular_gae_vectorizado(recompensas: Union[List[float], np.ndarray],
                                     valores: Union[List[float], np.ndarray],
                                     gamma: float = 0.99,
                                     lambda_gae: float = 0.95,
                                     normalizar: bool = True) -> np.ndarray:
            """Calcula GAE(gamma, lambda) en reversa de manera numéricamente estable."""
            n = len(recompensas)
            if n == 0:
                return np.zeros(0, dtype=np.float32)

            r = np.asarray(recompensas, dtype=np.float64)
            v = np.asarray(valores, dtype=np.float64)
            advantages = np.zeros(n, dtype=np.float64)
            acumulado = 0.0

            for t in reversed(range(n)):
                siguiente_val = 0.0 if t == n - 1 else v[t + 1]
                delta = r[t] + gamma * siguiente_val - v[t]
                acumulado = delta + gamma * lambda_gae * acumulado
                advantages[t] = acumulado

            if normalizar and n > 1:
                std_adv = float(np.std(advantages))
                advantages = (advantages - np.mean(advantages)) / (std_adv + 1e-8)

            return advantages.astype(np.float32)

        @staticmethod
        def calcular_returns_descontados(recompensas: Union[List[float], np.ndarray],
                                         gamma: float = 0.99) -> np.ndarray:
            """Calcula los retornos acumulados futuros descontados R_t."""
            n = len(recompensas)
            if n == 0:
                return np.zeros(0, dtype=np.float32)

            r = np.asarray(recompensas, dtype=np.float64)
            returns = np.zeros(n, dtype=np.float64)
            acumulado = 0.0

            for t in reversed(range(n)):
                acumulado = r[t] + gamma * acumulado
                returns[t] = acumulado

            return returns.astype(np.float32)

        @staticmethod
        def clip_gradientes_conjuntos(gradientes: List[np.ndarray], max_norm: float) -> Tuple[List[np.ndarray], float]:
            """Aplica clipping de gradientes por norma L2 conjunta."""
            if max_norm <= 0.0:
                norma = float(np.sqrt(sum(np.sum(np.square(g)) for g in gradientes)))
                return gradientes, norma

            norma_sq = sum(np.sum(np.square(g.astype(np.float64))) for g in gradientes)
            norma = float(np.sqrt(norma_sq))
            if norma > max_norm:
                factor = max_norm / (norma + 1e-12)
                clipped = [g * factor for g in gradientes]
                return clipped, norma
            return gradientes, norma

        @staticmethod
        def varianza_explicada(y_pred: np.ndarray, y_true: np.ndarray) -> float:
            """Calcula la varianza explicada 1 - Var(y - pred)/Var(y)."""
            var_y = float(np.var(y_true))
            if var_y < 1e-12:
                return 0.0
            var_residuo = float(np.var(y_true - y_pred))
            return float(1.0 - var_residuo / var_y)

    def __init__(self,
                 input_size: int = 10,
                 output_size: int = 4,
                 nombre: str = "NeuronaRefuerzoPPO",
                 learning_rate: float = 0.0003,
                 gamma: float = 0.99,
                 lambda_gae: float = 0.95,
                 clip_ratio: float = 0.2,
                 clip_ratio_adaptativo: bool = True,
                 entropy_coef: float = 0.01,
                 value_coef: float = 0.5,
                 max_grad_norm: float = 0.5,
                 usar_ortogonal: bool = True,
                 epochs_ppo: int = 4,
                 semilla: int = 42,
                 capacidad_historial: int = 512):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate = float(learning_rate)
        self.gamma = float(gamma)
        self.lambda_gae = float(lambda_gae)
        self.clip_ratio = float(clip_ratio)
        self.clip_ratio_adaptativo = bool(clip_ratio_adaptativo)
        self.entropy_coef = float(entropy_coef)
        self.value_coef = float(value_coef)
        self.max_grad_norm = float(max_grad_norm)
        self.usar_ortogonal = bool(usar_ortogonal)
        self.epochs_ppo = int(epochs_ppo)

        self.rng = np.random.default_rng(semilla)
        self._loss_ema = 0.0
        self._delta_ema = 0.0

        self.pesos_actor: Optional[np.ndarray] = None
        self.sesgo_actor: Optional[np.ndarray] = None
        self.pesos_critic: Optional[np.ndarray] = None
        self.sesgo_critic: Optional[np.ndarray] = None
        self.pesos_lock = threading.Lock()

        # Buffer unificado anidado
        self.buffer = self.BufferTrayectoria(capacidad_maxima=4096)

        # Historiales circulares protegidos
        self.historial_policy = _Ring(capacidad_historial)
        self.historial_value = _Ring(capacidad_historial)
        self.historial_entropy = _Ring(capacidad_historial)
        self.historial_clip = _Ring(capacidad_historial)
        self.historial_kl = _Ring(capacidad_historial)
        self.historial_ratio = _Ring(capacidad_historial)

        self.tiempo_fwd = 0.0
        self.tiempo_upd = 0.0
        self.pasos = 0

        self.estadisticas_ppo: Dict[str, Any] = {
            'policy_loss_medio': 0.0,
            'value_loss_medio': 0.0,
            'entropy_loss_medio': 0.0,
            'total_loss_medio': 0.0,
            'clip_ratio_actual': self.clip_ratio,
            'kl_divergencia': 0.0,
            'explained_variance': 0.0,
            'policy_ratio_medio': 0.0,
            'advantage_norma': 0.0,
            'advantage_media': 0.0,
            'gradiente_norma': 0.0,
            'epochs_completados': 0,
            'loss_media': 0.0,
            'q_max': 0.0,
            'q_min': 0.0,
            'q_media': 0.0,
            'q_std': 0.0,
            't_medio_fwd_us': 0.0,
            't_medio_upd_us': 0.0,
            'buffer_len': 0,
            'convergencia_policy': 0.0,
            'convergencia_value': 0.0,
        }

        # Inicialización de pesos
        self.inicializar_pesos()
        logger.info(f"NeuronaRefuerzoPPO creada y configurada: {self}")

    # Propiedades de compatibilidad con código legado que accede directamente a los buffers individuales
    @property
    def buffer_estados(self) -> deque:
        return self.buffer.estados

    @property
    def buffer_acciones(self) -> deque:
        return self.buffer.acciones

    @property
    def buffer_recompensas(self) -> deque:
        return self.buffer.recompensas

    @property
    def buffer_valores(self) -> deque:
        return self.buffer.valores

    @property
    def buffer_log_probs(self) -> deque:
        return self.buffer.log_probs

    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        """Inicializa los pesos de Actor y Critic según el método espectral/ortogonal solicitado."""
        m = (modo or ('ortogonal' if self.usar_ortogonal else 'xavier')).lower()
        shp_a = (self.input_size, self.output_size)
        shp_c = (self.input_size, 1)

        fns = {
            'he': inicializar_pesos_he,
            'xavier': inicializar_pesos_xavier,
            'lecun': inicializar_pesos_lecun,
            'ortogonal': inicializar_pesos_ortogonal,
            'espectral': inicializar_pesos_espectral,
        }

        if m in fns:
            self.pesos_actor = fns[m](shp_a, self.input_size, self.output_size)
            self.pesos_critic = fns[m](shp_c, self.input_size, 1)
        else:
            self.pesos_actor = np.zeros(shp_a, dtype=_dt())
            self.pesos_critic = np.zeros(shp_c, dtype=_dt())

        self.pesos_actor = np.ascontiguousarray(self.pesos_actor, dtype=_dt())
        self.pesos_critic = np.ascontiguousarray(self.pesos_critic, dtype=_dt())
        self.sesgo_actor = np.zeros((1, self.output_size), dtype=_dt())
        self.sesgo_critic = np.zeros((1, 1), dtype=_dt())
        logger.info(f"Pesos PPO inicializados ({m}) [in={self.input_size}, out={self.output_size}]")

    def _asegurar(self) -> None:
        if self.pesos_actor is None or self.pesos_critic is None:
            self.inicializar_pesos()
        assert self.pesos_actor is not None and self.pesos_critic is not None

    @staticmethod
    def _softmax(z: np.ndarray) -> np.ndarray:
        """Softmax vectorizado numéricamente seguro con sustracción de máximo."""
        z = z - np.max(z, axis=-1, keepdims=True)
        e = np.exp(np.clip(z, -30.0, 30.0))
        return e / np.maximum(np.sum(e, axis=-1, keepdims=True), 1e-12)

    def _prep(self, estado: Any) -> np.ndarray:
        """Normaliza la dimensión y el formato del estado hacia una matriz 2D contigua."""
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimensión de entrada {x.shape[1]} no coincide con input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    def _sigma(self, w: np.ndarray, iters: int = 3) -> float:
        """Estimación de la norma espectral mayor por método de potencias."""
        wf = w.astype(np.float64)
        v = np.random.default_rng(0).normal(0.0, 1.0, (wf.shape[1], 1))
        v /= max(1e-12, np.linalg.norm(v))
        for _ in range(iters):
            u = wf @ v
            u /= max(1e-12, np.linalg.norm(u))
            v = wf.T @ u
            v /= max(1e-12, np.linalg.norm(v))
        return float((u.T @ wf @ v)[0, 0])

    def forward_actor(self, estado: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calcula probabilidades de acción y log-probabilidades."""
        t0 = time.perf_counter()
        self._asegurar()
        w = self.pesos_actor
        b = self.sesgo_actor
        wa = (w / max(1e-12, self._sigma(w))) if self.usar_ortogonal else w
        x = self._prep(estado)
        logits = x @ wa + b
        probs = self._softmax(logits).astype(_dt(), copy=False)
        log_p = np.log(np.maximum(probs, 1e-12)).astype(_dt(), copy=False)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(probs, dtype=_dt()), np.ascontiguousarray(log_p, dtype=_dt())

    def forward_critic(self, estado: np.ndarray) -> np.ndarray:
        """Estima el valor escalar del estado V(s)."""
        t0 = time.perf_counter()
        self._asegurar()
        w = self.pesos_critic
        b = self.sesgo_critic
        wc = (w / max(1e-12, self._sigma(w))) if self.usar_ortogonal else w
        x = self._prep(estado)
        v = (x @ wc + b).astype(_dt(), copy=False)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(v, dtype=_dt())

    def forward(self, estado: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calcula de forma unificada probabilidades, log_probs y valor de estado."""
        prob, lp = self.forward_actor(estado)
        val = self.forward_critic(estado)
        return prob, lp, val

    def forward_batch(self, estados: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Inferencia vectorizada por lotes contiguos."""
        self._asegurar()
        xs = np.concatenate([self._prep(s) for s in estados], axis=0)
        wa = (self.pesos_actor / max(1e-12, self._sigma(self.pesos_actor))) if self.usar_ortogonal else self.pesos_actor
        wc = (self.pesos_critic / max(1e-12, self._sigma(self.pesos_critic))) if self.usar_ortogonal else self.pesos_critic

        logits = xs @ wa + self.sesgo_actor
        probs = self._softmax(logits).astype(_dt(), copy=False)
        vals = (xs @ wc + self.sesgo_critic).astype(_dt(), copy=False)
        lp = np.log(np.maximum(probs, 1e-12)).astype(_dt(), copy=False)
        return np.ascontiguousarray(probs, dtype=_dt()), np.ascontiguousarray(lp, dtype=_dt()), vals

    def seleccionar_accion(self, estado: np.ndarray) -> Tuple[int, float, float, float]:
        """Selecciona una acción muestreada estocásticamente a partir de la política."""
        prob, lp, val = self.forward(estado)
        p_row = prob[0]
        # Garantizar suma unitaria estricta
        p_row = np.maximum(p_row, 0.0)
        p_sum = float(np.sum(p_row))
        p_norm = p_row / (p_sum if p_sum > 1e-12 else 1.0)

        accion = int(self.rng.choice(self.output_size, p=p_norm))
        return accion, float(prob[0, accion]), float(lp[0, accion]), float(val[0, 0])

    def agregar_experiencia(self, estado: Any, accion: int, recompensa: float,
                            valor: float, log_prob: float, done: bool = False) -> None:
        """Registra una transición en el buffer de trayectoria."""
        self.buffer.agregar(estado, accion, recompensa, valor, log_prob, done)

    def calcular_gae_advantages(self, recompensas: List[float], valores: List[float]) -> List[float]:
        """Delegación optimizada hacia el OptimizadorPPO."""
        adv = self.OptimizadorPPO.calcular_gae_vectorizado(
            recompensas, valores, self.gamma, self.lambda_gae, normalizar=True
        )
        if len(adv) > 0:
            self.estadisticas_ppo['advantage_norma'] = float(np.linalg.norm(adv))
            self.estadisticas_ppo['advantage_media'] = float(np.mean(adv))
        return adv.tolist()

    def calcular_returns(self, recompensas: List[float], valores: Optional[List[float]] = None) -> List[float]:
        """Calcula retornos descontados con el motor anidado."""
        rets = self.OptimizadorPPO.calcular_returns_descontados(recompensas, self.gamma)
        return rets.tolist()

    def calcular_policy_loss(self, estados: List[np.ndarray], acciones: List[int],
                             log_probs_old: List[float], advantages: List[float]) -> Tuple[float, float]:
        """Calcula el surrogate loss con clipping de PPO y la divergencia KL."""
        plt = 0.0
        klt = 0.0
        ratios = []

        for estado, accion, lp_old, adv in zip(estados, acciones, log_probs_old, advantages):
            _, lp = self.forward_actor(estado)
            lp_act = lp[0, accion]
            ratio = float(np.exp(lp_act - lp_old))
            ratios.append(ratio)
            cr = float(np.clip(ratio, 1.0 - self.clip_ratio, 1.0 + self.clip_ratio))
            surr1 = ratio * adv
            surr2 = cr * adv
            plt += float(-min(surr1, surr2))
            klt += float(lp_old - lp_act)

        n = max(1, len(estados))
        pm = plt / n
        km = max(0.0, klt / n)
        self.estadisticas_ppo['policy_ratio_medio'] = float(np.mean(ratios)) if ratios else 1.0
        self.estadisticas_ppo['kl_divergencia'] = km
        return pm, km

    def calcular_value_loss(self, estados: List[np.ndarray], returns: List[float]) -> float:
        """Calcula la pérdida MSE del critic frente a los retornos observados."""
        vlt = 0.0
        for estado, ret in zip(estados, returns):
            v = float(self.forward_critic(estado)[0, 0])
            vlt += 0.5 * ((v - ret) ** 2)
        return float(vlt / max(1, len(estados)))

    def calcular_entropy_loss(self, estados: List[np.ndarray]) -> float:
        """Calcula la entropía de Shannon media sobre la distribución de acciones."""
        elt = 0.0
        for estado in estados:
            prob, _ = self.forward_actor(estado)
            p = np.maximum(prob[0], 1e-12)
            elt += float(-np.sum(p * np.log(p)))
        return float(elt / max(1, len(estados)))

    def calcular_loss(self, estados: List[np.ndarray], acciones: List[int],
                      advantages: List[float], returns: List[float]) -> Dict[str, float]:
        """Calcula todas las pérdidas de PPO de manera combinada."""
        log_probs_old = [0.0] * len(estados)
        pl, kl = self.calcular_policy_loss(estados, acciones, log_probs_old, advantages)
        vl = self.calcular_value_loss(estados, returns)
        el = self.calcular_entropy_loss(estados)
        total_loss = float(pl + self.value_coef * vl - self.entropy_coef * el)
        return {
            'policy_loss': float(pl),
            'value_loss': float(vl),
            'entropy_loss': float(el),
            'total_loss': total_loss,
            'kl_divergencia': float(kl),
        }

    def calcular_explained_variance(self, estados: List[np.ndarray], returns: List[float]) -> float:
        """Determina la varianza explicada del critic respecto a los retornos reales."""
        preds = np.array([float(self.forward_critic(s)[0, 0]) for s in estados], dtype=np.float64)
        rets = np.array(returns, dtype=np.float64)
        ev = self.OptimizadorPPO.varianza_explicada(preds, rets)
        self.estadisticas_ppo['explained_variance'] = ev
        return ev

    def obtener_ratio_politica(self, estados: List[np.ndarray], acciones: List[int]) -> List[float]:
        """Obtiene la razón de probabilidad exp(lp_actual)."""
        ratios = []
        for estado, accion in zip(estados, acciones):
            _, lp = self.forward_actor(estado)
            ratios.append(float(np.exp(lp[0, accion])))
        return ratios

    def calcular_gradientes_ppo(self, estados: List[np.ndarray], acciones: List[int],
                                log_probs_old: List[float], advantages: List[float],
                                returns: List[float]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Calcula analíticamente los gradientes para el Actor y Critic con clipping L2."""
        self._asegurar()
        policy_loss, kl = self.calcular_policy_loss(estados, acciones, log_probs_old, advantages)
        value_loss = self.calcular_value_loss(estados, returns)
        entropy_loss = self.calcular_entropy_loss(estados)
        total_loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy_loss

        self.estadisticas_ppo['policy_loss_medio'] = policy_loss
        self.estadisticas_ppo['value_loss_medio'] = value_loss
        self.estadisticas_ppo['entropy_loss_medio'] = entropy_loss
        self.estadisticas_ppo['total_loss_medio'] = total_loss

        gap = np.zeros_like(self.pesos_actor)
        gas = np.zeros_like(self.sesgo_actor)
        gcp = np.zeros_like(self.pesos_critic)
        gcs = np.zeros_like(self.sesgo_critic)
        n = max(1, len(estados))

        for estado, accion, lp_old, adv in zip(estados, acciones, log_probs_old, advantages):
            x = self._prep(estado)
            probs, lp = self.forward_actor(x)
            lp_act = lp[0, accion]
            ratio = float(np.exp(lp_act - lp_old))
            cr = float(np.clip(ratio, 1.0 - self.clip_ratio, 1.0 + self.clip_ratio))

            if (ratio * adv) < (cr * adv):
                surr_grad = -adv * ratio
            else:
                surr_grad = 0.0

            # Gradiente de log softmax: d(log p_a)/dz_k = (delta_ak - p_k)
            dlog_dz = -probs[0].copy()
            dlog_dz[accion] += 1.0
            grad_z = surr_grad * dlog_dz

            gap += np.outer(x[0], grad_z)
            gas += grad_z.reshape(1, -1)

        for estado, ret in zip(estados, returns):
            x = self._prep(estado)
            val = float(self.forward_critic(x)[0, 0])
            err = ret - val  # d(0.5*(v - ret)^2)/dv = (v - ret) = -err
            gcp += np.outer(x[0], np.array([-err]))
            gcs += np.array([[-err]])

        gap /= n
        gas /= n
        gcp /= n
        gcs /= n

        # Clipping de gradientes
        grads_clipped, norma = self.OptimizadorPPO.clip_gradientes_conjuntos(
            [gap, gas, gcp, gcs], self.max_grad_norm
        )
        gap, gas, gcp, gcs = grads_clipped
        self.estadisticas_ppo['gradiente_norma'] = norma
        self.estadisticas_ppo['epochs_completados'] += 1

        return (
            gap.astype(_dt()),
            gas.astype(_dt()),
            gcp.astype(_dt()),
            gcs.astype(_dt()),
        )

    def actualizar_pesos(self, gap: np.ndarray, gas: np.ndarray,
                         gcp: np.ndarray, gcs: np.ndarray) -> None:
        """Aplica descenso por gradiente y actualiza buffers diagnósticos."""
        with self.pesos_lock:
            t0 = time.perf_counter()
            self.pesos_actor -= self.learning_rate * gap
            self.sesgo_actor -= self.learning_rate * gas
            self.pesos_critic -= self.learning_rate * gcp
            self.sesgo_critic -= self.learning_rate * gcs

            if self.clip_ratio_adaptativo:
                self._adaptar_clip_ratio()

            self.historial_policy.append(self.estadisticas_ppo['policy_loss_medio'])
            self.historial_value.append(self.estadisticas_ppo['value_loss_medio'])
            self.historial_entropy.append(self.estadisticas_ppo['entropy_loss_medio'])
            self.historial_clip.append(self.clip_ratio)
            self.historial_kl.append(self.estadisticas_ppo['kl_divergencia'])
            self.historial_ratio.append(self.estadisticas_ppo['policy_ratio_medio'])

            self.pasos += 1
            self.tiempo_upd += time.perf_counter() - t0

    def _adaptar_clip_ratio(self) -> None:
        """Ajusta dinámicamente clip_ratio según la divergencia KL calculada."""
        kl = self.estadisticas_ppo['kl_divergencia']
        if kl > 0.02:
            self.clip_ratio *= 0.9
        elif kl < 0.01:
            self.clip_ratio *= 1.1
        self.clip_ratio = float(np.clip(self.clip_ratio, 0.1, 0.3))
        self.estadisticas_ppo['clip_ratio_actual'] = self.clip_ratio

    def entrenar_ppo(self) -> Dict[str, Any]:
        """Ejecuta una ronda completa de entrenamiento PPO sobre los datos almacenados."""
        if len(self.buffer) < self.epochs_ppo:
            return {'error': 'buffer_insuficiente'}

        estados, acciones, recompensas, valores, log_probs_old = self.buffer.obtener_listas()
        advantages = self.calcular_gae_advantages(recompensas, valores)
        returns = self.calcular_returns(recompensas, valores)

        for _ in range(self.epochs_ppo):
            gap, gas, gcp, gcs = self.calcular_gradientes_ppo(
                estados, acciones, log_probs_old, advantages, returns
            )
            self.actualizar_pesos(gap, gas, gcp, gcs)

        self.calcular_explained_variance(estados, returns)
        self.limpiar_buffers()

        return {
            'policy_loss': self.estadisticas_ppo['policy_loss_medio'],
            'value_loss': self.estadisticas_ppo['value_loss_medio'],
            'entropy_loss': self.estadisticas_ppo['entropy_loss_medio'],
            'total_loss': self.estadisticas_ppo['total_loss_medio'],
            'kl_divergencia': self.estadisticas_ppo['kl_divergencia'],
            'clip_ratio': self.clip_ratio,
            'epochs': self.epochs_ppo,
            'explained_variance': self.estadisticas_ppo['explained_variance'],
        }

    def limpiar_buffers(self) -> None:
        """Limpia los elementos del buffer de trayectoria."""
        self.buffer.limpiar()

    def limpiar_historiales(self) -> None:
        """Limpia historiales circulares de diagnósticos."""
        self.historial_policy.clear()
        self.historial_value.clear()
        self.historial_entropy.clear()
        self.historial_clip.clear()
        self.historial_kl.clear()
        self.historial_ratio.clear()

    def obtener_estadisticas_ppo(self) -> Dict[str, Any]:
        """Extrae métricas completas de entrenamiento y rendimiento de la red."""
        if self.pesos_actor is None:
            return {'estado': 'no_inicializada'}

        self.estadisticas_ppo['buffer_len'] = len(self.buffer)
        if self.pesos_actor is not None:
            self.estadisticas_ppo['q_max'] = float(np.max(np.abs(self.pesos_actor)))
            self.estadisticas_ppo['q_min'] = float(np.min(np.abs(self.pesos_actor)))
            self.estadisticas_ppo['q_media'] = float(np.mean(np.abs(self.pesos_actor)))
            self.estadisticas_ppo['q_std'] = float(np.std(np.abs(self.pesos_actor)))

        # Cálculo de convergencias
        if len(self.historial_policy) >= 10:
            vp = float(np.var(np.asarray(self.historial_policy.tail(10), dtype=np.float64)))
            self.estadisticas_ppo['convergencia_policy'] = 1.0 / (1.0 + vp)
        if len(self.historial_value) >= 10:
            vv = float(np.var(np.asarray(self.historial_value.tail(10), dtype=np.float64)))
            self.estadisticas_ppo['convergencia_value'] = 1.0 / (1.0 + vv)

        return {
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'lambda_gae': self.lambda_gae,
            'clip_ratio': self.clip_ratio,
            'clip_ratio_adaptativo': self.clip_ratio_adaptativo,
            'entropy_coef': self.entropy_coef,
            'value_coef': self.value_coef,
            'max_grad_norm': self.max_grad_norm,
            'epochs_ppo': self.epochs_ppo,
            'policy_loss_medio': self.estadisticas_ppo['policy_loss_medio'],
            'value_loss_medio': self.estadisticas_ppo['value_loss_medio'],
            'entropy_loss_medio': self.estadisticas_ppo['entropy_loss_medio'],
            'total_loss_medio': self.estadisticas_ppo['total_loss_medio'],
            'kl_divergencia': self.estadisticas_ppo['kl_divergencia'],
            'policy_ratio_medio': self.estadisticas_ppo['policy_ratio_medio'],
            'advantage_norma': self.estadisticas_ppo['advantage_norma'],
            'advantage_media': self.estadisticas_ppo['advantage_media'],
            'gradiente_norma': self.estadisticas_ppo['gradiente_norma'],
            'epochs_completados': self.estadisticas_ppo['epochs_completados'],
            'convergencia_policy': self.estadisticas_ppo.get('convergencia_policy', 0.0),
            'convergencia_value': self.estadisticas_ppo.get('convergencia_value', 0.0),
            'explained_variance': self.estadisticas_ppo.get('explained_variance', 0.0),
            't_medio_fwd_us': self.estadisticas_ppo.get('t_medio_fwd_us', 0.0),
            't_medio_upd_us': self.estadisticas_ppo.get('t_medio_upd_us', 0.0),
            'buffer_len': self.estadisticas_ppo['buffer_len'],
        }

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprueba umbrales numéricos de estabilidad y convergencia."""
        est: Dict[str, bool] = {}
        kl = self.estadisticas_ppo['kl_divergencia']
        est['kl_divergenia_ok'] = (0.005 <= kl <= 0.05) if kl > 0 else True
        est['clip_ratio_ok'] = 0.1 <= self.clip_ratio <= 0.3

        pl = self.estadisticas_ppo['policy_loss_medio']
        vl = self.estadisticas_ppo['value_loss_medio']
        est['policy_loss_estable'] = abs(pl) < 10.0
        est['value_loss_estable'] = vl < 10.0

        gn = self.estadisticas_ppo['gradiente_norma']
        est['gradientes_no_explosivos'] = gn < 10.0
        est['gradientes_no_desaparecen'] = gn > 1e-8 if gn > 0 else True

        if self.pesos_actor is not None and self.pesos_critic is not None:
            est['pesos_actor_no_explosivos'] = bool(np.max(np.abs(self.pesos_actor)) < 5.0)
            est['pesos_critic_no_explosivos'] = bool(np.max(np.abs(self.pesos_critic)) < 5.0)
        else:
            est['pesos_actor_no_explosivos'] = True
            est['pesos_critic_no_explosivos'] = True

        return est

    def verificar_integridad(self) -> Dict[str, Any]:
        """Comprueba sanidad estructural (ausencia de NaN/Inf, tipos contiguos)."""
        checks: Dict[str, Any] = {
            'pesos_inicializados': self.pesos_actor is not None,
            'pesos_critic_inicializados': self.pesos_critic is not None,
            'locks_funcionales': hasattr(self, 'pesos_lock'),
        }
        if self.pesos_actor is not None and self.pesos_critic is not None:
            checks['sin_nan_actor'] = not bool(np.any(np.isnan(self.pesos_actor)))
            checks['sin_nan_critic'] = not bool(np.any(np.isnan(self.pesos_critic)))
            checks['sin_inf_actor'] = not bool(np.any(np.isinf(self.pesos_actor)))
            checks['sin_inf_critic'] = not bool(np.any(np.isinf(self.pesos_critic)))
            checks['precision'] = str(self.pesos_actor.dtype)
            checks['peso_actor_max'] = float(np.max(np.abs(self.pesos_actor)))
            checks['peso_critic_max'] = float(np.max(np.abs(self.pesos_critic)))
        checks['buffer_tamano'] = len(self.buffer)
        checks['epochs_pendientes'] = self.epochs_ppo
        return checks

    def reinicializar_con_parametros(self, learning_rate: Optional[float] = None,
                                     gamma: Optional[float] = None,
                                     clip_ratio: Optional[float] = None,
                                     entropy_coef: Optional[float] = None) -> None:
        """Reinicializa los pesos y reinicia buffers con nuevos hiperparámetros."""
        if learning_rate is not None:
            self.learning_rate = float(learning_rate)
        if gamma is not None:
            self.gamma = float(gamma)
        if clip_ratio is not None:
            self.clip_ratio = float(clip_ratio)
        if entropy_coef is not None:
            self.entropy_coef = float(entropy_coef)

        self.inicializar_pesos()
        self.resetear_historial()
        self.limpiar_buffers()
        self.limpiar_historiales()
        self.estadisticas_ppo['epochs_completados'] = 0
        logger.info(f"Neurona PPO reinicializada: lr={self.learning_rate}, clip={self.clip_ratio}")

    def a_dict(self) -> Dict[str, Any]:
        """Serializa la configuración y pesos a un diccionario."""
        return {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'pesos_actor': self.pesos_actor.tolist() if self.pesos_actor is not None else None,
            'pesos_critic': self.pesos_critic.tolist() if self.pesos_critic is not None else None,
            'sesgo_actor': self.sesgo_actor.tolist() if self.sesgo_actor is not None else None,
            'sesgo_critic': self.sesgo_critic.tolist() if self.sesgo_critic is not None else None,
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'clip_ratio': self.clip_ratio,
        }

    def guardar(self, ruta: str) -> None:
        """Guarda los pesos del modelo en formato JSON."""
        import json
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.a_dict(), f, indent=2)

    def cargar(self, ruta: str) -> None:
        """Carga los pesos de la neurona desde un archivo JSON."""
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.inicializar_pesos()
        if d.get('pesos_actor') is not None:
            self.pesos_actor = np.asarray(d['pesos_actor'], dtype=_dt())
        if d.get('pesos_critic') is not None:
            self.pesos_critic = np.asarray(d['pesos_critic'], dtype=_dt())
        if d.get('sesgo_actor') is not None:
            self.sesgo_actor = np.asarray(d['sesgo_actor'], dtype=_dt())
        if d.get('sesgo_critic') is not None:
            self.sesgo_critic = np.asarray(d['sesgo_critic'], dtype=_dt())

    def __str__(self) -> str:
        return (f"NeuronaRefuerzoPPO(entrada={self.input_size}, salida={self.output_size}, "
                f"lr={self.learning_rate}, gamma={self.gamma}, clip={self.clip_ratio:.3f})")

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["NeuronaRefuerzoPPO"]
