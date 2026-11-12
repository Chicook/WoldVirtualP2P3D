"""Tipos y configuración compartidos del subsistema seq2seq."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ErrorSeq2Seq(Exception):
    """Error controlado del subsistema (petición vacía, sin memoria, etc.)."""


@dataclass
class ConfigSeq2Seq:
    """Parámetros del codificador-decodificador.

    - ``dims``: dimensión del vector de petición (feature hashing).
    - ``umbral``: similitud mínima de coseno para aceptar una respuesta.
    - ``max_caracteres``: recorte de seguridad de la petición.
    - ``ruta_memoria``: JSON donde se persisten los pares aprendidos.
    """

    dims: int = 256
    umbral: float = 0.86
    max_caracteres: int = 12_000
    max_pares: int = 512
    ruta_memoria: str | None = None

    def a_dict(self) -> dict[str, Any]:
        """Serializa la configuración (para diagnósticos)."""
        return {"dims": self.dims, "umbral": self.umbral,
                "max_caracteres": self.max_caracteres,
                "max_pares": self.max_pares,
                "ruta_memoria": self.ruta_memoria}

    @property
    def memoria(self) -> Path | None:
        """Ruta de la memoria como ``Path`` (o ``None`` si no hay)."""
        return Path(self.ruta_memoria) if self.ruta_memoria else None


@dataclass
class ResultadoGeneracion:
    """Resultado de una generación: código y la traza de cómo se obtuvo."""

    texto: str
    similitud: float
    origen: str
    peticion: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def a_dict(self) -> dict[str, Any]:
        """Serializa el resultado (sin el texto completo si es muy largo)."""
        return {"similitud": round(self.similitud, 4), "origen": self.origen,
                "caracteres": len(self.texto), "meta": dict(self.meta)}
