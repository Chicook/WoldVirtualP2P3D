"""RF_SL_SBRTM_RF_SL1_4_1.py
Neuronas especializadas en redes neuronales MLP (RF_SL - SBRTM - RF - 2026).
=============================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
de ``NeuralNetworkOptimizer`` (que no tenia imports, base, serializacion ni
validacion) manteniendo su API historica y mejorando el calculo numerico:

  * ``NeuralNetworkOptimizer``: red neuronal totalmente conectada.
      - Una o varias capas ocultas (``capas_ocultas``); por defecto una sola
        capa lineal, igual que el fragmento original.
      - Inicializacion He / Xavier / LeCun segun la activacion, con generador
        local (``seed``) para que el entrenamiento sea determinista.
      - Activaciones estables: relu, leaky_relu, elu, selu, gelu, swish,
        sigmoid, tanh, softmax y linear.
      - Perdidas: MSE, MAE, Huber, log-cosh, entropia cruzada binaria y
        entropia cruzada softmax. Todas con su gradiente analitico y
        normalizacion por numero de elementos.
      - Retropropagacion real con la derivada de la activacion de salida y de
        cada capa oculta (el fragmento original la omitia).
      - Optimizadores correctos: Adam/AdamW (primer y segundo momento con
        correccion de sesgo), SGD, momentum y RMSProp.
      - Recorte global de norma, weight decay desacoplado y dropout invertido.
      - Horarios de tasa de aprendizaje: constant, cosine, linear, step y
        exponential.
      - Mini-lotes, validacion, early stopping con rollback al mejor modelo,
        metricas (MSE, RMSE, MAE, R2, accuracy, precision, recall, F1) y
        serializacion robusta compatible con checkpoints antiguos.

  * ``NeuralNetworkOptimizer.NucleoDiferenciable``: **clase anidada** que
      fusiona en un solo objeto las funciones matematicas del modulo:
      activacion + derivada, perdida + gradiente, recorte de gradiente,
      paso de optimizador, horario de learning rate y metricas. La clase
      exterior delega en ella y mantiene los metodos historicos.

  * ``NeuronaMLP``: nombre recomendado por la convencion del proyecto. Usa
      una capa oculta de 32 neuronas por defecto para ser un MLP real.

  * Utilidades: ``crear_neurona``, ``tipos_disponibles``,
      ``entrenar_y_evaluar``, ``benchmark_modelo``, ``guardar_modelo``,
      ``cargar_modelo`` y ``demo``.

Referencias
-----------
- AdamW: decoupled weight decay regularization (Loshchilov & Hutter, 2019).
- He et al. (2015), inicializacion para ReLU; Glorot & Bengio (2010),
  inicializacion Xavier.
- GELU (Hendrycks & Gimpel, 2016) y aproximacion tanh.
- Dropout invertido (Srivastava et al., 2014).

Uso
---
    from RF_SL_SBRTM_RF_SL1_4_1 import NeuronaMLP

    modelo = NeuronaMLP(input_size=3, output_size=1, capas_ocultas=(32, 16))
    modelo.fit(X, y, epochs=200, batch_size=32, validation_split=0.2)
    print(modelo.evaluate(X, y))
    print(modelo.summary())
"""

from __future__ import annotations

import logging
import math
import pickle
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

__version__ = "2026.1.0"


# ---------------------------------------------------------------------------
# Configuracion global
# ---------------------------------------------------------------------------
LUCIA_NN_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "capas_ocultas": (),
    "learning_rate": 1e-3,
    "momentum": 0.9,
    "weight_decay": 1e-4,
    "clip_norm": 5.0,
    "activation": "relu",
    "dropout": 0.0,
    "loss": "mse",
    "huber_delta": 1.0,
    "optimizer": "adamw",
    "beta1": 0.9,
    "beta2": 0.999,
    "epsilon": 1e-8,
    "lr_schedule": "constant",
    "min_lr": 1e-6,
    "epochs": 100,
    "batch_size": 64,
    "early_stopping": 20,
}


# ---------------------------------------------------------------------------
# Base compartida (importada, no redefinida)
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_rfsl_base.RF_SL_SNRTM__rfsl_base1 import (
        NeuronaMemoriaBase,
    )
except (ImportError, ValueError):  # pragma: no cover - depende del contexto
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_BASE = "_rf_snrtm_base_import_nn"
    _modulo_base = _sys.modules.get(_CLAVE_BASE)
    if _modulo_base is None:
        _directorio_rf_sl = _os.path.dirname(
            _os.path.dirname(_os.path.abspath(__file__))
        )
        for _carpeta in ("RF_SL_SBRTM_RF_rfsl_base", "RF_SL_SBRTM_RF"):
            _ruta_base = _os.path.join(
                _directorio_rf_sl, _carpeta, "RF_SL_SNRTM__rfsl_base1.py"
            )
            if not _os.path.exists(_ruta_base):
                continue
            _especificacion = _ilu.spec_from_file_location(_CLAVE_BASE, _ruta_base)
            if _especificacion is None or _especificacion.loader is None:
                continue
            _modulo_base = _ilu.module_from_spec(_especificacion)
            _sys.modules[_CLAVE_BASE] = _modulo_base
            _especificacion.loader.exec_module(_modulo_base)
            break
    if _modulo_base is not None:
        NeuronaMemoriaBase = _modulo_base.NeuronaMemoriaBase  # type: ignore[no-redef]
    else:  # Ultimo recurso: base local minima para no romper la importacion.
        from collections import deque

        class NeuronaMemoriaBase:  # type: ignore[no-redef]
            """Base de neurona con memoria acotada (fallback minimo)."""

            def __init__(self, input_size: int, output_size: int,
                         nombre: str = "Neurona"):
                self.input_size = int(input_size)
                self.output_size = int(output_size)
                self.nombre = str(nombre)
                self.pesos: Optional[np.ndarray] = None
                self.sesgo: Optional[np.ndarray] = None
                self.historial_activaciones = deque(maxlen=100)
                self.historial_gradientes = deque(maxlen=100)
                self.historial_perdidas = deque(maxlen=500)
                self.pasos = 0

            def inicializar_pesos(self) -> None:
                raise NotImplementedError

            def forward(self, e: np.ndarray) -> np.ndarray:
                raise NotImplementedError

            def registrar_perdida(self, perdida: float) -> None:
                self.historial_perdidas.append(float(perdida))

            def obtener_estadisticas(self) -> Dict[str, Any]:
                return {
                    'nombre': self.nombre,
                    'input_size': self.input_size,
                    'output_size': self.output_size,
                    'pasos': self.pasos,
                    'historial_perdidas_len': len(self.historial_perdidas),
                }

            def info(self) -> str:
                return (f"{self.nombre}(in={self.input_size},"
                        f"out={self.output_size},pasos={self.pasos})")

            def params_count(self) -> int:
                total = 0
                if self.pesos is not None:
                    total += int(np.size(self.pesos))
                if self.sesgo is not None:
                    total += int(np.size(self.sesgo))
                return total

            def _arreglos_parametros(self) -> List[np.ndarray]:
                return [np.asarray(p, dtype=np.float64)
                        for p in (self.pesos, self.sesgo) if p is not None]

            def verificar_estabilidad(self) -> Dict[str, Any]:
                problemas = []
                for indice, arreglo in enumerate(self._arreglos_parametros()):
                    if arreglo.size and not np.all(np.isfinite(arreglo)):
                        problemas.append(f"parametro #{indice} no finito")
                return {'estable': not problemas, 'problemas': problemas,
                        'n_parametros': self.params_count()}


