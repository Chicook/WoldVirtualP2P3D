"""RF_SL_SBRTM_RF_SL1_8_1.py
Neuronas especializadas en regresion logistica (RF_SL - SBRTM - RF - 2026).
============================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
(que solo tenia ``SigmoidEngine``, ``LossCalculator``, ``GradientDescent``,
``Regularizer``, ``DecisionBoundary`` y ``FeatureScaler``, sin la neurona
principal) y lo sustituye por una implementacion real de regresion logistica:

  * ``NeuronaRegresionLogistica``: neurona lineal-probabilistica.
      - Clasificacion binaria (sigmoide) y multiclase (softmax).
      - Etiquetas string/one-hot, probabilidades y log-probabilidades estables.
      - Regularizacion L1, L2 y ElasticNet; umbral de decision configurable.
      - Optimizadores SGD, momentum y Adam con correccion de sesgo.
      - Mini-lotes, decaimiento de learning rate y early stopping opcional.
      - Escalado Standard/MinMax/Robust integrado.
      - Metricas binarias y multiclase (accuracy, balanced accuracy,
        precision, recall, F1, log-loss, MSE y matriz de confusion).
      - Serializacion compatible con checkpoints de la API historica.

  * ``NeuronaRegresionLogistica.NucleoLogistico``: **clase anidada** que
      fusiona sigmoide/softmax, perdidas, gradientes, regularizacion,
      optimizadores y metricas.

  * ``LogisticRegressionOptimizer``: adaptador de compatibilidad con la API
      historica de RF_SL1_8 (``train``, ``predict_proba``, ``evaluate``,
      ``set_regularization``, ``set_threshold``, ``get_loss_history``...).

  * Utilidades: ``SigmoidEngine``, ``LossCalculator``, ``GradientDescent``,
      ``Regularizer``, ``DecisionBoundary``, ``FeatureScaler``,
      ``crear_neurona``, ``tipos_disponibles``,
      ``create_logistic_regression_optimizer``, ``entrenar_y_evaluar``,
      ``benchmark_modelo``, ``guardar_modelo``, ``cargar_modelo`` y ``demo``.

Referencias
-----------
- Regresion logistica binaria y softmax multiclase.
- Regularizacion L1/L2/ElasticNet y descenso de gradiente estocastico.
- Adam (Kingma & Ba, 2015).
- Escalado Standard/MinMax/Robust.

Uso
---
    from RF_SL_SBRTM_RF_SL1_8_1 import NeuronaRegresionLogistica

    modelo = NeuronaRegresionLogistica(input_size=3)
    modelo.fit(X, y, epochs=300)
    print(modelo.evaluate(X, y))
    print(modelo.predict_proba(X[:5]))
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
LUCIA_LR_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "learning_rate": 0.01,
    "epochs": 200,
    "batch_size": 32,
    "regularization": "l2",
    "reg_lambda": 0.01,
    "l1_ratio": 0.5,
    "optimizer": "sgd",
    "momentum": 0.9,
    "beta1": 0.9,
    "beta2": 0.999,
    "decay": 0.0,
    "threshold": 0.5,
    "epsilon": 1e-12,
    "scaler": None,
    "early_stopping": 0,
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

    _CLAVE_BASE = "_rf_snrtm_base_import_lr"
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
# Neurona de regresion logistica
# ---------------------------------------------------------------------------
class NeuronaRegresionLogistica(NeuronaMemoriaBase):
    """Clasificador lineal-probabilistico binario y multiclase.

    Parametros
    ----------
    input_size, output_size:
        Dimensiones declaradas (compatibilidad con la jerarquia).
    learning_rate:
        Tasa de aprendizaje base.
    epochs:
        Numero de epocas de entrenamiento.
    batch_size:
        Tamano de mini-lote (``None`` o >= n usa lote completo).
    regularization:
        ``l1``, ``l2`` o ``elasticnet``.
    reg_lambda:
        Intensidad de regularizacion.
    l1_ratio:
        Proporcion L1 en ElasticNet.
    optimizer:
        ``sgd``, ``momentum`` o ``adam``.
    threshold:
        Umbral de decision binario.
    scaler:
        ``standard``, ``minmax``, ``robust`` o ``None``.
    seed:
        Semilla del generador local.
    """

    # ------------------------------------------------------------------
    # Clase anidada: nucleo matematico
    # ------------------------------------------------------------------
    class NucleoLogistico:
        """Fusiona activaciones, perdidas, regularizacion y optimizadores."""

        EPS = 1e-12
        OPTIMIZADORES: Tuple[str, ...] = ("sgd", "momentum", "adam")

        def __init__(self, clip_range: float = 500.0,
                     epsilon: float = 1e-12) -> None:
            self.clip_range = float(clip_range)
            self.epsilon = max(1e-15, float(epsilon))
            self.estado: Dict[str, Any] = {}
            self.reiniciar()

        # -- activaciones --------------------------------------------
        def sigmoide(self, z: np.ndarray) -> np.ndarray:
            """Sigmoide numericamente estable."""
            valores = np.asarray(z, dtype=np.float64)
            limite = np.clip(valores, -self.clip_range, self.clip_range)
            positivo = limite >= 0.0
            resultado = np.empty_like(limite)
            resultado[positivo] = 1.0 / (
                1.0 + np.exp(-limite[positivo])
            )
            exp_z = np.exp(limite[~positivo])
            resultado[~positivo] = exp_z / (1.0 + exp_z)
            return resultado

        @staticmethod
        def derivada_sigmoide(salida: np.ndarray) -> np.ndarray:
            s = np.asarray(salida, dtype=np.float64)
            return s * (1.0 - s)

        @staticmethod
        def logsumexp(valores: np.ndarray, axis: int = 1,
                      keepdims: bool = True) -> np.ndarray:
            datos = np.asarray(valores, dtype=np.float64)
            maximo = np.max(datos, axis=axis, keepdims=True)
            seguro = np.where(np.isfinite(maximo), maximo, 0.0)
            suma = np.sum(np.exp(datos - seguro), axis=axis, keepdims=True)
            resultado = np.log(np.maximum(suma, 1e-300)) + seguro
            return resultado if keepdims else np.squeeze(resultado, axis=axis)

        def softmax(self, z: np.ndarray) -> np.ndarray:
            datos = np.asarray(z, dtype=np.float64)
            if datos.ndim == 1:
                datos = datos.reshape(1, -1)
            exponencial = np.exp(datos - np.max(
                datos, axis=-1, keepdims=True
            ))
            return exponencial / np.maximum(
                np.sum(exponencial, axis=-1, keepdims=True), 1e-300
            )

        def log_softmax(self, z: np.ndarray) -> np.ndarray:
            datos = np.asarray(z, dtype=np.float64)
            if datos.ndim == 1:
                datos = datos.reshape(1, -1)
            return datos - self.logsumexp(datos, axis=1, keepdims=True)

        # -- perdidas -------------------------------------------------
        def perdida_binaria(self, y_true: np.ndarray,
                            y_pred: np.ndarray) -> float:
            real = np.asarray(y_true, dtype=np.float64).ravel()
            pred = np.asarray(y_pred, dtype=np.float64).ravel()
            pred = np.clip(pred, self.epsilon, 1.0 - self.epsilon)
            return float(-np.mean(
                real * np.log(pred) + (1.0 - real) * np.log1p(-pred)
            ))

        def perdida_multiclase(self, y_codificado: np.ndarray,
                               probabilidades: np.ndarray) -> float:
            indices = np.asarray(y_codificado, dtype=int).ravel()
            proba = np.asarray(probabilidades, dtype=np.float64)
            proba = np.clip(proba, self.epsilon, 1.0)
            elegidas = proba[np.arange(indices.size), indices]
            return float(-np.mean(np.log(elegidas)))

        @staticmethod
        def perdida_mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
            return float(np.mean(
                (np.asarray(y_true, dtype=np.float64)
                 - np.asarray(y_pred, dtype=np.float64)) ** 2
            ))

        # -- regularizacion ------------------------------------------
        @staticmethod
        def regularizacion(pesos: np.ndarray, tipo: str,
                           lambda_val: float,
                           l1_ratio: float = 0.5) -> float:
            matriz = np.asarray(pesos, dtype=np.float64)
            lam = max(0.0, float(lambda_val))
            if lam == 0.0:
                return 0.0
            if tipo == "l1":
                return lam * float(np.sum(np.abs(matriz)))
            if tipo == "l2":
                return 0.5 * lam * float(np.sum(matriz ** 2))
            proporcion = min(1.0, max(0.0, float(l1_ratio)))
            return (
                lam * proporcion * float(np.sum(np.abs(matriz)))
                + 0.5 * lam * (1.0 - proporcion)
                * float(np.sum(matriz ** 2))
            )

        @staticmethod
        def gradiente_regularizacion(pesos: np.ndarray, tipo: str,
                                     lambda_val: float,
                                     l1_ratio: float = 0.5) -> np.ndarray:
            matriz = np.asarray(pesos, dtype=np.float64)
            lam = max(0.0, float(lambda_val))
            if lam == 0.0:
                return np.zeros_like(matriz)
            if tipo == "l1":
                return lam * np.sign(matriz)
            if tipo == "l2":
                return lam * matriz
            proporcion = min(1.0, max(0.0, float(l1_ratio)))
            return (
                lam * proporcion * np.sign(matriz)
                + lam * (1.0 - proporcion) * matriz
            )

        # -- optimizadores -------------------------------------------
        def reiniciar(self) -> None:
            self.estado = {
                'velocidad': [],
                'momento': [],
                'varianza': [],
                't': 0,
            }

        def paso(self, parametros: Sequence[np.ndarray],
                 gradientes: Sequence[np.ndarray], *,
                 optimizador: str = "sgd", lr: float = 0.01,
                 momentum: float = 0.9, beta1: float = 0.9,
                 beta2: float = 0.999, epsilon: float = 1e-8,
                 weight_decay: float = 0.0) -> float:
            """Actualiza parametros in-place y devuelve la norma global."""
            if len(parametros) != len(gradientes):
                raise ValueError("Parametros y gradientes incompatibles")
            tipo = str(optimizador or "sgd").strip().lower()
            if tipo not in self.OPTIMIZADORES:
                raise ValueError(
                    f"Optimizador desconocido: {optimizador!r}"
                )
            norma = math.sqrt(sum(
                float(np.sum(np.asarray(g, dtype=np.float64) ** 2))
                for g in gradientes
            ))
            n_parametros = len(parametros)
            if len(self.estado['velocidad']) != n_parametros:
                self.estado['velocidad'] = [
                    np.zeros_like(p, dtype=np.float64) for p in parametros
                ]
                self.estado['momento'] = [
                    np.zeros_like(p, dtype=np.float64) for p in parametros
                ]
                self.estado['varianza'] = [
                    np.zeros_like(p, dtype=np.float64) for p in parametros
                ]
                self.estado['t'] = 0
            self.estado['t'] += 1
            t = int(self.estado['t'])
            for indice, (parametro, gradiente) in enumerate(
                zip(parametros, gradientes)
            ):
                p = np.asarray(parametro, dtype=np.float64)
                g = np.asarray(gradiente, dtype=np.float64)
                if p.shape != g.shape:
                    raise ValueError(
                        f"Gradiente incompatible: {g.shape} != {p.shape}"
                    )
                if tipo == "adam":
                    m = self.estado['momento'][indice]
                    v = self.estado['varianza'][indice]
                    m *= beta1
                    m += (1.0 - beta1) * g
                    v *= beta2
                    v += (1.0 - beta2) * g * g
                    m_hat = m / (1.0 - beta1 ** t)
                    v_hat = v / (1.0 - beta2 ** t)
                    direccion = m_hat / (np.sqrt(v_hat) + epsilon)
                    if weight_decay > 0.0:
                        direccion = direccion + weight_decay * p
                    p -= lr * direccion
                elif tipo == "momentum":
                    v = self.estado['velocidad'][indice]
                    v *= momentum
                    v += g
                    if weight_decay > 0.0:
                        v += weight_decay * p
                    p -= lr * v
                else:
                    if weight_decay > 0.0:
                        p -= lr * (g + weight_decay * p)
                    else:
                        p -= lr * g
            return float(norma)

        # -- metricas -------------------------------------------------
        @staticmethod
        def _codificar(valores: np.ndarray,
                       clases: np.ndarray) -> np.ndarray:
            mapa = {clase: indice for indice, clase in enumerate(clases)}
            return np.array([
                mapa.get(valor, -1) for valor in np.asarray(valores).ravel()
            ], dtype=int)

        def metricas_binarias(self, pred: np.ndarray, real: np.ndarray,
                              proba: Optional[np.ndarray],
                              clases: np.ndarray) -> Dict[str, Any]:
            y_true = self._codificar(real, clases)
            y_pred = self._codificar(pred, clases)
            validos = (y_true >= 0) & (y_pred >= 0)
            aciertos = float(np.mean(
                y_pred[validos] == y_true[validos]
            )) if np.any(validos) else 0.0
            tp = float(np.sum((y_pred == 1) & (y_true == 1)))
            fp = float(np.sum((y_pred == 1) & (y_true == 0)))
            fn = float(np.sum((y_pred == 0) & (y_true == 1)))
            precision = tp / max(1.0, tp + fp)
            recall = tp / max(1.0, tp + fn)
            f1 = 2.0 * precision * recall / max(self.EPS,
                                                precision + recall)
            matriz = np.zeros((2, 2), dtype=int)
            for verdadero, predicho in zip(y_true, y_pred):
                if 0 <= verdadero < 2 and 0 <= predicho < 2:
                    matriz[verdadero, predicho] += 1
            metricas: Dict[str, Any] = {
                'accuracy': aciertos,
                'precision': float(precision),
                'recall': float(recall),
                'f1': float(f1),
                'mse': float(np.mean((y_pred - y_true) ** 2))
                if np.any(validos) else 0.0,
                'n_samples': int(np.asarray(real).size),
                'confusion_matrix': matriz.tolist(),
            }
            if proba is not None:
                probabilidades = np.asarray(proba, dtype=np.float64)
                if probabilidades.ndim == 2 and probabilidades.shape[1] >= 2:
                    p_positiva = np.clip(
                        probabilidades[:, 1], self.epsilon, 1.0 - self.epsilon
                    )
                    elegidas = np.where(
                        y_true == 1, p_positiva, 1.0 - p_positiva
                    )
                    metricas['log_loss'] = float(
                        -np.mean(np.log(np.clip(
                            elegidas, self.epsilon, 1.0
                        )))
                    )
            return metricas

        def metricas_multiclase(self, pred: np.ndarray, real: np.ndarray,
                                proba: Optional[np.ndarray],
                                clases: np.ndarray) -> Dict[str, Any]:
            y_true = self._codificar(real, clases)
            y_pred = self._codificar(pred, clases)
            validos = (y_true >= 0) & (y_pred >= 0)
            aciertos = float(np.mean(
                y_pred[validos] == y_true[validos]
            )) if np.any(validos) else 0.0
            recalls: List[float] = []
            precisiones: List[float] = []
            f1s: List[float] = []
            for clase in range(len(clases)):
                verdadero = y_true == clase
                predicho = y_pred == clase
                if not np.any(verdadero):
                    continue
                tp = float(np.sum(verdadero & predicho))
                fp = float(np.sum(~verdadero & predicho))
                fn = float(np.sum(verdadero & ~predicho))
                recall = tp / max(1.0, tp + fn)
                precision = tp / max(1.0, tp + fp)
                f1 = 2.0 * precision * recall / max(
                    self.EPS, precision + recall
                )
                recalls.append(recall)
                precisiones.append(precision)
                f1s.append(f1)
            matriz = np.zeros((len(clases), len(clases)), dtype=int)
            for verdadero, predicho in zip(y_true, y_pred):
                if (0 <= verdadero < len(clases)
                        and 0 <= predicho < len(clases)):
                    matriz[verdadero, predicho] += 1
            metricas: Dict[str, Any] = {
                'accuracy': aciertos,
                'balanced_accuracy': float(np.mean(recalls))
                if recalls else 0.0,
                'precision_macro': float(np.mean(precisiones))
                if precisiones else 0.0,
                'recall_macro': float(np.mean(recalls))
                if recalls else 0.0,
                'f1_macro': float(np.mean(f1s)) if f1s else 0.0,
                'mse': float(np.mean((y_pred - y_true) ** 2))
                if np.any(validos) else 0.0,
                'n_samples': int(np.asarray(real).size),
                'n_classes': int(len(clases)),
                'confusion_matrix': matriz.tolist(),
            }
            if proba is not None:
                probabilidades = np.asarray(proba, dtype=np.float64)
                indices = np.clip(y_true, 0, probabilidades.shape[1] - 1)
                elegidas = np.clip(
                    probabilidades[np.arange(len(y_true)), indices],
                    self.epsilon, 1.0,
                )
                metricas['log_loss'] = float(-np.mean(np.log(elegidas)))
            return metricas

        def resumen(self) -> Dict[str, Any]:
            return {
                'optimizadores': list(self.OPTIMIZADORES),
                'epsilon': self.epsilon,
                'clip_range': self.clip_range,
            }

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuronaRegresionLogistica",
        *,
        learning_rate: float = 0.01,
        epochs: int = 200,
        batch_size: Optional[int] = 32,
        regularization: str = "l2",
        reg_lambda: float = 0.01,
        l1_ratio: float = 0.5,
        optimizer: str = "sgd",
        momentum: float = 0.9,
        beta1: float = 0.9,
        beta2: float = 0.999,
        decay: float = 0.0,
        threshold: float = 0.5,
        scaler: Optional[str] = None,
        epsilon: float = 1e-12,
        seed: Optional[int] = None,
        early_stopping: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        if "optimizer_type" in kwargs and optimizer == "sgd":
            optimizer = kwargs.pop("optimizer_type")
        if "reg_type" in kwargs and regularization == "l2":
            regularization = kwargs.pop("reg_type")
        if "lambda_val" in kwargs and reg_lambda == 0.01:
            reg_lambda = kwargs.pop("lambda_val")
        if "normalize" in kwargs and scaler is None:
            scaler = "standard" if kwargs.pop("normalize") else None
        if "escalado" in kwargs and scaler is None:
            scaler = kwargs.pop("escalado")
        if "random_state" in kwargs and seed is None:
            seed = kwargs.pop("random_state")
        if kwargs:
            raise TypeError(
                f"Argumentos no reconocidos: {sorted(kwargs)}"
            )

        self.input_size = int(input_size)
        self.output_size = int(output_size)
        if self.input_size <= 0 or self.output_size <= 0:
            raise ValueError("input_size y output_size deben ser positivos")

        self._learning_rate = float(learning_rate)
        if self._learning_rate <= 0.0:
            raise ValueError("learning_rate debe ser positivo")
        self._epochs = max(1, int(epochs))
        self._batch_size = (None if batch_size is None
                            else max(1, int(batch_size)))
        self._regularization = self._normalizar_regularizacion(
            regularization
        )
        self._reg_lambda = max(0.0, float(reg_lambda))
        self._l1_ratio = min(1.0, max(0.0, float(l1_ratio)))
        self._optimizer_type = self._normalizar_optimizador(optimizer)
        self._momentum = float(momentum)
        self._beta1 = float(beta1)
        self._beta2 = float(beta2)
        self._decay = max(0.0, float(decay))
        self._threshold = min(1.0, max(0.0, float(threshold)))
        self._epsilon = max(1e-15, float(epsilon))
        self._early_stopping = max(0, int(early_stopping))
        self._seed = int(
            LUCIA_LR_CONFIG["random_seed"] if seed is None else seed
        )
        self._rng = np.random.default_rng(self._seed)

        self._scaler = self._crear_scaler(scaler)
        self._nucleo = self.NucleoLogistico(
            epsilon=self._epsilon
        )

        self._classes: Optional[np.ndarray] = None
        self._n_classes: int = 0
        self._n_outputs: int = 0
        self._is_fitted: bool = False
        self._convergence_history: List[float] = []
        self._loss_history: List[float] = []
        self._training_time: float = 0.0
        self._accuracy: float = 0.0
        self._n_samples: int = 0

        self.inicializar_pesos()

    @staticmethod
    def _normalizar_regularizacion(nombre: Optional[str]) -> str:
        clave = str(nombre or "l2").strip().lower().replace("-", "_")
        alias = {
            "l1": "l1", "lasso": "l1", "l2": "l2", "ridge": "l2",
            "elasticnet": "elasticnet", "elastic_net": "elasticnet",
            "none": "l2", "ninguna": "l2",
        }
        clave = alias.get(clave, clave)
        if clave not in ("l1", "l2", "elasticnet"):
            raise ValueError(
                f"Regularizacion desconocida: {nombre!r}. Usa l1, l2 o "
                "elasticnet"
            )
        return clave

    @staticmethod
    def _normalizar_optimizador(nombre: Optional[str]) -> str:
        clave = str(nombre or "sgd").strip().lower()
        alias = {
            "sgd": "sgd", "gradiente": "sgd",
            "momentum": "momentum", "momento": "momentum",
            "adam": "adam",
        }
        clave = alias.get(clave, clave)
        if clave not in ("sgd", "momentum", "adam"):
            raise ValueError(
                f"Optimizador desconocido: {nombre!r}. Usa sgd, momentum "
                "o adam"
            )
        return clave

    @staticmethod
    def _crear_scaler(nombre: Any) -> Optional["FeatureScaler"]:
        if nombre is None or nombre is False:
            return None
        if isinstance(nombre, FeatureScaler):
            return nombre
        return FeatureScaler(str(nombre))

    def inicializar_pesos(self, n_outputs: Optional[int] = None) -> None:
        """Inicializa pesos Xavier y sesgo cero."""
        salidas = (self._n_outputs if n_outputs is None
                   else int(n_outputs))
        salidas = max(1, salidas if salidas > 0 else self.output_size)
        limite = math.sqrt(6.0 / max(1, self.input_size + salidas))
        self.pesos = self._rng.uniform(
            -limite, limite, (self.input_size, salidas)
        ).astype(np.float64)
        self.sesgo = np.zeros((1, salidas), dtype=np.float64)
        self._n_outputs = salidas
        if hasattr(self, "_nucleo"):
            self._nucleo.reiniciar()

    def _asegurar_pesos(self, n_outputs: int) -> None:
        if (self.pesos is None
                or self.pesos.ndim != 2
                or self.pesos.shape != (self.input_size, n_outputs)
                or self.sesgo is None
                or self.sesgo.shape != (1, n_outputs)):
            self.inicializar_pesos(n_outputs)

    # ------------------------------------------------------------------
    # Validacion y preparacion
    # ------------------------------------------------------------------
    def _validar_entrada(self, X: Any,
                         permitir_1d: bool = True) -> Tuple[np.ndarray, bool]:
        arreglo = np.asarray(X, dtype=np.float64)
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

    def _transformar_X(self, X: Any, permitir_1d: bool = True
                       ) -> Tuple[np.ndarray, bool]:
        matriz, unico = self._validar_entrada(X, permitir_1d)
        if self._scaler is not None:
            matriz = self._scaler.transform(matriz)
        return matriz, unico

    @staticmethod
    def _es_onehot(objetivo: np.ndarray) -> bool:
        if objetivo.ndim != 2 or objetivo.shape[1] < 2:
            return False
        datos = objetivo.astype(np.float64)
        return bool(
            np.all(datos >= 0.0)
            and np.all(datos <= 1.0)
            and np.allclose(np.sum(datos, axis=1), 1.0)
        )

    def _preparar_objetivo(self, y: Any, n_muestras: int
                           ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        arreglo = np.asarray(y)
        if arreglo.ndim == 0:
            arreglo = arreglo.reshape(1)
        if arreglo.ndim == 2:
            if arreglo.shape[1] == 1:
                arreglo = arreglo.reshape(-1)
            elif self._es_onehot(arreglo):
                arreglo = np.argmax(arreglo, axis=1)
            else:
                raise ValueError(
                    "y debe ser 1D, (n, 1) o una matriz one-hot"
                )
        if arreglo.ndim != 1:
            raise ValueError("y debe ser un vector 1D")
        if arreglo.shape[0] != n_muestras:
            raise ValueError(
                "X e y deben tener el mismo numero de muestras: "
                f"{n_muestras} != {arreglo.shape[0]}"
            )
        if arreglo.size == 0:
            raise ValueError("y no contiene muestras")
        if arreglo.dtype.kind in "fc" and not np.all(
            np.isfinite(arreglo.astype(np.float64))
        ):
            raise ValueError("y contiene valores no finitos")
        try:
            clases, codificado = np.unique(arreglo, return_inverse=True)
        except TypeError as error:
            raise ValueError(
                "Las etiquetas deben ser homogeneas y comparables"
            ) from error
        if len(clases) < 2:
            raise ValueError(
                "La regresion logistica requiere al menos dos clases"
            )
        return codificado.astype(int), arreglo, clases

    # ------------------------------------------------------------------
    # Propagacion
    # ------------------------------------------------------------------
    def _forward_matriz(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        z = X @ self.pesos + self.sesgo
        if self._n_outputs == 1:
            probabilidades = self._nucleo.sigmoide(z)
        else:
            probabilidades = self._nucleo.softmax(z)
        return probabilidades, z

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Propagacion; devuelve probabilidades (n, 1) o (n, clases)."""
        matriz, unico = self._transformar_X(entrada)
        probabilidades, _ = self._forward_matriz(matriz)
        self.historial_activaciones.append(
            np.array(probabilidades, copy=True)
        )
        self.pasos += 1
        return probabilidades[0] if unico else probabilidades

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """Logit o logits de la capa lineal."""
        matriz, unico = self._transformar_X(X)
        _, z = self._forward_matriz(matriz)
        if self._n_outputs == 1:
            salida = z[:, 0]
        else:
            salida = z
        return salida[0] if unico else salida

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilidades (n, 2) en binario o (n, clases) en multiclase."""
        if not self._is_fitted:
            raise RuntimeError("Modelo no entrenado: llama a fit primero")
        matriz, unico = self._transformar_X(X)
        probabilidades, _ = self._forward_matriz(matriz)
        if self._n_outputs == 1:
            p = probabilidades[:, 0]
            salida = np.column_stack([1.0 - p, p])
        else:
            salida = probabilidades
        return salida[0] if unico else salida

    def predict_log_proba(self, X: np.ndarray) -> np.ndarray:
        """Logaritmo de las probabilidades."""
        probabilidades = np.clip(
            self.predict_proba(X), self._epsilon, 1.0
        )
        return np.log(probabilidades)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Etiqueta de clase predicha."""
        probabilidades = self.predict_proba(X)
        if probabilidades.ndim == 1:
            if self._n_outputs == 1:
                indice = int(probabilidades[1] >= self._threshold)
            else:
                indice = int(np.argmax(probabilidades))
            return np.asarray(self._classes)[indice]
        if self._n_outputs == 1:
            indices = (probabilidades[:, 1] >= self._threshold).astype(int)
        else:
            indices = np.argmax(probabilidades, axis=1)
        return np.asarray(self._classes)[indices]

    # ------------------------------------------------------------------
    # Perdida y gradientes
    # ------------------------------------------------------------------
    def _codificar_objetivo(self, objetivo: Any, n: int) -> np.ndarray:
        arreglo = np.asarray(objetivo)
        if arreglo.ndim == 2:
            if self._es_onehot(arreglo):
                arreglo = np.argmax(arreglo, axis=1)
            elif arreglo.shape[1] == 1:
                arreglo = arreglo.reshape(-1)
            else:
                raise ValueError("Objetivo incompatible")
        valores = arreglo.ravel()
        if valores.size != n:
            raise ValueError(
                f"Objetivo con {valores.size} elementos y se esperaban {n}"
            )
        if self._classes is None:
            return np.asarray(valores, dtype=int)
        mapa = {clase: indice
                for indice, clase in enumerate(self._classes)}
        codificado = np.array([
            mapa.get(valor, -1) for valor in valores
        ], dtype=int)
        if np.any(codificado < 0):
            try:
                indices = np.asarray(valores, dtype=int)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "El objetivo contiene clases no vistas"
                ) from error
            if np.all((indices >= 0) & (indices < len(self._classes))):
                return indices
            raise ValueError("El objetivo contiene clases no vistas")
        return codificado

    def compute_loss(self, y_true: np.ndarray,
                     y_pred: np.ndarray) -> float:
        """Entropia cruzada (mas regularizacion) o MSE de compatibilidad."""
        prediccion = np.asarray(y_pred, dtype=np.float64)
        if prediccion.ndim == 1:
            prediccion = prediccion.reshape(-1, 1)
        n = prediccion.shape[0]
        codificado = self._codificar_objetivo(y_true, n)
        if prediccion.shape[1] == 1:
            objetivo = (codificado > 0).astype(np.float64)
            base = self._nucleo.perdida_binaria(
                objetivo, prediccion[:, 0]
            )
        else:
            if np.max(codificado) >= prediccion.shape[1]:
                raise ValueError(
                    "Las clases del objetivo superan las salidas del modelo"
                )
            base = self._nucleo.perdida_multiclase(
                codificado, prediccion
            )
        base += self._nucleo.regularizacion(
            self.pesos, self._regularization, self._reg_lambda,
            self._l1_ratio,
        )
        return float(base)

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Gradiente de pesos/sesgo con regularizacion (API historica)."""
        if self.pesos is None:
            raise RuntimeError("Modelo no entrenado")
        matriz, _ = self._validar_entrada(entrada, permitir_1d=False)
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(-1, 1)
        if gradiente.shape[0] != matriz.shape[0]:
            raise ValueError(
                "El gradiente y la entrada deben tener el mismo numero de "
                "muestras"
            )
        n = max(1, matriz.shape[0])
        grad_pesos = (matriz.T @ gradiente) / n
        grad_pesos += self._nucleo.gradiente_regularizacion(
            self.pesos, self._regularization, self._reg_lambda,
            self._l1_ratio,
        )
        grad_sesgo = np.sum(gradiente, axis=0, keepdims=True) / n
        self.historial_gradientes.append({
            'pesos': grad_pesos.copy(),
            'norma': float(np.linalg.norm(grad_pesos)),
        })
        return grad_pesos, grad_sesgo

    def _gradiente_salida(self, p: np.ndarray, y: np.ndarray,
                          codificado: np.ndarray) -> np.ndarray:
        if self._n_outputs == 1:
            return p - (codificado > 0).astype(np.float64).reshape(-1, 1)
        objetivo = np.zeros((codificado.size, self._n_outputs))
        objetivo[np.arange(codificado.size), codificado] = 1.0
        return p - objetivo

    # ------------------------------------------------------------------
    # Entrenamiento
    # ------------------------------------------------------------------
    def train(self, X: np.ndarray, y: np.ndarray,
              epochs: Optional[int] = None,
              learning_rate: Optional[float] = None,
              verbose: bool = False, **kwargs: Any) -> Dict[str, Any]:
        """Entrena con mini-lotes y devuelve historial y perdida final."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        matriz_original = matriz.copy()
        codificado, original, clases = self._preparar_objetivo(
            y, matriz.shape[0]
        )
        if epochs is not None:
            self._epochs = max(1, int(epochs))
        if learning_rate is not None:
            self._learning_rate = float(learning_rate)
        self._classes = np.asarray(clases)
        self._n_classes = int(len(clases))
        self._n_outputs = 1 if self._n_classes == 2 else self._n_classes
        self.output_size = int(self._n_outputs)
        self._asegurar_pesos(self._n_outputs)
        self._nucleo.reiniciar()

        if self._scaler is not None:
            matriz = self._scaler.fit_transform(matriz)
        self._n_samples = int(matriz.shape[0])
        self._convergence_history = []
        self._loss_history = []
        inicio = time.perf_counter()
        generador = np.random.default_rng(self._seed)
        tam_lote = (self._n_samples if self._batch_size is None
                    else max(1, min(self._batch_size, self._n_samples)))
        n_batches = math.ceil(self._n_samples / tam_lote)
        mejor_pesos: Optional[Tuple[np.ndarray, np.ndarray]] = None
        mejor_perdida = float("inf")
        espera = 0
        total_epocas = max(1, int(self._epochs))

        for epoca in range(total_epocas):
            lr_epoca = self._learning_rate / (
                1.0 + self._decay * epoca
            )
            orden = generador.permutation(self._n_samples)
            perdida_acumulada = 0.0
            vistos = 0
            for inicio_lote in range(0, self._n_samples, tam_lote):
                indices = orden[inicio_lote:inicio_lote + tam_lote]
                X_lote = matriz[indices]
                y_lote = codificado[indices]
                p, _ = self._forward_matriz(X_lote)
                gradiente = self._gradiente_salida(
                    p, original[indices], y_lote
                )
                grad_pesos = (
                    X_lote.T @ gradiente / len(indices)
                    + self._nucleo.gradiente_regularizacion(
                        self.pesos, self._regularization,
                        self._reg_lambda, self._l1_ratio,
                    )
                )
                grad_sesgo = np.sum(
                    gradiente, axis=0, keepdims=True
                ) / len(indices)
                self._nucleo.paso(
                    [self.pesos, self.sesgo],
                    [grad_pesos, grad_sesgo],
                    optimizador=self._optimizer_type,
                    lr=lr_epoca,
                    momentum=self._momentum,
                    beta1=self._beta1,
                    beta2=self._beta2,
                    epsilon=1e-8,
                )
                if self._n_outputs == 1:
                    perdida = self._nucleo.perdida_binaria(
                        (y_lote > 0).astype(np.float64),
                        p[:, 0],
                    )
                else:
                    perdida = self._nucleo.perdida_multiclase(y_lote, p)
                perdida_acumulada += perdida * len(indices)
                vistos += len(indices)
            perdida_epoca = perdida_acumulada / max(1, vistos)
            self._convergence_history.append(float(perdida_epoca))
            self._loss_history.append(float(perdida_epoca))
            if verbose and (epoca + 1) % 100 == 0:
                logger.info(
                    "LR Epoch %d/%d, loss=%.6f",
                    epoca + 1, total_epocas, perdida_epoca,
                )
            if self._early_stopping and epoca >= 5:
                if perdida_epoca < mejor_perdida - 1e-9:
                    mejor_perdida = float(perdida_epoca)
                    mejor_pesos = (
                        self.pesos.copy(), self.sesgo.copy()
                    )
                    espera = 0
                else:
                    espera += 1
                    if espera >= self._early_stopping:
                        break
            if not np.isfinite(perdida_epoca):
                logger.warning("Perdida no finita; se detiene el entrenamiento")
                break

        if mejor_pesos is not None:
            self.pesos, self.sesgo = mejor_pesos
        self._is_fitted = True
        self._accuracy = self.compute_accuracy(matriz_original, original)
        self._training_time = time.perf_counter() - inicio
        if self._loss_history and hasattr(self, "registrar_perdida"):
            self.registrar_perdida(self._loss_history[-1])
        return {
            'losses': list(self._loss_history),
            'final_loss': (float(self._loss_history[-1])
                           if self._loss_history else float('nan')),
            'training_time': float(self._training_time),
            'accuracy': float(self._accuracy),
            'n_batches': int(n_batches),
        }

    def fit(self, X: np.ndarray, y: np.ndarray,
            epochs: Optional[int] = None,
            learning_rate: Optional[float] = None,
            verbose: bool = False, **kwargs: Any
            ) -> "NeuronaRegresionLogistica":
        """API sklearn: entrena y devuelve la propia neurona."""
        self.train(
            X, y, epochs=epochs, learning_rate=learning_rate,
            verbose=verbose, **kwargs,
        )
        return self

    def partial_fit(self, X: np.ndarray, y: np.ndarray,
                    epochs: int = 1, **kwargs: Any) -> "NeuronaRegresionLogistica":
        """Compatibilidad: reentrena con una sola pasada adicional."""
        return self.fit(X, y, epochs=epochs, **kwargs)

    # ------------------------------------------------------------------
    # Evaluacion
    # ------------------------------------------------------------------
    def compute_accuracy(self, X: np.ndarray, y: np.ndarray) -> float:
        """Accuracy de clasificacion."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        _, original, _ = self._preparar_objetivo(y, matriz.shape[0])
        prediccion = self.predict(matriz)
        return float(np.mean(
            np.asarray(prediccion).ravel()
            == np.asarray(original).ravel()
        ))

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """Accuracy."""
        return self.compute_accuracy(X, y)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Metricas binarias o multiclase completas."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        _, original, _ = self._preparar_objetivo(y, matriz.shape[0])
        probabilidades = self.predict_proba(matriz)
        prediccion = self.predict(matriz)
        if self._n_outputs == 1:
            metricas = self._nucleo.metricas_binarias(
                prediccion, original, probabilidades, self._classes
            )
        else:
            metricas = self._nucleo.metricas_multiclase(
                prediccion, original, probabilidades, self._classes
            )
        metricas['loss'] = self.compute_loss(original, probabilidades)
        metricas['predictions'] = np.asarray(prediccion)
        metricas['true_labels'] = np.asarray(original)
        self._accuracy = float(metricas['accuracy'])
        return metricas

    # ------------------------------------------------------------------
    # Configuracion e informacion
    # ------------------------------------------------------------------
    def set_regularization(self, reg_type: str,
                           lambda_val: float = 0.01) -> None:
        self._regularization = self._normalizar_regularizacion(reg_type)
        self._reg_lambda = max(0.0, float(lambda_val))

    def set_threshold(self, threshold: float) -> None:
        self._threshold = min(1.0, max(0.0, float(threshold)))

    @property
    def classes_(self) -> Optional[np.ndarray]:
        return None if self._classes is None else self._classes.copy()

    @property
    def coef_(self) -> Optional[np.ndarray]:
        return None if self.pesos is None else self.pesos.T.copy()

    @property
    def intercept_(self) -> Optional[np.ndarray]:
        return None if self.sesgo is None else self.sesgo.ravel().copy()

    @property
    def n_features_in_(self) -> int:
        return int(self.input_size)

    def get_loss_history(self) -> List[float]:
        return list(self._loss_history)

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        stats = self.obtener_estadisticas()
        if self.pesos is not None:
            stats['pesos_mean'] = float(np.mean(self.pesos))
            stats['pesos_std'] = float(np.std(self.pesos))
            stats['pesos_min'] = float(np.min(self.pesos))
            stats['pesos_max'] = float(np.max(self.pesos))
        stats['learning_rate'] = self._learning_rate
        stats['epochs'] = self._epochs
        stats['regularization'] = self._regularization
        stats['is_fitted'] = self._is_fitted
        stats['accuracy'] = self._accuracy
        return stats

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'regresion_logistica',
            'learning_rate': self._learning_rate,
            'epochs': self._epochs,
            'batch_size': self._batch_size,
            'regularization': self._regularization,
            'reg_lambda': self._reg_lambda,
            'l1_ratio': self._l1_ratio,
            'optimizer': self._optimizer_type,
            'threshold': self._threshold,
            'scaler': (self._scaler.method
                       if self._scaler is not None else None),
            'is_fitted': self._is_fitted,
            'accuracy': self._accuracy,
            'n_samples': self._n_samples,
            'n_classes': self._n_classes,
            'n_outputs': self._n_outputs,
            'training_time': self._training_time,
            'nucleo': self._nucleo.resumen(),
        })
        if self._classes is not None:
            stats['classes'] = self._classes.tolist()
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
            stats['initial_loss'] = float(self._convergence_history[0])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprobaciones numericas de pesos y estado."""
        ok: Dict[str, bool] = {
            'pesos_inicializados': self.pesos is not None,
            'sesgo_inicializado': self.sesgo is not None,
            'modelo_entrenado': bool(self._is_fitted),
        }
        if self.pesos is not None:
            ok['pesos_no_explosivos'] = float(
                np.max(np.abs(self.pesos))
            ) < 1e6
            ok['pesos_no_nan'] = not bool(np.any(np.isnan(self.pesos)))
            ok['pesos_no_inf'] = not bool(np.any(np.isinf(self.pesos)))
        if self.sesgo is not None:
            ok['sesgo_no_nan'] = not bool(np.any(np.isnan(self.sesgo)))
            ok['sesgo_no_inf'] = not bool(np.any(np.isinf(self.sesgo)))
        if self._classes is not None:
            ok['clases_validas'] = bool(len(self._classes) >= 2)
        ok['estable'] = all(ok.values())
        return ok

    # ------------------------------------------------------------------
    # Serializacion
    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        """Guarda pesos, clases, escalador y configuracion."""
        estado = {
            'version': __version__,
            'tipo': 'NeuronaRegresionLogistica',
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'learning_rate': self._learning_rate,
            'epochs': self._epochs,
            'batch_size': self._batch_size,
            'regularization': self._regularization,
            'reg_lambda': self._reg_lambda,
            'l1_ratio': self._l1_ratio,
            'optimizer': self._optimizer_type,
            'momentum': self._momentum,
            'beta1': self._beta1,
            'beta2': self._beta2,
            'decay': self._decay,
            'threshold': self._threshold,
            'early_stopping': self._early_stopping,
            'epsilon': self._epsilon,
            'seed': self._seed,
            'scaler': (None if self._scaler is None
                       else dict(self._scaler.__dict__)),
            'classes': self._classes,
            'n_classes': self._n_classes,
            'n_outputs': self._n_outputs,
            'is_fitted': self._is_fitted,
            'pesos': self.pesos,
            'sesgo': self.sesgo,
            'accuracy': self._accuracy,
            'n_samples': self._n_samples,
            'convergence_history': list(self._convergence_history),
            'loss_history': list(self._loss_history),
            'training_time': self._training_time,
            'pasos': self.pasos,
        }
        with open(filepath, 'wb') as archivo:
            pickle.dump(estado, archivo, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        """Carga checkpoints de esta API o de la API historica."""
        with open(filepath, 'rb') as archivo:
            estado = pickle.load(archivo)
        if not isinstance(estado, dict):
            raise TypeError("El fichero no contiene un checkpoint valido")

        self.nombre = str(estado.get('nombre', self.nombre))
        self.input_size = int(estado.get('input_size', self.input_size))
        self.output_size = int(estado.get('output_size', self.output_size))
        self._learning_rate = float(estado.get('learning_rate', 0.01))
        self._epochs = max(1, int(estado.get('epochs', 200)))
        batch = estado.get('batch_size', 32)
        self._batch_size = None if batch is None else max(1, int(batch))
        self._regularization = self._normalizar_regularizacion(
            estado.get('regularization', 'l2')
        )
        self._reg_lambda = max(0.0, float(estado.get('reg_lambda', 0.01)))
        self._l1_ratio = min(1.0, max(0.0, float(
            estado.get('l1_ratio', 0.5)
        )))
        self._optimizer_type = self._normalizar_optimizador(
            estado.get('optimizer', 'sgd')
        )
        self._momentum = float(estado.get('momentum', 0.9))
        self._beta1 = float(estado.get('beta1', 0.9))
        self._beta2 = float(estado.get('beta2', 0.999))
        self._decay = max(0.0, float(estado.get('decay', 0.0)))
        self._threshold = min(1.0, max(0.0, float(
            estado.get('threshold', 0.5)
        )))
        self._early_stopping = max(0, int(
            estado.get('early_stopping', 0)
        ))
        self._epsilon = max(1e-15, float(estado.get('epsilon', 1e-12)))
        self._seed = int(estado.get('seed', LUCIA_LR_CONFIG["random_seed"]))
        self._rng = np.random.default_rng(self._seed)
        scaler_estado = estado.get('scaler')
        if isinstance(scaler_estado, dict):
            self._scaler = FeatureScaler(
                scaler_estado.get('method', 'standard')
            )
            self._scaler.__dict__.update(scaler_estado)
        else:
            self._scaler = None
        self._nucleo = self.NucleoLogistico(epsilon=self._epsilon)

        pesos = estado.get('pesos')
        sesgo = estado.get('sesgo')
        if pesos is None or sesgo is None:
            raise ValueError("El checkpoint no contiene pesos")
        self.pesos = np.asarray(pesos, dtype=np.float64)
        self.sesgo = np.asarray(sesgo, dtype=np.float64).reshape(1, -1)
        self._n_outputs = int(
            estado.get('n_outputs', self.pesos.shape[1])
        )
        clases = estado.get('classes')
        if clases is None:
            if self._n_outputs == 1:
                clases = np.array([0, 1])
            else:
                clases = np.arange(self._n_outputs)
        self._classes = np.asarray(clases)
        self._n_classes = int(
            estado.get('n_classes', len(self._classes))
        )
        self._is_fitted = bool(estado.get('is_fitted', True))
        self._accuracy = float(estado.get('accuracy', 0.0))
        self._n_samples = int(estado.get('n_samples', 0))
        self._convergence_history = [
            float(v) for v in estado.get('convergence_history', [])
        ]
        self._loss_history = [
            float(v) for v in estado.get('loss_history', [])
        ]
        self._training_time = float(estado.get('training_time', 0.0))
        self.pasos = int(estado.get('pasos', 0))

    def get_config(self) -> Dict[str, Any]:
        """Configuracion reproducible."""
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'learning_rate': self._learning_rate,
            'epochs': self._epochs,
            'batch_size': self._batch_size,
            'regularization': self._regularization,
            'reg_lambda': self._reg_lambda,
            'l1_ratio': self._l1_ratio,
            'optimizer': self._optimizer_type,
            'momentum': self._momentum,
            'beta1': self._beta1,
            'beta2': self._beta2,
            'decay': self._decay,
            'threshold': self._threshold,
            'scaler': (self._scaler.method
                       if self._scaler is not None else None),
            'early_stopping': self._early_stopping,
            'seed': self._seed,
        }

    def summary(self) -> str:
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {self.nombre} ===",
            (f"Regularizacion: {self._regularization} "
             f"({self._reg_lambda}), Optimizador: "
             f"{self._optimizer_type}"),
            (f"LR: {self._learning_rate}, Epochs: {self._epochs}, "
             f"Batch: {self._batch_size}"),
            (f"Input: {self.input_size}, Clases: "
             f"{stats.get('n_classes', 0)}, Salidas: "
             f"{stats.get('n_outputs', 0)}"),
            (f"Fitted: {stats.get('is_fitted', False)}, "
             f"Acc: {stats.get('accuracy', 0.0):.4f}, "
             f"Params: {self.params_count()}"),
            (f"Final loss: {stats.get('final_loss', 'N/A')}"),
        ])

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},"
                f"sal={self.output_size},pasos={self.pasos})")


