"""Vigilancia continua de salida (servicio periodico) de STM_DEF.

El monitor hacia pasadas puntuales; aqui pasa a **servicio**: una o varias
pasadas periodicas que observan las conexiones salientes y los procesos vivos y
entregan una alerta por cada contacto con la infraestructura C2. Es lo contrario
del dropper, que abria su canal una vez y lo ocultaba: aqui el canal, si existe,
se ve y se avisa.

No modifica nada: reutiliza ``monitor.revisar`` y ``monitor.procesos_con_c2``
(solo lectura) y se puede ejecutar en primer plano (``ejecutar``) o en segundo
plano (``iniciar``/``detener``) mediante un hilo daemon.
"""
from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional

from . import monitor
from .modelos import Alerta

#: Callback invocado por cada alerta nueva.
CallbackAlerta = Callable[[Alerta], None]


class ServicioVigilancia:
    """Servicio de vigilancia periodica de la salida de red.

    Cada ``paso`` enumera las conexiones salientes y los procesos con
    referencias C2 y entrega cada alerta al ``callback``. Acumula las alertas en
    ``self.alertas`` y cuenta los ciclos en ``self.ciclos``.
    """

    def __init__(
        self,
        intervalo: float = 60.0,
        resolver: bool = False,
        callback: Optional[CallbackAlerta] = None,
    ) -> None:
        self.intervalo = max(1.0, float(intervalo))
        self.resolver = resolver
        self.callback = callback
        self.alertas: List[Alerta] = []
        self.ciclos = 0
        self._hilo: Optional[threading.Thread] = None
        self._parar = threading.Event()

    # --------------------------------------------------------------- una pasada
    def paso(self) -> List[Alerta]:
        """Una pasada de vigilancia; devuelve e informa las alertas nuevas."""
        nuevas = monitor.revisar(resolver=self.resolver)
        nuevas.extend(monitor.procesos_con_c2())
        self.ciclos += 1
        for alerta in nuevas:
            if self.callback is not None:
                self.callback(alerta)
        self.alertas.extend(nuevas)
        return nuevas

    # ------------------------------------------------------------ primer plano
    def ejecutar(self, ciclos: int = 1) -> List[Alerta]:
        """Vigila en primer plano ``ciclos`` veces (``ciclos <= 0`` = continuo).

        En modo continuo solo termina al agotarse el ``ciclos``, al llamar a
        ``detener`` desde otro hilo o al propagarse un ``KeyboardInterrupt``.
        """
        if ciclos <= 0:
            while not self._parar.is_set():
                self.paso()
                self._parar.wait(self.intervalo)
            return self.alertas
        for indice in range(ciclos):
            self.paso()
            if indice < ciclos - 1:
                self._parar.wait(self.intervalo)
        return self.alertas

    # ------------------------------------------------------------ hilo daemon
    @property
    def activo(self) -> bool:
        """True si el servicio corre en segundo plano."""
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self) -> None:
        """Arranca la vigilancia periodica en un hilo daemon (idempotente)."""
        if self.activo:
            return
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name="STM_DEF-vigilancia", daemon=True)
        self._hilo.start()

    def detener(self, espera: float = 5.0) -> None:
        """Detiene el servicio y espera a que el hilo termine."""
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=espera)
            self._hilo = None

    def _bucle(self) -> None:
        while not self._parar.is_set():
            self.paso()
            self._parar.wait(self.intervalo)

    def resumen(self) -> Dict[str, object]:
        """Vista serializable del estado del servicio."""
        return {"activo": self.activo, "ciclos": self.ciclos, "alertas": len(self.alertas)}


__all__ = ["ServicioVigilancia", "CallbackAlerta"]
