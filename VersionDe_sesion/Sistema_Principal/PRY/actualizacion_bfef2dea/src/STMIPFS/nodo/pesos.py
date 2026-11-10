"""Pesos neuronales en IPFS: publicar con el API, recuperar con el API.

Formato del paquete: un ``.zip`` con los archivos de estado y un sobre JSON
(``indice.json``) dentro con nombre, SHA-256 y fecha. El puntero local
(``datos/pesos.json``) guarda el CID, el SHA-256 y la lista de archivos, para
poder verificar la descarga.

Si el nodo no está disponible, ``publicar`` deja el paquete en disco y devuelve
``ok=False`` con el motivo; nunca inventa un CID.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from . import cliente, rutas

#: Nombre del sobre con el índice dentro del paquete.
INDICE = "indice.json"


def _escribir_bytes(destino: Path, datos: bytes) -> None:
    """Escritura atómica de bytes (los ``.pkl`` son binarios)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    temporal.write_bytes(datos)
    os.replace(temporal, destino)


def empaquetar(archivos: list[Path]) -> tuple[bytes, list[str]]:
    """Empaqueta los archivos existentes en un zip con su índice."""
    validos = [archivo for archivo in archivos if archivo.is_file()]
    memoria = io.BytesIO()
    indice = {"fecha": _dt.datetime.now().isoformat(timespec="seconds"),
              "archivos": [], "sha256": {}}
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as paquete:
        for archivo in validos:
            datos = archivo.read_bytes()
            paquete.writestr(archivo.name, datos)
            indice["archivos"].append(archivo.name)
            indice["sha256"][archivo.name] = hashlib.sha256(datos).hexdigest()
        paquete.writestr(INDICE, json.dumps(indice, ensure_ascii=False, indent=2))
    return memoria.getvalue(), indice["archivos"]


def leer_puntero() -> dict:
    """Puntero local del último paquete publicado."""
    try:
        datos = json.loads(rutas.ruta_puntero().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def publicar(archivos: list[Path], nombre: str = "pesos.zip") -> dict:
    """Empaqueta, sube al nodo y apunta el CID; ``ok=False`` si no hay nodo."""
    contenido, incluidos = empaquetar(archivos)
    if not incluidos:
        return {"ok": False, "motivo": "no hay archivos que publicar"}
    sha = hashlib.sha256(contenido).hexdigest()
    paquete_local = rutas.dir_datos() / nombre
    _escribir_bytes(paquete_local, contenido)
    if not cliente.disponible():
        return {"ok": False, "motivo": "el daemon IPFS no está activo",
                "paquete": str(paquete_local), "sha256": sha,
                "archivos": incluidos}
    try:
        cid = cliente.agregar(contenido, nombre)
    except cliente.ErrorIPFS as error:
        return {"ok": False, "motivo": str(error), "paquete": str(paquete_local),
                "sha256": sha, "archivos": incluidos}
    puntero = {"cid": cid, "sha256": sha, "archivos": incluidos,
               "bytes": len(contenido), "paquete": str(paquete_local),
               "fecha": _dt.datetime.now().isoformat(timespec="seconds")}
    _escribir_bytes(rutas.ruta_puntero(),
                    json.dumps(puntero, ensure_ascii=False, indent=2).encode("utf-8"))
    return {"ok": True, **puntero}


def recuperar(cid: str | None = None, destino: Path | None = None) -> dict:
    """Descarga el paquete, verifica SHA-256 y restaura los archivos."""
    puntero = leer_puntero()
    elegido = (cid or "").strip() or str(puntero.get("cid", ""))
    if not elegido:
        return {"ok": False, "motivo": "sin CID: no hay nada publicado"}
    if not cliente.disponible():
        return {"ok": False, "motivo": "el daemon IPFS no está activo"}
    try:
        datos = cliente.leer(elegido)
    except cliente.ErrorIPFS as error:
        return {"ok": False, "motivo": str(error)}
    esperado = str(puntero.get("sha256", "")) if not cid else ""
    if esperado and hashlib.sha256(datos).hexdigest() != esperado:
        return {"ok": False, "motivo": "el SHA-256 no coincide: no se restaura"}
    carpeta = Path(destino) if destino else rutas.dir_datos()
    restaurados: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as paquete:
            for nombre in paquete.namelist():
                if nombre == INDICE or "/" in nombre or nombre.startswith("."):
                    continue
                _escribir_bytes(carpeta / nombre, paquete.read(nombre))
                restaurados.append(nombre)
    except (zipfile.BadZipFile, OSError) as error:
        return {"ok": False, "motivo": f"paquete ilegible: {error}"}
    return {"ok": True, "cid": elegido, "archivos": restaurados}


def estado() -> dict:
    """Puntero y paquete local."""
    puntero = leer_puntero()
    return {"cid": puntero.get("cid", ""), "archivos": puntero.get("archivos", []),
            "sha256": puntero.get("sha256", ""), "fecha": puntero.get("fecha", ""),
            "paquete": puntero.get("paquete", "")}
