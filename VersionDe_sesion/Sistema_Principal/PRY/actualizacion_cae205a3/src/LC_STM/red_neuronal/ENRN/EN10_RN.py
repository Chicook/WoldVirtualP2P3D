"""
NeuronaEntradaSigmoid V2 â€” refactorizaciÃ³n compatible para lucIA.

Arquitectura conservada:
    entrada -> (adaptaciÃ³n opcional) -> proyecciÃ³n densa XW+b -> Sigmoid -> salida

CaracterÃ­sticas:
- NumPy como Ãºnica dependencia matemÃ¡tica.
- Mantiene NeuronaEntradaSigmoid y su interfaz pÃºblica principal.
- Carga pesos del formato JSON legado.
- NormalizaciÃ³n adaptativa affine opcional.
- Feature gating opcional.
- TransformaciÃ³n spline lineal por tramos opcional (misma dimensiÃ³n de entrada).
- SGD, Momentum, Adam y AdamW.
- BCE/MSE con derivadas coherentes.
- Historiales acotados, callbacks, mÃ©tricas y checkpoint versionado.
- No contiene un mÃ©todo llamado entrenar_paso.

Nota:
Las opciones adaptativas se pueden activar explÃ­citamente para preservar por defecto
el comportamiento de modelos antiguos. No se cambia la topologÃ­a densa de la neurona.
"""

from __future__ import annotations

import json
import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    from . import NeuronaEntradaBase, LUCIA_CONFIG
except (ImportError, ValueError):
    LUCIA_CONFIG = {
        "precision": "float32",
        "random_seed": 42,
        "default_learning_rate": 0.001,
    }

    class NeuronaEntradaBase:
        """Fallback autocontenido cuando el paquete anfitriÃ³n no estÃ¡ disponible."""

        def __init__(self, input_size: int, output_size: int,
                     nombre: str = "NeuronaEntrada"):
            self.input_size = int(input_size)
            self.output_size = int(output_size)
            self.nombre = nombre
            self.pesos = None
            self.sesgo = None
            self.historial_activaciones = []
            self.historial_gradientes = []
            self.llm_connector = None

        def inicializar_pesos(self) -> None:
            raise NotImplementedError

        def forward(self, entrada):
            raise NotImplementedError

        def backward(self, gradiente, entrada):
            raise NotImplementedError

        def obtener_estadisticas(self):
            return {
                "nombre": self.nombre,
                "input_size": self.input_size,
                "output_size": self.output_size,
                "activaciones": len(self.historial_activaciones),
            }

        def obtener_estadisticas_completas(self):
            return self.obtener_estadisticas()

        def verificar_estabilidad(self):
            return {"pesos_inicializados": self.pesos is not None}


# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------

_DTYPE_MAP = {
    "float16": np.float16,
    "float32": np.float32,
    "float64": np.float64,
}


def _dtype() -> np.dtype:
    nombre = str(LUCIA_CONFIG.get("precision", "float32")).lower()
    return np.dtype(_DTYPE_MAP.get(nombre, np.float32))


def _ahora() -> float:
    return time.perf_counter()


def _matriz(valor: Any, dtype=np.float64) -> np.ndarray:
    """Convierte vectores/matrices a matriz 2D y rechaza dimensiones invÃ¡lidas."""
    arr = np.asarray(valor, dtype=dtype)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2:
        raise ValueError("Se esperaba una entrada vectorial o matricial 2D.")
    if not np.isfinite(arr).all():
        raise ValueError("La entrada contiene NaN o valores infinitos.")
    return arr


class RingBuffer:
    """Historial FIFO de capacidad fija."""

    def __init__(self, capacidad: int = 256):
        if int(capacidad) < 1:
            raise ValueError("La capacidad del historial debe ser >= 1.")
        self.capacidad = int(capacidad)
        self._datos: List[Any] = []

    def append(self, elemento: Any) -> None:
        self._datos.append(elemento)
        exceso = len(self._datos) - self.capacidad
        if exceso > 0:
            del self._datos[:exceso]

    def __len__(self) -> int:
        return len(self._datos)

    def __bool__(self) -> bool:
        return bool(self._datos)

    def ultimo(self) -> Any:
        return self._datos[-1] if self._datos else None

    def to_list(self) -> List[Any]:
        return list(self._datos)

    def clear(self) -> None:
        self._datos.clear()


# ---------------------------------------------------------------------------
# AdaptaciÃ³n de entrada: normalizaciÃ³n aprendible inspirada en EDAIN
# ---------------------------------------------------------------------------

