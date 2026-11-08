"""Pruebas del flujo de refactor (issue #80).

Todo se ejecuta sin red, sin Ollama y sin tocar los árboles del proyecto:
los modelos y la generación se sustituyen por dobles.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from STM_RFPRMN_stmDL import stm_flujo
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

MODULO_DIR = Path(__file__).resolve().parent.parent

ORIGEN_VALIDO = '''"""Módulo de ejemplo."""


def sumar(a, b):
    """Suma dos números."""
    return a + b


def restar(a, b):
    """Resta dos números."""
    return a - b
'''


def _flujo(tmp_path, contenido: str = ORIGEN_VALIDO):
    archivo = tmp_path / "ejemplo.py"
    archivo.write_text(contenido, encoding="utf-8")
    return stm_flujo.FlujoRefactorLucIA(archivo, contenido)


# --- estructura --------------------------------------------------------------

def test_ejecutar_se_define_una_sola_vez():
    arbol = ast.parse((MODULO_DIR / "STM_RFPRMN_stmDL" / "stm_flujo.py")
                      .read_text(encoding="utf-8"))
    clase = next(n for n in arbol.body
                 if isinstance(n, ast.ClassDef) and n.name == "FlujoRefactorLucIA")
    ejecutar = [n for n in clase.body
                if isinstance(n, ast.FunctionDef) and n.name == "ejecutar"]
    assert len(ejecutar) == 1, "issue #80: solo debe quedar una definición"


def test_no_quedan_nombres_indefinidos():
    proceso = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F821",
         "--no-cache", "--output-format", "concise", str(MODULO_DIR)],
        capture_output=True, text=True)
    if "No module named ruff" in proceso.stderr:
        pytest.skip("ruff no está instalado")
    assert proceso.returncode == 0, proceso.stdout


# --- fragmentos --------------------------------------------------------------

def test_generar_fragmentos_cubre_el_archivo(tmp_path):
    flujo = _flujo(tmp_path)
    flujo.modelo = "modelo de prueba"
    flujo.generar_fragmentos()
    assert flujo.fragmentos
    texto_reconstruido = "\n".join(f["original"] for f in flujo.fragmentos)
    assert texto_reconstruido == ORIGEN_VALIDO.rstrip("\n")
    for fragmento in flujo.fragmentos:
        ast.parse(fragmento["original"])


def test_generar_fragmentos_falla_si_el_archivo_esta_vacio(tmp_path):
    archivo = tmp_path / "vacio.py"
    archivo.write_text("", encoding="utf-8")
    flujo = stm_flujo.FlujoRefactorLucIA(archivo, "")
    flujo.modelo = "x"
    with pytest.raises(ErrorProyecto):
        flujo.generar_fragmentos()


# --- ensamblado --------------------------------------------------------------

def test_ensamblar_conserva_el_original_del_fragmento_irreparable(tmp_path):
    contenido = ("def a():\n    return 1\n\n\n"
                 "def b():\n    return 2\n")
    flujo = _flujo(tmp_path, contenido)
    flujo.fragmentos = [
        {"num": 1, "original": "def a():\n    return 1", "salida": "def a():\n    return 1",
         "irreparable": False},
        {"num": 2, "original": "def b():\n    return 2", "salida": "",
         "irreparable": True},
    ]
    resultado = flujo.ensamblar()
    assert "def a()" in resultado and "def b()" in resultado


def test_ensamblar_rechaza_sin_truncar_cuando_excede_el_tope(tmp_path):
    contenido = "def a():\n    return 1\n"
    flujo = _flujo(tmp_path, contenido)
    relleno = "\n".join(f"valor_{i} = {i}" for i in range(stm_flujo.LIMITE_LINEAS_REFACTOR + 50))
    flujo.fragmentos = [{"num": 1, "original": "def a():\n    return 1",
                         "salida": "def a():\n    return 1\n" + relleno,
                         "irreparable": False}]
    with pytest.raises(ErrorProyecto) as error:
        flujo.ensamblar()
    assert "truncar" in str(error.value)


def test_ensamblar_elimina_el_solape_repetido(tmp_path):
    contenido = ("def a():\n    x = 1\n    return x\n\n\n"
                 "def b():\n    return 2\n")
    flujo = _flujo(tmp_path, contenido)
    flujo.fragmentos = [
        {"num": 1, "original": "def a():\n    x = 1\n    return x",
         "salida": "def a():\n    x = 1\n    return x", "irreparable": False},
        {"num": 2, "original": "def b():\n    return 2",
         "salida": "    x = 1\n    return x\ndef b():\n    return 2",
         "irreparable": False},
    ]
    resultado = flujo.ensamblar()
    assert resultado.count("x = 1") == 1


# --- rotación y limpieza -----------------------------------------------------

def test_rotar_ia_excluye_el_modelo_aunque_no_se_pueda_borrar(tmp_path, monkeypatch):
    flujo = _flujo(tmp_path)
    flujo.modelo = "qwen2.5-coder:7b"
    flujo.endpoint = "http://localhost:11434"
    flujo.consumir_modelos = True  # se pidió borrar y el borrado falla
    monkeypatch.setattr(stm_flujo, "_borrar_modelo_ollama", lambda *_a: False)
    flujo.rotar_ia("timeout")
    assert "qwen2.5-coder:7b" in flujo.fallidas
    assert any("NO se pudo borrar" in linea for linea in flujo.rotaciones)


def test_rotar_ia_registra_el_borrado_correcto(tmp_path, monkeypatch):
    flujo = _flujo(tmp_path)
    flujo.modelo = "starcoder2:7b"
    flujo.consumir_modelos = True
    monkeypatch.setattr(stm_flujo, "_borrar_modelo_ollama", lambda *_a: True)
    flujo.rotar_ia("validación")
    assert any("ollama rm" in linea for linea in flujo.rotaciones)


def test_rotar_ia_conserva_el_modelo_por_defecto(tmp_path, monkeypatch):
    flujo = _flujo(tmp_path)
    flujo.modelo = "starcoder2:7b"
    llamadas: list[int] = []
    monkeypatch.setattr(stm_flujo, "_borrar_modelo_ollama",
                        lambda *_a: llamadas.append(1))
    assert flujo.consumir_modelos is False
    flujo.rotar_ia("validación")
    assert llamadas == [], "R3: por defecto no se borra el modelo del usuario"
    assert "starcoder2:7b" in flujo.fallidas
    assert any("sin borrar" in linea for linea in flujo.rotaciones)


def test_la_limpieza_del_peso_se_ejecuta_aunque_falle_el_flujo(tmp_path, monkeypatch):
    flujo = _flujo(tmp_path)
    llamadas: list[int] = []
    monkeypatch.setattr(stm_flujo, "_borrar_peso_local", lambda: llamadas.append(1))

    def _explotar():
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(flujo, "_ejecutar_fases", _explotar)
    with pytest.raises(RuntimeError):
        flujo.ejecutar()
    assert llamadas == [1], "el finally debe limpiar siempre"


def test_asegurar_ia_traduce_errores_de_configuracion(tmp_path, monkeypatch):
    flujo = _flujo(tmp_path)

    def _sin_config():
        raise FileNotFoundError("IAlocal.json")

    monkeypatch.setattr(stm_flujo, "_cargar_configuracion_ia_local", _sin_config)
    with pytest.raises(ErrorProyecto) as error:
        flujo.asegurar_ia()
    assert "Configuración de IA local" in str(error.value)


# --- escritura ---------------------------------------------------------------

def test_aplicar_escribe_de_forma_atomica(tmp_path, monkeypatch):
    flujo = _flujo(tmp_path)
    flujo.fragmentos = []
    monkeypatch.setattr(stm_flujo, "pedir_confirmacion", lambda *_a: True)
    nuevo = "def sumar(a, b):\n    return a + b\n"
    assert flujo._aplicar(nuevo) is True
    assert flujo.ruta.read_text(encoding="utf-8") == nuevo
    assert not [p for p in tmp_path.iterdir() if ".tmp-" in p.name]


def test_aplicar_no_toca_el_archivo_si_se_cancela(tmp_path, monkeypatch):
    flujo = _flujo(tmp_path)
    flujo.fragmentos = [{"num": 2, "original": "x", "salida": "", "irreparable": True}]
    monkeypatch.setattr(stm_flujo, "pedir_confirmacion", lambda *_a: False)
    assert flujo._aplicar("def otro():\n    pass\n") is False
    assert flujo.ruta.read_text(encoding="utf-8") == ORIGEN_VALIDO


def test_el_registro_no_rompe_el_flujo_si_es_ilegible(tmp_path, monkeypatch):
    """Si el registro no se puede escribir, se avisa y se sigue (no OSError)."""
    from STM_RFPRMN_stmDL import stm_refactor
    bloqueado = tmp_path / "registro_bloqueado.md"
    bloqueado.mkdir()  # abrir un directorio en modo texto lanza OSError
    monkeypatch.setattr(stm_refactor, "REGISTRO_REFACTOR_MD", bloqueado)
    stm_refactor._registrar_refactor_md(tmp_path / "a.py", "modelo", "nota")  # no lanza
