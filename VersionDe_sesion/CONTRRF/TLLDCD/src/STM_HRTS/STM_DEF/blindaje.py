"""Blindaje de red de STM_DEF.

Corta el canal C2 por dos vias complementarias:

  1. **Sinkhole DNS** en el fichero ``hosts``: los dominios del C2 apuntan a
     ``0.0.0.0``, de modo que el dropper no puede ni empezar la descarga.
  2. **Firewall de salida** (``netsh advfirewall``): reglas que bloquean el
     trafico hacia las IP resueltas de esos dominios.

Por seguridad, TODAS las acciones son **simuladas por defecto** (``aplicar=
False``): primero se muestra el plan y solo con ``--aplicar`` y privilegios de
administrador se escribe en el sistema. Antes de tocar ``hosts`` se guarda una
copia de seguridad, y el bloque aplicado queda delimitado por marcas, por lo
que es totalmente reversible.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import ESTADO_DIR, iocs
from . import integridad

#: Marcas que delimitan el bloque gestionado por STM_DEF en ``hosts``.
MARCA_INI = "# >>> STM_DEF blindaje C2 >>>"
MARCA_FIN = "# <<< STM_DEF blindaje C2 <<<"
#: Fichero donde se guarda la politica aplicada (firmada con HMAC).
POLITICA_PATH: Path = ESTADO_DIR / "blindaje.json"
#: Prefijo de las reglas de firewall creadas.
PREFIJO_REGLA = "STM_DEF bloqueo C2"


def ruta_hosts() -> Path:
    """Ruta del fichero ``hosts`` del sistema."""
    if os.name == "nt":
        raiz = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"
        return Path(raiz) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def es_admin() -> bool:
    """True si el proceso tiene privilegios suficientes para blindar."""
    if os.name != "nt":
        try:
            return os.geteuid() == 0  # type: ignore[attr-defined]
        except AttributeError:
            return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def dominios_hosts(dominios: Optional[Sequence[str]] = None) -> List[str]:
    """Dominios a sumiderar, sin comodines (``hosts`` no admite ``*``)."""
    base = list(dominios) if dominios is not None else list(iocs.todos_los_dominios())
    limpios = {(dominio or "").strip().lstrip(".").lower() for dominio in base if dominio}
    return sorted(limpios - {""})


def lineas_sinkhole(dominios: Optional[Sequence[str]] = None) -> List[str]:
    """Bloque completo (con marcas) que se anade al fichero ``hosts``."""
    fecha = datetime.now().astimezone().isoformat(timespec="seconds")
    lineas = [
        MARCA_INI,
        f"# Generado por STM_DEF el {fecha}. Bloquea la infraestructura C2 del",
        "# dropper EtherHiding (ethplorer + RPC publicos de Ethereum).",
        "# Retirar este bloque (marcas incluidas) deshace el blindaje.",
    ]
    lineas.extend(f"0.0.0.0 {dominio}" for dominio in dominios_hosts(dominios))
    lineas.append(MARCA_FIN)
    return lineas


def _sin_bloque(texto: str) -> List[str]:
    """Devuelve las lineas del ``hosts`` sin el bloque previo de STM_DEF."""
    dentro = False
    limpias: List[str] = []
    for linea in texto.splitlines():
        if linea.strip() == MARCA_INI:
            dentro = True
            continue
        if linea.strip() == MARCA_FIN:
            dentro = False
            continue
        if not dentro:
            limpias.append(linea)
    return limpias


def configuracion_hosts_actual(ruta: Optional[Path] = None) -> Dict[str, object]:
    """Estado del sinkhole en el fichero ``hosts``."""
    ruta = Path(ruta) if ruta else ruta_hosts()
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        texto = ""
    activo = MARCA_INI in texto and MARCA_FIN in texto
    dominios: List[str] = []
    if activo:
        for linea in texto.splitlines():
            partes = linea.split()
            if len(partes) >= 2 and partes[0] == "0.0.0.0":
                dominios.append(partes[1])
    return {"aplicado": activo, "dominios": sorted(set(dominios)), "ruta": str(ruta)}


def aplicar_sinkhole(
    aplicar: bool = False,
    ruta: Optional[Path] = None,
    dominios: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Planifica (o aplica, con ``aplicar=True``) el sumidero de dominios C2."""
    ruta = Path(ruta) if ruta else ruta_hosts()
    bloque = lineas_sinkhole(dominios)
    plan: Dict[str, object] = {
        "accion": "sinkhole",
        "ruta": str(ruta),
        "dominios": dominios_hosts(dominios),
        "lineas": bloque,
        "requiere_admin": True,
        "aplicado": False,
    }
    if not aplicar:
        return plan
    if not es_admin():
        plan["error"] = "requiere permisos de administrador para editar el fichero hosts"
        return plan
    try:
        original = ruta.read_text(encoding="utf-8", errors="replace") if ruta.is_file() else ""
    except OSError as exc:
        plan["error"] = f"no se pudo leer {ruta}: {exc}"
        return plan
    respaldo = ruta.with_name(ruta.name + ".stmdef.bak")
    try:
        if original:
            respaldo.write_text(original, encoding="utf-8")
        cuerpo = "\n".join([*_sin_bloque(original), "", *bloque, ""])
        ruta.write_text(cuerpo, encoding="utf-8")
    except OSError as exc:
        plan["error"] = f"no se pudo escribir {ruta}: {exc}"
        return plan
    plan["aplicado"] = True
    plan["respaldo"] = str(respaldo)
    return plan