class NormalizadorAdaptativo:
    """
    NormalizaciÃ³n por caracterÃ­stica con estadÃ­sticas mÃ³viles y transformaciÃ³n
    affine aprendible. Mantiene la dimensiÃ³n de entrada.
    """

    def __init__(self, dimensiones: int, momentum: float = 0.05,
                 epsilon: float = 1e-5):
        self.dimensiones = int(dimensiones)
        self.momentum = float(momentum)
        self.epsilon = float(epsilon)
        self.media = np.zeros((1, self.dimensiones), dtype=np.float64)
        self.varianza = np.ones((1, self.dimensiones), dtype=np.float64)
        self.escala = np.ones((1, self.dimensiones), dtype=np.float64)
        self.desplazamiento = np.zeros((1, self.dimensiones), dtype=np.float64)
        self.inicializado = False

    def forward(self, x: np.ndarray, actualizar_stats: bool = False):
        x = np.asarray(x, dtype=np.float64)
        if x.shape[1] != self.dimensiones:
            raise ValueError("DimensiÃ³n incompatible con el normalizador.")

        if actualizar_stats and x.shape[0] > 1:
            media_lote = np.mean(x, axis=0, keepdims=True)
            var_lote = np.var(x, axis=0, keepdims=True)
            if not self.inicializado:
                self.media = media_lote.copy()
                self.varianza = np.maximum(var_lote, self.epsilon)
                self.inicializado = True
            else:
                m = self.momentum
                self.media = (1.0 - m) * self.media + m * media_lote
                self.varianza = (1.0 - m) * self.varianza + m * var_lote

        z = (x - self.media) / np.sqrt(self.varianza + self.epsilon)
        salida = z * self.escala + self.desplazamiento
        cache = {"z": z}
        return salida, cache

    def backward(self, grad_salida: np.ndarray, cache: Dict[str, np.ndarray]):
        z = cache["z"]
        grad_escala = np.sum(grad_salida * z, axis=0, keepdims=True)
        grad_desplazamiento = np.sum(grad_salida, axis=0, keepdims=True)
        grad_entrada = (
            grad_salida * self.escala /
            np.sqrt(self.varianza + self.epsilon)
        )
        return grad_entrada, {
            "norm_escala": grad_escala,
            "norm_desplazamiento": grad_desplazamiento,
        }

    def estado(self) -> Dict[str, Any]:
        return {
            "media": self.media.tolist(),
            "varianza": self.varianza.tolist(),
            "escala": self.escala.tolist(),
            "desplazamiento": self.desplazamiento.tolist(),
            "inicializado": self.inicializado,
        }

    def cargar_estado(self, estado: Dict[str, Any]) -> None:
        for clave in ("media", "varianza", "escala", "desplazamiento"):
            if clave in estado:
                valor = np.asarray(estado[clave], dtype=np.float64)
                if valor.shape != (1, self.dimensiones):
                    raise ValueError(f"Forma invÃ¡lida en normalizador: {clave}")
                setattr(self, clave, valor)
        self.inicializado = bool(estado.get("inicializado", True))


# ---------------------------------------------------------------------------
# PonderaciÃ³n dinÃ¡mica de caracterÃ­sticas
# ---------------------------------------------------------------------------

class CompuertaCaracteristicas:
    """Gate sigmoidal por caracterÃ­stica; no altera la dimensiÃ³n del vector."""

    def __init__(self, dimensiones: int):
        self.logits = np.zeros((1, int(dimensiones)), dtype=np.float64)

    def forward(self, x: np.ndarray):
        gate = 1.0 / (1.0 + np.exp(-np.clip(self.logits, -30.0, 30.0)))
        return x * gate, {"entrada": x, "gate": gate}

    def backward(self, grad_salida: np.ndarray, cache: Dict[str, np.ndarray]):
        gate = cache["gate"]
        x = cache["entrada"]
        grad_logits = np.sum(
            grad_salida * x * gate * (1.0 - gate),
            axis=0,
            keepdims=True,
        )
        return grad_salida * gate, {"gate_logits": grad_logits}


# ---------------------------------------------------------------------------
# TransformaciÃ³n spline opcional, lineal por tramos
# ---------------------------------------------------------------------------

