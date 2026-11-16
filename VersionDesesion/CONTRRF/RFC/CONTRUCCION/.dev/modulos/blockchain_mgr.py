"""Módulo de Gestión de Blockchain Local (STM_BKCH) (.dev)
Gestiona el ciclo de vida, estado e integridad del Servidor Oficial de Cuentas
y Blockchain Neuronal (puerto 8545).
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from .entorno import configurar_variables_entorno, obtener_python_activo
from .rutas import BLOCKCHAIN_DIR, BLOCKCHAIN_SCRIPT, LEDGER_PATH, PSNRL_DIR


PUERTO_BLOCKCHAIN_DEFECTO: int = 8545
URL_BLOCKCHAIN_DEFECTO: str = f"http://127.0.0.1:{PUERTO_BLOCKCHAIN_DEFECTO}"


def puerto_abierto(host: str = "127.0.0.1", puerto: int = PUERTO_BLOCKCHAIN_DEFECTO, timeout: float = 0.5) -> bool:
    """Comprueba si el socket TCP está abierto y aceptando conexiones."""
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def consultar_estado_http(puerto: int = PUERTO_BLOCKCHAIN_DEFECTO, timeout: float = 2.0) -> Tuple[bool, Dict[str, Any]]:
    """Consulta el endpoint /status del servidor oficial de blockchain."""
    url = f"http://127.0.0.1:{puerto}/status"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WVP-DevManager/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            if res.status == 200:
                datos = json.loads(res.read().decode("utf-8"))
                return True, datos
    except Exception as e:
        return False, {"error": str(e)}
    return False, {"error": "Respuesta no exitosa"}


def validar_ledger_en_disco() -> Tuple[bool, int, str]:
    """Valida la existencia y estructura básica del archivo ledger oficial en disco."""
    if not LEDGER_PATH.is_file():
        return False, 0, f"No existe el archivo ledger en {LEDGER_PATH}"

    try:
        contenido = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        total = contenido.get("total_bloques", len(contenido.get("cadena", [])))
        return True, total, f"Ledger válido con {total} bloques en disco."
    except Exception as e:
        return False, 0, f"Error al leer ledger: {e}"


def estado_blockchain(puerto: int = PUERTO_BLOCKCHAIN_DEFECTO) -> Dict[str, Any]:
    """Devuelve un informe completo del estado del servidor blockchain."""
    abierto = puerto_abierto(puerto=puerto)
    ok_http, info = (False, {})
    if abierto:
        ok_http, info = consultar_estado_http(puerto=puerto)

    ledger_ok, total_bloques, msg_ledger = validar_ledger_en_disco()

    return {
        "puerto": puerto,
        "abierto": abierto,
        "responde_http": ok_http,
        "info_http": info,
        "ledger_ok": ledger_ok,
        "total_bloques_ledger": total_bloques,
        "detalle_ledger": msg_ledger,
        "script_existe": BLOCKCHAIN_SCRIPT.is_file(),
        "ruta_script": str(BLOCKCHAIN_SCRIPT),
    }


def detener_blockchain() -> int:
    """Detiene cualquier proceso que esté ejecutando servidor_oficial.py."""
    detenidos = 0
    if sys.platform == "win32":
        try:
            cmd = (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -like '*servidor_oficial.py*' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
            detenidos += 1
        except Exception:
            pass
    return detenidos


def iniciar_blockchain(
    puerto: int = PUERTO_BLOCKCHAIN_DEFECTO,
    segundo_plano: bool = True,
    sin_cuota_ubicacion: bool = True,
) -> Tuple[bool, str]:
    """Inicia el servidor oficial de blockchain usando el Python canónico de .dev."""
    configurar_variables_entorno()

    if not BLOCKCHAIN_SCRIPT.is_file():
        return False, f"No se encontró el script oficial: {BLOCKCHAIN_SCRIPT}"

    if puerto_abierto(puerto=puerto):
        ok, info = consultar_estado_http(puerto=puerto)
        if ok:
            return True, f"El servidor blockchain ya está activo y respondiendo en el puerto {puerto}."
        return False, f"El puerto {puerto} está ocupado por otro proceso."

    py_exe = obtener_python_activo()

    cmd = [
        str(py_exe),
        str(BLOCKCHAIN_SCRIPT),
        "--puerto",
        str(puerto),
    ]
    if sin_cuota_ubicacion:
        cmd.append("--sin-cuota-ubicacion")

    env = os.environ.copy()

    try:
        if segundo_plano:
            flags = 0
            if sys.platform == "win32":
                flags |= subprocess.CREATE_NO_WINDOW
            proceso = subprocess.Popen(
                cmd,
                cwd=str(BLOCKCHAIN_DIR),
                env=env,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Esperar hasta 4 segundos para comprobar si abrió el puerto
            for _ in range(8):
                time.sleep(0.5)
                if puerto_abierto(puerto=puerto):
                    return True, f"Servidor Blockchain iniciado correctamente (PID {proceso.pid}) en puerto {puerto}."
                if proceso.poll() is not None:
                    return False, f"El proceso terminó prematuramente con código {proceso.returncode}."

            return puerto_abierto(puerto=puerto), f"Proceso lanzado (PID {proceso.pid}), esperando respuesta..."
        else:
            res = subprocess.run(cmd, cwd=str(BLOCKCHAIN_DIR), env=env)
            return res.returncode == 0, f"Proceso finalizado con código {res.returncode}"
    except Exception as e:
        return False, f"Error al iniciar servidor blockchain: {e}"


def reiniciar_blockchain(puerto: int = PUERTO_BLOCKCHAIN_DEFECTO) -> Tuple[bool, str]:
    """Detiene y vuelve a iniciar el servidor blockchain oficial."""
    detener_blockchain()
    time.sleep(1.0)
    return iniciar_blockchain(puerto=puerto, segundo_plano=True)