# ---------------------------------------------------------------------------
# Utilidades numericas
# ---------------------------------------------------------------------------
def _sigmoide(x: np.ndarray) -> np.ndarray:
    """Sigmoide numericamente estable (sin desbordar exp)."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


def _softmax(x: np.ndarray) -> np.ndarray:
    """Softmax estable por filas (resta del maximo)."""
    z = np.asarray(x, dtype=np.float64)
    z = z - np.max(z, axis=-1, keepdims=True)
    exponencial = np.exp(z)
    denominador = np.maximum(np.sum(exponencial, axis=-1, keepdims=True), 1e-300)
    return exponencial / denominador


def _norma_global(arreglos: Sequence[np.ndarray]) -> float:
    """Norma L2 conjunta de varios arreglos (sin desbordar)."""
    total = 0.0
    for arreglo in arreglos:
        datos = np.asarray(arreglo, dtype=np.float64).ravel()
        if datos.size:
            total += float(np.dot(datos, datos))
    return math.sqrt(max(0.0, total))


# ---------------------------------------------------------------------------
# Red neuronal MLP
# ---------------------------------------------------------------------------
class NeuralNetworkOptimizer(NeuronaMemoriaBase):
    """Red neuronal totalmente conectada con optimizadores modernos.

    Mantiene los atributos y metodos de la version historica
    (``_learning_rate``, ``_momentum``, ``_weight_decay``, ``_clip_norm``,
    ``_activation``, ``_dropout_rate``, ``_is_fitted``, ``_velocity_w``,
    ``_velocity_b``, ``_convergence_history``, ``_training_time``, ``fit``,
    ``predict``, ``save``/``load``...) y anade capas ocultas opcionales y un
    nucleo matematico unificado.

    Parametros
    ----------
    input_size, output_size:
        Dimensiones de entrada y salida.
    capas_ocultas:
        Tupla con el numero de neuronas de cada capa oculta. Vacia (por
        defecto) reproduce la red de una sola capa del modulo legado.
    activacion:
        Activacion de las capas ocultas.
    activacion_salida:
        Activacion de la salida. Si es ``None`` se infiere de la perdida
        (``sigmoid`` para BCE, ``softmax`` para entropia cruzada softmax).
    perdida:
        ``mse``, ``mae``, ``huber``, ``log_cosh``,
        ``binary_cross_entropy`` o ``softmax_cross_entropy``.
    optimizador:
        ``adamw`` (por defecto), ``adam``, ``momentum``, ``sgd`` o
        ``rmsprop``.
    lr_schedule:
        ``constant``, ``cosine``, ``linear``, ``step`` o ``exponential``.
    seed:
        Semilla del generador local. ``None`` usa ``LUCIA_NN_CONFIG``.
    """

    # ------------------------------------------------------------------
    # Clase anidada: fusion de las funciones matematicas
    # ------------------------------------------------------------------
    class NucleoDiferenciable:
        """Nucleo matematico unificado de la red neuronal.

        Fusiona activacion, derivada, perdida, gradiente, recorte, paso de
        optimizador, horario de learning rate y metricas. Al ser una clase
        anidada se accede como ``NeuralNetworkOptimizer.NucleoDiferenciable``
        (o ``modelo.NucleoDiferenciable``) sin contaminar el espacio de
        nombres del modulo.
        """

        ACTIVACIONES: Tuple[str, ...] = (
            "relu", "leaky_relu", "elu", "selu", "gelu", "swish",
            "sigmoid", "tanh", "softmax", "linear",
        )
        PERDIDAS: Tuple[str, ...] = (
            "mse", "mae", "huber", "log_cosh",
            "binary_cross_entropy", "softmax_cross_entropy",
        )
        OPTIMIZADORES: Tuple[str, ...] = (
            "adamw", "adam", "momentum", "sgd", "rmsprop",
        )
        EPS = 1e-12

        def __init__(self, activacion: str = "relu", perdida: str = "mse",
                     huber_delta: float = 1.0,
                     activacion_salida: Optional[str] = None) -> None:
            self.activacion = self._normalizar_activacion(activacion)
            self.perdida_nombre = self._normalizar_perdida(perdida)
            self.huber_delta = max(1e-12, float(huber_delta))
            self.activacion_salida = (
                self._normalizar_activacion(activacion_salida)
                if activacion_salida not in (None, "", "auto") else None
            )
            self.llamadas = 0

        # -- normalizacion de nombres ---------------------------------
        @classmethod
        def _normalizar_activacion(cls, nombre: Optional[str]) -> str:
            clave = str(nombre or "linear").strip().lower().replace("-", "_")
            alias = {
                "none": "linear", "identidad": "linear", "identity": "linear",
                "leakyrelu": "leaky_relu", "lrelu": "leaky_relu",
                "silu": "swish", "gelu_aprox": "gelu",
            }
            clave = alias.get(clave, clave)
            if clave not in cls.ACTIVACIONES:
                raise ValueError(
                    f"Activacion desconocida: {nombre!r}. "
                    f"Usa una de {cls.ACTIVACIONES}"
                )
            return clave

        @classmethod
        def _normalizar_perdida(cls, nombre: Optional[str]) -> str:
            clave = str(nombre or "mse").strip().lower().replace("-", "_")
            alias = {
                "l2": "mse", "cuadratica": "mse",
                "l1": "mae", "absoluta": "mae",
                "logcosh": "log_cosh",
                "bce": "binary_cross_entropy",
                "cross_entropy": "binary_cross_entropy",
                "entropia_cruzada": "binary_cross_entropy",
                "categorical_cross_entropy": "softmax_cross_entropy",
                "cce": "softmax_cross_entropy",
            }
            clave = alias.get(clave, clave)
            if clave not in cls.PERDIDAS:
                raise ValueError(
                    f"Perdida desconocida: {nombre!r}. "
                    f"Usa una de {cls.PERDIDAS}"
                )
            return clave

        @classmethod
        def _normalizar_optimizador(cls, nombre: Optional[str]) -> str:
            clave = str(nombre or "adamw").strip().lower().replace("-", "")
            alias = {
                "adam": "adam", "adamw": "adamw", "adamweightdecay": "adamw",
                "momentum": "momentum", "sgd momentum": "momentum",
                "sgd": "sgd", "gradiente": "sgd", "rmsprop": "rmsprop",
            }
            clave = alias.get(clave, clave)
            if clave not in cls.OPTIMIZADORES:
                raise ValueError(
                    f"Optimizador desconocido: {nombre!r}. "
                    f"Usa uno de {cls.OPTIMIZADORES}"
                )
            return clave

        # -- activaciones y derivadas ---------------------------------
        def activar(self, z: np.ndarray,
                    nombre: Optional[str] = None) -> np.ndarray:
            """Aplica la activacion indicada (por defecto, la de la red)."""
            x = np.asarray(z, dtype=np.float64)
            nombre = self._normalizar_activacion(
                self.activacion if nombre is None else nombre
            )
            if nombre == "relu":
                return np.maximum(x, 0.0)
            if nombre == "leaky_relu":
                return np.where(x > 0.0, x, 0.01 * x)
            if nombre == "elu":
                return np.where(x > 0.0, x, np.expm1(np.minimum(x, 0.0)))
            if nombre == "selu":
                alfa = 1.6732632423543772
                escala = 1.0507009873554805
                return escala * np.where(
                    x > 0.0, x, alfa * np.expm1(np.minimum(x, 0.0))
                )
            if nombre == "gelu":
                interior = 0.7978845608028654 * (x + 0.044715 * x ** 3)
                return 0.5 * x * (1.0 + np.tanh(interior))
            if nombre == "swish":
                return x * _sigmoide(x)
            if nombre == "sigmoid":
                return _sigmoide(x)
            if nombre == "tanh":
                return np.tanh(x)
            if nombre == "softmax":
                return _softmax(x)
            return x

        def derivada(self, z: np.ndarray, salida: Optional[np.ndarray] = None,
                     nombre: Optional[str] = None) -> np.ndarray:
            """Derivada elemento a elemento respecto de la preactivacion.

            Para ``softmax`` la derivada no es diagonal: usa
            :meth:`gradiente_preactivacion`, que aplica el jacobiano-vector.
            """
            x = np.asarray(z, dtype=np.float64)
            nombre = self._normalizar_activacion(
                self.activacion if nombre is None else nombre
            )
            if nombre == "relu":
                return (x > 0.0).astype(np.float64)
            if nombre == "leaky_relu":
                return np.where(x > 0.0, 1.0, 0.01)
            if nombre == "elu":
                return np.where(x > 0.0, 1.0,
                                np.exp(np.minimum(x, 0.0)))
            if nombre == "selu":
                alfa = 1.6732632423543772
                escala = 1.0507009873554805
                return escala * np.where(
                    x > 0.0, 1.0, alfa * np.exp(np.minimum(x, 0.0))
                )
            if nombre == "gelu":
                interior = 0.7978845608028654 * (x + 0.044715 * x ** 3)
                tangente = np.tanh(interior)
                return 0.5 * (1.0 + tangente) + (
                    0.5 * x * (1.0 - tangente ** 2)
                    * 0.7978845608028654 * (1.0 + 3.0 * 0.044715 * x ** 2)
                )
            if nombre == "swish":
                s = _sigmoide(x)
                return s + x * s * (1.0 - s)
            if nombre == "sigmoid":
                s = _sigmoide(x) if salida is None else np.asarray(salida)
                return s * (1.0 - s)
            if nombre == "tanh":
                t = np.tanh(x) if salida is None else np.asarray(salida)
                return 1.0 - t ** 2
            return np.ones_like(x)

        def gradiente_preactivacion(
            self, z: np.ndarray, gradiente: np.ndarray,
            salida: Optional[np.ndarray] = None,
            nombre: Optional[str] = None,
        ) -> np.ndarray:
            """Convierte dL/dsalida en dL/dz aplicando la regla de la cadena."""
            nombre = self._normalizar_activacion(
                self.activacion if nombre is None else nombre
            )
            g = np.asarray(gradiente, dtype=np.float64)
            if nombre == "softmax":
                s = self.activar(z, "softmax") if salida is None else salida
                return s * (g - np.sum(g * s, axis=-1, keepdims=True))
            return g * self.derivada(z, salida, nombre)

        # -- perdidas y gradientes ------------------------------------
        def perdida(self, pred: np.ndarray, objetivo: np.ndarray,
                    nombre: Optional[str] = None) -> float:
            """Perdida media (todas las perdidas son medias)."""
            p = np.asarray(pred, dtype=np.float64)
            t = np.asarray(objetivo, dtype=np.float64)
            if p.shape != t.shape:
                if p.size == t.size:
                    t = t.reshape(p.shape)
                else:
                    t = np.broadcast_to(t, p.shape)
            tipo = self._normalizar_perdida(
                self.perdida_nombre if nombre is None else nombre
            )
            error = p - t
            if tipo == "mse":
                return float(np.mean(error ** 2))
            if tipo == "mae":
                return float(np.mean(np.abs(error)))
            if tipo == "huber":
                absoluto = np.abs(error)
                delta = self.huber_delta
                cuadratico = np.minimum(absoluto, delta)
                return float(np.mean(0.5 * cuadratico ** 2
                                     + delta * (absoluto - cuadratico)))
            if tipo == "log_cosh":
                absoluto = np.abs(error)
                return float(np.mean(
                    absoluto + np.log1p(np.exp(-2.0 * absoluto)) - math.log(2.0)
                ))
            if tipo == "binary_cross_entropy":
                probabilidad = np.clip(p, self.EPS, 1.0 - self.EPS)
                return float(-np.mean(
                    t * np.log(probabilidad)
                    + (1.0 - t) * np.log1p(-probabilidad)
                ))
            probabilidad = np.clip(p, self.EPS, 1.0)
            if probabilidad.ndim == 1:
                probabilidad = probabilidad.reshape(1, -1)
                t = np.asarray(t).reshape(probabilidad.shape)
            return float(-np.mean(np.sum(t * np.log(probabilidad), axis=1)))

        def gradiente(self, pred: np.ndarray, objetivo: np.ndarray,
                      nombre: Optional[str] = None) -> np.ndarray:
            """Gradiente de la perdida respecto de la prediccion."""
            p = np.asarray(pred, dtype=np.float64)
            t = np.asarray(objetivo, dtype=np.float64)
            if p.shape != t.shape:
                if p.size == t.size:
                    t = t.reshape(p.shape)
                else:
                    t = np.broadcast_to(t, p.shape)
            tipo = self._normalizar_perdida(
                self.perdida_nombre if nombre is None else nombre
            )
            size = max(1, p.size)
            error = p - t
            if tipo == "mse":
                return 2.0 * error / size
            if tipo == "mae":
                return np.sign(error) / size
            if tipo == "huber":
                return np.clip(error, -self.huber_delta,
                               self.huber_delta) / size
            if tipo == "log_cosh":
                return np.tanh(error) / size
            if tipo == "binary_cross_entropy":
                probabilidad = np.clip(p, self.EPS, 1.0 - self.EPS)
                return (probabilidad - t) / (
                    probabilidad * (1.0 - probabilidad) * size
                )
            if p.ndim == 1:
                p = p.reshape(1, -1)
                t = np.asarray(t).reshape(p.shape)
            return (p - t) / max(1, p.shape[0])

        def perdida_y_gradiente(
            self, pred: np.ndarray, objetivo: np.ndarray,
            nombre: Optional[str] = None,
        ) -> Tuple[float, np.ndarray, bool]:
            """Devuelve (perdida, gradiente, gradiente_es_respecto_logit)."""
            tipo = self._normalizar_perdida(
                self.perdida_nombre if nombre is None else nombre
            )
            return (
                self.perdida(pred, objetivo, tipo),
                self.gradiente(pred, objetivo, tipo),
                tipo == "softmax_cross_entropy",
            )

        def es_perdida_logit(self, nombre: Optional[str] = None) -> bool:
            tipo = self._normalizar_perdida(
                self.perdida_nombre if nombre is None else nombre
            )
            return tipo == "softmax_cross_entropy"

        # -- recorte y paso de optimizador ----------------------------
        def recortar(self, gradiente: np.ndarray, max_norm: float) -> np.ndarray:
            """Recorta un gradiente por norma L2 global."""
            g = np.asarray(gradiente, dtype=np.float64)
            if max_norm is None or max_norm <= 0.0:
                return g
            norma = float(np.linalg.norm(g))
            if norma > max_norm:
                return g * (max_norm / (norma + self.EPS))
            return g

        def actualizar(
            self,
            parametros: Sequence[np.ndarray],
            gradientes: Sequence[np.ndarray],
            estado: Dict[str, Any],
            *,
            algoritmo: str = "adamw",
            lr: float = 1e-3,
            momentum: float = 0.9,
            beta1: float = 0.9,
            beta2: float = 0.999,
            eps: float = 1e-8,
            weight_decay: float = 0.0,
            max_norm: float = 0.0,
        ) -> float:
            """Actualiza los parametros in-place y devuelve la norma del gradiente.

            El recorte es global: se calcula la norma conjunta de todos los
            tensores y se escala el conjunto, no cada tensor por separado.
            """
            if len(parametros) != len(gradientes):
                raise ValueError(
                    "El numero de parametros y gradientes no coincide: "
                    f"{len(parametros)} != {len(gradientes)}"
                )
            preparados: List[np.ndarray] = []
            suma_cuadrados = 0.0
            for parametro, gradiente in zip(parametros, gradientes):
                p = np.asarray(parametro, dtype=np.float64)
                g = np.asarray(gradiente, dtype=np.float64)
                if p.shape != g.shape:
                    raise ValueError(
                        f"Gradiente incompatible: {g.shape} != {p.shape}"
                    )
                preparados.append(g)
                suma_cuadrados += float(np.sum(g * g))
            norma = math.sqrt(max(0.0, suma_cuadrados))
            if max_norm and max_norm > 0.0 and norma > max_norm:
                factor = max_norm / (norma + self.EPS)
                preparados = [g * factor for g in preparados]

            clave = self._normalizar_optimizador(algoritmo)
            t = int(estado.get("t", 0)) + 1
            estado["t"] = t

            claves = ()
            if clave in ("adam", "adamw"):
                claves = ("m", "v")
            elif clave in ("momentum", "rmsprop"):
                claves = ("v",)
            for nombre_estado in claves:
                lista = estado.get(nombre_estado)
                valida = (
                    isinstance(lista, list)
                    and len(lista) == len(parametros)
                    and all(np.shape(a) == np.shape(p)
                            for a, p in zip(lista, parametros))
                )
                if not valida:
                    estado[nombre_estado] = [
                        np.zeros_like(p, dtype=np.float64) for p in parametros
                    ]

            for indice, (parametro, gradiente) in enumerate(
                zip(parametros, preparados)
            ):
                if clave in ("adam", "adamw"):
                    m = estado["m"][indice]
                    v = estado["v"][indice]
                    m *= beta1
                    m += (1.0 - beta1) * gradiente
                    v *= beta2
                    v += (1.0 - beta2) * gradiente * gradiente
                    m_hat = m / (1.0 - beta1 ** t)
                    v_hat = v / (1.0 - beta2 ** t)
                    direccion = m_hat / (np.sqrt(v_hat) + eps)
                    if clave == "adamw":
                        if weight_decay > 0.0:
                            parametro -= lr * weight_decay * parametro
                    elif weight_decay > 0.0:
                        direccion = direccion + weight_decay * parametro
                    parametro -= lr * direccion
                elif clave == "momentum":
                    v = estado["v"][indice]
                    v *= momentum
                    v += gradiente
                    if weight_decay > 0.0:
                        v += weight_decay * parametro
                    parametro -= lr * v
                elif clave == "rmsprop":
                    v = estado["v"][indice]
                    v *= beta2
                    v += (1.0 - beta2) * gradiente * gradiente
                    direccion = gradiente
                    if weight_decay > 0.0:
                        direccion = direccion + weight_decay * parametro
                    parametro -= lr * direccion / (np.sqrt(v) + eps)
                else:  # sgd
                    if weight_decay > 0.0:
                        parametro -= lr * (gradiente
                                           + weight_decay * parametro)
                    else:
                        parametro -= lr * gradiente
            return norma

        # -- horario de learning rate --------------------------------
        def tasa_aprendizaje(
            self, paso: int, total_pasos: int,
            estrategia: str = "constant", base_lr: float = 1e-3,
            min_lr: float = 0.0,
        ) -> float:
            """Tasa de aprendizaje para el paso indicado (0-based)."""
            total = max(1, int(total_pasos))
            actual = max(0, int(paso))
            progreso = min(1.0, actual / total)
            clave = str(estrategia or "constant").strip().lower()
            if clave in ("constant", "constante", "fijo"):
                valor = base_lr
            elif clave in ("cosine", "coseno"):
                valor = min_lr + 0.5 * (base_lr - min_lr) * (
                    1.0 + math.cos(math.pi * progreso)
                )
            elif clave in ("linear", "lineal"):
                valor = min_lr + (base_lr - min_lr) * (1.0 - progreso)
            elif clave in ("step", "escalon"):
                valor = base_lr * (0.5 ** (actual // 20))
            elif clave in ("exponential", "exponencial"):
                valor = base_lr * (0.95 ** actual)
            else:
                raise ValueError(
                    f"Horario desconocido: {estrategia!r}. Usa constant, "
                    "cosine, linear, step o exponential"
                )
            return float(max(min_lr, valor))

        # -- metricas -------------------------------------------------
        def metricas(self, pred: np.ndarray,
                     objetivo: np.ndarray) -> Dict[str, float]:
            """Metricas de regresion robustas y finitas."""
            p = np.asarray(pred, dtype=np.float64)
            t = np.asarray(objetivo, dtype=np.float64)
            if p.shape != t.shape:
                if p.size == t.size:
                    t = t.reshape(p.shape)
                else:
                    t = np.broadcast_to(t, p.shape)
            error = p - t
            mse = float(np.mean(error ** 2))
            varianza = float(np.sum((t - np.mean(t)) ** 2))
            if varianza > self.EPS:
                r2 = float(1.0 - np.sum(error ** 2) / varianza)
            elif mse <= self.EPS:
                r2 = 1.0
            else:
                r2 = 0.0
            n_muestras = int(p.shape[0]) if p.ndim > 0 else 1
            n_salidas = int(p.size // max(1, n_muestras))
            return {
                'mse': mse,
                'rmse': float(math.sqrt(max(0.0, mse))),
                'mae': float(np.mean(np.abs(error))),
                'max_error': float(np.max(np.abs(error))) if error.size else 0.0,
                'r2': r2,
                'n_samples': float(n_muestras),
                'n_outputs': float(n_salidas),
            }

        def resumen(self) -> Dict[str, Any]:
            """Configuracion del nucleo (util para logs y serializacion)."""
            return {
                'activacion': self.activacion,
                'activacion_salida': self.activacion_salida,
                'perdida': self.perdida_nombre,
                'huber_delta': self.huber_delta,
                'llamadas': int(self.llamadas),
                'activaciones': list(self.ACTIVACIONES),
                'perdidas': list(self.PERDIDAS),
                'optimizadores': list(self.OPTIMIZADORES),
            }

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuralNetworkOptimizer",
        *,
        capas_ocultas: Sequence[int] = (),
        activacion: str = "relu",
        activacion_salida: Optional[str] = None,
        perdida: str = "mse",
        learning_rate: float = 1e-3,
        momentum: float = 0.9,
        weight_decay: float = 1e-4,
        clip_norm: float = 5.0,
        dropout_rate: float = 0.0,
        optimizador: str = "adamw",
        lr_schedule: str = "constant",
        min_lr: float = 1e-6,
        huber_delta: float = 1.0,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
        seed: Optional[int] = None,
        dtype: str = "float64",
        early_stopping: int = 20,
        **kwargs: Any,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        # Alias tolerantes para consumidores antiguos.
        if "lr" in kwargs and learning_rate == 1e-3:
            learning_rate = float(kwargs.pop("lr"))
        if "dropout" in kwargs and dropout_rate == 0.0:
            dropout_rate = float(kwargs.pop("dropout"))
        if "hidden_layers" in kwargs and not capas_ocultas:
            capas_ocultas = kwargs.pop("hidden_layers")
        if "hidden_sizes" in kwargs and not capas_ocultas:
            capas_ocultas = kwargs.pop("hidden_sizes")
        if "loss" in kwargs and perdida == "mse":
            perdida = kwargs.pop("loss")
        if "activation" in kwargs and activacion == "relu":
            activacion = kwargs.pop("activation")
        if "activation_output" in kwargs and activacion_salida is None:
            activacion_salida = kwargs.pop("activation_output")
        if "optimizer" in kwargs and optimizador == "adamw":
            optimizador = kwargs.pop("optimizer")
        if "schedule" in kwargs and lr_schedule == "constant":
            lr_schedule = kwargs.pop("schedule")
        if kwargs:
            raise TypeError(
                f"Argumentos no reconocidos: {sorted(kwargs)}"
            )

        self.input_size = int(input_size)
        self.output_size = int(output_size)
        if self.input_size <= 0 or self.output_size <= 0:
            raise ValueError("input_size y output_size deben ser positivos")

        capas_ocultas = () if capas_ocultas is None else capas_ocultas
        self.capas_ocultas = tuple(
            int(n) for n in capas_ocultas if int(n) > 0
        )
        if any(int(n) <= 0 for n in capas_ocultas):
            raise ValueError("Todas las capas ocultas deben ser positivas")

        self._dtype = np.dtype(dtype).type
        if not np.issubdtype(np.dtype(dtype), np.floating):
            raise ValueError("dtype debe ser un tipo de coma flotante")

        self._perdida = self.NucleoDiferenciable._normalizar_perdida(perdida)
        self._activation = self.NucleoDiferenciable._normalizar_activacion(
            activacion
        )
        salida = activacion_salida
        if salida in (None, "", "auto"):
            if self._perdida == "binary_cross_entropy":
                salida = "sigmoid"
            elif self._perdida == "softmax_cross_entropy":
                salida = "softmax"
            else:
                # Regresion: salida lineal (el fragmento original aplicaba
                # ReLU a la salida, lo que impide predecir valores negativos).
                salida = "linear"
        self._activacion_salida = (
            self.NucleoDiferenciable._normalizar_activacion(salida)
            if salida not in (None, "", "auto") else None
        )

        self._learning_rate = float(learning_rate)
        if self._learning_rate <= 0.0:
            raise ValueError("learning_rate debe ser positivo")
        self._momentum = float(momentum)
        if not 0.0 <= self._momentum < 1.0:
            raise ValueError("momentum debe estar en [0, 1)")
        self._weight_decay = float(weight_decay)
        if self._weight_decay < 0.0:
            raise ValueError("weight_decay no puede ser negativo")
        self._clip_norm = float(clip_norm)
        if self._clip_norm < 0.0:
            raise ValueError("clip_norm no puede ser negativo (0 lo desactiva)")
        self._dropout_rate = float(dropout_rate)
        if not 0.0 <= self._dropout_rate < 1.0:
            raise ValueError("dropout_rate debe estar en [0, 1)")
        self._optimizador = self.NucleoDiferenciable._normalizar_optimizador(
            optimizador
        )
        self._lr_schedule = str(lr_schedule or "constant").strip().lower()
        self._min_lr = float(min_lr)
        if self._min_lr < 0.0:
            raise ValueError("min_lr no puede ser negativo")
        self._huber_delta = float(huber_delta)
        self._beta1 = float(beta1)
        self._beta2 = float(beta2)
        if not 0.0 <= self._beta1 < 1.0:
            raise ValueError("beta1 debe estar en [0, 1)")
        if not 0.0 <= self._beta2 < 1.0:
            raise ValueError("beta2 debe estar en [0, 1)")
        self._epsilon = float(epsilon)
        if self._epsilon <= 0.0:
            raise ValueError("epsilon debe ser positivo")
        self._early_stopping = max(0, int(early_stopping))

        self._seed = int(
            LUCIA_NN_CONFIG["random_seed"] if seed is None else seed
        )
        self._rng = np.random.default_rng(self._seed)

        self._nucleo = self.NucleoDiferenciable(
            activacion=self._activation,
            perdida=self._perdida,
            huber_delta=self._huber_delta,
            activacion_salida=self._activacion_salida,
        )

        self._capas: List[Dict[str, np.ndarray]] = []
        self._cache: Optional[Dict[str, Any]] = None
        self._estado_opt: Dict[str, Any] = {}
        self._velocity_w: Optional[np.ndarray] = None
        self._velocity_b: Optional[np.ndarray] = None
        self._adam_m_w: Optional[np.ndarray] = None
        self._adam_v_w: Optional[np.ndarray] = None
        self._adam_t: int = 0
        self._convergence_history: List[float] = []
        self._historial_epocas: List[float] = []
        self._historial_validacion: List[float] = []
        self._ultima_perdida: Optional[float] = None
        self._mejor_perdida: Optional[float] = None
        self._training_time: float = 0.0
        self._is_fitted: bool = False
        self._lr_actual: float = self._learning_rate

        self.inicializar_pesos()

    # ------------------------------------------------------------------
    # Inicializacion y estructura
    # ------------------------------------------------------------------
    def inicializar_pesos(self) -> None:
        """Inicializa todas las capas con He / Xavier / LeCun."""
        dimensiones = [self.input_size, *self.capas_ocultas, self.output_size]
        capas: List[Dict[str, np.ndarray]] = []
        for indice in range(len(dimensiones) - 1):
            fan_in = dimensiones[indice]
            fan_out = dimensiones[indice + 1]
            entrada = fan_in
            if self._activation in (
                "relu", "leaky_relu", "elu", "selu", "gelu", "swish"
            ):
                escala = math.sqrt(2.0 / max(1, entrada))
                pesos = self._rng.normal(0.0, escala, (fan_in, fan_out))
            elif self._activation in ("tanh", "sigmoid"):
                limite = math.sqrt(6.0 / max(1, fan_in + fan_out))
                pesos = self._rng.uniform(-limite, limite, (fan_in, fan_out))
            else:
                escala = math.sqrt(1.0 / max(1, entrada))
                pesos = self._rng.normal(0.0, escala, (fan_in, fan_out))
            sesgo = np.zeros((1, fan_out), dtype=self._dtype)
            capas.append({
                'W': pesos.astype(self._dtype),
                'b': sesgo,
            })
        self._capas = capas
        self.pesos = capas[-1]['W']
        self.sesgo = capas[-1]['b']
        self._velocity_w = np.zeros_like(self.pesos)
        self._velocity_b = np.zeros_like(self.sesgo)
        self._adam_m_w = np.zeros_like(self.pesos)
        self._adam_v_w = np.zeros_like(self.pesos)
        self._adam_t = 0
        self._estado_opt = self._nuevo_estado_optimizador()
        self._cache = None

    def _nuevo_estado_optimizador(self) -> Dict[str, Any]:
        parametros = self._parametros()
        return {
            'm': [np.zeros_like(p, dtype=np.float64) for p in parametros],
            'v': [np.zeros_like(p, dtype=np.float64) for p in parametros],
            't': 0,
        }

    def _copiar_estado_optimizador(self) -> Dict[str, Any]:
        copia: Dict[str, Any] = {}
        for clave, valor in self._estado_opt.items():
            if isinstance(valor, list):
                copia[clave] = [np.array(a, copy=True) for a in valor]
            else:
                copia[clave] = valor
        return copia

    def _parametros(self) -> List[np.ndarray]:
        parametros: List[np.ndarray] = []
        for capa in self._capas:
            parametros.append(capa['W'])
            parametros.append(capa['b'])
        return parametros

    def _asignar_parametros(self, valores: Sequence[np.ndarray]) -> None:
        parametros = self._parametros()
        if len(valores) != len(parametros):
            raise ValueError("Numero de parametros incompatible")
        for destino, origen in zip(parametros, valores):
            destino[...] = np.asarray(origen, dtype=destino.dtype)

    def _activacion_capa(self, indice: int) -> str:
        if (indice == len(self._capas) - 1
                and self._activacion_salida is not None):
            return self._activacion_salida
        return self._activation

    # ------------------------------------------------------------------
    # Validacion de datos
    # ------------------------------------------------------------------
    def _validar_entrada(self, X: Any,
                         permitir_1d: bool = True) -> Tuple[np.ndarray, bool]:
        arreglo = np.asarray(X, dtype=self._dtype)
        unico = False
        if arreglo.ndim == 0:
            if self.input_size != 1 or not permitir_1d:
                raise ValueError("X debe ser una matriz 2D")
            arreglo = arreglo.reshape(1, 1)
            unico = True
        elif arreglo.ndim == 1:
            if not permitir_1d:
                raise ValueError("X debe ser una matriz 2D")
            if arreglo.size != self.input_size:
                raise ValueError(
                    f"X tiene {arreglo.size} caracteristicas y se esperaban "
                    f"{self.input_size}"
                )
            arreglo = arreglo.reshape(1, -1)
            unico = True
        elif arreglo.ndim == 2:
            if arreglo.shape[0] == 0:
                raise ValueError("X no contiene muestras")
            if arreglo.shape[1] != self.input_size:
                raise ValueError(
                    f"X tiene {arreglo.shape[1]} caracteristicas y se "
                    f"esperaban {self.input_size}"
                )
        else:
            raise ValueError("X debe tener 1 o 2 dimensiones")
        if not np.all(np.isfinite(arreglo)):
            arreglo = np.nan_to_num(
                arreglo, nan=0.0, posinf=0.0, neginf=0.0
            )
        return arreglo, unico

    def _validar_objetivo(self, y: Any, n_muestras: int) -> np.ndarray:
        objetivo = np.asarray(y, dtype=self._dtype)
        if objetivo.ndim == 0:
            if self.output_size != 1:
                raise ValueError("y debe ser una matriz 2D")
            objetivo = objetivo.reshape(1, 1)
        elif objetivo.ndim == 1:
            if self.output_size != 1:
                raise ValueError(
                    "Para varias salidas, y debe ser una matriz 2D"
                )
            objetivo = objetivo.reshape(-1, 1)
        elif objetivo.ndim != 2:
            raise ValueError("y debe tener 1 o 2 dimensiones")
        if objetivo.shape[0] != n_muestras:
            raise ValueError(
                "X e y deben tener el mismo numero de muestras: "
                f"{n_muestras} != {objetivo.shape[0]}"
            )
        if objetivo.shape[1] != self.output_size:
            raise ValueError(
                f"y tiene {objetivo.shape[1]} salidas y se esperaban "
                f"{self.output_size}"
            )
        if not np.all(np.isfinite(objetivo)):
            objetivo = np.nan_to_num(
                objetivo, nan=0.0, posinf=0.0, neginf=0.0
            )
        return objetivo

    # ------------------------------------------------------------------
    # Propagacion
    # ------------------------------------------------------------------
    def _propagacion(self, matriz: np.ndarray,
                     entrenamiento: bool = False) -> Tuple[np.ndarray,
                                                           Dict[str, Any]]:
        activacion = matriz
        preactivaciones: List[np.ndarray] = []
        activaciones: List[np.ndarray] = []
        mascaras: List[Optional[np.ndarray]] = []
        n_capas = len(self._capas)
        for indice, capa in enumerate(self._capas):
            z = activacion @ capa['W'] + capa['b']
            nombre = self._activacion_capa(indice)
            salida = self._nucleo.activar(z, nombre)
            mascara: Optional[np.ndarray] = None
            if (entrenamiento and self._dropout_rate > 0.0
                    and indice < n_capas - 1):
                mascara = self._rng.random(salida.shape) >= self._dropout_rate
                salida = salida * mascara / (1.0 - self._dropout_rate)
            preactivaciones.append(z)
            activaciones.append(salida)
            mascaras.append(mascara)
            activacion = salida
        cache = {
            'entrada': matriz,
            'z': preactivaciones,
            'a': activaciones,
            'mascaras': mascaras,
        }
        return activacion, cache

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Propagacion en inferencia; registra la activacion en memoria."""
        matriz, unico = self._validar_entrada(entrada)
        salida, cache = self._propagacion(matriz, entrenamiento=False)
        self._cache = cache
        self.historial_activaciones.append(salida.copy())
        self.pasos += 1
        self._nucleo.llamadas += 1
        return salida[0] if unico else salida

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Prediccion pura (no contamina el historial de entrenamiento)."""
        matriz, unico = self._validar_entrada(X)
        salida, _ = self._propagacion(matriz, entrenamiento=False)
        self._nucleo.llamadas += 1
        return salida[0] if unico else salida

    # ------------------------------------------------------------------
    # Perdida y gradientes
    # ------------------------------------------------------------------
    def compute_loss(self, prediccion: np.ndarray,
                     objetivo: np.ndarray) -> float:
        """Perdida configurada entre prediccion y objetivo (media)."""
        p = np.asarray(prediccion, dtype=self._dtype)
        t = np.asarray(objetivo, dtype=self._dtype)
        if p.shape != t.shape:
            try:
                t = np.broadcast_to(t, p.shape)
            except ValueError:
                if p.size == t.size:
                    t = t.reshape(p.shape)
                else:
                    raise ValueError(
                        f"Formas incompatibles: {p.shape} y {t.shape}"
                    )
        return self._nucleo.perdida(p, t, self._perdida)

    def compute_gradient(self, prediccion: np.ndarray,
                         objetivo: np.ndarray) -> np.ndarray:
        """Gradiente analitico de la perdida respecto de la prediccion."""
        p = np.asarray(prediccion, dtype=self._dtype)
        t = np.asarray(objetivo, dtype=self._dtype)
        if p.shape != t.shape:
            try:
                t = np.broadcast_to(t, p.shape)
            except ValueError:
                if p.size == t.size:
                    t = t.reshape(p.shape)
                else:
                    raise ValueError(
                        f"Formas incompatibles: {p.shape} y {t.shape}"
                    )
        return self._nucleo.gradiente(p, t, self._perdida)

    def apply_gradient_clipping(self, grad: np.ndarray) -> np.ndarray:
        """Recorta un gradiente por su norma L2 (API historica)."""
        return self._nucleo.recortar(grad, self._clip_norm)

    def apply_weight_decay(self) -> None:
        """Weight decay multiplicativo historico (metodo independiente)."""
        if self._weight_decay <= 0.0:
            return
        factor = 1.0 - self._learning_rate * self._weight_decay
        factor = max(0.0, factor)
        for capa in self._capas:
            capa['W'] *= factor

    def _gradientes_completos(
        self, cache: Dict[str, Any], grad_prediccion: np.ndarray,
        es_logit: bool,
    ) -> List[np.ndarray]:
        """Retropropaga por todas las capas y devuelve [dW0, db0, ...]."""
        zs = cache['z']
        activaciones = cache['a']
        mascaras = cache['mascaras']
        n_capas = len(self._capas)
        if not n_capas:
            raise RuntimeError("La red no tiene capas inicializadas")

        gradiente = np.asarray(grad_prediccion, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(1, -1)
        if es_logit:
            delta = gradiente
        else:
            delta = self._nucleo.gradiente_preactivacion(
                zs[-1], gradiente, activaciones[-1],
                self._activacion_capa(n_capas - 1),
            )

        gradientes: List[Optional[np.ndarray]] = [None] * (2 * n_capas)
        for indice in range(n_capas - 1, -1, -1):
            entrada_capa = (cache['entrada'] if indice == 0
                            else activaciones[indice - 1])
            d_pesos = entrada_capa.T @ delta
            d_sesgo = np.sum(delta, axis=0, keepdims=True)
            gradientes[2 * indice] = d_pesos
            gradientes[2 * indice + 1] = d_sesgo
            if indice > 0:
                delta = delta @ self._capas[indice]['W'].T
                mascara = mascaras[indice - 1]
                if mascara is not None:
                    delta = delta * mascara / (
                        1.0 - self._dropout_rate
                    )
                delta = delta * self._nucleo.derivada(
                    zs[indice - 1], activaciones[indice - 1],
                    self._activacion_capa(indice - 1),
                )
        return [g for g in gradientes if g is not None]

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: Optional[np.ndarray] = None,
                 aplicar_derivada: bool = True
                 ) -> Tuple[np.ndarray, np.ndarray]:
        """Gradientes de la capa de salida (API historica).

        Aplica la derivada de la activacion de salida salvo que el gradiente
        ya venga respecto de los logits (entropia cruzada softmax). Para
        entrenar redes con capas ocultas se usa la retropropagacion completa
        de :meth:`train_step`.
        """
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(1, -1)
        if gradiente.ndim != 2:
            raise ValueError("gradiente_salida debe ser 1D o 2D")

        n_capas = len(self._capas)
        cache = self._cache
        if entrada is not None:
            matriz, _ = self._validar_entrada(entrada)
            _, cache = self._propagacion(matriz, entrenamiento=False)
        elif cache is None:
            raise ValueError(
                "No hay cache de forward; proporciona 'entrada'"
            )
        if cache['z'][-1].shape[0] != gradiente.shape[0]:
            raise ValueError(
                "El gradiente no coincide con el numero de muestras del "
                f"forward: {gradiente.shape[0]} != "
                f"{cache['z'][-1].shape[0]}"
            )

        entrada_capa = (cache['a'][-2] if n_capas > 1
                        else cache['entrada'])
        if aplicar_derivada and not self._nucleo.es_perdida_logit(
            self._perdida
        ):
            gradiente = self._nucleo.gradiente_preactivacion(
                cache['z'][-1], gradiente, cache['a'][-1],
                self._activacion_capa(n_capas - 1),
            )
        grad_pesos = entrada_capa.T @ gradiente
        grad_sesgo = np.sum(gradiente, axis=0, keepdims=True)
        self.historial_gradientes.append({
            'pesos': grad_pesos.copy(),
            'norma': _norma_global([grad_pesos, grad_sesgo]),
        })
        return grad_pesos, grad_sesgo

    # ------------------------------------------------------------------
    # Actualizacion de pesos (compatibilidad)
    # ------------------------------------------------------------------
    def update_weights_momentum(self, grad_pesos: np.ndarray,
                                grad_sesgo: np.ndarray) -> None:
        """Actualiza la capa de salida con SGD + momentum (API historica)."""
        g_w = np.asarray(grad_pesos, dtype=np.float64)
        g_b = np.asarray(grad_sesgo, dtype=np.float64)
        if g_w.shape != self.pesos.shape:
            raise ValueError(
                f"Gradiente de pesos incompatible: {g_w.shape} != "
                f"{self.pesos.shape}"
            )
        if g_b.shape != self.sesgo.shape:
            raise ValueError(
                f"Gradiente de sesgo incompatible: {g_b.shape} != "
                f"{self.sesgo.shape}"
            )
        if self._velocity_w is None or self._velocity_w.shape != g_w.shape:
            self._velocity_w = np.zeros_like(g_w)
            self._velocity_b = np.zeros_like(g_b)
        self._velocity_w = self._momentum * self._velocity_w + g_w
        self._velocity_b = self._momentum * self._velocity_b + g_b
        self.pesos -= self._learning_rate * self._velocity_w
        self.sesgo -= self._learning_rate * self._velocity_b

    def update_weights_adam(self, grad_pesos: np.ndarray,
                            grad_sesgo: np.ndarray, t: int = 1,
                            beta1: float = 0.9, beta2: float = 0.999,
                            eps: float = 1e-8) -> None:
        """Adam correcto (momentos + correccion de sesgo) para la salida."""
        g_w = np.asarray(grad_pesos, dtype=np.float64)
        g_b = np.asarray(grad_sesgo, dtype=np.float64)
        if self._adam_m_w is None or self._adam_m_w.shape != g_w.shape:
            self._adam_m_w = np.zeros_like(g_w)
            self._adam_v_w = np.zeros_like(g_w)
        if self._velocity_b is None or self._velocity_b.shape != g_b.shape:
            self._velocity_b = np.zeros_like(g_b)
        self._adam_t = max(int(t), self._adam_t + 1)
        m_w = beta1 * self._adam_m_w + (1.0 - beta1) * g_w
        v_w = beta2 * self._adam_v_w + (1.0 - beta2) * g_w * g_w
        m_b = beta1 * self._velocity_b + (1.0 - beta1) * g_b
        v_b = beta2 * self._velocity_b + (1.0 - beta2) * g_b * g_b
        correccion1 = 1.0 - beta1 ** self._adam_t
        correccion2 = 1.0 - beta2 ** self._adam_t
        self._adam_m_w = m_w
        self._adam_v_w = v_w
        self._velocity_b = m_b
        self.pesos -= (self._learning_rate * (m_w / correccion1)
                       / (np.sqrt(v_w / correccion2) + eps))
        self.sesgo -= (self._learning_rate * (m_b / correccion1)
                       / (np.sqrt(v_b / correccion2) + eps))

    # ------------------------------------------------------------------
    # Entrenamiento
    # ------------------------------------------------------------------
    def train_step(self, entrada: np.ndarray, objetivo: np.ndarray,
                   *, learning_rate: Optional[float] = None
                   ) -> Dict[str, float]:
        """Un paso de gradiente con la perdida y el optimizador configurados."""
        matriz, unico = self._validar_entrada(entrada)
        etiquetas = self._validar_objetivo(
            objetivo, 1 if unico else matriz.shape[0]
        )
        prediccion, cache = self._propagacion(matriz, entrenamiento=True)
        perdida, grad_pred, es_logit = self._nucleo.perdida_y_gradiente(
            prediccion, etiquetas, self._perdida
        )
        gradientes = self._gradientes_completos(cache, grad_pred, es_logit)
        lr = float(self._learning_rate if learning_rate is None
                   else learning_rate)
        norma = self._nucleo.actualizar(
            self._parametros(), gradientes, self._estado_opt,
            algoritmo=self._optimizador,
            lr=lr,
            momentum=self._momentum,
            beta1=self._beta1,
            beta2=self._beta2,
            eps=self._epsilon,
            weight_decay=self._weight_decay,
            max_norm=self._clip_norm,
        )
        self._lr_actual = lr
        anterior = self._ultima_perdida
        self._ultima_perdida = float(perdida)
        mejora = 0.0 if anterior is None else float(anterior - perdida)
        if hasattr(self, "registrar_perdida"):
            self.registrar_perdida(float(perdida))
        self.historial_gradientes.append({
            'pesos': gradientes[-2].copy(),
            'norma': float(norma),
        })
        return {
            'loss': float(perdida),
            'grad_norm': float(norma),
            'improvement': mejora,
            'lr': float(lr),
        }

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 50,
        verbose: bool = False,
        *,
        batch_size: Optional[int] = None,
        validation_split: float = 0.0,
        early_stopping_patience: Optional[int] = None,
        shuffle: bool = True,
        lr_schedule: Optional[str] = None,
        learning_rate: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> List[float]:
        """Entrena la red y devuelve la perdida media de cada epoca.

        Con ``batch_size=None`` se usa descenso de gradiente por lote completo
        (comportamiento historico). ``validation_split`` reserva una fraccion
        final para validacion y ``early_stopping_patience`` detiene el
        entrenamiento restaurando los mejores parametros. ``learning_rate``
        permite fijar la tasa base sin reconstruir el modelo (compatible con
        consumidores que llaman ``fit(X, y, learning_rate=...)``).
        """
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        etiquetas = self._validar_objetivo(y, matriz.shape[0])
        epochs = int(epochs)
        if epochs <= 0:
            raise ValueError("epochs debe ser positivo")
        if not 0.0 <= validation_split < 1.0:
            raise ValueError("validation_split debe estar en [0, 1)")
        if learning_rate is not None:
            tasa = float(learning_rate)
            if tasa <= 0.0:
                raise ValueError("learning_rate debe ser positivo")
            self._learning_rate = tasa
            self._lr_actual = tasa

        generador = np.random.default_rng(
            self._seed if seed is None else int(seed)
        )
        n_muestras = matriz.shape[0]
        indices = generador.permutation(n_muestras)
        n_validacion = (int(round(n_muestras * validation_split))
                        if validation_split > 0.0 else 0)
        n_validacion = min(max(0, n_validacion), max(0, n_muestras - 1))
        if n_validacion > 0:
            indices_validacion = indices[:n_validacion]
            indices_entrenamiento = indices[n_validacion:]
        else:
            indices_validacion = None
            indices_entrenamiento = indices
        X_entreno = matriz[indices_entrenamiento]
        y_entreno = etiquetas[indices_entrenamiento]
        X_validacion = (matriz[indices_validacion]
                        if indices_validacion is not None else None)
        y_validacion = (etiquetas[indices_validacion]
                        if indices_validacion is not None else None)

        n_entreno = X_entreno.shape[0]
        tam_lote = (n_entreno if batch_size is None
                    else max(1, min(int(batch_size), n_entreno)))
        estrategia = (self._lr_schedule if lr_schedule is None
                      else str(lr_schedule).strip().lower())
        total_pasos = max(1, epochs * math.ceil(n_entreno / tam_lote))
        paciencia = (
            self._early_stopping if early_stopping_patience is None
            else max(0, int(early_stopping_patience))
        )

        self._convergence_history = []
        self._historial_epocas = []
        self._historial_validacion = []
        self._mejor_perdida = None
        mejor_parametros: Optional[List[np.ndarray]] = None
        mejor_estado_opt: Optional[Dict[str, Any]] = None
        mejor_validacion = float("inf")
        espera = 0
        paso = 0
        perdidas: List[float] = []
        inicio = time.perf_counter()

        for epoca in range(epochs):
            if shuffle and tam_lote < n_entreno:
                orden = generador.permutation(n_entreno)
            else:
                orden = np.arange(n_entreno)
            acumulada = 0.0
            vistos = 0
            for comienzo in range(0, n_entreno, tam_lote):
                lote = orden[comienzo:comienzo + tam_lote]
                lr_paso = self._nucleo.tasa_aprendizaje(
                    paso, total_pasos, estrategia,
                    self._learning_rate, self._min_lr,
                )
                resultado = self.train_step(
                    X_entreno[lote], y_entreno[lote],
                    learning_rate=lr_paso,
                )
                acumulada += resultado['loss'] * len(lote)
                vistos += len(lote)
                paso += 1

            perdida_epoca = acumulada / max(1, vistos)
            perdidas.append(float(perdida_epoca))
            self._convergence_history.append(float(perdida_epoca))
            self._historial_epocas.append(float(perdida_epoca))

            if not np.isfinite(perdida_epoca):
                logger.warning(
                    "%s: perdida no finita en la epoca %d; se detiene",
                    self.nombre, epoca + 1,
                )
                break

            if X_validacion is not None and y_validacion is not None:
                prediccion_validacion = self.predict(X_validacion)
                perdida_validacion = self.compute_loss(
                    prediccion_validacion, y_validacion
                )
                self._historial_validacion.append(
                    float(perdida_validacion)
                )
                if perdida_validacion < mejor_validacion - 1e-12:
                    mejor_validacion = float(perdida_validacion)
                    mejor_parametros = [
                        np.array(p, copy=True) for p in self._parametros()
                    ]
                    mejor_estado_opt = self._copiar_estado_optimizador()
                    espera = 0
                else:
                    espera += 1
                if paciencia and espera >= paciencia:
                    if verbose:
                        logger.info(
                            "%s: early stopping en epoca %d "
                            "(mejor validacion=%.6f)",
                            self.nombre, epoca + 1, mejor_validacion,
                        )
                    break

            if verbose and (epoca + 1) % 10 == 0:
                logger.info(
                    "NN Epoch %d, loss=%.6f, lr=%.6g",
                    epoca + 1, perdida_epoca, self._lr_actual,
                )

        if mejor_parametros is not None:
            self._asignar_parametros(mejor_parametros)
            if mejor_estado_opt is not None:
                self._estado_opt = mejor_estado_opt
            self._mejor_perdida = mejor_validacion
        elif perdidas:
            self._mejor_perdida = float(np.min(perdidas))

        self._training_time = time.perf_counter() - inicio
        self._is_fitted = True
        return perdidas

    def train(self, X: np.ndarray, y: np.ndarray,
              epochs: Optional[int] = None, verbose: bool = False,
              **kwargs: Any) -> Dict[str, Any]:
        """Alias de ``fit`` que devuelve un resumen del entrenamiento."""
        historial = self.fit(
            X, y, epochs=100 if epochs is None else epochs,
            verbose=verbose, **kwargs,
        )
        return {
            'historial': historial,
            'perdida_final': float(historial[-1]) if historial else None,
            'mejor_perdida': self._mejor_perdida,
            'tiempo': self._training_time,
        }

    # ------------------------------------------------------------------
    # Evaluacion
    # ------------------------------------------------------------------
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Metricas de regresion y, si aplica, de clasificacion."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        objetivo = self._validar_objetivo(y, matriz.shape[0])
        prediccion = self.predict(matriz)
        metricas: Dict[str, Any] = self._nucleo.metricas(
            prediccion, objetivo
        )
        metricas['loss'] = self.compute_loss(prediccion, objetivo)
        metricas['n_samples'] = int(matriz.shape[0])
        metricas['n_outputs'] = int(self.output_size)

        if self._perdida == "binary_cross_entropy":
            probabilidad = np.clip(
                np.asarray(prediccion, dtype=np.float64), 0.0, 1.0
            ).reshape(-1)
            real = np.asarray(objetivo, dtype=np.float64).reshape(-1)
            binaria = (probabilidad >= 0.5).astype(np.float64)
            aciertos = float(np.mean(binaria == real))
            verdaderos_positivos = float(np.sum((binaria == 1.0)
                                                & (real == 1.0)))
            falsos_positivos = float(np.sum((binaria == 1.0)
                                            & (real == 0.0)))
            falsos_negativos = float(np.sum((binaria == 0.0)
                                            & (real == 1.0)))
            precision = (verdaderos_positivos
                         / max(1.0, verdaderos_positivos + falsos_positivos))
            recall = (verdaderos_positivos
                      / max(1.0, verdaderos_positivos + falsos_negativos))
            f1 = (2.0 * precision * recall / max(1e-12, precision + recall))
            metricas['accuracy'] = aciertos
            metricas['precision'] = float(precision)
            metricas['recall'] = float(recall)
            metricas['f1'] = float(f1)
        elif self._perdida == "softmax_cross_entropy":
            predicho = np.argmax(np.asarray(prediccion), axis=1)
            real = np.argmax(np.asarray(objetivo), axis=1)
            metricas['accuracy'] = float(np.mean(predicho == real))
        return metricas

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """Coeficiente R2 (o accuracy en clasificacion binaria)."""
        metricas = self.evaluate(X, y)
        if self._perdida == "binary_cross_entropy":
            return float(metricas.get('accuracy', 0.0))
        return float(metricas.get('r2', 0.0))

    # ------------------------------------------------------------------
    # Informacion y estabilidad
    # ------------------------------------------------------------------
    def params_count(self) -> int:
        """Numero total de parametros entrenables."""
        return int(sum(np.size(p) for p in self._parametros()))

    def _arreglos_parametros(self) -> List[np.ndarray]:
        return [np.asarray(p, dtype=np.float64) for p in self._parametros()]

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'mlp',
            'capas': [self.input_size, *self.capas_ocultas,
                      self.output_size],
            'n_capas': len(self._capas),
            'n_parametros': self.params_count(),
            'learning_rate': self._learning_rate,
            'lr_actual': self._lr_actual,
            'momentum': self._momentum,
            'weight_decay': self._weight_decay,
            'clip_norm': self._clip_norm,
            'activation': self._activation,
            'activation_salida': self._activacion_salida,
            'perdida': self._perdida,
            'optimizador': self._optimizador,
            'lr_schedule': self._lr_schedule,
            'dropout_rate': self._dropout_rate,
            'is_fitted': self._is_fitted,
            'training_time': self._training_time,
            'convergence_history_len': len(self._convergence_history),
            'mejor_perdida': self._mejor_perdida,
            'nucleo': self._nucleo.resumen(),
        })
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
            stats['primera_loss'] = float(self._convergence_history[0])
        if self._historial_validacion:
            stats['final_val_loss'] = float(self._historial_validacion[-1])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprobaciones numericas basicas (todas booleanas)."""
        ok: Dict[str, bool] = {
            'pesos_inicializados': bool(self._capas)
            and self.pesos is not None,
        }
        if self._capas and self.pesos is not None:
            parametros = self._arreglos_parametros()
            maximo = max(float(np.max(np.abs(p))) if p.size else 0.0
                         for p in parametros)
            ok['pesos_no_explosivos'] = maximo < 1e6
            ok['pesos_no_nan'] = all(
                not bool(np.any(np.isnan(p))) for p in parametros
            )
            ok['pesos_no_inf'] = all(
                not bool(np.any(np.isinf(p))) for p in parametros
            )
            ok['estado_entrenado'] = bool(self._is_fitted)
            ok['velocidad_inicializada'] = self._velocity_w is not None
            ok['momentos_inicializados'] = bool(
                self._estado_opt.get('m') or self._estado_opt.get('v')
            ) or self._optimizador in ('sgd', 'momentum', 'rmsprop')
            ok['gradientes_finitos'] = all(
                np.isfinite(registro.get('norma', 0.0))
                for registro in self.historial_gradientes
            )
            ok['perdidas_finitas'] = all(
                math.isfinite(float(v)) for v in self._convergence_history
            )
            ok['cache_consistente'] = (
                self._cache is None
                or len(self._cache.get('z', [])) == len(self._capas)
            )
        ok['estable'] = all(ok.values())
        return ok

    # ------------------------------------------------------------------
    # Serializacion y configuracion
    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        """Guarda un checkpoint completo (incluye optimizador y RNG)."""
        estado = {
            'version': __version__,
            'tipo': 'NeuralNetworkOptimizer',
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'capas_ocultas': list(self.capas_ocultas),
            'capas': [
                {'W': np.array(capa['W'], copy=True),
                 'b': np.array(capa['b'], copy=True)}
                for capa in self._capas
            ],
            'pesos': self.pesos,
            'sesgo': self.sesgo,
            'dtype': self._dtype.__name__,
            'activation': self._activation,
            'activacion_salida': self._activacion_salida,
            'perdida': self._perdida,
            'huber_delta': self._huber_delta,
            'learning_rate': self._learning_rate,
            'momentum': self._momentum,
            'weight_decay': self._weight_decay,
            'clip_norm': self._clip_norm,
            'dropout_rate': self._dropout_rate,
            'optimizador': self._optimizador,
            'lr_schedule': self._lr_schedule,
            'min_lr': self._min_lr,
            'beta1': self._beta1,
            'beta2': self._beta2,
            'epsilon': self._epsilon,
            'early_stopping': self._early_stopping,
            'is_fitted': self._is_fitted,
            'pasos': self.pasos,
            'training_time': self._training_time,
            'convergence_history': list(self._convergence_history),
            'historial_epocas': list(self._historial_epocas),
            'historial_validacion': list(self._historial_validacion),
            'mejor_perdida': self._mejor_perdida,
            'estado_opt': self._estado_opt,
            'velocity_w': self._velocity_w,
            'velocity_b': self._velocity_b,
            'adam_m_w': self._adam_m_w,
            'adam_v_w': self._adam_v_w,
            'adam_t': self._adam_t,
            'seed': self._seed,
            'rng_state': self._rng.bit_generator.state,
        }
        with open(filepath, 'wb') as archivo:
            pickle.dump(estado, archivo, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        """Carga un checkpoint nuevo o uno antiguo de una sola capa."""
        with open(filepath, 'rb') as archivo:
            estado = pickle.load(archivo)
        if not isinstance(estado, dict):
            raise TypeError("El fichero no contiene un checkpoint valido")

        self._dtype = np.dtype(estado.get('dtype', 'float64')).type
        capas_guardadas = estado.get('capas')
        if capas_guardadas:
            self._capas = [
                {
                    'W': np.asarray(capa['W'], dtype=self._dtype),
                    'b': np.asarray(capa['b'], dtype=self._dtype)
                    .reshape(1, -1),
                }
                for capa in capas_guardadas
            ]
            ocultas = estado.get('capas_ocultas')
            if ocultas is None:
                ocultas = [
                    capa['W'].shape[1] for capa in self._capas[:-1]
                ]
            self.capas_ocultas = tuple(int(n) for n in ocultas)
        else:
            pesos = estado.get('pesos')
            sesgo = estado.get('sesgo')
            if pesos is None or sesgo is None:
                raise ValueError("El checkpoint no contiene pesos")
            pesos = np.asarray(pesos, dtype=self._dtype)
            if pesos.ndim != 2:
                raise ValueError("Los pesos deben ser una matriz 2D")
            sesgo = np.asarray(sesgo, dtype=self._dtype).reshape(1, -1)
            self._capas = [{'W': pesos, 'b': sesgo}]
            self.capas_ocultas = ()

        self.pesos = self._capas[-1]['W']
        self.sesgo = self._capas[-1]['b']
        self.input_size = int(
            estado.get('input_size', self._capas[0]['W'].shape[0])
        )
        self.output_size = int(
            estado.get('output_size', self._capas[-1]['W'].shape[1])
        )
        self.nombre = str(estado.get('nombre', self.nombre))
        if self._capas[0]['W'].shape[0] != self.input_size:
            raise ValueError("Dimension de entrada incompatible en checkpoint")
        if self._capas[-1]['W'].shape[1] != self.output_size:
            raise ValueError("Dimension de salida incompatible en checkpoint")

        self._activation = self.NucleoDiferenciable._normalizar_activacion(
            estado.get('activation', 'relu')
        )
        self._perdida = self.NucleoDiferenciable._normalizar_perdida(
            estado.get('perdida', 'mse')
        )
        salida = estado.get('activacion_salida')
        self._activacion_salida = (
            self.NucleoDiferenciable._normalizar_activacion(salida)
            if salida not in (None, "", "auto") else None
        )
        self._huber_delta = float(estado.get('huber_delta', 1.0))
        self._learning_rate = float(estado.get('learning_rate', 1e-3))
        self._momentum = float(estado.get('momentum', 0.9))
        self._weight_decay = float(estado.get('weight_decay', 1e-4))
        self._clip_norm = float(estado.get('clip_norm', 5.0))
        self._dropout_rate = float(estado.get('dropout_rate', 0.0))
        self._optimizador = (
            self.NucleoDiferenciable._normalizar_optimizador(
                estado.get('optimizador', 'adamw')
            )
        )
        self._lr_schedule = str(estado.get('lr_schedule', 'constant'))
        self._min_lr = float(estado.get('min_lr', 1e-6))
        self._beta1 = float(estado.get('beta1', 0.9))
        self._beta2 = float(estado.get('beta2', 0.999))
        self._epsilon = float(estado.get('epsilon', 1e-8))
        self._early_stopping = int(estado.get('early_stopping', 20))
        self._lr_actual = self._learning_rate
        self._seed = int(estado.get('seed', LUCIA_NN_CONFIG["random_seed"]))
        self._rng = np.random.default_rng(self._seed)
        rng_state = estado.get('rng_state')
        if isinstance(rng_state, dict):
            try:
                self._rng.bit_generator.state = rng_state
            except (ValueError, TypeError):  # pragma: no cover
                self._rng = np.random.default_rng(self._seed)

        self._nucleo = self.NucleoDiferenciable(
            activacion=self._activation,
            perdida=self._perdida,
            huber_delta=self._huber_delta,
            activacion_salida=self._activacion_salida,
        )
        self._is_fitted = bool(estado.get('is_fitted', False))
        self.pasos = int(estado.get('pasos', 0))
        self._training_time = float(estado.get('training_time', 0.0))
        self._convergence_history = [
            float(v) for v in estado.get('convergence_history', [])
        ]
        self._historial_epocas = [
            float(v) for v in estado.get('historial_epocas', [])
        ]
        self._historial_validacion = [
            float(v) for v in estado.get('historial_validacion', [])
        ]
        mejor = estado.get('mejor_perdida')
        self._mejor_perdida = None if mejor is None else float(mejor)
        self._ultima_perdida = (
            self._convergence_history[-1]
            if self._convergence_history else None
        )

        estado_opt = estado.get('estado_opt')
        if (isinstance(estado_opt, dict)
                and (estado_opt.get('m') or estado_opt.get('v'))):
            self._estado_opt = estado_opt
        else:
            self._estado_opt = self._nuevo_estado_optimizador()
        self._velocity_w = self._arreglo_o_ceros(
            estado.get('velocity_w'), self.pesos
        )
        self._velocity_b = self._arreglo_o_ceros(
            estado.get('velocity_b'), self.sesgo
        )
        self._adam_m_w = self._arreglo_o_ceros(
            estado.get('adam_m_w'), self.pesos
        )
        self._adam_v_w = self._arreglo_o_ceros(
            estado.get('adam_v_w'), self.pesos
        )
        self._adam_t = int(estado.get('adam_t', 0))
        self._cache = None

    @staticmethod
    def _arreglo_o_ceros(valor: Any,
                         referencia: np.ndarray) -> np.ndarray:
        if valor is None:
            return np.zeros_like(referencia)
        arreglo = np.asarray(valor, dtype=np.float64)
        if arreglo.shape != referencia.shape:
            return np.zeros_like(referencia)
        return arreglo

    def get_config(self) -> Dict[str, Any]:
        """Configuracion completa (reproducible) del modelo."""
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'capas_ocultas': list(self.capas_ocultas),
            'capas': [self.input_size, *self.capas_ocultas,
                      self.output_size],
            'activacion': self._activation,
            'activacion_salida': self._activacion_salida,
            'perdida': self._perdida,
            'huber_delta': self._huber_delta,
            'learning_rate': self._learning_rate,
            'momentum': self._momentum,
            'weight_decay': self._weight_decay,
            'clip_norm': self._clip_norm,
            'dropout_rate': self._dropout_rate,
            'optimizador': self._optimizador,
            'lr_schedule': self._lr_schedule,
            'min_lr': self._min_lr,
            'beta1': self._beta1,
            'beta2': self._beta2,
            'epsilon': self._epsilon,
            'early_stopping': self._early_stopping,
            'seed': self._seed,
            'dtype': self._dtype.__name__,
        }

    def summary(self) -> str:
        cfg = self.get_config()
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {cfg['nombre']} ===",
            (f"Capas: {cfg['capas']} | parametros: "
             f"{self.params_count()}"),
            (f"LR: {cfg['learning_rate']}, Momentum: {cfg['momentum']}, "
             f"Optimizador: {cfg['optimizador']}"),
            (f"Activation: {cfg['activacion']} -> "
             f"{cfg['activacion_salida'] or cfg['activacion']}, "
             f"Loss: {cfg['perdida']}, Weight decay: {cfg['weight_decay']}"),
            (f"Dropout: {cfg['dropout_rate']}, Clip: {cfg['clip_norm']}, "
             f"Schedule: {cfg['lr_schedule']}"),
            (f"Fitted: {stats.get('is_fitted', False)}, "
             f"Final loss: {stats.get('final_loss', 'N/A')}"),
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"


