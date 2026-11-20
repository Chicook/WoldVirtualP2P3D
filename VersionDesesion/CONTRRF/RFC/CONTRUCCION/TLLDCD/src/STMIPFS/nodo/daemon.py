"""Daemon de Kubo lanzado por código: arranque, espera del API y parada.

No usa ``.bat``: arranca el binario en segundo plano con ``IPFS_PATH`` y espera
a que ``/api/v0/id`` responda. El PID y la salida van a ``datos/nodo.pid`` y
``datos/nodo.log``.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from . import cliente, repositorio, rutas

#: Segundos máximos que se espera al API tras arrancar.
ESPERA_MAXIMA = 45
#: Enteros de Python con los que se lanza el daemon.
FLAGS = ("--offline=false", "--migrate=true")


def _log() -> Path:
    """Abre (o crea) el archivo de log del daemon."""
    ruta = rutas.ruta_log()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta


def activo() -> bool:
    """True si el API responde ahora mismo."""
    return cliente.disponible()


def leer_pid() -> int | None:
    """PID guardado del daemon lanzado por nosotros."""
    try:
        return int(rutas.ruta_pid().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _guardar_pid(pid: int) -> None:
    """Escribe el PID de forma atómica."""
    ruta = rutas.ruta_pid()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(str(pid), encoding="utf-8")
    os.replace(temporal, ruta)


def esperar_api(segundos: int = ESPERA_MAXIMA) -> bool:
    """Espera a que el API conteste, comprobando cada medio segundo."""
    limite = time.monotonic() + max(1, segundos)
    while time.monotonic() < limite:
        if cliente.disponible(timeout=1.5):
            return True
        time.sleep(0.5)
    return False


def arrancar(esperar: int = ESPERA_MAXIMA, flags: tuple[str, ...] = FLAGS) -> dict:
    """Arranca el daemon si no está vivo y espera al API."""
    if activo():
        return {"ok": True, "arrancado": False, "motivo": "ya estaba en marcha"}
    if not rutas.ruta_binario().is_file():
        return {"ok": False, "motivo": "falta el binario de Kubo"}
    datos = repositorio.asegurar()
    if not datos.get("ok"):
        return {"ok": False, "motivo": f"repositorio: {datos.get('motivo')}"}
    entorno = os.environ.copy()
    entorno["IPFS_PATH"] = str(rutas.dir_repo())
    log = _log()
    try:
        with open(log, "ab") as salida:
            proceso = subprocess.Popen(
                [str(rutas.ruta_binario()), "daemon", *flags],
                env=entorno, stdout=salida, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        return {"ok": False, "motivo": f"no se pudo lanzar: {error}"}
    _guardar_pid(proceso.pid)
    if esperar_api(esperar):
        return {"ok": True, "arrancado": True, "pid": proceso.pid,
                "log": str(log)}
    return {"ok": False, "motivo": f"el API no respondió en {esperar}s",
            "pid": proceso.pid, "log": str(log)}


def parar(esperar: int = 10) -> dict:
    """Para el daemon: primero por API, y si no, terminando el PID."""
    detenido = False
    if activo():
        try:
            cliente._post("api/v0/shutdown", timeout=3)  # noqa: SLF001 - apagado
        except Exception:  # noqa: BLE001 - el daemon puede cortar la conexión
            pass
        limite = time.monotonic() + max(1, esperar)
        while time.monotonic() < limite and cliente.disponible(timeout=1):
            time.sleep(0.4)
        detenido = not cliente.disponible(timeout=1)
    pid = leer_pid()
    if pid and not detenido:
        try:
            os.kill(pid, 15)
            detenido = True
        except OSError:
            pass
    try:
        rutas.ruta_pid().unlink(missing_ok=True)
    except OSError:
        pass
    return {"ok": not cliente.disponible(timeout=1), "detenido": detenido}


def estado() -> dict:
    """Estado del daemon: activo, PID, peers y repositorio."""
    vivo = activo()
    datos = {"activo": vivo, "pid": leer_pid(), "log": str(rutas.ruta_log())}
    if vivo:
        try:
            datos["peer_id"] = cliente.identidad().get("ID", "")
            datos["peers"] = len(cliente.peers())
            datos["repo"] = cliente.estadisticas()
        except cliente.ErrorIPFS as error:
            datos["error"] = str(error)
    return datos