# ---------------------------------------------------------------------------
# Utilidades historicas de activacion, perdida, optimizacion y escalado
# ---------------------------------------------------------------------------
class SigmoidEngine:
    def __init__(self, clip_range: float = 500.0):
        self.clip_range = float(clip_range)

    def compute(self, z: np.ndarray) -> np.ndarray:
        valores = np.asarray(z, dtype=np.float64)
        limite = np.clip(valores, -self.clip_range, self.clip_range)
        positivo = limite >= 0.0
        resultado = np.empty_like(limite)
        resultado[positivo] = 1.0 / (1.0 + np.exp(-limite[positivo]))
        exp_z = np.exp(limite[~positivo])
        resultado[~positivo] = exp_z / (1.0 + exp_z)
        return resultado

    def derivative(self, sigmoid_output: np.ndarray) -> np.ndarray:
        salida = np.asarray(sigmoid_output, dtype=np.float64)
        return salida * (1.0 - salida)

    def log_odds(self, probability: np.ndarray) -> np.ndarray:
        epsilon = 1e-8
        p = np.clip(
            np.asarray(probability, dtype=np.float64),
            epsilon, 1.0 - epsilon,
        )
        return np.log(p / (1.0 - p))


class LossCalculator:
    def __init__(self, epsilon: float = 1e-8):
        self.epsilon = float(epsilon)

    def binary_crossentropy(self, y_true: np.ndarray,
                            y_pred: np.ndarray) -> float:
        real = np.asarray(y_true, dtype=np.float64)
        pred = np.clip(
            np.asarray(y_pred, dtype=np.float64),
            self.epsilon, 1.0 - self.epsilon,
        )
        return float(-np.mean(
            real * np.log(pred) + (1.0 - real) * np.log(1.0 - pred)
        ))

    def mean_squared_error(self, y_true: np.ndarray,
                           y_pred: np.ndarray) -> float:
        return float(np.mean(
            (np.asarray(y_true, dtype=np.float64)
             - np.asarray(y_pred, dtype=np.float64)) ** 2
        ))

    def log_loss_with_reg(self, y_true: np.ndarray, y_pred: np.ndarray,
                          pesos: np.ndarray,
                          reg_lambda: float = 0.01) -> float:
        base = self.binary_crossentropy(y_true, y_pred)
        return float(base + 0.5 * float(reg_lambda)
                     * float(np.sum(np.asarray(pesos) ** 2)))

    def categorical_crossentropy(self, y_codificado: np.ndarray,
                                 probabilidades: np.ndarray) -> float:
        indices = np.asarray(y_codificado, dtype=int).ravel()
        proba = np.clip(
            np.asarray(probabilidades, dtype=np.float64),
            self.epsilon, 1.0,
        )
        elegidas = proba[np.arange(indices.size), indices]
        return float(-np.mean(np.log(elegidas)))


