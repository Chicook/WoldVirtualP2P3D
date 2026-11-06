"""Cuarentena interna de STM_DEF.

Lo contrario de un dropper que se destruye (``os.unlink`` del temporal): aqui
toda muestra sospechosa se **copia** (nunca se mueve ni se borra) a un
directorio controlado y queda registrada con su SHA-256 en un manifiesto
firmado con HMAC. El original permanece en su sitio para la investigacion y la
copia sirve de evidencia cuya manipulacion posterior se delata.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import STM_DEF_DIR, integridad

#: Version del formato del manifiesto.
MANIFIESTO_VERSION = 1
#: Directorio de cuarentena (dentro del propio subsistema).
CUARENTENA_DIR: Path = STM_DEF_DIR / "cuarentena"
#: Manifiesto firmado con el indice de muestras.
MANIFIESTO_PATH: Path = CUARENTENA_DIR / "manifiesto.json"
#: Tamano maximo de la muestra que se copia.
LIMITE_BYTES = 8 * 1024 * 1024

_NOMBRE_SEGURO = re.compile(r"[^A-Za-z0-9._-]+")


def _asegurar() -> Path:
    """Crea el directorio de cuarentena si no existe y lo devuelve."""
    CUARENTENA_DIR.mkdir(parents=True, exist_ok=True)
    return CUARENTENA_DIR


def _nombre_seguro(nombre: str) -> str:
    """Sanea un nombre de fichero para que no escape del directorio."""
    limpio = _NOMBRE_SEGURO.sub("_", Path(nombre).name).strip("._")
    return (limpio or "muestra")[:80]


def _canonico(datos: dict) -> bytes:
    """Serializacion estable (claves ordenadas) para firmar el manifiesto."""
    return json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _cuerpo(manifiesto: Dict[str, object]) -> Dict[str, object]:
    return {
        "version": manifiesto.get("version", MANIFIESTO_VERSION),
        "registros": list(manifiesto.get("registros", [])),
    }


def _leer_manifiesto() -> Dict[str, object]:
    """Devuelve el manifiesto si la firma es valida; si no, uno vacio."""
    if not MANIFIESTO_PATH.is_file():
        return {"version": MANIFIESTO_VERSION, "registros": []}
    try:
        crudo = json.loads(MANIFIESTO_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": MANIFIESTO_VERSION, "registros": []}
    firma = crudo.pop("firma", "")
    if not integridad.verificar_firma(_canonico(crudo), firma):
        return {"version": MANIFIESTO_VERSION, "registros": []}  # manifiesto manipulado
    return crudo


def _guardar_manifiesto(manifiesto: Dict[str, object]) -> Path:
    """Firma y guarda el manifiesto, con su HMAC sobre el cuerpo canonico."""
    _asegurar()
    cuerpo = _cuerpo(manifiesto)
    firmado = dict(cuerpo)
    firmado["firma"] = integridad.firmar(_canonico(cuerpo))
    MANIFIESTO_PATH.write_text(json.dumps(firmado, indent=2, ensure_ascii=False), encoding="utf-8")
    return MANIFIESTO_PATH


def poner_en_cuarentena(ruta: Path, motivo: str = "") -> Dict[str, object]:
    """Copia una muestra a la cuarentena firmada.

    **Nunca borra ni mueve el original**: solo lo replica bajo un nombre
    derivado de su SHA-256 y anota el registro en el manifiesto firmado.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(str(ruta))
    if ruta.stat().st_size > LIMITE_BYTES:
        raise ValueError(f"muestra demasiado grande (> {LIMITE_BYTES} bytes)")
    datos = ruta.read_bytes()
    digest = hashlib.sha256(datos).hexdigest()
    destino = _asegurar() / f"{digest[:16]}__{_nombre_seguro(ruta.name)}"
    if not destino.is_file():
        destino.write_bytes(datos)

    manifiesto = _leer_manifiesto()
    registros: List[Dict[str, object]] = list(manifiesto.get("registros", []))
    previo = next((r for r in registros if r.get("sha256") == digest), None)
    if previo is None:
        registro = {
            "origen": str(ruta.resolve()),
            "copia": destino.name,
            "sha256": digest,
            "bytes": len(datos),
            "motivo": motivo,
            "fecha": datetime.now().isoformat(timespec="seconds"),
        }
        registros.append(registro)
        manifiesto["registros"] = registros
        _guardar_manifiesto(manifiesto)
        return registro
    return previo


def listar() -> List[Dict[str, object]]:
    """Devuelve los registros del manifiesto (vacio si la firma no es valida)."""
    return list(_leer_manifiesto().get("registros", []))


def verificar() -> Dict[str, object]:
    """Comprueba que cada copia sigue coincidiendo con su SHA-256 registrado."""
    registros = listar()
    integras: List[str] = []
    alteradas: List[str] = []
    ausentes: List[str] = []
    for registro in registros:
        copia = CUARENTENA_DIR / str(registro.get("copia", ""))
        if not copia.is_file():
            ausentes.append(str(registro.get("copia")))
            continue
        if hashlib.sha256(copia.read_bytes()).hexdigest() == registro.get("sha256"):
            integras.append(str(registro.get("copia")))
        else:
            alteradas.append(str(registro.get("copia")))
    return {
        "total": len(registros),
        "integras": integras,
        "alteradas": alteradas,
        "ausentes": ausentes,
        "intacto": not alteradas and not ausentes,
    }


__all__ = [
    "CUARENTENA_DIR", "MANIFIESTO_PATH", "MANIFIESTO_VERSION", "LIMITE_BYTES",
    "poner_en_cuarentena", "listar", "verificar",
]
