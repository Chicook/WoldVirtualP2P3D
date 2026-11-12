"""Subpaquete CELEBRO.BLOK1: Integración de Base Neuronal, Inferencia, Aprendizaje y Métricas.

Exporta:
  - `BaseNeuronal1`: Orquestador principal del bloque 1 con soporte para las 4 fases y servidor.
  - `ServidorNeuronal`: Servidor de red en tiempo real (WebSocket RFC 6455 & TCP Streaming) para clientes (Godot, GDScript, P2P).
  - `PipelineInferencia`: Fase 1 - Inferencia sensor -> latente -> decision (ENRN -> RF_EN).
  - `MotorAprendizajeUnificado`: Fase 2 - Aprendizaje RL + retropropagación sensorial.
  - `OrquestadorP2P`: Fase 3 - Topología multi-actor P2P asíncrona.
  - `MonitorSanidad`: Fase 4 - Monitoreo continuo y auto-sanación quirúrgica.
  - `ejecutar_bloque_resultados_terminal`: Función para análisis y reporte estadístico en terminal.
  - `analizar_pesos_tensor`: Función diagnóstica de tensores de pesos neuronales.
  - `extraer_todos_los_pesos`: Extractor reflexivo de matrices de pesos y sesgos.
  - `modulos_enrn`: Diccionario con módulos cargados de ENRN (EN1_RN a EN10_RN).
  - `modulos_rfen`: Diccionario con módulos cargados de RF_EN (RFEN1_RN_1 a RFEN1_RN_10).
  - `clases_enrn`: Catálogo de clases neuronales de entrada estándar.
  - `clases_rfen`: Catálogo de clases neuronales de refuerzo avanzado.
"""

from __future__ import annotations

try:
    from .BASE_NEURONAL1 import (
        BaseNeuronal1,
        ServidorNeuronal,
        PipelineInferencia,
        MotorAprendizajeUnificado,
        OrquestadorP2P,
        MonitorSanidad,
        ejecutar_bloque_resultados_terminal,
        analizar_pesos_tensor,
        extraer_todos_los_pesos,
        modulos_enrn,
        modulos_rfen,
        clases_enrn,
        clases_rfen,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base_dir = _os.path.dirname(_os.path.abspath(__file__))
    _path_bn1 = _os.path.join(_base_dir, "BASE_NEURONAL1.py")
    _spec = _ilu.spec_from_file_location("CELEBRO.BLOK1.BASE_NEURONAL1", _path_bn1)
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        BaseNeuronal1 = _mod.BaseNeuronal1
        ServidorNeuronal = _mod.ServidorNeuronal
        PipelineInferencia = _mod.PipelineInferencia
        MotorAprendizajeUnificado = _mod.MotorAprendizajeUnificado
        OrquestadorP2P = _mod.OrquestadorP2P
        MonitorSanidad = _mod.MonitorSanidad
        ejecutar_bloque_resultados_terminal = _mod.ejecutar_bloque_resultados_terminal
        analizar_pesos_tensor = _mod.analizar_pesos_tensor
        extraer_todos_los_pesos = _mod.extraer_todos_los_pesos
        modulos_enrn = _mod.modulos_enrn
        modulos_rfen = _mod.modulos_rfen
        clases_enrn = _mod.clases_enrn
        clases_rfen = _mod.clases_rfen
    else:
        raise ImportError(f"No se pudo cargar BASE_NEURONAL1 desde {_path_bn1}")

__all__ = [
    "BaseNeuronal1",
    "ServidorNeuronal",
    "PipelineInferencia",
    "MotorAprendizajeUnificado",
    "OrquestadorP2P",
    "MonitorSanidad",
    "ejecutar_bloque_resultados_terminal",
    "analizar_pesos_tensor",
    "extraer_todos_los_pesos",
    "modulos_enrn",
    "modulos_rfen",
    "clases_enrn",
    "clases_rfen",
]
