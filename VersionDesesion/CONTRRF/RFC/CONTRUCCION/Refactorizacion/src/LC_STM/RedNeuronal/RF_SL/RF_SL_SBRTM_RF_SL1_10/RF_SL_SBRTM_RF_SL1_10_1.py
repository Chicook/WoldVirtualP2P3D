"""RF_SL_SBRTM_RF_SL1_10_1.py
Neuronas especializadas en aprendizaje supervisado integrado
(RF_SL - SBRTM - RF - 2026).
============================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
de ``IntegratedSupervisedLearningOptimizer`` (sin imports, base ni utilidades)
y lo sustituye por una neurona integrada de aprendizaje supervisado con
especialidad en configuracion de IA local:

  * ``NeuronaAprendizajeIntegrado``: ensemble neuronal supervisado.
      - Deteccion automatica de tarea: regresion o clasificacion.
      - Modelos base: Ridge/OLS, regresion logistica softmax y MLP
        (una o varias capas ocultas) con retropropagacion y Adam.
      - Ensamble ponderado por validacion (average, weighted, majority).
      - Estandarizacion, split de validacion, early stopping y metricas
        completas (R2, MSE, RMSE, MAE, MAPE, accuracy, F1, log-loss).
      - Serializacion y compatibilidad con la API historica.

  * ``NeuronaAprendizajeIntegrado.NucleoIntegrado``: **clase anidada** que
      fusiona preparacion de tareas, split, solvers lineales, MLP
      (forward/backward/Adam), perdidas, metricas y pesos de ensemble.

  * ``NeuronaAprendizajeIntegrado.ConfiguradorIALocal``: **clase anidada**
      especializada en configuracion de IA local. Perfila CPU/RAM/disco/VRAM,
      recomienda arquitectura, lote, epocas, precision y dispositivo, estima
      consumo de recursos, valida y exporta/importa configuracion JSON.

  * ``IntegratedSupervisedLearningOptimizer``: adaptador de compatibilidad
      con la API historica de RF_SL1_10 (``train``, ``predict``,
      ``predict_classes``, ``evaluate``, ``add_model``, ``enable_ensemble``,
      ``enable_early_stopping``...).

  * Utilidades: ``EnsembleManager``, ``DataSplitter``, ``ModelValidator``,
      ``SupervisedTrainer``, ``PredictionAggregator``, ``crear_neurona``,
      ``tipos_disponibles``, ``create_integrated_supervised_learning_optimizer``,
      ``entrenar_y_evaluar``, ``benchmark_modelo``, ``guardar_modelo``,
      ``cargar_modelo`` y ``demo``.

Referencias
-----------
- Regresion Ridge/OLS y regresion logistica softmax.
- MLP con retropropagacion, ReLU/tanh y Adam (Kingma & Ba, 2015).
- Ensamblado por validacion y early stopping.
- Perfilado local de recursos para despliegue de IA en CPU/GPU.

Uso
---
    from RF_SL_SBRTM_RF_SL1_10_1 import NeuronaAprendizajeIntegrado

    modelo = NeuronaAprendizajeIntegrado(input_size=3)
    config = modelo.autoconfigurar(X, y)
    modelo.fit(X, y)
    print(modelo.evaluate(X, y))
    print(modelo.reporte_recursos())
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import pickle
import platform
import shutil
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

__version__ = "2026.1.0"


# ---------------------------------------------------------------------------
# Configuracion global
# ---------------------------------------------------------------------------
LUCIA_INTEGRATED_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "epochs": 300,
    "batch_size": 32,
    "learning_rate": 0.01,
    "hidden_sizes": (32, 16),
    "activation": "relu",
    "dropout": 0.0,
    "weight_decay": 1e-4,
    "validation_split": 0.2,
    "ensemble_method": "weighted",
    "early_stopping": 20,
    "usar_lineal": True,
    "usar_mlp": True,
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
    import sys as _sys

    _CLAVE_BASE = "_rf_snrtm_base_import_integrated"
    _modulo_base = _sys.modules.get(_CLAVE_BASE)
    if _modulo_base is None:
        _directorio_rf_sl = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        for _carpeta in ("RF_SL_SBRTM_RF_rfsl_base", "RF_SL_SBRTM_RF"):
            _ruta_base = os.path.join(
                _directorio_rf_sl, _carpeta, "RF_SL_SNRTM__rfsl_base1.py"
            )
            if not os.path.exists(_ruta_base):
                continue
            _especificacion = _ilu.spec_from_file_location(
                _CLAVE_BASE, _ruta_base
            )
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
# Neurona integrada
# ---------------------------------------------------------------------------
class NeuronaAprendizajeIntegrado(NeuronaMemoriaBase):
    """Ensemble neuronal para regresion y clasificacion supervisada.

    Combina un modelo lineal (Ridge o regresion logistica) con un MLP
    entrenado por retropropagacion. Los pesos del ensemble se calculan con la
    perdida de validacion. Incluye un configurador de IA local.
    """

    # ------------------------------------------------------------------
    # Clase anidada 1: nucleo matematico integrado
    # ------------------------------------------------------------------
    class NucleoIntegrado:
        """Fusiona tareas, split, solvers lineales, MLP, perdidas y metricas."""

        EPS = 1e-12

        # -- tareas y preparacion ------------------------------------
        @staticmethod
        def normalizar_tarea(tarea: Optional[str]) -> str:
            clave = str(tarea or "auto").strip().lower()
            alias = {
                "auto": "auto", "automatico": "auto",
                "clasificacion": "clasificacion",
                "classification": "clasificacion", "clf": "clasificacion",
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

        @staticmethod
        def inferir_tarea(y: Any) -> str:
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

        @staticmethod
        def preparar_objetivo(y: Any, tarea: str) -> Dict[str, Any]:
            arreglo = np.asarray(y)
            if arreglo.ndim == 2 and arreglo.shape[1] == 1:
                arreglo = arreglo.reshape(-1)
            if arreglo.ndim == 0:
                arreglo = arreglo.reshape(1)
            if tarea == "clasificacion":
                if arreglo.ndim == 2:
                    if arreglo.shape[1] >= 2 and np.allclose(
                        np.sum(arreglo.astype(np.float64), axis=1), 1.0
                    ):
                        arreglo = np.argmax(arreglo, axis=1)
                    else:
                        raise ValueError(
                            "Para clasificacion, y debe ser 1D, (n, 1) "
                            "o one-hot"
                        )
                clases, codificado = np.unique(
                    arreglo, return_inverse=True
                )
                if len(clases) < 2:
                    raise ValueError(
                        "La clasificacion requiere al menos dos clases"
                    )
                return {
                    'tarea': tarea,
                    'codificado': codificado.astype(int),
                    'original': arreglo,
                    'clases': clases,
                    'n_outputs': int(len(clases)),
                    'n_classes': int(len(clases)),
                }
            valores = np.asarray(y, dtype=np.float64)
            if valores.ndim == 1:
                valores = valores.reshape(-1, 1)
            elif valores.ndim != 2:
                raise ValueError("Para regresion, y debe ser 1D o 2D")
            if not np.all(np.isfinite(valores)):
                raise ValueError("y contiene valores no finitos")
            return {
                'tarea': tarea,
                'codificado': valores,
                'original': valores,
                'clases': None,
                'n_outputs': int(valores.shape[1]),
                'n_classes': 0,
            }

        @staticmethod
        def dividir(y: np.ndarray, tarea: str, fraccion: float,
                    rng: np.random.Generator
                    ) -> Tuple[np.ndarray, np.ndarray]:
            n = len(y)
            if fraccion <= 0.0 or fraccion >= 1.0 or n < 4:
                indices = rng.permutation(n)
                return indices, np.array([], dtype=int)
            if tarea == "clasificacion":
                codificado = np.asarray(y, dtype=int).ravel()
                indices_train: List[int] = []
                indices_val: List[int] = []
                for clase in np.unique(codificado):
                    grupo = np.where(codificado == clase)[0]
                    grupo = rng.permutation(grupo)
                    n_val = max(1, int(round(len(grupo) * fraccion)))
                    if len(grupo) > 1:
                        n_val = min(n_val, len(grupo) - 1)
                    indices_val.extend(grupo[:n_val].tolist())
                    indices_train.extend(grupo[n_val:].tolist())
                return (np.asarray(indices_train, dtype=int),
                        np.asarray(indices_val, dtype=int))
            indices = rng.permutation(n)
            n_val = max(1, int(round(n * fraccion)))
            n_val = min(n_val, n - 1)
            return indices[n_val:], indices[:n_val]

        # -- solvers lineales ----------------------------------------
        @classmethod
        def resolver_lineal(cls, X: np.ndarray, y: np.ndarray,
                            alpha: float = 0.0
                            ) -> Dict[str, np.ndarray]:
            matriz = np.asarray(X, dtype=np.float64)
            objetivo = np.asarray(y, dtype=np.float64)
            if objetivo.ndim == 1:
                objetivo = objetivo.reshape(-1, 1)
            diseno = np.hstack([
                matriz, np.ones((len(matriz), 1), dtype=np.float64)
            ])
            if alpha <= 0.0:
                theta, _, _, _ = np.linalg.lstsq(
                    diseno, objetivo, rcond=None
                )
            else:
                gram = diseno.T @ diseno
                penalizacion = alpha * np.eye(gram.shape[0])
                penalizacion[-1, -1] = 0.0
                try:
                    theta = np.linalg.solve(
                        gram + penalizacion, diseno.T @ objetivo
                    )
                except np.linalg.LinAlgError:
                    theta, _, _, _ = np.linalg.lstsq(
                        gram + penalizacion, diseno.T @ objetivo,
                        rcond=None,
                    )
            return {
                'W': theta[:-1, :],
                'b': theta[-1, :].reshape(1, -1),
            }

        @staticmethod
        def predecir_lineal(X: np.ndarray,
                            parametros: Dict[str, np.ndarray]
                            ) -> np.ndarray:
            return (np.asarray(X, dtype=np.float64)
                    @ parametros['W'] + parametros['b'])

        # -- activaciones y MLP --------------------------------------
        @staticmethod
        def activacion(z: np.ndarray, nombre: str) -> np.ndarray:
            if nombre == "tanh":
                return np.tanh(z)
            if nombre == "sigmoid":
                return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))
            if nombre == "leaky_relu":
                return np.where(z > 0.0, z, 0.01 * z)
            if nombre == "linear":
                return z
            return np.maximum(z, 0.0)

        @staticmethod
        def derivada(z: np.ndarray, salida: np.ndarray,
                     nombre: str) -> np.ndarray:
            if nombre == "tanh":
                return 1.0 - salida ** 2
            if nombre == "sigmoid":
                return salida * (1.0 - salida)
            if nombre == "leaky_relu":
                return np.where(z > 0.0, 1.0, 0.01)
            if nombre == "linear":
                return np.ones_like(z)
            return (z > 0.0).astype(np.float64)

        @staticmethod
        def softmax(z: np.ndarray) -> np.ndarray:
            datos = np.asarray(z, dtype=np.float64)
            if datos.ndim == 1:
                datos = datos.reshape(1, -1)
            exp = np.exp(datos - np.max(datos, axis=1, keepdims=True))
            return exp / np.maximum(
                np.sum(exp, axis=1, keepdims=True), 1e-300
            )

        @classmethod
        def inicializar_mlp(cls, n_features: int, n_outputs: int,
                            hidden_sizes: Sequence[int],
                            rng: np.random.Generator
                            ) -> List[np.ndarray]:
            dimensiones = [int(n_features)]
            dimensiones.extend(int(n) for n in hidden_sizes if int(n) > 0)
            dimensiones.append(int(n_outputs))
            parametros: List[np.ndarray] = []
            for entrada, salida in zip(dimensiones[:-1],
                                       dimensiones[1:]):
                limite = math.sqrt(6.0 / max(1, entrada + salida))
                parametros.append(
                    rng.uniform(-limite, limite, (entrada, salida))
                )
                parametros.append(np.zeros((1, salida)))
            return parametros

        @classmethod
        def forward_mlp(cls, X: np.ndarray, parametros: List[np.ndarray],
                        activacion: str, tarea: str,
                        dropout: float = 0.0,
                        rng: Optional[np.random.Generator] = None,
                        entrenamiento: bool = False
                        ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
            capas = len(parametros) // 2
            activacion_actual = np.asarray(X, dtype=np.float64)
            cache: List[Dict[str, Any]] = []
            for indice in range(capas):
                W = np.asarray(parametros[2 * indice], dtype=np.float64)
                b = np.asarray(parametros[2 * indice + 1], dtype=np.float64)
                z = activacion_actual @ W + b
                ultima = indice == capas - 1
                if ultima:
                    a = cls.softmax(z) if tarea == "clasificacion" else z
                    mascara = None
                else:
                    a = cls.activacion(z, activacion)
                    mascara = None
                    if entrenamiento and dropout > 0.0 and rng is not None:
                        mascara = rng.random(a.shape) >= dropout
                        a = a * mascara / (1.0 - dropout)
                cache.append({
                    'entrada': activacion_actual,
                    'z': z,
                    'a': a,
                    'mascara': mascara,
                    'W': W,
                })
                activacion_actual = a
            return activacion_actual, cache

        @classmethod
        def entrenar_mlp(
            cls, X: np.ndarray, y: np.ndarray, *, tarea: str,
            hidden_sizes: Sequence[int], activacion: str = "relu",
            epochs: int = 300, batch_size: int = 32,
            learning_rate: float = 0.01, weight_decay: float = 0.0,
            dropout: float = 0.0, seed: int = 2026,
            X_val: Optional[np.ndarray] = None,
            y_val: Optional[np.ndarray] = None,
            early_stopping: int = 0, verbose: bool = False,
        ) -> Dict[str, Any]:
            matriz = np.asarray(X, dtype=np.float64)
            objetivo = np.asarray(y, dtype=np.float64)
            if tarea == "regresion" and objetivo.ndim == 1:
                objetivo = objetivo.reshape(-1, 1)
            n, n_features = matriz.shape
            if tarea == "clasificacion":
                n_outputs = int(np.max(objetivo)) + 1
            else:
                n_outputs = (int(objetivo.shape[1])
                             if objetivo.ndim > 1 else 1)
            rng = np.random.default_rng(seed)
            parametros = cls.inicializar_mlp(
                n_features, n_outputs, hidden_sizes, rng
            )
            estado = {
                'm': [np.zeros_like(p) for p in parametros],
                'v': [np.zeros_like(p) for p in parametros],
                't': 0,
            }
            tam_lote = n if batch_size is None else max(
                1, min(int(batch_size), n)
            )
            historia: List[float] = []
            mejor = float('inf')
            mejores_parametros = copy.deepcopy(parametros)
            espera = 0
            for epoca in range(max(1, int(epochs))):
                orden = rng.permutation(n)
                perdida_acumulada = 0.0
                vistos = 0
                for inicio in range(0, n, tam_lote):
                    indices = orden[inicio:inicio + tam_lote]
                    X_lote = matriz[indices]
                    y_lote = objetivo[indices]
                    p, cache = cls.forward_mlp(
                        X_lote, parametros, activacion, tarea,
                        dropout, rng, entrenamiento=True,
                    )
                    if tarea == "clasificacion":
                        codificado = y_lote.astype(int).ravel()
                        objetivo_onehot = np.zeros_like(p)
                        objetivo_onehot[
                            np.arange(len(codificado)), codificado
                        ] = 1.0
                        perdida = float(-np.mean(np.log(np.clip(
                            p[np.arange(len(codificado)), codificado],
                            1e-12, 1.0,
                        ))))
                        delta = (p - objetivo_onehot) / max(1, len(indices))
                    else:
                        real = y_lote.reshape(p.shape)
                        perdida = float(np.mean((p - real) ** 2))
                        delta = 2.0 * (p - real) / max(1, p.size)
                    perdida_acumulada += perdida * len(indices)
                    vistos += len(indices)
                    estado['t'] += 1
                    t = estado['t']
                    for capa in range(len(cache) - 1, -1, -1):
                        info = cache[capa]
                        grad_W = info['entrada'].T @ delta
                        grad_b = np.sum(delta, axis=0, keepdims=True)
                        if capa > 0:
                            nuevo_delta = delta @ info['W'].T
                            if info['mascara'] is not None:
                                nuevo_delta = (
                                    nuevo_delta * info['mascara']
                                    / (1.0 - dropout)
                                )
                            info_anterior = cache[capa - 1]
                            nuevo_delta = nuevo_delta * cls.derivada(
                                info_anterior['z'],
                                info_anterior['a'],
                                activacion,
                            )
                            delta = nuevo_delta
                        if weight_decay > 0.0:
                            grad_W = grad_W + weight_decay * info['W']
                        indice_w = 2 * capa
                        indice_b = indice_w + 1
                        m_w = estado['m'][indice_w]
                        v_w = estado['v'][indice_w]
                        m_w *= 0.9
                        m_w += 0.1 * grad_W
                        v_w *= 0.999
                        v_w += 0.001 * grad_W * grad_W
                        m_hat = m_w / (1.0 - 0.9 ** t)
                        v_hat = v_w / (1.0 - 0.999 ** t)
                        parametros[indice_w] -= learning_rate * m_hat / (
                            np.sqrt(v_hat) + 1e-8
                        )
                        m_b = estado['m'][indice_b]
                        v_b = estado['v'][indice_b]
                        m_b *= 0.9
                        m_b += 0.1 * grad_b
                        v_b *= 0.999
                        v_b += 0.001 * grad_b * grad_b
                        m_hat_b = m_b / (1.0 - 0.9 ** t)
                        v_hat_b = v_b / (1.0 - 0.999 ** t)
                        parametros[indice_b] -= learning_rate * m_hat_b / (
                            np.sqrt(v_hat_b) + 1e-8
                        )
                perdida_epoca = perdida_acumulada / max(1, vistos)
                historia.append(float(perdida_epoca))
                if verbose and (epoca + 1) % 100 == 0:
                    logger.info(
                        "MLP Epoch %d/%d loss=%.6f",
                        epoca + 1, epochs, perdida_epoca,
                    )
                if X_val is not None and y_val is not None:
                    p_val, _ = cls.forward_mlp(
                        X_val, parametros, activacion, tarea
                    )
                    if tarea == "clasificacion":
                        cod_val = y_val.astype(int).ravel()
                        perdida_val = float(-np.mean(np.log(np.clip(
                            p_val[np.arange(len(cod_val)), cod_val],
                            1e-12, 1.0,
                        ))))
                    else:
                        perdida_val = float(np.mean(
                            (p_val - y_val.reshape(p_val.shape)) ** 2
                        ))
                    if perdida_val < mejor - 1e-9:
                        mejor = float(perdida_val)
                        mejores_parametros = copy.deepcopy(parametros)
                        espera = 0
                    else:
                        espera += 1
                        if early_stopping and espera >= early_stopping:
                            break
            if mejor < float('inf'):
                parametros = mejores_parametros
            return {
                'parametros': parametros,
                'historial': historia,
                'mejor_perdida': float(mejor if mejor < float('inf')
                                       else historia[-1]
                                       if historia else 0.0),
            }

        @classmethod
        def predecir_mlp(cls, X: np.ndarray, parametros: List[np.ndarray],
                         activacion: str, tarea: str) -> np.ndarray:
            salida, _ = cls.forward_mlp(
                X, parametros, activacion, tarea
            )
            return salida

        # -- perdidas, metricas y ensemble ---------------------------
        @classmethod
        def perdida(cls, tarea: str, prediccion: np.ndarray,
                    objetivo: np.ndarray) -> float:
            pred = np.asarray(prediccion, dtype=np.float64)
            real = np.asarray(objetivo, dtype=np.float64)
            if tarea == "clasificacion":
                codificado = real.astype(int).ravel()
                proba = np.clip(pred, 1e-12, 1.0)
                return float(-np.mean(np.log(
                    proba[np.arange(len(codificado)), codificado]
                )))
            if real.ndim == 1:
                real = real.reshape(pred.shape)
            return float(np.mean((pred - real) ** 2))

        @classmethod
        def metricas(cls, tarea: str, prediccion: np.ndarray,
                     objetivo: np.ndarray,
                     clases: Optional[np.ndarray] = None
                     ) -> Dict[str, Any]:
            if tarea == "clasificacion":
                codificado = np.asarray(objetivo, dtype=int).ravel()
                predicho = (np.asarray(prediccion).ravel()
                            if np.asarray(prediccion).ndim == 2
                            else np.asarray(prediccion))
                if np.asarray(prediccion).ndim == 2:
                    predicho = np.argmax(prediccion, axis=1)
                accuracy = float(np.mean(predicho == codificado))
                k = int(len(clases)) if clases is not None else int(
                    np.max(codificado) + 1
                )
                f1s: List[float] = []
                for clase in range(k):
                    verdadero = codificado == clase
                    estimado = predicho == clase
                    if not np.any(verdadero):
                        continue
                    tp = float(np.sum(verdadero & estimado))
                    fp = float(np.sum(~verdadero & estimado))
                    fn = float(np.sum(verdadero & ~estimado))
                    precision = tp / max(1.0, tp + fp)
                    recall = tp / max(1.0, tp + fn)
                    f1s.append(2.0 * precision * recall / max(
                        1e-12, precision + recall
                    ))
                return {
                    'accuracy': accuracy,
                    'f1_macro': float(np.mean(f1s)) if f1s else 0.0,
                    'n_samples': int(codificado.size),
                    'n_classes': int(k),
                }
            real = np.asarray(objetivo, dtype=np.float64)
            pred = np.asarray(prediccion, dtype=np.float64)
            if real.ndim == 1:
                real = real.reshape(pred.shape)
            error = pred - real
            mse = float(np.mean(error ** 2))
            varianza = float(np.sum((real - np.mean(real)) ** 2))
            r2 = (float(1.0 - np.sum(error ** 2) / varianza)
                  if varianza > 1e-12 else
                  (1.0 if mse <= 1e-12 else 0.0))
            return {
                'r2': r2,
                'mse': mse,
                'rmse': float(math.sqrt(max(0.0, mse))),
                'mae': float(np.mean(np.abs(error))),
                'n_samples': int(real.shape[0]),
            }

        @staticmethod
        def pesos_ensemble(puntajes: Sequence[float],
                           metodo: str = "weighted") -> np.ndarray:
            valores = np.asarray(puntajes, dtype=np.float64)
            if valores.size == 0:
                return valores
            if metodo == "average" or metodo == "majority":
                return np.full(valores.size, 1.0 / valores.size)
            errores = np.maximum(valores, 1e-8)
            inversos = 1.0 / errores
            total = float(np.sum(inversos))
            return (inversos / total if total > 0.0
                    else np.full(valores.size, 1.0 / valores.size))

        def resumen(self) -> Dict[str, Any]:
            return {
                'soporta': [
                    'regresion', 'clasificacion', 'mlp',
                    'ensemble', 'adam', 'early_stopping',
                ],
                'epsilon': self.EPS,
            }

    # ------------------------------------------------------------------
    # Clase anidada 2: configurador de IA local
    # ------------------------------------------------------------------
    class ConfiguradorIALocal:
        """Perfila el equipo y recomienda/configura IA local."""

        PERFILES: Dict[str, Dict[str, Any]] = {
            'edge': {
                'hidden_sizes': (8,),
                'batch_size': 8,
                'epochs': 100,
                'learning_rate': 0.02,
                'precision': 'float32',
                'ensemble_method': 'average',
                'early_stopping': 15,
            },
            'cpu_bajo': {
                'hidden_sizes': (16, 8),
                'batch_size': 16,
                'epochs': 200,
                'learning_rate': 0.01,
                'precision': 'float32',
                'ensemble_method': 'weighted',
                'early_stopping': 20,
            },
            'cpu_balanceado': {
                'hidden_sizes': (64, 32),
                'batch_size': 32,
                'epochs': 300,
                'learning_rate': 0.01,
                'precision': 'float64',
                'ensemble_method': 'weighted',
                'early_stopping': 25,
            },
            'gpu_balanceado': {
                'hidden_sizes': (128, 64),
                'batch_size': 64,
                'epochs': 500,
                'learning_rate': 0.005,
                'precision': 'float32',
                'ensemble_method': 'weighted',
                'early_stopping': 30,
            },
        }

        @staticmethod
        def _ram_mb() -> Tuple[float, float]:
            try:
                import psutil  # type: ignore
                memoria = psutil.virtual_memory()
                return (float(memoria.total) / (1024 ** 2),
                        float(memoria.available) / (1024 ** 2))
            except Exception:
                if hasattr(os, "sysconf"):
                    try:
                        total = float(os.sysconf("SC_PAGE_SIZE")
                                      * os.sysconf("SC_PHYS_PAGES"))
                        return (total / (1024 ** 2), total / (1024 ** 2) * 0.5)
                    except (ValueError, OSError):
                        pass
                return 8192.0, 4096.0

        @classmethod
        def perfilar_equipo(cls) -> Dict[str, Any]:
            ram_total, ram_disponible = cls._ram_mb()
            vram = float(os.environ.get(
                "LOCAL_AI_VRAM_MB",
                os.environ.get("CUDA_VRAM_MB", "0"),
            ) or 0.0)
            try:
                disco = shutil.disk_usage(os.getcwd()).free / (1024 ** 2)
            except OSError:
                disco = 0.0
            return {
                'cpu_count': int(os.cpu_count() or 1),
                'ram_total_mb': float(ram_total),
                'ram_disponible_mb': float(ram_disponible),
                'vram_mb': float(vram),
                'disco_libre_mb': float(disco),
                'plataforma': platform.platform(),
                'procesador': platform.processor() or 'desconocido',
                'dispositivo': 'cuda' if vram >= 1024.0 else 'cpu',
            }

        @classmethod
        def recomendar(
            cls, tarea: str, n_samples: int, n_features: int,
            n_outputs: int = 1, perfil: str = "auto",
            ram_mb: Optional[float] = None,
            vram_mb: Optional[float] = None,
        ) -> Dict[str, Any]:
            hardware = cls.perfilar_equipo()
            if perfil not in cls.PERFILES:
                perfil = "auto"
            if perfil == "auto":
                if hardware['vram_mb'] >= 4096.0 and n_samples >= 1000:
                    perfil = "gpu_balanceado"
                elif hardware['ram_total_mb'] < 4096.0:
                    perfil = "edge"
                elif hardware['ram_total_mb'] < 8192.0:
                    perfil = "cpu_bajo"
                else:
                    perfil = "cpu_balanceado"
            base = dict(cls.PERFILES[perfil])
            hidden = list(base['hidden_sizes'])
            if n_samples < 200 or n_features <= 2:
                hidden = []
            else:
                max_ancho = max(8, min(128, 2 * int(n_features)))
                hidden = [min(h, max_ancho) for h in hidden] or [max_ancho]
            lote = int(base['batch_size'])
            if ram_mb is not None:
                lote_ram = max(1, int(
                    float(ram_mb) * 0.15 * 1024 * 1024
                    / max(1, int(n_features) * 16)
                ))
                lote = min(lote, lote_ram)
            if vram_mb is not None and vram_mb < 2048:
                lote = min(lote, 16)
            configuracion = {
                'perfil': perfil,
                'tarea': tarea,
                'n_samples': int(n_samples),
                'n_features': int(n_features),
                'n_outputs': int(n_outputs),
                'hidden_sizes': tuple(int(h) for h in hidden),
                'batch_size': int(max(1, lote)),
                'epochs': int(base['epochs']),
                'learning_rate': float(base['learning_rate']),
                'precision': str(base['precision']),
                'ensemble_method': str(base['ensemble_method']),
                'early_stopping': int(base['early_stopping']),
                'dropout': 0.05 if n_samples > 1000 else 0.0,
                'weight_decay': 1e-4,
                'device': hardware['dispositivo'],
                'hardware': hardware,
                'presupuesto': {
                    'ram_mb': (hardware['ram_total_mb']
                               if ram_mb is None else float(ram_mb)),
                    'vram_mb': (hardware['vram_mb']
                                if vram_mb is None else float(vram_mb)),
                },
            }
            configuracion['recursos'] = cls.estimar_recursos(
                configuracion, n_samples, n_features, n_outputs
            )
            return configuracion

        @classmethod
        def estimar_recursos(cls, configuracion: Dict[str, Any],
                             n_samples: int, n_features: int,
                             n_outputs: int) -> Dict[str, Any]:
            ancho = 8 if configuracion.get('precision') == 'float64' else 4
            hidden = list(configuracion.get('hidden_sizes', []))
            dimensiones = [int(n_features), *hidden, int(n_outputs)]
            parametros = sum(
                a * b + b for a, b in zip(dimensiones[:-1], dimensiones[1:])
            )
            lote = int(configuracion.get('batch_size', 32))
            activaciones = lote * sum(dimensiones) * ancho * 4
            ram = parametros * ancho * 4 + activaciones
            vram = parametros * ancho * 3 + activaciones
            disco = parametros * ancho + 4096
            return {
                'parametros': int(parametros),
                'ram_mb': float(ram / (1024 ** 2)),
                'vram_mb': float(vram / (1024 ** 2)),
                'disco_mb': float(disco / (1024 ** 2)),
                'precision': configuracion.get('precision', 'float64'),
            }

        @staticmethod
        def validar(configuracion: Dict[str, Any]) -> Dict[str, Any]:
            problemas: List[str] = []
            hidden = configuracion.get('hidden_sizes', [])
            if any(int(h) <= 0 for h in hidden):
                problemas.append("hidden_sizes debe ser positivo")
            if int(configuracion.get('batch_size', 1)) < 1:
                problemas.append("batch_size debe ser >= 1")
            if int(configuracion.get('epochs', 1)) < 1:
                problemas.append("epochs debe ser >= 1")
            if float(configuracion.get('learning_rate', 0.0)) <= 0.0:
                problemas.append("learning_rate debe ser positivo")
            if configuracion.get('precision') not in (
                'float64', 'float32', 'float16'
            ):
                problemas.append("precision no soportada")
            return {'valida': not problemas, 'problemas': problemas}

        @staticmethod
        def exportar_json(configuracion: Dict[str, Any]) -> str:
            return json.dumps(configuracion, indent=2, ensure_ascii=False,
                              default=str)

        @staticmethod
        def importar_json(texto: str) -> Dict[str, Any]:
            return json.loads(texto)

        def resumen(self) -> Dict[str, Any]:
            return {
                'perfiles': list(self.PERFILES.keys()),
                'hardware': self.perfilar_equipo(),
                'capacidades': [
                    'perfilado_hardware', 'recomendacion_arquitectura',
                    'estimacion_ram_vram_disco', 'validacion_configuracion',
                    'exportacion_json',
                ],
            }

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuronaAprendizajeIntegrado",
        *,
        tarea: str = "auto",
        epochs: int = 300,
        batch_size: int = 32,
        learning_rate: float = 0.01,
        hidden_sizes: Sequence[int] = (32, 16),
        activacion: str = "relu",
        dropout: float = 0.0,
        weight_decay: float = 1e-4,
        regularization: str = "l2",
        reg_lambda: float = 0.01,
        validation_split: float = 0.2,
        ensemble_method: str = "weighted",
        early_stopping: int = 20,
        usar_lineal: bool = True,
        usar_mlp: bool = True,
        precision: str = "float64",
        seed: Optional[int] = None,
        configuracion_ia: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        if "learning_rate" not in kwargs and "lr" in kwargs:
            learning_rate = kwargs.pop("lr")
        if "hidden_layers" in kwargs and hidden_sizes == (32, 16):
            hidden_sizes = kwargs.pop("hidden_layers")
        if "early_stopping" in kwargs and early_stopping == 20:
            early_stopping = kwargs.pop("early_stopping")
        if kwargs:
            raise TypeError(
                f"Argumentos no reconocidos: {sorted(kwargs)}"
            )

        self.input_size = int(input_size)
        self.output_size = int(output_size)
        if self.input_size <= 0 or self.output_size <= 0:
            raise ValueError("input_size y output_size deben ser positivos")

        self._tarea_config = self.NucleoIntegrado.normalizar_tarea(tarea)
        self._tarea = ("clasificacion"
                       if self._tarea_config == "auto"
                       else self._tarea_config)
        self._epochs = max(1, int(epochs))
        self._batch_size = max(1, int(batch_size))
        self._learning_rate = float(learning_rate)
        if self._learning_rate <= 0.0:
            raise ValueError("learning_rate debe ser positivo")
        self._hidden_sizes = tuple(
            int(h) for h in hidden_sizes if int(h) > 0
        )
        self._activation = str(activacion or "relu").strip().lower()
        if self._activation not in (
            "relu", "tanh", "sigmoid", "leaky_relu", "linear"
        ):
            raise ValueError(f"Activacion desconocida: {activacion!r}")
        self._dropout = min(0.9, max(0.0, float(dropout)))
        self._weight_decay = max(0.0, float(weight_decay))
        self._regularization = self._normalizar_regularizacion(
            regularization
        )
        self._reg_lambda = max(0.0, float(reg_lambda))
        self._validation_split = min(0.9, max(0.0, float(
            validation_split
        )))
        self._ensemble_method = self._normalizar_ensemble(ensemble_method)
        self._early_stopping = max(0, int(early_stopping))
        self._usar_lineal = bool(usar_lineal)
        self._usar_mlp = bool(usar_mlp)
        self._precision = self._normalizar_precision(precision)
        self._seed = int(
            LUCIA_INTEGRATED_CONFIG["random_seed"]
            if seed is None else seed
        )
        self._rng = np.random.default_rng(self._seed)
        self._configurador = self.ConfiguradorIALocal()
        self._nucleo = self.NucleoIntegrado()
        self._configuracion_ia: Dict[str, Any] = (
            dict(configuracion_ia) if configuracion_ia else {}
        )
        if configuracion_ia:
            self.aplicar_configuracion(configuracion_ia)

        self._classes: Optional[np.ndarray] = None
        self._n_classes: int = 0
        self._n_outputs: int = 0
        self._is_fitted: bool = False
        self._n_samples: int = 0
        self._convergence_history: List[float] = []
        self._loss_history: List[float] = []
        self._training_time: float = 0.0
        self._val_accuracy: float = 0.0
        self._best_loss: float = float('inf')
        self._no_improve_count: int = 0
        self._modelos: List[Dict[str, Any]] = []
        self._models: List[Any] = []
        self._scaler: Optional[FeatureStandardizer] = None
        self._regularization = self._regularization

        self.inicializar_pesos()

    @staticmethod
    def _normalizar_regularizacion(nombre: Optional[str]) -> str:
        clave = str(nombre or "l2").strip().lower().replace("-", "_")
        return clave if clave in ("l1", "l2", "elasticnet") else "l2"

    @staticmethod
    def _normalizar_ensemble(nombre: Optional[str]) -> str:
        clave = str(nombre or "weighted").strip().lower()
        return (clave if clave in ("average", "weighted", "majority")
                else "weighted")

    @staticmethod
    def _normalizar_precision(precision: Optional[str]) -> str:
        clave = str(precision or "float64").strip().lower()
        return clave if clave in ("float64", "float32", "float16") else (
            "float64"
        )

    def inicializar_pesos(self) -> None:
        """Cabeza lineal minima para compatibilidad estadistica."""
        limite = math.sqrt(6.0 / max(1, self.input_size + self.output_size))
        self.pesos = self._rng.uniform(
            -limite, limite, (self.input_size, self.output_size)
        ).astype(self._precision)
        self.sesgo = np.zeros((1, self.output_size), dtype=self._precision)

    # ------------------------------------------------------------------
    # Configuracion de IA local
    # ------------------------------------------------------------------
    def autoconfigurar(
        self, X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None, perfil: str = "auto",
        aplicar: bool = True,
    ) -> Dict[str, Any]:
        """Perfila el equipo y recomienda una configuracion local."""
        if X is not None:
            matriz, _ = self._validar_entrada(X, permitir_1d=False)
            n_samples, n_features = matriz.shape
        else:
            n_samples, n_features = self._n_samples or 100, self.input_size
        tarea = self._tarea
        if y is not None:
            tarea = (self.NucleoIntegrado.inferir_tarea(y)
                     if self._tarea_config == "auto"
                     else self._tarea_config)
        n_outputs = int(self.output_size)
        configuracion = self._configurador.recomendar(
            tarea, n_samples, n_features, n_outputs, perfil
        )
        if aplicar:
            self.aplicar_configuracion(configuracion)
        return configuracion

    def configurar_ia_local(self, X: Optional[np.ndarray] = None,
                            y: Optional[np.ndarray] = None,
                            perfil: str = "auto",
                            aplicar: bool = True) -> Dict[str, Any]:
        return self.autoconfigurar(X, y, perfil, aplicar)

    def aplicar_configuracion(self, configuracion: Dict[str, Any]) -> None:
        """Aplica una configuracion validada a la neurona."""
        self._configuracion_ia = dict(configuracion)
        if 'hidden_sizes' in configuracion:
            self._hidden_sizes = tuple(
                int(h) for h in configuracion['hidden_sizes']
                if int(h) > 0
            )
        if 'batch_size' in configuracion:
            self._batch_size = max(1, int(configuracion['batch_size']))
        if 'epochs' in configuracion:
            self._epochs = max(1, int(configuracion['epochs']))
        if 'learning_rate' in configuracion:
            self._learning_rate = float(configuracion['learning_rate'])
        if 'dropout' in configuracion:
            self._dropout = min(0.9, max(0.0, float(
                configuracion['dropout']
            )))
        if 'weight_decay' in configuracion:
            self._weight_decay = max(0.0, float(
                configuracion['weight_decay']
            ))
        if 'precision' in configuracion:
            self._precision = self._normalizar_precision(
                configuracion['precision']
            )
        if 'ensemble_method' in configuracion:
            self._ensemble_method = self._normalizar_ensemble(
                configuracion['ensemble_method']
            )
        if 'early_stopping' in configuracion:
            self._early_stopping = max(0, int(
                configuracion['early_stopping']
            ))

    def exportar_configuracion(self, ruta: Optional[str] = None) -> str:
        texto = self._configurador.exportar_json(
            self._configuracion_ia
            or self.get_config()
        )
        if ruta is not None:
            with open(ruta, 'w', encoding='utf-8') as archivo:
                archivo.write(texto)
        return texto

    def cargar_configuracion(self, ruta: str,
                             aplicar: bool = True) -> Dict[str, Any]:
        with open(ruta, 'r', encoding='utf-8') as archivo:
            configuracion = self._configurador.importar_json(
                archivo.read()
            )
        if aplicar:
            self.aplicar_configuracion(configuracion)
        return configuracion

    def estimar_recursos(self) -> Dict[str, Any]:
        return self._configurador.estimar_recursos(
            self.get_config(), max(1, self._n_samples), self.input_size,
            max(1, self._n_outputs or self.output_size),
        )

    def reporte_recursos(self) -> str:
        hardware = self._configurador.perfilar_equipo()
        recursos = self.estimar_recursos()
        return "\n".join([
            f"=== Recursos {self.nombre} ===",
            (f"CPU: {hardware['cpu_count']} | RAM: "
             f"{hardware['ram_total_mb']:.0f} MB | VRAM: "
             f"{hardware['vram_mb']:.0f} MB | Dispositivo: "
             f"{hardware['dispositivo']}"),
            (f"Modelo: {recursos['parametros']} parametros | RAM: "
             f"{recursos['ram_mb']:.3f} MB | VRAM: "
             f"{recursos['vram_mb']:.3f} MB | Disco: "
             f"{recursos['disco_mb']:.3f} MB"),
            (f"Precision: {recursos['precision']} | Lote: "
             f"{self._batch_size} | Epocas: {self._epochs}"),
        ])

    # ------------------------------------------------------------------
    # Validacion y entrenamiento
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

    def _predecir_modelo(self, modelo: Dict[str, Any],
                         X: np.ndarray) -> np.ndarray:
        if modelo['tipo'] == 'lineal':
            return self._nucleo.predecir_lineal(X, modelo['parametros'])
        return self._nucleo.predecir_mlp(
            X, modelo['parametros'], self._activation, self._tarea
        )

    def _predecir_ensemble(self, X: np.ndarray) -> np.ndarray:
        if not self._modelos:
            return np.zeros((len(X), max(1, self._n_outputs or 1)))
        predicciones = [
            self._predecir_modelo(modelo, X) * float(modelo.get('peso', 1.0))
            for modelo in self._modelos
        ]
        return np.sum(predicciones, axis=0)

    def train(self, X: np.ndarray, y: np.ndarray,
              epochs: Optional[int] = None,
              learning_rate: Optional[float] = None,
              verbose: bool = False, **kwargs: Any) -> Dict[str, Any]:
        """Entrena los modelos base y calcula los pesos del ensemble."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        if epochs is not None:
            self._epochs = max(1, int(epochs))
        if learning_rate is not None:
            self._learning_rate = float(learning_rate)
        self._tarea = (self.NucleoIntegrado.inferir_tarea(y)
                       if self._tarea_config == "auto"
                       else self._tarea_config)
        datos = self._nucleo.preparar_objetivo(y, self._tarea)
        codificado = datos['codificado']
        self._classes = datos['clases']
        self._n_classes = int(datos['n_classes'])
        self._n_outputs = int(datos['n_outputs'])
        self.output_size = int(self._n_outputs)
        self._n_samples = int(matriz.shape[0])
        inicio = time.perf_counter()
        self._scaler = FeatureStandardizer().fit(matriz)
        matriz_escalada = self._scaler.transform(matriz)
        self._rng = np.random.default_rng(self._seed)
        indices_train, indices_val = self._nucleo.dividir(
            codificado if self._tarea == 'clasificacion' else y,
            self._tarea, self._validation_split, self._rng,
        )
        X_train = matriz_escalada[indices_train]
        X_val = (matriz_escalada[indices_val]
                 if len(indices_val) else None)
        if self._tarea == 'clasificacion':
            y_train = codificado[indices_train]
            y_val = (codificado[indices_val]
                     if len(indices_val) else None)
        else:
            y_train = np.asarray(y, dtype=np.float64).reshape(
                -1, self._n_outputs
            )[indices_train]
            y_val = (np.asarray(y, dtype=np.float64).reshape(
                -1, self._n_outputs
            )[indices_val] if len(indices_val) else None)

        modelos: List[Dict[str, Any]] = []
        if self._usar_lineal:
            if self._tarea == 'regresion':
                parametros = self._nucleo.resolver_lineal(
                    X_train, y_train, self._weight_decay
                )
                pred = self._nucleo.predecir_lineal(
                    X_val, parametros
                ) if X_val is not None else None
                puntaje = (self._nucleo.perdida(
                    'regresion', pred, y_val
                ) if pred is not None and y_val is not None else 0.0)
                modelos.append({
                    'tipo': 'lineal', 'nombre': 'ridge',
                    'parametros': parametros, 'puntaje': puntaje,
                    'historial': [],
                })
            else:
                resultado = self._nucleo.entrenar_mlp(
                    X_train, y_train, tarea='clasificacion',
                    hidden_sizes=(), activacion='linear',
                    epochs=self._epochs, batch_size=self._batch_size,
                    learning_rate=self._learning_rate,
                    weight_decay=self._weight_decay, dropout=0.0,
                    seed=self._seed, X_val=X_val, y_val=y_val,
                    early_stopping=self._early_stopping, verbose=verbose,
                )
                if X_val is not None and y_val is not None:
                    pred = self._nucleo.predecir_mlp(
                        X_val, resultado['parametros'],
                        'linear', 'clasificacion',
                    )
                    error = 1.0 - self._nucleo.metricas(
                        'clasificacion', pred, y_val, self._classes
                    )['accuracy']
                else:
                    error = resultado['mejor_perdida']
                modelos.append({
                    'tipo': 'mlp', 'nombre': 'logistico',
                    'parametros': resultado['parametros'],
                    'puntaje': float(error),
                    'historial': resultado['historial'],
                })

        if self._usar_mlp and self._hidden_sizes:
            resultado = self._nucleo.entrenar_mlp(
                X_train, y_train, tarea=self._tarea,
                hidden_sizes=self._hidden_sizes,
                activacion=self._activation,
                epochs=self._epochs, batch_size=self._batch_size,
                learning_rate=self._learning_rate,
                weight_decay=self._weight_decay, dropout=self._dropout,
                seed=self._seed + 1, X_val=X_val, y_val=y_val,
                early_stopping=self._early_stopping, verbose=verbose,
            )
            if X_val is not None and y_val is not None:
                pred = self._nucleo.predecir_mlp(
                    X_val, resultado['parametros'],
                    self._activation, self._tarea,
                )
                if self._tarea == 'clasificacion':
                    error = 1.0 - self._nucleo.metricas(
                        'clasificacion', pred, y_val, self._classes
                    )['accuracy']
                else:
                    error = self._nucleo.perdida(
                        'regresion', pred, y_val
                    )
            else:
                error = resultado['mejor_perdida']
            modelos.append({
                'tipo': 'mlp', 'nombre': 'mlp',
                'parametros': resultado['parametros'],
                'puntaje': float(error),
                'historial': resultado['historial'],
            })

        if not modelos:
            raise RuntimeError("No se configuro ningun modelo base")

        pesos = self._nucleo.pesos_ensemble(
            [modelo['puntaje'] for modelo in modelos],
            self._ensemble_method,
        )
        for modelo, peso in zip(modelos, pesos):
            modelo['peso'] = float(peso)
        self._modelos = modelos
        self._convergence_history = []
        self._loss_history = []
        for modelo in modelos:
            historial = modelo.get('historial') or []
            if historial:
                self._convergence_history.extend(
                    float(v) for v in historial
                )
                self._loss_history.extend(
                    float(v) for v in historial
                )
        if not self._loss_history:
            perdida = self._nucleo.perdida(
                self._tarea, self._predecir_ensemble(matriz_escalada),
                codificado if self._tarea == 'clasificacion' else y,
            )
            self._convergence_history = [float(perdida)]
            self._loss_history = [float(perdida)]
        self._is_fitted = True
        self._training_time = time.perf_counter() - inicio
        prediccion = self._predecir_ensemble(matriz_escalada)
        if self._tarea == 'clasificacion':
            self._val_accuracy = float(
                self._nucleo.metricas(
                    'clasificacion', self.predict_classes(matriz),
                    codificado, self._classes,
                )['accuracy']
            )
        else:
            self._val_accuracy = 0.0
        return {
            'losses': list(self._loss_history),
            'final_loss': (float(self._loss_history[-1])
                           if self._loss_history else float('nan')),
            'training_time': float(self._training_time),
            'val_accuracy': float(self._val_accuracy),
            'task': self._tarea,
            'weights': {modelo['nombre']: modelo['peso']
                        for modelo in modelos},
        }

    def fit(self, X: np.ndarray, y: np.ndarray,
            epochs: Optional[int] = None,
            learning_rate: Optional[float] = None,
            verbose: bool = False, **kwargs: Any
            ) -> "NeuronaAprendizajeIntegrado":
        self.train(X, y, epochs=epochs,
                   learning_rate=learning_rate, verbose=verbose, **kwargs)
        return self

    # ------------------------------------------------------------------
    # Prediccion
    # ------------------------------------------------------------------
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilidades de clase (solo clasificacion)."""
        if not self._is_fitted:
            raise RuntimeError("Modelo no entrenado: llama a fit primero")
        if self._tarea != 'clasificacion':
            raise ValueError("predict_proba solo aplica a clasificacion")
        matriz, unico = self._validar_entrada(X)
        matriz = self._scaler.transform(matriz)
        proba = self._predecir_ensemble(matriz)
        proba = np.clip(proba, 1e-12, 1.0)
        proba = proba / np.maximum(
            np.sum(proba, axis=1, keepdims=True), 1e-12
        )
        return proba[0] if unico else proba

    def predict_classes(self, X: np.ndarray) -> np.ndarray:
        """Clases predichas (indices o etiquetas originales)."""
        if not self._is_fitted:
            raise RuntimeError("Modelo no entrenado: llama a fit primero")
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        if self._tarea == 'clasificacion':
            proba = self.predict_proba(matriz)
            indices = np.argmax(proba, axis=1)
            if self._ensemble_method == 'majority' and self._modelos:
                votos = []
                for modelo in self._modelos:
                    p = self._predecir_modelo(modelo, matriz)
                    votos.append(np.argmax(p, axis=1))
                votos = np.asarray(votos)
                indices = np.array([
                    np.bincount(votos[:, i]).argmax()
                    for i in range(votos.shape[1])
                ])
            return np.asarray(self._classes)[indices]
        return (np.asarray(self.predict(X)).ravel() >= 0.5).astype(int)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Prediccion: probabilidades/clases o valores de regresion."""
        if not self._is_fitted:
            raise RuntimeError("Modelo no entrenado: llama a fit primero")
        matriz, unico = self._validar_entrada(X)
        matriz = self._scaler.transform(matriz)
        salida = self._predecir_ensemble(matriz)
        if self._tarea == 'clasificacion':
            if self._ensemble_method == 'majority' and self._modelos:
                votos = []
                for modelo in self._modelos:
                    p = self._predecir_modelo(modelo, matriz)
                    votos.append(np.argmax(p, axis=1))
                votos = np.asarray(votos)
                indices = np.array([
                    np.bincount(votos[:, i]).argmax()
                    for i in range(votos.shape[1])
                ])
                salida = np.asarray(self._classes)[indices]
            else:
                salida = np.asarray(self._classes)[
                    np.argmax(salida, axis=1)
                ]
        else:
            if salida.ndim == 2 and salida.shape[1] == 1:
                salida = salida.reshape(-1)
        return salida[0] if unico else salida

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Salida integrada de la neurona."""
        matriz, unico = self._validar_entrada(entrada)
        salida = self.predict(matriz)
        self.historial_activaciones.append(np.array(salida, copy=True))
        self.pasos += 1
        return salida[0] if unico else salida

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------
    def compute_loss(self, y_true: np.ndarray,
                     y_pred: np.ndarray) -> float:
        """MSE con regularizacion (compatibilidad historica)."""
        real = np.asarray(y_true, dtype=np.float64)
        pred = np.asarray(y_pred, dtype=np.float64)
        if real.shape != pred.shape:
            pred = pred.reshape(real.shape)
        mse = float(np.mean((real - pred) ** 2))
        if self.pesos is not None and self._reg_lambda > 0.0:
            if self._regularization == 'l2':
                mse += 0.5 * self._reg_lambda * float(
                    np.sum(self.pesos ** 2)
                )
            else:
                mse += self._reg_lambda * float(
                    np.sum(np.abs(self.pesos))
                )
        return float(mse)

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Gradiente de la cabeza lineal historica."""
        matriz, _ = self._validar_entrada(entrada, permitir_1d=False)
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(-1, 1)
        n = max(1, matriz.shape[0])
        grad_pesos = matriz.T @ gradiente / n
        if self.pesos is not None and self._reg_lambda > 0.0:
            grad_pesos += (self._reg_lambda * self.pesos
                           if self._regularization == 'l2'
                           else self._reg_lambda * np.sign(self.pesos))
        grad_sesgo = np.sum(gradiente, axis=0, keepdims=True) / n
        self.historial_gradientes.append({
            'pesos': grad_pesos.copy(),
            'norma': float(np.linalg.norm(grad_pesos)),
        })
        return grad_pesos, grad_sesgo

    def r2_score(self, y_true: np.ndarray,
                 y_pred: np.ndarray) -> float:
        return float(self._nucleo.metricas(
            'regresion', y_pred, y_true
        )['r2'])

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Metricas completas segun la tarea."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        if self._tarea == 'clasificacion':
            datos = self._nucleo.preparar_objetivo(y, 'clasificacion')
            proba = self.predict_proba(matriz)
            predicho = self.predict_classes(matriz)
            metricas = self._nucleo.metricas(
                'clasificacion', proba, datos['codificado'],
                datos['clases'],
            )
            metricas['predictions'] = predicho
            metricas['classes'] = predicho
            metricas['loss'] = float(-np.mean(np.log(np.clip(
                proba[np.arange(len(datos['codificado'])),
                      datos['codificado']], 1e-12, 1.0
            ))))
            self._val_accuracy = float(metricas['accuracy'])
            return metricas
        valores = np.asarray(y, dtype=np.float64)
        if valores.ndim == 1:
            valores = valores.reshape(-1, 1)
        prediccion = self.predict(matriz)
        if np.asarray(prediccion).ndim == 1:
            prediccion = np.asarray(prediccion).reshape(-1, 1)
        metricas = self._nucleo.metricas(
            'regresion', prediccion, valores
        )
        metricas['predictions'] = prediccion
        metricas['n_samples'] = int(len(matriz))
        metricas['loss'] = float(np.mean(
            (prediccion - valores) ** 2
        ))
        return metricas

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        metricas = self.evaluate(X, y)
        return float(metricas.get(
            'accuracy', metricas.get('r2', 0.0)
        ))

    # ------------------------------------------------------------------
    # API historica de ensemble
    # ------------------------------------------------------------------
    def add_model(self, model: Any) -> None:
        self._models.append(model)

    def get_ensemble_predictions(self, X: np.ndarray) -> np.ndarray:
        base = self.predict(X)
        if not self._models:
            return base
        predicciones = []
        for modelo in self._models:
            if hasattr(modelo, 'predict'):
                predicciones.append(np.asarray(modelo.predict(X)))
            else:
                predicciones.append(np.asarray(modelo))
        predicciones.append(np.asarray(base))
        return np.mean(predicciones, axis=0)

    def enable_ensemble(self, method: str = "majority") -> None:
        self._ensemble_method = self._normalizar_ensemble(method)

    def enable_early_stopping(self, patience: int = 20) -> None:
        self._early_stopping = max(0, int(patience))

    def set_regularization(self, reg_type: str,
                           lambda_val: float = 0.01) -> None:
        self._regularization = self._normalizar_regularizacion(reg_type)
        self._reg_lambda = max(0.0, float(lambda_val))

    def get_loss_history(self) -> List[float]:
        return list(self._loss_history)

    def get_models_count(self) -> int:
        return len(self._models)

    def params_count(self) -> int:
        """Parametros efectivos del ensemble (no la cabeza historica)."""
        total = 0
        for modelo in self._modelos:
            parametros = modelo.get('parametros')
            if isinstance(parametros, dict):
                total += int(sum(np.size(v) for v in parametros.values()
                                 if v is not None))
            elif isinstance(parametros, (list, tuple)):
                total += int(sum(np.size(v) for v in parametros))
        return int(total)

    @property
    def classes_(self) -> Optional[np.ndarray]:
        return None if self._classes is None else self._classes.copy()

    @property
    def n_features_in_(self) -> int:
        return int(self.input_size)

    @property
    def modelos_(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._modelos)

    # ------------------------------------------------------------------
    # Informacion y estabilidad
    # ------------------------------------------------------------------
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
        stats['val_accuracy'] = self._val_accuracy
        stats['n_models'] = len(self._models)
        stats['ensemble_method'] = self._ensemble_method
        stats['early_stopping'] = self._early_stopping
        stats['training_time'] = self._training_time
        return stats

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'aprendizaje_integrado',
            'task': self._tarea,
            'is_fitted': self._is_fitted,
            'n_samples': self._n_samples,
            'n_classes': self._n_classes,
            'n_outputs': self._n_outputs,
            'ensemble_method': self._ensemble_method,
            'n_modelos': len(self._modelos),
            'modelos': [
                {
                    'nombre': modelo['nombre'],
                    'tipo': modelo['tipo'],
                    'peso': float(modelo.get('peso', 0.0)),
                    'puntaje': float(modelo.get('puntaje', 0.0)),
                }
                for modelo in self._modelos
            ],
            'val_accuracy': self._val_accuracy,
            'training_time': self._training_time,
            'configuracion_ia': dict(self._configuracion_ia),
            'nucleo': self._nucleo.resumen(),
            'configurador': self._configurador.resumen(),
        })
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        ok: Dict[str, bool] = {
            'pesos_inicializados': self.pesos is not None,
            'sesgo_inicializado': self.sesgo is not None,
            'modelo_entrenado': bool(self._is_fitted),
            'modelos_base': bool(self._modelos),
        }
        if self.pesos is not None:
            ok['pesos_no_explosivos'] = float(
                np.max(np.abs(self.pesos))
            ) < 1e6
            ok['pesos_no_nan'] = not bool(np.any(np.isnan(self.pesos)))
            ok['pesos_no_inf'] = not bool(np.any(np.isinf(self.pesos)))
        if self._modelos:
            ok['pesos_modelos_finitos'] = all(
                bool(np.all(np.isfinite(parametro)))
                for modelo in self._modelos
                for parametro in (
                    modelo['parametros'].values()
                    if isinstance(modelo['parametros'], dict)
                    else modelo['parametros']
                )
            )
        ok['estable'] = all(ok.values())
        return ok

    # ------------------------------------------------------------------
    # Serializacion
    # ------------------------------------------------------------------
    def _estado(self) -> Dict[str, Any]:
        return {
            'version': __version__,
            'tipo': 'NeuronaAprendizajeIntegrado',
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'task': self._tarea,
            'task_config': self._tarea_config,
            'epochs': self._epochs,
            'batch_size': self._batch_size,
            'learning_rate': self._learning_rate,
            'hidden_sizes': list(self._hidden_sizes),
            'activation': self._activation,
            'dropout': self._dropout,
            'weight_decay': self._weight_decay,
            'regularization': self._regularization,
            'reg_lambda': self._reg_lambda,
            'validation_split': self._validation_split,
            'ensemble_method': self._ensemble_method,
            'early_stopping': self._early_stopping,
            'precision': self._precision,
            'seed': self._seed,
            'classes': self._classes,
            'n_classes': self._n_classes,
            'n_outputs': self._n_outputs,
            'is_fitted': self._is_fitted,
            'n_samples': self._n_samples,
            'modelos': copy.deepcopy(self._modelos),
            'scaler': (None if self._scaler is None
                       else self._scaler.get_params()),
            'convergence_history': list(self._convergence_history),
            'loss_history': list(self._loss_history),
            'training_time': self._training_time,
            'val_accuracy': self._val_accuracy,
            'configuracion_ia': dict(self._configuracion_ia),
            'pesos': self.pesos,
            'sesgo': self.sesgo,
            'pasos': self.pasos,
        }

    def save(self, filepath: str) -> None:
        with open(filepath, 'wb') as archivo:
            pickle.dump(self._estado(), archivo,
                        protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        with open(filepath, 'rb') as archivo:
            estado = pickle.load(archivo)
        self._cargar_estado(estado)

    def _cargar_estado(self, estado: Dict[str, Any]) -> None:
        if not isinstance(estado, dict):
            raise TypeError("Checkpoint no valido")
        self.nombre = str(estado.get('nombre', self.nombre))
        self.input_size = int(estado.get('input_size', self.input_size))
        self.output_size = int(estado.get('output_size', self.output_size))
        self._tarea = str(estado.get('task', 'clasificacion'))
        self._tarea_config = str(estado.get(
            'task_config', self._tarea
        ))
        self._epochs = max(1, int(estado.get('epochs', 300)))
        self._batch_size = max(1, int(estado.get('batch_size', 32)))
        self._learning_rate = float(estado.get('learning_rate', 0.01))
        self._hidden_sizes = tuple(
            int(h) for h in estado.get('hidden_sizes', (32, 16))
        )
        self._activation = str(estado.get('activation', 'relu'))
        self._dropout = float(estado.get('dropout', 0.0))
        self._weight_decay = float(estado.get('weight_decay', 1e-4))
        self._regularization = self._normalizar_regularizacion(
            estado.get('regularization', 'l2')
        )
        self._reg_lambda = float(estado.get('reg_lambda', 0.01))
        self._validation_split = float(estado.get(
            'validation_split', 0.2
        ))
        self._ensemble_method = self._normalizar_ensemble(
            estado.get('ensemble_method', 'weighted')
        )
        self._early_stopping = int(estado.get('early_stopping', 20))
        self._precision = self._normalizar_precision(
            estado.get('precision', 'float64')
        )
        self._seed = int(estado.get('seed', 2026))
        self._rng = np.random.default_rng(self._seed)
        self._classes = (None if estado.get('classes') is None
                         else np.asarray(estado['classes']))
        self._n_classes = int(estado.get('n_classes', 0))
        self._n_outputs = int(estado.get('n_outputs', 0))
        self._is_fitted = bool(estado.get('is_fitted', True))
        self._n_samples = int(estado.get('n_samples', 0))
        self._modelos = copy.deepcopy(estado.get('modelos', []))
        scaler = estado.get('scaler')
        if isinstance(scaler, dict):
            self._scaler = FeatureStandardizer()
            self._scaler._mean = scaler.get('mean')
            self._scaler._std = scaler.get('std')
        else:
            self._scaler = None
        self._convergence_history = [
            float(v) for v in estado.get('convergence_history', [])
        ]
        self._loss_history = [
            float(v) for v in estado.get('loss_history', [])
        ]
        self._training_time = float(estado.get('training_time', 0.0))
        self._val_accuracy = float(estado.get('val_accuracy', 0.0))
        self._configuracion_ia = dict(estado.get('configuracion_ia', {}))
        self.pesos = estado.get('pesos')
        self.sesgo = estado.get('sesgo')
        self.pasos = int(estado.get('pasos', 0))
        self._nucleo = self.NucleoIntegrado()
        self._configurador = self.ConfiguradorIALocal()

    def get_config(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'task': self._tarea,
            'epochs': self._epochs,
            'batch_size': self._batch_size,
            'learning_rate': self._learning_rate,
            'hidden_sizes': list(self._hidden_sizes),
            'activation': self._activation,
            'dropout': self._dropout,
            'weight_decay': self._weight_decay,
            'regularization': self._regularization,
            'reg_lambda': self._reg_lambda,
            'validation_split': self._validation_split,
            'ensemble_method': self._ensemble_method,
            'early_stopping': self._early_stopping,
            'precision': self._precision,
            'seed': self._seed,
        }

    def summary(self) -> str:
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {self.nombre} ===",
            (f"Tarea: {self._tarea}, Ensemble: "
             f"{self._ensemble_method}"),
            (f"Modelos: {len(self._modelos)} | Epocas: "
             f"{self._epochs} | Batch: {self._batch_size}"),
            (f"Input: {self.input_size}, Output: {self.output_size}, "
             f"Clases: {self._n_classes}"),
            (f"Fitted: {stats.get('is_fitted', False)}, "
             f"Acc/R2: {stats.get('val_accuracy', 0.0):.4f}"),
        ])

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},"
                f"sal={self.output_size},pasos={self.pasos})")


