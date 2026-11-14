"""RF_SL_SNRTM__rfsl_base1.py
Base y neuronas especializadas de RF_SL (SBRTM · RF · 2026).
=============================================================================

Modulo autocontenido y preparado para importar. Refactoriza el antiguo
``RF_SL_SNRTM__rfsl_base1.py`` (que solo tenia ``NeuronaMemoriaBase`` y
``TreeBuilder`` sin imports) y lo amplia con una familia de neuronas
especializadas mediante algoritmos de calculo neuronal:

  * ``NeuronaMemoriaBase``: base con memoria acotada de activaciones,
    gradientes y perdidas, estadisticas y comprobacion de estabilidad.
  * ``TreeBuilder``: arbol de decision por reduccion de varianza, con
    umbrales por cuantiles, ``min_samples_leaf`` e importancias de atributos.
  * ``NeuronaEntrenable``: base entrenable con Adam, mini-lotes, validacion,
    early stopping, weight decay, recorte de gradiente y restauracion del
    mejor modelo.
  * ``NeuronaKolmogorovArnold``: red KAN (Kolmogorov-Arnold Network) con una
    funcion aprendible por arista, representada como combinacion de bases RBF
    sobre una rejilla por caracteristica + rama lineal SiLU. Entrena por
    retropropagacion analitica.
  * ``NeuronaArbolDiferenciable``: arbol de decision suave (soft decision
    tree) con compuertas sigmoides por nodo, hojas aprendibles, temperatura
    anisotropa/annealing y gradientes exactos.
  * ``NeuronaAtencionCaracteristicas``: compuerta de atencion por
    caracteristica (feature-wise gating) + MLP, con regularizacion L1 para
    inducir esparsidad e importancias interpretables.
  * ``NeuronaBosqueNeuronal``: bosque de arboles diferenciables con
    submuestreo de caracteristicas y mezcla aprendida (softmax) de sus
    predicciones.

Todo el modulo usa solo la biblioteca estandar y NumPy: no importa ningun
otro fichero del proyecto, por lo que puede importarse por ruta, como modulo
de primer nivel o dentro del paquete.

Uso rapido
----------
    from RF_SL_SNRTM__rfsl_base1 import (
        NeuronaKolmogorovArnold, NeuronaArbolDiferenciable,
        NeuronaAtencionCaracteristicas, NeuronaBosqueNeuronal,
        crear_neurona,
    )

    neurona = NeuronaKolmogorovArnold(input_size=3, output_size=1)
    neurona.fit(X, y, epochs=100, learning_rate=0.01)
    y_pred = neurona.predict(X)
    print(neurona.evaluate(X, y))

    # o mediante la fabrica:
    neurona = crear_neurona("bosque", input_size=3, output_size=1)
"""

from __future__ import annotations

import logging
import math
import pickle
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

__version__ = "2026.1.0"

# ---------------------------------------------------------------------------
# Configuracion global
# ---------------------------------------------------------------------------
LUCIA_RF_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "learning_rate": 0.01,
    "epochs": 100,
    "batch_size": 32,
    "validation_split": 0.0,
    "early_stopping": False,
    "patience": 15,
    "weight_decay": 0.0,
    "max_norm": 5.0,
    "kan_bases": 5,
    "profundidad_arbol": 3,
    "temperatura_inicial": 1.0,
    "temperatura_minima": 0.1,
    "n_arboles": 5,
    "submuestreo_caracteristicas": 0.8,
}


# ---------------------------------------------------------------------------
# Utilidades numericas
# ---------------------------------------------------------------------------
def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def _silu(x: np.ndarray) -> np.ndarray:
    return x * _sigmoide(x)


def _softmax(x: np.ndarray, eje: int = -1) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    maximo = np.max(x, axis=eje, keepdims=True)
    exponencial = np.exp(x - maximo)
    return exponencial / np.maximum(np.sum(exponencial, axis=eje, keepdims=True), 1e-12)


def _preparar_entrada(entrada: Any, dimension: int) -> Tuple[np.ndarray, bool]:
    """Convierte la entrada en matriz (n, dimension); indica si era un vector."""
    arreglo = np.asarray(entrada, dtype=np.float64)
    unico = arreglo.ndim == 1
    if unico:
        arreglo = arreglo[None, :]
    if arreglo.ndim != 2:
        raise ValueError("La entrada debe ser un vector o una matriz 2D")
    if arreglo.shape[1] != dimension:
        raise ValueError(
            f"Se esperaban {dimension} caracteristicas y llegaron {arreglo.shape[1]}"
        )
    if arreglo.size and not np.all(np.isfinite(arreglo)):
        arreglo = np.nan_to_num(arreglo, nan=0.0, posinf=0.0, neginf=0.0)
    return arreglo, unico


def _validar_datos(X: Any, y: Any, input_size: int,
                   output_size: int) -> Tuple[np.ndarray, np.ndarray]:
    """Valida y normaliza X (n, input_size) e y (n, output_size)."""
    matriz = np.asarray(X, dtype=np.float64)
    objetivo = np.asarray(y, dtype=np.float64)
    if matriz.ndim != 2:
        raise ValueError("X debe ser una matriz 2D (muestras, caracteristicas)")
    if matriz.shape[1] != input_size:
        raise ValueError(
            f"X tiene {matriz.shape[1]} caracteristicas y se esperaban {input_size}"
        )
    if matriz.shape[0] == 0:
        raise ValueError("X no contiene muestras")
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


def _metricas_regresion(prediccion: np.ndarray, real: np.ndarray) -> Dict[str, float]:
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
        "mse": mse,
        "mae": mae,
        "rmse": float(math.sqrt(mse)),
        "r2": r2,
        "n_samples": int(real.shape[0]),
    }


def _norma_global(arreglos: Sequence[Optional[np.ndarray]]) -> float:
    total = 0.0
    for arreglo in arreglos:
        if arreglo is None:
            continue
        total += float(np.sum(np.square(np.asarray(arreglo, dtype=np.float64))))
    return float(math.sqrt(total))


