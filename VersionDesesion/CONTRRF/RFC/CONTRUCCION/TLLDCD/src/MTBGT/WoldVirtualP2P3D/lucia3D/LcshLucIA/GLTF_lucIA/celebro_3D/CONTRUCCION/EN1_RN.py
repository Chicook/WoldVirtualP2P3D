import numpy as np
import math
import time
import json
from typing import Tuple, Optional, Dict, Any, List, Callable


try:
    from . import NeuronaEntradaBase, LUCIA_CONFIG
except ImportError:
    import numpy as np  # noqa: F401
    from typing import Tuple, Dict, Any

    LUCIA_CONFIG = {
        "precision": "float32",
        "random_seed": 42,
        "default_learning_rate": 0.001,
    }

    class NeuronaEntradaBase:
        """Base autocontenida (fallback sin ciclo de import)."""

        def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaEntrada"):
            self.input_size = input_size
            self.output_size = output_size
            self.nombre = nombre
            self.pesos = None
            self.sesgo = None
            self.historial_activaciones = []
            self.historial_gradientes = []
            self.llm_connector = None

        def inicializar_pesos(self) -> None:
            raise NotImplementedError

        def forward(self, entrada):
            raise NotImplementedError

        def backward(self, g, e):
            raise NotImplementedError

        def obtener_estadisticas(self):
            return {"nombre": self.nombre, "input_size": self.input_size,
                    "output_size": self.output_size,
                    "activaciones": len(self.historial_activaciones)}

        def obtener_estadisticas_completas(self):
            return self.obtener_estadisticas()

        def verificar_estabilidad(self):
            return {"pesos_inicializados": self.pesos is not None}

        def __str__(self) -> str:
            return f"{self.nombre}(entrada={self.input_size}, salida={self.output_size})"


_DTYPE_MAP = {"float32": np.float32, "float64": np.float64, "float16": np.float16}


def _dtype() -> np.dtype:
    return np.dtype(_DTYPE_MAP.get(LUCIA_CONFIG.get("precision", "float32"), np.float32))


def _now() -> float:
    return time.perf_counter()


def update(self, gradiente_pesos: np.ndarray, gradiente_sesgo: np.ndarray) -> None:
    t0 = _now()
    self._aplicar_decaimiento_lr()
    if self.pesos is None:
        self.inicializar_pesos()
    g_pesos = np.asarray(gradiente_pesos, dtype=_dtype())
    g_sesgo = np.asarray(gradiente_sesgo, dtype=_dtype())
    # Momento
    if self._m_pesos is None:
        self._m_pesos = g_pesos
        self._m_sesgo = g_sesgo
    else:
        self._m_pesos = self.momento * self._m_pesos + (1 - self.momento) * g_pesos
        self._m_sesgo = self.momento * self._m_sesgo + (1 - self.momento) * g_sesgo
    # Actualización
    self.pesos -= self.learning_rate * self._m_pesos
    self.sesgo -= self.learning_rate * self._m_sesgo
    self.historial_gradientes.append(g_pesos)
    self.historial_activaciones.append(self.forward(self.sesgo))
    self.llm_connector.actualizar_pesos(self.pesos)
    self.llm_connector.actualizar_sesgo(self.sesgo)
    self.llm_connector.actualizar_historial_gradientes(self.historial_gradientes)
    self.llm_connector.actualizar_historial_activaciones(self.historial_activaciones)
    self.llm_connector.actualizar_estadisticas(self.obtener_estadisticas())
    self.llm_connector.actualizar_estadisticas_completas(self.obtener_estadisticas_completas())
    self.llm_connector.actualizar_estabilidad(self.verificar_estabilidad())
    self.llm_connector.actualizar_tiempo(t0)


def _aplicar_decaimiento_lr(self):
    self.learning_rate *= self.decaimiento_lr


def _inicializar_pesos(self):
    self.pesos = np.random.rand(self.input_size, self.output_size) * 2 - 1


def _inicializar_sesgo(self):
    self.sesgo = np.zeros((self.input_size, self.output_size))


def _inicializar_momento(self):
    self.momento = 0.9


def _inicializar_decaimiento_lr(self):
    self.decaimiento_lr = 0.999


def _inicializar_llm_connector(self):
    self.llm_connector = LLMConnector(self)


class LLMConnector:
    def __init__(self, neurona_entrada: NeuronaEntradaBase):
        self.neurona_entrada = neurona_entrada
        self.pesos = None
        self.sesgo = None
        self.historial_gradientes = None
        self.historial_activaciones = None
        self.estadisticas = None
        self.estadisticas_completas = None
        self.estabilidad = None
        self.tiempo = None

    def actualizar_pesos(self, pesos: np.ndarray):
        self.pesos = pesos

    def actualizar_sesgo(self, sesgo: np.ndarray):
        self.sesgo = sesgo

    def actualizar_historial_gradientes(self, historial_gradientes: List[np.ndarray]):
        self.historial_gradientes = historial_gradientes

    def actualizar_historial_activaciones(self, historial_activaciones: List[np.ndarray]):
        self.historial_activaciones = historial_activaciones

    def actualizar_estadisticas(self, estadisticas: Dict[str, Any]):
        self.estadisticas = estadisticas

    def actualizar_estadisticas_completas(self, estadisticas_completas: Dict[str, Any]):
        self.estadisticas_completas = estadisticas_completas

    def actualizar_estabilidad(self, estabilidad: Dict[str, Any]):
        self.estabilidad = estabilidad

    def actualizar_tiempo(self, tiempo: float):
        self.tiempo = tiempo


NEURONA_ENTRADA_BASE_INPUT_SIZE = 10


NEURONA_ENTRADA_BASE_OUTPUT_SIZE = 10


NEURONA_ENTRADA_BASE_NOMBRE = "NeuronaEntradaBase"


NEURONA_ENTRADA_BASE_PRECISION = "float32"


NEURONA_ENTRADA_BASE_RANDOM_SEED = 42


NEURONA_ENTRADA_BASE_DEFAULT_LEARNING_RATE = 0.001


NEURONA_ENTRADA_BASE_MOMENTO = 0.9


NEURONA_ENTRADA_BASE


class _RingBuffer:
    """Buffer circular eficiente para historiales (evita crecimiento infinito)."""

    def __init__(self, capacidad: int = 256):
        self.capacidad = int(capacidad)
        self._datos: List[Any] = []

    def append(self, item: Any) -> None:
        self._datos.append(item)
        if len(self._datos) > self.capacidad:
            del self._datos[0:len(self._datos) - self.capacidad]

    def __len__(self) -> int:
        return len(self._datos)

    def to_list(self) -> List[Any]:
        return list(self._datos)

    def clear(self) -> None:
        self._datos.clear()

# --- Partes/subsistemas extraídos automáticamente ---
from EN1_RN_p2 import *  # noqa: F401,F403
