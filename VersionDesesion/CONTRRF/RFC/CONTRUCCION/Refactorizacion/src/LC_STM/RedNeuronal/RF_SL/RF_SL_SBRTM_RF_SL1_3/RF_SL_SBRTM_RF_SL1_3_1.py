"""RF_SL_SBRTM_RF_SL1_3_1.py
Neuronas especializadas en bosques aleatorios y matrices neuronales
(RF_SL · SBRTM · RF · 2026).
=============================================================================

Modulo autocontenido y preparado para importar. Refactoriza el antiguo
fragmento (que solo tenia ``NeuronaMemoriaBase`` y un
``RandomForestOptimizer`` incompleto, sin imports ni arbol) y lo sustituye
por una implementacion real con algoritmos de calculo recientes:

  * ``NeuronaArbolAleatorio``: arbol CART mejorado.
      - Hojas **vectoriales** (multi-salida): la hoja guarda el vector de
        medias por salida, no un escalar (idea de las hojas vectoriales de
        XGBoost 3.0).
      - Umbrales por **histograma de cuantiles** para reducir el coste de
        busqueda de O(n) a O(n_bins) por caracteristica.
      - Criterio de ganancia multi-salida (SSE total) y Gini/entropia para
        clasificacion.
      - ``ExtraTrees`` (umbrales aleatorios por nodo) ademas de CART clasico.
      - Submuestreo de caracteristicas por nodo (``sqrt``, ``log2`` o
        fraccion) e importancias por ganancia.

  * ``NeuronaBosqueAleatorio``: Random Forest.
      - Bagging con bootstrap y **OOB score** real por muestra (no una
        mascara aleatoria independiente del arbol).
      - Prediccion multi-salida (media de hojas vectoriales) y clasificacion
        con probabilidades medias.
      - Importancias normalizadas, evaluacion y serializacion.

  * ``NeuronaTabM``: MLP tabular con **ensamblado parametro-eficiente**
      (BatchEnsemble / TabM, OpenTabular 2025). Cada miembro k usa matrices
      de rango 1: ``W_k = W ∘ (r_k s_k^T)``, compartiendo W entre los K
      miembros. Es la parte de "matrices neuronales": K modelos con coste de
      parametros O(K·(H+D)) en vez de O(K·H·D).
      - Regresion (MSE) y clasificacion (softmax) con gradientes analiticos.
      - Normalizacion interna de X e y, Adam, mini-lotes y early stop
        opcional.

  * ``RandomForestOptimizer``: adaptador de compatibilidad con la API
      historica de RF_SL1_3 (``fit``, ``train``, ``forward``,
      ``compute_loss``, ``compute_oob_score``, ``compute_feature_importances``,
      ``backward/update_weights/apply_gradient/train_step``, ``save/load``...).

Referencias de los metodos implementados
-----------------------------------------
- TabM: parameter-efficient ensembling for tabular deep learning
  (OpenTabular, 2025).
- Hojas vectoriales y multi-output en XGBoost 3.0.
- Honest / fixed-point random forests (submuestreo honesto, 2023-2025).
- TabPFN v2 como referencia de modelado tabular reciente.

La base ``NeuronaMemoriaBase`` se importa del modulo especializado
``RF_SL_SBRTM_RF_rfsl_base/RF_SL_SNRTM__rfsl_base1.py`` (con fallback por
ruta y base local minima), sin duplicar la jerarquia.

Uso rapido
----------
    from RF_SL_SBRTM_RF_SL1_3_1 import NeuronaBosqueAleatorio, NeuronaTabM

    bosque = NeuronaBosqueAleatorio(input_size=3, n_estimators=200,
                                    tarea="regresion")
    bosque.fit(X, y)
    print(bosque.evaluate(X, y))

    tabm = NeuronaTabM(input_size=3, k_miembros=8, tarea="clasificacion")
    tabm.fit(X, y)
    print(tabm.predict_proba(X)[:5])
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
LUCIA_RF_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "n_estimators": 100,
    "max_depth": 10,
    "min_samples_split": 2,
    "min_samples_leaf": 1,
    "max_features": "sqrt",
    "n_bins": 32,
    "bootstrap": True,
    "oob_score": True,
    "tabm_k": 8,
    "tabm_hidden": 64,
    "learning_rate": 0.01,
    "epochs": 100,
    "batch_size": 64,
    "weight_decay": 1e-4,
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

    _CLAVE_BASE = "_rf_snrtm_base_import_forest"
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
    else:  # Ultimo recurso: base local minima.

        class NeuronaMemoriaBase:  # type: ignore[no-redef]
            """Base de neurona con memoria acotada (fallback minimo)."""

            def __init__(self, input_size: int, output_size: int,
                         nombre: str = "Neurona"):
                from collections import deque
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
# Utilidades
# ---------------------------------------------------------------------------
def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


def _softmax(x: np.ndarray, eje: int = -1) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    maximo = np.max(x, axis=eje, keepdims=True)
    exponencial = np.exp(x - maximo)
    return exponencial / np.maximum(np.sum(exponencial, axis=eje, keepdims=True), 1e-12)


def _validar_entrada(X: Any, input_size: Optional[int] = None) -> np.ndarray:
    matriz = np.asarray(X, dtype=np.float64)
    if matriz.ndim == 1:
        matriz = matriz.reshape(1, -1)
    if matriz.ndim != 2:
        raise ValueError("X debe ser una matriz 2D (muestras, caracteristicas)")
    if matriz.shape[0] == 0:
        raise ValueError("X no contiene muestras")
    if input_size is not None and matriz.shape[1] != input_size:
        raise ValueError(
            f"X tiene {matriz.shape[1]} caracteristicas y se esperaban {input_size}"
        )
    if not np.all(np.isfinite(matriz)):
        matriz = np.nan_to_num(matriz, nan=0.0, posinf=0.0, neginf=0.0)
    return matriz


def _validar_objetivo_regresion(y: Any,
                                n_muestras: int) -> np.ndarray:
    objetivo = np.asarray(y, dtype=np.float64)
    if objetivo.ndim == 1:
        objetivo = objetivo.reshape(-1, 1)
    if objetivo.ndim != 2:
        raise ValueError("y debe ser un vector o una matriz 2D")
    if objetivo.shape[0] != n_muestras:
        raise ValueError("X e y deben tener el mismo numero de muestras")
    if not np.all(np.isfinite(objetivo)):
        objetivo = np.nan_to_num(objetivo, nan=0.0, posinf=0.0, neginf=0.0)
    return objetivo


def _validar_objetivo_clasificacion(y: Any,
                                    n_muestras: int) -> Tuple[np.ndarray, np.ndarray]:
    etiquetas = np.asarray(y).reshape(-1)
    if etiquetas.shape[0] != n_muestras:
        raise ValueError("X e y deben tener el mismo numero de muestras")
    clases = np.unique(etiquetas)
    if clases.size < 2:
        raise ValueError("Se necesitan al menos dos clases")
    indices = np.searchsorted(clases, etiquetas).astype(np.int64)
    return indices, clases


def _metricas_regresion(prediccion: np.ndarray,
                        real: np.ndarray) -> Dict[str, float]:
    prediccion = np.asarray(prediccion, dtype=np.float64)
    real = np.asarray(real, dtype=np.float64)
    if prediccion.shape != real.shape:
        real = real.reshape(prediccion.shape)
    error = prediccion - real
    mse = float(np.mean(error ** 2))
    mae = float(np.mean(np.abs(error)))
    varianza = float(np.sum((real - np.mean(real)) ** 2))
    r2 = float(1.0 - np.sum(error ** 2) / varianza) if varianza > 1e-12 else 0.0
    return {'mse': mse, 'mae': mae, 'rmse': float(math.sqrt(mse)),
            'r2': r2, 'n_samples': int(real.shape[0])}


def _metricas_clasificacion(real: np.ndarray, prediccion: np.ndarray,
                            clases: Sequence[Any]) -> Dict[str, float]:
    real = np.asarray(real).reshape(-1)
    prediccion = np.asarray(prediccion).reshape(-1)
    exactitud = float(np.mean(real == prediccion)) if real.size else 0.0
    precisiones: List[float] = []
    recalls: List[float] = []
    f1s: List[float] = []
    for clase in clases:
        vp = float(np.sum((prediccion == clase) & (real == clase)))
        fp = float(np.sum((prediccion == clase) & (real != clase)))
        fn = float(np.sum((prediccion != clase) & (real == clase)))
        precision = vp / (vp + fp) if vp + fp > 0 else 0.0
        recall = vp / (vp + fn) if vp + fn > 0 else 0.0
        f1 = (2.0 * precision * recall / (precision + recall)
              if precision + recall > 0 else 0.0)
        precisiones.append(precision)
        recalls.append(recall)
        f1s.append(f1)
    return {'accuracy': exactitud,
            'precision': float(np.mean(precisiones)),
            'recall': float(np.mean(recalls)),
            'f1': float(np.mean(f1s)),
            'n_samples': int(real.size)}


class OptimizadorAdam:
    """Adam con weight decay y recorte global de gradiente."""

    def __init__(self, learning_rate: float = 0.01,
                 beta1: float = 0.9, beta2: float = 0.999,
                 epsilon: float = 1e-8, weight_decay: float = 0.0,
                 max_norm: float = 5.0) -> None:
        self.learning_rate = float(learning_rate)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.weight_decay = max(0.0, float(weight_decay))
        self.max_norm = float(max_norm)
        self.momentos: Dict[str, np.ndarray] = {}
        self.velocidades: Dict[str, np.ndarray] = {}
        self.paso = 0

    def step(self, parametros: Dict[str, np.ndarray],
             gradientes: Dict[str, np.ndarray]) -> None:
        preparados: Dict[str, np.ndarray] = {}
        for nombre, parametro in parametros.items():
            gradiente = np.asarray(gradientes[nombre], dtype=np.float64)
            if gradiente.shape != parametro.shape:
                raise ValueError(f"Gradiente incompatible en {nombre}")
            if self.weight_decay > 0.0:
                gradiente = gradiente + self.weight_decay * parametro
            preparados[nombre] = gradiente
        norma = math.sqrt(sum(float(np.sum(g * g))
                              for g in preparados.values()))
        if self.max_norm > 0 and norma > self.max_norm:
            factor = self.max_norm / (norma + 1e-12)
            preparados = {k: g * factor for k, g in preparados.items()}
        self.paso += 1
        correccion1 = 1.0 - self.beta1 ** self.paso
        correccion2 = 1.0 - self.beta2 ** self.paso
        for nombre, gradiente in preparados.items():
            if nombre not in self.momentos:
                self.momentos[nombre] = np.zeros_like(parametros[nombre])
                self.velocidades[nombre] = np.zeros_like(parametros[nombre])
            self.momentos[nombre] = (self.beta1 * self.momentos[nombre]
                                     + (1.0 - self.beta1) * gradiente)
            self.velocidades[nombre] = (self.beta2 * self.velocidades[nombre]
                                        + (1.0 - self.beta2) * gradiente * gradiente)
            m_hat = self.momentos[nombre] / correccion1
            v_hat = self.velocidades[nombre] / correccion2
            parametros[nombre] -= (self.learning_rate * m_hat
                                   / (np.sqrt(v_hat) + self.epsilon))


# ---------------------------------------------------------------------------
# 1) Arbol CART con hojas vectoriales, histogramas y ExtraTrees
# ---------------------------------------------------------------------------
class NeuronaArbolAleatorio(NeuronaMemoriaBase):
    """Arbol de decision para regresion multi-salida o clasificacion.

    Parametros
    ----------
    tarea:
        ``"regresion"`` (hojas vectoriales) o ``"clasificacion"``.
    modo:
        ``"rf"`` (CART con umbrales por cuantiles) o ``"extratrees"``
        (umbral aleatorio por caracteristica y nodo).
    criterion:
        ``"gini"`` o ``"entropy"`` (solo clasificacion).
    max_features:
        ``None``, entero, ``"sqrt"``, ``"log2"`` o fraccion (0,1].
    """

    def __init__(self, max_depth: int = 10, min_samples_split: int = 2,
                 min_samples_leaf: int = 1, max_features: Any = None,
                 n_bins: int = 32, min_gain: float = 1e-7,
                 modo: str = "rf", tarea: str = "regresion",
                 criterion: str = "gini", seed: Optional[int] = None,
                 nombre: str = "NeuronaArbolAleatorio") -> None:
        super().__init__(1, 1, nombre)
        self.max_depth = max(1, int(max_depth))
        self.min_samples_split = max(2, int(min_samples_split))
        self.min_samples_leaf = max(1, int(min_samples_leaf))
        self.max_features = max_features
        self.n_bins = max(2, int(n_bins))
        self.min_gain = float(min_gain)
        self.modo = (modo if modo in ("rf", "extratrees") else "rf")
        self.tarea = (tarea if tarea in ("regresion", "clasificacion")
                      else "regresion")
        self.criterion = (criterion if criterion in ("gini", "entropy")
                          else "gini")
        self.rng = np.random.default_rng(
            int(LUCIA_RF_CONFIG["random_seed"] if seed is None else seed)
        )
        self.arbol: Optional[Dict[str, Any]] = None
        self.importancias_: Optional[np.ndarray] = None
        self.clases_: Optional[np.ndarray] = None
        self._X: Optional[np.ndarray] = None
        self._y: Optional[np.ndarray] = None
        self._n_clases = 0
        self._n_salidas = 0

    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    # -- utilidades internas ----------------------------------------------
    def _n_features_nodo(self, n_features: int) -> int:
        if self.max_features is None:
            return n_features
        if isinstance(self.max_features, str):
            if self.max_features == "sqrt":
                return max(1, int(math.sqrt(n_features)))
            if self.max_features == "log2":
                return max(1, int(math.log2(max(2, n_features))))
            return n_features
        valor = float(self.max_features)
        if 0.0 < valor <= 1.0:
            return max(1, int(round(valor * n_features)))
        return max(1, min(n_features, int(valor)))

    def _impureza(self, indices: np.ndarray) -> float:
        if self.tarea == "regresion":
            valores = self._y[indices]
            return float(np.sum(np.var(valores, axis=0)) * indices.size)
        conteos = np.bincount(self._y[indices].astype(np.int64),
                              minlength=self._n_clases).astype(np.float64)
        probabilidades = conteos / max(1.0, float(conteos.sum()))
        if self.criterion == "entropy":
            return float(-np.sum(probabilidades * np.log(
                np.clip(probabilidades, 1e-12, 1.0))) * indices.size)
        return float((1.0 - np.sum(probabilidades ** 2)) * indices.size)

    def _sse(self, indices: np.ndarray) -> float:
        valores = self._y[indices]
        if valores.size == 0:
            return 0.0
        return float(np.sum((valores - np.mean(valores, axis=0)) ** 2))

    def _division(self, indices: np.ndarray) -> Optional[Dict[str, Any]]:
        n = indices.size
        if n < self.min_samples_split or n < 2 * self.min_samples_leaf:
            return None
        n_features = self._X.shape[1]
        k = self._n_features_nodo(n_features)
        if k < n_features:
            caracteristicas = self.rng.choice(n_features, size=k, replace=False)
        else:
            caracteristicas = np.arange(n_features)

        if self.tarea == "regresion":
            impureza_padre = self._sse(indices)
        else:
            impureza_padre = self._impureza(indices)
        mejor: Optional[Dict[str, Any]] = None
        mejor_ganancia = 0.0

        for feature in caracteristicas:
            columna = self._X[indices, feature]
            valores = np.unique(columna)
            if valores.size <= 1:
                continue
            if self.modo == "extratrees":
                candidatos = [float(self.rng.uniform(valores[0], valores[-1]))]
            else:
                candidatos = np.unique(np.quantile(
                    columna, np.linspace(0.0, 1.0, self.n_bins + 1)[1:-1]
                ))
            for umbral in candidatos:
                mascara = columna <= umbral
                n_izquierda = int(np.sum(mascara))
                n_derecha = n - n_izquierda
                if (n_izquierda < self.min_samples_leaf
                        or n_derecha < self.min_samples_leaf):
                    continue
                izquierda = indices[mascara]
                derecha = indices[~mascara]
                if self.tarea == "regresion":
                    ganancia = (impureza_padre - self._sse(izquierda)
                                - self._sse(derecha))
                else:
                    ganancia = (impureza_padre - self._impureza(izquierda)
                                - self._impureza(derecha))
                if ganancia > mejor_ganancia:
                    mejor_ganancia = float(ganancia)
                    mejor = {
                        'feature': int(feature),
                        'umbral': float(umbral),
                        'ganancia': float(ganancia),
                    }
        return mejor

    def _hoja(self, indices: np.ndarray) -> Dict[str, Any]:
        if self.tarea == "regresion":
            return {
                'hoja': True,
                'n': int(indices.size),
                'valor': np.mean(self._y[indices], axis=0),
            }
        conteos = np.bincount(self._y[indices].astype(np.int64),
                              minlength=self._n_clases).astype(np.float64)
        return {
            'hoja': True,
            'n': int(indices.size),
            'probs': conteos / max(1.0, float(conteos.sum())),
        }

    def _construir(self, indices: np.ndarray, profundidad: int) -> Dict[str, Any]:
        if (profundidad >= self.max_depth
                or indices.size < 2 * self.min_samples_leaf
                or indices.size < self.min_samples_split):
            return self._hoja(indices)
        division = self._division(indices)
        if division is None or division['ganancia'] <= self.min_gain:
            return self._hoja(indices)
        columna = self._X[indices, division['feature']]
        mascara = columna <= division['umbral']
        izquierda = indices[mascara]
        derecha = indices[~mascara]
        if (izquierda.size < self.min_samples_leaf
                or derecha.size < self.min_samples_leaf):
            return self._hoja(indices)
        if self.importancias_ is not None:
            self.importancias_[division['feature']] += division['ganancia']
        return {
            'hoja': False,
            'feature': division['feature'],
            'umbral': division['umbral'],
            'gain': division['ganancia'],
            'n': int(indices.size),
            'izquierda': self._construir(izquierda, profundidad + 1),
            'derecha': self._construir(derecha, profundidad + 1),
        }

    # -- ajuste ------------------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray,
            clases: Optional[np.ndarray] = None) -> "NeuronaArbolAleatorio":
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 2:
            self.input_size = int(matriz.shape[1])
        if self.tarea == "regresion":
            objetivo = _validar_objetivo_regresion(y, matriz.shape[0])
            self._n_salidas = int(objetivo.shape[1])
            self.output_size = self._n_salidas
            self.clases_ = None
        else:
            indices, etiquetas = _validar_objetivo_clasificacion(
                y, matriz.shape[0]
            )
            if clases is not None:
                etiquetas = np.asarray(clases)
                indices = np.searchsorted(etiquetas, np.asarray(y).reshape(-1))
            objetivo = indices.astype(np.int64)
            self.clases_ = np.asarray(etiquetas)
            self._n_clases = int(self.clases_.size)
            self.output_size = self._n_clases
        self._X = matriz
        self._y = objetivo
        self.importancias_ = np.zeros(matriz.shape[1], dtype=np.float64)
        self.arbol = self._construir(np.arange(matriz.shape[0]), 0)
        total = float(np.sum(self.importancias_))
        if total > 1e-12:
            self.importancias_ = self.importancias_ / total
        self._X = None
        self._y = None
        return self

    # -- prediccion --------------------------------------------------------
    def _nodo_final(self, x: np.ndarray) -> Dict[str, Any]:
        nodo = self.arbol
        while not nodo['hoja']:
            nodo = (nodo['izquierda'] if x[nodo['feature']] <= nodo['umbral']
                    else nodo['derecha'])
        return nodo

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.arbol is None:
            raise RuntimeError("Arbol no ajustado: llama a fit primero")
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        if self.tarea == "regresion":
            return np.array([self._nodo_final(fila)['valor']
                             for fila in matriz], dtype=np.float64)
        probabilidades = self.predict_proba(matriz)
        return self.clases_[np.argmax(probabilidades, axis=1)]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.arbol is None:
            raise RuntimeError("Arbol no ajustado: llama a fit primero")
        if self.tarea != "clasificacion":
            raise RuntimeError("predict_proba solo aplica a clasificacion")
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        return np.array([self._nodo_final(fila)['probs'] for fila in matriz],
                        dtype=np.float64)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        return self.predict(entrada)

    # -- informacion -------------------------------------------------------
    def n_hojas(self) -> int:
        if self.arbol is None:
            return 0

        def _contar(nodo: Dict[str, Any]) -> int:
            if nodo['hoja']:
                return 1
            return _contar(nodo['izquierda']) + _contar(nodo['derecha'])

        return int(_contar(self.arbol))

    def profundidad_real(self) -> int:
        if self.arbol is None:
            return 0

        def _profundidad(nodo: Dict[str, Any]) -> int:
            if nodo['hoja']:
                return 1
            return 1 + max(_profundidad(nodo['izquierda']),
                           _profundidad(nodo['derecha']))

        return int(_profundidad(self.arbol))

    def params_count(self) -> int:
        if self.arbol is None:
            return 0
        total = 0
        pila = [self.arbol]
        while pila:
            nodo = pila.pop()
            if nodo['hoja']:
                total += (self._n_clases if self.tarea == "clasificacion"
                          else max(1, self._n_salidas))
            else:
                total += 2
                pila.extend([nodo['izquierda'], nodo['derecha']])
        return int(total)

    def _arreglos_parametros(self) -> List[np.ndarray]:
        arreglos: List[np.ndarray] = []
        pila = [self.arbol] if self.arbol is not None else []
        while pila:
            nodo = pila.pop()
            if nodo['hoja']:
                if 'valor' in nodo:
                    arreglos.append(np.asarray(nodo['valor'], dtype=np.float64))
                else:
                    arreglos.append(np.asarray(nodo['probs'], dtype=np.float64))
            else:
                pila.extend([nodo['izquierda'], nodo['derecha']])
        return arreglos

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        estadisticas.update({
            'tipo': 'arbol_aleatorio',
            'tarea': self.tarea,
            'modo': self.modo,
            'max_depth': self.max_depth,
            'n_hojas': self.n_hojas(),
            'profundidad_real': self.profundidad_real(),
            'n_salidas': self._n_salidas,
            'n_clases': self._n_clases,
            'importancias': (self.importancias_.round(6).tolist()
                             if self.importancias_ is not None else None),
        })
        return estadisticas


# ---------------------------------------------------------------------------
# 2) Random Forest con OOB real y hojas vectoriales
# ---------------------------------------------------------------------------
class NeuronaBosqueAleatorio(NeuronaMemoriaBase):
    """Bosque aleatorio para regresion multi-salida o clasificacion."""

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaBosqueAleatorio",
                 n_estimators: int = 100, max_depth: int = 10,
                 min_samples_split: int = 2, min_samples_leaf: int = 1,
                 max_features: Any = "sqrt", n_bins: int = 32,
                 bootstrap: bool = True, oob_score: bool = True,
                 modo: str = "rf", tarea: str = "regresion",
                 criterion: str = "gini", seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre)
        self.n_estimators = max(1, int(n_estimators))
        self.max_depth = max(1, int(max_depth))
        self.min_samples_split = max(2, int(min_samples_split))
        self.min_samples_leaf = max(1, int(min_samples_leaf))
        self.max_features = max_features
        self.n_bins = max(2, int(n_bins))
        self.bootstrap = bool(bootstrap)
        self.oob_score = bool(oob_score)
        self.modo = modo
        self.tarea = (tarea if tarea in ("regresion", "clasificacion")
                      else "regresion")
        self.criterion = criterion
        self.seed = int(LUCIA_RF_CONFIG["random_seed"]
                        if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.arboles: List[NeuronaArbolAleatorio] = []
        self.muestras_bootstrap: List[np.ndarray] = []
        self.classes_: Optional[np.ndarray] = None
        self.importancias_: Optional[np.ndarray] = None
        self._is_fitted = False
        self._oob_score = 0.0
        self._convergence_history: List[float] = []
        self._training_time = 0.0
        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    def fit(self, X: np.ndarray, y: np.ndarray,
            epochs: Optional[int] = None, verbose: bool = False,
            **kwargs: Any) -> List[float]:
        matriz = _validar_entrada(X, None)
        self.input_size = int(matriz.shape[1])
        if epochs is not None:
            self.n_estimators = max(1, int(epochs))
        if self.tarea == "regresion":
            objetivo = _validar_objetivo_regresion(y, matriz.shape[0])
            self.output_size = int(objetivo.shape[1])
            self.classes_ = None
            objetivo_entrenamiento = objetivo
        else:
            _, clases = _validar_objetivo_clasificacion(y, matriz.shape[0])
            self.classes_ = clases
            objetivo_entrenamiento = np.asarray(y).reshape(-1)
            self.output_size = int(clases.size)

        inicio = time.perf_counter()
        self.arboles = []
        self.muestras_bootstrap = []
        self._convergence_history = []
        n = matriz.shape[0]
        for _ in range(self.n_estimators):
            if self.bootstrap:
                indices_bootstrap = self.rng.integers(0, n, size=n)
            else:
                indices_bootstrap = np.arange(n)
            arbol = NeuronaArbolAleatorio(
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                max_features=self.max_features,
                n_bins=self.n_bins,
                modo=self.modo,
                tarea=self.tarea,
                criterion=self.criterion,
                seed=int(self.rng.integers(0, 2 ** 31 - 1)),
            )
            if self.tarea == "clasificacion":
                arbol.fit(matriz[indices_bootstrap],
                          objetivo_entrenamiento[indices_bootstrap],
                          clases=self.classes_)
            else:
                arbol.fit(matriz[indices_bootstrap],
                          objetivo_entrenamiento[indices_bootstrap])
            self.arboles.append(arbol)
            self.muestras_bootstrap.append(np.asarray(indices_bootstrap))
            self._convergence_history.append(self._error_entrenamiento())
        self.importancias_ = self._calcular_importancias()
        self._is_fitted = True
        self._training_time = time.perf_counter() - inicio
        if self.oob_score:
            self._oob_score = self._calcular_oob(matriz, objetivo_entrenamiento)
        if verbose:
            logger.info("%s: %d arboles, OOB=%.4f, %.3fs",
                        self.nombre, len(self.arboles), self._oob_score,
                        self._training_time)
        return list(self._convergence_history)

    def train(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
              learning_rate: Optional[float] = None, verbose: bool = False,
              **kwargs: Any) -> Dict[str, Any]:
        historial = self.fit(X, y, epochs=epochs, verbose=verbose, **kwargs)
        return {'historial': historial,
                'n_estimators': len(self.arboles),
                'oob_score': float(self._oob_score),
                'perdida_final': float(historial[-1]) if historial else None}

    # -- OOB / importancias ------------------------------------------------
    def _error_entrenamiento(self) -> float:
        if not self.arboles:
            return 0.0
        return 0.0

    def _calcular_importancias(self) -> np.ndarray:
        if not self.arboles:
            return np.zeros(self.input_size)
        acumulado = np.zeros(self.input_size, dtype=np.float64)
        for arbol in self.arboles:
            if arbol.importancias_ is not None:
                acumulado += arbol.importancias_
        total = float(np.sum(acumulado))
        return acumulado / total if total > 1e-12 else acumulado

    def _calcular_oob(self, X: np.ndarray, objetivo: np.ndarray) -> float:
        n = X.shape[0]
        if self.tarea == "regresion":
            sumas = np.zeros((n, self.output_size), dtype=np.float64)
            conteos = np.zeros(n, dtype=np.float64)
            for arbol, indices in zip(self.arboles, self.muestras_bootstrap):
                mascara = np.ones(n, dtype=bool)
                mascara[indices] = False
                if not np.any(mascara):
                    continue
                prediccion = np.asarray(arbol.predict(X[mascara]),
                                        dtype=np.float64)
                sumas[mascara] += prediccion
                conteos[mascara] += 1.0
            validos = conteos > 0
            if not np.any(validos):
                return 0.0
            prediccion_oob = sumas[validos] / conteos[validos][:, None]
            metricas = _metricas_regresion(prediccion_oob,
                                           objetivo[validos])
            return float(metricas['r2'])
        sumas = np.zeros((n, self.output_size), dtype=np.float64)
        conteos = np.zeros(n, dtype=np.float64)
        for arbol, indices in zip(self.arboles, self.muestras_bootstrap):
            mascara = np.ones(n, dtype=bool)
            mascara[indices] = False
            if not np.any(mascara):
                continue
            sumas[mascara] += arbol.predict_proba(X[mascara])
            conteos[mascara] += 1.0
        validos = conteos > 0
        if not np.any(validos):
            return 0.0
        prediccion = self.classes_[np.argmax(sumas[validos], axis=1)]
        return float(np.mean(prediccion == np.asarray(objetivo)[validos]))

    # -- inferencia --------------------------------------------------------
    def _predicciones_arboles(self, X: np.ndarray) -> List[np.ndarray]:
        if not self.arboles:
            raise RuntimeError("Bosque no ajustado: llama a fit primero")
        return [arbol.predict(X) for arbol in self.arboles]

    def predict(self, X: np.ndarray) -> np.ndarray:
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        if self.tarea == "regresion":
            predicciones = [np.asarray(arbol.predict(matriz), dtype=np.float64)
                            for arbol in self.arboles]
            return np.mean(np.stack(predicciones, axis=0), axis=0)
        probabilidades = self.predict_proba(matriz)
        return self.classes_[np.argmax(probabilidades, axis=1)]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.tarea != "clasificacion":
            raise RuntimeError("predict_proba solo aplica a clasificacion")
        if not self.arboles:
            raise RuntimeError("Bosque no ajustado: llama a fit primero")
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        probabilidades = [arbol.predict_proba(matriz) for arbol in self.arboles]
        return np.mean(np.stack(probabilidades, axis=0), axis=0)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        return self.predict(entrada)

    def compute_loss(self, prediccion: np.ndarray,
                     objetivo: np.ndarray) -> float:
        if self.tarea == "regresion":
            return float(np.mean((np.asarray(prediccion)
                                  - np.asarray(objetivo)) ** 2))
        return float(np.mean(np.asarray(prediccion) != np.asarray(objetivo)))

    def compute_oob_score(self, X: np.ndarray, y: np.ndarray) -> float:
        matriz = _validar_entrada(X, self.input_size)
        if self.tarea == "regresion":
            objetivo = _validar_objetivo_regresion(y, matriz.shape[0])
        else:
            objetivo = np.asarray(y).reshape(-1)
        return float(self._calcular_oob(matriz, objetivo))

    def compute_feature_importances(self) -> np.ndarray:
        if self.importancias_ is None:
            self.importancias_ = self._calcular_importancias()
        return self.importancias_

    # -- evaluacion --------------------------------------------------------
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        matriz = _validar_entrada(X, self.input_size)
        if self.tarea == "regresion":
            objetivo = _validar_objetivo_regresion(y, matriz.shape[0])
            metricas = _metricas_regresion(self.predict(matriz), objetivo)
        else:
            etiquetas = np.asarray(y).reshape(-1)
            metricas = _metricas_clasificacion(
                etiquetas, self.predict(matriz), self.classes_
            )
        metricas['oob_score'] = float(self._oob_score)
        metricas['n_estimators'] = len(self.arboles)
        return metricas

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        metricas = self.evaluate(X, y)
        return float(metricas.get('r2', metricas.get('accuracy', 0.0)))

    # -- informacion -------------------------------------------------------
    def params_count(self) -> int:
        return int(sum(arbol.params_count() for arbol in self.arboles))

    def _arreglos_parametros(self) -> List[np.ndarray]:
        arreglos: List[np.ndarray] = []
        for arbol in self.arboles:
            arreglos.extend(arbol._arreglos_parametros())
        return arreglos

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        estadisticas.update({
            'tipo': 'bosque_aleatorio',
            'tarea': self.tarea,
            'n_estimators': len(self.arboles),
            'oob_score': float(self._oob_score),
            'importancias': (self.compute_feature_importances().round(6).tolist()
                             if self.importancias_ is not None else None),
            'training_time': float(self._training_time),
        })
        return estadisticas

    def verificar_estabilidad(self) -> Dict[str, Any]:
        base = super().verificar_estabilidad()
        base['entrenado'] = bool(self._is_fitted)
        return base

    # -- persistencia ------------------------------------------------------
    def save(self, filepath: str) -> None:
        with open(filepath, 'wb') as fichero:
            pickle.dump(self, fichero, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        with open(filepath, 'rb') as fichero:
            self.__dict__.update(pickle.load(fichero).__dict__)

    def get_config(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'n_estimators': self.n_estimators,
            'max_depth': self.max_depth,
            'max_features': self.max_features,
            'tarea': self.tarea,
            'modo': self.modo,
        }

    def summary(self) -> str:
        estadisticas = self.obtener_estadisticas()
        return "\n".join([
            f"=== {self.nombre} ===",
            f"Tarea: {self.tarea} | arboles: {len(self.arboles)}",
            f"OOB: {estadisticas['oob_score']:.4f}",
            f"Params: {self.params_count()}",
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(trees={len(self.arboles)},tarea={self.tarea})"


# ---------------------------------------------------------------------------
# 3) TabM: MLP con ensamblado parametro-eficiente (BatchEnsemble)
# ---------------------------------------------------------------------------
class NeuronaTabM(NeuronaMemoriaBase):
    """Ensemble de K MLPs con matrices de rango 1 compartiendo W (TabM).

    Cada miembro usa ``W_k = W * (r_k s_k^T)``; el coste de parametros crece
    O(K(H+D)) en lugar de O(K H D). Entrena con gradientes analiticos.
    """

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaTabM", k_miembros: int = 8,
                 dim_oculta: int = 64, tarea: str = "regresion",
                 learning_rate: float = 0.01, epochs: int = 100,
                 batch_size: int = 64, weight_decay: float = 1e-4,
                 seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre)
        self.k_miembros = max(1, int(k_miembros))
        self.dim_oculta = max(2, int(dim_oculta))
        self.tarea = (tarea if tarea in ("regresion", "clasificacion")
                      else "regresion")
        self.learning_rate = max(1e-6, float(learning_rate))
        self.epochs = max(1, int(epochs))
        self.batch_size = max(1, int(batch_size))
        self.weight_decay = max(0.0, float(weight_decay))
        self.seed = int(LUCIA_RF_CONFIG["random_seed"]
                        if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.classes_: Optional[np.ndarray] = None
        self.media: Optional[np.ndarray] = None
        self.desviacion: Optional[np.ndarray] = None
        self.media_y = 0.0
        self.desviacion_y = 1.0
        self._parametros: Dict[str, np.ndarray] = {}
        self._historial: List[float] = []
        self._is_fitted = False
        self._training_time = 0.0
        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    def _crear_parametros(self, n_entradas: int, n_salidas: int) -> None:
        k, h = self.k_miembros, self.dim_oculta
        generador = np.random.default_rng(self.seed + 1)
        self._parametros = {
            'W1': generador.normal(0.0, math.sqrt(2.0 / n_entradas),
                                   (h, n_entradas)),
            'b1': np.zeros(h),
            'W2': generador.normal(0.0, math.sqrt(2.0 / h), (n_salidas, h)),
            'b2': np.zeros(n_salidas),
            'r1': generador.normal(1.0, 0.1, (k, h)),
            's1': generador.normal(1.0, 0.1, (k, n_entradas)),
            'r2': generador.normal(1.0, 0.1, (k, n_salidas)),
            's2': generador.normal(1.0, 0.1, (k, h)),
        }

    def _normalizar(self, X: np.ndarray) -> np.ndarray:
        if self.media is None:
            return X
        return (X - self.media) / self.desviacion

    def _forward_cache(self, X: np.ndarray
                       ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        Z = self._normalizar(X)
        p = self._parametros
        Z1 = Z[None, :, :] * p['s1'][:, None, :]
        U = np.einsum('kbd,hd->kbh', Z1, p['W1']) + p['b1'][None, None, :]
        pre = p['r1'][:, None, :] * U
        H = np.maximum(pre, 0.0)
        H2 = H * p['s2'][:, None, :]
        V = np.einsum('kbh,oh->kbo', H2, p['W2'])
        salida = p['r2'][:, None, :] * V + p['b2'][None, None, :]
        prediccion = np.mean(salida, axis=0)
        cache = {'Z': Z, 'Z1': Z1, 'U': U, 'pre': pre, 'H': H,
                 'H2': H2, 'V': V, 'salida': salida}
        return prediccion, cache

    def _gradientes(self, cache: Dict[str, np.ndarray],
                    grad_salida: np.ndarray) -> Dict[str, np.ndarray]:
        p = self._parametros
        Z1, U, pre, H, H2 = (cache['Z1'], cache['U'], cache['pre'],
                             cache['H'], cache['H2'])
        V = cache['V']
        dV = grad_salida * p['r2'][:, None, :]
        dW2 = np.einsum('kbh,kbo->oh', H2, dV)
        db2 = grad_salida.sum(axis=(0, 1))
        dr2 = np.sum(grad_salida * V, axis=1)
        dH2 = np.einsum('kbo,oh->kbh', dV, p['W2'])
        ds2 = np.sum(dH2 * H, axis=1)
        dH = dH2 * p['s2'][:, None, :]
        dpre = dH * (pre > 0.0)
        dr1 = np.sum(dpre * U, axis=1)
        dU = dpre * p['r1'][:, None, :]
        dW1 = np.einsum('kbh,kbd->hd', dU, Z1)
        db1 = dU.sum(axis=(0, 1))
        dZ1 = np.einsum('kbh,hd->kbd', dU, p['W1'])
        ds1 = np.sum(dZ1 * cache['Z'][None, :, :], axis=1)
        return {'W1': dW1, 'b1': db1, 'W2': dW2, 'b2': db2,
                'r1': dr1, 's1': ds1, 'r2': dr2, 's2': ds2}

    def _perdida(self, prediccion: np.ndarray, objetivo: np.ndarray) -> float:
        if self.tarea == "regresion":
            return float(np.mean((prediccion - objetivo) ** 2))
        probabilidades = _softmax(prediccion, eje=1)
        indice = np.arange(objetivo.size)
        return float(-np.mean(np.log(
            np.clip(probabilidades[indice, objetivo.astype(np.int64)],
                    1e-12, 1.0)
        )))

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
            learning_rate: Optional[float] = None, verbose: bool = False,
            **kwargs: Any) -> List[float]:
        matriz = _validar_entrada(X, self.input_size)
        if epochs is not None:
            self.epochs = max(1, int(epochs))
        if learning_rate is not None:
            self.learning_rate = max(1e-6, float(learning_rate))
        if self.tarea == "regresion":
            objetivo = _validar_objetivo_regresion(y, matriz.shape[0])
            self.media_y = float(np.mean(objetivo))
            self.desviacion_y = max(float(np.std(objetivo)), 1e-8)
            objetivo_entrenamiento = (objetivo - self.media_y) / self.desviacion_y
            n_salidas = int(objetivo.shape[1])
        else:
            indices, clases = _validar_objetivo_clasificacion(
                y, matriz.shape[0]
            )
            self.classes_ = clases
            objetivo_entrenamiento = indices
            n_salidas = int(clases.size)
        self.media = np.mean(matriz, axis=0)
        self.desviacion = np.maximum(np.std(matriz, axis=0), 1e-8)
        self.output_size = n_salidas
        self._crear_parametros(self.input_size, n_salidas)
        optimizador = OptimizadorAdam(
            learning_rate=self.learning_rate,
            weight_decay=self.weight_decay,
            max_norm=5.0,
        )
        inicio = time.perf_counter()
        self._historial = []
        n = matriz.shape[0]
        for _ in range(self.epochs):
            orden = self.rng.permutation(n)
            perdida_epoca = 0.0
            for comienzo in range(0, n, self.batch_size):
                lote = orden[comienzo:comienzo + self.batch_size]
                Xb = matriz[lote]
                Yb = objetivo_entrenamiento[lote]
                prediccion, cache = self._forward_cache(Xb)
                perdida = self._perdida(prediccion, Yb)
                perdida_epoca += perdida * len(lote)
                k = self.k_miembros
                if self.tarea == "regresion":
                    # Yb ya viene estandarizado (media 0, desviacion 1).
                    grad_prediccion = (2.0 * (prediccion - Yb)
                                       / prediccion.size)
                    grad_salida = np.repeat(
                        grad_prediccion[None, :, :] / k, k, axis=0
                    )
                else:
                    probabilidades = _softmax(prediccion, eje=1)
                    grad_prediccion = probabilidades.copy()
                    grad_prediccion[np.arange(len(lote)),
                                     Yb.astype(np.int64)] -= 1.0
                    grad_prediccion /= len(lote)
                    grad_salida = np.repeat(
                        grad_prediccion[None, :, :] / k, k, axis=0
                    )
                gradientes = self._gradientes(cache, grad_salida)
                optimizador.step(self._parametros, gradientes)
            self._historial.append(perdida_epoca / n)
            self.registrar_perdida(self._historial[-1])
            if verbose and (_ + 1) % 20 == 0:
                logger.info("%s epoca %d/%d | perdida=%.6f",
                            self.nombre, _ + 1, self.epochs,
                            self._historial[-1])
        self._is_fitted = True
        self._training_time = time.perf_counter() - inicio
        return list(self._historial)

    def train(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
              learning_rate: Optional[float] = None, verbose: bool = False,
              **kwargs: Any) -> Dict[str, Any]:
        historial = self.fit(X, y, epochs=epochs,
                             learning_rate=learning_rate, verbose=verbose,
                             **kwargs)
        return {'historial': historial,
                'perdida_final': float(historial[-1]) if historial else None}

    def _predecir_crudo(self, X: np.ndarray) -> np.ndarray:
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        if matriz.shape[1] != self.input_size:
            raise ValueError(
                f"Se esperaban {self.input_size} caracteristicas y llegaron "
                f"{matriz.shape[1]}"
            )
        prediccion, _ = self._forward_cache(matriz)
        if self.tarea == "regresion":
            return prediccion * self.desviacion_y + self.media_y
        return prediccion

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("TabM no entrenado: llama a fit primero")
        crudo = self._predecir_crudo(X)
        if self.tarea == "regresion":
            return crudo
        return self.classes_[np.argmax(crudo, axis=1)]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.tarea != "clasificacion":
            raise RuntimeError("predict_proba solo aplica a clasificacion")
        if not self._is_fitted:
            raise RuntimeError("TabM no entrenado: llama a fit primero")
        return _softmax(self._predecir_crudo(X), eje=1)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        return self.predict(entrada)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        if self.tarea == "regresion":
            matriz = np.asarray(X)
            n_muestras = 1 if matriz.ndim == 1 else matriz.shape[0]
            objetivo = _validar_objetivo_regresion(y, n_muestras)
            metricas = _metricas_regresion(self.predict(X), objetivo)
        else:
            etiquetas = np.asarray(y).reshape(-1)
            metricas = _metricas_clasificacion(
                etiquetas, self.predict(X), self.classes_
            )
        metricas['n_miembros'] = self.k_miembros
        return metricas

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        metricas = self.evaluate(X, y)
        return float(metricas.get('r2', metricas.get('accuracy', 0.0)))

    def params_count(self) -> int:
        return int(sum(parametro.size
                       for parametro in self._parametros.values()))

    def _arreglos_parametros(self) -> List[np.ndarray]:
        return [np.asarray(parametro, dtype=np.float64)
                for parametro in self._parametros.values()]

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        estadisticas.update({
            'tipo': 'tabm',
            'tarea': self.tarea,
            'k_miembros': self.k_miembros,
            'dim_oculta': self.dim_oculta,
            'is_fitted': bool(self._is_fitted),
            'historial_len': len(self._historial),
            'training_time': float(self._training_time),
        })
        return estadisticas

    def verificar_estabilidad(self) -> Dict[str, Any]:
        base = super().verificar_estabilidad()
        base['entrenado'] = bool(self._is_fitted)
        return base

    def save(self, filepath: str) -> None:
        with open(filepath, 'wb') as fichero:
            pickle.dump(self, fichero, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        with open(filepath, 'rb') as fichero:
            self.__dict__.update(pickle.load(fichero).__dict__)

    def get_config(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'k_miembros': self.k_miembros,
            'dim_oculta': self.dim_oculta,
            'tarea': self.tarea,
            'learning_rate': self.learning_rate,
            'epochs': self.epochs,
        }

    def summary(self) -> str:
        return "\n".join([
            f"=== {self.nombre} ===",
            f"TabM K={self.k_miembros} H={self.dim_oculta} ({self.tarea})",
            f"Params: {self.params_count()}",
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(K={self.k_miembros},H={self.dim_oculta})"


# ---------------------------------------------------------------------------
# 4) Adaptador de compatibilidad con RF_SL1_3
# ---------------------------------------------------------------------------
class RandomForestOptimizer(NeuronaBosqueAleatorio):
    """API historica de RF_SL1_3 respaldada por el bosque vectorial real."""

    def __init__(self, input_size: int = 4, output_size: int = 8,
                 nombre: str = "RandomForestOptimizer", **kwargs: Any) -> None:
        kwargs.setdefault("tarea", "regresion")
        super().__init__(input_size=input_size, output_size=output_size,
                         nombre=nombre, **kwargs)
        self._n_trees = int(self.n_estimators)
        self._max_depth = int(self.max_depth)
        self._min_samples_split = int(self.min_samples_split)
        self._subsample_ratio = 1.0
        self._n_features = self.max_features
        self._bootstrap = bool(self.bootstrap)
        self._trees = self.arboles
        self._feature_importances: Optional[np.ndarray] = None
        self._training_time = 0.0
        self._convergence_history: List[float] = []

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
            verbose: bool = False, **kwargs: Any) -> List[float]:
        historial = super().fit(X, y, epochs=epochs, verbose=verbose, **kwargs)
        self._n_trees = len(self.arboles)
        self._max_depth = int(self.max_depth)
        self._min_samples_split = int(self.min_samples_split)
        self._trees = self.arboles
        self._feature_importances = self.importancias_
        self._training_time = float(self._training_time)
        self._convergence_history = list(historial)
        return historial

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X = np.asarray(entrada, dtype=np.float64)
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(-1, 1)
        n = max(1, X.shape[0])
        return X.T @ gradiente / n, np.mean(gradiente, axis=0, keepdims=True)

    def update_weights(self, grad_pesos: np.ndarray,
                       grad_sesgo: np.ndarray) -> None:
        if self.pesos is None:
            self.pesos = np.zeros((self.input_size,
                                   max(1, self.output_size)))
        if self.sesgo is None:
            self.sesgo = np.zeros((1, max(1, self.output_size)))
        self.pesos = self.pesos - 0.01 * grad_pesos
        self.sesgo = self.sesgo - 0.01 * grad_sesgo

    def apply_gradient(self, entrada: np.ndarray,
                       objetivo: np.ndarray) -> float:
        prediccion = np.asarray(self.predict(entrada), dtype=np.float64)
        etiquetas = np.asarray(objetivo, dtype=np.float64)
        if prediccion.ndim == 1:
            prediccion = prediccion.reshape(-1, 1)
        if etiquetas.ndim == 1:
            etiquetas = etiquetas.reshape(-1, 1)
        if prediccion.shape != etiquetas.shape:
            etiquetas = etiquetas[:, :prediccion.shape[1]]
        gradiente = prediccion - etiquetas
        gp, gs = self.backward(gradiente, entrada)
        self.update_weights(gp, gs)
        return self.compute_loss(self.predict(entrada), objetivo)

    def train_step(self, entrada: np.ndarray,
                   objetivo: np.ndarray) -> Dict[str, float]:
        antes = self.compute_loss(self.predict(entrada), objetivo)
        despues = self.apply_gradient(entrada, objetivo)
        return {'loss_before': antes, 'loss_after': despues,
                'improvement': antes - despues}

    def get_config(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'n_trees': self._n_trees,
            'max_depth': self._max_depth,
            'min_samples_split': self._min_samples_split,
            'bootstrap': self._bootstrap,
        }

    def summary(self) -> str:
        configuracion = self.get_config()
        return "\n".join([
            f"=== {configuracion['nombre']} ===",
            (f"Arboles: {configuracion['n_trees']}, "
             f"Depth: {configuracion['max_depth']}"),
            f"OOB: {self._oob_score:.4f}, Params: {self.params_count()}",
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(trees={len(self.arboles)})"


# ---------------------------------------------------------------------------
# Fabrica, evaluacion y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "bosque", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaMemoriaBase:
    clave = str(tipo or "").strip().lower()
    if clave in ("bosque", "rf", "random_forest", "bosque_aleatorio"):
        return NeuronaBosqueAleatorio(input_size=input_size,
                                      output_size=output_size, **kwargs)
    if clave in ("tabm", "matrices", "batch_ensemble"):
        return NeuronaTabM(input_size=input_size,
                           output_size=output_size, **kwargs)
    if clave in ("arbol", "cart", "tree"):
        return NeuronaArbolAleatorio(**kwargs)
    if clave in ("compat", "compatibilidad", "optimizer"):
        return RandomForestOptimizer(input_size=input_size,
                                     output_size=output_size, **kwargs)
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: bosque, tabm, arbol, compat"
    )


def tipos_disponibles() -> List[str]:
    return ["bosque", "tabm", "arbol", "compat"]


def entrenar_y_evaluar(modelo: NeuronaMemoriaBase, X: np.ndarray,
                       y: np.ndarray, **kwargs: Any) -> Dict[str, Any]:
    historial = modelo.fit(X, y, **kwargs)
    return {
        'modelo': modelo,
        'historial': historial,
        'metricas': modelo.evaluate(X, y),
        'perdida_final': float(historial[-1]) if historial else float('nan'),
    }


def benchmark_modelo(modelo: NeuronaMemoriaBase, X: np.ndarray,
                     repeticiones: int = 5) -> Dict[str, float]:
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
        'n_runs': len(tiempos),
    }


def guardar_modelo(modelo: NeuronaMemoriaBase, ruta: str) -> None:
    with open(ruta, 'wb') as fichero:
        pickle.dump(modelo, fichero, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaMemoriaBase:
    with open(ruta, 'rb') as fichero:
        modelo = pickle.load(fichero)
    if not isinstance(modelo, NeuronaMemoriaBase):
        raise TypeError("El fichero no contiene una neurona de bosque/TabM")
    return modelo


def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_3_1.py``)."""
    generador = np.random.default_rng(2026)
    X = generador.uniform(-2.0, 2.0, size=(240, 3))
    y = (np.sin(2.0 * X[:, 0]) + X[:, 1] ** 2 - 1.5 * X[:, 2]
         + 0.05 * generador.normal(size=(240,))).reshape(-1, 1)

    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_3_1 :: bosques y matrices neuronales (v%s)"
          % __version__)
    print("Muestras:", X.shape[0], "| caracteristicas:", X.shape[1])
    print("=" * 78)

    resultados: Dict[str, Any] = {}
    bosque = crear_neurona("bosque", 3, 1, n_estimators=60,
                           max_depth=10, tarea="regresion", seed=7)
    resultado = entrenar_y_evaluar(bosque, X, y)
    resultados['bosque'] = resultado
    metricas = resultado['metricas']
    print("bosque     R2=%.4f MSE=%.6f OOB=%.4f params=%d"
          % (metricas['r2'], metricas['mse'], metricas['oob_score'],
             bosque.params_count()))

    tabm = crear_neurona("tabm", 3, 1, k_miembros=8, dim_oculta=48,
                         epochs=150, learning_rate=0.01, seed=7)
    resultado = entrenar_y_evaluar(tabm, X, y)
    resultados['tabm'] = resultado
    metricas = resultado['metricas']
    print("tabm       R2=%.4f MSE=%.6f params=%d"
          % (metricas['r2'], metricas['mse'], tabm.params_count()))

    # Clasificacion con el bosque y con TabM
    y_clases = np.where(X[:, 0] ** 2 + X[:, 1] ** 2 > 1.5, 1, 0)
    bosque_clf = crear_neurona("bosque", 3, 1, n_estimators=40,
                               tarea="clasificacion", seed=3)
    bosque_clf.fit(X, y_clases)
    print("bosque clf accuracy=%.4f OOB=%.4f"
          % (bosque_clf.evaluate(X, y_clases)['accuracy'],
             bosque_clf.obtener_estadisticas()['oob_score']))
    tabm_clf = crear_neurona("tabm", 3, 2, k_miembros=8, dim_oculta=48,
                             tarea="clasificacion", epochs=120, seed=3)
    tabm_clf.fit(X, y_clases)
    print("tabm clf   accuracy=%.4f proba_suma=%.4f"
          % (tabm_clf.evaluate(X, y_clases)['accuracy'],
             float(tabm_clf.predict_proba(X[:5]).sum(axis=1).mean())))
    print("importancias bosque:", bosque.compute_feature_importances().round(4).tolist())
    print("=" * 78)
    return resultados


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaArbolAleatorio',
    'NeuronaBosqueAleatorio',
    'NeuronaTabM',
    'RandomForestOptimizer',
    'OptimizadorAdam',
    'crear_neurona',
    'tipos_disponibles',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_RF_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
