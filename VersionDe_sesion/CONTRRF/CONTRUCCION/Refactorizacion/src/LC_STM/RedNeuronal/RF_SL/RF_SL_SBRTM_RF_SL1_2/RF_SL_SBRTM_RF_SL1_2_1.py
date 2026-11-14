"""RF_SL_SBRTM_RF_SL1_2_1.py
Neuronas especializadas en SVM y calculo de nucleos (RF_SL · SBRTM · RF · 2026).
=============================================================================

Modulo autocontenido y preparado para importar. Refactoriza el antiguo
fragmento (que solo tenia una neurona lineal llamada
``SupportVectorMachineOptimizer`` y un ``KernelEngine`` basico, sin imports)
y lo sustituye por una implementacion real de SVM con algoritmos de calculo
mejorados:

  * ``KernelEngine``: motores de nucleo estabilizados numericamente.
      - lineal, polinomico, sigmoide, RBF, Laplaciano, Cauchy, Matern 3/2 y
        coseno.
      - gamma automatica por heuristica de escala/mediana.
      - distancias por expansion ``|x|^2 + |y|^2 - 2<x,y>`` con clipping.
      - **Random Fourier Features (RFF)** con opcion **ortogonal (ORF)**, que
        aproxima el nucleo RBF con D frecuencias y reduce el coste de
        O(n^2 d) a O(n D d).
      - **Nystrom**: landmarks por muestreo aleatorio o *k-means++* y
        factorizacion ``K_nm K_mm^{-1/2}`` con autovalores recortados.

  * ``NeuronaSVMNucleo``: SVM de margen blando resuelto en el dual con
      - **SMO de segundo orden (WSS3)** para seleccionar el par de trabajo,
        en lugar de primero/segundo orden heuristicos;
      - matriz Q cacheada y clipping exacto de ``alpha`` en [0, C];
      - vector de soporte, sesgo, margen y calibracion de probabilidades
        (Platt scaling);
      - multiclase one-vs-rest.

  * ``NeuronaSVMHazAleatorio``: SVM lineal sobre **Random Fourier Features**
      (RFF/ORF) entrenado con perdida **squared hinge** y Adam. Es la via
      escalable cuando n es grande o el nucleo RBF es costoso.

  * ``NeuronaSVMNystrom``: **LS-SVM primal con Nystrom** (closed-form ridge
      sobre el mapa de caracteristicas de bajo rango), inspirado en los
      aceleradores Nystrom para LS-SVM (NeurIPS 2025).

  * ``SupportVectorMachineOptimizer``: adaptador de compatibilidad con la API
      historica de RF_SL1_2 (``kernel``, ``compute_loss``, ``compute_margin``,
      ``compute_decision_function``, ``fit``, ``evaluate``, ``save/load``...).

Referencias de los metodos implementados
-----------------------------------------
- Fan, Chen y Lin: *Working set selection using second order information for
  training support vector machines* (WSS3).
- Aproximaciones de nucleo y sus ensembles (Neurocomputing, 2026).
- *Nystrom-Accelerated Primal LS-SVMs* (NeurIPS 2025).
- *Data-Driven Random Feature Selection for Deep Kernel Learning with Kernel
  Alignment* (2025).

La base ``NeuronaMemoriaBase`` se importa del modulo especializado
``RF_SL_SBRTM_RF_rfsl_base/RF_SL_SNRTM__rfsl_base1.py`` (con fallback por
ruta y base local minima), sin duplicar la jerarquia.

Uso rapido
----------
    from RF_SL_SBRTM_RF_SL1_2_1 import NeuronaSVMNucleo

    modelo = NeuronaSVMNucleo(kernel="rbf", C=1.0, gamma="scale")
    modelo.fit(X, y)
    print(modelo.evaluate(X, y))
    print(modelo.predict_proba(X)[:5])
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
LUCIA_SVM_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "C": 1.0,
    "gamma": "scale",
    "degree": 3,
    "coef0": 1.0,
    "tol": 1e-3,
    "max_iter": 1000,
    "max_dual_muestras": 2500,
    "rff_componentes": 256,
    "nystrom_componentes": 128,
    "learning_rate": 0.05,
    "epochs": 120,
    "batch_size": 64,
    "reg_lambda": 1.0,
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

    _CLAVE_BASE = "_rf_snrtm_base_import_svm"
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
                arreglos = self._arreglos_parametros()
                for indice, arreglo in enumerate(arreglos):
                    if arreglo.size and not np.all(np.isfinite(arreglo)):
                        problemas.append(f"parametro #{indice} no finito")
                return {
                    'estable': not problemas,
                    'problemas': problemas,
                    'n_parametros': self.params_count(),
                }


# ---------------------------------------------------------------------------
# Utilidades numericas
# ---------------------------------------------------------------------------
def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


def _softmax(x: np.ndarray, eje: int = -1) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    maximo = np.max(x, axis=eje, keepdims=True)
    exponencial = np.exp(x - maximo)
    return exponencial / np.maximum(np.sum(exponencial, axis=eje, keepdims=True), 1e-12)


def _validar_clasificacion(X: Any, y: Any,
                           input_size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    matriz = np.asarray(X, dtype=np.float64)
    etiquetas = np.asarray(y)
    if matriz.ndim != 2:
        raise ValueError("X debe ser una matriz 2D (muestras, caracteristicas)")
    if matriz.shape[0] == 0:
        raise ValueError("X no contiene muestras")
    if matriz.shape[1] != input_size:
        raise ValueError(
            f"X tiene {matriz.shape[1]} caracteristicas y se esperaban {input_size}"
        )
    if etiquetas.ndim == 2 and etiquetas.shape[1] == 1:
        etiquetas = etiquetas.reshape(-1)
    if etiquetas.ndim != 1:
        raise ValueError("y debe ser un vector de etiquetas")
    if etiquetas.shape[0] != matriz.shape[0]:
        raise ValueError("X e y deben tener el mismo numero de muestras")
    if not np.all(np.isfinite(matriz)):
        matriz = np.nan_to_num(matriz, nan=0.0, posinf=0.0, neginf=0.0)
    clases = np.unique(etiquetas)
    if clases.size < 2:
        raise ValueError("Se necesitan al menos dos clases para entrenar")
    return matriz, etiquetas, clases


def _metricas_clasificacion(real: np.ndarray, prediccion: np.ndarray,
                            clases: Sequence[Any]) -> Dict[str, float]:
    real = np.asarray(real).reshape(-1)
    prediccion = np.asarray(prediccion).reshape(-1)
    exactitud = float(np.mean(real == prediccion)) if real.size else 0.0
    precisiones: List[float] = []
    recalls: List[float] = []
    f1s: List[float] = []
    for clase in clases:
        verdadero_positivo = float(np.sum((prediccion == clase) & (real == clase)))
        falso_positivo = float(np.sum((prediccion == clase) & (real != clase)))
        falso_negativo = float(np.sum((prediccion != clase) & (real == clase)))
        precision = (verdadero_positivo / (verdadero_positivo + falso_positivo)
                     if verdadero_positivo + falso_positivo > 0 else 0.0)
        recall = (verdadero_positivo / (verdadero_positivo + falso_negativo)
                  if verdadero_positivo + falso_negativo > 0 else 0.0)
        f1 = (2.0 * precision * recall / (precision + recall)
              if precision + recall > 0 else 0.0)
        precisiones.append(precision)
        recalls.append(recall)
        f1s.append(f1)
    return {
        'accuracy': exactitud,
        'precision': float(np.mean(precisiones)),
        'recall': float(np.mean(recalls)),
        'f1': float(np.mean(f1s)),
        'n_samples': int(real.size),
    }


def _objetivos_binarios(etiquetas: np.ndarray,
                        clases: np.ndarray) -> List[np.ndarray]:
    """Etiquetas +-1 para alineacion/entrenamiento (OVR si multiclase)."""
    if clases.size == 2:
        return [np.where(etiquetas == clases[1], 1.0, -1.0)]
    return [np.where(etiquetas == clase, 1.0, -1.0) for clase in clases]


class OptimizadorAdam:
    """Adam minimo para los pesos lineales de las neuronas de features."""

    def __init__(self, learning_rate: float = 0.05,
                 beta1: float = 0.9, beta2: float = 0.999,
                 epsilon: float = 1e-8, max_norm: float = 5.0) -> None:
        self.learning_rate = float(learning_rate)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.max_norm = float(max_norm)
        self.momentos: Dict[str, np.ndarray] = {}
        self.velocidades: Dict[str, np.ndarray] = {}
        self.paso = 0

    def step(self, parametros: Dict[str, np.ndarray],
             gradientes: Dict[str, np.ndarray]) -> None:
        self.paso += 1
        norma = math.sqrt(sum(float(np.sum(g * g)) for g in gradientes.values()))
        factor = (self.max_norm / (norma + 1e-12)
                  if self.max_norm > 0 and norma > self.max_norm else 1.0)
        correccion1 = 1.0 - self.beta1 ** self.paso
        correccion2 = 1.0 - self.beta2 ** self.paso
        for nombre, parametro in parametros.items():
            gradiente = np.asarray(gradientes[nombre], dtype=np.float64) * factor
            if nombre not in self.momentos:
                self.momentos[nombre] = np.zeros_like(parametro)
                self.velocidades[nombre] = np.zeros_like(parametro)
            self.momentos[nombre] = (self.beta1 * self.momentos[nombre]
                                     + (1.0 - self.beta1) * gradiente)
            self.velocidades[nombre] = (self.beta2 * self.velocidades[nombre]
                                        + (1.0 - self.beta2) * gradiente * gradiente)
            m_hat = self.momentos[nombre] / correccion1
            v_hat = self.velocidades[nombre] / correccion2
            parametro -= (self.learning_rate * m_hat
                          / (np.sqrt(v_hat) + self.epsilon))


# ---------------------------------------------------------------------------
# Motor de nucleos
# ---------------------------------------------------------------------------
class KernelEngine:
    """Calculo de nucleos, Random Fourier Features y Nystrom.

    Parametros
    ----------
    kernel_type:
        ``linear``, ``poly``, ``sigmoid``, ``rbf``, ``laplacian``,
        ``cauchy``, ``matern32`` o ``cosine``.
    gamma:
        ``"scale"`` (1 / (d * Var(X))), ``"auto"`` (1 / d) o un float > 0.
    """

    NUCLEOS = ("linear", "poly", "sigmoid", "rbf", "laplacian",
               "cauchy", "matern32", "cosine")

    def __init__(self, kernel_type: str = "rbf",
                 gamma: Any = "scale", degree: int = 3,
                 coef0: float = 1.0) -> None:
        self.kernel_type = (kernel_type if kernel_type in self.NUCLEOS else "rbf")
        self.gamma = gamma
        self.degree = max(1, int(degree))
        self.coef0 = float(coef0)
        self.gamma_efectiva: Optional[float] = None
        self._rff_W: Optional[np.ndarray] = None
        self._rff_b: Optional[np.ndarray] = None
        self._rff_dim: int = 0
        self._nystrom_landmarks: Optional[np.ndarray] = None
        self._nystrom_matriz: Optional[np.ndarray] = None

    # -- gamma -------------------------------------------------------------
    def resolver_gamma(self, X: np.ndarray) -> float:
        if isinstance(self.gamma, str):
            caracteristicas = max(1, X.shape[1])
            if self.gamma == "auto":
                valor = 1.0 / caracteristicas
            else:
                varianza = float(np.var(X))
                valor = 1.0 / (caracteristicas * varianza) if varianza > 1e-12 else 1.0
        else:
            valor = float(self.gamma)
        self.gamma_efectiva = max(float(valor), 1e-9)
        return self.gamma_efectiva

    def set_gamma(self, gamma: Any) -> None:
        self.gamma = gamma
        self.gamma_efectiva = None

    # -- distancias --------------------------------------------------------
    @staticmethod
    def distancias(X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        cuadrado1 = np.sum(X1 * X1, axis=1)[:, None]
        cuadrado2 = np.sum(X2 * X2, axis=1)[None, :]
        distancia = cuadrado1 + cuadrado2 - 2.0 * (X1 @ X2.T)
        return np.maximum(distancia, 0.0)

    # -- nucleos -----------------------------------------------------------
    def compute(self, X1: np.ndarray, X2: Optional[np.ndarray] = None) -> np.ndarray:
        A = np.asarray(X1, dtype=np.float64)
        B = A if X2 is None else np.asarray(X2, dtype=np.float64)
        if A.ndim != 2 or B.ndim != 2:
            raise ValueError("Los nucleos esperan matrices 2D")
        if self.gamma_efectiva is None:
            self.resolver_gamma(A)
        gamma = float(self.gamma_efectiva)
        if self.kernel_type == "linear":
            return A @ B.T
        if self.kernel_type == "poly":
            return (gamma * (A @ B.T) + self.coef0) ** self.degree
        if self.kernel_type == "sigmoid":
            return np.tanh(gamma * (A @ B.T) + self.coef0)
        distancia = self.distancias(A, B)
        if self.kernel_type == "rbf":
            return np.exp(-gamma * distancia)
        if self.kernel_type == "laplacian":
            return np.exp(-gamma * np.sqrt(distancia))
        if self.kernel_type == "cauchy":
            return 1.0 / (1.0 + gamma * distancia)
        if self.kernel_type == "matern32":
            raiz = np.sqrt(3.0 * gamma * distancia)
            return (1.0 + raiz) * np.exp(-raiz)
        # cosine
        norma1 = np.linalg.norm(A, axis=1)[:, None]
        norma2 = np.linalg.norm(B, axis=1)[None, :]
        return (A @ B.T) / np.maximum(norma1 * norma2, 1e-12)

    def gram_matrix(self, X: np.ndarray) -> np.ndarray:
        return self.compute(X, X)

    def get_gram_matrix(self, X: np.ndarray) -> np.ndarray:
        return self.gram_matrix(X)

    # -- kernel alignment --------------------------------------------------
    @staticmethod
    def alineacion_nucleo(K: np.ndarray, y: np.ndarray) -> float:
        """Alineacion kernel-target (centrada) para elegir gamma."""
        K = np.asarray(K, dtype=np.float64)
        objetivo = np.asarray(y, dtype=np.float64).reshape(-1)
        n = K.shape[0]
        if n < 2 or objetivo.size != n:
            return 0.0
        Kc = (K - K.mean(axis=1, keepdims=True)
              - K.mean(axis=0, keepdims=True) + K.mean())
        T = np.outer(objetivo, objetivo)
        Tc = (T - T.mean(axis=1, keepdims=True)
              - T.mean(axis=0, keepdims=True) + T.mean())
        denominador = float(np.linalg.norm(Kc) * np.linalg.norm(Tc))
        return (float(np.sum(Kc * Tc)) / denominador
                if denominador > 1e-12 else 0.0)

    def elegir_gamma_alineacion(self, X: np.ndarray,
                                objetivos: Any,
                                candidatos: Optional[Sequence[float]] = None
                                ) -> float:
        """Selecciona gamma maximizando la alineacion kernel-target."""
        X = np.asarray(X, dtype=np.float64)
        if isinstance(objetivos, np.ndarray):
            lista_objetivos = [objetivos]
        else:
            lista_objetivos = [np.asarray(o, dtype=np.float64)
                               for o in objetivos]
        if candidatos is None:
            varianza = float(np.var(X))
            base = (1.0 / (max(1, X.shape[1]) * varianza)
                    if varianza > 1e-12 else 1.0)
            candidatos = [base * factor for factor in (0.1, 0.25, 0.5, 1, 2, 4)]
        mejor_gamma = float(candidatos[0])
        mejor_alineacion = -float("inf")
        for gamma in candidatos:
            gamma = max(float(gamma), 1e-9)
            self.gamma = gamma
            self.gamma_efectiva = gamma
            try:
                K = self.compute(X)
            except Exception:  # pragma: no cover
                continue
            alineacion = float(np.mean([
                self.alineacion_nucleo(K, objetivo)
                for objetivo in lista_objetivos
            ]))
            if alineacion > mejor_alineacion:
                mejor_alineacion = alineacion
                mejor_gamma = gamma
        self.gamma = float(mejor_gamma)
        self.gamma_efectiva = float(mejor_gamma)
        return float(mejor_gamma)

    def get_params(self) -> Dict[str, Any]:
        return {
            'kernel_type': self.kernel_type,
            'gamma': self.gamma,
            'degree': self.degree,
            'coef0': self.coef0,
        }

    # -- Random Fourier Features ------------------------------------------
    @staticmethod
    def _matriz_ortogonal(generador: np.random.Generator,
                          filas: int, columnas: int) -> np.ndarray:
        """Filas ortonormales con la escala de una gaussiana (ORF)."""
        normales = generador.normal(0.0, 1.0, (filas, columnas))
        normas = np.linalg.norm(normales, axis=1, keepdims=True)
        bloque = min(filas, columnas)
        resultado = np.empty_like(normales)
        for inicio in range(0, filas, bloque):
            fin = min(inicio + bloque, filas)
            Q, _ = np.linalg.qr(normales[inicio:fin].T)
            resultado[inicio:fin] = (Q.T[:fin - inicio]
                                     * normas[inicio:fin])
        return resultado

    def ajustar_haz_aleatorio(self, X: np.ndarray, n_componentes: int = 256,
                              ortogonal: bool = True,
                              seed: Optional[int] = None) -> np.ndarray:
        """Aprende la proyeccion RFF/ORF del nucleo RBF y devuelve Z."""
        if self.kernel_type != "rbf":
            raise ValueError(
                "Random Fourier Features esta implementado para kernel='rbf'"
            )
        X = np.asarray(X, dtype=np.float64)
        self.resolver_gamma(X)
        gamma = float(self.gamma_efectiva)
        generador = np.random.default_rng(
            int(LUCIA_SVM_CONFIG["random_seed"] if seed is None else seed)
        )
        dimension = max(1, int(n_componentes))
        if ortogonal and self.kernel_type == "rbf":
            W = self._matriz_ortogonal(generador, dimension, X.shape[1])
        else:
            W = generador.normal(0.0, 1.0, (dimension, X.shape[1]))
        W = W * math.sqrt(2.0 * gamma)
        b = generador.uniform(0.0, 2.0 * math.pi, dimension)
        self._rff_W = W
        self._rff_b = b
        self._rff_dim = dimension
        return self.transformar_haz_aleatorio(X)

    def transformar_haz_aleatorio(self, X: np.ndarray) -> np.ndarray:
        if self._rff_W is None or self._rff_b is None:
            raise RuntimeError("RFF no ajustado: llama a ajustar_haz_aleatorio")
        X = np.asarray(X, dtype=np.float64)
        proyeccion = X @ self._rff_W.T + self._rff_b[None, :]
        escala = 1.0 / math.sqrt(self._rff_dim)
        return np.hstack([np.cos(proyeccion), np.sin(proyeccion)]) * escala

    # -- Nystrom -----------------------------------------------------------
    def _landmarks(self, X: np.ndarray, n_landmarks: int,
                   metodo: str, generador: np.random.Generator) -> np.ndarray:
        n = X.shape[0]
        if n_landmarks >= n:
            return X.copy()
        if metodo != "kmeans++":
            indices = generador.choice(n, size=n_landmarks, replace=False)
            return X[indices].copy()
        indices = [int(generador.integers(0, n))]
        distancias = np.sum((X - X[indices[0]]) ** 2, axis=1)
        for _ in range(1, n_landmarks):
            total = float(np.sum(distancias))
            if total <= 1e-12:
                candidato = int(generador.integers(0, n))
            else:
                candidato = int(generador.choice(n, p=distancias / total))
            indices.append(candidato)
            distancias = np.minimum(
                distancias, np.sum((X - X[candidato]) ** 2, axis=1)
            )
        centros = X[np.array(indices)].copy()
        for _ in range(5):
            distancia = self.distancias(X, centros)
            asignacion = np.argmin(distancia, axis=1)
            for indice in range(n_landmarks):
                mascara = asignacion == indice
                if np.any(mascara):
                    centros[indice] = np.mean(X[mascara], axis=0)
        return centros

    def ajustar_nystrom(self, X: np.ndarray, n_componentes: int = 128,
                        metodo: str = "kmeans++",
                        seed: Optional[int] = None) -> np.ndarray:
        """Aprende el mapa Nystrom de bajo rango y devuelve Z."""
        X = np.asarray(X, dtype=np.float64)
        self.resolver_gamma(X)
        generador = np.random.default_rng(
            int(LUCIA_SVM_CONFIG["random_seed"] if seed is None else seed)
        )
        landmarks = self._landmarks(X, max(2, int(n_componentes)),
                                    metodo, generador)
        K_mm = self.compute(landmarks, landmarks)
        K_nm = self.compute(X, landmarks)
        autovalores, autovectores = np.linalg.eigh(K_mm)
        autovalores = np.clip(autovalores, 1e-10, None)
        matriz = autovectores / np.sqrt(autovalores)[None, :]
        self._nystrom_landmarks = landmarks
        self._nystrom_matriz = matriz
        return K_nm @ matriz

    def transformar_nystrom(self, X: np.ndarray) -> np.ndarray:
        if self._nystrom_landmarks is None or self._nystrom_matriz is None:
            raise RuntimeError("Nystrom no ajustado: llama a ajustar_nystrom")
        X = np.asarray(X, dtype=np.float64)
        return self.compute(X, self._nystrom_landmarks) @ self._nystrom_matriz


# ---------------------------------------------------------------------------
# Calibracion de probabilidades (Platt scaling)
# ---------------------------------------------------------------------------
class _PlattScaler:
    def __init__(self) -> None:
        self.A = 1.0
        self.B = 0.0
        self.ajustado = False

    def fit(self, decision: np.ndarray, etiquetas: np.ndarray) -> "_PlattScaler":
        f = np.asarray(decision, dtype=np.float64).reshape(-1)
        y = np.asarray(etiquetas, dtype=np.float64).reshape(-1)
        if f.size == 0:
            return self
        diseno = np.column_stack([f, np.ones_like(f)])
        pesos = np.array([1.0, 0.0])
        for _ in range(50):
            probabilidad = _sigmoide(diseno @ pesos)
            pesos_curvatura = np.clip(probabilidad * (1.0 - probabilidad), 1e-9, None)
            gradiente = diseno.T @ (probabilidad - y) + 1e-3 * pesos
            hessiano = (diseno.T @ (diseno * pesos_curvatura[:, None])
                        + 1e-3 * np.eye(2))
            try:
                paso = np.linalg.solve(hessiano, gradiente)
            except np.linalg.LinAlgError:  # pragma: no cover
                break
            pesos = pesos - paso
            if float(np.linalg.norm(paso)) < 1e-8:
                break
        self.A = float(pesos[0]) if abs(float(pesos[0])) > 1e-6 else 1.0
        self.B = float(pesos[1])
        self.ajustado = True
        return self

    def transform(self, decision: np.ndarray) -> np.ndarray:
        return _sigmoide(self.A * np.asarray(decision, dtype=np.float64) + self.B)


# ---------------------------------------------------------------------------
# 1) SVM con nucleo exacto (SMO de segundo orden, WSS3)
# ---------------------------------------------------------------------------
class NeuronaSVMNucleo(NeuronaMemoriaBase):
    """SVM de margen blando con kernel, resuelto en el dual por SMO-WSS3."""

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaSVMNucleo", kernel: str = "rbf",
                 C: float = 1.0, gamma: Any = "scale", degree: int = 3,
                 coef0: float = 1.0, tol: float = 1e-3,
                 max_iter: int = 1000, probabilidad: bool = True,
                 seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre)
        self.C = max(1e-6, float(C))
        self.tol = max(1e-9, float(tol))
        self.max_iter = max(10, int(max_iter))
        self.probabilidad = bool(probabilidad)
        self.seed = int(LUCIA_SVM_CONFIG["random_seed"]
                        if seed is None else seed)
        self.engine = KernelEngine(kernel, gamma, degree, coef0)
        self.classes_: Optional[np.ndarray] = None
        self._modelos: List[Dict[str, Any]] = []
        self._is_fitted = False
        self._convergence_history: List[float] = []
        self._timer_train = 0.0
        self._support_vectors: Optional[np.ndarray] = None
        self._support_labels: Optional[np.ndarray] = None
        self._alphas: Optional[np.ndarray] = None
        self._bias = 0.0
        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    # -- API de compatibilidad --------------------------------------------
    def kernel(self, X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        return self.engine.compute(X1, X2)

    def compute_loss(self, prediccion: np.ndarray,
                     objetivo: np.ndarray) -> float:
        prediccion = np.asarray(prediccion, dtype=np.float64).reshape(-1)
        objetivo = np.asarray(objetivo, dtype=np.float64).reshape(-1)
        if objetivo.size == 0:
            return 0.0
        return float(np.mean(np.maximum(0.0, 1.0 - objetivo * prediccion)))

    def compute_margin(self) -> float:
        if not self._is_fitted or not self._modelos:
            return 0.0
        modelo = self._modelos[0]["modelo"]
        norma = float(modelo.get("norma_w", 0.0))
        return float(1.0 / math.sqrt(norma)) if norma > 1e-12 else 0.0

    def compute_decision_function(self, X: np.ndarray) -> np.ndarray:
        return self.decision_function(X)

    # -- entrenamiento -----------------------------------------------------
    def _smo(self, K: np.ndarray, y: np.ndarray, C: float,
             tol: float, max_iter: int) -> Tuple[np.ndarray, float, List[float], int]:
        n = y.size
        Q = (y[:, None] * y[None, :]) * K
        alpha = np.zeros(n, dtype=np.float64)
        G = -np.ones(n, dtype=np.float64)
        diagonales = np.diag(K).copy()
        historial: List[float] = []
        iteraciones = 0
        for iteracion in range(max_iter):
            iteraciones = iteracion + 1
            f = -y * G
            en_up = ((alpha < C) & (y > 0)) | ((alpha > 0) & (y < 0))
            en_low = ((alpha < C) & (y < 0)) | ((alpha > 0) & (y > 0))
            if not np.any(en_up) or not np.any(en_low):
                break
            i = int(np.argmax(np.where(en_up, f, -np.inf)))
            m = float(f[i])
            M = float(np.min(np.where(en_low, f, np.inf)))
            if m - M < tol:
                break
            b_it = f - m
            a_it = np.maximum(diagonales[i] + diagonales - 2.0 * K[i], 1e-12)
            candidatos = en_low & (f < m - 1e-12)
            if not np.any(candidatos):
                candidatos = en_low & (np.arange(n) != i)
            valores = np.where(candidatos, -(b_it ** 2) / a_it, np.inf)
            j = int(np.argmin(valores))
            if not np.isfinite(valores[j]):
                break

            alpha_i, alpha_j = alpha[i], alpha[j]
            if y[i] != y[j]:
                cuadratico = diagonales[i] + diagonales[j] - 2.0 * K[i, j]
                if cuadratico <= 1e-12:
                    continue
                delta = (-G[i] - G[j]) / cuadratico
                diferencia = alpha_i - alpha_j
                nuevo_i, nuevo_j = alpha_i + delta, alpha_j + delta
                if diferencia > 0:
                    if nuevo_j < 0:
                        nuevo_j, nuevo_i = 0.0, diferencia
                    elif nuevo_i > C:
                        nuevo_i, nuevo_j = C, C - diferencia
                else:
                    if nuevo_i < 0:
                        nuevo_i, nuevo_j = 0.0, -diferencia
                    elif nuevo_j > C:
                        nuevo_j, nuevo_i = C, C + diferencia
            else:
                cuadratico = diagonales[i] + diagonales[j] - 2.0 * K[i, j]
                if cuadratico <= 1e-12:
                    continue
                delta = (G[i] - G[j]) / cuadratico
                suma = alpha_i + alpha_j
                nuevo_i, nuevo_j = alpha_i - delta, alpha_j + delta
                if suma > C:
                    if nuevo_i > C:
                        nuevo_i, nuevo_j = C, suma - C
                    elif nuevo_j > C:
                        nuevo_j, nuevo_i = C, suma - C
                else:
                    if nuevo_i < 0:
                        nuevo_i, nuevo_j = 0.0, suma
                    elif nuevo_j < 0:
                        nuevo_j, nuevo_i = 0.0, suma

            delta_i = nuevo_i - alpha_i
            delta_j = nuevo_j - alpha_j
            alpha[i] = nuevo_i
            alpha[j] = nuevo_j
            G += Q[:, i] * delta_i + Q[:, j] * delta_j
            if iteracion % 10 == 0:
                historial.append(float(0.5 * alpha @ (Q @ alpha) - np.sum(alpha)))

        # Sesgo: promedio sobre vectores de soporte libres.
        w_dual = alpha * y
        sin_sesgo = K @ w_dual
        libres = (alpha > 1e-8) & (alpha < C - 1e-8)
        if np.any(libres):
            bias = float(np.mean(y[libres] - sin_sesgo[libres]))
        else:
            soporte = alpha > 1e-8
            bias = (float(np.mean(y[soporte] - sin_sesgo[soporte]))
                    if np.any(soporte) else 0.0)
        objetivo = float(0.5 * alpha @ (Q @ alpha) - np.sum(alpha))
        historial.append(objetivo)
        return alpha, bias, historial, iteraciones

    def _entrenar_binario(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        K = self.engine.gram_matrix(X)
        alpha, bias, historial, iteraciones = self._smo(
            K, y, self.C, self.tol, self.max_iter
        )
        soporte = alpha > 1e-8
        w_dual = alpha * y
        norma_w = float(w_dual @ (K @ w_dual))
        decision_entrenamiento = K @ w_dual + bias
        platt = _PlattScaler().fit(decision_entrenamiento,
                                   (y > 0).astype(np.float64))
        return {
            'alpha': alpha,
            'bias': bias,
            'sv_idx': np.flatnonzero(soporte),
            'sv_X': X[soporte],
            'sv_y': y[soporte],
            'sv_dual': w_dual[soporte],
            'norma_w': norma_w,
            'historial': historial,
            'iteraciones': iteraciones,
            'platt': platt,
        }

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
            verbose: bool = False, max_iter: Optional[int] = None,
            tol: Optional[float] = None, C: Optional[float] = None,
            **kwargs: Any) -> List[float]:
        matriz, etiquetas, clases = _validar_clasificacion(
            X, y, self.input_size
        )
        if max_iter is not None:
            self.max_iter = max(10, int(max_iter))
        elif epochs is not None:
            self.max_iter = max(100, int(epochs) * 20)
        if tol is not None:
            self.tol = max(1e-9, float(tol))
        if C is not None:
            self.C = max(1e-6, float(C))
        if matriz.shape[0] > int(LUCIA_SVM_CONFIG["max_dual_muestras"]):
            logger.warning(
                "SVM dual con %d muestras: considera NeuronaSVMHazAleatorio "
                "o NeuronaSVMNystrom para escalar.",
                matriz.shape[0],
            )

        inicio = time.perf_counter()
        if isinstance(self.engine.gamma, str) and self.engine.gamma == "alignment":
            self.engine.elegir_gamma_alineacion(
                matriz, _objetivos_binarios(etiquetas, clases)
            )
        else:
            self.engine.resolver_gamma(matriz)
        self.classes_ = clases
        self._modelos = []
        self._convergence_history = []
        if clases.size == 2:
            binario = np.where(etiquetas == clases[1], 1.0, -1.0)
            modelo = self._entrenar_binario(matriz, binario)
            self._modelos.append({'clase': clases[1], 'modelo': modelo})
        else:
            for clase in clases:
                binario = np.where(etiquetas == clase, 1.0, -1.0)
                modelo = self._entrenar_binario(matriz, binario)
                self._modelos.append({'clase': clase, 'modelo': modelo})

        primero = self._modelos[0]['modelo']
        self._convergence_history = list(primero['historial'])
        self._support_vectors = primero['sv_X']
        self._support_labels = primero['sv_y']
        self._alphas = primero['alpha']
        self._bias = float(primero['bias'])
        self._is_fitted = True
        self._timer_train = time.perf_counter() - inicio
        if self._convergence_history:
            self.registrar_perdida(self._convergence_history[-1])
        if verbose:
            logger.info(
                "%s: %d clases, %d iteraciones SMO, %.3fs",
                self.nombre, len(self._modelos),
                primero['iteraciones'], self._timer_train,
            )
        return list(self._convergence_history)

    def train(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
              learning_rate: Optional[float] = None, verbose: bool = False,
              **kwargs: Any) -> Dict[str, Any]:
        historial = self.fit(X, y, epochs=epochs, verbose=verbose, **kwargs)
        return {
            'historial': historial,
            'iteraciones': (self._modelos[0]['modelo']['iteraciones']
                            if self._modelos else 0),
            'perdida_final': float(historial[-1]) if historial else None,
        }

    # -- inferencia --------------------------------------------------------
    def _puntuaciones(self, X: np.ndarray) -> np.ndarray:
        matriz = np.asarray(X, dtype=np.float64)
        unico = matriz.ndim == 1
        if unico:
            matriz = matriz.reshape(1, -1)
        if matriz.shape[1] != self.input_size:
            raise ValueError(
                f"Se esperaban {self.input_size} caracteristicas y llegaron "
                f"{matriz.shape[1]}"
            )
        puntuaciones = np.column_stack([
            self.engine.compute(matriz, entrada['modelo']['sv_X'])
            @ entrada['modelo']['sv_dual'] + entrada['modelo']['bias']
            for entrada in self._modelos
        ])
        if unico and puntuaciones.shape[1] == 1:
            return puntuaciones[0]
        return puntuaciones

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("El modelo no esta entrenado: llama a fit primero")
        puntuaciones = self._puntuaciones(X)
        if puntuaciones.ndim == 2 and puntuaciones.shape[1] == 1:
            return puntuaciones[:, 0]
        return puntuaciones

    def predict(self, X: np.ndarray) -> np.ndarray:
        puntuaciones = self.decision_function(X)
        entrada = np.asarray(X)
        if puntuaciones.ndim == 1:
            if puntuaciones.size == 1 and entrada.ndim == 1:
                return np.array([
                    self.classes_[1] if puntuaciones[0] > 0 else self.classes_[0]
                ])
            return np.where(puntuaciones > 0, self.classes_[1], self.classes_[0])
        return self.classes_[np.argmax(puntuaciones, axis=1)]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("El modelo no esta entrenado: llama a fit primero")
        if len(self._modelos) == 1:
            modelo = self._modelos[0]['modelo']
            decision = self._puntuaciones(X)
            decision = np.asarray(decision).reshape(-1)
            if not self.probabilidad or not modelo['platt'].ajustado:
                probabilidad = _sigmoide(decision)
            else:
                probabilidad = modelo['platt'].transform(decision)
            return np.column_stack([1.0 - probabilidad, probabilidad])
        puntuaciones = np.asarray(self._puntuaciones(X), dtype=np.float64)
        return _softmax(puntuaciones, eje=1)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        real = np.asarray(y).reshape(-1)
        return float(np.mean(self.predict(X) == real))

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        matriz, etiquetas, clases = _validar_clasificacion(X, y, self.input_size)
        prediccion = self.predict(matriz)
        metricas = _metricas_clasificacion(etiquetas, prediccion, clases)
        decision = np.asarray(self.decision_function(matriz), dtype=np.float64)
        if decision.ndim == 1:
            objetivo = np.where(etiquetas == clases[1], 1.0, -1.0)
            perdida = float(np.mean(np.maximum(0.0, 1.0 - objetivo * decision)))
        else:
            perdidas = []
            for indice, clase in enumerate(clases):
                objetivo = np.where(etiquetas == clase, 1.0, -1.0)
                perdidas.append(np.mean(np.maximum(
                    0.0, 1.0 - objetivo * decision[:, indice]
                )))
            perdida = float(np.mean(perdidas))
        metricas.update({
            'loss': perdida,
            'margin': self.compute_margin(),
            'n_support_vectors': self.n_support_vectors(),
            'n_samples': int(matriz.shape[0]),
        })
        return metricas

    def n_support_vectors(self) -> int:
        return int(sum(entrada['modelo']['sv_idx'].size
                       for entrada in self._modelos))

    # -- informacion -------------------------------------------------------
    def params_count(self) -> int:
        total = 0
        for entrada in self._modelos:
            total += int(entrada['modelo']['sv_idx'].size) + 1
        return total

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        estadisticas.update({
            'tipo': 'svm_nucleo',
            'kernel': self.engine.kernel_type,
            'C': float(self.C),
            'gamma': self.engine.gamma_efectiva,
            'tol': float(self.tol),
            'max_iter': int(self.max_iter),
            'is_fitted': bool(self._is_fitted),
            'clases': None if self.classes_ is None else self.classes_.tolist(),
            'n_support_vectors': self.n_support_vectors(),
            'margin': self.compute_margin(),
            'bias': float(self._bias),
            'historial_len': len(self._convergence_history),
            'timer_train': float(self._timer_train),
        })
        return estadisticas

    def verificar_estabilidad(self) -> Dict[str, bool]:
        estado = {'entrenado': bool(self._is_fitted)}
        if self._is_fitted:
            for entrada in self._modelos:
                alpha = entrada['modelo']['alpha']
                estado['alphas_finitas'] = bool(np.all(np.isfinite(alpha)))
                estado['alphas_en_rango'] = bool(
                    np.all(alpha >= -1e-8) and np.all(alpha <= self.C + 1e-8)
                )
                estado['bias_finito'] = bool(np.isfinite(entrada['modelo']['bias']))
                if not all(estado.values()):
                    break
        return estado

    # -- persistencia ------------------------------------------------------
    def save(self, filepath: str) -> None:
        with open(filepath, 'wb') as fichero:
            pickle.dump(self, fichero, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath: str) -> None:
        with open(filepath, 'rb') as fichero:
            cargado = pickle.load(fichero)
        self.__dict__.update(cargado.__dict__)

    def get_config(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'kernel': self.engine.kernel_type,
            'C': self.C,
            'gamma': self.engine.gamma,
            'degree': self.engine.degree,
            'tol': self.tol,
            'max_iter': self.max_iter,
        }

    def summary(self) -> str:
        configuracion = self.get_config()
        estadisticas = self.obtener_estadisticas()
        return "\n".join([
            f"=== {configuracion['nombre']} ===",
            (f"Kernel: {configuracion['kernel']}, C: {configuracion['C']}, "
             f"gamma: {estadisticas.get('gamma')}"),
            (f"Input: {configuracion['input_size']}, "
             f"Output: {configuracion['output_size']}"),
            (f"Fitted: {estadisticas['is_fitted']}, "
             f"Margin: {estadisticas['margin']:.4f}"),
            (f"Support vectors: {estadisticas['n_support_vectors']}, "
             f"Params: {self.params_count()}"),
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"


# ---------------------------------------------------------------------------
# 2) SVM con Random Fourier Features (RFF/ORF)
# ---------------------------------------------------------------------------
class NeuronaSVMHazAleatorio(NeuronaMemoriaBase):
    """SVM lineal sobre RFF/ORF con perdida squared hinge y Adam."""

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaSVMHazAleatorio",
                 n_componentes: int = 256, C: float = 1.0,
                 gamma: Any = "scale", ortogonal: bool = True,
                 learning_rate: float = 0.05, epochs: int = 120,
                 batch_size: int = 64, probabilidad: bool = True,
                 seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre)
        self.n_componentes = max(4, int(n_componentes))
        self.C = max(1e-6, float(C))
        self.learning_rate = max(1e-5, float(learning_rate))
        self.epochs = max(1, int(epochs))
        self.batch_size = max(1, int(batch_size))
        self.probabilidad = bool(probabilidad)
        self.seed = int(LUCIA_SVM_CONFIG["random_seed"]
                        if seed is None else seed)
        self.engine = KernelEngine("rbf", gamma)
        self.ortogonal = bool(ortogonal)
        self.classes_: Optional[np.ndarray] = None
        self._pesos: Optional[np.ndarray] = None
        self._sesgos: Optional[np.ndarray] = None
        self._platt: List[_PlattScaler] = []
        self._is_fitted = False
        self._historial: List[float] = []
        self._timer_train = 0.0
        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    def _entrenar_lineal(self, Z: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float, List[float]]:
        n, dimension = Z.shape
        w = np.zeros(dimension, dtype=np.float64)
        b = 0.0
        optimizador = OptimizadorAdam(learning_rate=self.learning_rate)
        parametros = {'w': w, 'b': np.array([b])}
        generador = np.random.default_rng(self.seed)
        historial: List[float] = []
        for _ in range(self.epochs):
            orden = generador.permutation(n)
            perdida_epoca = 0.0
            for inicio in range(0, n, self.batch_size):
                lote = orden[inicio:inicio + self.batch_size]
                Zb, yb = Z[lote], y[lote]
                f = Zb @ parametros['w'] + parametros['b'][0]
                margen = 1.0 - yb * f
                activo = margen > 0.0
                # Primal: 0.5||w||^2 + C * sum(hinge^2); dividido por n.
                perdida = (0.5 * float(parametros['w'] @ parametros['w']) / n
                           + self.C * float(np.mean(np.maximum(margen, 0.0) ** 2)))
                perdida_epoca += perdida * len(lote)
                factor = np.where(activo, -2.0 * self.C * margen / len(lote), 0.0)
                grad_w = parametros['w'] / n + Zb.T @ (factor * yb)
                grad_b = np.array([float(np.sum(factor * yb))])
                optimizador.step(parametros, {'w': grad_w, 'b': grad_b})
            historial.append(perdida_epoca / n)
        self._pesos = np.array(parametros['w'], copy=True)
        self._sesgos = np.array([parametros['b'][0]], dtype=np.float64)
        return self._pesos, float(self._sesgos[0]), historial

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
            learning_rate: Optional[float] = None, verbose: bool = False,
            **kwargs: Any) -> List[float]:
        matriz, etiquetas, clases = _validar_clasificacion(X, y, self.input_size)
        if epochs is not None:
            self.epochs = max(1, int(epochs))
        if learning_rate is not None:
            self.learning_rate = max(1e-5, float(learning_rate))
        inicio = time.perf_counter()
        if isinstance(self.engine.gamma, str) and self.engine.gamma == "alignment":
            self.engine.elegir_gamma_alineacion(
                matriz, _objetivos_binarios(etiquetas, clases)
            )
        Z = self.engine.ajustar_haz_aleatorio(
            matriz, self.n_componentes, self.ortogonal, self.seed
        )
        self.classes_ = clases
        pesos: List[np.ndarray] = []
        sesgos: List[float] = []
        self._platt = []
        self._historial = []
        if clases.size == 2:
            objetivos = [np.where(etiquetas == clases[1], 1.0, -1.0)]
        else:
            objetivos = [np.where(etiquetas == clase, 1.0, -1.0)
                         for clase in clases]
        for binario in objetivos:
            w, b, historial = self._entrenar_lineal(Z, binario)
            pesos.append(w)
            sesgos.append(b)
            self._historial = historial
            decision = Z @ w + b
            self._platt.append(_PlattScaler().fit(
                decision, (binario > 0).astype(np.float64)
            ))
        self._pesos = np.stack(pesos, axis=0)
        self._sesgos = np.asarray(sesgos, dtype=np.float64)
        self._is_fitted = True
        self._timer_train = time.perf_counter() - inicio
        if self._historial:
            self.registrar_perdida(self._historial[-1])
        if verbose:
            logger.info("%s: %d componentes RFF, %.3fs",
                        self.nombre, self.n_componentes, self._timer_train)
        return list(self._historial)

    def train(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
              learning_rate: Optional[float] = None, verbose: bool = False,
              **kwargs: Any) -> Dict[str, Any]:
        historial = self.fit(X, y, epochs=epochs,
                             learning_rate=learning_rate, verbose=verbose,
                             **kwargs)
        return {'historial': historial,
                'perdida_final': float(historial[-1]) if historial else None}

    def _mapa(self, X: np.ndarray) -> np.ndarray:
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        if matriz.shape[1] != self.input_size:
            raise ValueError(
                f"Se esperaban {self.input_size} caracteristicas y llegaron "
                f"{matriz.shape[1]}"
            )
        return self.engine.transformar_haz_aleatorio(matriz)

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("El modelo no esta entrenado: llama a fit primero")
        Z = self._mapa(X)
        puntuaciones = Z @ self._pesos.T + self._sesgos[None, :]
        if puntuaciones.shape[1] == 1:
            return puntuaciones[:, 0]
        return puntuaciones

    def predict(self, X: np.ndarray) -> np.ndarray:
        puntuaciones = self.decision_function(X)
        if puntuaciones.ndim == 1:
            return np.where(puntuaciones > 0, self.classes_[1], self.classes_[0])
        return self.classes_[np.argmax(puntuaciones, axis=1)]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("El modelo no esta entrenado: llama a fit primero")
        if len(self.classes_) == 2:
            decision = np.asarray(self.decision_function(X)).reshape(-1)
            probabilidad = (self._platt[0].transform(decision)
                            if self._platt and self._platt[0].ajustado
                            else _sigmoide(decision))
            return np.column_stack([1.0 - probabilidad, probabilidad])
        return _softmax(self.decision_function(X), eje=1)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(self.predict(X) == np.asarray(y).reshape(-1)))

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        matriz, etiquetas, clases = _validar_clasificacion(X, y, self.input_size)
        metricas = _metricas_clasificacion(etiquetas, self.predict(matriz), clases)
        metricas.update({
            'n_components': self.n_componentes,
            'loss': float(self._historial[-1]) if self._historial else 0.0,
            'n_samples': int(matriz.shape[0]),
        })
        return metricas

    def params_count(self) -> int:
        return int(self._pesos.size + self._sesgos.size) if self._pesos is not None else 0

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        estadisticas.update({
            'tipo': 'svm_haz_aleatorio',
            'n_componentes': self.n_componentes,
            'ortogonal': self.ortogonal,
            'C': self.C,
            'gamma': self.engine.gamma_efectiva,
            'is_fitted': bool(self._is_fitted),
            'historial_len': len(self._historial),
            'timer_train': float(self._timer_train),
        })
        return estadisticas

    def verificar_estabilidad(self) -> Dict[str, bool]:
        estado = {'entrenado': bool(self._is_fitted)}
        if self._pesos is not None:
            estado['pesos_finitos'] = bool(np.all(np.isfinite(self._pesos)))
            estado['pesos_no_explosivos'] = bool(
                float(np.max(np.abs(self._pesos))) < 1e6
            )
        return estado

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
            'n_componentes': self.n_componentes,
            'C': self.C,
            'gamma': self.engine.gamma,
            'ortogonal': self.ortogonal,
        }

    def summary(self) -> str:
        return "\n".join([
            f"=== {self.nombre} ===",
            f"RFF: {self.n_componentes} (ortogonal={self.ortogonal})",
            f"Kernel: rbf, gamma={self.engine.gamma_efectiva}",
            f"Params: {self.params_count()}",
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(rff={self.n_componentes})"


# ---------------------------------------------------------------------------
# 3) SVM con Nystrom + LS-SVM primal
# ---------------------------------------------------------------------------
class NeuronaSVMNystrom(NeuronaMemoriaBase):
    """LS-SVM primal sobre mapa Nystrom (ridge en caracteristicas)."""

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaSVMNystrom",
                 n_componentes: int = 128, C: float = 1.0,
                 gamma: Any = "scale", metodo_landmarks: str = "kmeans++",
                 probabilidad: bool = True,
                 seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre)
        self.n_componentes = max(2, int(n_componentes))
        self.C = max(1e-6, float(C))
        self.metodo_landmarks = metodo_landmarks
        self.probabilidad = bool(probabilidad)
        self.seed = int(LUCIA_SVM_CONFIG["random_seed"]
                        if seed is None else seed)
        self.engine = KernelEngine("rbf", gamma)
        self.classes_: Optional[np.ndarray] = None
        self._betas: Optional[np.ndarray] = None
        self._platt: List[_PlattScaler] = []
        self._is_fitted = False
        self._timer_train = 0.0
        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        self.pesos = None
        self.sesgo = None

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
            learning_rate: Optional[float] = None, verbose: bool = False,
            **kwargs: Any) -> List[float]:
        matriz, etiquetas, clases = _validar_clasificacion(X, y, self.input_size)
        inicio = time.perf_counter()
        if isinstance(self.engine.gamma, str) and self.engine.gamma == "alignment":
            self.engine.elegir_gamma_alineacion(
                matriz, _objetivos_binarios(etiquetas, clases)
            )
        Z = self.engine.ajustar_nystrom(
            matriz, self.n_componentes, self.metodo_landmarks, self.seed
        )
        Z_aumentada = np.hstack([Z, np.ones((Z.shape[0], 1))])
        self.classes_ = clases
        betas: List[np.ndarray] = []
        self._platt = []
        perdidas: List[float] = []
        if clases.size == 2:
            objetivos = [np.where(etiquetas == clases[1], 1.0, -1.0)]
        else:
            objetivos = [np.where(etiquetas == clase, 1.0, -1.0)
                         for clase in clases]
        for binario in objetivos:
            matriz_ridge = (Z_aumentada.T @ Z_aumentada
                            + (1.0 / self.C) * np.eye(Z_aumentada.shape[1]))
            vector = Z_aumentada.T @ binario
            try:
                beta = np.linalg.solve(matriz_ridge, vector)
            except np.linalg.LinAlgError:  # pragma: no cover
                beta = np.linalg.lstsq(matriz_ridge, vector, rcond=None)[0]
            betas.append(beta)
            decision = Z_aumentada @ beta
            self._platt.append(_PlattScaler().fit(
                decision, (binario > 0).astype(np.float64)
            ))
            perdidas.append(float(np.mean((decision - binario) ** 2)))
        self._betas = np.stack(betas, axis=0)
        self._is_fitted = True
        self._timer_train = time.perf_counter() - inicio
        if perdidas:
            self.registrar_perdida(perdidas[-1])
        if verbose:
            logger.info("%s: Nystrom m=%d, %.3fs",
                        self.nombre, self.n_componentes, self._timer_train)
        return perdidas

    def train(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
              learning_rate: Optional[float] = None, verbose: bool = False,
              **kwargs: Any) -> Dict[str, Any]:
        return {'historial': self.fit(X, y, verbose=verbose, **kwargs)}

    def _mapa(self, X: np.ndarray) -> np.ndarray:
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        if matriz.shape[1] != self.input_size:
            raise ValueError(
                f"Se esperaban {self.input_size} caracteristicas y llegaron "
                f"{matriz.shape[1]}"
            )
        Z = self.engine.transformar_nystrom(matriz)
        return np.hstack([Z, np.ones((Z.shape[0], 1))])

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("El modelo no esta entrenado: llama a fit primero")
        puntuaciones = self._mapa(X) @ self._betas.T
        if puntuaciones.shape[1] == 1:
            return puntuaciones[:, 0]
        return puntuaciones

    def predict(self, X: np.ndarray) -> np.ndarray:
        puntuaciones = self.decision_function(X)
        if puntuaciones.ndim == 1:
            return np.where(puntuaciones > 0, self.classes_[1], self.classes_[0])
        return self.classes_[np.argmax(puntuaciones, axis=1)]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("El modelo no esta entrenado: llama a fit primero")
        if len(self.classes_) == 2:
            decision = np.asarray(self.decision_function(X)).reshape(-1)
            probabilidad = (self._platt[0].transform(decision)
                            if self._platt and self._platt[0].ajustado
                            else _sigmoide(decision))
            return np.column_stack([1.0 - probabilidad, probabilidad])
        return _softmax(self.decision_function(X), eje=1)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(self.predict(X) == np.asarray(y).reshape(-1)))

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        matriz, etiquetas, clases = _validar_clasificacion(X, y, self.input_size)
        metricas = _metricas_clasificacion(etiquetas, self.predict(matriz), clases)
        decision = np.asarray(self.decision_function(matriz), dtype=np.float64)
        if decision.ndim == 1:
            objetivo = np.where(etiquetas == clases[1], 1.0, -1.0)
            perdida = float(np.mean((decision - objetivo) ** 2))
        else:
            perdidas = []
            for indice, clase in enumerate(clases):
                objetivo = np.where(etiquetas == clase, 1.0, -1.0)
                perdidas.append(np.mean((decision[:, indice] - objetivo) ** 2))
            perdida = float(np.mean(perdidas))
        metricas.update({
            'loss': perdida,
            'n_components': self.n_componentes,
            'n_samples': int(matriz.shape[0]),
        })
        return metricas

    def params_count(self) -> int:
        return int(self._betas.size) if self._betas is not None else 0

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        estadisticas.update({
            'tipo': 'svm_nystrom',
            'n_componentes': self.n_componentes,
            'metodo_landmarks': self.metodo_landmarks,
            'C': self.C,
            'gamma': self.engine.gamma_efectiva,
            'is_fitted': bool(self._is_fitted),
            'timer_train': float(self._timer_train),
        })
        return estadisticas

    def verificar_estabilidad(self) -> Dict[str, bool]:
        estado = {'entrenado': bool(self._is_fitted)}
        if self._betas is not None:
            estado['betas_finitas'] = bool(np.all(np.isfinite(self._betas)))
        return estado

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
            'n_componentes': self.n_componentes,
            'C': self.C,
            'gamma': self.engine.gamma,
            'metodo_landmarks': self.metodo_landmarks,
        }

    def summary(self) -> str:
        return "\n".join([
            f"=== {self.nombre} ===",
            f"Nystrom: {self.n_componentes} landmarks ({self.metodo_landmarks})",
            f"Kernel: rbf, gamma={self.engine.gamma_efectiva}",
            f"Params: {self.params_count()}",
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(nystrom={self.n_componentes})"


# ---------------------------------------------------------------------------
# 4) Adaptador de compatibilidad con RF_SL1_2
# ---------------------------------------------------------------------------
class SupportVectorMachineOptimizer(NeuronaSVMNucleo):
    """API historica de RF_SL1_2 respaldada por el SVM dual real."""

    def __init__(self, input_size: int = 4, output_size: int = 8,
                 nombre: str = "SupportVectorMachineOptimizer",
                 **kwargs: Any) -> None:
        super().__init__(input_size=input_size, output_size=output_size,
                         nombre=nombre, **kwargs)
        self._kernel_type = self.engine.kernel_type
        self._C = float(self.C)
        self._gamma = self.engine.gamma
        self._degree = int(self.engine.degree)
        self._tol = float(self.tol)
        self._max_iter = int(self.max_iter)
        self._convergence_history: List[float] = []
        self._timer_train = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: Optional[int] = None,
            verbose: bool = False, **kwargs: Any) -> List[float]:
        historial = super().fit(X, y, epochs=epochs, verbose=verbose, **kwargs)
        self._kernel_type = self.engine.kernel_type
        self._C = float(self.C)
        self._gamma = self.engine.gamma
        self._degree = int(self.engine.degree)
        self._tol = float(self.tol)
        self._max_iter = int(self.max_iter)
        self._convergence_history = list(historial)
        self._timer_train = float(self._timer_train)
        return historial

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        matriz, etiquetas, clases = _validar_clasificacion(
            X, y, self.input_size
        )
        prediccion = self.predict(matriz)
        exactitud = float(np.mean(prediccion == etiquetas))
        decision = np.asarray(self.decision_function(matriz), dtype=np.float64)
        if decision.ndim == 1:
            perdida = self.compute_loss(
                decision, np.where(etiquetas == clases[-1], 1.0, -1.0)
            )
        else:
            perdidas = [
                self.compute_loss(
                    decision[:, indice],
                    np.where(etiquetas == clase, 1.0, -1.0),
                )
                for indice, clase in enumerate(clases)
            ]
            perdida = float(np.mean(perdidas))
        return {
            'accuracy': exactitud,
            'margin': self.compute_margin(),
            'mse': perdida,
            'n_samples': int(matriz.shape[0]),
        }

    def obtener_estadisticas(self) -> Dict[str, Any]:
        estadisticas = super().obtener_estadisticas()
        estadisticas.update({
            'learning_rate': self._C,
            'kernel_type': self._kernel_type,
            'C': self._C,
            'gamma': self._gamma,
            'degree': self._degree,
            'max_iter': self._max_iter,
            'is_fitted': self._is_fitted,
            'margin': self.compute_margin(),
            'bias': self._bias,
            'n_support_vectors': self.n_support_vectors(),
        })
        if self._convergence_history:
            estadisticas['final_loss'] = float(self._convergence_history[-1])
        return estadisticas

    def verificar_estabilidad(self) -> Dict[str, bool]:
        estado: Dict[str, bool] = {
            'entrenado': bool(self._is_fitted),
            'alphas_finitas': bool(self._alphas is not None
                                   and np.all(np.isfinite(self._alphas))),
        }
        if self._is_fitted:
            estado['alphas_en_rango'] = bool(
                self._alphas is not None
                and np.all(self._alphas >= -1e-8)
                and np.all(self._alphas <= self.C + 1e-8)
            )
            estado['bias_finito'] = bool(np.isfinite(self._bias))
        return estado

    # -- metodos lineales historicos (compatibilidad) ----------------------
    def forward(self, entrada: np.ndarray) -> np.ndarray:
        return self.decision_function(entrada)

    def predict(self, entrada: np.ndarray) -> np.ndarray:
        return super().predict(entrada)

    def backward(self, gradiente_salida: np.ndarray,
                 entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X = np.asarray(entrada, dtype=np.float64)
        gradiente = np.asarray(gradiente_salida, dtype=np.float64)
        if gradiente.ndim == 1:
            gradiente = gradiente.reshape(-1, 1)
        return X.T @ gradiente / max(1, X.shape[0]), np.mean(
            gradiente, axis=0, keepdims=True
        )

    def update_weights(self, grad_pesos: np.ndarray,
                       grad_sesgo: np.ndarray) -> None:
        if self.pesos is None:
            self.pesos = np.zeros((self.input_size, 1))
        if self.sesgo is None:
            self.sesgo = np.zeros((1, 1))
        self.pesos = self.pesos - (1.0 / self.C) * grad_pesos
        self.sesgo = self.sesgo - (1.0 / self.C) * grad_sesgo

    def _decision_legacy(self, entrada: np.ndarray) -> np.ndarray:
        decision = np.asarray(self.decision_function(entrada), dtype=np.float64)
        if decision.ndim == 2:
            decision = decision[:, 0]
        return decision.reshape(-1)

    def apply_gradient(self, entrada: np.ndarray,
                       objetivo: np.ndarray) -> float:
        salida = self._decision_legacy(entrada).reshape(-1, 1)
        etiquetas = np.asarray(objetivo, dtype=np.float64).reshape(-1, 1)
        gradiente = np.where(etiquetas * salida < 1.0, -etiquetas, 0.0)
        grad_pesos, grad_sesgo = self.backward(gradiente, entrada)
        self.update_weights(grad_pesos, grad_sesgo)
        margen = 1.0 - etiquetas * self._decision_legacy(entrada).reshape(-1, 1)
        return float(np.mean(np.maximum(0.0, margen)))

    def train_step(self, entrada: np.ndarray,
                   objetivo: np.ndarray) -> Dict[str, float]:
        etiquetas = np.asarray(objetivo, dtype=np.float64).reshape(-1, 1)
        antes = float(np.mean(np.maximum(
            0.0, 1.0 - etiquetas
            * self._decision_legacy(entrada).reshape(-1, 1)
        )))
        despues = self.apply_gradient(entrada, objetivo)
        return {'loss_before': antes, 'loss_after': despues,
                'improvement': antes - despues}

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
            'kernel_type': self._kernel_type,
            'C': self._C,
            'gamma': self._gamma,
            'degree': self._degree,
            'max_iter': self._max_iter,
        }

    def summary(self) -> str:
        configuracion = self.get_config()
        estadisticas = self.obtener_estadisticas()
        return "\n".join([
            f"=== {configuracion['nombre']} ===",
            (f"Kernel: {configuracion['kernel_type']}, "
             f"C: {configuracion['C']}, gamma: {configuracion['gamma']}"),
            (f"Input: {configuracion['input_size']}, "
             f"Output: {configuracion['output_size']}"),
            (f"Fitted: {estadisticas.get('is_fitted', False)}, "
             f"Margin: {estadisticas.get('margin', 0):.4f}"),
            (f"Support vectors: {estadisticas.get('n_support_vectors', 0)}, "
             f"Params: {self.params_count()}"),
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"


# ---------------------------------------------------------------------------
# Fabrica, evaluacion y persistencia
# ---------------------------------------------------------------------------
def crear_neurona(tipo: str = "svm", input_size: int = 4,
                  output_size: int = 1, **kwargs: Any
                  ) -> NeuronaMemoriaBase:
    clave = str(tipo or "").strip().lower()
    if clave in ("svm", "nucleo", "svm_nucleo", "kernel"):
        return NeuronaSVMNucleo(input_size=input_size,
                                output_size=output_size, **kwargs)
    if clave in ("rff", "haz_aleatorio", "aleatorio", "orf"):
        return NeuronaSVMHazAleatorio(input_size=input_size,
                                      output_size=output_size, **kwargs)
    if clave in ("nystrom", "nyström"):
        return NeuronaSVMNystrom(input_size=input_size,
                                 output_size=output_size, **kwargs)
    if clave in ("compat", "compatibilidad", "optimizer"):
        return SupportVectorMachineOptimizer(input_size=input_size,
                                             output_size=output_size, **kwargs)
    raise ValueError(
        f"Tipo desconocido: {tipo!r}. Usa: svm, rff, nystrom, compat"
    )


def tipos_disponibles() -> List[str]:
    return ["svm", "rff", "nystrom", "compat"]


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
        raise TypeError("El fichero no contiene una neurona SVM")
    return modelo


def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SBRTM_RF_SL1_2_1.py``)."""
    generador = np.random.default_rng(2026)
    X = generador.uniform(-2.0, 2.0, size=(240, 2))
    y = np.where(X[:, 0] ** 2 + X[:, 1] ** 2 > 1.5, 1, -1)
    y = y + np.where(generador.random(240) < 0.05, -2 * y, 0)

    print("=" * 78)
    print("RF_SL_SBRTM_RF_SL1_2_1 :: SVM y nucleos mejorados (v%s)" % __version__)
    print("Muestras:", X.shape[0], "| clases:", np.unique(y).tolist())
    print("=" * 78)

    resultados: Dict[str, Any] = {}
    for etiqueta, tipo in (("svm-rbf", "svm"), ("rff", "rff"),
                           ("nystrom", "nystrom")):
        modelo = crear_neurona(tipo, input_size=2, output_size=1,
                              C=1.0, seed=7)
        inicio = time.perf_counter()
        resultado = entrenar_y_evaluar(modelo, X, y)
        duracion = time.perf_counter() - inicio
        resultados[etiqueta] = resultado
        metricas = resultado['metricas']
        print("%-10s accuracy=%.4f f1=%.4f loss=%.4f params=%d t=%.3fs"
              % (etiqueta, metricas['accuracy'], metricas['f1'],
                 metricas['loss'], modelo.params_count(), duracion))

    # Multiclase con SVM de nucleo
    centros = np.array([[-2.0, -2.0], [2.0, 0.0], [0.0, 2.5]])
    Xm = np.vstack([centro + generador.normal(0, 0.6, (90, 2))
                    for centro in centros])
    ym = np.repeat([0, 1, 2], 90)
    modelo = crear_neurona("svm", input_size=2, output_size=1,
                          kernel="rbf", C=1.0, seed=3)
    resultado = entrenar_y_evaluar(modelo, Xm, ym)
    print("multiclase  accuracy=%.4f f1=%.4f clases=%s"
          % (resultado['metricas']['accuracy'],
             resultado['metricas']['f1'], modelo.classes_.tolist()))
    print("probabilidades (3):", np.round(modelo.predict_proba(Xm[:3]), 3).tolist())
    print("=" * 78)
    return resultados


__all__ = [
    'NeuronaMemoriaBase',
    'KernelEngine',
    'NeuronaSVMNucleo',
    'NeuronaSVMHazAleatorio',
    'NeuronaSVMNystrom',
    'SupportVectorMachineOptimizer',
    'OptimizadorAdam',
    'crear_neurona',
    'tipos_disponibles',
    'entrenar_y_evaluar',
    'benchmark_modelo',
    'guardar_modelo',
    'cargar_modelo',
    'demo',
    'LUCIA_SVM_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