# ---------------------------------------------------------------------------
# Optimizador Adam con recorte global de gradiente
# ---------------------------------------------------------------------------
class OptimizadorAdam:
    """Adam sobre un diccionario de parametros (referencias compartidas)."""

    def __init__(self, parametros: Dict[str, np.ndarray],
                 learning_rate: float = 0.01, beta1: float = 0.9,
                 beta2: float = 0.999, epsilon: float = 1e-8,
                 weight_decay: float = 0.0, max_norm: float = 5.0) -> None:
        self.parametros = parametros
        self.learning_rate = max(1e-8, float(learning_rate))
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.weight_decay = max(0.0, float(weight_decay))
        self.max_norm = max(0.0, float(max_norm))
        self.momentos = {k: np.zeros_like(v, dtype=np.float64) for k, v in parametros.items()}
        self.velocidades = {k: np.zeros_like(v, dtype=np.float64) for k, v in parametros.items()}
        self.paso_actual = 0

    def step(self, gradientes: Dict[str, np.ndarray]) -> None:
        if not gradientes:
            return
        preparados: Dict[str, np.ndarray] = {}
        for nombre, parametro in self.parametros.items():
            gradiente = gradientes.get(nombre)
            if gradiente is None:
                continue
            gradiente = np.asarray(gradiente, dtype=np.float64)
            if gradiente.shape != parametro.shape:
                raise ValueError(
                    f"Gradiente incompatible para {nombre}: "
                    f"{gradiente.shape} != {parametro.shape}"
                )
            if self.weight_decay > 0.0:
                gradiente = gradiente + self.weight_decay * parametro
            preparados[nombre] = gradiente
        if not preparados:
            return
        if self.max_norm > 0.0:
            norma = math.sqrt(sum(float(np.sum(g * g)) for g in preparados.values()))
            if norma > self.max_norm:
                factor = self.max_norm / (norma + 1e-12)
                preparados = {k: g * factor for k, g in preparados.items()}
        self.paso_actual += 1
        correccion1 = 1.0 - self.beta1 ** self.paso_actual
        correccion2 = 1.0 - self.beta2 ** self.paso_actual
        for nombre, gradiente in preparados.items():
            self.momentos[nombre] = (self.beta1 * self.momentos[nombre]
                                    + (1.0 - self.beta1) * gradiente)
            self.velocidades[nombre] = (self.beta2 * self.velocidades[nombre]
                                        + (1.0 - self.beta2) * gradiente * gradiente)
            m_hat = self.momentos[nombre] / correccion1
            v_hat = self.velocidades[nombre] / correccion2
            self.parametros[nombre] -= (self.learning_rate * m_hat
                                        / (np.sqrt(v_hat) + self.epsilon))


# ---------------------------------------------------------------------------
# Base de neurona con memoria
# ---------------------------------------------------------------------------
class NeuronaMemoriaBase:
    """Clase base de neurona con memoria acotada de activaciones y gradientes."""

    def __init__(self, input_size: int, output_size: int, nombre: str = "Neurona"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.historial_activaciones: Deque[np.ndarray] = deque(maxlen=100)
        self.historial_gradientes: Deque[Dict[str, np.ndarray]] = deque(maxlen=100)
        self.historial_perdidas: Deque[float] = deque(maxlen=500)
        self.pasos: int = 0

    # -- API que deben implementar las subclases ---------------------------
    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, e: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    # -- memoria -----------------------------------------------------------
    def registrar_activacion(self, salida: np.ndarray) -> None:
        self.historial_activaciones.append(np.array(salida, copy=True))
        self.pasos += 1

    def registrar_gradientes(self, gradientes: Dict[str, np.ndarray]) -> None:
        copia = {k: np.array(v, copy=True) for k, v in gradientes.items()}
        copia["norma"] = np.array([_norma_global(list(gradientes.values()))])
        self.historial_gradientes.append(copia)

    def registrar_perdida(self, perdida: float) -> None:
        self.historial_perdidas.append(float(perdida))

    def resetear_historial(self) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.historial_perdidas.clear()

    # -- informacion -------------------------------------------------------
    def _arreglos_parametros(self) -> List[np.ndarray]:
        generador = getattr(self, "_parametros_gradientes", None)
        if callable(generador):
            try:
                return [np.asarray(v, dtype=np.float64)
                        for v in generador().values()]
            except Exception:  # pragma: no cover - depende de la subclase
                pass
        return [np.asarray(p, dtype=np.float64)
                for p in (self.pesos, self.sesgo) if p is not None]

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'pasos': self.pasos,
            'historial_activaciones_len': len(self.historial_activaciones),
            'historial_gradientes_len': len(self.historial_gradientes),
            'historial_perdidas_len': len(self.historial_perdidas),
        }
        if self.historial_perdidas:
            stats['ultima_perdida'] = float(self.historial_perdidas[-1])
        if self.pesos is not None:
            stats['pesos_shape'] = tuple(self.pesos.shape)
            stats['pesos_size'] = int(self.pesos.size)
        if self.sesgo is not None:
            stats['sesgo_shape'] = tuple(np.shape(self.sesgo))
        return stats

    def info(self) -> str:
        return (f"{self.nombre}(in={self.input_size},out={self.output_size},"
                f"pasos={self.pasos})")

    def params_count(self) -> int:
        total = 0
        if self.pesos is not None:
            total += int(np.size(self.pesos))
        if self.sesgo is not None:
            total += int(np.size(self.sesgo))
        return total

    def verificar_estabilidad(self) -> Dict[str, Any]:
        problemas: List[str] = []
        arreglos = self._arreglos_parametros()
        for indice, arreglo in enumerate(arreglos):
            if arreglo.size and not np.all(np.isfinite(arreglo)):
                problemas.append(f"parametro #{indice} contiene valores no finitos")
        return {
            'estable': not problemas,
            'problemas': problemas,
            'norma_pesos': _norma_global(arreglos),
            'n_parametros': self.params_count(),
        }


