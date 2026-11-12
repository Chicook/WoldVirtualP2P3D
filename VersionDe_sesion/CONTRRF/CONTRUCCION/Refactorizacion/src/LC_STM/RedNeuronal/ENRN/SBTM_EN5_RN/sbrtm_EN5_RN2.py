"""sbrtm_EN5_RN2 - Utilidades extendidas de la neurona de entrada EN5.

Continua la estructura de ``sbrtm_EN5_RN1``: una clase principal que hereda de
``NeuronaEntradaRegularizada`` y agrupa poda, metricas y persistencia, con las
clases anidadas ``Metricas`` (contadores/tiempos por operacion) y
``Serializador`` (JSON) para no mezclar responsabilidades.

API publica: podar, norma_actual, obtener_estadisticas(_completas),
verificar_estabilidad, resumen_rendimiento, reiniciar_metricas, a_dict,
guardar, cargar.
"""

from __future__ import annotations

import json
from functools import wraps
from typing import Any, Callable, Dict

import numpy as np

try:
    from .sbrtm_EN5_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaRegularizada as _NeuronaEntradaRegularizadaBase,
        _now,
    )
except ImportError:  # ejecucion directa sin paquete
    import importlib.util as _ilu
    import os as _os

    _ruta = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "sbrtm_EN5_RN1.py")
    _spec = _ilu.spec_from_file_location("sbrtm_EN5_RN1", _ruta)
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LUCIA_CONFIG = _mod.LUCIA_CONFIG
    _NeuronaEntradaRegularizadaBase = _mod.NeuronaEntradaRegularizada
    _now = _mod._now

__all__ = [
    "LUCIA_CONFIG",
    "NeuronaEntradaRegularizadaExt",
]


