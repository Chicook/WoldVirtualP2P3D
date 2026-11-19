"""RF_SL_SBRTM__init__1.py
Neuronas especializadas en importaciones para RF_SL (SBRTM · 2026).
=============================================================================

Modulo autocontenido y preparado para importar. Completa y amplia el antiguo
``RF_SL_SBRTM__init__1.py`` (que solo contenia el esqueleto de utilidades RF_SL)
con una familia de neuronas que **optimizan las importaciones mediante calculo
neuronal**:

  * Perfilado estatico del grafo de imports (AST puro, sin ejecutar el codigo).
  * Codificacion hiperdimensional (HDC / Vector Symbolic Architecture) de
    modulos y caracteristicas: binding por convolucion circular + bundling.
  * Atencion sobre grafo de dependencias (Graph Attention, GATv2-style con
    multi-cabeza, LeakyReLU y softmax enmascarado).
  * Mezcla de expertos (Mixture-of-Experts top-k estilo Switch/Transformer) para
    enrutar cada modulo a una estrategia de importacion: lazy / eager / cache /
    paralelo.
  * Modelo de estado selectivo (Selective State Space, Mamba/S6-style) para
    predecir el coste acumulado de una secuencia de importaciones.
  * Codificacion predictiva con incertidumbre (predictive coding / inferencia
    activa) para estimar latencia y su intervalo de confianza.
  * Deteccion de ciclos por SCC de Tarjan + radio espectral + PageRank.
  * Planificacion por busqueda en haz (beam search) consciente del camino
    critico y del riesgo de ciclos.
  * Cache neuronal con admision aprendida (learning-augmented caching).

Estructura principal
--------------------
``NeuronaImportacionSBRTM`` hereda de ``NeuronaMemoriaBase`` y compone, como
clases anidadas, todos los motores anteriores:

    NeuronaImportacionSBRTM
        .PerfiladorEstatico          -> AST, grafo, features
        .CodificadorHiperdimensional -> HDC/VSA
        .AtencionGrafoImportacion    -> GAT multi-cabeza
        .EnrutadorMezclaExpertos     -> MoE top-k + balance de carga
        .NeuronaEstadoSelectivo      -> SSM selectivo
        .EstimadorPredictivoCoste    -> predictive coding
        .DetectorCiclosEspectral     -> Tarjan + PageRank + radio espectral
        .PlanificadorBeamImportaciones
        .CacheNeuronalImportaciones

API publica de alto nivel:
    crear_neurona_importacion(), analizar_importaciones(), plan_de_importacion(),
    benchmark_neurona_importacion(), demo().

Las utilidades heredadas de RF_SL (``ModelRegistry``, ``TrainingConfig``,
``MetricsCollector``, ``DataPipeline``, ``build_model``...) se conservan con la
misma API y se completan (imports, ``validate_model``, serializacion,
benchmarking, busqueda de hiperparametros...).

Nota de diseno: el modulo no ejecuta ni importa el codigo analizado; solo lee
sus fuentes con ``ast``. Es seguro analizar paquetes de terceros.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import logging
import math
import os
import pickle
import sys
import time
import types
from collections import OrderedDict, deque
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

__version__ = "2026.1.0"

# ---------------------------------------------------------------------------
# Base compartida (_rfsl_base). Import relativo, carga por ruta y fallback.
# ---------------------------------------------------------------------------
try:  # paquete normal: LC_STM.RedNeuronal.RF_SL.RFSL1
    from ..RFSL1._rfsl_base import NeuronaMemoriaBase  # type: ignore[no-redef]

    _BASE_RFSL1 = True
except Exception:  # pragma: no cover - depende del contexto de importacion
    _BASE_RFSL1 = False
    _RUTA_BASE_RFSL1 = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "RFSL1",
        "_rfsl_base.py",
    )
    try:
        if not os.path.exists(_RUTA_BASE_RFSL1):
            raise FileNotFoundError(_RUTA_BASE_RFSL1)
        _spec_base = importlib.util.spec_from_file_location(
            "RF_SL_rfsl_base_import", _RUTA_BASE_RFSL1
        )
        if _spec_base is None or _spec_base.loader is None:
            raise ImportError(f"spec nulo para {_RUTA_BASE_RFSL1}")
        _mod_base = importlib.util.module_from_spec(_spec_base)
        _spec_base.loader.exec_module(_mod_base)
        NeuronaMemoriaBase = _mod_base.NeuronaMemoriaBase  # type: ignore[no-redef]
        _BASE_RFSL1 = True
    except Exception:  # fallback minimo equivalente

        class NeuronaMemoriaBase:  # type: ignore[no-redef]
            """Base de neurona con memoria acotada (fallback autocontenido)."""

            def __init__(self, input_size: int, output_size: int, nombre: str = "Neurona"):
                self.input_size = int(input_size)
                self.output_size = int(output_size)
                self.nombre = str(nombre)
                self.pesos: Optional[np.ndarray] = None
                self.sesgo: Optional[np.ndarray] = None
                self.historial_activaciones: Deque[np.ndarray] = deque(maxlen=100)
                self.historial_gradientes: Deque[Dict[str, np.ndarray]] = deque(maxlen=100)
                self.pasos = 0

            def inicializar_pesos(self) -> None:
                raise NotImplementedError

            def forward(self, e: np.ndarray) -> np.ndarray:
                raise NotImplementedError

            def obtener_estadisticas(self) -> Dict[str, Any]:
                stats: Dict[str, Any] = {
                    'nombre': self.nombre,
                    'input_size': self.input_size,
                    'output_size': self.output_size,
                    'pasos': self.pasos,
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
                if self.pesos is not None:
                    total += int(self.pesos.size)
                if self.sesgo is not None:
                    total += int(self.sesgo.size)
                return total


# ---------------------------------------------------------------------------
# Configuracion global del subsistema de importaciones
# ---------------------------------------------------------------------------
LUCIA_IMPORT_CONFIG: Dict[str, Any] = {
    'precision': 'float64',
    'random_seed': 2026,
    'dim_embedding': 64,
    'dim_estado': 16,
    'cabezas_atencion': 4,
    'top_k_expertos': 2,
    'capacidad_cache': 256,
    'umbral_admision': 0.15,
    'max_archivos': 4000,
    'max_nodos_plan': 1500,
    'ancho_beam': 4,
    'learning_rate': 0.05,
    'dropout': 0.0,
}


# ---------------------------------------------------------------------------
# Utilidades numericas compartidas
# ---------------------------------------------------------------------------
def _rng(seed: Optional[int] = None) -> np.random.Generator:
    semilla = LUCIA_IMPORT_CONFIG['random_seed'] if seed is None else int(seed)
    return np.random.default_rng(semilla)


def _softmax(x: np.ndarray, eje: int = -1) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    maximo = np.max(x, axis=eje, keepdims=True)
    exp = np.exp(x - maximo)
    suma = np.sum(exp, axis=eje, keepdims=True)
    return exp / np.maximum(suma, 1e-12)


def _leaky_relu(x: np.ndarray, alfa: float = 0.2) -> np.ndarray:
    return np.where(x >= 0.0, x, alfa * x)


def _layer_norm(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    media = np.mean(x, axis=-1, keepdims=True)
    desviacion = np.std(x, axis=-1, keepdims=True)
    return (x - media) / np.maximum(desviacion, eps)


def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


def _softplus(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0.0)


def _radio_espectral(matriz: np.ndarray, iteraciones: int = 40) -> float:
    """Radio espectral aproximado por iteracion de potencia (matriz no negativa)."""
    a = np.asarray(matriz, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] == 0 or a.shape[0] != a.shape[1]:
        return 0.0
    n = a.shape[0]
    vector = np.ones(n, dtype=np.float64) / math.sqrt(n)
    lam = 0.0
    for _ in range(max(1, iteraciones)):
        producto = a @ vector
        norma = float(np.linalg.norm(producto))
        if norma < 1e-12:
            return 0.0
        vector = producto / norma
        lam = norma
    return float(lam)


def _norma_global(arrays: Sequence[Optional[np.ndarray]]) -> float:
    total = 0.0
    for arr in arrays:
        if arr is None:
            continue
        total += float(np.sum(np.square(np.asarray(arr, dtype=np.float64))))
    return float(math.sqrt(total))


# ---------------------------------------------------------------------------
# Utilidades RF_SL heredadas (completadas)
# ---------------------------------------------------------------------------
class ModelRegistry:
    """Registro de modelos con metadatos asociados."""

    def __init__(self) -> None:
        self._models: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, model: Any, info: Optional[Dict[str, Any]] = None) -> None:
        self._models[name] = model
        self._metadata[name] = dict(info or {})

    def get(self, name: str) -> Any:
        if name not in self._models:
            raise KeyError(f"Modelo '{name}' no registrado")
        return self._models[name]

    def has(self, name: str) -> bool:
        return name in self._models

    def list_models(self) -> List[str]:
        return list(self._models.keys())

    def get_metadata(self, name: str) -> Dict[str, Any]:
        return dict(self._metadata.get(name, {}))

    def count(self) -> int:
        return len(self._models)

    def clear(self) -> None:
        self._models.clear()
        self._metadata.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._models

    def __len__(self) -> int:
        return len(self._models)


class TrainingConfig:
    """Configuracion de entrenamiento con validacion de rangos."""

    _CAMPOS = (
        'epochs', 'learning_rate', 'batch_size', 'validation_split',
        'regularization', 'reg_lambda', 'early_stopping', 'patience',
        'shuffle', 'verbose',
    )

    def __init__(self, epochs: int = 100, learning_rate: float = 0.01,
                 batch_size: int = 32, validation_split: float = 0.2,
                 regularization: str = "l2", reg_lambda: float = 0.01,
                 early_stopping: bool = False, patience: int = 20,
                 shuffle: bool = True, verbose: bool = False):
        self.epochs = max(1, int(epochs))
        self.learning_rate = max(1e-6, float(learning_rate))
        self.batch_size = max(1, int(batch_size))
        self.validation_split = max(0.0, min(0.99, float(validation_split)))
        self.regularization = regularization if regularization in ("l1", "l2") else "l2"
        self.reg_lambda = max(0.0, float(reg_lambda))
        self.early_stopping = bool(early_stopping)
        self.patience = max(1, int(patience))
        self.shuffle = bool(shuffle)
        self.verbose = bool(verbose)

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self._CAMPOS}

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "TrainingConfig":
        limpio = {k: v for k, v in dict(config).items() if k in cls._CAMPOS}
        return cls(**limpio)


class MetricsCollector:
    """Colector de metricas acotado en memoria."""

    def __init__(self, max_por_metrica: int = 10000) -> None:
        self._metrics: Dict[str, List[float]] = {}
        self._timestamps: Deque[float] = deque(maxlen=max_por_metrica)
        self.max_por_metrica = max(1, int(max_por_metrica))

    def record(self, name: str, value: float) -> None:
        serie = self._metrics.setdefault(name, [])
        serie.append(float(value))
        if len(serie) > self.max_por_metrica:
            del serie[:len(serie) - self.max_por_metrica]
        self._timestamps.append(time.time())

    def get_metric(self, name: str) -> Optional[List[float]]:
        serie = self._metrics.get(name)
        return list(serie) if serie is not None else None

    def get_average(self, name: str) -> Optional[float]:
        vals = self._metrics.get(name)
        return float(np.mean(vals)) if vals else None

    def get_all_averages(self) -> Dict[str, float]:
        resultado: Dict[str, float] = {}
        for k, vals in self._metrics.items():
            if vals:
                resultado[k] = float(np.mean(vals))
        return resultado

    def last(self, name: str) -> Optional[float]:
        vals = self._metrics.get(name)
        return float(vals[-1]) if vals else None

    def reset(self) -> None:
        self._metrics.clear()
        self._timestamps.clear()


class DataPipeline:
    """Generacion de lotes y division train/validacion reproducible."""

    def __init__(self, batch_size: int = 32, shuffle: bool = True,
                 random_state: int = 42) -> None:
        self.batch_size = max(1, int(batch_size))
        self.shuffle = bool(shuffle)
        self._rng = np.random.default_rng(int(random_state))

    def generate_batches(self, X: np.ndarray, y: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
        n = len(X)
        if n == 0:
            return []
        indices = np.arange(n)
        if self.shuffle:
            self._rng.shuffle(indices)
        batches: List[Tuple[np.ndarray, np.ndarray]] = []
        for i in range(0, n, self.batch_size):
            batch_idx = indices[i:i + self.batch_size]
            batches.append((X[batch_idx], y[batch_idx]))
        return batches

    def get_n_batches(self, n_samples: int) -> int:
        return max(1, int(math.ceil(max(0, n_samples) / self.batch_size)))

    def dividir(self, X: np.ndarray, y: np.ndarray,
                validation_split: float = 0.2) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        n = len(X)
        corte = int(round(n * max(0.0, min(0.99, float(validation_split)))))
        corte = max(0, min(n, corte))
        idx = np.arange(n)
        if self.shuffle:
            self._rng.shuffle(idx)
        val_idx, train_idx = idx[:corte], idx[corte:]
        return X[train_idx], y[train_idx], X[val_idx], y[val_idx]


# ---------------------------------------------------------------------------
# Carga perezosa de los optimizadores RF_SL (evita import circular al cargar)
# ---------------------------------------------------------------------------
_OPTIMIZADORES_RFSL1: Dict[str, Tuple[str, str]] = {
    'gradient_boosting': ('RF_SL1_1', 'GradientBoostingOptimizer'),
    'svm': ('RF_SL1_2', 'SupportVectorMachineOptimizer'),
    'random_forest': ('RF_SL1_3', 'RandomForestOptimizer'),
    'neural_network': ('RF_SL1_4', 'NeuralNetworkOptimizer'),
    'decision_tree': ('RF_SL1_5', 'DecisionTreeOptimizer'),
    'naive_bayes': ('RF_SL1_6', 'NaiveBayesOptimizer'),
    'knn': ('RF_SL1_7', 'KNearestNeighborsOptimizer'),
    'logistic_regression': ('RF_SL1_8', 'LogisticRegressionOptimizer'),
    'linear_regression': ('RF_SL1_9', 'LinearRegressionOptimizer'),
    'integrated': ('RF_SL1_10', 'IntegratedSupervisedLearningOptimizer'),
}

_MODEL_TYPES: List[str] = list(_OPTIMIZADORES_RFSL1.keys())

_CACHE_OPTIMIZADORES: Optional[Dict[str, type]] = None


def _cargar_optimizadores_embebidos() -> Dict[str, type]:
    """Carga RFSL1 como paquete sintetico cuando el import relativo falla."""
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "RFSL1"
    )
    if not os.path.isdir(ruta):
        raise ImportError(
            "No se encontro el paquete RFSL1 junto a RF_SL_SBRTM_IMPORT: " + ruta
        )
    nombre_paquete = "RF_SL_RFSL1_EMBEBIDO"
    paquete = types.ModuleType(nombre_paquete)
    paquete.__path__ = [ruta]  # type: ignore[attr-defined]
    paquete.__package__ = nombre_paquete
    sys.modules[nombre_paquete] = paquete
    for modulo, _ in _OPTIMIZADORES_RFSL1.values():
        nombre_completo = f"{nombre_paquete}.{modulo}"
        spec = importlib.util.spec_from_file_location(
            nombre_completo, os.path.join(ruta, modulo + ".py")
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"No se pudo cargar {nombre_completo}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[nombre_completo] = mod
        spec.loader.exec_module(mod)
    return {
        tipo: getattr(sys.modules[f"{nombre_paquete}.{modulo}"], clase)
        for tipo, (modulo, clase) in _OPTIMIZADORES_RFSL1.items()
    }


def _cargar_optimizadores() -> Dict[str, type]:
    """Devuelve ``{tipo: clase}`` de los optimizadores RF_SL (cacheado)."""
    global _CACHE_OPTIMIZADORES
    if _CACHE_OPTIMIZADORES is not None:
        return _CACHE_OPTIMIZADORES
    clases: Dict[str, type] = {}
    try:
        for tipo, (modulo, clase) in _OPTIMIZADORES_RFSL1.items():
            mod = importlib.import_module(f"..RFSL1.{modulo}", __package__)
            clases[tipo] = getattr(mod, clase)
    except Exception as error:  # pragma: no cover - segun contexto
        logger.debug("Import relativo de RFSL1 fallido (%s); usando carga embebida", error)
        clases = _cargar_optimizadores_embebidos()
    _CACHE_OPTIMIZADORES = clases
    return clases


def _entrenar_modelo(modelo: Any, X: np.ndarray, y: np.ndarray,
                     epochs: int = 10, learning_rate: float = 0.01,
                     verbose: bool = False) -> Any:
    """Entrena un modelo RF_SL tolerando firmas ``train`` / ``fit`` distintas."""
    if hasattr(modelo, 'train'):
        for kwargs in (
            {'epochs': epochs, 'learning_rate': learning_rate, 'verbose': verbose},
            {'epochs': epochs, 'verbose': verbose},
            {},
        ):
            try:
                return modelo.train(X, y, **kwargs)
            except TypeError:
                continue
    if hasattr(modelo, 'fit'):
        for kwargs in ({'epochs': epochs, 'verbose': verbose}, {}):
            try:
                return modelo.fit(X, y, **kwargs)
            except TypeError:
                continue
    raise RuntimeError(f"{type(modelo).__name__} no soporta entrenamiento")


def build_model(model_type: str, input_size: int, output_size: int) -> Any:
    """Construye un optimizador RF_SL por nombre (carga perezosa)."""
    tipo = (model_type or "").strip().lower()
    clases = _cargar_optimizadores()
    if tipo not in clases:
        raise ValueError(
            f"Tipo desconocido: {model_type}. Disponibles: {sorted(clases)}"
        )
    return clases[tipo](input_size, output_size)


def train_all_models(X: np.ndarray, y: np.ndarray, epochs: int = 100,
                     learning_rate: float = 0.01, **kwargs: Any) -> Dict[str, Any]:
    """Entrena todos los modelos disponibles y devuelve sus resultados."""
    resultados: Dict[str, Any] = {}
    salida = y.shape[1] if getattr(y, "ndim", 1) > 1 else 1
    for tipo in _MODEL_TYPES:
        try:
            modelo = build_model(tipo, X.shape[1], salida)
            resultados[tipo] = _entrenar_modelo(
                modelo, X, y, epochs=epochs,
                learning_rate=learning_rate, verbose=kwargs.get('verbose', False),
            )
        except Exception as error:  # un modelo no debe romper el barrido
            resultados[tipo] = {'error': str(error)}
            logger.warning("Entrenamiento fallido para %s: %s", tipo, error)
    return resultados


def _puntuar_modelo(modelo: Any, X: np.ndarray, y: np.ndarray,
                    metric: str = "r2") -> float:
    if hasattr(modelo, 'evaluate'):
        try:
            metricas = modelo.evaluate(X, y)
            if isinstance(metricas, dict):
                return float(metricas.get(metric, metricas.get('mse', 0.0) or 0.0))
            return float(metricas)
        except Exception:
            pass
    if hasattr(modelo, 'predict'):
        try:
            pred = np.asarray(modelo.predict(X), dtype=np.float64)
            objetivo = np.asarray(y, dtype=np.float64)
            if pred.shape != objetivo.shape and pred.size == objetivo.size:
                pred = pred.reshape(objetivo.shape)
            residuo = float(np.sum((objetivo - pred) ** 2))
            total = float(np.sum((objetivo - np.mean(objetivo)) ** 2))
            if metric == "r2":
                return 1.0 - residuo / max(total, 1e-12)
            return float(np.mean((objetivo - pred) ** 2))
        except Exception:
            pass
    return 0.0


def compare_models(models: Dict[str, Any], X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """Compara modelos por metrica (``r2`` por defecto)."""
    return {nombre: _puntuar_modelo(modelo, X, y) for nombre, modelo in models.items()}


def validate_model(model: Any, X: np.ndarray, y: np.ndarray,
                   metric: str = "r2") -> float:
    """Valida un modelo; si no esta entrenado, lo entrena brevemente."""
    puntuacion = _puntuar_modelo(model, X, y, metric=metric)
    if puntuacion == 0.0 and hasattr(model, 'train'):
        try:
            _entrenar_modelo(model, X, y, epochs=5)
            puntuacion = _puntuar_modelo(model, X, y, metric=metric)
        except Exception:
            pass
    return puntuacion


def serialize_model(model: Any, filepath: str) -> None:
    with open(filepath, 'wb') as f:
        pickle.dump(model, f)


def deserialize_model(filepath: str) -> Any:
    with open(filepath, 'rb') as f:
        return pickle.load(f)


def benchmark_model(model: Any, X: np.ndarray, y: Optional[np.ndarray] = None,
                    n_runs: int = 5) -> Dict[str, float]:
    tiempos: List[float] = []
    for _ in range(max(1, int(n_runs))):
        inicio = time.perf_counter()
        if hasattr(model, 'predict'):
            model.predict(X)
        elif hasattr(model, 'forward'):
            model.forward(X)
        tiempos.append(time.perf_counter() - inicio)
    return {
        'avg_time': float(np.mean(tiempos)),
        'min_time': float(np.min(tiempos)),
        'max_time': float(np.max(tiempos)),
        'std_time': float(np.std(tiempos)),
        'n_runs': len(tiempos),
    }


def summary(model: Any) -> Dict[str, Any]:
    info = model.info() if hasattr(model, 'info') else str(model)
    params = model.params_count() if hasattr(model, 'params_count') else 0
    stats = model.obtener_estadisticas() if hasattr(model, 'obtener_estadisticas') else {}
    estabilidad = model.verificar_estabilidad() if hasattr(model, 'verificar_estabilidad') else {}
    return {'info': info, 'params': params, 'stats': stats, 'stability': estabilidad}


def get_available_models() -> List[str]:
    return list(_MODEL_TYPES)


class HyperparameterSearch:
    """Busqueda exhaustiva de hiperparametros sobre los modelos RF_SL."""

    def __init__(self, param_grid: Dict[str, List[Any]]) -> None:
        self.param_grid = {k: list(v) for k, v in dict(param_grid).items()}
        self._results: List[Dict[str, Any]] = []

    def enumerate_combinations(self) -> List[Dict[str, Any]]:
        claves = list(self.param_grid.keys())
        if not claves:
            return [{}]
        combinaciones: List[Dict[str, Any]] = [{}]
        for clave in claves:
            combinaciones = [dict(actual, **{clave: valor})
                             for actual in combinaciones
                             for valor in self.param_grid[clave]]
        return combinaciones

    def search(self, X: np.ndarray, y: np.ndarray, model_type: str,
               metric: str = "r2", epochs: int = 5) -> Dict[str, Any]:
        mejor_puntuacion = float('-inf')
        mejores: Dict[str, Any] = {}
        self._results = []
        salida = y.shape[1] if getattr(y, "ndim", 1) > 1 else 1
        for params in self.enumerate_combinations():
            modelo = build_model(model_type, X.shape[1], salida)
            try:
                _entrenar_modelo(modelo, X, y, epochs=epochs)
            except Exception as error:
                logger.debug("Combinacion descartada %s: %s", params, error)
                continue
            puntuacion = _puntuar_modelo(modelo, X, y, metric=metric)
            self._results.append({'params': dict(params), 'score': puntuacion})
            if puntuacion > mejor_puntuacion:
                mejor_puntuacion = puntuacion
                mejores = dict(params)
        return {'best_score': mejor_puntuacion, 'best_params': mejores,
                'results': list(self._results)}


class PerformanceMonitor:
    """Cronometro con checkpoints con nombre."""

    def __init__(self) -> None:
        self._start_time: Optional[float] = None
        self._checkpoints: Dict[str, float] = {}

    def start(self) -> None:
        self._start_time = time.perf_counter()

    def checkpoint(self, name: str) -> None:
        self._checkpoints[name] = time.perf_counter()

    def elapsed(self) -> Optional[float]:
        if self._start_time is None:
            return None
        return time.perf_counter() - self._start_time

    def checkpoint_duration(self, name: str) -> Optional[float]:
        if name not in self._checkpoints or self._start_time is None:
            return None
        return self._checkpoints[name] - self._start_time

    def get_all_durations(self) -> Dict[str, float]:
        return {k: v for k, v in ((k, self.checkpoint_duration(k)) for k in self._checkpoints)
                if v is not None}


class FeatureSelector:
    """Selector de atributos por varianza o correlacion absoluta."""

    def __init__(self, n_features: int = 10, method: str = "variance") -> None:
        self.n_features = max(1, int(n_features))
        self.method = method if method in ("variance", "correlation") else "variance"
        self._selected_indices: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> None:
        X = np.asarray(X, dtype=np.float64)
        if X.ndim != 2 or X.shape[0] == 0:
            raise ValueError("X debe ser una matriz 2D no vacia")
        if self.method == "correlation" and y is not None:
            objetivo = np.asarray(y, dtype=np.float64).reshape(-1)
            if objetivo.shape[0] != X.shape[0]:
                raise ValueError("y y X deben tener el mismo numero de filas")
            objetivo = objetivo - objetivo.mean()
            desviacion = X.std(axis=0) * (objetivo.std() + 1e-12)
            puntuacion = np.abs((X - X.mean(axis=0)).T @ objetivo / max(1, len(X) - 1) / np.maximum(desviacion, 1e-12))
        else:
            puntuacion = np.var(X, axis=0)
        k = min(self.n_features, X.shape[1])
        self._selected_indices = np.argsort(puntuacion)[-k:]

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self._selected_indices is None:
            raise RuntimeError("FeatureSelector no ajustado")
        return np.asarray(X, dtype=np.float64)[:, self._selected_indices]

    def fit_transform(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> np.ndarray:
        self.fit(X, y)
        return self.transform(X)

    def get_selected(self) -> Optional[np.ndarray]:
        return self._selected_indices.copy() if self._selected_indices is not None else None


def create_default_pipeline(input_size: int = 8, output_size: int = 4) -> Dict[str, Any]:
    return {
        'data_pipeline': DataPipeline(batch_size=32, shuffle=True),
        'training_config': TrainingConfig(epochs=100, learning_rate=0.01),
        'metrics_collector': MetricsCollector(),
        'model_registry': ModelRegistry(),
        'input_size': int(input_size),
        'output_size': int(output_size),
    }


def create_ensemble_predictions(models: Sequence[Any], X: np.ndarray) -> np.ndarray:
    predicciones: List[np.ndarray] = []
    for modelo in models:
        if not hasattr(modelo, 'predict'):
            continue
        try:
            predicciones.append(np.asarray(modelo.predict(X), dtype=np.float64))
        except Exception:
            if hasattr(modelo, 'train'):
                try:
                    _entrenar_modelo(modelo, X, np.zeros((len(X), 1)), epochs=3)
                    predicciones.append(np.asarray(modelo.predict(X), dtype=np.float64))
                except Exception:
                    continue
    if not predicciones:
        raise ValueError("Sin predicciones disponibles")
    return np.mean(np.stack(predicciones, axis=0), axis=0)


def quick_train(model: Any, X: np.ndarray, y: np.ndarray,
                epochs: int = 10, **kwargs: Any) -> Any:
    return _entrenar_modelo(model, X, y, epochs=epochs,
                            learning_rate=kwargs.get('learning_rate', 0.01),
                            verbose=kwargs.get('verbose', False))


def quick_predict(model: Any, X: np.ndarray) -> np.ndarray:
    if hasattr(model, 'predict'):
        try:
            return np.asarray(model.predict(X), dtype=np.float64)
        except Exception:
            pass
    if hasattr(model, 'forward'):
        return np.asarray(model.forward(X), dtype=np.float64)
    if hasattr(model, 'train'):
        _entrenar_modelo(model, X, np.zeros((len(X), 1)), epochs=3)
        if hasattr(model, 'predict'):
            return np.asarray(model.predict(X), dtype=np.float64)
    raise RuntimeError("El modelo no soporta predict/forward")


def quick_evaluate(model: Any, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    if hasattr(model, 'evaluate'):
        try:
            return dict(model.evaluate(X, y))
        except Exception:
            pass
    return {'predictions': quick_predict(model, X)}


def info_paquete() -> Dict[str, Any]:
    """Metadatos del subsistema de importaciones."""
    return {
        'nombre': 'RF_SL_SBRTM_IMPORT',
        'version': __version__,
        'base_rfsl1_disponible': _BASE_RFSL1,
        'config': dict(LUCIA_IMPORT_CONFIG),
        'estrategias': list(NeuronaImportacionSBRTM.NOMBRES_ESTRATEGIA),
        'clases': [
            'NeuronaImportacionSBRTM',
            'PerfiladorEstatico',
            'CodificadorHiperdimensional',
            'AtencionGrafoImportacion',
            'EnrutadorMezclaExpertos',
            'NeuronaEstadoSelectivo',
            'EstimadorPredictivoCoste',
            'DetectorCiclosEspectral',
            'PlanificadorBeamImportaciones',
            'CacheNeuronalImportaciones',
        ],
    }


# ===========================================================================
# NEURONAS DE IMPORTACION (SBRTM · 2026)
# ===========================================================================
class NeuronaImportacionSBRTM(NeuronaMemoriaBase):
    """Neurona que aprende a ordenar, enrutar y cachear importaciones.

    Entrada (``input_size``, por defecto 8): caracteristicas estaticas de un
    modulo segun ``PerfiladorEstatico.EJES``:
        fan_in, fan_out, profundidad, es_stdlib, es_local, tamano_log,
        tiene_ciclo, coste_log.

    Salida (``output_size``, por defecto 4): probabilidades de estrategia
    ``lazy``, ``eager``, ``cache`` y ``paralelo``.
    """

    NOMBRES_ESTRATEGIA: Tuple[str, ...] = ('lazy', 'eager', 'cache', 'paralelo')

    # ------------------------------------------------------------------
    # 1) Perfilado estatico del grafo de imports (AST)
    # ------------------------------------------------------------------
    class PerfiladorEstatico:
        """Analiza fuentes con ``ast`` y construye el grafo de dependencias."""

        EJES: Tuple[str, ...] = (
            'fan_in', 'fan_out', 'profundidad', 'es_stdlib',
            'es_local', 'tamano_log', 'tiene_ciclo', 'coste_log',
        )

        DIRECTORIOS_IGNORADOS = {
            '__pycache__', '.git', '.hg', '.svn', '.idea', '.vscode',
            'node_modules', 'venv', 'env', '.venv', '.env', 'build',
            'dist', 'site-packages', '.mypy_cache', '.pytest_cache',
            'target', 'bin', 'obj',
        }

        def __init__(self, raiz: Optional[str] = None, max_archivos: int = 4000) -> None:
            self.raiz = os.path.abspath(raiz) if raiz else os.getcwd()
            self.max_archivos = max(1, int(max_archivos))
            self._cache_analisis: Dict[str, Dict[str, Any]] = {}
            self._firmas: Dict[str, Tuple[float, int]] = {}
            self._raices_locales: set = set()
            self._texto_cache: Dict[str, str] = {}
            self._inicializar_raices()

        # -- utilidades internas ---------------------------------------
        def _inicializar_raices(self) -> None:
            if os.path.isfile(self.raiz):
                self._raices_locales.add(
                    os.path.splitext(os.path.basename(self.raiz))[0]
                )
                return
            try:
                for entrada in os.listdir(self.raiz):
                    ruta = os.path.join(self.raiz, entrada)
                    if os.path.isdir(ruta):
                        if os.path.exists(os.path.join(ruta, "__init__.py")):
                            self._raices_locales.add(entrada)
                    elif entrada.endswith('.py'):
                        self._raices_locales.add(os.path.splitext(entrada)[0])
            except OSError:
                pass

        @staticmethod
        def _modulo_id(ruta: str, raiz: str) -> str:
            relativa = os.path.relpath(ruta, raiz)
            relativa = relativa.replace(os.sep, '/')
            if relativa.endswith('.py'):
                relativa = relativa[:-3]
            if relativa.endswith('/__init__'):
                relativa = relativa[:-len('/__init__')]
            if relativa in ('__init__', ''):
                relativa = os.path.basename(os.path.normpath(raiz)) or 'raiz'
            return relativa.replace('/', '.')

        @staticmethod
        def _paquete_de(modulo_id: str) -> str:
            return modulo_id.rsplit('.', 1)[0] if '.' in modulo_id else ''

        @staticmethod
        def _resolver(modulo: str, nivel: int, paquete: str) -> str:
            if not nivel:
                return modulo or ''
            partes = [p for p in (paquete or '').split('.') if p]
            if nivel > 1:
                partes = partes[:max(0, len(partes) - (nivel - 1))]
            base = '.'.join(partes)
            if modulo:
                return f"{base}.{modulo}" if base else modulo
            return base

        def clasificar(self, modulo: str, nivel: int = 0) -> str:
            if nivel and nivel > 0:
                return 'relativo'
            raiz = (modulo or '').split('.')[0]
            if not raiz:
                return 'local'
            if raiz in getattr(sys, 'stdlib_module_names', frozenset()):
                return 'stdlib'
            if raiz in getattr(sys, 'builtin_module_names', ()):  # pragma: no cover
                return 'stdlib'
            if raiz in self._raices_locales:
                return 'local'
            return 'tercero'

        def _listar_ficheros(self) -> List[str]:
            if os.path.isfile(self.raiz):
                return [self.raiz] if self.raiz.endswith('.py') else []
            ficheros: List[str] = []
            for directorio, subdirs, nombres in os.walk(self.raiz):
                subdirs[:] = sorted(
                    d for d in subdirs if d not in self.DIRECTORIOS_IGNORADOS
                    and not d.startswith('.')
                )
                for nombre in sorted(nombres):
                    if not nombre.endswith('.py'):
                        continue
                    ficheros.append(os.path.join(directorio, nombre))
                    if len(ficheros) >= self.max_archivos:
                        logger.warning(
                            "Perfilador: limite de %d ficheros alcanzado en %s",
                            self.max_archivos, self.raiz,
                        )
                        return ficheros
            return ficheros

        def _leer(self, ruta: str) -> str:
            if ruta in self._texto_cache:
                return self._texto_cache[ruta]
            with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
                texto = f.read()
            self._texto_cache[ruta] = texto
            return texto

        # -- analisis ---------------------------------------------------
        def analizar_fichero(self, ruta: str) -> Dict[str, Any]:
            ruta = os.path.abspath(ruta)
            try:
                estado = os.stat(ruta)
                firma = (float(estado.st_mtime), int(estado.st_size))
            except OSError as error:
                return {'ruta': ruta, 'modulo': '', 'error': str(error),
                        'imports': [], 'n_lineas': 0, 'tamano_bytes': 0}
            modulo_id = self._modulo_id(ruta, self.raiz)
            if self._firmas.get(ruta) == firma and modulo_id in self._cache_analisis:
                return self._cache_analisis[modulo_id]

            datos: Dict[str, Any] = {
                'ruta': ruta,
                'modulo': modulo_id,
                'paquete': self._paquete_de(modulo_id),
                'n_lineas': 0,
                'tamano_bytes': firma[1],
                'imports': [],
                'error': None,
            }
            try:
                fuente = self._leer(ruta)
                datos['n_lineas'] = fuente.count('\n') + 1
                arbol = ast.parse(fuente, filename=ruta)
            except (OSError, SyntaxError, ValueError) as error:
                datos['error'] = f"{type(error).__name__}: {error}"
                logger.debug("No se pudo parsear %s: %s", ruta, error)
                self._cache_analisis[modulo_id] = datos
                self._firmas[ruta] = firma
                return datos

            paquete = datos['paquete']
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    for alias in nodo.names:
                        nombre = alias.name
                        datos['imports'].append({
                            'modulo': nombre,
                            'nombres': [alias.asname or nombre.rsplit('.', 1)[-1]],
                            'nivel': 0,
                            'linea': getattr(nodo, 'lineno', 0),
                            'resuelto': nombre,
                            'resueltos': [nombre],
                            'tipo': self.clasificar(nombre, 0),
                        })
                elif isinstance(nodo, ast.ImportFrom):
                    nivel = int(nodo.level or 0)
                    modulo = nodo.module or ''
                    resuelto = self._resolver(modulo, nivel, paquete)
                    nombres = [a.asname or a.name for a in nodo.names]
                    candidatos = [resuelto] if resuelto else []
                    if resuelto:
                        for alias in nodo.names:
                            if alias.name != '*':
                                candidatos.append(f"{resuelto}.{alias.name}")
                    datos['imports'].append({
                        'modulo': modulo,
                        'nombres': nombres,
                        'nivel': nivel,
                        'linea': getattr(nodo, 'lineno', 0),
                        'resuelto': resuelto,
                        'resueltos': candidatos,
                        'tipo': self.clasificar(modulo, nivel),
                    })

            self._cache_analisis[modulo_id] = datos
            self._firmas[ruta] = firma
            if '.' in modulo_id:
                self._raices_locales.add(modulo_id.split('.')[0])
            return datos

        def construir_grafo(self) -> Dict[str, Dict[str, Any]]:
            """Grafo ``modulo -> {deps, fan_in, fan_out, profundidad, ...}``."""
            analisis = dict(self._cache_analisis)
            nodos = sorted(analisis)
            grafo: Dict[str, Dict[str, Any]] = {}
            for modulo in nodos:
                datos = analisis[modulo]
                deps: List[str] = []
                for registro in datos.get('imports', []):
                    for candidato in registro.get('resueltos', []):
                        if candidato and candidato not in deps:
                            deps.append(candidato)
                grafo[modulo] = {
                    'ruta': datos.get('ruta', ''),
                    'paquete': datos.get('paquete', ''),
                    'n_lineas': int(datos.get('n_lineas', 0)),
                    'tamano_bytes': int(datos.get('tamano_bytes', 0)),
                    'deps': deps,
                    'deps_locales': [d for d in deps if d in analisis],
                    'fan_out': len(deps),
                    'fan_in': 0,
                    'profundidad': 0,
                    'tiene_ciclo': False,
                    'es_local': True,
                    'clasificacion': 'local',
                    'imports': datos.get('imports', []),
                }

            conjunto = set(nodos)
            for modulo in nodos:
                for dep in grafo[modulo]['deps_locales']:
                    grafo[dep]['fan_in'] += 1

            # Profundidad = longitud de la cadena de dependencias locales.
            profundidad = self._profundidades(grafo, conjunto)
            for modulo in nodos:
                deps_locales = grafo[modulo]['deps_locales']
                coste = (
                    1.5e-4 * (grafo[modulo]['tamano_bytes'] / 1024.0)
                    + 1.0e-3 * len(deps_locales)
                    + 6.0e-4 * min(grafo[modulo]['fan_in'], 32)
                    + 5.0e-4
                )
                grafo[modulo]['profundidad'] = int(profundidad.get(modulo, 0))
                grafo[modulo]['coste_estatico'] = float(max(1e-6, coste))
            return grafo

        @staticmethod
        def _profundidades(grafo: Dict[str, Dict[str, Any]],
                           conjunto: set) -> Dict[str, int]:
            pendientes = {m: len(grafo[m]['deps_locales']) for m in grafo}
            dependientes: Dict[str, List[str]] = {m: [] for m in grafo}
            for modulo in grafo:
                for dep in grafo[modulo]['deps_locales']:
                    dependientes[dep].append(modulo)
            cola = deque(m for m, p in pendientes.items() if p == 0)
            orden: List[str] = []
            while cola:
                actual = cola.popleft()
                orden.append(actual)
                for padre in dependientes.get(actual, []):
                    pendientes[padre] -= 1
                    if pendientes[padre] == 0:
                        cola.append(padre)
            resultado: Dict[str, int] = {}
            for modulo in orden:
                deps = [d for d in grafo[modulo]['deps_locales'] if d in resultado]
                resultado[modulo] = 1 + max((resultado[d] for d in deps), default=-1)
            for modulo in grafo:  # nodos en ciclos no visitados
                resultado.setdefault(modulo, 0)
            return resultado

        def perfil_completo(self) -> Dict[str, Any]:
            """Analiza todos los ficheros y devuelve perfil + grafo + resumen."""
            self._cache_analisis.clear()
            self._firmas.clear()
            self._texto_cache.clear()
            self._inicializar_raices()
            ficheros = self._listar_ficheros()
            for ruta in ficheros:
                self.analizar_fichero(ruta)
            grafo = self.construir_grafo()
            por_tipo: Dict[str, int] = {}
            total_deps = 0
            max_fan_in = 0
            for datos in grafo.values():
                total_deps += len(datos['deps'])
                max_fan_in = max(max_fan_in, datos['fan_in'])
                for registro in datos['imports']:
                    tipo = registro.get('tipo', 'desconocido')
                    por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
            resumen = {
                'raiz': self.raiz,
                'n_ficheros': len(ficheros),
                'n_modulos': len(grafo),
                'n_aristas': int(sum(len(d['deps_locales']) for d in grafo.values())),
                'total_imports': total_deps,
                'max_fan_in': int(max_fan_in),
                'por_tipo': dict(sorted(por_tipo.items())),
                'coste_total_estatico': float(sum(
                    d['coste_estatico'] for d in grafo.values()
                )),
            }
            return {
                'raiz': self.raiz,
                'modulos': sorted(grafo.keys()),
                'grafo': grafo,
                'resumen': resumen,
            }

        def caracteristicas_modulo(self, datos: Dict[str, Any]) -> np.ndarray:
            """Vector de caracteristicas en el orden de ``EJES``."""
            coste = float(datos.get('coste_estatico', 0.0))
            clasificacion = str(datos.get('clasificacion', 'local'))
            return np.array([
                math.log1p(max(0, int(datos.get('fan_in', 0)))),
                math.log1p(max(0, int(datos.get('fan_out', 0)))),
                float(datos.get('profundidad', 0)) / 10.0,
                1.0 if clasificacion == 'stdlib' else 0.0,
                1.0 if bool(datos.get('es_local', True)) else 0.0,
                math.log1p(max(0, int(datos.get('tamano_bytes', 0)))) / 12.0,
                1.0 if bool(datos.get('tiene_ciclo', False)) else 0.0,
                math.log1p(max(0.0, coste * 1000.0)),
            ], dtype=np.float64)

        def matriz_caracteristicas(
            self,
            grafo: Dict[str, Dict[str, Any]],
            orden: Optional[Sequence[str]] = None,
        ) -> Tuple[np.ndarray, List[str]]:
            modulos = list(orden) if orden is not None else sorted(grafo)
            if not modulos:
                return np.zeros((0, len(self.EJES)), dtype=np.float64), []
            matriz = np.zeros((len(modulos), len(self.EJES)), dtype=np.float64)
            for i, modulo in enumerate(modulos):
                datos = grafo.get(modulo)
                if datos is None:
                    continue
                matriz[i] = self.caracteristicas_modulo(datos)
            return matriz, modulos

    # ------------------------------------------------------------------
    # 2) Codificador hiperdimensional (HDC / VSA)
    # ------------------------------------------------------------------
    class CodificadorHiperdimensional:
        """Codifica tokens y features como vectores bipolares de alta dimension.

        Operaciones: binding por convolucion circular (FFT) y bundling por
        superposicion con umbralizacion por signo (VSA clasico, 2026-ready).
        """

        def __init__(self, dim: int = 64, seed: int = 2026) -> None:
            self.dim = max(8, int(dim))
            self.seed = int(seed)
            self._cache_vectores: Dict[str, np.ndarray] = {}
            self._proyecciones: Dict[int, np.ndarray] = {}

        def vector_token(self, token: str) -> np.ndarray:
            clave = str(token)
            cache = self._cache_vectores.get(clave)
            if cache is not None:
                return cache
            resumen = hashlib.blake2b(
                f"{self.seed}|{clave}".encode('utf-8', errors='replace'),
                digest_size=16,
            ).digest()
            generador = np.random.default_rng(int.from_bytes(resumen[:8], 'little'))
            vector = generador.integers(0, 2, size=self.dim).astype(np.float64) * 2.0 - 1.0
            self._cache_vectores[clave] = vector
            return vector

        def codificar_modulo(self, nombre: str) -> np.ndarray:
            partes = [nombre]
            partes.extend(p for p in nombre.replace('__', '.').split('.') if p)
            partes.extend(p for p in nombre.replace('.', '_').split('_') if p)
            return self._bundle([self.vector_token(p) for p in partes])

        def codificar_features(self, features: Dict[str, float]) -> np.ndarray:
            componentes: List[np.ndarray] = []
            for clave, valor in features.items():
                rol = self.vector_token(f"rol:{clave}")
                cuantizado = self.vector_token(f"valor:{clave}:{round(float(valor), 3)}")
                componentes.append(self.enlazar(rol, cuantizado))
            return self._bundle(componentes)

        def enlazar(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
            a = np.asarray(a, dtype=np.float64)
            b = np.asarray(b, dtype=np.float64)
            if a.shape != b.shape:
                b = np.resize(b, a.shape)
            producto = np.fft.rfft(a) * np.fft.rfft(b)
            return np.fft.irfft(producto, n=a.shape[0])

        def _bundle(self, vectores: Sequence[np.ndarray]) -> np.ndarray:
            if not vectores:
                return np.zeros(self.dim, dtype=np.float64)
            suma = np.sum(np.stack([np.asarray(v, dtype=np.float64) for v in vectores]), axis=0)
            return np.where(suma >= 0.0, 1.0, -1.0)

        @staticmethod
        def similitud(a: np.ndarray, b: np.ndarray) -> float:
            a = np.asarray(a, dtype=np.float64).ravel()
            b = np.asarray(b, dtype=np.float64).ravel()
            if a.size == 0 or b.size == 0:
                return 0.0
            if a.shape != b.shape:
                b = np.resize(b, a.shape)
            denominador = float(np.linalg.norm(a) * np.linalg.norm(b))
            if denominador < 1e-12:
                return 0.0
            return float(np.dot(a, b) / denominador)

        def proyectar(self, vector: np.ndarray, salida: int) -> np.ndarray:
            salida = max(1, int(salida))
            vector = np.asarray(vector, dtype=np.float64).ravel()
            if salida == vector.size:
                return vector.copy()
            matriz = self._proyecciones.get(salida)
            if matriz is None:
                generador = np.random.default_rng(self.seed + 7919 * salida)
                escala = 1.0 / math.sqrt(max(1, vector.size))
                matriz = generador.normal(0.0, escala, (vector.size, salida))
                self._proyecciones[salida] = matriz
            return vector @ matriz

        def limpiar_cache(self) -> None:
            self._cache_vectores.clear()
            self._proyecciones.clear()

    # ------------------------------------------------------------------
    # 3) Atencion sobre grafo de dependencias (GAT multi-cabeza)
    # ------------------------------------------------------------------
    class AtencionGrafoImportacion:
        """Capa de Graph Attention que propaga informacion entre dependencias."""

        def __init__(self, dim: int = 64, cabezas: int = 4,
                     dropout: float = 0.0, seed: int = 2026) -> None:
            self.dim = max(2, int(dim))
            self.cabezas = max(1, int(cabezas))
            self.dropout = max(0.0, min(0.9, float(dropout)))
            self._rng = _rng(seed)
            escala = 1.0 / math.sqrt(max(1, self.dim))
            self.W = [
                self._rng.normal(0.0, escala, (self.dim, self.dim))
                for _ in range(self.cabezas)
            ]
            self.b = [np.zeros(self.dim) for _ in range(self.cabezas)]
            self.a_origen = [self._rng.normal(0.0, 0.1, self.dim) for _ in range(self.cabezas)]
            self.a_destino = [self._rng.normal(0.0, 0.1, self.dim) for _ in range(self.cabezas)]
            self.ultima_atencion: Optional[np.ndarray] = None

        def forward(self, X: np.ndarray,
                    adyacencia: Optional[np.ndarray] = None,
                    mascara: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
            X = np.asarray(X, dtype=np.float64)
            unico = X.ndim == 1
            if unico:
                X = X[None, :]
            n = int(X.shape[0])
            if n == 0:
                return X.copy(), np.zeros((0, 0), dtype=np.float64)
            if not hasattr(self, '_dim_entrada'):
                self._dim_entrada = int(X.shape[1])
            elif X.shape[1] != self._dim_entrada:
                # Nueva dimensionalidad de entrada: se reajustan solo las W.
                self._dim_entrada = int(X.shape[1])
                escala_entrada = 1.0 / math.sqrt(max(1, self._dim_entrada))
                self.W = [self._rng.normal(0.0, escala_entrada,
                                           (self._dim_entrada, self.dim))
                          for _ in range(self.cabezas)]
            if adyacencia is None:
                adyacencia = np.ones((n, n), dtype=np.float64)
            else:
                adyacencia = np.asarray(adyacencia, dtype=np.float64)
                if adyacencia.shape != (n, n):
                    adyacencia = np.ones((n, n), dtype=np.float64)
            if mascara is not None:
                adyacencia = adyacencia * np.asarray(mascara, dtype=np.float64)

            salidas: List[np.ndarray] = []
            atencion_total = np.zeros((n, n), dtype=np.float64)
            for cabeza in range(self.cabezas):
                H = X @ self.W[cabeza] + self.b[cabeza]
                logits = ((H @ self.a_origen[cabeza])[:, None]
                          + (H @ self.a_destino[cabeza])[None, :])
                logits = _leaky_relu(logits, 0.2)
                logits = np.where(adyacencia > 0.0, logits, -1e9)
                pesos = _softmax(logits, eje=1)
                if self.dropout > 0.0:
                    pesos = pesos * (self._rng.random(pesos.shape) >= self.dropout)
                    pesos = pesos / np.maximum(pesos.sum(axis=1, keepdims=True), 1e-12)
                salidas.append(pesos @ H)
                atencion_total += pesos
            Z = np.mean(np.stack(salidas, axis=0), axis=0) + X
            Z = _layer_norm(Z)
            self.ultima_atencion = atencion_total / float(self.cabezas)
            if unico:
                return Z[0], self.ultima_atencion
            return Z, self.ultima_atencion

        def entropia_atencion(self) -> float:
            """Entropia media de la ultima matriz de atencion (0 = colapso)."""
            if self.ultima_atencion is None or self.ultima_atencion.size == 0:
                return 0.0
            p = np.clip(self.ultima_atencion, 1e-12, 1.0)
            return float(-np.mean(np.sum(p * np.log(p), axis=1)))

    # ------------------------------------------------------------------
    # 4) Mezcla de expertos (MoE top-k, Switch-style)
    # ------------------------------------------------------------------
    class EnrutadorMezclaExpertos:
        """Enruta cada modulo a los mejores expertos de estrategia de import."""

        NOMBRES_EXPERTOS: Tuple[str, ...] = ('lazy', 'eager', 'cache', 'paralelo')

        def __init__(self, dim: int = 64, n_expertos: int = 4,
                     top_k: int = 2, seed: int = 2026) -> None:
            self.dim = max(2, int(dim))
            self.n_expertos = max(2, int(n_expertos))
            self.top_k = max(1, min(int(top_k), self.n_expertos))
            self._rng = _rng(seed)
            escala = 1.0 / math.sqrt(max(1, self.dim))
            self.W_expertos = [
                self._rng.normal(0.0, escala, (self.dim, self.dim))
                for _ in range(self.n_expertos)
            ]
            self.b_expertos = [np.zeros(self.dim) for _ in range(self.n_expertos)]
            self.W_gate = self._rng.normal(0.0, escala, (self.dim, self.n_expertos))
            self.b_gate = np.zeros(self.n_expertos)
            self.ultima_carga: Optional[np.ndarray] = None
            self.historial_carga: Deque[np.ndarray] = deque(maxlen=100)

        def forward(self, x: np.ndarray) -> Dict[str, Any]:
            X = np.asarray(x, dtype=np.float64)
            unico = X.ndim == 1
            if unico:
                X = X[None, :]
            if not hasattr(self, '_dim_entrada'):
                self._dim_entrada = int(X.shape[1])
            elif X.shape[1] != self._dim_entrada:
                # Nueva dimensionalidad de entrada: se reajustan gate y expertos.
                self._dim_entrada = int(X.shape[1])
                escala_entrada = 1.0 / math.sqrt(max(1, self._dim_entrada))
                self.W_gate = self._rng.normal(
                    0.0, escala_entrada, (self._dim_entrada, self.n_expertos)
                )
                self.W_expertos = [
                    self._rng.normal(0.0, escala_entrada,
                                     (self._dim_entrada, self.dim))
                    for _ in range(self.n_expertos)
                ]

            logits = X @ self.W_gate + self.b_gate
            pesos = _softmax(logits, eje=1)
            indices = np.argsort(-pesos, axis=1)[:, :self.top_k]
            mascara = np.zeros_like(pesos)
            np.put_along_axis(mascara, indices, 1.0, axis=1)
            pesos_top = pesos * mascara
            pesos_top = pesos_top / np.maximum(pesos_top.sum(axis=1, keepdims=True), 1e-12)

            salida = np.zeros((X.shape[0], self.dim), dtype=np.float64)
            for experto in range(self.n_expertos):
                coeficiente = pesos_top[:, experto][:, None]
                if not np.any(coeficiente > 0.0):
                    continue
                salida += coeficiente * np.maximum(
                    X @ self.W_expertos[experto] + self.b_expertos[experto], 0.0
                )

            carga = pesos.mean(axis=0)
            self.ultima_carga = carga
            self.historial_carga.append(carga.copy())
            perdida_balance = float(self.n_expertos * np.sum(np.square(carga)))
            return {
                'salida': salida[0] if unico else salida,
                'pesos': pesos[0] if unico else pesos,
                'indices': indices[0] if unico else indices,
                'carga': carga,
                'perdida_balance': perdida_balance,
            }

        def perdida_balance(self) -> float:
            if self.ultima_carga is None:
                return 0.0
            return float(self.n_expertos * np.sum(np.square(self.ultima_carga)))

        def expertos_por_estrategia(self) -> Dict[str, str]:
            nombres = list(self.NOMBRES_EXPERTOS)
            return {f"experto_{i}": nombres[i % len(nombres)]
                    for i in range(self.n_expertos)}

    # ------------------------------------------------------------------
    # 5) Modelo de estado selectivo (SSM, Mamba/S6-style)
    # ------------------------------------------------------------------
    class NeuronaEstadoSelectivo:
        """Escanea una secuencia de features y acumula estado latente."""

        def __init__(self, dim: int = 8, dim_estado: int = 16, seed: int = 2026) -> None:
            self.dim = max(1, int(dim))
            self.dim_estado = max(2, int(dim_estado))
            generador = _rng(seed)
            self.A_log = np.log(np.arange(1, self.dim_estado + 1, dtype=np.float64))
            self.D = np.ones(self.dim, dtype=np.float64)
            self.W_delta = generador.normal(0.0, 0.1, (self.dim, self.dim))
            self.b_delta = np.zeros(self.dim)
            self.W_B = generador.normal(0.0, 0.2, (self.dim, self.dim_estado))
            self.W_C = generador.normal(0.0, 0.2, (self.dim, self.dim_estado))
            self.ultimo_estado: Optional[np.ndarray] = None

        def forward(self, secuencia: np.ndarray) -> Dict[str, Any]:
            X = np.asarray(secuencia, dtype=np.float64)
            if X.ndim == 1:
                X = X[None, :]
            if X.size == 0:
                return {'salidas': np.zeros((0, self.dim)), 'ultimo_estado': np.zeros(
                    (self.dim, self.dim_estado)), 'pasos': 0}
            if X.shape[1] != self.dim:
                raise ValueError(
                    f"SSM espera dim={self.dim} y recibio {X.shape[1]}"
                )
            h = np.zeros((self.dim, self.dim_estado), dtype=np.float64)
            salidas = np.zeros((X.shape[0], self.dim), dtype=np.float64)
            A = -np.exp(self.A_log)
            for t in range(X.shape[0]):
                x = X[t]
                dt = _softplus(x @ self.W_delta + self.b_delta)
                B = x @ self.W_B
                C = x @ self.W_C
                h = (np.exp(dt[:, None] * A[None, :]) * h
                     + dt[:, None] * B[None, :] * x[:, None])
                salidas[t] = np.sum(h * C[None, :], axis=1) + self.D * x
            self.ultimo_estado = h
            return {
                'salidas': salidas,
                'ultimo_estado': h,
                'pasos': int(X.shape[0]),
                'norma_estado': float(np.linalg.norm(h)),
            }

    # ------------------------------------------------------------------
    # 6) Estimador predictivo de coste (predictive coding)
    # ------------------------------------------------------------------
    class EstimadorPredictivoCoste:
        """Regresor online con incertidumbre (media, desviacion, intervalo)."""

        def __init__(self, dim: int, learning_rate: float = 0.05,
                     seed: int = 2026) -> None:
            self.dim = max(1, int(dim))
            self.learning_rate = max(1e-4, float(learning_rate))
            self.pesos = np.zeros(self.dim, dtype=np.float64)
            self.sesgo = 0.0
            self.varianza = 1.0
            self.n = 0
            self.historial_error: Deque[float] = deque(maxlen=200)

        def predecir(self, x: np.ndarray) -> Dict[str, Any]:
            vector = np.asarray(x, dtype=np.float64).ravel()
            if vector.size != self.dim:
                vector = np.resize(vector, self.dim)
            media = float(vector @ self.pesos + self.sesgo)
            desviacion = math.sqrt(max(self.varianza, 1e-12))
            media = max(1e-9, media)
            margen = 1.96 * desviacion
            return {
                'media': media,
                'desviacion': desviacion,
                'intervalo': (max(0.0, media - margen), media + margen),
                'n': self.n,
            }

        def actualizar(self, x: np.ndarray, objetivo: float) -> float:
            vector = np.asarray(x, dtype=np.float64).ravel()
            if vector.size != self.dim:
                vector = np.resize(vector, self.dim)
            media = float(vector @ self.pesos + self.sesgo)
            error = float(objetivo) - media
            norma = float(vector @ vector) + 1.0
            self.pesos = self.pesos + self.learning_rate * error * vector / norma
            self.sesgo += self.learning_rate * error
            self.varianza = 0.9 * self.varianza + 0.1 * error * error
            self.n += 1
            self.historial_error.append(abs(error))
            return abs(error)

        def reiniciar(self) -> None:
            self.pesos = np.zeros(self.dim, dtype=np.float64)
            self.sesgo = 0.0
            self.varianza = 1.0
            self.n = 0
            self.historial_error.clear()

        def error_medio(self) -> float:
            return float(np.mean(self.historial_error)) if self.historial_error else 0.0

    # ------------------------------------------------------------------
    # 7) Deteccion de ciclos y centralidad (Tarjan + PageRank)
    # ------------------------------------------------------------------
    class DetectorCiclosEspectral:
        """SCC de Tarjan, orden topologico, PageRank y radio espectral."""

        @staticmethod
        def _deps(grafo: Dict[str, Any], nodo: str) -> List[str]:
            datos = grafo.get(nodo)
            if datos is None:
                return []
            if isinstance(datos, dict):
                return list(datos.get('deps_locales', datos.get('deps', [])))
            return list(datos)

        def _scc(self, nodos: Sequence[str],
                 deps: Dict[str, List[str]]) -> List[List[str]]:
            indice: Dict[str, int] = {}
            bajo: Dict[str, int] = {}
            pila: List[str] = []
            en_pila: set = set()
            componentes: List[List[str]] = []
            contador = 0
            for raiz in nodos:
                if raiz in indice:
                    continue
                trabajo: List[Tuple[str, int]] = [(raiz, 0)]
                while trabajo:
                    nodo, i = trabajo[-1]
                    if i == 0:
                        indice[nodo] = bajo[nodo] = contador
                        contador += 1
                        pila.append(nodo)
                        en_pila.add(nodo)
                    hijos = deps.get(nodo, [])
                    if i < len(hijos):
                        trabajo[-1] = (nodo, i + 1)
                        hijo = hijos[i]
                        if hijo not in indice:
                            trabajo.append((hijo, 0))
                        elif hijo in en_pila:
                            bajo[nodo] = min(bajo[nodo], indice[hijo])
                    else:
                        trabajo.pop()
                        for hijo in hijos:
                            if hijo in en_pila and hijo in bajo:
                                bajo[nodo] = min(bajo[nodo], bajo[hijo])
                        if bajo[nodo] == indice[nodo]:
                            componente: List[str] = []
                            while True:
                                extraido = pila.pop()
                                en_pila.discard(extraido)
                                componente.append(extraido)
                                if extraido == nodo:
                                    break
                            componentes.append(componente)
            return componentes

        def detectar(self, grafo: Dict[str, Any],
                     iteraciones_pagerank: int = 40) -> Dict[str, Any]:
            nodos = sorted(grafo)
            indice = {n: i for i, n in enumerate(nodos)}
            n = len(nodos)
            deps = {
                nodo: [d for d in self._deps(grafo, nodo) if d in indice and d != nodo]
                for nodo in nodos
            }

            if n == 0:
                return {'ciclos': [], 'tiene_ciclos': False,
                        'orden_topologico': [], 'pagerank': {},
                        'radio_espectral': 0.0, 'n_nodos': 0}

            adyacencia = np.zeros((n, n), dtype=np.float64)
            for nodo in nodos:
                for dep in deps[nodo]:
                    adyacencia[indice[nodo], indice[dep]] = 1.0

            salida = adyacencia.sum(axis=1)
            cola_dangling = np.where(salida == 0.0)[0]
            normalizada = adyacencia / np.where(
                salida[:, None] > 0.0, salida[:, None], 1.0
            )
            pagerank = np.ones(n, dtype=np.float64) / n
            for _ in range(max(1, int(iteraciones_pagerank))):
                contribucion = normalizada.T @ pagerank
                if cola_dangling.size:
                    contribucion += float(pagerank[cola_dangling].sum()) / n
                pagerank = 0.85 * contribucion + 0.15 / n
            pagerank = pagerank / max(float(pagerank.sum()), 1e-12)

            componentes = self._scc(nodos, deps)
            ciclos = [
                sorted(comp) for comp in componentes
                if len(comp) > 1 or (len(comp) == 1 and comp[0] in deps.get(comp[0], []))
            ]

            pendientes = {nodo: len(deps[nodo]) for nodo in nodos}
            dependientes: Dict[str, List[str]] = {nodo: [] for nodo in nodos}
            for nodo in nodos:
                for dep in deps[nodo]:
                    dependientes[dep].append(nodo)
            disponibles = deque(nodo for nodo in nodos if pendientes[nodo] == 0)
            orden: List[str] = []
            while disponibles:
                actual = disponibles.popleft()
                orden.append(actual)
                for padre in dependientes[actual]:
                    pendientes[padre] -= 1
                    if pendientes[padre] == 0:
                        disponibles.append(padre)
            en_ciclo = {modulo for ciclo in ciclos for modulo in ciclo}
            resto = sorted(
                (nodo for nodo in nodos if nodo not in set(orden)),
                key=lambda nodo: (-float(pagerank[indice[nodo]]), nodo),
            )
            orden.extend(resto)

            return {
                'ciclos': ciclos,
                'tiene_ciclos': bool(ciclos),
                'orden_topologico': orden,
                'pagerank': {nodo: float(pagerank[indice[nodo]]) for nodo in nodos},
                'radio_espectral': _radio_espectral(adyacencia),
                'n_nodos': n,
                'n_aristas': int(adyacencia.sum()),
                'nodos_en_ciclo': sorted(en_ciclo),
                'matriz_adyacencia': adyacencia,
            }

    # ------------------------------------------------------------------
    # 8) Planificador por haz (beam search)
    # ------------------------------------------------------------------
    class PlanificadorBeamImportaciones:
        """Ordena importaciones minimizando camino critico y riesgo de ciclos."""

        def __init__(self, ancho_beam: int = 4, penalizacion_riesgo: float = 0.5,
                     max_nodos: int = 1500) -> None:
            self.ancho_beam = max(1, int(ancho_beam))
            self.penalizacion_riesgo = max(0.0, float(penalizacion_riesgo))
            self.max_nodos = max(1, int(max_nodos))
            self.truncado = False
            self.ultimo_plan: List[Dict[str, Any]] = []

        def _deps(self, grafo: Dict[str, Any], nodo: str) -> List[str]:
            return NeuronaImportacionSBRTM.DetectorCiclosEspectral._deps(grafo, nodo)

        def _coste(self, grafo: Dict[str, Any], nodo: str) -> float:
            datos = grafo.get(nodo)
            if isinstance(datos, dict):
                return float(datos.get('coste_estatico', 0.001))
            return 0.001

        def planificar(self, grafo: Dict[str, Any],
                       costes: Optional[Dict[str, float]] = None,
                       prioridades: Optional[Dict[str, float]] = None,
                       ancho_beam: Optional[int] = None) -> List[Dict[str, Any]]:
            ancho = max(1, int(ancho_beam if ancho_beam is not None else self.ancho_beam))
            costes = dict(costes or {})
            prioridades = dict(prioridades or {})
            nodos = sorted(grafo)
            self.truncado = False
            if len(nodos) > self.max_nodos:
                nodos = sorted(
                    nodos,
                    key=lambda m: (-float(prioridades.get(m, 0.0)), m),
                )[:self.max_nodos]
                self.truncado = True
                logger.warning(
                    "Planificador truncado a %d nodos (de %d)",
                    self.max_nodos, len(grafo),
                )

            conjunto = set(nodos)
            deps = {
                nodo: [d for d in self._deps(grafo, nodo)
                       if d in conjunto and d != nodo]
                for nodo in nodos
            }
            coste_nodo = {
                nodo: max(1e-9, float(costes.get(nodo, self._coste(grafo, nodo))))
                for nodo in nodos
            }

            # estado = (score, orden, colocados, coste_acumulado)
            frentes: List[Tuple[float, Tuple[str, ...], frozenset, float]] = [
                (0.0, (), frozenset(), 0.0)
            ]
            for _ in range(len(nodos)):
                nuevos: List[Tuple[float, Tuple[str, ...], frozenset, float]] = []
                for score, orden, colocados, coste in frentes:
                    disponibles = [
                        nodo for nodo in nodos
                        if nodo not in colocados
                        and all(d in colocados for d in deps[nodo])
                    ]
                    forzado = False
                    if not disponibles:
                        restantes = [nodo for nodo in nodos if nodo not in colocados]
                        if not restantes:
                            continue
                        elegido = max(
                            restantes,
                            key=lambda m: (float(prioridades.get(m, 0.0)),
                                           -len(deps[m]), m),
                        )
                        disponibles = [elegido]
                        forzado = True
                    for nodo in disponibles:
                        c = coste_nodo[nodo]
                        p = float(prioridades.get(nodo, 0.0))
                        nueva_orden = orden + (nodo,)
                        penalizacion = self.penalizacion_riesgo if forzado else 0.0
                        nuevos.append((
                            score - (len(colocados) + 1) * c + 0.05 * p - penalizacion,
                            nueva_orden,
                            colocados | {nodo},
                            coste + c,
                        ))
                if not nuevos:
                    break
                nuevos.sort(key=lambda estado: -estado[0])
                vistos: set = set()
                frentes = []
                for estado in nuevos:
                    clave = estado[2]
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    frentes.append(estado)
                    if len(frentes) >= ancho:
                        break

            mejor = frentes[0] if frentes else (0.0, (), frozenset(), 0.0)
            orden_final = list(mejor[1])
            colocados: set = set()
            plan: List[Dict[str, Any]] = []
            for posicion, nodo in enumerate(orden_final):
                pendientes = [d for d in deps[nodo] if d not in colocados]
                plan.append({
                    'orden': posicion,
                    'modulo': nodo,
                    'coste': float(coste_nodo[nodo]),
                    'coste_acumulado': float(sum(p['coste'] for p in plan) + coste_nodo[nodo]),
                    'prioridad': float(prioridades.get(nodo, 0.0)),
                    'riesgo_ciclo': bool(pendientes),
                    'dependencias_pendientes': pendientes,
                })
                colocados.add(nodo)
            self.ultimo_plan = plan
            return plan

    # ------------------------------------------------------------------
    # 9) Cache neuronal (learning-augmented caching)
    # ------------------------------------------------------------------
    class CacheNeuronalImportaciones:
        """Cache LRU con politica de admision basada en similitud HDC."""

        def __init__(self, capacidad: int = 256, umbral: float = 0.15,
                     dim: int = 32, seed: int = 2026,
                     codificador: Optional["NeuronaImportacionSBRTM.CodificadorHiperdimensional"] = None) -> None:
            self.capacidad = max(1, int(capacidad))
            self.umbral = float(umbral)
            self._cache: "OrderedDict[str, np.ndarray]" = OrderedDict()
            self._accesos: Dict[str, int] = {}
            self._aciertos = 0
            self._fallos = 0
            self._codificador = codificador or NeuronaImportacionSBRTM.CodificadorHiperdimensional(
                dim=dim, seed=seed
            )

        def _vector(self, nombre: str) -> np.ndarray:
            return self._codificador.codificar_modulo(nombre)

        def esta_en_cache(self, nombre: str) -> bool:
            return nombre in self._cache

        def consultar(self, nombre: str) -> bool:
            if nombre in self._cache:
                self._cache.move_to_end(nombre)
                self._aciertos += 1
                return True
            self._fallos += 1
            self._accesos[nombre] = self._accesos.get(nombre, 0) + 1
            return False

        def decidir_admitir(self, nombre: str) -> bool:
            if nombre in self._cache:
                return True
            if len(self._cache) < self.capacidad:
                return True
            if self._accesos.get(nombre, 0) >= 2:
                return True
            if not self._cache:
                return True
            centroide = np.mean(list(self._cache.values()), axis=0)
            novedad = 1.0 - self._codificador.similitud(self._vector(nombre), centroide)
            return bool(novedad >= max(0.0, 1.0 - self.umbral))

        def insertar(self, nombre: str) -> bool:
            if not self.decidir_admitir(nombre):
                return False
            vector = self._vector(nombre)
            self._cache[nombre] = vector
            self._cache.move_to_end(nombre)
            while len(self._cache) > self.capacidad:
                self._cache.popitem(last=False)
            return True

        def precargar(self, nombres: Sequence[str]) -> int:
            insertados = 0
            for nombre in nombres:
                if self.insertar(nombre):
                    insertados += 1
            return insertados

        @property
        def tamano(self) -> int:
            return len(self._cache)

        @property
        def tasa_acierto(self) -> float:
            total = self._aciertos + self._fallos
            return float(self._aciertos) / total if total else 0.0

        def estadisticas(self) -> Dict[str, Any]:
            return {
                'tamano': len(self._cache),
                'capacidad': self.capacidad,
                'aciertos': self._aciertos,
                'fallos': self._fallos,
                'tasa_acierto': self.tasa_acierto,
                'umbral_admision': self.umbral,
            }

        def estado_serializable(self) -> Dict[str, Any]:
            return {'nombres': list(self._cache.keys()),
                    'accesos': dict(self._accesos)}

        def limpiar(self) -> None:
            self._cache.clear()
            self._accesos.clear()
            self._aciertos = 0
            self._fallos = 0

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(self, input_size: Optional[int] = None, output_size: int = 4,
                 nombre: str = "NeuronaImportacionSBRTM",
                 ruta_raiz: Optional[str] = None,
                 seed: Optional[int] = None,
                 dim_embedding: Optional[int] = None,
                 capacidad_cache: Optional[int] = None,
                 max_archivos: Optional[int] = None) -> None:
        entrada = int(input_size) if input_size else len(self.PerfiladorEstatico.EJES)
        salida = max(1, int(output_size))
        super().__init__(entrada, salida, nombre)
        self.seed = int(LUCIA_IMPORT_CONFIG['random_seed'] if seed is None else seed)
        self.dim_embedding = max(8, int(dim_embedding or LUCIA_IMPORT_CONFIG['dim_embedding']))
        self._rng = _rng(self.seed)
        self.config: Dict[str, Any] = {
            'dim_embedding': self.dim_embedding,
            'dim_estado': int(LUCIA_IMPORT_CONFIG['dim_estado']),
            'cabezas_atencion': int(LUCIA_IMPORT_CONFIG['cabezas_atencion']),
            'top_k_expertos': int(LUCIA_IMPORT_CONFIG['top_k_expertos']),
            'capacidad_cache': int(capacidad_cache or LUCIA_IMPORT_CONFIG['capacidad_cache']),
            'learning_rate': float(LUCIA_IMPORT_CONFIG['learning_rate']),
            'ruta_raiz': ruta_raiz or os.getcwd(),
        }
        self.inicializar_pesos()

        self.perfilador = self.PerfiladorEstatico(
            ruta_raiz, max_archivos or int(LUCIA_IMPORT_CONFIG['max_archivos'])
        )
        self.codificador = self.CodificadorHiperdimensional(
            dim=self.dim_embedding, seed=self.seed
        )
        self.atencion = self.AtencionGrafoImportacion(
            dim=self.dim_embedding,
            cabezas=int(self.config['cabezas_atencion']),
            dropout=float(LUCIA_IMPORT_CONFIG['dropout']),
            seed=self.seed,
        )
        self.enrutador = self.EnrutadorMezclaExpertos(
            dim=self.dim_embedding,
            n_expertos=int(len(self.NOMBRES_ESTRATEGIA)),
            top_k=int(self.config['top_k_expertos']),
            seed=self.seed,
        )
        self.ssm = self.NeuronaEstadoSelectivo(
            dim=self.input_size,
            dim_estado=int(self.config['dim_estado']),
            seed=self.seed,
        )
        self.estimador = self.EstimadorPredictivoCoste(
            dim=self.input_size,
            learning_rate=float(self.config['learning_rate']),
            seed=self.seed,
        )
        self.detector = self.DetectorCiclosEspectral()
        self.planificador = self.PlanificadorBeamImportaciones(
            ancho_beam=int(LUCIA_IMPORT_CONFIG['ancho_beam']),
            max_nodos=int(LUCIA_IMPORT_CONFIG['max_nodos_plan']),
        )
        self.cache = self.CacheNeuronalImportaciones(
            capacidad=int(self.config['capacidad_cache']),
            umbral=float(LUCIA_IMPORT_CONFIG['umbral_admision']),
            dim=min(64, self.dim_embedding),
            seed=self.seed,
            codificador=self.codificador,
        )

        self._grafo: Dict[str, Dict[str, Any]] = {}
        self._analisis: Dict[str, Any] = {}
        self._adyacencia: Optional[np.ndarray] = None
        self._orden_analisis: List[str] = []
        self.ultima_atencion: Optional[np.ndarray] = None
        self.historial_planes: Deque[List[Dict[str, Any]]] = deque(maxlen=32)
        self.historial_costes: Deque[Dict[str, float]] = deque(maxlen=64)
        logger.debug(
            "NeuronaImportacionSBRTM creada (in=%d, out=%d, dim=%d, seed=%d)",
            self.input_size, self.output_size, self.dim_embedding, self.seed,
        )

    # ------------------------------------------------------------------
    # Pesos y parametros
    # ------------------------------------------------------------------
    def inicializar_pesos(self) -> None:
        generador = _rng(self.seed + 1)
        escala_entrada = math.sqrt(2.0 / max(1, self.input_size))
        self.W_entrada = generador.normal(
            0.0, escala_entrada, (self.input_size, self.dim_embedding)
        )
        self.b_entrada = np.zeros(self.dim_embedding, dtype=np.float64)
        escala_salida = math.sqrt(2.0 / max(1, self.dim_embedding))
        self.W_salida = generador.normal(
            0.0, escala_salida, (self.dim_embedding, self.output_size)
        )
        self.b_salida = np.zeros((1, self.output_size), dtype=np.float64)
        # Compatibilidad con NeuronaMemoriaBase (params/estadisticas)
        self.pesos = self.W_salida
        self.sesgo = self.b_salida

    def _parametros_nombrados(self) -> List[Tuple[str, np.ndarray]]:
        parametros: List[Tuple[str, np.ndarray]] = [
            ('W_entrada', self.W_entrada),
            ('b_entrada', self.b_entrada),
            ('W_salida', self.W_salida),
            ('b_salida', self.b_salida.reshape(-1)),
        ]
        for cabeza in range(self.atencion.cabezas):
            parametros.append((f'atencion.W[{cabeza}]', self.atencion.W[cabeza]))
            parametros.append((f'atencion.a_origen[{cabeza}]', self.atencion.a_origen[cabeza]))
            parametros.append((f'atencion.a_destino[{cabeza}]', self.atencion.a_destino[cabeza]))
        parametros.append(('moe.W_gate', self.enrutador.W_gate))
        for experto in range(self.enrutador.n_expertos):
            parametros.append((f'moe.W_expertos[{experto}]', self.enrutador.W_expertos[experto]))
        parametros.append(('ssm.W_delta', self.ssm.W_delta))
        parametros.append(('ssm.W_B', self.ssm.W_B))
        parametros.append(('ssm.W_C', self.ssm.W_C))
        parametros.append(('ssm.A_log', self.ssm.A_log))
        parametros.append(('estimador.pesos', self.estimador.pesos))
        return parametros

    def params_count(self) -> int:
        return int(sum(int(np.asarray(p).size) for _, p in self._parametros_nombrados()))

    # ------------------------------------------------------------------
    # Forward neuronal
    # ------------------------------------------------------------------
    def _ajustar_dim(self, vector: np.ndarray, dimension: int) -> np.ndarray:
        vector = np.asarray(vector, dtype=np.float64).ravel()
        if vector.size == dimension:
            return vector
        if vector.size > dimension:
            return vector[:dimension]
        return np.concatenate([vector, np.zeros(dimension - vector.size)])

    def _adyacencia_para(self, n: int,
                         adyacencia: Optional[np.ndarray] = None) -> np.ndarray:
        if adyacencia is not None:
            matriz = np.asarray(adyacencia, dtype=np.float64)
            if matriz.shape == (n, n):
                return matriz
        if self._adyacencia is not None and self._adyacencia.shape == (n, n):
            return self._adyacencia
        return np.ones((n, n), dtype=np.float64)

    def _matriz_adyacencia(self, orden: Sequence[str],
                           grafo: Optional[Dict[str, Dict[str, Any]]] = None) -> np.ndarray:
        """Matriz booleana modulo -> dependencia en el orden indicado."""
        orden = list(orden)
        n = len(orden)
        matriz = np.eye(n, dtype=np.float64)
        if n == 0:
            return matriz
        datos_grafo = grafo if grafo is not None else self._grafo
        indices = {modulo: i for i, modulo in enumerate(orden)}
        for modulo in orden:
            datos = datos_grafo.get(modulo, {})
            for dep in datos.get('deps_locales', []):
                if dep in indices:
                    matriz[indices[modulo], indices[dep]] = 1.0
        return matriz

    def forward(self, entrada: np.ndarray,
                adyacencia: Optional[np.ndarray] = None) -> np.ndarray:
        """Propaga features de modulos y devuelve probabilidades de estrategia."""
        x = np.asarray(entrada, dtype=np.float64)
        unico = x.ndim == 1
        if unico:
            x = x[None, :]
        if x.ndim != 2:
            raise ValueError("forward espera un vector o una matriz 2D")
        if x.shape[1] != self.input_size:
            x = np.stack([self._ajustar_dim(fila, self.input_size) for fila in x], axis=0)
        if not np.all(np.isfinite(x)):
            x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

        oculto = np.tanh(x @ self.W_entrada + self.b_entrada)
        matriz_adyacencia = self._adyacencia_para(oculto.shape[0], adyacencia)
        contexto, atencion = self.atencion.forward(oculto, matriz_adyacencia)
        mezcla = self.enrutador.forward(contexto)
        logits = np.asarray(mezcla['salida']) @ self.W_salida + self.b_salida
        probabilidades = _softmax(logits, eje=1)

        self.historial_activaciones.append(probabilidades.copy())
        self.historial_gradientes.append({
            'atencion': np.asarray(atencion).copy(),
            'carga_expertos': np.asarray(mezcla['carga']).copy(),
            'perdida_balance': float(mezcla['perdida_balance']),
        })
        self.pasos += 1
        self.ultima_atencion = atencion
        return probabilidades[0] if unico else probabilidades

    def predict(self, entrada: np.ndarray) -> np.ndarray:
        return self.forward(entrada)

    def _vector_caracteristicas(self, modulo: str) -> np.ndarray:
        datos = self._grafo.get(modulo)
        if datos is None:
            return np.zeros(self.input_size, dtype=np.float64)
        vector = self.perfilador.caracteristicas_modulo(datos)
        return self._ajustar_dim(vector, self.input_size)

    # ------------------------------------------------------------------
    # Analisis del arbol de importaciones
    # ------------------------------------------------------------------
    def analizar(self, ruta_raiz: Optional[str] = None,
                 perfil: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perfila el arbol de imports y prepara el grafo neuronal."""
        if perfil is None:
            if ruta_raiz:
                self.perfilador = self.PerfiladorEstatico(
                    ruta_raiz, self.perfilador.max_archivos
                )
                self.config['ruta_raiz'] = self.perfilador.raiz
            perfil = self.perfilador.perfil_completo()
        grafo = perfil.get('grafo', {})
        deteccion = self.detector.detectar(grafo)
        for ciclo in deteccion.get('ciclos', []):
            for modulo in ciclo:
                if modulo in grafo:
                    grafo[modulo]['tiene_ciclo'] = True
                    grafo[modulo]['clasificacion'] = 'local'

        orden = list(deteccion.get('orden_topologico', sorted(grafo)))
        adyacencia = self._matriz_adyacencia(orden, grafo)

        costes = {
            modulo: float(datos.get('coste_estatico', 0.0))
            for modulo, datos in grafo.items()
        }
        resumen_perfil = dict(perfil.get('resumen', {}))
        resumen_perfil['ciclos'] = len(deteccion.get('ciclos', []))
        resumen_perfil['radio_espectral'] = float(deteccion.get('radio_espectral', 0.0))

        self._grafo = grafo
        self._orden_analisis = orden
        self._adyacencia = adyacencia
        self._analisis = {
            'raiz': perfil.get('raiz', self.perfilador.raiz),
            'modulos': sorted(grafo),
            'grafo': grafo,
            'orden': orden,
            'deteccion': deteccion,
            'costes_estaticos': costes,
            'prioridades': dict(deteccion.get('pagerank', {})),
            'resumen': resumen_perfil,
            'adyacencia': adyacencia,
        }
        logger.info(
            "Analisis de importaciones: %d modulos, %d aristas, %d ciclos",
            len(grafo), resumen_perfil.get('n_aristas', 0), len(deteccion.get('ciclos', [])),
        )
        return self._analisis

    # ------------------------------------------------------------------
    # Prediccion de costes
    # ------------------------------------------------------------------
    def predecir_costes(self, epocas: int = 2) -> Dict[str, Any]:
        """Predice coste por modulo con SSM + codificacion predictiva."""
        if not self._analisis:
            self.analizar()
        grafo = self._grafo
        if not grafo:
            return {'modulos': [], 'costes': {}, 'intervalos': {}, 'orden': [],
                    'correccion': {}, 'salida_ssm': np.zeros((0, self.input_size)),
                    'error_medio': 0.0}

        orden = list(self._analisis.get('orden') or sorted(grafo))
        matriz, modulos = self.perfilador.matriz_caracteristicas(grafo, orden)
        medias = matriz.mean(axis=0)
        desviaciones = matriz.std(axis=0)
        desviaciones = np.where(desviaciones < 1e-9, 1.0, desviaciones)
        normalizada = (matriz - medias) / desviaciones

        estaticos = np.array(
            [float(grafo[m].get('coste_estatico', 1e-4)) for m in modulos],
            dtype=np.float64,
        )
        for _ in range(max(1, int(epocas))):
            for i in range(len(modulos)):
                self.estimador.actualizar(normalizada[i], float(estaticos[i]))

        exploracion = self.ssm.forward(normalizada)
        salidas = np.asarray(exploracion['salidas'], dtype=np.float64)
        correccion = 1.0 + 0.25 * np.tanh(salidas.mean(axis=1))

        costes: Dict[str, float] = {}
        intervalos: Dict[str, Tuple[float, float]] = {}
        correcciones: Dict[str, float] = {}
        for i, modulo in enumerate(modulos):
            prediccion = self.estimador.predecir(normalizada[i])
            coste = max(1e-9, float(prediccion['media']) * float(correccion[i]))
            margen = 1.96 * float(prediccion['desviacion'])
            costes[modulo] = coste
            intervalos[modulo] = (max(0.0, coste - margen), coste + margen)
            correcciones[modulo] = float(correccion[i])

        resultado = {
            'modulos': modulos,
            'costes': costes,
            'intervalos': intervalos,
            'orden': modulos,
            'correccion': correcciones,
            'salida_ssm': salidas,
            'error_medio': self.estimador.error_medio(),
            'coste_total': float(sum(costes.values())),
        }
        self.historial_costes.append(dict(costes))
        return resultado

    # ------------------------------------------------------------------
    # Estrategia por modulo
    # ------------------------------------------------------------------
    def decidir_estrategia(self, modulo: str) -> Dict[str, Any]:
        """Elige estrategia neuronal (lazy/eager/cache/paralelo) para un modulo."""
        if not self._analisis:
            self.analizar()
        vector = self._vector_caracteristicas(modulo).reshape(1, -1)
        probabilidades = np.asarray(self.forward(vector), dtype=np.float64).ravel()
        indice_ganador = int(np.argmax(probabilidades))
        return {
            'modulo': modulo,
            'estrategia': self.NOMBRES_ESTRATEGIA[indice_ganador],
            'confianza': float(probabilidades[indice_ganador]),
            'probabilidades': {
                nombre: float(probabilidades[i])
                for i, nombre in enumerate(self.NOMBRES_ESTRATEGIA)
            },
            'en_cache': self.cache.esta_en_cache(modulo),
        }

    # ------------------------------------------------------------------
    # Planificacion
    # ------------------------------------------------------------------
    def planificar(self, ancho_beam: Optional[int] = None,
                   costes: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """Devuelve un plan de importaciones anotado con estrategia neuronal."""
        if not self._analisis:
            self.analizar()
        if not self._grafo:
            return []
        if costes is None:
            costes = self.predecir_costes()['costes']
        prioridades = dict(self._analisis.get('prioridades', {}))
        plan = self.planificador.planificar(
            self._grafo, costes, prioridades, ancho_beam=ancho_beam
        )
        if plan:
            modulos = [paso['modulo'] for paso in plan]
            matriz, _ = self.perfilador.matriz_caracteristicas(self._grafo, modulos)
            adyacencia = self._matriz_adyacencia(modulos)
            probabilidades = np.atleast_2d(self.forward(matriz, adyacencia))
            for i, paso in enumerate(plan):
                if i >= probabilidades.shape[0]:
                    break
                ganador = int(np.argmax(probabilidades[i]))
                paso['estrategia'] = self.NOMBRES_ESTRATEGIA[ganador]
                paso['confianza'] = float(probabilidades[i][ganador])
                paso['en_cache'] = self.cache.esta_en_cache(paso['modulo'])
        self.historial_planes.append(plan)
        return plan

    def simular_ejecucion(self, plan: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Simula el plan aplicando aciertos de cache neuronales."""
        if plan is None:
            plan = self.planificar()
        tiempo_total = 0.0
        aciertos = 0
        detalle: List[Dict[str, Any]] = []
        for paso in plan:
            modulo = str(paso.get('modulo', ''))
            coste = float(paso.get('coste', 0.0))
            if self.cache.consultar(modulo):
                aciertos += 1
                coste *= 0.15
                estado = 'hit'
            else:
                self.cache.insertar(modulo)
                estado = 'miss'
            tiempo_total += coste
            detalle.append({'modulo': modulo, 'coste': coste, 'cache': estado})
        return {
            'tiempo_total': float(tiempo_total),
            'n_modulos': len(plan),
            'aciertos_cache': aciertos,
            'tasa_acierto': float(aciertos) / len(plan) if plan else 0.0,
            'detalle': detalle,
        }

    # ------------------------------------------------------------------
    # Estabilidad, estadisticas y persistencia
    # ------------------------------------------------------------------
    def verificar_estabilidad(self) -> Dict[str, Any]:
        problemas: List[str] = []
        for nombre, parametro in self._parametros_nombrados():
            arreglo = np.asarray(parametro, dtype=np.float64)
            if arreglo.size and not np.all(np.isfinite(arreglo)):
                problemas.append(f"{nombre} contiene valores no finitos")
        radio = 0.0
        if self._adyacencia is not None and self._adyacencia.size:
            radio = _radio_espectral(self._adyacencia)
        norma = _norma_global([p for _, p in self._parametros_nombrados()])
        entropia = self.atencion.entropia_atencion()
        return {
            'estable': not problemas,
            'problemas': problemas,
            'radio_espectral': radio,
            'norma_pesos': norma,
            'entropia_atencion': entropia,
            'atencion_no_colapsada': bool(entropia >= 0.0),
            'n_parametros': self.params_count(),
        }

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        resumen = self._analisis.get('resumen', {}) if self._analisis else {}
        estadisticas.update({
            'version': __version__,
            'dim_embedding': self.dim_embedding,
            'n_estrategias': len(self.NOMBRES_ESTRATEGIA),
            'n_modulos_analizados': len(self._grafo),
            'n_ciclos': len(self._analisis.get('deteccion', {}).get('ciclos', [])) if self._analisis else 0,
            'coste_total_predicho': float(
                sum(self.historial_costes[-1].values())
            ) if self.historial_costes else 0.0,
            'cache': self.cache.estadisticas(),
            'moe_perdida_balance': self.enrutador.perdida_balance(),
            'estimador_error_medio': self.estimador.error_medio(),
            'resumen_perfil': dict(resumen),
        })
        return estadisticas

    def estado_serializable(self) -> Dict[str, Any]:
        return {
            'version': __version__,
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'config': dict(self.config),
            'pesos': {nombre: np.asarray(parametro).copy()
                      for nombre, parametro in self._parametros_nombrados()},
            'cache': self.cache.estado_serializable(),
            'analisis_resumen': dict(self._analisis.get('resumen', {})) if self._analisis else {},
        }

    def guardar(self, ruta: str) -> None:
        with open(ruta, 'wb') as f:
            pickle.dump(self.estado_serializable(), f)
        logger.info("Neurona de importaciones guardada en %s", ruta)

    def cargar(self, ruta: str) -> "NeuronaImportacionSBRTM":
        with open(ruta, 'rb') as f:
            estado = pickle.load(f)
        pesos = estado.get('pesos', {})
        for nombre, parametro in self._parametros_nombrados():
            guardado = pesos.get(nombre)
            if guardado is None:
                continue
            arreglo = np.asarray(guardado, dtype=np.float64)
            actual = np.asarray(parametro)
            if arreglo.shape == actual.shape:
                actual[...] = arreglo
            else:
                logger.warning("Forma incompatible al cargar %s: %s != %s",
                               nombre, arreglo.shape, actual.shape)
        self.pesos = self.W_salida
        self.sesgo = self.b_salida
        cache = estado.get('cache', {})
        for nombre in cache.get('nombres', []):
            self.cache.insertar(str(nombre))
        logger.info("Neurona de importaciones cargada desde %s", ruta)
        return self

    def reiniciar(self) -> None:
        """Reinicia memoria, cache e historiales conservando pesos."""
        self.resetear_historial()
        self.cache.limpiar()
        self.historial_planes.clear()
        self.historial_costes.clear()
        self.estimador.reiniciar()
        self._analisis = {}
        self._grafo = {}
        self._adyacencia = None
        self._orden_analisis = []
        self.pasos = 0

    def resumen(self) -> Dict[str, Any]:
        return {
            'info': self.info(),
            'params': self.params_count(),
            'estadisticas': self.obtener_estadisticas(),
            'estabilidad': self.verificar_estabilidad(),
            'plan': self._analisis.get('orden', [])[:10] if self._analisis else [],
        }


# ===========================================================================
# API de alto nivel
# ===========================================================================
def crear_neurona_importacion(ruta_raiz: Optional[str] = None,
                              input_size: Optional[int] = None,
                              output_size: int = 4,
                              seed: Optional[int] = None,
                              **kwargs: Any) -> NeuronaImportacionSBRTM:
    """Fabrica una ``NeuronaImportacionSBRTM`` lista para usar."""
    parametros = dict(kwargs)
    parametros.setdefault('ruta_raiz', ruta_raiz)
    if seed is not None:
        parametros['seed'] = seed
    return NeuronaImportacionSBRTM(input_size=input_size,
                                   output_size=output_size, **parametros)


def analizar_importaciones(ruta_raiz: Optional[str] = None,
                           seed: Optional[int] = None,
                           con_plan: bool = True,
                           ancho_beam: Optional[int] = None) -> Dict[str, Any]:
    """Analiza un arbol de codigo y devuelve perfil, costes y plan neuronal."""
    neurona = crear_neurona_importacion(ruta_raiz=ruta_raiz, seed=seed)
    perfil = neurona.perfilador.perfil_completo()
    analisis = neurona.analizar(perfil=perfil)
    costes = neurona.predecir_costes()
    plan = neurona.planificar(ancho_beam=ancho_beam, costes=costes['costes']) if con_plan else []
    return {
        'neurona': neurona,
        'perfil': perfil,
        'analisis': analisis,
        'costes': costes,
        'plan': plan,
        'resumen': perfil.get('resumen', {}),
    }


def plan_de_importacion(ruta_raiz: Optional[str] = None,
                        ancho_beam: Optional[int] = None,
                        seed: Optional[int] = None) -> List[Dict[str, Any]]:
    """Devuelve solo el plan de importaciones ordenado y anotado."""
    neurona = crear_neurona_importacion(ruta_raiz=ruta_raiz, seed=seed)
    neurona.analizar()
    return neurona.planificar(ancho_beam=ancho_beam)


def benchmark_neurona_importacion(neurona: Optional[NeuronaImportacionSBRTM] = None,
                                  ruta_raiz: Optional[str] = None,
                                  repeticiones: int = 3,
                                  ancho_beam: Optional[int] = None) -> Dict[str, Any]:
    """Mide tiempos de analisis, prediccion y planificacion."""
    neurona = neurona or crear_neurona_importacion(ruta_raiz=ruta_raiz)
    tiempos_analisis: List[float] = []
    tiempos_plan: List[float] = []
    plan: List[Dict[str, Any]] = []
    for _ in range(max(1, int(repeticiones))):
        inicio = time.perf_counter()
        neurona.analizar()
        tiempos_analisis.append(time.perf_counter() - inicio)
        inicio = time.perf_counter()
        plan = neurona.planificar(ancho_beam=ancho_beam)
        tiempos_plan.append(time.perf_counter() - inicio)
    simulacion = neurona.simular_ejecucion(plan)
    return {
        'n_modulos': len(neurona._grafo),
        'n_pasos_plan': len(plan),
        'analisis_medio_s': float(np.mean(tiempos_analisis)),
        'plan_medio_s': float(np.mean(tiempos_plan)),
        'repeticiones': int(repeticiones),
        'truncado': bool(neurona.planificador.truncado),
        'tiempo_total_simulado': float(simulacion['tiempo_total']),
        'tasa_acierto_simulada': float(simulacion['tasa_acierto']),
    }


def demo(ruta_raiz: Optional[str] = None) -> Dict[str, Any]:
    """Demostracion autocontenida (utilizable como ``python modulo.py``)."""
    ruta = ruta_raiz or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 74)
    print("RF_SL_SBRTM_IMPORT :: neuronas de importacion (v%s)" % __version__)
    print("Raiz analizada:", ruta)
    print("=" * 74)

    neurona = crear_neurona_importacion(ruta_raiz=ruta)
    perfil = neurona.perfilador.perfil_completo()
    resumen = perfil.get('resumen', {})
    print("Modulos:", resumen.get('n_modulos'), "| aristas:",
          resumen.get('n_aristas'), "| imports:", resumen.get('total_imports'))
    print("Tipos:", resumen.get('por_tipo'))

    analisis = neurona.analizar(perfil=perfil)
    deteccion = analisis['deteccion']
    print("Ciclos:", deteccion['ciclos'] or "ninguno",
          "| radio espectral: %.4f" % deteccion['radio_espectral'])

    costes = neurona.predecir_costes()
    print("Coste total predicho: %.6f s (error medio %.6f)"
          % (costes['coste_total'], costes['error_medio']))

    plan = neurona.planificar(costes=costes['costes'])
    print("Plan de importacion (top 10):")
    for paso in plan[:10]:
        print("  %2d. %-42s %-9s coste=%.6f riesgo=%s"
              % (paso['orden'], paso['modulo'][:42], paso.get('estrategia', '?'),
                 paso['coste'], paso['riesgo_ciclo']))

    simulacion = neurona.simular_ejecucion(plan)
    print("Simulacion: %.6fs | cache hit-rate %.2f%%"
          % (simulacion['tiempo_total'], 100.0 * simulacion['tasa_acierto']))
    print("Estabilidad:", neurona.verificar_estabilidad()['estable'],
          "| parametros:", neurona.params_count())
    print("=" * 74)
    return {
        'perfil': perfil,
        'analisis': analisis,
        'costes': costes,
        'plan': plan,
        'simulacion': simulacion,
        'resumen': neurona.resumen(),
    }


__all__ = [
    # Neuronas de importacion
    'NeuronaImportacionSBRTM',
    'LUCIA_IMPORT_CONFIG',
    'crear_neurona_importacion',
    'analizar_importaciones',
    'plan_de_importacion',
    'benchmark_neurona_importacion',
    'demo',
    'info_paquete',
    # Utilidades RF_SL
    'NeuronaMemoriaBase',
    'ModelRegistry',
    'TrainingConfig',
    'MetricsCollector',
    'DataPipeline',
    'build_model',
    'train_all_models',
    'compare_models',
    'validate_model',
    'serialize_model',
    'deserialize_model',
    'benchmark_model',
    'summary',
    'create_default_pipeline',
    'create_ensemble_predictions',
    'quick_train',
    'quick_predict',
    'quick_evaluate',
    'get_available_models',
    'HyperparameterSearch',
    'PerformanceMonitor',
    'FeatureSelector',
]


logger.info("RF_SL_SBRTM_IMPORT cargado (v%s): neuronas de importacion listas",
            __version__)


if __name__ == "__main__":  # pragma: no cover
    demo()