# ---------------------------------------------------------------------------
# Arbol de decision por reduccion de varianza
# ---------------------------------------------------------------------------
class TreeBuilder:
    """Constructor de arboles de decision por reduccion de varianza."""

    def __init__(self, max_depth: int = 3, min_samples_split: int = 2,
                 min_samples_leaf: int = 1, min_gain: float = 1e-8) -> None:
        self.max_depth = max(1, int(max_depth))
        self.min_samples_split = max(2, int(min_samples_split))
        self.min_samples_leaf = max(1, int(min_samples_leaf))
        self.min_gain = float(min_gain)
        self._tree: Optional[Dict[str, Any]] = None
        self.importancias_: Optional[np.ndarray] = None

    # -- ajuste ------------------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        matriz = np.asarray(X, dtype=np.float64)
        objetivo = np.asarray(y, dtype=np.float64).reshape(-1)
        if matriz.ndim != 2:
            raise ValueError("X debe ser una matriz 2D")
        if matriz.shape[0] != objetivo.shape[0]:
            raise ValueError("X e y deben tener el mismo numero de muestras")
        if matriz.shape[0] == 0:
            raise ValueError("X no contiene muestras")
        if not np.all(np.isfinite(matriz)) or not np.all(np.isfinite(objetivo)):
            matriz = np.nan_to_num(matriz, nan=0.0, posinf=0.0, neginf=0.0)
            objetivo = np.nan_to_num(objetivo, nan=0.0, posinf=0.0, neginf=0.0)
        self.importancias_ = np.zeros(matriz.shape[1], dtype=np.float64)
        self._tree = self._build_tree(matriz, objetivo, depth=0)
        total = float(np.sum(self.importancias_))
        if total > 1e-12:
            self.importancias_ = self.importancias_ / total
        return self._tree

    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int) -> Dict[str, Any]:
        n_samples = len(X)
        valor = float(np.mean(y))
        if (depth >= self.max_depth
                or n_samples < self.min_samples_split
                or n_samples < 2 * self.min_samples_leaf
                or float(np.var(y)) < 1e-12):
            return {'leaf': True, 'value': valor, 'n_samples': int(n_samples)}
        feature, umbral, ganancia = self._find_best_split(X, y)
        if ganancia < self.min_gain:
            return {'leaf': True, 'value': valor, 'n_samples': int(n_samples)}
        mascara = X[:, feature] <= umbral
        if (int(np.sum(mascara)) < self.min_samples_leaf
                or int(np.sum(~mascara)) < self.min_samples_leaf):
            return {'leaf': True, 'value': valor, 'n_samples': int(n_samples)}
        if self.importancias_ is not None:
            self.importancias_[feature] += ganancia * n_samples
        return {
            'leaf': False,
            'feature': int(feature),
            'threshold': float(umbral),
            'left': self._build_tree(X[mascara], y[mascara], depth + 1),
            'right': self._build_tree(X[~mascara], y[~mascara], depth + 1),
            'gain': float(ganancia),
            'n_samples': int(n_samples),
        }

    def _find_best_split(self, X: np.ndarray,
                         y: np.ndarray) -> Tuple[int, float, float]:
        mejor_feature, mejor_umbral, mejor_ganancia = 0, 0.0, 0.0
        varianza_padre = float(np.var(y))
        n_total = len(y)
        for feature in range(X.shape[1]):
            columna = X[:, feature]
            valores = np.unique(columna)
            if valores.size <= 1:
                continue
            if valores.size > 32:
                candidatos = np.unique(np.quantile(columna, np.linspace(0.05, 0.95, 32)))
            else:
                candidatos = (valores[:-1] + valores[1:]) / 2.0
            for umbral in candidatos:
                izquierda = columna <= umbral
                n_izquierda = int(np.sum(izquierda))
                n_derecha = n_total - n_izquierda
                if (n_izquierda < self.min_samples_leaf
                        or n_derecha < self.min_samples_leaf):
                    continue
                var_izquierda = float(np.var(y[izquierda]))
                var_derecha = float(np.var(y[~izquierda]))
                ganancia = varianza_padre - (
                    n_izquierda * var_izquierda + n_derecha * var_derecha
                ) / n_total
                if ganancia > mejor_ganancia:
                    mejor_ganancia = float(ganancia)
                    mejor_feature = int(feature)
                    mejor_umbral = float(umbral)
        return mejor_feature, mejor_umbral, mejor_ganancia

    # -- prediccion --------------------------------------------------------
    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._tree is None:
            raise RuntimeError("TreeBuilder no ajustado: llama a fit primero")
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        return np.array([self._predecir_una(fila, self._tree) for fila in matriz])

    def _predecir_una(self, x: np.ndarray, nodo: Dict[str, Any]) -> float:
        if nodo['leaf']:
            return float(nodo['value'])
        if x[nodo['feature']] <= nodo['threshold']:
            return self._predecir_una(x, nodo['left'])
        return self._predecir_una(x, nodo['right'])

    # -- informacion -------------------------------------------------------
    @property
    def arbol(self) -> Optional[Dict[str, Any]]:
        return self._tree

    def profundidad_real(self) -> int:
        if self._tree is None:
            return 0

        def _profundidad(nodo: Dict[str, Any]) -> int:
            if nodo['leaf']:
                return 1
            return 1 + max(_profundidad(nodo['left']), _profundidad(nodo['right']))

        return int(_profundidad(self._tree))

    def obtener_estadisticas(self) -> Dict[str, Any]:
        return {
            'ajustado': self._tree is not None,
            'max_depth': self.max_depth,
            'profundidad_real': self.profundidad_real(),
            'min_samples_leaf': self.min_samples_leaf,
            'importancias': (self.importancias_.tolist()
                             if self.importancias_ is not None else None),
        }