class GradientDescent:
    def __init__(self, learning_rate: float = 0.01, momentum: float = 0.0,
                 decay: float = 0.0, optimizer_type: str = "sgd"):
        self.learning_rate = float(learning_rate)
        self.momentum = float(momentum)
        self.decay = max(0.0, float(decay))
        self.optimizer_type = (
            optimizer_type if optimizer_type in ("sgd", "momentum", "adam")
            else "sgd"
        )
        self._velocity: Optional[np.ndarray] = None
        self._m: Optional[np.ndarray] = None
        self._v: Optional[np.ndarray] = None
        self._t: int = 0

    def update(self, params: np.ndarray,
               gradient: np.ndarray) -> np.ndarray:
        p = np.asarray(params, dtype=np.float64)
        g = np.asarray(gradient, dtype=np.float64)
        if self.decay > 0.0:
            self.learning_rate *= 1.0 / (1.0 + self.decay * self._t)
        if self.optimizer_type == "adam":
            if self._m is None or self._m.shape != p.shape:
                self._m = np.zeros_like(p)
                self._v = np.zeros_like(p)
            self._t += 1
            self._m = 0.9 * self._m + 0.1 * g
            self._v = 0.999 * self._v + 0.001 * g * g
            m_hat = self._m / (1.0 - 0.9 ** self._t)
            v_hat = self._v / (1.0 - 0.999 ** self._t)
            return p - self.learning_rate * m_hat / (
                np.sqrt(v_hat) + 1e-8
            )
        if self.optimizer_type == "momentum" or self.momentum > 0.0:
            if self._velocity is None or self._velocity.shape != p.shape:
                self._velocity = np.zeros_like(p)
            self._velocity = (
                self.momentum * self._velocity
                + self.learning_rate * g
            )
            self._t += 1
            return p - self._velocity
        self._t += 1
        return p - self.learning_rate * g

    def reset(self) -> None:
        self._velocity = None
        self._m = None
        self._v = None
        self._t = 0