# ---------------------------------------------------------------------------
# Alias recomendado por la convencion del proyecto
# ---------------------------------------------------------------------------
class NeuronaMLP(NeuralNetworkOptimizer):
    """MLP con una capa oculta de 32 neuronas por defecto.

    Es la clase principal recomendada por la convencion ``Neurona<Algoritmo>``.
    Acepta todos los parametros de :class:`NeuralNetworkOptimizer`.
    """

    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuronaMLP",
        capas_ocultas: Sequence[int] = (32,),
        **kwargs: Any,
    ) -> None:
        super().__init__(
            input_size=input_size,
            output_size=output_size,
            nombre=nombre,
            capas_ocultas=capas_ocultas,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Fabrica, utilidades y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "mlp", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuralNetworkOptimizer:
    """Fabrica una red neuronal por nombre.

    Tipos: ``mlp``/``nn`` (capa oculta por defecto), ``compat`` (red de una
    sola capa con la API historica de ``NeuralNetworkOptimizer``).
    """
    clave = str(tipo or "mlp").strip().lower().replace("-", "_")
    if clave in ("mlp", "neurona_mlp", "nn", "neural_network",
                 "red_neuronal"):
        return NeuronaMLP(input_size=input_size, output_size=output_size,
                          **kwargs)
    if clave in ("compat", "neural_network_optimizer", "optimizer",
                 "optimizador"):
        return NeuralNetworkOptimizer(
            input_size=input_size, output_size=output_size, **kwargs
        )
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: mlp, nn, compat"
    )


