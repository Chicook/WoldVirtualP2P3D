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
    DEV_GITHUB_DIR,
    DEV_GITHUB_WORKFLOWS_DIR,
    DEV_PYTEST_INI,
    PRY_DIR,
    PYCACHE_DIR,
    PYTEST_CACHE_DIR,
    PYTHON_DIR,
    PYTHON_EXE,
    PYTHONW_EXE,
    REPO_GITHUB_DIR,
    REPO_GITHUB_WORKFLOWS_DIR,
    REPO_ROOT,
    RFC_DIR,
    RUFF_CACHE_DIR,
    STM_RFC_DIR,
    TLLDCD_SRC,
    VENV_DIR,
    VENV_PYTHON,
    VENV_PYTHONW,
    VSCODE_DIR,
    asegurar_ruta_en_repositorio,
)


def obtener_python_activo(estricto: bool = False) -> Path:
    """Devuelve el ejecutable de Python prioritario (.python > venv).
    Si estricto=True, rechaza caer a sys.executable si no está contenido en .dev."""
    if PYTHON_EXE.is_file():
        return PYTHON_EXE
    if VENV_PYTHON.is_file():
        return VENV_PYTHON

    interp_actual = Path(sys.executable).resolve()
    dev_res = DEV_DIR.resolve()
    es_contenido = dev_res in interp_actual.parents

    if estricto and not es_contenido:
        raise RuntimeError(
            f"[VIOLACIÓN DE AISLAMIENTO ZERO TRUST] Fallback a sys.executable bloqueado: "
            f"'{interp_actual}' reside fuera del entorno aislado '{dev_res}'. "
            f"Instale las dependencias en .dev/.python o .dev/venv."
        )

    if not es_contenido:
        print(
            f"[AVISO SEGURIDAD ENTORNO] Fallback temporal a sys.executable ({interp_actual}) fuera de .dev. "
            f"Se recomienda utilizar el entorno aislado canónico en {DEV_DIR}.",
            file=sys.stderr
        )

    return interp_actual


def obtener_pythonw_activo(estricto: bool = False) -> Path:
    """Devuelve el ejecutable de Python sin ventana prioritario."""
    if PYTHONW_EXE.is_file():
        return PYTHONW_EXE
    if VENV_PYTHONW.is_file():
        return VENV_PYTHONW
    if PYTHON_EXE.is_file():
        return PYTHON_EXE
    return obtener_python_activo(estricto=estricto)


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
        "PYTEST_ADDOPTS": f"-o cache_dir={PYTEST_CACHE_DIR} -c {DEV_PYTEST_INI}",
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
    """Trae pytest.ini desde la raíz del repositorio hacia .dev/pytest.ini con salvaguardas Zero-Trust."""
    ini_raiz = (REPO_ROOT / "pytest.ini").resolve()
    ini_dev = DEV_PYTEST_INI.resolve()

    # Validar que ambas rutas pertenezcan de forma estricta a REPO_ROOT
    if not (asegurar_ruta_en_repositorio(ini_raiz) and asegurar_ruta_en_repositorio(ini_dev)):
        raise PermissionError("[VIOLACIÓN DE FRONTERA] Ruta de pytest.ini inválida o fuera del repositorio.")

    contenido_canonico = (
        "[pytest]\n"
        "cache_dir = .pytest_cache\n"
        "testpaths = tests ../TLLDCD/src/tests ../STM_RFC/STM_RFPRMN/tests\n"
        "pythonpath = ../TLLDCD/src ../STM_RFC/STM_RFPRMN ../../../../.. .\n"
        "python_files = test_*.py\n"
        "python_classes = Test*\n"
        "python_functions = test_*\n"
    )

    movido = False
    if ini_raiz.is_file():
        # Salvaguarda: Verificar que no sea un enlace simbólico que apunte fuera
        if ini_raiz.is_symlink():
            try:
                ini_raiz.unlink()
                movido = True
            except Exception as err:
                print(f"[AVISO] Error al eliminar symlink pytest.ini: {err}")
        else:
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


