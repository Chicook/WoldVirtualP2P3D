"""Módulo de Espacios Temporales Canónicos (.dev)
Concentra todo artefacto temporal del ecosistema dentro de .dev:

- Espacios de trabajo con prefijo ``_tmp_`` (``_tmp_bundle``, ``_tmp_tests``...).
- Extracción de paquetes single-file (.NET) de la vista previa del visor.

El host .NET SingleFile añade ``<AssemblyName>\\<hash>`` a la base de extracción,
por lo que la variable debe apuntar a un directorio existente, nunca a una
subcarpeta concreta de la aplicación.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .rutas import DEV_DIR, asegurar_ruta_en_repositorio

PREFIJO_TEMPORAL = "_tmp_"
DIR_BUNDLE: Path = DEV_DIR / "_tmp_bundle"

_CARACTERES_INVALIDOS = ("\\", "/", ":", "*", "?", '"', "<", ">", "|")


def _validar_nombre(nombre: str) -> str:
    """Rechaza nombres que pudieran escapar de .dev o romper el sistema de archivos."""
    limpio = nombre.strip()
    if (
        not limpio
        or limpio in (".", "..")
        or any(c in limpio for c in _CARACTERES_INVALIDOS)
    ):
        raise ValueError(f"Nombre temporal no válido: {nombre!r}")
    return limpio


def carpeta_temporal(nombre: str, limpiar: bool = False) -> Path:
    """Crea (o reutiliza) ``.dev/_tmp_<nombre>`` como espacio de trabajo temporal."""
    ruta = DEV_DIR / f"{PREFIJO_TEMPORAL}{_validar_nombre(nombre)}"
    if not asegurar_ruta_en_repositorio(ruta):
        raise PermissionError(f"La carpeta temporal escaparía del repositorio: {ruta}")
    if limpiar and ruta.is_dir():
        shutil.rmtree(ruta, ignore_errors=True)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def listar_temporales() -> List[Path]:
    """Devuelve las carpetas temporales canónicas (``_tmp_*``) de .dev."""
    if not DEV_DIR.is_dir():
        return []
    return sorted(
        p for p in DEV_DIR.iterdir() if p.is_dir() and p.name.startswith(PREFIJO_TEMPORAL)
    )


def limpiar_temporales(conservar: Optional[List[str]] = None) -> List[Path]:
    """Elimina las carpetas ``_tmp_*`` de .dev salvo las indicadas en ``conservar``."""
    protegidas = {f"{PREFIJO_TEMPORAL}{_validar_nombre(n)}" for n in (conservar or [])}
    borradas: List[Path] = []
    for ruta in listar_temporales():
        if ruta.name in protegidas:
            continue
        shutil.rmtree(ruta, ignore_errors=True)
        borradas.append(ruta)
    return borradas


def entorno_bundle_visor() -> Dict[str, str]:
    """Variables de entorno para extraer el paquete single-file dentro de .dev/_tmp_bundle."""
    DIR_BUNDLE.mkdir(parents=True, exist_ok=True)
    return {"DOTNET_BUNDLE_EXTRACT_BASE_DIR": str(DIR_BUNDLE)}


def lanzar_vista_previa(exe: Path | str, args: Optional[List[str]] = None) -> int:
    """Ejecuta un exe single-file del visor con la extracción contenida en .dev/_tmp_bundle."""
    exe_path = Path(exe)
    if not exe_path.is_file():
        print(f"[Temporales] No existe el ejecutable: {exe_path}")
        return 1

    entorno = os.environ.copy()
    entorno.update(entorno_bundle_visor())

    print(f"[Temporales] Base de extracción: {DIR_BUNDLE}")
    print(f"[Temporales] Ejecutando: {exe_path}")
    if args:
        print(f"[Temporales] Argumentos: {' '.join(args)}")
    return subprocess.run([str(exe_path), *list(args or [])], env=entorno).returncode


def _tamano_mb(ruta: Path) -> float:
    total = 0
    for archivo in ruta.rglob("*"):
        try:
            if archivo.is_file():
                total += archivo.stat().st_size
        except OSError:
            continue
    return total / (1024 * 1024)


def formatear_informe_temporales() -> str:
    """Informe legible de los espacios temporales y su tamaño en disco."""
    temporales = listar_temporales()
    lineas = [
        "=" * 76,
        "  ESPACIOS TEMPORALES CANÓNICOS (.dev)",
        "=" * 76,
        f"  Prefijo obligatorio: {PREFIJO_TEMPORAL}*",
    ]
    if not temporales:
        lineas.append("  [VACÍO] No hay carpetas temporales en .dev.")
        return "\n".join(lineas)

    total = 0.0
    for ruta in temporales:
        mb = _tamano_mb(ruta)
        total += mb
        lineas.append(f"  [OK] {mb:9.1f} MB  {ruta}")
    lineas.append("-" * 76)
    lineas.append(f"  Total: {total:.1f} MB en {len(temporales)} carpeta(s)")
    return "\n".join(lineas)
