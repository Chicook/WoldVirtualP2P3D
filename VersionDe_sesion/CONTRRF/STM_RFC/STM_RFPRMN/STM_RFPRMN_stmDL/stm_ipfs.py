"""Subida de los pesos del registro a IPFS en cuatro niveles.

1. ``IPFSManager`` de ``STM_BKCH`` (patrón BKSVCB).
2. API HTTP del daemon local (``127.0.0.1:5001``).
3. Binario ``ipfs.exe`` del sistema (Kubo de STMIPFS o el del PATH).
4. CID sintético local cuando no hay daemon (mismo criterio que el shim actual).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

from .stm_base import advertir, exito, informar, MODULO_DIR
from .stm_rutas import ultima_actualizacion_pry

#: Endpoint del daemon IPFS local (mismo que usa STMIPFS del sistema).
IPFS_API_URL = "http://127.0.0.1:5001"
IPFS_GATEWAY_URL = "http://127.0.0.1:8080"


def url_pasarela(cid: str, local: bool = True) -> str:
    """URL de pasarela para recuperar unos pesos por su CID.

    Con ``local=True`` usa el gateway del daemon (127.0.0.1:8080);
    si no, el gateway público ipfs.io (mismo que usa STMIPFS).
    """
    cid = cid.strip().strip("/")
    if not cid:
        return ""
    base = IPFS_GATEWAY_URL if local else "https://ipfs.io"
    return f"{base}/ipfs/{cid}"


def _cid_sintetico(pesos: dict) -> str:
    """CID local determinista (mismo estilo QmLocal del shim del sistema)."""
    sello = hashlib.sha256(
        json.dumps(pesos, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"QmLocal{sello}"


def _subir_via_manager(datos: bytes, nombre: str) -> dict:
    """Nivel 1: IPFSManager.almacenar_pesos() de STM_BKCH (patrón BKSVCB).

    El shim de ``STM_BKCH`` devuelve CIDs ``QmLocal…`` con ``ok=False`` cuando
    no hay daemon. Eso **no** cuenta como subida: se rechaza para que el flujo
    siga bajando de nivel (API → CLI → CID local honesto). Antes un CID
    sintético se daba por bueno y nunca se intentaba el daemon real (P1).
    """
    from STM_BKCH.compat_local import get_ipfs_manager  # type: ignore[import]
    recibo = get_ipfs_manager().almacenar_pesos(
        datos=datos, nombre_modelo=nombre, eliminar_local=False)
    if not isinstance(recibo, dict) or not recibo.get("cid"):
        raise ValueError("IPFSManager no devolvió CID.")
    if recibo.get("simulado") or recibo.get("ok") is False:
        raise ValueError(
            f"IPFSManager sin daemon real ({recibo.get('error', 'sin persistencia')}).")
    if str(recibo["cid"]).startswith("QmLocal"):
        raise ValueError("IPFSManager devolvió un CID sintético (sin daemon).")
    recibo = dict(recibo)
    recibo.setdefault("via", "ipfs-manager")
    return recibo


def _subir_via_api(datos: bytes, nombre: str, timeout: int = 60) -> dict:
    """Nivel 2: POST /api/v0/add al daemon local (127.0.0.1:5001).

    Construye el multipart a mano (solo stdlib) y extrae el Hash de la
    respuesta NDJSON del daemon.
    """
    frontera = f"----RFPRMN{hashlib.md5(datos).hexdigest()[:8]}"
    cuerpo = (f"--{frontera}\r\nContent-Disposition: form-data; "
              f'name="file"; filename="{nombre}"\r\n'
              f"Content-Type: application/json\r\n\r\n").encode("utf-8")
    cuerpo += datos + f"\r\n--{frontera}--\r\n".encode("utf-8")
    pet = urllib.request.Request(
        f"{IPFS_API_URL}/api/v0/add", data=cuerpo,
        headers={"Content-Type": f"multipart/form-data; boundary={frontera}"},
        method="POST")
    with urllib.request.urlopen(pet, timeout=timeout) as resp:
        crudo = resp.read().decode("utf-8")
    cid = ""
    for linea in crudo.splitlines():
        try:
            cid = json.loads(linea).get("Hash", "") or cid
        except ValueError:
            continue
    if not cid:
        raise ValueError("El daemon no devolvió Hash.")
    return {"cid": cid, "modo": "ipfs-daemon", "via": "api-http",
            "modelo": nombre, "bytes": len(datos)}


def _localizar_ipfs_bin() -> Optional[Path]:
    """Localiza el ipfs.exe del sistema (STMIPFS) o en el PATH."""
    candidatos = [
        MODULO_DIR.parent.parent / "RFC" / "src" / "STMIPFS" / ".ipfs"
        / "STMIPFSCOMFIG" / "ipfs.exe",
    ]
    for cand in candidatos:
        if cand.is_file() and cand.suffix.lower() == ".exe":
            return cand
    ultima = ultima_actualizacion_pry()
    if ultima is not None:
        cand = ultima / "src" / "STMIPFS" / ".ipfs" / "STMIPFSCOMFIG" / "ipfs.exe"
        if cand.is_file():
            return cand
    for nombre in ("ipfs", "ipfs.exe"):
        for ruta in os.getenv("PATH", "").split(os.pathsep):
            cand = Path(ruta) / nombre
            if cand.is_file():
                return cand
    return None


def _subir_via_cli(ruta_pesos: Path, timeout: int = 120) -> dict:
    """Nivel 3: ``ipfs add -Q`` con el binario del sistema.

    Reutiliza el Kubo empaquetado en STMIPFS sin exigir daemon previo
    (usa el repo local si responde, si no falla al siguiente nivel).
    """
    binario = _localizar_ipfs_bin()
    if binario is None:
        raise FileNotFoundError("Sin binario ipfs disponible.")
    proc = subprocess.run([str(binario), "add", "-Q", str(ruta_pesos)],
                          capture_output=True, text=True, timeout=timeout)
    cid = proc.stdout.strip().split()[-1] if proc.stdout.strip() else ""
    if proc.returncode != 0 or not cid:
        raise ValueError(f"ipfs add falló: {proc.stderr.strip()[:120]}")
    return {"cid": cid, "modo": "ipfs-daemon", "via": "cli",
            "modelo": ruta_pesos.name, "bytes": ruta_pesos.stat().st_size}


def _detallado() -> bool:
    """True si RFPRMN_DEBUG=1 (muestra cada nivel de subida intentado)."""
    return os.getenv("RFPRMN_DEBUG", "").strip() == "1"


def subir_a_ipfs(ruta_pesos: Path) -> dict:
    """Sube los pesos a IPFS en 4 niveles (devuelve el recibo).

    Solo se informa el resultado final, salvo RFPRMN_DEBUG=1 que detalla
    cada nivel intentado.
    """
    datos = ruta_pesos.read_bytes()
    niveles = [("manager", lambda: _subir_via_manager(datos, ruta_pesos.name)),
               ("api-http", lambda: _subir_via_api(datos, ruta_pesos.name)),
               ("cli", lambda: _subir_via_cli(ruta_pesos))]
    fallos: list[str] = []
    for nombre, intento in niveles:
        try:
            recibo = intento()
            exito(f"Pesos subidos a IPFS vía {nombre}: {recibo['cid']}")
            return recibo
        except Exception as error:  # noqa: BLE001 - se prueba el siguiente nivel
            fallos.append(f"{nombre}: {error}")
            if _detallado():
                advertir(f"Nivel {nombre} no disponible ({error}); siguiente.")
    cid = _cid_sintetico({"md5": hashlib.md5(datos).hexdigest()})
    informar("IPFS sin daemon disponible; pesos guardados con CID local "
             f"(RFPRMN_DEBUG=1 para detalle): {cid}.")
    return {"cid": cid, "modo": "local-sin-daemon", "via": "local",
            "modelo": ruta_pesos.name, "bytes": len(datos)}
