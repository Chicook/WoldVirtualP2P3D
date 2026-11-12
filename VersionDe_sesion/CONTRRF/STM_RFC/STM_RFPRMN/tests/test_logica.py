"""Pruebas del comando «crear logica» y de su módulo."""
from __future__ import annotations

import ast
import builtins
from pathlib import Path

import pytest

from STM_RFPRMN_stmDL import stm_logica
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

LOGICA = '''def sumar_enteros(a: int, b: int) -> int:
    """Suma dos enteros validando el tipo."""
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Se esperaban enteros")
    return a + b
'''

EXISTENTE = '''"""Modulo previo."""


def restar(a: int, b: int) -> int:
    """Resta dos enteros."""
    return a - b
'''


@pytest.fixture(autouse=True)
def _confirmar(monkeypatch):
    monkeypatch.setattr(stm_logica, "pedir_confirmacion", lambda *_a: True)
    yield


def _consultor(texto: str, _analisis) -> str:
    return f"Diseño para: {texto[:40]}"


# --- Nombre y lenguaje -------------------------------------------------------

def test_el_nombre_sale_de_la_peticion():
    nombre = stm_logica.nombre_desde("Una función que sume dos números")
    assert nombre.startswith("logica_")
    assert nombre.endswith(".py")
    assert "sume" in nombre and "numeros" in nombre


def test_el_nombre_ignora_acentos_y_palabras_vacias():
    assert "funcion" not in stm_logica.nombre_desde("La función básica")


def test_el_nombre_tolera_peticiones_raras():
    assert stm_logica.nombre_desde("¿¿??") == "logica_nueva.py"


def test_lenguaje_por_extension(tmp_path):
    assert stm_logica._lenguaje_de(tmp_path / "x.cs") == "csharp"
    assert stm_logica._lenguaje_de(tmp_path / "x.py") == "python"
    assert stm_logica._lenguaje_de(tmp_path / "x.raro") == "python"


def test_extension_por_lenguaje(tmp_path):
    assert stm_logica._extension("python", tmp_path / "x") == ".py"
    assert stm_logica._extension("csharp", tmp_path / "x") == ".cs"


# --- Diseño y validación -----------------------------------------------------

def test_el_diseno_usa_el_consultor():
    assert stm_logica.disenar("sumar", Path("x.py"), "python",
                              _consultor).startswith("Diseño para:")


def test_el_diseno_sin_peticion_falla():
    with pytest.raises(ErrorProyecto):
        stm_logica.disenar("   ", Path("x.py"), "python")


def test_diseno_de_respaldo_menciona_la_peticion():
    texto = stm_logica.diseno_de_respaldo("ordenar una lista", "python")
    assert "ordenar una lista" in texto


def test_validar_logica_quita_cercas():
    assert stm_logica.validar_logica("```python\nx = 1\n```",
                                     Path("x.py")) == "x = 1\n"


def test_validar_logica_rechaza_vacio():
    with pytest.raises(ErrorProyecto):
        stm_logica.validar_logica("  ", Path("x.py"))


def test_validar_logica_rechaza_sintaxis_rota():
    with pytest.raises(ErrorProyecto):
        stm_logica.validar_logica("def f(:\n    pass", Path("x.py"))


# --- Creación ----------------------------------------------------------------

def test_crear_logica_en_archivo_nuevo(tmp_path, monkeypatch):
    destino = tmp_path / "nueva.py"
    monkeypatch.setattr(stm_logica, "generar_logica", lambda *_a, **_k: LOGICA)
    monkeypatch.setattr(stm_logica, "_aprender", lambda *_a: None)
    monkeypatch.setattr(stm_logica, "comando_test_ruta", lambda *_a: {})
    assert stm_logica.crear_logica("sumar enteros", str(destino), "python",
                                   consultor=_consultor) is True
    assert destino.read_text(encoding="utf-8") == LOGICA
    ast.parse(destino.read_text(encoding="utf-8"))


def test_crear_logica_anade_sin_pisar_lo_que_habia(tmp_path, monkeypatch):
    destino = tmp_path / "modulo.py"
    destino.write_text(EXISTENTE, encoding="utf-8")
    monkeypatch.setattr(stm_logica, "generar_logica", lambda *_a, **_k: LOGICA)
    monkeypatch.setattr(stm_logica, "_aprender", lambda *_a: None)
    monkeypatch.setattr(stm_logica, "comando_test_ruta", lambda *_a: {})
    assert stm_logica.crear_logica("sumar enteros", str(destino), "python",
                                   consultor=_consultor) is True
    texto = destino.read_text(encoding="utf-8")
    assert "def restar" in texto and "def sumar_enteros" in texto
    ast.parse(texto)


def test_crear_logica_rechaza_codigo_invalido(tmp_path, monkeypatch):
    destino = tmp_path / "rota.py"
    monkeypatch.setattr(stm_logica, "generar_logica",
                        lambda *_a, **_k: "def f(:\n    pass")
    monkeypatch.setattr(stm_logica, "comando_test_ruta", lambda *_a: {})
    assert stm_logica.crear_logica("algo", str(destino), "python",
                                   consultor=_consultor) is False
    assert not destino.exists()


def test_crear_logica_sin_peticion_no_hace_nada(tmp_path):
    destino = tmp_path / "x.py"
    assert stm_logica.crear_logica("   ", str(destino), "python") is False
    assert not destino.exists()


def test_crear_logica_cancela_si_el_diseno_no_convence(tmp_path, monkeypatch):
    destino = tmp_path / "x.py"
    monkeypatch.setattr(stm_logica, "pedir_confirmacion", lambda *_a: False)
    assert stm_logica.crear_logica("algo", str(destino), "python",
                                   consultor=_consultor) is False
    assert not destino.exists()


def test_crear_logica_deriva_el_nombre_si_no_hay_ruta(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(stm_logica, "generar_logica", lambda *_a, **_k: LOGICA)
    monkeypatch.setattr(stm_logica, "_aprender", lambda *_a: None)
    monkeypatch.setattr(stm_logica, "comando_test_ruta", lambda *_a: {})
    assert stm_logica.crear_logica("sumar dos numeros", None, "python",
                                   consultor=_consultor) is True
    assert any(archivo.name.startswith("logica_") for archivo in tmp_path.iterdir())


# --- Comando -----------------------------------------------------------------

def test_el_comando_solo_exige_la_peticion(tmp_path, monkeypatch):
    destino = tmp_path / "hecha.py"
    entradas = iter(["sumar enteros", str(destino), ""])
    monkeypatch.setattr(builtins, "input", lambda *_a: next(entradas))
    monkeypatch.setattr(stm_logica, "generar_logica", lambda *_a, **_k: LOGICA)
    monkeypatch.setattr(stm_logica, "_aprender", lambda *_a: None)
    monkeypatch.setattr(stm_logica, "comando_test_ruta", lambda *_a: {})
    monkeypatch.setattr(stm_logica, "disenar", lambda *_a, **_k: "Diseño de prueba")
    stm_logica.comando_crear_logica()
    assert destino.is_file()


def test_el_comando_avisa_si_no_hay_peticion(monkeypatch):
    errores: list[str] = []
    monkeypatch.setattr(builtins, "input", lambda *_a: "")
    monkeypatch.setattr(stm_logica, "reportar_error", errores.append)
    stm_logica.comando_crear_logica()
    assert errores and "lógica" in errores[0]
