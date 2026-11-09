"""Rutas del nodo IPFS: una sola fuente para binario, repositorio y datos.

Todo se puede redefinir por entorno, que es lo que necesita una instalación
portable (y las pruebas):

- ``WOLD_IPFS_BIN``: ruta al ejecutable de Kubo.
- ``IPFS_PATH``: repositorio (``config``, ``blocks``, ``datastore``).
- ``WOLD_IPFS_DATOS``: carpeta de punteros y paquetes de pesos.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Raíz del paquete STMIPFS.
DIR_STMIPFS = Path(__file__).resolve().parents[1]
#: Repositorio por defecto del proyecto (no el ``~/.ipfs`` global).
DIR_REPO = DIR_STMIPFS / ".ipfs"
#: Datos propios del nodo (punteros, paquetes, log).
DIR_DATOS = DIR_REPO / "datos"


def dir_repo() -> Path:
    """Repositorio IPFS: ``IPFS_PATH`` o el del proyecto."""
    entorno = os.environ.get("IPFS_PATH", "").strip()
    return Path(entorno).expanduser() if entorno else DIR_REPO


def dir_datos() -> Path:
    """Carpeta de datos del nodo (se crea al usarla)."""
    entorno = os.environ.get("WOLD_IPFS_DATOS", "").strip()
    return Path(entorno).expanduser() if entorno else DIR_DATOS


def ruta_binario() -> Path:
    """Ejecutable de Kubo: ``WOLD_IPFS_BIN``, PATH o dentro de STMIPFS."""
    entorno = os.environ.get("WOLD_IPFS_BIN", "").strip()
    if entorno:
        return Path(entorno).expanduser()
    import shutil

    for nombre in ("ipfs", "ipfs.exe"):
        encontrado = shutil.which(nombre)
        if encontrado:
            return Path(encontrado)
    for candidato in (DIR_STMIPFS / "ipfs.exe", DIR_STMIPFS / "ipfs",
                      DIR_STMIPFS / "kubo" / "ipfs.exe"):
        if candidato.exists():
            return candidato
    return DIR_STMIPFS / "ipfs.exe"


def ruta_log() -> Path:
    """Archivo de log del daemon."""
    return dir_datos() / "nodo.log"


def ruta_pid() -> Path:
    """Archivo con el PID del daemon lanzado por nosotros."""
    return dir_datos() / "nodo.pid"


def ruta_puntero() -> Path:
    """Puntero con el CID y el SHA-256 del último paquete de pesos."""
    return dir_datos() / "pesos.json"


def describir() -> dict:
    """Rutas activas y de dónde salen (para diagnósticos)."""
    return {"binario": str(ruta_binario()), "binario_existe": ruta_binario().is_file(),
            "repo": str(dir_repo()), "repo_existe": dir_repo().is_dir(),
            "datos": str(dir_datos()), "log": str(ruta_log())}
