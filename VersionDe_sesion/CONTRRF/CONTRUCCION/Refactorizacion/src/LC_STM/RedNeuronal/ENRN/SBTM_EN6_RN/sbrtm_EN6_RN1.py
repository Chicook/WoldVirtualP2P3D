"""EN6 / RN1 - Neurona de entrada con dropout (mascara invertida).

Modulo autocontenido: solo depende de numpy. La configuracion global vive en
``LUCIA_CONFIG`` y puede ajustarse con ``actualizar_config``.

API publica preservada de la version original:
    dropout_rate, dropout_entrada, factor_escala, modo_entrenamiento,
    inicializar_pesos, forward, backward, obtener_estadisticas,
    verificar_estabilidad, fijar_dropout, entrenar, evaluar.

Mejoras matematicas:
  - Dropout invertido: E[mask] = 1, por lo que la salida en entrenamiento y
    en evaluacion tiene la misma esperanza (no hay que reescalar al evaluar).
  - Mascaras generadas con ``Generator.random`` y escalado en una sola
    operacion vectorizada (float32 nativo si la precision es float32).
  - Optimizador unificado Adam / AdamW / SGD / SGD con momento, con
    correccion de sesgo y weight decay desacoplado en AdamW.

Ejemplo:
    >>> neurona = NeuronaEntradaDropout(8, 4, dropout_rate=0.2)
    >>> salida = neurona.forward(np.zeros((3, 8)))
    >>> gradiente = neurona.backward(np.ones_like(salida))
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

__all__ = [
    "LUCIA_CONFIG",
    "actualizar_config",
    "NeuronaEntradaBase",
    "NeuronaEntradaDropout",
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
    duplicar la medicion en forward y backward.
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


class NeuronaEntradaDropout(NeuronaEntradaBase):
    """EN6 dropout eficiente: mascara invertida, Adam/SGD, clipping y cache.

    Las clases anidadas aíslan las dos matematicas del modulo:
    ``Dropout`` (mascaras) y ``Optimizador`` (regla de actualizacion).
    """

    # ------------------------------------------------------------------
    class Dropout:
        """Mascara de dropout invertida (escala 1/(1-rate))."""

        def __init__(self, rng: np.random.Generator, dtype: np.dtype, activo: bool = True):
            self.rng = rng
            self.dtype = np.dtype(dtype)
            self.activo = bool(activo)

        def mascara(self, forma: Tuple[int, ...], tasa: float,
                    activo: Optional[bool] = None) -> Optional[np.ndarray]:
            """Devuelve la mascara escalada o ``None`` si el dropout es identidad."""
            aplicar = self.activo if activo is None else bool(activo)
            tasa = float(tasa)
            if not aplicar or tasa <= 0.0:
                return None
            if tasa >= 1.0:
                return np.zeros(forma, dtype=self.dtype)
            conserva = 1.0 - tasa
            viva = (self.rng.random(forma) >= tasa).astype(self.dtype)
            return (viva / conserva).astype(self.dtype, copy=False)

        @staticmethod
        def aplicar(x: np.ndarray, mask: Optional[np.ndarray]) -> np.ndarray:
            return x if mask is None else x * mask

        @staticmethod
        def esperanza(mask: Optional[np.ndarray]) -> float:
            """Factor esperado de la mascara (1.0 para dropout invertido)."""
            return 1.0 if mask is None else float(np.mean(mask))

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
                 nombre: str = "NeuronaEntradaDropout",
                 dropout_rate: float = 0.1,
                 factor_escala: float = 1.0,
                 modo_entrenamiento: bool = True,
                 dropout_entrada: float = 0.0,
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
        self.modo_entrenamiento = bool(modo_entrenamiento)
        self.varianza_real = 0.0
        self.varianza_esperada = 2.0 / max(1, input_size)
        self.lr_base = float(learning_rate or LUCIA_CONFIG.get("default_learning_rate", 0.001))
        self.lr_actual = float(self.lr_base)
        self.grad_clip = float(grad_clip)
        self.lr_decay = float(lr_decay)
        self.lr_min = float(lr_min)
        self.usar_cache_forward = bool(usar_cache_forward)
        self.semilla = semilla if semilla is not None else int(LUCIA_CONFIG.get("random_seed", 42))
        self.rng = np.random.default_rng(self.semilla)

        self.dropout = self.Dropout(self.rng, _dtype(), self.modo_entrenamiento)
        self.optimizador = self.Optimizador(optimizador, beta1, beta2, epsilon, weight_decay)
        self.dropout_rate = float(np.clip(dropout_rate, 0.0, 0.9999))
        self.dropout_entrada = float(np.clip(dropout_entrada, 0.0, 0.9999))

        self._paso = 0
        self._cache_entrada: Optional[np.ndarray] = None
        self._cache_xin: Optional[np.ndarray] = None
        self._cache_mask_in: Optional[np.ndarray] = None
        self._cache_mask_out: Optional[np.ndarray] = None

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
    # Propiedades derivadas
    # ------------------------------------------------------------------
    @property
    def dt(self) -> np.dtype:
        return _dtype()

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

    # ------------------------------------------------------------------
    # Modo y tasas
    # ------------------------------------------------------------------
    def entrenar(self) -> None:
        self.modo_entrenamiento = True
        self.dropout.activo = True

    def evaluar(self) -> None:
        self.modo_entrenamiento = False
        self.dropout.activo = False

    def fijar_dropout(self, salida: Optional[float] = None,
                      entrada: Optional[float] = None) -> None:
        if salida is not None:
            self.dropout_rate = float(np.clip(float(salida), 0.0, 0.9999))
        if entrada is not None:
            self.dropout_entrada = float(np.clip(float(entrada), 0.0, 0.9999))

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

    def _mask(self, forma: Tuple[int, ...], rate: float) -> Optional[np.ndarray]:
        """Compatibilidad: delega en la clase anidada ``Dropout``."""
        return self.dropout.mascara(forma, rate, self.modo_entrenamiento)

    # ------------------------------------------------------------------
    # Parametros
    # ------------------------------------------------------------------
    def inicializar_pesos(self) -> None:
        escala = np.sqrt(2.0 / max(1, self.input_size)) * self.factor_escala
        self.pesos = self.rng.normal(
            0.0, escala, size=(self.input_size, self.output_size),
        ).astype(self.dt)
        self.sesgo = np.zeros(self.output_size, dtype=self.dt)
        self.varianza_real = float(np.var(self.pesos))
        self.varianza_esperada = 2.0 / max(1, self.input_size)
        self.optimizador.reiniciar()
        self._paso = 0
        self._cache_entrada = None
        self._cache_xin = None
        self._cache_mask_in = None
        self._cache_mask_out = None
        self._registrar_norma()
        self._emit("init", {"modo": "he"})

    def _registrar_norma(self) -> None:
        if self.pesos is not None:
            self.norma_pesos_historial.append(float(np.linalg.norm(self.pesos)))

    def penalizacion(self) -> float:
        """Weight decay L2: 0.5 * wd * ||W||^2 (se desacopla en AdamW)."""
        if self.pesos is None or self.weight_decay <= 0.0:
            return 0.0
        w = self.pesos.astype(np.float64).ravel()
        return 0.5 * self.weight_decay * float(np.dot(w, w))

    # ------------------------------------------------------------------
    # Paso del optimizador
    # ------------------------------------------------------------------
    def paso_optimizador(self, grad_pesos: np.ndarray,
                         grad_sesgo: np.ndarray) -> Dict[str, float]:
        """Aplica weight decay acoplado (o desacoplado), clipping y el paso."""
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
        xin = x * self.factor_escala

        mask_in = self.dropout.mascara(xin.shape, self.dropout_entrada,
                                       self.modo_entrenamiento)
        xin_d = self.dropout.aplicar(xin, mask_in)

        z = xin_d @ self.pesos + self.sesgo

        mask_out = self.dropout.mascara(z.shape, self.dropout_rate,
                                        self.modo_entrenamiento)
        salida = self.dropout.aplicar(z, mask_out)

        if self.usar_cache_forward:
            self._cache_entrada = x
            self._cache_xin = xin_d
            self._cache_mask_in = mask_in
            self._cache_mask_out = mask_out
        self.historial_activaciones.append(salida)

        v = float(np.var(salida)) if salida.size else 0.0
        if len(self.historial_activaciones) > 1:
            self.varianza_real = 0.9 * self.varianza_real + 0.1 * v
        else:
            self.varianza_real = v
        self._emit("activacion", {"forma": salida.shape,
                                  "media": float(np.mean(salida))})
        return salida.astype(self.dt)

    @_instrumentar("backward")
    @_requiere_pesos
    def backward(self, g, e=None) -> np.ndarray:
        """Backpropaga aplicando las mismas mascaras del forward cacheado."""
        grad = np.asarray(g, dtype=np.float64)
        if grad.ndim == 1:
            grad = grad.reshape(1, -1)
        if grad.ndim != 2 or grad.shape[1] != self.output_size:
            raise ValueError(f"gradiente dim {grad.shape[-1]} != output_size {self.output_size}")

        if e is not None:
            x = self._preparar(e)
            xin = x * self.factor_escala
            mask_in = self.dropout.mascara(xin.shape, self.dropout_entrada,
                                           self.modo_entrenamiento)
            mask_out = self.dropout.mascara((x.shape[0], self.output_size),
                                            self.dropout_rate, self.modo_entrenamiento)
            xin_d = self.dropout.aplicar(xin, mask_in)
        elif self._cache_xin is not None:
            xin_d = self._cache_xin
            mask_in = self._cache_mask_in
            mask_out = self._cache_mask_out
        else:
            raise RuntimeError("backward sin cache: llama forward o pasa e")

        # La salida se multiplico por la mascara; su gradiente tambien.
        grad = self.dropout.aplicar(grad, mask_out)
        grad = self._clip(grad)

        grad_pesos = self._clip(xin_d.T @ grad)
        grad_sesgo = self._clip(grad.sum(axis=0))
        info = self.paso_optimizador(grad_pesos, grad_sesgo)

        grad_entrada = (grad @ self.pesos.T) * self.factor_escala
        if mask_in is not None:
            grad_entrada = grad_entrada * mask_in

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
            "dropout_rate": self.dropout_rate,
            "dropout_entrada": self.dropout_entrada,
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
            "pesos_inicializados": self.pesos is not None,
        }
        if completas:
            info["historial_loss"] = list(self.historial_loss)
            info["historial_lr"] = list(self.historial_lr)
            info["norma_pesos_historial"] = self.norma_pesos_historial.to_list()
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        return self.obtener_estadisticas(completas=True)

    def verificar_estabilidad(self) -> Dict[str, Any]:
        pesos_ok = self.pesos is not None
        pesos_finitos = bool(pesos_ok and np.all(np.isfinite(self.pesos)))
        sesgo_finitos = bool(self.sesgo is not None and np.all(np.isfinite(self.sesgo)))
        forma_ok = bool(pesos_ok and self.pesos.shape == (self.input_size, self.output_size))
        tasas_ok = bool(0.0 <= self.dropout_rate < 1.0 and 0.0 <= self.dropout_entrada < 1.0)
        return {
            "pesos_inicializados": pesos_ok,
            "pesos_finitos": pesos_finitos,
            "sesgo_finitos": sesgo_finitos,
            "forma_correcta": forma_ok,
            "tasas_validas": tasas_ok,
            "dropout_activo": self.modo_entrenamiento and self.dropout_rate > 0.0,
            "estable": bool(pesos_finitos and sesgo_finitos and forma_ok and tasas_ok),
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
        self._cache_entrada = None
        self._cache_xin = None
        self._cache_mask_in = None
        self._cache_mask_out = None
        if completo:
            self.pesos = None
            self.sesgo = None
            self.inicializar_pesos()

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},sal={self.output_size},"
                f"drop={self.dropout_rate},opt={self.algoritmo})")
