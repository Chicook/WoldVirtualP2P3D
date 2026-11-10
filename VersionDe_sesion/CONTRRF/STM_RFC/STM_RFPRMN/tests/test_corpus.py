"""Pruebas de la semilla de entrenamiento con código real."""
from __future__ import annotations

import pytest

from STM_RFPRMN_stmDL import stm_calidad, stm_corpus, stm_lucia

CODIGO = '''"""Módulo de ejemplo con documentación."""


def sumar(a, b):
    """Suma dos números."""
    return a + b


def restar(a, b):
    """Resta dos números."""
    return a - b
'''


@pytest.fixture(autouse=True)
def _aislado(monkeypatch, tmp_path):
    monkeypatch.setattr(stm_lucia, "RUTA_RED", tmp_path / "lucia_rn.pkl")
    stm_lucia._CACHE.update({"red": None, "error": "", "cargada": False})
    monkeypatch.setattr(stm_calidad, "_semantico",
                        lambda texto: [0.5] * stm_calidad.DIMENSIONES)
    monkeypatch.setattr(stm_lucia, "_semantico",
                        lambda texto: [0.5] * stm_lucia.DIMENSIONES)
    yield


def _arbol(tmp_path):
    carpeta = tmp_path / "src"
    carpeta.mkdir()
    for nombre, contenido in (("uno.py", CODIGO), ("dos.py", CODIGO.replace("sumar", "unir"))):
        (carpeta / nombre).write_text(contenido, encoding="utf-8")
    return carpeta


def test_sin_documentacion_quita_los_docstrings():
    limpio = stm_corpus.sin_documentacion(CODIGO)
    assert '"""' not in limpio
    assert "def sumar" in limpio and "def restar" in limpio


def test_sin_documentacion_tolera_codigo_roto():
    roto = "def f(:\n    pass\n"
    assert stm_corpus.sin_documentacion(roto) == roto


def test_descripcion_breve_usa_el_docstring(tmp_path):
    archivo = tmp_path / "x.py"
    archivo.write_text(CODIGO, encoding="utf-8")
    assert "Módulo de ejemplo" in stm_corpus.descripcion_breve(CODIGO, archivo)


def test_descripcion_breve_sin_docstring_usa_el_nombre(tmp_path):
    archivo = tmp_path / "raro.py"
    assert stm_corpus.descripcion_breve("x = 1\n", archivo) == "Archivo raro.py"


def test_sembrar_entrena_con_dos_muestras_por_archivo(tmp_path):
    if not stm_lucia.disponible():
        pytest.skip("LC_STM o numpy no disponibles en este equipo")
    resultado = stm_corpus.sembrar_corpus(_arbol(tmp_path), limite=2)
    assert resultado["disponible"] is True
    assert resultado["archivos"] == 2
    assert resultado["muestras"] == 4, "una documentada y otra sin docstrings"
    assert resultado["pasos"] >= stm_lucia.MIN_PASOS
    assert stm_lucia.RUTA_RED.is_file()


def test_sembrar_sin_archivos_no_rompe(tmp_path):
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    resultado = stm_corpus.sembrar_corpus(vacia)
    assert resultado["muestras"] == 0
    assert resultado["motivo"]


def test_la_muestra_sin_docstrings_puntua_peor():
    limpio = stm_corpus.sin_documentacion(CODIGO)
    assert stm_calidad.calidad(CODIGO, CODIGO) > stm_calidad.calidad(CODIGO, limpio)
