"""Catalogo de las herramientas de STM_HRTS/utils.

Cada script suelto del directorio de herramientas se describe aqui a partir de
su propio fichero (tipo por extension, resumen del encabezado y si necesita
ventana). El comando se resuelve con las rutas de `STM_HRTS.rutas`, de modo que
ninguna herramienta depende de donde este el arbol ni de una ruta absoluta
escrita a mano.

Uso desde Python:
    from STM_HRTS.herramientas import catalogo, comando, ejecutar
    ejecutar("probar_shapekeys")

Uso desde la consola:
    python -m STM_HRTS herramientas
    python -m STM_HRTS ejecutar probar_shapekeys
"""
from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from STM_HRTS import rutas


class ErrorHerramienta(RuntimeError):
    """La herramienta no existe, no tiene comando o falta su interprete."""


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    archivo: Path
    tipo: str
    resumen: str
    headless: bool = True
    extra: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def relativa(self) -> str:
        return str(self.archivo.relative_to(rutas.SRC_DIR)).replace("\\", "/")


def _resumen_gd(archivo: Path) -> str:
    partes: List[str] = []
    for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines()[:12]:
        texto = linea.strip()
        if texto.startswith("##"):
            trozo = texto.lstrip("#").strip()
            if trozo:
                partes.append(trozo)
        elif partes and not texto.startswith("#"):
            break
    return " ".join(partes)


def _resumen_py(archivo: Path) -> str:
    try:
        arbol = ast.parse(archivo.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return ""
    doc = ast.get_docstring(arbol) or ""
    for linea in doc.splitlines():
        if linea.strip():
            return linea.strip()
    return ""


def _resumen_plano(archivo: Path, prefijos: Sequence[str]) -> str:
    for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines()[:12]:
        texto = linea.strip()
        bajo = texto.lower()
        for prefijo in prefijos:
            if bajo.startswith(prefijo):
                trozo = texto[len(prefijo):].strip()
                if trozo:
                    return trozo
    return ""


TIPO_POR_SUFIJO = {
    ".gd": "godot",
    ".py": "python",
    ".ps1": "powershell",
    ".bat": "cmd",
    ".sh": "shell",
}

# Los scripts de captura y render necesitan ventana: sin `--headless` y con
# salida grafica. El resto de pruebas y validadores corren en modo headless.
NECESITA_VENTANA = ("capturar_", "render_")


def _describir(archivo: Path) -> Optional[Herramienta]:
    tipo = TIPO_POR_SUFIJO.get(archivo.suffix.lower())
    if tipo is None:
        return None
    if tipo == "godot":
        resumen = _resumen_gd(archivo)
    elif tipo == "python":
        resumen = _resumen_py(archivo)
    elif tipo == "powershell":
        resumen = _resumen_plano(archivo, ("#",))
    elif tipo == "shell":
        resumen = _resumen_plano(archivo, ("#",))
    else:
        resumen = _resumen_plano(archivo, ("rem ", "@rem "))
    return Herramienta(
        nombre=archivo.stem,
        archivo=archivo,
        tipo=tipo,
        resumen=resumen,
        headless=not archivo.stem.startswith(NECESITA_VENTANA),
    )


def catalogo() -> List[Herramienta]:
    """Todas las herramientas del directorio, ordenadas por nombre."""
    if not rutas.HERRAMIENTAS_DIR.is_dir():
        return []
    encontradas: List[Herramienta] = []
    for archivo in sorted(rutas.HERRAMIENTAS_DIR.rglob("*")):
        if not archivo.is_file() or any(p.startswith(".") for p in archivo.relative_to(
                rutas.HERRAMIENTAS_DIR).parts):
            continue
        descrita = _describir(archivo)
        if descrita is not None:
            encontradas.append(descrita)
    return encontradas


def _por_nombre() -> Dict[str, Herramienta]:
    indice: Dict[str, Herramienta] = {}
    for herramienta in catalogo():
        indice[herramienta.nombre.lower()] = herramienta
        indice[herramienta.archivo.name.lower()] = herramienta
    return indice


def buscar(nombre: str) -> Herramienta:
    herramienta = _por_nombre().get(nombre.lower())
    if herramienta is None:
        raise ErrorHerramienta(
            f"No existe la herramienta '{nombre}'. Usa `python -m STM_HRTS herramientas`."
        )
    return herramienta


def _comando_godot(herramienta: Herramienta, extra: Sequence[str]) -> List[str]:
    binario = rutas.binario_godot()
    if binario is None:
        raise ErrorHerramienta(
            "No se encontro Godot. Define GODOT_BIN con la ruta del ejecutable."
        )
    argv = [str(binario), "--path", str(rutas.GODOT_DIR)]
    if herramienta.headless:
        argv.append("--headless")
    argv.extend(["--script", str(herramienta.archivo)])
    if extra:
        argv.append("--")
        argv.extend(extra)
    return argv


def comando(nombre: str, extra: Sequence[str] = ()) -> Dict[str, object]:
    """Comando listo para ejecutar: `{"argv": [...], "cwd": ruta}`."""
    herramienta = buscar(nombre)
    if herramienta.tipo == "godot":
        argv = _comando_godot(herramienta, extra)
    elif herramienta.tipo == "python":
        argv = [str(rutas.python_actual()), str(herramienta.archivo), *extra]
    elif herramienta.tipo == "powershell":
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(herramienta.archivo), *extra]
    elif herramienta.tipo == "cmd":
        argv = ["cmd", "/c", str(herramienta.archivo), *extra]
    elif herramienta.tipo == "shell":
        argv = ["sh", str(herramienta.archivo), *extra]
    else:  # pragma: no cover - el tipo sale del mapa de sufijos
        raise ErrorHerramienta(f"Tipo sin comando: {herramienta.tipo}")
    return {"argv": argv, "cwd": str(rutas.SRC_DIR)}


def comando_pytest(extra: Sequence[str] = ()) -> Dict[str, object]:
    argv = [str(rutas.python_actual()), "-m", "pytest", "-q",
            "-c", str(rutas.PYTEST_INI), *extra]
    return {"argv": argv, "cwd": str(rutas.SRC_DIR)}


def ejecutar(nombre: str, extra: Sequence[str] = ()) -> int:
    """Lanza una herramienta y devuelve su codigo de salida."""
    plan = comando(nombre, extra)
    print(f"$ {' '.join(str(p) for p in plan['argv'])}")
    return subprocess.run(plan["argv"], cwd=plan["cwd"]).returncode