def tipos_disponibles() -> List[str]:
    """Nombres aceptados por :func:`crear_neurona`."""
    return ["mlp", "nn", "compat"]


def create_neural_network_optimizer(
    input_size: int = 4, output_size: int = 8,
    **kwargs: Any,
) -> NeuralNetworkOptimizer:
    """Fabrica historica de RF_SL1_4 (se conserva por compatibilidad)."""
    return NeuralNetworkOptimizer(
        input_size=input_size, output_size=output_size, **kwargs
    )


def entrenar_y_evaluar(modelo: NeuralNetworkOptimizer, X: np.ndarray,
                       y: np.ndarray, epochs: int = 100,
                       **kwargs: Any) -> Dict[str, Any]:
    """Entrena y devuelve historial y metricas en una sola llamada."""
    historial = modelo.fit(X, y, epochs=epochs, **kwargs)
    return {
        'modelo': modelo,
        'historial': historial,
        'metricas': modelo.evaluate(X, y),
        'perdida_final': float(historial[-1]) if historial else float('nan'),
    }


def benchmark_modelo(modelo: NeuralNetworkOptimizer, X: np.ndarray,
                     repeticiones: int = 5) -> Dict[str, float]:
    """Mide el tiempo de inferencia (media, minimo, maximo y desviacion)."""
    tiempos: List[float] = []
    for _ in range(max(1, int(repeticiones))):
        inicio = time.perf_counter()
        modelo.predict(X)
        tiempos.append(time.perf_counter() - inicio)
    return {
        'avg_time': float(np.mean(tiempos)),
        'min_time': float(np.min(tiempos)),
        'max_time': float(np.max(tiempos)),
        'std_time': float(np.std(tiempos)),
        'n_runs': int(len(tiempos)),
    }


