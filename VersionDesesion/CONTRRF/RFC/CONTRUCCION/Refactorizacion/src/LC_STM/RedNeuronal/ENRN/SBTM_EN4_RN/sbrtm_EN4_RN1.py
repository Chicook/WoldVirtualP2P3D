"""EN4 / RN1 - Neurona de entrada normalizada (SBTM).

Modulo autocontenido: solo depende de numpy. La configuracion global vive en
``LUCIA_CONFIG`` y puede ajustarse con ``actualizar_config`` antes de instanciar.

API publica preservada de la version original:
    metodo, factor_escala, params_norm, _normalizar, _actualizar_stats,
    inicializar_pesos, forward, backward, fijar_metodo, reiniciar_stats_norm,
    obtener_estadisticas, verificar_estabilidad.

Ejemplo:
    >>> neurona = NeuronaEntradaNormalizada(8, 4, metodo="z_score")
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
    "NeuronaEntradaNormalizada",
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
    duplicar el mismo codigo de medicion en forward y backward.
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


class NeuronaEntradaNormalizada(NeuronaEntradaBase):
    """EN4 normalizada eficiente: z_score/min_max/robusta, Adam/SGD.

    Preserva la API original y agrupa en clases anidadas las dos
    responsabilidades que antes estaban disueltas en la clase:
    ``Normalizador`` (estadisticas + transformacion) y ``Optimizador``
    (estado y paso de Adam/AdamW/SGD).
    """

    # ------------------------------------------------------------------
    # Clases anidadas
    # ------------------------------------------------------------------
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

    class Normalizador:
        """Estadisticas moviles y transformacion segun el metodo elegido."""

        METODOS = ("z_score", "min_max", "robusta", "ninguna")

        def __init__(self, input_size: int, metodo: str = "z_score",
                     momento_stats: float = 0.1):
            self.input_size = int(input_size)
            self.momento_stats = float(momento_stats)
            self.metodo = "z_score"
            self.params: Dict[str, Optional[np.ndarray]] = {
                "media": None, "std": None, "min": None, "max": None,
                "mediana": None, "iqr": None,
            }
            self.cambiar_metodo(metodo)

        def cambiar_metodo(self, metodo: str) -> None:
            if metodo not in self.METODOS:
                raise ValueError(f"metodo {metodo} no en {self.METODOS}")
            self.metodo = metodo

        def reiniciar(self) -> None:
            for clave in self.params:
                self.params[clave] = None

        def actualizar(self, x: np.ndarray) -> None:
            x = np.asarray(x, dtype=np.float64)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            m = self.momento_stats
            media = np.mean(x, axis=0, keepdims=True)
            std = np.std(x, axis=0, keepdims=True) + 1e-8
            minimo = np.min(x, axis=0, keepdims=True)
            maximo = np.max(x, axis=0, keepdims=True)
            mediana = np.median(x, axis=0, keepdims=True)
            q75 = np.percentile(x, 75, axis=0, keepdims=True)
            q25 = np.percentile(x, 25, axis=0, keepdims=True)
            iqr = np.maximum(q75 - q25, 1e-8)

            p = self.params
            if p["media"] is None:
                p["media"], p["std"] = media, std
                p["min"], p["max"] = minimo, maximo
                p["mediana"], p["iqr"] = mediana, iqr
                return
            p["media"] = (1 - m) * p["media"] + m * media
            p["std"] = (1 - m) * p["std"] + m * std
            p["min"] = np.minimum(p["min"], minimo)
            p["max"] = np.maximum(p["max"], maximo)
            p["mediana"] = (1 - m) * p["mediana"] + m * mediana
            p["iqr"] = (1 - m) * p["iqr"] + m * iqr

        def transformar(self, x: np.ndarray, actualizar: bool = True) -> np.ndarray:
            xa = np.asarray(x, dtype=np.float64)
            if actualizar:
                self.actualizar(xa)
            p = self.params
            if p["media"] is None or self.metodo == "ninguna":
                return xa
            if self.metodo == "z_score":
                return (xa - p["media"]) / (p["std"] + 1e-8)
            if self.metodo == "min_max":
                return (xa - p["min"]) / (p["max"] - p["min"] + 1e-8)
            return (xa - p["mediana"]) / (p["iqr"] + 1e-8)  # robusta

    class Optimizador:
        """Estado y actualizacion de parametros para Adam / AdamW / SGD."""

        ALGORITMOS = ("adam", "adamw", "sgd", "sgd_momento")

        def __init__(self, algoritmo: str = "adam", beta1: float = 0.9,
                     beta2: float = 0.999, epsilon: float = 1e-8,
                     peso_decaimiento: float = 0.0):
            algoritmo = str(algoritmo).lower()
            self.algoritmo = algoritmo if algoritmo in self.ALGORITMOS else "adam"
            self.beta1 = float(beta1)
            self.beta2 = float(beta2)
            self.epsilon = float(epsilon)
            self.peso_decaimiento = float(peso_decaimiento)
            self.paso = 0
            self._estado: Dict[str, Dict[str, np.ndarray]] = {}

        def reiniciar(self) -> None:
            self.paso = 0
            self._estado.clear()

        def preparar(self, nombre: str, parametro: np.ndarray) -> None:
            if parametro is None:
                raise ValueError(f"parametro {nombre} no inicializado")
            self._estado.setdefault(nombre, {
                "m": np.zeros_like(parametro, dtype=np.float64),
                "v": np.zeros_like(parametro, dtype=np.float64),
            })

        def nuevo_paso(self) -> int:
            self.paso += 1
            return self.paso

        def aplicar(self, nombre: str, parametro: np.ndarray,
                    gradiente: np.ndarray, lr: float, paso: int) -> None:
            self.preparar(nombre, parametro)
            estado = self._estado[nombre]
            g = np.asarray(gradiente, dtype=np.float64)

            if self.peso_decaimiento and self.algoritmo != "adamw":
                g = g + self.peso_decaimiento * parametro

            if self.algoritmo == "sgd":
                parametro -= lr * g
                return

            if self.algoritmo == "sgd_momento":
                estado["v"] = self.beta1 * estado["v"] + (1.0 - self.beta1) * g
                parametro -= lr * estado["v"]
                return

            estado["m"] = self.beta1 * estado["m"] + (1.0 - self.beta1) * g
            estado["v"] = self.beta2 * estado["v"] + (1.0 - self.beta2) * (g * g)
            m_hat = estado["m"] / (1.0 - self.beta1 ** paso)
            v_hat = estado["v"] / (1.0 - self.beta2 ** paso)
            parametro -= lr * m_hat / (np.sqrt(v_hat) + self.epsilon)

            if self.algoritmo == "adamw" and self.peso_decaimiento:
                parametro -= lr * self.peso_decaimiento * parametro

    METODOS = Normalizador.METODOS

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaNormalizada",
                 metodo: str = 'z_score',
                 factor_escala: float = 1.0,
                 momento_stats: float = 0.1,
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
        self.factor_escala = float(factor_escala)

        self.normalizador = self.Normalizador(input_size, metodo, momento_stats)
        self.varianza_real = 0.0
        self.varianza_esperada = 2.0 / max(1, input_size)

        self.lr_base = float(learning_rate or LUCIA_CONFIG.get("default_learning_rate", 0.001))
        self.lr_actual = float(self.lr_base)
        self.optimizador = self.Optimizador(
            optimizador, beta1, beta2, epsilon, weight_decay,
        )
        self.grad_clip = float(grad_clip)
        self.lr_decay = float(lr_decay)
        self.lr_min = float(lr_min)
        self.usar_cache_forward = bool(usar_cache_forward)

        self.semilla = semilla if semilla is not None else int(LUCIA_CONFIG.get("random_seed", 42))
        self.rng = np.random.default_rng(self.semilla)

        self._paso = 0
        self._cache_entrada: Optional[np.ndarray] = None
        self._cache_norm: Optional[np.ndarray] = None

        capacidad = int(capacidad_historial or LUCIA_CONFIG.get("capacidad_historial", 256))
        self.historial_activaciones = self._RingBuffer(capacidad)
        self.historial_gradientes = self._RingBuffer(capacidad)
        self.historial_loss: List[float] = []
        self.historial_lr: List[float] = []
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self.callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Propiedades que reflejan el estado del normalizador
    # ------------------------------------------------------------------
    @property
    def metodo(self) -> str:
        return self.normalizador.metodo

    @metodo.setter
    def metodo(self, valor: str) -> None:
        self.normalizador.cambiar_metodo(valor)

    @property
    def params_norm(self) -> Dict[str, Optional[np.ndarray]]:
        return self.normalizador.params

    @property
    def momento_stats(self) -> float:
        return self.normalizador.momento_stats

    @momento_stats.setter
    def momento_stats(self, valor: float) -> None:
        self.normalizador.momento_stats = float(valor)

    @property
    def dt(self) -> np.dtype:
        return _dtype()

    # ------------------------------------------------------------------
    def _emit(self, evento: str, info: Optional[Dict[str, Any]] = None) -> None:
        for cb in self.callbacks:
            try:
                cb(evento, info or {})
            except Exception:
                continue

    def registrar_callback(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        self.callbacks.append(fn)

    def _actualizar_stats(self, x: np.ndarray) -> None:
        xa = np.asarray(x, dtype=np.float64)
        if xa.ndim == 1:
            xa = xa.reshape(1, -1)
        self.normalizador.actualizar(xa)
        self.varianza_real = float(np.var(xa))

    def _normalizar(self, x: np.ndarray, actualizar: bool = True) -> np.ndarray:
        xa = self._preparar(x)
        return self.normalizador.transformar(xa, actualizar=actualizar).astype(self.dt)

    def fijar_metodo(self, metodo: str) -> None:
        self.normalizador.cambiar_metodo(metodo)

    def reiniciar_stats_norm(self) -> None:
        self.normalizador.reiniciar()

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

    def _asegurar_adam(self) -> None:
        self.optimizador.preparar("pesos", self.pesos)
        self.optimizador.preparar("sesgo", self.sesgo)

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
    def inicializar_pesos(self) -> None:
        escala = np.sqrt(2.0 / max(1, self.input_size))
        self.pesos = self.rng.normal(
            0.0, escala, size=(self.input_size, self.output_size),
        ).astype(np.float64)
        self.sesgo = np.zeros(self.output_size, dtype=np.float64)
        self.optimizador.reiniciar()
        self._paso = 0
        self._cache_entrada = None
        self._cache_norm = None

    # ------------------------------------------------------------------
    # Propagacion
    # ------------------------------------------------------------------
    @_instrumentar("forward")
    @_requiere_pesos
    def forward(self, entrada) -> np.ndarray:
        x = self._preparar(entrada)
        xn = self.normalizador.transformar(x, actualizar=True)
        self.varianza_real = float(np.var(xn))
        xin = xn * self.factor_escala

        z = xin @ self.pesos + self.sesgo
        if self.usar_cache_forward:
            self._cache_entrada = x
            self._cache_norm = xin
        self.historial_activaciones.append(z)
        self._emit("activacion", {"forma": z.shape, "media": float(np.mean(z))})
        return z.astype(self.dt)

    @_instrumentar("backward")
    @_requiere_pesos
    def backward(self, g, e=None) -> np.ndarray:
        if e is not None:
            x = self._preparar(e)
            xin = self.normalizador.transformar(x, actualizar=False) * self.factor_escala
            if self.usar_cache_forward:
                self._cache_entrada, self._cache_norm = x, xin
        elif self._cache_norm is not None:
            xin = self._cache_norm
        else:
            raise RuntimeError("backward sin cache: llama forward o pasa 'e'")

        grad = np.asarray(g, dtype=np.float64)
        if grad.ndim == 1:
            grad = grad.reshape(1, -1)
        if grad.ndim != 2 or grad.shape[1] != self.output_size:
            raise ValueError(f"gradiente dim {grad.shape[-1]} != output_size {self.output_size}")
        grad = self._clip(grad)

        grad_pesos = self._clip(xin.T @ grad)
        grad_sesgo = self._clip(grad.sum(axis=0))

        self._paso = self.optimizador.nuevo_paso()
        self._decaer_lr()
        self.optimizador.aplicar("pesos", self.pesos, grad_pesos, self.lr_actual, self._paso)
        self.optimizador.aplicar("sesgo", self.sesgo, grad_sesgo, self.lr_actual, self._paso)

        grad_entrada = (grad @ self.pesos.T) * self.factor_escala
        self.historial_gradientes.append(grad_entrada)
        self._emit("backward", {"norma": float(np.linalg.norm(grad))})
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
            "metodo": self.metodo,
            "factor_escala": self.factor_escala,
            "optimizador": self.optimizador.algoritmo,
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
            info["params_norm"] = {
                k: None if v is None else np.asarray(v).ravel().tolist()
                for k, v in self.params_norm.items()
            }
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        return self.obtener_estadisticas(completas=True)

    def verificar_estabilidad(self) -> Dict[str, Any]:
        pesos_ok = self.pesos is not None
        pesos_finitos = bool(pesos_ok and np.all(np.isfinite(self.pesos)))
        sesgo_finitos = bool(self.sesgo is not None and np.all(np.isfinite(self.sesgo)))
        forma_ok = bool(pesos_ok and self.pesos.shape == (self.input_size, self.output_size))
        stats_ok = all(
            v is None or np.all(np.isfinite(v)) for v in self.params_norm.values()
        )
        return {
            "pesos_inicializados": pesos_ok,
            "pesos_finitos": pesos_finitos,
            "sesgo_finitos": sesgo_finitos,
            "forma_correcta": forma_ok,
            "stats_finitas": bool(stats_ok),
            "estable": bool(pesos_finitos and sesgo_finitos and forma_ok and stats_ok),
        }

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def resetear(self, completo: bool = False) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.historial_loss.clear()
        self.historial_lr.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.mejor_loss = float("inf")
        self._paso = 0
        self.optimizador.reiniciar()
        self._cache_entrada = None
        self._cache_norm = None
        if completo:
            self.pesos = None
            self.sesgo = None
            self.normalizador.reiniciar()
            self.inicializar_pesos()