# ---------------------------------------------------------------------------
# Utilidades historicas
# ---------------------------------------------------------------------------
class FeatureStandardizer:
    def __init__(self):
        self._mean: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> "FeatureStandardizer":
        datos = np.asarray(X, dtype=np.float64)
        if datos.ndim != 2:
            raise ValueError("X debe ser 2D")
        self._mean = np.mean(datos, axis=0)
        self._std = np.std(datos, axis=0) + 1e-8
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self._mean is None or self._std is None:
            raise RuntimeError("FeatureStandardizer no ajustado")
        return (np.asarray(X, dtype=np.float64) - self._mean) / self._std

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)

    def get_params(self) -> Dict[str, np.ndarray]:
        return {
            'mean': (self._mean.copy()
                     if self._mean is not None else None),
            'std': (self._std.copy()
                    if self._std is not None else None),
        }


class EnsembleManager:
    def __init__(self, method: str = "average"):
        self.method = (method if method in ("majority", "average", "weighted")
                       else "average")
        self._models: List[Any] = []
        self._weights: List[float] = []

    def add(self, model: Any, weight: float = 1.0) -> None:
        self._models.append(model)
        self._weights.append(max(0.01, float(weight)))

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._models:
            raise RuntimeError("Sin modelos")
        preds = []
        for modelo in self._models:
            preds.append(modelo.predict(X) if hasattr(modelo, 'predict')
                         else np.asarray(modelo))
        if self.method == "majority":
            stacked = np.array([
                np.argmax(p, axis=1) if np.asarray(p).ndim > 1 else p
                for p in preds
            ])
            return np.array([
                np.bincount(stacked[:, i]).argmax()
                for i in range(stacked.shape[1])
            ])
        if self.method == "weighted":
            pesos = np.asarray(self._weights, dtype=np.float64)
            pesos = pesos / max(1e-12, float(np.sum(pesos)))
            return np.sum(np.asarray(preds) * pesos.reshape(-1, 1), axis=0)
        return np.mean(preds, axis=0)

    def get_count(self) -> int:
        return len(self._models)


