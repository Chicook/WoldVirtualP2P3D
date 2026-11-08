"""Pruebas del puente LucIA ↔ red neuronal (expediente y aprendizaje)."""
from __future__ import annotations

import pytest

from STM_RFPRMN_stmDL import stm_calidad, stm_lucia
from STM_RFPRMN_stmDL.stm_analisis import analizar_archivo_local

CODIGO = '''"""Módulo de ejemplo."""


def sumar(a, b):
    """Suma dos números."""
    return a + b


def restar(a, b):
    return a - b
'''


@pytest.fixture(autouse=True)
def _red_aislada(monkeypatch, tmp_path):
    """Cada prueba usa pesos propios, caché limpia y sin red."""
    monkeypatch.setattr(stm_lucia, "RUTA_RED", tmp_path / "lucia_rn.pkl")
    stm_lucia._CACHE.update({"red": None, "error": "", "cargada": False})
    # La parte semántica se fija para no depender de Ollama en las pruebas.
    monkeypatch.setattr(stm_lucia, "_semantico",
                        lambda texto: [0.5] * stm_lucia.DIMENSIONES)
    monkeypatch.setattr(stm_calidad, "_semantico",
                        lambda texto: [0.5] * stm_calidad.DIMENSIONES)
    monkeypatch.setattr(stm_lucia, "estado_embeddings",
                        lambda: {"ok": False, "modelo": "", "dim": 0,
                                 "motivo": "prueba"})
    monkeypatch.setattr(stm_lucia, "describir_embeddings",
                        lambda: "Embeddings: no disponibles (prueba).")
    yield


def _expediente(tmp_path, contenido: str = CODIGO):
    archivo = tmp_path / "ejemplo.py"
    archivo.write_text(contenido, encoding="utf-8")
    analisis = analizar_archivo_local(archivo)
    return stm_lucia.preparar(archivo, contenido, analisis,
                              "Suma y resta números enteros.")


# --- Expediente --------------------------------------------------------------

def test_el_expediente_incluye_descripcion_y_deuda(tmp_path):
    expediente = _expediente(tmp_path)
    assert "Suma y resta" in expediente.descripcion
    assert expediente.deuda, "siempre debe haber al menos una línea de deuda"
    assert "Deuda técnica" in expediente.readme


def test_el_readme_detalla_la_deuda_del_archivo(tmp_path):
    expediente = _expediente(tmp_path)
    assert "ejemplo.py" in expediente.readme
    assert "funciones sin docstring" in expediente.readme.lower()
    assert "Criterios para el refactor" in expediente.readme


def test_la_deuda_detecta_los_problemas_reales(tmp_path):
    archivo = tmp_path / "feo.py"
    contenido = "\n".join(
        [f"def f{i}(x=[]):\n    return x" for i in range(30)])
    archivo.write_text(contenido, encoding="utf-8")
    analisis = analizar_archivo_local(archivo)
    deuda = " ".join(stm_lucia.deuda_tecnica(analisis))
    assert "docstring" in deuda
    assert "mutables" in deuda


def test_el_contexto_es_compacto_y_menciona_la_deuda(tmp_path):
    expediente = _expediente(tmp_path)
    contexto = expediente.contexto
    assert "[CONTEXTO DEL ARCHIVO" in contexto
    assert "[DEUDA TÉCNICA" in contexto
    assert "[LENGUAJE] .py" in contexto
    assert len(contexto) < 900


# --- Vector de entrada -------------------------------------------------------

def test_el_vector_tiene_la_dimension_de_la_red(tmp_path):
    expediente = _expediente(tmp_path)
    assert len(expediente.vector) == stm_lucia.ALTO
    assert all(0.0 <= valor <= 1.0 for valor in expediente.vector)


def test_el_vector_es_estable(tmp_path):
    primero = _expediente(tmp_path).vector
    segundo = _expediente(tmp_path).vector
    assert primero == segundo


def test_el_vector_incluye_la_parte_semantica(tmp_path, monkeypatch):
    monkeypatch.setattr(stm_lucia, "_semantico",
                        lambda texto: [0.25] * stm_lucia.DIMENSIONES)
    expediente = _expediente(tmp_path)
    assert len(expediente.vector) == 11 + stm_lucia.DIMENSIONES
    assert expediente.vector[-stm_lucia.DIMENSIONES:] == [0.25] * stm_lucia.DIMENSIONES


# --- Vector de calidad -------------------------------------------------------

def test_el_objetivo_penaliza_perder_definiciones():
    original = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"
    candidato = "def a():\n    return 1\n"
    fidelidad, _limpieza, seguro = stm_lucia.objetivo(original, candidato)
    assert fidelidad == pytest.approx(0.5)
    assert seguro == 1.0


def test_el_objetivo_marca_el_vacio_como_inseguro():
    assert stm_lucia.objetivo("def a():\n    return 1\n", "")[2] == 0.0


def test_el_objetivo_penaliza_pasarse_del_tope():
    original = "def a():\n    return 1\n"
    enorme = original + "\n" + "\n".join(f"x{i} = {i}"
                                         for i in range(stm_lucia.LIMITE_LINEAS_REFACTOR + 5))
    assert stm_lucia.objetivo(original, enorme)[2] == 0.0


# --- Aprendizaje -------------------------------------------------------------

def test_sin_red_el_flujo_no_se_rompe(tmp_path, monkeypatch):
    expediente = _expediente(tmp_path)
    monkeypatch.setattr(stm_lucia, "_obtener_red", lambda: None)
    stm_lucia._CACHE["error"] = "sin red"
    veredicto = stm_lucia.evaluar_y_aprender(expediente, CODIGO, CODIGO)
    assert veredicto["disponible"] is False
    assert veredicto["aceptado"] is True


def test_las_primeras_muestras_no_rechazan(tmp_path):
    if not stm_lucia.disponible():
        pytest.skip("LC_STM o numpy no disponibles en este equipo")
    expediente = _expediente(tmp_path)
    veredicto = stm_lucia.evaluar_y_aprender(expediente, CODIGO, CODIGO)
    assert veredicto["disponible"] is True
    assert veredicto["aceptado"] is True
    assert "aprendiendo" in veredicto["motivo"]


def test_aprender_persiste_los_pesos(tmp_path):
    if not stm_lucia.disponible():
        pytest.skip("LC_STM o numpy no disponibles en este equipo")
    expediente = _expediente(tmp_path)
    stm_lucia.evaluar_y_aprender(expediente, CODIGO, CODIGO)
    assert stm_lucia.RUTA_RED.is_file(), "la red debe guardar lo aprendido"
    assert stm_lucia.pasos_aprendidos() >= 1


def test_el_estado_refleja_la_arquitectura(tmp_path):
    estado = stm_lucia.estado()
    assert estado["disponible"] is True
    assert estado["arquitectura"] == f"{stm_lucia.ENTRADA}x{stm_lucia.SALIDA}"
    assert "red neuronal" in stm_lucia.describir()
