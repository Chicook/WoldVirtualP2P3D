"""Puente de pesos de LucIA hacia IPFS (Kubo local).

- Publica un JSON de pesos con `ipfs add --pin` y guarda el CID puntero.
- Restaura los pesos con `ipfs cat` al arrancar.
- Si el daemon no está disponible, deja el fichero local y devuelve error legible.

No depende de servicios externos: usa la CLI de Kubo y el repo local (IPFS_PATH).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]          # .../src
STM_CH = ROOT / "STM_CH"
PSNRL = STM_CH / "PSNRL"
PUNTERO = STM_CH / "lucia_pesos.cid"


def _binario() -> str | None:
    """Localiza ipfs.exe: variable de entorno, PATH o dentro de STMIPFS."""
    propio = os.environ.get("WOLD_IPFS_BIN", "").strip()
    if propio and Path(propio).exists():
        return propio
    en_path = shutil.which("ipfs")
    if en_path:
        return en_path
    for candidato in ROOT.glob("STMIPFS/**/ipfs.exe"):
        if candidato.exists():
            return str(candidato)
    return None


def _repo() -> Path:
    return Path(os.environ.get("IPFS_PATH") or (ROOT / "STMIPFS" / ".ipfs"))


def _ejecutar(args: list[str], timeout: int = 60) -> str:
    binario = _binario()
    if not binario:
        raise RuntimeError("ipfs no está instalado (ni en PATH ni en STMIPFS)")

    entorno = os.environ.copy()
    entorno.setdefault("IPFS_PATH", str(_repo()))
    proceso = subprocess.run(
        [binario, *args], capture_output=True, text=True, timeout=timeout, env=entorno
    )
    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout or "").strip()
        raise RuntimeError(detalle or f"ipfs {' '.join(args)} falló")
    return proceso.stdout.strip()


def estado() -> dict[str, Any]:
    """Estado del puente: binario, puntero y último CID conocido."""
    puntero = _leer_puntero()
    return {
        "binario": _binario(),
        "repo": str(_repo()),
        "puntero": str(PUNTERO) if PUNTERO.exists() else None,
        "cid": puntero.get("cid") if puntero else None,
    }


def publicar_pesos(datos: dict[str, Any], etiqueta: str = "lucia") -> dict[str, Any]:
    """Escribe los pesos, los publica en IPFS y actualiza el puntero.

    Devuelve {"ok", "cid", "archivo", "fecha"} o {"ok": False, "error"}.
    """
    PSNRL.mkdir(parents=True, exist_ok=True)

    sello = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    nombre = f"{etiqueta}_pesos_{sello}.json"
    ruta = PSNRL / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    # Copia estable "último" para consumo local aunque IPFS falle.
    (PSNRL / f"{etiqueta}_pesos_ultimo.json").write_text(
        ruta.read_text(encoding="utf-8"), encoding="utf-8"
    )

    try:
        cid = _ejecutar(["add", "--pin", "--quieter", "--cid-version=1", str(ruta)])
    except Exception as exc:  # daemon caído, binario ausente, timeout...
        return {"ok": False, "cid": None, "archivo": str(ruta), "error": str(exc)}

    if not cid:
        return {"ok": False, "cid": None, "archivo": str(ruta), "error": "IPFS no devolvió CID"}

    _escribir_puntero({"cid": cid, "archivo": nombre, "fecha": sello, "etiqueta": etiqueta})
    return {"ok": True, "cid": cid, "archivo": str(ruta), "fecha": sello}


def cargar_pesos(cid: str | None = None) -> dict[str, Any] | None:
    """Descarga los pesos desde IPFS (o desde el puntero) y los parsea."""
    objetivo = (cid or "").strip() or (_leer_puntero() or {}).get("cid", "")
    if not objetivo:
        return None

    try:
        crudo = _ejecutar(["cat", objetivo])
        return json.loads(crudo)
    except Exception:
        # Fallback local: el JSON "ultimo" escrito antes de publicar.
        local = PSNRL / "lucia_pesos_ultimo.json"
        if local.exists():
            try:
                return json.loads(local.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None


def _leer_puntero() -> dict[str, Any] | None:
    try:
        if not PUNTERO.exists():
            return None
        texto = PUNTERO.read_text(encoding="utf-8").strip()
        if texto.startswith("{"):
            return json.loads(texto)
        return {"cid": texto}
    except Exception:
        return None


def _escribir_puntero(datos: dict[str, Any]) -> None:
    PUNTERO.parent.mkdir(parents=True, exist_ok=True)
    PUNTERO.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
