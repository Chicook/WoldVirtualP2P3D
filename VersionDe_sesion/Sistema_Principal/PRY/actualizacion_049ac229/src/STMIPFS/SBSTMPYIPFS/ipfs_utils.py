"""
ipfs_utils.py - Utilidades de infraestructura, resolucion de rutas y metricas IPFS
================================================================================
Funciones auxiliares para localizacion de binario/repo, consulta de estadisticas
y utilidades HTTP del nodo Kubo IPFS.
"""
from __future__ import annotations
import os
import shutil
import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("WoldVirtualP2P3D.IPFSUtils")

IPFSONL_DIR: Path = Path(__file__).parent.resolve()


def localizar_binario() -> Path:
    """Localiza el ejecutable de ipfs en variables de entorno, PATH o rutas locales."""
    if "IPFS_BIN" in os.environ and Path(os.environ["IPFS_BIN"]).exists():
        return Path(os.environ["IPFS_BIN"]).resolve()
    w = shutil.which("ipfs") or shutil.which("ipfs.exe")
    if w and Path(w).exists():
        return Path(w).resolve()
    for c in (
        IPFSONL_DIR.parent / ".ipfs" / "STMIPFSCOMFIG" / "ipfs.exe",
        IPFSONL_DIR / "ipfs.exe",
        IPFSONL_DIR.parent / "ipfs.exe",
    ):
        if c.exists():
            return c.resolve()
    return IPFSONL_DIR.parent / ".ipfs" / "STMIPFSCOMFIG" / "ipfs.exe"


def localizar_repo() -> Path:
    """Localiza el repositorio .ipfs en variables de entorno o rutas por defecto."""
    if "IPFS_PATH" in os.environ and Path(os.environ["IPFS_PATH"]).exists():
        return Path(os.environ["IPFS_PATH"]).resolve()
    for c in (
        IPFSONL_DIR.parent.parent / "STM_CH" / "ipfs_repo",
        IPFSONL_DIR.parent / ".ipfs",
        IPFSONL_DIR / ".ipfs",
        Path.home() / ".ipfs",
    ):
        if c.exists() and (c / "config").exists():
            return c.resolve()
    return IPFSONL_DIR.parent / ".ipfs"


def obtener_id_nodo(api_url: str = "http://127.0.0.1:5001", timeout: float = 2.0) -> Dict[str, Any]:
    """Obtiene metadatos del nodo: PeerID, AgentVersion y Protocolos."""
    try:
        req = urllib.request.Request(f"{api_url}/api/v0/id", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        logger.debug("Error obteniendo node id: %s", e)
    return {}


def obtener_estadisticas_repo(api_url: str = "http://127.0.0.1:5001", timeout: float = 3.0) -> Dict[str, Any]:
    """Recupera volumen de almacenamiento, numero de objetos y version de repo."""
    try:
        req = urllib.request.Request(f"{api_url}/api/v0/repo/stat", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        logger.debug("Error leyendo repo stats: %s", e)
    return {}


def ejecutar_repo_gc(api_url: str = "http://127.0.0.1:5001", timeout: float = 10.0) -> Dict[str, Any]:
    """Invoca la recoleccion de basura en el repositorio IPFS para compactar datastore."""
    try:
        req = urllib.request.Request(f"{api_url}/api/v0/repo/gc", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                lineas = r.read().decode("utf-8", errors="replace").strip().splitlines()
                return {"ok": True, "bloques_liberados": len(lineas)}
    except Exception as e:
        logger.debug("Error ejecutando repo gc: %s", e)
    return {"ok": False, "bloques_liberados": 0}


def obtener_peers_conectados(api_url: str = "http://127.0.0.1:5001", timeout: float = 3.0) -> List[Dict[str, Any]]:
    """Consulta la lista de peers activos en el IPFS swarm."""
    try:
        req = urllib.request.Request(f"{api_url}/api/v0/swarm/peers", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
                return data.get("Peers") or []
    except Exception as e:
        logger.debug("Error listando peers de enjambre: %s", e)
    return []


def obtener_estadisticas_ancho_banda(api_url: str = "http://127.0.0.1:5001", timeout: float = 2.5) -> Dict[str, Any]:
    """Consulta el ratio y volumen total de ancho de banda consumido (in/out)."""
    try:
        req = urllib.request.Request(f"{api_url}/api/v0/stats/bw", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        logger.debug("Error consultando bandwidth stats: %s", e)
    return {}


def generar_urls_pasarela(cid: str, gateway_url: str = "http://127.0.0.1:8080") -> Dict[str, str]:
    """Construye enlaces a pasarelas publicas y privadas para un CID dado."""
    return {
        "local": f"{gateway_url}/ipfs/{cid}",
        "ipfs_io": f"https://ipfs.io/ipfs/{cid}",
        "pinata": f"https://gateway.pinata.cloud/ipfs/{cid}",
        "dweb": f"https://dweb.link/ipfs/{cid}",
        "cloudflare": f"https://cloudflare-ipfs.com/ipfs/{cid}",
    }


def imprimir_panel_estado(
    api_url: str = "http://127.0.0.1:5001",
    session_stats: Optional[Dict[str, Any]] = None,
) -> None:
    """Muestra un dashboard ANSI con telemetria del nodo y estado del cluster."""
    import time
    id_info = obtener_id_nodo(api_url=api_url)
    peers = obtener_peers_conectados(api_url=api_url)
    repo_stats = obtener_estadisticas_repo(api_url=api_url)
    bw_stats = obtener_estadisticas_ancho_banda(api_url=api_url)

    peer_id = id_info.get("ID", "Desconocido")
    agent = id_info.get("AgentVersion", "Kubo P2P")
    repo_size = repo_stats.get("RepoSize", 0) / (1024 * 1024)
    num_obj = repo_stats.get("NumObjects", 0)
    total_in = bw_stats.get("TotalIn", 0) / 1024
    total_out = bw_stats.get("TotalOut", 0) / 1024

    stats = session_stats or {}
    uptime = 0.0
    if stats.get("start_time", 0.0) > 0:
        uptime = time.time() - stats["start_time"]

    print("\033[1;36m" + "=" * 68 + "\033[0m")
    print("  \033[1;32mPANEL OPERATIVO IPFS KUBO (WoldVirtualP2P3D 2026)\033[0m")
    print("\033[1;36m" + "=" * 68 + "\033[0m")
    print(f"  Estado Daemon   : \033[1;32mONLINE\033[0m (HTTP {api_url})")
    print(f"  PeerID Nodo     : \033[1;33m{peer_id}\033[0m")
    print(f"  Agente / Motor  : {agent}")
    print(f"  Peers Conectados: \033[1;35m{len(peers)}\033[0m nodos en enjambre")
    print(f"  Repo Local      : {repo_size:.2f} MB ({num_obj} objetos persistidos)")
    print(f"  Trafico P2P     : IN: {total_in:.1f} KB | OUT: {total_out:.1f} KB")
    print(f"  Uptime Sesion   : {uptime:.1f} s | Reinicios: {stats.get('restarts', 0)}")
    print(f"  Subidas Sesion  : {stats.get('cids_uploaded', 0)} CIDs")
    print("\033[1;36m" + "-" * 68 + "\033[0m")
    if peers:
        print("  Top Peers Activos:")
        for p in peers[:3]:
            print(f"    -> {p.get('Peer', '')[:24]}... ({p.get('Addr', '')[:32]})")
    print("\033[1;36m" + "=" * 68 + "\033[0m\n")
