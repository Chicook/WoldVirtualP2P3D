"""Pruebas de la conversión del informe .md a matriz y pesos neuronales."""
from __future__ import annotations

import json

import numpy as np
import pytest

from STM_RFPRMN_stmDL import stm_entrenamiento
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

INFORME = """# Informe de código · modulo.py

Resumen general del módulo.

## Deuda técnica

- 35 funciones sin docstring
- 12 líneas largas

## Hoja de ruta

1. Documentar las funciones con `comentar archivo`.
2. Partir el archivo si pasa de 450 líneas.

## Estructura

| Tipo | Nombre | Líneas |
|---|---|---|
| clase | `Neurona` | 22 |
"""


def _escribir(tmp_path, texto=INFORME, nombre="informe_modulo.md"):
    archivo = tmp_path / nombre
    archivo.write_text(texto, encoding="utf-8")
    return archivo


# --- Secciones y vectorización ----------------------------------------------

def test_parte_por_encabezados(tmp_path):
    secciones = stm_entrenamiento._secciones(INFORME)
    nombres = [nombre for nombre, _ in secciones]
    assert "Deuda técnica" in nombres
    assert "Hoja de ruta" in nombres
    assert nombres[0] == "resumen"


def test_sin_encabezados_usa_parrafos():
    secciones = stm_entrenamiento._secciones("uno\n\ndos\n\ntres")
    assert [nombre for nombre, _ in secciones] == [
        "parrafo_1", "parrafo_2", "parrafo_3"]


def test_vectorizar_es_determinista_y_normalizado():
    primero = stm_entrenamiento.vectorizar("documentar funciones de la red")
    segundo = stm_entrenamiento.vectorizar("documentar funciones de la red")
    assert primero == segundo
    assert pytest.approx(sum(v * v for v in primero), rel=1e-5) == 1.0


def test_vectorizar_ordena_por_parecido():
    base = stm_entrenamiento.vectorizar("documentar funciones sin docstring")
    cerca = stm_entrenamiento.vectorizar("documentar funciones")
    lejos = stm_entrenamiento.vectorizar("red neuronal convolucional imagen")

    def coseno(a, b):
        return sum(x * y for x, y in zip(a, b))

    assert coseno(base, cerca) > coseno(base, lejos)


def test_vectorizar_texto_vacio_da_ceros():
    assert set(stm_entrenamiento.vectorizar("   ")) == {0.0}


# --- Conversión a pesos ------------------------------------------------------

def test_convierte_el_informe_en_npz_y_json(tmp_path):
    archivo = _escribir(tmp_path)
    resultado = stm_entrenamiento.convertir_a_pesos(archivo, dims=32)
    assert resultado["npz"].is_file() and resultado["json"].is_file()
    datos = np.load(resultado["npz"])
    assert datos["X"].shape[1] == 32
    assert datos["X"].shape[0] == resultado["filas"]
    assert datos["W"].shape == (32, resultado["clases"])
    assert datos["b"].shape == (resultado["clases"],)
    assert set(datos["y"].tolist()) <= set(range(resultado["clases"]))


def test_los_metadatos_describen_la_matriz(tmp_path):
    archivo = _escribir(tmp_path)
    resultado = stm_entrenamiento.convertir_a_pesos(archivo, dims=16)
    meta = json.loads(resultado["json"].read_text(encoding="utf-8"))
    assert meta["dims"] == 16 and meta["filas"] == resultado["filas"]
    assert meta["fuente"].endswith("informe_modulo.md")
    assert "W: pesos" in meta["descripcion"]


def test_las_filas_son_las_secciones(tmp_path):
    archivo = _escribir(tmp_path)
    secciones = stm_entrenamiento._secciones(INFORME)
    resultado = stm_entrenamiento.convertir_a_pesos(archivo, dims=32)
    assert resultado["filas"] == len(secciones)


def test_un_solo_bloque_genera_dos_clases(tmp_path):
    archivo = _escribir(tmp_path, "Solo un párrafo sin encabezados.")
    resultado = stm_entrenamiento.convertir_a_pesos(archivo, dims=8)
    assert resultado["clases"] == 2


def test_informe_inexistente_falla(tmp_path):
    with pytest.raises(ErrorProyecto):
        stm_entrenamiento.convertir_a_pesos(tmp_path / "nada.md")


def test_informe_vacio_falla(tmp_path):
    archivo = _escribir(tmp_path, "   \n\n")
    with pytest.raises(ErrorProyecto):
        stm_entrenamiento.convertir_a_pesos(archivo)


def test_convertir_si_existe_no_rompe(tmp_path):
    assert stm_entrenamiento.convertir_si_existe(tmp_path / "nada.md") is None


def test_generar_informe_deja_la_matriz_al_lado(tmp_path, monkeypatch):
    from STM_RFPRMN_stmDL import stm_informe

    carpeta = tmp_path / "DatosDeEntrenamiento"
    carpeta.mkdir()
    archivo = tmp_path / "modulo.py"
    archivo.write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(stm_informe, "DIR_DOCS", carpeta)
    salida = stm_informe.generar_informe(archivo)
    assert salida.is_file()
    assert (carpeta / "informe_modulo_entrenamiento.npz").is_file()
    assert (carpeta / "informe_modulo_entrenamiento.json").is_file()
