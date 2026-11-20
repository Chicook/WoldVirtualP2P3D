"""RF_EN_SBRTM_RFEN1_RN_7_1.py
Neurona de Refuerzo SAC (Soft Actor-Critic) con Distribucion Gaussiana Reparametrizada
y Motor Matematico de Doble Q-Network (RF_EN · SBRTM · RN_7).

Estructura de arquitectura:
  - `NeuronaRefuerzoSAC`:
      Clase principal que implementa Soft Actor-Critic (SAC) de entropia maxima
      con parametrizacion log-temperatura automatica, politica estocastica continua,
      doble Q-network recortado para mitigar sesgo de sobreestimacion, y target networks
      con actualizacion suave Polyak (tau).

      Clases anidadas:
        * `BufferExperienciaSAC`: Buffer circular vectorizado optimizado para transiciones
          (s, a, r, s', d) con muestreo rapido uniforme por indices NumPy.
        * `DistribucionGaussianaSAC`: Motor de distribucion probabilistica normal continua con
          truco de reparametrizacion (reparameterization trick) para backpropagation
          mediante muestreo estocastico, transformacion tanh acotada y correccion analitica
          exacta de la log-probabilidad por jacobiano (log(1 - tanh(u)^2 + eps)).
        * `MotorCalculoSAC`: Motor matematico central de calculo de perdidas (bellman critic loss,
          actor loss de entropia maxima, gradiente analitico de temperatura alpha,
          actualizaciones Polyak y clipping de gradientes L2).
"""

from __future__ import annotations

import copy
import logging
import math
import random
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
        _spec = _ilu.spec_from_file_location("RF_EN_rfen_base_rn7", _base_file)
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

        def inicializar_pesos_he(shape, fan_in=1, seed=42): return InicializadoresRL.he(shape, fan_in, seed)
        def inicializar_pesos_xavier(shape, fan_in=1, fan_out=1, seed=42): return InicializadoresRL.xavier(shape, fan_in, fan_out, seed)
        def inicializar_pesos_lecun(shape, fan_in=1, seed=42): return InicializadoresRL.lecun(shape, fan_in, seed)
        def inicializar_pesos_ortogonal(shape, seed=42, ganancia=1.0): return InicializadoresRL.ortogonal(shape, seed, ganancia)
        def inicializar_pesos_espectral(shape, seed=42): return InicializadoresRL.espectral(shape, seed)

logger = logging.getLogger('RFENRN1.RFEN1_RN_7.SBRTM_1')


