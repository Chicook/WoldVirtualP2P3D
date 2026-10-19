"""_rfen_base.py - Base compartida e inicializadores para el paquete RF_EN.

Centraliza:
- LUCIA_RL_CONFIG
- _dt
- NeuronaRefuerzoBase
- InicializadoresRL y funciones inicializar_pesos_*
- _Ring buffer
"""
import math
import logging
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

LUCIA_RL_CONFIG = {
    'precision': 'float32',
    'random_seed': 42,
    'default_learning_rate': 0.001,
}

_DTYPE = {'float32': np.float32, 'float64': np.float64}


def _dt() -> np.dtype:
    return np.dtype(_DTYPE.get(LUCIA_RL_CONFIG.get('precision', 'float32'), np.float32))


class NeuronaRefuerzoBase:
    """Clase base para neuronas de aprendizaje por refuerzo."""

    def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaRefuerzo"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos = None
        self.sesgo = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[Any] = []
        self.pasos: int = 0

    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, e: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def resetear_historial(self) -> None:
        self.historial_activaciones = []
        self.historial_gradientes = []

    def info(self) -> str:
        return f"{self.nombre}(in={self.input_size},out={self.output_size},pasos={self.pasos})"

    def params_count(self) -> int:
        total = 0
        if self.pesos is not None:
            total += self.pesos.size
        if self.sesgo is not None:
            total += self.sesgo.size
        return total

    def add_historial_activacion(self, activacion: np.ndarray) -> None:
        self.historial_activaciones.append(activacion.copy())

    def add_historial_gradiente(self, gradiente: Dict[str, np.ndarray]) -> None:
        self.historial_gradientes.append({k: v.copy() for k, v in gradiente.items()})


class InicializadoresRL:
    """Inicializadores eficientes de pesos (he, xavier, lecun, ortogonal, espectral)."""

    @staticmethod
    def _rng(seed: int = 42) -> np.random.Generator:
        return np.random.default_rng(seed)

    @classmethod
    def he(cls, shape, fan_in: int = 1, seed: int = 42) -> np.ndarray:
        return cls._rng(seed).normal(0.0, math.sqrt(2.0 / max(1, fan_in)), shape).astype(LUCIA_RL_CONFIG['precision'])

    @classmethod
    def xavier(cls, shape, fan_in: int = 1, fan_out: int = 1, seed: int = 42) -> np.ndarray:
        lim = math.sqrt(6.0 / max(1, fan_in + fan_out))
        return cls._rng(seed).uniform(-lim, lim, shape).astype(LUCIA_RL_CONFIG['precision'])

    @classmethod
    def lecun(cls, shape, fan_in: int = 1, seed: int = 42) -> np.ndarray:
        return cls._rng(seed).normal(0.0, math.sqrt(1.0 / max(1, fan_in)), shape).astype(LUCIA_RL_CONFIG['precision'])

    @classmethod
    def ortogonal(cls, shape, seed: int = 42, ganancia: float = 1.0) -> np.ndarray:
        a = cls._rng(seed).normal(0, 1, shape)
        q, _ = np.linalg.qr(a) if shape[0] >= shape[1] else np.linalg.qr(a.T)
        q = q if shape[0] >= shape[1] else q.T
        return (q[:, :shape[1]] * ganancia).astype(LUCIA_RL_CONFIG['precision'])

    @classmethod
    def espectral(cls, shape, seed: int = 42) -> np.ndarray:
        w = cls._rng(seed).normal(0, 1, shape)
        s = np.linalg.svd(w, compute_uv=False)
        return (w / max(1e-12, s[0])).astype(LUCIA_RL_CONFIG['precision'])


def inicializar_pesos_he(shape, fan_in: int = 1, seed: int = 42) -> np.ndarray:
    return InicializadoresRL.he(shape, fan_in, seed)


def inicializar_pesos_xavier(shape, fan_in: int = 1, fan_out: int = 1, seed: int = 42) -> np.ndarray:
    return InicializadoresRL.xavier(shape, fan_in, fan_out, seed)


def inicializar_pesos_lecun(shape, fan_in: int = 1, seed: int = 42) -> np.ndarray:
    return InicializadoresRL.lecun(shape, fan_in, seed)


def inicializar_pesos_ortogonal(shape, seed: int = 42, ganancia: float = 1.0) -> np.ndarray:
    return InicializadoresRL.ortogonal(shape, seed, ganancia)


def inicializar_pesos_espectral(shape, seed: int = 42) -> np.ndarray:
    return InicializadoresRL.espectral(shape, seed)


class _Ring:
    """Ring buffer acotado en memoria."""

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