class DataSplitter:
    def __init__(self, val_ratio: float = 0.2,
                 test_ratio: float = 0.2, seed: int = 42):
        self.val_ratio = max(0.0, min(0.99, float(val_ratio)))
        self.test_ratio = max(0.0, min(0.99, float(test_ratio)))
        self.seed = int(seed)
        self._train_idx: Optional[np.ndarray] = None
        self._val_idx: Optional[np.ndarray] = None
        self._test_idx: Optional[np.ndarray] = None

    def split(self, X: np.ndarray, y: Optional[np.ndarray] = None
              ) -> Tuple[Tuple[np.ndarray, ...], ...]:
        generador = np.random.default_rng(self.seed)
        n = len(X)
        n_test = int(n * self.test_ratio)
        n_val = int(n * self.val_ratio)
        indices = generador.permutation(n)
        test_idx = indices[:n_test]
        val_idx = indices[n_test:n_test + n_val]
        train_idx = indices[n_test + n_val:]
        self._train_idx = train_idx
        self._val_idx = val_idx
        self._test_idx = test_idx
        if y is not None:
            return ((X[train_idx], y[train_idx]),
                    (X[val_idx], y[val_idx]),
                    (X[test_idx], y[test_idx]))
        return ((X[train_idx],), (X[val_idx],), (X[test_idx],))

    def get_sizes(self, n: int) -> Dict[str, int]:
        n_test = int(n * self.test_ratio)
        n_val = int(n * self.val_ratio)
        return {'train': n - n_test - n_val, 'val': n_val, 'test': n_test}


