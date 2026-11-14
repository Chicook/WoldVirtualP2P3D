"""RF_SL_SBRTM_RF_SL1_7_1.py
Neuronas especializadas en K vecinos mas cercanos (RF_SL - SBRTM - RF - 2026).
===============================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
de ``KNearestNeighborsOptimizer`` (sin imports, base ni helpers) y lo sustituye
por una implementacion real de KNN con calculo vectorizado y eficiente:

  * ``NeuronaKNN``: neurona de vecindad para clasificacion y regresion.
      - Metricas: ``euclidean``, ``manhattan``, ``cosine``, ``minkowski``,
        ``chebyshev`` y ``hamming``.
      - Distancias por matriz de Gram para Euclidiana y coseno; calculo por
        bloques para Manhattan/Minkowski/Chebyshev/Hamming, acotando memoria.
      - Vecinos con ``argpartition`` + orden estable; pesos ``uniform``,
        ``distance`` o callable.
      - Clasificacion con etiquetas string/one-hot, ``predict_proba`` y
        margen de decision; regresion monosalida o multi-salida.
      - Normalizacion opcional de caracteristicas y cache de normas.
      - ``kneighbors``, ``predict``, ``predict_proba``, ``evaluate``,
        metricas completas y serializacion compatible con el checkpoint
        historico.
      - Decoradores ``@lru_cache`` para normalizar metricas, ``@property``
        para atributos derivados y ``@_requiere_ajuste`` para la API publica.

  * ``NeuronaKNN.NucleoDistancias``: **clase anidada** que fusiona metricas,
      normalizacion de filas, calculo por bloques, busqueda de vecinos y
      pesos.

  * ``NeuronaKNN.NucleoVotacion``: **clase anidada** que fusiona votos,
      probabilidades, agregacion de regresion, margen y metricas.

  * ``KNearestNeighborsOptimizer``: adaptador de compatibilidad con la API
      historica de RF_SL1_7. Mantiene ``_k``, ``_distance_metric``, ``_data``,
      ``_labels``, ``_is_fitted``, ``_accuracy``, ``_convergence_history`` y
      la cabeza lineal legada (``forward``/``backward``) sin duplicar KNN.

  * Utilidades: ``crear_neurona``, ``tipos_disponibles``,
      ``create_k_nearest_neighbors_optimizer``, ``entrenar_y_evaluar``,
      ``benchmark_modelo``, ``guardar_modelo``, ``cargar_modelo`` y ``demo``.

Referencias
-----------
- KNN de Cover & Hart (1967).
- Distancias de Minkowski, coseno y Hamming.
- Busqueda de vecinos con ``argpartition`` y particionado por bloques.
- Normalizacion z-score y votacion ponderada por distancia.

Uso
---
    from RF_SL_SBRTM_RF_SL1_7_1 import NeuronaKNN

    modelo = NeuronaKNN(input_size=3, k=5, metrica="euclidean")
    modelo.fit(X, y)
    print(modelo.evaluate(X, y))
    print(modelo.predict_proba(X[:5]))
"""

from __future__ import annotations

import functools
import logging
import math
import pickle
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

__version__ = "2026.1.0"


# ---------------------------------------------------------------------------
# Configuracion global
# ---------------------------------------------------------------------------
LUCIA_KNN_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "k": 5,
    "metrica": "euclidean",
    "weights": "uniform",
    "tarea": "auto",
    "normalize": False,
    "p": 3,
    "epsilon": 1e-8,
    "bloque_max": 2_000_000,
    "epochs": 1,
}

METRICAS_KNN: Tuple[str, ...] = (
    "euclidean", "manhattan", "cosine", "minkowski", "chebyshev", "hamming",
)


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

    _CLAVE_BASE = "_rf_snrtm_base_import_knn"
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
# Decoradores y utilidades de validacion
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=32)
def normalizar_metrica(nombre: Optional[str]) -> str:
    """Normaliza el nombre de una metrica (cacheado por ser puro)."""
    clave = str(nombre or "euclidean").strip().lower().replace("-", "_")
    alias = {
        "euclidean": "euclidean", "euclidiana": "euclidean",
        "l2": "euclidean",
        "manhattan": "manhattan", "l1": "manhattan",
        "cityblock": "manhattan", "city_block": "manhattan",
        "cosine": "cosine", "coseno": "cosine", "cos": "cosine",
        "minkowski": "minkowski", "lp": "minkowski",
        "chebyshev": "chebyshev", "chebychev": "chebyshev",
        "hamming": "hamming",
    }
    clave = alias.get(clave, clave)
    if clave not in METRICAS_KNN:
        raise ValueError(
            f"Metrica desconocida: {nombre!r}. Usa una de {METRICAS_KNN}"
        )
    return clave


def _requiere_ajuste(func: Callable[..., Any]) -> Callable[..., Any]:
    """Exige que el modelo este ajustado antes de llamar al metodo."""
    @functools.wraps(func)
    def envoltura(self: Any, *args: Any, **kwargs: Any) -> Any:
        if not getattr(self, "_is_fitted", False):
            raise RuntimeError(
                f"{type(self).__name__} no esta ajustado: llama a fit primero"
            )
        return func(self, *args, **kwargs)

    return envoltura


