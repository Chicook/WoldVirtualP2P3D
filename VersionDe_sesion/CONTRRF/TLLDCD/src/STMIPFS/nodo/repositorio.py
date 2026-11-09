"""Repositorio de Kubo: inicialización, comprobación y limpieza de bloqueos."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import rutas
from .cliente import ErrorIPFS


def _entorno() -> dict:
    """Entorno con ``IPFS_PATH`` apuntando al repositorio activo."""
    entorno = os.environ.copy()
    entorno["IPFS_PATH"] = str(rutas.dir_repo())
    return entorno


def _ejecutar(argumentos: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Ejecuta el binario con el repo activo; devuelve (código, salida, error)."""
    binario = rutas.ruta_binario()
    if not binario.is_file():
        return 127, "", f"falta el binario de Kubo en {binario}"
    try:
        proceso = subprocess.run([str(binario), *argumentos], env=_entorno(),
                                 capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return 1, "", str(error)
    return proceso.returncode, proceso.stdout or "", proceso.stderr or ""


def inicializado() -> bool:
    """True si el repositorio tiene ``config`` (está inicializado)."""
    return (rutas.dir_repo() / "config").is_file()


def inicializar(forzar: bool = False) -> dict:
    """Crea el repositorio con perfil ``server`` si falta."""
    if inicializado() and not forzar:
        return {"ok": True, "inicializado": True, "motivo": "ya existía"}
    rutas.dir_repo().mkdir(parents=True, exist_ok=True)
    codigo, salida, error = _ejecutar(["init", "--profile=server"], timeout=60)
    if codigo != 0 or not inicializado():
        return {"ok": False, "motivo": (error or salida or "init falló").strip()[:300]}
    return {"ok": True, "inicializado": True, "motivo": "creado"}


def leer_config() -> dict:
    """Configuración del repositorio (vacío si no se puede leer)."""
    try:
        datos = json.loads((rutas.dir_repo() / "config").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def version_repo() -> str:
    """Versión del formato de repositorio."""
    try:
        return str((rutas.dir_repo() / "version").read_text(encoding="utf-8")).strip()
    except OSError:
        return ""


def limpiar_bloqueos() -> dict:
    """Quita el ``repo.lock`` huérfano si no hay daemon escribiendo.

    Solo actúa si el archivo tiene más de un minuto: un bloqueo recién creado
    puede ser de un daemon que está arrancando.
    """
    import time

    bloqueo = rutas.dir_repo() / "repo.lock"
    if not bloqueo.exists():
        return {"ok": True, "limpiado": False}
    try:
        edad = time.time() - bloqueo.stat().st_mtime
    except OSError:
        return {"ok": False, "motivo": "no se pudo leer el bloqueo"}
    if edad < 60:
        return {"ok": False, "motivo": f"el bloqueo es reciente ({int(edad)}s)",
                "limpiado": False}
    try:
        bloqueo.unlink()
    except OSError as error:
        return {"ok": False, "motivo": str(error), "limpiado": False}
    return {"ok": True, "limpiado": True}


def estado() -> dict:
    """Resumen del repositorio."""
    config = leer_config()
    return {"repo": str(rutas.dir_repo()), "inicializado": inicializado(),
            "version": version_repo(),
            "peer_id": str((config.get("Identity") or {}).get("PeerID", "")),
            "api": str((config.get("Addresses") or {}).get("API", "")),
            "gateway": str((config.get("Addresses") or {}).get("Gateway", ""))}


def asegurar() -> dict:
    """Inicializa el repositorio si falta."""
    if inicializado():
        return {"ok": True, "inicializado": True, "motivo": "ya existía"}
    return inicializar()


def error_si_falta() -> None:
    """Lanza ``ErrorIPFS`` si el repositorio no está inicializado."""
    if not inicializado():
        raise ErrorIPFS("el repositorio IPFS no está inicializado")
