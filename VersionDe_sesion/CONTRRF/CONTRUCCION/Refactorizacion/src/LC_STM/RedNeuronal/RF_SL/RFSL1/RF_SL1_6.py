"""
RF_SL1_6.py - Naive Bayes avanzado (puente legado)
==================================================

Este modulo ya no reimplementa el clasificador Naive Bayes. La implementacion
unica vive en el modulo especializado:

    RF_SL_SBRTM_RF_SL1_6/RF_SL_SBRTM_RF_SL1_6_1.py

Desde alli se importan ``NeuronaNaiveBayes``, el adaptador historico
``NaiveBayesOptimizer``, la base compartida ``NeuronaMemoriaBase``, las
distribuciones historicas (``GaussianDistribution``, ``LaplaceSmoother``,
``FeatureLikelihood``) y las funciones nuevas (fabrica, metricas, benchmark,
persistencia y demo). El resto del archivo conserva las utilidades historicas
que no tienen equivalente directo (``PriorEstimator``, ``BayesianClassifier``,
``ModelEvaluator``, ``BernoulliLikelihood``, ``MultinomialNB`` y
``ConfusionMatrix``).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Naive Bayes: fuente unica en el modulo especializado RF_SL_SBRTM_RF_SL1_6.
#
# Se importan sus clases (Gaussian/Multinomial/Bernoulli, priors, suavizado,
# log-posterior estable y metricas) y sus funciones nuevas. El antiguo bloque
# local de NaiveBayesOptimizer y de las distribuciones (lineas 60-277) queda
# sustituido por este import, sin dejar definiciones duplicadas.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_6.RF_SL_SBRTM_RF_SL1_6_1 import (
        LUCIA_NB_CONFIG,
        FeatureLikelihood,
        GaussianDistribution,
        LaplaceSmoother,
        NaiveBayesOptimizer,
        NeuronaMemoriaBase,
        NeuronaNaiveBayes,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        create_naive_bayes_optimizer,
        demo,
        entrenar_y_evaluar,
        guardar_modelo,
        tipos_disponibles,
    )
except (ImportError, ValueError):
    # Fallback por ruta para cargas por fichero o sin paquete padre.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_MODULO = "_rf_sl1_6_nb_import"
    _modulo_nb = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_nb is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_6",
            "RF_SL_SBRTM_RF_SL1_6_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_nb = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_nb
        _especificacion.loader.exec_module(_modulo_nb)
    LUCIA_NB_CONFIG = _modulo_nb.LUCIA_NB_CONFIG
    FeatureLikelihood = _modulo_nb.FeatureLikelihood
    GaussianDistribution = _modulo_nb.GaussianDistribution
    LaplaceSmoother = _modulo_nb.LaplaceSmoother
    NaiveBayesOptimizer = _modulo_nb.NaiveBayesOptimizer
    NeuronaMemoriaBase = _modulo_nb.NeuronaMemoriaBase
    NeuronaNaiveBayes = _modulo_nb.NeuronaNaiveBayes
    benchmark_modelo = _modulo_nb.benchmark_modelo
    cargar_modelo = _modulo_nb.cargar_modelo
    crear_neurona = _modulo_nb.crear_neurona
    create_naive_bayes_optimizer = _modulo_nb.create_naive_bayes_optimizer
    demo = _modulo_nb.demo
    entrenar_y_evaluar = _modulo_nb.entrenar_y_evaluar
    guardar_modelo = _modulo_nb.guardar_modelo
    tipos_disponibles = _modulo_nb.tipos_disponibles

# Acceso directo a las clases anidadas del nucleo y del evaluador.
NucleoBayesiano = NeuronaNaiveBayes.NucleoBayesiano
EvaluadorBayesiano = NeuronaNaiveBayes.EvaluadorBayesiano

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades historicas sin equivalente directo en el modulo especializado
# ---------------------------------------------------------------------------
class PriorEstimator:
    def __init__(self, smoothing: float = 1e-8):
        self.smoothing = smoothing

    def estimate(self, y: np.ndarray, n_classes: int) -> np.ndarray:
        counts = np.bincount(y.astype(int), minlength=n_classes)
        return (counts + self.smoothing) / (
            counts.sum() + self.smoothing * n_classes
        )

    def log_prior(self, y: np.ndarray, n_classes: int) -> np.ndarray:
        priors = self.estimate(y, n_classes)
        return np.log(np.maximum(1e-8, priors))


class BayesianClassifier:
    def __init__(self, distribution: str = "gaussian",
                 var_smoothing: float = 1e-9):
        self.distribution = distribution
        self.var_smoothing = var_smoothing
        self.prior = PriorEstimator()
        self.likelihood = None
        self._is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BayesianClassifier":
        n_classes = len(np.unique(y))
        self.priors = self.prior.estimate(y, n_classes)
        self.likelihood = FeatureLikelihood(
            X.shape[1], n_classes, self.distribution
        )
        self.likelihood.fit(X, y)
        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("No entrenado")
        n = len(X)
        n_classes = len(self.priors)
        log_probs = np.zeros((n, n_classes))
        for c in range(n_classes):
            log_probs[:, c] = np.log(self.priors[c] + 1e-8)
            for f in range(X.shape[1]):
                mean = self.likelihood.get_means()[f][c]
                var = self.likelihood.get_vars()[f][c]
                log_probs[:, c] += GaussianDistribution.log_pdf(
                    X[:, f], mean, var
                )
        return np.argmax(log_probs, axis=1)


class ModelEvaluator:
    def __init__(self, cv_folds: int = 5):
        self.cv_folds = cv_folds
        self._scores: List[float] = []

    def cross_validate(self, model, X: np.ndarray,
                       y: np.ndarray) -> List[float]:
        n = len(X)
        fold_size = n // self.cv_folds
        scores = []
        for i in range(self.cv_folds):
            start = i * fold_size
            end = start + fold_size if i < self.cv_folds - 1 else n
            X_test = X[start:end]
            y_test = y[start:end]
            X_train = np.concatenate([X[:start], X[end:]])
            y_train = np.concatenate([y[:start], y[end:]])
            model_copy = type(model)(
                X.shape[1], max(2, int(np.max(y)) + 1)
            )
            model_copy.fit(X_train, y_train)
            scores.append(model_copy.compute_accuracy(X_test, y_test))
        self._scores = scores
        return scores

    def get_mean_score(self) -> float:
        return float(np.mean(self._scores)) if self._scores else 0.0

    def get_std_score(self) -> float:
        return float(np.std(self._scores)) if self._scores else 0.0

    def get_scores(self) -> List[float]:
        return self._scores.copy()


class BernoulliLikelihood:
    @staticmethod
    def fit(X: np.ndarray, y: np.ndarray, n_classes: int,
            alpha: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        n_features = X.shape[1]
        means = np.zeros((n_features, n_classes))
        vars_ = np.ones((n_features, n_classes))
        for c in range(n_classes):
            mask = y == c
            if mask.sum() > 0:
                means[:, c] = np.mean(X[mask], axis=0) * alpha
                vars_[:, c] = np.var(X[mask], axis=0) + alpha
        return means, vars_

    @staticmethod
    def log_likelihood(X: np.ndarray, means: np.ndarray,
                       vars_: np.ndarray) -> np.ndarray:
        n, n_features = X.shape
        n_classes = means.shape[1]
        ll = np.zeros((n, n_classes))
        for c in range(n_classes):
            diff = X - means[:, c]
            ll[:, c] = -0.5 * np.sum(
                np.log(vars_[:, c] + 1e-8)
                + diff ** 2 / (vars_[:, c] + 1e-8),
                axis=1,
            )
        return ll


class MultinomialNB:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self._classes = None
        self._log_prior = None
        self._log_likelihood = None
        self._is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "MultinomialNB":
        n_classes = len(np.unique(y))
        self._classes = np.unique(y)
        n_features = X.shape[1]
        self._log_prior = np.zeros(n_classes)
        self._log_likelihood = np.zeros((n_features, n_classes))
        for c, cls in enumerate(self._classes):
            mask = y == cls
            count = mask.sum()
            self._log_prior[c] = np.log(count / len(y))
            class_counts = np.zeros(n_features)
            for i in range(n_features):
                class_counts[i] = X[mask][:, i].sum()
            total = class_counts.sum() + self.alpha * n_features
            self._log_likelihood[:, c] = np.log(
                (class_counts + self.alpha) / total
            )
        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("No entrenado")
        scores = X @ self._log_likelihood + self._log_prior.T
        return self._classes[np.argmax(scores, axis=1)]


class ConfusionMatrix:
    def __init__(self, n_classes: int):
        self.n_classes = n_classes
        self._matrix = np.zeros((n_classes, n_classes), dtype=int)

    def update(self, y_true: np.ndarray, y_pred: np.ndarray) -> None:
        for t, p in zip(y_true.astype(int), y_pred.astype(int)):
            if 0 <= t < self.n_classes and 0 <= p < self.n_classes:
                self._matrix[t][p] += 1

    def get_matrix(self) -> np.ndarray:
        return self._matrix.copy()

    def accuracy(self) -> float:
        total = self._matrix.sum()
        return float(np.trace(self._matrix) / max(1, total))


# ``create_naive_bayes_optimizer`` se importa del modulo especializado para no
# duplicar la fabrica. Se conserva el mismo nombre y firma historica.


if __name__ == "__main__":
    logger.info("RF_SL1_6.py cargado exitosamente")