class TransformadorSpline:
    """
    TransformaciÃ³n unidimensional por caracterÃ­stica, lineal por tramos.
    Cada caracterÃ­stica conserva su posiciÃ³n y la dimensiÃ³n total no cambia.
    Es una aproximaciÃ³n ligera y opcional a una transformaciÃ³n basada en splines;
    no implementa una capa KAN ni una expansiÃ³n de la matriz neuronal.
    """

    def __init__(self, dimensiones: int, n_nudos: int = 8,
                 minimo: float = -3.0, maximo: float = 3.0):
        if n_nudos < 2 or minimo >= maximo:
            raise ValueError("ConfiguraciÃ³n spline invÃ¡lida.")
        self.dimensiones = int(dimensiones)
        self.n_nudos = int(n_nudos)
        self.minimo = float(minimo)
        self.maximo = float(maximo)
        self.nudos = np.linspace(minimo, maximo, n_nudos, dtype=np.float64)
        # Identidad inicial: la transformaciÃ³n comienza aproximadamente neutra.
        self.valores = np.tile(self.nudos, (self.dimensiones, 1))
        self._pendiente_extremos = True

    def forward(self, x: np.ndarray):
        x = np.asarray(x, dtype=np.float64)
        salida = np.empty_like(x)
        indices = np.empty(x.shape, dtype=np.int64)
        fracciones = np.empty_like(x)
        pendientes = np.empty_like(x)

        for j in range(self.dimensiones):
            idx = np.searchsorted(self.nudos, x[:, j], side="right") - 1
            idx = np.clip(idx, 0, self.n_nudos - 2)
            x0 = self.nudos[idx]
            x1 = self.nudos[idx + 1]
            y0 = self.valores[j, idx]
            y1 = self.valores[j, idx + 1]
            t = np.clip((x[:, j] - x0) / (x1 - x0), 0.0, 1.0)
            pendiente = (y1 - y0) / (x1 - x0)
            salida[:, j] = y0 + t * (y1 - y0)
            indices[:, j] = idx
            fracciones[:, j] = t
            pendientes[:, j] = pendiente

        return salida, {
            "indices": indices,
            "fracciones": fracciones,
            "pendientes": pendientes,
        }

    def backward(self, grad_salida: np.ndarray, cache: Dict[str, np.ndarray]):
        grad_entrada = grad_salida * cache["pendientes"]
        grad_valores = np.zeros_like(self.valores)
        idx = cache["indices"]
        t = cache["fracciones"]

        for j in range(self.dimensiones):
            np.add.at(grad_valores[j], idx[:, j],
                      grad_salida[:, j] * (1.0 - t[:, j]))
            np.add.at(grad_valores[j], idx[:, j] + 1,
                      grad_salida[:, j] * t[:, j])

        return grad_entrada, {"spline_valores": grad_valores}

    def estado(self) -> Dict[str, Any]:
        return {"valores": self.valores.tolist()}

    def cargar_estado(self, estado: Dict[str, Any]) -> None:
        valores = np.asarray(estado["valores"], dtype=np.float64)
        if valores.shape != self.valores.shape:
            raise ValueError("Forma incompatible para parÃ¡metros spline.")
        self.valores = valores


# ---------------------------------------------------------------------------
# Motor de optimizaciÃ³n independiente de la neurona
# ---------------------------------------------------------------------------

class MotorOptimizacion:
    """SGD, Momentum, Adam y AdamW con estados independientes por parÃ¡metro."""

    VALIDOS = {"sgd", "momentum", "sgd_momentum", "adam", "adamw"}

    def __init__(self, nombre: str = "adam", beta1: float = 0.9,
                 beta2: float = 0.999, epsilon: float = 1e-8,
                 weight_decay: float = 0.0):
        nombre = str(nombre).lower()
        if nombre not in self.VALIDOS:
            raise ValueError(
                f"Optimizador '{nombre}' no vÃ¡lido. Opciones: {sorted(self.VALIDOS)}"
            )
        if not (0.0 <= beta1 < 1.0 and 0.0 <= beta2 < 1.0):
            raise ValueError("beta1 y beta2 deben estar en [0, 1).")
        if epsilon <= 0 or weight_decay < 0:
            raise ValueError("epsilon debe ser positivo y weight_decay no negativo.")
        self.nombre = nombre
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.weight_decay = float(weight_decay)
        self.paso = 0
        self.m: Dict[str, np.ndarray] = {}
        self.v: Dict[str, np.ndarray] = {}

    def actualizar(self, parametros: Dict[str, np.ndarray],
                   gradientes: Dict[str, np.ndarray], lr: float) -> None:
        self.paso += 1
        for nombre, parametro in parametros.items():
            grad = np.asarray(gradientes[nombre], dtype=np.float64)
            if grad.shape != parametro.shape:
                raise ValueError(f"Gradiente con forma incorrecta: {nombre}")
            if not np.isfinite(grad).all():
                raise FloatingPointError(f"Gradiente no finito: {nombre}")

            p = parametro.astype(np.float64)
            if self.nombre == "sgd":
                nuevo = p - lr * grad
            else:
                if nombre not in self.m:
                    self.m[nombre] = np.zeros_like(p)
                    self.v[nombre] = np.zeros_like(p)

                self.m[nombre] = (
                    self.beta1 * self.m[nombre] + (1.0 - self.beta1) * grad
                )

                if self.nombre in {"momentum", "sgd_momentum"}:
                    nuevo = p - lr * self.m[nombre]
                else:
                    self.v[nombre] = (
                        self.beta2 * self.v[nombre] +
                        (1.0 - self.beta2) * (grad * grad)
                    )
                    m_hat = self.m[nombre] / (1.0 - self.beta1 ** self.paso)
                    v_hat = self.v[nombre] / (1.0 - self.beta2 ** self.paso)
                    nuevo = p - lr * m_hat / (np.sqrt(v_hat) + self.epsilon)

            if self.nombre == "adamw" and self.weight_decay > 0:
                # Decaimiento desacoplado: no contamina los momentos.
                if nombre in {"pesos", "spline_valores"}:
                    nuevo = nuevo - lr * self.weight_decay * p

            if not np.isfinite(nuevo).all():
                raise FloatingPointError(f"ParÃ¡metro no finito tras actualizar: {nombre}")
            parametro[...] = nuevo.astype(parametro.dtype, copy=False)

    def estado(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "beta1": self.beta1,
            "beta2": self.beta2,
            "epsilon": self.epsilon,
            "weight_decay": self.weight_decay,
            "paso": self.paso,
            "m": {k: v.tolist() for k, v in self.m.items()},
            "v": {k: v.tolist() for k, v in self.v.items()},
        }

    def cargar_estado(self, estado: Dict[str, Any]) -> None:
        if estado.get("nombre", self.nombre) != self.nombre:
            raise ValueError("El optimizador del checkpoint no coincide.")
        self.paso = int(estado.get("paso", 0))
        self.m = {k: np.asarray(v, dtype=np.float64)
                  for k, v in estado.get("m", {}).items()}
        self.v = {k: np.asarray(v, dtype=np.float64)
                  for k, v in estado.get("v", {}).items()}


