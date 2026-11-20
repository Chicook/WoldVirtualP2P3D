"""Módulo de Gestión del Cerebro de LucIA 3D (.dev)
Gestiona el ciclo de vida, estado y conexión del puente socket
neuronal de LucIA (puerto 8765).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .entorno import configurar_variables_entorno, obtener_pythonw_activo, obtener_python_activo
from .rutas import LUCIA_DIR, LUCIA_SCRIPT


PUERTO_LUCIA_DEFECTO: int = 8765
OLLAMA_URL_DEFECTO: str = os.getenv("LUCIA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


def puerto_abierto(host: str = "127.0.0.1", puerto: int = PUERTO_LUCIA_DEFECTO, timeout: float = 0.5) -> bool:
    """Comprueba si el socket TCP está abierto y aceptando conexiones."""
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def probar_saludo_lucia(host: str = "127.0.0.1", puerto: int = PUERTO_LUCIA_DEFECTO, timeout: float = 1.2) -> Tuple[bool, str]:
    """Comprueba que LucIA conteste con el saludo o handshake inicial."""
    try:
        with socket.create_connection((host, puerto), timeout=timeout) as s:
            s.settimeout(timeout)
            datos = s.recv(1024).decode("utf-8", errors="ignore")
            if any(k in datos.lower() for k in ("hola", "listo", "saludo", "lucia")):
                return True, datos.strip()
            return True, datos.strip() if datos else "Conectado pero sin datos iniciales"
    except Exception as e:
        return False, str(e)


def consultar_estado_ollama(timeout: float = 1.5) -> Tuple[bool, List[str]]:
    """Comprueba si el daemon local de Ollama está escuchando y qué modelos tiene."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL_DEFECTO}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            if res.status == 200:
                datos = json.loads(res.read().decode("utf-8"))
                modelos = [str(m.get("name", "")) for m in datos.get("models", []) if m.get("name")]
                return True, modelos
    except Exception:
        pass
    return False, []


def estado_lucia(puerto: int = PUERTO_LUCIA_DEFECTO) -> Dict[str, Any]:
    """Devuelve un informe completo del estado del cerebro de LucIA."""
    abierto = puerto_abierto(puerto=puerto)
    listo, saludo = (False, "")
    if abierto:
        listo, saludo = probar_saludo_lucia(puerto=puerto)

    ollama_ok, modelos_ollama = consultar_estado_ollama()

    return {
        "puerto": puerto,
        "abierto": abierto,
        "listo": listo,
        "saludo": saludo,
        "ollama_activo": ollama_ok,
        "modelos_ollama": modelos_ollama,
        "script_existe": LUCIA_SCRIPT.is_file(),
        "ruta_script": str(LUCIA_SCRIPT),
    }


def detener_lucia() -> int:
    """Detiene cualquier proceso que esté ejecutando servidor_lucia.py."""
    detenidos = 0
    if sys.platform == "win32":
        try:
            cmd = (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -like '*servidor_lucia.py*' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
            detenidos += 1
        except Exception:
            pass
    return detenidos


def iniciar_lucia(
    puerto: int = PUERTO_LUCIA_DEFECTO,
    modelo: str = "qwen2.5:7b",
    segundo_plano: bool = True,
    sin_voz: bool = False,
    sin_precarga_voz: bool = True,
) -> Tuple[bool, str]:
    """Inicia el servidor de LucIA usando el Python canónico de .dev."""
    configurar_variables_entorno()

    if not LUCIA_SCRIPT.is_file():
        return False, f"No se encontró el script de LucIA: {LUCIA_SCRIPT}"

    if puerto_abierto(puerto=puerto):
        listo, _ = probar_saludo_lucia(puerto=puerto)
        if listo:
            return True, f"LucIA ya está escuchando y respondiendo en el puerto {puerto}."
        return False, f"El puerto {puerto} está ocupado por otro proceso."

    py_exe = obtener_pythonw_activo() if segundo_plano else obtener_python_activo()

    cmd = [
        str(py_exe),
        str(LUCIA_SCRIPT),
        "--puerto",
        str(puerto),
    ]
    if modelo:
        cmd.extend(["--modelo", modelo])
    if sin_voz:
        cmd.append("--sin-voz")
    if sin_precarga_voz:
        cmd.append("--sin-precarga-voz")

    env = os.environ.copy()

    try:
        if segundo_plano:
            flags = 0
            if sys.platform == "win32":
                flags |= subprocess.CREATE_NO_WINDOW
            proceso = subprocess.Popen(
                cmd,
                cwd=str(LUCIA_DIR),
                env=env,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(10):
                time.sleep(0.5)
                if puerto_abierto(puerto=puerto):
                    return True, f"Servidor LucIA iniciado (PID {proceso.pid}) en puerto {puerto}."
                if proceso.poll() is not None:
                    return False, f"El proceso terminó prematuramente con código {proceso.returncode}."

            return puerto_abierto(puerto=puerto), f"Proceso LucIA lanzado (PID {proceso.pid}), esperando..."
        else:
            res = subprocess.run(cmd, cwd=str(LUCIA_DIR), env=env)
            return res.returncode == 0, f"Proceso finalizado con código {res.returncode}"
    except Exception as e:
        return False, f"Error al iniciar servidor LucIA: {e}"


def reiniciar_lucia(puerto: int = PUERTO_LUCIA_DEFECTO, modelo: str = "qwen2.5:7b") -> Tuple[bool, str]:
    """Detiene y vuelve a iniciar el servidor de LucIA."""
    detener_lucia()
    time.sleep(1.0)
    return iniciar_lucia(puerto=puerto, modelo=modelo, segundo_plano=True)