class ModelValidator:
    def __init__(self, n_folds: int = 5):
        self.n_folds = max(2, int(n_folds))
        self._scores: List[float] = []

    def validate(self, model: Any, X: np.ndarray, y: np.ndarray,
                 metric: str = "accuracy") -> float:
        n = len(X)
        fold_size = n // self.n_folds
        scores = []
        for fold in range(self.n_folds):
            inicio = fold * fold_size
            fin = (inicio + fold_size if fold < self.n_folds - 1 else n)
            X_test = X[inicio:fin]
            y_test = y[inicio:fin]
            X_train = np.concatenate([X[:inicio], X[fin:]])
            y_train = np.concatenate([y[:inicio], y[fin:]])
            if hasattr(model, 'train'):
                try:
                    model.train(X_train, y_train, epochs=1, verbose=False)
                except TypeError:
                    model.train(X_train, y_train)
            pred = model.predict(X_test) if hasattr(model, 'predict') else None
            if pred is not None and metric == "accuracy":
                if np.asarray(y_test).ndim > 1:
                    aciertos = float(np.mean(
                        np.argmax(pred, axis=1)
                        == np.argmax(y_test, axis=1)
                    ))
                else:
                    aciertos = float(np.mean(
                        np.asarray(pred).ravel()
                        == np.asarray(y_test).ravel()
                    ))
                scores.append(aciertos)
        self._scores = scores
        return float(np.mean(scores)) if scores else 0.0

    def get_scores(self) -> List[float]:
        return list(self._scores)


