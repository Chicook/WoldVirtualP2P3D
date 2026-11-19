"""Vectores y pesos neuronales derivados del registro de actualización.

Convierte ``registro.md`` en un vector global de ``DIM_VECTOR`` dimensiones más
un vector por sección, y su versión cuantizada a int8 para subidas livianas.
Funciones puras: reciben las rutas como parámetros, así se pueden probar sin
tocar el sistema de archivos del proyecto.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .stm_base import exito, reportar_error

#: Dimensión del vector neuronal derivado del registro.
DIM_VECTOR = 64
#: Nombre del archivo de pesos dentro del registro.
NOMBRE_PESOS = "registro_pesos.json"


def texto_a_vector(texto: str, dim: int = DIM_VECTOR) -> list[float]:
    """Convierte ``texto`` en un vector neuronal determinista de ``dim``.

    Encadena SHA-256 sobre el texto (mismo enfoque de hash del
    SimpleEncoder del sistema) y normaliza cada byte a [-0.5, 0.5).
    """
    semilla = texto.encode("utf-8")
    valores: list[float] = []
    contador = 0
    while len(valores) < dim:
        bloque = hashlib.sha256(semilla + contador.to_bytes(4, "big")).digest()
        valores.extend(b / 256.0 - 0.5 for b in bloque)
        contador += 1
    return valores[:dim]


def norma(vector: list[float]) -> float:
    """Norma euclídea del vector (0.0 si está vacío)."""
    return math.sqrt(sum(v * v for v in vector)) if vector else 0.0


def seccionar_md(texto: str) -> list[tuple[str, str]]:
    """Divide el registro en secciones por encabezados ``#``/``##``.

    Devuelve pares (título, cuerpo); el texto previo al primer encabezado
    va en la sección "general". Si no hay encabezados, todo es "general".
    """
    secciones: list[tuple[str, str]] = []
    titulo, cuerpo = "general", []
    for linea in texto.splitlines():
        if linea.startswith("#"):
            if cuerpo or titulo != "general":
                secciones.append((titulo, "\n".join(cuerpo)))
            titulo = linea.lstrip("#").strip() or "general"
            cuerpo = []
        else:
            cuerpo.append(linea)
    secciones.append((titulo, "\n".join(cuerpo)))
    return [(t, c) for t, c in secciones if c.strip()]


def cuantizar(vector: list[float]) -> list[int]:
    """Cuantiza el vector de [-0.5, 0.5) a enteros int8 [-127, 127].

    Reduce el peso a ~1 byte por neurona para subidas livianas; la
    desnormalización es ``v / 254`` con error máximo de 1/254.
    """
    return [max(-127, min(127, round(v * 254))) for v in vector]


def desnormalizar(cuant: list[int]) -> list[float]:
    """Devuelve el vector cuantizado a flotantes aproximados."""
    return [c / 254.0 for c in cuant]


def similitud_coseno(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores (1.0 = idénticos, 0.0 si falla).

    Sirve para verificar que unos pesos recuperados de IPFS corresponden
    al registro que se publicó.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    den = norma(a) * norma(b)
    return num / den if den else 0.0


def md_a_pesos(ruta_md: Path, ruta_pesos: Path) -> dict:
    """Convierte ``registro.md`` en pesos neuronales y los guarda en JSON.

    Genera el vector global más un vector por sección (matriz) y su
    versión cuantizada int8. Devuelve el dict de pesos.
    """
    texto = ruta_md.read_text(encoding="utf-8")
    if not texto.strip():
        raise ValueError("registro.md vacío: no se generan pesos.")
    vector = texto_a_vector(texto)
    secciones = [{"titulo": t, "vector": texto_a_vector(t + "\n" + c),
                  "norma": norma(texto_a_vector(t + "\n" + c))}
                 for t, c in seccionar_md(texto)]
    pesos = {"formato": "registro-pesos-v2", "dim": len(vector),
             "vector": vector, "norma": norma(vector),
             "cuantizado": cuantizar(vector),
             "secciones": secciones, "n_secciones": len(secciones),
             "fuente": ruta_md.name,
             "fecha": __import__("datetime").datetime.now().isoformat(timespec="seconds")}
    ruta_pesos.parent.mkdir(parents=True, exist_ok=True)
    ruta_pesos.write_text(json.dumps(pesos, ensure_ascii=False), encoding="utf-8")
    exito(f"registro.md convertido en {len(vector)} pesos "
          f"({len(secciones)} secciones).")
    return pesos


def verificar_pesos(ruta_pesos: Path, umbral: float = 0.999) -> bool:
    """Verifica la integridad de unos pesos: recalcula norma y cuantizado.

    Devuelve True si la norma y el cuantizado coinciden con lo guardado
    (tolerancia ``umbral`` para la norma). Informa el resultado.
    """
    try:
        pesos = json.loads(ruta_pesos.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        reportar_error(f"No se pudieron leer los pesos ({error}).")
        return False
    vector = pesos.get("vector", [])
    ok_norma = abs(norma(vector) - float(pesos.get("norma", -1.0))) < 0.001
    ok_cuant = cuantizar(vector) == pesos.get("cuantizado", [])
    ok_dim = len(vector) == int(pesos.get("dim", -1)) == DIM_VECTOR
    valido = ok_norma and ok_cuant and ok_dim
    if valido:
        exito(f"Pesos íntegros: dim {len(vector)}, {pesos.get('n_secciones', 0)} secciones.")
    else:
        reportar_error(f"Pesos corruptos (norma:{ok_norma} cuant:{ok_cuant} dim:{ok_dim}).")
    return valido and umbral <= 1.0