def _con_metricas(nombre: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Cuenta llamadas y acumula duracion de ``fn`` en ``self.metricas``."""

    def decorador(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def envoltura(self: Any, *args: Any, **kwargs: Any) -> Any:
            inicio = _now()
            try:
                return fn(self, *args, **kwargs)
            finally:
                self.metricas.registrar(nombre, _now() - inicio)
        return envoltura

    return decorador


class NeuronaEntradaRegularizadaExt(_NeuronaEntradaRegularizadaBase):
    """EN5 extendida: poda, metricas y serializacion sobre la base RN1."""

    # ------------------------------------------------------------------
    class Metricas:
        """Contadores y tiempos por operacion, encapsulados por neurona."""

        def __init__(self) -> None:
            self._ops: Dict[str, int] = {}
            self._tiempos: Dict[str, float] = {}

        def registrar(self, nombre: str, duracion: float) -> None:
            self._ops[nombre] = self._ops.get(nombre, 0) + 1
            self._tiempos[nombre] = self._tiempos.get(nombre, 0.0) + float(duracion)

        def contador(self, nombre: str) -> int:
            return self._ops.get(nombre, 0)

        def tiempo(self, nombre: str) -> float:
            return self._tiempos.get(nombre, 0.0)

        def medio_ms(self, nombre: str) -> float:
            n = self.contador(nombre)
            return (self.tiempo(nombre) / n) * 1000.0 if n else 0.0

        def to_dict(self) -> Dict[str, Any]:
            return {"contadores": dict(self._ops), "tiempos_s": dict(self._tiempos)}

        def clear(self) -> None:
            self._ops.clear()
            self._tiempos.clear()

        def __repr__(self) -> str:
            return f"Metricas({self._ops})"

    # ------------------------------------------------------------------
    class Serializador:
        """Conversion desde/hacia JSON de la neurona (sin estado propio)."""

        CAMPOS = ("input_size", "output_size", "nombre",
                  "lambda_l2", "lambda_l1", "factor_escala",
                  "lr_base", "optimizador")

        @staticmethod
        def a_dict(neurona: Any) -> Dict[str, Any]:
            destino: Dict[str, Any] = {
                campo: getattr(neurona, campo) for campo in Serializador.CAMPOS
            }
            destino["pesos"] = (neurona.pesos.tolist()
                                if neurona.pesos is not None else None)
            destino["sesgo"] = (neurona.sesgo.tolist()
                                if neurona.sesgo is not None else None)
            return destino

        @staticmethod
        def aplicar(neurona: Any, datos: Dict[str, Any]) -> Any:
            if datos.get("pesos") is not None:
                neurona.pesos = np.asarray(datos["pesos"], dtype=neurona.dt)
                neurona.sesgo = np.asarray(datos["sesgo"],
                                           dtype=neurona.dt).reshape(-1)
            return neurona

        @classmethod
        def guardar(cls, neurona: Any, ruta: str) -> None:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(cls.a_dict(neurona), f)

        @classmethod
        def cargar(cls, ruta: str, neurona_cls: type) -> Any:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
            neurona = neurona_cls(
                datos["input_size"], datos["output_size"],
                datos.get("nombre", "NeuronaEntradaRegularizadaExt"),
                lambda_l2=datos.get("lambda_l2", 0.01),
                lambda_l1=datos.get("lambda_l1", 0.0),
                factor_escala=datos.get("factor_escala", 1.0),
                learning_rate=datos.get("lr_base", 0.001),
                optimizador=datos.get("optimizador", "adamw"),
            )
            return cls.aplicar(neurona, datos)

    # ------------------------------------------------------------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.metricas = self.Metricas()

    # ------------------------------------------------------------------
    # Poda y normas
    # ------------------------------------------------------------------
    @_con_metricas("podar")
    def podar(self, umbral: float = 1e-3) -> int:
        if self.pesos is None:
            return 0
        mask = np.abs(self.pesos) < umbral
        n = int(np.sum(mask))
        self.pesos[mask] = 0
        return n

    @_con_metricas("norma_actual")
    def norma_actual(self) -> float:
        return float(np.linalg.norm(self.pesos)) if self.pesos is not None else 0.0

    # ------------------------------------------------------------------
    # Metricas (amplian las de la base, sin reimplementarlas)
    # ------------------------------------------------------------------
    @_con_metricas("estadisticas")
    def obtener_estadisticas(self, completas: bool = False) -> Dict[str, Any]:
        info = super().obtener_estadisticas(completas=completas)
        info["forwards"] = self.contador_forward
        info["backwards"] = self.contador_backward
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        stats = self.obtener_estadisticas(completas=True)
        hist = self.norma_pesos_historial.to_list()
        stats.update({
            "norma_pesos_prom": float(np.mean(hist)) if hist else 0.0,
            "norma_pesos_actual": self.norma_actual(),
            "reg_actual": self.penalizacion(),
            "ultima_loss": self.historial_loss[-1] if self.historial_loss else None,
            "t_medio_forward_ms": (self.tiempo_forward_acum
                                   / max(1, self.contador_forward)) * 1000.0,
            "t_medio_backward_ms": (self.tiempo_backward_acum
                                    / max(1, self.contador_backward)) * 1000.0,
            "metricas": self.metricas.to_dict(),
        })
        return stats

    @_con_metricas("estabilidad")
    def verificar_estabilidad(self) -> Dict[str, Any]:
        est = super().verificar_estabilidad()
        est["sesgo_inicializado"] = self.sesgo is not None
        if self.pesos is not None:
            pmax = float(np.max(np.abs(self.pesos)))
            pmin = max(float(np.min(np.abs(self.pesos))), 1e-12)
            est["pesos_no_explosivos"] = pmax < 5.0
            est["pesos_no_desaparecen"] = pmin > 1e-6
            est["sin_nan"] = bool(not np.isnan(self.pesos).any())
            est["sin_inf"] = bool(not np.isinf(self.pesos).any())
        return est

    def resumen_rendimiento(self) -> Dict[str, Any]:
        return {
            "forwards": self.contador_forward,
            "backwards": self.contador_backward,
            "t_forward_total_s": self.tiempo_forward_acum,
            "t_backward_total_s": self.tiempo_backward_acum,
            "operaciones": self.metricas.to_dict(),
        }

    def reiniciar_metricas(self) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.norma_pesos_historial.clear()
        self.historial_loss.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0
        self.metricas.clear()

    # ------------------------------------------------------------------
    # Persistencia JSON
    # ------------------------------------------------------------------
    def a_dict(self) -> Dict[str, Any]:
        return self.Serializador.a_dict(self)

    def guardar(self, ruta: str) -> None:
        self.Serializador.guardar(self, ruta)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaEntradaRegularizadaExt":
        return cls.Serializador.cargar(ruta, cls)
