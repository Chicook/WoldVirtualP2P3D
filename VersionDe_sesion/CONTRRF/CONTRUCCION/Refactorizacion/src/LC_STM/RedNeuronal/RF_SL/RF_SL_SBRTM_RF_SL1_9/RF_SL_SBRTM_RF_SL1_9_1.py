"""RF_SL_SBRTM_RF_SL1_9_1.py
Neuronas especializadas en regresion lineal (RF_SL - SBRTM - RF - 2026).
=========================================================================

Modulo autocontenido y preparado para importar. Completa el antiguo fragmento
(que solo tenia ``LossMSE``, ``GradientDescentLR``, ``NormalEquation``,
``FeatureStandardizer``, ``LinearPredictor`` y ``ModelMetrics``, sin la neurona
principal) y lo sustituye por una implementacion real de regresion lineal con
gestion de recursos:

  * ``NeuronaRegresionLineal``: neurona lineal para regresion monosalida y
      multi-salida.
      - Solucion cerrada OLS/SVD y Ridge por ecuaciones normales.
      - Lasso y ElasticNet por descenso coordinado con umbral suave.
      - SGD, momentum y Adam para datos grandes o entrenamiento por lotes.
      - Estandarizacion opcional de caracteristicas.
      - Metricas R2, MAE, RMSE, MAPE y MSE.
      - Serializacion normal y comprimida (gzip) y compatibilidad historica.

  * ``NeuronaRegresionLineal.NucleoRegresionLineal``: **clase anidada** que
      fusiona solvers (normal/ridge/coordenado), gradiente, optimizadores y
      metricas.

  * ``NeuronaRegresionLineal.GestorRecursos``: **clase anidada** especializada
      en tamano final en disco y consumo de RAM/VRAM. Estima bytes de
      parametros, gradientes, momentos del optimizador y lotes; mide el tamano
      serializado comprimido; recomputa el lote recomendado segun presupuesto;
      permite cuantizar a float32/float16 y podar pesos.

  * ``LinearRegressionOptimizer``: adaptador de compatibilidad con la API
      historica de RF_SL1_9 (``train``, ``predict``, ``predict_flat``,
      ``evaluate``, ``enable_normal_equation``, ``set_regularization``...).

  * Utilidades: ``LossMSE``, ``GradientDescentLR``, ``NormalEquation``,
      ``FeatureStandardizer``, ``LinearPredictor``, ``ModelMetrics``,
      ``crear_neurona``, ``tipos_disponibles``,
      ``create_linear_regression_optimizer``, ``entrenar_y_evaluar``,
      ``benchmark_modelo``, ``guardar_modelo``, ``cargar_modelo`` y ``demo``.

Referencias
-----------
- Ecuaciones normales, descomposicion SVD y regresion Ridge.
- Lasso/ElasticNet por descenso coordinado y umbral suave.
- Adam (Kingma & Ba, 2015).
- Cuantizacion float32/float16 y compresion gzip para reducir disco/RAM.

Uso
---
    from RF_SL_SBRTM_RF_SL1_9_1 import NeuronaRegresionLineal

    modelo = NeuronaRegresionLineal(input_size=3)
    modelo.fit(X, y)
    print(modelo.evaluate(X, y))
    print(modelo.estimar_recursos(X))
    modelo.comprimir("float32")
"""

from __future__ import annotations

