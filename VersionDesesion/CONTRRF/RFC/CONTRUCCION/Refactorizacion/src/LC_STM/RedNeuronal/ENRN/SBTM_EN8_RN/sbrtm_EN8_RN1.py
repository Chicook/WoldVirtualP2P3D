"""EN8 / RN1 - Neurona de entrada con activacion ReLU y variantes.

Modulo autocontenido: solo depende de numpy. La configuracion global vive en
``LUCIA_CONFIG`` y puede ajustarse con ``actualizar_config``.

API publica preservada de la version original:
    tipo_relu, alpha, factor_escala, tasa_activacion, tasa_muerta,
    fijar_activacion, _activar, _gradiente_activacion, inicializar_pesos,
    forward, backward, grad_entrada, paso_optimizador, entrenar_paso.

Mejoras:
  - Activaciones y derivadas centralizadas en la clase anidada ``Activaciones``
    (una sola fuente para relu / leaky_relu / elu / silu / gelu_aprox).
  - Sigmoid numerico estable con clipping comun y derivadas cerradas
    (sin diferencias finitas).
  - Optimizador unificado Adam / AdamW / SGD / SGD con momento en la clase
    anidada ``Optimizador``, con weight decay acoplado o desacoplado.

Ejemplo:
    >>> neurona = NeuronaEntradaReLU(8, 4, tipo_relu="leaky_relu")
    >>> salida = neurona.forward(np.zeros((3, 8)))
    >>> gp, gb = neurona.backward(np.ones_like(salida))
"""

from __future__ import annotations

import json
import math
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaReLU",
    "_DTYPE_MAP",
    "_dtype",
    "_now",
]


# ----------------------------------------------------------------------
# Configuracion global con valores por defecto (sin ciclo de import)
# ----------------------------------------------------------------------
LUCIA_CONFIG: Dict[str, Any] = {
    "precision": "float32",
    "default_learning_rate": 0.001,
    "random_seed": 42,
    "grad_clip": 5.0,
    "capacidad_historial": 256,
}


def actualizar_config(**valores: Any) -> Dict[str, Any]:
    """Actualiza la configuracion global y devuelve una copia del resultado."""
    LUCIA_CONFIG.update(valores)
    return dict(LUCIA_CONFIG)


_DTYPE_MAP = {"float32": np.float32, "float64": np.float64, "float16": np.float16}


def _dtype() -> np.dtype:
    return np.dtype(_DTYPE_MAP.get(str(LUCIA_CONFIG.get("precision", "float32")), np.float32))


def _now() -> float:
    return time.perf_counter()


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Sigmoide numericamente estable (clip simetrico)."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


