"""Pruebas del módulo ``test`` (diagnóstico de deuda técnica)."""
from __future__ import annotations

import builtins

import pytest

from STM_RFPRMN_stmDL import test as pruebas
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

SANO = '''"""Módulo de ejemplo bien documentado."""


def sumar(a: int, b: int) -> int:
    """Suma dos enteros y devuelve el resultado."""
    return a + b
'''

SUCIO = '''def f(a=[]):
    try:
        return a[0]
    except:
        return None
'''


@pytest.fixture
def archivos(tmp_path):
    sano = tmp_path / "sano.py"
    sano.write_text(SANO, encoding="utf-8")
    sucio = tmp_path / "sucio.py"
    sucio.write_text(SUCIO, encoding="utf-8")
    return sano, sucio


# --- Diagnóstico -------------------------------------------------------------

def test_un_archivo_sano_puntua_alto(archivos):
    informe = pruebas.diagnostico_deuda(archivos[0])
    assert informe["puntuacion"] >= 90
    assert informe["nivel"] == "sano"
    assert informe["sintaxis_ok"] is True


def test_un_archivo_sucio_puntua_bajo(archivos):
    informe = pruebas.diagnostico_deuda(archivos[1])
    assert informe["puntuacion"] < 90
    assert informe["nivel"] in ("aceptable", "revisar")
    motivos = " ".join(motivo for motivo, _ in informe["motivos"])
    assert "docstring" in motivos
    assert "genéricas" in motivos
    assert "mutables" in motivos


def test_el_informe_trae_los_hallazgos(archivos):
    informe = pruebas.diagnostico_deuda(archivos[1])
    assert any("docstring" in hallazgo for hallazgo in informe["hallazgos"])
    assert informe["lineas"] == len(SUCIO.splitlines())


def test_un_archivo_inexistente_falla(tmp_path):
    with pytest.raises(ErrorProyecto):
        pruebas.diagnostico_deuda(tmp_path / "no-existe.py")


def test_python_roto_puntua_cero(tmp_path):
    roto = tmp_path / "roto.py"
    roto.write_text("def f(:\n    pass\n", encoding="utf-8")
    informe = pruebas.diagnostico_deuda(roto)
    assert informe["sintaxis_ok"] is False
    assert informe["puntuacion"] == 0


def test_lenguaje_sin_ast_usa_delimitadores(tmp_path):
    cs = tmp_path / "x.cs"
    cs.write_text("class A { void M() { } }\n", encoding="utf-8")
    assert pruebas.diagnostico_deuda(cs)["sintaxis_ok"] is True
    roto = tmp_path / "roto.cs"
    roto.write_text("class A { void M() { \n", encoding="utf-8")
    informe = pruebas.diagnostico_deuda(roto)
    assert informe["sintaxis_ok"] is False
    assert informe["puntuacion"] <= 40


def test_el_formato_menciona_archivo_y_puntuacion(archivos):
    texto = pruebas.formatear(pruebas.diagnostico_deuda(archivos[0]))
    assert "Diagnóstico de deuda" in texto
    assert "sano.py" in texto
    assert "100" in texto or "90" in texto


# --- Comparación -------------------------------------------------------------

def test_la_comparacion_detecta_mejora(tmp_path):
    archivo = tmp_path / "mejora.py"
    archivo.write_text(SANO, encoding="utf-8")
    mensaje = pruebas.mensaje_comparacion(50, archivo)
    assert "mejora" in mensaje


def test_la_comparacion_detecta_empeora(tmp_path):
    archivo = tmp_path / "peor.py"
    archivo.write_text(SUCIO, encoding="utf-8")
    mensaje = pruebas.mensaje_comparacion(100, archivo)
    assert "empeora" in mensaje


def test_puntuacion_de_archivo_inexistente_no_rompe(tmp_path):
    assert pruebas.puntuacion_deuda(tmp_path / "nada.py") == 100


# --- Comandos ----------------------------------------------------------------

def test_comando_test_ruta_devuelve_informe(archivos):
    informe = pruebas.comando_test_ruta(archivos[0])
    assert informe["nivel"] == "sano"


def test_comando_test_ruta_avisa_si_no_existe(tmp_path):
    errores: list[str] = []
    original = pruebas.reportar_error
    pruebas.reportar_error = errores.append
    try:
        assert pruebas.comando_test_ruta(tmp_path / "nada.py") == {}
    finally:
        pruebas.reportar_error = original
    assert errores and "No existe" in errores[0]


def test_el_comando_pide_el_archivo(archivos, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *_a: str(archivos[0]))
    pruebas.comando_test()  # no debe lanzar


def test_el_comando_avisa_si_no_hay_ruta(monkeypatch):
    errores: list[str] = []
    monkeypatch.setattr(builtins, "input", lambda *_a: "")
    monkeypatch.setattr(pruebas, "reportar_error", errores.append)
    pruebas.comando_test()
    assert errores and "archivo" in errores[0]
