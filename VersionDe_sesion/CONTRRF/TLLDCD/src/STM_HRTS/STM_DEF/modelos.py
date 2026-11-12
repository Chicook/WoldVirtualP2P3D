"""Modelos de datos compartidos por el subsistema STM_DEF.

Tipos inmutables y funciones puras de puntuacion/clasificacion. Ningun modulo
de STM_DEF define sus propias estructuras: todo pasa por aqui para que el
informe, los hallazgos y las alertas sean homogeneos y testeables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- severidades, de mayor a menor gravedad -------------------------------
ALTA = "ALTA"
MEDIA = "MEDIA"
BAJA = "BAJA"
INFO = "INFO"
LIMPIO = "LIMPIO"

ORDEN_SEVERIDAD: Tuple[str, ...] = (ALTA, MEDIA, BAJA, INFO)

#: Peso por defecto de cada severidad cuando un patron no fija el suyo.
PESO_SEVERIDAD: Dict[str, int] = {ALTA: 40, MEDIA: 15, BAJA: 5, INFO: 0}


@dataclass(frozen=True)
class Patron:
    """Un indicador de compromiso expresado como expresion regular."""

    id: str
    regex: str
    severidad: str
    descripcion: str
    peso: int = 0

    def peso_efectivo(self) -> int:
        return self.peso or PESO_SEVERIDAD.get(self.severidad, 0)


@dataclass(frozen=True)
class Hallazgo:
    """Coincidencia de un indicador sobre un texto, fichero o comando."""

    id: str
    severidad: str
    descripcion: str
    origen: str = ""
    linea: int = 0
    fragmento: str = ""
    repeticiones: int = 1

    def como_texto(self) -> str:
        ubicacion = self.origen or "(memoria)"
        if self.linea:
            ubicacion = f"{ubicacion}:{self.linea}"
        cola = f"  (+{self.repeticiones - 1})" if self.repeticiones > 1 else ""
        return f"[{self.severidad}] {self.id}  {ubicacion}  {self.descripcion}{cola}"


@dataclass
class Conexion:
    """Una conexion de red saliente observada en el equipo."""

    pid: int = 0
    proceso: str = ""
    ip_remota: str = ""
    puerto_remoto: int = 0
    host_remoto: str = ""
    estado: str = ""

    def destino(self) -> str:
        host = self.host_remoto or self.ip_remota or "?"
        return f"{host}:{self.puerto_remoto}" if self.puerto_remoto else host


@dataclass
class Alerta:
    """Veredicto sobre una conexion o un artefacto."""

    severidad: str
    motivo: str
    detalle: str = ""
    conexion: Optional[Conexion] = None

    def como_texto(self) -> str:
        base = f"[{self.severidad}] {self.motivo}"
        if self.conexion is not None:
            base += f"  {self.conexion.proceso or '?'} (pid {self.conexion.pid}) -> {self.conexion.destino()}"
        if self.detalle:
            base += f"  {self.detalle}"
        return base


@dataclass
class Informe:
    """Resultado agregado de una pasada del motor."""

    hallazgos: List[Hallazgo] = field(default_factory=list)
    alertas: List[Alerta] = field(default_factory=list)
    resumen: Dict[str, object] = field(default_factory=dict)

    def extension(self, otros: "Informe") -> None:
        """Acumula otro informe en este."""
        self.hallazgos.extend(otros.hallazgos)
        self.alertas.extend(otros.alertas)

    def puntos(self) -> int:
        total = sum(p.peso_efectivo() for p in (_patron_de(h) for h in self.hallazgos))
        total += sum(PESO_SEVERIDAD.get(a.severidad, 0) for a in self.alertas)
        return total

    def veredicto(self) -> str:
        return clasificar(self.puntos())


def _patron_de(hallazgo: Hallazgo) -> Patron:
    """Reconstruye el peso de un hallazgo a partir de su severidad."""
    return Patron(hallazgo.id, "", hallazgo.severidad, hallazgo.descripcion)


def puntuar(hallazgos: List[Hallazgo]) -> int:
    """Suma los pesos efectivos de una lista de hallazgos."""
    return sum(_patron_de(h).peso_efectivo() for h in hallazgos)


def clasificar(puntos: int) -> str:
    """Traduce una puntuacion a un veredicto cualitativo."""
    if puntos >= 60:
        return ALTA
    if puntos >= 25:
        return MEDIA
    if puntos > 0:
        return BAJA
    return LIMPIO