# ---------------------------------------------------------------------------
# Base entrenable por retropropagacion (Adam + mini-lotes)
# ---------------------------------------------------------------------------
class NeuronaEntrenable(NeuronaMemoriaBase):
    """Neurona con bucle de entrenamiento comun y gradientes analiticos.

    Las subclases implementan ``_parametros_gradientes`` y
    ``_perdida_y_gradientes``; esta clase aporta ``fit``, ``loss``,
    ``evaluate``, ``predict`` y utilidades de optimizacion.
    """

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntrenable", seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre)
        self.seed = int(LUCIA_RF_CONFIG["random_seed"] if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self._adam: Optional[OptimizadorAdam] = None
        self.perdidas_epocas: List[float] = []

    # -- API para subclases ------------------------------------------------
    def _parametros_gradientes(self) -> Dict[str, np.ndarray]:
        raise NotImplementedError

    def _perdida_y_gradientes(self, X: np.ndarray,
                              Y: np.ndarray) -> Tuple[float, Dict[str, np.ndarray]]:
        raise NotImplementedError

    def _preparar_datos(self, X: np.ndarray) -> None:
        """Hook: rejillas, estadisticas o reparametrizaciones previas."""

    def _ajustar_temperatura(self, epoca: int, total_epocas: int) -> None:
        """Hook: annealing de temperatura u otros hiperparametros."""

    # -- utilidades internas ----------------------------------------------
    def _copia_parametros(self) -> Dict[str, np.ndarray]:
        return {k: np.array(v, copy=True)
                for k, v in self._parametros_gradientes().items()}

    def _restaurar_parametros(self, copia: Dict[str, np.ndarray]) -> None:
        actuales = self._parametros_gradientes()
        for nombre, valor in copia.items():
            if nombre not in actuales:
                continue
            destino = actuales[nombre]
            if destino.shape == valor.shape:
                destino[...] = valor

    def _reiniciar_optimizador(self, learning_rate: float,
                               weight_decay: float = 0.0) -> None:
        self._adam = OptimizadorAdam(
            self._parametros_gradientes(),
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            max_norm=float(LUCIA_RF_CONFIG["max_norm"]),
        )

    # -- entrenamiento -----------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 100,
            learning_rate: float = 0.01, batch_size: int = 32,
            validation_split: float = 0.0, early_stopping: bool = False,
            patience: int = 15, weight_decay: float = 0.0,
            verbose: bool = False, shuffle: bool = True) -> List[float]:
        matriz, objetivo = _validar_datos(
            X, y, self.input_size, self.output_size
        )
        self._preparar_datos(matriz)
        total_muestras = len(matriz)
        indices = np.arange(total_muestras)
        if shuffle:
            self.rng.shuffle(indices)

        corte = 0
        if validation_split > 0.0 and total_muestras >= 5:
            corte = int(round(total_muestras * min(0.9, float(validation_split))))
            corte = max(1, min(total_muestras - 1, corte))
        indices_validacion = indices[:corte]
        indices_entrenamiento = indices[corte:]
        if indices_entrenamiento.size == 0:
            indices_entrenamiento = indices

        self._reiniciar_optimizador(learning_rate, weight_decay)
        self.perdidas_epocas = []
        tamano_lote = max(1, int(batch_size))
        mejor_loss = float("inf")
        mejor_copia: Optional[Dict[str, np.ndarray]] = None
        espera = 0

        for epoca in range(max(1, int(epochs))):
            self._ajustar_temperatura(epoca, max(1, int(epochs)))
            orden = np.array(indices_entrenamiento, copy=True)
            if shuffle:
                self.rng.shuffle(orden)
            for inicio in range(0, len(orden), tamano_lote):
                lote = orden[inicio:inicio + tamano_lote]
                if lote.size == 0:
                    continue
                _, gradientes = self._perdida_y_gradientes(matriz[lote], objetivo[lote])
                if self._adam is not None:
                    self._adam.step(gradientes)

            perdida_entrenamiento = self.loss(
                matriz[indices_entrenamiento], objetivo[indices_entrenamiento]
            )
            if corte > 0:
                perdida_validacion = self.loss(
                    matriz[indices_validacion], objetivo[indices_validacion]
                )
            else:
                perdida_validacion = perdida_entrenamiento

            self.perdidas_epocas.append(float(perdida_entrenamiento))
            self.registrar_perdida(perdida_entrenamiento)

            if perdida_validacion < mejor_loss - 1e-12:
                mejor_loss = float(perdida_validacion)
                mejor_copia = self._copia_parametros()
                espera = 0
            else:
                espera += 1

            if verbose and (epoca % 10 == 0 or epoca == epochs - 1):
                logger.info(
                    "%s epoca %d/%d | perdida=%.6f | val=%.6f",
                    self.nombre, epoca + 1, epochs,
                    perdida_entrenamiento, perdida_validacion,
                )
            if early_stopping and espera >= max(1, int(patience)):
                break

        if mejor_copia is not None and (early_stopping or corte > 0):
            self._restaurar_parametros(mejor_copia)
        return list(self.perdidas_epocas)

    # -- evaluacion --------------------------------------------------------
    def loss(self, X: np.ndarray, y: np.ndarray) -> float:
        matriz, objetivo = _validar_datos(X, y, self.input_size, self.output_size)
        prediccion = np.asarray(self.forward(matriz), dtype=np.float64)
        return float(np.mean((prediccion - objetivo) ** 2))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.forward(X)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        matriz, objetivo = _validar_datos(X, y, self.input_size, self.output_size)
        prediccion = np.asarray(self.forward(matriz), dtype=np.float64)
        return _metricas_regresion(prediccion, objetivo)

    def params_count(self) -> int:
        try:
            return int(sum(np.asarray(v).size
                           for v in self._parametros_gradientes().values()))
        except Exception:  # pragma: no cover - subclase sin parametros
            return super().params_count()