# ---------------------------------------------------------------------------
# Neurona KNN
# ---------------------------------------------------------------------------
class NeuronaKNN(NeuronaMemoriaBase):
    """Clasificador/regresor de K vecinos mas cercanos.

    Parametros
    ----------
    input_size, output_size:
        Dimensiones declaradas (compatibilidad con la jerarquia).
    k:
        Numero de vecinos.
    metrica:
        ``euclidean``, ``manhattan``, ``cosine``, ``minkowski``,
        ``chebyshev`` o ``hamming``.
    weights:
        ``uniform``, ``distance`` o callable ``f(distancias) -> pesos``.
    tarea:
        ``auto``, ``clasificacion`` o ``regresion``.
    normalize:
        Normalizacion z-score ajustada con los datos de entrenamiento.
    p:
        Exponente de Minkowski.
    bloque_max:
        Maximo de elementos temporales por bloque de distancias.
    """

    # ------------------------------------------------------------------
    # Clase anidada 1: distancias y vecinos
    # ------------------------------------------------------------------
    class NucleoDistancias:
        """Fusiona metricas, calculo por bloques, vecinos y pesos."""

        METRICAS = METRICAS_KNN

        def __init__(self, metrica: str = "euclidean", p: float = 3.0,
                     epsilon: float = 1e-8,
                     bloque_max: int = 2_000_000) -> None:
            self.metrica = normalizar_metrica(metrica)
            self.p = float(p)
            if self.p <= 0.0:
                raise ValueError("p de Minkowski debe ser positivo")
            self.epsilon = max(1e-15, float(epsilon))
            self.bloque_max = max(1, int(bloque_max))
            self._data: Optional[np.ndarray] = None
            self._norm2: Optional[np.ndarray] = None
            self._unit: Optional[np.ndarray] = None

        # -- ajuste y metricas base ----------------------------------
        def ajustar(self, data: np.ndarray) -> "NucleoDistancias":
            matriz = np.ascontiguousarray(
                np.asarray(data, dtype=np.float64)
            )
            if matriz.ndim != 2:
                raise ValueError("Los datos de referencia deben ser 2D")
            self._data = matriz
            self._norm2 = np.einsum('ij,ij->i', matriz, matriz)
            normas = np.sqrt(np.maximum(self._norm2, self.epsilon))
            self._unit = matriz / normas[:, None]
            return self

        def _comprobar(self) -> np.ndarray:
            if self._data is None:
                raise RuntimeError("NucleoDistancias no ajustado")
            return self._data

        @staticmethod
        def euclidiana(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            """Matriz de distancias euclidianas via producto de Gram."""
            x = np.asarray(a, dtype=np.float64)
            y = np.asarray(b, dtype=np.float64)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            if y.ndim == 1:
                y = y.reshape(1, -1)
            x2 = np.einsum('ij,ij->i', x, x)[:, None]
            y2 = np.einsum('ij,ij->i', y, y)[None, :]
            distancia2 = x2 + y2 - 2.0 * (x @ y.T)
            return np.sqrt(np.maximum(distancia2, 0.0))

        @staticmethod
        def _bloques(a: np.ndarray, b: np.ndarray,
                     bloque_max: int) -> np.ndarray:
            """Calcula una matriz de distancias acotando memoria."""
            x = np.asarray(a, dtype=np.float64)
            y = np.asarray(b, dtype=np.float64)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            if y.ndim == 1:
                y = y.reshape(1, -1)
            n_consultas = x.shape[0]
            n_referencia = y.shape[0]
            dimension = max(1, x.shape[1])
            tam_bloque = max(
                1, int(bloque_max) // max(1, n_referencia * dimension)
            )
            salida = np.empty((n_consultas, n_referencia), dtype=np.float64)
            for inicio in range(0, n_consultas, tam_bloque):
                fin = min(n_consultas, inicio + tam_bloque)
                diff = x[inicio:fin, None, :] - y[None, :, :]
                salida[inicio:fin] = np.sum(np.abs(diff), axis=2)
            return salida

        @classmethod
        def manhattan(cls, a: np.ndarray, b: np.ndarray,
                      bloque_max: int = 2_000_000) -> np.ndarray:
            return cls._bloques(a, b, bloque_max)

        @classmethod
        def minkowski(cls, a: np.ndarray, b: np.ndarray, p: float,
                      bloque_max: int = 2_000_000) -> np.ndarray:
            x = np.asarray(a, dtype=np.float64)
            y = np.asarray(b, dtype=np.float64)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            if y.ndim == 1:
                y = y.reshape(1, -1)
            n_consultas = x.shape[0]
            n_referencia = y.shape[0]
            dimension = max(1, x.shape[1])
            tam_bloque = max(
                1, int(bloque_max) // max(1, n_referencia * dimension)
            )
            salida = np.empty((n_consultas, n_referencia), dtype=np.float64)
            for inicio in range(0, n_consultas, tam_bloque):
                fin = min(n_consultas, inicio + tam_bloque)
                diff = np.abs(x[inicio:fin, None, :] - y[None, :, :])
                salida[inicio:fin] = np.sum(diff ** p, axis=2) ** (1.0 / p)
            return salida

        @classmethod
        def chebyshev(cls, a: np.ndarray, b: np.ndarray,
                      bloque_max: int = 2_000_000) -> np.ndarray:
            x = np.asarray(a, dtype=np.float64)
            y = np.asarray(b, dtype=np.float64)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            if y.ndim == 1:
                y = y.reshape(1, -1)
            n_consultas = x.shape[0]
            n_referencia = y.shape[0]
            dimension = max(1, x.shape[1])
            tam_bloque = max(
                1, int(bloque_max) // max(1, n_referencia * dimension)
            )
            salida = np.empty((n_consultas, n_referencia), dtype=np.float64)
            for inicio in range(0, n_consultas, tam_bloque):
                fin = min(n_consultas, inicio + tam_bloque)
                diff = np.abs(x[inicio:fin, None, :] - y[None, :, :])
                salida[inicio:fin] = np.max(diff, axis=2)
            return salida

        @classmethod
        def hamming(cls, a: np.ndarray, b: np.ndarray,
                    bloque_max: int = 2_000_000) -> np.ndarray:
            x = np.asarray(a, dtype=np.float64)
            y = np.asarray(b, dtype=np.float64)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            if y.ndim == 1:
                y = y.reshape(1, -1)
            n_consultas = x.shape[0]
            n_referencia = y.shape[0]
            dimension = max(1, x.shape[1])
            tam_bloque = max(
                1, int(bloque_max) // max(1, n_referencia * dimension)
            )
            salida = np.empty((n_consultas, n_referencia), dtype=np.float64)
            for inicio in range(0, n_consultas, tam_bloque):
                fin = min(n_consultas, inicio + tam_bloque)
                diff = x[inicio:fin, None, :] != y[None, :, :]
                salida[inicio:fin] = np.mean(diff, axis=2)
            return salida

        @staticmethod
        def coseno(a: np.ndarray, b: np.ndarray,
                   epsilon: float = 1e-8) -> np.ndarray:
            x = np.asarray(a, dtype=np.float64)
            y = np.asarray(b, dtype=np.float64)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            if y.ndim == 1:
                y = y.reshape(1, -1)
            norm_x = np.maximum(
                np.sqrt(np.einsum('ij,ij->i', x, x)), epsilon
            )
            norm_y = np.maximum(
                np.sqrt(np.einsum('ij,ij->i', y, y)), epsilon
            )
            similitud = (x @ y.T) / (norm_x[:, None] * norm_y[None, :])
            return np.clip(1.0 - similitud, 0.0, 2.0)

        # -- calculo de la matriz de distancias -----------------------
        def distancias(self, X: np.ndarray) -> np.ndarray:
            data = self._comprobar()
            consultas = np.asarray(X, dtype=np.float64)
            if consultas.ndim == 1:
                consultas = consultas.reshape(1, -1)
            if consultas.shape[1] != data.shape[1]:
                raise ValueError(
                    f"Dimensionalidad incompatible: {consultas.shape[1]} != "
                    f"{data.shape[1]}"
                )
            if self.metrica == "euclidean":
                x2 = np.einsum('ij,ij->i', consultas, consultas)[:, None]
                distancia2 = (
                    x2 + self._norm2[None, :]
                    - 2.0 * (consultas @ data.T)
                )
                return np.sqrt(np.maximum(distancia2, 0.0))
            if self.metrica == "cosine":
                normas = np.maximum(
                    np.sqrt(np.einsum('ij,ij->i', consultas, consultas)),
                    self.epsilon,
                )
                unitarias = consultas / normas[:, None]
                similitud = unitarias @ self._unit.T
                return np.clip(1.0 - similitud, 0.0, 2.0)
            if self.metrica == "manhattan":
                return self.manhattan(
                    consultas, data, self.bloque_max
                )
            if self.metrica == "minkowski":
                return self.minkowski(
                    consultas, data, self.p, self.bloque_max
                )
            if self.metrica == "chebyshev":
                return self.chebyshev(
                    consultas, data, self.bloque_max
                )
            return self.hamming(consultas, data, self.bloque_max)

        def vecinos(self, X: np.ndarray, k: int
                    ) -> Tuple[np.ndarray, np.ndarray]:
            """Devuelve distancias e indices de los k vecinos ordenados."""
            data = self._comprobar()
            consultas = np.asarray(X, dtype=np.float64)
            if consultas.ndim == 1:
                consultas = consultas.reshape(1, -1)
            n_referencia = data.shape[0]
            k_efectivo = max(1, min(int(k), n_referencia))
            n_consultas = consultas.shape[0]
            tam_bloque = max(
                1, int(self.bloque_max) // max(1, n_referencia)
            )
            distancias = np.empty(
                (n_consultas, k_efectivo), dtype=np.float64
            )
            indices = np.empty(
                (n_consultas, k_efectivo), dtype=np.int64
            )
            for inicio in range(0, n_consultas, tam_bloque):
                fin = min(n_consultas, inicio + tam_bloque)
                matriz = self.distancias(consultas[inicio:fin])
                if k_efectivo >= n_referencia:
                    orden = np.argsort(matriz, axis=1, kind="stable")
                    indices_lote = orden[:, :k_efectivo]
                else:
                    indices_lote = np.argpartition(
                        matriz, k_efectivo - 1, axis=1
                    )[:, :k_efectivo]
                distancias_lote = np.take_along_axis(
                    matriz, indices_lote, axis=1
                )
                orden = np.argsort(distancias_lote, axis=1, kind="stable")
                indices_lote = np.take_along_axis(
                    indices_lote, orden, axis=1
                )
                distancias[inicio:fin] = np.take_along_axis(
                    distancias_lote, orden, axis=1
                )
                indices[inicio:fin] = indices_lote
            return distancias, indices

        def pesos(self, distancias: np.ndarray,
                  modo: Any = "uniform") -> np.ndarray:
            """Pesos de voto a partir de las distancias."""
            if callable(modo):
                pesos = np.asarray(modo(distancias), dtype=np.float64)
            elif str(modo).strip().lower() in (
                "uniform", "uniforme", "none", "ninguno"
            ):
                pesos = np.ones_like(distancias, dtype=np.float64)
            elif str(modo).strip().lower() in (
                "distance", "distancia", "inverse", "inverso"
            ):
                pesos = 1.0 / (distancias + self.epsilon)
            else:
                raise ValueError(
                    "weights debe ser uniform, distance o callable"
                )
            if pesos.shape != distancias.shape:
                raise ValueError("Los pesos deben tener la forma de distancias")
            return pesos

        def resumen(self) -> Dict[str, Any]:
            return {
                'metrica': self.metrica,
                'p': self.p,
                'epsilon': self.epsilon,
                'bloque_max': self.bloque_max,
                'metricas': list(self.METRICAS),
            }

    # ------------------------------------------------------------------
    # Clase anidada 2: votacion, regresion y metricas
    # ------------------------------------------------------------------
    class NucleoVotacion:
        """Fusiona votos, probabilidades, regresion y metricas."""

        EPS = 1e-12

        @staticmethod
        def probabilidades(labels: np.ndarray, weights: np.ndarray,
                           n_classes: int) -> np.ndarray:
            """Votos ponderados normalizados por fila."""
            etiquetas = np.asarray(labels, dtype=np.int64)
            pesos = np.asarray(weights, dtype=np.float64)
            if etiquetas.ndim != 2 or pesos.shape != etiquetas.shape:
                raise ValueError("labels y weights deben ser 2D compatibles")
            n, k = etiquetas.shape
            votos = np.zeros((n, n_classes), dtype=np.float64)
            filas = np.repeat(np.arange(n), k)
            np.add.at(votos, (filas, etiquetas.ravel()), pesos.ravel())
            totales = np.sum(votos, axis=1, keepdims=True)
            return np.divide(
                votos, totales,
                out=np.zeros_like(votos),
                where=totales > 0,
            )

        @staticmethod
        def regresion(targets: np.ndarray, weights: np.ndarray) -> np.ndarray:
            """Media ponderada de los vecinos (mono/multi-salida)."""
            valores = np.asarray(targets, dtype=np.float64)
            pesos = np.asarray(weights, dtype=np.float64)
            if valores.ndim == 2:
                total = np.sum(pesos, axis=1)
                return np.divide(
                    np.sum(pesos * valores, axis=1), total,
                    out=np.zeros(valores.shape[0], dtype=np.float64),
                    where=total > 0,
                )
            if valores.ndim == 3:
                total = np.sum(pesos, axis=1)[:, None]
                return np.divide(
                    np.sum(pesos[:, :, None] * valores, axis=1), total,
                    out=np.zeros((valores.shape[0], valores.shape[2])),
                    where=total > 0,
                )
            raise ValueError("targets debe ser 2D o 3D")

        @staticmethod
        def margen(probabilidades: np.ndarray) -> np.ndarray:
            proba = np.asarray(probabilidades, dtype=np.float64)
            if proba.ndim != 2:
                raise ValueError("probabilidades debe ser 2D")
            if proba.shape[1] < 2:
                return np.ones(proba.shape[0], dtype=np.float64)
            ordenadas = np.sort(proba, axis=1)
            return ordenadas[:, -1] - ordenadas[:, -2]

        @staticmethod
        def _codificar(valores: np.ndarray,
                       clases: np.ndarray) -> np.ndarray:
            mapa = {clase: indice for indice, clase in enumerate(clases)}
            return np.array([
                mapa.get(valor, -1) for valor in np.asarray(valores).ravel()
            ], dtype=int)

        @classmethod
        def metricas_clasificacion(
            cls, pred: np.ndarray, real: np.ndarray,
            proba: Optional[np.ndarray], clases: np.ndarray,
        ) -> Dict[str, Any]:
            y_true = cls._codificar(real, clases)
            y_pred = cls._codificar(pred, clases)
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
                f1 = (2.0 * precision * recall
                      / max(cls.EPS, precision + recall))
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
                if probabilidades.ndim == 2 \
                        and probabilidades.shape[0] == len(y_true):
                    indices = np.clip(y_true, 0, probabilidades.shape[1] - 1)
                    elegidas = np.clip(
                        probabilidades[np.arange(len(y_true)), indices],
                        cls.EPS, 1.0,
                    )
                    metricas['log_loss'] = float(
                        -np.mean(np.log(elegidas))
                    )
                    objetivo = np.zeros_like(probabilidades)
                    validos_proba = (y_true >= 0) & (
                        y_true < probabilidades.shape[1]
                    )
                    objetivo[np.arange(len(y_true))[validos_proba],
                            y_true[validos_proba]] = 1.0
                    metricas['brier_score'] = float(np.mean(
                        np.sum((probabilidades - objetivo) ** 2, axis=1)
                    ))
            return metricas

        @staticmethod
        def metricas_regresion(pred: np.ndarray,
                               real: np.ndarray) -> Dict[str, Any]:
            prediccion = np.asarray(pred, dtype=np.float64)
            objetivo = np.asarray(real, dtype=np.float64)
            if prediccion.shape != objetivo.shape:
                objetivo = objetivo.reshape(prediccion.shape)
            error = prediccion - objetivo
            mse = float(np.mean(error ** 2))
            varianza = float(np.sum((objetivo - np.mean(objetivo)) ** 2))
            if varianza > 1e-12:
                r2 = float(1.0 - np.sum(error ** 2) / varianza)
            elif mse <= 1e-12:
                r2 = 1.0
            else:
                r2 = 0.0
            return {
                'mse': mse,
                'rmse': float(math.sqrt(max(0.0, mse))),
                'mae': float(np.mean(np.abs(error))),
                'max_error': float(np.max(np.abs(error))),
                'r2': r2,
                'n_samples': int(objetivo.shape[0]),
            }

        def resumen(self) -> Dict[str, Any]:
            return {
                'metricas_clasificacion': [
                    'accuracy', 'balanced_accuracy', 'precision_macro',
                    'recall_macro', 'f1_macro', 'log_loss', 'brier_score',
                ],
                'metricas_regresion': [
                    'mse', 'rmse', 'mae', 'max_error', 'r2',
                ],
            }

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuronaKNN",
        *,
        k: int = 5,
        metrica: str = "euclidean",
        weights: Any = "uniform",
        tarea: str = "auto",
        normalize: bool = False,
        p: float = 3.0,
        epsilon: float = 1e-8,
        bloque_max: int = 2_000_000,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        if "distance_metric" in kwargs and metrica == "euclidean":
            metrica = kwargs.pop("distance_metric")
        if "k_vecinos" in kwargs and k == 5:
            k = kwargs.pop("k_vecinos")
        if "pesos" in kwargs and weights == "uniform":
            weights = kwargs.pop("pesos")
        if "normalizar" in kwargs and not normalize:
            normalize = kwargs.pop("normalizar")
        if "minkowski_p" in kwargs and p == 3.0:
            p = kwargs.pop("minkowski_p")
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

        self._k = int(k)
        if self._k < 1:
            raise ValueError("k debe ser al menos 1")
        self._distance_metric = normalizar_metrica(metrica)
        self._weights = weights
        self._tarea_config = self._normalizar_tarea(tarea)
        self._normalize = bool(normalize)
        self._p = float(p)
        if self._p <= 0.0:
            raise ValueError("p debe ser positivo")
        self._epsilon = max(1e-15, float(epsilon))
        self._bloque_max = max(1, int(bloque_max))
        self._seed = int(
            LUCIA_KNN_CONFIG["random_seed"] if seed is None else seed
        )
        self._rng = np.random.default_rng(self._seed)

        self._tarea = ("clasificacion"
                       if self._tarea_config == "auto" else self._tarea_config)
        self._nucleo_distancias = self.NucleoDistancias(
            metrica=self._distance_metric,
            p=self._p,
            epsilon=self._epsilon,
            bloque_max=self._bloque_max,
        )
        self._nucleo_votacion = self.NucleoVotacion()

        self._data: Optional[np.ndarray] = None
        self._data_efectiva: Optional[np.ndarray] = None
        self._labels: Optional[np.ndarray] = None
        self._labels_codificados: Optional[np.ndarray] = None
        self._targets: Optional[np.ndarray] = None
        self._classes: Optional[np.ndarray] = None
        self._n_classes: int = 0
        self._media: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None
        self._is_fitted: bool = False
        self._n_samples: int = 0
        self._n_features: int = self.input_size
        self._convergence_history: List[float] = []
        self._training_time: float = 0.0
        self._accuracy: float = 0.0
        self._learning_rate: float = 0.01

        self.inicializar_pesos()

    @staticmethod
    def _normalizar_tarea(tarea: Optional[str]) -> str:
        clave = str(tarea or "auto").strip().lower()
        alias = {
            "auto": "auto", "automatico": "auto",
            "clasificacion": "clasificacion", "classification": "clasificacion",
            "clf": "clasificacion",
            "regresion": "regresion", "regression": "regresion",
            "reg": "regresion",
        }
        clave = alias.get(clave, clave)
        if clave not in ("auto", "clasificacion", "regresion"):
            raise ValueError(
                f"Tarea desconocida: {tarea!r}. Usa auto, clasificacion "
                "o regresion"
            )
        return clave

    def inicializar_pesos(self) -> None:
        """KNN no usa pesos lineales; se mantiene la API de la base."""
        self.pesos = None
        self.sesgo = None

    # ------------------------------------------------------------------
    # Validacion y tarea
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

    @staticmethod
    def _inferir_tarea(y: Any) -> str:
        arreglo = np.asarray(y)
        if arreglo.dtype.kind in "biuUSO":
            return "clasificacion"
        if arreglo.dtype.kind == "f":
            valores = arreglo.ravel()
            unicos = np.unique(valores)
            entero = bool(np.allclose(valores, np.round(valores)))
            limite = max(2, min(20, max(1, valores.size // 3)))
            return ("clasificacion"
                    if entero and unicos.size <= limite
                    else "regresion")
        return "clasificacion"

    def _preparar_objetivo(self, y: Any, n_muestras: int
                           ) -> Tuple[np.ndarray, np.ndarray,
                                      Optional[np.ndarray]]:
        arreglo = np.asarray(y)
        if arreglo.ndim == 2 and arreglo.shape[1] == 1:
            arreglo = arreglo.reshape(-1)
        if arreglo.ndim == 0:
            arreglo = arreglo.reshape(1)
        if arreglo.shape[0] != n_muestras:
            raise ValueError(
                "X e y deben tener el mismo numero de muestras: "
                f"{n_muestras} != {arreglo.shape[0]}"
            )
        if arreglo.size == 0:
            raise ValueError("y no contiene muestras")

        if self._tarea == "clasificacion":
            if arreglo.ndim == 2:
                if arreglo.shape[1] >= 2 and np.allclose(
                    np.sum(arreglo.astype(np.float64), axis=1), 1.0
                ) and np.all(arreglo >= 0) and np.all(arreglo <= 1):
                    arreglo = np.argmax(arreglo, axis=1)
                else:
                    raise ValueError(
                        "Para clasificacion, y debe ser 1D, (n, 1) o one-hot"
                    )
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
            return codificado.astype(int), arreglo, clases

        try:
            valores = np.asarray(y, dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Para regresion, y debe ser numerico"
            ) from error
        if valores.ndim == 2 and valores.shape[1] == 1:
            valores = valores.reshape(-1)
        if valores.ndim not in (1, 2):
            raise ValueError("Para regresion, y debe ser 1D o 2D")
        if not np.all(np.isfinite(valores)):
            raise ValueError("y contiene valores no finitos")
        return valores, valores, None

    def _sincronizar_legado(self) -> None:
        """Sincroniza atributos fijados manualmente por consumidores antiguos."""
        if self._data is None:
            return
        if self._data_efectiva is None:
            if self._normalize and self._media is not None \
                    and self._std is not None:
                self._data_efectiva = (
                    self._data - self._media
                ) / self._std
            else:
                self._data_efectiva = np.asarray(
                    self._data, dtype=np.float64
                ).copy()
        if self._tarea == "clasificacion" and self._labels is not None:
            if self._classes is None:
                self._classes = np.unique(self._labels)
            self._n_classes = int(len(self._classes))
            if self._labels_codificados is None:
                mapa = {clase: indice
                        for indice, clase in enumerate(self._classes)}
                self._labels_codificados = np.array([
                    mapa.get(valor, -1) for valor in self._labels
                ], dtype=np.int64)
        if (self._nucleo_distancias._data is None
                or self._nucleo_distancias._data.shape
                != self._data_efectiva.shape):
            self._nucleo_distancias.ajustar(self._data_efectiva)

    def _transformar_X(self, X: Any, permitir_1d: bool = True
                       ) -> Tuple[np.ndarray, bool]:
        self._sincronizar_legado()
        matriz, unico = self._validar_entrada(X, permitir_1d)
        if self._normalize and self._media is not None \
                and self._std is not None:
            matriz = (matriz - self._media) / self._std
        return matriz, unico

    # ------------------------------------------------------------------
    # Ajuste
    # ------------------------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 1,
            verbose: bool = False) -> List[float]:
        """Almacena los datos y prepara la busqueda de vecinos."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        self._tarea = (self._inferir_tarea(y)
                       if self._tarea_config == "auto"
                       else self._tarea_config)
        codificado, original, clases = self._preparar_objetivo(
            y, matriz.shape[0]
        )
        inicio = time.perf_counter()
        self._n_features = matriz.shape[1]
        self._data = np.array(matriz, dtype=np.float64, copy=True)
        if self._normalize:
            self._media = np.mean(self._data, axis=0)
            self._std = np.std(self._data, axis=0) + self._epsilon
            self._data_efectiva = (
                self._data - self._media
            ) / self._std
        else:
            self._media = None
            self._std = None
            self._data_efectiva = self._data.copy()
        self._classes = None if clases is None else np.asarray(clases)
        self._n_classes = (
            int(len(self._classes)) if self._classes is not None else 0
        )
        self._labels = np.array(original, copy=True)
        self._labels_codificados = (
            np.asarray(codificado, dtype=np.int64).copy()
            if self._tarea == "clasificacion" else None
        )
        self._targets = (
            None if self._tarea == "clasificacion"
            else np.array(original, dtype=np.float64, copy=True)
        )
        self._n_samples = int(matriz.shape[0])
        self._nucleo_distancias = self.NucleoDistancias(
            metrica=self._distance_metric,
            p=self._p,
            epsilon=self._epsilon,
            bloque_max=self._bloque_max,
        )
        self._nucleo_distancias.ajustar(self._data_efectiva)
        self._is_fitted = True
        self._accuracy = self.compute_accuracy(matriz, original)
        self._training_time = time.perf_counter() - inicio

        self._convergence_history = []
        perdidas: List[float] = []
        for epoca in range(max(1, int(epochs))):
            prediccion = self.predict(matriz)
            perdida = self.compute_loss(prediccion, original)
            perdidas.append(float(perdida))
            self._convergence_history.append(float(perdida))
            if verbose and (epoca + 1) % 5 == 0:
                logger.info(
                    "KNN Epoch %d, loss=%.6f", epoca + 1, perdida
                )
        if hasattr(self, "registrar_perdida") and perdidas:
            self.registrar_perdida(perdidas[-1])
        return perdidas

    # ------------------------------------------------------------------
    # Vecinos y prediccion
    # ------------------------------------------------------------------
    def _vecinos_con_pesos(self, X: np.ndarray
                           ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        matriz, _ = self._transformar_X(X, permitir_1d=False)
        k_efectivo = max(1, min(self._k, self._n_samples))
        distancias, indices = self._nucleo_distancias.vecinos(
            matriz, k_efectivo
        )
        pesos = self._nucleo_distancias.pesos(
            distancias, self._weights
        )
        return distancias, indices, pesos

    @_requiere_ajuste
    def kneighbors(self, X: np.ndarray, n_neighbors: Optional[int] = None,
                   return_distance: bool = True) -> Any:
        """Devuelve distancias e indices de los vecinos mas cercanos."""
        k = self._k if n_neighbors is None else int(n_neighbors)
        if k < 1:
            raise ValueError("n_neighbors debe ser al menos 1")
        matriz, unico = self._transformar_X(X)
        distancias, indices = self._nucleo_distancias.vecinos(
            matriz, min(k, self._n_samples)
        )
        if unico:
            distancias = distancias[0]
            indices = indices[0]
            if return_distance:
                return distancias, indices
            return indices
        if return_distance:
            return distancias, indices
        return indices

    @_requiere_ajuste
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilidades por clase (solo clasificacion)."""
        if self._tarea != "clasificacion":
            raise ValueError(
                "predict_proba solo esta disponible en clasificacion"
            )
        matriz, unico = self._transformar_X(X)
        k_efectivo = max(1, min(self._k, self._n_samples))
        distancias, indices = self._nucleo_distancias.vecinos(
            matriz, k_efectivo
        )
        pesos = self._nucleo_distancias.pesos(
            distancias, self._weights
        )
        etiquetas = self._labels_codificados[indices]
        probabilidades = self._nucleo_votacion.probabilidades(
            etiquetas, pesos, self._n_classes
        )
        return probabilidades[0] if unico else probabilidades

    @_requiere_ajuste
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Etiquetas (clasificacion) o valores (regresion)."""
        matriz, unico = self._transformar_X(X)
        k_efectivo = max(1, min(self._k, self._n_samples))
        distancias, indices = self._nucleo_distancias.vecinos(
            matriz, k_efectivo
        )
        pesos = self._nucleo_distancias.pesos(
            distancias, self._weights
        )
        if self._tarea == "clasificacion":
            etiquetas = self._labels_codificados[indices]
            probabilidades = self._nucleo_votacion.probabilidades(
                etiquetas, pesos, self._n_classes
            )
            prediccion = np.asarray(self._classes)[
                np.argmax(probabilidades, axis=1)
            ]
            return prediccion[0] if unico else prediccion

        targets = self._targets[indices]
        prediccion = self._nucleo_votacion.regresion(targets, pesos)
        if unico:
            return prediccion[0]
        return prediccion

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Salida de la neurona: probabilidades o prediccion."""
        matriz, unico = self._validar_entrada(entrada)
        if self._tarea == "clasificacion":
            salida = self.predict_proba(matriz)
        else:
            salida = self.predict(matriz)
        self.historial_activaciones.append(np.array(salida, copy=True))
        self.pasos += 1
        return salida[0] if unico else salida

    # ------------------------------------------------------------------
    # Distancias historicas
    # ------------------------------------------------------------------
    def _euclidean(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return self.NucleoDistancias.euclidiana(a, b)

    def _manhattan(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return self.NucleoDistancias.manhattan(
            a, b, self._bloque_max
        )

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return self.NucleoDistancias.coseno(a, b, self._epsilon)

    def _compute_distances(self, X: np.ndarray) -> np.ndarray:
        matriz, _ = self._transformar_X(X, permitir_1d=False)
        return self._nucleo_distancias.distancias(matriz)

    # ------------------------------------------------------------------
    # Perdida y metricas
    # ------------------------------------------------------------------
    def _codificar_objetivo(self, objetivo: Any, n: int) -> np.ndarray:
        arreglo = np.asarray(objetivo)
        if arreglo.ndim == 2:
            if arreglo.shape[1] >= 2 and np.allclose(
                np.sum(arreglo.astype(np.float64), axis=1), 1.0
            ):
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

    def compute_loss(self, prediccion: np.ndarray,
                     objetivo: np.ndarray) -> float:
        """Error de clasificacion o MSE de regresion."""
        if self._tarea == "clasificacion":
            pred = np.asarray(prediccion)
            if pred.ndim == 2 and self._classes is not None \
                    and pred.shape[1] == len(self._classes):
                codificado = self._codificar_objetivo(
                    objetivo, pred.shape[0]
                )
                elegidas = np.clip(
                    pred[np.arange(pred.shape[0]), codificado],
                    1e-12, 1.0,
                )
                return float(-np.mean(np.log(elegidas)))
            real = np.asarray(objetivo).ravel()
            return float(np.mean(
                np.asarray(prediccion).ravel() != real
            ))
        real = np.asarray(objetivo, dtype=np.float64)
        pred = np.asarray(prediccion, dtype=np.float64)
        if pred.shape != real.shape:
            real = real.reshape(pred.shape)
        return float(np.mean((pred - real) ** 2))

    @_requiere_ajuste
    def compute_accuracy(self, X: np.ndarray, y: np.ndarray) -> float:
        """Accuracy en clasificacion; R2 en regresion."""
        if self._tarea == "clasificacion":
            _, original, _ = self._preparar_objetivo(y, len(np.asarray(X)))
            prediccion = self.predict(X)
            return float(np.mean(
                np.asarray(prediccion).ravel()
                == np.asarray(original).ravel()
            ))
        metricas = self.evaluate(X, y)
        return float(metricas.get('r2', 0.0))

    @_requiere_ajuste
    def compute_margin(self, X: np.ndarray) -> float:
        """Margen medio entre la clase mas probable y la segunda."""
        if self._tarea != "clasificacion":
            return 0.0
        probabilidades = self.predict_proba(X)
        return float(np.mean(
            self._nucleo_votacion.margen(probabilidades)
        ))

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """Accuracy o R2."""
        return self.compute_accuracy(X, y)

    @_requiere_ajuste
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Metricas completas de clasificacion o regresion."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        _, original, _ = self._preparar_objetivo(y, matriz.shape[0])
        if self._tarea == "clasificacion":
            probabilidades = self.predict_proba(matriz)
            prediccion = np.asarray(self._classes)[
                np.argmax(probabilidades, axis=1)
            ]
            metricas = self._nucleo_votacion.metricas_clasificacion(
                prediccion, original, probabilidades, self._classes
            )
            metricas['margin'] = float(np.mean(
                self._nucleo_votacion.margen(probabilidades)
            ))
            metricas['loss'] = self.compute_loss(
                probabilidades, original
            )
            return metricas
        prediccion = self.predict(matriz)
        metricas = self._nucleo_votacion.metricas_regresion(
            prediccion, original
        )
        metricas['loss'] = self.compute_loss(prediccion, original)
        return metricas

    # ------------------------------------------------------------------
    # Informacion y estabilidad
    # ------------------------------------------------------------------
    def _arreglos_parametros(self) -> List[np.ndarray]:
        arreglos: List[np.ndarray] = []
        if self._data_efectiva is not None:
            arreglos.append(np.asarray(self._data_efectiva))
        if self._targets is not None:
            arreglos.append(np.asarray(self._targets, dtype=np.float64))
        elif self._labels_codificados is not None:
            arreglos.append(np.asarray(
                self._labels_codificados, dtype=np.float64
            ))
        return arreglos

    def params_count(self) -> int:
        """Parametros efectivos: vectores de entrenamiento almacenados."""
        if self._data_efectiva is None:
            return 0
        total = int(self._data_efectiva.size)
        if self._targets is not None:
            total += int(self._targets.size)
        elif self._labels_codificados is not None:
            total += int(self._labels_codificados.size)
        return total

    @property
    def classes_(self) -> Optional[np.ndarray]:
        """Etiquetas de clase (solo clasificacion)."""
        return None if self._classes is None else self._classes.copy()

    @property
    def n_features_in_(self) -> int:
        return int(self._n_features)

    @property
    def data_(self) -> Optional[np.ndarray]:
        """Datos de referencia almacenados (sin normalizar)."""
        return None if self._data is None else self._data.copy()

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'knn',
            'tarea': self._tarea,
            'k': self._k,
            'distance_metric': self._distance_metric,
            'weights': (self._weights
                        if isinstance(self._weights, str) else 'callable'),
            'normalize': self._normalize,
            'p': self._p,
            'is_fitted': self._is_fitted,
            'n_samples': self._n_samples,
            'n_features': self._n_features,
            'n_classes': self._n_classes,
            'accuracy': self._accuracy,
            'n_parametros': self.params_count(),
            'training_time': self._training_time,
            'nucleo_distancias': self._nucleo_distancias.resumen(),
            'nucleo_votacion': self._nucleo_votacion.resumen(),
        })
        if self._classes is not None:
            stats['classes'] = self._classes.tolist()
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
            stats['initial_loss'] = float(self._convergence_history[0])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprobaciones de coherencia de los datos almacenados."""
        ok: Dict[str, bool] = {
            'estado_entrenado': bool(self._is_fitted),
            'datos_cargados': self._data is not None,
        }
        if self._data is not None:
            ok['datos_finitos'] = bool(np.all(np.isfinite(self._data)))
            ok['k_valido'] = bool(
                1 <= self._k <= max(1, self._n_samples)
            )
            ok['etiquetas_coherentes'] = bool(
                self._labels is not None
                and len(self._labels) == self._n_samples
            )
            ok['distancias_finitas'] = bool(
                self._data_efectiva is not None
                and np.all(np.isfinite(self._data_efectiva))
            )
        if self._tarea == "clasificacion":
            ok['clases_validas'] = bool(
                self._classes is not None and len(self._classes) >= 1
            )
            ok['codificacion_valida'] = bool(
                self._labels_codificados is not None
                and np.all(self._labels_codificados >= 0)
                and np.all(self._labels_codificados < self._n_classes)
            )
        if self.pesos is not None:
            ok['pesos_no_nan'] = not bool(np.any(np.isnan(self.pesos)))
            ok['pesos_no_inf'] = not bool(np.any(np.isinf(self.pesos)))
        ok['estable'] = all(ok.values())
        return ok

    # ------------------------------------------------------------------
    # Serializacion y configuracion
    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        """Guarda datos, etiquetas, parametros y configuracion."""
        estado = {
            'version': __version__,
            'tipo': 'NeuronaKNN',
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'tarea': self._tarea,
            'tarea_config': self._tarea_config,
            'k': self._k,
            'distance_metric': self._distance_metric,
            'weights': self._weights,
            'normalize': self._normalize,
            'p': self._p,
            'epsilon': self._epsilon,
            'bloque_max': self._bloque_max,
            'is_fitted': self._is_fitted,
            'pasos': self.pasos,
            'data': self._data,
            'data_efectiva': self._data_efectiva,
            'labels': self._labels,
            'labels_codificados': self._labels_codificados,
            'targets': self._targets,
            'classes': self._classes,
            'n_classes': self._n_classes,
            'media': self._media,
            'std': self._std,
            'n_samples': self._n_samples,
            'n_features': self._n_features,
            'accuracy': self._accuracy,
            'convergence_history': list(self._convergence_history),
            'training_time': self._training_time,
            'pesos': self.pesos,
            'sesgo': self.sesgo,
            'learning_rate': self._learning_rate,
            'seed': self._seed,
        }
        with open(filepath, 'wb') as archivo:
            pickle.dump(estado, archivo, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        """Carga checkpoints nuevos o el formato historico de RF_SL1_7."""
        with open(filepath, 'rb') as archivo:
            estado = pickle.load(archivo)
        if not isinstance(estado, dict):
            raise TypeError("El fichero no contiene un checkpoint valido")

        self.nombre = str(estado.get('nombre', self.nombre))
        self.input_size = int(estado.get('input_size', self.input_size))
        self.output_size = int(estado.get('output_size', self.output_size))
        self._k = max(1, int(estado.get('k', self._k)))
        self._distance_metric = normalizar_metrica(
            estado.get('distance_metric',
                       estado.get('metrica', self._distance_metric))
        )
        self._weights = estado.get('weights', self._weights)
        self._normalize = bool(estado.get('normalize', False))
        self._p = float(estado.get('p', self._p))
        self._epsilon = max(1e-15, float(estado.get('epsilon', 1e-8)))
        self._bloque_max = max(1, int(estado.get('bloque_max', 2_000_000)))
        self._learning_rate = float(estado.get('learning_rate', 0.01))
        self._seed = int(estado.get('seed', LUCIA_KNN_CONFIG["random_seed"]))
        self._rng = np.random.default_rng(self._seed)

        data = estado.get('data')
        if data is None:
            data = estado.get('data_efectiva')
        if data is None:
            raise ValueError("El checkpoint no contiene datos")
        self._data = np.asarray(data, dtype=np.float64)
        self._n_samples = int(estado.get('n_samples', len(self._data)))
        self._n_features = int(estado.get('n_features', self._data.shape[1]))
        self._media = estado.get('media')
        self._std = estado.get('std')
        self._data_efectiva = estado.get('data_efectiva')
        if self._data_efectiva is None:
            if self._normalize and self._media is not None \
                    and self._std is not None:
                self._data_efectiva = (
                    self._data - self._media
                ) / self._std
            else:
                self._data_efectiva = self._data.copy()
        else:
            self._data_efectiva = np.asarray(
                self._data_efectiva, dtype=np.float64
            )

        etiquetas = estado.get('labels')
        self._labels = None if etiquetas is None else np.asarray(etiquetas)
        clases = estado.get('classes')
        tarea = estado.get('tarea')
        if tarea is None:
            tarea = ('clasificacion'
                     if etiquetas is not None
                     and np.asarray(etiquetas).dtype.kind in "biuUSO"
                     else 'clasificacion')
        self._tarea = self._normalizar_tarea(tarea)
        self._tarea_config = estado.get('tarea_config', self._tarea)

        if self._tarea == "clasificacion":
            if clases is None and self._labels is not None:
                clases = np.unique(self._labels)
            self._classes = (None if clases is None
                             else np.asarray(clases))
            self._n_classes = (
                int(estado.get('n_classes', 0))
                or (len(self._classes) if self._classes is not None else 0)
            )
            codificados = estado.get('labels_codificados')
            if codificados is None and self._labels is not None:
                mapa = {clase: indice
                        for indice, clase in enumerate(self._classes)}
                codificados = np.array([
                    mapa.get(valor, -1) for valor in self._labels
                ], dtype=int)
            self._labels_codificados = (
                None if codificados is None
                else np.asarray(codificados, dtype=np.int64)
            )
            self._targets = None
        else:
            objetivos = estado.get('targets')
            if objetivos is None:
                objetivos = etiquetas
            self._targets = np.asarray(objetivos, dtype=np.float64)
            self._classes = None
            self._n_classes = 0
            self._labels_codificados = None
            self._labels = np.array(self._targets, copy=True)

        self._nucleo_distancias = self.NucleoDistancias(
            metrica=self._distance_metric,
            p=self._p,
            epsilon=self._epsilon,
            bloque_max=self._bloque_max,
        )
        self._nucleo_distancias.ajustar(self._data_efectiva)
        self._nucleo_votacion = self.NucleoVotacion()
        self._is_fitted = bool(estado.get('is_fitted', True))
        self.pasos = int(estado.get('pasos', 0))
        self._accuracy = float(estado.get('accuracy', 0.0))
        self._convergence_history = [
            float(v) for v in estado.get('convergence_history', [])
        ]
        self._training_time = float(estado.get('training_time', 0.0))
        self.pesos = estado.get('pesos')
        self.sesgo = estado.get('sesgo')

    def get_config(self) -> Dict[str, Any]:
        """Configuracion reproducible del modelo."""
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'tarea': self._tarea,
            'k': self._k,
            'distance_metric': self._distance_metric,
            'weights': (self._weights
                        if isinstance(self._weights, str) else 'callable'),
            'normalize': self._normalize,
            'p': self._p,
            'epsilon': self._epsilon,
            'bloque_max': self._bloque_max,
            'seed': self._seed,
        }

    def summary(self) -> str:
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {self.nombre} ===",
            (f"K: {self._k}, Metrica: {self._distance_metric}, "
             f"Pesos: {stats.get('weights')}"),
            (f"Tarea: {self._tarea}, Normalize: {self._normalize}, "
             f"Input: {self.input_size}"),
            (f"Fitted: {stats.get('is_fitted', False)}, "
             f"Acc/R2: {stats.get('accuracy', 0.0):.4f}, "
             f"Samples: {stats.get('n_samples', 0)}"),
            (f"Params: {self.params_count()}, "
             f"Final loss: {stats.get('final_loss', 'N/A')}"),
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"


# ---------------------------------------------------------------------------
# Utilidades historicas de distancia y normalizacion
# ---------------------------------------------------------------------------
class DistanceMetric:
    @staticmethod
    def euclidean(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        x = np.asarray(a, dtype=np.float64)
        y = np.asarray(b, dtype=np.float64)
        if x.ndim == 1 and y.ndim == 2:
            return np.sqrt(np.sum((y - x) ** 2, axis=1))
        return NeuronaKNN.NucleoDistancias.euclidiana(x, y)

    @staticmethod
    def manhattan(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        x = np.asarray(a, dtype=np.float64)
        y = np.asarray(b, dtype=np.float64)
        if x.ndim == 1 and y.ndim == 2:
            return np.sum(np.abs(y - x), axis=1)
        return NeuronaKNN.NucleoDistancias.manhattan(x, y)

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        x = np.asarray(a, dtype=np.float64)
        y = np.asarray(b, dtype=np.float64)
        if x.ndim == 1 and y.ndim == 2:
            x = x.reshape(1, -1)
        return NeuronaKNN.NucleoDistancias.coseno(x, y)[0] \
            if x.shape[0] == 1 else NeuronaKNN.NucleoDistancias.coseno(x, y)

    @staticmethod
    def minkowski(a: np.ndarray, b: np.ndarray,
                  p: int = 3) -> np.ndarray:
        return NeuronaKNN.NucleoDistancias.minkowski(a, b, p)

    @staticmethod
    def get_metric(name: str) -> str:
        return normalizar_metrica(name)


class FeatureNormalizer:
    def __init__(self) -> None:
        self._mean: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> "FeatureNormalizer":
        datos = np.asarray(X, dtype=np.float64)
        self._mean = np.mean(datos, axis=0)
        self._std = np.std(datos, axis=0) + 1e-8
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self._mean is None or self._std is None:
            raise RuntimeError("Normalizer no ajustado")
        return (np.asarray(X, dtype=np.float64) - self._mean) / self._std

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)


class VoteAggregator:
    def __init__(self, weighted: bool = False):
        self.weighted = weighted

    def aggregate(self, labels: np.ndarray,
                  distances: Optional[np.ndarray] = None) -> int:
        etiquetas = np.asarray(labels)
        if distances is not None and self.weighted:
            pesos = 1.0 / (np.asarray(distances) + 1e-8)
            uniques, inverse = np.unique(etiquetas, return_inverse=True)
            conteos = np.bincount(
                inverse, weights=pesos, minlength=len(uniques)
            )
            return int(uniques[np.argmax(conteos)])
        uniques, conteos = np.unique(etiquetas, return_counts=True)
        return int(uniques[np.argmax(conteos)])

    def aggregate_proba(self, labels: np.ndarray,
                        n_classes: int) -> np.ndarray:
        conteos = np.bincount(
            np.asarray(labels, dtype=int), minlength=n_classes
        )
        total = max(1, len(labels))
        return conteos / total


class KNNSearcher:
    def __init__(self, k: int = 5, metric: str = "euclidean"):
        self.k = max(1, int(k))
        self.metric = normalizar_metrica(metric)

    def find_neighbors(self, query: np.ndarray,
                       data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        nucleo = NeuronaKNN.NucleoDistancias(self.metric).ajustar(data)
        distancias, indices = nucleo.vecinos(
            np.asarray(query, dtype=np.float64).reshape(1, -1),
            min(self.k, len(data)),
        )
        return indices[0], distancias[0]

    def find_neighbors_batch(
        self, queries: np.ndarray, data: np.ndarray,
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        nucleo = NeuronaKNN.NucleoDistancias(self.metric).ajustar(data)
        distancias, indices = nucleo.vecinos(
            np.asarray(queries, dtype=np.float64),
            min(self.k, len(data)),
        )
        return [(indices[i], distancias[i])
                for i in range(indices.shape[0])]


class RadiusNeighborSearcher:
    def __init__(self, radius: float = 1.0):
        self.radius = float(radius)

    def find(self, query: np.ndarray,
             data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        distancias = DistanceMetric.euclidean(
            np.asarray(query, dtype=np.float64), data
        )
        indices = np.where(distancias <= self.radius)[0]
        return indices, distancias[indices]

    def find_batch(self, queries: np.ndarray,
                   data: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
        return [self.find(q, data) for q in np.asarray(queries)]


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


# ---------------------------------------------------------------------------
# Adaptador de compatibilidad con la API historica de RF_SL1_7
# ---------------------------------------------------------------------------
class KNearestNeighborsOptimizer(NeuronaKNN):
    """KNN real con la API historica de ``KNearestNeighborsOptimizer``.

    Conserva la cabeza lineal legada (``forward``/``backward``/
    ``update_weights``/``apply_gradient``/``train_step``) para no romper
    consumidores antiguos. ``fit``, ``predict`` y ``predict_proba`` usan KNN.
    """

    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "KNearestNeighborsOptimizer",
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
        """Cabeza lineal historica (``predict`` usa KNN)."""
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

    def update_weights(self, grad_pesos: np.ndarray,
                       grad_sesgo: np.ndarray) -> None:
        """Descenso de gradiente de la cabeza lineal historica."""
        self.pesos -= self._learning_rate * grad_pesos
        self.sesgo -= self._learning_rate * grad_sesgo

    def apply_gradient(self, entrada: np.ndarray,
                       objetivo: np.ndarray) -> float:
        """Un paso de la cabeza lineal y perdida resultante."""
        matriz, _ = self._validar_entrada(entrada, permitir_1d=False)
        pred = self.forward(matriz)
        real = np.asarray(objetivo, dtype=np.float64)
        if real.ndim == 1:
            real = real.reshape(-1, 1)
        grad = pred - real
        grad_pesos, grad_sesgo = self.backward(grad, matriz)
        self.update_weights(grad_pesos, grad_sesgo)
        return self.compute_loss(pred, real)

    def train_step(self, entrada: np.ndarray,
                   objetivo: np.ndarray) -> Dict[str, float]:
        """Paso historico de la cabeza lineal (no modifica KNN)."""
        matriz, _ = self._validar_entrada(entrada, permitir_1d=False)
        prediccion = self.forward(matriz)
        real = np.asarray(objetivo, dtype=np.float64)
        if real.ndim == 1:
            real = real.reshape(-1, 1)
        loss_before = self.compute_loss(prediccion, real)
        loss_after = self.apply_gradient(matriz, real)
        return {
            'loss_before': float(loss_before),
            'loss_after': float(loss_after),
            'improvement': float(loss_before - loss_after),
        }

    def get_config(self) -> Dict[str, Any]:
        configuracion = super().get_config()
        configuracion['learning_rate'] = self._learning_rate
        return configuracion


# ---------------------------------------------------------------------------
# Fabrica, utilidades y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "knn", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaKNN:
    """Fabrica una neurona KNN por nombre.

    Tipos: ``knn``/``nearest_neighbors``, ``clasificacion``, ``regresion`` y
    ``compat`` (adaptador historico).
    """
    clave = str(tipo or "knn").strip().lower().replace("-", "_")
    if clave in ("knn", "k_nearest_neighbors", "nearest_neighbors",
                 "vecinos", "knn_classifier"):
        return NeuronaKNN(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("clasificacion", "classification", "clf"):
        kwargs.setdefault("tarea", "clasificacion")
        return NeuronaKNN(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("regresion", "regression", "reg"):
        kwargs.setdefault("tarea", "regresion")
        return NeuronaKNN(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("compat", "k_nearest_neighbors_optimizer", "optimizer"):
        return KNearestNeighborsOptimizer(
            input_size=input_size, output_size=output_size, **kwargs
        )
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: knn, clasificacion, regresion, "
        "compat"
    )


def tipos_disponibles() -> List[str]:
    """Nombres aceptados por :func:`crear_neurona`."""
    return ["knn", "clasificacion", "regresion", "compat"]


def create_k_nearest_neighbors_optimizer(
    input_size: int = 4, output_size: int = 8, **kwargs: Any,
) -> KNearestNeighborsOptimizer:
    """Fabrica historica de RF_SL1_7."""
    return KNearestNeighborsOptimizer(
        input_size=input_size, output_size=output_size, **kwargs
    )


def entrenar_y_evaluar(modelo: NeuronaKNN, X: np.ndarray,
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


def benchmark_modelo(modelo: NeuronaKNN, X: np.ndarray,
                     repeticiones: int = 5) -> Dict[str, float]:
    """Mide el tiempo de inferencia de KNN."""
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


def guardar_modelo(modelo: NeuronaKNN, ruta: str) -> None:
    """Serializa el objeto completo (pickle)."""
    with open(ruta, 'wb') as archivo:
        pickle.dump(modelo, archivo, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaKNN:
    """Carga un modelo serializado con :func:`guardar_modelo`."""
    with open(ruta, 'rb') as archivo:
        modelo = pickle.load(archivo)
    if not isinstance(modelo, NeuronaKNN):
        raise TypeError("El fichero no contiene una neurona KNN")
    return modelo


# ---------------------------------------------------------------------------
# Demostracion
# ---------------------------------------------------------------------------
def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_7_1.py``)."""
    generador = np.random.default_rng(2026)
    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_7_1 :: KNN (v%s)" % __version__)
    print("=" * 78)

    n = 360
    centros = np.array([[0.0, 0.0], [3.0, 0.0], [1.5, 3.0]])
    etiquetas = generador.integers(0, 3, size=n)
    X = centros[etiquetas] + generador.normal(scale=0.7, size=(n, 2))
    y = np.array(["rojo", "verde", "azul"])[etiquetas]

    for metrica in ("euclidean", "manhattan", "cosine", "chebyshev"):
        modelo = crear_neurona(
            "clasificacion", 2, 3, k=5, metrica=metrica,
            weights="distance",
        )
        modelo.fit(X, y)
        met = modelo.evaluate(X, y)
        print("%-13s accuracy=%.4f margen=%.4f | params=%d"
              % (metrica, met['accuracy'], met['margin'],
                 modelo.params_count()))

    regresor = crear_neurona("regresion", 2, 1, k=7, metrica="euclidean")
    y_reg = (np.sin(X[:, 0]) + X[:, 1] ** 2).reshape(-1, 1)
    regresor.fit(X, y_reg)
    met_reg = regresor.evaluate(X, y_reg)
    print("%-13s R2=%.4f MSE=%.4f | params=%d"
          % ("regresion", met_reg['r2'], met_reg['mse'],
             regresor.params_count()))

    print("Probabilidades (3):",
          np.round(modelo.predict_proba(X[:3]), 3).tolist())
    print("Estabilidad:", modelo.verificar_estabilidad())
    print("Benchmark:", benchmark_modelo(modelo, X, repeticiones=3))
    print("=" * 78)
    return {
        'clasificacion': met,
        'regresion': met_reg,
    }


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaKNN',
    'KNearestNeighborsOptimizer',
    'DistanceMetric',
    'FeatureNormalizer',
    'VoteAggregator',
    'KNNSearcher',
    'RadiusNeighborSearcher',
    'ConfusionMatrix',
    'crear_neurona',
    'tipos_disponibles',
    'create_k_nearest_neighbors_optimizer',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_KNN_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