import gzip
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
LUCIA_LINEAR_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "learning_rate": 0.01,
    "epochs": 200,
    "batch_size": 32,
    "regularization": "l2",
    "reg_lambda": 0.01,
    "l1_ratio": 0.5,
    "solver": "auto",
    "estandarizar": False,
    "dtype": "float64",
    "ram_budget_mb": None,
    "vram_budget_mb": None,
    "disk_budget_mb": None,
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

    _CLAVE_BASE = "_rf_snrtm_base_import_linear"
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
# Neurona de regresion lineal
# ---------------------------------------------------------------------------
class NeuronaRegresionLineal(NeuronaMemoriaBase):
    """Regresion lineal con solvers exactos, regularizados e iterativos.

    Parametros
    ----------
    input_size, output_size:
        Dimensiones declaradas (compatibilidad con la jerarquia).
    solver:
        ``auto``, ``normal``, ``svd``, ``ridge``, ``lasso``, ``elasticnet``,
        ``sgd``, ``momentum`` o ``adam``.
    regularization:
        ``none``, ``l1``, ``l2`` o ``elasticnet``.
    reg_lambda:
        Intensidad de regularizacion.
    l1_ratio:
        Proporcion L1 en ElasticNet.
    estandarizar:
        Estandariza las caracteristicas (z-score) antes de ajustar.
    dtype:
        ``float64``, ``float32`` o ``float16`` para pesos.
    ram_budget_mb, vram_budget_mb, disk_budget_mb:
        Presupuestos opcionales para comprobaciones de recursos.
    """

    # ------------------------------------------------------------------
    # Clase anidada 1: nucleo matematico
    # ------------------------------------------------------------------
    class NucleoRegresionLineal:
        """Fusiona solvers, gradientes, optimizadores y metricas."""

        EPS = 1e-12
        OPTIMIZADORES: Tuple[str, ...] = ("sgd", "momentum", "adam")

        def __init__(self, epsilon: float = 1e-12) -> None:
            self.epsilon = max(1e-15, float(epsilon))
            self.estado: Dict[str, Any] = {}
            self.reiniciar()

        def reiniciar(self) -> None:
            self.estado = {
                'velocidad': [],
                'momento': [],
                'varianza': [],
                't': 0,
            }

        # -- solvers --------------------------------------------------
        @staticmethod
        def _diseno(X: np.ndarray) -> np.ndarray:
            return np.hstack([
                np.asarray(X, dtype=np.float64),
                np.ones((len(X), 1), dtype=np.float64),
            ])

        @classmethod
        def resolver_lineal(cls, X: np.ndarray, y: np.ndarray,
                            alpha: float = 0.0) -> Tuple[np.ndarray,
                                                          np.ndarray]:
            """OLS o Ridge por ecuaciones normales/SVD."""
            matriz = np.asarray(X, dtype=np.float64)
            objetivo = np.asarray(y, dtype=np.float64)
            if objetivo.ndim == 1:
                objetivo = objetivo.reshape(-1, 1)
            diseno = cls._diseno(matriz)
            if alpha <= 0.0:
                theta, _, _, _ = np.linalg.lstsq(
                    diseno, objetivo, rcond=None
                )
            else:
                gram = diseno.T @ diseno
                penalizacion = alpha * np.eye(gram.shape[0])
                penalizacion[-1, -1] = 0.0
                sistema = gram + penalizacion
                lado_derecho = diseno.T @ objetivo
                try:
                    theta = np.linalg.solve(sistema, lado_derecho)
                except np.linalg.LinAlgError:
                    theta, _, _, _ = np.linalg.lstsq(
                        sistema, lado_derecho, rcond=None
                    )
            pesos = theta[:-1, :]
            sesgo = theta[-1, :].reshape(1, -1)
            return pesos, sesgo

        @staticmethod
        def umbral_suave(valor: float, umbral: float) -> float:
            if valor > umbral:
                return valor - umbral
            if valor < -umbral:
                return valor + umbral
            return 0.0

        @classmethod
        def coordinate_descent(
            cls, X: np.ndarray, y: np.ndarray, alpha: float,
            l1_ratio: float = 1.0, max_iter: int = 1000,
            tol: float = 1e-8,
        ) -> Tuple[np.ndarray, np.ndarray]:
            """Lasso/ElasticNet por descenso coordinado."""
            matriz = np.asarray(X, dtype=np.float64)
            objetivo = np.asarray(y, dtype=np.float64)
            if objetivo.ndim == 1:
                objetivo = objetivo.reshape(-1, 1)
            n, n_features = matriz.shape
            n_salidas = objetivo.shape[1]
            media_x = np.mean(matriz, axis=0)
            centro_x = matriz - media_x
            pesos = np.zeros((n_features, n_salidas), dtype=np.float64)
            sesgos = np.zeros((1, n_salidas), dtype=np.float64)
            for salida in range(n_salidas):
                valores = objetivo[:, salida]
                media_y = float(np.mean(valores))
                centro_y = valores - media_y
                w = np.zeros(n_features, dtype=np.float64)
                residual = centro_y.copy()
                normalizacion = np.einsum('ij,ij->j', centro_x, centro_x)
                for _ in range(max(1, int(max_iter))):
                    max_delta = 0.0
                    for feature in range(n_features):
                        columna = centro_x[:, feature]
                        rho = float(columna @ residual) \
                            + normalizacion[feature] * w[feature]
                        denominador = (
                            normalizacion[feature]
                            + alpha * (1.0 - l1_ratio)
                        )
                        if denominador <= cls.EPS:
                            nuevo = 0.0
                        else:
                            nuevo = cls.umbral_suave(
                                rho, alpha * l1_ratio
                            ) / denominador
                        delta = nuevo - w[feature]
                        if delta != 0.0:
                            residual -= columna * delta
                            w[feature] = nuevo
                        max_delta = max(max_delta, abs(delta))
                    if max_delta < tol:
                        break
                pesos[:, salida] = w
                sesgos[0, salida] = media_y - float(media_x @ w)
            return pesos, sesgos

        @staticmethod
        def gradiente_mse(prediccion: np.ndarray,
                          objetivo: np.ndarray) -> np.ndarray:
            pred = np.asarray(prediccion, dtype=np.float64)
            real = np.asarray(objetivo, dtype=np.float64)
            if pred.shape != real.shape:
                real = real.reshape(pred.shape)
            return 2.0 * (pred - real) / max(1, pred.size)

        def paso(self, parametros: Sequence[np.ndarray],
                 gradientes: Sequence[np.ndarray], *,
                 optimizador: str = "sgd", lr: float = 0.01,
                 momentum: float = 0.9, beta1: float = 0.9,
                 beta2: float = 0.999, epsilon: float = 1e-8,
                 weight_decay: float = 0.0) -> float:
            tipo = str(optimizador or "sgd").strip().lower()
            if tipo not in self.OPTIMIZADORES:
                raise ValueError(
                    f"Optimizador desconocido: {optimizador!r}"
                )
            if len(parametros) != len(gradientes):
                raise ValueError("Parametros y gradientes incompatibles")
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
            norma = math.sqrt(sum(
                float(np.sum(np.asarray(g, dtype=np.float64) ** 2))
                for g in gradientes
            ))
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
        def metricas(y_true: np.ndarray,
                     y_pred: np.ndarray) -> Dict[str, Any]:
            real = np.asarray(y_true, dtype=np.float64)
            pred = np.asarray(y_pred, dtype=np.float64)
            if real.shape != pred.shape:
                pred = pred.reshape(real.shape)
            error = pred - real
            mse = float(np.mean(error ** 2))
            varianza = float(np.sum((real - np.mean(real)) ** 2))
            if varianza > 1e-12:
                r2 = float(1.0 - np.sum(error ** 2) / varianza)
            elif mse <= 1e-12:
                r2 = 1.0
            else:
                r2 = 0.0
            mascara = real != 0.0
            mape = (float(np.mean(np.abs(
                (real[mascara] - pred[mascara]) / real[mascara]
            ))) if np.any(mascara) else float('inf'))
            return {
                'r2': r2,
                'mse': mse,
                'rmse': float(math.sqrt(max(0.0, mse))),
                'mae': float(np.mean(np.abs(error))),
                'mape': mape,
                'max_error': float(np.max(np.abs(error))) if error.size else 0.0,
                'n_samples': int(real.shape[0]),
            }

        def resumen(self) -> Dict[str, Any]:
            return {
                'optimizadores': list(self.OPTIMIZADORES),
                'epsilon': self.epsilon,
            }

    # ------------------------------------------------------------------
    # Clase anidada 2: gestion de disco, RAM y VRAM
    # ------------------------------------------------------------------
    class GestorRecursos:
        """Estima y reduce el consumo de disco, RAM y VRAM del modelo.

        La VRAM se estima de forma analitica (NumPy no reserva GPU); sirve
        para decidir si el modelo cabe en una GPU antes de moverlo.
        """

        BYTES: Dict[str, int] = {
            'float64': 8,
            'float32': 4,
            'float16': 2,
            'int32': 4,
            'int8': 1,
        }
        MB = 1024.0 * 1024.0

        @classmethod
        def bytes_de(cls, valor: Any,
                     dtype: Optional[str] = None) -> int:
            if valor is None:
                return 0
            arreglo = np.asarray(valor)
            if dtype is not None:
                ancho = cls.BYTES.get(str(dtype), arreglo.itemsize)
            else:
                ancho = arreglo.itemsize
            return int(arreglo.size * ancho)

        @classmethod
        def estimar_parametros(cls, pesos: np.ndarray,
                               sesgo: np.ndarray,
                               dtype: Optional[str] = None) -> int:
            return (cls.bytes_de(pesos, dtype)
                    + cls.bytes_de(sesgo, dtype))

        @classmethod
        def factor_optimizador(cls, optimizador: str) -> float:
            clave = str(optimizador or "sgd").strip().lower()
            return {'sgd': 1.0, 'momentum': 2.0, 'adam': 3.0}.get(
                clave, 1.0
            )

        @classmethod
        def estimar_memoria(
            cls, pesos: np.ndarray, sesgo: np.ndarray,
            X: Optional[np.ndarray] = None,
            batch_size: Optional[int] = None,
            dtype: Optional[str] = None,
            optimizador: str = "sgd",
        ) -> Dict[str, Any]:
            parametros = cls.estimar_parametros(pesos, sesgo, dtype)
            factor = cls.factor_optimizador(optimizador)
            ram_parametros = parametros * (1.0 + factor)
            ancho_lote = 0
            if X is not None:
                matriz = np.asarray(X)
                filas = matriz.shape[0]
                columnas = matriz.shape[1] if matriz.ndim > 1 else 1
                lote = filas if batch_size is None else max(
                    1, min(int(batch_size), filas)
                )
                salidas = (1 if sesgo is None else int(np.size(sesgo)))
                ancho_lote = int(
                    lote * (columnas + salidas * 3) * 8
                )
            ram = int(ram_parametros * 1.15 + ancho_lote)
            vram = int(ram_parametros * 1.10 + ancho_lote * 0.50)
            return {
                'parametros_bytes': int(parametros),
                'ram_parametros_bytes': int(ram_parametros),
                'ram_lote_bytes': int(ancho_lote),
                'ram_estimada_bytes': int(ram),
                'vram_estimada_bytes': int(vram),
                'ram_estimada_mb': float(ram / cls.MB),
                'vram_estimada_mb': float(vram / cls.MB),
                'factor_optimizador': float(factor),
                'dtype': str(dtype or getattr(pesos, 'dtype', 'float64')),
            }

        @classmethod
        def estimar_disco(cls, estado: Dict[str, Any],
                          comprimido: bool = True) -> Dict[str, Any]:
            datos = pickle.dumps(estado, protocol=pickle.HIGHEST_PROTOCOL)
            bruto = len(datos)
            reducido = len(gzip.compress(datos, compresslevel=6))
            return {
                'disco_bruto_bytes': int(bruto),
                'disco_comprimido_bytes': int(reducido),
                'disco_estimado_bytes': int(reducido if comprimido else bruto),
                'disco_bruto_mb': float(bruto / cls.MB),
                'disco_comprimido_mb': float(reducido / cls.MB),
                'ratio_compresion': float(
                    reducido / max(1, bruto)
                ),
            }

        @classmethod
        def convertir(cls, valor: np.ndarray,
                      dtype: str) -> np.ndarray:
            clave = str(dtype).strip().lower()
            if clave not in cls.BYTES:
                raise ValueError(
                    f"dtype no soportado: {dtype!r}. Usa float64, float32 "
                    "o float16"
                )
            return np.asarray(valor, dtype=clave)

        @classmethod
        def podar(cls, pesos: np.ndarray,
                  umbral: float = 1e-4) -> Tuple[np.ndarray, float]:
            matriz = np.array(pesos, copy=True)
            limite = max(0.0, float(umbral))
            if limite > 0.0:
                matriz[np.abs(matriz) < limite] = 0.0
            total = matriz.size
            ceros = int(np.sum(matriz == 0.0))
            return matriz, float(ceros / max(1, total))

        @classmethod
        def lote_recomendado(cls, X: np.ndarray,
                             ram_disponible_mb: Optional[float],
                             dtype: Optional[str] = None,
                             margen: float = 0.5) -> Optional[int]:
            if ram_disponible_mb is None:
                return None
            matriz = np.asarray(X)
            if matriz.ndim != 2 or matriz.shape[0] == 0:
                return None
            ancho = cls.BYTES.get(str(dtype), 8)
            bytes_fila = max(
                1, matriz.shape[1] * ancho + 64
            )
            disponible = max(
                0.0, float(ram_disponible_mb) * cls.MB * margen
            )
            lote = int(disponible // bytes_fila)
            return max(1, min(int(matriz.shape[0]), lote))

        @classmethod
        def presupuesto(
            cls, estimacion: Dict[str, Any],
            ram_budget_mb: Optional[float] = None,
            vram_budget_mb: Optional[float] = None,
            disk_budget_mb: Optional[float] = None,
        ) -> Dict[str, Any]:
            def _excede(valor_mb: float, limite: Optional[float]) -> bool:
                return bool(limite is not None and valor_mb > float(limite))

            ram_mb = float(estimacion.get('ram_estimada_mb', 0.0))
            vram_mb = float(estimacion.get('vram_estimada_mb', 0.0))
            if 'disco_comprimido_mb' in estimacion:
                disco_mb = float(estimacion['disco_comprimido_mb'])
            else:
                disco_mb = float(
                    estimacion.get('disco_estimado_bytes', 0)
                ) / cls.MB
            excesos = []
            if _excede(ram_mb, ram_budget_mb):
                excesos.append('ram')
            if _excede(vram_mb, vram_budget_mb):
                excesos.append('vram')
            if _excede(disco_mb, disk_budget_mb):
                excesos.append('disco')
            return {
                'ram_mb': ram_mb,
                'vram_mb': vram_mb,
                'disco_mb': disco_mb,
                'ram_ok': not _excede(ram_mb, ram_budget_mb),
                'vram_ok': not _excede(vram_mb, vram_budget_mb),
                'disco_ok': not _excede(disco_mb, disk_budget_mb),
                'cumple': not excesos,
                'excesos': excesos,
            }

        @classmethod
        def resumen(cls) -> Dict[str, Any]:
            return {
                'dtypes': dict(cls.BYTES),
                'unidad_mb': cls.MB,
                'soporta': [
                    'estimacion_ram', 'estimacion_vram',
                    'estimacion_disco', 'compresion_gzip',
                    'cuantizacion_float32_float16', 'poda_pesos',
                    'lote_recomendado', 'presupuesto',
                ],
            }

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "NeuronaRegresionLineal",
        *,
        learning_rate: float = 0.01,
        epochs: int = 200,
        batch_size: Optional[int] = 32,
        regularization: str = "l2",
        reg_lambda: float = 0.01,
        l1_ratio: float = 0.5,
        solver: str = "auto",
        estandarizar: bool = False,
        dtype: str = "float64",
        ram_budget_mb: Optional[float] = None,
        vram_budget_mb: Optional[float] = None,
        disk_budget_mb: Optional[float] = None,
        max_iter_cd: int = 1000,
        tol: float = 1e-8,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        if "normal_equation" in kwargs and solver == "auto":
            solver = "normal" if kwargs.pop("normal_equation") else "sgd"
        if "use_normal_eq" in kwargs and solver == "auto":
            solver = "normal" if kwargs.pop("use_normal_eq") else "sgd"
        if "reg_type" in kwargs and regularization == "l2":
            regularization = kwargs.pop("reg_type")
        if "lambda_val" in kwargs and reg_lambda == 0.01:
            reg_lambda = kwargs.pop("lambda_val")
        if "standardize" in kwargs and not estandarizar:
            estandarizar = bool(kwargs.pop("standardize"))
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
        self._solver = self._normalizar_solver(solver)
        self._estandarizar = bool(estandarizar)
        self._dtype = self._normalizar_dtype(dtype)
        self._ram_budget_mb = None if ram_budget_mb is None else float(
            ram_budget_mb
        )
        self._vram_budget_mb = None if vram_budget_mb is None else float(
            vram_budget_mb
        )
        self._disk_budget_mb = None if disk_budget_mb is None else float(
            disk_budget_mb
        )
        self._max_iter_cd = max(1, int(max_iter_cd))
        self._tol = max(1e-15, float(tol))
        self._seed = int(
            LUCIA_LINEAR_CONFIG["random_seed"] if seed is None else seed
        )
        self._rng = np.random.default_rng(self._seed)

        self._nucleo = self.NucleoRegresionLineal()
        self._gestor = self.GestorRecursos()
        self._scaler = FeatureStandardizer() if self._estandarizar else None

        self._is_fitted: bool = False
        self._convergence_history: List[float] = []
        self._loss_history: List[float] = []
        self._training_time: float = 0.0
        self._r2_score: float = 0.0
        self._n_samples: int = 0
        self._n_outputs: int = 0
        self._use_normal_eq: bool = self._solver in (
            "normal", "svd", "ridge"
        )

        self.inicializar_pesos()

    @staticmethod
    def _normalizar_regularizacion(nombre: Optional[str]) -> str:
        clave = str(nombre or "l2").strip().lower().replace("-", "_")
        alias = {
            "none": "none", "ninguna": "none", "sin": "none",
            "l1": "l1", "lasso": "l1",
            "l2": "l2", "ridge": "l2",
            "elasticnet": "elasticnet", "elastic_net": "elasticnet",
        }
        clave = alias.get(clave, clave)
        if clave not in ("none", "l1", "l2", "elasticnet"):
            raise ValueError(
                f"Regularizacion desconocida: {nombre!r}"
            )
        return clave

    @staticmethod
    def _normalizar_solver(nombre: Optional[str]) -> str:
        clave = str(nombre or "auto").strip().lower().replace("-", "_")
        alias = {
            "auto": "auto", "automatico": "auto",
            "normal": "normal", "ecuacion_normal": "normal",
            "closed": "normal", "cerrado": "normal",
            "svd": "svd", "lstsq": "svd",
            "ridge": "ridge", "lasso": "lasso",
            "elasticnet": "elasticnet", "elastic_net": "elasticnet",
            "coordinate": "elasticnet", "coordenado": "elasticnet",
            "sgd": "sgd", "gradiente": "sgd",
            "momentum": "momentum", "momento": "momentum",
            "adam": "adam",
        }
        clave = alias.get(clave, clave)
        validos = (
            "auto", "normal", "svd", "ridge", "lasso", "elasticnet",
            "sgd", "momentum", "adam",
        )
        if clave not in validos:
            raise ValueError(
                f"Solver desconocido: {nombre!r}. Usa uno de {validos}"
            )
        return clave

    @staticmethod
    def _normalizar_dtype(dtype: Any) -> str:
        clave = str(dtype or "float64").strip().lower()
        if clave not in ("float64", "float32", "float16"):
            raise ValueError(
                f"dtype no soportado: {dtype!r}. Usa float64, float32 "
                "o float16"
            )
        return clave

    def inicializar_pesos(self, n_outputs: Optional[int] = None) -> None:
        """Inicializa pesos pequenos y sesgo cero en el dtype configurado."""
        salidas = (self._n_outputs if n_outputs is None
                   else int(n_outputs))
        salidas = max(1, salidas if salidas > 0 else self.output_size)
        self.pesos = (
            self._rng.normal(0.0, 0.1, (self.input_size, salidas))
            .astype(self._dtype)
        )
        self.sesgo = np.zeros((1, salidas), dtype=self._dtype)
        self._n_outputs = salidas
        if hasattr(self, "_nucleo"):
            self._nucleo.reiniciar()

    def _asegurar_pesos(self, n_outputs: int) -> None:
        if (self.pesos is None
                or self.pesos.shape != (self.input_size, n_outputs)
                or self.sesgo is None
                or self.sesgo.shape != (1, n_outputs)):
            self.inicializar_pesos(n_outputs)
        else:
            self.pesos = self.pesos.astype(self._dtype, copy=False)
            self.sesgo = self.sesgo.astype(self._dtype, copy=False)

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

    def _preparar_objetivo(self, y: Any, n_muestras: int
                           ) -> np.ndarray:
        arreglo = np.asarray(y, dtype=np.float64)
        if arreglo.ndim == 1:
            arreglo = arreglo.reshape(-1, 1)
        elif arreglo.ndim == 2 and arreglo.shape[1] == 1:
            pass
        elif arreglo.ndim != 2:
            raise ValueError("y debe ser 1D o 2D")
        if arreglo.shape[0] != n_muestras:
            raise ValueError(
                "X e y deben tener el mismo numero de muestras: "
                f"{n_muestras} != {arreglo.shape[0]}"
            )
        if arreglo.size == 0:
            raise ValueError("y no contiene muestras")
        if not np.all(np.isfinite(arreglo)):
            raise ValueError("y contiene valores no finitos")
        return arreglo

    # ------------------------------------------------------------------
    # Solver
    # ------------------------------------------------------------------
    def _resolver_solver(self, n_samples: int,
                         n_features: int) -> str:
        if self._use_normal_eq:
            return "normal"
        solver = self._solver
        if solver != "auto":
            return solver
        if self._regularization in ("l1", "elasticnet"):
            return "elasticnet"
        if n_features <= 5000 and n_samples >= max(2, n_features):
            return "normal"
        return "sgd"

    def _alpha_ridge(self) -> float:
        return (self._reg_lambda
                if self._regularization == "l2" else 0.0)

    # ------------------------------------------------------------------
    # Propagacion
    # ------------------------------------------------------------------
    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Propagacion lineal (n, salidas)."""
        matriz, unico = self._transformar_X(entrada)
        salida = matriz @ self.pesos + self.sesgo
        self.historial_activaciones.append(np.array(salida, copy=True))
        self.pasos += 1
        return salida[0] if unico else salida

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Prediccion lineal (n, salidas)."""
        if self.pesos is None:
            raise RuntimeError("Modelo no entrenado")
        matriz, unico = self._transformar_X(X)
        salida = matriz @ self.pesos + self.sesgo
        return salida[0] if unico else salida

    def predict_flat(self, X: np.ndarray) -> np.ndarray:
        """Prediccion aplanada (compatibilidad historica)."""
        return np.asarray(self.predict(X)).ravel()

    @property
    def coef_(self) -> Optional[np.ndarray]:
        return None if self.pesos is None else self.pesos.T.copy()

    @property
    def intercept_(self) -> Optional[np.ndarray]:
        return None if self.sesgo is None else self.sesgo.ravel().copy()

    @property
    def n_features_in_(self) -> int:
        return int(self.input_size)

    # ------------------------------------------------------------------
    # Perdida y gradientes
    # ------------------------------------------------------------------
    def _regularizacion(self, pesos: np.ndarray) -> float:
        if self._regularization == "none" or self._reg_lambda <= 0.0:
            return 0.0
        if self._regularization == "l1":
            return self._reg_lambda * float(np.sum(np.abs(pesos)))
        if self._regularization == "l2":
            return 0.5 * self._reg_lambda * float(np.sum(pesos ** 2))
        return (
            self._reg_lambda * self._l1_ratio
            * float(np.sum(np.abs(pesos)))
            + 0.5 * self._reg_lambda * (1.0 - self._l1_ratio)
            * float(np.sum(pesos ** 2))
        )

    def _gradiente_regularizacion(self, pesos: np.ndarray) -> np.ndarray:
        if self._regularization == "none" or self._reg_lambda <= 0.0:
            return np.zeros_like(pesos)
        if self._regularization == "l1":
            return self._reg_lambda * np.sign(pesos)
        if self._regularization == "l2":
            return self._reg_lambda * pesos
        return (
            self._reg_lambda * self._l1_ratio * np.sign(pesos)
            + self._reg_lambda * (1.0 - self._l1_ratio) * pesos
        )

    def compute_loss(self, y_true: np.ndarray,
                     y_pred: np.ndarray) -> float:
        """MSE mas penalizacion de regularizacion."""
        real = np.asarray(y_true, dtype=np.float64)
        pred = np.asarray(y_pred, dtype=np.float64)
        if real.shape != pred.shape:
            pred = pred.reshape(real.shape)
        mse = float(np.mean((real - pred) ** 2))
        return float(mse + self._regularizacion(self.pesos))

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Gradiente de pesos/sesgo (API historica)."""
        if self.pesos is None:
            raise RuntimeError("Modelo no entrenado")
        matriz, _ = self._validar_entrada(entrada, permitir_1d=False)
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(-1, 1)
        n = max(1, matriz.shape[0])
        grad_pesos = (matriz.T @ gradiente) / n
        grad_pesos += self._gradiente_regularizacion(self.pesos)
        grad_sesgo = np.sum(gradiente, axis=0, keepdims=True) / n
        self.historial_gradientes.append({
            'pesos': grad_pesos.copy(),
            'norma': float(np.linalg.norm(grad_pesos)),
        })
        return grad_pesos, grad_sesgo

    # ------------------------------------------------------------------
    # Entrenamiento
    # ------------------------------------------------------------------
    def train(self, X: np.ndarray, y: np.ndarray,
              epochs: Optional[int] = None,
              learning_rate: Optional[float] = None,
              verbose: bool = False, **kwargs: Any) -> Dict[str, Any]:
        """Entrena con solver exacto, coordenado o iterativo."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        objetivo = self._preparar_objetivo(y, matriz.shape[0])
        if epochs is not None:
            self._epochs = max(1, int(epochs))
        if learning_rate is not None:
            self._learning_rate = float(learning_rate)
        self._n_outputs = int(objetivo.shape[1])
        self.output_size = int(self._n_outputs)
        self._asegurar_pesos(self._n_outputs)

        if self._estandarizar and self._scaler is not None:
            matriz = self._scaler.fit_transform(matriz)
        self._n_samples = int(matriz.shape[0])
        inicio = time.perf_counter()
        solver = self._resolver_solver(
            matriz.shape[0], matriz.shape[1]
        )
        self._use_normal_eq = solver in ("normal", "svd", "ridge")

        if solver in ("normal", "svd", "ridge"):
            pesos, sesgo = self._nucleo.resolver_lineal(
                matriz, objetivo, self._alpha_ridge()
            )
            self.pesos = np.asarray(pesos, dtype=self._dtype)
            self.sesgo = np.asarray(sesgo, dtype=self._dtype)
            self._convergence_history = []
            self._loss_history = []
            perdida = self.compute_loss(objetivo, matriz @ self.pesos
                                        + self.sesgo)
            self._convergence_history.append(float(perdida))
            self._loss_history.append(float(perdida))
            metodo = "normal_equation"
        elif solver in ("lasso", "elasticnet"):
            alpha = max(self._reg_lambda, 1e-12)
            pesos, sesgo = self._nucleo.coordinate_descent(
                matriz, objetivo, alpha,
                self._l1_ratio if self._regularization == "elasticnet"
                else 1.0,
                self._max_iter_cd, self._tol,
            )
            self.pesos = np.asarray(pesos, dtype=self._dtype)
            self.sesgo = np.asarray(sesgo, dtype=self._dtype)
            perdida = self.compute_loss(objetivo, matriz @ self.pesos
                                        + self.sesgo)
            self._convergence_history = [float(perdida)]
            self._loss_history = [float(perdida)]
            metodo = "coordinate_descent"
        else:
            metodo = self._entrenar_iterativo(
                matriz, objetivo, solver, verbose
            )

        self._is_fitted = True
        self._training_time = time.perf_counter() - inicio
        self._r2_score = float(self._nucleo.metricas(
            objetivo, matriz @ self.pesos + self.sesgo
        )['r2'])
        if self._loss_history and hasattr(self, "registrar_perdida"):
            self.registrar_perdida(self._loss_history[-1])
        return {
            'method': metodo,
            'solver': solver,
            'losses': list(self._loss_history),
            'final_loss': (float(self._loss_history[-1])
                           if self._loss_history else float('nan')),
            'training_time': float(self._training_time),
            'r2': float(self._r2_score),
            'n_samples': int(self._n_samples),
        }

    def _entrenar_iterativo(self, matriz: np.ndarray, objetivo: np.ndarray,
                            solver: str, verbose: bool) -> str:
        self._nucleo.reiniciar()
        self._convergence_history = []
        self._loss_history = []
        generador = np.random.default_rng(self._seed)
        n = matriz.shape[0]
        tam_lote = (n if self._batch_size is None
                    else max(1, min(self._batch_size, n)))
        optimizador = "sgd" if solver in (
            "normal", "svd", "ridge"
        ) else solver
        if optimizador not in ("sgd", "momentum", "adam"):
            optimizador = "sgd"
        for epoca in range(max(1, self._epochs)):
            lr = self._learning_rate
            orden = generador.permutation(n)
            perdida_acumulada = 0.0
            vistos = 0
            for inicio in range(0, n, tam_lote):
                indices = orden[inicio:inicio + tam_lote]
                X_lote = matriz[indices]
                y_lote = objetivo[indices]
                prediccion = X_lote @ self.pesos + self.sesgo
                gradiente = self._nucleo.gradiente_mse(
                    prediccion, y_lote
                )
                grad_pesos = X_lote.T @ gradiente
                grad_pesos += self._gradiente_regularizacion(self.pesos)
                grad_sesgo = np.sum(
                    gradiente, axis=0, keepdims=True
                )
                self._nucleo.paso(
                    [self.pesos, self.sesgo],
                    [grad_pesos, grad_sesgo],
                    optimizador=optimizador,
                    lr=lr,
                )
                perdida = float(np.mean(
                    (prediccion - y_lote) ** 2
                ))
                perdida_acumulada += perdida * len(indices)
                vistos += len(indices)
            perdida_epoca = perdida_acumulada / max(1, vistos)
            self._convergence_history.append(float(perdida_epoca))
            self._loss_history.append(float(perdida_epoca))
            if verbose and (epoca + 1) % 100 == 0:
                logger.info(
                    "Linear Epoch %d/%d, loss=%.6f",
                    epoca + 1, self._epochs, perdida_epoca,
                )
            if not np.isfinite(perdida_epoca):
                logger.warning("Perdida no finita; se detiene")
                break
        return optimizador

    def fit(self, X: np.ndarray, y: np.ndarray,
            epochs: Optional[int] = None,
            learning_rate: Optional[float] = None,
            verbose: bool = False, **kwargs: Any
            ) -> "NeuronaRegresionLineal":
        """API sklearn: entrena y devuelve la propia neurona."""
        self.train(
            X, y, epochs=epochs, learning_rate=learning_rate,
            verbose=verbose, **kwargs,
        )
        return self

    # ------------------------------------------------------------------
    # Evaluacion
    # ------------------------------------------------------------------
    def r2_score(self, y_true: np.ndarray,
                 y_pred: np.ndarray) -> float:
        metricas = self._nucleo.metricas(y_true, y_pred)
        self._r2_score = float(metricas['r2'])
        return self._r2_score

    def mae(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(np.abs(
            np.asarray(y_true, dtype=np.float64)
            - np.asarray(y_pred, dtype=np.float64)
        )))

    def rmse(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(math.sqrt(np.mean(
            (np.asarray(y_true, dtype=np.float64)
             - np.asarray(y_pred, dtype=np.float64)) ** 2
        )))

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """R2."""
        return float(self.evaluate(X, y)['r2'])

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Metricas de regresion completas."""
        matriz, _ = self._validar_entrada(X, permitir_1d=False)
        objetivo = self._preparar_objetivo(y, matriz.shape[0])
        prediccion = self.predict(matriz)
        metricas = self._nucleo.metricas(objetivo, prediccion)
        metricas['loss'] = self.compute_loss(objetivo, prediccion)
        metricas['predictions'] = np.asarray(prediccion)
        self._r2_score = float(metricas['r2'])
        return metricas

    # ------------------------------------------------------------------
    # Gestion de recursos
    # ------------------------------------------------------------------
    def set_regularization(self, reg_type: str,
                           lambda_val: float = 0.01) -> None:
        self._regularization = self._normalizar_regularizacion(reg_type)
        self._reg_lambda = max(0.0, float(lambda_val))

    def enable_normal_equation(self, enable: bool = True) -> None:
        self._solver = "normal" if enable else "sgd"
        self._use_normal_eq = bool(enable)

    def get_loss_history(self) -> List[float]:
        return list(self._loss_history)

    def _estado(self) -> Dict[str, Any]:
        return {
            'version': __version__,
            'tipo': 'NeuronaRegresionLineal',
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'learning_rate': self._learning_rate,
            'epochs': self._epochs,
            'batch_size': self._batch_size,
            'regularization': self._regularization,
            'reg_lambda': self._reg_lambda,
            'l1_ratio': self._l1_ratio,
            'solver': self._solver,
            'estandarizar': self._estandarizar,
            'dtype': self._dtype,
            'scaler': (None if self._scaler is None
                       else self._scaler.get_params()),
            'ram_budget_mb': self._ram_budget_mb,
            'vram_budget_mb': self._vram_budget_mb,
            'disk_budget_mb': self._disk_budget_mb,
            'use_normal_eq': self._use_normal_eq,
            'is_fitted': self._is_fitted,
            'n_outputs': self._n_outputs,
            'pesos': self.pesos,
            'sesgo': self.sesgo,
            'r2_score': self._r2_score,
            'n_samples': self._n_samples,
            'convergence_history': list(self._convergence_history),
            'loss_history': list(self._loss_history),
            'training_time': self._training_time,
            'pasos': self.pasos,
        }

    def estimar_recursos(self, X: Optional[np.ndarray] = None,
                         batch_size: Optional[int] = None,
                         comprimido: bool = True) -> Dict[str, Any]:
        """Estima RAM/VRAM y tamano en disco del modelo."""
        memoria = self.GestorRecursos.estimar_memoria(
            self.pesos, self.sesgo, X,
            self._batch_size if batch_size is None else batch_size,
            self._dtype, self._solver,
        )
        disco = self.GestorRecursos.estimar_disco(
            self._estado(), comprimido=comprimido
        )
        return {**memoria, **disco}

    def tamano_disco(self, comprimido: bool = True) -> Dict[str, Any]:
        return self.GestorRecursos.estimar_disco(
            self._estado(), comprimido=comprimido
        )

    def presupuesto_recursos(
        self, ram_budget_mb: Optional[float] = None,
        vram_budget_mb: Optional[float] = None,
        disk_budget_mb: Optional[float] = None,
    ) -> Dict[str, Any]:
        estimacion = self.estimar_recursos()
        return self.GestorRecursos.presupuesto(
            estimacion,
            self._ram_budget_mb if ram_budget_mb is None else ram_budget_mb,
            self._vram_budget_mb if vram_budget_mb is None else vram_budget_mb,
            self._disk_budget_mb if disk_budget_mb is None else disk_budget_mb,
        )

    def comprimir(self, dtype: str = "float32") -> "NeuronaRegresionLineal":
        """Cuantiza pesos y sesgo a float32/float16 para reducir RAM/disco."""
        clave = self._normalizar_dtype(dtype)
        if self.pesos is not None:
            self.pesos = self.GestorRecursos.convertir(self.pesos, clave)
        if self.sesgo is not None:
            self.sesgo = self.GestorRecursos.convertir(self.sesgo, clave)
        self._dtype = clave
        return self

    def podar(self, umbral: float = 1e-4) -> float:
        """Pone a cero pesos pequenos y devuelve la fraccion podada."""
        if self.pesos is None:
            return 0.0
        self.pesos, fraccion = self.GestorRecursos.podar(
            self.pesos, umbral
        )
        return float(fraccion)

    def optimizar_memoria(
        self, ram_budget_mb: Optional[float] = None,
        vram_budget_mb: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Reduce dtype y lote recomendado si se excede el presupuesto."""
        presupuesto = self.presupuesto_recursos(
            ram_budget_mb=ram_budget_mb,
            vram_budget_mb=vram_budget_mb,
        )
        if not presupuesto['cumple'] and self._dtype != "float32":
            self.comprimir("float32")
        if ram_budget_mb is not None:
            lote = self.GestorRecursos.lote_recomendado(
                np.zeros((max(1, self._n_samples), self.input_size)),
                ram_budget_mb, self._dtype,
            )
            if lote is not None:
                self._batch_size = int(lote)
        return self.presupuesto_recursos(
            ram_budget_mb=ram_budget_mb,
            vram_budget_mb=vram_budget_mb,
        )

    def guardar_comprimido(self, filepath: str) -> int:
        """Guarda el estado con gzip y devuelve los bytes escritos."""
        datos = pickle.dumps(
            self._estado(), protocol=pickle.HIGHEST_PROTOCOL
        )
        comprimido = gzip.compress(datos, compresslevel=6)
        with open(filepath, 'wb') as archivo:
            archivo.write(comprimido)
        return int(len(comprimido))

    def reporte_recursos(self, X: Optional[np.ndarray] = None) -> str:
        estimacion = self.estimar_recursos(X)
        return "\n".join([
            f"=== Recursos {self.nombre} ===",
            (f"Parametros: {estimacion['parametros_bytes']} B | "
             f"RAM: {estimacion['ram_estimada_mb']:.3f} MB | "
             f"VRAM: {estimacion['vram_estimada_mb']:.3f} MB"),
            (f"Disco bruto: {estimacion['disco_bruto_mb']:.3f} MB | "
             f"comprimido: {estimacion['disco_comprimido_mb']:.3f} MB | "
             f"ratio: {estimacion['ratio_compresion']:.2f}"),
            (f"dtype: {estimacion['dtype']} | "
             f"lote: {self._batch_size}"),
        ])

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
        stats['r2_score'] = self._r2_score
        stats['use_normal_equation'] = self._use_normal_eq
        return stats

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'regresion_lineal',
            'learning_rate': self._learning_rate,
            'epochs': self._epochs,
            'batch_size': self._batch_size,
            'regularization': self._regularization,
            'reg_lambda': self._reg_lambda,
            'l1_ratio': self._l1_ratio,
            'solver': self._solver,
            'estandarizar': self._estandarizar,
            'dtype': self._dtype,
            'is_fitted': self._is_fitted,
            'r2_score': self._r2_score,
            'n_samples': self._n_samples,
            'n_outputs': self._n_outputs,
            'training_time': self._training_time,
            'use_normal_equation': self._use_normal_eq,
            'recursos': self.GestorRecursos.resumen(),
        })
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprobaciones numericas y de recursos."""
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
        ok['dtype_valido'] = self._dtype in ("float64", "float32", "float16")
        ok['estable'] = all(ok.values())
        return ok

    # ------------------------------------------------------------------
    # Serializacion
    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        """Serializa el modelo completo (pickle)."""
        with open(filepath, 'wb') as archivo:
            pickle.dump(
                self._estado(), archivo,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    def load(self, filepath: str) -> None:
        """Carga checkpoints nuevos o de la API historica."""
        with open(filepath, 'rb') as archivo:
            estado = pickle.load(archivo)
        self._cargar_estado(estado)

    def _cargar_estado(self, estado: Dict[str, Any]) -> None:
        if not isinstance(estado, dict):
            raise TypeError("El fichero no contiene un checkpoint valido")
        self.nombre = str(estado.get('nombre', self.nombre))
        self.input_size = int(estado.get('input_size', self.input_size))
        self.output_size = int(estado.get('output_size', self.output_size))
        self._learning_rate = float(estado.get('learning_rate', 0.01))
        self._epochs = max(1, int(estado.get('epochs', 200)))
        lote = estado.get('batch_size', 32)
        self._batch_size = None if lote is None else max(1, int(lote))
        self._regularization = self._normalizar_regularizacion(
            estado.get('regularization', 'l2')
        )
        self._reg_lambda = max(0.0, float(estado.get('reg_lambda', 0.01)))
        self._l1_ratio = min(1.0, max(0.0, float(
            estado.get('l1_ratio', 0.5)
        )))
        self._solver = self._normalizar_solver(
            estado.get('solver', 'auto')
        )
        self._estandarizar = bool(estado.get('estandarizar', False))
        self._dtype = self._normalizar_dtype(
            estado.get('dtype', 'float64')
        )
        self._use_normal_eq = bool(estado.get(
            'use_normal_eq', self._solver in ("normal", "svd", "ridge")
        ))
        self._ram_budget_mb = estado.get('ram_budget_mb', None)
        self._vram_budget_mb = estado.get('vram_budget_mb', None)
        self._disk_budget_mb = estado.get('disk_budget_mb', None)

        pesos = estado.get('pesos')
        sesgo = estado.get('sesgo')
        if pesos is None or sesgo is None:
            raise ValueError("El checkpoint no contiene pesos")
        self.pesos = np.asarray(pesos, dtype=self._dtype)
        self.sesgo = np.asarray(sesgo, dtype=self._dtype).reshape(1, -1)
        self._n_outputs = int(
            estado.get('n_outputs', self.pesos.shape[1])
        )
        self._is_fitted = bool(estado.get('is_fitted', True))
        self._r2_score = float(estado.get('r2_score', 0.0))
        self._n_samples = int(estado.get('n_samples', 0))
        self._convergence_history = [
            float(v) for v in estado.get('convergence_history', [])
        ]
        self._loss_history = [
            float(v) for v in estado.get('loss_history', [])
        ]
        self._training_time = float(estado.get('training_time', 0.0))
        self.pasos = int(estado.get('pasos', 0))
        scaler = estado.get('scaler')
        if self._estandarizar:
            self._scaler = FeatureStandardizer()
            if isinstance(scaler, dict):
                self._scaler._mean = scaler.get('mean')
                self._scaler._std = scaler.get('std')
        else:
            self._scaler = None
        self._nucleo = self.NucleoRegresionLineal()
        self._gestor = self.GestorRecursos()

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
            'solver': self._solver,
            'estandarizar': self._estandarizar,
            'dtype': self._dtype,
            'ram_budget_mb': self._ram_budget_mb,
            'vram_budget_mb': self._vram_budget_mb,
            'disk_budget_mb': self._disk_budget_mb,
        }

    def summary(self) -> str:
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {self.nombre} ===",
            (f"Solver: {self._solver}, Regularizacion: "
             f"{self._regularization} ({self._reg_lambda})"),
            (f"LR: {self._learning_rate}, Epochs: {self._epochs}, "
             f"Batch: {self._batch_size}"),
            (f"Input: {self.input_size}, Output: {self.output_size}, "
             f"dtype: {self._dtype}"),
            (f"Fitted: {stats.get('is_fitted', False)}, "
             f"R2: {stats.get('r2_score', 0.0):.4f}, "
             f"Params: {self.params_count()}"),
            (f"Final loss: {stats.get('final_loss', 'N/A')}"),
        ])

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},"
                f"sal={self.output_size},pasos={self.pasos})")


# ---------------------------------------------------------------------------
# Utilidades historicas
# ---------------------------------------------------------------------------
class LossMSE:
    def __init__(self):
        self._name: str = "MSE"

    def compute(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(
            (np.asarray(y_true, dtype=np.float64)
             - np.asarray(y_pred, dtype=np.float64)) ** 2
        ))

    def gradient(self, y_true: np.ndarray,
                 y_pred: np.ndarray) -> np.ndarray:
        real = np.asarray(y_true, dtype=np.float64)
        pred = np.asarray(y_pred, dtype=np.float64)
        return 2.0 * (pred - real) / max(1, pred.size)

    def name(self) -> str:
        return self._name


class GradientDescentLR:
    def __init__(self, learning_rate: float = 0.01,
                 momentum: float = 0.0, decay: float = 0.0):
        self.learning_rate = float(learning_rate)
        self.momentum = float(momentum)
        self.decay = max(0.0, float(decay))
        self._velocity: Optional[np.ndarray] = None
        self._t: int = 0

    def update(self, params: np.ndarray,
               gradient: np.ndarray) -> np.ndarray:
        p = np.asarray(params, dtype=np.float64)
        g = np.asarray(gradient, dtype=np.float64)
        if self.decay > 0.0:
            self.learning_rate *= 1.0 / (1.0 + self.decay * self._t)
        if self.momentum > 0.0:
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
        self._t = 0


class NormalEquation:
    @staticmethod
    def solve(X: np.ndarray, y: np.ndarray) -> np.ndarray:
        pesos, sesgo = NeuronaRegresionLineal.NucleoRegresionLineal\
            .resolver_lineal(X, y, alpha=0.0)
        return np.vstack([pesos, sesgo])

    @staticmethod
    def ridge_solve(X: np.ndarray, y: np.ndarray,
                    alpha: float = 0.01) -> np.ndarray:
        pesos, sesgo = NeuronaRegresionLineal.NucleoRegresionLineal\
            .resolver_lineal(X, y, alpha=float(alpha))
        return np.vstack([pesos, sesgo])


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


class ModelMetrics:
    @staticmethod
    def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(NeuronaRegresionLineal.NucleoRegresionLineal
                     .metricas(y_true, y_pred)['r2'])

    @staticmethod
    def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(np.abs(
            np.asarray(y_true, dtype=np.float64)
            - np.asarray(y_pred, dtype=np.float64)
        )))

    @staticmethod
    def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.sqrt(np.mean(
            (np.asarray(y_true, dtype=np.float64)
             - np.asarray(y_pred, dtype=np.float64)) ** 2
        )))

    @staticmethod
    def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        real = np.asarray(y_true, dtype=np.float64)
        pred = np.asarray(y_pred, dtype=np.float64)
        mascara = real != 0
        if not np.any(mascara):
            return float('inf')
        return float(np.mean(np.abs(
            (real[mascara] - pred[mascara]) / real[mascara]
        )))

    @staticmethod
    def evaluate_all(y_true: np.ndarray,
                     y_pred: np.ndarray) -> Dict[str, float]:
        return {
            'r2': ModelMetrics.r2(y_true, y_pred),
            'mae': ModelMetrics.mae(y_true, y_pred),
            'rmse': ModelMetrics.rmse(y_true, y_pred),
            'mape': ModelMetrics.mape(y_true, y_pred),
        }


class LinearPredictor:
    def __init__(self, model: Optional["LinearRegressionOptimizer"] = None):
        self._model = model

    def fit(self, X: np.ndarray, y: np.ndarray,
            **kwargs: Any) -> "LinearRegressionOptimizer":
        self._model = LinearRegressionOptimizer(
            input_size=X.shape[1], output_size=1
        )
        self._model.train(X, y, **kwargs)
        return self._model

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Modelo no entrenado")
        return np.asarray(self._model.predict(X)).ravel()

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        predicciones = self.predict(X)
        return ModelMetrics.r2(
            np.asarray(y, dtype=np.float64), predicciones
        )


# ---------------------------------------------------------------------------
# Adaptador de compatibilidad con la API historica de RF_SL1_9
# ---------------------------------------------------------------------------
class LinearRegressionOptimizer(NeuronaRegresionLineal):
    """Regresion lineal real con la API historica de RF_SL1_9."""

    def __init__(
        self,
        input_size: int = 4,
        output_size: int = 8,
        nombre: str = "LinearRegressionOptimizer",
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
def crear_neurona(tipo: str = "lineal", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaRegresionLineal:
    """Fabrica una neurona de regresion lineal por nombre."""
    clave = str(tipo or "lineal").strip().lower().replace("-", "_")
    if clave in ("lineal", "linear", "linear_regression", "regresion_lineal",
                 "ols", "ridge"):
        return NeuronaRegresionLineal(
            input_size=input_size, output_size=output_size, **kwargs
        )
    if clave in ("compat", "linear_regression_optimizer", "optimizer"):
        return LinearRegressionOptimizer(
            input_size=input_size, output_size=output_size, **kwargs
        )
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: lineal, ols, ridge, compat"
    )


def tipos_disponibles() -> List[str]:
    """Nombres aceptados por :func:`crear_neurona`."""
    return ["lineal", "ols", "ridge", "compat"]


def create_linear_regression_optimizer(
    input_size: int = 4, output_size: int = 8, **kwargs: Any,
) -> LinearRegressionOptimizer:
    """Fabrica historica de RF_SL1_9."""
    return LinearRegressionOptimizer(
        input_size=input_size, output_size=output_size, **kwargs
    )


def entrenar_y_evaluar(modelo: NeuronaRegresionLineal, X: np.ndarray,
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


def benchmark_modelo(modelo: NeuronaRegresionLineal, X: np.ndarray,
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


def guardar_modelo(modelo: NeuronaRegresionLineal, ruta: str) -> None:
    """Serializa el objeto completo (pickle)."""
    with open(ruta, 'wb') as archivo:
        pickle.dump(modelo, archivo, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_modelo(ruta: str) -> NeuronaRegresionLineal:
    """Carga un modelo serializado con :func:`guardar_modelo`."""
    with open(ruta, 'rb') as archivo:
        modelo = pickle.load(archivo)
    if not isinstance(modelo, NeuronaRegresionLineal):
        raise TypeError("El fichero no contiene una regresion lineal")
    return modelo


def cargar_modelo_comprimido(ruta: str) -> NeuronaRegresionLineal:
    """Carga un modelo guardado con ``guardar_comprimido``."""
    with gzip.open(ruta, 'rb') as archivo:
        estado = pickle.load(archivo)
    modelo = NeuronaRegresionLineal(
        input_size=int(estado.get('input_size', 4)),
        output_size=int(estado.get('output_size', 1)),
    )
    modelo._cargar_estado(estado)
    return modelo


# ---------------------------------------------------------------------------
# Demostracion
# ---------------------------------------------------------------------------
def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_9_1.py``)."""
    generador = np.random.default_rng(2026)
    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_9_1 :: Regresion lineal (v%s)" % __version__)
    print("=" * 78)

    n = 500
    X = generador.normal(size=(n, 4))
    y = (X @ np.array([2.0, -1.0, 0.5, 3.0])
         + 0.7 + generador.normal(scale=0.2, size=n)).reshape(-1, 1)
    modelo = crear_neurona("lineal", 4, 1, solver="auto", seed=7)
    resultado = modelo.train(X, y)
    metricas = modelo.evaluate(X, y)
    print("%-10s metodo=%s R2=%.6f MAE=%.6f"
          % ("OLS", resultado['method'], metricas['r2'],
             metricas['mae']))
    print("Coef:", np.round(modelo.coef_[0], 4).tolist(),
          "Intercept:", round(float(modelo.intercept_[0]), 4))

    ridge = crear_neurona("ridge", 4, 1, solver="ridge",
                          reg_lambda=0.5, seed=8)
    ridge.fit(X, y)
    print("%-10s R2=%.6f"
          % ("Ridge", ridge.evaluate(X, y)['r2']))

    lasso = NeuronaRegresionLineal(
        4, 1, solver="elasticnet", regularization="elasticnet",
        reg_lambda=0.05, l1_ratio=0.7, seed=9,
    )
    lasso.fit(X, y)
    print("%-10s R2=%.6f"
          % ("ElasticNet", lasso.evaluate(X, y)['r2']))

    print(modelo.reporte_recursos(X))
    modelo.comprimir("float32")
    fraccion = modelo.podar(1e-5)
    print("Compactado: dtype=%s, poda=%.2f%%"
          % (modelo.get_config()['dtype'], fraccion * 100))
    print("Presupuesto:", modelo.presupuesto_recursos(
        ram_budget_mb=64, vram_budget_mb=64, disk_budget_mb=8
    ))
    print("Benchmark:", benchmark_modelo(modelo, X, repeticiones=3))
    print("=" * 78)
    return {'metricas': metricas, 'recursos': modelo.estimar_recursos(X)}


__all__ = [
    'NeuronaMemoriaBase',
    'NeuronaRegresionLineal',
    'LinearRegressionOptimizer',
    'LossMSE',
    'GradientDescentLR',
    'NormalEquation',
    'FeatureStandardizer',
    'LinearPredictor',
    'ModelMetrics',
    'crear_neurona',
    'tipos_disponibles',
    'create_linear_regression_optimizer',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'cargar_modelo_comprimido',
    'demo',
    'LUCIA_LINEAR_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