class SupervisedTrainer:
    def __init__(self, model: Any, X: np.ndarray, y: np.ndarray):
        self.model = model
        self.X = X
        self.y = y
        self._history: List[Dict[str, Any]] = []

    def run_training(self, epochs: int, **kwargs: Any) -> Dict[str, Any]:
        resultado = self.model.train(self.X, self.y, epochs=epochs, **kwargs)
        self._history.append({'epochs': epochs, 'result': resultado})
        return resultado

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        if hasattr(self.model, 'evaluate'):
            return self.model.evaluate(X, y)
        pred = (self.model.predict(X)
                if hasattr(self.model, 'predict') else self.model)
        return {'predictions': pred}

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)


class PredictionAggregator:
    def __init__(self, strategy: str = "mean"):
        self.strategy = (strategy if strategy in ("mean", "median", "weighted")
                         else "mean")

    def aggregate(self, predictions: List[np.ndarray]) -> np.ndarray:
        if not predictions:
            raise ValueError("Sin predicciones")
        if self.strategy == "median":
            return np.median(np.asarray(predictions), axis=0)
        return np.mean(np.asarray(predictions), axis=0)

    def aggregate_weighted(self, predictions: List[np.ndarray],
                           weights: List[float]) -> np.ndarray:
        matriz = np.asarray(predictions, dtype=np.float64)
        pesos = np.asarray(weights, dtype=np.float64)
        pesos = pesos / max(1e-12, float(np.sum(pesos)))
        return np.sum(matriz * pesos.reshape(-1, *([1] * (matriz.ndim - 1))),
                      axis=0)

    def get_strategy(self) -> str:
        return self.strategy

    def count_predictions(self, predictions: List[np.ndarray]) -> int:
        return sum(len(p) for p in predictions)


