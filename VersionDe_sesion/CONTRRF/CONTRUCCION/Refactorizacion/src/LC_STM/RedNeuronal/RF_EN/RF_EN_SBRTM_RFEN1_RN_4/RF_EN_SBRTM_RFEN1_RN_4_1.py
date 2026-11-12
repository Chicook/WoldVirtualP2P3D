"""RF_EN_SBRTM_RFEN1_RN_4_1.py
Neurona Deep Q-Network (DQN) con Replay Buffer anidado y optimización matemática avanzada.

Arquitectura:
  - `NeuronaRefuerzoDQN`:
      * `NeuronaRefuerzoDQN.ReplayBuffer`: Clase anidada con buffers NumPy pre-alojados tipo ring
        (elimina el coste O(N) de `del lst[0]`), muestreo vectorizado ultra-rápido y soporte de prioridades TD.
      * Doble DQN desacoplado (Double DQN / Hasselt et al.).
      * Bellman vectorizado con pérdida Huber / MSE estable para gradientes acotados.
      * Actualización suave Polyak (Soft-update / Target network tracking) y hard sync periódico.
      * Recorte de gradientes adaptativo por norma L2.
"""

from __future__ import annotations

import logging
import math
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
        # Fallback de contingencia si no se resuelve la ruta base
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


