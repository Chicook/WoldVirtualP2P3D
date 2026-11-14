"""Publicación del registro de actualización y limpieza del directorio.

Flujo al completarse ``actualizar``:

1. Lee los eventos de ``stm_registro_json/STM_RFC/envios.json`` y redacta
   ``registro.md`` en lenguaje natural (qué se hizo, cuántos ficheros).
2. Borra el json.
3. Convierte el md en pesos neuronales (``stm_pesos``).
4. Sube los pesos a IPFS (``stm_ipfs``, cuatro niveles).
5. Borra md y pesos: el directorio queda limpio.

Los cálculos viven en :mod:`stm_pesos` y la subida en :mod:`stm_ipfs`; aquí se
re-exportan para no romper la fachada ni el registro de símbolos.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .stm_base import (
    E, advertir, exito, informar, reportar_error, MODULO_DIR, _imprimir_seguro,
)
from .stm_ipfs import (  # noqa: F401  (re-exportados)
    IPFS_API_URL, IPFS_GATEWAY_URL, subir_a_ipfs, url_pasarela,
)
from .stm_pesos import (  # noqa: F401  (re-exportados)
    DIM_VECTOR, NOMBRE_PESOS, cuantizar, desnormalizar, norma, seccionar_md,
    similitud_coseno, texto_a_vector,
)
from .stm_pesos import md_a_pesos as _md_a_pesos
from .stm_pesos import verificar_pesos as _verificar_pesos

#: Carpeta de registro del sistema (queda vacía tras publicar).
DIR_REGISTRO = MODULO_DIR / "stm_registro_json"
#: El registro de envíos vive en el espejo STM_RFC (viaja con la herramienta).
RUTA_JSON = DIR_REGISTRO / "STM_RFC" / "envios.json"
RUTA_MD = DIR_REGISTRO / "registro.md"
RUTA_PESOS = DIR_REGISTRO / NOMBRE_PESOS


def _ahora() -> str:
    """Marca temporal actual en formato ISO (segundos)."""
    return datetime.now().isoformat(timespec="seconds")


def leer_eventos() -> list[dict]:
    """Lee los eventos pendientes de envios.json ([] si no hay o falla)."""
    try:
        if RUTA_JSON.exists():
            datos = json.loads(RUTA_JSON.read_text(encoding="utf-8"))
            return datos if isinstance(datos, list) else []
    except (OSError, ValueError) as error:
        advertir(f"No se pudo leer envios.json ({error}).")
    return []


def construir_texto(eventos: list[dict], info: dict) -> str:
    """Redacta en lenguaje natural lo que se hizo al actualizar.

    ``eventos`` son los registros históricos de envios.json e ``info``
    describe la operación actual (origen, destino, ficheros, purgadas).
    """
    lineas = ["# Registro de actualización", "",
              f"El {info.get('fecha', _ahora())} actualicé el sistema:",
              f"copié {info.get('ficheros', 0)} ficheros verificados desde "
              f"{info.get('origen', '?')} hasta {info.get('destino', '?')}.",
              ""]
    purgadas = info.get("purgadas", [])
    if purgadas:
        lineas.append("Al hacerlo purgué las versiones anteriores de PRY: "
                      + ", ".join(str(p) for p in purgadas) + ".")
        lineas.append("")
    else:
        lineas.append("No había versiones anteriores de PRY que purgar.")
        lineas.append("")
    lineas.append("Después vacié RFC por completo para dejarlo listo para el "
                  "siguiente ciclo de trabajo.")
    lineas.append("")
    if eventos:
        lineas.append("## Historial previo (envios.json)")
        lineas.append("")
        for ev in eventos:
            lineas.append(f"- El {ev.get('fecha', '?')} se procesó "
                          f"'{ev.get('carpeta', '?')}' "
                          f"({ev.get('ficheros', '?')} ficheros) con estado "
                          f"'{ev.get('estado', '?')}'.")
        lineas.append("")
    lineas.append("El directorio de registro queda limpio: este documento se "
                  "convirtió en pesos neuronales y se subió a IPFS.")
    return "\n".join(lineas) + "\n"


def md_a_pesos(ruta_md: Path = RUTA_MD, ruta_pesos: Path = RUTA_PESOS) -> dict:
    """Convierte ``registro.md`` en pesos neuronales (ver :mod:`stm_pesos`)."""
    return _md_a_pesos(ruta_md, ruta_pesos)


def verificar_pesos(ruta_pesos: Path = RUTA_PESOS, umbral: float = 0.999) -> bool:
    """Verifica la integridad de unos pesos (ver :mod:`stm_pesos`)."""
    return _verificar_pesos(ruta_pesos, umbral)


def vista_previa(info: dict) -> str:
    """Muestra cómo quedaría registro.md sin escribir ni publicar nada.

    Útil para revisar la redacción antes de un ``actualizar`` real.
    Devuelve el texto generado.
    """
    datos_info = dict(info)
    datos_info.setdefault("fecha", _ahora())
    texto = construir_texto(leer_eventos(), datos_info)
    _imprimir_seguro(f"{E.negrita}Vista previa de registro.md{E.reset} "
                     f"({len(texto.splitlines())} líneas, "
                     f"{len(texto_a_vector(texto))} pesos):")
    _imprimir_seguro(texto)
    return texto


def _borrar_si_existe(ruta: Path) -> bool:
    """Borra ``ruta`` si existe; True si ya no queda rastro."""
    try:
        if ruta.exists():
            if ruta.is_dir():
                objetivo = str(ruta)
                if os.name == "nt" and not objetivo.startswith("\\\\?\\"):
                    objetivo = "\\\\?\\" + objetivo
                shutil.rmtree(objetivo, ignore_errors=True)
            else:
                ruta.unlink()
        return not ruta.exists()
    except OSError as error:
        advertir(f"No se pudo borrar {ruta.name} ({error}).")
        return False


def limpiar_caches() -> dict[str, bool]:
    """Borra las cachés de bytecode de la herramienta al cerrar el ciclo.

    Elimina __pycache__/ de STM_RFPRMN y STM_RFPRMN_stmDL más
    .pycache_rfprmn (se recrean solas en la próxima ejecución).
    """
    objetivos = [MODULO_DIR / "__pycache__",
                 MODULO_DIR / "STM_RFPRMN_stmDL" / "__pycache__",
                 MODULO_DIR / ".pycache_rfprmn"]
    estado = {p.relative_to(MODULO_DIR).as_posix(): _borrar_si_existe(p)
              for p in objetivos}
    if all(estado.values()):
        exito("Cachés de bytecode eliminadas.")
    return estado


def limpiar_registro() -> dict[str, bool]:
    """Borra json, md y pesos del registro; devuelve estado por archivo."""
    estado = {p.name: _borrar_si_existe(p)
              for p in (RUTA_JSON, RUTA_MD, RUTA_PESOS)}
    if all(estado.values()):
        exito(f"Directorio limpio: {DIR_REGISTRO.name} vacío.")
    else:
        pendientes = [n for n, ok in estado.items() if not ok]
        reportar_error(f"Limpieza parcial, pendientes: {pendientes}.")
    return estado


def publicar_registro_actualizar(info: dict) -> dict:
    """Publica lo ocurrido al actualizar y deja el directorio limpio.

    ``info`` trae origen, destino, ficheros y purgadas. Flujo:
    envios.json -> registro.md -> borra json -> pesos -> IPFS ->
    borra md y pesos. Devuelve el recibo de subida.
    """
    DIR_REGISTRO.mkdir(parents=True, exist_ok=True)
    eventos = leer_eventos()
    datos_info = dict(info)
    datos_info.setdefault("fecha", _ahora())
    RUTA_MD.write_text(construir_texto(eventos, datos_info), encoding="utf-8")
    informar(f"Registro redactado en lenguaje natural: {RUTA_MD.name}")
    _borrar_si_existe(RUTA_JSON)
    informar("envios.json borrado tras redactar el registro.")
    md_a_pesos()
    recibo = subir_a_ipfs(RUTA_PESOS)
    _borrar_si_existe(RUTA_MD)
    _borrar_si_existe(RUTA_PESOS)
    informar("registro.md convertido en pesos, subido y borrado.")
    limpiar_registro()
    limpiar_caches()
    _imprimir_seguro(f"{E.verde}✔{E.reset} Actualización publicada en IPFS: "
                     f"{recibo.get('cid')}")
    if recibo.get("via") != "local":
        _imprimir_seguro(f"Recuperable en: {url_pasarela(str(recibo.get('cid', '')))}")
    return {"recibo": recibo, "ficheros": datos_info.get("ficheros", 0),
            "purgadas": datos_info.get("purgadas", [])}