class Regularizer:
    def __init__(self, reg_type: str = "l2", lambda_val: float = 0.01):
        self.reg_type = (reg_type if reg_type in ("l1", "l2", "elasticnet")
                         else "l2")
        self.lambda_val = max(0.0, float(lambda_val))
        self._l1_ratio: float = 0.5

    def penalty(self, pesos: np.ndarray) -> float:
        matriz = np.asarray(pesos, dtype=np.float64)
        if self.reg_type == "l1":
            return self.lambda_val * float(np.sum(np.abs(matriz)))
        if self.reg_type == "l2":
            return 0.5 * self.lambda_val * float(np.sum(matriz ** 2))
        l1 = self.lambda_val * 0.5 * float(np.sum(np.abs(matriz)))
        l2 = 0.5 * self.lambda_val * float(np.sum(matriz ** 2))
        return l1 * self._l1_ratio + l2 * (1.0 - self._l1_ratio)

    def gradient(self, pesos: np.ndarray) -> np.ndarray:
        matriz = np.asarray(pesos, dtype=np.float64)
        if self.reg_type == "l1":
            return self.lambda_val * np.sign(matriz)
        if self.reg_type == "l2":
            return self.lambda_val * matriz
        l1_grad = self.lambda_val * np.sign(matriz)
        l2_grad = self.lambda_val * matriz
        return l1_grad * self._l1_ratio + l2_grad * (1.0 - self._l1_ratio)

    def set_elasticnet(self, l1_ratio: float) -> None:
        self._l1_ratio = min(1.0, max(0.0, float(l1_ratio)))
        self.reg_type = "elasticnet"