# ---------------------------------------------------------------------------
# Neurona principal: topologÃ­a densa + Sigmoid conservada
# ---------------------------------------------------------------------------

class NeuronaEntradaSigmoid(NeuronaEntradaBase):
    """Neurona de entrada densa con activaciÃ³n Sigmoid y adaptaciÃ³n opcional."""

    VERSION_FORMATO = 2

    def __init__(
        self,
        input_size: int,
        output_size: int,
        nombre: str = "NeuronaEntradaSigmoid",
        factor_escala: float = 1.0,
        umbral_sat_lo: float = 0.05,
        umbral_sat_hi: float = 0.95,
        fraccion_sat: float = 0.1,
        learning_rate: float = 0.001,
        optimizador: str = "adam",
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
        weight_decay: float = 0.0,
        grad_clip: float = 5.0,
        lr_decay: float = 0.0,
        lr_min: float = 1e-6,
        usar_cache_forward: bool = True,
        semilla: Optional[int] = None,
        capacidad_historial: int = 256,
        usar_normalizacion_adaptativa: bool = False,
        usar_feature_gating: bool = False,
        usar_spline: bool = False,
        spline_n_nudos: int = 8,
        momentum_normalizador: float = 0.05,
    ):
        if int(input_size) < 1 or int(output_size) < 1:
            raise ValueError("input_size y output_size deben ser positivos.")
        if not (0.0 <= umbral_sat_lo < umbral_sat_hi <= 1.0):
            raise ValueError("Umbrales de saturaciÃ³n invÃ¡lidos.")
        if not (0.0 <= fraccion_sat <= 1.0):
            raise ValueError("fraccion_sat debe estar entre 0 y 1.")
        if learning_rate <= 0 or lr_min <= 0 or grad_clip < 0:
            raise ValueError("Tasas de aprendizaje y grad_clip invÃ¡lidos.")

        super().__init__(int(input_size), int(output_size), nombre)
        self.factor_escala = float(factor_escala)
        self.umbral_sat_lo = float(umbral_sat_lo)
        self.umbral_sat_hi = float(umbral_sat_hi)
        self.fraccion_sat = float(fraccion_sat)

        self.lr_base = float(learning_rate or LUCIA_CONFIG.get(
            "default_learning_rate", 0.001
        ))
        self.lr_actual = self.lr_base
        self.lr_decay = float(lr_decay)
        self.lr_min = float(lr_min)
        self.grad_clip = float(grad_clip)
        self.weight_decay = float(weight_decay)
        self.usar_cache_forward = bool(usar_cache_forward)

        self.semilla = int(
            semilla if semilla is not None
            else LUCIA_CONFIG.get("random_seed", 42)
        )
        self.rng = np.random.default_rng(self.semilla)

        self.optimizador = str(optimizador).lower()
        self.motor_optimizacion = MotorOptimizacion(
            self.optimizador, beta1, beta2, epsilon, weight_decay
        )

        self.usar_normalizacion_adaptativa = bool(usar_normalizacion_adaptativa)
        self.usar_feature_gating = bool(usar_feature_gating)
        self.usar_spline = bool(usar_spline)

        self.normalizador = NormalizadorAdaptativo(
            self.input_size, momentum=momentum_normalizador
        )
        self.comp_puerta = (
            CompuertaCaracteristicas(self.input_size)
            if self.usar_feature_gating else None
        )
        self.transformador_spline = (
            TransformadorSpline(self.input_size, n_nudos=spline_n_nudos)
            if self.usar_spline else None
        )

        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self._cache: Dict[str, Any] = {}
        self.historial_activaciones = RingBuffer(capacidad_historial)
        self.historial_gradientes = RingBuffer(capacidad_historial)
        self.historial_loss = RingBuffer(capacidad_historial)
        self.historial_lr = RingBuffer(capacidad_historial)

        self.varianza_real = 0.0
        self.saturacion = False
        self.ratio_sat = 0.0
        self.mejor_loss = float("inf")
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._ultimo_lote_entrenamiento = False

    # -------------------------- InicializaciÃ³n --------------------------

    def inicializar_pesos(self, modo: str = "xavier") -> None:
        modo = str(modo).lower()
        dt = _dtype()
        if modo == "xavier":
            limite = math.sqrt(6.0 / (self.input_size + self.output_size))
            limite *= self.factor_escala
            self.pesos = self.rng.uniform(
                -limite, limite, (self.input_size, self.output_size)
            ).astype(dt)
        elif modo == "he":
            std = math.sqrt(2.0 / self.input_size) * self.factor_escala
            self.pesos = self.rng.normal(
                0.0, std, (self.input_size, self.output_size)
            ).astype(dt)
        else:
            raise ValueError(f"Modo de inicializaciÃ³n desconocido: {modo}")

        self.sesgo = np.zeros((1, self.output_size), dtype=dt)
        self.varianza_real = float(np.var(self.pesos))
        self.motor_optimizacion = MotorOptimizacion(
            self.optimizador,
            self.motor_optimizacion.beta1,
            self.motor_optimizacion.beta2,
            self.motor_optimizacion.epsilon,
            self.weight_decay,
        )
        self._cache.clear()
        self._emitir("inicializacion", {"modo": modo})

    def _asegurar_pesos(self) -> None:
        if self.pesos is None or self.sesgo is None:
            self.inicializar_pesos()

    # -------------------------- Entrada y activaciÃ³n -------------------

    def _preparar(self, entrada: Any) -> np.ndarray:
        x = _matriz(entrada, dtype=_dtype())
        if x.shape[1] != self.input_size:
            raise ValueError(
                f"DimensiÃ³n de entrada {x.shape[1]} != input_size {self.input_size}"
            )
        return np.ascontiguousarray(x, dtype=_dtype())

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        # ImplementaciÃ³n estable por ramas para evitar overflow.
        x64 = np.asarray(x, dtype=np.float64)
        salida = np.empty_like(x64)
        positivos = x64 >= 0
        salida[positivos] = 1.0 / (1.0 + np.exp(-x64[positivos]))
        exp_x = np.exp(x64[~positivos])
        salida[~positivos] = exp_x / (1.0 + exp_x)
        return salida.astype(_dtype())

    def procesar_entrada(self, entrada: Any,
                         actualizar_estadisticas: bool = False) -> np.ndarray:
        """Interfaz descriptiva equivalente al forward pÃºblico."""
        return self.forward(
            entrada, actualizar_estadisticas=actualizar_estadisticas
        )

    def forward(self, entrada: Any,
                actualizar_estadisticas: bool = False) -> np.ndarray:
        t0 = _ahora()
        self._asegurar_pesos()
        x_original = self._preparar(entrada).astype(np.float64)
        x = x_original
        cache: Dict[str, Any] = {"x_original": x_original}

        if self.usar_normalizacion_adaptativa:
            x, cache["normalizador"] = self.normalizador.forward(
                x, actualizar_stats=actualizar_estadisticas
            )
        if self.transformador_spline is not None:
            x, cache["spline"] = self.transformador_spline.forward(x)
        if self.comp_puerta is not None:
            x, cache["gate"] = self.comp_puerta.forward(x)

        z = np.dot(x, self.pesos.astype(np.float64)) + self.sesgo.astype(np.float64)
        salida = self._sigmoid(z)
        salida = np.ascontiguousarray(salida, dtype=_dtype())

        ratio = float(np.mean(
            (salida < self.umbral_sat_lo) | (salida > self.umbral_sat_hi)
        )) if salida.size else 0.0
        self.ratio_sat = (
            0.9 * self.ratio_sat + 0.1 * ratio
            if self.contador_forward else ratio
        )
        self.saturacion = bool(self.ratio_sat > self.fraccion_sat)
        var_salida = float(np.var(salida)) if salida.size else 0.0
        self.varianza_real = (
            0.9 * self.varianza_real + 0.1 * var_salida
            if self.contador_forward else var_salida
        )

        cache.update({"x_proyectada": x, "z": z, "salida": salida})
        if self.usar_cache_forward:
            self._cache = cache

        self.historial_activaciones.append(salida.copy())
        self.contador_forward += 1
        self.tiempo_forward_acum += _ahora() - t0
        return salida

    def forward_batch(self, lote: Any) -> np.ndarray:
        """Procesa un lote en una sola operaciÃ³n vectorizada."""
        return self.forward(lote)

    # -------------------------- RetropropagaciÃ³n -----------------------

    def calcular_gradientes(self, gradiente_salida: Any,
                            entrada: Optional[Any] = None,
                            cache: Optional[Dict[str, Any]] = None):
        """Calcula gradientes sin actualizar parÃ¡metros; devuelve gradientes y dL/dx."""
        t0 = _ahora()
        self._asegurar_pesos()
        c = cache if cache is not None else self._cache
        if not c:
            raise RuntimeError(
                "No existe cachÃ© de forward. Ejecuta forward antes de backward."
            )

        g = _matriz(gradiente_salida, dtype=np.float64)
        salida = np.asarray(c["salida"], dtype=np.float64)
        if g.shape != salida.shape:
            raise ValueError(
                f"Gradiente de salida {g.shape} incompatible con salida {salida.shape}"
            )

        # El gradiente recibido es dL/d(salida); aquÃ­ se aplica la derivada Sigmoid.
        delta = g * salida * (1.0 - salida)
        x = np.asarray(c["x_proyectada"], dtype=np.float64)
        n = max(1, x.shape[0])
        grad_pesos = np.dot(x.T, delta) / n
        grad_sesgo = np.sum(delta, axis=0, keepdims=True) / n

        grad_x = np.dot(delta, self.pesos.astype(np.float64).T)
        grads_extra: Dict[str, np.ndarray] = {}

        if self.comp_puerta is not None and "gate" in c:
            grad_x, extra = self.comp_puerta.backward(grad_x, c["gate"])
            grads_extra.update(extra)
        if self.transformador_spline is not None and "spline" in c:
            grad_x, extra = self.transformador_spline.backward(
                grad_x, c["spline"]
            )
            grads_extra.update(extra)
        if self.usar_normalizacion_adaptativa and "normalizador" in c:
            grad_x, extra = self.normalizador.backward(
                grad_x, c["normalizador"]
            )
            grads_extra.update(extra)

        gradientes = {
            "pesos": grad_pesos,
            "sesgo": grad_sesgo,
            **{k: v / n for k, v in grads_extra.items()},
        }
        if self.grad_clip > 0:
            norma = math.sqrt(sum(float(np.sum(v * v)) for v in gradientes.values()))
            if norma > self.grad_clip:
                factor = self.grad_clip / (norma + 1e-12)
                gradientes = {k: v * factor for k, v in gradientes.items()}

        self.historial_gradientes.append({
            k: np.asarray(v).copy() for k, v in gradientes.items()
        })
        self.contador_backward += 1
        self.tiempo_backward_acum += _ahora() - t0
        return gradientes, grad_x

    def backward(self, gradiente_salida: Any,
                 entrada: Optional[Any] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Compatibilidad con la interfaz antigua: devuelve grad_pesos, grad_sesgo."""
        if entrada is not None:
            # Se reconstruye un forward explÃ­cito para garantizar que la cachÃ©
            # corresponde a la entrada entregada, sin recuperar activaciones antiguas.
            self.forward(entrada)
        gradientes, _ = self.calcular_gradientes(gradiente_salida)
        return (
            np.asarray(gradientes["pesos"], dtype=_dtype()),
            np.asarray(gradientes["sesgo"], dtype=_dtype()),
        )

    def grad_entrada(self, gradiente_salida: Any) -> np.ndarray:
        """Gradiente respecto a la entrada original, usando la cachÃ© mÃ¡s reciente."""
        _, grad_x = self.calcular_gradientes(gradiente_salida)
        return np.asarray(grad_x, dtype=_dtype())

    # -------------------------- OptimizaciÃ³n ---------------------------

    def _parametros_entrenables(self) -> Dict[str, np.ndarray]:
        self._asegurar_pesos()
        parametros = {"pesos": self.pesos, "sesgo": self.sesgo}
        if self.usar_normalizacion_adaptativa:
            parametros["norm_escala"] = self.normalizador.escala
            parametros["norm_desplazamiento"] = self.normalizador.desplazamiento
        if self.comp_puerta is not None:
            parametros["gate_logits"] = self.comp_puerta.logits
        if self.transformador_spline is not None:
            parametros["spline_valores"] = self.transformador_spline.valores
        return parametros

    def aplicar_optimizacion(self, gradientes: Dict[str, np.ndarray]) -> Dict[str, float]:
        """Actualiza parÃ¡metros mediante el optimizador configurado."""
        if self.lr_decay > 0:
            self.lr_actual = max(
                self.lr_min,
                self.lr_base / (1.0 + self.lr_decay *
                                (self.motor_optimizacion.paso + 1))
            )
        parametros = self._parametros_entrenables()
        faltantes = set(parametros) - set(gradientes)
        if faltantes:
            raise ValueError(f"Faltan gradientes para: {sorted(faltantes)}")
        grads = {k: np.asarray(gradientes[k], dtype=np.float64)
                 for k in parametros}
        if self.weight_decay > 0 and self.optimizador != "adamw":
            # RegularizaciÃ³n L2 acoplada para SGD/Momentum/Adam.
            grads["pesos"] = grads["pesos"] + self.weight_decay * self.pesos
        self.motor_optimizacion.actualizar(parametros, grads, self.lr_actual)
        self.historial_lr.append(self.lr_actual)
        info = {
            "lr": float(self.lr_actual),
            "paso": float(self.motor_optimizacion.paso),
        }
        self._emitir("optimizacion", info)
        return info

    def evaluar_y_ajustar(self, entrada: Any, objetivo: Any,
                          funcion_perdida: str = "mse") -> Dict[str, float]:
        """EvalÃºa un lote, calcula gradientes y aplica una actualizaciÃ³n."""
        perdida_tipo = str(funcion_perdida).lower()
        if perdida_tipo not in {"mse", "bce"}:
            raise ValueError("funcion_perdida debe ser 'mse' o 'bce'.")

        pred = self.forward(entrada, actualizar_estadisticas=True).astype(np.float64)
        y = _matriz(objetivo, dtype=np.float64)
        if y.shape != pred.shape:
            raise ValueError(f"Objetivo {y.shape} incompatible con salida {pred.shape}")
        if np.any(y < 0) or np.any(y > 1):
            raise ValueError("Los objetivos sigmoidales deben estar en [0, 1].")

        eps = 1e-7
        p = np.clip(pred, eps, 1.0 - eps)
        if perdida_tipo == "bce":
            loss = float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))
            # Para BCE + sigmoid: dL/dz = (p-y)/N.
            # Se evita aplicar otra vez sigmoid'(z) en calcular_gradientes.
            grad_logits = (p - y) / max(1, p.shape[1])
            gradientes = self._gradientes_desde_delta(grad_logits)
        else:
            loss = float(np.mean((pred - y) ** 2))
            grad_salida = 2.0 * (pred - y) / max(1, pred.shape[1])
            gradientes, _ = self.calcular_gradientes(grad_salida)

        info_opt = self.aplicar_optimizacion(gradientes)
        self.historial_loss.append(loss)
        self.mejor_loss = min(self.mejor_loss, loss)
        return {"loss": loss, **info_opt}

    def _gradientes_desde_delta(self, delta: np.ndarray):
        """Ruta BCE estable: recibe directamente dL/dz, sin derivar Sigmoid otra vez."""
        c = self._cache
        x = np.asarray(c["x_proyectada"], dtype=np.float64)
        n = max(1, x.shape[0])
        grad_pesos = np.dot(x.T, delta)
        grad_sesgo = np.sum(delta, axis=0, keepdims=True)
        grad_x = np.dot(delta, self.pesos.astype(np.float64).T)
        extra: Dict[str, np.ndarray] = {}

        if self.comp_puerta is not None and "gate" in c:
            grad_x, g = self.comp_puerta.backward(grad_x, c["gate"])
            extra.update(g)
        if self.transformador_spline is not None and "spline" in c:
            grad_x, g = self.transformador_spline.backward(grad_x, c["spline"])
            extra.update(g)
        if self.usar_normalizacion_adaptativa and "normalizador" in c:
            grad_x, g = self.normalizador.backward(grad_x, c["normalizador"])
            extra.update(g)

        grads = {
            "pesos": grad_pesos / n,
            "sesgo": grad_sesgo / n,
            **{k: v / n for k, v in extra.items()},
        }
        if self.grad_clip > 0:
            norma = math.sqrt(sum(float(np.sum(v * v)) for v in grads.values()))
            if norma > self.grad_clip:
                factor = self.grad_clip / (norma + 1e-12)
                grads = {k: v * factor for k, v in grads.items()}
        self.historial_gradientes.append({
            k: np.asarray(v).copy() for k, v in grads.items()
        })
        self.contador_backward += 1
        return grads

    # -------------------------- SupervisiÃ³n ----------------------------

    def corregir_saturacion(self, factor: float = 0.9) -> bool:
        """IntervenciÃ³n explÃ­cita y conservadora; no se ejecuta automÃ¡ticamente."""
        if not (0.0 < factor < 1.0):
            raise ValueError("factor debe estar entre 0 y 1.")
        if self.pesos is not None and self.saturacion:
            self.pesos[...] = (self.pesos.astype(np.float64) * factor).astype(
                self.pesos.dtype
            )
            return True
        return False

    def registrar_callback(self, funcion: Callable[[str, Dict[str, Any]], None]):
        if not callable(funcion):
            raise TypeError("El callback debe ser invocable.")
        self.callbacks.append(funcion)

    def _emitir(self, evento: str, info: Optional[Dict[str, Any]] = None):
        for callback in tuple(self.callbacks):
            try:
                callback(evento, dict(info or {}))
            except Exception:
                # Un callback externo no debe interrumpir el cÃ¡lculo neuronal.
                continue

    def obtener_estadisticas(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "activaciones": len(self.historial_activaciones),
            "forwards": self.contador_forward,
            "backwards": self.contador_backward,
            "lr_actual": self.lr_actual,
            "paso": self.motor_optimizacion.paso,
            "optimizador": self.optimizador,
            "normalizacion_adaptativa": self.usar_normalizacion_adaptativa,
            "feature_gating": self.usar_feature_gating,
            "spline": self.usar_spline,
        }

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        stats = self.obtener_estadisticas()
        stats.update({
            "varianza_real": self.varianza_real,
            "saturacion": self.saturacion,
            "ratio_sat": self.ratio_sat,
            "mejor_loss": self.mejor_loss,
            "ultima_loss": self.historial_loss.ultimo(),
            "t_medio_forward_ms": (
                self.tiempo_forward_acum / max(1, self.contador_forward)
            ) * 1000.0,
            "t_medio_backward_ms": (
                self.tiempo_backward_acum / max(1, self.contador_backward)
            ) * 1000.0,
        })
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        resultado = {
            "pesos_inicializados": self.pesos is not None,
            "sesgo_inicializado": self.sesgo is not None,
            "sin_saturacion": not self.saturacion,
        }
        if self.pesos is not None:
            resultado.update({
                "pesos_finitos": bool(np.isfinite(self.pesos).all()),
                "sesgo_finito": bool(
                    self.sesgo is not None and np.isfinite(self.sesgo).all()
                ),
                "pesos_no_explosivos": bool(
                    np.max(np.abs(self.pesos)) < 3.0
                ),
            })
        if self.historial_loss:
            resultado["perdida_finita"] = bool(
                np.isfinite(self.historial_loss.ultimo())
            )
        return resultado

    def resumen_rendimiento(self) -> Dict[str, float]:
        return {
            "forwards": self.contador_forward,
            "backwards": self.contador_backward,
            "t_forward_total_s": self.tiempo_forward_acum,
            "t_backward_total_s": self.tiempo_backward_acum,
        }

    def reiniciar_metricas(self) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.historial_loss.clear()
        self.historial_lr.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0

    # -------------------------- Persistencia ---------------------------

    def a_dict(self, incluir_estado_entrenamiento: bool = True) -> Dict[str, Any]:
        datos = {
            "formato_version": self.VERSION_FORMATO,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "nombre": self.nombre,
            "factor_escala": self.factor_escala,
            "lr_base": self.lr_base,
            "lr_actual": self.lr_actual,
            "optimizador": self.optimizador,
            "weight_decay": self.weight_decay,
            "pesos": self.pesos.tolist() if self.pesos is not None else None,
            "sesgo": self.sesgo.tolist() if self.sesgo is not None else None,
            "opciones": {
                "usar_normalizacion_adaptativa": self.usar_normalizacion_adaptativa,
                "usar_feature_gating": self.usar_feature_gating,
                "usar_spline": self.usar_spline,
            },
        }
        if incluir_estado_entrenamiento:
            datos["estado_entrenamiento"] = {
                "motor": self.motor_optimizacion.estado(),
                "normalizador": self.normalizador.estado(),
                "gate_logits": (
                    self.comp_puerta.logits.tolist()
                    if self.comp_puerta is not None else None
                ),
                "spline": (
                    self.transformador_spline.estado()
                    if self.transformador_spline is not None else None
                ),
                "mejor_loss": (
                    self.mejor_loss if np.isfinite(self.mejor_loss) else None
                ),
            }
        return datos

    def guardar(self, ruta: str,
                incluir_estado_entrenamiento: bool = True) -> None:
        datos = self.a_dict(incluir_estado_entrenamiento)
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, allow_nan=False)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaEntradaSigmoid":
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        opciones = datos.get("opciones", {})
        obj = cls(
            input_size=datos["input_size"],
            output_size=datos["output_size"],
            nombre=datos.get("nombre", "NeuronaEntradaSigmoid"),
            factor_escala=datos.get("factor_escala", 1.0),
            learning_rate=datos.get("lr_base", 0.001),
            optimizador=datos.get("optimizador", "adam"),
            weight_decay=datos.get("weight_decay", 0.0),
            usar_normalizacion_adaptativa=opciones.get(
                "usar_normalizacion_adaptativa", False
            ),
            usar_feature_gating=opciones.get("usar_feature_gating", False),
            usar_spline=opciones.get("usar_spline", False),
        )

        if datos.get("pesos") is not None:
            pesos = np.asarray(datos["pesos"], dtype=_dtype())
            sesgo = np.asarray(datos["sesgo"], dtype=_dtype())
            if pesos.shape != (obj.input_size, obj.output_size):
                raise ValueError("La matriz de pesos guardada tiene forma invÃ¡lida.")
            if sesgo.shape != (1, obj.output_size):
                raise ValueError("El sesgo guardado tiene forma invÃ¡lida.")
            obj.pesos = pesos
            obj.sesgo = sesgo

        estado = datos.get("estado_entrenamiento", {})
        if "motor" in estado:
            obj.motor_optimizacion.cargar_estado(estado["motor"])
        if "normalizador" in estado and obj.usar_normalizacion_adaptativa:
            obj.normalizador.cargar_estado(estado["normalizador"])
        if estado.get("gate_logits") is not None and obj.comp_puerta is not None:
            gate = np.asarray(estado["gate_logits"], dtype=np.float64)
            if gate.shape != obj.comp_puerta.logits.shape:
                raise ValueError("Estado de compuerta incompatible.")
            obj.comp_puerta.logits = gate
        if estado.get("spline") is not None and obj.transformador_spline is not None:
            obj.transformador_spline.cargar_estado(estado["spline"])
        if estado.get("mejor_loss") is not None:
            obj.mejor_loss = float(estado["mejor_loss"])
        obj.lr_actual = float(datos.get("lr_actual", obj.lr_base))
        return obj

    def __str__(self) -> str:
        return (
            f"{self.nombre}(ent={self.input_size},sal={self.output_size},"
            f"act=Sigmoid,opt={self.optimizador})"
        )


__all__ = [
    "NeuronaEntradaSigmoid",
    "NormalizadorAdaptativo",
    "CompuertaCaracteristicas",
    "TransformadorSpline",
    "MotorOptimizacion",
    "RingBuffer",
]