def guardar_modelo(modelo: NeuralNetworkOptimizer, ruta: str) -> None:
    """Serializa el objeto completo (pickle)."""
    with open(ruta, 'wb') as archivo:
        pickle.dump(modelo, archivo, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuralNetworkOptimizer:
    """Carga un modelo serializado con :func:`guardar_modelo`."""
    with open(ruta, 'rb') as archivo:
        modelo = pickle.load(archivo)
    if not isinstance(modelo, NeuralNetworkOptimizer):
        raise TypeError("El fichero no contiene una red neuronal")
    return modelo


# ---------------------------------------------------------------------------
# Demostracion
# ---------------------------------------------------------------------------
def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_4_1.py``)."""
    generador = np.random.default_rng(2026)
    n_muestras = 360
    X = generador.uniform(-2.0, 2.0, size=(n_muestras, 3))
    y = (
        np.sin(2.0 * X[:, 0]) + X[:, 1] ** 2 - 0.8 * X[:, 2]
        + 0.05 * generador.normal(size=n_muestras)
    ).reshape(-1, 1)

    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_4_1 :: Red neuronal MLP (v%s)" % __version__)
    print("Muestras:", X.shape[0], "| caracteristicas:", X.shape[1])
    print("=" * 78)

    regresion = crear_neurona(
        "mlp", input_size=3, output_size=1,
        capas_ocultas=(32, 16), learning_rate=0.01,
        dropout_rate=0.05, seed=7,
    )
    historial = regresion.fit(
        X, y, epochs=120, batch_size=32, validation_split=0.2,
        early_stopping_patience=20,
    )
    metricas = regresion.evaluate(X, y)
    print("%-12s MSE=%.6f MAE=%.6f R2=%.4f | capas=%s | params=%d"
          % ("regresion", metricas['mse'], metricas['mae'],
             metricas['r2'], regresion.get_config()['capas'],
             regresion.params_count()))
    print("Epocas entrenadas:", len(historial),
          "| perdida final: %.6f" % historial[-1])

    clasificacion = crear_neurona(
        "mlp", input_size=3, output_size=1, capas_ocultas=(24,),
        perdida="binary_cross_entropy", learning_rate=0.01, seed=11,
    )
    y_binaria = (
        (X[:, 0] ** 2 + X[:, 1] ** 2 - 0.8 * X[:, 2]) > 0.5
    ).astype(np.float64)
    clasificacion.fit(
        X, y_binaria, epochs=100, batch_size=32,
        validation_split=0.2, early_stopping_patience=15,
    )
    metricas_clf = clasificacion.evaluate(X, y_binaria)
    print("%-12s accuracy=%.4f F1=%.4f | params=%d"
          % ("clasificacion", metricas_clf['accuracy'],
             metricas_clf['f1'], clasificacion.params_count()))
    print("Estabilidad:", regresion.verificar_estabilidad())
    print("Benchmark:", benchmark_modelo(regresion, X, repeticiones=3))
    print("=" * 78)
    return {
        'regresion': metricas,
        'clasificacion': metricas_clf,
        'historial': historial,
    }


__all__ = [
    'NeuronaMemoriaBase',
    'NeuralNetworkOptimizer',
    'NeuronaMLP',
    'crear_neurona',
    'tipos_disponibles',
    'create_neural_network_optimizer',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_NN_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
