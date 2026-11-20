"""RF_SL_SBRTM_RF_SL1_1_1.py
Neuronas especializadas en Gradient Boosting (RF_SL · SBRTM · RF · 2026).
=============================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
(que solo tenia una neurona lineal llamada ``GradientBoostingOptimizer``, sin
imports ni metodos de evaluacion) y lo sustituye por una implementacion real
de boosting con algoritmos de calculo mejorados:

  * ``NeuronaArbolGradiente``: arbol debil de gradiente de segundo orden.
      - Expansion de Taylor (gradiente + hessiano) y hoja Newton:
        ``w* = -soft_threshold(G, alpha) / (H + lambda)``.
      - Cortes por histograma de cuantiles (estilo LightGBM) en lugar de
        explorar todos los umbrales.
      - Crecimiento hoja a hoja (leaf-wise) con ``max_leaves`` y cola de
        prioridad por ganancia.
      - Regularizacion L2 (``lambda``), L1 (``alpha``) y ``gamma`` minimo.
      - Submuestreo de caracteristicas por division (``max_features``).
      - Importancias por ganancia acumulada.

  * ``NeuronaArbolLinealGradiente``: variante con hojas lineales (piecewise
      linear). La estructura se elige con la ganancia de segundo orden y cada
      hoja resuelve una regresion ridge ponderada por el hessiano:
      ``beta = (X^T W X + lambda I)^-1 X^T W z`` con ``z = -g/h``.

  * ``NeuronaGradienteBoosting``: ensemble de boosting.
      - Perdidas: MSE, Huber y logistica binaria.
      - Multi-salida (un ensemble independiente por salida).
      - Shrinkage (learning rate), subsample de filas, colsample de columnas.
      - Early stopping con validacion y rollback al mejor iteracion.
      - Base lineal ridge opcional (mejora el arranque en problemas suaves).
      - Importancias, estadisticas, serializacion y comprobacion de estabilidad.

  * ``GradientBoostingOptimizer``: adaptador de compatibilidad con la API
      historica de RF_SL1_1 (``fit``/``train``/``forward``/``compute_loss``/
      ``compute_gradient``/``backward``/``update_weights``/``apply_gradient``/
      ``train_step``), ahora respaldada por el boosting real.

La base ``NeuronaMemoriaBase`` se importa del modulo especializado
``RF_SL_SBRTM_RF_rfsl_base/RF_SL_SNRTM__rfsl_base1.py`` (con fallback por
ruta y, en ultimo termino, una base local minima), de modo que no se duplica
la jerarquia de neuronas.

Uso rapido
----------
    from RF_SL_SBRTM_RF_SL1_1_1 import NeuronaGradienteBoosting

    modelo = NeuronaGradienteBoosting(input_size=3, output_size=1,
                                      n_estimators=200, learning_rate=0.1)
    modelo.fit(X, y, validation_split=0.2, early_stopping=True)
    print(modelo.evaluate(X, y))
    print(modelo.importancias())

    # hojas lineales
    modelo = NeuronaGradienteBoosting(..., tipo_arbol="lineal")
"""

from __future__ import annotations

import heapq
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
LUCIA_GB_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "n_estimators": 100,
    "learning_rate": 0.1,
    "max_depth": 3,
    "max_leaves": None,
    "min_samples_leaf": 5,
    "reg_lambda": 1.0,
    "reg_alpha": 0.0,
    "gamma": 0.0,
    "n_bins": 32,
    "subsample": 1.0,
    "colsample": 1.0,
    "loss": "mse",
    "huber_delta": 1.0,
    "patience": 20,
    "reg_lambda_base": 1e-3,
    "reg_lambda_hoja": 1.0,
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

    _CLAVE_BASE = "_rf_snrtm_base_import_gb"
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

        class NeuronaMemoriaBase:  # type: ignore[no-redef]
            """Base de neurona con memoria acotada (fallback minimo)."""

            def __init__(self, input_size: int, output_size: int,
                         nombre: str = "Neurona"):
                self.input_size = int(input_size)
                self.output_size = int(output_size)
                self.nombre = str(nombre)
                self.pesos: Optional[np.ndarray] = None
                self.sesgo: Optional[np.ndarray] = None
                from collections import deque
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
                arreglos = self._arreglos_parametros()
                for indice, arreglo in enumerate(arreglos):
                    if arreglo.size and not np.all(np.isfinite(arreglo)):
                        problemas.append(f"parametro #{indice} no finito")
                return {
                    'estable': not problemas,
                    'problemas': problemas,
                    'norma_pesos': float(math.sqrt(sum(
                        float(np.sum(np.square(a))) for a in arreglos
                    ))),
                    'n_parametros': self.params_count(),
                }


# ---------------------------------------------------------------------------
# Utilidades numericas y de perdida
# ---------------------------------------------------------------------------
def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def _soft_threshold(valor: float, alfa: float) -> float:
    """Umbral suave L1: signo(v) * max(|v| - alfa, 0)."""
    if valor > alfa:
        return valor - alfa
    if valor < -alfa:
        return valor + alfa
    return 0.0


def _validar_datos(X: Any, y: Any, input_size: int,
                   output_size: int) -> Tuple[np.ndarray, np.ndarray]:
    matriz = np.asarray(X, dtype=np.float64)
    objetivo = np.asarray(y, dtype=np.float64)
    if matriz.ndim != 2:
        raise ValueError("X debe ser una matriz 2D (muestras, caracteristicas)")
    if matriz.shape[0] == 0:
        raise ValueError("X no contiene muestras")
    if matriz.shape[1] != input_size:
        raise ValueError(
            f"X tiene {matriz.shape[1]} caracteristicas y se esperaban {input_size}"
        )
    if objetivo.ndim == 1:
        objetivo = objetivo.reshape(-1, 1)
    if objetivo.ndim != 2:
        raise ValueError("y debe ser un vector o una matriz 2D")
    if objetivo.shape[0] != matriz.shape[0]:
        raise ValueError("X e y deben tener el mismo numero de muestras")
    if objetivo.shape[1] != output_size:
        raise ValueError(
            f"y tiene {objetivo.shape[1]} salidas y se esperaban {output_size}"
        )
    if not np.all(np.isfinite(matriz)):
        matriz = np.nan_to_num(matriz, nan=0.0, posinf=0.0, neginf=0.0)
    if not np.all(np.isfinite(objetivo)):
        objetivo = np.nan_to_num(objetivo, nan=0.0, posinf=0.0, neginf=0.0)
    return matriz, objetivo


