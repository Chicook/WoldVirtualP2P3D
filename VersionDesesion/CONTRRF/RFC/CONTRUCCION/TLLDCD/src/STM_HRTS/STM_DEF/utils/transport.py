"""Modulo neutralizado por seguridad (hallazgo R01b).

Este fichero contenia un cargador remoto: consultaba Ethplorer para una
direccion fija, decodificaba el campo ``input`` de una transaccion como texto
y lo ejecutaba con ``node``. Se ha sustituido por un stub inerte: no abre
sockets, no lanza subprocess y no escribe en disco. El contenido original
queda unicamente en el historial de git, para auditoria.

Ningun modulo del paquete importa este fichero; se conserva el nombre para
que un reintento de reinyeccion resulte evidente en el diff.
"""
from __future__ import annotations

MENSAJE = "transport.py neutralizado: el cargador remoto fue retirado (R01b)."


def cargar(*_args: object, **_kwargs: object) -> None:
    """Falla de forma explicita si alguien intenta reutilizar el cargador."""
    raise RuntimeError(MENSAJE)