# ---------------------------------------------------------------------------
# 1) Neurona Kolmogorov-Arnold (KAN)
# ---------------------------------------------------------------------------
class NeuronaKolmogorovArnold(NeuronaEntrenable):
    """KAN: una funcion aprendible por arista, como combinacion de bases RBF.

    Para cada caracteristica ``i`` y base ``k`` se aprende un coeficiente
    ``C[i, k, o]``; la salida es::

        y_o = sum_{i,k} phi_k(x_i) * C[i,k,o] + sum_i silu(x_i) * W_base[i,o] + b_o

    donde ``phi_k`` son gaussianas centradas en una rejilla por caracteristica
    (variante RBF de las B-splines de KAN). El gradiente es analitico.
    """

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaKolmogorovArnold",
                 n_bases: int = 5, seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre, seed)
        self.n_bases = max(3, int(n_bases))
        self.centros: Optional[np.ndarray] = None
        self.ancho: Optional[np.ndarray] = None
        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        generador = np.random.default_rng(self.seed + 1)
        escala_coeficientes = 1.0 / math.sqrt(max(1, self.input_size * self.n_bases))
        self.coeficientes = generador.normal(
            0.0, escala_coeficientes,
            (self.input_size, self.n_bases, self.output_size),
        )
        self.W_base = generador.normal(
            0.0, 1.0 / math.sqrt(max(1, self.input_size)),
            (self.input_size, self.output_size),
        )
        self.sesgo = np.zeros((self.output_size,), dtype=np.float64)
        self.centros = None
        self.ancho = None
        # Compatibilidad con la API de NeuronaMemoriaBase.
        self.pesos = self.coeficientes.reshape(
            self.input_size, self.n_bases * self.output_size
        )

    def _preparar_datos(self, X: np.ndarray) -> None:
        minimos = np.min(X, axis=0)
        maximos = np.max(X, axis=0)
        rango = np.maximum(maximos - minimos, 1e-6)
        posiciones = np.linspace(0.0, 1.0, self.n_bases)
        self.centros = (minimos - 0.05 * rango)[:, None] + (
            1.1 * rango
        )[:, None] * posiciones[None, :]
        self.ancho = np.maximum(rango / max(1, self.n_bases - 1), 1e-6)

    def _base_rbf(self, X: np.ndarray) -> np.ndarray:
        if self.centros is None or self.ancho is None:
            self._preparar_datos(X)
        diferencia = X[:, :, None] - self.centros[None, :, :]
        return np.exp(-0.5 * (diferencia / self.ancho[None, :, None]) ** 2)

    def _parametros_gradientes(self) -> Dict[str, np.ndarray]:
        return {
            'coeficientes': self.coeficientes,
            'W_base': self.W_base,
            'sesgo': self.sesgo,
        }

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        X, unico = _preparar_entrada(entrada, self.input_size)
        phi = self._base_rbf(X)
        salida = np.einsum('bfk,fko->bo', phi, self.coeficientes)
        salida = salida + _silu(X) @ self.W_base + self.sesgo
        self.registrar_activacion(salida)
        return salida[0] if unico else salida

    def _perdida_y_gradientes(self, X: np.ndarray,
                              Y: np.ndarray) -> Tuple[float, Dict[str, np.ndarray]]:
        phi = self._base_rbf(X)
        silu = _silu(X)
        prediccion = np.einsum('bfk,fko->bo', phi, self.coeficientes)
        prediccion = prediccion + silu @ self.W_base + self.sesgo
        error = prediccion - Y
        perdida = float(np.mean(error ** 2))
        gradiente = 2.0 * error / error.size
        gradientes = {
            'coeficientes': np.einsum('bfk,bo->fko', phi, gradiente),
            'W_base': silu.T @ gradiente,
            'sesgo': gradiente.sum(axis=0),
        }
        self.registrar_gradientes(gradientes)
        return perdida, gradientes

    def importancias(self) -> np.ndarray:
        return np.mean(np.abs(self.coeficientes), axis=(1, 2))

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'KAN',
            'n_bases': self.n_bases,
            'rejilla_ajustada': self.centros is not None,
            'importancias': self.importancias().round(6).tolist(),
        })
        return stats


# ---------------------------------------------------------------------------
# 2) Neurona de arbol de decision diferenciable (soft decision tree)
# ---------------------------------------------------------------------------
class NeuronaArbolDiferenciable(NeuronaEntrenable):
    """Arbol de decision suave entrenable por retropropagacion.

    Cada nodo interno tiene un hiperplano ``w_n . x + b_n`` y una compuerta
    ``sigmoid((w_n . x + b_n) / T)``; la probabilidad de una hoja es el
    producto de las compuertas de su camino. La prediccion es la mezcla de
    los valores de las hojas y la temperatura ``T`` decae durante el
    entrenamiento (annealing) para endurecer la particion.
    """

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaArbolDiferenciable",
                 profundidad: int = 3, temperatura: float = 1.0,
                 temperatura_minima: float = 0.1,
                 seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre, seed)
        self.profundidad = max(1, int(profundidad))
        self.n_internos = 2 ** self.profundidad - 1
        self.n_hojas = 2 ** self.profundidad
        self.temperatura_inicial = max(0.05, float(temperatura))
        self.temperatura_minima = max(0.01, float(temperatura_minima))
        self.temperatura = self.temperatura_inicial
        self._rutas = self._construir_rutas()
        self.inicializar_pesos()

    def _construir_rutas(self) -> List[List[Tuple[int, int]]]:
        rutas: List[List[Tuple[int, int]]] = []
        for hoja in range(self.n_hojas):
            nodo = 0
            ruta: List[Tuple[int, int]] = []
            for nivel in range(self.profundidad):
                direccion = (hoja >> (self.profundidad - 1 - nivel)) & 1
                ruta.append((nodo, direccion))
                nodo = 2 * nodo + 1 + direccion
            rutas.append(ruta)
        return rutas

    def inicializar_pesos(self) -> None:
        generador = np.random.default_rng(self.seed + 2)
        self.W = generador.normal(
            0.0, 1.0 / math.sqrt(max(1, self.input_size)),
            (self.n_internos, self.input_size),
        )
        self.b = np.zeros((self.n_internos,), dtype=np.float64)
        self.hojas = generador.normal(
            0.0, 0.1, (self.n_hojas, self.output_size)
        )
        self.temperatura = self.temperatura_inicial
        # Compatibilidad con la API de NeuronaMemoriaBase.
        self.pesos = self.W
        self.sesgo = self.b.reshape(1, -1)

    def _parametros_gradientes(self) -> Dict[str, np.ndarray]:
        return {'W': self.W, 'b': self.b, 'hojas': self.hojas}

    def _ajustar_temperatura(self, epoca: int, total_epocas: int) -> None:
        total = max(1, int(total_epocas) - 1)
        progreso = min(1.0, float(epoca) / total)
        factor = (self.temperatura_minima / self.temperatura_inicial) ** progreso
        self.temperatura = max(
            self.temperatura_minima,
            self.temperatura_inicial * factor,
        )

    def _forward_cache(self, X: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        temperatura = max(self.temperatura, 1e-3)
        z = (X @ self.W.T + self.b) / temperatura
        compuertas = np.clip(_sigmoide(z), 1e-6, 1.0 - 1e-6)
        probabilidades = np.ones((X.shape[0], self.n_hojas), dtype=np.float64)
        for indice_hoja, ruta in enumerate(self._rutas):
            for nodo, direccion in ruta:
                if direccion == 0:
                    probabilidades[:, indice_hoja] *= compuertas[:, nodo]
                else:
                    probabilidades[:, indice_hoja] *= (1.0 - compuertas[:, nodo])
        prediccion = probabilidades @ self.hojas
        cache = {
            'X': X,
            'compuertas': compuertas,
            'probabilidades': probabilidades,
            'temperatura': temperatura,
        }
        return prediccion, cache

    def _backward(self, cache: Dict[str, Any],
                  gradiente_prediccion: np.ndarray) -> Dict[str, np.ndarray]:
        X = cache['X']
        compuertas = cache['compuertas']
        probabilidades = cache['probabilidades']
        temperatura = cache['temperatura']

        grad_hojas = probabilidades.T @ gradiente_prediccion
        grad_probabilidades = gradiente_prediccion @ self.hojas.T
        coeficientes = np.zeros_like(compuertas)

        for indice_hoja, ruta in enumerate(self._rutas):
            factor = grad_probabilidades[:, indice_hoja] * probabilidades[:, indice_hoja]
            for nodo, direccion in ruta:
                if direccion == 0:
                    coeficientes[:, nodo] += factor / compuertas[:, nodo]
                else:
                    coeficientes[:, nodo] -= factor / (1.0 - compuertas[:, nodo])

        grad_z = coeficientes * compuertas * (1.0 - compuertas) / temperatura
        return {
            'W': grad_z.T @ X,
            'b': grad_z.sum(axis=0),
            'hojas': grad_hojas,
        }

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        X, unico = _preparar_entrada(entrada, self.input_size)
        prediccion, _ = self._forward_cache(X)
        self.registrar_activacion(prediccion)
        return prediccion[0] if unico else prediccion

    def _perdida_y_gradientes(self, X: np.ndarray,
                              Y: np.ndarray) -> Tuple[float, Dict[str, np.ndarray]]:
        prediccion, cache = self._forward_cache(X)
        error = prediccion - Y
        perdida = float(np.mean(error ** 2))
        gradiente = 2.0 * error / error.size
        gradientes = self._backward(cache, gradiente)
        self.registrar_gradientes(gradientes)
        return perdida, gradientes

    def probabilidades_hojas(self, X: np.ndarray) -> np.ndarray:
        matriz, _ = _preparar_entrada(X, self.input_size)
        _, cache = self._forward_cache(matriz)
        return cache['probabilidades']

    def importancias(self) -> np.ndarray:
        importancias = np.sum(np.abs(self.W), axis=0)
        total = float(np.sum(importancias))
        return importancias / total if total > 1e-12 else importancias

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'arbol_diferenciable',
            'profundidad': self.profundidad,
            'n_hojas': self.n_hojas,
            'temperatura': float(self.temperatura),
            'importancias': self.importancias().round(6).tolist(),
        })
        return stats


