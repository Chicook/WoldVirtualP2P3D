"""Capa de aprendizaje por recompensa de celebro_3D.

Convierte la calidad de la interaccion 3D (rubrica + RPLC) en una senal de
recompensa que entrena las neuronas REALES de refuerzo (RF_EN/RF_SL) del
sistema principal y persiste los pesos en el PSNRL principal.

No sustituye a las copias propias de celebro_3D: solo anade cableado encima.
El punto de entrada es :func:`aplicar_turno`, llamado desde NucleoLucia.
"""
from .aprendizaje import (
    aplicar_turno,
    calcular_recompensa,
    mapear_estado_accion,
    estado_refuerzo,
    ETIQUETA_REFUERZO,
)

__all__ = [
    "aplicar_turno",
    "calcular_recompensa",
    "mapear_estado_accion",
    "estado_refuerzo",
    "ETIQUETA_REFUERZO",
]