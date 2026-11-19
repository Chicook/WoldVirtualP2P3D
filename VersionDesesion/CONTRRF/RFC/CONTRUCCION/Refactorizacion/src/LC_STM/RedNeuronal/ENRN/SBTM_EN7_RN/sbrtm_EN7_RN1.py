"""EN7 / RN1 - Neurona de entrada con BatchNorm.

Modulo autocontenido: solo depende de numpy. La configuracion global vive en
``LUCIA_CONFIG`` y puede ajustarse con ``actualizar_config``.

API publica preservada de la version original:
    momentum, epsilon, factor_escala, modo_entrenamiento, gamma, beta,
    running_mean, running_var, inicializar_pesos, forward, backward,
    entrenar, evaluar.

Mejoras matematicas:
  - BatchNorm con varianza sesgada calculada en una sola pasada (``z_c``) y
    ``rsqrt`` numerico estable.
  - Backward de BN vectorizado (``einsum``) con los tres gradientes
    (entrada, gamma, beta) en una pasada.
  - Actualizacion de medias/varianzas moviles con momentum exponencial.
  - Optimizador unificado Adam / AdamW / SGD / SGD con momento aplicado a
    pesos, sesgo, gamma y beta con el mismo contador de pasos.

Ejemplo:
    >>> neurona = NeuronaEntradaBatchNorm(8, 4)
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
    "NeuronaEntradaBatchNorm",
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
    """Inicializa los parametros de forma perezosa antes de ejecutar ``fn``."""

    @wraps(fn)
    def envoltura(self: Any, *args: Any, **kwargs: Any) -> Any:
        if self.pesos is None or self.sesgo is None or self.gamma is None or self.beta is None:
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


class NeuronaEntradaBatchNorm(NeuronaEntradaBase):
    """EN7 BatchNorm eficiente: forward/backward BN correctos, Adam/SGD.

    Las clases anidadas aíslan las dos matematicas del modulo:
    ``BatchNorm`` (normalizacion y estadisticas moviles) y ``Optimizador``
    (regla de actualizacion comun a pesos, sesgo, gamma y beta).
    """

    # ------------------------------------------------------------------
    class BatchNorm:
        """Normalizacion por lotes con medias/varianzas moviles."""

        def __init__(self, epsilon: float = 1e-5, momentum: float = 0.9):
            self.epsilon = float(epsilon)
            self.momentum = float(momentum)
            self.running_mean: Optional[np.ndarray] = None
            self.running_var: Optional[np.ndarray] = None

        @property
        def inicializado(self) -> bool:
            return self.running_mean is not None and self.running_var is not None

        def reiniciar(self) -> None:
            self.running_mean = None
            self.running_var = None

        def forward(self, z: np.ndarray, gamma: np.ndarray, beta: np.ndarray,
                    entrenamiento: bool = True,
                    actualizar: bool = True) -> Tuple[np.ndarray, Dict[str, Any]]:
            z64 = np.asarray(z, dtype=np.float64)
            if entrenamiento:
                mu = z64.mean(axis=0, keepdims=True)
                zc = z64 - mu
                var = np.mean(zc * zc, axis=0, keepdims=True)
                if actualizar:
                    mu42 = mu.reshape(-1)
                    var42 = var.reshape(-1)
                    if self.running_mean is None:
                        self.running_mean = mu42.copy()
                        self.running_var = var42.copy()
                    else:
                        m = self.momentum
                        self.running_mean = m * self.running_mean + (1.0 - m) * mu42
                        self.running_var = m * self.running_var + (1.0 - m) * var42
            else:
                mu = (self.running_mean.reshape(1, -1)
                      if self.running_mean is not None
                      else np.zeros((1, z64.shape[1])))
                var = (self.running_var.reshape(1, -1)
                       if self.running_var is not None
                       else np.ones((1, z64.shape[1])))
            std_inv = 1.0 / np.sqrt(var + self.epsilon)
            zn = (z64 - mu) * std_inv
            out = zn * np.asarray(gamma, dtype=np.float64) + np.asarray(beta, dtype=np.float64)
            cache = {"zn": zn, "std_inv": std_inv,
                     "gamma": np.asarray(gamma, dtype=np.float64),
                     "m": max(1, z64.shape[0])}
            return out, cache

        def backward(self, g: np.ndarray,
                     cache: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
            """Gradientes (entrada, gamma, beta) de la normalizacion."""
            zn = cache["zn"]
            std_inv = cache["std_inv"]
            gamma = cache["gamma"]
            m = cache["m"]
            g64 = np.asarray(g, dtype=np.float64)
            g_gamma = np.einsum("ij,ij->j", g64, zn)
            g_beta = g64.sum(axis=0)
            sum_g = g_beta.reshape(1, -1)
            sum_gzn = g_gamma.reshape(1, -1)
            gz = (gamma * std_inv / m) * (m * g64 - sum_g - zn * sum_gzn)
            return gz, g_gamma, g_beta

        def __str__(self) -> str:
            return f"BatchNorm(eps={self.epsilon}, mom={self.momentum})"

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
    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaBatchNorm",
                 momentum: float = 0.9,
                 epsilon: float = 1e-5,
                 factor_escala: float = 1.0,
                 modo_entrenamiento: bool = True,
                 learning_rate: float = 0.001,
                 optimizador: str = "adam",
                 beta1: float = 0.9,
                 beta2: float = 0.999,
                 eps_adam: float = 1e-8,
                 weight_decay: float = 0.0,
                 grad_clip: float = 5.0,
                 lr_decay: float = 0.0,
                 lr_min: float = 1e-6,
                 usar_cache_forward: bool = True,
                 semilla: Optional[int] = None,
                 capacidad_historial: int = 256):
        super().__init__(input_size, output_size, nombre)
        self.factor_escala = float(factor_escala)
        self.modo_entrenamiento = bool(modo_entrenamiento)
        self.varianza_real = 0.0
        self.varianza_esperada = 1.0
        self.lr_base = float(learning_rate or LUCIA_CONFIG.get("default_learning_rate", 0.001))
        self.lr_actual = float(self.lr_base)
        self.grad_clip = float(grad_clip)
        self.lr_decay = float(lr_decay)
        self.lr_min = float(lr_min)
        self.usar_cache_forward = bool(usar_cache_forward)
        self.semilla = semilla if semilla is not None else int(LUCIA_CONFIG.get("random_seed", 42))
        self.rng = np.random.default_rng(self.semilla)

        self.gamma: Optional[np.ndarray] = None
        self.beta: Optional[np.ndarray] = None
        self.bn = self.BatchNorm(epsilon, momentum)
        self.optimizador = self.Optimizador(optimizador, beta1, beta2, eps_adam, weight_decay)

        self._paso = 0
        self._cache: Dict[str, Any] = {}

        capacidad = int(capacidad_historial or LUCIA_CONFIG.get("capacidad_historial", 256))
        self.norma_pesos_historial = _RingBuffer(capacidad)
        self.historial_activaciones = _RingBuffer(capacidad)
        self.historial_gradientes = _RingBuffer(capacidad)
        self.historial_loss: List[float] = []
        self.historial_lr: List[float] = []
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self.callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Propiedades (la API original expone BN como atributos)
    # ------------------------------------------------------------------
    @property
    def dt(self) -> np.dtype:
        return _dtype()

    @property
    def epsilon(self) -> float:
        return self.bn.epsilon

    @epsilon.setter
    def epsilon(self, valor: float) -> None:
        self.bn.epsilon = float(valor)

    @property
    def momentum(self) -> float:
        return self.bn.momentum

    @momentum.setter
    def momentum(self, valor: float) -> None:
        self.bn.momentum = float(valor)

    @property
    def running_mean(self) -> Optional[np.ndarray]:
        return self.bn.running_mean

    @running_mean.setter
    def running_mean(self, valor: Optional[np.ndarray]) -> None:
        self.bn.running_mean = (None if valor is None
                                else np.asarray(valor, dtype=np.float64).reshape(-1))

    @property
    def running_var(self) -> Optional[np.ndarray]:
        return self.bn.running_var

    @running_var.setter
    def running_var(self, valor: Optional[np.ndarray]) -> None:
        self.bn.running_var = (None if valor is None
                               else np.asarray(valor, dtype=np.float64).reshape(-1))

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
    def eps_adam(self) -> float:
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

    def entrenar(self) -> None:
        self.modo_entrenamiento = True

    def evaluar(self) -> None:
        self.modo_entrenamiento = False

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

    # Compatibilidad con la API original
    def _bn_forward(self, z: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        assert self.gamma is not None and self.beta is not None
        out, cache = self.bn.forward(z, self.gamma, self.beta,
                                     self.modo_entrenamiento)
        return out.astype(self.dt, copy=False), cache

    def _bn_backward(self, g: np.ndarray, cache: Dict[str, Any]
                     ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        gz, g_gamma, g_beta = self.bn.backward(g, cache)
        return (gz.astype(self.dt), g_gamma.astype(self.dt),
                g_beta.astype(self.dt))

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
        self.gamma = np.ones(self.output_size, dtype=self.dt)
        self.beta = np.zeros(self.output_size, dtype=self.dt)
        self.varianza_real = float(np.var(self.pesos))
        self.bn.reiniciar()
        self.optimizador.reiniciar()
        self._paso = 0
        self._cache = {}
        self._registrar_norma()
        self._emit("init", {"modo": modo})

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
    # Propiedades de pesos entrenables
    # ------------------------------------------------------------------
    def _asegurar_todo(self) -> None:
        if (self.pesos is None or self.sesgo is None
                or self.gamma is None or self.beta is None):
            self.inicializar_pesos()

    # ------------------------------------------------------------------
    # Paso del optimizador
    # ------------------------------------------------------------------
    def paso_optimizador(self, grad_pesos: np.ndarray,
                         grad_sesgo: np.ndarray,
                         grad_gamma: Optional[np.ndarray] = None,
                         grad_beta: Optional[np.ndarray] = None
                         ) -> Dict[str, float]:
        """Weight decay + clipping + paso comun a pesos, sesgo, gamma y beta."""
        self._asegurar_todo()
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
        if grad_gamma is not None and self.gamma is not None:
            self.optimizador.aplicar("gamma", self.gamma,
                                     self._clip(np.asarray(grad_gamma, dtype=np.float64)),
                                     self.lr_actual, self._paso)
        if grad_beta is not None and self.beta is not None:
            self.optimizador.aplicar("beta", self.beta,
                                     self._clip(np.asarray(grad_beta, dtype=np.float64)),
                                     self.lr_actual, self._paso)

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
    def forward(self, entrada, entrenamiento: Optional[bool] = None) -> np.ndarray:
        if entrenamiento is not None:
            self.modo_entrenamiento = bool(entrenamiento)
        x = self._preparar(entrada)
        if self.pesos is None or self.sesgo is None:
            raise RuntimeError("pesos no inicializados")

        z = x @ self.pesos + self.sesgo
        salida, cache_bn = self.bn.forward(z, self.gamma, self.beta,
                                           self.modo_entrenamiento)
        salida = salida.astype(self.dt, copy=False)

        if self.usar_cache_forward:
            self._cache = {"x": x, "z": z, "bn": cache_bn}
        self.historial_activaciones.append(salida)

        v = float(np.var(salida)) if salida.size else 0.0
        if len(self.historial_activaciones) > 1:
            self.varianza_real = 0.9 * self.varianza_real + 0.1 * v
        else:
            self.varianza_real = v
        self._emit("activacion", {"forma": salida.shape,
                                  "media": float(np.mean(salida))})
        return salida

    def forward_batch(self, lote: List[np.ndarray]) -> List[np.ndarray]:
        return [self.forward(x) for x in lote]

    @_instrumentar("backward")
    @_requiere_pesos
    def backward(self, gradiente_salida: np.ndarray,
                 entrada: Optional[np.ndarray] = None
                 ) -> Tuple[np.ndarray, np.ndarray]:
        """Devuelve (grad_pesos, grad_sesgo) SIN aplicar el optimizador.

        Los gradientes de gamma/beta quedan en la cache para
        ``paso_optimizador``; el weight decay se aplica alli una sola vez.
        """
        g = np.asarray(gradiente_salida, dtype=np.float64)
        if g.ndim == 1:
            g = g.reshape(1, -1)
        if g.ndim != 2 or g.shape[1] != self.output_size:
            raise ValueError(f"gradiente dim {g.shape[-1]} != output_size {self.output_size}")

        if entrada is not None:
            x = self._preparar(entrada)
            if self.pesos is None or self.sesgo is None:
                raise RuntimeError("pesos no inicializados")
            z = x @ self.pesos + self.sesgo
            _, bn = self.bn.forward(z, self.gamma, self.beta,
                                    self.modo_entrenamiento, actualizar=False)
        elif "x" in self._cache and "bn" in self._cache:
            x = self._cache["x"]
            bn = self._cache["bn"]
        else:
            raise ValueError("sin entrada ni cache forward")

        gz, g_gamma, g_beta = self.bn.backward(g, bn)
        b = max(1, x.shape[0])
        gp = self._clip(x.T @ gz / b)
        gb = self._clip(np.sum(gz, axis=0) / b)

        self._cache["g_gamma"] = g_gamma
        self._cache["g_beta"] = g_beta
        self._cache["gz"] = gz
        self.historial_gradientes.append({
            "pesos": gp.astype(self.dt).copy(),
            "sesgo": gb.astype(self.dt).copy(),
            "gamma": g_gamma.astype(self.dt).copy(),
            "beta": g_beta.astype(self.dt).copy(),
            "norma_pesos": float(np.linalg.norm(gp)),
            "norma_sesgo": float(np.linalg.norm(gb)),
        })
        return gp.astype(self.dt), gb.astype(self.dt)

    @_requiere_pesos
    def grad_entrada(self, gradiente_salida: np.ndarray) -> np.ndarray:
        """Gradiente respecto a la entrada usando la cache del ultimo forward."""
        g = np.asarray(gradiente_salida, dtype=np.float64)
        if g.ndim == 1:
            g = g.reshape(1, -1)
        bn = self._cache.get("bn")
        if bn is None:
            raise ValueError("grad_entrada requiere un forward previo")
        gz, _, _ = self.bn.backward(g, bn)
        return (gz @ self.pesos.T).astype(self.dt)

    def entrenar_paso(self, entrada: np.ndarray,
                      objetivo: np.ndarray) -> Dict[str, float]:
        pred = self.forward(entrada, entrenamiento=True)
        y = np.asarray(objetivo, dtype=self.dt)
        if y.ndim == 1:
            y = y.reshape(1, -1)
        err = (pred - y) / max(1, pred.shape[0])
        loss = float(np.mean((pred - y) ** 2))
        gp, gb = self.backward(err, entrada)
        opt = self.paso_optimizador(gp, gb,
                                    self._cache.get("g_gamma"),
                                    self._cache.get("g_beta"))
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
            "momentum": self.momentum,
            "epsilon": self.epsilon,
            "modo_entrenamiento": self.modo_entrenamiento,
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
            "running_stats": self.bn.inicializado,
            "pesos_inicializados": self.pesos is not None,
        }
        if completas:
            info["historial_loss"] = list(self.historial_loss)
            info["historial_lr"] = list(self.historial_lr)
            info["norma_pesos_historial"] = self.norma_pesos_historial.to_list()
            if self.running_mean is not None:
                info["running_mean"] = self.running_mean.tolist()
            if self.running_var is not None:
                info["running_var"] = self.running_var.tolist()
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        return self.obtener_estadisticas(completas=True)

    def verificar_estabilidad(self) -> Dict[str, Any]:
        pesos_ok = self.pesos is not None
        gamma_ok = self.gamma is not None
        beta_ok = self.beta is not None
        finitos = [np.all(np.isfinite(a)) for a in (self.pesos, self.gamma, self.beta)
                   if a is not None]
        sesgo_ok = bool(self.sesgo is not None and np.all(np.isfinite(self.sesgo)))
        forma_ok = bool(pesos_ok and self.pesos.shape == (self.input_size, self.output_size))
        eps_ok = self.epsilon > 0.0
        momentum_ok = 0.0 <= self.momentum < 1.0
        return {
            "pesos_inicializados": pesos_ok,
            "gamma_inicializado": gamma_ok,
            "beta_inicializado": beta_ok,
            "sesgo_finitos": sesgo_ok,
            "parametros_finitos": bool(all(finitos)) if finitos else False,
            "forma_correcta": forma_ok,
            "epsilon_valido": eps_ok,
            "momentum_valido": momentum_ok,
            "running_stats": self.bn.inicializado,
            "estable": bool(pesos_ok and gamma_ok and beta_ok and sesgo_ok
                            and forma_ok and eps_ok and momentum_ok),
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
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self.optimizador.reiniciar()
        self._paso = 0
        self._cache = {}
        if completo:
            self.pesos = None
            self.sesgo = None
            self.gamma = None
            self.beta = None
            self.bn.reiniciar()
            self.inicializar_pesos()

    # ------------------------------------------------------------------
    # Persistencia JSON
    # ------------------------------------------------------------------
    def a_dict(self) -> Dict[str, Any]:
        return {
            "input_size": self.input_size,
            "output_size": self.output_size,
            "nombre": self.nombre,
            "momentum": self.momentum,
            "epsilon": self.epsilon,
            "factor_escala": self.factor_escala,
            "lr_base": self.lr_base,
            "optimizador": self.algoritmo,
            "weight_decay": self.weight_decay,
            "pesos": self.pesos.tolist() if self.pesos is not None else None,
            "sesgo": self.sesgo.tolist() if self.sesgo is not None else None,
            "gamma": self.gamma.tolist() if self.gamma is not None else None,
            "beta": self.beta.tolist() if self.beta is not None else None,
            "running_mean": self.running_mean.tolist() if self.running_mean is not None else None,
            "running_var": self.running_var.tolist() if self.running_var is not None else None,
        }

    def guardar(self, ruta: str) -> None:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.a_dict(), f)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaEntradaBatchNorm":
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        obj = cls(
            data["input_size"], data["output_size"],
            data.get("nombre", "NeuronaEntradaBatchNorm"),
            momentum=data.get("momentum", 0.9),
            epsilon=data.get("epsilon", 1e-5),
            factor_escala=data.get("factor_escala", 1.0),
            learning_rate=data.get("lr_base", 0.001),
            optimizador=data.get("optimizador", "adam"),
            weight_decay=data.get("weight_decay", 0.0),
        )
        if data.get("pesos") is not None:
            obj.pesos = np.asarray(data["pesos"], dtype=obj.dt)
            obj.sesgo = np.asarray(data["sesgo"], dtype=obj.dt).reshape(-1)
            obj.gamma = np.asarray(data["gamma"], dtype=obj.dt).reshape(-1)
            obj.beta = np.asarray(data["beta"], dtype=obj.dt).reshape(-1)
        if data.get("running_mean") is not None:
            obj.running_mean = np.asarray(data["running_mean"], dtype=np.float64)
            obj.running_var = np.asarray(data["running_var"], dtype=np.float64)
        return obj

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},sal={self.output_size},"
                f"mom={self.momentum},eps={self.epsilon},opt={self.algoritmo})")
