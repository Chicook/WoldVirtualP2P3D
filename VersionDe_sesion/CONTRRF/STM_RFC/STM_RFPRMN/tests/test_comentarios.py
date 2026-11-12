"""Pruebas del comando «comentar archivo» y de su módulo."""
from __future__ import annotations

import ast
import builtins

import pytest

from STM_RFPRMN_stmDL import stm_comentarios
from STM_RFPRMN_stmDL.stm_calidad import solo_documenta

SIN_DOCS = '''"""Modulo de ejemplo."""


def sumar(a, b):
    return a + b


def restar(a: int, b: int) -> int:
    return a - b


class Cuenta:
    def saldo(self):
        return 0
'''

CSHARP = '''using System;

class Calculadora
{
    static int Doblar(int x)
    {
        return x * 2;
    }
}
'''


@pytest.fixture(autouse=True)
def _confirmar(monkeypatch):
    monkeypatch.setattr(stm_comentarios, "pedir_confirmacion", lambda *_a: True)
    monkeypatch.setattr(stm_comentarios, "comando_test_ruta", lambda *_a: {})
    yield


def _generador(objetivos, _ruta):
    return {objetivo["clave"]: f"Explica qué hace {objetivo['nombre']} de verdad."
            for objetivo in objetivos}


# --- Análisis ----------------------------------------------------------------

def test_detecta_solo_lo_que_no_tiene_docstring(tmp_path):
    archivo = tmp_path / "modulo.py"
    archivo.write_text(SIN_DOCS, encoding="utf-8")
    objetivos = stm_comentarios.funciones_sin_documentar(SIN_DOCS, archivo)
    nombres = {objetivo["nombre"] for objetivo in objetivos}
    assert nombres == {"sumar", "restar", "saldo", "Cuenta"}


def test_detecta_firmas_en_csharp(tmp_path):
    archivo = tmp_path / "x.cs"
    objetivos = stm_comentarios.funciones_sin_documentar(CSHARP, archivo)
    assert [objetivo["nombre"] for objetivo in objetivos] == ["Doblar"]


def test_no_confunde_control_con_metodo(tmp_path):
    codigo = "class A {\n    if (x) {\n    }\n    void M() {\n    }\n}\n"
    objetivos = stm_comentarios.funciones_sin_documentar(codigo, tmp_path / "x.cs")
    assert [objetivo["nombre"] for objetivo in objetivos] == ["M"]


def test_ignora_lo_que_ya_tiene_comentario_encima(tmp_path):
    codigo = "class A {\n    // ya documentado\n    void M() {\n    }\n}\n"
    objetivos = stm_comentarios.funciones_sin_documentar(codigo, tmp_path / "x.cs")
    assert objetivos == []


# --- Validación de comentarios ----------------------------------------------

def test_sanear_quita_cercas_y_comillas():
    assert stm_comentarios.sanear('```\n"""Suma dos números."""\n```') == "Suma dos números."


def test_comentario_valido_rechaza_lo_que_no_aporta():
    assert stm_comentarios.comentario_valido("Suma dos enteros", "sumar") is True
    assert stm_comentarios.comentario_valido("sumar", "sumar") is False
    assert stm_comentarios.comentario_valido("Sumar", "sumar") is False
    assert stm_comentarios.comentario_valido("corto", "x") is False
    assert stm_comentarios.comentario_valido("a" * 400, "x") is False


def test_parsear_mapea_por_nombre(tmp_path):
    archivo = tmp_path / "modulo.py"
    objetivos = stm_comentarios.funciones_sin_documentar(SIN_DOCS, archivo)
    texto = ("sumar :: Devuelve la suma de dos enteros.\nbasura\n"
             "restar :: Resta el segundo número del primero.")
    resultado = stm_comentarios._parsear(texto, objetivos)
    assert len(resultado) == 2
    assert any("suma" in valor for valor in resultado.values())


def test_parsear_ignora_nombres_desconocidos(tmp_path):
    archivo = tmp_path / "modulo.py"
    objetivos = stm_comentarios.funciones_sin_documentar(SIN_DOCS, archivo)
    assert stm_comentarios._parsear("inexistente :: algo útil aquí", objetivos) == {}


# --- Inserción ---------------------------------------------------------------

def test_inserta_docstrings_en_python(tmp_path):
    archivo = tmp_path / "modulo.py"
    objetivos = stm_comentarios.funciones_sin_documentar(SIN_DOCS, archivo)
    comentarios = _generador(objetivos, archivo)
    nuevo = stm_comentarios.insertar(SIN_DOCS, objetivos, comentarios, True)
    ast.parse(nuevo)
    assert '"""Explica qué hace sumar de verdad."""' in nuevo
    # La invariante: solo cambian los comentarios.
    assert solo_documenta(SIN_DOCS, nuevo, True) is True


