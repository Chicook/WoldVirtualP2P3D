"""RF_EN_SBRTM_RFEN1_RN_8_1.py
Neurona de Refuerzo TD3 (Twin Delayed Deep Deterministic Policy Gradient) con
Doble Q-Network, Politica Determinista Retardada y Ruido de Accion Suavizado (RF_EN · SBRTM · RN_8).

Estructura de arquitectura:
  - `NeuronaRefuerzoTD3`:
      Clase principal que implementa el algoritmo TD3 completo:
      1) Doble Critic Q1 y Q2 para mitigar sobreestimacion de valores Q.
      2) Target Policy Smoothing: adición de ruido gaussiano truncado a las acciones target.
      3) Delayed Policy Updates: actualizacion de la red Actor y de las redes objetivo cada N pasos.
      
      Clases anidadas:
        * `BufferExperienciaTD3`: Almacen circular optimizado con muestreo por lotes eficiente.
        * `MotorCalculoTD3`: Fusión de funciones matemáticas y algoritmos de optimización:
            - Cálculo de Q-target con regularización por ruido gaussiano truncado (policy smoothing).
            - Estimación de pérdidas MSE para Q1 y Q2 y diagnóstico de sesgo de sobreestimación.
            - Cálculo de gradientes del Actor vía política determinista continua.
            - Actualización suave Polyak multired de parámetros objetivo.
            - Recorte de gradientes L2 conjunto.
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
        _spec = _ilu.spec_from_file_location("RF_EN_rfen_base_rn8", _base_file)
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
            'default_learning_rate': 0.001,
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

logger = logging.getLogger('RFENRN1.RFEN1_RN_8.SBRTM_1')


class NeuronaRefuerzoTD3(NeuronaRefuerzoBase):
    """Neurona de Refuerzo basada en Twin Delayed Deep Deterministic Policy Gradient (TD3).

    Incorpora:
      - Doble Critic Q1 y Q2 para resolver la sobreestimación del valor Q.
      - Regularización por ruido gaussiano recortado en acciones objetivo (Target Policy Smoothing).
      - Retardo en la actualización de política y de redes target (Policy Delay).
      - Buffer circular y motor analítico anidado de alto rendimiento.
    """

    class BufferExperienciaTD3:
        """Buffer circular de alta eficiencia para transiciones continuas de TD3."""

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

    class MotorCalculoTD3:
        """Motor matemático unificado para algoritmos TD3."""

        @staticmethod
        def suavizar_accion_objetivo(accion_target: np.ndarray,
                                     policy_noise: float = 0.2,
                                     noise_clip: float = 0.5,
                                     rng: Optional[np.random.Generator] = None) -> np.ndarray:
            """Añade ruido gaussiano truncado a la acción del actor objetivo:

            a_target = clip(pi_target(s') + clip(N(0, sigma), -c, c), -1, 1).
            """
            if rng is not None:
                ruido = rng.normal(0.0, policy_noise, size=accion_target.shape)
            else:
                ruido = np.random.normal(0.0, policy_noise, size=accion_target.shape)

            ruido_clipped = np.clip(ruido, -noise_clip, noise_clip)
            return np.clip(accion_target + ruido_clipped, -1.0, 1.0).astype(_dt(), copy=False)

        @staticmethod
        def calcular_bellman_target_td3(recompensa: float,
                                        terminado: bool,
                                        q1_target: float,
                                        q2_target: float,
                                        gamma: float = 0.99) -> float:
            """Q_obj = r + gamma * (1 - d) * min(Q1_target, Q2_target)."""
            q_min = min(q1_target, q2_target)
            return float(recompensa + gamma * (1.0 - float(terminado)) * q_min)

        @staticmethod
        def actualizar_polyak(target: np.ndarray, source: np.ndarray, tau: float) -> None:
            """Actualiza in-place el tensor target: target = (1 - tau)*target + tau*source."""
            target[:] = (1.0 - tau) * target + tau * source

        @staticmethod
        def clipping_l2(grad: np.ndarray, max_norm: float = 5.0) -> Tuple[np.ndarray, float]:
            """Normalización o recorte de gradientes por norma L2."""
            norma = float(np.linalg.norm(grad))
            if max_norm > 0.0 and norma > max_norm:
                return (grad * (max_norm / (norma + 1e-12))).astype(grad.dtype, copy=False), norma
            return grad, norma

    def __init__(self,
                 input_size: int = 10,
                 output_size: int = 4,
                 nombre: str = "NeuronaRefuerzoTD3",
                 learning_rate_actor: float = 0.001,
                 learning_rate_critic: float = 0.001,
                 gamma: float = 0.99,
                 tau: float = 0.005,
                 policy_noise: float = 0.2,
                 noise_clip: float = 0.5,
                 policy_delay: int = 2,
                 buffer_size: int = 1000000,
                 batch_size: int = 256,
                 usar_he: bool = True,
                 semilla: int = 42):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate_actor = float(learning_rate_actor)
        self.learning_rate_critic = float(learning_rate_critic)
        self.gamma = float(gamma)
        self.tau = float(tau)
        self.policy_noise = float(policy_noise)
        self.noise_clip = float(noise_clip)
        self.policy_delay = int(policy_delay)
        self.batch_size = int(batch_size)
        self.usar_he = bool(usar_he)

        self.rng = np.random.default_rng(semilla)
        self.pesos_actor: Optional[np.ndarray] = None
        self.sesgo_actor: Optional[np.ndarray] = None
        self.pesos_actor_target: Optional[np.ndarray] = None
        self.sesgo_actor_target: Optional[np.ndarray] = None

        self.pesos_q1: Optional[np.ndarray] = None
        self.sesgo_q1: Optional[np.ndarray] = None
        self.pesos_q1_target: Optional[np.ndarray] = None
        self.sesgo_q1_target: Optional[np.ndarray] = None

        self.pesos_q2: Optional[np.ndarray] = None
        self.sesgo_q2: Optional[np.ndarray] = None
        self.pesos_q2_target: Optional[np.ndarray] = None
        self.sesgo_q2_target: Optional[np.ndarray] = None

        self.pesos_lock = threading.Lock()

        # Clase anidada: Buffer optimizado
        self.buffer = self.BufferExperienciaTD3(capacidad=buffer_size)

        # Historiales de métricas
        self.historial_actor = _Ring(512)
        self.historial_q = _Ring(512)
        self.historial_sobreest = _Ring(512)

        self.policy_update_counter = 0
        self.tiempo_fwd = 0.0
        self.tiempo_upd = 0.0
        self.pasos = 0

        self.estadisticas_td3: Dict[str, Any] = {
            'actor_loss_medio': 0.0,
            'q1_loss_medio': 0.0,
            'q2_loss_medio': 0.0,
            'sobreestimacion_q1': 0.0,
            'sobreestimacion_q2': 0.0,
            'sobreestimacion_total': 0.0,
            'gradiente_norma_actor': 0.0,
            'gradiente_norma_q1': 0.0,
            'gradiente_norma_q2': 0.0,
            'target_updates': 0,
            'policy_updates': 0,
            'muestras_buffer': 0,
            'loss_media': 0.0,
            'q_values_media': 0.0,
            'q_values_std': 0.0,
            't_medio_fwd_us': 0.0,
            't_medio_upd_us': 0.0,
        }

        self.inicializar_pesos()
        logger.info(f"NeuronaRefuerzoTD3 creada y lista: {self}")

    @property
    def buffer_experiencia(self) -> deque:
        """Retrocompatibilidad con accesos directos al buffer."""
        return self.buffer._buffer

    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        """Inicializa los pesos de Actor, Critics Q1/Q2 y sus respectivas redes target."""
        m = (modo or ('he' if self.usar_he else 'xavier')).lower()
        shp_a = (self.input_size, self.output_size)
        shp_q = (self.input_size + self.output_size, 1)

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
        else:
            self.pesos_actor = init_fn(shp_a, self.input_size)
            self.pesos_q1 = init_fn(shp_q, self.input_size + self.output_size)
            self.pesos_q2 = init_fn(shp_q, self.input_size + self.output_size)

        self.pesos_actor = np.ascontiguousarray(self.pesos_actor, dtype=_dt())
        self.pesos_q1 = np.ascontiguousarray(self.pesos_q1, dtype=_dt())
        self.pesos_q2 = np.ascontiguousarray(self.pesos_q2, dtype=_dt())

        self.sesgo_actor = np.zeros((1, self.output_size), dtype=_dt())
        self.sesgo_q1 = np.zeros((1, 1), dtype=_dt())
        self.sesgo_q2 = np.zeros((1, 1), dtype=_dt())

        # Copias independientes para targets
        self.pesos_actor_target = self.pesos_actor.copy()
        self.sesgo_actor_target = self.sesgo_actor.copy()
        self.pesos_q1_target = self.pesos_q1.copy()
        self.sesgo_q1_target = self.sesgo_q1.copy()
        self.pesos_q2_target = self.pesos_q2.copy()
        self.sesgo_q2_target = self.sesgo_q2.copy()

        logger.info(f"Pesos TD3 inicializados ({m}) [in={self.input_size}, out={self.output_size}]")

    def _asegurar(self) -> None:
        if self.pesos_actor is None or self.pesos_q1 is None or self.pesos_q2 is None:
            self.inicializar_pesos()
        assert (
            self.pesos_actor is not None
            and self.pesos_q1 is not None
            and self.pesos_q2 is not None
        )

    def _prep(self, estado: Any) -> np.ndarray:
        """Formatea el estado como vector matricial 2D."""
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimensión de entrada {x.shape[1]} != input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    def forward_actor(self, estado: np.ndarray, usar_target: bool = False) -> np.ndarray:
        """Calcula la acción determinista acotada en [-1, 1] mediante tanh."""
        t0 = time.perf_counter()
        self._asegurar()
        x = self._prep(estado)
        w = self.pesos_actor_target if usar_target else self.pesos_actor
        b = self.sesgo_actor_target if usar_target else self.sesgo_actor
        accion = np.tanh(x @ w + b).astype(_dt(), copy=False)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(accion, dtype=_dt())

    def forward_q(self, estado: np.ndarray, accion: np.ndarray,
                  usar_target: bool = False, q_network: int = 1) -> np.ndarray:
        """Estima Q(s, a) con Q1 o Q2 (o sus respectivas redes target)."""
        t0 = time.perf_counter()
        self._asegurar()
        accion_arr = np.asarray(accion, dtype=_dt())
        if accion_arr.ndim == 1:
            accion_arr = accion_arr.reshape(1, -1)

        x = self._prep(estado)
        if accion_arr.shape[1] != self.output_size:
            if accion_arr.shape[1] > self.output_size:
                accion_arr = accion_arr[:, :self.output_size]
            else:
                pad = np.zeros((accion_arr.shape[0], self.output_size - accion_arr.shape[1]), dtype=_dt())
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

    def forward(self, estado: np.ndarray) -> np.ndarray:
        """Inferencia principal determinista."""
        return self.forward_actor(estado)

    def seleccionar_accion(self, estado: np.ndarray, agregar_ruido: bool = False) -> np.ndarray:
        """Genera una acción de control determinista con ruido de exploración opcional."""
        accion = self.forward_actor(estado, usar_target=False)
        if agregar_ruido:
            ruido = self.rng.normal(0.0, 0.1, accion.shape)
            accion = np.clip(accion + ruido, -1.0, 1.0)
        return accion.astype(_dt(), copy=False)

    def agregar_experiencia(self, estado: Any, accion: Any, recompensa: float,
                            siguiente_estado: Any, terminado: bool) -> None:
        """Guarda la transición (s, a, r, s', d) en el buffer."""
        self.buffer.agregar(estado, accion, recompensa, siguiente_estado, terminado)
        self.estadisticas_td3['muestras_buffer'] = len(self.buffer)

    def muestrear_batch(self) -> Optional[List[Dict[str, Any]]]:
        """Obtiene un lote de transiciones para optimización."""
        return self.buffer.muestrear(self.batch_size, rng=self.rng)

    def calcular_q_loss(self, batch: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Calcula el error cuadrático medio de Q1 y Q2 contra el target suavizado de Bellman."""
        q1l = 0.0
        q2l = 0.0
        o1 = 0.0
        o2 = 0.0

        for exp in batch:
            s = exp['estado']
            a = exp['accion']
            ns = exp['siguiente_estado']
            r = exp['recompensa']
            term = exp['terminado']

            q1_pred = self.forward_q(s, a, usar_target=False, q_network=1)[0, 0]
            q2_pred = self.forward_q(s, a, usar_target=False, q_network=2)[0, 0]

            # Acción objetivo suavizada con ruido gaussiano recortado
            sa_target = self.forward_actor(ns, usar_target=True)
            sa_suave = self.MotorCalculoTD3.suavizar_accion_objetivo(
                sa_target, self.policy_noise, self.noise_clip, rng=self.rng
            )

            q1_t = self.forward_q(ns, sa_suave, usar_target=True, q_network=1)[0, 0]
            q2_t = self.forward_q(ns, sa_suave, usar_target=True, q_network=2)[0, 0]

            q_obj = self.MotorCalculoTD3.calcular_bellman_target_td3(
                r, term, q1_t, q2_t, self.gamma
            )

            err1 = q1_pred - q_obj
            err2 = q2_pred - q_obj

            q1l += 0.5 * (err1 ** 2)
            q2l += 0.5 * (err2 ** 2)
            o1 += err1
            o2 += err2

        n = max(1, len(batch))
        self.estadisticas_td3['sobreestimacion_q1'] = float(o1 / n)
        self.estadisticas_td3['sobreestimacion_q2'] = float(o2 / n)
        self.estadisticas_td3['sobreestimacion_total'] = float((o1 + o2) / (2.0 * n))
        return float(q1l / n), float(q2l / n)

    def calcular_actor_loss(self, batch: List[Dict[str, Any]]) -> float:
        """Pérdida determinista del actor: J = -E[Q1(s, pi(s))]."""
        al = 0.0
        for exp in batch:
            s = exp['estado']
            accion = self.forward_actor(s, usar_target=False)
            q1v = self.forward_q(s, accion, usar_target=False, q_network=1)[0, 0]
            al += -q1v
        return float(al / max(1, len(batch)))

    def calcular_gradientes_td3(self, batch: List[Dict[str, Any]]) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ]:
        """Calcula los gradientes analíticos de las redes Q y Actor con clipping L2."""
        self._asegurar()
        q1l, q2l = self.calcular_q_loss(batch)
        al = self.calcular_actor_loss(batch)

        self.estadisticas_td3['q1_loss_medio'] = q1l
        self.estadisticas_td3['q2_loss_medio'] = q2l
        self.estadisticas_td3['actor_loss_medio'] = al

        ga = np.zeros_like(self.pesos_actor)
        gsa = np.zeros_like(self.sesgo_actor)
        gq1 = np.zeros_like(self.pesos_q1)
        gq1s = np.zeros_like(self.sesgo_q1)
        gq2 = np.zeros_like(self.pesos_q2)
        gq2s = np.zeros_like(self.sesgo_q2)

        n = max(1, len(batch))

        for exp in batch:
            s = self._prep(exp['estado'])
            a = np.asarray(exp['accion'], dtype=_dt()).reshape(1, -1)
            ns = self._prep(exp['siguiente_estado'])
            r = exp['recompensa']
            term = exp['terminado']

            # Target con smoothing
            sa_target = self.forward_actor(ns, usar_target=True)
            sa_suave = self.MotorCalculoTD3.suavizar_accion_objetivo(
                sa_target, self.policy_noise, self.noise_clip, rng=self.rng
            )

            q1_t = self.forward_q(ns, sa_suave, usar_target=True, q_network=1)[0, 0]
            q2_t = self.forward_q(ns, sa_suave, usar_target=True, q_network=2)[0, 0]
            q_obj = self.MotorCalculoTD3.calcular_bellman_target_td3(r, term, q1_t, q2_t, self.gamma)

            q1_pred = self.forward_q(s, a, usar_target=False, q_network=1)[0, 0]
            q2_pred = self.forward_q(s, a, usar_target=False, q_network=2)[0, 0]

            err1 = q1_pred - q_obj
            err2 = q2_pred - q_obj

            in_q = np.concatenate([s, a[:, :self.output_size]], axis=1)
            gq1 += np.outer(in_q[0], np.array([err1]))
            gq1s += np.array([[err1]])
            gq2 += np.outer(in_q[0], np.array([err2]))
            gq2s += np.array([[err2]])

            # Gradiente del actor: d(-Q1)/d_theta = - dQ1/da * da/d_theta
            a_cur = self.forward_actor(s, usar_target=False)
            # Aproximación del gradiente de acción sobre Q1
            grad_a = self.pesos_q1[self.input_size:, 0]  # linear critic approximation
            # Regla de la cadena con derivada de tanh: (1 - tanh^2)
            d_tanh = (1.0 - a_cur[0] ** 2)
            grad_out = (-grad_a * d_tanh).reshape(1, -1)

            ga += np.outer(s[0], grad_out[0])
            gsa += grad_out

        ga /= n
        gsa /= n
        gq1 /= n
        gq1s /= n
        gq2 /= n
        gq2s /= n

        # Recorte de gradientes
        ga, na = self.MotorCalculoTD3.clipping_l2(ga, 5.0)
        gq1, nq1 = self.MotorCalculoTD3.clipping_l2(gq1, 5.0)
        gq2, nq2 = self.MotorCalculoTD3.clipping_l2(gq2, 5.0)

        self.estadisticas_td3['gradiente_norma_actor'] = na
        self.estadisticas_td3['gradiente_norma_q1'] = nq1
        self.estadisticas_td3['gradiente_norma_q2'] = nq2

        return (
            ga.astype(_dt()),
            gsa.astype(_dt()),
            gq1.astype(_dt()),
            gq1s.astype(_dt()),
            gq2.astype(_dt()),
            gq2s.astype(_dt()),
        )

    def actualizar_pesos(self, ga: np.ndarray, gsa: np.ndarray,
                         gq1: np.ndarray, gq1s: np.ndarray,
                         gq2: np.ndarray, gq2s: np.ndarray) -> None:
        """Aplica la actualización de parámetros para Critics y Actor con retardo (Policy Delay)."""
        with self.pesos_lock:
            # 1. Siempre se actualizan los Critics
            self.pesos_q1 -= self.learning_rate_critic * gq1
            self.sesgo_q1 -= self.learning_rate_critic * gq1s
            self.pesos_q2 -= self.learning_rate_critic * gq2
            self.sesgo_q2 -= self.learning_rate_critic * gq2s

            # 2. Delayed Policy Updates: actualizar Actor y targets cada policy_delay pasos
            self.policy_update_counter += 1
            if self.policy_update_counter % self.policy_delay == 0:
                self.pesos_actor -= self.learning_rate_actor * ga
                self.sesgo_actor -= self.learning_rate_actor * gsa
                self.estadisticas_td3['policy_updates'] += 1
                self._actualizar_redes_objetivo()

            self.historial_actor.append(self.estadisticas_td3['actor_loss_medio'])
            q_mean = (self.estadisticas_td3['q1_loss_medio'] + self.estadisticas_td3['q2_loss_medio']) / 2.0
            self.historial_q.append(q_mean)
            self.historial_sobreest.append(self.estadisticas_td3['sobreestimacion_total'])

    def _actualizar_redes_objetivo(self) -> None:
        """Actualización suave Polyak para redes Actor y Critics target."""
        if (
            self.pesos_actor_target is None
            or self.pesos_q1_target is None
            or self.pesos_q2_target is None
        ):
            return

        for p_target, p_source, b_target, b_source in [
            (self.pesos_actor_target, self.pesos_actor, self.sesgo_actor_target, self.sesgo_actor),
            (self.pesos_q1_target, self.pesos_q1, self.sesgo_q1_target, self.sesgo_q1),
            (self.pesos_q2_target, self.pesos_q2, self.sesgo_q2_target, self.sesgo_q2),
        ]:
            self.MotorCalculoTD3.actualizar_polyak(p_target, p_source, self.tau)
            self.MotorCalculoTD3.actualizar_polyak(b_target, b_source, self.tau)

        self.estadisticas_td3['target_updates'] += 1

    def entrenar_step(self) -> Optional[Dict[str, float]]:
        """Paso completo de entrenamiento sobre el lote de repetición."""
        batch = self.muestrear_batch()
        if batch is None:
            return None

        t0 = time.perf_counter()
        ga, gsa, gq1, gq1s, gq2, gq2s = self.calcular_gradientes_td3(batch)
        self.actualizar_pesos(ga, gsa, gq1, gq1s, gq2, gq2s)
        self.pasos += 1
        self.tiempo_upd += time.perf_counter() - t0

        return {
            'actor_loss': self.estadisticas_td3['actor_loss_medio'],
            'q1_loss': self.estadisticas_td3['q1_loss_medio'],
            'q2_loss': self.estadisticas_td3['q2_loss_medio'],
            'sobreestimacion': self.estadisticas_td3['sobreestimacion_total'],
            'policy_updates': self.estadisticas_td3['policy_updates'],
        }

    def calcular_loss(self, batch: List[Dict[str, Any]]) -> Dict[str, float]:
        """Pérdidas acumuladas de Q1, Q2 y Actor."""
        q1l, q2l = self.calcular_q_loss(batch)
        al = self.calcular_actor_loss(batch)
        return {
            'policy_loss': float(al),
            'value_loss': float((q1l + q2l) / 2.0),
            'total_loss': float(abs(al) + abs(q1l) + abs(q2l)),
        }

    def calcular_explained_variance(self, batch: List[Dict[str, Any]]) -> float:
        """Varianza explicada de Q1 frente a las recompensas reales."""
        preds = np.array([float(self.forward_q(e['estado'], e['accion'], False, 1)[0, 0]) for e in batch], dtype=np.float64)
        rets = np.array([e['recompensa'] for e in batch], dtype=np.float64)
        var = float(np.var(rets))
        resid = float(np.var(rets - preds))
        return float(1.0 - resid / max(1e-12, var))

    def forward_batch(self, estados: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """Inferencia de acciones por lote concatenado."""
        self._asegurar()
        xs = np.concatenate([self._prep(s) for s in estados], axis=0)
        logits = xs @ self.pesos_actor + self.sesgo_actor
        return np.tanh(logits).astype(_dt()), logits.astype(_dt())

    def limpiar_historiales(self) -> None:
        """Limpia los anillos históricos."""
        self.historial_actor.clear()
        self.historial_q.clear()
        self.historial_sobreest.clear()

    def verificar_integridad(self) -> Dict[str, Any]:
        """Verifica inicialización, ausencia de NaNs y coherencia estructural."""
        checks: Dict[str, Any] = {
            'pesos_actor_init': self.pesos_actor is not None,
            'pesos_q1_init': self.pesos_q1 is not None,
            'pesos_q2_init': self.pesos_q2 is not None,
            'pesos_at_init': self.pesos_actor_target is not None,
            'pesos_q1t_init': self.pesos_q1_target is not None,
            'pesos_q2t_init': self.pesos_q2_target is not None,
        }
        for nm, p in [('actor', self.pesos_actor), ('q1', self.pesos_q1), ('q2', self.pesos_q2)]:
            if p is not None:
                checks[f'sin_nan_{nm}'] = not bool(np.any(np.isnan(p)))
                checks[f'sin_inf_{nm}'] = not bool(np.any(np.isinf(p)))
                checks[f'peso_{nm}_max'] = float(np.max(np.abs(p)))

        checks['precision'] = str(self.pesos_actor.dtype) if self.pesos_actor is not None else 'N/A'
        checks['buffer_tamano'] = len(self.buffer)
        checks['policy_updates'] = self.estadisticas_td3['policy_updates']
        checks['target_updates'] = self.estadisticas_td3['target_updates']
        return checks

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Valida que los valores de sobreestimación y pérdidas no hayan divergido."""
        est: Dict[str, bool] = {}
        al = self.estadisticas_td3['actor_loss_medio']
        q1l = self.estadisticas_td3['q1_loss_medio']
        q2l = self.estadisticas_td3['q2_loss_medio']
        est['actor_loss_estable'] = abs(al) < 100.0
        est['q1_loss_estable'] = q1l < 100.0
        est['q2_loss_estable'] = q2l < 100.0

        sob = self.estadisticas_td3['sobreestimacion_total']
        est['sobreestimacion_controlada'] = abs(sob) < 10.0
        est['policy_delay_apropiado'] = 1 <= self.policy_delay <= 5
        est['buffer_suficiente'] = len(self.buffer) >= self.batch_size

        if self.pesos_actor is not None:
            est['pesos_actor_no_explosivos'] = bool(np.max(np.abs(self.pesos_actor)) < 10.0)
        else:
            est['pesos_actor_no_explosivos'] = True

        return est

    def obtener_estadisticas_td3(self) -> Dict[str, Any]:
        """Extrae el informe completo de entrenamiento."""
        if self.pesos_actor is None:
            return {'estado': 'no_inicializada'}

        return {
            'learning_rate_actor': self.learning_rate_actor,
            'learning_rate_critic': self.learning_rate_critic,
            'gamma': self.gamma,
            'tau': self.tau,
            'policy_noise': self.policy_noise,
            'noise_clip': self.noise_clip,
            'policy_delay': self.policy_delay,
            'batch_size': self.batch_size,
            'buffer_size': len(self.buffer),
            'actor_loss_medio': self.estadisticas_td3['actor_loss_medio'],
            'q1_loss_medio': self.estadisticas_td3['q1_loss_medio'],
            'q2_loss_medio': self.estadisticas_td3['q2_loss_medio'],
            'sobreestimacion_q1': self.estadisticas_td3['sobreestimacion_q1'],
            'sobreestimacion_q2': self.estadisticas_td3['sobreestimacion_q2'],
            'sobreestimacion_total': self.estadisticas_td3['sobreestimacion_total'],
            'target_updates': self.estadisticas_td3['target_updates'],
            'policy_updates': self.estadisticas_td3['policy_updates'],
            'muestras_buffer': self.estadisticas_td3['muestras_buffer'],
            't_medio_fwd_us': self.estadisticas_td3.get('t_medio_fwd_us', 0.0),
            't_medio_upd_us': self.estadisticas_td3.get('t_medio_upd_us', 0.0),
            'q_values_media': self.estadisticas_td3.get('q_values_media', 0.0),
            'q_values_std': self.estadisticas_td3.get('q_values_std', 0.0),
            'convergencia': self.estadisticas_td3.get('loss_media', 0.0),
            'loss_media': self.estadisticas_td3.get('loss_media', 0.0),
        }

    def reinicializar_con_parametros(self,
                                     learning_rate_actor: Optional[float] = None,
                                     learning_rate_critic: Optional[float] = None,
                                     gamma: Optional[float] = None,
                                     tau: Optional[float] = None,
                                     policy_delay: Optional[int] = None) -> None:
        """Reinicia parámetros y estado de la neurona TD3."""
        if learning_rate_actor is not None:
            self.learning_rate_actor = float(learning_rate_actor)
        if learning_rate_critic is not None:
            self.learning_rate_critic = float(learning_rate_critic)
        if gamma is not None:
            self.gamma = float(gamma)
        if tau is not None:
            self.tau = float(tau)
        if policy_delay is not None:
            self.policy_delay = int(policy_delay)

        self.inicializar_pesos()
        self.resetear_historial()
        self.buffer.limpiar()
        self.limpiar_historiales()
        self.policy_update_counter = 0
        self.estadisticas_td3['target_updates'] = 0
        self.estadisticas_td3['policy_updates'] = 0
        self.estadisticas_td3['muestras_buffer'] = 0
        logger.info(f"Neurona TD3 reinicializada: lr_actor={self.learning_rate_actor}")

    def a_dict(self) -> Dict[str, Any]:
        """Serialización a diccionario JSON."""
        return {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'pesos_actor': self.pesos_actor.tolist() if self.pesos_actor is not None else None,
            'pesos_q1': self.pesos_q1.tolist() if self.pesos_q1 is not None else None,
            'pesos_q2': self.pesos_q2.tolist() if self.pesos_q2 is not None else None,
            'pesos_actor_target': self.pesos_actor_target.tolist() if self.pesos_actor_target is not None else None,
            'pesos_q1_target': self.pesos_q1_target.tolist() if self.pesos_q1_target is not None else None,
            'pesos_q2_target': self.pesos_q2_target.tolist() if self.pesos_q2_target is not None else None,
            'sesgo_actor': self.sesgo_actor.tolist() if self.sesgo_actor is not None else None,
            'sesgo_q1': self.sesgo_q1.tolist() if self.sesgo_q1 is not None else None,
            'sesgo_q2': self.sesgo_q2.tolist() if self.sesgo_q2 is not None else None,
            'learning_rate_actor': self.learning_rate_actor,
            'learning_rate_critic': self.learning_rate_critic,
            'gamma': self.gamma,
            'tau': self.tau,
            'policy_delay': self.policy_delay,
        }

    def guardar(self, ruta: str) -> None:
        """Guarda los pesos del modelo en formato JSON."""
        import json
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.a_dict(), f, indent=2)

    def cargar(self, ruta: str) -> None:
        """Carga el modelo desde archivo JSON."""
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.inicializar_pesos()
        for k in ['pesos_actor', 'pesos_q1', 'pesos_q2', 'pesos_actor_target', 'pesos_q1_target', 'pesos_q2_target']:
            if d.get(k) is not None:
                setattr(self, k, np.asarray(d[k], dtype=_dt()))
        for k in ['sesgo_actor', 'sesgo_q1', 'sesgo_q2']:
            if d.get(k) is not None:
                setattr(self, k, np.asarray(d[k], dtype=_dt()))

    def __str__(self) -> str:
        return (f"NeuronaRefuerzoTD3(entrada={self.input_size}, salida={self.output_size}, "
                f"lr_a={self.learning_rate_actor}, lr_c={self.learning_rate_critic}, pd={self.policy_delay})")

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["NeuronaRefuerzoTD3"]
