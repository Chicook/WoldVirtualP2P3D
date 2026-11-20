# -*- coding: utf-8 -*-
"""
Cargador volátil en RAM para el paquete de actualización del visor.

Espejo en Python del VolatilePackage de C#. Recibe los bytes del .zip
embebido en el ejecutable (no su ruta: el zip nunca se escribe suelto) y:

  • Configuración  (config/cuenta.json, config/sesion.yaml,
    config/version.json, manifest.json)  -> SOLO en RAM (dict/str).
  • Mundo y modelos (mundo/wvp3d.pck, lucia/*) -> materialización mínima
    en un directorio temporal único. Godot 4 exige una ruta de fichero
    para --main-pack y onnxruntime necesita rutas en disco; no es posible
    montarlos desde un stream puro.

Uso típico (Lucía recibe los bytes por IPC desde el proceso C#):

    import cargador_volatil as cv
    cv.montar_paquete(bytes_del_zip)
    cfg = cv.config_cuenta()          # dict en RAM
    pck = cv.ruta_pck()               # ruta temporal (o None)
    ...
    cv.liberar()                      # purga RAM + directorio temporal

Como CLI (solo para verificación local):

    python cargador_volatil.py ruta/al/actualizacion_v2.8.1.zip
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

_ESTADO: dict = {
    "tmpdir": None,      # directorio temporal raíz
    "pck": None,         # ruta temporal del pck
    "cuenta": None,      # dict en RAM
    "sesion": None,      # dict en RAM
    "version": None,     # dict en RAM
    "manifest": None,    # dict en RAM
}

_PCK_RUTA = "mundo/wvp3d.pck"
_CONFIG_JSON = ("config/cuenta.json", "config/version.json", "manifest.json")
_CONFIG_YAML = ("config/sesion.yaml",)


def _normalizar(ruta: str) -> str:
    return ruta.replace("\\", "/").lstrip("/")


def _leer_entrada(archivo: zipfile.ZipFile, nombre: str) -> bytes:
    with archivo.open(nombre) as f:
        return f.read()


def _parsear_yaml(texto: str) -> dict:
    """YAML mínimo para sesion.yaml (clave: valor plano, sin anidados)."""
    out: dict = {}
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea or ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        out[clave] = valor
    return out


def montar_paquete(datos: bytes) -> bool:
    """Monta el zip desde bytes en RAM. Devuelve True si hay pck materializado."""
    liberar()

    bio = io.BytesIO(datos)
    tmpdir = tempfile.mkdtemp(prefix="wvp_vol_")
    _ESTADO["tmpdir"] = tmpdir

    with zipfile.ZipFile(bio) as archivo:
        for nombre in archivo.namelist():
            limpio = _normalizar(nombre)
            if not limpio or limpio.endswith("/"):
                continue

            destino = os.path.normpath(os.path.join(tmpdir, limpio))
            if not destino.startswith(os.path.abspath(tmpdir) + os.sep):
                continue  # zip-slip

            if limpio in _CONFIG_JSON:
                texto = _leer_entrada(archivo, nombre).decode("utf-8")
                if limpio == "config/cuenta.json":
                    _ESTADO["cuenta"] = json.loads(texto)
                elif limpio == "config/version.json":
                    _ESTADO["version"] = json.loads(texto)
                elif limpio == "manifest.json":
                    _ESTADO["manifest"] = json.loads(texto)
            elif limpio in _CONFIG_YAML:
                texto = _leer_entrada(archivo, nombre).decode("utf-8")
                _ESTADO["sesion"] = _parsear_yaml(texto)
            else:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, "wb") as f:
                    f.write(_leer_entrada(archivo, nombre))
                if limpio == _PCK_RUTA:
                    _ESTADO["pck"] = destino

    return _ESTADO["pck"] is not None


def liberar() -> None:
    """Purga RAM y borra el directorio temporal (mejor esfuerzo)."""
    for clave in ("cuenta", "sesion", "version", "manifest", "pck"):
        _ESTADO[clave] = None
    tmpdir = _ESTADO.get("tmpdir")
    if tmpdir and os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir, ignore_errors=True)
    _ESTADO["tmpdir"] = None


def config_cuenta() -> dict | None:
    return _ESTADO["cuenta"]


def config_sesion() -> dict | None:
    return _ESTADO["sesion"]


def ruta_pck() -> str | None:
    return _ESTADO["pck"]


def dir_temporal() -> str | None:
    return _ESTADO["tmpdir"]


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("uso: python cargador_volatil.py <zip>", file=sys.stderr)
        return 2
    with open(argv[1], "rb") as f:
        datos = f.read()
    ok = montar_paquete(datos)
    print("montado:", ok)
    print("cuenta:", config_cuenta())
    print("sesion:", config_sesion())
    print("pck:", ruta_pck())
    liberar()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
