"""RF_EN_SBRTM_RFEN1_RN_10_1.py
Neurona de Refuerzo IMPALA (Importance Weighted Actor-Learner Architecture) con
Algoritmo de Correccion Off-Policy V-trace y Clases Anidadas Especializadas (RF_EN · SBRTM · RN_10).

Estructura de arquitectura:
  - `NeuronaRefuerzoIMPALA`:
      Clase principal que implementa el marco distribuido Actor-Learner desvinculado (IMPALA):
      1) Múltiples Actores locales que generan trayectorias asíncronas con políticas locales desactualizadas (mu).
      2) Learner central con cálculo de corrección V-trace (rhos y cs acotados) para reconciliar
         la discrepancia entre la política del actor que recolectó datos (mu) y la política actual del learner (pi).
      3) Actualizaciones vectorizadas de Actor, Critic y regularización entrópica.
      4) Sincronización thread-safe periódica entre Learner central y Actores.

      Clases anidadas:
        * `BufferActoresIMPALA`: Gestor multicanal de buffers circulares thread-safe por cada worker/actor.
        * `MotorCalculoVTrace`: Fusión matemática de los algoritmos de corrección off-policy V-trace:
            - Ratios de importancia truncados rho_t = min(rho_bar, pi(a_t|s_t) / mu(a_t|s_t)).
            - Coeficientes de corrección c_t = min(c_bar, pi(a_t|s_t) / mu(a_t|s_t)).
            - Targets recursivos de valor V-trace v_s y ventajas corregidas delta_V.
            - Recorte L2 conjunto de gradientes (Actor + Critic).
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
        _spec = _ilu.spec_from_file_location("RF_EN_rfen_base_rn10", _base_file)
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

logger = logging.getLogger('RFENRN1.RFEN1_RN_10.SBRTM_1')


class NeuronaRefuerzoIMPALA(NeuronaRefuerzoBase):
    """Arquitectura distribuida IMPALA con corrección de sesgo V-trace off-policy."""

    class BufferActoresIMPALA:
        """Almacén multicanal thread-safe de experiencias por cada Actor/Worker."""

        def __init__(self, num_actors: int = 8, capacidad_actor: int = 1000):
            self.num_actors = int(num_actors)
            self.capacidad_actor = int(capacidad_actor)
            self._lock = threading.Lock()
            self._canales: Dict[int, deque] = {
                aid: deque(maxlen=self.capacidad_actor) for aid in range(self.num_actors)
            }
            self._prioridades: Dict[int, deque] = {
                aid: deque(maxlen=self.capacidad_actor) for aid in range(self.num_actors)
            }

        def agregar(self, actor_id: int, estado: Any, accion: int, recompensa: float,
                    siguiente_estado: Any, terminado: bool, probabilidad_accion: float) -> None:
            with self._lock:
                if actor_id not in self._canales:
                    self._canales[actor_id] = deque(maxlen=self.capacidad_actor)
                    self._prioridades[actor_id] = deque(maxlen=self.capacidad_actor)

                exp = {
                    'estado': np.asarray(estado, dtype=np.float32),
                    'accion': int(accion),
                    'recompensa': float(recompensa),
                    'siguiente_estado': np.asarray(siguiente_estado, dtype=np.float32),
                    'terminado': bool(terminado),
                    'probabilidad_accion': float(max(1e-12, probabilidad_accion)),
                    'timestamp': time.time(),
                }
                self._canales[actor_id].append(exp)

        def muestrear(self, actor_id: int, batch_size: int,
                      rng: Optional[np.random.Generator] = None) -> Optional[List[Dict[str, Any]]]:
            with self._lock:
                canal = self._canales.get(actor_id)
                if canal is None or len(canal) < batch_size:
                    return None
                if rng is not None:
                    indices = rng.choice(len(canal), size=batch_size, replace=False)
                    return [canal[i] for i in indices]
                return random.sample(list(canal), batch_size)

        def limpiar(self, actor_id: Optional[int] = None) -> None:
            with self._lock:
                if actor_id is not None:
                    if actor_id in self._canales:
                        self._canales[actor_id].clear()
                else:
                    for c in self._canales.values():
                        c.clear()

        def total_muestras(self) -> int:
            with self._lock:
                return sum(len(c) for c in self._canales.values())

    class MotorCalculoVTrace:
        """Motor matemático unificado para el algoritmo V-trace y sincronizaciones."""

        @staticmethod
        def calcular_vtrace(recompensas: np.ndarray,
                            valores: np.ndarray,
                            terminados: np.ndarray,
                            probabilidades_learner: np.ndarray,
                            probabilidades_actor: np.ndarray,
                            gamma: float = 0.99,
                            rho_bar: float = 1.0,
                            c_bar: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
            """Calcula las ventajas y objetivos corregidos mediante V-trace.

            Retorna:
              - vs: Objetivos de valor V-trace para el Critic
              - ventajas: Ventajas corregidas para la pérdida de la política
              - is_ratios: Ratios de importancia sin recortar (para diagnóstico)
            """
            n = len(recompensas)
            # Ratios de importancia rho_t = pi(a_t|s_t) / mu(a_t|s_t)
            is_ratios = probabilidades_learner / np.maximum(probabilidades_actor, 1e-12)
            rhos = np.minimum(rho_bar, is_ratios)
            cs = np.minimum(c_bar, is_ratios)

            vs = np.zeros(n, dtype=np.float32)
            ventajas = np.zeros(n, dtype=np.float32)

            # Acumulador recursivo en reversa de V-trace
            acumulado_diff = 0.0

            for t in reversed(range(n)):
                siguiente_val = 0.0 if (t == n - 1 or terminados[t]) else valores[t + 1]
                # delta_t V = rho_t * (r_t + gamma * V(s_{t+1}) - V(s_t))
                delta_t = rhos[t] * (recompensas[t] + gamma * siguiente_val - valores[t])

                # v_t = V(s_t) + delta_t V + gamma * c_t * (v_{t+1} - V(s_{t+1}))
                v_t = valores[t] + delta_t + gamma * cs[t] * acumulado_diff
                vs[t] = v_t
                acumulado_diff = v_t - siguiente_val

                # Ventaja para la política: rho_t * (r_t + gamma * v_{t+1} - V(s_t))
                siguiente_v = 0.0 if (t == n - 1 or terminados[t]) else vs[t + 1]
                ventajas[t] = rhos[t] * (recompensas[t] + gamma * siguiente_v - valores[t])

            return vs, ventajas, is_ratios

        @staticmethod
        def clipping_l2(grad: np.ndarray, max_norm: float = 0.5) -> Tuple[np.ndarray, float]:
            """Recorte de gradientes por norma L2."""
            norma = float(np.linalg.norm(grad))
            if max_norm > 0.0 and norma > max_norm:
                return (grad * (max_norm / (norma + 1e-12))).astype(grad.dtype, copy=False), norma
            return grad, norma

    def __init__(self,
                 input_size: int = 10,
                 output_size: int = 4,
                 nombre: str = "NeuronaRefuerzoIMPALA",
                 learning_rate: float = 0.0003,
                 gamma: float = 0.99,
                 lambda_gae: float = 0.95,
                 num_actors: int = 8,
                 num_learners: int = 2,
                 batch_size: int = 32,
                 sequence_length: int = 20,
                 usar_ortogonal: bool = True,
                 entropy_coef: float = 0.01,
                 value_coef: float = 0.5,
                 max_grad_norm: float = 0.5,
                 update_frequency: int = 100,
                 semilla: int = 42):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate = float(learning_rate)
        self.gamma = float(gamma)
        self.lambda_gae = float(lambda_gae)
        self.num_actors = int(num_actors)
        self.num_learners = int(num_learners)
        self.batch_size = int(batch_size)
        self.sequence_length = int(sequence_length)
        self.usar_ortogonal = bool(usar_ortogonal)
        self.entropy_coef = float(entropy_coef)
        self.value_coef = float(value_coef)
        self.max_grad_norm = float(max_grad_norm)
        self.update_frequency = int(update_frequency)

        self.rng = np.random.default_rng(semilla)
        self.pesos_actor_global: Optional[np.ndarray] = None
        self.sesgo_actor_global: Optional[np.ndarray] = None
        self.pesos_critic_global: Optional[np.ndarray] = None
        self.sesgo_critic_global: Optional[np.ndarray] = None

        self.pesos_actor_locales: Dict[int, np.ndarray] = {}
        self.sesgo_actor_locales: Dict[int, np.ndarray] = {}
        self.pesos_critic_locales: Dict[int, np.ndarray] = {}
        self.sesgo_critic_locales: Dict[int, np.ndarray] = {}

        self.pesos_lock = threading.Lock()

        # Clase anidada: Buffer multicanal para actores
        self.buffer = self.BufferActoresIMPALA(num_actors=self.num_actors, capacidad_actor=1000)

        self.historial_actor_loss: List[float] = []
        self.historial_critic_loss: List[float] = []
        self.historial_entropy_loss: List[float] = []
        self.historial_importance_weights: List[float] = []
        self.historial_sincronizaciones: List[float] = []

        self.estadisticas_impala: Dict[str, Any] = {
            'actor_loss_medio': 0.0,
            'critic_loss_medio': 0.0,
            'entropy_loss_medio': 0.0,
            'total_loss_medio': 0.0,
            'importance_weights_medio': 1.0,
            'importance_weights_std': 0.0,
            'convergencia_actor': 0.0,
            'convergencia_critic': 0.0,
            'estabilidad_actor': 0.0,
            'estabilidad_critic': 0.0,
            'sincronizaciones': 0,
            'updates_globales': 0,
            'muestras_totales': 0,
            'gradiente_norma_actor': 0.0,
            'gradiente_norma_critic': 0.0,
            'actors_activos': self.num_actors,
            'learners_activos': self.num_learners,
        }

        self.inicializar_pesos()
        logger.info(f"NeuronaRefuerzoIMPALA creada y configurada con exito: {self}")

    @property
    def buffer_experiencias(self) -> Dict[int, deque]:
        return self.buffer._canales

    @property
    def buffer_prioridades(self) -> Dict[int, deque]:
        return self.buffer._prioridades

    def inicializar_pesos(self) -> None:
        """Inicializa los pesos globales y crea copias locales para cada worker/actor."""
        init_fn = inicializar_pesos_ortogonal if self.usar_ortogonal else inicializar_pesos_xavier
        shp_a = (self.input_size, self.output_size)
        shp_c = (self.input_size, 1)

        self.pesos_actor_global = init_fn(shp_a)
        self.pesos_critic_global = init_fn(shp_c)
        self.sesgo_actor_global = np.zeros((1, self.output_size), dtype=_dt())
        self.sesgo_critic_global = np.zeros((1, 1), dtype=_dt())

        for aid in range(self.num_actors):
            self.pesos_actor_locales[aid] = self.pesos_actor_global.copy()
            self.sesgo_actor_locales[aid] = self.sesgo_actor_global.copy()
            self.pesos_critic_locales[aid] = self.pesos_critic_global.copy()
            self.sesgo_critic_locales[aid] = self.sesgo_critic_global.copy()

        logger.info(f"Pesos IMPALA inicializados para {self.num_actors} actores [in={self.input_size}, out={self.output_size}]")

    def _asegurar(self) -> None:
        if self.pesos_actor_global is None or self.pesos_critic_global is None:
            self.inicializar_pesos()
        assert self.pesos_actor_global is not None and self.pesos_critic_global is not None

    def _prep(self, estado: Any) -> np.ndarray:
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimensión {x.shape[1]} != input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    def forward_actor(self, estado: np.ndarray, actor_id: int = 0) -> np.ndarray:
        """Inferencia de probabilidades de acción (usando la política local del actor o global)."""
        self._asegurar()
        wp = self.pesos_actor_locales.get(actor_id, self.pesos_actor_global)
        sb = self.sesgo_actor_locales.get(actor_id, self.sesgo_actor_global)

        x = self._prep(estado)
        logits = x @ wp + sb
        logits_safe = logits - np.max(logits, axis=1, keepdims=True)
        e = np.exp(np.clip(logits_safe, -30.0, 30.0))
        probs = e / np.maximum(np.sum(e, axis=1, keepdims=True), 1e-12)
        return np.ascontiguousarray(probs, dtype=_dt())

    def forward_critic(self, estado: np.ndarray, actor_id: int = 0) -> np.ndarray:
        """Inferencia del valor escalar V(s) con la red crítica local o global."""
        self._asegurar()
        wp = self.pesos_critic_locales.get(actor_id, self.pesos_critic_global)
        sb = self.sesgo_critic_locales.get(actor_id, self.sesgo_critic_global)
        return (self._prep(estado) @ wp + sb).astype(_dt(), copy=False)

    def forward(self, estado: np.ndarray, actor_id: int = 0) -> Tuple[np.ndarray, np.ndarray]:
        return self.forward_actor(estado, actor_id), self.forward_critic(estado, actor_id)

    def forward_batch(self, estados: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        self._asegurar()
        xs = np.concatenate([self._prep(s) for s in estados], axis=0)
        logits = xs @ self.pesos_actor_global + self.sesgo_actor_global
        e = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = e / np.maximum(np.sum(e, axis=1, keepdims=True), 1e-12)
        vals = xs @ self.pesos_critic_global + self.sesgo_critic_global
        return np.ascontiguousarray(probs, dtype=_dt()), np.ascontiguousarray(vals, dtype=_dt())

    def forward_q(self, estado: Any, accion: Any = None,
                  usar_objetivo: bool = False, q_network: int = 1) -> np.ndarray:
        return self.forward_critic(estado, 0)

    def seleccionar_accion(self, estado: np.ndarray, actor_id: int = 0) -> Tuple[int, float, float]:
        """El actor selecciona una acción estocástica según su política local."""
        probs, val = self.forward(estado, actor_id)
        p = probs[0].copy()
        p = np.maximum(p, 0.0)
        p /= np.sum(p)
        accion = int(self.rng.choice(self.output_size, p=p))
        return accion, float(probs[0, accion]), float(val[0, 0])

    def agregar_experiencia(self, actor_id: int, estado: Any, accion: int, recompensa: float,
                            siguiente_estado: Any, terminado: bool, probabilidad_accion: float) -> None:
        """Agrega experiencia recolectada por un actor específico."""
        self.buffer.agregar(actor_id, estado, accion, recompensa, siguiente_estado, terminado, probabilidad_accion)
        self.estadisticas_impala['muestras_totales'] = self.buffer.total_muestras()

    def calcular_gae_advantages(self, recompensas: List[float], valores: List[float]) -> np.ndarray:
        rews = np.array(recompensas, dtype=np.float64)
        vals = np.array(valores, dtype=np.float64)
        n = len(rews)
        advantages = np.zeros(n, dtype=np.float64)
        adv = 0.0
        for t in range(n - 1, -1, -1):
            nv = 0.0 if t == n - 1 else vals[t + 1]
            delta = rews[t] + self.gamma * nv - vals[t]
            adv = delta + self.gamma * self.lambda_gae * adv
            advantages[t] = adv
        return advantages

    def calcular_importance_weights(self, experiencias: List[Dict[str, Any]], actor_id: int) -> np.ndarray:
        estados = np.array([e['estado'] for e in experiencias], dtype=_dt())
        acciones = np.array([e['accion'] for e in experiencias], dtype=int)
        p_ant = np.array([e['probabilidad_accion'] for e in experiencias], dtype=np.float64)

        # Política actual del Learner (global)
        p_act = self.forward_actor(estados, actor_id=-1)[np.arange(len(experiencias)), acciones]
        iw = np.clip(p_act / np.maximum(p_ant, 1e-8), 0.01, 10.0)

        if len(iw):
            self.estadisticas_impala['importance_weights_medio'] = float(np.mean(iw))
            self.estadisticas_impala['importance_weights_std'] = float(np.std(iw))
            self.historial_importance_weights.extend(iw.tolist())
        return iw

    def calcular_gradientes_impala(self, experiencias: List[Dict[str, Any]], actor_id: int) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ]:
        """Calcula gradientes usando la formulación analítica de V-trace."""
        self._asegurar()
        n = len(experiencias)
        estados = np.array([e['estado'] for e in experiencias], dtype=_dt()).reshape(-1, self.input_size)
        acciones = np.array([e['accion'] for e in experiencias], dtype=int)
        recompensas = np.array([e['recompensa'] for e in experiencias], dtype=np.float32)
        terminados = np.array([e['terminado'] for e in experiencias], dtype=bool)
        prob_actor = np.array([e['probabilidad_accion'] for e in experiencias], dtype=np.float32)

        # Inferencia con pesos globales del Learner
        probs_learner_all = self.forward_actor(estados, actor_id=-1)
        prob_learner = probs_learner_all[np.arange(n), acciones]
        valores_learner = self.forward_critic(estados, actor_id=-1)[:, 0]

        # V-trace
        vs, ventajas, is_ratios = self.MotorCalculoVTrace.calcular_vtrace(
            recompensas=recompensas,
            valores=valores_learner,
            terminados=terminados,
            probabilidades_learner=prob_learner,
            probabilidades_actor=prob_actor,
            gamma=self.gamma,
            rho_bar=1.0,
            c_bar=1.0,
        )

        error_critic = vs - valores_learner

        # Gradientes del Actor: grad log pi(a|s) * ventaja_vtrace
        grad_acc = np.zeros_like(probs_learner_all)
        grad_acc[np.arange(n), acciones] = 1.0 / np.maximum(probs_learner_all[np.arange(n), acciones], 1e-8)
        grad_actor_sample = grad_acc * ventajas.reshape(-1, 1)

        gw_a = estados.T @ grad_actor_sample / n
        gs_a = np.mean(grad_actor_sample, axis=0, keepdims=True)

        # Gradientes del Critic: -error_critic * grad V
        gw_c = estados.T @ (-error_critic.reshape(-1, 1)) / n
        gs_c = np.mean(-error_critic.reshape(-1, 1), axis=0, keepdims=True)

        actor_loss = float(-np.mean(np.log(prob_learner + 1e-8) * ventajas))
        critic_loss = float(0.5 * np.mean(error_critic ** 2))
        entropy = float(-np.mean(np.sum(probs_learner_all * np.log(probs_learner_all + 1e-8), axis=1)))

        self.estadisticas_impala['actor_loss_medio'] = actor_loss
        self.estadisticas_impala['critic_loss_medio'] = critic_loss
        self.estadisticas_impala['entropy_loss_medio'] = entropy
        self.estadisticas_impala['total_loss_medio'] = actor_loss + self.value_coef * critic_loss - self.entropy_coef * entropy

        # Recorte L2
        gw_a, na = self.MotorCalculoVTrace.clipping_l2(gw_a, self.max_grad_norm)
        gw_c, nc = self.MotorCalculoVTrace.clipping_l2(gw_c, self.max_grad_norm)

        self.estadisticas_impala['gradiente_norma_actor'] = na
        self.estadisticas_impala['gradiente_norma_critic'] = nc

        return gw_a.astype(_dt()), gs_a.astype(_dt()), gw_c.astype(_dt()), gs_c.astype(_dt())

    def actualizar_pesos_learner(self, gwa: np.ndarray, gsa: np.ndarray,
                                 gwc: np.ndarray, gsc: np.ndarray) -> None:
        """Aplica gradientes a los parámetros globales del Learner central."""
        self._asegurar()
        with self.pesos_lock:
            lr = self.learning_rate
            self.pesos_actor_global -= lr * gwa
            self.sesgo_actor_global -= lr * gsa
            self.pesos_critic_global -= lr * gwc
            self.sesgo_critic_global -= lr * gsc
            self.estadisticas_impala['updates_globales'] += 1

    def sincronizar_actores(self) -> None:
        """Transfiere los pesos actualizados del Learner a todos los Actores locales."""
        self._asegurar()
        with self.pesos_lock:
            for aid in range(self.num_actors):
                self.pesos_actor_locales[aid] = self.pesos_actor_global.copy()
                self.sesgo_actor_locales[aid] = self.sesgo_actor_global.copy()
                self.pesos_critic_locales[aid] = self.pesos_critic_global.copy()
                self.sesgo_critic_locales[aid] = self.sesgo_critic_global.copy()
            self.estadisticas_impala['sincronizaciones'] += 1
            self.historial_sincronizaciones.append(time.time())

    def entrenar_step(self, actor_id: int = 0) -> Optional[Dict[str, float]]:
        """Paso de entrenamiento sobre las muestras de un actor."""
        exp = self.buffer.muestrear(actor_id, self.batch_size, rng=self.rng)
        if exp is None:
            return None

        gwa, gsa, gwc, gsc = self.calcular_gradientes_impala(exp, actor_id)
        self.actualizar_pesos_learner(gwa, gsa, gwc, gsc)

        if self.estadisticas_impala['updates_globales'] % self.update_frequency == 0:
            self.sincronizar_actores()

        self.historial_actor_loss.append(self.estadisticas_impala['actor_loss_medio'])
        self.historial_critic_loss.append(self.estadisticas_impala['critic_loss_medio'])
        self.historial_entropy_loss.append(self.estadisticas_impala['entropy_loss_medio'])

        return {
            'actor_loss': self.estadisticas_impala['actor_loss_medio'],
            'critic_loss': self.estadisticas_impala['critic_loss_medio'],
            'entropy_loss': self.estadisticas_impala['entropy_loss_medio'],
            'total_loss': self.estadisticas_impala['total_loss_medio'],
            'importance_weights_medio': self.estadisticas_impala['importance_weights_medio'],
            'sincronizaciones': self.estadisticas_impala['sincronizaciones'],
        }

    def calcular_loss(self, experiencias: List[Dict[str, Any]], actor_id: int = 0) -> Dict[str, float]:
        self.calcular_gradientes_impala(experiencias, actor_id)
        return {
            'actor_loss': self.estadisticas_impala['actor_loss_medio'],
            'critic_loss': self.estadisticas_impala['critic_loss_medio'],
            'entropy_loss': self.estadisticas_impala['entropy_loss_medio'],
            'total_loss': self.estadisticas_impala['total_loss_medio'],
        }

    def calcular_entropy(self, estado: np.ndarray, actor_id: int = 0) -> float:
        probs = self.forward_actor(estado, actor_id)
        return float(-np.sum(probs * np.log(probs + 1e-8)))

    def calcular_explained_variance(self, experiencias: List[Dict[str, Any]], actor_id: int = 0) -> float:
        preds = np.array([self.forward_critic(e['estado'], actor_id)[0, 0] for e in experiencias])
        rets = np.array([e['recompensa'] for e in experiencias], dtype=np.float64)
        var = float(np.var(rets))
        resid = float(np.var(rets - preds))
        return float(1.0 - resid / max(1e-12, var))

    def verificar_integridad(self) -> Dict[str, Any]:
        checks = {
            'pesos_actor_global_init': self.pesos_actor_global is not None,
            'pesos_critic_global_init': self.pesos_critic_global is not None,
            'num_actores_configurados': len(self.pesos_actor_locales),
            'muestras_totales_buffer': self.buffer.total_muestras(),
            'sincronizaciones': self.estadisticas_impala['sincronizaciones'],
        }
        if self.pesos_actor_global is not None:
            checks['sin_nan_actor'] = not bool(np.any(np.isnan(self.pesos_actor_global)))
            checks['sin_inf_actor'] = not bool(np.any(np.isinf(self.pesos_actor_global)))
            checks['peso_actor_max'] = float(np.max(np.abs(self.pesos_actor_global)))
        return checks

    def verificar_estabilidad(self) -> Dict[str, bool]:
        est: Dict[str, bool] = {}
        al = self.estadisticas_impala['actor_loss_medio']
        cl = self.estadisticas_impala['critic_loss_medio']
        est['actor_loss_estable'] = abs(al) < 100.0
        est['critic_loss_estable'] = cl < 100.0

        iw = self.estadisticas_impala['importance_weights_medio']
        est['importance_weights_estables'] = 0.05 <= iw <= 20.0
        est['buffer_suficiente'] = self.buffer.total_muestras() >= self.batch_size

        if self.pesos_actor_global is not None:
            est['pesos_actor_no_explosivos'] = bool(np.max(np.abs(self.pesos_actor_global)) < 10.0)
        else:
            est['pesos_actor_no_explosivos'] = True

        return est

    def limpiar_historiales(self) -> None:
        self.historial_actor_loss.clear()
        self.historial_critic_loss.clear()
        self.historial_entropy_loss.clear()
        self.historial_importance_weights.clear()
        self.historial_sincronizaciones.clear()

    def guardar(self, ruta: str) -> None:
        import json
        d = {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'pesos_actor_global': self.pesos_actor_global.tolist() if self.pesos_actor_global is not None else None,
            'pesos_critic_global': self.pesos_critic_global.tolist() if self.pesos_critic_global is not None else None,
            'sesgo_actor_global': self.sesgo_actor_global.tolist() if self.sesgo_actor_global is not None else None,
            'sesgo_critic_global': self.sesgo_critic_global.tolist() if self.sesgo_critic_global is not None else None,
            'num_actors': self.num_actors,
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
        }
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2)

    def cargar(self, ruta: str) -> None:
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.inicializar_pesos()
        if d.get('pesos_actor_global') is not None:
            self.pesos_actor_global = np.asarray(d['pesos_actor_global'], dtype=_dt())
        if d.get('pesos_critic_global') is not None:
            self.pesos_critic_global = np.asarray(d['pesos_critic_global'], dtype=_dt())
        if d.get('sesgo_actor_global') is not None:
            self.sesgo_actor_global = np.asarray(d['sesgo_actor_global'], dtype=_dt())
        if d.get('sesgo_critic_global') is not None:
            self.sesgo_critic_global = np.asarray(d['sesgo_critic_global'], dtype=_dt())
        self.sincronizar_actores()

    def obtener_estadisticas_impala(self) -> Dict[str, Any]:
        if self.pesos_actor_global is None:
            return {'estado': 'no_inicializada'}

        return {
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'lambda_gae': self.lambda_gae,
            'num_actors': self.num_actors,
            'batch_size': self.batch_size,
            'muestras_totales': self.buffer.total_muestras(),
            'actor_loss_medio': self.estadisticas_impala['actor_loss_medio'],
            'critic_loss_medio': self.estadisticas_impala['critic_loss_medio'],
            'entropy_loss_medio': self.estadisticas_impala['entropy_loss_medio'],
            'total_loss_medio': self.estadisticas_impala['total_loss_medio'],
            'importance_weights_medio': self.estadisticas_impala['importance_weights_medio'],
            'importance_weights_std': self.estadisticas_impala['importance_weights_std'],
            'sincronizaciones': self.estadisticas_impala['sincronizaciones'],
            'updates_globales': self.estadisticas_impala['updates_globales'],
            'gradiente_norma_actor': self.estadisticas_impala['gradiente_norma_actor'],
            'gradiente_norma_critic': self.estadisticas_impala['gradiente_norma_critic'],
        }

    def reinicializar_con_parametros(self, learning_rate: Optional[float] = None,
                                     gamma: Optional[float] = None,
                                     num_actors: Optional[int] = None) -> None:
        if learning_rate is not None:
            self.learning_rate = float(learning_rate)
        if gamma is not None:
            self.gamma = float(gamma)
        if num_actors is not None:
            self.num_actors = int(num_actors)

        self.inicializar_pesos()
        self.resetear_historial()
        self.buffer.limpiar()
        self.limpiar_historiales()
        self.estadisticas_impala['sincronizaciones'] = 0
        self.estadisticas_impala['updates_globales'] = 0
        logger.info(f"Neurona IMPALA reinicializada: lr={self.learning_rate}, actors={self.num_actors}")

    def __str__(self) -> str:
        return (f"NeuronaRefuerzoIMPALA(entrada={self.input_size}, salida={self.output_size}, "
                f"lr={self.learning_rate}, actors={self.num_actors}, buffer={self.buffer.total_muestras()})")

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["NeuronaRefuerzoIMPALA"]