# ---------------------------------------------------------------------------
# 3) Neurona de atencion de caracteristicas (feature gating + MLP)
# ---------------------------------------------------------------------------
class NeuronaAtencionCaracteristicas(NeuronaEntrenable):
    """Compuerta de atencion por caracteristica con MLP y regularizacion L1.

    ``g = sigmoid(x * W_g + b_g)``; ``x_g = x * g``; luego un MLP de una capa
    oculta. La penalizacion L1 sobre ``g`` sesga hacia compuertas cerradas y
    produce importancias interpretables por caracteristica.
    """

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaAtencionCaracteristicas",
                 dim_oculta: Optional[int] = None, l1_gates: float = 0.0,
                 seed: Optional[int] = None) -> None:
        super().__init__(input_size, output_size, nombre, seed)
        self.dim_oculta = max(1, int(dim_oculta or max(8, 2 * self.input_size)))
        self.l1_gates = max(0.0, float(l1_gates))
        self.inicializar_pesos()

    def inicializar_pesos(self) -> None:
        generador = np.random.default_rng(self.seed + 3)
        self.W_g = generador.normal(0.0, 0.1, (self.input_size,))
        self.b_g = np.zeros((self.input_size,), dtype=np.float64)
        self.W1 = generador.normal(
            0.0, math.sqrt(2.0 / max(1, self.input_size)),
            (self.input_size, self.dim_oculta),
        )
        self.b1 = np.zeros((self.dim_oculta,), dtype=np.float64)
        self.W2 = generador.normal(
            0.0, math.sqrt(2.0 / max(1, self.dim_oculta)),
            (self.dim_oculta, self.output_size),
        )
        self.b2 = np.zeros((self.output_size,), dtype=np.float64)
        # Compatibilidad con la API de NeuronaMemoriaBase.
        self.pesos = self.W1
        self.sesgo = self.b2.reshape(1, -1)

    def _parametros_gradientes(self) -> Dict[str, np.ndarray]:
        return {
            'W_g': self.W_g,
            'b_g': self.b_g,
            'W1': self.W1,
            'b1': self.b1,
            'W2': self.W2,
            'b2': self.b2,
        }

    def _forward_cache(self, X: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        compuertas = _sigmoide(X * self.W_g + self.b_g)
        Xg = X * compuertas
        Z1 = Xg @ self.W1 + self.b1
        H1 = _relu(Z1)
        salida = H1 @ self.W2 + self.b2
        cache = {
            'X': X,
            'compuertas': compuertas,
            'Xg': Xg,
            'Z1': Z1,
            'H1': H1,
        }
        return salida, cache

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        X, unico = _preparar_entrada(entrada, self.input_size)
        salida, _ = self._forward_cache(X)
        self.registrar_activacion(salida)
        return salida[0] if unico else salida

    def _perdida_y_gradientes(self, X: np.ndarray,
                              Y: np.ndarray) -> Tuple[float, Dict[str, np.ndarray]]:
        salida, cache = self._forward_cache(X)
        error = salida - Y
        perdida = float(np.mean(error ** 2))
        if self.l1_gates > 0.0:
            perdida += self.l1_gates * float(np.mean(cache['compuertas']))
        gradiente = 2.0 * error / error.size

        grad_W2 = cache['H1'].T @ gradiente
        grad_b2 = gradiente.sum(axis=0)
        grad_H1 = gradiente @ self.W2.T
        grad_Z1 = grad_H1 * (cache['Z1'] > 0.0)
        grad_W1 = cache['Xg'].T @ grad_Z1
        grad_b1 = grad_Z1.sum(axis=0)
        grad_Xg = grad_Z1 @ self.W1.T

        compuertas = cache['compuertas']
        grad_compuertas = grad_Xg * cache['X']
        if self.l1_gates > 0.0:
            grad_compuertas = grad_compuertas + self.l1_gates / compuertas.size
        grad_logits = grad_compuertas * compuertas * (1.0 - compuertas)

        gradientes = {
            'W_g': np.sum(grad_logits * cache['X'], axis=0),
            'b_g': np.sum(grad_logits, axis=0),
            'W1': grad_W1,
            'b1': grad_b1,
            'W2': grad_W2,
            'b2': grad_b2,
        }
        self.registrar_gradientes(gradientes)
        return perdida, gradientes

    def compuertas(self, X: np.ndarray) -> np.ndarray:
        matriz, _ = _preparar_entrada(X, self.input_size)
        return _sigmoide(matriz * self.W_g + self.b_g)

    def importancias(self) -> np.ndarray:
        return np.abs(self.W_g)

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'atencion_caracteristicas',
            'dim_oculta': self.dim_oculta,
            'l1_gates': self.l1_gates,
            'importancias': self.importancias().round(6).tolist(),
        })
        return stats


