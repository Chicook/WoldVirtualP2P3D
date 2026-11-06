"""Catalogo de las herramientas de STM_HRTS/utils.

Cada script suelto del directorio de herramientas se describe aqui a partir de
su propio fichero (tipo por extension, resumen del encabezado y si necesita
ventana). El comando se resuelve con las rutas del paquete (``.rutas``), de modo
que ninguna herramienta depende de donde este el arbol ni de una ruta absoluta
escrita a mano.

Uso desde Python:
    from STM_HRTS.utils.add_utils.herramientas import catalogo, comando, ejecutar
    ejecutar("probar_shapekeys")

Uso desde la consola:
    python -m STM_HRTS herramientas
    python -m STM_HRTS ejecutar probar_shapekeys
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import rutas


class ErrorHerramienta(RuntimeError):
    """La herramienta no existe, no tiene comando o falta su interprete."""


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    archivo: Path
    tipo: str
    resumen: str
    headless: bool = True
    montar_pck: bool = False
    extra: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def relativa(self) -> str:
        return str(self.archivo.relative_to(rutas.SRC_DIR)).replace("\\", "/")

    @property
    def modo(self) -> str:
        return MODO_PCK if self.montar_pck else MODO_ARBOL


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

# Los nombres "capturar_" y "render_" declaran un script que produce pixeles,
# pero el nombre no basta: probar_cara, probar_cuerpo y probar_personalizacion
# se llamaban "probar_" y aun asi solo hacen capturas (medida 2026-11-05).
NOMBRES_CON_VENTANA = ("capturar_", "render_")

# Captura del viewport. Sin rasterizador (``--headless``) ``get_texture()``
# devuelve null y el script revienta con "Cannot call method 'save_png' on a
# null value" mientras el proceso sale con 0: verde silencioso.
CAPTURA_VIEWPORT = "get_texture("

# Un script que comprueba el servidor de visualizacion puede capturar y seguir
# siendo headless a la vez; es la autoguarda de probar_registro.gd:90.
AUTOGUARDA_HEADLESS = "DisplayServer.get_name()"

# H1 (P0-3): scripts destructivos excluidos del catálogo ordinario.
# Solo accesibles mediante ``catalogo_privilegiado(confirmado=True)``.
# Razón: borrar_packs_viejos.ps1 opera sobre objetos internos de .git con
# rutas fijas; purgar_repositorio.ps1 reescribe historia del repositorio.
HERRAMIENTAS_PRIVILEGIADAS: frozenset = frozenset({
    "borrar_packs_viejos",
    "purgar_repositorio",
})

# Los dos modos de res:// que puede tener una prueba de Godot (medidos el
# 2026-11-05 sobre las 22 pruebas con veredicto, matriz completa en el
# README_DESARROLLO §17.6):
#   arbol -> `--path MTBGT/WoldVirtualP2P3D`: el codigo fuente que va en el commit.
#   pck   -> ademas `--main-pack VSC#/wvp3d.pck`: los assets YA IMPORTADOS del paquete.
# El arbol del taller no tiene `.godot/imported` (esta en .gitignore), asi que
# todo lo que carga un modelo necesita el PCK. Y al reves: el PCK se exporto con
# el `gdscrip/` de la 2.7.6, asi que montar un PCK viejo prueba codigo viejo
# (medido: probar_red_puerto con --main-pack sale 1 con 15 errores de parseo por
# el trabajo de puertos de U4, y sale 0 desde el arbol).
MODO_ARBOL = "arbol"
MODO_PCK = "pck"

# Pruebas que solo dicen algo con el PCK montado (los 8 de la matriz que fallan
# o se cuelgan en el arbol por la falta de imports).
PCK_OBLIGATORIO: frozenset = frozenset({
    "probar_carrusel_ocupado",
    "probar_control_clic",
    "probar_flujo_portal",
    "probar_ganchos",
    "probar_registro",
    "validar_avatares",
    "validar_ch3d",
    "validar_personalizacion",
    "validar_shapekeys_reales",
})

# Un guion que cuenta fallos pero sale siempre con 0 es un verde que no comprueba
# nada: el veredicto tiene que estar condicionado al contador. Se escribe de dos
# maneras en el taller (`quit(1 if fallos > 0 else 0)` y
# `quit(0 if fallos == 0 else 1)`), y las dos valen.
VEREDICTO = re.compile(r"quit\(\s*[01]\s+if\s+[^()]*fallos[^()]*[<>!=]=?\s*\d")


def necesita_ventana(archivo: Path) -> bool:
    """Si el script exige un servidor de visualizacion real para decir algo util.

    Dos señales, y la segunda manda aunque el nombre la niegue: el prefijo y la
    presencia de una captura de viewport sin autoguarda.
    """
    if archivo.stem.startswith(NOMBRES_CON_VENTANA):
        return True
    if archivo.suffix.lower() != ".gd":
        return False
    texto = archivo.read_text(encoding="utf-8", errors="replace")
    if CAPTURA_VIEWPORT not in texto:
        return False
    return AUTOGUARDA_HEADLESS not in texto


def necesita_pck(archivo: Path) -> bool:
    """Si la prueba solo es valida con los assets importados del paquete."""
    return archivo.suffix.lower() == ".gd" and archivo.stem in PCK_OBLIGATORIO


def emite_veredicto(archivo: Path) -> bool:
    """Si el guion sale con 1 cuando su propio contador de fallos sube."""
    if archivo.suffix.lower() != ".gd":
        return False
    return bool(VEREDICTO.search(archivo.read_text(encoding="utf-8", errors="replace")))


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
        headless=not necesita_ventana(archivo),
        montar_pck=necesita_pck(archivo),
    )


def catalogo() -> List[Herramienta]:
    """Todas las herramientas del directorio, ordenadas por nombre.

    H1 (P0-3): los scripts en ``HERRAMIENTAS_PRIVILEGIADAS`` quedan excluidos.
    Para listarlos usar ``catalogo_privilegiado(confirmado=True)``.
    """
    if not rutas.HERRAMIENTAS_DIR.is_dir():
        return []
    encontradas: List[Herramienta] = []
    for archivo in sorted(rutas.HERRAMIENTAS_DIR.rglob("*")):
        if not archivo.is_file() or any(p.startswith(".") for p in archivo.relative_to(
                rutas.HERRAMIENTAS_DIR).parts):
            continue
        # H1: excluir scripts destructivos del catálogo ordinario
        if archivo.stem.lower() in HERRAMIENTAS_PRIVILEGIADAS:
            continue
        descrita = _describir(archivo)
        if descrita is not None:
            encontradas.append(descrita)
    return encontradas


def catalogo_privilegiado(confirmado: bool = False) -> List[Herramienta]:
    """Lista únicamente los scripts en ``HERRAMIENTAS_PRIVILEGIADAS`` (H1).

    Requiere ``confirmado=True`` explícito.  Uso previsto solo por herramientas
    de mantenimiento con doble confirmación interactiva; nunca en flujos
    automáticos ni desde el orquestador principal.

    Args:
        confirmado: debe ser ``True`` para obtener la lista.

    Returns:
        Lista de ``Herramienta`` o lista vacía si ``confirmado=False``.
    """
    if not confirmado:
        return []
    if not rutas.HERRAMIENTAS_DIR.is_dir():
        return []
    encontradas: List[Herramienta] = []
    for archivo in sorted(rutas.HERRAMIENTAS_DIR.rglob("*")):
        if not archivo.is_file() or any(p.startswith(".") for p in archivo.relative_to(
                rutas.HERRAMIENTAS_DIR).parts):
            continue
        if archivo.stem.lower() not in HERRAMIENTAS_PRIVILEGIADAS:
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


def entorno_aislado() -> Dict[str, str]:
    """Entorno con el `user://` de Godot apuntando a una carpeta de pruebas.

    Godot 4.7.2 no tiene `--user-data-dir` (medido con su `--help` completo),
    pero resuelve `user://` por APPDATA/LOCALAPPDATA en Windows y por
    XDG_DATA_HOME en Linux, asi que redirigir esas variables aísla el registro
    de cada prueba. Sin esto, `probar_registro` escribe en el `registro.cfg`
    real del visor instalado — paso el 2026-11-05 al sondear la suite.
    """
    rutas.GODOT_USER_DIR.mkdir(parents=True, exist_ok=True)
    anclaje = str(rutas.GODOT_USER_DIR)
    entorno = dict(os.environ)
    entorno["APPDATA"] = anclaje
    entorno["LOCALAPPDATA"] = anclaje
    entorno["XDG_DATA_HOME"] = anclaje
    return entorno


def _comando_godot(herramienta: Herramienta, extra: Sequence[str]) -> List[str]:
    binario = rutas.binario_godot()
    if binario is None:
        raise ErrorHerramienta(
            "No se encontro Godot. Define GODOT_BIN con la ruta del ejecutable."
        )
    argv = [str(binario), "--path", str(rutas.GODOT_DIR)]
    if herramienta.montar_pck:
        if not rutas.PCK_EMBEBIDO.is_file():
            raise ErrorHerramienta(
                f"{herramienta.nombre} necesita los assets importados del PCK y no "
                f"hay ninguno en {rutas.PCK_EMBEBIDO}. Ejecuta la exportacion (regla "
                "RU5) o quita la prueba de la puerta hasta entonces."
            )
        argv.extend(["--main-pack", str(rutas.PCK_EMBEBIDO)])
    if herramienta.headless:
        argv.append("--headless")
    argv.extend(["--script", str(herramienta.archivo)])
    if extra:
        argv.append("--")
        argv.extend(extra)
    return argv


def comando(nombre: str, extra: Sequence[str] = ()) -> Dict[str, object]:
    """Comando listo para ejecutar: `{"argv": [...], "cwd": ruta, "env": {...}}`."""
    herramienta = buscar(nombre)
    if herramienta.tipo == "godot":
        argv = _comando_godot(herramienta, extra)
        return {"argv": argv, "cwd": str(rutas.SRC_DIR), "env": entorno_aislado()}
    if herramienta.tipo == "python":
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
    return {"argv": argv, "cwd": str(rutas.SRC_DIR), "env": dict(os.environ)}


def comando_pytest(extra: Sequence[str] = ()) -> Dict[str, object]:
    # ``--rootdir`` fija el rootdir en src/ para que ``testpaths`` y ``cache_dir``
    # (relativos) se resuelvan igual aunque la config viaje dentro del paquete.
    argv = [str(rutas.python_actual()), "-m", "pytest", "-q",
            "--rootdir", str(rutas.SRC_DIR),
            "-c", str(rutas.PYTEST_INI), *extra]
    return {"argv": argv, "cwd": str(rutas.SRC_DIR), "env": dict(os.environ)}


def ejecutar(nombre: str, extra: Sequence[str] = (), timeout: Optional[float] = None) -> int:
    """Lanza una herramienta y devuelve su codigo de salida.

    `timeout` (segundos) existe por la puerta de Godot: sin el, una prueba que
    se cuelga — `probar_registro` sin el PCK se colgaba >75 s — se lleva el
    CI por delante en lugar de fallar con su codigo.
    """
    plan = comando(nombre, extra)
    print(f"$ {' '.join(str(p) for p in plan['argv'])}")
    try:
        return subprocess.run(plan["argv"], cwd=plan["cwd"], env=plan["env"],
                              timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        print(f"FALLO {nombre} no termino en {timeout} s (codigo 124)")
        return 124
