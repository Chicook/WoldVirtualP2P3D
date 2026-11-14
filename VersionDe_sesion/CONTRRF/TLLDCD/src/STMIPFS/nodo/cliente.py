"""Cliente de la API HTTP v0 de Kubo (Kubo escucha en 127.0.0.1:5001).

Solo stdlib: ``urllib`` con multipart construido a mano. Todas las llamadas
devuelven datos ya parseados y lanzan ``ErrorIPFS`` con el motivo real
(daemon apagado, timeout, CID inválido, respuesta sin Hash).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

#: Endpoint local del API (se puede cambiar con ``WOLD_IPFS_API``).
API = "http://127.0.0.1:5001"


class ErrorIPFS(Exception):
    """Fallo controlado del nodo IPFS."""


def api_url(entorno: str | None = None) -> str:
    """URL del API (entorno o valor por defecto)."""
    import os

    return (entorno or os.environ.get("WOLD_IPFS_API", "").strip() or API).rstrip("/")


def _post(ruta: str, cuerpo: bytes | None = None, tipo: str = "",
          timeout: float = 60.0) -> bytes:
    """POST al API v0; devuelve el cuerpo de la respuesta."""
    cabeceras = {"Content-Type": tipo} if tipo else {}
    peticion = urllib.request.Request(f"{api_url()}/{ruta.lstrip('/')}",
                                      data=cuerpo if cuerpo is not None else b"",
                                      headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return respuesta.read()
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", "replace")[:300]
        raise ErrorIPFS(f"API {ruta}: HTTP {error.code} {detalle}") from error
    except (urllib.error.URLError, OSError) as error:
        raise ErrorIPFS(f"API {ruta} inaccesible: {error}") from error


def disponible(timeout: float = 2.0) -> bool:
    """True si el daemon responde (``/api/v0/id``)."""
    try:
        _post("api/v0/id", timeout=timeout)
        return True
    except ErrorIPFS:
        return False


def identidad(timeout: float = 3.0) -> dict:
    """PeerID y versión del nodo."""
    datos = json.loads(_post("api/v0/id", timeout=timeout).decode("utf-8", "replace"))
    if not isinstance(datos, dict):
        raise ErrorIPFS("respuesta inesperada de /id")
    return datos


def agregar(datos: bytes, nombre: str, timeout: float = 120.0) -> str:
    """Sube ``datos`` (con pin) y devuelve el CID."""
    frontera = f"----wvp{uuid.uuid4().hex}"
    cuerpo = (
        f"--{frontera}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{nombre}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + datos + f"\r\n--{frontera}--\r\n".encode("utf-8")
    respuesta = _post("api/v0/add?pin=true&cid-version=1", cuerpo,
                      f"multipart/form-data; boundary={frontera}", timeout)
    for linea in respuesta.decode("utf-8", "replace").splitlines():
        if not linea.strip():
            continue
        try:
            evento = json.loads(linea)
        except ValueError:
            continue
        if isinstance(evento, dict) and evento.get("Hash"):
            return str(evento["Hash"])
    raise ErrorIPFS("el API no devolvió Hash al añadir")


def leer(cid: str, timeout: float = 120.0) -> bytes:
    """Descarga el contenido de un CID (``/api/v0/cat``)."""
    if not cid or "/" in cid or " " in cid:
        raise ErrorIPFS(f"CID inválido: {cid!r}")
    return _post(f"api/v0/cat?arg={cid}", timeout=timeout)


def pin(cid: str, quitar: bool = False) -> bool:
    """Fija (o suelta) un CID; True si el API lo acepta."""
    _post(f"api/v0/pin/{'rm' if quitar else 'add'}?arg={cid}")
    return True


def estadisticas() -> dict[str, Any]:
    """Tamaño del repositorio y número de objetos."""
    datos = json.loads(_post("api/v0/repo/stat").decode("utf-8", "replace"))
    return datos if isinstance(datos, dict) else {}


def peers(timeout: float = 5.0) -> list:
    """Lista de peers conectados."""
    datos = json.loads(_post("api/v0/swarm/peers", timeout=timeout)
                       .decode("utf-8", "replace"))
    return datos.get("Peers", []) if isinstance(datos, dict) else []
