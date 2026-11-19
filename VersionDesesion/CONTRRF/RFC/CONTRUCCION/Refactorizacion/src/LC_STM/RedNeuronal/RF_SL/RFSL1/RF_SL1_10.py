"""
RF_SL1_10.py - Aprendizaje supervisado integrado (puente legado)
================================================================

Este modulo ya no reimplementa el sistema integrado ni sus utilidades. La
implementacion unica vive en el modulo especializado:

    RF_SL_SBRTM_RF_SL1_10/RF_SL_SBRTM_RF_SL1_10_1.py

Desde alli se importan ``NeuronaAprendizajeIntegrado``, el adaptador historico
``IntegratedSupervisedLearningOptimizer``, la base compartida
``NeuronaMemoriaBase``, las utilidades de ensemble/validacion y las funciones
nuevas (fabrica, configuracion de IA local, metricas, benchmark, persistencia
y demo). No quedan definiciones locales duplicadas.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Aprendizaje integrado: fuente unica en RF_SL_SBRTM_RF_SL1_10.
#
# Se importan sus clases (ensemble Ridge/logistico/MLP, configurador de IA
# local y utilidades) y sus funciones nuevas. El antiguo bloque local de
# IntegratedSupervisedLearningOptimizer y sus helpers (lineas 60-394) queda
# sustituido por este import, sin definiciones duplicadas.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_10.RF_SL_SBRTM_RF_SL1_10_1 import (
        LUCIA_INTEGRATED_CONFIG,
        DataSplitter,
        EnsembleManager,
        FeatureStandardizer,
        IntegratedSupervisedLearningOptimizer,
        ModelValidator,
        NeuronaAprendizajeIntegrado,
        NeuronaMemoriaBase,
        PredictionAggregator,
        SupervisedTrainer,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        create_integrated_supervised_learning_optimizer,
        demo,
        entrenar_y_evaluar,
        guardar_modelo,
        tipos_disponibles,
    )
except (ImportError, ValueError):
    # Fallback por ruta para cargas por fichero o sin paquete padre.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_MODULO = "_rf_sl1_10_integrated_import"
    _modulo_integrado = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_integrado is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_10",
            "RF_SL_SBRTM_RF_SL1_10_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(
            _CLAVE_MODULO, _ruta_modulo
        )
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_integrado = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_integrado
        _especificacion.loader.exec_module(_modulo_integrado)
    LUCIA_INTEGRATED_CONFIG = _modulo_integrado.LUCIA_INTEGRATED_CONFIG
    DataSplitter = _modulo_integrado.DataSplitter
    EnsembleManager = _modulo_integrado.EnsembleManager
    FeatureStandardizer = _modulo_integrado.FeatureStandardizer
    IntegratedSupervisedLearningOptimizer = (
        _modulo_integrado.IntegratedSupervisedLearningOptimizer
    )
    ModelValidator = _modulo_integrado.ModelValidator
    NeuronaAprendizajeIntegrado = (
        _modulo_integrado.NeuronaAprendizajeIntegrado
    )
    NeuronaMemoriaBase = _modulo_integrado.NeuronaMemoriaBase
    PredictionAggregator = _modulo_integrado.PredictionAggregator
    SupervisedTrainer = _modulo_integrado.SupervisedTrainer
    benchmark_modelo = _modulo_integrado.benchmark_modelo
    cargar_modelo = _modulo_integrado.cargar_modelo
    crear_neurona = _modulo_integrado.crear_neurona
    create_integrated_supervised_learning_optimizer = (
        _modulo_integrado.create_integrated_supervised_learning_optimizer
    )
    demo = _modulo_integrado.demo
    entrenar_y_evaluar = _modulo_integrado.entrenar_y_evaluar
    guardar_modelo = _modulo_integrado.guardar_modelo
    tipos_disponibles = _modulo_integrado.tipos_disponibles

# Acceso directo a las clases anidadas del nucleo y del configurador local.
NucleoIntegrado = NeuronaAprendizajeIntegrado.NucleoIntegrado
ConfiguradorIALocal = NeuronaAprendizajeIntegrado.ConfiguradorIALocal

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("RF_SL1_10.py cargado exitosamente")
