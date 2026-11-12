"""Pesos de LucIA y del agente en IPFS: se suben al cerrar, se bajan al iniciar.

- **Al cerrar**: empaqueta en un ``.zip`` los pesos de la red
  (``.modelos/lucia_rn_*.pkl``), el historial del agente (``agente.json``) y la
  memoria del ``seq2seq`` (``seq2seq.json``), lo sube con ``stm_ipfs`` y guarda
  el CID y el SHA-256 en ``.modelos/ipfs_pesos.json``.
- **Al iniciar**: si faltan los pesos locales y el puntero tiene un CID de
  verdad, descarga el paquete, comprueba el SHA-256 y lo restaura.

Honestidad: sin daemon de IPFS el CID que devuelve ``stm_ipfs`` es local y no se
puede descargar; en ese caso se informa y no se pierde nada, porque los pesos
siguen en disco.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from .stm_base import advertir, exito, informar
from .stm_fs import escribir_texto_atomico
from .stm_ipfs import subir_a_ipfs, url_pasarela
from .stm_rutas import DIR_MODELOS_LOCAL

#: Carpeta de pesos y puntero del último paquete subido.
RUTA_AGENTE = DIR_MODELOS_LOCAL / "agente.json"
RUTA_PUNTERO = DIR_MODELOS_LOCAL / "ipfs_pesos.json"


def _escribir_bytes(destino: Path, datos: bytes) -> None:
    """Escritura atómica de bytes (los ``.pkl`` no pueden pasar por texto)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    temporal.write_bytes(datos)
    os.replace(temporal, destino)


def _archivos() -> list[Path]:
    """Archivos de estado que viajan en el paquete (los que existan)."""
    candidatos: list[Path] = []
    candidatos += sorted(DIR_MODELOS_LOCAL.glob("lucia_rn_*.pkl"))
    for nombre in ("agente.json", "seq2seq.json"):
        ruta = DIR_MODELOS_LOCAL / nombre
        if ruta.is_file():
            candidatos.append(ruta)
    for extra in sorted(DIR_MODELOS_LOCAL.glob("*.json")):
        if extra.name != RUTA_PUNTERO.name and extra not in candidatos:
            candidatos.append(extra)
    return [ruta for ruta in candidatos if ruta.is_file()]


def empaquetar() -> tuple[bytes, list[str]]:
    """Devuelve ``(zip, nombres)`` con el estado actual de los pesos."""
    archivos = _archivos()
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as paquete:
        for archivo in archivos:
            paquete.write(archivo, arcname=archivo.name)
    return memoria.getvalue(), [archivo.name for archivo in archivos]


def guardar_historial(historial: dict) -> Path | None:
    """Persiste el historial del agente (calidad media e intentos por acción)."""
    try:
        escribir_texto_atomico(
            RUTA_AGENTE,
            json.dumps(historial, ensure_ascii=False, indent=2))
    except OSError as error:
        advertir(f"No se pudo guardar el historial del agente ({error}).")
        return None
    return RUTA_AGENTE


def cargar_historial() -> dict:
    """Historial guardado (vacío si no existe o está corrupto)."""
    try:
        datos = json.loads(RUTA_AGENTE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(datos, dict):
        return {}
    limpio: dict[str, list[float]] = {}
    for accion, valores in datos.items():
        if isinstance(valores, list) and len(valores) == 2:
            try:
                limpio[str(accion)] = [float(valores[0]), int(valores[1])]
            except (TypeError, ValueError):
                continue
    return limpio


def leer_puntero() -> dict:
    """Puntero del último paquete subido (vacío si no hay)."""
    try:
        datos = json.loads(RUTA_PUNTERO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def subir() -> dict:
    """Empaqueta los pesos, los sube a IPFS y deja el puntero."""
    contenido, nombres = empaquetar()
    if not nombres:
        informar("No hay pesos que subir a IPFS todavía.")
        return {"ok": False, "motivo": "sin pesos"}
    temporal = DIR_MODELOS_LOCAL / "pesos_ipfs.zip"
    try:
        _escribir_bytes(temporal, contenido)
        recibo = subir_a_ipfs(temporal)
    except OSError as error:
        advertir(f"No se pudo preparar el paquete de pesos ({error}).")
        return {"ok": False, "motivo": str(error)}
    puntero = {
        "cid": recibo.get("cid", ""), "via": recibo.get("via", ""),
        "modo": recibo.get("modo", ""), "sha256": hashlib.sha256(contenido).hexdigest(),
        "archivos": nombres, "bytes": len(contenido),
        "fecha": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    try:
        escribir_texto_atomico(RUTA_PUNTERO,
                               json.dumps(puntero, ensure_ascii=False, indent=2))
    except OSError as error:
        advertir(f"No se pudo anotar el CID ({error}).")
    return {"ok": True, **puntero}


def descargar(cid: str | None = None, destino: Path | None = None) -> dict:
    """Descarga el paquete del CID, verifica el SHA-256 y restaura los archivos."""
    puntero = leer_puntero()
    elegido = cid or str(puntero.get("cid", ""))
    if not elegido:
        return {"ok": False, "motivo": "sin CID de IPFS"}
    if not cid and puntero.get("modo") == "local-sin-daemon":
        return {"ok": False, "motivo": "el CID es local: IPFS no tenía daemon"}
    carpeta = Path(destino) if destino else DIR_MODELOS_LOCAL
    try:
        with urllib.request.urlopen(url_pasarela(elegido), timeout=120) as respuesta:
            datos = respuesta.read()
    except (urllib.error.URLError, OSError) as error:
        return {"ok": False, "motivo": f"no se pudo descargar ({error})"}
    esperado = str(puntero.get("sha256", ""))
    if esperado and hashlib.sha256(datos).hexdigest() != esperado:
        return {"ok": False, "motivo": "el SHA-256 no coincide: no se restaura"}
    restaurados: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as paquete:
            for nombre in paquete.namelist():
                if "/" in nombre or nombre.startswith("."):
                    continue  # sin rutas: solo archivos sueltos
                _escribir_bytes(carpeta / nombre, paquete.read(nombre))
                restaurados.append(nombre)
    except (zipfile.BadZipFile, OSError) as error:
        return {"ok": False, "motivo": f"paquete ilegible ({error})"}
    exito(f"Pesos restaurados desde IPFS: {', '.join(restaurados)}")
    return {"ok": True, "cid": elegido, "archivos": restaurados}


def sincronizar_al_iniciar() -> dict:
    """Si faltan pesos locales y hay un CID real, los trae de IPFS."""
    if list(DIR_MODELOS_LOCAL.glob("lucia_rn_*.pkl")):
        return {"ok": True, "motivo": "pesos locales presentes"}
    puntero = leer_puntero()
    if not puntero.get("cid"):
        return {"ok": False, "motivo": "sin puntero de IPFS"}
    return descargar()


def estado() -> dict:
    """Resumen para diagnósticos."""
    puntero = leer_puntero()
    return {"pesos": len(_archivos()), "cid": puntero.get("cid", ""),
            "via": puntero.get("via", ""), "modo": puntero.get("modo", ""),
            "archivos": puntero.get("archivos", []),
            "fecha": puntero.get("fecha", "")}