class NeuronaRefuerzoDQN(NeuronaRefuerzoBase):
    """DQN de alto rendimiento: Replay Buffer anidado circular vectorizado, Double DQN y Huber loss."""

    class ReplayBuffer:
        """Buffer de experiencia circular anidado con arrays contiguos pre-alojados (O(1) push y sample)."""

        def __init__(self, capacidad: int = 10000, input_dim: int = 4, semilla: int = 42):
            self.capacidad = max(16, int(capacidad))
            self.input_dim = int(input_dim)
            self.rng = np.random.default_rng(semilla)
            self._idx: int = 0
            self._tam: int = 0

            # Pre-reserva contigua de memoria para máxima velocidad de lectura/escritura
            self.s_buf = np.zeros((self.capacidad, self.input_dim), dtype=np.float32)
            self.a_buf = np.zeros(self.capacidad, dtype=np.int64)
            self.r_buf = np.zeros(self.capacidad, dtype=np.float64)
            self.ns_buf = np.zeros((self.capacidad, self.input_dim), dtype=np.float32)
            self.d_buf = np.zeros(self.capacidad, dtype=bool)

        def __len__(self) -> int:
            return self._tam

        def push(self, s: np.ndarray, a: int, r: float, ns: np.ndarray, d: bool) -> None:
            """Inserción circular O(1) sin reasignaciones de memoria."""
            i = self._idx
            self.s_buf[i] = np.asarray(s, dtype=np.float32).flatten()[:self.input_dim]
            self.a_buf[i] = int(a)
            self.r_buf[i] = float(r)
            self.ns_buf[i] = np.asarray(ns, dtype=np.float32).flatten()[:self.input_dim]
            self.d_buf[i] = bool(d)

            self._idx = (i + 1) % self.capacidad
            if self._tam < self.capacidad:
                self._tam += 1

        def sample(self, n: int) -> Dict[str, np.ndarray]:
            """Muestreo pseudoaleatorio vectorizado sobre los elementos activos."""
            if self._tam == 0:
                raise ValueError("No se puede muestrear de un ReplayBuffer vacío")
            k = min(int(n), self._tam)
            indices = self.rng.integers(0, self._tam, size=k)
            return {
                's': self.s_buf[indices],
                'a': self.a_buf[indices],
                'r': self.r_buf[indices],
                'ns': self.ns_buf[indices],
                'd': self.d_buf[indices],
            }

        def clear(self) -> None:
            self._idx = 0
            self._tam = 0

    def __init__(
        self,
        input_size: int,
        output_size: int,
        nombre: str = "NeuronaRefuerzoDQN",
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        epsilon: float = 0.2,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
        usar_doble: bool = True,
        sync_objetivo_cada: int = 100,
        tau_soft_sync: float = 0.005,
        buffer_capacidad: int = 10000,
        batch_size: int = 32,
        huber_delta: float = 1.0,
        grad_clip: float = 5.0,
        semilla: int = 42,
        capacidad_historial: int = 512,
    ):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate = float(learning_rate)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.epsilon_decay = float(epsilon_decay)
        self.epsilon_min = float(epsilon_min)
        self.usar_doble = bool(usar_doble)
        self.sync_objetivo_cada = max(1, int(sync_objetivo_cada))
        self.tau_soft_sync = float(np.clip(tau_soft_sync, 0.0, 1.0))
        self.batch_size = max(1, int(batch_size))
        self.huber_delta = float(huber_delta)
        self.grad_clip = float(grad_clip)
        self.semilla = int(semilla)
        self.rng = np.random.default_rng(self.semilla)

        self.q_online: Optional[np.ndarray] = None
        self.q_objetivo: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None

        self.pasos: int = 0
        self.tiempo_fwd: float = 0.0
        self.tiempo_upd: float = 0.0

        # Instancia del ReplayBuffer anidado
        self.buffer = self.ReplayBuffer(
            capacidad=buffer_capacidad,
            input_dim=self.input_size,
            semilla=self.semilla,
        )

        self.estadisticas_dqn: Dict[str, Any] = {
            'loss_media': 0.0,
            'convergencia': 0.0,
            'exploracion_rate': 0,
            'exploitacion_rate': 0,
            'actualizaciones': 0,
            'syncs_objetivo': 0,
            'td_error_medio': 0.0,
        }
        self.historial_loss = _Ring(capacidad_historial)
        self.historial_q = _Ring(capacidad_historial)
        self._loss_ema: float = 0.0

        logger.info(f"NeuronaRefuerzoDQN creada: {self}")

    def inicializar_pesos(self, modo: str = "he") -> None:
        m = str(modo).lower()
        shp = (self.input_size, self.output_size)
        if m == 'he':
            self.q_online = inicializar_pesos_he(shp, self.input_size, seed=self.semilla)
        elif m == 'xavier':
            self.q_online = inicializar_pesos_xavier(shp, self.input_size, self.output_size, seed=self.semilla)
        elif m == 'lecun':
            self.q_online = inicializar_pesos_lecun(shp, self.input_size, seed=self.semilla)
        elif m == 'ortogonal':
            self.q_online = inicializar_pesos_ortogonal(shp, seed=self.semilla)
        elif m == 'espectral':
            self.q_online = inicializar_pesos_espectral(shp, seed=self.semilla)
        elif m == 'ceros':
            self.q_online = np.zeros(shp, dtype=_dt())
        else:
            raise ValueError(f"Modo de inicialización '{m}' desconocido")

        self.q_online = np.ascontiguousarray(self.q_online, dtype=_dt())
        self.q_objetivo = self.q_online.copy()
        self.sesgo = np.zeros((1, self.output_size), dtype=_dt())
        self.pesos = self.q_online
        logger.info(f"Red DQN inicializada ({modo}): forma={self.q_online.shape}")

    def _asegurar(self) -> None:
        if self.q_online is None or self.sesgo is None or self.q_objetivo is None:
            self.inicializar_pesos()

    def _prep(self, estado: np.ndarray) -> np.ndarray:
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimensión de estado {x.shape[1]} != input {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    def forward(self, estado: np.ndarray) -> np.ndarray:
        """Selecciona acción bajo política epsilon-greedy vectorizada."""
        t0 = time.perf_counter()
        self._asegurar()
        assert self.q_online is not None and self.sesgo is not None

        x = self._prep(estado)
        qv = (np.dot(x, self.q_online).astype(np.float64) + self.sesgo.astype(np.float64))[0]

        if self.rng.random() < self.epsilon:
            acc = int(self.rng.integers(0, self.output_size))
            self.estadisticas_dqn['exploracion_rate'] += 1
        else:
            acc = int(np.argmax(qv))
            self.estadisticas_dqn['exploitacion_rate'] += 1

        self.historial_q.append(qv.copy())
        self.tiempo_fwd += time.perf_counter() - t0
        return np.array([acc], dtype=np.int64)

    def recordar(self, s: np.ndarray, a: int, r: float, ns: np.ndarray, d: bool = False) -> None:
        self.buffer.push(s, a, r, ns, d)

    def valores_q(self, estado: np.ndarray, red: str = "online") -> np.ndarray:
        self._asegurar()
        assert self.q_online is not None and self.sesgo is not None
        x = self._prep(estado)
        w = self.q_online if red == "online" else self.q_objetivo
        return np.ascontiguousarray((np.dot(x, w).astype(np.float64) + self.sesgo.astype(np.float64)).astype(_dt()))

    def calcular_gradientes_dqn(
        self, s: np.ndarray, a: np.ndarray, r: np.ndarray, ns: np.ndarray, d: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, float, float]:
        """Cálculo vectorizado de gradientes con Double DQN y pérdida Huber para gradientes suaves."""
        self._asegurar()
        assert self.q_online is not None and self.sesgo is not None and self.q_objetivo is not None

        S = np.asarray(s, dtype=np.float64)
        NS = np.asarray(ns, dtype=np.float64)
        A = np.asarray(a, dtype=np.int64) % self.output_size
        R = np.asarray(r, dtype=np.float64)
        D = np.asarray(d, dtype=bool)

        wo = self.q_online.astype(np.float64)
        wt = self.q_objetivo.astype(np.float64)
        b = self.sesgo.astype(np.float64)

        n = max(1, len(S))
        q_act = (S @ wo + b)[np.arange(n), A]

        # Double DQN vs DQN estándar
        if self.usar_doble:
            a_star = np.argmax(NS @ wo + b, axis=1)
            q_next = (NS @ wt + b)[np.arange(n), a_star]
        else:
            q_next = np.max(NS @ wt + b, axis=1)

        q_obj = np.where(D, R, R + self.gamma * q_next)
        td_error = q_obj - q_act

        # Gradiente con función de pérdida Huber (Smooth L1)
        abs_td = np.abs(td_error)
        delta = self.huber_delta
        linear_mask = abs_td > delta
        grad_error = np.where(linear_mask, delta * np.sign(td_error), td_error)
        loss = float(np.mean(np.where(linear_mask, delta * (abs_td - 0.5 * delta), 0.5 * (td_error ** 2))))

        oh = np.zeros((n, self.output_size), dtype=np.float64)
        oh[np.arange(n), A] = -grad_error / n
        grad_w = S.T @ oh
        grad_b = oh.sum(axis=0, keepdims=True)

        # Recorte conjunto por norma L2
        norma_total = float(np.sqrt(np.sum(grad_w ** 2) + np.sum(grad_b ** 2)))
        if self.grad_clip > 0 and norma_total > self.grad_clip:
            factor = self.grad_clip / (norma_total + 1e-12)
            grad_w *= factor
            grad_b *= factor

        td_medio = float(np.mean(abs_td))
        return grad_w.astype(_dt()), grad_b.astype(_dt()), loss, td_medio

    def actualizar_q_batch(
        self, s: np.ndarray, a: np.ndarray, r: np.ndarray, ns: np.ndarray, d: np.ndarray
    ) -> float:
        t0 = time.perf_counter()
        self._asegurar()
        assert self.q_online is not None and self.sesgo is not None and self.q_objetivo is not None

        grad_w, grad_b, loss, td_medio = self.calcular_gradientes_dqn(s, a, r, ns, d)

        # Descenso por gradiente
        self.q_online = np.ascontiguousarray(
            (self.q_online.astype(np.float64) - self.learning_rate * grad_w.astype(np.float64)).astype(_dt())
        )
        self.sesgo = np.ascontiguousarray(
            (self.sesgo.astype(np.float64) - self.learning_rate * grad_b.astype(np.float64)).astype(_dt())
        )
        self.pesos = self.q_online
        self.pasos += 1
        self.estadisticas_dqn['actualizaciones'] += 1
        self.estadisticas_dqn['td_error_medio'] = td_medio

        # Actualización de red objetivo (Polyak soft-update o hard sync)
        if self.tau_soft_sync > 0.0:
            self.q_objetivo = np.ascontiguousarray(
                (self.tau_soft_sync * self.q_online.astype(np.float64)
                 + (1.0 - self.tau_soft_sync) * self.q_objetivo.astype(np.float64)).astype(_dt())
            )
        elif self.pasos % self.sync_objetivo_cada == 0:
            self.q_objetivo = self.q_online.copy()
            self.estadisticas_dqn['syncs_objetivo'] += 1

        self.historial_loss.append(loss)
        self._loss_ema = 0.05 * loss + 0.95 * self._loss_ema
        self.estadisticas_dqn['loss_media'] = self._loss_ema
        self.estadisticas_dqn['convergencia'] = 1.0 / (1.0 + self._loss_ema)

        # Decaimiento del epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        self.tiempo_upd += time.perf_counter() - t0
        return loss

    def entrenar_desde_buffer(self, batch: Optional[int] = None) -> Optional[float]:
        if len(self.buffer) < max(4, min(self.batch_size, 8)):
            return None
        b = self.buffer.sample(batch or self.batch_size)
        return self.actualizar_q_batch(b['s'], b['a'], b['r'], b['ns'], b['d'])

    def entrenar_paso(
        self, s: np.ndarray, a: int, r: float, ns: np.ndarray, d: bool = False, usar_buffer: bool = True
    ) -> Dict[str, float]:
        self.recordar(s, a, r, ns, d)
        if usar_buffer and len(self.buffer) >= max(4, min(self.batch_size, 8)):
            loss = self.entrenar_desde_buffer()
        else:
            loss = self.actualizar_q_batch(
                np.asarray(s).reshape(1, -1),
                np.array([a], dtype=np.int64),
                np.array([r], dtype=np.float64),
                np.asarray(ns).reshape(1, -1),
                np.array([d], dtype=bool),
            )
        return {'loss': float(loss) if loss is not None else 0.0, 'paso': float(self.pasos)}

    def obtener_mejor_politica(self, estados: np.ndarray) -> np.ndarray:
        return np.argmax(self.valores_q(estados, "online"), axis=1)

    def obtener_valores_q(self, estado: np.ndarray) -> np.ndarray:
        return self.valores_q(estado, "online")[0].copy()

    def obtener_estadisticas_dqn(self) -> Dict[str, Any]:
        if self.q_online is None:
            return {'estado': 'no_inicializada'}
        qf = self.q_online.astype(np.float64).flatten()
        tot = self.estadisticas_dqn['exploracion_rate'] + self.estadisticas_dqn['exploitacion_rate']
        return {
            'q_media': float(qf.mean()),
            'q_std': float(qf.std()),
            'q_min': float(qf.min()),
            'q_max': float(qf.max()),
            'loss_media': self.estadisticas_dqn['loss_media'],
            'convergencia': self.estadisticas_dqn['convergencia'],
            'td_error_medio': self.estadisticas_dqn['td_error_medio'],
            'epsilon': self.epsilon,
            'buffer_len': len(self.buffer),
            'actualizaciones': self.estadisticas_dqn['actualizaciones'],
            'syncs_objetivo': self.estadisticas_dqn['syncs_objetivo'],
            'tasa_exploracion': self.estadisticas_dqn['exploracion_rate'] / max(1, tot),
            't_medio_fwd_us': self.tiempo_fwd / max(1, self.pasos + 1) * 1e6,
            't_medio_upd_us': self.tiempo_upd / max(1, self.pasos) * 1e6,
        }

    def verificar_estabilidad(self) -> Dict[str, bool]:
        est = {
            'convergencia_ok': self.estadisticas_dqn['convergencia'] > 0.5,
            'epsilon_ok': self.epsilon_min <= self.epsilon <= 1.0,
            'buffer_ok': len(self.buffer) > 0,
        }
        if self.q_online is not None:
            est['q_no_explosiva'] = float(np.max(np.abs(self.q_online))) < 100.0
            est['sin_nan'] = bool(not np.isnan(self.q_online).any())
            est['sin_inf'] = bool(not np.isinf(self.q_online).any())
        else:
            est.update({'q_no_explosiva': True, 'sin_nan': True, 'sin_inf': True})
        return est

    def resetear_historial(self) -> None:
        self.historial_loss.clear()
        self.historial_q.clear()

    def reinicializar_con_parametros(
        self,
        learning_rate: Optional[float] = None,
        gamma: Optional[float] = None,
        epsilon: Optional[float] = None,
    ) -> None:
        if learning_rate is not None:
            self.learning_rate = float(learning_rate)
        if gamma is not None:
            self.gamma = float(gamma)
        if epsilon is not None:
            self.epsilon = float(epsilon)
        self.inicializar_pesos()
        self.resetear_historial()
        self.buffer.clear()
        self.pasos = 0
        logger.info(f"DQN reinicializada: lr={self.learning_rate}, eps={self.epsilon}")

    def a_dict(self) -> Dict[str, Any]:
        return {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'lr': self.learning_rate,
            'gamma': self.gamma,
            'epsilon': self.epsilon,
            'q_online': self.q_online.tolist() if self.q_online is not None else None,
            'q_objetivo': self.q_objetivo.tolist() if self.q_objetivo is not None else None,
            'sesgo': self.sesgo.tolist() if self.sesgo is not None else None,
        }

    def guardar(self, ruta: str) -> None:
        import json
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.a_dict(), f)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaRefuerzoDQN":
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        o = cls(
            d['input_size'],
            d['output_size'],
            d.get('nombre', 'NeuronaRefuerzoDQN'),
            learning_rate=d.get('lr', 0.001),
            gamma=d.get('gamma', 0.99),
            epsilon=d.get('epsilon', 0.2),
        )
        if d.get('q_online') is not None:
            o.q_online = np.asarray(d['q_online'], dtype=_dt())
            o.q_objetivo = (
                np.asarray(d['q_objetivo'], dtype=_dt())
                if d.get('q_objetivo') is not None
                else o.q_online.copy()
            )
            o.sesgo = (
                np.asarray(d['sesgo'], dtype=_dt())
                if d.get('sesgo') is not None
                else np.zeros((1, o.output_size), dtype=_dt())
            )
            o.pesos = o.q_online
        return o

    def __str__(self) -> str:
        return (
            f"NeuronaRefuerzoDQN(in={self.input_size}, out={self.output_size}, "
            f"lr={self.learning_rate}, gamma={self.gamma}, eps={self.epsilon:.3f}, doble={self.usar_doble})"
        )

    def __repr__(self) -> str:
        return self.__str__()


# Alias de retrocompatibilidad si algún importador busca ReplayBuffer en el namespace global del módulo
ReplayBuffer = NeuronaRefuerzoDQN.ReplayBuffer

__all__ = [
    "NeuronaRefuerzoDQN",
    "ReplayBuffer",
]