def sincronizar_github_workflows(eliminar_de_raiz: bool = True, exportar_a_raiz: bool = False) -> Dict[str, Any]:
    """Centraliza los workflows de CI/CD en .dev/.github y elimina la carpeta suelta de la raíz.

    Salvaguarda la filosofía del proyecto: toda configuración de desarrollo,
    archivos .yml y dependencias se alojan estrictamente en .dev (.dev/.github).
    Si exportar_a_raiz=True, permite desplegarlos temporalmente en la raíz para CI remoto.
    Por defecto, asegura que todo esté guardado en .dev y elimina la carpeta .github de la raíz.
    """
    DEV_GITHUB_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

    resultado: Dict[str, Any] = {
        "canonicos": [],
        "eliminados_de_raiz": False,
        "exportados_a_raiz": False,
        "errores": [],
    }

    # 1. Absorber y asegurar cualquier workflow de la raíz hacia .dev/.github
    if REPO_GITHUB_WORKFLOWS_DIR.is_dir():
        for ruta_raiz in REPO_GITHUB_WORKFLOWS_DIR.glob("*.yml"):
            destino_dev = DEV_GITHUB_WORKFLOWS_DIR / ruta_raiz.name
            if not destino_dev.exists() or ruta_raiz.stat().st_mtime > destino_dev.stat().st_mtime:
                try:
                    shutil.copy2(ruta_raiz, destino_dev)
                    resultado["canonicos"].append(destino_dev.name)
                except Exception as err:
                    resultado["errores"].append(f"Error al absorber {ruta_raiz.name} hacia .dev: {err}")
            else:
                resultado["canonicos"].append(destino_dev.name)

    # Registrar todos los workflows canónicos presentes en .dev
    for ruta_dev in DEV_GITHUB_WORKFLOWS_DIR.glob("*.yml"):
        resultado["canonicos"].append(ruta_dev.name)

    # 2. Manejo de la carpeta en la raíz del repositorio
    if exportar_a_raiz:
        REPO_GITHUB_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
        for ruta_dev in DEV_GITHUB_WORKFLOWS_DIR.glob("*.yml"):
            destino_raiz = REPO_GITHUB_WORKFLOWS_DIR / ruta_dev.name
            try:
                shutil.copy2(ruta_dev, destino_raiz)
            except Exception as err:
                resultado["errores"].append(f"Error al exportar {ruta_dev.name} a raíz: {err}")
        resultado["exportados_a_raiz"] = True
    elif eliminar_de_raiz and REPO_GITHUB_DIR.is_dir():
        # Verificar que todos los workflows de raíz estén respaldados en .dev antes de borrar
        archivos_raiz = list(REPO_GITHUB_WORKFLOWS_DIR.glob("*.yml")) if REPO_GITHUB_WORKFLOWS_DIR.is_dir() else []
        seguro_para_borrar = True
        for arch in archivos_raiz:
            if not (DEV_GITHUB_WORKFLOWS_DIR / arch.name).is_file():
                seguro_para_borrar = False
                resultado["errores"].append(f"No se borra .github de raíz: {arch.name} no está en .dev")
                break
        if seguro_para_borrar:
            try:
                shutil.rmtree(REPO_GITHUB_DIR)
                resultado["eliminados_de_raiz"] = True
            except Exception as err:
                resultado["errores"].append(f"Error al eliminar .github de la raíz: {err}")

    # Deduplicar
    resultado["canonicos"] = sorted(list(set(resultado["canonicos"])))
    return resultado


def buscar_archivos_dev_desperdigados() -> List[Dict[str, str]]:
    """Detecta archivos .yml, configuraciones o artefactos de desarrollo fuera de .dev."""
    desperdigados = []
    patrones_sospechosos = ["*.yml", "*.yaml", "pytest.ini", "tox.ini", ".ruff.toml"]

    dirs_a_revisar = [
        REPO_ROOT / "VersionDesesion" / "CONTRRF" / "RFC" / "CONTRUCCION" / "TLLDCD" / "src",
        REPO_ROOT / "VersionDesesion" / "CONTRRF" / "RFC" / "CONTRUCCION" / "STM_RFC",
    ]
    for d in dirs_a_revisar:
        if not d.is_dir():
            continue
        for patron in patrones_sospechosos:
            for arch in d.rglob(patron):
                rel = str(arch.relative_to(REPO_ROOT))
                desperdigados.append({
                    "archivo": rel,
                    "tipo": patron,
                    "sugerencia": "Reubicar en .dev o gestionar desde gestor_entorno.py",
                })
    return desperdigados