# ---------------------------------------------------------------------------
# 4) Neurona de bosque (ensemble de arboles diferenciables)
# ---------------------------------------------------------------------------
class NeuronaBosqueNeuronal(NeuronaEntrenable):
    """Bosque de arboles diferenciables con mezcla aprendida (softmax).

    Cada arbol ve un subconjunto aleatorio de caracteristicas (estilo Random
    Forest). Las predicciones se combinan con pesos aprendidos por descenso de
    gradiente sobre los logits de la mezcla.
    """

    def __init__(self, input_size: int = 4, output_size: int = 1,
                 nombre: str = "NeuronaBosqueNeuronal", n_arboles: int = 5,
                 profundidad: int = 3, submuestreo_caracteristicas: float = 0.8,
                 seed: Optional[int] = None, **kwargs_arbol: Any) -> None:
        super().__init__(input_size, output_size, nombre, seed)
        self.n_arboles = max(1, int(n_arboles))
        self.profundidad = max(1, int(profundidad))
        self.submuestreo = min(
            1.0, max(1.0 / max(1, self.input_size),
                     float(submuestreo_caracteristicas)),
        )
        self._kwargs_arbol = dict(kwargs_arbol)
        self.mascaras: List[np.ndarray] = []
        self.arboles: List[NeuronaArbolDiferenciable] = []
        for indice in range(self.n_arboles):
            n_seleccion = (self.input_size if self.submuestreo >= 1.0
                           else max(1, int(round(self.submuestreo * self.input_size))))
            seleccion = np.sort(
                self.rng.choice(self.input_size, size=n_seleccion, replace=False)
            )
            mascara = np.zeros(self.input_size, dtype=bool)
            mascara[seleccion] = True
            self.mascaras.append(mascara)
            self.arboles.append(NeuronaArbolDiferenciable(
                input_size=n_seleccion,
                output_size=self.output_size,
                nombre=f"ArbolDiferenciable_{indice}",
                profundidad=self.profundidad,
                seed=self.seed + indice + 1,
                **self._kwargs_arbol,
            ))
        self.logits_mezcla = np.zeros((self.n_arboles,), dtype=np.float64)
        # Compatibilidad con la API de NeuronaMemoriaBase.
        self.pesos = self.logits_mezcla
        self.sesgo = None

    def _parametros_gradientes(self) -> Dict[str, np.ndarray]:
        return {'logits_mezcla': self.logits_mezcla}

    def _arreglos_parametros(self) -> List[np.ndarray]:
        arreglos: List[np.ndarray] = [self.logits_mezcla]
        for arbol in self.arboles:
            arreglos.extend(arbol._arreglos_parametros())
        return arreglos

    def pesos_mezcla(self) -> np.ndarray:
        return _softmax(self.logits_mezcla)

    def _predicciones_arboles(self, X: np.ndarray) -> np.ndarray:
        predicciones = [
            np.asarray(arbol.forward(X[:, mascara]), dtype=np.float64)
            for arbol, mascara in zip(self.arboles, self.mascaras)
        ]
        return np.stack(predicciones, axis=1)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        X, unico = _preparar_entrada(entrada, self.input_size)
        predicciones = self._predicciones_arboles(X)
        salida = np.tensordot(self.pesos_mezcla(), predicciones, axes=(0, 1))
        self.registrar_activacion(salida)
        return salida[0] if unico else salida

    def _entrenar_mezcla(self, X: np.ndarray, Y: np.ndarray,
                         epocas: int = 100, learning_rate: float = 0.05) -> List[float]:
        optimizador = OptimizadorAdam(
            self._parametros_gradientes(),
            learning_rate=learning_rate,
            max_norm=float(LUCIA_RF_CONFIG["max_norm"]),
        )
        historial: List[float] = []
        for _ in range(max(1, int(epocas))):
            predicciones = self._predicciones_arboles(X)
            pesos = self.pesos_mezcla()
            mezcla = np.tensordot(pesos, predicciones, axes=(0, 1))
            error = mezcla - Y
            perdida = float(np.mean(error ** 2))
            gradiente = 2.0 * error / error.size
            grad_logits = np.array([
                pesos[indice] * float(np.sum(gradiente * (predicciones[:, indice] - mezcla)))
                for indice in range(self.n_arboles)
            ], dtype=np.float64)
            optimizador.step({'logits_mezcla': grad_logits})
            historial.append(perdida)
            self.registrar_perdida(perdida)
        self.perdidas_epocas = historial
        return historial

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 100,
            learning_rate: float = 0.01, batch_size: int = 32,
            validation_split: float = 0.0, early_stopping: bool = False,
            patience: int = 15, weight_decay: float = 0.0,
            verbose: bool = False, shuffle: bool = True) -> List[float]:
        matriz, objetivo = _validar_datos(X, y, self.input_size, self.output_size)
        self._preparar_datos(matriz)
        for indice, (arbol, mascara) in enumerate(zip(self.arboles, self.mascaras)):
            arbol.fit(
                matriz[:, mascara], objetivo,
                epochs=epochs, learning_rate=learning_rate,
                batch_size=batch_size, validation_split=validation_split,
                early_stopping=early_stopping, patience=patience,
                weight_decay=weight_decay, verbose=False, shuffle=shuffle,
            )
            if verbose:
                logger.info("Bosque: arbol %d/%d entrenado", indice + 1, self.n_arboles)
        return self._entrenar_mezcla(
            matriz, objetivo,
            epocas=max(20, min(300, int(epochs))),
            learning_rate=max(1e-3, float(learning_rate) * 5.0),
        )

    def params_count(self) -> int:
        total = int(self.logits_mezcla.size)
        for arbol in self.arboles:
            total += arbol.params_count()
        return total

    def importancias(self) -> np.ndarray:
        importancias = np.zeros((self.input_size,), dtype=np.float64)
        for arbol, mascara in zip(self.arboles, self.mascaras):
            importancias[mascara] += arbol.importancias()
        total = float(np.sum(importancias))
        return importancias / total if total > 1e-12 else importancias

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats.update({
            'tipo': 'bosque_neuronal',
            'n_arboles': self.n_arboles,
            'profundidad': self.profundidad,
            'submuestreo': self.submuestreo,
            'pesos_mezcla': self.pesos_mezcla().round(6).tolist(),
            'importancias': self.importancias().round(6).tolist(),
        })
        return stats