# ---------------------------------------------------------------------------
# Adaptador de compatibilidad con la API historica de RF_SL1_10
# ---------------------------------------------------------------------------
class IntegratedSupervisedLearningOptimizer(NeuronaAprendizajeIntegrado):
    """Aprendizaje integrado real con la API historica de RF_SL1_10."""

    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "IntegratedSupervisedLearningOptimizer",
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("epochs", 500)
        kwargs.setdefault("ensemble_method", "majority")
        super().__init__(
            input_size=input_size, output_size=output_size,
            nombre=nombre, **kwargs,
        )


# ---------------------------------------------------------------------------
# Fabrica, utilidades y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "integrado", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaAprendizajeIntegrado:
    """Fabrica una neurona integrada por nombre."""
    clave = str(tipo or "integrado").strip().lower().replace("-", "_")
    if clave in ("integrado", "integrated", "ensemble",
                 "supervisado", "supervised"):
        return NeuronaAprendizajeIntegrado(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("compat", "integrated_supervised_learning_optimizer",
                 "optimizer"):
        return IntegratedSupervisedLearningOptimizer(
            input_size=input_size, output_size=output_size, **kwargs
        )
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: integrado, ensemble, compat"
    )


def tipos_disponibles() -> List[str]:
    """Nombres aceptados por :func:`crear_neurona`."""
    return ["integrado", "ensemble", "compat"]