def test_inserta_comentarios_de_linea_en_csharp(tmp_path):
    archivo = tmp_path / "x.cs"
    objetivos = stm_comentarios.funciones_sin_documentar(CSHARP, archivo)
    comentarios = _generador(objetivos, archivo)
    nuevo = stm_comentarios.insertar(CSHARP, objetivos, comentarios, False)
    assert "// Explica qué hace Doblar de verdad." in nuevo
    assert solo_documenta(CSHARP, nuevo, False) is True


def test_la_insercion_respeta_el_orden(tmp_path):
    archivo = tmp_path / "modulo.py"
    objetivos = stm_comentarios.funciones_sin_documentar(SIN_DOCS, archivo)
    comentarios = _generador(objetivos, archivo)
    nuevo = stm_comentarios.insertar(SIN_DOCS, objetivos, comentarios, True)
    assert nuevo.count('"""Explica qué hace') == len(objetivos)


def test_los_comentarios_largos_se_envuelven(tmp_path):
    archivo = tmp_path / "modulo.py"
    objetivos = stm_comentarios.funciones_sin_documentar(SIN_DOCS, archivo)
    largo = " ".join(["Devuelve el valor calculado"] * 6)
    comentarios = {objetivo["clave"]: largo for objetivo in objetivos}
    nuevo = stm_comentarios.insertar(SIN_DOCS, objetivos, comentarios, True)
    ast.parse(nuevo)
    assert max(len(linea) for linea in nuevo.splitlines()) <= 88
    assert solo_documenta(SIN_DOCS, nuevo, True) is True


# --- Comando -----------------------------------------------------------------

def test_comentar_archivo_escribe_solo_comentarios(tmp_path):
    archivo = tmp_path / "modulo.py"
    archivo.write_text(SIN_DOCS, encoding="utf-8")
    assert stm_comentarios.comentar_archivo(archivo, generador=_generador) is True
    texto = archivo.read_text(encoding="utf-8")
    ast.parse(texto)
    assert '"""' in texto and solo_documenta(SIN_DOCS, texto, True) is True


def test_comentar_archivo_sin_funciones_no_escribe(tmp_path):
    archivo = tmp_path / "vacio.py"
    archivo.write_text('"""Ya documentado."""\n\n\nX = 1\n', encoding="utf-8")
    antes = archivo.read_text(encoding="utf-8")
    assert stm_comentarios.comentar_archivo(archivo, generador=_generador) is False
    assert archivo.read_text(encoding="utf-8") == antes


def test_no_escribe_si_el_resultado_toca_codigo(tmp_path, monkeypatch):
    archivo = tmp_path / "modulo.py"
    archivo.write_text(SIN_DOCS, encoding="utf-8")
    monkeypatch.setattr(stm_comentarios, "insertar",
                        lambda *_a, **_k: SIN_DOCS.replace("return a + b", "return b + a"))
    assert stm_comentarios.comentar_archivo(archivo, generador=_generador) is False
    assert archivo.read_text(encoding="utf-8") == SIN_DOCS


def test_no_escribe_si_no_hay_comentarios_validos(tmp_path):
    archivo = tmp_path / "modulo.py"
    archivo.write_text(SIN_DOCS, encoding="utf-8")
    assert stm_comentarios.comentar_archivo(archivo, generador=lambda *_a: {}) is False
    assert archivo.read_text(encoding="utf-8") == SIN_DOCS


def test_archivo_inexistente_falla(tmp_path):
    assert stm_comentarios.comentar_archivo(tmp_path / "nada.py") is False


def test_el_comando_pide_el_archivo(tmp_path, monkeypatch):
    archivo = tmp_path / "modulo.py"
    archivo.write_text(SIN_DOCS, encoding="utf-8")
    monkeypatch.setattr(builtins, "input", lambda *_a: str(archivo))
    monkeypatch.setattr(stm_comentarios, "_generar_comentarios", _generador)
    stm_comentarios.comando_comentar_archivo()
    assert '"""' in archivo.read_text(encoding="utf-8")


def test_el_comando_avisa_si_no_hay_ruta(monkeypatch):
    errores: list[str] = []
    monkeypatch.setattr(builtins, "input", lambda *_a: "")
    monkeypatch.setattr(stm_comentarios, "reportar_error", errores.append)
    stm_comentarios.comando_comentar_archivo()
    assert errores and "archivo" in errores[0]
