"""Del informe ``.md`` a matriz de entrenamiento y pesos neuronales.

El informe que redacta LucIA en ``STM_CH/PSNRL/DatosDeEntrenamiento`` es texto:
aquí se convierte en números que la red puede consumir.

1. Se parte el documento en **secciones** (encabezados ``##`` o párrafos).
2. Cada sección se vectoriza con *feature hashing* de sus tokens (``dims``
   valores normalizados), así que dos secciones parecidas quedan cerca.
3. Se obtiene la **matriz de entrenamiento** ``X`` (secciones × dims) y las
   etiquetas ``y`` (la sección a la que pertenece cada fila).
4. Se calculan los **pesos** de un clasificador de prototipos: ``W`` es la matriz
   de centroides traspuesta (dims × clases) y ``b`` el sesgo. Es un conjunto de
   pesos real, inicializable y entrenable con ``NeuralNetworkOptimizer``.

Se guarda en ``<nombre>_entrenamiento.npz`` (numpy) y un ``.json`` con metadatos
al lado del informe.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from .stm_base import ErrorProyecto, advertir, exito, informar

#: Dimensión por defecto del vector de sección.
DIMS = 64
#: Tokens con contenido (letras, mínimo 3 caracteres).
_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ_]{2,}")


def _secciones(texto: str) -> list[tuple[str, str]]:
    """Parte el Markdown en secciones (encabezado, cuerpo)."""
    secciones: list[tuple[str, list[str]]] = []
    actual = "resumen"
    lineas: list[str] = []
    for linea in (texto or "").splitlines():
        if linea.startswith("## "):
            secciones.append((actual, lineas))
            actual = linea[3:].strip()
            lineas = []
            continue
        lineas.append(linea)
    secciones.append((actual, lineas))
    resultado = [(nombre, "\n".join(cuerpo).strip())
                 for nombre, cuerpo in secciones if "\n".join(cuerpo).strip()]
    if len(resultado) > 1:
        return resultado
    # Sin encabezados: se usan los párrafos como secciones.
    parrafos = [p.strip() for p in (texto or "").split("\n\n") if p.strip()]
    return [(f"parrafo_{indice}", parrafo)
            for indice, parrafo in enumerate(parrafos, start=1)]


def vectorizar(texto: str, dims: int = DIMS) -> list[float]:
    """Vector normalizado de un texto (feature hashing determinista)."""
    valores = [0.0] * max(8, dims)
    for token in _TOKEN.findall((texto or "").lower()):
        digest = hashlib.sha256(token.encode("utf-8", "replace")).digest()
        posicion = int.from_bytes(digest[:4], "big") % len(valores)
        valores[posicion] += 1.0 if digest[4] % 2 == 0 else -1.0
    norma = math.sqrt(sum(valor * valor for valor in valores))
    if norma <= 0.0:
        return valores
    return [valor / norma for valor in valores]


def _pesos_por_prototipo(X, y, clases: int) -> tuple:
    """Centroides por clase como pesos (``W``) y sesgo (``b``)."""
    import numpy as np

    centroides = np.zeros((clases, X.shape[1]), dtype=np.float32)
    cuentas = np.zeros(clases, dtype=np.float32)
    for fila, clase in zip(X, y):
        centroides[clase] += fila
        cuentas[clase] += 1.0
    cuentas[cuentas == 0] = 1.0
    centroides /= cuentas[:, None]
    pesos = centroides.T.copy()
    sesgo = -0.5 * np.sum(centroides * centroides, axis=1)
    return pesos, sesgo.astype(np.float32)


def convertir_a_pesos(ruta_md: str | Path, dims: int = DIMS) -> dict:
    """Convierte el informe en ``.npz`` (matriz + pesos) y ``.json`` (metadatos)."""
    import numpy as np

    origen = Path(ruta_md)
    if not origen.is_file():
        raise ErrorProyecto(f"No existe el informe: {origen}")
    texto = origen.read_text(encoding="utf-8-sig")
    secciones = _secciones(texto)
    if not secciones:
        raise ErrorProyecto("El informe está vacío: no hay nada que convertir.")
    nombres = [nombre for nombre, _ in secciones]
    indice = {nombre: posicion for posicion, nombre in enumerate(nombres)}
    clases = len(indice)
    if clases < 2:  # una sola sección: dos clases para que la red tenga salida
        nombres = ["documento", "documento"]
        indice = {"documento": 0}
        clases = 2
    X = np.asarray([vectorizar(cuerpo, dims) for _, cuerpo in secciones],
                   dtype=np.float32)
    y = np.asarray([indice.get(nombre, 0) for nombre in nombres[:len(secciones)]],
                   dtype=np.int64)
    pesos, sesgo = _pesos_por_prototipo(X, y, clases)
    destino = origen.with_suffix("")
    ruta_npz = destino.with_name(destino.name + "_entrenamiento.npz")
    ruta_json = destino.with_name(destino.name + "_entrenamiento.json")
    np.savez(ruta_npz, X=X, y=y, W=pesos, b=sesgo)
    metadatos = {
        "fuente": str(origen), "dims": X.shape[1], "filas": int(X.shape[0]),
        "clases": clases, "secciones": [nombre for nombre, _ in secciones],
        "descripcion": "X: matriz de entrenamiento; y: etiquetas; W: pesos; b: sesgo",
    }
    ruta_json.write_text(json.dumps(metadatos, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    informar(f"Entrenamiento: {X.shape[0]} filas × {X.shape[1]} dims · "
             f"{clases} clases · pesos {pesos.shape}.")
    exito(f"Matriz y pesos guardados: {ruta_npz.name} y {ruta_json.name}")
    return {"npz": ruta_npz, "json": ruta_json, "filas": int(X.shape[0]),
            "dims": int(X.shape[1]), "clases": clases}


def convertir_si_existe(ruta_md: str | Path) -> dict | None:
    """Convierte el informe si está; nunca interrumpe el flujo que lo generó."""
    try:
        return convertir_a_pesos(ruta_md)
    except (ErrorProyecto, OSError, ImportError) as error:
        advertir(f"No se pudo convertir el informe a pesos ({error}).")
        return None