def create_integrated_supervised_learning_optimizer(
    input_size: int = 4, output_size: int = 8, **kwargs: Any,
) -> IntegratedSupervisedLearningOptimizer:
    """Fabrica historica de RF_SL1_10."""
    return IntegratedSupervisedLearningOptimizer(
        input_size=input_size, output_size=output_size, **kwargs
    )


def entrenar_y_evaluar(modelo: NeuronaAprendizajeIntegrado, X: np.ndarray,
                       y: np.ndarray, epochs: int = 200,
                       **kwargs: Any) -> Dict[str, Any]:
    """Entrena y devuelve historial y metricas."""
    resultado = modelo.train(X, y, epochs=epochs, **kwargs)
    return {
        'modelo': modelo,
        'historial': resultado['losses'],
        'metricas': modelo.evaluate(X, y),
        'perdida_final': float(resultado['final_loss']),
    }


def benchmark_modelo(modelo: NeuronaAprendizajeIntegrado, X: np.ndarray,
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


def guardar_modelo(modelo: NeuronaAprendizajeIntegrado, ruta: str) -> None:
    """Serializa el objeto completo (pickle)."""
    with open(ruta, 'wb') as archivo:
        pickle.dump(modelo, archivo, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaAprendizajeIntegrado:
    """Carga un modelo serializado con :func:`guardar_modelo`."""
    with open(ruta, 'rb') as archivo:
        modelo = pickle.load(archivo)
    if not isinstance(modelo, NeuronaAprendizajeIntegrado):
        raise TypeError("El fichero no contiene una neurona integrada")
    return modelo


# ---------------------------------------------------------------------------
# Demostracion
# ---------------------------------------------------------------------------
def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_10_1.py``)."""
    generador = np.random.default_rng(2026)
    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_10_1 :: Aprendizaje integrado (v%s)"
          % __version__)
    print("=" * 78)

    n = 400
    X = generador.normal(size=(n, 3))
    y_reg = (X @ np.array([2.0, -1.0, 0.5])
             + 0.4 + generador.normal(scale=0.1, size=n))
    modelo = crear_neurona("integrado", 3, 1, epochs=200, seed=7)
    configuracion = modelo.autoconfigurar(X, y_reg)
    modelo.fit(X, y_reg)
    metricas = modelo.evaluate(X, y_reg)
    print("%-12s task=%s R2=%.6f MAE=%.6f"
          % ("regresion", modelo.get_config()['task'],
             metricas['r2'], metricas['mae']))
    print("Configuracion local:", configuracion['perfil'],
          configuracion['hidden_sizes'], configuracion['batch_size'])

    clases = (
        (X[:, 0] > 0.0).astype(int)
        + (X[:, 1] > 0.0).astype(int)
    )
    clasificador = crear_neurona("integrado", 3, 3, epochs=200, seed=11)
    clasificador.autoconfigurar(X, clases)
    clasificador.fit(X, clases)
    met_clf = clasificador.evaluate(X, clases)
    print("%-12s task=%s accuracy=%.4f F1=%.4f"
          % ("clasificacion", clasificador.get_config()['task'],
             met_clf['accuracy'], met_clf['f1_macro']))
    print("Modelos:", [
        (m['nombre'], round(m['peso'], 3))
        for m in clasificador._modelos
    ])
    print(clasificador.reporte_recursos())
    print("Benchmark:", benchmark_modelo(clasificador, X, repeticiones=3))
    print("=" * 78)
    return {'regresion': metricas, 'clasificacion': met_clf}


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaAprendizajeIntegrado',
    'IntegratedSupervisedLearningOptimizer',
    'EnsembleManager',
    'DataSplitter',
    'ModelValidator',
    'SupervisedTrainer',
    'PredictionAggregator',
    'FeatureStandardizer',
    'crear_neurona',
    'tipos_disponibles',
    'create_integrated_supervised_learning_optimizer',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_INTEGRATED_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