# ---------------------------------------------------------------------------
# Fabrica, evaluacion y persistencia
# ---------------------------------------------------------------------------
_REGISTRO_NEURONAS: Dict[str, Callable[..., NeuronaEntrenable]] = {
    'kan': NeuronaKolmogorovArnold,
    'kolmogorov_arnold': NeuronaKolmogorovArnold,
    'arbol_diferenciable': NeuronaArbolDiferenciable,
    'soft_tree': NeuronaArbolDiferenciable,
    'atencion': NeuronaAtencionCaracteristicas,
    'atencion_caracteristicas': NeuronaAtencionCaracteristicas,
    'bosque': NeuronaBosqueNeuronal,
    'bosque_neuronal': NeuronaBosqueNeuronal,
}


def crear_neurona(tipo: str, input_size: int = 4, output_size: int = 1,
                  **kwargs: Any) -> NeuronaEntrenable:
    """Fabrica una neurona especializada por nombre."""
    clave = str(tipo or '').strip().lower()
    if clave not in _REGISTRO_NEURONAS:
        raise ValueError(
            f"Tipo de neurona desconocido: {tipo!r}. "
            f"Disponibles: {sorted(set(_REGISTRO_NEURONAS))}"
        )
    return _REGISTRO_NEURONAS[clave](
        input_size=input_size, output_size=output_size, **kwargs
    )


def tipos_disponibles() -> List[str]:
    return sorted(set(_REGISTRO_NEURONAS))


def entrenar_y_evaluar(neurona: NeuronaEntrenable, X: np.ndarray, y: np.ndarray,
                       epochs: int = 50, learning_rate: float = 0.01,
                       **kwargs: Any) -> Dict[str, Any]:
    """Entrena una neurona y devuelve historial y metricas."""
    historial = neurona.fit(
        X, y, epochs=epochs, learning_rate=learning_rate, **kwargs
    )
    metricas = neurona.evaluate(X, y)
    return {
        'neurona': neurona,
        'historial': historial,
        'perdida_final': float(historial[-1]) if historial else float('nan'),
        'metricas': metricas,
    }


def benchmark_neurona(neurona: NeuronaEntrenable, X: np.ndarray,
                      repeticiones: int = 5) -> Dict[str, float]:
    """Mide el coste de inferencia de la neurona."""
    tiempos: List[float] = []
    for _ in range(max(1, int(repeticiones))):
        inicio = time.perf_counter()
        neurona.forward(X)
        tiempos.append(time.perf_counter() - inicio)
    return {
        'avg_time': float(np.mean(tiempos)),
        'min_time': float(np.min(tiempos)),
        'max_time': float(np.max(tiempos)),
        'std_time': float(np.std(tiempos)),
        'n_runs': int(len(tiempos)),
    }


def guardar_neurona(neurona: NeuronaEntrenable, ruta: str) -> None:
    """Serializa la neurona completa con pickle."""
    with open(ruta, 'wb') as fichero:
        pickle.dump(neurona, fichero, protocol=pickle.HIGHEST_PROTOCOL)


def cargar_neurona(ruta: str) -> NeuronaEntrenable:
    """Carga una neurona serializada con ``guardar_neurona``."""
    with open(ruta, 'rb') as fichero:
        neurona = pickle.load(fichero)
    if not isinstance(neurona, NeuronaEntrenable):
        raise TypeError("El fichero no contiene una NeuronaEntrenable")
    return neurona


def demo() -> Dict[str, Any]:
    """Demostracion autocontenida (``python RF_SL_SNRTM__rfsl_base1.py``)."""
    generador = np.random.default_rng(2026)
    X = generador.uniform(-2.0, 2.0, size=(160, 3))
    y = (np.sin(X[:, 0]) + 0.5 * X[:, 1] ** 2 - 1.5 * X[:, 2]
         + 0.05 * generador.normal(size=(160,))).reshape(-1, 1)

    print("=" * 74)
    print("RF_SL_SNRTM__rfsl_base1 :: neuronas especializadas (v%s)" % __version__)
    print("Muestras:", X.shape[0], "| caracteristicas:", X.shape[1])
    print("=" * 74)

    resultados: Dict[str, Any] = {}
    configuraciones = [
        ('kan', {'n_bases': 5}, 60),
        ('arbol_diferenciable', {'profundidad': 3}, 40),
        ('atencion', {'l1_gates': 0.0}, 80),
        ('bosque', {'n_arboles': 4, 'profundidad': 3}, 30),
    ]
    for tipo, extra, epocas in configuraciones:
        neurona = crear_neurona(tipo, input_size=3, output_size=1, **extra)
        resultado = entrenar_y_evaluar(
            neurona, X, y, epochs=epocas, learning_rate=0.02,
            batch_size=32, shuffle=True,
        )
        resultados[tipo] = resultado
        metricas = resultado['metricas']
        print("%-22s MSE=%.6f MAE=%.6f R2=%.4f | params=%d"
              % (tipo, metricas['mse'], metricas['mae'],
                 metricas['r2'], neurona.params_count()))
        print("    estable:", neurona.verificar_estabilidad()['estable'],
              "| perdida final: %.6f" % resultado['perdida_final'])

    ejemplo = resultados['kan']['neurona']
    print("=" * 74)
    print("Importancias KAN:", np.round(ejemplo.importancias(), 4).tolist())
    print("Benchmark KAN:", benchmark_neurona(ejemplo, X, repeticiones=3))
    print("=" * 74)
    return resultados


__all__ = [
    'NeuronaMemoriaBase',
    'TreeBuilder',
    'NeuronaEntrenable',
    'NeuronaKolmogorovArnold',
    'NeuronaArbolDiferenciable',
    'NeuronaAtencionCaracteristicas',
    'NeuronaBosqueNeuronal',
    'OptimizadorAdam',
    'crear_neurona',
    'tipos_disponibles',
    'entrenar_y_evaluar',
    'benchmark_neurona',
    'guardar_neurona',
    'cargar_neurona',
    'demo',
    'LUCIA_RF_CONFIG',
]


if __name__ == "__main__":  # pragma: no cover
    demo()
