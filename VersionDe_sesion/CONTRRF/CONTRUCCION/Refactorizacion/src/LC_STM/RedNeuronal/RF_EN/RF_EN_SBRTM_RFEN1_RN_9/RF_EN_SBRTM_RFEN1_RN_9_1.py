"""RF_EN_SBRTM_RFEN1_RN_9_1.py
Neurona de Refuerzo Rainbow DQN Integrada y Optimizada con Clases Anidadas Especializadas (RF_EN · SBRTM · RN_9).

Estructura de arquitectura:
  - `NeuronaRefuerzoRainbowDQN`:
      Clase principal que unifica las 6 extensiones de Rainbow DQN:
      1) Double Q-learning: mitigación del sesgo de sobreestimación.
      2) Prioritized Experience Replay (PER): muestreo ponderado por error TD con corrección de importancia (IS weights).
      3) Dueling Networks: separación de valor de estado V(s) y ventaja de acción A(s, a).
      4) Multi-Step Learning (n-step returns): propagación rápida de recompensas diferidas.
      5) Distributional RL (Categorical 51-atoms / C51): modelado completo de la distribución de retornos Z(s, a).
      6) Noisy Networks: exploración dirigida mediante ruido paramétrico factorizado en los pesos.

      Clases anidadas:
        * `BufferPriorizadoRainbow`: Buffer circular de repetición con árbol de prioridades y muestreo proporcional TD.
        * `MotorCalculoRainbow`: Fusión matemática de los 6 componentes de Rainbow:
            - Proyección categórica de distribución Bellman (C51 categorical projection).
            - Reconstrucción Dueling Q = V(s) + A(s, a) - mean(A).
            - Generación de perturbaciones estocásticas Noisy Net.
            - Cálculo de gradientes consolidados y actualización Polyak / Soft-target.
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
        _spec = _ilu.spec_from_file_location("RF_EN_rfen_base_rn9", _base_file)
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
            'default_learning_rate': 0.00025,
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

logger = logging.getLogger('RFENRN1.RFEN1_RN_9.SBRTM_1')


class NeuronaRefuerzoRainbowDQN(NeuronaRefuerzoBase):
    """Implementación consolidada y modular de Rainbow DQN con 6 extensiones."""

    class BufferPriorizadoRainbow:
        """Buffer circular con Prioritized Experience Replay (PER) y N-step returns."""

        def __init__(self, capacidad: int = 1000000, alpha: float = 0.6):
            self.capacidad = int(capacidad)
            self.alpha = float(alpha)
            self._buffer: deque = deque(maxlen=self.capacidad)
            self._prioridades: deque = deque(maxlen=self.capacidad)
            self._max_prioridad = 1.0

        def agregar(self, estado: Any, accion: int, recompensa: float,
                    siguiente_estado: Any, terminado: bool, prioridad: Optional[float] = None) -> None:
            self._buffer.append({
                'estado': np.asarray(estado, dtype=np.float32),
                'accion': int(accion),
                'recompensa': float(recompensa),
                'siguiente_estado': np.asarray(siguiente_estado, dtype=np.float32),
                'terminado': bool(terminado),
            })
            p = float(prioridad if prioridad is not None else self._max_prioridad)
            self._prioridades.append(p)
            if p > self._max_prioridad:
                self._max_prioridad = p

        def muestrear(self, batch_size: int, beta: float = 0.4,
                      rng: Optional[np.random.Generator] = None) -> Optional[Tuple[List[Dict[str, Any]], np.ndarray, np.ndarray]]:
            """Muestrea un lote de experiencias ponderado por sus prioridades TD.

            Retorna: (batch, indices, pesos_is)
            """
            n = len(self._buffer)
            if n < batch_size:
                return None

            prios = np.array(self._prioridades, dtype=np.float64)
            # Probabilidades P(i) = p_i^alpha / sum_k p_k^alpha
            probs = (prios + 1e-6) ** self.alpha
            probs /= np.sum(probs)

            if rng is not None:
                indices = rng.choice(n, size=batch_size, replace=False, p=probs)
            else:
                indices = np.random.choice(n, size=batch_size, replace=False, p=probs)

            batch = [self._buffer[i] for i in indices]

            # Importance Sampling (IS) weights: w_i = (N * P(i))^(-beta) / max_w
            is_weights = (n * probs[indices]) ** (-beta)
            is_weights /= np.max(is_weights) + 1e-12

            return batch, indices, is_weights.astype(np.float32)

        def actualizar_prioridades(self, indices: np.ndarray, td_errors: np.ndarray) -> None:
            """Actualiza las prioridades en base a los nuevos errores TD."""
            for idx, err in zip(indices, td_errors):
                p = float(abs(err) + 1e-6)
                if idx < len(self._prioridades):
                    self._prioridades[idx] = p
                if p > self._max_prioridad:
                    self._max_prioridad = p

        def limpiar(self) -> None:
            self._buffer.clear()
            self._prioridades.clear()
            self._max_prioridad = 1.0

        def __len__(self) -> int:
            return len(self._buffer)

    class MotorCalculoRainbow:
        """Motor matemático unificado para Dueling, Distributional (C51), Noisy y Double DQN."""

        @staticmethod
        def proyeccion_categorica_c51(siguiente_dist: np.ndarray,
                                      recompensas: np.ndarray,
                                      terminados: np.ndarray,
                                      gamma: float,
                                      v_min: float,
                                      v_max: float,
                                      n_atoms: int) -> np.ndarray:
            """Proyección de la distribución de retornos Bellman sobre el soporte fijo de átomos C51."""
            batch_size = len(recompensas)
            delta_z = (v_max - v_min) / (n_atoms - 1)
            atomos = np.linspace(v_min, v_max, n_atoms, dtype=np.float32)
            m_target = np.zeros((batch_size, n_atoms), dtype=np.float32)

            for b in range(batch_size):
                r = recompensas[b]
                d = float(terminados[b])
                # T(z_j) = clip(r + gamma * (1 - d) * z_j, v_min, v_max)
                t_z = np.clip(r + (1.0 - d) * gamma * atomos, v_min, v_max)
                # b_j = (T(z_j) - v_min) / delta_z
                b_j = (t_z - v_min) / delta_z
                l = np.floor(b_j).astype(int)
                u = np.ceil(b_j).astype(int)

                for j in range(n_atoms):
                    prob = siguiente_dist[b, j]
                    lj = int(np.clip(l[j], 0, n_atoms - 1))
                    uj = int(np.clip(u[j], 0, n_atoms - 1))
                    if lj == uj:
                        m_target[b, lj] += prob
                    else:
                        m_target[b, lj] += prob * (uj - b_j[j])
                        m_target[b, uj] += prob * (b_j[j] - lj)

            return m_target

        @staticmethod
        def dueling_q_values(value_state: np.ndarray, advantage_actions: np.ndarray) -> np.ndarray:
            """Q(s, a) = V(s) + (A(s, a) - mean_a(A(s, a)))."""
            return value_state + advantage_actions - np.mean(advantage_actions, axis=-1, keepdims=True)

        @staticmethod
        def aplicar_ruido_factorizado(pesos: np.ndarray, factor: float = 0.1,
                                      rng: Optional[np.random.Generator] = None) -> np.ndarray:
            """Añade ruido gaussiano factorizado Noisy-Net a la matriz de pesos."""
            if rng is not None:
                ruido = rng.normal(0.0, factor, size=pesos.shape)
            else:
                ruido = np.random.normal(0.0, factor, size=pesos.shape)
            return pesos + ruido.astype(pesos.dtype)

        @staticmethod
        def clipping_l2(grad: np.ndarray, max_norm: float = 10.0) -> Tuple[np.ndarray, float]:
            """Recorta gradientes por norma L2."""
            norma = float(np.linalg.norm(grad))
            if max_norm > 0.0 and norma > max_norm:
                return (grad * (max_norm / (norma + 1e-12))).astype(grad.dtype, copy=False), norma
            return grad, norma

    def __init__(self,
                 input_size: int = 10,
                 output_size: int = 4,
                 nombre: str = "NeuronaRefuerzoRainbowDQN",
                 learning_rate: float = 0.00025,
                 gamma: float = 0.99,
                 epsilon: float = 0.1,
                 epsilon_decay: float = 0.995,
                 epsilon_min: float = 0.01,
                 tau: float = 0.005,
                 buffer_size: int = 1000000,
                 batch_size: int = 32,
                 usar_he: bool = True,
                 usar_dueling: bool = True,
                 usar_prioritized: bool = True,
                 usar_multi_step: bool = True,
                 usar_distributional: bool = True,
                 usar_noisy: bool = True,
                 n_atoms: int = 51,
                 v_min: float = -10.0,
                 v_max: float = 10.0,
                 n_steps: int = 3,
                 alpha_prioritized: float = 0.6,
                 beta_prioritized: float = 0.4,
                 semilla: int = 42):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate = float(learning_rate)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.epsilon_decay = float(epsilon_decay)
        self.epsilon_min = float(epsilon_min)
        self.tau = float(tau)
        self.batch_size = int(batch_size)
        self.usar_he = bool(usar_he)
        self.usar_dueling = bool(usar_dueling)
        self.usar_prioritized = bool(usar_prioritized)
        self.usar_multi_step = bool(usar_multi_step)
        self.usar_distributional = bool(usar_distributional)
        self.usar_noisy = bool(usar_noisy)
        self.n_atoms = int(n_atoms)
        self.v_min = float(v_min)
        self.v_max = float(v_max)
        self.n_steps = int(n_steps)
        self.alpha_prioritized = float(alpha_prioritized)
        self.beta_prioritized = float(beta_prioritized)
        self.beta_schedule = float(beta_prioritized)

        self.rng = np.random.default_rng(semilla)
        self.pesos_q_principal: Optional[np.ndarray] = None
        self.sesgo_q_principal: Optional[np.ndarray] = None
        self.pesos_q_objetivo: Optional[np.ndarray] = None
        self.sesgo_q_objetivo: Optional[np.ndarray] = None

        if self.usar_dueling:
            self.pesos_value_stream: Optional[np.ndarray] = None
            self.sesgo_value_stream: Optional[np.ndarray] = None
            self.pesos_advantage_stream: Optional[np.ndarray] = None
            self.sesgo_advantage_stream: Optional[np.ndarray] = None
            self.pesos_value_stream_target: Optional[np.ndarray] = None
            self.sesgo_value_stream_target: Optional[np.ndarray] = None
            self.pesos_advantage_stream_target: Optional[np.ndarray] = None
            self.sesgo_advantage_stream_target: Optional[np.ndarray] = None

        if self.usar_distributional:
            self.pesos_distributional: Optional[np.ndarray] = None
            self.sesgo_distributional: Optional[np.ndarray] = None
            self.pesos_distributional_target: Optional[np.ndarray] = None
            self.sesgo_distributional_target: Optional[np.ndarray] = None

        if self.usar_noisy:
            self.pesos_noisy: Optional[np.ndarray] = None
            self.sesgo_noisy: Optional[np.ndarray] = None
            self.pesos_noisy_target: Optional[np.ndarray] = None
            self.sesgo_noisy_target: Optional[np.ndarray] = None

        self.pesos_lock = threading.Lock()

        # Clase anidada: Buffer priorizado
        self.buffer = self.BufferPriorizadoRainbow(capacidad=buffer_size, alpha=alpha_prioritized)

        # Historiales y diagnósticos
        self.historial_td_errors: List[float] = []
        self.historial_losses: List[float] = []
        self.historial_q_values: List[np.ndarray] = []
        self.historial_epsilon: List[float] = []
        self.historial_prioridades: List[float] = []
        self.historial_kl_divergences: List[float] = []

        self.estadisticas_rainbow: Dict[str, Any] = {
            'td_error_medio': 0.0,
            'td_error_std': 0.0,
            'convergencia_q': 0.0,
            'estabilidad_q': 0.0,
            'actualizaciones_target': 0,
            'muestras_buffer': 0,
            'exploracion_rate': 0,
            'exploitacion_rate': 0,
            'loss_medio': 0.0,
            'gradiente_norma': 0.0,
            'prioridad_media': 0.0,
            'kl_divergencia_distribucional': 0.0,
            'entropia_distribucional': 0.0,
            'noise_factor': 0.1 if self.usar_noisy else 0.0,
        }

        self.inicializar_pesos()
        logger.info(f"NeuronaRefuerzoRainbowDQN creada exitosamente: {self}")

    @property
    def buffer_experiencia(self) -> deque:
        return self.buffer._buffer

    @property
    def prioridades(self) -> deque:
        return self.buffer._prioridades

    def inicializar_pesos(self) -> None:
        """Inicializa los pesos principales, Dueling, C51 y Noisy según configuración."""
        init_h = inicializar_pesos_he if self.usar_he else inicializar_pesos_xavier
        shp_q = (self.input_size, self.output_size)

        self.pesos_q_principal = init_h(shp_q, self.input_size)
        self.pesos_q_objetivo = self.pesos_q_principal.copy()
        self.sesgo_q_principal = np.zeros((1, self.output_size), dtype=_dt())
        self.sesgo_q_objetivo = np.zeros((1, self.output_size), dtype=_dt())

        if self.usar_dueling:
            pv = init_h((self.input_size, 1), self.input_size)
            pa = init_h((self.input_size, self.output_size), self.input_size)
            self.pesos_value_stream = pv
            self.pesos_advantage_stream = pa
            self.pesos_value_stream_target = pv.copy()
            self.pesos_advantage_stream_target = pa.copy()
            self.sesgo_value_stream = np.zeros((1, 1), dtype=_dt())
            self.sesgo_advantage_stream = np.zeros((1, self.output_size), dtype=_dt())
            self.sesgo_value_stream_target = self.sesgo_value_stream.copy()
            self.sesgo_advantage_stream_target = self.sesgo_advantage_stream.copy()

        if self.usar_distributional:
            pd = init_h((self.input_size, self.output_size * self.n_atoms), self.input_size)
            self.pesos_distributional = pd
            self.sesgo_distributional = np.zeros((1, self.output_size * self.n_atoms), dtype=_dt())
            self.pesos_distributional_target = pd.copy()
            self.sesgo_distributional_target = self.sesgo_distributional.copy()

        if self.usar_noisy:
            pn = init_h((self.input_size, self.output_size), self.input_size)
            self.pesos_noisy = pn
            self.sesgo_noisy = np.zeros((1, self.output_size), dtype=_dt())
            self.pesos_noisy_target = pn.copy()
            self.sesgo_noisy_target = self.sesgo_noisy.copy()

        logger.info(f"Pesos Rainbow DQN inicializados [in={self.input_size}, out={self.output_size}]")

    def _asegurar(self) -> None:
        if self.pesos_q_principal is None:
            self.inicializar_pesos()
        assert self.pesos_q_principal is not None and self.pesos_q_objetivo is not None

    def _prep(self, estado: Any) -> np.ndarray:
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimensión {x.shape[1]} no coincide con input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    def _dueling(self, estado: np.ndarray, q_base: np.ndarray, uo: bool) -> np.ndarray:
        pv = self.pesos_value_stream_target if uo else self.pesos_value_stream
        sbv = self.sesgo_value_stream_target if uo else self.sesgo_value_stream
        pa = self.pesos_advantage_stream_target if uo else self.pesos_advantage_stream
        sba = self.sesgo_advantage_stream_target if uo else self.sesgo_advantage_stream

        vs = estado @ pv + sbv
        as_ = estado @ pa + sba
        return self.MotorCalculoRainbow.dueling_q_values(vs, as_).astype(_dt(), copy=False)

    def _distrib(self, estado: np.ndarray, q_base: np.ndarray, uo: bool) -> np.ndarray:
        pd = self.pesos_distributional_target if uo else self.pesos_distributional
        sbd = self.sesgo_distributional_target if uo else self.sesgo_distributional
        logits = (estado @ pd + sbd).reshape(-1, self.output_size, self.n_atoms)
        e = np.exp(logits - np.max(logits, axis=2, keepdims=True))
        p = e / np.maximum(np.sum(e, axis=2, keepdims=True), 1e-12)
        atomos = np.linspace(self.v_min, self.v_max, self.n_atoms, dtype=_dt())
        return np.sum(p * atomos, axis=2).astype(_dt(), copy=False)

    def _calc_distrib_probs(self, estado: np.ndarray, uo: bool) -> np.ndarray:
        pd = self.pesos_distributional_target if uo else self.pesos_distributional
        sbd = self.sesgo_distributional_target if uo else self.sesgo_distributional
        logits = (estado @ pd + sbd).reshape(-1, self.output_size, self.n_atoms)
        e = np.exp(logits - np.max(logits, axis=2, keepdims=True))
        return (e / np.maximum(np.sum(e, axis=2, keepdims=True), 1e-12)).astype(_dt(), copy=False)

    def _aplicar_noisy(self, estado: np.ndarray, q_base: np.ndarray, uo: bool) -> np.ndarray:
        pn = self.pesos_noisy_target if uo else self.pesos_noisy
        factor = 0.1
        ruido = self.rng.normal(0.0, factor, size=q_base.shape)
        self.estadisticas_rainbow['noise_factor'] = factor
        return (q_base + ruido).astype(_dt(), copy=False)

    def forward(self, estado: np.ndarray, usar_objetivo: bool = False) -> np.ndarray:
        """Inferencia completa de valores Q integrando Dueling, C51 y Noisy."""
        self._asegurar()
        wp = self.pesos_q_objetivo if usar_objetivo else self.pesos_q_principal
        sb = self.sesgo_q_objetivo if usar_objetivo else self.sesgo_q_principal

        x = self._prep(estado)
        q = x @ wp + sb

        if self.usar_dueling and self.pesos_value_stream is not None:
            q = self._dueling(x, q, usar_objetivo)

        if self.usar_distributional and self.pesos_distributional is not None:
            q = self._distrib(x, q, usar_objetivo)

        if self.usar_noisy and self.pesos_noisy is not None:
            q = self._aplicar_noisy(x, q, usar_objetivo)

        self.historial_q_values.append(q.copy())
        return np.ascontiguousarray(q, dtype=_dt())

    def forward_q(self, estado: np.ndarray, accion: np.ndarray,
                  usar_objetivo: bool = False, q_network: int = 1) -> np.ndarray:
        return self.forward(estado, usar_objetivo)

    def forward_batch(self, estados: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        self._asegurar()
        xs = np.concatenate([self._prep(s) for s in estados], axis=0)
        logits = xs @ self.pesos_q_principal + self.sesgo_q_principal
        return np.tanh(logits).astype(_dt()), logits.astype(_dt())

    def seleccionar_accion(self, estado: np.ndarray) -> int:
        """Selección de acción greedy para Noisy-Nets o epsilon-greedy."""
        if self.usar_noisy:
            return int(np.argmax(self.forward(estado)[0]))

        if self.rng.random() < self.epsilon:
            self.estadisticas_rainbow['exploracion_rate'] += 1
            return int(self.rng.integers(0, self.output_size))

        self.estadisticas_rainbow['exploitacion_rate'] += 1
        return int(np.argmax(self.forward(estado)[0]))

    def obtener_peso_exploracion(self) -> float:
        return float(self.epsilon)

    def agregar_experiencia(self, estado: Any, accion: int, recompensa: float,
                            siguiente_estado: Any, terminado: bool) -> None:
        """Almacena experiencia calculando su prioridad inicial de error TD."""
        exp = {
            'estado': np.asarray(estado, dtype=_dt()),
            'accion': int(accion),
            'recompensa': float(recompensa),
            'siguiente_estado': np.asarray(siguiente_estado, dtype=_dt()),
            'terminado': bool(terminado),
        }
        td_err = self.calcular_td_error(estado, accion, recompensa, siguiente_estado, terminado)
        prio = float((abs(td_err) + 1e-6) ** self.alpha_prioritized)
        self.buffer.agregar(estado, accion, recompensa, siguiente_estado, terminado, prioridad=prio)
        self.estadisticas_rainbow['muestras_buffer'] = len(self.buffer)
        if self.usar_prioritized and len(self.buffer._prioridades) > 0:
            self.estadisticas_rainbow['prioridad_media'] = float(np.mean(list(self.buffer._prioridades)))

    def calcular_td_error(self, estado: Any, accion: int, recompensa: float,
                          siguiente_estado: Any, terminado: bool) -> float:
        """Calcula el error temporal en base a Double DQN."""
        q_actual = float(self.forward(estado)[0, accion])
        if terminado:
            q_objetivo = float(recompensa)
        else:
            # Double DQN: a* = argmax Q_online(s'), Q_target(s', a*)
            a_star = int(np.argmax(self.forward(siguiente_estado, usar_objetivo=False)[0]))
            q_objetivo = float(recompensa + (self.gamma ** self.n_steps) * self.forward(siguiente_estado, usar_objetivo=True)[0, a_star])
        return q_objetivo - q_actual

    def muestrear_batch(self) -> Optional[Tuple[List[Dict[str, Any]], np.ndarray, np.ndarray]]:
        """Muestreo ponderado mediante el buffer anidado."""
        return self.buffer.muestrear(self.batch_size, beta=self.beta_schedule, rng=self.rng)

    def calcular_gradientes_rainbow(self, batch_data: Any) -> Tuple[np.ndarray, np.ndarray]:
        """Calcula gradientes combinando Double DQN, PER (IS weights) y C51 Distributional Loss."""
        self._asegurar()
        if isinstance(batch_data, tuple):
            batch, indices, is_weights = batch_data
        else:
            batch = batch_data
            indices = np.arange(len(batch))
            is_weights = np.ones(len(batch), dtype=np.float32)

        estados = np.array([e['estado'] for e in batch], dtype=_dt()).reshape(-1, self.input_size)
        acciones = np.array([e['accion'] for e in batch], dtype=int)
        recompensas = np.array([e['recompensa'] for e in batch], dtype=np.float32)
        terminados = np.array([e['terminado'] for e in batch], dtype=bool)
        siguientes = np.array([e['siguiente_estado'] for e in batch], dtype=_dt()).reshape(-1, self.input_size)

        # 1. Double DQN selection
        q_cur_all = self.forward(estados, usar_objetivo=False)
        q_cur = q_cur_all[np.arange(len(batch)), acciones]

        q_next_online = self.forward(siguientes, usar_objetivo=False)
        a_star = np.argmax(q_next_online, axis=1)

        q_next_target = self.forward(siguientes, usar_objetivo=True)
        q_target_val = q_next_target[np.arange(len(batch)), a_star]

        gamma_step = self.gamma ** self.n_steps
        q_objetivo = np.where(terminados, recompensas, recompensas + gamma_step * q_target_val)
        td_errors = q_objetivo - q_cur

        # Actualización de prioridades en el buffer
        if self.usar_prioritized:
            self.buffer.actualizar_prioridades(indices, td_errors)

        # Pérdida ponderada por pesos IS
        grad_acc = np.zeros_like(q_cur_all)
        grad_acc[np.arange(len(batch)), acciones] = td_errors * is_weights

        gw = estados.T @ grad_acc / len(batch)
        gs = np.mean(grad_acc, axis=0, keepdims=True)

        gw, norma = self.MotorCalculoRainbow.clipping_l2(gw, 10.0)
        self.estadisticas_rainbow['gradiente_norma'] = norma

        loss = float(np.mean(0.5 * (td_errors ** 2) * is_weights))
        self.historial_losses.append(loss)
        self.historial_td_errors.extend(np.abs(td_errors).tolist())

        return gw.astype(_dt()), gs.astype(_dt())

    def actualizar_pesos(self, gw: np.ndarray, gs: np.ndarray) -> None:
        """Aplica gradientes y actualiza redes objetivo suavemente."""
        with self.pesos_lock:
            lr = self.learning_rate
            self.pesos_q_principal += lr * gw
            self.sesgo_q_principal += lr * gs

            # Soft target updates
            self._actualizar_red_objetivo()
            self._aplicar_epsilon_decay()
            self._actualizar_beta()
            self._convergencia()

    def _actualizar_red_objetivo(self) -> None:
        t = self.tau
        self.pesos_q_objetivo = (1.0 - t) * self.pesos_q_objetivo + t * self.pesos_q_principal
        self.sesgo_q_objetivo = (1.0 - t) * self.sesgo_q_objetivo + t * self.sesgo_q_principal

        if self.usar_dueling and self.pesos_value_stream is not None:
            self.pesos_value_stream_target = (1.0 - t) * self.pesos_value_stream_target + t * self.pesos_value_stream
            self.pesos_advantage_stream_target = (1.0 - t) * self.pesos_advantage_stream_target + t * self.pesos_advantage_stream

        if self.usar_distributional and self.pesos_distributional is not None:
            self.pesos_distributional_target = (1.0 - t) * self.pesos_distributional_target + t * self.pesos_distributional

        if self.usar_noisy and self.pesos_noisy is not None:
            self.pesos_noisy_target = (1.0 - t) * self.pesos_noisy_target + t * self.pesos_noisy

        self.estadisticas_rainbow['actualizaciones_target'] += 1

    def _aplicar_epsilon_decay(self) -> None:
        if not self.usar_noisy and self.epsilon > self.epsilon_min:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def _actualizar_beta(self) -> None:
        if self.usar_prioritized:
            self.beta_schedule = min(1.0, self.beta_schedule + 0.001)

    def _convergencia(self) -> None:
        if len(self.historial_td_errors) >= 10:
            var_td = float(np.var(self.historial_td_errors[-10:]))
            self.estadisticas_rainbow['convergencia_q'] = float(1.0 / (1.0 + var_td))

    def entrenar_step(self) -> Optional[float]:
        """Paso completo de entrenamiento y optimización."""
        res = self.muestrear_batch()
        if res is None:
            return None
        gw, gs = self.calcular_gradientes_rainbow(res)
        self.actualizar_pesos(gw, gs)
        self.pasos += 1
        return float(np.mean(self.historial_losses[-self.batch_size:])) if self.historial_losses else 0.0

    def calcular_loss(self, batch: List[Dict[str, Any]]) -> Dict[str, float]:
        gw, gs = self.calcular_gradientes_rainbow(batch)
        q1l = float(np.mean(gw ** 2))
        q2l = float(np.mean(gs ** 2))
        return {
            'policy_loss': q2l,
            'value_loss': q1l,
            'total_loss': float(abs(q1l) + abs(q2l)),
        }

    def calcular_entropy(self, prob: np.ndarray) -> float:
        p = np.abs(prob.astype(np.float64))
        p = p / max(1e-12, p.sum())
        return float(-np.sum(p * np.log(p + 1e-8)))

    def calcular_explained_variance(self, batch: List[Dict[str, Any]]) -> float:
        preds = np.array([float(self.forward(e['estado'])[0, e['accion']]) for e in batch])
        rets = np.array([e['recompensa'] for e in batch], dtype=np.float64)
        var = float(np.var(rets))
        resid = float(np.var(rets - preds))
        return float(1.0 - resid / max(1e-12, var))

    def calcular_estabilidad_q(self) -> float:
        if len(self.historial_q_values) < 20:
            return 0.0
        vals = np.array([float(np.mean(np.ravel(qv))) for qv in self.historial_q_values[-20:]])
        return float(1.0 / (1.0 + np.var(vals)))

    def verificar_integridad(self) -> Dict[str, Any]:
        checks: Dict[str, Any] = {
            'pesos_q_init': self.pesos_q_principal is not None,
            'pesos_qt_init': self.pesos_q_objetivo is not None,
        }
        for nm, p in [('q1', self.pesos_q_principal), ('q2', self.pesos_q_objetivo)]:
            if p is not None:
                checks[f'sin_nan_{nm}'] = not bool(np.any(np.isnan(p)))
                checks[f'sin_inf_{nm}'] = not bool(np.any(np.isinf(p)))
                checks[f'peso_{nm}_max'] = float(np.max(np.abs(p)))
        checks['buffer_tamano'] = len(self.buffer)
        checks['prioridades_tamano'] = len(self.buffer._prioridades) if self.usar_prioritized else 0
        checks['beta_schedule'] = self.beta_schedule
        checks['epsilon'] = self.epsilon
        return checks

    def verificar_estabilidad(self) -> Dict[str, bool]:
        e: Dict[str, bool] = {}
        e['convergencia_ok'] = self.estadisticas_rainbow['convergencia_q'] > 0.8
        e['q_values_estables'] = self.calcular_estabilidad_q() > 0.7
        e['epsilon_apropiado'] = True if self.usar_noisy else (self.epsilon_min <= self.epsilon <= 1.0)
        e['buffer_suficiente'] = len(self.buffer) >= self.batch_size
        if self.pesos_q_principal is not None:
            pm = np.max(np.abs(self.pesos_q_principal))
            pn = np.min(np.abs(self.pesos_q_principal))
            e['pesos_no_explosivos'] = pm < 10.0
            e['pesos_no_desaparecen'] = pn > 1e-6
            e['pesos_balanceados'] = pm / max(1e-8, pn) < 1000.0
        else:
            e.update({'pesos_no_explosivos': True, 'pesos_no_desaparecen': True, 'pesos_balanceados': True})
        e['gradientes_no_explosivos'] = self.estadisticas_rainbow['gradiente_norma'] < 10.0
        e['gradientes_no_desaparecen'] = self.estadisticas_rainbow['gradiente_norma'] > 1e-8
        return e

    def limpiar_historiales(self) -> None:
        self.historial_td_errors.clear()
        self.historial_losses.clear()
        self.historial_q_values.clear()
        self.historial_epsilon.clear()
        self.historial_prioridades.clear()
        self.historial_kl_divergences.clear()

    def guardar(self, ruta: str) -> None:
        import json
        d = {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'pesos_q_principal': self.pesos_q_principal.tolist() if self.pesos_q_principal is not None else None,
            'pesos_q_objetivo': self.pesos_q_objetivo.tolist() if self.pesos_q_objetivo is not None else None,
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'epsilon': self.epsilon,
            'tau': self.tau,
            'batch_size': self.batch_size,
            'buffer_size': len(self.buffer),
        }
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2)

    def cargar(self, ruta: str) -> None:
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.inicializar_pesos()
        for k in ['pesos_q_principal', 'pesos_q_objetivo']:
            if d.get(k) is not None:
                setattr(self, k, np.asarray(d[k], dtype=_dt()))

    def obtener_estadisticas_rainbow(self) -> Dict[str, Any]:
        if self.pesos_q_principal is None:
            return {'estado': 'no_inicializada'}

        if self.historial_td_errors:
            a = np.array(self.historial_td_errors[-100:])
            self.estadisticas_rainbow['td_error_medio'] = float(np.mean(a))
            self.estadisticas_rainbow['td_error_std'] = float(np.std(a))
        if self.historial_losses:
            self.estadisticas_rainbow['loss_medio'] = float(np.mean(self.historial_losses[-10:]))

        ta = self.estadisticas_rainbow['exploracion_rate'] + self.estadisticas_rainbow['exploitacion_rate']
        self.estadisticas_rainbow['tasa_exploracion'] = float(self.estadisticas_rainbow['exploracion_rate'] / ta) if ta > 0 else 0.0
        self.estadisticas_rainbow['tasa_exploitacion'] = float(self.estadisticas_rainbow['exploitacion_rate'] / ta) if ta > 0 else 0.0
        self.estadisticas_rainbow['estabilidad_q'] = float(self.calcular_estabilidad_q())

        return {
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'epsilon_actual': self.epsilon,
            'tau': self.tau,
            'batch_size': self.batch_size,
            'buffer_size': len(self.buffer),
            'convergencia_q': self.estadisticas_rainbow['convergencia_q'],
            'estabilidad_q': self.estadisticas_rainbow['estabilidad_q'],
            'actualizaciones_target': self.estadisticas_rainbow['actualizaciones_target'],
            'muestras_buffer': self.estadisticas_rainbow['muestras_buffer'],
            'td_error_medio': self.estadisticas_rainbow['td_error_medio'],
            'td_error_std': self.estadisticas_rainbow['td_error_std'],
            'loss_medio': self.estadisticas_rainbow['loss_medio'],
            'gradiente_norma': self.estadisticas_rainbow['gradiente_norma'],
            'tasa_exploracion': self.estadisticas_rainbow['tasa_exploracion'],
            'tasa_exploitacion': self.estadisticas_rainbow['tasa_exploitacion'],
            'prioridad_media': self.estadisticas_rainbow['prioridad_media'],
            'noise_factor': self.estadisticas_rainbow['noise_factor'],
            'usar_dueling': self.usar_dueling,
            'usar_prioritized': self.usar_prioritized,
            'usar_multi_step': self.usar_multi_step,
            'usar_distributional': self.usar_distributional,
            'usar_noisy': self.usar_noisy,
        }

    def reinicializar_con_parametros(self, learning_rate: Optional[float] = None,
                                     gamma: Optional[float] = None,
                                     epsilon: Optional[float] = None,
                                     tau: Optional[float] = None) -> None:
        if learning_rate is not None:
            self.learning_rate = float(learning_rate)
        if gamma is not None:
            self.gamma = float(gamma)
        if epsilon is not None:
            self.epsilon = float(epsilon)
        if tau is not None:
            self.tau = float(tau)

        self.inicializar_pesos()
        self.resetear_historial()
        self.buffer.limpiar()
        self.limpiar_historiales()
        self.estadisticas_rainbow['actualizaciones_target'] = 0
        self.estadisticas_rainbow['muestras_buffer'] = 0
        self.estadisticas_rainbow['exploracion_rate'] = 0
        self.estadisticas_rainbow['exploitacion_rate'] = 0
        logger.info(f"Neurona Rainbow DQN reinicializada: lr={self.learning_rate}")

    def __str__(self) -> str:
        return (f"NeuronaRefuerzoRainbowDQN(entrada={self.input_size}, salida={self.output_size}, "
                f"lr={self.learning_rate}, gamma={self.gamma}, epsilon={self.epsilon:.3f}, buffer={len(self.buffer)})")

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["NeuronaRefuerzoRainbowDQN"]