class DecisionBoundary:
    def __init__(self, threshold: float = 0.5):
        self.threshold = min(1.0, max(0.0, float(threshold)))

    def classify(self, probabilities: np.ndarray) -> np.ndarray:
        proba = np.asarray(probabilities, dtype=np.float64)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            return (proba[:, 1] >= self.threshold).astype(int)
        return (proba.ravel() >= self.threshold).astype(int)

    def set_threshold(self, threshold: float) -> None:
        self.threshold = min(1.0, max(0.0, float(threshold)))

    def margin_analysis(self, probabilities: np.ndarray) -> Dict[str, Any]:
        proba = np.asarray(probabilities, dtype=np.float64)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            proba = proba[:, 1]
        margen = np.abs(proba.ravel() - self.threshold)
        return {
            'mean_margin': float(np.mean(margen)),
            'min_margin': float(np.min(margen)),
            'max_margin': float(np.max(margen)),
            'uncertain_predictions': int(np.sum(margen < 0.1)),
        }


class FeatureScaler:
    def __init__(self, method: str = "standard"):
        self.method = (
            method if method in ("standard", "minmax", "robust")
            else "standard"
        )
        self._mean: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None
        self._min: Optional[np.ndarray] = None
        self._max: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> "FeatureScaler":
        datos = np.asarray(X, dtype=np.float64)
        if datos.ndim != 2:
            raise ValueError("X debe ser 2D para el escalador")
        if self.method == "standard":
            self._mean = np.mean(datos, axis=0)
            self._std = np.std(datos, axis=0) + 1e-8
        elif self.method == "minmax":
            self._min = np.min(datos, axis=0)
            self._max = np.max(datos, axis=0)
        else:
            self._mean = np.median(datos, axis=0)
            q75 = np.percentile(datos, 75, axis=0)
            q25 = np.percentile(datos, 25, axis=0)
            self._std = q75 - q25 + 1e-8
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        datos = np.asarray(X, dtype=np.float64)
        if self.method == "standard":
            if self._mean is None or self._std is None:
                raise RuntimeError("Scaler no ajustado")
            return (datos - self._mean) / self._std
        if self.method == "minmax":
            if self._min is None or self._max is None:
                raise RuntimeError("Scaler no ajustado")
            return (datos - self._min) / (
                self._max - self._min + 1e-8
            )
        if self._mean is None or self._std is None:
            raise RuntimeError("Scaler no ajustado")
        return (datos - self._mean) / self._std

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        datos = np.asarray(X, dtype=np.float64)
        if self.method == "minmax":
            if self._min is None or self._max is None:
                raise RuntimeError("Scaler no ajustado")
            return datos * (self._max - self._min + 1e-8) + self._min
        if self._mean is None or self._std is None:
            raise RuntimeError("Scaler no ajustado")
        return datos * self._std + self._mean