# ----------------------------------------------------------------------
# Decoradores reutilizables
# ----------------------------------------------------------------------
def _instrumentar(nombre: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mide y contabiliza una operacion; emite eventos de inicio/fin/error."""

    atributo_contador = f"contador_{nombre}"
    atributo_tiempo = f"tiempo_{nombre}_acum"

    def decorador(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def envoltura(self: Any, *args: Any, **kwargs: Any) -> Any:
            inicio = _now()
            self._emit(f"{nombre}_inicio")
            try:
                return fn(self, *args, **kwargs)
            except Exception as exc:
                self._emit(f"{nombre}_error", {"error": repr(exc)})
                raise
            finally:
                duracion = _now() - inicio
                self._emit(nombre, {"duracion": duracion})
                setattr(self, atributo_contador, getattr(self, atributo_contador, 0) + 1)
                setattr(self, atributo_tiempo,
                        getattr(self, atributo_tiempo, 0.0) + duracion)
        return envoltura

    return decorador


def _requiere_pesos(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Inicializa los pesos de forma perezosa antes de ejecutar ``fn``."""

    @wraps(fn)
    def envoltura(self: Any, *args: Any, **kwargs: Any) -> Any:
        if self.pesos is None or self.sesgo is None:
            self.inicializar_pesos()
        return fn(self, *args, **kwargs)

    return envoltura


class NeuronaEntradaBase:
    """Base autocontenida (fallback sin ciclo de import)."""

    def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaEntrada"):
        self.input_size = input_size
        self.output_size = output_size
        self.nombre = nombre
        self.pesos = None
        self.sesgo = None
        self.historial_activaciones: List[Any] = []
        self.historial_gradientes: List[Any] = []
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


class _RingBuffer:
    """Buffer circular eficiente para historiales."""

    def __init__(self, capacidad: int = 256):
        self.capacidad = max(1, int(capacidad))
        self._datos: List[Any] = []

    def append(self, item: Any) -> None:
        self._datos.append(item)
        exceso = len(self._datos) - self.capacidad
        if exceso > 0:
            del self._datos[0:exceso]

    def __len__(self) -> int:
        return len(self._datos)

    def __iter__(self):
        return iter(self._datos)

    def to_list(self) -> List[Any]:
        return list(self._datos)

    def clear(self) -> None:
        self._datos.clear()


class NeuronaEntradaReLU(NeuronaEntradaBase):
    """EN8 ReLU eficiente: relu/leaky/elu/silu/gelu vectorizados, Adam/SGD."""

    # ------------------------------------------------------------------
    class Activaciones:
        """Funcion de activacion y su derivada en una sola fuente."""

        TIPOS = ("relu", "leaky_relu", "elu", "silu", "gelu_aprox")

        def __init__(self, tipo: str = "relu", alpha: float = 0.01):
            nombre = str(tipo)
            self.tipo = nombre if nombre in self.TIPOS else "relu"
            self.alpha = float(alpha)

        def fijar(self, tipo: str, alpha: Optional[float] = None) -> None:
            if tipo not in self.TIPOS:
                raise ValueError(f"tipo {tipo} no en {self.TIPOS}")
            self.tipo = tipo
            if alpha is not None:
                self.alpha = float(alpha)

        def activar(self, x: np.ndarray) -> np.ndarray:
            x64 = np.asarray(x, dtype=np.float64)
            if self.tipo == "relu":
                return np.maximum(0.0, x64)
            if self.tipo == "leaky_relu":
                return np.where(x64 > 0.0, x64, self.alpha * x64)
            if self.tipo == "elu":
                return np.where(x64 > 0.0, x64,
                                self.alpha * (np.exp(np.clip(x64, -20.0, 20.0)) - 1.0))
            if self.tipo == "silu":
                return x64 * _sigmoid(x64)
            if self.tipo == "gelu_aprox":
                c = np.sqrt(2.0 / np.pi)
                return 0.5 * x64 * (1.0 + np.tanh(c * (x64 + 0.044715 * x64 ** 3)))
            return np.maximum(0.0, x64)

        def gradiente(self, x: np.ndarray) -> np.ndarray:
            x64 = np.asarray(x, dtype=np.float64)
            if self.tipo == "relu":
                return (x64 > 0.0).astype(np.float64)
            if self.tipo == "leaky_relu":
                return np.where(x64 > 0.0, 1.0, self.alpha)
            if self.tipo == "elu":
                return np.where(x64 > 0.0, 1.0,
                                self.alpha * np.exp(np.clip(x64, -20.0, 20.0)))
            if self.tipo == "silu":
                s = _sigmoid(x64)
                return s + x64 * s * (1.0 - s)
            if self.tipo == "gelu_aprox":
                c = np.sqrt(2.0 / np.pi)
                t = np.tanh(c * (x64 + 0.044715 * x64 ** 3))
                return (0.5 * (1.0 + t)
                        + 0.5 * x64 * (1.0 - t * t) * c * (1.0 + 3.0 * 0.044715 * x64 * x64))
            return (x64 > 0.0).astype(np.float64)

        def tasa_activa(self, salida: np.ndarray) -> float:
            salida = np.asarray(salida)
            return float(np.sum(salida > 0.0)) / max(1, salida.size)

        def __call__(self, x: np.ndarray) -> np.ndarray:
            return self.activar(x)

        def __str__(self) -> str:
            return f"Activaciones({self.tipo}, alpha={self.alpha})"

    # ------------------------------------------------------------------
    class Optimizador:
        """Adam / AdamW / SGD / SGD con momento en una sola regla."""

        ALGORITMOS = ("adam", "adamw", "sgd", "sgd_momento")

        def __init__(self, algoritmo: str = "adam",
                     beta1: float = 0.9, beta2: float = 0.999,
                     epsilon: float = 1e-8, peso_decaimiento: float = 0.0):
            nombre = str(algoritmo).lower()
            self.algoritmo = nombre if nombre in self.ALGORITMOS else "adam"
            self.beta1 = float(beta1)
            self.beta2 = float(beta2)
            self.epsilon = float(epsilon)
            self.peso_decaimiento = max(0.0, float(peso_decaimiento))
            self._estado: Dict[str, Dict[str, np.ndarray]] = {}

        def reiniciar(self) -> None:
            self._estado.clear()

        def _estado_de(self, nombre: str, parametro: np.ndarray) -> Dict[str, np.ndarray]:
            estado = self._estado.get(nombre)
            if estado is None:
                estado = {"m": np.zeros_like(parametro, dtype=np.float64),
                          "v": np.zeros_like(parametro, dtype=np.float64)}
                self._estado[nombre] = estado
            return estado

        def aplicar(self, nombre: str, parametro: np.ndarray,
                    gradiente: np.ndarray, lr: float, paso: int) -> None:
            g = np.asarray(gradiente, dtype=np.float64)
            if self.algoritmo == "sgd":
                parametro -= lr * g
                return
            estado = self._estado_de(nombre, parametro)
            if self.algoritmo == "sgd_momento":
                estado["v"] = self.beta1 * estado["v"] + (1.0 - self.beta1) * g
                parametro -= lr * estado["v"]
                return
            estado["m"] = self.beta1 * estado["m"] + (1.0 - self.beta1) * g
            estado["v"] = self.beta2 * estado["v"] + (1.0 - self.beta2) * (g * g)
            m_hat = estado["m"] / (1.0 - self.beta1 ** paso)
            v_hat = estado["v"] / (1.0 - self.beta2 ** paso)
            parametro -= lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
            if self.algoritmo == "adamw" and self.peso_decaimiento > 0.0:
                parametro -= lr * self.peso_decaimiento * parametro

        def __str__(self) -> str:
            return (f"Optimizador({self.algoritmo}, wd={self.peso_decaimiento})")

    # ------------------------------------------------------------------
    TIPOS = Activaciones.TIPOS

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaReLU",
                 tipo_relu: str = "relu",
                 alpha: float = 0.01,
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
                 semilla: Optional[int] = None,
                 capacidad_historial: int = 256):
        super().__init__(input_size, output_size, nombre)
        self.activacion = self.Activaciones(tipo_relu, alpha)
        self.factor_escala = float(factor_escala)
        self.varianza_real = 0.0
        self.varianza_esperada = 1.0
        self.tasa_activacion = 0.0
        self.tasa_muerta = 0.0
        self.lr_base = float(learning_rate or LUCIA_CONFIG.get("default_learning_rate", 0.001))
        self.lr_actual = float(self.lr_base)
        self.grad_clip = float(grad_clip)
        self.lr_decay = float(lr_decay)
        self.lr_min = float(lr_min)
        self.usar_cache_forward = bool(usar_cache_forward)
        self.semilla = semilla if semilla is not None else int(LUCIA_CONFIG.get("random_seed", 42))
        self.rng = np.random.default_rng(self.semilla)
        self.optimizador = self.Optimizador(optimizador, beta1, beta2, epsilon, weight_decay)

        self._paso = 0
        self._cache: Dict[str, Any] = {}

        capacidad = int(capacidad_historial or LUCIA_CONFIG.get("capacidad_historial", 256))
        self.norma_pesos_historial = _RingBuffer(capacidad)
        self.historial_activaciones = _RingBuffer(capacidad)
        self.historial_gradientes = _RingBuffer(capacidad)
        self.historial_loss: List[float] = []
        self.historial_lr: List[float] = []
        self.historial_tasa: List[float] = []
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self.callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Propiedades (API original expone tipo_relu/alpha directamente)
    # ------------------------------------------------------------------
    @property
    def dt(self) -> np.dtype:
        return _dtype()

    @property
    def tipo_relu(self) -> str:
        return self.activacion.tipo

    @tipo_relu.setter
    def tipo_relu(self, valor: str) -> None:
        self.activacion.fijar(str(valor))

    @property
    def alpha(self) -> float:
        return self.activacion.alpha

    @alpha.setter
    def alpha(self, valor: float) -> None:
        self.activacion.alpha = float(valor)

    @property
    def algoritmo(self) -> str:
        return self.optimizador.algoritmo

    @property
    def weight_decay(self) -> float:
        return self.optimizador.peso_decaimiento

    @weight_decay.setter
    def weight_decay(self, valor: float) -> None:
        self.optimizador.peso_decaimiento = max(0.0, float(valor))

    @property
    def beta1(self) -> float:
        return self.optimizador.beta1

    @property
    def beta2(self) -> float:
        return self.optimizador.beta2

    @property
    def epsilon(self) -> float:
        return self.optimizador.epsilon

    # ------------------------------------------------------------------
    # Callbacks / eventos
    # ------------------------------------------------------------------
    def _emit(self, evento: str, info: Optional[Dict[str, Any]] = None) -> None:
        for cb in self.callbacks:
            try:
                cb(evento, info or {})
            except Exception:
                continue

    def registrar_callback(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        self.callbacks.append(fn)

    def fijar_activacion(self, tipo: str, alpha: Optional[float] = None) -> None:
        self.activacion.fijar(tipo, alpha)

    # Compatibilidad con la API original
    def _activar(self, x: np.ndarray) -> np.ndarray:
        return self.activacion.activar(x)

    def _gradiente_activacion(self, x: np.ndarray) -> np.ndarray:
        return self.activacion.gradiente(x)

    # ------------------------------------------------------------------
    # Utilidades numericas
    # ------------------------------------------------------------------
    def _decaer_lr(self) -> None:
        if self.lr_decay > 0.0:
            self.lr_actual = max(self.lr_min, self.lr_base / (1.0 + self.lr_decay * self._paso))
        self.historial_lr.append(self.lr_actual)
        if len(self.historial_lr) > 4096:
            del self.historial_lr[:len(self.historial_lr) - 4096]

    def _clip(self, g: np.ndarray) -> np.ndarray:
        if self.grad_clip and self.grad_clip > 0:
            norma = float(np.linalg.norm(g))
            if norma > self.grad_clip:
                g = g * (self.grad_clip / (norma + 1e-12))
        return g

    def _preparar(self, entrada: np.ndarray) -> np.ndarray:
        x = np.asarray(entrada, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.ndim != 2 or x.shape[1] != self.input_size:
            raise ValueError(f"entrada dim {x.shape[-1]} != input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=np.float64)

    # ------------------------------------------------------------------
    # Parametros
    # ------------------------------------------------------------------
    def inicializar_pesos(self, modo: str = "he") -> None:
        modo = str(modo).lower()
        if modo == "he":
            std = math.sqrt(2.0 / max(1, self.input_size)) * self.factor_escala
            pesos = self.rng.normal(0.0, std, (self.input_size, self.output_size))
        elif modo == "xavier":
            lim = math.sqrt(6.0 / (self.input_size + self.output_size)) * self.factor_escala
            pesos = self.rng.uniform(-lim, lim, (self.input_size, self.output_size))
        elif modo == "lecun":
            std = math.sqrt(1.0 / max(1, self.input_size)) * self.factor_escala
            pesos = self.rng.normal(0.0, std, (self.input_size, self.output_size))
        else:
            raise ValueError(f"modo {modo} desconocido")
        self.pesos = pesos.astype(self.dt)
        self.sesgo = np.zeros(self.output_size, dtype=self.dt)
        self.varianza_real = float(np.var(self.pesos))
        self.optimizador.reiniciar()
        self._paso = 0
        self._cache = {}
        self._registrar_norma()
        self._emit("init", {"modo": modo, "activacion": self.tipo_relu})

    def _registrar_norma(self) -> None:
        if self.pesos is not None:
            self.norma_pesos_historial.append(float(np.linalg.norm(self.pesos)))

    def penalizacion(self) -> float:
        """Weight decay L2: 0.5 * wd * ||W||^2 (desacoplado en AdamW)."""
        if self.pesos is None or self.weight_decay <= 0.0:
            return 0.0
        w = self.pesos.astype(np.float64).ravel()
        return 0.5 * self.weight_decay * float(np.dot(w, w))

    # ------------------------------------------------------------------
    # Paso del optimizador
    # ------------------------------------------------------------------
    def paso_optimizador(self, grad_pesos: np.ndarray,
                         grad_sesgo: np.ndarray) -> Dict[str, float]:
        """Weight decay + clipping + paso del optimizador unificado."""
        if self.pesos is None or self.sesgo is None:
            raise RuntimeError("pesos no inicializados")

        gp = np.asarray(grad_pesos, dtype=np.float64)
        if self.weight_decay > 0.0 and self.algoritmo != "adamw":
            gp = gp + self.weight_decay * self.pesos.astype(np.float64)
        gp = self._clip(gp)
        gb = self._clip(np.asarray(grad_sesgo, dtype=np.float64))

        self._paso += 1
        self._decaer_lr()
        self.optimizador.aplicar("pesos", self.pesos, gp, self.lr_actual, self._paso)
        self.optimizador.aplicar("sesgo", self.sesgo, gb, self.lr_actual, self._paso)

        self._registrar_norma()
        info = {"lr": self.lr_actual, "paso": float(self._paso),
                "penalizacion": self.penalizacion()}
        self._emit("paso", info)
        return info

    # ------------------------------------------------------------------
    # Propagacion
    # ------------------------------------------------------------------
    @_instrumentar("forward")
    @_requiere_pesos
    def forward(self, entrada) -> np.ndarray:
        x = self._preparar(entrada)
        if self.pesos is None or self.sesgo is None:
            raise RuntimeError("pesos no inicializados")

        pre = x @ self.pesos + self.sesgo
        salida = self.activacion.activar(pre).astype(self.dt, copy=False)

        tasa = self.activacion.tasa_activa(salida)
        n = len(self.historial_activaciones)
        self.tasa_activacion = 0.9 * self.tasa_activacion + 0.1 * tasa if n else tasa
        self.tasa_muerta = 1.0 - self.tasa_activacion

        v = float(np.var(salida)) if salida.size else 0.0
        self.varianza_real = 0.9 * self.varianza_real + 0.1 * v if n else v

        self.historial_activaciones.append(salida)
        self.historial_tasa.append(self.tasa_activacion)
        if len(self.historial_tasa) > 4096:
            del self.historial_tasa[:len(self.historial_tasa) - 4096]
        if self.usar_cache_forward:
            self._cache = {"x": x, "pre": pre}
        self._emit("activacion", {"forma": salida.shape, "tasa": tasa})
        return salida

    def forward_batch(self, lote: List[np.ndarray]) -> List[np.ndarray]:
        return [self.forward(x) for x in lote]

    @_instrumentar("backward")
    @_requiere_pesos
    def backward(self, gradiente_salida: np.ndarray,
                 entrada: Optional[np.ndarray] = None
                 ) -> Tuple[np.ndarray, np.ndarray]:
        """Devuelve (grad_pesos, grad_sesgo) SIN aplicar el optimizador."""
        g = np.asarray(gradiente_salida, dtype=np.float64)
        if g.ndim == 1:
            g = g.reshape(1, -1)
        if g.ndim != 2 or g.shape[1] != self.output_size:
            raise ValueError(f"gradiente dim {g.shape[-1]} != output_size {self.output_size}")

        if entrada is not None:
            x = self._preparar(entrada)
            if self.pesos is None or self.sesgo is None:
                raise RuntimeError("pesos no inicializados")
            pre = x @ self.pesos + self.sesgo
        elif "pre" in self._cache and "x" in self._cache:
            x = self._cache["x"]
            pre = self._cache["pre"]
        else:
            raise ValueError("sin entrada ni cache forward")

        g = g * self.activacion.gradiente(pre)
        g = self._clip(g)
        b = max(1, x.shape[0])
        gp = self._clip(x.T @ g / b)
        gb = self._clip(np.sum(g, axis=0) / b)

        self.historial_gradientes.append({
            "pesos": gp.astype(self.dt).copy(),
            "sesgo": gb.astype(self.dt).copy(),
            "norma_pesos": float(np.linalg.norm(gp)),
            "norma_sesgo": float(np.linalg.norm(gb)),
        })
        return gp.astype(self.dt), gb.astype(self.dt)

    @_requiere_pesos
    def grad_entrada(self, gradiente_salida: np.ndarray) -> np.ndarray:
        g = np.asarray(gradiente_salida, dtype=np.float64)
        if g.ndim == 1:
            g = g.reshape(1, -1)
        pre = self._cache.get("pre")
        if pre is not None:
            g = g * self.activacion.gradiente(pre)
        return (g @ self.pesos.T).astype(self.dt)

    def entrenar_paso(self, entrada: np.ndarray,
                      objetivo: np.ndarray) -> Dict[str, float]:
        pred = self.forward(entrada)
        y = np.asarray(objetivo, dtype=np.float64)
        if y.ndim == 1:
            y = y.reshape(1, -1)
        err = (pred.astype(np.float64) - y) / max(1, pred.shape[0])
        loss = float(np.mean((pred.astype(np.float64) - y) ** 2))
        gp, gb = self.backward(err, entrada)
        opt = self.paso_optimizador(gp, gb)
        self.historial_loss.append(loss)
        if loss < self.mejor_loss:
            self.mejor_loss = loss
        return {"loss": loss, **opt}

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------
    def registrar_loss(self, valor: float) -> None:
        valor = float(valor)
        self.historial_loss.append(valor)
        if len(self.historial_loss) > 4096:
            del self.historial_loss[:len(self.historial_loss) - 4096]
        if valor < self.mejor_loss:
            self.mejor_loss = valor
        self._emit("loss", {"loss": valor, "mejor": self.mejor_loss})

    def obtener_estadisticas(self, completas: bool = False) -> Dict[str, Any]:
        loss_medio = float(np.mean(self.historial_loss)) if self.historial_loss else None
        info: Dict[str, Any] = {
            "nombre": self.nombre,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "tipo_relu": self.tipo_relu,
            "alpha": self.alpha,
            "tasa_activacion": self.tasa_activacion,
            "tasa_muerta": self.tasa_muerta,
            "factor_escala": self.factor_escala,
            "optimizador": self.algoritmo,
            "weight_decay": self.weight_decay,
            "penalizacion": self.penalizacion(),
            "norma_pesos": float(np.linalg.norm(self.pesos)) if self.pesos is not None else 0.0,
            "activaciones": len(self.historial_activaciones),
            "gradientes": len(self.historial_gradientes),
            "pasos": self._paso,
            "lr_actual": self.lr_actual,
            "mejor_loss": None if self.mejor_loss == float("inf") else self.mejor_loss,
            "loss_medio": loss_medio,
            "varianza_real": self.varianza_real,
            "varianza_esperada": self.varianza_esperada,
            "tiempo_forward": self.tiempo_forward_acum,
            "tiempo_backward": self.tiempo_backward_acum,
            "pesos_inicializados": self.pesos is not None,
        }
        if completas:
            info["historial_loss"] = list(self.historial_loss)
            info["historial_lr"] = list(self.historial_lr)
            info["historial_tasa"] = list(self.historial_tasa)
            info["norma_pesos_historial"] = self.norma_pesos_historial.to_list()
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        return self.obtener_estadisticas(completas=True)

    def verificar_estabilidad(self) -> Dict[str, Any]:
        pesos_ok = self.pesos is not None
        pesos_finitos = bool(pesos_ok and np.all(np.isfinite(self.pesos)))
        sesgo_finitos = bool(self.sesgo is not None and np.all(np.isfinite(self.sesgo)))
        forma_ok = bool(pesos_ok and self.pesos.shape == (self.input_size, self.output_size))
        tasa_ok = bool(0.0 <= self.tasa_activacion <= 1.0)
        tipo_ok = self.tipo_relu in self.TIPOS
        return {
            "pesos_inicializados": pesos_ok,
            "pesos_finitos": pesos_finitos,
            "sesgo_finitos": sesgo_finitos,
            "forma_correcta": forma_ok,
            "tipo_valido": tipo_ok,
            "tasa_valida": tasa_ok,
            "activacion_viva": self.tasa_activacion > 0.0,
            "estable": bool(pesos_finitos and sesgo_finitos and forma_ok
                            and tipo_ok and tasa_ok),
        }

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def resetear(self, completo: bool = False) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.norma_pesos_historial.clear()
        self.historial_loss.clear()
        self.historial_lr.clear()
        self.historial_tasa.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self.tasa_activacion = 0.0
        self.tasa_muerta = 0.0
        self.optimizador.reiniciar()
        self._paso = 0
        self._cache = {}
        if completo:
            self.pesos = None
            self.sesgo = None
            self.inicializar_pesos()

    # ------------------------------------------------------------------
    # Persistencia JSON
    # ------------------------------------------------------------------
    def a_dict(self) -> Dict[str, Any]:
        return {
            "input_size": self.input_size,
            "output_size": self.output_size,
            "nombre": self.nombre,
            "tipo_relu": self.tipo_relu,
            "alpha": self.alpha,
            "factor_escala": self.factor_escala,
            "lr_base": self.lr_base,
            "optimizador": self.algoritmo,
            "weight_decay": self.weight_decay,
            "pesos": self.pesos.tolist() if self.pesos is not None else None,
            "sesgo": self.sesgo.tolist() if self.sesgo is not None else None,
        }

    def guardar(self, ruta: str) -> None:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.a_dict(), f)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaEntradaReLU":
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        obj = cls(
            data["input_size"], data["output_size"],
            data.get("nombre", "NeuronaEntradaReLU"),
            tipo_relu=data.get("tipo_relu", "relu"),
            alpha=data.get("alpha", 0.01),
            factor_escala=data.get("factor_escala", 1.0),
            learning_rate=data.get("lr_base", 0.001),
            optimizador=data.get("optimizador", "adam"),
            weight_decay=data.get("weight_decay", 0.0),
        )
        if data.get("pesos") is not None:
            obj.pesos = np.asarray(data["pesos"], dtype=obj.dt)
            obj.sesgo = np.asarray(data["sesgo"], dtype=obj.dt).reshape(-1)
        return obj

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},sal={self.output_size},"
                f"act={self.tipo_relu},opt={self.algoritmo})")