def _perdida(nombre: str, predicion: np.ndarray, objetivo: np.ndarray,
             delta: float = 1.0) -> float:
    if nombre == "logistic":
        p = np.clip(_sigmoide(predicion), 1e-12, 1.0 - 1e-12)
        return float(-np.mean(objetivo * np.log(p)
                              + (1.0 - objetivo) * np.log(1.0 - p)))
    error = predicion - objetivo
    if nombre == "huber":
        absoluto = np.abs(error)
        cuadratico = np.minimum(absoluto, delta)
        lineal = absoluto - cuadratico
        return float(np.mean(0.5 * cuadratico ** 2 + delta * lineal))
    return float(np.mean(error ** 2))


def _gradiente_hessiano(nombre: str, predicion: np.ndarray,
                        objetivo: np.ndarray,
                        delta: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    if nombre == "logistic":
        p = np.clip(_sigmoide(predicion), 1e-8, 1.0 - 1e-8)
        return p - objetivo, np.clip(p * (1.0 - p), 1e-8, None)
    error = predicion - objetivo
    if nombre == "huber":
        absoluto = np.abs(error)
        gradiente = np.clip(error, -delta, delta)
        hessiano = np.where(absoluto <= delta, 1.0, 1e-6)
        return gradiente, hessiano
    return error, np.ones_like(error)


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
    return {
        'mse': mse,
        'mae': mae,
        'rmse': float(math.sqrt(mse)),
        'r2': r2,
        'n_samples': int(real.shape[0]),
    }


# ---------------------------------------------------------------------------
# 1) Arbol debil de gradiente (segundo orden + histograma + leaf-wise)
# ---------------------------------------------------------------------------
class NeuronaArbolGradiente(NeuronaMemoriaBase):
    """Arbol de decision para boosting de segundo orden.

    Se ajusta a un gradiente ``g`` y un hessiano ``h`` por muestra. Las hojas
    almacenan el paso Newton regularizado, por lo que el arbol no necesita
    etiquetas: solo derivadas de la perdida.

    Parametros
    ----------
    max_depth:
        Profundidad maxima (siempre se respeta).
    max_leaves:
        Numero maximo de hojas (crecimiento leaf-wise). Por defecto
        ``2**max_depth``.
    min_samples_leaf:
        Minimo de muestras por hoja.
    reg_lambda / reg_alpha / gamma:
        Regularizacion L2, L1 y ganancia minima de division.
    n_bins:
        Numero maximo de bins del histograma por caracteristica.
    max_features:
        Caracteristicas evaluadas por division (submuestreo de columnas).
    """

    def __init__(self, max_depth: int = 3, max_leaves: Optional[int] = None,
                 min_samples_leaf: int = 5, reg_lambda: float = 1.0,
                 reg_alpha: float = 0.0, gamma: float = 0.0,
                 n_bins: int = 32, max_features: Optional[int] = None,
                 seed: Optional[int] = None,
                 nombre: str = "NeuronaArbolGradiente") -> None:
        super().__init__(1, 1, nombre)
        self.max_depth = max(1, int(max_depth))
        self.max_leaves = (max(1, int(max_leaves)) if max_leaves is not None
                           else 2 ** self.max_depth)
        self.min_samples_leaf = max(1, int(min_samples_leaf))
        self.reg_lambda = max(0.0, float(reg_lambda))
        self.reg_alpha = max(0.0, float(reg_alpha))
        self.gamma = float(gamma)
        self.n_bins = max(2, int(n_bins))
        self.max_features = (max(1, int(max_features))
                             if max_features is not None else None)
        self.rng = np.random.default_rng(
            int(LUCIA_GB_CONFIG["random_seed"] if seed is None else seed)
        )
        self.arbol: List[Dict[str, Any]] = []
        self.importancias_: Optional[np.ndarray] = None
        self._g: Optional[np.ndarray] = None
        self._h: Optional[np.ndarray] = None
        self._X: Optional[np.ndarray] = None
        self._cortes: List[np.ndarray] = []

    # -- construccion ------------------------------------------------------
    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    def _cortes_columna(self, columna: np.ndarray) -> np.ndarray:
        valores = np.unique(columna)
        if valores.size <= 1:
            return np.empty(0, dtype=np.float64)
        if valores.size <= self.n_bins:
            candidatos = (valores[:-1] + valores[1:]) / 2.0
        else:
            candidatos = np.quantile(
                columna, np.linspace(0.0, 1.0, self.n_bins + 1)[1:-1]
            )
        candidatos = np.unique(candidatos)
        return candidatos[np.isfinite(candidatos)]

    def _nuevo_nodo(self, indices: np.ndarray, profundidad: int) -> Dict[str, Any]:
        gradiente = float(np.sum(self._g[indices]))
        hessiano = max(float(np.sum(self._h[indices])), 1e-12)
        nodo: Dict[str, Any] = {
            'id': len(self.arbol),
            'hoja': True,
            'profundidad': int(profundidad),
            'n': int(indices.size),
            'G': gradiente,
            'H': hessiano,
            'valor': -_soft_threshold(gradiente, self.reg_alpha) / (
                hessiano + self.reg_lambda
            ),
            '_indices': indices,
        }
        self.arbol.append(nodo)
        return nodo

    def _mejor_division(self, nodo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        indices = nodo['_indices']
        if (nodo['profundidad'] >= self.max_depth
                or indices.size < 2 * self.min_samples_leaf):
            return None
        total_G = float(nodo['G'])
        total_H = float(nodo['H'])
        if total_H < 1e-12:
            return None
        n_total = int(indices.size)
        n_features = self._X.shape[1]
        if self.max_features is not None and self.max_features < n_features:
            caracteristicas = self.rng.choice(
                n_features, size=self.max_features, replace=False
            )
        else:
            caracteristicas = np.arange(n_features)

        mejor: Optional[Dict[str, Any]] = None
        mejor_ganancia = 0.0
        for feature in caracteristicas:
            cortes = self._cortes[feature]
            if cortes.size == 0:
                continue
            bins = np.searchsorted(cortes, self._X[indices, feature], side='left')
            n_bins_total = cortes.size + 1
            G_bin = np.bincount(bins, weights=self._g[indices],
                                minlength=n_bins_total)
            H_bin = np.bincount(bins, weights=self._h[indices],
                                minlength=n_bins_total)
            C_bin = np.bincount(bins, minlength=n_bins_total).astype(np.float64)

            G_izq = np.cumsum(G_bin)[:-1]
            H_izq = np.cumsum(H_bin)[:-1]
            C_izq = np.cumsum(C_bin)[:-1]
            G_der = total_G - G_izq
            H_der = total_H - H_izq
            C_der = n_total - C_izq

            valido = ((C_izq >= self.min_samples_leaf)
                      & (C_der >= self.min_samples_leaf)
                      & (H_izq > 1e-12) & (H_der > 1e-12))
            if not np.any(valido):
                continue
            ganancia = 0.5 * (
                G_izq ** 2 / (H_izq + self.reg_lambda)
                + G_der ** 2 / (H_der + self.reg_lambda)
                - total_G ** 2 / (total_H + self.reg_lambda)
            ) - self.gamma
            ganancia = np.where(valido, ganancia, -np.inf)
            posicion = int(np.argmax(ganancia))
            if not np.isfinite(ganancia[posicion]):
                continue
            if float(ganancia[posicion]) > mejor_ganancia:
                mejor_ganancia = float(ganancia[posicion])
                mejor = {
                    'feature': int(feature),
                    'umbral': float(cortes[posicion]),
                    'ganancia': float(ganancia[posicion]),
                }
        return mejor

    def fit(self, X: np.ndarray, gradiente: np.ndarray,
            hessiano: Optional[np.ndarray] = None) -> "NeuronaArbolGradiente":
        """Ajusta el arbol a ``(gradiente, hessiano)``; sin etiquetas."""
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim != 2 or matriz.shape[0] == 0:
            raise ValueError("X debe ser una matriz 2D no vacia")
        g = np.asarray(gradiente, dtype=np.float64).reshape(-1)
        if g.size != matriz.shape[0]:
            raise ValueError("gradiente debe tener una entrada por muestra")
        h = (np.ones_like(g) if hessiano is None
             else np.asarray(hessiano, dtype=np.float64).reshape(-1))
        if h.size != g.size:
            raise ValueError("hessiano debe tener una entrada por muestra")
        h = np.clip(h, 1e-8, None)

        self.input_size = int(matriz.shape[1])
        self._X = matriz
        self._g = g
        self._h = h
        self._cortes = [self._cortes_columna(matriz[:, f])
                        for f in range(self.input_size)]
        self.arbol = []
        self.importancias_ = np.zeros(self.input_size, dtype=np.float64)

        raiz = self._nuevo_nodo(np.arange(matriz.shape[0]), 0)
        monticulo: List[Tuple[float, int, int]] = []
        contador = 0

        def _empujar(nodo: Dict[str, Any]) -> None:
            nonlocal contador
            if nodo['profundidad'] >= self.max_depth:
                return
            if nodo['n'] < 2 * self.min_samples_leaf:
                return
            division = self._mejor_division(nodo)
            if division is None or division['ganancia'] <= 1e-12:
                return
            contador += 1
            heapq.heappush(
                monticulo,
                (-division['ganancia'], contador, nodo['id'], division),
            )

        _empujar(raiz)
        hojas = 1
        while monticulo and hojas < self.max_leaves:
            _, _, nodo_id, division = heapq.heappop(monticulo)
            nodo = self.arbol[nodo_id]
            if not nodo['hoja']:
                continue
            indices = nodo['_indices']
            mascara = (self._X[indices, division['feature']]
                       <= division['umbral'])
            if (int(np.sum(mascara)) < self.min_samples_leaf
                    or int(np.sum(~mascara)) < self.min_samples_leaf):
                continue

            nodo['hoja'] = False
            nodo['feature'] = division['feature']
            nodo['umbral'] = division['umbral']
            nodo['ganancia'] = division['ganancia']
            self.importancias_[division['feature']] += division['ganancia']

            izquierda = self._nuevo_nodo(indices[mascara],
                                         nodo['profundidad'] + 1)
            derecha = self._nuevo_nodo(indices[~mascara],
                                       nodo['profundidad'] + 1)
            nodo['izquierda'] = izquierda['id']
            nodo['derecha'] = derecha['id']
            hojas += 1
            _empujar(izquierda)
            _empujar(derecha)

        self._finalizar_hojas(matriz)
        total = float(np.sum(self.importancias_))
        if total > 1e-12:
            self.importancias_ = self.importancias_ / total
        for nodo in self.arbol:
            nodo.pop('_indices', None)
        self._X = None
        self._g = None
        self._h = None
        self.registrar_perdida(self.perdida_aproximada())
        return self

    # -- ganchos para variantes -------------------------------------------
    def _finalizar_hojas(self, X: np.ndarray) -> None:
        """Hook: la variante lineal sobreescribe el valor de las hojas."""

    def perdida_aproximada(self) -> float:
        """Ganancia total de segundo orden (proxy de calidad del arbol)."""
        ganancia = 0.0
        for nodo in self.arbol:
            if not nodo['hoja']:
                ganancia += float(nodo.get('ganancia', 0.0))
        return float(-ganancia)

    # -- prediccion --------------------------------------------------------
    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.arbol:
            raise RuntimeError("NeuronaArbolGradiente no ajustada")
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        salida = np.zeros(matriz.shape[0], dtype=np.float64)
        pila: List[Tuple[int, np.ndarray]] = [(0, np.arange(matriz.shape[0]))]
        while pila:
            nodo_id, indices = pila.pop()
            if indices.size == 0:
                continue
            nodo = self.arbol[nodo_id]
            if nodo['hoja']:
                if 'beta' in nodo:
                    beta = nodo['beta']
                    salida[indices] = (beta[0]
                                       + matriz[indices] @ beta[1:])
                else:
                    salida[indices] = nodo['valor']
            else:
                mascara = (matriz[indices, nodo['feature']]
                           <= nodo['umbral'])
                pila.append((nodo['izquierda'], indices[mascara]))
                pila.append((nodo['derecha'], indices[~mascara]))
        return salida

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        return self.predict(entrada)

    # -- informacion -------------------------------------------------------
    def n_hojas(self) -> int:
        return int(sum(1 for nodo in self.arbol if nodo['hoja']))

    def profundidad_real(self) -> int:
        if not self.arbol:
            return 0
        return int(max(nodo['profundidad'] for nodo in self.arbol))

    def params_count(self) -> int:
        total = 0
        for nodo in self.arbol:
            if nodo['hoja']:
                total += int(nodo.get('beta', np.array([0.0])).size)
            else:
                total += 1
        return total

    def _arreglos_parametros(self) -> List[np.ndarray]:
        arreglos: List[np.ndarray] = []
        for nodo in self.arbol:
            if nodo['hoja']:
                if 'beta' in nodo:
                    arreglos.append(np.asarray(nodo['beta'], dtype=np.float64))
                else:
                    arreglos.append(np.array([nodo['valor']], dtype=np.float64))
        return arreglos

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': type(self).__name__,
            'n_nodos': len(self.arbol),
            'n_hojas': self.n_hojas(),
            'profundidad_real': self.profundidad_real(),
            'max_leaves': self.max_leaves,
            'n_bins': self.n_bins,
            'importancias': (self.importancias_.round(6).tolist()
                             if self.importancias_ is not None else None),
        })
        return stats


