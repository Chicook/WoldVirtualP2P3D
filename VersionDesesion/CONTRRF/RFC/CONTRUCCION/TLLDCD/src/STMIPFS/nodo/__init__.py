"""Nodo IPFS de LucIA, activado por código (sin ``.bat``).

Uso mínimo::

    from STMIPFS.nodo import NodoIPFS

    nodo = NodoIPFS(arrancar=True)      # binario + repo + daemon
    nodo.publicar(archivos_pesos)       # sube y apunta el CID
    nodo.recuperar()                    # baja, verifica SHA-256 y restaura
    nodo.parar()                        # cierra el daemon

Cada pieza es un módulo independiente: ``rutas``, ``binario``, ``repositorio``,
``daemon``, ``cliente`` y ``pesos``. La fachada ``NodoIPFS`` los orquesta.
"""
from __future__ import annotations

from .cliente import ErrorIPFS
from .nodo import NodoIPFS, activar

__version__ = "1.0.0"

__all__ = ["ErrorIPFS", "NodoIPFS", "activar", "__version__"]
