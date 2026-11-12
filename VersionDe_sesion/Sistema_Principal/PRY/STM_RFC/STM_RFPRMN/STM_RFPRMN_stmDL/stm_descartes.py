"""Modelos de IA local descartados: los que no pasaron los filtros.

Cuando ``ds ialocal`` rota porque el modelo devolvió código inválido, una salida
vacía o solo documentación, el modelo **se borra** con ``ollama rm`` y se apunta
aquí con el motivo. La lista se persiste, así que el siguiente flujo elige (y si
hace falta descarga) otro modelo de código distinto en vez de repetir el mismo.

Se guarda en ``.config/modelos_descartados.json`` junto a las opciones, fuera de
los árboles sincronizados.
"""
from __future__ import annotations

import json
from pathlib import Path

from .stm_base import advertir
from .stm_fs import escribir_texto_atomico
from .stm_rutas import ARCHIVO_OPCIONES


def ruta_descartados() -> Path:
    """JSON con los modelos borrados por no pasar los filtros."""
    return ARCHIVO_OPCIONES.parent / "modelos_descartados.json"


def leer_descartados() -> dict[str, str]:
    """Modelos descartados (nombre → motivo); vacío si no hay archivo."""
    try:
        datos = json.loads(ruta_descartados().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return {str(clave): str(valor) for clave, valor in datos.items()}


def _guardar(descartados: dict[str, str]) -> None:
    """Escribe la lista de forma atómica (best-effort)."""
    try:
        escribir_texto_atomico(ruta_descartados(),
                               json.dumps(descartados, ensure_ascii=False, indent=2))
    except OSError as error:
        advertir(f"No se pudo guardar la lista de descartados ({error}).")


def retirar_modelo(endpoint: str, modelo: str, motivo: str = "",
                   descartar: bool = False) -> bool:
    """Borra el modelo; con ``descartar`` además lo apunta para no repetirlo."""
    if not modelo:
        return False
    from .stm_modelos import _borrar_modelo_ollama  # diferido: evita el ciclo

    borrado = _borrar_modelo_ollama(endpoint, modelo)
    if descartar:
        descartados = leer_descartados()
        descartados[modelo] = motivo or "no pasó los filtros"
        _guardar(descartados)
    return borrado


def descartar_modelo(endpoint: str, modelo: str, motivo: str = "") -> bool:
    """Borra la IA local y la apunta para no volver a elegirla; True si la borró."""
    return retirar_modelo(endpoint, modelo, motivo, descartar=True)


def olvidar_descartados() -> None:
    """Vacía la lista (permite volver a probar los modelos descartados)."""
    _guardar({})
