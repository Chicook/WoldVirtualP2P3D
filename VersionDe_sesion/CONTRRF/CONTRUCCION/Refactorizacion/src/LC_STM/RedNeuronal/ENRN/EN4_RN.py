"""EN4 / RN1 - version extendida de la neurona de entrada normalizada.

La base normalizada (estadisticas, Adam/SGD, decoradores y clases anidadas)
vive en ``sbrtm_EN4_RN1``; aqui solo se anade el ciclo de entrenamiento,
la serializacion y las metricas extendidas.
"""

import json
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .SBTM_EN4_RN.sbrtm_EN4_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaNormalizada as _NeuronaEntradaNormalizadaBase,
        _dtype,
        _now,
    )
except ImportError:  # ejecucion directa o modulo suelto
    from SBTM_EN4_RN.sbrtm_EN4_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaNormalizada as _NeuronaEntradaNormalizadaBase,
        _dtype,
        _now,
    )

try:  # mantiene la precision configurada por el paquete ENRN
    from . import LUCIA_CONFIG as _CONFIG_ENRN
    if isinstance(_CONFIG_ENRN, dict):
        LUCIA_CONFIG.update(_CONFIG_ENRN)
except ImportError:
    pass


class NeuronaEntradaNormalizada(_NeuronaEntradaNormalizadaBase):
    """Version extendida: hereda normalizacion, optimizador y decoradores.

    Anade entrenamiento por lotes, serializacion y metricas de rendimiento.
    ``weight_decay`` se aplica en ``backward`` (no en el optimizador) para
    preservar el gradiente penalizado que se devuelve al llamador.
    """

    _ALIAS_OPTIMIZADOR = {"sgd_momentum": "sgd_momento", "momentum": "sgd_momento"}

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaNormalizada",
                 metodo: str = 'z_score',
                 factor_escala: float = 1.0,
                 momento_stats: float = 0.1,
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
                 capacidad_historial: int = 256):
        metodo = metodo if metodo in self.METODOS else "z_score"
        algoritmo = str(optimizador).lower()
        algoritmo = self._ALIAS_OPTIMIZADOR.get(algoritmo, algoritmo)
        if algoritmo not in self.Optimizador.ALGORITMOS:
            algoritmo = "adam"
        super().__init__(
            input_size, output_size, nombre, metodo, factor_escala,
            momento_stats, learning_rate, algoritmo, beta1, beta2, epsilon,
            0.0,  # weight_decay lo aplica backward, no el optimizador
            grad_clip, lr_decay, lr_min, usar_cache_forward, semilla,
            capacidad_historial,
        )
        self.weight_decay = float(weight_decay)

    # ------------------------------------------------------------------
    def inicializar_pesos(self, modo: str = "he") -> None:
        dt = _dtype()
        modo = str(modo).lower()
        if modo == "he":
            std = math.sqrt(2.0 / self.input_size) * self.factor_escala
            self.pesos = self.rng.normal(0, std, (self.input_size, self.output_size)).astype(dt)
            self.varianza_esperada = 2.0 / self.input_size
        elif modo == "xavier":
            lim = math.sqrt(6.0 / (self.input_size + self.output_size)) * self.factor_escala
            self.pesos = self.rng.uniform(-lim, lim, (self.input_size, self.output_size)).astype(dt)
            self.varianza_esperada = 1.0 / ((self.input_size + self.output_size) / 2.0)
        elif modo == "lecun":
            std = math.sqrt(1.0 / self.input_size) * self.factor_escala
            self.pesos = self.rng.normal(0, std, (self.input_size, self.output_size)).astype(dt)
            self.varianza_esperada = 1.0 / self.input_size
        else:
            raise ValueError(f"modo {modo} desconocido")
        self.sesgo = np.zeros((1, self.output_size), dtype=dt)
        self.varianza_real = float(np.var(self.pesos))
        self.optimizador.reiniciar()
        self._paso = 0
        self._emit("init", {"modo": modo})

    def forward(self, entrada: np.ndarray, actualizar_stats: bool = True) -> np.ndarray:
        t0 = _now()
        if self.pesos is None:
            self.inicializar_pesos()
        assert self.pesos is not None and self.sesgo is not None
        entrada_norm = self._normalizar(entrada, actualizar=actualizar_stats)
        entrada_norm = np.ascontiguousarray(entrada_norm, dtype=_dtype())
        salida = np.dot(entrada_norm, self.pesos) + self.sesgo
        salida = np.ascontiguousarray(salida, dtype=_dtype())
        if self.usar_cache_forward:
            self._cache_entrada = entrada_norm
        v = float(np.var(salida)) if salida.size else 0.0
        self.varianza_real = 0.9 * self.varianza_real + 0.1 * v if len(self.historial_activaciones) else v
        self.historial_activaciones.append(salida.copy())
        self.contador_forward += 1
        self.tiempo_forward_acum += _now() - t0
        return salida

    def forward_batch(self, lote: List[np.ndarray]) -> List[np.ndarray]:
        return [self.forward(x) for x in lote]

    def backward(self, gradiente_salida: np.ndarray, entrada: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        t0 = _now()
        g = np.ascontiguousarray(np.asarray(gradiente_salida, dtype=_dtype()))
        if g.ndim == 1:
            g = g.reshape(1, -1)
        entrada_norm = self._normalizar(entrada, actualizar=False)
        b = max(1, entrada_norm.shape[0])
        gp = self._clip(np.asarray(np.dot(entrada_norm.T, g) / b, dtype=np.float64))
        gb = self._clip(np.asarray(np.sum(g, axis=0, keepdims=True) / b, dtype=np.float64))
        if self.weight_decay > 0.0 and self.pesos is not None:
            gp = gp + self.weight_decay * self.pesos.astype(np.float64)
        self.historial_gradientes.append({'pesos': np.asarray(gp, dtype=_dtype()).copy(),
                                          'sesgo': np.asarray(gb, dtype=_dtype()).copy(),
                                          'norma_pesos': float(np.linalg.norm(gp)),
                                          'norma_sesgo': float(np.linalg.norm(gb))})
        self.contador_backward += 1
        self.tiempo_backward_acum += _now() - t0
        return np.asarray(gp, dtype=_dtype()), np.asarray(gb, dtype=_dtype())

    def grad_entrada(self, gradiente_salida: np.ndarray) -> np.ndarray:
        g = np.asarray(gradiente_salida, dtype=_dtype())
        if g.ndim == 1:
            g = g.reshape(1, -1)
        assert self.pesos is not None
        return np.dot(g, self.pesos.T)

    def paso_optimizador(self, grad_pesos: np.ndarray, grad_sesgo: np.ndarray) -> Dict[str, float]:
        if self.pesos is None or self.sesgo is None:
            raise RuntimeError("pesos no inicializados")
        self._paso = self.optimizador.nuevo_paso()
        self._decaer_lr()
        self.optimizador.aplicar(
            "pesos", self.pesos, np.asarray(grad_pesos, dtype=np.float64),
            self.lr_actual, self._paso,
        )
        self.optimizador.aplicar(
            "sesgo", self.sesgo, np.asarray(grad_sesgo, dtype=np.float64),
            self.lr_actual, self._paso,
        )
        info = {"lr": self.lr_actual, "paso": float(self._paso)}
        self._emit("paso", info)
        return info

    def entrenar_paso(self, entrada: np.ndarray, objetivo: np.ndarray) -> Dict[str, float]:
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
    def obtener_estadisticas(self, completas: bool = False) -> Dict[str, Any]:
        stats = super().obtener_estadisticas(completas=completas)
        stats.update({"forwards": self.contador_forward,
                      "backwards": self.contador_backward,
                      "paso": self._paso})
        return stats

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas_completas()
        nw = float(np.linalg.norm(self.pesos)) if self.pesos is not None else 0.0
        stats.update({'metodo_norm': self.metodo, 'norma_pesos': nw,
                      'ultima_loss': self.historial_loss[-1] if self.historial_loss else None,
                      't_medio_forward_ms': (self.tiempo_forward_acum / max(1, self.contador_forward)) * 1000.0,
                      't_medio_backward_ms': (self.tiempo_backward_acum / max(1, self.contador_backward)) * 1000.0})
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        est = super().verificar_estabilidad()
        est['sesgo_inicializado'] = self.sesgo is not None
        est['normalizacion_lista'] = self.params_norm['media'] is not None
        if self.pesos is not None:
            pmax = float(np.max(np.abs(self.pesos)))
            pmin = max(float(np.min(np.abs(self.pesos))), 1e-12)
            est['pesos_no_explosivos'] = pmax < 5.0
            est['pesos_no_desaparecen'] = pmin > 1e-6
            est['sin_nan'] = bool(not np.isnan(self.pesos).any())
            est['sin_inf'] = bool(not np.isinf(self.pesos).any())
        return est

    def resumen_rendimiento(self) -> Dict[str, Any]:
        return {"forwards": self.contador_forward, "backwards": self.contador_backward,
                "t_forward_total_s": self.tiempo_forward_acum,
                "t_backward_total_s": self.tiempo_backward_acum}

    def reiniciar_metricas(self) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.historial_loss.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0

    def a_dict(self) -> Dict[str, Any]:
        return {"input_size": self.input_size, "output_size": self.output_size,
                "nombre": self.nombre, "metodo": self.metodo,
                "factor_escala": self.factor_escala, "lr_base": self.lr_base,
                "optimizador": self.optimizador.algoritmo,
                "pesos": self.pesos.tolist() if self.pesos is not None else None,
                "sesgo": self.sesgo.tolist() if self.sesgo is not None else None}

    def guardar(self, ruta: str) -> None:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.a_dict(), f)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaEntradaNormalizada":
        with open(ruta, "r", encoding="utf-8") as f:
            d = json.load(f)
        obj = cls(d["input_size"], d["output_size"], d.get("nombre", "NeuronaEntradaNormalizada"),
                  metodo=d.get("metodo", "z_score"),
                  factor_escala=d.get("factor_escala", 1.0),
                  learning_rate=d.get("lr_base", 0.001),
                  optimizador=d.get("optimizador", "adam"))
        if d.get("pesos") is not None:
            obj.pesos = np.asarray(d["pesos"], dtype=_dtype())
            obj.sesgo = np.asarray(d["sesgo"], dtype=_dtype())
        return obj

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},sal={self.output_size},"
                f"norm={self.metodo},opt={self.optimizador.algoritmo})")