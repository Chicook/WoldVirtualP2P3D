"""Sello de integridad de STM_DEF.

Lo contrario de un dropper que se instala y se esconde: aqui se calcula un
sello SHA-256 de los ficheros criticos del taller y se firma con HMAC-SHA256
usando una clave local. Cualquier alta, cambio o borrado posterior queda
delatado, incluso si el atacante intenta reescribir el propio sello.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from . import ESTADO_DIR, SRC_DIR
from .deteccion import DIRS_IGNORADOS

#: Version del formato de sello.
SELLO_VERSION = 1
#: Ruta de la clave HMAC local (se crea con permisos restringidos).
CLAVE_PATH: Path = ESTADO_DIR / "clave.bin"
#: Ruta por defecto del sello.
SELLO_PATH: Path = ESTADO_DIR / "sello.json"
#: Tamano maximo de fichero que se sella individualmente.
LIMITE_BYTES = 4 * 1024 * 1024


def asegurar_estado() -> Path:
    """Crea el directorio de estado si no existe y devuelve su ruta."""
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    return ESTADO_DIR


# ------------------------------------------------------------------- clave
def clave_local() -> bytes:
    """Clave HMAC de 32 bytes; se genera una sola vez y se guarda localmente."""
    asegurar_estado()
    if CLAVE_PATH.is_file():
        datos = CLAVE_PATH.read_bytes()
        if len(datos) >= 32:
            return datos
    clave = secrets.token_bytes(32)
    CLAVE_PATH.write_bytes(clave)
    try:
        os.chmod(CLAVE_PATH, 0o600)
    except OSError:
        pass
    return clave


def firmar(datos: bytes, clave: Optional[bytes] = None) -> str:
    """HMAC-SHA256 en hexadecimal de ``datos``."""
    return hmac.new(clave or clave_local(), datos, hashlib.sha256).hexdigest()


def verificar_firma(datos: bytes, firma: str, clave: Optional[bytes] = None) -> bool:
    """Compara en tiempo constante la firma esperada con la recibida."""
    return hmac.compare_digest(firmar(datos, clave), firma or "")


# ------------------------------------------------------------------ hashing
def sha256_fichero(ruta: Path, bloque: int = 1 << 20) -> str:
    """SHA-256 de un fichero, leido por bloques."""
    digest = hashlib.sha256()
    with open(ruta, "rb") as manejador:
        for trozo in iter(lambda: manejador.read(bloque), b""):
            digest.update(trozo)
    return digest.hexdigest()


def _relativa(ruta: Path) -> str:
    try:
        return ruta.resolve().relative_to(SRC_DIR).as_posix()
    except ValueError:
        return ruta.resolve().as_posix()


def _objetivos_por_defecto() -> List[Path]:
    """Ficheros y carpetas criticos que se sellan por defecto."""
    return [
        SRC_DIR / "STM_HRTS" / "utils" / "add_utils" / "rutas.py",
        SRC_DIR / "STM_HRTS" / "utils" / "add_utils" / "__main__.py",
        SRC_DIR / "STM_HRTS" / "opencode" / "package.json",
        SRC_DIR / "STM_HRTS" / ".github" / "workflows" / "ci.yml",
        SRC_DIR / "VSC#" / "Visor3D.csproj",
        SRC_DIR / "README_DESARROLLO.md",
        SRC_DIR / "STM_HRTS" / "STM_DEF",
    ]


def _iter_ficheros(objetivos: Iterable[Path]) -> Iterable[Path]:
    for objetivo in objetivos:
        objetivo = Path(objetivo)
        if objetivo.is_file():
            yield objetivo
            continue
        if not objetivo.is_dir():
            continue
        for ruta in objetivo.rglob("*"):
            if not ruta.is_file():
                continue
            if any(parte in DIRS_IGNORADOS for parte in ruta.parts):
                continue
            resuelto = ruta.resolve()
            if ESTADO_DIR.resolve() in resuelto.parents:
                continue  # la clave y el propio sello no se sellan a si mismos
            yield ruta


def construir_sello(objetivos: Optional[Iterable[Path]] = None) -> Dict[str, object]:
    """Calcula el sello actual: SHA-256 de cada fichero critico."""
    lista = list(objetivos) if objetivos is not None else _objetivos_por_defecto()
    ficheros: Dict[str, str] = {}
    omitidos: Dict[str, int] = {}
    for ruta in _iter_ficheros(lista):
        try:
            tamano = ruta.stat().st_size
        except OSError:
            continue
        if tamano > LIMITE_BYTES:
            omitidos[_relativa(ruta)] = tamano
            continue
        try:
            ficheros[_relativa(ruta)] = sha256_fichero(ruta)
        except OSError:
            continue
    return {
        "version": SELLO_VERSION,
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "raiz": str(SRC_DIR),
        "ficheros": ficheros,
        "omitidos": omitidos,
    }


# --------------------------------------------------------------- persistencia
def _serializar(sello: Dict[str, object]) -> bytes:
    return json.dumps(sello, sort_keys=True, ensure_ascii=False).encode("utf-8")


def guardar_sello(sello: Dict[str, object], ruta: Path = SELLO_PATH) -> Path:
    """Guarda el sello firmado con HMAC."""
    asegurar_estado()
    documento = {
        "algoritmo": "hmac-sha256",
        "firma": firmar(_serializar(sello)),
        "sello": sello,
    }
    Path(ruta).write_text(json.dumps(documento, indent=2, ensure_ascii=False), encoding="utf-8")
    return Path(ruta)


def leer_sello(ruta: Path = SELLO_PATH) -> Optional[Dict[str, object]]:
    """Lee y valida el sello. ``None`` si falta o la firma no cuadra."""
    ruta = Path(ruta)
    if not ruta.is_file():
        return None
    try:
        documento = json.loads(ruta.read_text(encoding="utf-8"))
        sello = documento["sello"]
        firma = str(documento.get("firma", ""))
    except (OSError, ValueError, KeyError):
        return None
    if not isinstance(sello, dict) or not verificar_firma(_serializar(sello), firma):
        return None
    return sello


def verificar_sello(ruta: Path = SELLO_PATH, objetivos: Optional[Iterable[Path]] = None) -> Dict[str, object]:
    """Compara el sello guardado con el estado real del arbol."""
    guardado = leer_sello(ruta)
    if guardado is None:
        return {
            "firma_ok": False, "intacto": False,
            "añadidos": [], "modificados": [], "borrados": [],
            "mensaje": "no hay sello valido (ausente o con firma manipulada)",
        }
    actual = construir_sello(objetivos)
    previos = dict(guardado.get("ficheros", {}))
    ahora = dict(actual.get("ficheros", {}))
    anadidos = sorted(clave for clave in ahora if clave not in previos)
    borrados = sorted(clave for clave in previos if clave not in ahora)
    modificados = sorted(clave for clave in ahora if clave in previos and ahora[clave] != previos[clave])
    return {
        "firma_ok": True,
        "intacto": not (anadidos or borrados or modificados),
        "añadidos": anadidos,
        "modificados": modificados,
        "borrados": borrados,
        "fecha_sello": guardado.get("fecha", ""),
        "total_sellados": len(ahora),
        "mensaje": "arbol intacto" if not (anadidos or borrados or modificados) else "cambios detectados",
    }


def bloqueos_sello(ruta: Path = SELLO_PATH) -> Tuple[List[str], Dict[str, object]]:
    """Motivos de bloqueo y detalle del sello, con criterio *fail-closed*.

    Decision unica compartida por la puerta de CI (``motor.puerta_seguridad``) y
    por el hook de arranque (``arranque.arranque_seguro``): un sello con firma
    manipulada o un arbol cambiado respecto al sello bloquean; la *ausencia* de
    sello no bloquea (no puede exigirse una linea base que aun no existe).
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        return [], {"intacto": None, "mensaje": "sin sello previo (no bloquea)"}
    estado = verificar_sello(ruta)
    if not estado.get("firma_ok"):
        return ["sello de integridad con firma manipulada"], estado
    if not estado.get("intacto"):
        return ["arbol modificado respecto al sello"], estado
    return [], estado


__all__ = [
    "asegurar_estado", "clave_local", "firmar", "verificar_firma", "sha256_fichero",
    "construir_sello", "guardar_sello", "leer_sello", "verificar_sello", "bloqueos_sello",
    "CLAVE_PATH", "SELLO_PATH", "SELLO_VERSION",
]
