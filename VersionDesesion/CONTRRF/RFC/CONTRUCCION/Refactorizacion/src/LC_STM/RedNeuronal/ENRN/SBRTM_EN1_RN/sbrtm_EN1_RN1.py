"""Módulo autocontenido de neuronas de entrada (SBRTM_EN1_RN).

Unifica la base abstracta y la neurona concreta bajo NeuronaEntradaBase,
con la neurona densa anidada como NeuronaEntradaBase.Basica y su alias
de módulo NeuronaEntradaBasica.
"""

import time

import numpy as np
from typing import Any, Callable, Dict, List, Optional

LUCIA_CONFIG = {
    "precision": "float32",
    "random_seed": 42,
    "default_learning_rate": 0.001,
}

_DTYPE_MAP = {"float32": np.float32, "float64": np.float64, "float16": np.float16}


def _dtype() -> np.dtype:
    return np.dtype(_DTYPE_MAP.get(LUCIA_CONFIG.get("precision", "float32"), np.float32))


def _now() -> float:
    return time.perf_counter()


class NeuronaEntradaBase:
    """Base autocontenida (fallback sin ciclo de import).

    Contiene el buffer de historiales y la neurona densa concreta Basica.
    """

    class RingBuffer:
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

    def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaEntrada"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
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


class _Basica(NeuronaEntradaBase):
    """Neurona de entrada densa con init He, Adam/SGD, clipping y metricas.

    Mantiene API original: inicializar_pesos, forward, backward,
    obtener_estadisticas_completas, verificar_estabilidad, __str__.
    """

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaBasica",
                 factor_escala: float = 1.0,
                 learning_rate: float = 0.001,
                 optimizador: str = "adam",
                 beta1: float = 0.9,
                 beta2: float = 0.999,
                 epsilon: float = 1e-8,
                 weight_decay: float = 0.0,
                 grad_clip: float = 5.0,
                 lr_decay: float = 0.0,
                 lr_min: float = 1e-6,
                 usar_cache_forward: bool = True,
                 normalizar_entrada: bool = False,
                 semilla: Optional[int] = None,
                 capacidad_historial: int = 256):
        super().__init__(input_size, output_size, nombre)
        self.factor_escala = float(factor_escala)
        self.varianza_esperada = 0.0
        self.varianza_real = 0.0
        # Hiperparametros eficientes
        self.lr_base = float(learning_rate or LUCIA_CONFIG.get("default_learning_rate", 0.001))
        self.lr_actual = float(self.lr_base)
        self.optimizador = str(optimizador).lower()
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.weight_decay = float(weight_decay)
        self.grad_clip = float(grad_clip)
        self.lr_decay = float(lr_decay)
        self.lr_min = float(lr_min)
        self.usar_cache_forward = bool(usar_cache_forward)
        self.normalizar_entrada = bool(normalizar_entrada)
        self.semilla = semilla if semilla is not None else int(LUCIA_CONFIG.get("random_seed", 42))
        self.rng = np.random.default_rng(self.semilla)
        # Estado Adam
        self._m_pesos: Optional[np.ndarray] = None
        self._v_pesos: Optional[np.ndarray] = None
        self._m_sesgo: Optional[np.ndarray] = None
        self._v_sesgo: Optional[np.ndarray] = None
        self._paso = 0
        # Cache y estadisticas de rendimiento
        self._cache_entrada: Optional[np.ndarray] = None
        self._cache_salida: Optional[np.ndarray] = None
        self._media_entrada: Optional[np.ndarray] = None
        self._std_entrada: Optional[np.ndarray] = None
        self.historial_activaciones = self.RingBuffer(capacidad_historial)
        self.historial_gradientes = self.RingBuffer(capacidad_historial)
        self.historial_loss: List[float] = []
        self.historial_lr: List[float] = []
        self.historial_tiempo: List[float] = []
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss: float = float("inf")
        self.callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    def _emit(self, evento: str, info: Optional[Dict[str, Any]] = None) -> None:
        for cb in self.callbacks:
            try:
                cb(evento, info or {})
            except Exception:
                continue

    def registrar_callback(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        self.callbacks.append(fn)

    def _asegurar_estado_adam(self) -> None:
        if self._m_pesos is None:
            self._m_pesos = np.zeros_like(self.pesos, dtype=np.float64)
            self._v_pesos = np.zeros_like(self.pesos, dtype=np.float64)
            self._m_sesgo = np.zeros_like(self.sesgo, dtype=np.float64)
            self._v_sesgo = np.zeros_like(self.sesgo, dtype=np.float64)

    def _aplicar_decaimiento_lr(self) -> None:
        if self.lr_decay > 0.0:
            self.lr_actual = max(self.lr_min, self.lr_base / (1.0 + self.lr_decay * self._paso))
        self.historial_lr.append(self.lr_actual)

    def _clip(self, g: np.ndarray) -> np.ndarray:
        if self.grad_clip and self.grad_clip > 0:
            n = float(np.linalg.norm(g))
            if n > self.grad_clip:
                g = g * (self.grad_clip / (n + 1e-12))
        return g

    def _preparar_entrada(self, entrada: np.ndarray) -> np.ndarray:
        x = np.asarray(entrada, dtype=_dtype())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"entrada dim {x.shape[1]} != input_size {self.input_size}")
        if self.normalizar_entrada:
            mu = x.mean(axis=0, keepdims=True)
            sd = x.std(axis=0, keepdims=True) + 1e-8
            self._media_entrada = mu.astype(_dtype())
            self._std_entrada = sd.astype(_dtype())
            x = ((x - mu) / sd).astype(_dtype(), copy=False)
        x = np.ascontiguousarray(x, dtype=_dtype())
        return x

    # ------------------------------------------------------------------
    # API de entrenamiento/inferencia
    # ------------------------------------------------------------------
    def inicializar_pesos(self) -> None:
        fan_in = max(1, self.input_size)
        std = float(np.sqrt(2.0 / fan_in))
        self.pesos = self.rng.normal(0.0, std, (self.output_size, self.input_size)).astype(_dtype())
        self.sesgo = np.zeros((self.output_size,), dtype=_dtype())
        self.varianza_esperada = 2.0 / fan_in
        self._m_pesos = None
        self._v_pesos = None
        self._m_sesgo = None
        self._v_sesgo = None
        self._paso = 0
        self._cache_entrada = None
        self._cache_salida = None

    def forward(self, entrada):
        x = self._preparar_entrada(entrada)
        if self.pesos is None or self.sesgo is None:
            self.inicializar_pesos()
        inicio = _now()
        if self.usar_cache_forward:
            self._cache_entrada = x
        a = x @ self.pesos.T * self.factor_escala + self.sesgo
        a = a.astype(_dtype(), copy=False)
        self._cache_salida = a
        self.varianza_real = float(np.var(a))
        self.historial_activaciones.append(a)
        self.contador_forward += 1
        self.tiempo_forward_acum += _now() - inicio
        self._emit("forward", {"forma": tuple(a.shape)})
        return a

    def backward(self, g, e):
        inicio = _now()
        if self.pesos is None or self.sesgo is None:
            self.inicializar_pesos()
        g = np.asarray(g, dtype=_dtype())
        if g.ndim == 1:
            g = g.reshape(1, -1)
        x = self._cache_entrada
        if x is None:
            x = self._preparar_entrada(e)
        grad_pesos = g.T @ x
        grad_sesgo = g.sum(axis=0)
        grad_entrada = (g @ self.pesos) * self.factor_escala
        self._actualizar(grad_pesos, grad_sesgo)
        self.historial_gradientes.append(grad_entrada)
        self.contador_backward += 1
        self.tiempo_backward_acum += _now() - inicio
        self._emit("backward", {"forma": tuple(grad_entrada.shape)})
        return grad_entrada

    def _actualizar(self, grad_pesos: np.ndarray, grad_sesgo: np.ndarray) -> None:
        self._aplicar_decaimiento_lr()
        if self.weight_decay:
            grad_pesos = grad_pesos + self.weight_decay * self.pesos
        grad_pesos = self._clip(grad_pesos)
        grad_sesgo = self._clip(grad_sesgo)
        self._paso += 1
        if self.optimizador == "adam":
            self._asegurar_estado_adam()
            m_p, v_p = self._m_pesos, self._v_pesos
            m_b, v_b = self._m_sesgo, self._v_sesgo
            m_p[:] = self.beta1 * m_p + (1.0 - self.beta1) * grad_pesos
            v_p[:] = self.beta2 * v_p + (1.0 - self.beta2) * (grad_pesos ** 2)
            m_b[:] = self.beta1 * m_b + (1.0 - self.beta1) * grad_sesgo
            v_b[:] = self.beta2 * v_b + (1.0 - self.beta2) * (grad_sesgo ** 2)
            t = self._paso
            m_p_hat = m_p / (1.0 - self.beta1 ** t)
            v_p_hat = v_p / (1.0 - self.beta2 ** t)
            m_b_hat = m_b / (1.0 - self.beta1 ** t)
            v_b_hat = v_b / (1.0 - self.beta2 ** t)
            self.pesos = self.pesos - self.lr_actual * m_p_hat / (np.sqrt(v_p_hat) + self.epsilon)
            self.sesgo = self.sesgo - self.lr_actual * m_b_hat / (np.sqrt(v_b_hat) + self.epsilon)
        else:
            self.pesos = self.pesos - self.lr_actual * grad_pesos
            self.sesgo = self.sesgo - self.lr_actual * grad_sesgo
        self.pesos = self.pesos.astype(_dtype())
        self.sesgo = self.sesgo.astype(_dtype())

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------
    def obtener_estadisticas(self):
        stats = super().obtener_estadisticas()
        stats.update({
            "forward": self.contador_forward,
            "backward": self.contador_backward,
            "lr_actual": self.lr_actual,
            "mejor_loss": self.mejor_loss,
            "varianza_real": self.varianza_real,
            "varianza_esperada": self.varianza_esperada,
        })
        return stats

    def verificar_estabilidad(self):
        stats = super().verificar_estabilidad()
        if self.pesos is not None:
            stats["pesos_finitos"] = bool(np.all(np.isfinite(self.pesos)))
        return stats


# La neurona concreta queda anidada en la base (sin redefinir la herencia
# dentro del cuerpo de la clase, lo que provocaria NameError).
NeuronaEntradaBase.Basica = _Basica
NeuronaEntradaBasica = _Basica

__all__ = ["NeuronaEntradaBase", "NeuronaEntradaBasica", "LUCIA_CONFIG"]