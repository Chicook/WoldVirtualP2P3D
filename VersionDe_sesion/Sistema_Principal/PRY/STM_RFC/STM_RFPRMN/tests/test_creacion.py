"""Pruebas del comando «crear codigo» y de su módulo."""
from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from STM_RFPRMN_stmDL import stm_creacion
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

CODIGO = '''"""Suma de enteros."""


def sumar(a, b):
    """Devuelve a + b validando que ambos sean enteros."""
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Se esperaban enteros")
    return a + b
'''


@pytest.fixture(autouse=True)
def _confirmar(monkeypatch):
    """Las pruebas no deben quedarse esperando en un input."""
    monkeypatch.setattr(stm_creacion, "pedir_confirmacion", lambda *_a: True)
    yield


def _consultor(texto: str, _analisis) -> str:
    return f"Plan para: {texto[:40]}"


# --- Piezas ------------------------------------------------------------------

def test_extension_por_lenguaje(tmp_path):
    assert stm_creacion._extension("python", tmp_path / "x") == ".py"
    assert stm_creacion._extension("csharp", tmp_path / "x") == ".cs"
    assert stm_creacion._extension("", tmp_path / "x.cs") == ".cs"
    assert stm_creacion._extension("desconocido", tmp_path / "x") == ".py"


def test_plan_de_respaldo_menciona_la_peticion():
    plan = stm_creacion.plan_de_respaldo("una calculadora de IVA", "python")
    assert "calculadora de IVA" in plan
    assert "python" in plan


def test_diagnostico_usa_el_consultor():
    plan = stm_creacion.diagnosticar("algo", Path("x.py"), "python", _consultor)
    assert plan.startswith("Plan para: algo")


def test_diagnostico_sin_descripcion_falla():
    with pytest.raises(ErrorProyecto):
        stm_creacion.diagnosticar("   ", Path("x.py"), "python")


def test_validar_codigo_quita_cercas():
    texto = "```python\nprint('hola')\n```"
    assert stm_creacion.validar_codigo(texto, Path("x.py")) == "print('hola')\n"


def test_validar_codigo_rechaza_vacio():
    with pytest.raises(ErrorProyecto):
        stm_creacion.validar_codigo("   ", Path("x.py"))


def test_validar_codigo_rechaza_sintaxis_rota():
    with pytest.raises(ErrorProyecto):
        stm_creacion.validar_codigo("def f(:\n    pass", Path("x.py"))


def test_validar_codigo_rechaza_pasarse_del_tope():
    enorme = "\n".join(f"x{i} = {i}" for i in range(500))
    with pytest.raises(ErrorProyecto):
        stm_creacion.validar_codigo(enorme, Path("x.py"))


def test_validar_codigo_no_parsea_lenguajes_que_no_son_python(tmp_path):
    texto = "public static int Sumar(int a, int b) { return a + b; }"
    assert stm_creacion.validar_codigo(texto, tmp_path / "x.cs")


# --- Creación completa -------------------------------------------------------

def test_crear_codigo_escribe_el_archivo(tmp_path, monkeypatch):
    destino = tmp_path / "suma.py"
    aprendido: list[tuple[str, str]] = []
    monkeypatch.setattr(stm_creacion, "generar_codigo",
                        lambda *_a, **_k: CODIGO)
    monkeypatch.setattr(stm_creacion, "_aprender",
                        lambda descripcion, codigo: aprendido.append((descripcion, codigo)))
    assert stm_creacion.crear_codigo(destino, "sumar enteros", "python",
                                     consultor=_consultor) is True
    assert destino.read_text(encoding="utf-8") == CODIGO
    assert aprendido and aprendido[0][0] == "sumar enteros"


def test_crear_codigo_infiere_la_extension(tmp_path, monkeypatch):
    destino = tmp_path / "suma"
    monkeypatch.setattr(stm_creacion, "generar_codigo", lambda *_a, **_k: CODIGO)
    monkeypatch.setattr(stm_creacion, "_aprender", lambda *_a: None)
    assert stm_creacion.crear_codigo(destino, "sumar", "python",
                                     consultor=_consultor) is True
    assert (tmp_path / "suma.py").is_file()


def test_crear_codigo_rechaza_codigo_invalido(tmp_path, monkeypatch):
    destino = tmp_path / "roto.py"
    monkeypatch.setattr(stm_creacion, "generar_codigo",
                        lambda *_a, **_k: "def f(:\n    pass")
    monkeypatch.setattr(stm_creacion, "_aprender", lambda *_a: None)
    assert stm_creacion.crear_codigo(destino, "algo", "python",
                                     consultor=_consultor) is False
    assert not destino.exists(), "no debe escribirse código inválido"


def test_crear_codigo_sin_descripcion_no_hace_nada(tmp_path):
    destino = tmp_path / "x.py"
    assert stm_creacion.crear_codigo(destino, "   ", "python") is False
    assert not destino.exists()


def test_crear_codigo_pide_confirmacion_si_el_archivo_existe(tmp_path, monkeypatch):
    destino = tmp_path / "existe.py"
    destino.write_text("print('original')\n", encoding="utf-8")
    monkeypatch.setattr(stm_creacion, "pedir_confirmacion", lambda *_a: False)
    assert stm_creacion.crear_codigo(destino, "otra cosa", "python",
                                     consultor=_consultor) is False
    assert destino.read_text(encoding="utf-8") == "print('original')\n"


def test_crear_codigo_cancela_si_el_plan_no_convence(tmp_path, monkeypatch):
    destino = tmp_path / "x.py"
    monkeypatch.setattr(stm_creacion, "pedir_confirmacion", lambda *_a: False)
    assert stm_creacion.crear_codigo(destino, "algo", "python",
                                     consultor=_consultor) is False
    assert not destino.exists()


def test_el_comando_pide_los_tres_datos(tmp_path, monkeypatch):
    destino = tmp_path / "hecho.py"
    entradas = iter([str(destino), "sumar", "python"])
    monkeypatch.setattr(builtins, "input", lambda *_a: next(entradas))
    monkeypatch.setattr(stm_creacion, "generar_codigo", lambda *_a, **_k: CODIGO)
    monkeypatch.setattr(stm_creacion, "_aprender", lambda *_a: None)
    monkeypatch.setattr(stm_creacion, "diagnosticar",
                        lambda *_a, **_k: "Plan de prueba")
    stm_creacion.comando_crear_codigo()
    assert destino.is_file()


def test_el_comando_avisa_si_no_hay_ruta(monkeypatch):
    errores: list[str] = []
    monkeypatch.setattr(builtins, "input", lambda *_a: "")
    monkeypatch.setattr(stm_creacion, "reportar_error", errores.append)
    stm_creacion.comando_crear_codigo()
    assert errores and "ruta" in errores[0]