def actualizar_vscode_config() -> Path:
    """Actualiza .dev/.vscode/settings.json y launch.json con rutas portables dinámicas."""
    VSCODE_DIR.mkdir(parents=True, exist_ok=True)
    settings_file = VSCODE_DIR / "settings.json"
    launch_file = VSCODE_DIR / "launch.json"

    # Configuración portable utilizando ${workspaceFolder}
    config = {
        "python.defaultInterpreterPath": "${workspaceFolder}/.python/python.exe",
        "python.pythonPath": "${workspaceFolder}/.python/python.exe",
        "python-envs.defaultEnvManager": "ms-python.python:system",
        "python.analysis.extraPaths": [
            "${workspaceFolder}/../TLLDCD/src",
            "${workspaceFolder}/../STM_RFC/STM_RFPRMN",
            "${workspaceFolder}",
            "${workspaceFolder}/../../../../.."
        ],
        "python.autoComplete.extraPaths": [
            "${workspaceFolder}/../TLLDCD/src",
            "${workspaceFolder}/../STM_RFC/STM_RFPRMN",
            "${workspaceFolder}",
            "${workspaceFolder}/../../../../.."
        ],
        "python.testing.pytestEnabled": True,
        "python.testing.unittestEnabled": False,
        "python.testing.pytestArgs": [
            "-c", "${workspaceFolder}/pytest.ini",
            "-o", "cache_dir=${workspaceFolder}/.pytest_cache",
        ],
        "terminal.integrated.env.windows": {
            "PYTHONHOME": "${workspaceFolder}/.python",
            "WVP_PYTHON": "${workspaceFolder}/.python/python.exe",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "PYTEST_CACHE_DIR": "${workspaceFolder}/.pytest_cache",
            "RUFF_CACHE_DIR": "${workspaceFolder}/.ruff_cache",
            "PYTHONPYCACHEPREFIX": "${workspaceFolder}/pycache",
            "RFPRMN_RFC_DIR": "${workspaceFolder}/..",
            "RFPRMN_PRY_DIR": "${workspaceFolder}/../../../../SistemaPrincipal/PRY"
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
                "program": "${workspaceFolder}/../STM_RFC/STM_RFPRMN/RFPRMN.py",
                "python": "${workspaceFolder}/.python/python.exe",
                "args": ["--arranque"],
                "console": "integratedTerminal",
                "cwd": "${workspaceFolder}/../STM_RFC/STM_RFPRMN"
            },
            {
                "name": "Gestor Entorno (.dev)",
                "type": "debugpy",
                "request": "launch",
                "program": "${workspaceFolder}/gestor_entorno.py",
                "python": "${workspaceFolder}/.python/python.exe",
                "args": ["sincronizar"],
                "console": "integratedTerminal",
                "cwd": "${workspaceFolder}"
            },
            {
                "name": "Pytest (.dev)",
                "type": "debugpy",
                "request": "launch",
                "module": "pytest",
                "python": "${workspaceFolder}/.python/python.exe",
                "args": ["-c", "${workspaceFolder}/pytest.ini", "-o", "cache_dir=${workspaceFolder}/.pytest_cache"],
                "console": "integratedTerminal",
                "cwd": "${workspaceFolder}"
            }
        ]
    }
    launch_file.write_text(json.dumps(launch_config, indent=4, ensure_ascii=False), encoding="utf-8")

    return settings_file


def limpiar_cache_raiz() -> bool:
    """Si se generó algún .pytest_cache o .ruff_cache en la raíz, lo limpia con salvaguardas Zero Trust."""
    borrado = False
    directorios_permitidos = {".pytest_cache", ".ruff_cache"}

    for nombre in directorios_permitidos:
        cache_raiz = (REPO_ROOT / nombre).resolve()

        # Salvaguardas críticas:
        # 1. El nombre debe ser estrictamente uno de los directorios de caché permitidos
        if cache_raiz.name not in directorios_permitidos:
            continue
        # 2. Debe ser hijo directo de REPO_ROOT (nunca REPO_ROOT ni directorios superiores)
        if cache_raiz.parent != REPO_ROOT.resolve():
            continue
        # 3. Validar contención en repositorio
        if not asegurar_ruta_en_repositorio(cache_raiz):
            continue

        if cache_raiz.is_symlink():
            try:
                cache_raiz.unlink()
                borrado = True
            except Exception as err:
                print(f"[AVISO SEGURIDAD] Error al desvincular symlink de caché {cache_raiz}: {err}")
        elif cache_raiz.is_dir():
            try:
                shutil.rmtree(cache_raiz)
                borrado = True
            except Exception as err:
                print(f"[AVISO SEGURIDAD] Error al limpiar caché {cache_raiz}: {err}")

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
        for a in args:
            if not a.startswith("-"):
                p_dev = DEV_DIR / a
                p_root = REPO_ROOT / a
                if p_dev.exists():
                    args_completos.append(str(p_dev))
                elif p_root.exists():
                    args_completos.append(str(p_root))
                else:
                    args_completos.append(a)
            else:
                args_completos.append(a)
    else:
        args_completos.append(str(DEV_DIR / "tests"))

    resultado = subprocess.run(args_completos, cwd=str(REPO_ROOT))
    limpiar_cache_raiz()
    traer_pytest_ini()
    return resultado.returncode