class NeuronaArbolLinealGradiente(NeuronaArbolGradiente):
    """Arbol de gradiente con hojas lineales (piecewise linear).

    La estructura se elige con la ganancia de segundo orden y, al finalizar,
    cada hoja resuelve una regresion ridge ponderada por el hessiano sobre el
    pseudo-objetivo ``z = -g/h``. Mejora la aproximacion de funciones suaves
    sin multiplicar el numero de arboles.
    """

    def __init__(self, reg_lambda_hoja: float = 1.0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.reg_lambda_hoja = max(1e-6, float(reg_lambda_hoja))

    def _finalizar_hojas(self, X: np.ndarray) -> None:
        for nodo in self.arbol:
            if not nodo['hoja']:
                continue
            indices = nodo['_indices']
            if indices.size == 0:
                nodo['beta'] = np.zeros(X.shape[1] + 1)
                continue
            X_hoja = X[indices]
            h = np.clip(self._h[indices], 1e-8, None)
            z = -self._g[indices] / h
            X_aumentada = np.hstack(
                [np.ones((indices.size, 1), dtype=np.float64), X_hoja]
            )
            pesos = h[:, None]
            matriz = X_aumentada.T @ (pesos * X_aumentada)
            matriz += self.reg_lambda_hoja * np.eye(matriz.shape[0])
            vector = X_aumentada.T @ (h * z)
            try:
                beta = np.linalg.solve(matriz, vector)
            except np.linalg.LinAlgError:  # pragma: no cover - caso singular
                beta = np.linalg.lstsq(matriz, vector, rcond=None)[0]
            nodo['beta'] = beta


# ---------------------------------------------------------------------------
# 2) Ensemble de Gradient Boosting
# ---------------------------------------------------------------------------
class NeuronaGradienteBoosting(NeuronaMemoriaBase):
    """Boosting de gradiente con arboles de segundo orden.

    Parametros
    ----------
    loss:
        ``"mse"``, ``"huber"`` o ``"logistic"`` (binaria).
    tipo_arbol:
        ``"constante"`` (hoja Newton) o ``"lineal"`` (hoja ridge).
    usar_base_lineal:
        Ajusta una base lineal ridge antes de boostear los residuos.
    validation_split / early_stopping:
        Validacion interna y parada temprana con rollback.
    """

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaGradienteBoosting",
                 n_estimators: int = 100, learning_rate: float = 0.1,
                 max_depth: int = 3, max_leaves: Optional[int] = None,
                 min_samples_leaf: int = 5, reg_lambda: float = 1.0,
                 reg_alpha: float = 0.0, gamma: float = 0.0,
                 n_bins: int = 32, subsample: float = 1.0,
                 colsample: float = 1.0, loss: str = "mse",
                 huber_delta: float = 1.0, tipo_arbol: str = "constante",
                 usar_base_lineal: bool = False,
                 seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre)
        self.n_estimators = max(1, int(n_estimators))
        self.learning_rate = max(1e-4, float(learning_rate))
        self.max_depth = max(1, int(max_depth))
        self.max_leaves = (max(1, int(max_leaves)) if max_leaves is not None
                           else None)
        self.min_samples_leaf = max(1, int(min_samples_leaf))
        self.reg_lambda = max(0.0, float(reg_lambda))
        self.reg_alpha = max(0.0, float(reg_alpha))
        self.gamma = float(gamma)
        self.n_bins = max(2, int(n_bins))
        self.subsample = min(1.0, max(0.05, float(subsample)))
        self.colsample = min(1.0, max(0.05, float(colsample)))
        self.loss = (loss if loss in ("mse", "huber", "logistic")
                     else "mse")
        self.huber_delta = max(1e-3, float(huber_delta))
        self.tipo_arbol = (tipo_arbol if tipo_arbol in ("constante", "lineal")
                           else "constante")
        self.usar_base_lineal = bool(usar_base_lineal)
        self.seed = int(LUCIA_GB_CONFIG["random_seed"]
                        if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.inicializar_pesos()

        self._modelos: List[List[NeuronaArbolGradiente]] = []
        self._base_constante: np.ndarray = np.zeros((1, self.output_size))
        self.n_estimators_: int = 0
        self.mejor_iteracion: int = 0
        self.historial: List[float] = []
        self.historial_validacion: List[float] = []
        self._entrenado = False

    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    # -- construccion de arboles ------------------------------------------
    def _crear_arbol(self, iteracion: int) -> NeuronaArbolGradiente:
        clase = (NeuronaArbolLinealGradiente if self.tipo_arbol == "lineal"
                 else NeuronaArbolGradiente)
        max_features = max(1, int(round(self.colsample * self.input_size)))
        extra: Dict[str, Any] = {}
        if clase is NeuronaArbolLinealGradiente:
            extra['reg_lambda_hoja'] = float(LUCIA_GB_CONFIG["reg_lambda_hoja"])
        return clase(
            max_depth=self.max_depth,
            max_leaves=self.max_leaves,
            min_samples_leaf=self.min_samples_leaf,
            reg_lambda=self.reg_lambda,
            reg_alpha=self.reg_alpha,
            gamma=self.gamma,
            n_bins=self.n_bins,
            max_features=max_features if self.colsample < 1.0 else None,
            seed=self.seed + 97 * (iteracion + 1),
            **extra,
        )

    # -- base lineal / constante ------------------------------------------
    def _inicializar_prediccion(self, X_entrenamiento: np.ndarray,
                                Y_entrenamiento: np.ndarray,
                                X_completo: np.ndarray) -> np.ndarray:
        if self.usar_base_lineal and self.loss in ("mse", "huber"):
            aumentada = np.hstack(
                [np.ones((X_entrenamiento.shape[0], 1)), X_entrenamiento]
            )
            matriz = aumentada.T @ aumentada
            matriz += float(LUCIA_GB_CONFIG["reg_lambda_base"]) * np.eye(
                matriz.shape[0]
            )
            vector = aumentada.T @ Y_entrenamiento
            try:
                beta = np.linalg.solve(matriz, vector)
            except np.linalg.LinAlgError:  # pragma: no cover
                beta = np.linalg.lstsq(matriz, vector, rcond=None)[0]
            self.pesos = beta[1:]
            self.sesgo = beta[:1]
            return X_completo @ self.pesos + self.sesgo

        if self.loss == "logistic":
            media = np.clip(np.mean(Y_entrenamiento, axis=0), 1e-6, 1.0 - 1e-6)
            self._base_constante = _logit(media).reshape(1, 1)
        else:
            self._base_constante = np.mean(
                Y_entrenamiento, axis=0
            ).reshape(1, self.output_size)
        return np.tile(self._base_constante, (X_completo.shape[0], 1))

    def _prediccion_base(self, X: np.ndarray) -> np.ndarray:
        if (self.usar_base_lineal and self.loss in ("mse", "huber")
                and self.pesos is not None):
            return X @ self.pesos + self.sesgo
        return np.tile(self._base_constante, (X.shape[0], 1))

    # -- entrenamiento -----------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray,
            n_estimators: Optional[int] = None,
            learning_rate: Optional[float] = None,
            validation_split: float = 0.0, early_stopping: bool = False,
            patience: int = 20, verbose: bool = False,
            epochs: Optional[int] = None, **kwargs: Any) -> List[float]:
        """Entrena el ensemble; acepta ``epochs`` como alias de ``n_estimators``."""
        if n_estimators is None and epochs is not None:
            n_estimators = epochs
        if n_estimators is not None:
            self.n_estimators = max(1, int(n_estimators))
        if learning_rate is not None:
            self.learning_rate = max(1e-4, float(learning_rate))
        if self.loss == "logistic" and self.output_size != 1:
            raise ValueError("loss='logistic' solo admite output_size=1")

        matriz, objetivo = _validar_datos(
            X, y, self.input_size, self.output_size
        )
        if self.loss == "logistic":
            objetivo = np.clip(objetivo, 0.0, 1.0)
        inicio = time.perf_counter()

        total = matriz.shape[0]
        indices = np.arange(total)
        self.rng.shuffle(indices)
        corte = 0
        if validation_split > 0.0 and total >= 5:
            corte = int(round(total * min(0.9, float(validation_split))))
            corte = max(1, min(total - 1, corte))
        indices_validacion = indices[:corte]
        indices_entrenamiento = indices[corte:]

        X_entrenamiento = matriz[indices_entrenamiento]
        Y_entrenamiento = objetivo[indices_entrenamiento]
        bruto = self._inicializar_prediccion(
            X_entrenamiento, Y_entrenamiento, matriz
        )

        self._modelos = [[] for _ in range(self.output_size)]
        self.historial = []
        self.historial_validacion = []
        mejor_validacion = float("inf")
        mejor_iteracion = 0
        espera = 0
        paciencia = max(1, int(patience))

        for iteracion in range(self.n_estimators):
            gradiente, hessiano = _gradiente_hessiano(
                self.loss, bruto, objetivo, self.huber_delta
            )
            tamano_submuestra = max(
                1, int(round(self.subsample * indices_entrenamiento.size))
            )
            for salida in range(self.output_size):
                if self.subsample < 1.0:
                    filas = self.rng.choice(
                        indices_entrenamiento.size, size=tamano_submuestra,
                        replace=False,
                    )
                else:
                    filas = np.arange(indices_entrenamiento.size)
                arbol = self._crear_arbol(iteracion)
                arbol.fit(
                    X_entrenamiento[filas],
                    gradiente[indices_entrenamiento[filas], salida],
                    hessiano[indices_entrenamiento[filas], salida],
                )
                bruto[:, salida] += (self.learning_rate
                                     * arbol.predict(matriz))
                self._modelos[salida].append(arbol)

            perdida_entrenamiento = _perdida(
                self.loss, bruto[indices_entrenamiento],
                Y_entrenamiento, self.huber_delta,
            )
            if corte > 0:
                perdida_validacion = _perdida(
                    self.loss, bruto[indices_validacion],
                    objetivo[indices_validacion], self.huber_delta,
                )
            else:
                perdida_validacion = perdida_entrenamiento

            self.historial.append(float(perdida_entrenamiento))
            self.historial_validacion.append(float(perdida_validacion))
            self.registrar_perdida(perdida_entrenamiento)

            if perdida_validacion < mejor_validacion - 1e-12:
                mejor_validacion = float(perdida_validacion)
                mejor_iteracion = iteracion + 1
                espera = 0
            else:
                espera += 1

            if verbose and (iteracion % 10 == 0 or iteracion == self.n_estimators - 1):
                logger.info(
                    "%s iter %d/%d | perdida=%.6f | val=%.6f",
                    self.nombre, iteracion + 1, self.n_estimators,
                    perdida_entrenamiento, perdida_validacion,
                )
            if early_stopping and corte > 0 and espera >= paciencia:
                break

        if corte > 0 and mejor_iteracion > 0:
            self.mejor_iteracion = int(mejor_iteracion)
            for salida in range(self.output_size):
                self._modelos[salida] = self._modelos[salida][:mejor_iteracion]
        else:
            self.mejor_iteracion = len(self._modelos[0]) if self._modelos else 0

        self.n_estimators_ = (len(self._modelos[0]) if self._modelos else 0)
        self._entrenado = True
        self._timer_train = time.perf_counter() - inicio
        return list(self.historial)

    def train(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
              learning_rate: Optional[float] = None, verbose: bool = False,
              **kwargs: Any) -> Dict[str, Any]:
        """Alias compatible con la API de entrenamiento de RF_SL."""
        historial = self.fit(
            X, y, epochs=epochs, learning_rate=learning_rate, verbose=verbose,
            **kwargs,
        )
        return {
            'historial': historial,
            'n_estimators': self.n_estimators_,
            'perdida_final': float(historial[-1]) if historial else None,
        }

    # -- inferencia --------------------------------------------------------
    def _predecir_bruto(self, X: np.ndarray) -> np.ndarray:
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        if matriz.shape[1] != self.input_size:
            raise ValueError(
                f"Se esperaban {self.input_size} caracteristicas y llegaron "
                f"{matriz.shape[1]}"
            )
        bruto = self._prediccion_base(matriz)
        for salida in range(self.output_size):
            for arbol in self._modelos[salida]:
                bruto[:, salida] += self.learning_rate * arbol.predict(matriz)
        return bruto

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._entrenado:
            raise RuntimeError("El modelo no esta entrenado: llama a fit primero")
        entrada = np.asarray(X, dtype=np.float64)
        unico = entrada.ndim == 1
        bruto = self._predecir_bruto(entrada)
        if self.loss == "logistic":
            salida = _sigmoide(bruto)
        else:
            salida = bruto
        self.historial_activaciones.append(np.array(salida, copy=True))
        if len(self.historial_activaciones) > 100:
            self.historial_activaciones.popleft()
        self.pasos += 1
        return salida[0] if unico else salida

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        return self.predict(entrada)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.loss != "logistic":
            raise RuntimeError("predict_proba solo aplica con loss='logistic'")
        return self.predict(X)

    # -- perdidas y gradientes (API historica) ----------------------------
    def compute_loss(self, prediccion: np.ndarray,
                     objetivo: np.ndarray) -> float:
        return _perdida(self.loss, np.asarray(prediccion, dtype=np.float64),
                        np.asarray(objetivo, dtype=np.float64),
                        self.huber_delta)

    def squared_error_loss(self, pred: np.ndarray,
                           target: np.ndarray) -> float:
        return float(np.mean((np.asarray(pred) - np.asarray(target)) ** 2))

    def log_loss(self, pred: np.ndarray, target: np.ndarray) -> float:
        return _perdida("logistic", _logit(np.asarray(pred, dtype=np.float64)),
                        np.asarray(target, dtype=np.float64))

    def compute_gradient(self, prediccion: np.ndarray,
                         objetivo: np.ndarray) -> np.ndarray:
        gradiente, _ = _gradiente_hessiano(
            self.loss, np.asarray(prediccion, dtype=np.float64),
            np.asarray(objetivo, dtype=np.float64), self.huber_delta,
        )
        return gradiente

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Gradientes medios de la base lineal (API de compatibilidad)."""
        X = np.asarray(entrada, dtype=np.float64)
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(-1, 1)
        n = max(1, X.shape[0])
        grad_pesos = (X.T @ gradiente) / n
        grad_sesgo = np.mean(gradiente, axis=0, keepdims=True)
        self.historial_gradientes.append({
            'pesos': grad_pesos.copy(),
            'norma': float(np.linalg.norm(grad_pesos)),
        })
        return grad_pesos, grad_sesgo

    def update_weights(self, grad_pesos: np.ndarray,
                       grad_sesgo: np.ndarray) -> None:
        """Actualiza la base lineal con el learning rate (API previa)."""
        if self.pesos is None:
            self.pesos = np.zeros((self.input_size, self.output_size))
        if self.sesgo is None:
            self.sesgo = np.zeros((1, self.output_size))
        self.pesos = self.pesos - self.learning_rate * grad_pesos
        self.sesgo = self.sesgo - self.learning_rate * grad_sesgo

    def apply_gradient(self, entrada: np.ndarray,
                       objetivo: np.ndarray) -> float:
        """Un paso de gradiente con busqueda de linea sobre la base lineal."""
        matriz = np.asarray(entrada, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        etiquetas = np.asarray(objetivo, dtype=np.float64)
        if etiquetas.ndim == 1:
            etiquetas = etiquetas.reshape(-1, 1)

        pesos_previos = None if self.pesos is None else self.pesos.copy()
        sesgo_previo = None if self.sesgo is None else self.sesgo.copy()
        perdida_antes = self.compute_loss(self.predict(matriz), etiquetas)
        gradiente = self.compute_gradient(self.predict(matriz), etiquetas)
        grad_pesos, grad_sesgo = self.backward(gradiente, matriz)

        if self.loss == "logistic":
            self.update_weights(grad_pesos, grad_sesgo)
            return self.compute_loss(self.predict(matriz), etiquetas)

        escala = 1.0
        for _ in range(5):
            self.pesos = (np.zeros((self.input_size, self.output_size))
                          if pesos_previos is None else pesos_previos.copy())
            self.sesgo = (np.zeros((1, self.output_size))
                          if sesgo_previo is None else sesgo_previo.copy())
            self.update_weights(grad_pesos * escala, grad_sesgo * escala)
            perdida = self.compute_loss(self.predict(matriz), etiquetas)
            if perdida < perdida_antes - 1e-12:
                return float(perdida)
            escala *= 0.25

        self.pesos = pesos_previos
        self.sesgo = sesgo_previo
        return float(perdida_antes)

    def train_step(self, entrada: np.ndarray,
                   objetivo: np.ndarray) -> Dict[str, float]:
        antes = self.compute_loss(self.predict(entrada), objetivo)
        despues = self.apply_gradient(entrada, objetivo)
        return {
            'loss_before': float(antes),
            'loss_after': float(despues),
            'improvement': float(antes - despues),
        }

    # -- evaluacion --------------------------------------------------------
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        matriz, objetivo = _validar_datos(
            X, y, self.input_size, self.output_size
        )
        prediccion = self.predict(matriz)
        metricas = _metricas_regresion(prediccion, objetivo)
        # Para logistica, la perdida se calcula sobre el logit (prediccion bruta).
        bruto = self._predecir_bruto(matriz) if self.loss == "logistic" else prediccion
        metricas['loss'] = _perdida(self.loss, bruto, objetivo,
                                    self.huber_delta)
        if self.loss == "logistic":
            etiquetas = (np.asarray(prediccion) >= 0.5).astype(np.float64)
            metricas['accuracy'] = float(np.mean(etiquetas == objetivo))
            metricas['logloss'] = _perdida("logistic", bruto, objetivo)
        return metricas

    # -- informacion -------------------------------------------------------
    def importancias(self) -> np.ndarray:
        if not self._modelos:
            return np.zeros(self.input_size)
        acumulado = np.zeros(self.input_size, dtype=np.float64)
        for salida in range(self.output_size):
            for arbol in self._modelos[salida]:
                if arbol.importancias_ is not None:
                    acumulado += arbol.importancias_
        total = float(np.sum(acumulado))
        return acumulado / total if total > 1e-12 else acumulado

    def params_count(self) -> int:
        total = 0
        if self.usar_base_lineal and self.pesos is not None:
            total += int(np.size(self.pesos)) + int(np.size(self.sesgo))
        for salida in range(self.output_size):
            for arbol in self._modelos[salida]:
                total += arbol.params_count()
        return total

    def _arreglos_parametros(self) -> List[np.ndarray]:
        arreglos: List[np.ndarray] = []
        if self.pesos is not None:
            arreglos.append(np.asarray(self.pesos, dtype=np.float64))
        if self.sesgo is not None:
            arreglos.append(np.asarray(self.sesgo, dtype=np.float64))
        for salida in range(self.output_size):
            for arbol in self._modelos[salida]:
                arreglos.extend(arbol._arreglos_parametros())
        return arreglos

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'gradiente_boosting',
            'loss': self.loss,
            'tipo_arbol': self.tipo_arbol,
            'n_estimators_config': self.n_estimators,
            'n_estimators_entrenados': self.n_estimators_,
            'mejor_iteracion': self.mejor_iteracion,
            'base_lineal': bool(self.usar_base_lineal and self.pesos is not None),
            'importancias': self.importancias().round(6).tolist(),
            'historial_len': len(self.historial),
            'ultima_perdida': (float(self.historial[-1])
                               if self.historial else None),
        })
        return stats


# ---------------------------------------------------------------------------
# 3) Adaptador de compatibilidad con RF_SL1_1
# ---------------------------------------------------------------------------
class GradientBoostingOptimizer(NeuronaGradienteBoosting):
    """Compatibilidad con la clase historica, ahora con boosting real.

    Mantiene los atributos y metodos de la version anterior
    (``_learning_rate``, ``_n_estimators``, ``_max_depth``, ``_subsample``,
    ``_loss_type``, ``_convergence_history``, ``_timer_train`` y la API de
    gradiente), respaldados por ``NeuronaGradienteBoosting``.
    """

    def __init__(self, input_size: int = 4, output_size: int = 8,
                 nombre: str = "GradientBoostingOptimizer", **kwargs: Any) -> None:
        kwargs.setdefault("usar_base_lineal", True)
        super().__init__(input_size=input_size, output_size=output_size,
                         nombre=nombre, **kwargs)
        self._learning_rate = float(self.learning_rate)
        self._n_estimators = int(self.n_estimators)
        self._max_depth = int(self.max_depth)
        self._subsample = float(self.subsample)
        self._loss_type = str(self.loss)
        self._convergence_history: List[float] = []
        self._timer_train = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
            epochs_boosting: Optional[int] = None, verbose: bool = False,
            **kwargs: Any) -> List[float]:
        historial = super().fit(
            X, y, epochs=epochs if epochs is not None else epochs_boosting,
            verbose=verbose, **kwargs,
        )
        self._learning_rate = float(self.learning_rate)
        self._n_estimators = int(self.n_estimators)
        self._max_depth = int(self.max_depth)
        self._subsample = float(self.subsample)
        self._loss_type = str(self.loss)
        self._convergence_history = list(historial)
        self._timer_train = float(getattr(self, "_timer_train", 0.0))
        return historial

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        return self.predict(entrada)


# ---------------------------------------------------------------------------
# Fabrica, evaluacion y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "gb", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaGradienteBoosting:
    """Fabrica un modelo de boosting por nombre."""
    clave = str(tipo or "").strip().lower()
    if clave in ("gb", "boosting", "gradiente_boosting", "gradient_boosting"):
        return NeuronaGradienteBoosting(input_size=input_size,
                                        output_size=output_size, **kwargs)
    if clave in ("gb_lineal", "boosting_lineal", "hojas_lineales"):
        kwargs.setdefault("tipo_arbol", "lineal")
        return NeuronaGradienteBoosting(input_size=input_size,
                                        output_size=output_size, **kwargs)
    if clave in ("compat", "compatibilidad", "gradient_boosting_optimizer"):
        return GradientBoostingOptimizer(input_size=input_size,
                                         output_size=output_size, **kwargs)
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: gb, gb_lineal, compat"
    )


def tipos_disponibles() -> List[str]:
    return ["gb", "gb_lineal", "compat"]


def entrenar_y_evaluar(modelo: NeuronaGradienteBoosting,
                       X: np.ndarray, y: np.ndarray,
                       n_estimators: int = 100,
                       learning_rate: float = 0.1,
                       **kwargs: Any) -> Dict[str, Any]:
    historial = modelo.fit(X, y, n_estimators=n_estimators,
                           learning_rate=learning_rate, **kwargs)
    return {
        'modelo': modelo,
        'historial': historial,
        'metricas': modelo.evaluate(X, y),
        'perdida_final': float(historial[-1]) if historial else float('nan'),
    }


def benchmark_modelo(modelo: NeuronaGradienteBoosting, X: np.ndarray,
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


def guardar_modelo(modelo: NeuronaGradienteBoosting, ruta: str) -> None:
    with open(ruta, 'wb') as fichero:
        pickle.dump(modelo, fichero, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaGradienteBoosting:
    with open(ruta, 'rb') as fichero:
        modelo = pickle.load(fichero)
    if not isinstance(modelo, NeuronaGradienteBoosting):
        raise TypeError("El fichero no contiene un modelo de boosting")
    return modelo


def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_1_1.py``)."""
    generador = np.random.default_rng(2026)
    X = generador.uniform(-2.0, 2.0, size=(300, 3))
    y = (np.sin(2.0 * X[:, 0]) + X[:, 1] ** 2 - 1.5 * X[:, 2]
         + 0.05 * generador.normal(size=(300,))).reshape(-1, 1)

    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_1_1 :: Gradient Boosting mejorado (v%s)" % __version__)
    print("Muestras:", X.shape[0], "| caracteristicas:", X.shape[1])
    print("=" * 78)

    resultados: Dict[str, Any] = {}
    for etiqueta, tipo in (("constante", "gb"), ("lineal", "gb_lineal")):
        modelo = crear_neurona(tipo, input_size=3, output_size=1,
                               n_estimators=80, learning_rate=0.1,
                               max_depth=3, n_bins=32, seed=7)
        resultado = entrenar_y_evaluar(
            modelo, X, y, n_estimators=80, learning_rate=0.1,
            validation_split=0.2, early_stopping=True, patience=15,
        )
        resultados[etiqueta] = resultado
        metricas = resultado['metricas']
        print("%-12s MSE=%.6f MAE=%.6f R2=%.4f | arboles=%d | params=%d"
              % (etiqueta, metricas['mse'], metricas['mae'], metricas['r2'],
                 modelo.n_estimators_, modelo.params_count()))

    clasificacion = crear_neurona(
        "gb", input_size=3, output_size=1, n_estimators=80,
        learning_rate=0.15, max_depth=3, loss="logistic", seed=11,
    )
    y_bin = ((X[:, 0] ** 2 + X[:, 1] ** 2 - 1.5 * X[:, 2]) > 0.5).astype(float)
    clasificacion.fit(X, y_bin, validation_split=0.2,
                       early_stopping=True, patience=15)
    metricas = clasificacion.evaluate(X, y_bin)
    print("logistic     accuracy=%.4f logloss=%.4f | arboles=%d"
          % (metricas['accuracy'], metricas['logloss'],
             clasificacion.n_estimators_))
    print("Importancias:", clasificacion.importancias().round(4).tolist())
    print("Benchmark:", benchmark_modelo(clasificacion, X, repeticiones=3))
    print("=" * 78)
    return resultados


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaArbolGradiente',
    'NeuronaArbolLinealGradiente',
    'NeuronaGradienteBoosting',
    'GradientBoostingOptimizer',
    'crear_neurona',
    'tipos_disponibles',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_GB_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
