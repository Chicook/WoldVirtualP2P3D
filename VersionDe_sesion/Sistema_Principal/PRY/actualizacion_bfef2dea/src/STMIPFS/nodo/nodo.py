"""Fachada del nodo IPFS: activarlo todo por código y en orden.

``NodoIPFS.asegurar()`` deja el nodo listo sin intervención:

1. binario de Kubo (lo descarga si falta),
2. repositorio inicializado (``ipfs init --profile=server``),
3. daemon arrancado y API respondiendo.

Después: ``publicar()`` sube un paquete de pesos y ``recuperar()`` lo baja y
verifica. ``parar()`` cierra el daemon. Ningún método usa ``.bat``.
"""
from __future__ import annotations

from pathlib import Path

from . import binario, cliente, daemon, pesos, repositorio, rutas


class NodoIPFS:
    """Ciclo de vida completo del nodo, en una sola clase."""

    def __init__(self, arrancar: bool = False, descargar: bool = True) -> None:
        self._arrancar = arrancar
        self._descargar = descargar
        self._listo = False
        if arrancar:
            self.asegurar()

    # -- ciclo de vida ----------------------------------------------------
    def asegurar(self) -> dict:
        """Deja binario, repositorio y daemon listos (en ese orden)."""
        datos = binario.asegurar() if self._descargar else {
            "ok": rutas.ruta_binario().is_file(),
            "motivo": "" if rutas.ruta_binario().is_file() else "sin binario"}
        if not datos.get("ok"):
            return {"ok": False, "paso": "binario", "motivo": datos.get("motivo", "")}
        repo = repositorio.asegurar()
        if not repo.get("ok"):
            return {"ok": False, "paso": "repositorio", "motivo": repo.get("motivo", "")}
        proceso = daemon.arrancar()
        if not proceso.get("ok"):
            return {"ok": False, "paso": "daemon", "motivo": proceso.get("motivo", "")}
        self._listo = True
        return {"ok": True, "binario": str(rutas.ruta_binario()),
                "repo": str(rutas.dir_repo()),
                "api": cliente.api_url(), "arrancado": proceso.get("arrancado")}

    def parar(self) -> dict:
        """Para el daemon y marca el nodo como no listo."""
        self._listo = False
        return daemon.parar()

    def adoptar_legado(self, forzar: bool = False) -> dict:
        """Trae la identidad del ``~/.ipfs`` antiguo al repo del proyecto."""
        return repositorio.adoptar_legado(forzar=forzar)

    # -- estado -----------------------------------------------------------
    @property
    def listo(self) -> bool:
        """True si el API responde ahora mismo (no usa caché)."""
        return cliente.disponible()

    def estado(self) -> dict:
        """Binario, repositorio, daemon y puntero de pesos."""
        return {"rutas": rutas.describir(), "binario": binario.estado(),
                "repositorio": repositorio.estado(), "daemon": daemon.estado(),
                "pesos": pesos.estado(), "listo": self.listo}

    # -- pesos ------------------------------------------------------------
    def publicar(self, archivos: list[Path], nombre: str = "pesos.zip") -> dict:
        """Sube el paquete de pesos al nodo (y apunta el CID)."""
        return pesos.publicar(archivos, nombre=nombre)

    def recuperar(self, cid: str | None = None,
                  destino: Path | None = None) -> dict:
        """Baja el paquete de pesos, verifica y restaura."""
        return pesos.recuperar(cid=cid, destino=destino)


def activar(descargar: bool = True) -> dict:
    """Atajo: crea el nodo y lo deja listo."""
    return NodoIPFS(arrancar=True, descargar=descargar).asegurar()
