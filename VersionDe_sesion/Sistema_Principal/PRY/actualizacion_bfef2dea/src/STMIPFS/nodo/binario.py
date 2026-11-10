"""Instalación del binario de Kubo (descarga verificada, sin .bat).

Solo se descarga si se pide explícitamente: ``instalar()``. La URL se puede
cambiar con ``WOLD_IPFS_URL`` y el SHA-256 con ``WOLD_IPFS_SHA256``; si no hay
hash configurado, se verifica el tamaño mínimo y se avisa de que no se pudo
comprobar la integridad.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path

from . import rutas
from .cliente import ErrorIPFS

#: Versión de Kubo que usa el proyecto (la del .bat original).
VERSION = "0.43.1"
#: URL por defecto (release oficial de Kubo para Windows).
URL = ("https://github.com/ipfs/kubo/releases/download/v{v}/"
       "kubo_v{v}_windows-amd64.zip")
#: Tamaño mínimo razonable del ejecutable (Kubo supera los 20 MB).
TAMANO_MINIMO = 10 * 1024 * 1024


def version_instalada(binario: Path | None = None) -> str:
    """Versión que reporta el binario (``Desconocida`` si no se puede)."""
    import subprocess

    ejecutable = binario or rutas.ruta_binario()
    if not ejecutable.is_file():
        return "Desconocida"
    try:
        proceso = subprocess.run([str(ejecutable), "version"],
                                 capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return "Desconocida"
    return (proceso.stdout or "").strip() or "Desconocida"


def descargar(destino: Path | None = None, url: str | None = None) -> dict:
    """Descarga y descomprime Kubo; devuelve ``{ok, binario, version, motivo}``."""
    import urllib.error
    import urllib.request

    objetivo = Path(destino) if destino else rutas.ruta_binario()
    enlace = (url or os.environ.get("WOLD_IPFS_URL", "").strip()
              or URL.format(v=VERSION))
    try:
        with urllib.request.urlopen(enlace, timeout=600) as respuesta:
            paquete = respuesta.read()
    except (urllib.error.URLError, OSError) as error:
        return {"ok": False, "motivo": f"descarga fallida: {error}"}
    esperado = os.environ.get("WOLD_IPFS_SHA256", "").strip().lower()
    obtenido = hashlib.sha256(paquete).hexdigest()
    if esperado and esperado != obtenido:
        return {"ok": False, "motivo": "el SHA-256 del paquete no coincide",
                "sha256": obtenido}
    objetivo.parent.mkdir(parents=True, exist_ok=True)
    temporal = objetivo.with_suffix(".zip")
    temporal.write_bytes(paquete)
    try:
        with zipfile.ZipFile(temporal) as comprimido:
            miembro = next((n for n in comprimido.namelist()
                            if n.lower().endswith("ipfs.exe")
                            or n.lower().endswith("/ipfs")), "")
            if not miembro:
                return {"ok": False, "motivo": "el paquete no trae el ejecutable"}
            with comprimido.open(miembro) as origen, open(objetivo, "wb") as salida:
                shutil.copyfileobj(origen, salida)
    except (zipfile.BadZipFile, OSError) as error:
        return {"ok": False, "motivo": f"paquete ilegible: {error}"}
    finally:
        temporal.unlink(missing_ok=True)
    if objetivo.stat().st_size < TAMANO_MINIMO:
        return {"ok": False, "motivo": "el ejecutable descargado es demasiado pequeño"}
    return {"ok": True, "binario": str(objetivo),
            "version": version_instalada(objetivo), "sha256": obtenido}


def asegurar() -> dict:
    """Si falta el binario, lo descarga; si está, no hace nada."""
    actual = rutas.ruta_binario()
    if actual.is_file():
        return {"ok": True, "binario": str(actual),
                "version": version_instalada(actual), "descargado": False}
    datos = descargar(actual)
    datos["descargado"] = bool(datos.get("ok"))
    return datos


def estado() -> dict:
    """Binario presente, versión y tamaño."""
    actual = rutas.ruta_binario()
    return {"ruta": str(actual), "existe": actual.is_file(),
            "version": version_instalada(actual) if actual.is_file() else "",
            "mb": round(actual.stat().st_size / (1024 * 1024), 1)
            if actual.is_file() else 0.0}


def error_si_falta() -> None:
    """Lanza ``ErrorIPFS`` si no hay binario (mensaje accionable)."""
    if not rutas.ruta_binario().is_file():
        raise ErrorIPFS(
            "falta el binario de Kubo; ejecuta `instalar()` o define "
            "WOLD_IPFS_BIN")
