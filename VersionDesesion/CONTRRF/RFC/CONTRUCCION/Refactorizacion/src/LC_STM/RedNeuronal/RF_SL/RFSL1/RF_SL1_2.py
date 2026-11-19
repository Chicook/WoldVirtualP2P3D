"""
RF_SL1_2.py - Support Vector Machines Avanzados (SVM)
Optimizado con clases inline y estructura eficiente.
"""
import numpy as np
import logging
import time
import pickle
from typing import Dict, Any, List, Optional, Tuple

class NeuronaMemoriaBase:
    def __init__(self, input_size: int, output_size: int, nombre: str = "Neurona"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos = None
        self.sesgo = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[Dict[str, np.ndarray]] = []
        self.pasos = 0

    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, e: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = {
            'nombre': self.nombre, 'input_size': self.input_size,
            'output_size': self.output_size, 'pasos': self.pasos,
            'historial_activaciones_len': len(self.historial_activaciones),
            'historial_gradientes_len': len(self.historial_gradientes),
        }
        if self.pesos is not None:
            stats['pesos_shape'] = self.pesos.shape
            stats['pesos_size'] = self.pesos.size
        if self.sesgo is not None:
            stats['sesgo_shape'] = self.sesgo.shape
        return stats

    def resetear_historial(self) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()

    def info(self) -> str:
        return f"{self.nombre}(in={self.input_size},out={self.output_size},pasos={self.pasos})"

    def params_count(self) -> int:
        total = 0
        if self.pesos is not None: total += self.pesos.size
        if self.sesgo is not None: total += self.sesgo.size
        return total

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SupportVectorMachineOptimizer y KernelEngine: fuente unica en el modulo
# especializado RF_SL_SBRTM_RF_SL1_2/RF_SL_SBRTM_RF_SL1_2_1.py.
#
# Se importan sus clases (SVM dual con SMO-WSS3, RFF/ORF, Nystrom, LS-SVM y
# kernel alignment) junto con sus funciones nuevas, en lugar de duplicar la
# implementacion lineal historica. El resto del archivo (SMOTrainer,
# SVMClassifier, fabricas) sigue usando KernelEngine con la misma API.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_2.RF_SL_SBRTM_RF_SL1_2_1 import (
        KernelEngine,
        NeuronaSVMHazAleatorio,
        NeuronaSVMNucleo,
        NeuronaSVMNystrom,
        SupportVectorMachineOptimizer,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        entrenar_y_evaluar,
        guardar_modelo,
    )
except (ImportError, ValueError):
    # Fallback por ruta para cargas por fichero o sin paquete padre.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_MODULO = "_rf_sl1_2_svm_import"
    _modulo_svm = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_svm is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_2",
            "RF_SL_SBRTM_RF_SL1_2_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_svm = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_svm
        _especificacion.loader.exec_module(_modulo_svm)
    KernelEngine = _modulo_svm.KernelEngine
    NeuronaSVMHazAleatorio = _modulo_svm.NeuronaSVMHazAleatorio
    NeuronaSVMNucleo = _modulo_svm.NeuronaSVMNucleo
    NeuronaSVMNystrom = _modulo_svm.NeuronaSVMNystrom
    SupportVectorMachineOptimizer = _modulo_svm.SupportVectorMachineOptimizer
    benchmark_modelo = _modulo_svm.benchmark_modelo
    cargar_modelo = _modulo_svm.cargar_modelo
    crear_neurona = _modulo_svm.crear_neurona
    entrenar_y_evaluar = _modulo_svm.entrenar_y_evaluar
    guardar_modelo = _modulo_svm.guardar_modelo


class SMOTrainer:
    def __init__(self, C: float = 1.0, tol: float = 1e-3, max_iter: int = 1000):
        self.C = C
        self.tol = tol
        self.max_iter = max_iter
        self._objective_history: List[float] = []

    def optimize(self, K: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float]:
        n = len(y)
        alphas = np.zeros(n)
        bias = 0.0
        for _ in range(self.max_iter):
            alpha_prev = alphas.copy()
            for i in range(n):
                Ei = np.sum(alphas * y * K[:, i]) + bias - y[i]
                if (y[i] * Ei < -self.tol and alphas[i] < self.C) or (y[i] * Ei > self.tol and alphas[i] > 0):
                    j = np.random.randint(0, n)
                    Ej = np.sum(alphas * y * K[:, j]) + bias - y[j]
                    alpha_i_old, alpha_j_old = alphas[i], alphas[j]
                    if y[i] != y[j]:
                        L = max(0, alphas[j] - alphas[i])
                        H = min(self.C, self.C + alphas[j] - alphas[i])
                    else:
                        L = max(0, alphas[i] + alphas[j] - self.C)
                        H = min(self.C, alphas[i] + alphas[j])
                    if L == H: continue
                    eta = 2 * K[i, j] - K[i, i] - K[j, j]
                    if eta >= 0: continue
                    alphas[j] -= y[j] * (Ei - Ej) / eta
                    alphas[j] = np.clip(alphas[j], L, H)
                    if abs(alphas[j] - alpha_j_old) < 1e-5: continue
                    alphas[i] += y[i] * y[j] * (alpha_j_old - alphas[j])
            if np.max(np.abs(alphas - alpha_prev)) < self.tol: break
        sv = alphas > 1e-5
        self._objective_history.append(float(np.sum(alphas[sv])))
        return alphas, bias

    def get_objective_history(self) -> List[float]: return self._objective_history.copy()

    def is_converged(self, tol: float = 1e-4) -> bool:
        if len(self._objective_history) < 2: return False
        return abs(self._objective_history[-1] - self._objective_history[-2]) < tol

    def reset(self) -> None: self._objective_history.clear()


