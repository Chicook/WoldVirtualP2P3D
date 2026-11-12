"""Subsistema seq2seq de LC_STM: generar en vez de solo evaluar.

El resto de ``red_neuronal`` son **optimizadores** (numpy) que aprenden pesos y
sirven para *evaluar*: dada una ficha, estimar una calidad. No emiten texto.
Este paquete añade la pieza que faltaba —un **codificador-decodificador**— con
los mismos límites del proyecto: sólo numpy, sin dependencias externas, y con
persistencia en JSON.

Cómo genera, siendo honesto con lo que permite numpy
-----------------------------------------------------
No se entrena un transformer desde cero: sería imposible sin GPU y sin corpus
masivo. Lo que sí se puede construir y sí funciona es un **seq2seq de memoria**:

1. el **codificador** convierte la petición (código + descripción) en un vector
   por *feature hashing* de sus tokens;
2. la **memoria** guarda pares (vector de petición → texto de respuesta) que se
   han aceptado antes;
3. el **decodificador** busca el par más parecido por coseno y, si supera el
   umbral, devuelve *su* respuesta; si no, se niega en vez de inventar.

Es recuperación guiada por similitud, no generación libre: devuelve código que
ya se aprobó para una petición equivalente. Para lo que pide el comando
``ds ialocal`` (reutilizar decisiones anteriores coherentes) es exactamente lo
que hace falta; para inventar código nuevo hace falta un modelo de lenguaje.

Se integra con la red neuronal mediante :class:`puente_rn.NeuronaSeq2Seq`,
que implementa el mismo protocolo que ``NeuronaMemoriaBase``
(``forward``/``train_step``/``fit``/``predict``/``save``/``load``).
"""
from __future__ import annotations

__version__ = "1.0.0"

from ._base import ConfigSeq2Seq, ErrorSeq2Seq, ResultadoGeneracion
from .generador import Generador
from .memoria import MemoriaPares
from .puente_rn import NeuronaSeq2Seq
from .tokenizador import Tokenizador
from .vectorizador import Vectorizador

__all__ = [
    "ConfigSeq2Seq", "ErrorSeq2Seq", "Generador", "MemoriaPares",
    "NeuronaSeq2Seq", "ResultadoGeneracion", "Tokenizador", "Vectorizador",
    "crear", "health_check", "get_version",
]


def crear(ruta_memoria: str | None = None,
          dims: int = 256,
          umbral: float = 0.86) -> Generador:
    """Crea un generador listo para usar (carga la memoria si existe)."""
    configuracion = ConfigSeq2Seq(ruta_memoria=ruta_memoria, dims=dims,
                                  umbral=umbral)
    return Generador(configuracion)


def get_version() -> str:
    """Versión del subsistema."""
    return __version__


def health_check() -> dict:
    """Comprobación rápida: importa las piezas y verifica una generación vacía."""
    try:
        generador = crear()
        estado = generador.estado()
        return {"ok": True, "version": __version__, "dims": estado["dims"],
                "pares": estado["pares"], "umbral": estado["umbral"],
                "motivo": ""}
    except Exception as error:  # noqa: BLE001 - se informa del fallo
        return {"ok": False, "version": __version__, "motivo": str(error)}
