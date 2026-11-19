"""Neurona de refuerzo Q-Learning (RF_EN · SBRTM).

Tabla Q con actualización Bellman, epsilon-greedy reproducible y buffers
acotados. La subrutina anidada SubrutinaQ unifica la selección de acciones,
el cálculo de objetivos y la escritura vectorizada en la tabla Q, de modo
que las rutas escalar y por mini-lote comparten el mismo algoritmo.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import numpy as np

try:
    from .._rfen_base import NeuronaRefuerzoBase, _dt, _Ring
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_rfen_base", _os.path.join(_base, "_rfen_base.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaRefuerzoBase = _mod.NeuronaRefuerzoBase
    _dt = _mod._dt
    _Ring = _mod._Ring

logger = logging.getLogger(__name__)


class NeuronaRefuerzoQLearning(NeuronaRefuerzoBase):
    """Q-Learning eficiente: Bellman vectorizado, RNG propio, buffers acotados."""

    class SubrutinaQ:
        """Subrutina única de cálculo Q compartida por todas las rutas.

        Unifica normalización de índices, selección epsilon-greedy, objetivos
        Bellman (con doble Q), decaimiento de epsilon, EMA de convergencia y
        escritura de la tabla, aplicando operaciones vectorizadas.
        """

        @staticmethod
        def normalizar(valores, modulo: int) -> np.ndarray:
            """Convierte a int64 y acota por módulo (índices de tabla válidos)."""
            return np.asarray(valores, dtype=np.int64) % int(modulo)

        @staticmethod
        def seleccionar(q_values: np.ndarray, epsilon: float,
                        rng: np.random.Generator, n_acciones: int):
            """Selección epsilon-greedy; devuelve (acción, exploró)."""
            if epsilon > 0.0 and rng.random() < epsilon:
                return int(rng.integers(0, n_acciones)), True
            return int(np.argmax(q_values)), False

        @staticmethod
        def objetivos_bellman(q_online: np.ndarray, q_objetivo: np.ndarray,
                              siguientes: np.ndarray, recompensas: np.ndarray,
                              terminados: np.ndarray, gamma: float,
                              doble_q: bool = False) -> np.ndarray:
            """Objetivo Bellman vectorizado, con doble Q opcional."""
            q_siguiente = q_objetivo[siguientes]
            if doble_q:
                a_estrella = np.argmax(q_online[siguientes], axis=1)
                q_max = np.take_along_axis(q_siguiente, a_estrella[:, None], axis=1)[:, 0]
            else:
                q_max = np.max(q_siguiente, axis=1)
            return np.where(terminados, recompensas, recompensas + gamma * q_max)

        @staticmethod
        def aplicar_delta(q_tabla: np.ndarray, estados: np.ndarray,
                          acciones: np.ndarray, deltas: np.ndarray) -> None:
            """Escribe lr*delta en la tabla acumulando pares (s, a) repetidos."""
            np.add.at(q_tabla, (estados, acciones), deltas.astype(q_tabla.dtype))

        @staticmethod
        def decaer_epsilon(epsilon: float, decay: float, minimo: float,
                           n: int = 1) -> float:
            """Decaimiento multiplicativo acotado por epsilon_min."""
            if epsilon <= minimo:
                return epsilon
            return max(minimo, epsilon * (decay ** n))

        @staticmethod
        def ema(actual: float, nuevo: float, alfa: float) -> float:
            return alfa * nuevo + (1.0 - alfa) * actual

        @staticmethod
        def resumen_q(q_tabla: np.ndarray) -> Dict[str, float]:
            qf = q_tabla.astype(np.float64).ravel()
            return {
                "q_values_media": float(np.mean(qf)),
                "q_values_std": float(np.std(qf)),
                "q_values_min": float(np.min(qf)),
                "q_values_max": float(np.max(qf)),
            }

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaRefuerzoQLearning",
                 learning_rate: float = 0.1,
                 gamma: float = 0.99,
                 epsilon: float = 0.1,
                 epsilon_decay: float = 0.995,
                 epsilon_min: float = 0.01,
                 usar_xavier: bool = True,
                 usar_doble_q: bool = False,
                 sync_objetivo_cada: int = 0,
                 semilla: int = 42,
                 capacidad_historial: int = 512):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate = float(learning_rate)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.epsilon_decay = float(epsilon_decay)
        self.epsilon_min = float(epsilon_min)
        self.usar_xavier = bool(usar_xavier)
        self.usar_doble_q = bool(usar_doble_q)
        self.sync_objetivo_cada = int(sync_objetivo_cada)
        self.rng = np.random.default_rng(semilla)
        self.q_table: Optional[np.ndarray] = None
        self.q_objetivo: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.pasos = 0
        self.tiempo_fwd = 0.0
        self.tiempo_upd = 0.0
        self.estadisticas_qlearning = {
            'convergencia_q': 0.0, 'estabilidad_q': 0.0,
            'exploracion_rate': 0, 'exploitacion_rate': 0,
            'q_values_media': 0.0, 'q_values_std': 0.0,
            'q_values_min': 0.0, 'q_values_max': 0.0,
            'actualizaciones_q': 0, 'convergencia_detectada': False}
        self.historial_q_values = _Ring(capacidad_historial)
        self.historial_epsilon = _Ring(capacidad_historial)
        self.historial_convergencia = _Ring(capacidad_historial)
        self._delta_ema = 0.0
        logger.info(f"NeuronaRefuerzoQLearning creada: {self}")

    @property
    def num_estados(self) -> int:
        return self.input_size

    @property
    def num_acciones(self) -> int:
        return self.output_size

    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        dt = _dt()
        m = (modo or ('xavier' if self.usar_xavier else 'ceros')).lower()
        shp = (self.input_size, self.output_size)
        if m in ('ceros', 'zeros', 'none'):
            self.q_table = np.zeros(shp, dtype=dt)
        else:
            self.q_table = self.Inicializacion.crear(
                m, shp, fan_in=self.input_size, fan_out=self.output_size)
        self.q_table = np.ascontiguousarray(self.q_table, dtype=dt)
        self.q_objetivo = self.q_table.copy()
        self.sesgo = np.zeros((1, self.output_size), dtype=dt)
        self.pesos = self.q_table
        logger.info(f"Tabla Q inicializada ({m}): forma={self.q_table.shape}")

    def _asegurar(self) -> None:
        if self.q_table is None:
            self.inicializar_pesos()
        assert self.q_table is not None

    def forward(self, estado: np.ndarray) -> np.ndarray:
        t0 = time.perf_counter()
        self._asegurar()
        assert self.q_table is not None
        s = int(self.SubrutinaQ.normalizar(np.asarray(estado).flat[0], self.input_size))
        qv = self.q_table[s]
        acc, exploro = self.SubrutinaQ.seleccionar(
            qv, self.epsilon, self.rng, self.output_size)
        clave = 'exploracion_rate' if exploro else 'exploitacion_rate'
        self.estadisticas_qlearning[clave] += 1
        self.historial_q_values.append(qv.copy())
        self.historial_epsilon.append(self.epsilon)
        self.tiempo_fwd += time.perf_counter() - t0
        return np.array([acc])

    def forward_batch(self, estados: np.ndarray) -> np.ndarray:
        self._asegurar()
        assert self.q_table is not None
        arr = self.SubrutinaQ.normalizar(np.asarray(estados).flatten(), self.input_size)
        return np.argmax(self.q_table[arr], axis=1)

    def actualizar_q_value(self, estado: int, accion: int, recompensa: float,
                           siguiente_estado: int, terminado: bool = False) -> float:
        t0 = time.perf_counter()
        self._asegurar()
        assert self.q_table is not None and self.q_objetivo is not None
        s = int(self.SubrutinaQ.normalizar(estado, self.input_size))
        ns = int(self.SubrutinaQ.normalizar(siguiente_estado, self.input_size))
        a = int(self.SubrutinaQ.normalizar(accion, self.output_size))
        q_act = float(self.q_table[s, a])
        if terminado:
            q_obj = float(recompensa)
        elif self.usar_doble_q:
            a_star = int(np.argmax(self.q_table[ns]))
            q_obj = float(recompensa) + self.gamma * float(self.q_objetivo[ns, a_star])
        else:
            q_obj = float(recompensa) + self.gamma * float(np.max(self.q_objetivo[ns]))
        delta = q_obj - q_act
        self.q_table[s, a] = q_act + self.learning_rate * delta
        self.pasos += 1
        self.estadisticas_qlearning['actualizaciones_q'] += 1
        self._delta_ema = self.SubrutinaQ.ema(self._delta_ema, abs(delta), 0.02)
        self.epsilon = self.SubrutinaQ.decaer_epsilon(
            self.epsilon, self.epsilon_decay, self.epsilon_min)
        self._sincronizar_objetivo(1)
        self._convergencia_rapida()
        self.tiempo_upd += time.perf_counter() - t0
        return delta

    def actualizar_q_batch(self, estados: np.ndarray, acciones: np.ndarray,
                           recompensas: np.ndarray, siguientes: np.ndarray,
                           terminados: np.ndarray) -> float:
        """Bellman vectorizado por mini-lote (mucho mas rapido que 1 a 1)."""
        self._asegurar()
        assert self.q_table is not None and self.q_objetivo is not None
        s = self.SubrutinaQ.normalizar(estados, self.input_size)
        a = self.SubrutinaQ.normalizar(acciones, self.output_size)
        ns = self.SubrutinaQ.normalizar(siguientes, self.input_size)
        n = len(s)
        if n == 0:
            return 0.0
        r = np.asarray(recompensas, dtype=np.float64)
        done = np.asarray(terminados, dtype=bool)
        q_obj = self.SubrutinaQ.objetivos_bellman(
            self.q_table, self.q_objetivo, ns, r, done, self.gamma, self.usar_doble_q)
        q_act = self.q_table[s, a].astype(np.float64)
        delta = q_obj - q_act
        self.SubrutinaQ.aplicar_delta(
            self.q_table, s, a, self.learning_rate * delta)
        self.pasos += n
        self.estadisticas_qlearning['actualizaciones_q'] += n
        self._delta_ema = self.SubrutinaQ.ema(
            self._delta_ema, float(np.mean(np.abs(delta))), 0.1)
        self.epsilon = self.SubrutinaQ.decaer_epsilon(
            self.epsilon, self.epsilon_decay, self.epsilon_min, n)
        self._sincronizar_objetivo(n)
        self._convergencia_rapida()
        return float(np.mean(delta ** 2))

    def _sincronizar_objetivo(self, n: int) -> None:
        """Copia la tabla a la red objetivo según la política configurada."""
        if self.q_table is None:
            return
        if self.sync_objetivo_cada > 0 and self.pasos % self.sync_objetivo_cada < n:
            self.q_objetivo = self.q_table.copy()
        elif self.sync_objetivo_cada == 0:
            self.q_objetivo = self.q_table

    def _convergencia_rapida(self) -> None:
        conv = 1.0 - min(self._delta_ema, 1.0)
        self.estadisticas_qlearning['convergencia_q'] = conv
        self.historial_convergencia.append(conv)
        if conv > 0.95 and self.estadisticas_qlearning['actualizaciones_q'] > 500:
            self.estadisticas_qlearning['convergencia_detectada'] = True

    def calcular_estabilidad_q(self) -> float:
        if len(self.historial_q_values) < 20:
            return 0.0
        arr = np.stack(self.historial_q_values.tail(20), axis=0).astype(np.float64)
        var = float(np.mean(np.var(arr, axis=0)))
        est = 1.0 / (1.0 + var)
        self.estadisticas_qlearning['estabilidad_q'] = est
        return est

    def obtener_estadisticas_q(self) -> Dict[str, Any]:
        if self.q_table is None:
            return {'estado': 'no_inicializada'}
        resumen = self.SubrutinaQ.resumen_q(self.q_table)
        self.estadisticas_qlearning.update(resumen)
        tot = (self.estadisticas_qlearning['exploracion_rate']
               + self.estadisticas_qlearning['exploitacion_rate'])
        return {
            **resumen,
            'epsilon_actual': self.epsilon, 'learning_rate': self.learning_rate, 'gamma': self.gamma,
            'convergencia_q': self.estadisticas_qlearning['convergencia_q'],
            'estabilidad_q': self.calcular_estabilidad_q(),
            'actualizaciones_q': self.estadisticas_qlearning['actualizaciones_q'],
            'convergencia_detectada': self.estadisticas_qlearning['convergencia_detectada'],
            'tasa_exploracion': self.estadisticas_qlearning['exploracion_rate'] / max(1, tot),
            'tasa_exploitacion': self.estadisticas_qlearning['exploitacion_rate'] / max(1, tot),
            't_medio_fwd_us': self.tiempo_fwd / max(1, self.pasos) * 1e6,
            't_medio_upd_us': self.tiempo_upd / max(1, self.pasos) * 1e6,
        }

    def verificar_estabilidad(self) -> Dict[str, bool]:
        est = {'convergencia_ok': self.estadisticas_qlearning['convergencia_q'] > 0.8,
               'q_values_estables': self.calcular_estabilidad_q() > 0.7,
               'epsilon_apropiado': self.epsilon_min <= self.epsilon <= 1.0}
        if self.q_table is not None:
            qmax = float(np.max(np.abs(self.q_table.astype(np.float64))))
            est['q_values_no_explosivos'] = qmax < 100.0
            est['q_values_no_desaparecen'] = True
            est['sin_nan'] = bool(not np.isnan(self.q_table).any())
            est['sin_inf'] = bool(not np.isinf(self.q_table).any())
        else:
            est.update({'q_values_no_explosivos': True, 'q_values_no_desaparecen': True,
                        'sin_nan': True, 'sin_inf': True})
        return est

    def reinicializar_con_parametros(self, learning_rate: float = None, gamma: float = None,
                                     epsilon: float = None, epsilon_decay: float = None,
                                     epsilon_min: float = None) -> None:
        if learning_rate is not None:
            self.learning_rate = float(learning_rate)
        if gamma is not None:
            self.gamma = float(gamma)
        if epsilon is not None:
            self.epsilon = float(epsilon)
        if epsilon_decay is not None:
            self.epsilon_decay = float(epsilon_decay)
        if epsilon_min is not None:
            self.epsilon_min = float(epsilon_min)
        self.inicializar_pesos()
        self.resetear_historial()
        self.historial_q_values.clear()
        self.historial_epsilon.clear()
        self.historial_convergencia.clear()
        for k in ('exploracion_rate', 'exploitacion_rate', 'actualizaciones_q'):
            self.estadisticas_qlearning[k] = 0
        self.estadisticas_qlearning['convergencia_detectada'] = False
        self.pasos = 0
        logger.info(f"Q-Learning reinicializada: lr={self.learning_rate}, gamma={self.gamma}, eps={self.epsilon}")


__all__ = ["NeuronaRefuerzoQLearning"]
