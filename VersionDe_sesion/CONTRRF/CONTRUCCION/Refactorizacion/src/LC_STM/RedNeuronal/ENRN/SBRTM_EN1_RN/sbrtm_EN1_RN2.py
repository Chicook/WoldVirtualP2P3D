"""Módulo autocontenido de métricas, estabilidad y persistencia (SBRTM_EN1_RN).

Unifica las funciones sueltas de la neurona de entrada en una sola clase
(NeuronaHerramientas) con clases anidadas:
- Estadisticas: métricas de activación, pesos y rendimiento.
- Estabilidad: chequeos numéricos de estabilidad de los pesos.
- Persistencia: serialización JSON (a_dict / guardar / cargar).
"""

import json

import numpy as np
from typing import Any, Dict

try:
    from .sbrtm_EN1_RN1 import _dtype
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        'sbrtm_EN1_RN1', _os.path.join(_base, 'sbrtm_EN1_RN1.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _dtype = _mod._dtype


class NeuronaHerramientas:
    """Mixin con métricas, estabilidad y persistencia de la neurona de entrada."""

    class Estadisticas:
        """Métricas de activación, pesos y rendimiento."""

        @staticmethod
        def base(neurona: Any) -> Dict[str, Any]:
            base = {"nombre": neurona.nombre, "input_size": neurona.input_size,
                    "output_size": neurona.output_size,
                    "activaciones": len(neurona.historial_activaciones)}
            base.update({"forwards": neurona.contador_forward, "backwards": neurona.contador_backward,
                         "lr_actual": neurona.lr_actual, "paso": neurona._paso,
                         "optimizador": neurona.optimizador})
            return base

        @staticmethod
        def completas(neurona: Any) -> Dict[str, Any]:
            stats = NeuronaHerramientas.Estadisticas.base(neurona)
            pesos = neurona.pesos
            pw = float(np.mean(np.abs(pesos))) if pesos is not None else 0.0
            nw = float(np.linalg.norm(pesos)) if pesos is not None else 0.0
            tf = neurona.tiempo_forward_acum / max(1, neurona.contador_forward)
            tb = neurona.tiempo_backward_acum / max(1, neurona.contador_backward)
            stats.update({'varianza_esperada': neurona.varianza_esperada, 'varianza_real': neurona.varianza_real,
                          'media_abs_pesos': pw, 'norma_pesos': nw,
                          'mejor_loss': neurona.mejor_loss,
                          'ultima_loss': neurona.historial_loss[-1] if neurona.historial_loss else None,
                          't_medio_forward_ms': tf * 1000.0, 't_medio_backward_ms': tb * 1000.0})
            return stats

        @staticmethod
        def rendimiento(neurona: Any) -> Dict[str, Any]:
            return {"forwards": neurona.contador_forward, "backwards": neurona.contador_backward,
                    "t_forward_total_s": neurona.tiempo_forward_acum, "t_backward_total_s": neurona.tiempo_backward_acum,
                    "t_medio_forward_ms": (neurona.tiempo_forward_acum / max(1, neurona.contador_forward)) * 1000.0,
                    "t_medio_backward_ms": (neurona.tiempo_backward_acum / max(1, neurona.contador_backward)) * 1000.0}

        @staticmethod
        def reiniciar(neurona: Any) -> None:
            neurona.historial_activaciones.clear()
            neurona.historial_gradientes.clear()
            neurona.historial_loss.clear()
            neurona.historial_lr.clear()
            neurona.historial_tiempo.clear()
            neurona.contador_forward = 0
            neurona.contador_backward = 0
            neurona.tiempo_forward_acum = 0.0
            neurona.tiempo_backward_acum = 0.0

    class Estabilidad:
        """Chequeos numéricos de estabilidad de los pesos."""

        @staticmethod
        def verificar(neurona: Any) -> Dict[str, bool]:
            est = {'pesos_inicializados': neurona.pesos is not None,
                   'sesgo_inicializado': neurona.sesgo is not None}
            if neurona.pesos is not None:
                pmax = float(np.max(np.abs(neurona.pesos)))
                pmin = max(float(np.min(np.abs(neurona.pesos))), 1e-12)
                est['pesos_no_explosivos'] = pmax < 5.0
                est['pesos_no_desaparecen'] = pmin > 1e-6
                est['pesos_balanceados'] = pmax / pmin < 1000.0
                est['sin_nan'] = bool(not np.isnan(neurona.pesos).any())
                est['sin_inf'] = bool(not np.isinf(neurona.pesos).any())
                est['sesgo_acotado'] = bool(float(np.max(np.abs(neurona.sesgo))) < 5.0)
            return est

    class Persistencia:
        """Serialización JSON de la neurona."""

        @staticmethod
        def a_dict(neurona: Any) -> Dict[str, Any]:
            return {"input_size": neurona.input_size, "output_size": neurona.output_size, "nombre": neurona.nombre,
                    "factor_escala": neurona.factor_escala, "lr_base": neurona.lr_base, "optimizador": neurona.optimizador,
                    "pesos": neurona.pesos.tolist() if neurona.pesos is not None else None,
                    "sesgo": neurona.sesgo.tolist() if neurona.sesgo is not None else None}

        @staticmethod
        def guardar(neurona: Any, ruta: str) -> None:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(NeuronaHerramientas.Persistencia.a_dict(neurona), f)

        @staticmethod
        def cargar(cls: Any, ruta: str) -> Any:
            with open(ruta, "r", encoding="utf-8") as f:
                d = json.load(f)
            obj = cls(d["input_size"], d["output_size"], d.get("nombre", "NeuronaEntradaBasica"),
                      factor_escala=d.get("factor_escala", 1.0),
                      learning_rate=d.get("lr_base", 0.001),
                      optimizador=d.get("optimizador", "adam"))
            if d.get("pesos") is not None:
                obj.pesos = np.asarray(d["pesos"], dtype=_dtype())
                obj.sesgo = np.asarray(d["sesgo"], dtype=_dtype())
            return obj

    # ------------------------------------------------------------------
    # Métodos de instancia que delegan en las clases anidadas
    # ------------------------------------------------------------------
    def obtener_estadisticas(self) -> Dict[str, Any]:
        return self.Estadisticas.base(self)

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        return self.Estadisticas.completas(self)

    def verificar_estabilidad(self) -> Dict[str, bool]:
        return self.Estabilidad.verificar(self)

    def resumen_rendimiento(self) -> Dict[str, Any]:
        return self.Estadisticas.rendimiento(self)

    def reiniciar_metricas(self) -> None:
        self.Estadisticas.reiniciar(self)

    def a_dict(self) -> Dict[str, Any]:
        return self.Persistencia.a_dict(self)

    def guardar(self, ruta: str) -> None:
        self.Persistencia.guardar(self, ruta)

    @classmethod
    def cargar(cls, ruta: str) -> Any:
        return cls.Persistencia.cargar(cls, ruta)


__all__ = ["NeuronaHerramientas"]
