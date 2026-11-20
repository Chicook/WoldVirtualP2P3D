"""RFEN1_RN_1.py - Neurona de Refuerzo con Q-Learning (refactor eficiente).

La implementación (Bellman vectorizado y SubrutinaQ) vive en
RF_EN_SBRTM_RFEN1_RN_1; este módulo reexporta la neurona y añade política
explícita, persistencia JSON y utilidades de comparación.
"""
import json
import logging
from typing import Any, Dict

import numpy as np

from ._rfen_base import (
    LUCIA_RL_CONFIG,
    _dt,
    NeuronaRefuerzoBase,
    InicializadoresRL,
    inicializar_pesos_he,
    inicializar_pesos_xavier,
    inicializar_pesos_lecun,
    inicializar_pesos_ortogonal,
    inicializar_pesos_espectral,
    _Ring,
)
from .RF_EN_SBRTM_RFEN1_RN_1 import (
    NeuronaRefuerzoQLearning as _NeuronaRefuerzoQLearning,
)

logger = logging.getLogger('RFENRN1.RFEN1_RN_1')


class NeuronaRefuerzoQLearning(_NeuronaRefuerzoQLearning):
    """Q-Learning con política explícita, persistencia JSON y resumen."""

    def obtener_mejor_politica(self) -> np.ndarray:
        if self.q_table is None:
            raise ValueError("Tabla Q no inicializada")
        return np.argmax(self.q_table, axis=1)

    def obtener_valores_q(self, estado: int) -> np.ndarray:
        if self.q_table is None:
            raise ValueError("Tabla Q no inicializada")
        return self.q_table[int(estado) % self.input_size].copy()

    def resumen_rendimiento(self) -> Dict[str, Any]:
        return {'pasos': self.pasos, 't_fwd_s': self.tiempo_fwd, 't_upd_s': self.tiempo_upd,
                't_medio_fwd_us': self.tiempo_fwd / max(1, self.pasos) * 1e6,
                't_medio_upd_us': self.tiempo_upd / max(1, self.pasos) * 1e6,
                'actualizaciones': self.estadisticas_qlearning['actualizaciones_q']}

    def a_dict(self) -> Dict[str, Any]:
        return {'input_size': self.input_size, 'output_size': self.output_size, 'nombre': self.nombre,
                'learning_rate': self.learning_rate, 'gamma': self.gamma, 'epsilon': self.epsilon,
                'epsilon_decay': self.epsilon_decay, 'epsilon_min': self.epsilon_min,
                'q_table': self.q_table.tolist() if self.q_table is not None else None}

    def guardar(self, ruta: str) -> None:
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.a_dict(), f)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaRefuerzoQLearning":
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        o = cls(d['input_size'], d['output_size'], d.get('nombre', 'NeuronaRefuerzoQLearning'),
                learning_rate=d.get('learning_rate', 0.1), gamma=d.get('gamma', 0.99),
                epsilon=d.get('epsilon', 0.1))
        if d.get('q_table') is not None:
            o.q_table = np.asarray(d['q_table'], dtype=_dt())
            o.q_objetivo = o.q_table.copy()
            o.pesos = o.q_table
        return o

    def __str__(self) -> str:
        return (f"NeuronaRefuerzoQLearning(entrada={self.input_size}, salida={self.output_size}, "
                f"lr={self.learning_rate}, gamma={self.gamma}, epsilon={self.epsilon:.3f})")

    def __repr__(self) -> str:
        return self.__str__()


def crear_neurona_qlearning(input_size: int, output_size: int,
                            configuracion: Dict[str, Any] = None) -> NeuronaRefuerzoQLearning:
    configuracion = configuracion or {}
    return NeuronaRefuerzoQLearning(
        input_size=input_size, output_size=output_size,
        nombre=configuracion.get('nombre', 'NeuronaRefuerzoQLearning'),
        learning_rate=configuracion.get('learning_rate', 0.1),
        gamma=configuracion.get('gamma', 0.99),
        epsilon=configuracion.get('epsilon', 0.1),
        epsilon_decay=configuracion.get('epsilon_decay', 0.995),
        epsilon_min=configuracion.get('epsilon_min', 0.01),
        usar_xavier=configuracion.get('usar_xavier', True),
        usar_doble_q=configuracion.get('usar_doble_q', False))


def analizar_convergencia_qlearning(neurona: NeuronaRefuerzoQLearning) -> Dict[str, Any]:
    return {'convergencia_q': neurona.estadisticas_qlearning['convergencia_q'],
            'estabilidad_q': neurona.calcular_estabilidad_q(),
            'epsilon_actual': neurona.epsilon,
            'actualizaciones_q': neurona.estadisticas_qlearning['actualizaciones_q'],
            'convergencia_detectada': neurona.estadisticas_qlearning['convergencia_detectada'],
            'estadisticas_q': neurona.obtener_estadisticas_q(),
            'estabilidad_verificada': neurona.verificar_estabilidad()}


def comparar_inicializaciones_qlearning(input_size: int, output_size: int,
                                        episodios: int = 1000) -> Dict[str, Any]:
    nx = NeuronaRefuerzoQLearning(input_size, output_size, usar_xavier=True)
    nc = NeuronaRefuerzoQLearning(input_size, output_size, usar_xavier=False)
    rng = np.random.default_rng(0)
    sx = rng.integers(0, input_size, episodios)
    ax = np.array([nx.forward(np.array([s]))[0] for s in sx])
    rx = rng.random(episodios)
    nsx = rng.integers(0, input_size, episodios)
    nx.actualizar_q_batch(sx, ax, rx, nsx, np.zeros(episodios, dtype=bool))
    sc = rng.integers(0, input_size, episodios)
    ac = np.array([nc.forward(np.array([s]))[0] for s in sc])
    rc = rng.random(episodios)
    nsc = rng.integers(0, input_size, episodios)
    nc.actualizar_q_batch(sc, ac, rc, nsc, np.zeros(episodios, dtype=bool))
    out = {}
    for k, n in (('xavier', nx), ('ceros', nc)):
        out[k] = {'convergencia_q': n.estadisticas_qlearning['convergencia_q'],
                  'estabilidad_q': n.calcular_estabilidad_q(),
                  'q_values_media': float(np.mean(n.q_table)), 'q_values_std': float(np.std(n.q_table)),
                  'actualizaciones_q': n.estadisticas_qlearning['actualizaciones_q']}
    out['ratios'] = {'convergencia_q': out['xavier']['convergencia_q'] / max(1e-12, out['ceros']['convergencia_q']),
                     'estabilidad_q': out['xavier']['estabilidad_q'] / max(1e-12, out['ceros']['estabilidad_q'])}
    return out


RFEN1_CONFIG = {'inicializacion_preferida': 'xavier', 'learning_rate_default': 0.1,
                'gamma_default': 0.99, 'epsilon_default': 0.1, 'epsilon_decay_default': 0.995,
                'epsilon_min_default': 0.01, 'umbral_convergencia': 0.95, 'umbral_estabilidad': 0.7}


__all__ = [
    "LUCIA_RL_CONFIG",
    "RFEN1_CONFIG",
    "NeuronaRefuerzoBase",
    "InicializadoresRL",
    "NeuronaRefuerzoQLearning",
    "crear_neurona_qlearning",
    "analizar_convergencia_qlearning",
    "comparar_inicializaciones_qlearning",
]

logger.info("RFEN1_RN_1.py cargado correctamente - Neurona de Refuerzo Q-Learning")
