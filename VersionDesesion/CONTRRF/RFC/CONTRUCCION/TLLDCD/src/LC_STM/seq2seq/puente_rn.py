"""Puente entre el seq2seq y la familia ``red_neuronal``.

``NeuronaMemoriaBase`` (RF_SL/RFSL1) define el protocolo que entiende la red:
``forward``, ``train_step``, ``fit``, ``predict``, ``obtener_estadisticas``,
``save``/``load``, ``params_count`` e ``info``. Esta clase lo implementa sobre
una **memoria asociativa** de vectores, de modo que el resto de la arquitectura
puede tratar el seq2seq como una neurona más, sin saber que por debajo guarda
pares de texto.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ._base import ConfigSeq2Seq, ErrorSeq2Seq
from .codificador import Codificador
from .generador import Generador
from .vectorizador import similitud_coseno


class NeuronaSeq2Seq:
    """Neurona asociativa compatible con ``NeuronaMemoriaBase``.

    ``forward(e)`` devuelve la salida memorizada más parecida a ``e``;
    ``train_step(e, salida)`` memoriza el par. Los textos viven en un
    :class:`Generador` para poder recuperarlos por similitud.
    """

    def __init__(self, input_size: int = 256, output_size: int = 256,
                 nombre: str = "Seq2Seq", configuracion: ConfigSeq2Seq | None = None) -> None:
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.config = configuracion or ConfigSeq2Seq(dims=self.input_size)
        self.generador = Generador(self.config)
        self.codificador = Codificador(self.config)
        self._entradas: list[list[float]] = []
        self._salidas: list[list[float]] = []
        self.pasos = 0

    # -- protocolo de neurona --------------------------------------------
    def inicializar_pesos(self) -> None:
        """Sin pesos: la 'memoria' son los pares. Se mantiene por protocolo."""
        self._entradas = []
        self._salidas = []

    def forward(self, e: np.ndarray) -> np.ndarray:
        """Salida memorizada más cercana a ``e`` (ceros si no hay memoria)."""
        vector = np.asarray(e, dtype=np.float32).ravel().tolist()
        if not self._entradas:
            return np.zeros((1, self.output_size), dtype=np.float32)
        mejor, mejor_similitud = None, -2.0
        for entrada, salida in zip(self._entradas, self._salidas):
            similitud = similitud_coseno(vector, entrada)
            if similitud > mejor_similitud:
                mejor, mejor_similitud = salida, similitud
        return np.asarray([mejor], dtype=np.float32)

    def train_step(self, entrada: np.ndarray, objetivo: np.ndarray) -> dict[str, float]:
        """Memoriza el par de vectores; devuelve una pérdida coseno."""
        x = np.asarray(entrada, dtype=np.float32).ravel().tolist()
        y = np.asarray(objetivo, dtype=np.float32).ravel().tolist()
        self._entradas.append(x)
        self._salidas.append(y)
        self.pasos += 1
        return {"loss": float(1.0 - similitud_coseno(x, y)), "pasos": float(self.pasos)}

    def fit(self, X: np.ndarray, y: np.ndarray,
            epochs: int = 1, verbose: bool = False) -> list[float]:
        """Entrena ``epochs`` pasadas sobre el lote (memoriza cada par)."""
        perdidas: list[float] = []
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)
        for _ in range(max(1, int(epochs))):
            perdida = 0.0
            for indice in range(len(X)):
                resultado = self.train_step(X[indice], y[indice])
                perdida += resultado["loss"]
            perdidas.append(perdida / max(1, len(X)))
        return perdidas

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predicción para cada fila de ``X``."""
        X = np.asarray(X, dtype=np.float32)
        if X.ndim == 1:
            return self.forward(X)
        return np.vstack([self.forward(fila) for fila in X])

    # -- textos -----------------------------------------------------------
    def aprender_texto(self, peticion: str, respuesta: str,
                       meta: dict | None = None) -> int:
        """Aprende un par de textos (lo usa el flujo de refactor)."""
        return self.generador.aprender(peticion, respuesta, meta)

    def generar_texto(self, peticion: str):
        """Devuelve el ``ResultadoGeneracion`` o ``None`` si no hay nada válido."""
        return self.generador.intentar_generar(peticion)

    # -- estado y persistencia -------------------------------------------
    def obtener_estadisticas(self) -> dict[str, Any]:
        """Estadísticas con el mismo estilo que el resto de neuronas."""
        return {"nombre": self.nombre, "input_size": self.input_size,
                "output_size": self.output_size, "pasos": self.pasos,
                "pares": len(self.generador.memoria),
                "historial_activaciones_len": len(self._entradas),
                "historial_gradientes_len": 0}

    def params_count(self) -> int:
        """Parámetros equivalentes: los valores memorizados."""
        return sum(len(fila) for fila in self._entradas) + sum(
            len(fila) for fila in self._salidas)

    def info(self) -> str:
        """Línea corta de identificación."""
        return (f"{self.nombre}(in={self.input_size},out={self.output_size},"
                f"pares={len(self.generador.memoria)},pasos={self.pasos})")

    def save(self, filepath: str | Path) -> None:
        """Guarda vectores (JSON) y memoria de textos junto al archivo."""
        destino = Path(filepath)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"entradas": self._entradas,
                                       "salidas": self._salidas,
                                       "pasos": self.pasos}, ensure_ascii=False),
                           encoding="utf-8")
        self.generador.memoria.guardar(str(destino.with_suffix(".memoria.json")))

    def load(self, filepath: str | Path) -> None:
        """Carga vectores y memoria si existen."""
        origen = Path(filepath)
        if origen.is_file():
            try:
                datos = json.loads(origen.read_text(encoding="utf-8"))
                self._entradas = list(datos.get("entradas", []))
                self._salidas = list(datos.get("salidas", []))
                self.pasos = int(datos.get("pasos", len(self._entradas)))
            except (OSError, ValueError) as error:
                raise ErrorSeq2Seq(f"No se pudo cargar la neurona ({error}).") from error
        self.generador.memoria.cargar(str(origen.with_suffix(".memoria.json")))

    def __str__(self) -> str:
        return self.info()
