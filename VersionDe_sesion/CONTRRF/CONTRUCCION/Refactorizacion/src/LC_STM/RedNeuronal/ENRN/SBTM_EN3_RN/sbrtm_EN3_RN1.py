"""Modulo autocontenido de neurona de entrada LeCun (SBRTM_EN3_RN).

Unifica la base abstracta y la neurona concreta:
  - NeuronaEntradaBase  : contrato abstracto + RingBuffer
  - NeuronaEntradaLeCun : inicializacion LeCun uniforme/normal, optimizadores
                          SGD / SGD-momentum / Adam, metricas, persistencia JSON.

Diferencias matematicas LeCun vs Xavier
-----------------------------------------
  Uniforme  : lim  = sqrt(3 / fan_in)          [solo entrada]
  Normal    : std  = 1 / sqrt(fan_in)           [forma canonica LeCun]
  Var. esp. : 1 / fan_in                        (vs 2/(fan_in+fan_out) Xavier)
  Ganancia  : fija 1.0 (LeCun no parametriza ganancia)
"""

import json
import math
import time
import functools
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Configuracion global del modulo
# ---------------------------------------------------------------------------
LUCIA_CONFIG: Dict[str, Any] = {
    "precision": "float32",
    "random_seed": 42,
    "default_learning_rate": 0.001,
}

_DTYPE_MAP: Dict[str, np.dtype] = {
    "float32": np.float32,
    "float64": np.float64,
    "float16": np.float16,
}


def _dtype() -> np.dtype:
    """Devuelve el dtype numpy activo segun LUCIA_CONFIG['precision']."""
    return np.dtype(_DTYPE_MAP.get(LUCIA_CONFIG.get("precision", "float32"), np.float32))


def _now() -> float:
    """Marca de tiempo de alta resolucion (segundos)."""
    return time.perf_counter()


# ---------------------------------------------------------------------------
# Buffer circular
# ---------------------------------------------------------------------------
class _RingBuffer:
    """Buffer circular de capacidad fija: evita crecimiento infinito de historiales."""

    __slots__ = ("capacidad", "_datos")

    def __init__(self, capacidad: int = 256) -> None:
        self.capacidad: int = int(capacidad)
        self._datos: List[Any] = []

    def append(self, item: Any) -> None:
        self._datos.append(item)
        if len(self._datos) > self.capacidad:
            del self._datos[0: len(self._datos) - self.capacidad]

    def __len__(self) -> int:
        return len(self._datos)

    def to_list(self) -> List[Any]:
        return list(self._datos)

    def clear(self) -> None:
        self._datos.clear()

    def __repr__(self) -> str:
        return f"RingBuffer(cap={self.capacidad}, len={len(self._datos)})"


# ---------------------------------------------------------------------------
# Base abstracta
# ---------------------------------------------------------------------------
class NeuronaEntradaBase:
    """Contrato abstracto autocontenido para cualquier neurona de entrada.

    Incluye el RingBuffer como clase anidada para que las subclases lo usen
    sin importar modulos adicionales.
    """

    RingBuffer = _RingBuffer

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntrada") -> None:
        self.input_size: int = int(input_size)
        self.output_size: int = int(output_size)
        self.nombre: str = nombre
        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.historial_activaciones: List[Any] = []
        self.historial_gradientes: List[Any] = []
        self.llm_connector: Optional[Any] = None

    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def backward(self, g: np.ndarray, e: Optional[np.ndarray] = None
                 ) -> Tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def obtener_estadisticas(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "activaciones": len(self.historial_activaciones),
        }

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        return self.obtener_estadisticas()

    def verificar_estabilidad(self) -> Dict[str, bool]:
        return {"pesos_inicializados": self.pesos is not None}

    def __str__(self) -> str:
        return f"{self.nombre}(entrada={self.input_size}, salida={self.output_size})"

    def __repr__(self) -> str:
        return self.__str__()