class SupportVectorIdentifier:
    def __init__(self, threshold: float = 1e-5):
        self.threshold = threshold
        self._sv_indices: Optional[np.ndarray] = None

    def identify(self, alphas: np.ndarray) -> np.ndarray:
        self._sv_indices = np.where(alphas > self.threshold)[0]
        return self._sv_indices

    def count(self) -> int: return len(self._sv_indices) if self._sv_indices is not None else 0

    def get_mask(self, n_samples: int) -> np.ndarray:
        mask = np.zeros(n_samples, dtype=bool)
        if self._sv_indices is not None:
            mask[self._sv_indices] = True
        return mask

    @property
    def indices(self) -> Optional[np.ndarray]: return self._sv_indices


class MarginOptimizer:
    def __init__(self):
        self._best_margin: float = 0.0
        self._margin_history: List[float] = []

    def compute(self, weights: np.ndarray) -> float:
        margin = float(1.0 / (np.linalg.norm(weights) + 1e-8))
        self._margin_history.append(margin)
        self._best_margin = max(self._best_margin, margin)
        return margin

    def get_best_margin(self) -> float: return self._best_margin

    def get_avg_margin(self) -> float:
        if not self._margin_history: return 0.0
        return float(np.mean(self._margin_history))

    def get_margin_variance(self) -> float:
        if len(self._margin_history) < 2: return 0.0
        return float(np.var(self._margin_history))

    def is_stable(self, threshold: float = 0.1) -> bool:
        return self.get_margin_variance() < threshold

    def reset(self) -> None:
        self._best_margin = 0.0
        self._margin_history.clear()


class SVMClassifier:
    def __init__(self, kernel: str = "rbf", C: float = 1.0, gamma: float = 0.1):
        self.kernel_type = kernel
        self.C = C
        self.gamma = gamma
        self.kernel_engine = KernelEngine(kernel, gamma)
        self.trainer = SMOTrainer(C)
        self.identifier = SupportVectorIdentifier()
        self.margin_opt = MarginOptimizer()
        self._is_trained: bool = False
        self._training_time: float = 0.0

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        t0 = time.perf_counter()
        K = self.kernel_engine.gram_matrix(X)
        alphas, bias = self.trainer.optimize(K, y)
        sv_mask = alphas > self.identifier.threshold
        self._support_vectors = X[sv_mask]
        self._support_labels = y[sv_mask]
        self._alphas = alphas[sv_mask]
        self._bias = bias
        self._is_trained = True
        self._training_time = time.perf_counter() - t0
        self.identifier.identify(alphas)
        margin = self.margin_opt.compute(self.pesos_svm) if hasattr(self, 'pesos_svm') else 0.0
        return {
            'n_support_vectors': self.identifier.count(),
            'margin': margin, 'training_time': self._training_time,
            'kernel': self.kernel_type, 'C': self.C, 'converged': True,
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_trained: raise RuntimeError("SVM no entrenado")
        K = self.kernel_engine.compute(self._support_vectors, X)
        decision = (self._alphas * self._support_labels) @ K + self._bias
        return np.sign(decision)

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if not self._is_trained: raise RuntimeError("SVM no entrenado")
        K = self.kernel_engine.compute(self._support_vectors, X)
        return (self._alphas * self._support_labels) @ K + self._bias

    @property
    def is_trained(self) -> bool: return self._is_trained

    @property
    def n_support_vectors(self) -> int: return self.identifier.count()

    @property
    def training_time(self) -> float: return self._training_time


def create_support_vector_machine_optimizer(input_size: int = 4, output_size: int = 8) -> SupportVectorMachineOptimizer:
    return SupportVectorMachineOptimizer(input_size=input_size, output_size=output_size)


def train_svm(X: np.ndarray, y: np.ndarray, kernel: str = "rbf", C: float = 1.0, gamma: float = 0.1) -> SVMClassifier:
    clf = SVMClassifier(kernel=kernel, C=C, gamma=gamma)
    clf.train(X, y)
    return clf


def evaluate_svm(clf: SVMClassifier, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    pred = clf.predict(X)
    accuracy = float(np.mean(np.sign(pred) == np.sign(y)))
    return {'accuracy': accuracy, 'n_support_vectors': clf.n_support_vectors, 'n_samples': len(X)}


if __name__ == "__main__":
    logger.info("RF_SL1_2.py cargado exitosamente")