# ---------------------------------------------------------------------------
# Adaptador de compatibilidad con la API historica de RF_SL1_8
# ---------------------------------------------------------------------------
class LogisticRegressionOptimizer(NeuronaRegresionLogistica):
    """Regresion logistica real con la API historica de RF_SL1_8."""

    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "LogisticRegressionOptimizer",
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("epochs", 1000)
        super().__init__(
            input_size=input_size, output_size=output_size,
            nombre=nombre, **kwargs,
        )


# ---------------------------------------------------------------------------
# Fabrica, utilidades y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "logistica", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaRegresionLogistica:
    """Fabrica una neurona de regresion logistica por nombre."""
    clave = str(tipo or "logistica").strip().lower().replace("-", "_")
    if clave in ("logistica", "logistic", "logistic_regression", "lr",
                 "regresion_logistica"):
        return NeuronaRegresionLogistica(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("binaria", "binary", "binario"):
        kwargs.pop("output_size", None)
        return NeuronaRegresionLogistica(
            input_size=input_size, output_size=1, **kwargs
        )
    if clave in ("multiclase", "multiclass", "multinomial"):
        return NeuronaRegresionLogistica(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("compat", "logistic_regression_optimizer", "optimizer"):
        return LogisticRegressionOptimizer(
            input_size=input_size, output_size=output_size, **kwargs
        )
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: logistica, binaria, multiclase, "
        "compat"
    )


def tipos_disponibles() -> List[str]:
    """Nombres aceptados por :func:`crear_neurona`."""
    return ["logistica", "binaria", "multiclase", "compat"]


def create_logistic_regression_optimizer(
    input_size: int = 4, output_size: int = 8, **kwargs: Any,
) -> LogisticRegressionOptimizer:
    """Fabrica historica de RF_SL1_8."""
    return LogisticRegressionOptimizer(
        input_size=input_size, output_size=output_size, **kwargs
    )


def entrenar_y_evaluar(modelo: NeuronaRegresionLogistica, X: np.ndarray,
                       y: np.ndarray, epochs: int = 200,
                       **kwargs: Any) -> Dict[str, Any]:
    """Entrena y devuelve historial y metricas en una sola llamada."""
    resultado = modelo.train(X, y, epochs=epochs, **kwargs)
    return {
        'modelo': modelo,
        'historial': resultado['losses'],
        'metricas': modelo.evaluate(X, y),
        'perdida_final': float(resultado['final_loss']),
    }


def benchmark_modelo(modelo: NeuronaRegresionLogistica, X: np.ndarray,
                     repeticiones: int = 5) -> Dict[str, float]:
    """Mide el tiempo de inferencia."""
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


def guardar_modelo(modelo: NeuronaRegresionLogistica, ruta: str) -> None:
    """Serializa el objeto completo (pickle)."""
    with open(ruta, 'wb') as archivo:
        pickle.dump(modelo, archivo, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaRegresionLogistica:
    """Carga un modelo serializado con :func:`guardar_modelo`."""
    with open(ruta, 'rb') as archivo:
        modelo = pickle.load(archivo)
    if not isinstance(modelo, NeuronaRegresionLogistica):
        raise TypeError("El fichero no contiene una regresion logistica")
    return modelo


# ---------------------------------------------------------------------------
# Demostracion
# ---------------------------------------------------------------------------
def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_8_1.py``)."""
    generador = np.random.default_rng(2026)
    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_8_1 :: Regresion logistica (v%s)" % __version__)
    print("=" * 78)

    n = 400
    X = generador.normal(size=(n, 3))
    y_bin = (X[:, 0] + 2.0 * X[:, 1] - X[:, 2] > 0.0).astype(int)
    binario = crear_neurona(
        "binaria", 3, 1, learning_rate=0.05, epochs=300,
        regularization="l2", scaler="standard", seed=7,
    )
    binario.fit(X, y_bin)
    met_bin = binario.evaluate(X, y_bin)
    print("%-12s accuracy=%.4f precision=%.4f recall=%.4f F1=%.4f"
          % ("binaria", met_bin['accuracy'], met_bin['precision'],
             met_bin['recall'], met_bin['f1']))

    y_multi = (
        (X[:, 0] > 0.0).astype(int)
        + (X[:, 1] > 0.0).astype(int)
    )
    multi = crear_neurona(
        "multiclase", 3, 3, learning_rate=0.05, epochs=300,
        regularization="l2", optimizer="adam", scaler="standard", seed=11,
    )
    multi.fit(X, y_multi)
    met_multi = multi.evaluate(X, y_multi)
    print("%-12s accuracy=%.4f F1=%.4f log_loss=%.4f"
          % ("multiclase", met_multi['accuracy'], met_multi['f1_macro'],
             met_multi['log_loss']))
    print("Probabilidades (3):",
          np.round(binario.predict_proba(X[:3]), 3).tolist())
    print("Estabilidad:", binario.verificar_estabilidad())
    print("Benchmark:", benchmark_modelo(binario, X, repeticiones=3))
    print("=" * 78)
    return {'binaria': met_bin, 'multiclase': met_multi}


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaRegresionLogistica',
    'LogisticRegressionOptimizer',
    'SigmoidEngine',
    'LossCalculator',
    'GradientDescent',
    'Regularizer',
    'DecisionBoundary',
    'FeatureScaler',
    'crear_neurona',
    'tipos_disponibles',
    'create_logistic_regression_optimizer',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_LR_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
