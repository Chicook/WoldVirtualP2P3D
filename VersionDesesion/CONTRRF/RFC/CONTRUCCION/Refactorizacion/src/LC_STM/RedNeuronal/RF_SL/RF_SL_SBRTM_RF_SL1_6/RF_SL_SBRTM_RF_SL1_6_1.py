"""RF_SL_SBRTM_RF_SL1_6_1.py
Neuronas especializadas en clasificacion Naive Bayes (RF_SL - SBRTM - RF - 2026).
================================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
de ``NaiveBayesOptimizer`` (que empezaba en mitad de la clase, sin imports ni
base) y lo sustituye por una implementacion real de clasificadores Naive Bayes
con calculo mejorado:

  * ``NeuronaNaiveBayes``: neurona probabilistica especializada.
      - Distribuciones ``gaussian``, ``multinomial`` y ``bernoulli``.
      - Priors ponderados, ``fit_prior``, ``class_prior`` y suavizado.
      - ``var_smoothing`` y suelo numerico para varianzas gaussianas.
      - ``alpha`` de Laplace/Lidstone para multinomial y Bernoulli.
      - Log-verosimilitudes vectorizadas y posterior estable con log-sum-exp.
      - Soporte de etiquetas string, one-hot, pesos de muestra y binarizacion.
      - ``predict``, ``predict_proba``, ``predict_log_proba``,
        ``joint_log_likelihood``, ``compute_accuracy``, ``compute_loss`` y
        metricas completas (accuracy, balanced accuracy, precision, recall,
        F1 macro, log-loss, Brier y matriz de confusion).
      - Serializacion compatible con checkpoint nuevos y con el formato
        historico basado en ``feature_mean``/``feature_var``.

  * ``NeuronaNaiveBayes.NucleoBayesiano``: **clase anidada** que fusiona las
      funciones matematicas del modelo: priors, estimacion de parametros por
      distribucion, log-verosimilitud, log-posterior y prediccion.

  * ``NeuronaNaiveBayes.EvaluadorBayesiano``: **clase anidada** que fusiona
      log-sum-exp, normalizacion posterior, log-loss, Brier, metricas de
      clasificacion y matriz de confusion.

  * ``NaiveBayesOptimizer``: adaptador de compatibilidad con la API historica
      de RF_SL1_6. Mantiene ``_var_smoothing``, ``_distribution``,
      ``_classes``, ``_class_priors``, ``_feature_mean``, ``_feature_var``,
      ``_accuracy``, ``_convergence_history`` y la cabeza lineal legada
      (``forward``/``backward``) sin duplicar el Naive Bayes real.

  * Utilidades: ``crear_neurona``, ``tipos_disponibles``,
      ``create_naive_bayes_optimizer``, ``entrenar_y_evaluar``,
      ``benchmark_modelo``, ``guardar_modelo``, ``cargar_modelo`` y ``demo``.

Referencias
-----------
- Naive Bayes gaussiano, multinomial y Bernoulli.
- Suavizado de Laplace/Lidstone y estimacion de priors.
- Log-sum-exp para estabilidad numerica del posterior.
- Scikit-learn: ``GaussianNB``, ``MultinomialNB``, ``BernoulliNB``.

Uso
---
    from RF_SL_SBRTM_RF_SL1_6_1 import NeuronaNaiveBayes

    modelo = NeuronaNaiveBayes(input_size=3, distribucion="gaussian")
    modelo.fit(X, y)
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
LUCIA_NB_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "distribucion": "gaussian",
    "var_smoothing": 1e-9,
    "alpha": 1.0,
    "fit_prior": True,
    "class_prior": None,
    "prior_smoothing": 1e-10,
    "binarize": None,
    "epochs": 1,
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

    _CLAVE_BASE = "_rf_snrtm_base_import_nb"
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
# Neurona Naive Bayes
# ---------------------------------------------------------------------------
class NeuronaNaiveBayes(NeuronaMemoriaBase):
    """Clasificador Naive Bayes con tres distribuciones y calculo estable.

    Parametros
    ----------
    input_size, output_size:
        Dimensiones declaradas (compatibilidad con la jerarquia).
    distribucion:
        ``gaussian``, ``multinomial`` o ``bernoulli``.
    var_smoothing:
        Suavizado aditivo de la varianza gaussiana.
    alpha:
        Suavizado de Laplace/Lidstone para multinomial y Bernoulli.
    fit_prior:
        Si es ``False`` usa priors uniformes.
    class_prior:
        Array, secuencia o diccionario ``{clase: prior}``. Sustituye a los
        priors estimados.
    binarize:
        Umbral opcional para convertir caracteristicas a 0/1 en Bernoulli.
    prior_smoothing:
        Suavizado de los priors estimados.
    """

    # ------------------------------------------------------------------
    # Clase anidada 1: nucleo matematico bayesiano
    # ------------------------------------------------------------------
    class NucleoBayesiano:
        """Fusiona priors, parametros, verosimilitudes y posterior.

        Se accede como ``NeuronaNaiveBayes.NucleoBayesiano`` o
        ``modelo.NucleoBayesiano``.
        """

        DISTRIBUCIONES: Tuple[str, ...] = (
            "gaussian", "multinomial", "bernoulli",
        )
        EPS = 1e-12

        def __init__(self, distribucion: str = "gaussian",
                     var_smoothing: float = 1e-9,
                     alpha: float = 1.0,
                     fit_prior: bool = True,
                     class_prior: Optional[np.ndarray] = None,
                     prior_smoothing: float = 1e-10,
                     binarize: Optional[float] = None) -> None:
            self.distribucion = self.normalizar_distribucion(distribucion)
            self.var_smoothing = max(0.0, float(var_smoothing))
            self.alpha = max(1e-12, float(alpha))
            self.fit_prior = bool(fit_prior)
            self.class_prior = class_prior
            self.prior_smoothing = max(0.0, float(prior_smoothing))
            self.binarize = None if binarize is None else float(binarize)

        # -- normalizacion y estabilidad numerica ---------------------
        @classmethod
        def normalizar_distribucion(cls, nombre: Optional[str]) -> str:
            clave = str(nombre or "gaussian").strip().lower().replace("-", "_")
            alias = {
                "gaussian": "gaussian", "gauss": "gaussian",
                "normal": "gaussian", "gaussiana": "gaussian",
                "multinomial": "multinomial", "multinomial_nb": "multinomial",
                "counts": "multinomial", "conteos": "multinomial",
                "bernoulli": "bernoulli", "bernoulli_nb": "bernoulli",
                "binomial": "bernoulli", "binaria": "bernoulli",
            }
            clave = alias.get(clave, clave)
            if clave not in cls.DISTRIBUCIONES:
                raise ValueError(
                    f"Distribucion desconocida: {nombre!r}. Usa una de "
                    f"{cls.DISTRIBUCIONES}"
                )
            return clave

        @staticmethod
        def logsumexp(valores: np.ndarray, axis: int = 1,
                      keepdims: bool = True) -> np.ndarray:
            """log(sum(exp(x))) numericamente estable."""
            datos = np.asarray(valores, dtype=np.float64)
            if datos.ndim == 1 and axis == 1:
                axis = 0
            maximo = np.max(datos, axis=axis, keepdims=True)
            seguro = np.where(np.isfinite(maximo), maximo, 0.0)
            suma = np.sum(np.exp(datos - seguro), axis=axis, keepdims=True)
            resultado = np.log(np.maximum(suma, 1e-300)) + seguro
            return resultado if keepdims else np.squeeze(resultado, axis=axis)

        # -- priors ---------------------------------------------------
        def estimar_priors(self, y: np.ndarray, n_classes: int,
                           weights: Optional[np.ndarray] = None
                           ) -> np.ndarray:
            """Priors normalizados (uniformes, estimados o impuestos)."""
            y_arr = np.asarray(y, dtype=int).ravel()
            w = (np.ones(y_arr.size, dtype=np.float64)
                 if weights is None else np.asarray(weights, dtype=np.float64))
            if w.size != y_arr.size:
                raise ValueError("Los pesos no coinciden con y")
            if self.class_prior is not None:
                prior = np.asarray(self.class_prior, dtype=np.float64).ravel()
                if prior.size != n_classes:
                    raise ValueError(
                        f"class_prior tiene {prior.size} clases y se "
                        f"esperaban {n_classes}"
                    )
                prior = np.maximum(prior, 0.0)
                total = float(np.sum(prior))
                if total <= self.EPS:
                    raise ValueError("class_prior debe sumar un valor positivo")
                return prior / total
            if not self.fit_prior:
                return np.full(n_classes, 1.0 / max(1, n_classes))
            conteos = np.bincount(y_arr, weights=w, minlength=n_classes)
            total = float(np.sum(conteos))
            if total <= self.EPS:
                return np.full(n_classes, 1.0 / max(1, n_classes))
            prior = (conteos + self.prior_smoothing) / (
                total + self.prior_smoothing * n_classes
            )
            suma = float(np.sum(prior))
            return prior / suma if suma > self.EPS else prior

        # -- parametros por distribucion ------------------------------
        def estimar_parametros(self, X: np.ndarray, y: np.ndarray,
                               n_classes: int,
                               weights: Optional[np.ndarray] = None
                               ) -> Dict[str, np.ndarray]:
            """Estima medias/varianzas o probabilidades por clase."""
            matriz = np.asarray(X, dtype=np.float64)
            y_arr = np.asarray(y, dtype=int).ravel()
            n_muestras, n_features = matriz.shape
            w = (np.ones(n_muestras, dtype=np.float64)
                 if weights is None else np.asarray(weights, dtype=np.float64))
            if w.size != n_muestras:
                raise ValueError("Los pesos no coinciden con X")
            if self.distribucion == "gaussian":
                medias = np.zeros((n_features, n_classes), dtype=np.float64)
                varianzas = np.ones((n_features, n_classes), dtype=np.float64)
                for clase in range(n_classes):
                    mascara = y_arr == clase
                    w_clase = w[mascara]
                    total = float(np.sum(w_clase))
                    if total <= self.EPS:
                        continue
                    valores = matriz[mascara]
                    media = np.sum(w_clase[:, None] * valores, axis=0) / total
                    varianza = np.sum(
                        w_clase[:, None] * (valores - media) ** 2, axis=0
                    ) / total
                    medias[:, clase] = media
                    varianzas[:, clase] = (
                        np.maximum(varianza, self.EPS)
                        + self.var_smoothing
                    )
                return {'means': medias, 'vars': varianzas}

            if self.distribucion == "multinomial":
                if np.any(matriz < 0.0):
                    raise ValueError(
                        "La distribucion multinomial requiere X >= 0"
                    )
                conteos = np.zeros((n_features, n_classes), dtype=np.float64)
                for clase in range(n_classes):
                    mascara = y_arr == clase
                    if np.any(mascara):
                        conteos[:, clase] = (
                            w[mascara] @ matriz[mascara]
                        )
                totales = np.sum(conteos, axis=0)
                theta = (conteos + self.alpha) / (
                    totales[None, :] + self.alpha * n_features
                )
                theta = np.maximum(theta, self.EPS)
                return {'log_theta': np.log(theta), 'theta': theta}

            # Bernoulli
            if self.binarize is not None:
                binaria = (matriz > self.binarize).astype(np.float64)
            else:
                if not np.all(
                    np.isclose(matriz, 0.0) | np.isclose(matriz, 1.0)
                ):
                    raise ValueError(
                        "La distribucion Bernoulli requiere X binaria (0/1) "
                        "o un valor de binarize"
                    )
                binaria = matriz
            conteos = np.zeros((n_features, n_classes), dtype=np.float64)
            totales = np.zeros(n_classes, dtype=np.float64)
            for clase in range(n_classes):
                mascara = y_arr == clase
                if np.any(mascara):
                    w_clase = w[mascara]
                    conteos[:, clase] = w_clase @ binaria[mascara]
                    totales[clase] = float(np.sum(w_clase))
            theta = (conteos + self.alpha) / (
                totales[None, :] + 2.0 * self.alpha
            )
            theta = np.clip(theta, self.EPS, 1.0 - self.EPS)
            return {
                'theta': theta,
                'log_theta': np.log(theta),
                'log_not_theta': np.log1p(-theta),
            }

        # -- verosimilitud y posterior --------------------------------
        def log_verosimilitud(self, X: np.ndarray,
                              parametros: Dict[str, np.ndarray]
                              ) -> np.ndarray:
            """Matriz (n_muestras, n_clases) de log p(X | clase)."""
            matriz = np.asarray(X, dtype=np.float64)
            if self.distribucion == "gaussian":
                medias = np.asarray(parametros['means'], dtype=np.float64)
                varianzas = np.asarray(parametros['vars'], dtype=np.float64)
                diferencia = matriz[:, :, None] - medias[None, :, :]
                log_veros = -0.5 * (
                    np.log(2.0 * math.pi * varianzas)[None, :, :]
                    + (diferencia ** 2) / varianzas[None, :, :]
                )
                return np.sum(log_veros, axis=1)
            if self.distribucion == "multinomial":
                return matriz @ np.asarray(
                    parametros['log_theta'], dtype=np.float64
                )
            log_theta = np.asarray(
                parametros['log_theta'], dtype=np.float64
            )
            log_no_theta = np.asarray(
                parametros['log_not_theta'], dtype=np.float64
            )
            return matriz @ log_theta + (1.0 - matriz) @ log_no_theta

        def log_joint(self, X: np.ndarray,
                      parametros: Dict[str, np.ndarray],
                      priors: np.ndarray) -> np.ndarray:
            """log p(clase) + log p(X | clase)."""
            log_prior = np.log(np.maximum(
                np.asarray(priors, dtype=np.float64), self.EPS
            ))
            return self.log_verosimilitud(X, parametros) + log_prior[None, :]

        def predecir(self, X: np.ndarray,
                     parametros: Dict[str, np.ndarray],
                     priors: np.ndarray,
                     clases: np.ndarray) -> np.ndarray:
            log_joint = self.log_joint(X, parametros, priors)
            return np.asarray(clases)[np.argmax(log_joint, axis=1)]

        def resumen(self) -> Dict[str, Any]:
            return {
                'distribucion': self.distribucion,
                'var_smoothing': self.var_smoothing,
                'alpha': self.alpha,
                'fit_prior': self.fit_prior,
                'prior_smoothing': self.prior_smoothing,
                'binarize': self.binarize,
                'distribuciones': list(self.DISTRIBUCIONES),
            }

    # ------------------------------------------------------------------
    # Clase anidada 2: evaluador probabilistico
    # ------------------------------------------------------------------
    class EvaluadorBayesiano:
        """Fusiona normalizacion posterior, metricas y calibracion."""

        EPS = 1e-12

        @staticmethod
        def normalizar_log_probs(log_joint: np.ndarray) -> np.ndarray:
            """Convierte log-joint en log-posterior estable."""
            datos = np.asarray(log_joint, dtype=np.float64)
            if datos.ndim == 1:
                datos = datos.reshape(1, -1)
            log_norm = NeuronaNaiveBayes.NucleoBayesiano.logsumexp(
                datos, axis=1, keepdims=True
            )
            return datos - log_norm

        @staticmethod
        def _codificar(valores: np.ndarray,
                       clases: np.ndarray) -> np.ndarray:
            mapa = {clase: indice for indice, clase in enumerate(clases)}
            codificado = np.array([
                mapa.get(valor, -1) for valor in np.asarray(valores).ravel()
            ], dtype=int)
            return codificado

        def log_loss(self, probabilidades: np.ndarray,
                     y_codificado: np.ndarray) -> float:
            proba = np.asarray(probabilidades, dtype=np.float64)
            indices = np.asarray(y_codificado, dtype=int).ravel()
            if proba.ndim != 2 or proba.shape[0] != indices.size:
                raise ValueError("probabilidades y etiquetas incompatibles")
            validos = (indices >= 0) & (indices < proba.shape[1])
            if not np.any(validos):
                return float('nan')
            elegidas = proba[np.arange(indices.size)[validos],
                            indices[validos]]
            return float(-np.mean(np.log(np.clip(
                elegidas, self.EPS, 1.0
            ))))

        def brier_score(self, probabilidades: np.ndarray,
                        y_codificado: np.ndarray,
                        n_classes: int) -> float:
            proba = np.asarray(probabilidades, dtype=np.float64)
            indices = np.asarray(y_codificado, dtype=int).ravel()
            if proba.ndim != 2:
                raise ValueError("probabilidades debe ser 2D")
            objetivo = np.zeros_like(proba)
            validos = (indices >= 0) & (indices < n_classes)
            objetivo[np.arange(indices.size)[validos],
                    indices[validos]] = 1.0
            return float(np.mean(np.sum((proba - objetivo) ** 2, axis=1)))

        def matriz_confusion(self, pred: np.ndarray, real: np.ndarray,
                             clases: np.ndarray) -> np.ndarray:
            y_true = self._codificar(real, clases)
            y_pred = self._codificar(pred, clases)
            k = len(clases)
            matriz = np.zeros((k, k), dtype=int)
            for verdadero, predicho in zip(y_true, y_pred):
                if 0 <= verdadero < k and 0 <= predicho < k:
                    matriz[verdadero, predicho] += 1
            return matriz

        def metricas(self, pred: np.ndarray, real: np.ndarray,
                     proba: Optional[np.ndarray],
                     clases: np.ndarray) -> Dict[str, Any]:
            """Metricas de clasificacion, todas finitas."""
            y_true = self._codificar(real, clases)
            y_pred = self._codificar(pred, clases)
            validos = (y_true >= 0) & (y_pred >= 0)
            aciertos = float(np.mean(
                y_pred[validos] == y_true[validos]
            )) if np.any(validos) else 0.0
            k = len(clases)
            recalls: List[float] = []
            precisiones: List[float] = []
            f1s: List[float] = []
            for clase in range(k):
                verdadero = y_true == clase
                predicho = y_pred == clase
                if not np.any(verdadero):
                    continue
                tp = float(np.sum(verdadero & predicho))
                fp = float(np.sum(~verdadero & predicho))
                fn = float(np.sum(verdadero & ~predicho))
                recall = tp / max(1.0, tp + fn)
                precision = tp / max(1.0, tp + fp)
                f1 = (2.0 * precision * recall
                      / max(self.EPS, precision + recall))
                recalls.append(recall)
                precisiones.append(precision)
                f1s.append(f1)
            matriz = self.matriz_confusion(pred, real, clases)
            metricas: Dict[str, Any] = {
                'accuracy': aciertos,
                'balanced_accuracy': float(np.mean(recalls))
                if recalls else 0.0,
                'precision_macro': float(np.mean(precisiones))
                if precisiones else 0.0,
                'recall_macro': float(np.mean(recalls))
                if recalls else 0.0,
                'f1_macro': float(np.mean(f1s)) if f1s else 0.0,
                'n_samples': int(np.asarray(real).size),
                'n_classes': int(k),
                'confusion_matrix': matriz.tolist(),
            }
            if proba is not None:
                metricas['log_loss'] = self.log_loss(proba, y_true)
                metricas['brier_score'] = self.brier_score(
                    proba, y_true, k
                )
            return metricas

        def resumen(self) -> Dict[str, Any]:
            return {
                'metricas': [
                    'accuracy', 'balanced_accuracy', 'precision_macro',
                    'recall_macro', 'f1_macro', 'log_loss', 'brier_score',
                ],
                'soporta_matriz_confusion': True,
            }

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuronaNaiveBayes",
        *,
        distribucion: str = "gaussian",
        var_smoothing: float = 1e-9,
        alpha: float = 1.0,
        fit_prior: bool = True,
        class_prior: Any = None,
        prior_smoothing: float = 1e-10,
        binarize: Optional[float] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        if "distribution" in kwargs and distribucion == "gaussian":
            distribucion = kwargs.pop("distribution")
        if "dist" in kwargs and distribucion == "gaussian":
            distribucion = kwargs.pop("dist")
        if "smoothing" in kwargs and var_smoothing == 1e-9:
            var_smoothing = kwargs.pop("smoothing")
        if "laplace" in kwargs and alpha == 1.0:
            alpha = kwargs.pop("laplace")
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

        self._distribucion = self.NucleoBayesiano.normalizar_distribucion(
            distribucion
        )
        self._distribution = self._distribucion  # alias historico
        self._var_smoothing = max(0.0, float(var_smoothing))
        self._alpha = max(1e-12, float(alpha))
        self._fit_prior = bool(fit_prior)
        self._class_prior_config = class_prior
        self._prior_smoothing = max(0.0, float(prior_smoothing))
        self._binarize = None if binarize is None else float(binarize)
        self._seed = int(
            LUCIA_NB_CONFIG["random_seed"] if seed is None else seed
        )
        self._rng = np.random.default_rng(self._seed)

        self._nucleo = self.NucleoBayesiano(
            distribucion=self._distribucion,
            var_smoothing=self._var_smoothing,
            alpha=self._alpha,
            fit_prior=self._fit_prior,
            class_prior=None,
            prior_smoothing=self._prior_smoothing,
            binarize=self._binarize,
        )
        self._evaluador = self.EvaluadorBayesiano()

        self._classes: Optional[np.ndarray] = None
        self._n_classes: int = 0
        self._class_priors: Optional[np.ndarray] = None
        self._feature_mean: Optional[Dict[int, np.ndarray]] = None
        self._feature_var: Optional[Dict[int, np.ndarray]] = None
        self._parametros: Dict[str, np.ndarray] = {}
        self._is_fitted: bool = False
        self._n_samples: int = 0
        self._convergence_history: List[float] = []
        self._training_time: float = 0.0
        self._accuracy: float = 0.0
        self._learning_rate: float = 0.01

        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        """Naive Bayes no usa pesos lineales; se mantiene la API base."""
        self.pesos = None
        self.sesgo = None

    # ------------------------------------------------------------------
    # Validacion y preparacion de datos
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

    def _preprocesar_X(self, X: np.ndarray) -> np.ndarray:
        """Aplica binarizacion/validaciones propias de la distribucion."""
        matriz = np.array(X, dtype=np.float64, copy=True)
        if self._distribucion == "multinomial":
            if np.any(matriz < 0.0):
                raise ValueError(
                    "La distribucion multinomial requiere X >= 0"
                )
        elif self._distribucion == "bernoulli":
            if self._binarize is not None:
                matriz = (matriz > self._binarize).astype(np.float64)
            elif not np.all(np.isclose(matriz, 0.0) | np.isclose(matriz, 1.0)):
                raise ValueError(
                    "La distribucion Bernoulli requiere X binaria (0/1) "
                    "o un valor de binarize"
                )
        return matriz

    @staticmethod
    def _es_onehot(objetivo: np.ndarray) -> bool:
        if objetivo.ndim != 2 or objetivo.shape[1] < 2:
            return False
        if not np.all(np.isfinite(objetivo.astype(np.float64))):
            return False
        datos = objetivo.astype(np.float64)
        return bool(
            np.all(datos >= 0.0)
            and np.all(datos <= 1.0)
            and np.allclose(np.sum(datos, axis=1), 1.0)
        )

    def _preparar_objetivo(self, y: Any, n_muestras: int
                           ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        objetivo = np.asarray(y)
        if objetivo.ndim == 2:
            if objetivo.shape[1] == 1:
                objetivo = objetivo.reshape(-1)
            elif self._es_onehot(objetivo):
                objetivo = np.argmax(objetivo, axis=1)
            else:
                raise ValueError(
                    "y debe ser 1D, (n, 1) o una matriz one-hot"
                )
        if objetivo.ndim != 1:
            raise ValueError("y debe ser un vector 1D")
        if objetivo.shape[0] != n_muestras:
            raise ValueError(
                "X e y deben tener el mismo numero de muestras: "
                f"{n_muestras} != {objetivo.shape[0]}"
            )
        if objetivo.size == 0:
            raise ValueError("y no contiene muestras")
        if objetivo.dtype.kind in "fc" and not np.all(
            np.isfinite(objetivo.astype(np.float64))
        ):
            raise ValueError("y contiene valores no finitos")
        try:
            clases, codificado = np.unique(objetivo, return_inverse=True)
        except TypeError as error:
            raise ValueError(
                "Las etiquetas deben ser homogeneas y comparables"
            ) from error
        return codificado.astype(int), objetivo, clases

    def _pesos_muestra(self, n: int,
                       sample_weight: Optional[np.ndarray]) -> np.ndarray:
        if sample_weight is None:
            return np.ones(n, dtype=np.float64)
        pesos = np.asarray(sample_weight, dtype=np.float64).reshape(-1)
        if pesos.size != n:
            raise ValueError(
                f"sample_weight tiene {pesos.size} elementos y se "
                f"esperaban {n}"
            )
        if np.any(pesos < 0.0):
            raise ValueError("sample_weight no puede ser negativo")
        if float(np.sum(pesos)) <= self.NucleoBayesiano.EPS:
            raise ValueError("La suma de sample_weight debe ser positiva")
        return pesos

    def _resolver_class_prior(self, clases: np.ndarray) -> Optional[np.ndarray]:
        configuracion = self._class_prior_config
        if configuracion is None:
            return None
        if isinstance(configuracion, dict):
            prior = np.array([
                float(configuracion.get(clase, 0.0)) for clase in clases
            ], dtype=np.float64)
        else:
            prior = np.asarray(configuracion, dtype=np.float64).ravel()
        if prior.size != len(clases):
            raise ValueError(
                f"class_prior tiene {prior.size} elementos y se esperaban "
                f"{len(clases)}"
            )
        return prior

    # ------------------------------------------------------------------
    # Ajuste
    # ------------------------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 1,
            verbose: bool = False,
            sample_weight: Optional[np.ndarray] = None) -> List[float]:
        """Estima priors y parametros; devuelve el historial de log-loss."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        matriz = self._preprocesar_X(matriz)
        codificado, original, clases = self._preparar_objetivo(
            y, matriz.shape[0]
        )
        pesos = self._pesos_muestra(matriz.shape[0], sample_weight)
        class_prior = self._resolver_class_prior(clases)

        nucleo = self.NucleoBayesiano(
            distribucion=self._distribucion,
            var_smoothing=self._var_smoothing,
            alpha=self._alpha,
            fit_prior=self._fit_prior,
            class_prior=class_prior,
            prior_smoothing=self._prior_smoothing,
            binarize=self._binarize,
        )
        priors = nucleo.estimar_priors(codificado, len(clases), pesos)
        parametros = nucleo.estimar_parametros(
            matriz, codificado, len(clases), pesos
        )
        inicio = time.perf_counter()
        self._nucleo = nucleo
        self._classes = np.asarray(clases)
        self._n_classes = int(len(clases))
        self._class_priors = priors
        self._parametros = {**parametros, 'priors': priors}
        self._is_fitted = True
        self._n_samples = int(matriz.shape[0])
        self._actualizar_compatibilidad()
        self._accuracy = self.compute_accuracy(matriz, original)
        self._training_time = time.perf_counter() - inicio

        self._convergence_history = []
        perdidas: List[float] = []
        for epoca in range(max(1, int(epochs))):
            probabilidades = self.predict_proba(matriz)
            perdida = self.compute_loss(probabilidades, original)
            perdidas.append(float(perdida))
            self._convergence_history.append(float(perdida))
            if verbose and (epoca + 1) % 5 == 0:
                logger.info(
                    "NB Epoch %d, loss=%.6f", epoca + 1, perdida
                )
        if hasattr(self, "registrar_perdida") and perdidas:
            self.registrar_perdida(perdidas[-1])
        return perdidas

    def _actualizar_compatibilidad(self) -> None:
        """Rellena ``_feature_mean``/``_feature_var`` historicos."""
        self._feature_mean = {}
        self._feature_var = {}
        if not self._parametros:
            return
        if self._distribucion == "gaussian":
            medias = np.asarray(self._parametros.get('means'))
            varianzas = np.asarray(self._parametros.get('vars'))
            for feature in range(self.input_size):
                self._feature_mean[feature] = medias[feature].copy()
                self._feature_var[feature] = varianzas[feature].copy()
        elif 'theta' in self._parametros:
            theta = np.asarray(self._parametros['theta'])
            for feature in range(self.input_size):
                self._feature_mean[feature] = theta[feature].copy()
                self._feature_var[feature] = np.zeros(
                    self._n_classes, dtype=np.float64
                )

    # ------------------------------------------------------------------
    # Prediccion
    # ------------------------------------------------------------------
    def joint_log_likelihood(self, X: np.ndarray) -> np.ndarray:
        """Matriz (n, clases) de log p(clase) + log p(X | clase)."""
        if not self._is_fitted:
            raise RuntimeError("Modelo no entrenado: llama a fit primero")
        matriz, unico = self._validar_entrada(X)
        matriz = self._preprocesar_X(matriz)
        log_joint = self._nucleo.log_joint(
            matriz, self._parametros, self._class_priors
        )
        return log_joint[0] if unico else log_joint

    def predict_log_proba(self, X: np.ndarray) -> np.ndarray:
        """Log-posterior estable."""
        if not self._is_fitted:
            raise RuntimeError("Modelo no entrenado: llama a fit primero")
        matriz, unico = self._validar_entrada(X)
        matriz = self._preprocesar_X(matriz)
        log_joint = self._nucleo.log_joint(
            matriz, self._parametros, self._class_priors
        )
        log_posterior = self._evaluador.normalizar_log_probs(log_joint)
        return log_posterior[0] if unico else log_posterior

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilidades posteriores por clase."""
        log_posterior = self.predict_log_proba(X)
        probabilidades = np.exp(log_posterior)
        # Re-normaliza por seguridad numerica.
        if probabilidades.ndim == 1:
            total = float(np.sum(probabilidades))
            return probabilidades / total if total > 0 else probabilidades
        totales = np.sum(probabilidades, axis=1, keepdims=True)
        return np.divide(
            probabilidades, totales,
            out=np.zeros_like(probabilidades),
            where=totales > 0,
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Etiqueta de clase mas probable."""
        probabilidades = self.predict_proba(X)
        if probabilidades.ndim == 1:
            return np.asarray(self._classes)[int(np.argmax(probabilidades))]
        return np.asarray(self._classes)[np.argmax(probabilidades, axis=1)]

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Posterior de la neurona (API forward de la jerarquia)."""
        matriz, unico = self._validar_entrada(entrada)
        salida = self.predict_proba(matriz)
        self.historial_activaciones.append(np.array(salida, copy=True))
        self.pasos += 1
        return salida[0] if unico else salida

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax estable (compatibilidad historica)."""
        datos = np.asarray(x, dtype=np.float64)
        unico = datos.ndim == 1
        if unico:
            datos = datos.reshape(1, -1)
        log_norm = self.NucleoBayesiano.logsumexp(
            datos, axis=1, keepdims=True
        )
        resultado = np.exp(datos - log_norm)
        return resultado[0] if unico else resultado

    # ------------------------------------------------------------------
    # Perdida y metricas
    # ------------------------------------------------------------------
    def _codificar_objetivo(self, objetivo: Any,
                            n: int) -> np.ndarray:
        arreglo = np.asarray(objetivo)
        if arreglo.ndim == 2:
            if self._es_onehot(arreglo):
                arreglo = np.argmax(arreglo, axis=1)
            elif arreglo.shape[1] == 1:
                arreglo = arreglo.reshape(-1)
            else:
                raise ValueError("Objetivo incompatible con la clasificacion")
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
            # Permite pasar indices codificados directamente.
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

    def compute_loss(self, prediccion: np.ndarray,
                     objetivo: np.ndarray) -> float:
        """Log-loss para probabilidades; MSE como compatibilidad."""
        proba = np.asarray(prediccion, dtype=np.float64)
        if proba.ndim == 2 and self._classes is not None \
                and proba.shape[1] == len(self._classes):
            codificado = self._codificar_objetivo(
                objetivo, proba.shape[0]
            )
            return self._evaluador.log_loss(proba, codificado)
        real = np.asarray(objetivo, dtype=np.float64)
        if proba.shape != real.shape:
            if proba.size == real.size:
                real = real.reshape(proba.shape)
            else:
                real = np.broadcast_to(real, proba.shape)
        return float(np.mean((proba - real) ** 2))

    def compute_accuracy(self, X: np.ndarray, y: np.ndarray) -> float:
        """Accuracy de clasificacion."""
        _, original, _ = self._preparar_objetivo(y, len(np.asarray(X)))
        prediccion = self.predict(X)
        return float(np.mean(
            np.asarray(prediccion).ravel() == np.asarray(original).ravel()
        ))

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """Accuracy (metrica principal de la neurona)."""
        return self.compute_accuracy(X, y)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Metricas completas de clasificacion."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        _, original, _ = self._preparar_objetivo(y, matriz.shape[0])
        probabilidades = self.predict_proba(matriz)
        prediccion = np.asarray(self._classes)[
            np.argmax(probabilidades, axis=1)
        ]
        metricas = self._evaluador.metricas(
            prediccion, original, probabilidades, self._classes
        )
        metricas['loss'] = self.compute_loss(probabilidades, original)
        return metricas

    # ------------------------------------------------------------------
    # Informacion y estabilidad
    # ------------------------------------------------------------------
    def _arreglos_parametros(self) -> List[np.ndarray]:
        return [
            np.asarray(valor, dtype=np.float64)
            for valor in self._parametros.values()
            if valor is not None
        ]

    @property
    def classes_(self) -> Optional[np.ndarray]:
        """Etiquetas de clase ordenadas (compatibilidad sklearn)."""
        return None if self._classes is None else self._classes.copy()

    @property
    def class_prior_(self) -> Optional[np.ndarray]:
        """Priors estimados o impuestos."""
        return (None if self._class_priors is None
                else self._class_priors.copy())

    def params_count(self) -> int:
        """Numero de parametros libres (priors + verosimilitudes)."""
        total = 0
        if 'priors' in self._parametros:
            total += int(np.size(self._parametros['priors']))
        if self._distribucion == "gaussian":
            if 'means' in self._parametros:
                total += int(np.size(self._parametros['means']))
            if 'vars' in self._parametros:
                total += int(np.size(self._parametros['vars']))
        elif 'theta' in self._parametros:
            total += int(np.size(self._parametros['theta']))
        return int(total)

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'naive_bayes',
            'distribution': self._distribucion,
            'var_smoothing': self._var_smoothing,
            'alpha': self._alpha,
            'fit_prior': self._fit_prior,
            'prior_smoothing': self._prior_smoothing,
            'binarize': self._binarize,
            'is_fitted': self._is_fitted,
            'n_samples': self._n_samples,
            'n_classes': self._n_classes,
            'accuracy': self._accuracy,
            'n_parametros': self.params_count(),
            'training_time': self._training_time,
            'nucleo': self._nucleo.resumen(),
            'evaluador': self._evaluador.resumen(),
        })
        if self._classes is not None:
            stats['classes'] = self._classes.tolist()
        if self._class_priors is not None:
            stats['class_priors'] = self._class_priors.tolist()
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
            stats['initial_loss'] = float(self._convergence_history[0])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprobaciones numericas del modelo bayesiano."""
        ok: Dict[str, bool] = {
            'estado_entrenado': bool(self._is_fitted),
            'parametros_inicializados': bool(self._parametros),
        }
        if self._parametros:
            arreglos = self._arreglos_parametros()
            ok['parametros_finitos'] = all(
                bool(np.all(np.isfinite(a))) for a in arreglos
            )
            ok['sin_nan'] = all(
                not bool(np.any(np.isnan(a))) for a in arreglos
            )
            ok['sin_inf'] = all(
                not bool(np.any(np.isinf(a))) for a in arreglos
            )
        if self._class_priors is not None:
            ok['priores_normalizados'] = bool(np.isclose(
                float(np.sum(self._class_priors)), 1.0, atol=1e-8
            ))
        if self._distribucion == "gaussian" \
                and 'vars' in self._parametros:
            ok['varianzas_positivas'] = bool(
                np.all(np.asarray(self._parametros['vars']) > 0.0)
            )
        if self._classes is not None:
            ok['clases_validas'] = bool(len(self._classes) >= 1)
        if self.pesos is not None:
            ok['pesos_no_nan'] = not bool(np.any(np.isnan(self.pesos)))
            ok['pesos_no_inf'] = not bool(np.any(np.isinf(self.pesos)))
        ok['estable'] = all(ok.values())
        return ok

    # ------------------------------------------------------------------
    # Serializacion y configuracion
    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        """Guarda parametros, priors, clases y configuracion."""
        estado = {
            'version': __version__,
            'tipo': 'NeuronaNaiveBayes',
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'distribution': self._distribucion,
            'var_smoothing': self._var_smoothing,
            'alpha': self._alpha,
            'fit_prior': self._fit_prior,
            'class_prior': self._class_prior_config,
            'prior_smoothing': self._prior_smoothing,
            'binarize': self._binarize,
            'seed': self._seed,
            'is_fitted': self._is_fitted,
            'pasos': self.pasos,
            'classes': self._classes,
            'n_classes': self._n_classes,
            'class_priors': self._class_priors,
            'parametros': self._parametros,
            'feature_mean': self._feature_mean,
            'feature_var': self._feature_var,
            'accuracy': self._accuracy,
            'n_samples': self._n_samples,
            'convergence_history': list(self._convergence_history),
            'training_time': self._training_time,
            'pesos': self.pesos,
            'sesgo': self.sesgo,
            'learning_rate': self._learning_rate,
        }
        with open(filepath, 'wb') as archivo:
            pickle.dump(estado, archivo, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        """Carga checkpoints nuevos o el formato historico de RF_SL1_6."""
        with open(filepath, 'rb') as archivo:
            estado = pickle.load(archivo)
        if not isinstance(estado, dict):
            raise TypeError("El fichero no contiene un checkpoint valido")

        self.nombre = str(estado.get('nombre', self.nombre))
        self.input_size = int(estado.get('input_size', self.input_size))
        self.output_size = int(estado.get('output_size', self.output_size))
        self._distribucion = self.NucleoBayesiano.normalizar_distribucion(
            estado.get('distribution', estado.get('distribucion', 'gaussian'))
        )
        self._distribution = self._distribucion
        self._var_smoothing = max(
            0.0, float(estado.get('var_smoothing', 1e-9))
        )
        self._alpha = max(1.0e-12, float(estado.get('alpha', 1.0)))
        self._fit_prior = bool(estado.get('fit_prior', True))
        self._class_prior_config = estado.get('class_prior', None)
        self._prior_smoothing = max(
            0.0, float(estado.get('prior_smoothing', 1e-10))
        )
        self._binarize = estado.get('binarize', None)
        self._seed = int(
            estado.get('seed', LUCIA_NB_CONFIG["random_seed"])
        )
        self._rng = np.random.default_rng(self._seed)
        self._learning_rate = float(estado.get('learning_rate', 0.01))

        clases = estado.get('classes')
        priors = estado.get('class_priors')
        if clases is None and priors is not None:
            clases = np.arange(len(priors))
        self._classes = None if clases is None else np.asarray(clases)
        self._n_classes = (int(estado.get('n_classes', 0))
                           or (len(self._classes)
                               if self._classes is not None else 0))
        self._class_priors = (
            None if priors is None
            else np.asarray(priors, dtype=np.float64)
        )

        parametros = estado.get('parametros')
        if parametros is None:
            parametros = self._reconstruir_parametros_legado(estado)
            # El formato historico solo guardaba medias y varianzas.
            self._distribucion = "gaussian"
            self._distribution = self._distribucion
        self._parametros = parametros
        self._nucleo = self.NucleoBayesiano(
            distribucion=self._distribucion,
            var_smoothing=self._var_smoothing,
            alpha=self._alpha,
            fit_prior=self._fit_prior,
            class_prior=None,
            prior_smoothing=self._prior_smoothing,
            binarize=self._binarize,
        )
        self._evaluador = self.EvaluadorBayesiano()
        self._is_fitted = bool(estado.get(
            'is_fitted', bool(self._parametros)
        ))
        self.pasos = int(estado.get('pasos', 0))
        self._accuracy = float(estado.get('accuracy', 0.0))
        self._n_samples = int(estado.get('n_samples', 0))
        self._convergence_history = [
            float(v) for v in estado.get('convergence_history', [])
        ]
        self._training_time = float(estado.get('training_time', 0.0))
        self.pesos = estado.get('pesos')
        self.sesgo = estado.get('sesgo')
        self._feature_mean = estado.get('feature_mean')
        self._feature_var = estado.get('feature_var')
        if self._feature_mean is None or self._feature_var is None:
            self._actualizar_compatibilidad()

    def _reconstruir_parametros_legado(
        self, estado: Dict[str, Any],
    ) -> Dict[str, np.ndarray]:
        """Reconstruye matrices desde feature_mean/feature_var historicos."""
        clases = estado.get('classes')
        priors = estado.get('class_priors')
        if priors is None and clases is not None:
            priors = np.full(len(clases), 1.0 / max(1, len(clases)))
        if priors is None:
            priors = np.ones(1, dtype=np.float64)
        priors = np.asarray(priors, dtype=np.float64)
        n_classes = int(priors.size)
        n_features = int(estado.get('input_size', self.input_size))
        medias = np.zeros((n_features, n_classes), dtype=np.float64)
        varianzas = np.ones((n_features, n_classes), dtype=np.float64)
        medias_guardadas = estado.get('feature_mean') or {}
        vars_guardadas = estado.get('feature_var') or {}
        for feature in range(n_features):
            media = medias_guardadas.get(feature)
            varianza = vars_guardadas.get(feature)
            if media is not None:
                valores = np.asarray(media, dtype=np.float64).ravel()
                medias[feature, :min(n_classes, valores.size)] = (
                    valores[:n_classes]
                )
            if varianza is not None:
                valores = np.asarray(varianza, dtype=np.float64).ravel()
                varianzas[feature, :min(n_classes, valores.size)] = (
                    np.maximum(valores[:n_classes], 1e-12)
                )
        return {
            'priors': priors,
            'means': medias,
            'vars': varianzas,
        }

    def get_config(self) -> Dict[str, Any]:
        """Configuracion reproducible del clasificador."""
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'distribucion': self._distribucion,
            'var_smoothing': self._var_smoothing,
            'alpha': self._alpha,
            'fit_prior': self._fit_prior,
            'class_prior': self._class_prior_config,
            'prior_smoothing': self._prior_smoothing,
            'binarize': self._binarize,
            'seed': self._seed,
        }

    def summary(self) -> str:
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {self.nombre} ===",
            (f"Distribucion: {self._distribucion}, "
             f"Smoothing: {self._var_smoothing}, Alpha: {self._alpha}"),
            (f"Input: {self.input_size}, Output: {self.output_size}, "
             f"Clases: {stats.get('n_classes', 0)}"),
            (f"Fitted: {stats.get('is_fitted', False)}, "
             f"Acc: {stats.get('accuracy', 0.0):.4f}, "
             f"Params: {self.params_count()}"),
            (f"Final loss: {stats.get('final_loss', 'N/A')}"),
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"


# ---------------------------------------------------------------------------
# Utilidades historicas de distribuciones
# ---------------------------------------------------------------------------
class GaussianDistribution:
    @staticmethod
    def pdf(x: np.ndarray, mean: float, var: float) -> np.ndarray:
        varianza = max(float(var), 1e-12)
        return (np.exp(-0.5 * ((x - mean) ** 2) / varianza)
                / np.sqrt(2.0 * math.pi * varianza))

    @staticmethod
    def log_pdf(x: np.ndarray, mean: float, var: float) -> np.ndarray:
        varianza = max(float(var), 1e-12)
        return (-0.5 * np.log(2.0 * math.pi * varianza)
                - ((x - mean) ** 2) / (2.0 * varianza))

    @staticmethod
    def fit(X: np.ndarray,
            weights: Optional[np.ndarray] = None
            ) -> Tuple[Any, Any]:
        datos = np.asarray(X, dtype=np.float64)
        unico = datos.ndim == 1
        if unico:
            datos = datos.reshape(-1, 1)
        if weights is None:
            w = np.ones(datos.shape[0], dtype=np.float64)
        else:
            w = np.asarray(weights, dtype=np.float64).reshape(-1)
        total = float(np.sum(w))
        if total <= 1e-12:
            media = np.zeros(datos.shape[1])
            varianza = np.ones(datos.shape[1])
        else:
            media = np.sum(w[:, None] * datos, axis=0) / total
            varianza = np.sum(
                w[:, None] * (datos - media) ** 2, axis=0
            ) / total
            varianza = np.maximum(varianza, 1e-12)
        if unico:
            return float(media[0]), float(varianza[0])
        return media, varianza


class LaplaceSmoother:
    def __init__(self, alpha: float = 1.0):
        self.alpha = max(1e-12, float(alpha))

    def smooth(self, counts: np.ndarray, n_classes: int) -> np.ndarray:
        conteos = np.asarray(counts, dtype=np.float64)
        return (conteos + self.alpha) / (
            float(np.sum(conteos)) + self.alpha * max(1, n_classes)
        )

    def get_smoothed_prob(self, count: float, total: float,
                          n_classes: int) -> float:
        return float(
            (float(count) + self.alpha)
            / (float(total) + self.alpha * max(1, n_classes))
        )


class FeatureLikelihood:
    """Compatibilidad: verosimilitud por caracteristica y clase."""

    def __init__(self, n_features: int, n_classes: int,
                 distribution: str = "gaussian",
                 var_smoothing: float = 1e-9,
                 alpha: float = 1.0) -> None:
        self.n_features = int(n_features)
        self.n_classes = int(n_classes)
        self.distribution = distribution
        self.var_smoothing = float(var_smoothing)
        self.alpha = float(alpha)
        self._means = np.zeros((self.n_features, self.n_classes))
        self._vars = np.ones((self.n_features, self.n_classes))
        self._theta: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: np.ndarray,
            weights: Optional[np.ndarray] = None) -> None:
        self._theta = None
        matriz = np.asarray(X, dtype=np.float64)
        etiquetas = np.asarray(y)
        if etiquetas.ndim > 1:
            etiquetas = etiquetas.ravel()
        if etiquetas.dtype.kind not in "iu":
            _, etiquetas = np.unique(etiquetas, return_inverse=True)
        etiquetas = etiquetas.astype(int)
        if etiquetas.size and int(np.max(etiquetas)) >= self.n_classes:
            raise ValueError(
                f"y tiene mas clases que las declaradas ({self.n_classes})"
            )
        nucleo = NeuronaNaiveBayes.NucleoBayesiano(
            distribucion=self.distribution,
            var_smoothing=self.var_smoothing,
            alpha=self.alpha,
        )
        parametros = nucleo.estimar_parametros(
            matriz, etiquetas, self.n_classes, weights
        )
        if 'means' in parametros:
            self._means = np.asarray(parametros['means'])
            self._vars = np.asarray(parametros['vars'])
        elif 'theta' in parametros:
            self._theta = np.asarray(parametros['theta'])
            self._means = self._theta.copy()
            self._vars = np.zeros_like(self._theta)

    def get_means(self) -> np.ndarray:
        return self._means.copy()

    def get_vars(self) -> np.ndarray:
        return self._vars.copy()

    def get_feature_log_prob(self) -> np.ndarray:
        if self._theta is None:
            raise ValueError("La distribucion estimada no es discreta")
        return np.log(np.maximum(self._theta, 1e-12))


# ---------------------------------------------------------------------------
# Adaptador de compatibilidad con la API historica de RF_SL1_6
# ---------------------------------------------------------------------------
class NaiveBayesOptimizer(NeuronaNaiveBayes):
    """Naive Bayes real con la API historica de ``NaiveBayesOptimizer``.

    Conserva la cabeza lineal legada (``forward``/``backward``) para no romper
    consumidores antiguos. ``fit``, ``predict`` y ``predict_proba`` usan el
    clasificador bayesiano real.
    """

    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NaiveBayesOptimizer",
        **kwargs: Any,
    ) -> None:
        tasa = float(kwargs.pop("learning_rate", 0.01))
        super().__init__(
            input_size=input_size, output_size=output_size,
            nombre=nombre, **kwargs,
        )
        self._learning_rate = tasa
        self._velocity_w = (np.zeros_like(self.pesos)
                            if self.pesos is not None else None)
        self._velocity_b = (np.zeros_like(self.sesgo)
                            if self.sesgo is not None else None)

    def inicializar_pesos(self) -> None:
        """Cabeza lineal minima para los metodos historicos."""
        generador = getattr(self, "_rng", np.random.default_rng(2026))
        self.pesos = generador.normal(
            0.0, 0.1, (self.input_size, self.output_size)
        ).astype(np.float32)
        self.sesgo = np.zeros((1, self.output_size), dtype=np.float32)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Cabeza lineal historica (``predict`` usa Naive Bayes)."""
        matriz, unico = self._validar_entrada(entrada)
        salida = np.dot(matriz, self.pesos) + self.sesgo
        self.historial_activaciones.append(np.array(salida, copy=True))
        self.pasos += 1
        return salida[0] if unico else salida

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Gradientes de la cabeza lineal (compatibilidad historica)."""
        matriz, _ = self._validar_entrada(entrada)
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(1, -1)
        if gradiente.shape[0] != matriz.shape[0]:
            raise ValueError(
                "El gradiente y la entrada deben tener el mismo numero de "
                "muestras"
            )
        grad_pesos = matriz.T @ gradiente
        grad_sesgo = np.sum(gradiente, axis=0, keepdims=True)
        self.historial_gradientes.append({
            'pesos': grad_pesos.copy(),
            'norma': float(np.linalg.norm(grad_pesos)),
        })
        return grad_pesos, grad_sesgo

    def get_config(self) -> Dict[str, Any]:
        configuracion = super().get_config()
        configuracion['learning_rate'] = self._learning_rate
        return configuracion


# ---------------------------------------------------------------------------
# Fabrica, utilidades y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "gaussian", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaNaiveBayes:
    """Fabrica un clasificador Naive Bayes por nombre.

    Tipos: ``gaussian``/``nb``, ``multinomial``, ``bernoulli`` y ``compat``
    (adaptador historico).
    """
    clave = str(tipo or "gaussian").strip().lower().replace("-", "_")
    if clave in ("gaussian", "gauss", "gaussiana", "nb",
                 "naive_bayes", "naivebayes", "normal"):
        kwargs.setdefault("distribucion", "gaussian")
        return NeuronaNaiveBayes(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("multinomial", "multinomial_nb", "counts", "conteos"):
        kwargs.setdefault("distribucion", "multinomial")
        return NeuronaNaiveBayes(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("bernoulli", "bernoulli_nb", "binomial", "binaria"):
        kwargs.setdefault("distribucion", "bernoulli")
        return NeuronaNaiveBayes(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("compat", "naive_bayes_optimizer", "optimizer"):
        return NaiveBayesOptimizer(
            input_size=input_size, output_size=output_size, **kwargs
        )
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: gaussian, multinomial, "
        "bernoulli, compat"
    )


def tipos_disponibles() -> List[str]:
    """Nombres aceptados por :func:`crear_neurona`."""
    return ["gaussian", "multinomial", "bernoulli", "compat"]


def create_naive_bayes_optimizer(
    input_size: int = 4, output_size: int = 8, **kwargs: Any,
) -> NaiveBayesOptimizer:
    """Fabrica historica de RF_SL1_6."""
    return NaiveBayesOptimizer(
        input_size=input_size, output_size=output_size, **kwargs
    )


def entrenar_y_evaluar(modelo: NeuronaNaiveBayes, X: np.ndarray,
                       y: np.ndarray, epochs: int = 1,
                       **kwargs: Any) -> Dict[str, Any]:
    """Entrena y devuelve historial y metricas en una sola llamada."""
    historial = modelo.fit(X, y, epochs=epochs, **kwargs)
    return {
        'modelo': modelo,
        'historial': historial,
        'metricas': modelo.evaluate(X, y),
        'perdida_final': float(historial[-1]) if historial else float('nan'),
    }


def benchmark_modelo(modelo: NeuronaNaiveBayes, X: np.ndarray,
                     repeticiones: int = 5) -> Dict[str, float]:
    """Mide el tiempo de inferencia del clasificador."""
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


def guardar_modelo(modelo: NeuronaNaiveBayes, ruta: str) -> None:
    """Serializa el objeto completo (pickle)."""
    with open(ruta, 'wb') as archivo:
        pickle.dump(modelo, archivo, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaNaiveBayes:
    """Carga un modelo serializado con :func:`guardar_modelo`."""
    with open(ruta, 'rb') as archivo:
        modelo = pickle.load(archivo)
    if not isinstance(modelo, NeuronaNaiveBayes):
        raise TypeError("El fichero no contiene un Naive Bayes")
    return modelo


# ---------------------------------------------------------------------------
# Demostracion
# ---------------------------------------------------------------------------
def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_6_1.py``)."""
    generador = np.random.default_rng(2026)
    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_6_1 :: Naive Bayes (v%s)" % __version__)
    print("=" * 78)

    # 1) Gaussiano: tres clases en 2D.
    n = 360
    centros = np.array([[0.0, 0.0], [3.0, 0.0], [1.5, 3.0]])
    etiquetas = generador.integers(0, 3, size=n)
    X = centros[etiquetas] + generador.normal(scale=0.65, size=(n, 2))
    y = np.array(["rojo", "verde", "azul"])[etiquetas]
    gauss = crear_neurona("gaussian", 2, 3, var_smoothing=1e-8, seed=7)
    gauss.fit(X, y)
    met = gauss.evaluate(X, y)
    print("%-12s accuracy=%.4f log_loss=%.4f | params=%d"
          % ("gaussian", met['accuracy'], met['log_loss'],
             gauss.params_count()))

    # 2) Multinomial: conteos de palabras por clase.
    n_docs = 300
    vocabulario = 6
    probabilidades = np.array([
        [0.40, 0.20, 0.10, 0.10, 0.10, 0.10],
        [0.10, 0.10, 0.40, 0.20, 0.10, 0.10],
        [0.10, 0.10, 0.10, 0.10, 0.30, 0.30],
    ])
    clases_multi = generador.integers(0, 3, size=n_docs)
    X_multi = np.vstack([
        generador.multinomial(20, probabilidades[clase])
        for clase in clases_multi
    ]).astype(np.float64)
    multi = crear_neurona("multinomial", vocabulario, 3,
                          alpha=1.0, seed=11)
    multi.fit(X_multi, clases_multi)
    met_multi = multi.evaluate(X_multi, clases_multi)
    print("%-12s accuracy=%.4f log_loss=%.4f | params=%d"
          % ("multinomial", met_multi['accuracy'],
             met_multi['log_loss'], multi.params_count()))

    # 3) Bernoulli: caracteristicas binarias.
    n_ber = 300
    probas = np.array([
        [0.85, 0.15, 0.80, 0.20],
        [0.15, 0.85, 0.20, 0.80],
    ])
    clases_ber = generador.integers(0, 2, size=n_ber)
    X_ber = (generador.random((n_ber, 4))
             < probas[clases_ber]).astype(np.float64)
    bern = crear_neurona("bernoulli", 4, 2, alpha=1.0, seed=13)
    bern.fit(X_ber, clases_ber)
    met_ber = bern.evaluate(X_ber, clases_ber)
    print("%-12s accuracy=%.4f log_loss=%.4f | params=%d"
          % ("bernoulli", met_ber['accuracy'], met_ber['log_loss'],
             bern.params_count()))
    print("Probabilidades (3):",
          np.round(gauss.predict_proba(X[:3]), 3).tolist())
    print("Estabilidad:", gauss.verificar_estabilidad())
    print("Benchmark:", benchmark_modelo(gauss, X, repeticiones=3))
    print("=" * 78)
    return {
        'gaussian': met,
        'multinomial': met_multi,
        'bernoulli': met_ber,
    }


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaNaiveBayes',
    'NaiveBayesOptimizer',
    'GaussianDistribution',
    'LaplaceSmoother',
    'FeatureLikelihood',
    'crear_neurona',
    'tipos_disponibles',
    'create_naive_bayes_optimizer',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_NB_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
