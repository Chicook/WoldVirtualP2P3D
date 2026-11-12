"""EN5 / RN1 - Neurona de entrada regularizada (L1/L2/elastic).

Modulo autocontenido: solo depende de numpy. La configuracion global vive en
``LUCIA_CONFIG`` y puede ajustarse con ``actualizar_config``.

API publica preservada de la version original:
    lambda_l2, lambda_l1, factor_escala, norma_pesos_historial,
    penalizacion, fijar_lambdas, inicializar_pesos, forward, backward,
    obtener_estadisticas, verificar_estabilidad.

La penalizacion y su gradiente viven en la clase anidada ``Regularizador``;
el optimizador (Adam/AdamW/SGD) se unifica en un solo metodo interno.

Ejemplo:
    >>> neurona = NeuronaEntradaRegularizada(8, 4, lambda_l2=0.01)
    >>> salida = neurona.forward(np.zeros((3, 8)))
    >>> gradiente = neurona.backward(np.ones_like(salida))
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import numpy as np

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaRegularizada",
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
    """Mide y contabiliza una operacion; emite eventos de inicio/fin/error.

    Escribe en ``contador_<nombre>`` y ``tiempo_<nombre>_acum`` para no
    duplicar la misma medicion en forward y backward.
    """

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


class NeuronaEntradaRegularizada(NeuronaEntradaBase):
    """EN5 regularizada eficiente: L1/L2/elastic, AdamW/SGD, clipping.

    Preserva la API original y unifica en la clase anidada ``Regularizador``
    el calculo de la penalizacion y de su gradiente.
    """

    OPTIMIZADORES = ("adam", "adamw", "sgd", "sgd_momento")

    # ------------------------------------------------------------------
    class Regularizador:
        """Penalizacion L1/L2/elastic y su gradiente en una sola pasada."""

        TIPOS = ("ninguna", "l1", "l2", "elastic")

        def __init__(self, lambda_l2: float = 0.01, lambda_l1: float = 0.0):
            self.lambda_l2 = max(0.0, float(lambda_l2))
            self.lambda_l1 = max(0.0, float(lambda_l1))

        @property
        def tipo(self) -> str:
            if self.lambda_l1 > 0.0 and self.lambda_l2 > 0.0:
                return "elastic"
            if self.lambda_l2 > 0.0:
                return "l2"
            if self.lambda_l1 > 0.0:
                return "l1"
            return "ninguna"

        @property
        def activo(self) -> bool:
            return self.lambda_l1 > 0.0 or self.lambda_l2 > 0.0

        def penalizacion(self, pesos: Optional[np.ndarray]) -> float:
            if pesos is None or not self.activo:
                return 0.0
            w = np.asarray(pesos, dtype=np.float64).ravel()
            return (0.5 * self.lambda_l2 * float(np.dot(w, w))
                    + self.lambda_l1 * float(np.sum(np.abs(w))))

        def evaluar(self, pesos: np.ndarray,
                    incluir_l2_en_grad: bool = True) -> tuple:
            """Devuelve (penalizacion_total, gradiente) leyendo pesos una vez."""
            w = np.asarray(pesos, dtype=np.float64)
            if not self.activo:
                return 0.0, np.zeros_like(w)
            w_flat = w.ravel()
            penal = (0.5 * self.lambda_l2 * float(np.dot(w_flat, w_flat))
                     + self.lambda_l1 * float(np.sum(np.abs(w_flat))))
            grad = np.zeros_like(w)
            if incluir_l2_en_grad and self.lambda_l2 > 0.0:
                grad += self.lambda_l2 * w
            if self.lambda_l1 > 0.0:
                grad += self.lambda_l1 * np.sign(w)
            return penal, grad

        def gradiente(self, pesos: np.ndarray,
                      incluir_l2_en_grad: bool = True) -> np.ndarray:
            return self.evaluar(pesos, incluir_l2_en_grad)[1]

        def __call__(self, pesos: np.ndarray,
                     incluir_l2_en_grad: bool = True) -> tuple:
            return self.evaluar(pesos, incluir_l2_en_grad)

        def __str__(self) -> str:
            return (f"Regularizador(tipo={self.tipo}, l2={self.lambda_l2}, "
                    f"l1={self.lambda_l1})")

    # ------------------------------------------------------------------
    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaRegularizada",
                 lambda_l2: float = 0.01,
                 lambda_l1: float = 0.0,
                 factor_escala: float = 1.0,
                 learning_rate: float = 0.001,
                 optimizador: str = "adamw",
                 beta1: float = 0.9,
                 beta2: float = 0.999,
                 epsilon: float = 1e-8,
                 grad_clip: float = 5.0,
                 lr_decay: float = 0.0,
                 lr_min: float = 1e-6,
                 usar_cache_forward: bool = True,
                 semilla: Optional[int] = None,
                 capacidad_historial: int = 256):
        super().__init__(input_size, output_size, nombre)
        self.regularizador = self.Regularizador(lambda_l2, lambda_l1)
        self.factor_escala = float(factor_escala)
        self.varianza_real = 0.0
        self.varianza_esperada = 2.0 / max(1, input_size)

        algoritmo = str(optimizador).lower()
        self.optimizador = algoritmo if algoritmo in self.OPTIMIZADORES else "adamw"
        self.lr_base = float(learning_rate or LUCIA_CONFIG.get("default_learning_rate", 0.001))
        self.lr_actual = float(self.lr_base)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.grad_clip = float(grad_clip)
        self.lr_decay = float(lr_decay)
        self.lr_min = float(lr_min)
        self.usar_cache_forward = bool(usar_cache_forward)

        self.semilla = semilla if semilla is not None else int(LUCIA_CONFIG.get("random_seed", 42))
        self.rng = np.random.default_rng(self.semilla)

        self._paso = 0
        self._estado: Dict[str, Dict[str, np.ndarray]] = {}
        self._cache_entrada: Optional[np.ndarray] = None
        self._cache_norm: Optional[np.ndarray] = None

        capacidad = int(capacidad_historial or LUCIA_CONFIG.get("capacidad_historial", 256))
        self.norma_pesos_historial = _RingBuffer(capacidad)
        self.historial_activaciones = _RingBuffer(capacidad)
        self.historial_gradientes = _RingBuffer(capacidad)
        self.historial_loss: List[float] = []
        self.historial_lr: List[float] = []
        self.historial_reg: List[float] = []
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self.callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Propiedades que reflejan el estado del regularizador
    # ------------------------------------------------------------------
    @property
    def lambda_l2(self) -> float:
        return self.regularizador.lambda_l2

    @lambda_l2.setter
    def lambda_l2(self, valor: float) -> None:
        self.regularizador.lambda_l2 = max(0.0, float(valor))

    @property
    def lambda_l1(self) -> float:
        return self.regularizador.lambda_l1

    @lambda_l1.setter
    def lambda_l1(self, valor: float) -> None:
        self.regularizador.lambda_l1 = max(0.0, float(valor))

    @property
    def tipo_regularizacion(self) -> str:
        return self.regularizador.tipo

    @property
    def dt(self) -> np.dtype:
        return _dtype()

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

    # ------------------------------------------------------------------
    # Utilidades numericas
    # ------------------------------------------------------------------
    def _clip(self, g: np.ndarray) -> np.ndarray:
        if self.grad_clip and self.grad_clip > 0:
            norma = float(np.linalg.norm(g))
            if norma > self.grad_clip:
                g = g * (self.grad_clip / (norma + 1e-12))
        return g

    def _decaer_lr(self) -> None:
        if self.lr_decay > 0.0:
            self.lr_actual = max(self.lr_min, self.lr_base / (1.0 + self.lr_decay * self._paso))
        self.historial_lr.append(self.lr_actual)
        if len(self.historial_lr) > 4096:
            del self.historial_lr[:len(self.historial_lr) - 4096]

    def _preparar(self, entrada: np.ndarray) -> np.ndarray:
        x = np.asarray(entrada, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.ndim != 2 or x.shape[1] != self.input_size:
            raise ValueError(f"entrada dim {x.shape[-1]} != input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=np.float64)

    # ------------------------------------------------------------------
    # Regularizacion (delegada)
    # ------------------------------------------------------------------
    def penalizacion(self) -> float:
        if self.pesos is None:
            return 0.0
        return self.regularizador.penalizacion(self.pesos)

    def fijar_lambdas(self, l2: Optional[float] = None, l1: Optional[float] = None) -> None:
        if l2 is not None:
            self.lambda_l2 = l2
        if l1 is not None:
            self.lambda_l1 = l1

    # ------------------------------------------------------------------
    # Parametros
    # ------------------------------------------------------------------
    def inicializar_pesos(self) -> None:
        escala = np.sqrt(2.0 / max(1, self.input_size))
        self.pesos = self.rng.normal(
            0.0, escala, size=(self.input_size, self.output_size),
        ).astype(self.dt)
        self.sesgo = np.zeros(self.output_size, dtype=self.dt)
        self.varianza_real = float(np.var(self.pesos))
        self.varianza_esperada = 2.0 / max(1, self.input_size)
        self._estado.clear()
        self._paso = 0
        self._cache_entrada = None
        self._cache_norm = None
        self._registrar_norma()
        self._emit("init", {"modo": "he"})

    def _registrar_norma(self) -> None:
        if self.pesos is not None:
            self.norma_pesos_historial.append(float(np.linalg.norm(self.pesos)))

    # ------------------------------------------------------------------
    # Optimizador unificado (Adam / AdamW / SGD / SGD con momento)
    # ------------------------------------------------------------------
    def _actualizar(self, nombre: str, parametro: np.ndarray,
                    gradiente: np.ndarray) -> None:
        estado = self._estado.get(nombre)
        if estado is None:
            estado = {"m": np.zeros_like(parametro, dtype=np.float64),
                      "v": np.zeros_like(parametro, dtype=np.float64)}
            self._estado[nombre] = estado
        g = np.asarray(gradiente, dtype=np.float64)

        if self.optimizador == "sgd":
            parametro -= self.lr_actual * g
            return

        if self.optimizador == "sgd_momento":
            estado["v"] = self.beta1 * estado["v"] + (1.0 - self.beta1) * g
            parametro -= self.lr_actual * estado["v"]
            return

        estado["m"] = self.beta1 * estado["m"] + (1.0 - self.beta1) * g
        estado["v"] = self.beta2 * estado["v"] + (1.0 - self.beta2) * (g * g)
        m_hat = estado["m"] / (1.0 - self.beta1 ** self._paso)
        v_hat = estado["v"] / (1.0 - self.beta2 ** self._paso)
        parametro -= self.lr_actual * m_hat / (np.sqrt(v_hat) + self.epsilon)

    def paso_optimizador(self, grad_pesos: np.ndarray,
                         grad_sesgo: np.ndarray) -> Dict[str, float]:
        """Aplica regularizacion + clipping + un paso del optimizador."""
        if self.pesos is None or self.sesgo is None:
            raise RuntimeError("pesos no inicializados")

        desacoplado = self.optimizador == "adamw"
        penal, grad_reg = self.regularizador.evaluar(
            self.pesos, incluir_l2_en_grad=not desacoplado,
        )
        gp = self._clip(np.asarray(grad_pesos, dtype=np.float64) + grad_reg)
        gb = self._clip(np.asarray(grad_sesgo, dtype=np.float64))

        self._paso += 1
        self._decaer_lr()
        self._actualizar("pesos", self.pesos, gp)
        self._actualizar("sesgo", self.sesgo, gb)
        if desacoplado and self.lambda_l2 > 0.0:
            self.pesos -= self.lr_actual * self.lambda_l2 * self.pesos

        self._registrar_norma()
        self.historial_reg.append(penal)
        if len(self.historial_reg) > 4096:
            del self.historial_reg[:len(self.historial_reg) - 4096]

        info = {"lr": self.lr_actual, "paso": float(self._paso),
                "penalizacion": float(penal)}
        self._emit("paso", info)
        return info

    # ------------------------------------------------------------------
    # Propagacion
    # ------------------------------------------------------------------
    @_instrumentar("forward")
    @_requiere_pesos
    def forward(self, entrada) -> np.ndarray:
        x = self._preparar(entrada)
        xin = x * self.factor_escala
        z = xin @ self.pesos + self.sesgo

        if self.usar_cache_forward:
            self._cache_entrada = x
            self._cache_norm = xin
        self.historial_activaciones.append(z)

        v = float(np.var(z)) if z.size else 0.0
        if len(self.historial_activaciones) > 1:
            self.varianza_real = 0.9 * self.varianza_real + 0.1 * v
        else:
            self.varianza_real = v
        self._emit("activacion", {"forma": z.shape, "media": float(np.mean(z))})
        return z.astype(self.dt)

    @_instrumentar("backward")
    @_requiere_pesos
    def backward(self, g, e=None) -> np.ndarray:
        if e is not None:
            x = self._preparar(e)
            xin = x * self.factor_escala
            if self.usar_cache_forward:
                self._cache_entrada, self._cache_norm = x, xin
        elif self._cache_norm is not None:
            xin = self._cache_norm
        else:
            raise RuntimeError("backward sin cache: llama forward o pasa e")

        grad = np.asarray(g, dtype=np.float64)
        if grad.ndim == 1:
            grad = grad.reshape(1, -1)
        if grad.ndim != 2 or grad.shape[1] != self.output_size:
            raise ValueError(f"gradiente dim {grad.shape[-1]} != output_size {self.output_size}")
        grad = self._clip(grad)

        grad_pesos = self._clip(xin.T @ grad)
        grad_sesgo = self._clip(grad.sum(axis=0))
        info = self.paso_optimizador(grad_pesos, grad_sesgo)

        grad_entrada = (grad @ self.pesos.T) * self.factor_escala
        self.historial_gradientes.append(grad_entrada)
        self._emit("backward_info", {"norma": float(np.linalg.norm(grad))})
        self._emit("regularizacion", {"penalizacion": info["penalizacion"]})
        return grad_entrada.astype(self.dt)

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
            "lambda_l2": self.lambda_l2,
            "lambda_l1": self.lambda_l1,
            "tipo_regularizacion": self.tipo_regularizacion,
            "factor_escala": self.factor_escala,
            "optimizador": self.optimizador,
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
            info["historial_reg"] = list(self.historial_reg)
            info["norma_pesos_historial"] = self.norma_pesos_historial.to_list()
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        return self.obtener_estadisticas(completas=True)

    def verificar_estabilidad(self) -> Dict[str, Any]:
        pesos_ok = self.pesos is not None
        pesos_finitos = bool(pesos_ok and np.all(np.isfinite(self.pesos)))
        sesgo_finitos = bool(self.sesgo is not None and np.all(np.isfinite(self.sesgo)))
        forma_ok = bool(pesos_ok and self.pesos.shape == (self.input_size, self.output_size))
        lambdas_ok = bool(np.isfinite(self.lambda_l2) and np.isfinite(self.lambda_l1)
                          and self.lambda_l2 >= 0.0 and self.lambda_l1 >= 0.0)
        return {
            "pesos_inicializados": pesos_ok,
            "pesos_finitos": pesos_finitos,
            "sesgo_finitos": sesgo_finitos,
            "forma_correcta": forma_ok,
            "lambdas_validas": lambdas_ok,
            "regularizacion_activa": self.regularizador.activo,
            "estable": bool(pesos_finitos and sesgo_finitos and forma_ok and lambdas_ok),
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
        self.historial_reg.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self._estado.clear()
        self._paso = 0
        self._cache_entrada = None
        self._cache_norm = None
        if completo:
            self.pesos = None
            self.sesgo = None
            self.inicializar_pesos()

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},sal={self.output_size},"
                f"reg={self.tipo_regularizacion},opt={self.optimizador})")