# ---------------------------------------------------------------------------
# Neurona LeCun concreta
# ---------------------------------------------------------------------------
class NeuronaEntradaLeCun(NeuronaEntradaBase):
    """EN3 LeCun: inicializacion LeCun uniforme/normal, Adam/SGD, metricas.

    Matematica de inicializacion
    ----------------------------
      Uniforme : pesos ~ U(-lim, lim)   lim = sqrt(3 / fan_in) * factor_escala
      Normal   : pesos ~ N(0, std)      std = 1/sqrt(fan_in) * factor_escala
      Var. esp.: 1 / fan_in

    Preserva API compatible con NeuronaEntradaXavier (EN2):
      inicializar_pesos, forward, backward, paso_optimizador,
      entrenar_paso, obtener_estadisticas_completas, verificar_estabilidad,
      guardar, cargar.
    """

    def __init__(
        self,
        input_size: int,
        output_size: int,
        nombre: str = "NeuronaEntradaLeCun",
        usar_uniforme: bool = False,          # LeCun canonico usa normal
        factor_escala: float = 1.0,
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
        normalizar_entrada: bool = False,
        semilla: Optional[int] = None,
        capacidad_historial: int = 256,
    ) -> None:
        super().__init__(input_size, output_size, nombre)

        # Hiperparametros de inicializacion
        self.usar_uniforme: bool = bool(usar_uniforme)
        self.factor_escala: float = float(factor_escala)
        self.varianza_esperada: float = 0.0
        self.varianza_real: float = 0.0

        # Optimizador
        self.lr_base: float = float(
            learning_rate or LUCIA_CONFIG.get("default_learning_rate", 0.001))
        self.lr_actual: float = float(self.lr_base)
        self.optimizador: str = str(optimizador).lower()
        self.beta1: float = float(beta1)
        self.beta2: float = float(beta2)
        self.epsilon: float = float(epsilon)
        self.weight_decay: float = float(weight_decay)
        self.grad_clip: float = float(grad_clip)
        self.lr_decay: float = float(lr_decay)
        self.lr_min: float = float(lr_min)

        # Entrada / cache
        self.usar_cache_forward: bool = bool(usar_cache_forward)
        self.normalizar_entrada: bool = bool(normalizar_entrada)

        # RNG determinista
        self.semilla: int = (semilla if semilla is not None
                             else int(LUCIA_CONFIG.get("random_seed", 42)))
        self.rng = np.random.default_rng(self.semilla)

        # Momentos Adam/SGD-momentum
        self._m_pesos: Optional[np.ndarray] = None
        self._v_pesos: Optional[np.ndarray] = None
        self._m_sesgo: Optional[np.ndarray] = None
        self._v_sesgo: Optional[np.ndarray] = None
        self._paso: int = 0
        self._cache_entrada: Optional[np.ndarray] = None
        self._cache_salida: Optional[np.ndarray] = None

        # Historiales con RingBuffer
        self.historial_activaciones = _RingBuffer(capacidad_historial)
        self.historial_gradientes = _RingBuffer(capacidad_historial)
        self.historial_loss: List[float] = []
        self.historial_lr: List[float] = []
        self.historial_ratio_var: List[float] = []

        # Contadores de rendimiento
        self.contador_forward: int = 0
        self.contador_backward: int = 0
        self.tiempo_forward_acum: float = 0.0
        self.tiempo_backward_acum: float = 0.0
        self.mejor_loss: float = float("inf")

        # Callbacks de eventos
        self.callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Propiedades de solo lectura (matematica LeCun)
    # ------------------------------------------------------------------
    @property
    def fan_in(self) -> int:
        """Numero de entradas: dimension determinante en LeCun."""
        return self.input_size

    @property
    def limite_lecun(self) -> float:
        """Limite de inicializacion uniforme LeCun: sqrt(3 / fan_in) * escala."""
        return math.sqrt(3.0 / self.fan_in) * self.factor_escala

    @property
    def std_lecun(self) -> float:
        """Desviacion estandar LeCun normal: 1/sqrt(fan_in) * escala."""
        return (1.0 / math.sqrt(self.fan_in)) * self.factor_escala

    @property
    def varianza_lecun(self) -> float:
        """Varianza teorica LeCun: 1 / fan_in."""
        return 1.0 / self.fan_in

    @property
    def ratio_varianza(self) -> float:
        """Ratio varianza_real / varianza_esperada (1.0 = equilibrio perfecto)."""
        return self._ratio_varianza()

    @property
    def esta_inicializada(self) -> bool:
        """True si los pesos ya han sido inicializados."""
        return self.pesos is not None

    # ------------------------------------------------------------------
    # Internos (helpers privados)
    # ------------------------------------------------------------------
    def _ratio_varianza(self) -> float:
        return self.varianza_real / max(self.varianza_esperada, 1e-12)

    def _emit(self, evento: str, info: Optional[Dict[str, Any]] = None) -> None:
        """Dispara todos los callbacks registrados con el evento dado."""
        for cb in self.callbacks:
            try:
                cb(evento, info or {})
            except Exception:
                continue

    def _asegurar_momentos(self) -> None:
        """Inicializa momentos Adam/SGD-momentum si aun no existen."""
        if self._m_pesos is None:
            self._m_pesos = np.zeros_like(self.pesos, dtype=np.float64)
            self._v_pesos = np.zeros_like(self.pesos, dtype=np.float64)
            self._m_sesgo = np.zeros_like(self.sesgo, dtype=np.float64)
            self._v_sesgo = np.zeros_like(self.sesgo, dtype=np.float64)

    def _decaer_lr(self) -> None:
        """Aplica decaimiento de tasa de aprendizaje y registra en historial."""
        if self.lr_decay > 0.0:
            self.lr_actual = max(
                self.lr_min,
                self.lr_base / (1.0 + self.lr_decay * self._paso),
            )
        self.historial_lr.append(self.lr_actual)

    def _clip_grad(self, g: np.ndarray) -> np.ndarray:
        """Recorte de gradiente por norma global (gradient clipping)."""
        if self.grad_clip > 0.0:
            n = float(np.linalg.norm(g))
            if n > self.grad_clip:
                return g * (self.grad_clip / (n + 1e-12))
        return g

    def _preparar_entrada(self, entrada: np.ndarray) -> np.ndarray:
        """Convierte entrada a dtype activo, reshape a 2-D y normaliza si aplica."""
        x = np.asarray(entrada, dtype=_dtype())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(
                f"entrada dim {x.shape[1]} != input_size {self.input_size}")
        if self.normalizar_entrada:
            mu = x.mean(axis=0, keepdims=True)
            sd = x.std(axis=0, keepdims=True) + 1e-8
            x = ((x - mu) / sd).astype(_dtype(), copy=False)
        return np.ascontiguousarray(x, dtype=_dtype())

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def registrar_callback(
            self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        """Registra una funcion que se llama en cada evento (init, paso, etc.)."""
        self.callbacks.append(fn)

    # ------------------------------------------------------------------
    # Inicializacion de pesos (matematica LeCun)
    # ------------------------------------------------------------------
    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        """Inicializa pesos con la distribucion LeCun.

        Parameters
        ----------
        modo : str, opcional
            ``'uniforme'`` fuerza distribucion uniforme;
            ``'normal'`` fuerza distribucion normal;
            ``None`` usa ``self.usar_uniforme``.
        """
        dt = _dtype()
        # Varianza esperada LeCun: 1 / fan_in
        self.varianza_esperada = self.varianza_lecun

        usar_u = (self.usar_uniforme if modo is None
                  else str(modo).lower() == "uniforme")
        if usar_u:
            lim = self.limite_lecun
            self.pesos = self.rng.uniform(
                -lim, lim, (self.input_size, self.output_size)).astype(dt)
        else:
            std = self.std_lecun
            self.pesos = self.rng.normal(
                0.0, std, (self.input_size, self.output_size)).astype(dt)

        self.sesgo = np.zeros((1, self.output_size), dtype=dt)
        self.varianza_real = float(np.var(self.pesos))
        # Resetear momentos y contador
        self._m_pesos = self._v_pesos = self._m_sesgo = self._v_sesgo = None
        self._paso = 0
        self._emit("init", {"var": self.varianza_real, "uniforme": usar_u,
                             "varianza_esperada": self.varianza_esperada})

    def reescalar_lecun(self) -> float:
        """Corrige varianza real hacia la esperada LeCun sin re-inicializar.

        Returns
        -------
        float
            Factor de escala aplicado.
        """
        if self.pesos is None:
            self.inicializar_pesos()
            return 1.0
        v = float(np.var(self.pesos)) + 1e-12
        f = math.sqrt(max(self.varianza_esperada, 1e-12) / v)
        self.pesos = (self.pesos.astype(np.float64) * f).astype(_dtype())
        self.varianza_real = float(np.var(self.pesos))
        return f

    # ------------------------------------------------------------------
    # Forward / Backward
    # ------------------------------------------------------------------
    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Proyeccion lineal: salida = entrada @ pesos + sesgo.

        Registra cache, varianza exponencial y contadores de tiempo.
        """
        t0 = _now()
        if self.pesos is None:
            self.inicializar_pesos()
        x = self._preparar_entrada(entrada)
        salida = np.dot(x, self.pesos) + self.sesgo          # type: ignore[operator]
        salida = np.ascontiguousarray(salida, dtype=_dtype())
        if self.usar_cache_forward:
            self._cache_entrada = x
            self._cache_salida = salida
        v = float(np.var(salida)) if salida.size else 0.0
        self.varianza_real = (
            0.9 * self.varianza_real + 0.1 * v
            if len(self.historial_activaciones) else v
        )
        self.historial_activaciones.append(salida.copy())
        self.historial_ratio_var.append(self._ratio_varianza())
        self.contador_forward += 1
        self.tiempo_forward_acum += _now() - t0
        return salida

    def forward_batch(self, lote: List[np.ndarray]) -> List[np.ndarray]:
        """Aplica forward a cada muestra de un lote (lista de arrays)."""
        return [self.forward(x) for x in lote]

    def backward(
        self,
        gradiente_salida: np.ndarray,
        entrada: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calcula gradientes de pesos y sesgo con clipping.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            ``(grad_pesos, grad_sesgo)`` en el dtype activo.
        """
        t0 = _now()
        g = np.ascontiguousarray(np.asarray(gradiente_salida, dtype=_dtype()))
        if g.ndim == 1:
            g = g.reshape(1, -1)
        x = (self._cache_entrada if entrada is None
             else self._preparar_entrada(entrada))
        if x is None:
            raise ValueError("sin entrada ni cache forward")
        b = max(1, x.shape[0])
        gp = self._clip_grad(
            np.asarray(np.dot(x.T, g) / b, dtype=np.float64))
        gb = self._clip_grad(
            np.asarray(np.sum(g, axis=0, keepdims=True) / b, dtype=np.float64))
        if self.weight_decay > 0.0 and self.pesos is not None:
            gp = gp + self.weight_decay * self.pesos.astype(np.float64)
        self.historial_gradientes.append({
            "pesos": np.asarray(gp, dtype=_dtype()).copy(),
            "sesgo": np.asarray(gb, dtype=_dtype()).copy(),
            "norma_pesos": float(np.linalg.norm(gp)),
            "norma_sesgo": float(np.linalg.norm(gb)),
        })
        self.contador_backward += 1
        self.tiempo_backward_acum += _now() - t0
        return np.asarray(gp, dtype=_dtype()), np.asarray(gb, dtype=_dtype())

    def grad_entrada(self, gradiente_salida: np.ndarray) -> np.ndarray:
        """Propaga gradiente hacia la capa anterior: grad_x = grad_salida @ W^T."""
        g = np.asarray(gradiente_salida, dtype=_dtype())
        if g.ndim == 1:
            g = g.reshape(1, -1)
        assert self.pesos is not None, "pesos no inicializados"
        return np.dot(g, self.pesos.T)

    # ------------------------------------------------------------------
    # Optimizador unificado (SGD / SGD-momentum / Adam)
    # ------------------------------------------------------------------
    def paso_optimizador(
        self,
        grad_pesos: np.ndarray,
        grad_sesgo: np.ndarray,
    ) -> Dict[str, float]:
        """Aplica un paso del optimizador activo sobre pesos y sesgo.

        Soporta: ``'sgd'``, ``'sgd_momentum'``, ``'adam'`` (default).

        Returns
        -------
        Dict[str, float]
            Diccionario con ``lr`` y ``paso`` actuales.
        """
        if self.pesos is None or self.sesgo is None:
            raise RuntimeError("pesos no inicializados; llama inicializar_pesos()")
        self._paso += 1
        self._decaer_lr()
        gp = np.asarray(grad_pesos, dtype=np.float64)
        gb = np.asarray(grad_sesgo, dtype=np.float64)
        lr = self.lr_actual
        dt = _dtype()

        if self.optimizador == "sgd":
            self.pesos = (self.pesos.astype(np.float64) - lr * gp).astype(dt)
            self.sesgo = (self.sesgo.astype(np.float64) - lr * gb).astype(dt)

        elif self.optimizador == "sgd_momentum":
            self._asegurar_momentos()
            assert self._m_pesos is not None and self._m_sesgo is not None
            self._m_pesos[:] = self.beta1 * self._m_pesos + (1 - self.beta1) * gp
            self._m_sesgo[:] = self.beta1 * self._m_sesgo + (1 - self.beta1) * gb
            self.pesos = (self.pesos.astype(np.float64) - lr * self._m_pesos).astype(dt)
            self.sesgo = (self.sesgo.astype(np.float64) - lr * self._m_sesgo).astype(dt)

        else:  # adam (default)
            self._asegurar_momentos()
            assert (self._m_pesos is not None and self._v_pesos is not None
                    and self._m_sesgo is not None and self._v_sesgo is not None)
            b1t = self.beta1 ** self._paso
            b2t = self.beta2 ** self._paso
            self._m_pesos[:] = self.beta1 * self._m_pesos + (1 - self.beta1) * gp
            self._v_pesos[:] = self.beta2 * self._v_pesos + (1 - self.beta2) * (gp * gp)
            self._m_sesgo[:] = self.beta1 * self._m_sesgo + (1 - self.beta1) * gb
            self._v_sesgo[:] = self.beta2 * self._v_sesgo + (1 - self.beta2) * (gb * gb)
            mh_p = self._m_pesos / (1.0 - b1t)
            vh_p = self._v_pesos / (1.0 - b2t)
            mh_b = self._m_sesgo / (1.0 - b1t)
            vh_b = self._v_sesgo / (1.0 - b2t)
            self.pesos = (self.pesos.astype(np.float64)
                          - lr * mh_p / (np.sqrt(vh_p) + self.epsilon)).astype(dt)
            self.sesgo = (self.sesgo.astype(np.float64)
                          - lr * mh_b / (np.sqrt(vh_b) + self.epsilon)).astype(dt)

        info: Dict[str, float] = {"lr": lr, "paso": float(self._paso)}
        self._emit("paso", info)
        return info

    def entrenar_paso(
        self,
        entrada: np.ndarray,
        objetivo: np.ndarray,
    ) -> Dict[str, float]:
        """Pipeline completo: forward -> MSE loss -> backward -> optimizador.

        Returns
        -------
        Dict[str, float]
            Diccionario con ``loss``, ``lr`` y ``paso``.
        """
        pred = self.forward(entrada)
        y = np.asarray(objetivo, dtype=_dtype())
        if y.ndim == 1:
            y = y.reshape(1, -1)
        err = (pred - y) / max(1, pred.shape[0])
        loss = float(np.mean((pred - y) ** 2))
        gp, gb = self.backward(err, entrada)
        opt = self.paso_optimizador(gp, gb)
        self.historial_loss.append(loss)
        if loss < self.mejor_loss:
            self.mejor_loss = loss
        return {"loss": loss, **opt}

    # ------------------------------------------------------------------
    # Estadisticas y estabilidad
    # ------------------------------------------------------------------
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Estadisticas basicas de la neurona."""
        return {
            "nombre": self.nombre,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "activaciones": len(self.historial_activaciones),
            "forwards": self.contador_forward,
            "backwards": self.contador_backward,
            "lr_actual": self.lr_actual,
            "paso": self._paso,
            "optimizador": self.optimizador,
            "usar_uniforme": self.usar_uniforme,
        }

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        """Estadisticas extendidas incluyendo varianza, ratio y tiempos."""
        stats = self.obtener_estadisticas()
        nw = float(np.linalg.norm(self.pesos)) if self.pesos is not None else 0.0
        stats.update({
            "varianza_esperada": self.varianza_esperada,
            "varianza_real": self.varianza_real,
            "ratio_varianza": self._ratio_varianza(),
            "norma_pesos": nw,
            "mejor_loss": self.mejor_loss,
            "ultima_loss": self.historial_loss[-1] if self.historial_loss else None,
            "t_medio_forward_ms": (
                self.tiempo_forward_acum / max(1, self.contador_forward)) * 1000.0,
            "t_medio_backward_ms": (
                self.tiempo_backward_acum / max(1, self.contador_backward)) * 1000.0,
        })
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        """Comprueba salud numerica de los pesos."""
        est: Dict[str, bool] = {
            "pesos_inicializados": self.pesos is not None,
            "sesgo_inicializado": self.sesgo is not None,
        }
        if self.pesos is not None:
            pmax = float(np.max(np.abs(self.pesos)))
            pmin = max(float(np.min(np.abs(self.pesos))), 1e-12)
            est["pesos_no_explosivos"] = pmax < 5.0
            est["pesos_no_desaparecen"] = pmin > 1e-6
            est["pesos_balanceados"] = (pmax / pmin) < 1000.0
            est["varianza_estable"] = 0.5 <= self._ratio_varianza() <= 2.0
            est["sin_nan"] = bool(not np.isnan(self.pesos).any())
            est["sin_inf"] = bool(not np.isinf(self.pesos).any())
        return est

    @staticmethod
    def optimizadores_disponibles() -> List[str]:
        """Lista de nombres de optimizador soportados por esta clase."""
        return ["sgd", "sgd_momentum", "adam"]

    def resumen_rendimiento(self) -> Dict[str, Any]:
        """Tiempos acumulados de forward y backward."""
        return {
            "forwards": self.contador_forward,
            "backwards": self.contador_backward,
            "t_forward_total_s": self.tiempo_forward_acum,
            "t_backward_total_s": self.tiempo_backward_acum,
        }

    def reiniciar_metricas(self) -> None:
        """Resetea contadores y historiales sin tocar pesos ni optimizador."""
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.historial_loss.clear()
        self.historial_lr.clear()
        self.historial_ratio_var.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0

    # ------------------------------------------------------------------
    # Persistencia JSON
    # ------------------------------------------------------------------
    def a_dict(self) -> Dict[str, Any]:
        """Serializa el estado de la neurona a un diccionario JSON-compatible."""
        return {
            "tipo": "NeuronaEntradaLeCun",
            "input_size": self.input_size,
            "output_size": self.output_size,
            "nombre": self.nombre,
            "usar_uniforme": self.usar_uniforme,
            "factor_escala": self.factor_escala,
            "lr_base": self.lr_base,
            "optimizador": self.optimizador,
            "semilla": self.semilla,
            "pesos": self.pesos.tolist() if self.pesos is not None else None,
            "sesgo": self.sesgo.tolist() if self.sesgo is not None else None,
        }

    def guardar(self, ruta: str) -> None:
        """Guarda el estado en un archivo JSON en ``ruta``."""
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(self.a_dict(), fh, indent=2, ensure_ascii=False)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaEntradaLeCun":
        """Carga una neurona desde un archivo JSON creado con ``guardar``.

        Parameters
        ----------
        ruta : str
            Ruta al archivo ``.json``.

        Returns
        -------
        NeuronaEntradaLeCun
            Instancia reconstruida con pesos y configuracion originales.
        """
        with open(ruta, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        obj = cls(
            d["input_size"],
            d["output_size"],
            d.get("nombre", "NeuronaEntradaLeCun"),
            usar_uniforme=d.get("usar_uniforme", False),
            factor_escala=d.get("factor_escala", 1.0),
            learning_rate=d.get("lr_base", 0.001),
            optimizador=d.get("optimizador", "adam"),
            semilla=d.get("semilla", None),
        )
        if d.get("pesos") is not None:
            obj.pesos = np.asarray(d["pesos"], dtype=_dtype())
            obj.sesgo = np.asarray(d["sesgo"], dtype=_dtype())
            obj.varianza_real = float(np.var(obj.pesos))
            obj.varianza_esperada = obj.varianza_lecun
        return obj

    # ------------------------------------------------------------------
    # Representacion
    # ------------------------------------------------------------------
    def __str__(self) -> str:
        init = "unif" if self.usar_uniforme else "norm"
        return (f"{self.nombre}("
                f"ent={self.input_size},sal={self.output_size},"
                f"init=LeCun-{init},opt={self.optimizador})")

    def __repr__(self) -> str:
        return self.__str__()


# ---------------------------------------------------------------------------
# Alias de modulo y exportaciones
# ---------------------------------------------------------------------------
NeuronaEntradaBase.LeCun = NeuronaEntradaLeCun  # type: ignore[attr-defined]

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaLeCun",
    "LUCIA_CONFIG",
    "_dtype",
    "_now",
]