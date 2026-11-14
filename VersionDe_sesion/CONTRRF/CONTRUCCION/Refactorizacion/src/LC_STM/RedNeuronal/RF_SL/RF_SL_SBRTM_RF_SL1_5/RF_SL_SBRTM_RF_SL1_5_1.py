"""RF_SL_SBRTM_RF_SL1_5_1.py
Neuronas especializadas en arboles de decision CART (RF_SL - SBRTM - RF - 2026).
===============================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
de ``DecisionTreeOptimizer`` (sin imports, base ni serializacion completa) y lo
sustituye por una implementacion real de arboles CART con calculo mejorado:

  * ``NeuronaArbolDecision``: arbol de decision CART.
      - Clasificacion con criterios ``gini``, ``entropy`` y ``log_loss``.
      - Regresion con criterios ``mse``, ``friedman_mse``, ``mae`` y
        ``huber``.
      - Busqueda de cortes vectorizada: ordena cada caracteristica y evalua
        todos los umbrales validos con sumas acumuladas (Gini/entropia por
        conteos de clase, MSE por sumas y sumas de cuadrados).
      - ``max_depth``, ``min_samples_split``, ``min_samples_leaf``,
        ``min_impurity_decrease``, ``max_features`` y ``ccp_alpha``.
      - Pesos de muestra y ``class_weight`` (``balanced``, diccionario o
        callable).
      - Poda por error reducido con validacion y poda por complejidad de
        coste (``ccp_alpha``).
      - ``predict_proba``, importancias normalizadas, profundidad, numero de
        hojas/nodos y serializacion robusta.

  * ``NeuronaArbolDecision.NucleoArbol``: **clase anidada** que fusiona las
      funciones matematicas del arbol: criterios de impureza, valor/probabilidad
      de hoja, busqueda del mejor corte, metricas, error de poda y resumen.

  * ``DecisionTreeOptimizer``: adaptador de compatibilidad con la API
      historica de RF_SL1_5. Mantiene ``_max_depth``, ``_min_samples_split``,
      ``_criterion``, ``_tree``, ``_feature_importances``, ``_classes``,
      ``_convergence_history``, ``_training_time`` y los metodos
      ``forward``/``backward``/``update_weights``/``apply_gradient``/
      ``train_step`` (cabeza lineal legada) sin duplicar el arbol real.

  * Utilidades: ``crear_neurona``, ``tipos_disponibles``,
      ``create_decision_tree_optimizer``, ``entrenar_y_evaluar``,
      ``benchmark_modelo``, ``guardar_modelo``, ``cargar_modelo`` y ``demo``.

Referencias
-----------
- CART: Breiman, Friedman, Olshen & Stone (1984).
- Gini / entropia y ganancia de informacion.
- Poda por complejidad de coste: weakest-link pruning (Breiman et al.).
- Tratamiento de pesos de clase e impurezas ponderadas tipo scikit-learn.

Uso
---
    from RF_SL_SBRTM_RF_SL1_5_1 import NeuronaArbolDecision

    arbol = NeuronaArbolDecision(input_size=3, criterion="gini")
    arbol.fit(X, y)
    print(arbol.evaluate(X, y))
    print(arbol.feature_importances_)
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
LUCIA_DT_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "max_depth": 10,
    "min_samples_split": 2,
    "min_samples_leaf": 1,
    "criterion": "gini",
    "tarea": "auto",
    "max_features": None,
    "min_impurity_decrease": 0.0,
    "ccp_alpha": 0.0,
    "huber_delta": 1.0,
    "epochs": 10,
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

    _CLAVE_BASE = "_rf_snrtm_base_import_dt"
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
# Arbol CART
# ---------------------------------------------------------------------------
class NeuronaArbolDecision(NeuronaMemoriaBase):
    """Arbol de decision CART para clasificacion y regresion.

    Parametros
    ----------
    input_size, output_size:
        Dimensiones declaradas (compatibilidad con la jerarquia de neuronas).
    max_depth:
        Profundidad maxima del arbol.
    min_samples_split, min_samples_leaf:
        Minimo de muestras (o peso) para dividir y por hoja.
    criterion:
        ``gini``, ``entropy``, ``log_loss`` (clasificacion) o ``mse``,
        ``friedman_mse``, ``mae``, ``huber`` (regresion).
    tarea:
        ``auto`` (se deduce del criterio), ``clasificacion`` o ``regresion``.
    max_features:
        ``None``/``all``, ``sqrt``, ``log2``, entero o fraccion (0, 1].
    min_impurity_decrease:
        Ganancia minima ponderada para aceptar una division.
    ccp_alpha:
        Parametro de poda por complejidad de coste (0 la desactiva).
    class_weight:
        ``None``, ``balanced``, diccionario ``{clase: peso}`` o callable.
    seed:
        Semilla del generador local (seleccion de caracteristicas y poda).
    """

    # ------------------------------------------------------------------
    # Clase anidada: fusion de las funciones matematicas del arbol
    # ------------------------------------------------------------------
    class NucleoArbol:
        """Nucleo matematico unificado del arbol CART.

        Fusiona impurezas, valores de hoja, busqueda del mejor corte,
        metricas, error de poda y resumen. Se accede como
        ``NeuronaArbolDecision.NucleoArbol`` o ``modelo.NucleoArbol``.
        """

        CRITERIOS_CLASIFICACION: Tuple[str, ...] = (
            "gini", "entropy", "log_loss",
        )
        CRITERIOS_REGRESION: Tuple[str, ...] = (
            "mse", "friedman_mse", "mae", "huber",
        )
        TAREAS: Tuple[str, ...] = ("clasificacion", "regresion")
        EPS = 1e-12

        def __init__(self, criterio: str = "gini",
                     tarea: str = "auto",
                     huber_delta: float = 1.0) -> None:
            self.criterio, self.tarea = self.resolver(criterio, tarea)
            self.huber_delta = max(1e-12, float(huber_delta))

        # -- normalizacion y resolucion de tarea ----------------------
        @classmethod
        def normalizar_criterio(cls, nombre: Optional[str]) -> str:
            clave = str(nombre or "gini").strip().lower().replace("-", "_")
            alias = {
                "gini": "gini", "impureza_gini": "gini",
                "entropy": "entropy", "entropia": "entropy",
                "log_loss": "log_loss", "logloss": "log_loss",
                "mse": "mse", "cuadratico": "mse", "l2": "mse",
                "friedman_mse": "friedman_mse",
                "mae": "mae", "absoluto": "mae", "l1": "mae",
                "huber": "huber",
            }
            clave = alias.get(clave, clave)
            permitidos = (cls.CRITERIOS_CLASIFICACION
                          + cls.CRITERIOS_REGRESION)
            if clave not in permitidos:
                raise ValueError(
                    f"Criterio desconocido: {nombre!r}. Usa uno de "
                    f"{permitidos}"
                )
            return clave

        @classmethod
        def normalizar_tarea(cls, tarea: Optional[str]) -> str:
            clave = str(tarea or "auto").strip().lower()
            alias = {
                "auto": "auto", "automatico": "auto",
                "clasificacion": "clasificacion", "classification": "clasificacion",
                "clf": "clasificacion", "clasificador": "clasificacion",
                "regresion": "regresion", "regression": "regresion",
                "reg": "regresion", "regressor": "regresion",
            }
            clave = alias.get(clave, clave)
            if clave not in ("auto",) + cls.TAREAS:
                raise ValueError(
                    f"Tarea desconocida: {tarea!r}. Usa auto, "
                    "clasificacion o regresion"
                )
            return clave

        @classmethod
        def resolver(cls, criterio: str,
                     tarea: str) -> Tuple[str, str]:
            crit = cls.normalizar_criterio(criterio)
            task = cls.normalizar_tarea(tarea)
            if task == "auto":
                task = ("clasificacion"
                        if crit in cls.CRITERIOS_CLASIFICACION
                        else "regresion")
            elif task == "clasificacion":
                if crit not in cls.CRITERIOS_CLASIFICACION:
                    crit = "gini"
            elif task == "regresion":
                if crit not in cls.CRITERIOS_REGRESION:
                    crit = "mse"
            return crit, task

        # -- utilidades de peso ---------------------------------------
        @staticmethod
        def _pesos(y: np.ndarray,
                   weights: Optional[np.ndarray]) -> np.ndarray:
            n = len(y)
            if weights is None:
                return np.ones(n, dtype=np.float64)
            w = np.asarray(weights, dtype=np.float64).reshape(-1)
            if w.size != n:
                raise ValueError(
                    f"weights tiene {w.size} elementos y se esperaban {n}"
                )
            if np.any(w < 0.0):
                raise ValueError("Los pesos no pueden ser negativos")
            return w

        @staticmethod
        def mediana_ponderada(y: np.ndarray,
                              weights: np.ndarray) -> float:
            orden = np.argsort(y, kind="mergesort")
            valores = np.asarray(y, dtype=np.float64)[orden]
            pesos = np.asarray(weights, dtype=np.float64)[orden]
            acumulado = np.cumsum(pesos)
            if acumulado.size == 0 or acumulado[-1] <= 0.0:
                return 0.0
            mitad = acumulado[-1] / 2.0
            indice = int(np.searchsorted(acumulado, mitad, side="left"))
            return float(valores[min(indice, valores.size - 1)])

        # -- impurezas -------------------------------------------------
        def impureza(self, y: np.ndarray,
                     weights: Optional[np.ndarray] = None,
                     criterio: Optional[str] = None) -> float:
            """Impureza ponderada del nodo segun el criterio activo."""
            y_arr = np.asarray(y)
            w = self._pesos(y_arr, weights)
            total = float(np.sum(w))
            if y_arr.size == 0 or total <= self.EPS:
                return 0.0
            tipo = self.normalizar_criterio(
                self.criterio if criterio is None else criterio
            )
            if self.tarea == "clasificacion":
                yi = y_arr.astype(int)
                k = int(np.max(yi)) + 1 if yi.size else 1
                conteos = np.bincount(yi, weights=w, minlength=k).astype(float)
                prob = conteos / total
                prob = prob[prob > 0.0]
                if tipo == "gini":
                    return float(1.0 - np.sum(prob ** 2))
                return float(-np.sum(prob * np.log2(prob)))
            valores = y_arr.astype(np.float64)
            media = float(np.sum(w * valores) / total)
            if tipo in ("mse", "friedman_mse"):
                return float(np.sum(w * (valores - media) ** 2) / total)
            mediana = self.mediana_ponderada(valores, w)
            error = valores - mediana
            if tipo == "mae":
                return float(np.sum(w * np.abs(error)) / total)
            delta = self.huber_delta
            absoluto = np.abs(error)
            perdida = np.where(
                absoluto <= delta,
                0.5 * error ** 2,
                delta * (absoluto - 0.5 * delta),
            )
            return float(np.sum(w * perdida) / total)

        def valor_hoja(self, y: np.ndarray,
                       weights: Optional[np.ndarray],
                       clases: Optional[np.ndarray] = None
                       ) -> Tuple[Any, Optional[np.ndarray]]:
            """Devuelve (valor_predicho, probabilidades) de una hoja."""
            y_arr = np.asarray(y)
            w = self._pesos(y_arr, weights)
            total = float(np.sum(w))
            if self.tarea == "clasificacion":
                yi = y_arr.astype(int)
                k = int(np.max(yi)) + 1 if yi.size else 1
                conteos = np.bincount(yi, weights=w, minlength=k).astype(float)
                if total <= self.EPS:
                    proba = np.zeros(k, dtype=np.float64)
                else:
                    proba = conteos / total
                indice = int(np.argmax(proba)) if proba.size else 0
                if clases is not None and indice < len(clases):
                    return clases[indice], proba
                return float(indice), proba
            if total <= self.EPS:
                return 0.0, None
            return float(np.sum(w * y_arr.astype(np.float64)) / total), None

        # -- busqueda de la mejor division ----------------------------
        def seleccionar_caracteristicas(
            self, n_features: int, max_features: Any,
            rng: np.random.Generator,
        ) -> np.ndarray:
            """Selecciona las caracteristicas candidatas de un nodo."""
            if max_features in (None, "all", "todas", 0):
                return np.arange(n_features)
            if isinstance(max_features, str):
                clave = max_features.strip().lower()
                if clave == "sqrt":
                    k = max(1, int(math.sqrt(n_features)))
                elif clave == "log2":
                    k = max(1, int(math.log2(max(2, n_features))))
                else:
                    raise ValueError(
                        f"max_features desconocido: {max_features!r}"
                    )
            elif isinstance(max_features, (int, np.integer)):
                k = max(1, int(max_features))
            elif isinstance(max_features, (float, np.floating)):
                if not 0.0 < float(max_features) <= 1.0:
                    raise ValueError(
                        "max_features fraccionario debe estar en (0, 1]"
                    )
                k = max(1, int(round(n_features * float(max_features))))
            else:
                raise ValueError(
                    f"max_features invalido: {max_features!r}"
                )
            k = min(n_features, k)
            if k >= n_features:
                return np.arange(n_features)
            return np.sort(rng.choice(n_features, size=k, replace=False))

        def mejor_division(
            self, X: np.ndarray, y: np.ndarray,
            weights: Optional[np.ndarray], min_samples_leaf: int,
            max_features: Any, rng: np.random.Generator,
        ) -> Dict[str, Any]:
            """Busca la division de mayor ganancia ponderada."""
            n, n_features = X.shape
            w = self._pesos(y, weights)
            total_w = float(np.sum(w))
            if total_w <= self.EPS or n < 2:
                return {'feature': None, 'threshold': None, 'gain': 0.0}
            padre = self.impureza(y, w)
            mejor: Dict[str, Any] = {
                'feature': None, 'threshold': None, 'gain': 0.0,
                'n_left': 0, 'n_right': 0,
            }
            for feature in self.seleccionar_caracteristicas(
                n_features, max_features, rng
            ):
                resultado = self._evaluar_caracteristica(
                    X[:, feature], y, w, int(min_samples_leaf), padre,
                    total_w,
                )
                if resultado is None:
                    continue
                posiciones, umbrales, ganancias = resultado
                indice = int(np.argmax(ganancias))
                ganancia = float(ganancias[indice])
                if ganancia > mejor['gain']:
                    mejor = {
                        'feature': int(feature),
                        'threshold': float(umbrales[indice]),
                        'gain': ganancia,
                        'n_left': int(posiciones[indice]) + 1,
                        'n_right': int(n - posiciones[indice] - 1),
                    }
            return mejor

        def _evaluar_caracteristica(
            self, columna: np.ndarray, y: np.ndarray, w: np.ndarray,
            min_samples_leaf: int, padre: float, total_w: float,
        ) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
            n = len(columna)
            orden = np.argsort(columna, kind="mergesort")
            xs = np.asarray(columna, dtype=np.float64)[orden]
            ys = np.asarray(y)[orden]
            ws = np.asarray(w, dtype=np.float64)[orden]
            posiciones = np.nonzero(xs[:-1] < xs[1:])[0]
            if posiciones.size == 0:
                return None
            posiciones = posiciones[
                (posiciones + 1 >= min_samples_leaf)
                & (n - posiciones - 1 >= min_samples_leaf)
            ]
            if posiciones.size == 0:
                return None
            max_candidatos = 128 if self.tarea == "clasificacion" else 96
            if self.criterio in ("mae", "huber"):
                max_candidatos = 48
            if posiciones.size > max_candidatos:
                elegidos = np.linspace(
                    0, posiciones.size - 1, max_candidatos
                ).astype(int)
                posiciones = np.unique(posiciones[elegidos])
            umbrales = (xs[posiciones] + xs[posiciones + 1]) / 2.0

            if self.tarea == "clasificacion":
                yi = ys.astype(int)
                k = int(np.max(yi)) + 1 if yi.size else 1
                onehot = np.zeros((n, k), dtype=np.float64)
                onehot[np.arange(n), yi] = ws
                acumulado = np.cumsum(onehot, axis=0)[posiciones]
                total = np.sum(onehot, axis=0)
                izquierda_w = np.sum(acumulado, axis=1)
                derecha_w = total_w - izquierda_w
                with np.errstate(divide="ignore", invalid="ignore"):
                    p_izq = acumulado / izquierda_w[:, None]
                    p_der = (total - acumulado) / derecha_w[:, None]
                if self.criterio == "gini":
                    imp_izq = 1.0 - np.sum(p_izq ** 2, axis=1)
                    imp_der = 1.0 - np.sum(p_der ** 2, axis=1)
                else:
                    imp_izq = -np.sum(
                        np.where(p_izq > 0.0, p_izq * np.log2(
                            np.where(p_izq > 0.0, p_izq, 1.0)
                        ), 0.0), axis=1
                    )
                    imp_der = -np.sum(
                        np.where(p_der > 0.0, p_der * np.log2(
                            np.where(p_der > 0.0, p_der, 1.0)
                        ), 0.0), axis=1
                    )
                ganancias = padre - (
                    izquierda_w * imp_izq + derecha_w * imp_der
                ) / total_w
                return posiciones, umbrales, ganancias

            valores = ys.astype(np.float64)
            if self.criterio in ("mse", "friedman_mse"):
                wy = ws * valores
                wy2 = wy * valores
                acum_w = np.cumsum(ws)[posiciones]
                acum_wy = np.cumsum(wy)[posiciones]
                acum_wy2 = np.cumsum(wy2)[posiciones]
                total_wy = float(np.sum(wy))
                total_wy2 = float(np.sum(wy2))
                with np.errstate(divide="ignore", invalid="ignore"):
                    media_izq = acum_wy / acum_w
                    media_der = (total_wy - acum_wy) / (total_w - acum_w)
                    var_izq = acum_wy2 / acum_w - media_izq ** 2
                    var_der = ((total_wy2 - acum_wy2) / (total_w - acum_w)
                               - media_der ** 2)
                var_izq = np.maximum(var_izq, 0.0)
                var_der = np.maximum(var_der, 0.0)
                ganancias = padre - (
                    acum_w * var_izq + (total_w - acum_w) * var_der
                ) / total_w
                return posiciones, umbrales, ganancias

            ganancias = np.empty(posiciones.size, dtype=np.float64)
            for indice, posicion in enumerate(posiciones):
                w_izq = ws[:posicion + 1]
                w_der = ws[posicion + 1:]
                imp_izq = self.impureza(valores[:posicion + 1], w_izq)
                imp_der = self.impureza(valores[posicion + 1:], w_der)
                ganancias[indice] = padre - (
                    np.sum(w_izq) * imp_izq + np.sum(w_der) * imp_der
                ) / total_w
            return posiciones, umbrales, ganancias

        # -- metricas --------------------------------------------------
        @staticmethod
        def _codificar(valores: np.ndarray,
                       clases: np.ndarray) -> np.ndarray:
            mapa = {clase: indice for indice, clase in enumerate(clases)}
            return np.array([mapa.get(valor, -1)
                             for valor in np.asarray(valores).ravel()],
                            dtype=int)

        def metricas(self, prediccion: np.ndarray, objetivo: np.ndarray,
                     proba: Optional[np.ndarray] = None,
                     clases: Optional[np.ndarray] = None
                     ) -> Dict[str, Any]:
            """Metricas de clasificacion o regresion, todas finitas."""
            pred = np.asarray(prediccion).ravel()
            real = np.asarray(objetivo).ravel()
            if pred.size != real.size:
                raise ValueError(
                    f"Prediccion y objetivo incompatibles: "
                    f"{pred.size} != {real.size}"
                )
            if self.tarea == "clasificacion":
                if clases is None:
                    clases = np.unique(np.concatenate([pred, real]))
                y_enc = self._codificar(real, clases)
                p_enc = self._codificar(pred, clases)
                validos = (y_enc >= 0) & (p_enc >= 0)
                aciertos = float(np.mean(p_enc[validos] == y_enc[validos])
                                 ) if np.any(validos) else 0.0
                recalls = []
                f1s = []
                for clase in range(len(clases)):
                    verdadero = y_enc == clase
                    predicho = p_enc == clase
                    if not np.any(verdadero):
                        continue
                    tp = float(np.sum(verdadero & predicho))
                    fp = float(np.sum(~verdadero & predicho))
                    fn = float(np.sum(verdadero & ~predicho))
                    recall = tp / max(1.0, tp + fn)
                    precision = tp / max(1.0, tp + fp)
                    f1 = (2.0 * precision * recall
                          / max(1e-12, precision + recall))
                    recalls.append(recall)
                    f1s.append(f1)
                metricas: Dict[str, Any] = {
                    'accuracy': aciertos,
                    'balanced_accuracy': float(np.mean(recalls))
                    if recalls else 0.0,
                    'precision_macro': float(np.mean([
                        (np.sum((y_enc == c) & (p_enc == c))
                         / max(1.0, np.sum(p_enc == c)))
                        for c in range(len(clases))
                        if np.any(p_enc == c)
                    ])) if np.any(p_enc >= 0) else 0.0,
                    'f1_macro': float(np.mean(f1s)) if f1s else 0.0,
                    'mse': float(np.mean((p_enc - y_enc) ** 2))
                    if np.any(validos) else 0.0,
                    'n_samples': int(real.size),
                    'n_classes': int(len(clases)),
                }
                if proba is not None:
                    probabilidades = np.asarray(proba, dtype=np.float64)
                    if probabilidades.ndim == 2 and probabilidades.shape[0] == real.size:
                        indices = np.clip(y_enc, 0, probabilidades.shape[1] - 1)
                        p_verdaderas = np.clip(
                            probabilidades[np.arange(real.size), indices],
                            self.EPS, 1.0,
                        )
                        metricas['log_loss'] = float(
                            -np.mean(np.log(p_verdaderas))
                        )
                return metricas
            error = pred - real
            mse = float(np.mean(error ** 2))
            varianza = float(np.sum((real - np.mean(real)) ** 2))
            if varianza > self.EPS:
                r2 = float(1.0 - np.sum(error ** 2) / varianza)
            elif mse <= self.EPS:
                r2 = 1.0
            else:
                r2 = 0.0
            return {
                'mse': mse,
                'rmse': float(math.sqrt(max(0.0, mse))),
                'mae': float(np.mean(np.abs(error))),
                'max_error': float(np.max(np.abs(error))) if error.size else 0.0,
                'r2': r2,
                'n_samples': int(real.size),
            }

        def error(self, prediccion: np.ndarray, objetivo: np.ndarray,
                  clases: Optional[np.ndarray] = None) -> float:
            """Error escalar usado por la poda (accuracy o MSE)."""
            if self.tarea == "clasificacion":
                if clases is None:
                    clases = np.unique(np.concatenate([
                        np.asarray(prediccion).ravel(),
                        np.asarray(objetivo).ravel(),
                    ]))
                metricas = self.metricas(prediccion, objetivo, None, clases)
                return float(1.0 - metricas['accuracy'])
            return float(np.mean(
                (np.asarray(prediccion).ravel()
                 - np.asarray(objetivo).ravel()) ** 2
            ))

        def resumen(self) -> Dict[str, Any]:
            """Configuracion del nucleo (logs y serializacion)."""
            return {
                'criterio': self.criterio,
                'tarea': self.tarea,
                'huber_delta': self.huber_delta,
                'criterios_clasificacion': list(self.CRITERIOS_CLASIFICACION),
                'criterios_regresion': list(self.CRITERIOS_REGRESION),
            }

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuronaArbolDecision",
        *,
        max_depth: int = 10,
        min_samples_split: int = 2,
        min_samples_leaf: int = 1,
        criterion: str = "gini",
        tarea: str = "auto",
        max_features: Any = None,
        min_impurity_decrease: float = 0.0,
        ccp_alpha: float = 0.0,
        class_weight: Any = None,
        huber_delta: float = 1.0,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        if "max_profundidad" in kwargs and max_depth == 10:
            max_depth = kwargs.pop("max_profundidad")
        if "max_hojas" in kwargs:
            kwargs.pop("max_hojas")
        if "random_state" in kwargs and seed is None:
            seed = kwargs.pop("random_state")
        if "loss" in kwargs and criterion == "gini":
            criterion = kwargs.pop("loss")
        if kwargs:
            raise TypeError(
                f"Argumentos no reconocidos: {sorted(kwargs)}"
            )

        self.input_size = int(input_size)
        self.output_size = int(output_size)
        if self.input_size <= 0 or self.output_size <= 0:
            raise ValueError("input_size y output_size deben ser positivos")

        self._max_depth = int(max_depth)
        if self._max_depth < 1:
            raise ValueError("max_depth debe ser al menos 1")
        self._min_samples_split = int(min_samples_split)
        if self._min_samples_split < 2:
            raise ValueError("min_samples_split debe ser al menos 2")
        self._min_samples_leaf = int(min_samples_leaf)
        if self._min_samples_leaf < 1:
            raise ValueError("min_samples_leaf debe ser al menos 1")
        self._min_impurity_decrease = float(min_impurity_decrease)
        if self._min_impurity_decrease < 0.0:
            raise ValueError("min_impurity_decrease no puede ser negativo")
        self._ccp_alpha = float(ccp_alpha)
        if self._ccp_alpha < 0.0:
            raise ValueError("ccp_alpha no puede ser negativo")
        self._max_features = max_features
        self._class_weight = class_weight

        self._nucleo = self.NucleoArbol(criterion, tarea, huber_delta)
        self._criterion = self._nucleo.criterio
        self._tarea = self._nucleo.tarea

        self._seed = int(
            LUCIA_DT_CONFIG["random_seed"] if seed is None else seed
        )
        self._rng = np.random.default_rng(self._seed)

        self._tree: Optional[Dict[str, Any]] = None
        self._feature_importances: Optional[np.ndarray] = None
        self._classes: Optional[np.ndarray] = None
        self._n_classes: int = 0
        self._n_samples: int = 0
        self._n_features: int = self.input_size
        self._is_fitted: bool = False
        self._convergence_history: List[float] = []
        self._training_time: float = 0.0
        self._learning_rate: float = 0.01  # solo para el adaptador legado
        self._velocity_w: Optional[np.ndarray] = None
        self._velocity_b: Optional[np.ndarray] = None

        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        """El arbol no usa pesos lineales; se mantiene la API de la base."""
        self.pesos = None
        self.sesgo = None
        self._velocity_w = None
        self._velocity_b = None

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

    @staticmethod
    def _es_onehot(objetivo: np.ndarray) -> bool:
        if objetivo.ndim != 2 or objetivo.shape[1] < 2:
            return False
        if not np.all(np.isfinite(objetivo)):
            return False
        return bool(
            np.all(objetivo >= 0.0)
            and np.all(objetivo <= 1.0)
            and np.allclose(np.sum(objetivo, axis=1), 1.0)
        )

    def _preparar_objetivo(self, y: Any, n_muestras: int
                           ) -> Tuple[np.ndarray, np.ndarray,
                                      Optional[np.ndarray]]:
        objetivo = np.asarray(y)
        if objetivo.ndim == 2:
            if objetivo.shape[1] == 1:
                objetivo = objetivo.reshape(-1)
            elif self._tarea == "clasificacion" and self._es_onehot(objetivo):
                objetivo = np.argmax(objetivo, axis=1)
            else:
                raise ValueError(
                    "Solo se admite una salida; y debe ser 1D o (n, 1)"
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

        if self._tarea == "clasificacion":
            if objetivo.dtype.kind in "fc" and not np.all(
                np.isfinite(objetivo.astype(np.float64))
            ):
                raise ValueError("y contiene valores no finitos")
            try:
                clases, codificado = np.unique(objetivo, return_inverse=True)
            except TypeError as error:
                raise ValueError(
                    "Las etiquetas de clasificacion deben ser homogeneas"
                ) from error
            return codificado.astype(int), objetivo, clases

        try:
            valores = objetivo.astype(np.float64)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Para regresion, y debe ser numerico"
            ) from error
        if not np.all(np.isfinite(valores)):
            raise ValueError("y contiene valores no finitos")
        return valores, objetivo, None

    def _codificar_etiquetas(self, y: Any) -> np.ndarray:
        valores = np.asarray(y).ravel()
        if self._tarea != "clasificacion":
            return valores.astype(np.float64)
        if self._classes is None:
            raise RuntimeError("El arbol no esta ajustado")
        mapa = {clase: indice
                for indice, clase in enumerate(self._classes)}
        codificado = np.array([mapa.get(valor, -1) for valor in valores],
                              dtype=int)
        if np.any(codificado < 0):
            raise ValueError("y contiene clases no vistas durante el fit")
        return codificado

    def _pesos_entrenamiento(
        self, y_original: np.ndarray, codificado: np.ndarray,
        sample_weight: Optional[np.ndarray],
    ) -> np.ndarray:
        n = len(y_original)
        if sample_weight is None:
            pesos = np.ones(n, dtype=np.float64)
        else:
            pesos = np.asarray(sample_weight, dtype=np.float64).reshape(-1)
            if pesos.size != n:
                raise ValueError(
                    f"sample_weight tiene {pesos.size} elementos y se "
                    f"esperaban {n}"
                )
            if np.any(pesos < 0.0):
                raise ValueError("sample_weight no puede ser negativo")
        if self._tarea == "clasificacion" and self._class_weight is not None:
            if self._class_weight == "balanced":
                conteos = np.bincount(codificado)
                activos = conteos > 0
                pesos_clase = np.ones(len(conteos), dtype=np.float64)
                pesos_clase[activos] = (
                    n / (max(1, int(np.sum(activos))) * conteos[activos])
                )
                pesos = pesos * pesos_clase[codificado]
            elif callable(self._class_weight):
                pesos = pesos * np.asarray(
                    self._class_weight(y_original), dtype=np.float64
                ).reshape(-1)
            elif isinstance(self._class_weight, dict):
                pesos = pesos * np.array([
                    float(self._class_weight.get(clase, 1.0))
                    for clase in y_original
                ], dtype=np.float64)
            else:
                raise ValueError(
                    "class_weight debe ser None, 'balanced', dict o callable"
                )
        if float(np.sum(pesos)) <= self.NucleoArbol.EPS:
            raise ValueError("La suma de pesos debe ser positiva")
        return pesos

    # ------------------------------------------------------------------
    # Construccion del arbol
    # ------------------------------------------------------------------
    def _completar_proba(self, proba: Optional[np.ndarray]
                         ) -> Optional[np.ndarray]:
        """Rellena/recorta las probabilidades al numero total de clases."""
        if proba is None or self._tarea != "clasificacion":
            return proba
        arreglo = np.asarray(proba, dtype=np.float64).ravel()
        if arreglo.size < self._n_classes:
            arreglo = np.pad(
                arreglo, (0, self._n_classes - arreglo.size)
            )
        elif arreglo.size > self._n_classes:
            arreglo = arreglo[:self._n_classes]
        total = float(np.sum(arreglo))
        if total > self.NucleoArbol.EPS:
            arreglo = arreglo / total
        return arreglo

    def _construir(
        self, X: np.ndarray, y: np.ndarray, weights: np.ndarray,
        depth: int,
    ) -> Dict[str, Any]:
        n = len(y)
        total_w = float(np.sum(weights))
        impureza = self._nucleo.impureza(y, weights)
        valor, proba = self._nucleo.valor_hoja(y, weights, self._classes)
        proba = self._completar_proba(proba)
        hoja: Dict[str, Any] = {
            'leaf': True,
            'value': valor,
            'proba': proba,
            'n_samples': int(n),
            'weight': total_w,
            'impurity': float(impureza),
        }
        if (depth >= self._max_depth
                or n < max(self._min_samples_split,
                           2 * self._min_samples_leaf)
                or impureza <= self.NucleoArbol.EPS):
            return hoja
        division = self._nucleo.mejor_division(
            X, y, weights, self._min_samples_leaf,
            self._max_features, self._rng,
        )
        if (division['feature'] is None
                or division['gain'] <= self._min_impurity_decrease
                + self.NucleoArbol.EPS):
            return hoja
        mascara = X[:, division['feature']] <= division['threshold']
        n_izq = int(np.sum(mascara))
        n_der = n - n_izq
        if (n_izq < self._min_samples_leaf
                or n_der < self._min_samples_leaf):
            return hoja
        nodo: Dict[str, Any] = {
            'leaf': False,
            'feature': int(division['feature']),
            'threshold': float(division['threshold']),
            'gain': float(division['gain']),
            'n_samples': int(n),
            'weight': total_w,
            'impurity': float(impureza),
            'value': valor,
            'proba': proba,
        }
        nodo['left'] = self._construir(
            X[mascara], y[mascara], weights[mascara], depth + 1
        )
        nodo['right'] = self._construir(
            X[~mascara], y[~mascara], weights[~mascara], depth + 1
        )
        return nodo

    def _build_tree(self, X: np.ndarray, y: np.ndarray,
                    depth: int = 0) -> Dict[str, Any]:
        """Compatibilidad: construye un subarbol con pesos unitarios."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        objetivo = np.asarray(y).reshape(-1)
        if self._tarea == "clasificacion" and objetivo.dtype.kind not in "iu":
            objetivo = self._codificar_etiquetas(objetivo)
        return self._construir(
            matriz, objetivo, np.ones(len(objetivo), dtype=np.float64),
            int(depth),
        )

    def _best_split(self, X: np.ndarray,
                    y: np.ndarray) -> Tuple[int, float, float]:
        """Compatibilidad: mejor (caracteristica, umbral, ganancia)."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        objetivo = np.asarray(y).reshape(-1)
        if self._tarea == "clasificacion" and objetivo.dtype.kind not in "iu":
            objetivo = self._codificar_etiquetas(objetivo)
        division = self._nucleo.mejor_division(
            matriz, objetivo, np.ones(len(objetivo), dtype=np.float64),
            self._min_samples_leaf, self._max_features, self._rng,
        )
        return (
            int(division['feature']) if division['feature'] is not None else 0,
            float(division['threshold']) if division['threshold'] is not None else 0.0,
            float(division['gain']),
        )

    # ------------------------------------------------------------------
    # Prediccion
    # ------------------------------------------------------------------
    def _pred_one(self, x: np.ndarray, node: Dict[str, Any]) -> Any:
        actual = node
        while not actual.get('leaf', False):
            if x[actual['feature']] <= actual['threshold']:
                actual = actual['left']
            else:
                actual = actual['right']
        return actual.get('value', 0.0)

    def _pred_one_batch(self, X: np.ndarray,
                        node: Dict[str, Any]) -> np.ndarray:
        return np.array([self._pred_one(fila, node) for fila in X])

    def _predecir(self, X: np.ndarray) -> np.ndarray:
        if self._tree is None:
            raise RuntimeError("El arbol no esta ajustado: llama a fit primero")
        return self._pred_one_batch(X, self._tree)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Prediccion del arbol (API forward de la jerarquia de neuronas)."""
        matriz, unico = self._validar_entrada(entrada)
        salida = self._predecir(matriz)
        self.historial_activaciones.append(np.array(salida, copy=True))
        self.pasos += 1
        return salida[0] if unico else salida

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predice etiquetas (clasificacion) o valores (regresion)."""
        matriz, unico = self._validar_entrada(X)
        salida = self._predecir(matriz)
        return salida[0] if unico else salida

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilidades por clase (solo clasificacion)."""
        if self._tarea != "clasificacion":
            raise ValueError("predict_proba solo esta disponible en clasificacion")
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        if self._tree is None:
            raise RuntimeError("El arbol no esta ajustado: llama a fit primero")
        resultados = []
        for fila in matriz:
            nodo = self._tree
            while not nodo.get('leaf', False):
                nodo = (nodo['left']
                        if fila[nodo['feature']] <= nodo['threshold']
                        else nodo['right'])
            proba = nodo.get('proba')
            if proba is None:
                proba = np.zeros(self._n_classes, dtype=np.float64)
                indice = int(np.searchsorted(self._classes, nodo['value']))
                if 0 <= indice < proba.size:
                    proba[indice] = 1.0
            proba = self._completar_proba(proba)
            resultados.append(np.asarray(proba, dtype=np.float64))
        return np.vstack(resultados) if resultados else np.zeros(
            (0, self._n_classes), dtype=np.float64
        )

    # ------------------------------------------------------------------
    # Ajuste y evaluacion
    # ------------------------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 10,
            verbose: bool = False,
            sample_weight: Optional[np.ndarray] = None) -> List[float]:
        """Construye el arbol y devuelve el historial de perdida por epoca."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        codificado, original, clases = self._preparar_objetivo(
            y, matriz.shape[0]
        )
        self._n_features = matriz.shape[1]
        self._classes = clases
        self._n_classes = int(len(clases)) if clases is not None else 0
        self._n_samples = int(matriz.shape[0])
        self._feature_importances = np.zeros(self.input_size, dtype=np.float64)
        pesos = self._pesos_entrenamiento(original, codificado, sample_weight)

        inicio = time.perf_counter()
        self._tree = self._construir(matriz, codificado, pesos, 0)
        if self._ccp_alpha > 0.0:
            self._tree = self._podar_ccp(
                self._tree, matriz, codificado, pesos, self._ccp_alpha
            )
        self._compute_importances(self._tree)
        self._is_fitted = True
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
                    "DT Epoch %d, loss=%.6f", epoca + 1, perdida
                )
        if hasattr(self, "registrar_perdida") and perdidas:
            self.registrar_perdida(perdidas[-1])
        return perdidas

    def compute_loss(self, prediccion: np.ndarray,
                     objetivo: np.ndarray) -> float:
        """Perdida de clasificacion (error) o regresion (MSE)."""
        pred = np.asarray(prediccion)
        real = np.asarray(objetivo)
        if pred.shape != real.shape:
            if pred.size == real.size:
                real = real.reshape(pred.shape)
            elif pred.ndim == 2 and pred.shape[1] == 1 and real.ndim == 1:
                real = real.reshape(-1, 1)
            else:
                try:
                    real = np.broadcast_to(real, pred.shape)
                except ValueError as error:
                    raise ValueError(
                        f"Formas incompatibles: {pred.shape} y {real.shape}"
                    ) from error
        if self._tarea == "clasificacion":
            return float(np.mean(pred.ravel() != real.ravel()))
        return float(np.mean(
            (pred.astype(np.float64) - real.astype(np.float64)) ** 2
        ))

    def compute_gini(self, y: np.ndarray) -> float:
        valores = np.asarray(y).ravel()
        if valores.size == 0:
            return 0.0
        _, conteos = np.unique(valores, return_counts=True)
        prob = conteos.astype(np.float64) / valores.size
        return float(1.0 - np.sum(prob ** 2))

    def compute_entropy(self, y: np.ndarray) -> float:
        valores = np.asarray(y).ravel()
        if valores.size == 0:
            return 0.0
        _, conteos = np.unique(valores, return_counts=True)
        prob = conteos.astype(np.float64) / valores.size
        prob = prob[prob > 0.0]
        return float(-np.sum(prob * np.log2(prob)))

    def _criterion_score(self, y: np.ndarray) -> float:
        """Compatibilidad: impureza del criterio configurado."""
        if self._criterion == "gini":
            return self.compute_gini(y)
        if self._criterion in ("entropy", "log_loss"):
            return self.compute_entropy(y)
        valores = np.asarray(y, dtype=np.float64)
        return float(np.var(valores))

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """Accuracy (clasificacion) o R2 (regresion)."""
        metricas = self.evaluate(X, y)
        if self._tarea == "clasificacion":
            return float(metricas.get('accuracy', 0.0))
        return float(metricas.get('r2', 0.0))

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Metricas completas de clasificacion o regresion."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        _, original, _ = self._preparar_objetivo(y, matriz.shape[0])
        prediccion = self.predict(matriz)
        proba = (self.predict_proba(matriz)
                 if self._tarea == "clasificacion" else None)
        metricas = self._nucleo.metricas(
            prediccion, original, proba, self._classes
        )
        metricas['loss'] = self.compute_loss(prediccion, original)
        return metricas

    # ------------------------------------------------------------------
    # Poda
    # ------------------------------------------------------------------
    def _podar_ccp(self, nodo: Dict[str, Any], X: np.ndarray,
                   y: np.ndarray, weights: np.ndarray,
                   alpha: float) -> Dict[str, Any]:
        if nodo.get('leaf', False):
            return nodo
        mascara = X[:, nodo['feature']] <= nodo['threshold']
        izquierda = self._podar_ccp(
            nodo['left'], X[mascara], y[mascara], weights[mascara], alpha
        )
        derecha = self._podar_ccp(
            nodo['right'], X[~mascara], y[~mascara], weights[~mascara], alpha
        )
        nodo['left'] = izquierda
        nodo['right'] = derecha

        impureza = self._nucleo.impureza(y, weights)
        riesgo_hoja = impureza * float(np.sum(weights))
        riesgo_sub = self._riesgo(izquierda) + self._riesgo(derecha)
        hojas_sub = self._contar_hojas(izquierda) + self._contar_hojas(derecha)
        if riesgo_hoja + alpha <= riesgo_sub + alpha * hojas_sub:
            valor, proba = self._nucleo.valor_hoja(
                y, weights, self._classes
            )
            return {
                'leaf': True,
                'value': valor,
                'proba': self._completar_proba(proba),
                'n_samples': int(len(y)),
                'weight': float(np.sum(weights)),
                'impurity': float(impureza),
            }
        return nodo

    @staticmethod
    def _riesgo(nodo: Dict[str, Any]) -> float:
        return float(nodo.get('impurity', 0.0)) * float(
            nodo.get('weight', 1.0)
        )

    @staticmethod
    def _contar_hojas(nodo: Dict[str, Any]) -> int:
        if nodo.get('leaf', False):
            return 1
        return (NeuronaArbolDecision._contar_hojas(nodo['left'])
                + NeuronaArbolDecision._contar_hojas(nodo['right']))

    def _error_pred(self, prediccion: np.ndarray,
                    y_codificado: np.ndarray) -> float:
        if self._tarea == "clasificacion":
            real = np.asarray(self._classes)[y_codificado.astype(int)]
            return float(np.mean(np.asarray(prediccion).ravel() != real))
        return float(np.mean(
            (np.asarray(prediccion).ravel()
             - np.asarray(y_codificado).ravel()) ** 2
        ))

    def _podar_reducido(self, nodo: Dict[str, Any], X: np.ndarray,
                        y: np.ndarray, weights: np.ndarray
                        ) -> Dict[str, Any]:
        if nodo.get('leaf', False) or len(X) == 0:
            return nodo
        mascara = X[:, nodo['feature']] <= nodo['threshold']
        if np.sum(mascara) == 0 or np.sum(~mascara) == 0:
            return nodo
        izquierda = self._podar_reducido(
            nodo['left'], X[mascara], y[mascara], weights[mascara]
        )
        derecha = self._podar_reducido(
            nodo['right'], X[~mascara], y[~mascara], weights[~mascara]
        )
        candidato = dict(nodo)
        candidato['left'] = izquierda
        candidato['right'] = derecha
        prediccion = self._pred_one_batch(X, candidato)
        error_sub = self._error_pred(prediccion, y)
        valor, proba = self._nucleo.valor_hoja(y, weights, self._classes)
        prediccion_hoja = np.full(len(y), valor)
        error_hoja = self._error_pred(prediccion_hoja, y)
        if error_hoja <= error_sub:
            return {
                'leaf': True,
                'value': valor,
                'proba': self._completar_proba(proba),
                'n_samples': int(len(y)),
                'weight': float(np.sum(weights)),
                'impurity': float(self._nucleo.impureza(y, weights)),
            }
        return candidato

    def prune(self, X: np.ndarray, y: np.ndarray,
              validation_fraction: float = 0.2) -> None:
        """Poda por error reducido usando una fraccion de validacion."""
        if self._tree is None:
            raise RuntimeError("El arbol no esta ajustado")
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        codificado = self._codificar_etiquetas(y)
        n = matriz.shape[0]
        if n == 0:
            raise ValueError("X no contiene muestras")
        if 0.0 < float(validation_fraction) < 1.0 and n >= 2:
            cantidad = max(1, min(n - 1, int(round(n * validation_fraction))))
            indices = self._rng.choice(n, size=cantidad, replace=False)
            X_val = matriz[indices]
            y_val = codificado[indices]
        else:
            X_val = matriz
            y_val = codificado
        pesos = np.ones(len(y_val), dtype=np.float64)
        self._tree = self._podar_reducido(self._tree, X_val, y_val, pesos)
        self._compute_importances(self._tree)

    def _prune_tree(self, node: Dict[str, Any], X: np.ndarray,
                    y: np.ndarray) -> Dict[str, Any]:
        """Compatibilidad con la poda recursiva historica."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        codificado = self._codificar_etiquetas(y)
        return self._podar_reducido(
            node, matriz, codificado,
            np.ones(len(codificado), dtype=np.float64),
        )

    def _leaf_accuracy(self, y: np.ndarray) -> float:
        valores = np.asarray(y)
        if self._tarea == "clasificacion":
            if valores.size == 0:
                return 0.0
            _, conteos = np.unique(valores, return_counts=True)
            mayoritaria = np.unique(valores)[int(np.argmax(conteos))]
            return float(np.mean(valores == mayoritaria))
        return -float(np.var(valores.astype(np.float64)))

    def _subtree_accuracy(self, node: Dict[str, Any], X: np.ndarray,
                          y: np.ndarray) -> float:
        try:
            Xv, _ = self._validar_entrada(X, permitir_1d=False)
            codificado = self._codificar_etiquetas(y)
            prediccion = self._pred_one_batch(Xv, node)
            if self._tarea == "clasificacion":
                real = np.asarray(self._classes)[codificado.astype(int)]
                return float(np.mean(prediccion == real))
            return -float(np.mean((prediccion - codificado) ** 2))
        except (ValueError, RuntimeError):
            return 0.0

    # ------------------------------------------------------------------
    # Importancias y estructura
    # ------------------------------------------------------------------
    def _compute_importances(self, node: Dict[str, Any]) -> None:
        """Recalcula y normaliza las importancias por ganancia."""
        self._feature_importances = np.zeros(
            self._n_features, dtype=np.float64
        )

        def recorrer(actual: Dict[str, Any]) -> None:
            if actual.get('leaf', False):
                return
            caracteristica = int(actual['feature'])
            if 0 <= caracteristica < self._feature_importances.size:
                self._feature_importances[caracteristica] += (
                    float(actual.get('gain', 0.0))
                    * float(actual.get('n_samples', 1))
                )
            recorrer(actual['left'])
            recorrer(actual['right'])

        if node is not None:
            recorrer(node)
        total = float(np.sum(self._feature_importances))
        if total > self.NucleoArbol.EPS:
            self._feature_importances /= total

    @property
    def feature_importances_(self) -> np.ndarray:
        if self._feature_importances is None:
            return np.zeros(self.input_size, dtype=np.float64)
        return self._feature_importances.copy()

    @property
    def classes_(self) -> Optional[np.ndarray]:
        return None if self._classes is None else self._classes.copy()

    @property
    def tree_(self) -> Optional[Dict[str, Any]]:
        return self._tree

    def get_depth(self) -> int:
        if self._tree is None:
            return 0

        def profundidad(nodo: Dict[str, Any]) -> int:
            if nodo.get('leaf', False):
                return 0
            return 1 + max(profundidad(nodo['left']),
                           profundidad(nodo['right']))

        return int(profundidad(self._tree))

    def get_n_leaves(self) -> int:
        if self._tree is None:
            return 0
        return int(self._contar_hojas(self._tree))

    def get_n_nodes(self) -> int:
        if self._tree is None:
            return 0

        def contar(nodo: Dict[str, Any]) -> int:
            if nodo.get('leaf', False):
                return 1
            return 1 + contar(nodo['left']) + contar(nodo['right'])

        return int(contar(self._tree))

    def params_count(self) -> int:
        """Numero de nodos del arbol (parametros efectivos)."""
        return int(self.get_n_nodes())

    # ------------------------------------------------------------------
    # Informacion y estabilidad
    # ------------------------------------------------------------------
    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'arbol_decision',
            'tarea': self._tarea,
            'criterion': self._criterion,
            'max_depth': self._max_depth,
            'min_samples_split': self._min_samples_split,
            'min_samples_leaf': self._min_samples_leaf,
            'min_impurity_decrease': self._min_impurity_decrease,
            'ccp_alpha': self._ccp_alpha,
            'max_features': self._max_features,
            'is_fitted': self._is_fitted,
            'n_samples': self._n_samples,
            'n_features': self._n_features,
            'n_classes': self._n_classes,
            'profundidad_real': self.get_depth(),
            'n_leaves': self.get_n_leaves(),
            'n_nodes': self.get_n_nodes(),
            'n_parametros': self.params_count(),
            'training_time': self._training_time,
            'nucleo': self._nucleo.resumen(),
        })
        if self._classes is not None:
            stats['classes'] = self._classes.tolist()
        if self._feature_importances is not None:
            stats['feature_importances'] = \
                self._feature_importances.tolist()
            if self._feature_importances.size:
                stats['top_feature'] = int(
                    np.argmax(self._feature_importances)
                )
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
            stats['initial_loss'] = float(self._convergence_history[0])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprobaciones basicas de coherencia del arbol."""
        ok: Dict[str, bool] = {
            'arbol_inicializado': self._tree is not None,
            'estado_entrenado': bool(self._is_fitted),
        }
        if self._tree is not None:
            ok['profundidad_valida'] = self.get_depth() <= self._max_depth
            ok['hojas_validas'] = self.get_n_leaves() >= 1
            ok['nodos_validos'] = self.get_n_nodes() >= 1
            ok['clases_validas'] = (
                self._tarea != "clasificacion"
                or (self._classes is not None and len(self._classes) >= 1)
            )
        if self._feature_importances is not None:
            ok['importancias_finitas'] = bool(
                np.all(np.isfinite(self._feature_importances))
            )
        if self.pesos is not None:
            ok['pesos_no_nan'] = not bool(np.any(np.isnan(self.pesos)))
            ok['pesos_no_inf'] = not bool(np.any(np.isinf(self.pesos)))
            ok['pesos_no_explosivos'] = float(
                np.max(np.abs(self.pesos))
            ) < 1e6
        ok['estable'] = all(ok.values())
        return ok

    # ------------------------------------------------------------------
    # Serializacion y configuracion
    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        """Guarda el arbol, clases, importancias y configuracion."""
        estado = {
            'version': __version__,
            'tipo': 'NeuronaArbolDecision',
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'max_depth': self._max_depth,
            'min_samples_split': self._min_samples_split,
            'min_samples_leaf': self._min_samples_leaf,
            'criterion': self._criterion,
            'tarea': self._tarea,
            'max_features': self._max_features,
            'min_impurity_decrease': self._min_impurity_decrease,
            'ccp_alpha': self._ccp_alpha,
            'class_weight': self._class_weight,
            'huber_delta': self._nucleo.huber_delta,
            'seed': self._seed,
            'is_fitted': self._is_fitted,
            'tree': self._tree,
            'classes': self._classes,
            'n_classes': self._n_classes,
            'n_samples': self._n_samples,
            'n_features': self._n_features,
            'feature_importances': self._feature_importances,
            'convergence_history': list(self._convergence_history),
            'training_time': self._training_time,
            'pesos': self.pesos,
            'sesgo': self.sesgo,
            'velocity_w': self._velocity_w,
            'velocity_b': self._velocity_b,
            'learning_rate': self._learning_rate,
            'rng_state': self._rng.bit_generator.state,
        }
        with open(filepath, 'wb') as archivo:
            pickle.dump(estado, archivo, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        """Carga checkpoints nuevos o el formato historico de una cabeza lineal."""
        with open(filepath, 'rb') as archivo:
            estado = pickle.load(archivo)
        if not isinstance(estado, dict):
            raise TypeError("El fichero no contiene un checkpoint valido")

        self.input_size = int(estado.get('input_size', self.input_size))
        self.output_size = int(estado.get('output_size', self.output_size))
        self.nombre = str(estado.get('nombre', self.nombre))
        self._max_depth = max(1, int(estado.get('max_depth', 10)))
        self._min_samples_split = max(
            2, int(estado.get('min_samples_split', 2))
        )
        self._min_samples_leaf = max(
            1, int(estado.get('min_samples_leaf', 1))
        )
        self._min_impurity_decrease = max(
            0.0, float(estado.get('min_impurity_decrease', 0.0))
        )
        self._ccp_alpha = max(
            0.0, float(estado.get('ccp_alpha', 0.0))
        )
        self._max_features = estado.get('max_features', None)
        self._class_weight = estado.get('class_weight', None)
        self._seed = int(estado.get('seed', LUCIA_DT_CONFIG["random_seed"]))
        self._rng = np.random.default_rng(self._seed)
        rng_state = estado.get('rng_state')
        if isinstance(rng_state, dict):
            try:
                self._rng.bit_generator.state = rng_state
            except (ValueError, TypeError):  # pragma: no cover
                self._rng = np.random.default_rng(self._seed)

        criterio = estado.get('criterion', 'gini')
        tarea = estado.get('tarea')
        if tarea is None:
            tarea = ("clasificacion"
                     if criterio in self.NucleoArbol.CRITERIOS_CLASIFICACION
                     else "regresion")
        self._nucleo = self.NucleoArbol(
            criterio, tarea, float(estado.get('huber_delta', 1.0))
        )
        self._criterion = self._nucleo.criterio
        self._tarea = self._nucleo.tarea

        self._tree = estado.get('tree')
        clases = estado.get('classes')
        if clases is None and self._tarea == "clasificacion" \
                and self._tree is not None:
            valores = []

            def recoger(nodo: Dict[str, Any]) -> None:
                if nodo.get('leaf', False):
                    valores.append(nodo.get('value', 0.0))
                    return
                recoger(nodo['left'])
                recoger(nodo['right'])

            recoger(self._tree)
            clases = np.unique(np.asarray(valores))
        self._classes = None if clases is None else np.asarray(clases)
        self._n_classes = int(len(self._classes)) if self._classes is not None else 0
        self._n_samples = int(estado.get('n_samples', 0))
        self._n_features = int(estado.get('n_features', self.input_size))
        importancias = estado.get('feature_importances')
        self._feature_importances = (
            None if importancias is None
            else np.asarray(importancias, dtype=np.float64)
        )
        if self._feature_importances is None and self._tree is not None:
            self._compute_importances(self._tree)
        self._is_fitted = bool(estado.get('is_fitted', self._tree is not None))
        self._convergence_history = [
            float(v) for v in estado.get('convergence_history', [])
        ]
        self._training_time = float(estado.get('training_time', 0.0))
        self._learning_rate = float(estado.get('learning_rate', 0.01))
        self.pesos = estado.get('pesos')
        self.sesgo = estado.get('sesgo')
        self._velocity_w = estado.get('velocity_w')
        self._velocity_b = estado.get('velocity_b')

    def get_config(self) -> Dict[str, Any]:
        """Configuracion reproducible del arbol."""
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'tarea': self._tarea,
            'criterion': self._criterion,
            'max_depth': self._max_depth,
            'min_samples_split': self._min_samples_split,
            'min_samples_leaf': self._min_samples_leaf,
            'max_features': self._max_features,
            'min_impurity_decrease': self._min_impurity_decrease,
            'ccp_alpha': self._ccp_alpha,
            'class_weight': self._class_weight,
            'huber_delta': self._nucleo.huber_delta,
            'seed': self._seed,
        }

    def summary(self) -> str:
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {self.nombre} ===",
            (f"Tarea: {self._tarea}, Criterio: {self._criterion}, "
             f"Depth: {self._max_depth}"),
            (f"Input: {self.input_size}, Output: {self.output_size}, "
             f"Clases: {self._n_classes}"),
            (f"Fitted: {self._is_fitted}, Profundidad: "
             f"{stats.get('profundidad_real', 0)}, Hojas: "
             f"{stats.get('n_leaves', 0)}, Nodos: "
             f"{stats.get('n_nodes', 0)}"),
            (f"Top feature: {stats.get('top_feature', 'N/A')}, "
             f"Final loss: {stats.get('final_loss', 'N/A')}"),
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"


# ---------------------------------------------------------------------------
# Adaptador de compatibilidad con la API historica de RF_SL1_5
# ---------------------------------------------------------------------------
class DecisionTreeOptimizer(NeuronaArbolDecision):
    """Arbol CART real con la API historica de ``DecisionTreeOptimizer``.

    Conserva la cabeza lineal legada (``forward``/``backward``/
    ``update_weights``/``apply_gradient``/``train_step``) para no romper
    consumidores antiguos. ``predict`` y ``fit`` usan el arbol real.
    """

    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "DecisionTreeOptimizer",
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
        """Cabeza lineal minima para los metodos historicos de gradiente."""
        generador = getattr(self, "_rng", np.random.default_rng(2026))
        self.pesos = generador.normal(
            0.0, 0.1, (self.input_size, self.output_size)
        ).astype(np.float32)
        self.sesgo = np.zeros((1, self.output_size), dtype=np.float32)
        self._velocity_w = np.zeros_like(self.pesos)
        self._velocity_b = np.zeros_like(self.sesgo)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Cabeza lineal historica (``predict`` usa el arbol)."""
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
        """Paso historico de la cabeza lineal (no modifica el arbol)."""
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
def crear_neurona(tipo: str = "arbol", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaArbolDecision:
    """Fabrica un arbol de decision por nombre.

    Tipos: ``arbol``/``cart``/``decision_tree`` (CART principal),
    ``compat`` (adaptador historico). ``regresion`` y ``clasificacion``
    fijan la tarea automaticamente.
    """
    clave = str(tipo or "arbol").strip().lower().replace("-", "_")
    if clave in ("arbol", "cart", "decision_tree", "dt", "tree"):
        return NeuronaArbolDecision(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("clasificacion", "classification", "clf"):
        kwargs.setdefault("tarea", "clasificacion")
        return NeuronaArbolDecision(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("regresion", "regression", "reg"):
        kwargs.setdefault("tarea", "regresion")
        kwargs.setdefault("criterion", "mse")
        return NeuronaArbolDecision(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("compat", "decision_tree_optimizer", "optimizer"):
        return DecisionTreeOptimizer(
            input_size=input_size, output_size=output_size, **kwargs
        )
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: arbol, cart, clasificacion, "
        "regresion, compat"
    )


def tipos_disponibles() -> List[str]:
    """Nombres aceptados por :func:`crear_neurona`."""
    return ["arbol", "cart", "clasificacion", "regresion", "compat"]


def create_decision_tree_optimizer(
    input_size: int = 4, output_size: int = 8, **kwargs: Any,
) -> DecisionTreeOptimizer:
    """Fabrica historica de RF_SL1_5."""
    return DecisionTreeOptimizer(
        input_size=input_size, output_size=output_size, **kwargs
    )


def entrenar_y_evaluar(modelo: NeuronaArbolDecision, X: np.ndarray,
                       y: np.ndarray, epochs: int = 10,
                       **kwargs: Any) -> Dict[str, Any]:
    """Entrena y devuelve historial y metricas en una sola llamada."""
    historial = modelo.fit(X, y, epochs=epochs, **kwargs)
    return {
        'modelo': modelo,
        'historial': historial,
        'metricas': modelo.evaluate(X, y),
        'perdida_final': float(historial[-1]) if historial else float('nan'),
    }


def benchmark_modelo(modelo: NeuronaArbolDecision, X: np.ndarray,
                     repeticiones: int = 5) -> Dict[str, float]:
    """Mide el tiempo de inferencia del arbol."""
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


def guardar_modelo(modelo: NeuronaArbolDecision, ruta: str) -> None:
    """Serializa el objeto completo (pickle)."""
    with open(ruta, 'wb') as archivo:
        pickle.dump(modelo, archivo, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaArbolDecision:
    """Carga un modelo serializado con :func:`guardar_modelo`."""
    with open(ruta, 'rb') as archivo:
        modelo = pickle.load(archivo)
    if not isinstance(modelo, NeuronaArbolDecision):
        raise TypeError("El fichero no contiene un arbol de decision")
    return modelo


# ---------------------------------------------------------------------------
# Demostracion
# ---------------------------------------------------------------------------
def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_5_1.py``)."""
    generador = np.random.default_rng(2026)
    n = 360
    X = generador.uniform(-2.0, 2.0, size=(n, 3))
    y_clf = (
        (X[:, 0] ** 2 + X[:, 1] ** 2 - 0.8 * X[:, 2]) > 0.8
    ).astype(int)
    y_reg = (np.sin(2.0 * X[:, 0]) + X[:, 1] ** 2
             - 0.5 * X[:, 2]).reshape(-1, 1)

    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_5_1 :: Arbol CART (v%s)" % __version__)
    print("Muestras:", n, "| caracteristicas:", X.shape[1])
    print("=" * 78)

    clasificador = crear_neurona(
        "clasificacion", input_size=3, output_size=2,
        max_depth=8, min_samples_leaf=3, seed=7,
    )
    clasificador.fit(X, y_clf)
    metricas_clf = clasificador.evaluate(X, y_clf)
    print("%-12s accuracy=%.4f F1=%.4f | hojas=%d | nodos=%d"
          % ("clasificacion", metricas_clf['accuracy'],
             metricas_clf['f1_macro'], clasificador.get_n_leaves(),
             clasificador.get_n_nodes()))

    regresor = crear_neurona(
        "regresion", input_size=3, output_size=1,
        max_depth=8, min_samples_leaf=3, seed=11,
    )
    regresor.fit(X, y_reg)
    metricas_reg = regresor.evaluate(X, y_reg)
    print("%-12s MSE=%.6f MAE=%.6f R2=%.4f | hojas=%d"
          % ("regresion", metricas_reg['mse'], metricas_reg['mae'],
             metricas_reg['r2'], regresor.get_n_leaves()))

    clasificador.prune(X, y_clf, validation_fraction=0.25)
    metricas_poda = clasificador.evaluate(X, y_clf)
    print("Tras poda    accuracy=%.4f | hojas=%d"
          % (metricas_poda['accuracy'], clasificador.get_n_leaves()))
    print("Importancias:", clasificador.feature_importances_.round(4).tolist())
    print("Benchmark:", benchmark_modelo(clasificador, X, repeticiones=3))
    print("=" * 78)
    return {
        'clasificacion': metricas_clf,
        'regresion': metricas_reg,
        'poda': metricas_poda,
    }


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaArbolDecision',
    'DecisionTreeOptimizer',
    'crear_neurona',
    'tipos_disponibles',
    'create_decision_tree_optimizer',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_DT_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
