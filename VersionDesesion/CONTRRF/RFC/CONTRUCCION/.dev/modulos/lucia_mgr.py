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
from .rutas import DEV_DIR, LUCIA_DIR, LUCIA_SCRIPT


PUERTO_LUCIA_DEFECTO: int = 8765
OLLAMA_URL_DEFECTO: str = os.getenv("LUCIA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
PID_FILE_LUCIA = DEV_DIR / ".pids" / "lucia.pid"


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
    """Detiene el proceso del servidor de LucIA mediante verificación segura de PID y ejecutable.
    Elimina por completo el uso de comodines PowerShell para prevenir terminación no intencionada."""
    detenidos = 0
    pids_a_verificar: list[int] = []

    # 1. Leer PID desde archivo de tracking si existe
    if PID_FILE_LUCIA.is_file():
        try:
            pid_txt = PID_FILE_LUCIA.read_text(encoding="utf-8").strip()
            if pid_txt.isdigit():
                pids_a_verificar.append(int(pid_txt))
        except Exception:
            pass

    # 2. Localizar PID escuchando en el puerto si psutil está disponible
    try:
        import psutil
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == PUERTO_LUCIA_DEFECTO and conn.status == psutil.CONN_LISTEN:
                if conn.pid and conn.pid not in pids_a_verificar:
                    pids_a_verificar.append(conn.pid)
    except Exception:
        pass

    # 3. Verificar de forma estricta y terminar únicamente procesos autenticados
    for pid in pids_a_verificar:
        try:
            import psutil
            if not psutil.pid_exists(pid):
                continue
            proc = psutil.Process(pid)
            nombre = proc.name().lower()
            cmdline = " ".join(proc.cmdline()).lower()

            if "python" in nombre and "servidor_lucia.py" in cmdline:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except psutil.TimeoutExpired:
                    proc.kill()
                detenidos += 1
        except Exception:
            # Fallback seguro Win32 sin comodines: únicamente por PID verificado
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=False)
                    detenidos += 1
            except Exception:
                pass

    if PID_FILE_LUCIA.is_file():
        try:
            PID_FILE_LUCIA.unlink(missing_ok=True)
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
            # Registrar PID de forma segura
            try:
                PID_FILE_LUCIA.parent.mkdir(parents=True, exist_ok=True)
                PID_FILE_LUCIA.write_text(f"{proceso.pid}\n", encoding="utf-8")
            except Exception:
                pass

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