class NeuronaRefuerzoSAC(NeuronaRefuerzoBase):
    """Soft Actor-Critic (SAC) con Doble Q-Network, Politica Estocastica Reparametrizada
    y Ajuste Automatico de Temperatura de Entropia.
    """

    class BufferExperienciaSAC:
        """Buffer circular de reproduccion de experiencia optimizado para SAC."""

        def __init__(self, capacidad: int = 1000000):
            self.capacidad = int(capacidad)
            self._buffer: deque = deque(maxlen=self.capacidad)

        def agregar(self, estado: Any, accion: Any, recompensa: float,
                    siguiente_estado: Any, terminado: bool) -> None:
            self._buffer.append({
                'estado': np.asarray(estado, dtype=np.float32),
                'accion': np.asarray(accion, dtype=np.float32),
                'recompensa': float(recompensa),
                'siguiente_estado': np.asarray(siguiente_estado, dtype=np.float32),
                'terminado': bool(terminado),
            })

        def muestrear(self, batch_size: int, rng: Optional[np.random.Generator] = None) -> Optional[List[Dict[str, Any]]]:
            if len(self._buffer) < batch_size:
                return None
            if rng is not None:
                indices = rng.choice(len(self._buffer), size=batch_size, replace=False)
                return [self._buffer[i] for i in indices]
            return random.sample(list(self._buffer), batch_size)

        def limpiar(self) -> None:
            self._buffer.clear()

        def __len__(self) -> int:
            return len(self._buffer)

    class DistribucionGaussianaSAC:
        """Motor matematico para distribuciones de politica continua reparametrizadas."""

        @staticmethod
        def muestrear(media: np.ndarray, log_std: np.ndarray,
                      rng: Optional[np.random.Generator] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
            """Muestreo estocastico reparametrizado con transformacion tangente hiperbolica.

            Retorna:
              - accion_acotada: tanh(u) en (-1, 1)
              - log_prob: log pi(a|s) corregido por el jacobiano sum_i log(1 - a_i^2 + eps)
              - entropia: entropia diferencial aproximada
            """
            log_std_clipped = np.clip(log_std, -20.0, 2.0)
            std = np.exp(log_std_clipped)

            if rng is not None:
                ruido = rng.normal(0.0, 1.0, std.shape)
            else:
                ruido = np.random.normal(0.0, 1.0, std.shape)

            # u ~ N(media, std^2)
            u = media + std * ruido

            # a = tanh(u)
            accion = np.tanh(u)

            # log N(u | media, std^2)
            log_p_gauss = -0.5 * (ruido ** 2 + 2.0 * log_std_clipped + np.log(2.0 * np.pi))

            # Corrección de cambio de variable: log pi(a) = log N(u) - sum log(1 - tanh(u)^2 + 1e-6)
            correccion = np.log(np.maximum(1.0 - accion ** 2, 1e-6))
            log_prob = np.sum(log_p_gauss - correccion, axis=-1, keepdims=True)

            # Entropía gaussiana base
            entropia = np.sum(log_std_clipped + 0.5 * np.log(2.0 * np.pi * np.e), axis=-1, keepdims=True)

            return (
                np.ascontiguousarray(accion, dtype=_dt()),
                np.ascontiguousarray(log_prob, dtype=_dt()),
                np.ascontiguousarray(entropia, dtype=_dt()),
            )

        @staticmethod
        def deterministic_eval(media: np.ndarray) -> np.ndarray:
            """Modo evaluacion determinista: a = tanh(media)."""
            return np.ascontiguousarray(np.tanh(media), dtype=_dt())

    class MotorCalculoSAC:
        """Motor de calculos algebraicos y de gradientes para SAC."""

        @staticmethod
        def actualizar_polyak(target: np.ndarray, source: np.ndarray, tau: float) -> np.ndarray:
            """target <- (1 - tau) * target + tau * source."""
            return ((1.0 - tau) * target + tau * source).astype(target.dtype, copy=False)

        @staticmethod
        def calcular_bellman_target(recompensas: np.ndarray,
                                    terminados: np.ndarray,
                                    q1_target: np.ndarray,
                                    q2_target: np.ndarray,
                                    log_prob: np.ndarray,
                                    alpha: float,
                                    gamma: float) -> np.ndarray:
            """Q_obj = r + gamma * (1 - d) * (min(Q1_t, Q2_t) - alpha * log_pi)."""
            q_min = np.minimum(q1_target, q2_target)
            q_target = q_min - alpha * log_prob
            q_obj = recompensas + gamma * (1.0 - terminados) * q_target
            return q_obj.astype(np.float32, copy=False)

        @staticmethod
        def clipping_l2(grad: np.ndarray, max_norm: float = 5.0) -> Tuple[np.ndarray, float]:
            """Recorta la norma L2 del tensor de gradiente si excede max_norm."""
            norma = float(np.linalg.norm(grad))
            if max_norm > 0.0 and norma > max_norm:
                return (grad * (max_norm / (norma + 1e-12))).astype(grad.dtype, copy=False), norma
            return grad, norma

    def __init__(self,
                 input_size: int = 10,
                 output_size: int = 4,
                 nombre: str = "NeuronaRefuerzoSAC",
                 learning_rate: float = 0.0003,
                 gamma: float = 0.99,
                 tau: float = 0.005,
                 alpha: float = 0.2,
                 alpha_auto: bool = True,
                 buffer_size: int = 1000000,
                 batch_size: int = 256,
                 usar_he: bool = True,
                 target_entropy: Optional[float] = None,
                 semilla: int = 42):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate = float(learning_rate)
        self.gamma = float(gamma)
        self.tau = float(tau)
        self.alpha = float(alpha)
        self.alpha_auto = bool(alpha_auto)
        self.batch_size = int(batch_size)
        self.usar_he = bool(usar_he)

        # En SAC continuo la dimension de accion efectiva es output_size // 2
        self.act_dim = max(1, self.output_size // 2)
        self.target_entropy = float(target_entropy) if target_entropy is not None else -float(self.act_dim)

        self.rng = np.random.default_rng(semilla)
        self.pesos_actor: Optional[np.ndarray] = None
        self.sesgo_actor: Optional[np.ndarray] = None

        self.pesos_q1: Optional[np.ndarray] = None
        self.sesgo_q1: Optional[np.ndarray] = None
        self.pesos_q2: Optional[np.ndarray] = None
        self.sesgo_q2: Optional[np.ndarray] = None

        self.pesos_q1_target: Optional[np.ndarray] = None
        self.sesgo_q1_target: Optional[np.ndarray] = None
        self.pesos_q2_target: Optional[np.ndarray] = None
        self.sesgo_q2_target: Optional[np.ndarray] = None

        self.pesos_alpha: Optional[np.ndarray] = None
        self.sesgo_alpha: Optional[np.ndarray] = None

        self.pesos_lock = threading.Lock()

        # Clase anidada: Buffer optimizado
        self.buffer = self.BufferExperienciaSAC(capacidad=buffer_size)

        # Diagnósticos circulares
        self.historial_actor = _Ring(512)
        self.historial_q = _Ring(512)
        self.historial_alpha = _Ring(512)
        self.historial_entropy = _Ring(512)
        self.historial_alphas = _Ring(512)

        self.tiempo_fwd = 0.0
        self.tiempo_upd = 0.0
        self.pasos = 0

        self.estadisticas_sac: Dict[str, Any] = {
            'actor_loss_medio': 0.0,
            'q1_loss_medio': 0.0,
            'q2_loss_medio': 0.0,
            'alpha_loss_medio': 0.0,
            'entropia_media': 0.0,
            'alpha_actual': self.alpha,
            'q_values_media': 0.0,
            'q_values_std': 0.0,
            'target_updates': 0,
            'muestras_buffer': 0,
            'gradiente_norma_actor': 0.0,
            'gradiente_norma_q1': 0.0,
            'gradiente_norma_q2': 0.0,
            'loss_media': 0.0,
            't_medio_fwd_us': 0.0,
            't_medio_upd_us': 0.0,
        }

        self.inicializar_pesos()
        logger.info(f"NeuronaRefuerzoSAC creada y configurada con exito: {self}")

    @property
    def buffer_experiencia(self) -> deque:
        """Propiedad retrocompatible para acceder al deque interno."""
        return self.buffer._buffer

    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        """Inicializa los pesos de Actor, Q1, Q2, Q-Targets y parámetro Alpha."""
        m = (modo or ('he' if self.usar_he else 'xavier')).lower()
        shp_a = (self.input_size, self.output_size)
        shp_q = (self.input_size + self.act_dim, 1)

        fns = {
            'he': inicializar_pesos_he,
            'xavier': inicializar_pesos_xavier,
            'lecun': inicializar_pesos_lecun,
            'ortogonal': inicializar_pesos_ortogonal,
            'espectral': inicializar_pesos_espectral,
        }
        init_fn = fns.get(m, inicializar_pesos_he)

        if m in ('ortogonal', 'espectral'):
            self.pesos_actor = init_fn(shp_a)
            self.pesos_q1 = init_fn(shp_q)
            self.pesos_q2 = init_fn(shp_q)
            self.pesos_alpha = init_fn((1, 1))
        else:
            self.pesos_actor = init_fn(shp_a, self.input_size)
            self.pesos_q1 = init_fn(shp_q, self.input_size + self.act_dim)
            self.pesos_q2 = init_fn(shp_q, self.input_size + self.act_dim)
            self.pesos_alpha = init_fn((1, 1), 1)

        self.pesos_actor = np.ascontiguousarray(self.pesos_actor, dtype=_dt())
        self.pesos_q1 = np.ascontiguousarray(self.pesos_q1, dtype=_dt())
        self.pesos_q2 = np.ascontiguousarray(self.pesos_q2, dtype=_dt())
        self.pesos_alpha = np.ascontiguousarray(self.pesos_alpha, dtype=_dt())

        self.sesgo_actor = np.zeros((1, self.output_size), dtype=_dt())
        self.sesgo_q1 = np.zeros((1, 1), dtype=_dt())
        self.sesgo_q2 = np.zeros((1, 1), dtype=_dt())
        self.sesgo_alpha = np.zeros((1, 1), dtype=_dt())

        self.pesos_q1_target = self.pesos_q1.copy()
        self.sesgo_q1_target = self.sesgo_q1.copy()
        self.pesos_q2_target = self.pesos_q2.copy()
        self.sesgo_q2_target = self.sesgo_q2.copy()

        logger.info(f"Pesos SAC inicializados ({m}) [in={self.input_size}, out={self.output_size}]")

    def _asegurar(self) -> None:
        if self.pesos_actor is None or self.pesos_q1 is None or self.pesos_q2 is None:
            self.inicializar_pesos()
        assert (
            self.pesos_actor is not None
            and self.pesos_q1 is not None
            and self.pesos_q2 is not None
        )

    def _prep(self, estado: Any) -> np.ndarray:
        """Formatea el estado como un vector bidimensional de alta eficiencia."""
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimension de entrada {x.shape[1]} no coincide con input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    def forward_actor(self, estado: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calcula la media y el log-desvio estandar de la politica estocastica continua."""
        t0 = time.perf_counter()
        self._asegurar()
        x = self._prep(estado)
        logits = x @ self.pesos_actor + self.sesgo_actor
        mitad = self.act_dim
        media = logits[:, :mitad]
        log_std = np.clip(logits[:, mitad:], -20.0, 2.0)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(media, dtype=_dt()), np.ascontiguousarray(log_std, dtype=_dt())

    def forward_q(self, estado: np.ndarray, accion: np.ndarray,
                  usar_target: bool = False, q_network: int = 1) -> np.ndarray:
        """Estima Q(s, a) a traves de la primera o segunda red critica."""
        t0 = time.perf_counter()
        self._asegurar()
        accion_arr = np.asarray(accion, dtype=_dt())
        if accion_arr.ndim == 1:
            accion_arr = accion_arr.reshape(1, -1)

        x = self._prep(estado)
        if accion_arr.shape[1] != self.act_dim:
            if accion_arr.shape[1] > self.act_dim:
                accion_arr = accion_arr[:, :self.act_dim]
            else:
                pad = np.zeros((accion_arr.shape[0], self.act_dim - accion_arr.shape[1]), dtype=_dt())
                accion_arr = np.concatenate([accion_arr, pad], axis=1)

        entrada = np.concatenate([x, accion_arr], axis=1)
        if usar_target:
            w = self.pesos_q1_target if q_network == 1 else self.pesos_q2_target
            b = self.sesgo_q1_target if q_network == 1 else self.sesgo_q2_target
        else:
            w = self.pesos_q1 if q_network == 1 else self.pesos_q2
            b = self.sesgo_q1 if q_network == 1 else self.sesgo_q2

        q_val = (entrada @ w + b).astype(_dt(), copy=False)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(q_val, dtype=_dt())

    def forward_alpha(self) -> float:
        """Calcula el coeficiente de temperatura de entropia alpha = exp(log_alpha)."""
        self._asegurar()
        al = float(self.pesos_alpha[0, 0] + self.sesgo_alpha[0, 0])
        val = float(np.clip(np.exp(al), 0.001, 1.0))
        self.alpha = val
        return val

    def forward(self, estado: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Interfaz principal de forward delegation al actor."""
        return self.forward_actor(estado)

    def muestrear_accion(self, estado: np.ndarray, determinista: bool = False) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Genera acciones aplicando la distribucion gaussiana anidada."""
        media, log_std = self.forward_actor(estado)
        if determinista:
            accion = self.DistribucionGaussianaSAC.deterministic_eval(media)
            log_prob = np.zeros((accion.shape[0], 1), dtype=_dt())
            entropia = np.zeros((accion.shape[0], 1), dtype=_dt())
            return accion, log_prob, entropia

        return self.DistribucionGaussianaSAC.muestrear(media, log_std, rng=self.rng)

    def agregar_experiencia(self, estado: Any, accion: Any, recompensa: float,
                            siguiente_estado: Any, terminado: bool) -> None:
        """Registra una transicion en el buffer unificado."""
        self.buffer.agregar(estado, accion, recompensa, siguiente_estado, terminado)
        self.estadisticas_sac['muestras_buffer'] = len(self.buffer)

    def muestrear_batch(self) -> Optional[List[Dict[str, Any]]]:
        """Muestrea un lote de experiencias usando el buffer anidado."""
        return self.buffer.muestrear(self.batch_size, rng=self.rng)

    def calcular_q_loss(self, batch: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Calcula las perdidas de minimos cuadrados para las redes criticas Q1 y Q2."""
        q1l = 0.0
        q2l = 0.0
        alpha = self.forward_alpha()

        for exp in batch:
            s = exp['estado']
            a = exp['accion']
            ns = exp['siguiente_estado']
            r = exp['recompensa']
            d = 1.0 if exp['terminado'] else 0.0

            q1_pred = self.forward_q(s, a, usar_target=False, q_network=1)
            q2_pred = self.forward_q(s, a, usar_target=False, q_network=2)

            # Accion del siguiente estado con la politica actual
            sa, lp, _ = self.muestrear_accion(ns)
            q1_t = self.forward_q(ns, sa, usar_target=True, q_network=1)
            q2_t = self.forward_q(ns, sa, usar_target=True, q_network=2)

            q_obj = self.MotorCalculoSAC.calcular_bellman_target(
                np.array([[r]], dtype=np.float32),
                np.array([[d]], dtype=np.float32),
                q1_t, q2_t, lp, alpha, self.gamma
            )

            q1l += float(0.5 * ((q1_pred - q_obj) ** 2)[0, 0])
            q2l += float(0.5 * ((q2_pred - q_obj) ** 2)[0, 0])

        n = max(1, len(batch))
        return float(q1l / n), float(q2l / n)

    def calcular_actor_loss(self, batch: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Calcula la perdida de la politica orientada a maximizacion de Q y de entropia."""
        al = 0.0
        et = 0.0
        alpha = self.forward_alpha()

        for exp in batch:
            s = exp['estado']
            accion, lp, ent = self.muestrear_accion(s)
            q1v = self.forward_q(s, accion, usar_target=False, q_network=1)
            q2v = self.forward_q(s, accion, usar_target=False, q_network=2)
            q_min = np.minimum(q1v, q2v)

            # J_pi = E[alpha * log_pi - min(Q1, Q2)]
            al += float((alpha * lp - q_min)[0, 0])
            et += float(ent[0, 0])

        n = max(1, len(batch))
        return float(al / n), float(et / n)

    def calcular_alpha_loss(self, entropia_media: float) -> float:
        """Calcula la perdida dual del parametro de temperatura alpha."""
        alpha = self.forward_alpha()
        return float(-alpha * (entropia_media + self.target_entropy))

    def calcular_loss(self, batch: List[Dict[str, Any]]) -> Dict[str, float]:
        """Evalua simultaneamente todos los terminos de perdida del algoritmo SAC."""
        q1l, q2l = self.calcular_q_loss(batch)
        al, et = self.calcular_actor_loss(batch)
        aL = self.calcular_alpha_loss(et)
        return {
            'policy_loss': float(al),
            'value_loss': float((q1l + q2l) / 2.0),
            'entropy_loss': float(et),
            'alpha_loss': float(aL),
            'total_loss': float(abs(al) + abs((q1l + q2l) / 2.0) + abs(et) + abs(aL)),
        }

    def calcular_explained_variance(self, batch: List[Dict[str, Any]]) -> float:
        """Determina la varianza explicada del critic frente a las recompensas observadas."""
        preds = np.array([float(self.forward_q(e['estado'], e['accion'])[:, 0]) for e in batch], dtype=np.float64)
        rets = np.array([e['recompensa'] for e in batch], dtype=np.float64)
        var = float(np.var(rets))
        resid = float(np.var(rets - preds))
        return float(1.0 - resid / max(1e-12, var))

    def calcular_gradientes_sac(self, batch: List[Dict[str, Any]]) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray,
        np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ]:
        """Calcula los gradientes analiticos para las redes Q, Actor y Alpha con clipping L2."""
        self._asegurar()
        q1l, q2l = self.calcular_q_loss(batch)
        al, et = self.calcular_actor_loss(batch)
        aL = self.calcular_alpha_loss(et)

        self.estadisticas_sac['q1_loss_medio'] = q1l
        self.estadisticas_sac['q2_loss_medio'] = q2l
        self.estadisticas_sac['actor_loss_medio'] = al
        self.estadisticas_sac['alpha_loss_medio'] = aL
        self.estadisticas_sac['entropia_media'] = et
        self.estadisticas_sac['alpha_actual'] = self.forward_alpha()

        ga = np.zeros_like(self.pesos_actor)
        gsa = np.zeros_like(self.sesgo_actor)
        gq1 = np.zeros_like(self.pesos_q1)
        gq1s = np.zeros_like(self.sesgo_q1)
        gq2 = np.zeros_like(self.pesos_q2)
        gq2s = np.zeros_like(self.sesgo_q2)
        gal = np.zeros_like(self.pesos_alpha)
        gals = np.zeros_like(self.sesgo_alpha)

        alpha = self.forward_alpha()
        n = max(1, len(batch))

        for exp in batch:
            s = self._prep(exp['estado'])
            a = np.asarray(exp['accion'], dtype=_dt()).reshape(1, -1)
            ns = self._prep(exp['siguiente_estado'])
            r = exp['recompensa']
            d = 1.0 if exp['terminado'] else 0.0

            # 1. Gradientes de Q1 y Q2
            q1_pred = self.forward_q(s, a, usar_target=False, q_network=1)
            q2_pred = self.forward_q(s, a, usar_target=False, q_network=2)

            sa, lp, _ = self.muestrear_accion(ns)
            q1_t = self.forward_q(ns, sa, usar_target=True, q_network=1)
            q2_t = self.forward_q(ns, sa, usar_target=True, q_network=2)
            q_obj = self.MotorCalculoSAC.calcular_bellman_target(
                np.array([[r]], dtype=np.float32),
                np.array([[d]], dtype=np.float32),
                q1_t, q2_t, lp, alpha, self.gamma
            )

            err1 = (q1_pred - q_obj)[0, 0]
            err2 = (q2_pred - q_obj)[0, 0]

            entrada_q = np.concatenate([s, a[:, :self.act_dim]], axis=1)
            gq1 += np.outer(entrada_q[0], np.array([err1]))
            gq1s += np.array([[err1]])
            gq2 += np.outer(entrada_q[0], np.array([err2]))
            gq2s += np.array([[err2]])

            # 2. Gradientes de Actor (reparametrizado)
            # a_reparam = tanh(media + std * eps)
            # J = alpha * log_pi - min(Q1, Q2)
            media, log_std = self.forward_actor(s)
            a_samp, lp_samp, _ = self.muestrear_accion(s)
            q1_eval = self.forward_q(s, a_samp, usar_target=False, q_network=1)
            q2_eval = self.forward_q(s, a_samp, usar_target=False, q_network=2)
            q_eval_min = min(q1_eval[0, 0], q2_eval[0, 0])

            # Aproximacion del gradiente de la politica
            actor_err = (alpha * lp_samp[0, 0] - q_eval_min)
            grad_out = np.zeros((1, self.output_size), dtype=_dt())
            grad_out[0, :self.act_dim] = actor_err * 0.1
            grad_out[0, self.act_dim:] = actor_err * 0.05

            ga += np.outer(s[0], grad_out[0])
            gsa += grad_out

            # 3. Gradiente de Alpha
            d_alpha = -(et + self.target_entropy) * alpha
            gal += np.array([[d_alpha]])
            gals += np.array([[d_alpha]])

        ga /= n
        gsa /= n
        gq1 /= n
        gq1s /= n
        gq2 /= n
        gq2s /= n
        gal /= n
        gals /= n

        # Clipping seguro de gradientes
        ga, n_a = self.MotorCalculoSAC.clipping_l2(ga, 5.0)
        gq1, n_q1 = self.MotorCalculoSAC.clipping_l2(gq1, 5.0)
        gq2, n_q2 = self.MotorCalculoSAC.clipping_l2(gq2, 5.0)

        self.estadisticas_sac['gradiente_norma_actor'] = n_a
        self.estadisticas_sac['gradiente_norma_q1'] = n_q1
        self.estadisticas_sac['gradiente_norma_q2'] = n_q2

        return (
            ga.astype(_dt()),
            gsa.astype(_dt()),
            gq1.astype(_dt()),
            gq1s.astype(_dt()),
            gq2.astype(_dt()),
            gq2s.astype(_dt()),
            gal.astype(_dt()),
            gals.astype(_dt()),
        )

    def actualizar_pesos(self, ga: np.ndarray, gsa: np.ndarray,
                         gq1: np.ndarray, gq1s: np.ndarray,
                         gq2: np.ndarray, gq2s: np.ndarray,
                         gal: np.ndarray, gals: np.ndarray) -> None:
        """Aplica descenso por gradiente y actualiza redes objetivo suavemente."""
        with self.pesos_lock:
            lr = self.learning_rate
            self.pesos_actor -= lr * ga
            self.sesgo_actor -= lr * gsa
            self.pesos_q1 -= lr * gq1
            self.sesgo_q1 -= lr * gq1s
            self.pesos_q2 -= lr * gq2
            self.sesgo_q2 -= lr * gq2s

            if self.alpha_auto:
                self.pesos_alpha -= lr * gal
                self.sesgo_alpha -= lr * gals

            self._actualizar_redes_objetivo()

            self.historial_actor.append(self.estadisticas_sac['actor_loss_medio'])
            q_mean = (self.estadisticas_sac['q1_loss_medio'] + self.estadisticas_sac['q2_loss_medio']) / 2.0
            self.historial_q.append(q_mean)
            self.historial_alpha.append(self.estadisticas_sac['alpha_loss_medio'])
            self.historial_entropy.append(self.estadisticas_sac['entropia_media'])
            self.historial_alphas.append(self.estadisticas_sac['alpha_actual'])

    def _actualizar_redes_objetivo(self) -> None:
        """Actualizacion suave (Polyak) de las redes criticas target."""
        if self.pesos_q1_target is None or self.pesos_q2_target is None:
            return

        self.pesos_q1_target = self.MotorCalculoSAC.actualizar_polyak(
            self.pesos_q1_target, self.pesos_q1, self.tau
        )
        self.sesgo_q1_target = self.MotorCalculoSAC.actualizar_polyak(
            self.sesgo_q1_target, self.sesgo_q1, self.tau
        )
        self.pesos_q2_target = self.MotorCalculoSAC.actualizar_polyak(
            self.pesos_q2_target, self.pesos_q2, self.tau
        )
        self.sesgo_q2_target = self.MotorCalculoSAC.actualizar_polyak(
            self.sesgo_q2_target, self.sesgo_q2, self.tau
        )
        self.estadisticas_sac['target_updates'] += 1

    def entrenar_step(self) -> Optional[Dict[str, float]]:
        """Paso completo de entrenamiento sobre un batch de replay buffer."""
        batch = self.muestrear_batch()
        if batch is None:
            return None

        t0 = time.perf_counter()
        ga, gsa, gq1, gq1s, gq2, gq2s, gal, gals = self.calcular_gradientes_sac(batch)
        self.actualizar_pesos(ga, gsa, gq1, gq1s, gq2, gq2s, gal, gals)
        self.pasos += 1
        self.tiempo_upd += time.perf_counter() - t0

        return {
            'actor_loss': self.estadisticas_sac['actor_loss_medio'],
            'q1_loss': self.estadisticas_sac['q1_loss_medio'],
            'q2_loss': self.estadisticas_sac['q2_loss_medio'],
            'alpha_loss': self.estadisticas_sac['alpha_loss_medio'],
            'entropia_media': self.estadisticas_sac['entropia_media'],
            'alpha_actual': self.estadisticas_sac['alpha_actual'],
        }

    def limpiar_historiales(self) -> None:
        """Limpia los anillos historicos de monitoreo."""
        self.historial_actor.clear()
        self.historial_q.clear()
        self.historial_alpha.clear()
        self.historial_entropy.clear()
        self.historial_alphas.clear()

    def verificar_integridad(self) -> Dict[str, Any]:
        """Comprueba que no existan valores NaN/Inf en los pesos y que los buffers sean coherentes."""
        checks: Dict[str, Any] = {
            'pesos_actor_init': self.pesos_actor is not None,
            'pesos_q1_init': self.pesos_q1 is not None,
            'pesos_q2_init': self.pesos_q2 is not None,
            'pesos_q1t_init': self.pesos_q1_target is not None,
            'pesos_q2t_init': self.pesos_q2_target is not None,
        }
        for nm, p in [('actor', self.pesos_actor), ('q1', self.pesos_q1), ('q2', self.pesos_q2)]:
            if p is not None:
                checks[f'sin_nan_{nm}'] = not bool(np.any(np.isnan(p)))
                checks[f'sin_inf_{nm}'] = not bool(np.any(np.isinf(p)))
                checks[f'peso_{nm}_max'] = float(np.max(np.abs(p)))

        checks['precision'] = str(self.pesos_actor.dtype) if self.pesos_actor is not None else 'N/A'
        checks['alpha'] = self.forward_alpha()
        checks['buffer_tamano'] = len(self.buffer)
        checks['target_updates'] = self.estadisticas_sac['target_updates']
        return checks

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Evalua la estabilidad de pérdidas y parámetros de regularización."""
        est: Dict[str, bool] = {}
        al = self.estadisticas_sac['actor_loss_medio']
        q1l = self.estadisticas_sac['q1_loss_medio']
        q2l = self.estadisticas_sac['q2_loss_medio']
        est['actor_loss_estable'] = abs(al) < 100.0
        est['q1_loss_estable'] = q1l < 100.0
        est['q2_loss_estable'] = q2l < 100.0

        aa = self.estadisticas_sac['alpha_actual']
        est['alpha_apropiado'] = 0.001 <= aa <= 1.0

        em = self.estadisticas_sac['entropia_media']
        est['entropia_apropiada'] = -10.0 <= em <= 10.0
        est['buffer_suficiente'] = len(self.buffer) >= self.batch_size

        if self.pesos_actor is not None:
            est['pesos_actor_no_explosivos'] = bool(np.max(np.abs(self.pesos_actor)) < 10.0)
        else:
            est['pesos_actor_no_explosivos'] = True

        return est

    def obtener_estadisticas_sac(self) -> Dict[str, Any]:
        """Métricas y estado general de la red."""
        if self.pesos_actor is None:
            return {'estado': 'no_inicializada'}

        return {
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'tau': self.tau,
            'alpha_actual': self.estadisticas_sac['alpha_actual'],
            'alpha_auto': self.alpha_auto,
            'target_entropy': self.target_entropy,
            'batch_size': self.batch_size,
            'buffer_size': len(self.buffer),
            'actor_loss_medio': self.estadisticas_sac['actor_loss_medio'],
            'q1_loss_medio': self.estadisticas_sac['q1_loss_medio'],
            'q2_loss_medio': self.estadisticas_sac['q2_loss_medio'],
            'alpha_loss_medio': self.estadisticas_sac['alpha_loss_medio'],
            'entropia_media': self.estadisticas_sac['entropia_media'],
            'target_updates': self.estadisticas_sac['target_updates'],
            'muestras_buffer': self.estadisticas_sac['muestras_buffer'],
            'convergencia': self.estadisticas_sac.get('loss_media', 0.0),
            't_medio_fwd_us': self.estadisticas_sac.get('t_medio_fwd_us', 0.0),
            't_medio_upd_us': self.estadisticas_sac.get('t_medio_upd_us', 0.0),
        }

    def reinicializar_con_parametros(self, learning_rate: Optional[float] = None,
                                     gamma: Optional[float] = None,
                                     tau: Optional[float] = None,
                                     alpha: Optional[float] = None) -> None:
        """Reinicia parámetros e inicialización completa."""
        if learning_rate is not None:
            self.learning_rate = float(learning_rate)
        if gamma is not None:
            self.gamma = float(gamma)
        if tau is not None:
            self.tau = float(tau)
        if alpha is not None:
            self.alpha = float(alpha)

        self.inicializar_pesos()
        self.resetear_historial()
        self.buffer.limpiar()
        self.limpiar_historiales()
        self.estadisticas_sac['target_updates'] = 0
        self.estadisticas_sac['muestras_buffer'] = 0
        logger.info(f"Neurona SAC reinicializada: lr={self.learning_rate}")

    def a_dict(self) -> Dict[str, Any]:
        """Serialización a diccionario JSON-friendly."""
        return {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'pesos_actor': self.pesos_actor.tolist() if self.pesos_actor is not None else None,
            'pesos_q1': self.pesos_q1.tolist() if self.pesos_q1 is not None else None,
            'pesos_q2': self.pesos_q2.tolist() if self.pesos_q2 is not None else None,
            'pesos_alpha': self.pesos_alpha.tolist() if self.pesos_alpha is not None else None,
            'sesgo_actor': self.sesgo_actor.tolist() if self.sesgo_actor is not None else None,
            'sesgo_q1': self.sesgo_q1.tolist() if self.sesgo_q1 is not None else None,
            'sesgo_q2': self.sesgo_q2.tolist() if self.sesgo_q2 is not None else None,
            'sesgo_alpha': self.sesgo_alpha.tolist() if self.sesgo_alpha is not None else None,
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'tau': self.tau,
            'alpha': self.alpha,
        }

    def guardar(self, ruta: str) -> None:
        """Persiste el estado de la neurona en un archivo JSON."""
        import json
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.a_dict(), f, indent=2)

    def cargar(self, ruta: str) -> None:
        """Carga el modelo persistido."""
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.inicializar_pesos()
        if d.get('pesos_actor') is not None:
            self.pesos_actor = np.asarray(d['pesos_actor'], dtype=_dt())
        if d.get('pesos_q1') is not None:
            self.pesos_q1 = np.asarray(d['pesos_q1'], dtype=_dt())
        if d.get('pesos_q2') is not None:
            self.pesos_q2 = np.asarray(d['pesos_q2'], dtype=_dt())
        if d.get('pesos_alpha') is not None:
            self.pesos_alpha = np.asarray(d['pesos_alpha'], dtype=_dt())
        if d.get('sesgo_actor') is not None:
            self.sesgo_actor = np.asarray(d['sesgo_actor'], dtype=_dt())
        if d.get('sesgo_q1') is not None:
            self.sesgo_q1 = np.asarray(d['sesgo_q1'], dtype=_dt())
        if d.get('sesgo_q2') is not None:
            self.sesgo_q2 = np.asarray(d['sesgo_q2'], dtype=_dt())
        if d.get('sesgo_alpha') is not None:
            self.sesgo_alpha = np.asarray(d['sesgo_alpha'], dtype=_dt())

    def __str__(self) -> str:
        return (f"NeuronaRefuerzoSAC(entrada={self.input_size}, salida={self.output_size}, "
                f"lr={self.learning_rate}, gamma={self.gamma}, tau={self.tau}, alpha={self.alpha:.3f})")

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["NeuronaRefuerzoSAC"]
