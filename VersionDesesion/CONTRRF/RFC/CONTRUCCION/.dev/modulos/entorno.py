"""Módulo de Configuración de Entorno y Variables del Sistema (.dev)
Centraliza la preparación de variables de entorno, configuración de VS Code y Pytest.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .rutas import (
    DEV_DIR,
    DEV_PYTEST_INI,
    PRY_DIR,
    PYCACHE_DIR,
    PYTEST_CACHE_DIR,
    PYTHON_DIR,
    PYTHON_EXE,
    PYTHONW_EXE,
    REPO_ROOT,
    RFC_DIR,
    RUFF_CACHE_DIR,
    STM_RFC_DIR,
    TLLDCD_SRC,
    VENV_DIR,
    VENV_PYTHON,
    VENV_PYTHONW,
    VSCODE_DIR,
)


def obtener_python_activo() -> Path:
    """Devuelve el ejecutable de Python prioritario (.python > venv > sys.executable)."""
    if PYTHON_EXE.is_file():
        return PYTHON_EXE
    if VENV_PYTHON.is_file():
        return VENV_PYTHON
    return Path(sys.executable)


def obtener_pythonw_activo() -> Path:
    """Devuelve el ejecutable de Python sin ventana prioritario."""
    if PYTHONW_EXE.is_file():
        return PYTHONW_EXE
    if VENV_PYTHONW.is_file():
        return VENV_PYTHONW
    return PYTHON_EXE if PYTHON_EXE.is_file() else Path(sys.executable)


def configurar_variables_entorno() -> Dict[str, str]:
    """Configura las variables de entorno para que todo el sistema use las rutas canónicas de .dev."""
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    PYTEST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RUFF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PYCACHE_DIR.mkdir(parents=True, exist_ok=True)

    py_activo = obtener_python_activo()

    nuevos_valores = {
        "VIRTUAL_ENV": str(VENV_DIR),
        "PYTHONHOME": str(PYTHON_DIR),
        "WVP_PYTHON": str(py_activo),
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",  # Evita errores de registro/seguridad en Windows
        "PYTEST_CACHE_DIR": str(PYTEST_CACHE_DIR),
        "RUFF_CACHE_DIR": str(RUFF_CACHE_DIR),
        # Todo bytecode compilado del ecosistema se escribe en .dev/pycache
        "PYTHONPYCACHEPREFIX": str(PYCACHE_DIR),
        "RFPRMN_RFC_DIR": str(RFC_DIR),
        "RFPRMN_PRY_DIR": str(PRY_DIR),
        "WVP_DEV_DIR": str(DEV_DIR),
        "WVP_SRC": str(TLLDCD_SRC),
    }

    for clave, valor in nuevos_valores.items():
        os.environ[clave] = valor

    # Añadir .python y Scripts del venv al PATH del proceso actual
    py_dir = str(PYTHON_DIR)
    scripts_dir = str(VENV_DIR / "Scripts")
    path_actual = os.environ.get("PATH", "")
    elementos_path = [py_dir, scripts_dir] + [
        p for p in path_actual.split(os.pathsep) if p not in (py_dir, scripts_dir)
    ]
    os.environ["PATH"] = os.pathsep.join(elementos_path)

    # Inyectar rutas en sys.path
    for p in (str(TLLDCD_SRC), str(STM_RFC_DIR), str(DEV_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)

    return nuevos_valores


def traer_pytest_ini() -> bool:
    """Trae pytest.ini desde la raíz del repositorio hacia .dev/pytest.ini."""
    ini_raiz = REPO_ROOT / "pytest.ini"
    ini_dev = DEV_PYTEST_INI

    contenido_canonico = (
        "[pytest]\n"
        "cache_dir = .pytest_cache\n"
        "testpaths = ../TLLDCD/src/tests ../STM_RFC/STM_RFPRMN/tests\n"
        "pythonpath = ../TLLDCD/src ../STM_RFC/STM_RFPRMN ../../../../..\n"
        "python_files = test_*.py\n"
        "python_classes = Test*\n"
        "python_functions = test_*\n"
    )

    movido = False
    if ini_raiz.is_file():
        try:
            ini_dev.write_text(contenido_canonico, encoding="utf-8")
            ini_raiz.unlink()
            movido = True
            print(f"[OK] pytest.ini traído a: {ini_dev}")
            print(f"[OK] Archivo suelto eliminado de la raíz: {ini_raiz}")
        except Exception as err:
            print(f"[AVISO] Error al mover pytest.ini de raíz a .dev: {err}")
    elif not ini_dev.is_file():
        ini_dev.write_text(contenido_canonico, encoding="utf-8")
        movido = True
        print(f"[OK] pytest.ini inicializado en: {ini_dev}")

    return movido


def actualizar_vscode_config() -> Path:
    """Actualiza .dev/.vscode/settings.json y launch.json con intérpretes canónicos."""
    VSCODE_DIR.mkdir(parents=True, exist_ok=True)
    settings_file = VSCODE_DIR / "settings.json"
    launch_file = VSCODE_DIR / "launch.json"

    py_exe_str = str(PYTHON_EXE).replace("\\", "/")
    dev_dir_str = str(DEV_DIR).replace("\\", "/")
    pytest_ini_str = str(DEV_PYTEST_INI).replace("\\", "/")
    pytest_cache_str = str(PYTEST_CACHE_DIR).replace("\\", "/")

    config = {
        "python.defaultInterpreterPath": py_exe_str,
        "python.pythonPath": py_exe_str,
        "python-envs.defaultEnvManager": "ms-python.python:system",
        "python.analysis.extraPaths": [
            str(TLLDCD_SRC).replace("\\", "/"),
            str(STM_RFC_DIR).replace("\\", "/"),
            dev_dir_str,
            str(REPO_ROOT).replace("\\", "/"),
        ],
        "python.autoComplete.extraPaths": [
            str(TLLDCD_SRC).replace("\\", "/"),
            str(STM_RFC_DIR).replace("\\", "/"),
            dev_dir_str,
            str(REPO_ROOT).replace("\\", "/"),
        ],
        "python.testing.pytestEnabled": True,
        "python.testing.unittestEnabled": False,
        "python.testing.pytestArgs": [
            "-c", pytest_ini_str,
            "-o", f"cache_dir={pytest_cache_str}",
        ],
        "terminal.integrated.env.windows": {
            "PYTHONHOME": str(PYTHON_DIR),
            "WVP_PYTHON": str(PYTHON_EXE),
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "PYTEST_CACHE_DIR": str(PYTEST_CACHE_DIR),
            "RUFF_CACHE_DIR": str(RUFF_CACHE_DIR),
            "PYTHONPYCACHEPREFIX": str(PYCACHE_DIR),
            "RFPRMN_RFC_DIR": str(RFC_DIR),
            "RFPRMN_PRY_DIR": str(PRY_DIR),
        }
    }

    settings_file.write_text(json.dumps(config, indent=4, ensure_ascii=False), encoding="utf-8")

    launch_config = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "RFPRMN (Fachada .dev)",
                "type": "debugpy",
                "request": "launch",
                "program": str(STM_RFC_DIR / "RFPRMN.py").replace("\\", "/"),
                "python": py_exe_str,
                "args": ["--arranque"],
                "console": "integratedTerminal",
                "cwd": str(STM_RFC_DIR).replace("\\", "/")
            },
            {
                "name": "Gestor Entorno (.dev)",
                "type": "debugpy",
                "request": "launch",
                "program": str(DEV_DIR / "gestor_entorno.py").replace("\\", "/"),
                "python": py_exe_str,
                "args": ["sincronizar"],
                "console": "integratedTerminal",
                "cwd": dev_dir_str
            },
            {
                "name": "Pytest (.dev)",
                "type": "debugpy",
                "request": "launch",
                "module": "pytest",
                "python": py_exe_str,
                "args": ["-c", pytest_ini_str, "-o", f"cache_dir={pytest_cache_str}"],
                "console": "integratedTerminal",
                "cwd": dev_dir_str
            }
        ]
    }
    launch_file.write_text(json.dumps(launch_config, indent=4, ensure_ascii=False), encoding="utf-8")

    return settings_file


def limpiar_cache_raiz() -> bool:
    """Si se generó algún .pytest_cache o .ruff_cache en la raíz, lo limpia."""
    borrado = False
    for nombre in (".pytest_cache", ".ruff_cache"):
        cache_raiz = REPO_ROOT / nombre
        if cache_raiz.is_dir():
            try:
                shutil.rmtree(cache_raiz, ignore_errors=True)
                borrado = True
            except Exception:
                pass
    return borrado


def ejecutar_pytest(args: Optional[List[str]] = None) -> int:
    """Ejecuta pytest forzando que se use .dev/pytest.ini y cache_dir=.dev/.pytest_cache."""
    configurar_variables_entorno()
    traer_pytest_ini()
    limpiar_cache_raiz()

    py = obtener_python_activo()
    args_completos = [
        str(py),
        "-m",
        "pytest",
        "-c",
        str(DEV_PYTEST_INI),
        "-o",
        f"cache_dir={PYTEST_CACHE_DIR}",
    ]
    if args:
        args_completos.extend(args)
    else:
        args_completos.append(str(TLLDCD_SRC / "tests"))

    resultado = subprocess.run(args_completos, cwd=str(REPO_ROOT))
    limpiar_cache_raiz()
    traer_pytest_ini()
    return resultado.returncode
