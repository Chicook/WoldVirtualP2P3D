"""Subpaquete RF_EN_SBRTM_IMPORT: utilidades de refuerzo (SBRTM).

Reexporta la configuración, las clases unificadas (HerramientasRefuerzo,
GestorEntrenamientoRefuerzo), la base de neuronas y la fachada de funciones.
"""

try:
    from .rf_en_sbrtm_import1 import (
        LUCIA_RL_CONFIG,
        _dt,
        actualizar_config,
        HerramientasRefuerzo,
        NeuronaRefuerzoBase,
        GestorEntrenamientoRefuerzo,
        inicializar_pesos_he,
        inicializar_pesos_xavier,
        inicializar_pesos_lecun,
        inicializar_pesos_ortogonal,
        inicializar_pesos_espectral,
        inicializar_pesos_eficiente,
        layer_init,
        comparar_inicializaciones,
        calcular_recompensa_descontada,
        compute_returns,
        discount_cumulative_returns,
        normalizar_recompensas,
        calcular_gae,
        huber_loss,
        calcular_entropy,
        calcular_loss,
        mean_std_normalize,
        sample_gumbel_softmax,
        crear_buffer_experiencia,
        muestrear_buffer,
        crear_buffer_priorizado,
        muestrear_priorizado,
        actualizar_prioridades,
        aplicar_clip_gradientes,
        lr_scheduler,
        early_stopping_check,
        train_batch_neuron,
        train_epoch,
        parallel_train,
        get_optimizer,
        count_parameters,
        neuron_info,
        evaluate_neurona,
        analizar_convergencia,
        _Ring,
        _RingBufferNumpy,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "rf_en_sbrtm_import1", _os.path.join(_base, "rf_en_sbrtm_import1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LUCIA_RL_CONFIG = _mod.LUCIA_RL_CONFIG
    _dt = _mod._dt
    actualizar_config = _mod.actualizar_config
    HerramientasRefuerzo = _mod.HerramientasRefuerzo
    NeuronaRefuerzoBase = _mod.NeuronaRefuerzoBase
    GestorEntrenamientoRefuerzo = _mod.GestorEntrenamientoRefuerzo
    inicializar_pesos_he = _mod.inicializar_pesos_he
    inicializar_pesos_xavier = _mod.inicializar_pesos_xavier
    inicializar_pesos_lecun = _mod.inicializar_pesos_lecun
    inicializar_pesos_ortogonal = _mod.inicializar_pesos_ortogonal
    inicializar_pesos_espectral = _mod.inicializar_pesos_espectral
    inicializar_pesos_eficiente = _mod.inicializar_pesos_eficiente
    layer_init = _mod.layer_init
    comparar_inicializaciones = _mod.comparar_inicializaciones
    calcular_recompensa_descontada = _mod.calcular_recompensa_descontada
    compute_returns = _mod.compute_returns
    discount_cumulative_returns = _mod.discount_cumulative_returns
    normalizar_recompensas = _mod.normalizar_recompensas
    calcular_gae = _mod.calcular_gae
    huber_loss = _mod.huber_loss
    calcular_entropy = _mod.calcular_entropy
    calcular_loss = _mod.calcular_loss
    mean_std_normalize = _mod.mean_std_normalize
    sample_gumbel_softmax = _mod.sample_gumbel_softmax
    crear_buffer_experiencia = _mod.crear_buffer_experiencia
    muestrear_buffer = _mod.muestrear_buffer
    crear_buffer_priorizado = _mod.crear_buffer_priorizado
    muestrear_priorizado = _mod.muestrear_priorizado
    actualizar_prioridades = _mod.actualizar_prioridades
    aplicar_clip_gradientes = _mod.aplicar_clip_gradientes
    lr_scheduler = _mod.lr_scheduler
    early_stopping_check = _mod.early_stopping_check
    train_batch_neuron = _mod.train_batch_neuron
    train_epoch = _mod.train_epoch
    parallel_train = _mod.parallel_train
    get_optimizer = _mod.get_optimizer
    count_parameters = _mod.count_parameters
    neuron_info = _mod.neuron_info
    evaluate_neurona = _mod.evaluate_neurona
    analizar_convergencia = _mod.analizar_convergencia
    _Ring = _mod._Ring
    _RingBufferNumpy = _mod._RingBufferNumpy

__all__ = [
    "LUCIA_RL_CONFIG",
    "_dt",
    "actualizar_config",
    "HerramientasRefuerzo",
    "NeuronaRefuerzoBase",
    "GestorEntrenamientoRefuerzo",
    "inicializar_pesos_he",
    "inicializar_pesos_xavier",
    "inicializar_pesos_lecun",
    "inicializar_pesos_ortogonal",
    "inicializar_pesos_espectral",
    "inicializar_pesos_eficiente",
    "layer_init",
    "comparar_inicializaciones",
    "calcular_recompensa_descontada",
    "compute_returns",
    "discount_cumulative_returns",
    "normalizar_recompensas",
    "calcular_gae",
    "huber_loss",
    "calcular_entropy",
    "calcular_loss",
    "mean_std_normalize",
    "sample_gumbel_softmax",
    "crear_buffer_experiencia",
    "muestrear_buffer",
    "crear_buffer_priorizado",
    "muestrear_priorizado",
    "actualizar_prioridades",
    "aplicar_clip_gradientes",
    "lr_scheduler",
    "early_stopping_check",
    "train_batch_neuron",
    "train_epoch",
    "parallel_train",
    "get_optimizer",
    "count_parameters",
    "neuron_info",
    "evaluate_neurona",
    "analizar_convergencia",
    "_Ring",
    "_RingBufferNumpy",
]
