"""Monitor de red de STM_DEF (capacidad prioritaria).

Hace lo contrario del dropper: en vez de abrir una conexion silenciosa al C2,
enumera las conexiones salientes del equipo, resuelve sus destinos y avisa de
cualquier contacto con la infraestructura C2 o con puertos JSON-RPC.

Usa ``psutil`` cuando esta disponible (da el nombre del proceso y permite leer
lineas de comandos completas). Si no, cae a ``netstat -ano`` en Windows. Nunca
modifica nada: solo observa y reporta.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from typing import Callable, Dict, List, Optional, Sequence

from . import iocs
from .modelos import ALTA, MEDIA, Alerta, Conexion

#: Estados de conexion que implican trafico saliente real.
ESTADOS_ACTIVOS = frozenset({"ESTABLISHED", "SYN_SENT", "SYN_RECV", "CLOSE_WAIT"})


# --------------------------------------------------------------- obtencion
def _via_psutil() -> Optional[List[Conexion]]:
    """Conexiones salientes por ``psutil``. ``None`` si no esta instalado."""
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    conexiones: List[Conexion] = []
    try:
        crudas = psutil.net_connections(kind="inet")
    except Exception:
        return conexiones
    cache: Dict[int, str] = {}
    for cruda in crudas:
        if not cruda.raddr:
            continue
        estado = str(cruda.status or "")
        if estado and estado not in ESTADOS_ACTIVOS:
            continue
        pid = int(cruda.pid or 0)
        if pid and pid not in cache:
            try:
                cache[pid] = psutil.Process(pid).name()
            except Exception:
                cache[pid] = ""
        conexiones.append(Conexion(
            pid=pid, proceso=cache.get(pid, ""),
            ip_remota=str(cruda.raddr.ip), puerto_remoto=int(cruda.raddr.port),
            estado=estado,
        ))
    return conexiones


def _parsear_netstat(texto: str) -> List[Conexion]:
    """Extrae conexiones salientes del texto de ``netstat -ano``."""
    conexiones: List[Conexion] = []
    for linea in texto.splitlines():
        partes = linea.split()
        if len(partes) < 4 or not partes[0].upper().startswith("TCP"):
            continue
        remota = partes[2]
        if remota in ("0.0.0.0:0", "*:*", "[::]:0"):
            continue
        estado = partes[3] if len(partes) >= 5 else ""
        if estado and estado.upper() not in ESTADOS_ACTIVOS:
            continue
        pid = 0
        if partes[-1].isdigit():
            pid = int(partes[-1])
        host, _, puerto = remota.rpartition(":")
        host = host.strip("[]")
        try:
            puerto_int = int(puerto)
        except ValueError:
            puerto_int = 0
        conexiones.append(Conexion(
            pid=pid, ip_remota=host, puerto_remoto=puerto_int, estado=estado.upper(),
        ))
    return conexiones


def conexiones_actuales() -> List[Conexion]:
    """Conexiones salientes del equipo, por ``psutil`` o ``netstat``."""
    por_psutil = _via_psutil()
    if por_psutil:  # psutil disponible y con datos
        return por_psutil
    if os.name != "nt" and por_psutil is not None:
        return por_psutil
    try:
        salida = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=20, check=False,
        ).stdout
    except Exception:
        return por_psutil or []
    return _parsear_netstat(salida)


def resolver_host(ip: str) -> str:
    """Nombre inverso de una IP; cadena vacia si no se puede resolver."""
    if not ip:
        return ""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


# ---------------------------------------------------------------- analisis
def revisar(conexiones: Optional[Sequence[Conexion]] = None, resolver: bool = False) -> List[Alerta]:
    """Veredicto sobre una lista de conexiones (reales o sinteticas)."""
    lista = list(conexiones) if conexiones is not None else conexiones_actuales()
    alertas: List[Alerta] = []
    for conexion in lista:
        host = conexion.host_remoto
        if not host and resolver and conexion.ip_remota:
            host = resolver_host(conexion.ip_remota)
        candidato = host or conexion.ip_remota
        if iocs.es_dominio_c2(candidato):
            alertas.append(Alerta(
                ALTA, "conexion a infraestructura C2 conocida",
                f"destino {candidato}", conexion,
            ))
        elif conexion.puerto_remoto in iocs.PUERTOS_RPC:
            alertas.append(Alerta(
                MEDIA, "conexion a puerto JSON-RPC de Ethereum",
                "canal tipico de EtherHiding", conexion,
            ))
    return alertas


def procesos_con_c2() -> List[Alerta]:
    """Procesos vivos cuyo nombre o linea de comandos cite al C2."""
    try:
        import psutil  # type: ignore
    except Exception:
        return []
    alertas: List[Alerta] = []
    for proceso in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proceso.info
        except Exception:
            continue
        nombre = str(info.get("name") or "")
        linea = " ".join(info.get("cmdline") or [])
        if not linea:
            continue
        bajo = linea.lower()
        if iocs.es_direccion_c2(bajo) or any(dom in bajo for dom in iocs.todos_los_dominios()):
            alertas.append(Alerta(
                ALTA, "proceso con referencias C2 en su linea de comandos",
                linea[:160], Conexion(pid=int(info.get("pid") or 0), proceso=nombre),
            ))
    return alertas


def estado_resolucion(dominios: Optional[Sequence[str]] = None) -> List[Dict[str, str]]:
    """Estado DNS de los dominios C2: resuelto, sinkhole o sin resolver."""
    filas: List[Dict[str, str]] = []
    for dominio in (dominios or iocs.DOMINIOS_C2):
        try:
            ip = socket.gethostbyname(dominio)
            estado = "sinkhole" if ip in ("0.0.0.0", "127.0.0.1") else "resuelto"
        except OSError:
            ip, estado = "", "sin_resolver"
        filas.append({"dominio": dominio, "ip": ip, "estado": estado})
    return filas


def sinkhole_activo(dominios: Optional[Sequence[str]] = None) -> bool:
    """True si todos los dominios C2 apuntan al sumidero local."""
    filas = estado_resolucion(dominios)
    return bool(filas) and all(fila["estado"] == "sinkhole" for fila in filas)


def vigilar(
    ciclos: int = 1,
    intervalo: float = 60.0,
    resolver: bool = False,
    callback: Optional[Callable[[Alerta], None]] = None,
) -> List[Alerta]:
    """Ejecuta una o varias pasadas de vigilancia y devuelve las alertas."""
    alertas: List[Alerta] = []
    for indice in range(max(1, ciclos)):
        nuevas = revisar(resolver=resolver)
        nuevas.extend(procesos_con_c2())
        for alerta in nuevas:
            if callback is not None:
                callback(alerta)
        alertas.extend(nuevas)
        if indice < ciclos - 1:
            time.sleep(intervalo)
    return alertas


__all__ = [
    "conexiones_actuales", "revisar", "resolver_host", "procesos_con_c2",
    "estado_resolucion", "sinkhole_activo", "vigilar",
]