def resolver_dominio(dominio: str) -> List[str]:
    """IP v4 del dominio; lista vacia si no resuelve."""
    try:
        _, _, direcciones = socket.gethostbyname_ex(dominio)
        return list(dict.fromkeys(direcciones))
    except OSError:
        return []


def lineas_firewall(dominios: Optional[Sequence[str]] = None) -> List[List[str]]:
    """Comandos ``netsh`` que bloquean la salida hacia las IP del C2."""
    comandos: List[List[str]] = []
    for dominio in dominios_hosts(dominios):
        ips = resolver_dominio(dominio)
        if not ips:
            continue
        comandos.append([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={PREFIJO_REGLA} {dominio}",
            "dir=out", "action=block", f"remoteip={','.join(ips)}", "enable=yes",
        ])
    return comandos


def aplicar_firewall(aplicar: bool = False, dominios: Optional[Sequence[str]] = None) -> Dict[str, object]:
    """Planifica (o aplica) las reglas de firewall de salida."""
    comandos = lineas_firewall(dominios)
    resultado: Dict[str, object] = {
        "accion": "firewall",
        "comandos": comandos,
        "requiere_admin": True,
        "aplicado": False,
    }
    if not aplicar:
        return resultado
    if not es_admin():
        resultado["error"] = "requiere permisos de administrador para crear reglas de firewall"
        return resultado
    ejecutados: List[Dict[str, object]] = []
    for comando in comandos:
        try:
            proceso = subprocess.run(comando, capture_output=True, text=True, timeout=30, check=False)
            ejecutados.append({"comando": " ".join(comando), "codigo": proceso.returncode})
        except Exception as exc:  # noqa: BLE001 - se reporta, no se oculta
            ejecutados.append({"comando": " ".join(comando), "error": str(exc)})
    resultado["aplicado"] = bool(ejecutados)
    resultado["ejecutados"] = ejecutados
    return resultado


def guardar_politica(documento: Dict[str, object]) -> Path:
    """Persiste la politica aplicada firmada con HMAC (antimanipulacion)."""
    integridad.asegurar_estado()
    payload = json.dumps(documento, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sobre = {"algoritmo": "hmac-sha256", "firma": integridad.firmar(payload), "politica": documento}
    POLITICA_PATH.write_text(json.dumps(sobre, indent=2, ensure_ascii=False), encoding="utf-8")
    return POLITICA_PATH


def leer_politica() -> Optional[Dict[str, object]]:
    """Lee la politica si su firma es valida; ``None`` si fue manipulada."""
    if not POLITICA_PATH.is_file():
        return None
    try:
        sobre = json.loads(POLITICA_PATH.read_text(encoding="utf-8"))
        politica = sobre["politica"]
        firma = str(sobre.get("firma", ""))
    except (OSError, ValueError, KeyError):
        return None
    payload = json.dumps(politica, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return politica if integridad.verificar_firma(payload, firma) else None


def blindar(aplicar: bool = False) -> Dict[str, object]:
    """Ejecuta el blindaje completo (sinkhole + firewall) y guarda la politica."""
    sinkhole = aplicar_sinkhole(aplicar)
    firewall = aplicar_firewall(aplicar)
    politica = {
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dominios": dominios_hosts(),
        "sinkhole_aplicado": bool(sinkhole.get("aplicado")),
        "firewall_aplicado": bool(firewall.get("aplicado")),
    }
    guardar_politica(politica)
    return {"sinkhole": sinkhole, "firewall": firewall, "politica": politica}


def estado() -> Dict[str, object]:
    """Panorama del blindaje: hosts, politica, admin y resolucion DNS."""
    from . import monitor

    return {
        "admin": es_admin(),
        "hosts": str(ruta_hosts()),
        "sinkhole": configuracion_hosts_actual(),
        "politica": leer_politica(),
        "resolucion_c2": monitor.estado_resolucion(),
        "sinkhole_dns_activo": monitor.sinkhole_activo(),
    }


__all__ = [
    "ruta_hosts", "es_admin", "dominios_hosts", "lineas_sinkhole",
    "configuracion_hosts_actual", "aplicar_sinkhole", "lineas_firewall",
    "aplicar_firewall", "blindar", "estado", "guardar_politica", "leer_politica",
    "MARCA_INI", "MARCA_FIN", "POLITICA_PATH", "PREFIJO_REGLA",
]
