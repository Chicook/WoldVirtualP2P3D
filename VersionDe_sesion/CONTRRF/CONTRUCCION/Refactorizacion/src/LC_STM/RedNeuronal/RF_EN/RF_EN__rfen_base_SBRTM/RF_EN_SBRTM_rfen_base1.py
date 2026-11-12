"""Base compartida de las neuronas de refuerzo (RF_EN · SBRTM).

Autocontenido: configuración, tipo de dato, clase base de neurona,
inicializadores de pesos unificados y buffer circular acotado.

Los inicializadores viven como clase anidada NeuronaRefuerzoBase.Inicializacion;
el alias de módulo InicializadoresRL y las funciones inicializar_pesos_*
conservan la API original para el resto de neuronas RF.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

LUCIA_RL_CONFIG: Dict[str, Any] = {
    "precision": "float32",
    "random_seed": 42,
    "default_learning_rate": 0.001,
}

_DTYPE_MAP = {"float16": np.float16, "float32": np.float32, "float64": np.float64}
_DTYPE = _DTYPE_MAP  # alias histórico

_METODOS_INICIALIZACION = ("he", "xavier", "lecun", "ortogonal", "espectral")


def actualizar_config(**kwargs) -> Dict[str, Any]:
    """Actualiza LUCIA_RL_CONFIG y devuelve la configuración resultante."""
    for clave, valor in kwargs.items():
        if valor is not None:
            LUCIA_RL_CONFIG[clave] = valor
    return dict(LUCIA_RL_CONFIG)


def _dt() -> np.dtype:
    return np.dtype(_DTYPE_MAP.get(str(LUCIA_RL_CONFIG.get("precision", "float32")).lower(), np.float32))


class NeuronaRefuerzoBase:
    """Clase base de las neuronas de refuerzo.

    Agrupa la inicialización reproducible de pesos (clase anidada
    Inicializacion) y el contrato común de las neuronas RF.
    """

    class Inicializacion:
        """Inicializadores de pesos eficientes y reproducibles.

        Todos devuelven el tensor convertido a la precisión configurada.
        """

        @staticmethod
        def _rng(seed: int = 42) -> np.random.Generator:
            return np.random.default_rng(seed)

        @classmethod
        def he(cls, shape, fan_in: int = 1, seed: int = 42) -> np.ndarray:
            return cls._rng(seed).normal(0.0, math.sqrt(2.0 / max(1, fan_in)), shape).astype(_dt())

        @classmethod
        def xavier(cls, shape, fan_in: int = 1, fan_out: int = 1, seed: int = 42) -> np.ndarray:
            lim = math.sqrt(6.0 / max(1, fan_in + fan_out))
            return cls._rng(seed).uniform(-lim, lim, shape).astype(_dt())

        @classmethod
        def lecun(cls, shape, fan_in: int = 1, seed: int = 42) -> np.ndarray:
            return cls._rng(seed).normal(0.0, math.sqrt(1.0 / max(1, fan_in)), shape).astype(_dt())

        @classmethod
        def ortogonal(cls, shape, seed: int = 42, ganancia: float = 1.0) -> np.ndarray:
            a = cls._rng(seed).normal(0, 1, shape)
            if shape[0] >= shape[1]:
                q, _ = np.linalg.qr(a)
            else:
                q, _ = np.linalg.qr(a.T)
                q = q.T
            return (q[:, :shape[1]] * ganancia).astype(_dt())

        @classmethod
        def espectral(cls, shape, seed: int = 42) -> np.ndarray:
            w = cls._rng(seed).normal(0, 1, shape)
            s = np.linalg.svd(w, compute_uv=False)
            return (w / max(1e-12, s[0])).astype(_dt())

        @classmethod
        def crear(cls, metodo: str = "he", shape=None, fan_in: int = 1,
                  fan_out: int = 1, seed: int = 42,
                  ganancia: float = 1.0) -> np.ndarray:
            """Despacha al inicializador pedido (he si el nombre no existe)."""
            nombre = str(metodo).lower()
            if nombre == "xavier":
                return cls.xavier(shape, fan_in, fan_out, seed)
            if nombre == "lecun":
                return cls.lecun(shape, fan_in, seed)
            if nombre == "ortogonal":
                return cls.ortogonal(shape, seed, ganancia)
            if nombre == "espectral":
                return cls.espectral(shape, seed)
            return cls.he(shape, fan_in, seed)

        @classmethod
        def disponibles(cls) -> Tuple[str, ...]:
            return _METODOS_INICIALIZACION

    def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaRefuerzo"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[Any] = []
        self.pasos: int = 0

    # ------------------------------------------------------------------
    # Contrato de la neurona
    # ------------------------------------------------------------------
    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, e: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def inicializar_pesos_con(self, metodo: str = "he",
                              seed: Optional[int] = None) -> None:
        """Atajo de la base: inicializa pesos y sesgo con el método indicado."""
        s = int(LUCIA_RL_CONFIG.get("random_seed", 42)) if seed is None else int(seed)
        fan_in = max(1, self.input_size)
        self.pesos = self.Inicializacion.crear(
            metodo, (self.output_size, self.input_size),
            fan_in=fan_in, fan_out=self.output_size, seed=s)
        self.sesgo = np.zeros((self.output_size,), dtype=_dt())
        self.pasos = 0

    # ------------------------------------------------------------------
    # Historiales e introspección
    # ------------------------------------------------------------------
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

    def __repr__(self) -> str:
        return self.info()


# Alias de compatibilidad: la clase anidada como inicializador de módulo.
InicializadoresRL = NeuronaRefuerzoBase.Inicializacion


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


def inicializar_pesos_eficiente(shape, metodo: str = "he", fan_in: int = 1,
                                fan_out: int = 1, seed: int = 42,
                                ganancia: float = 1.0) -> np.ndarray:
    return InicializadoresRL.crear(metodo, shape, fan_in, fan_out, seed, ganancia)


class _Ring:
    """Ring buffer acotado en memoria para historiales."""

    def __init__(self, cap: int = 512):
        self.cap = int(cap)
        self._d: List[Any] = []

    def append(self, x: Any) -> None:
        self._d.append(x)
        if len(self._d) > self.cap:
            del self._d[0:len(self._d) - self.cap]

    def tail(self, n: int) -> List[Any]:
        return self._d[-n:]

    def to_list(self) -> List[Any]:
        return list(self._d)

    def clear(self) -> None:
        self._d.clear()

    def __len__(self) -> int:
        return len(self._d)

    def __getitem__(self, i: int) -> Any:
        return self._d[i]

    def __iter__(self):
        return iter(self._d)

    def __repr__(self) -> str:
        return f"_Ring(cap={self.cap}, len={len(self._d)})"

    @property
    def full(self) -> bool:
        return len(self._d) == self.cap


__all__ = [
    "LUCIA_RL_CONFIG",
    "actualizar_config",
    "NeuronaRefuerzoBase",
    "InicializadoresRL",
    "inicializar_pesos_he",
    "inicializar_pesos_xavier",
    "inicializar_pesos_lecun",
    "inicializar_pesos_ortogonal",
    "inicializar_pesos_espectral",
    "inicializar_pesos_eficiente",
    "_Ring",
    "_dt",
    "_DTYPE",
]
