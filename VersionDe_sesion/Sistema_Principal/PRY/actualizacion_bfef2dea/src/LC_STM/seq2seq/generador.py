"""Generador: la fachada del subsistema (codificar → buscar → devolver).

Uso típico::

    from LC_STM.seq2seq import crear
    gen = crear(ruta_memoria=".../seq2seq.json")
    gen.aprender("def sumar(a, b): ...", "def sumar(a, b):\\n    '''Suma.''' ...")
    resultado = gen.generar("def sumar(a, b): ...")
    resultado.texto
"""
from __future__ import annotations

from ._base import ConfigSeq2Seq, ErrorSeq2Seq, ResultadoGeneracion
from .codificador import Codificador
from .decodificador import Decodificador
from .memoria import MemoriaPares


class Generador:
    """Codificador + memoria + decodificador, con persistencia opcional."""

    def __init__(self, configuracion: ConfigSeq2Seq | None = None) -> None:
        self.config = configuracion or ConfigSeq2Seq()
        self.codificador = Codificador(self.config)
        self.decodificador = Decodificador(self.config)
        self.memoria = MemoriaPares(self.config.max_pares)
        self.memoria.cargar(self.config.memoria)

    # -- aprendizaje ------------------------------------------------------
    def aprender(self, peticion: str, respuesta: str,
                 meta: dict | None = None) -> int:
        """Guarda un par petición→respuesta; devuelve el total de pares."""
        vector = self.codificador.codificar(peticion)
        self.memoria.agregar(peticion, respuesta, vector, meta)
        return len(self.memoria)

    def aprender_lote(self, pares: list[tuple[str, str]]) -> int:
        """Aprende varios pares ``(peticion, respuesta)`` de golpe."""
        for peticion, respuesta in pares:
            try:
                self.aprender(peticion, respuesta)
            except ErrorSeq2Seq:
                continue
        return len(self.memoria)

    # -- generación -------------------------------------------------------
    def generar(self, peticion: str) -> ResultadoGeneracion:
        """Devuelve la respuesta aprendida más parecida (o lanza el error)."""
        vector = self.codificador.codificar(peticion)
        texto, similitud, meta = self.decodificador.decodificar(vector, self.memoria)
        return ResultadoGeneracion(texto=texto, similitud=similitud,
                                   origen="memoria", peticion=peticion, meta=meta)

    def intentar_generar(self, peticion: str) -> ResultadoGeneracion | None:
        """Como :meth:`generar` pero devuelve ``None`` en vez de lanzar."""
        try:
            return self.generar(peticion)
        except ErrorSeq2Seq:
            return None

    # -- estado y persistencia -------------------------------------------
    def guardar(self) -> str | None:
        """Persiste la memoria en la ruta configurada (``None`` si no hay)."""
        destino = self.memoria.guardar(self.config.memoria)
        return str(destino) if destino else None

    def estado(self) -> dict:
        """Resumen para diagnósticos."""
        try:
            from . import __version__ as version
        except Exception:  # noqa: BLE001 - versión no disponible
            version = ""
        return {"version": version, "dims": self.config.dims,
                "pares": len(self.memoria), "umbral": self.config.umbral,
                "memoria": self.config.ruta_memoria or "(sin persistencia)"}
