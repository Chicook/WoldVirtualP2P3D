"""Pruebas del particionador de módulos que superan el tope de 450 líneas."""
from __future__ import annotations

import ast

import pytest

from STM_RFPRMN_stmDL import stm_particion
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

CABECERA = '''"""Módulo grande de prueba."""

import math
from pathlib import Path


'''


def _modulo(n_funciones: int = 20, cuerpo: int = 25) -> str:
    piezas = [CABECERA]
    for indice in range(n_funciones):
        cuerpo_fn = "\n".join(
            f"    valor_{indice}_{linea} = {linea} * 2" for linea in range(cuerpo))
        piezas.append(f"def funcion_{indice}(a, b):\n"
                      f"    \"\"\"Hace algo {indice}.\"\"\"\n{cuerpo_fn}\n"
                      f"    return a + b\n\n")
    return "".join(piezas)


@pytest.fixture(autouse=True)
def _confirmar(monkeypatch):
    monkeypatch.setattr(stm_particion, "pedir_confirmacion", lambda *_a: True)
    yield


# --- Análisis ----------------------------------------------------------------

def test_separa_cabecera_y_unidades():
    cabecera, unidades = stm_particion.separar_unidades(_modulo(3))
    assert "import math" in cabecera and "Módulo grande" in cabecera
    assert [unidad["nombre"] for unidad in unidades] == [
        "funcion_0", "funcion_1", "funcion_2"]
    assert all(unidad["tipo"] == "funcion" for unidad in unidades)


def test_reconoce_clases():
    codigo = "class A:\n    pass\n\n\ndef f():\n    pass\n"
    _, unidades = stm_particion.separar_unidades(codigo)
    assert [(u["nombre"], u["tipo"]) for u in unidades] == [
        ("A", "clase"), ("f", "funcion")]


def test_sintaxis_invalida_falla():
    with pytest.raises(ErrorProyecto):
        stm_particion.separar_unidades("def f(:\n    pass")


def test_un_archivo_corto_no_se_parte():
    plan = stm_particion.plan_de_particion(_modulo(2, 3))
    assert plan["necesita"] is False
    assert len(plan["partes"]) == 1


def test_un_archivo_largo_necesita_varias_partes():
    plan = stm_particion.plan_de_particion(_modulo(20, 25))
    assert plan["necesita"] is True
    assert len(plan["partes"]) >= 2
    assert plan["problemas"] == []


def test_una_unidad_gigante_se_marca_como_problema():
    gigante = CABECERA + "def enorme():\n" + "\n".join(
        f"    x{i} = {i}" for i in range(600)) + "\n    return x0\n"
    plan = stm_particion.plan_de_particion(gigante)
    assert "enorme" in plan["problemas"]


def test_no_reparte_si_no_hay_unidades():
    with pytest.raises(ErrorProyecto):
        stm_particion.plan_de_particion(CABECERA)


# --- Partición real ----------------------------------------------------------

def test_parte_el_archivo_y_respeta_el_tope(tmp_path):
    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    destino = tmp_path / "subsistemas"
    resultado = stm_particion.partir_archivo(origen, destino_subsistema=destino)
    assert resultado["partido"] is True
    assert resultado["partes"] >= 2
    assert len(origen.read_text(encoding="utf-8").splitlines()) <= 450
    for archivo in destino.glob("grande_p*.py"):
        texto = archivo.read_text(encoding="utf-8")
        assert len(texto.splitlines()) <= 450
        ast.parse(texto)
    ast.parse(origen.read_text(encoding="utf-8"))


def test_el_principal_reexporta_los_subsistemas(tmp_path):
    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    stm_particion.partir_archivo(origen, destino_subsistema=tmp_path / "subs")
    principal = origen.read_text(encoding="utf-8")
    assert "STM_SBSISTEMA" in principal
    assert "from grande_p2 import *" in principal
    assert "import sys as _sys" in principal


def test_no_duplica_definiciones(tmp_path):
    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    stm_particion.partir_archivo(origen, destino_subsistema=tmp_path / "subs")
    textos = [origen.read_text(encoding="utf-8")]
    textos += [a.read_text(encoding="utf-8")
               for a in (tmp_path / "subs").glob("grande_p*.py")]
    juntos = "\n".join(textos)
    assert juntos.count("def funcion_7(") == 1


def test_escribe_el_informe(tmp_path):
    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    stm_particion.partir_archivo(origen, destino_subsistema=tmp_path / "subs")
    informe = tmp_path / "particion_grande.md"
    assert informe.is_file()
    assert "Partición de grande.py" in informe.read_text(encoding="utf-8")


def test_no_parte_un_archivo_corto(tmp_path):
    origen = tmp_path / "pequeno.py"
    origen.write_text("def f():\n    return 1\n", encoding="utf-8")
    assert stm_particion.partir_archivo(origen)["partido"] is False


def test_archivo_inexistente(tmp_path):
    assert stm_particion.partir_archivo(tmp_path / "nada.py")["partido"] is False


def test_cancelado_no_escribe(tmp_path, monkeypatch):
    origen = tmp_path / "grande.py"
    original = _modulo(20, 25)
    origen.write_text(original, encoding="utf-8")
    monkeypatch.setattr(stm_particion, "pedir_confirmacion", lambda *_a: False)
    assert stm_particion.partir_archivo(origen)["partido"] is False
    assert origen.read_text(encoding="utf-8") == original


def test_partir_si_excede_no_hace_nada_si_cabe(tmp_path):
    origen = tmp_path / "pequeno.py"
    origen.write_text("def f():\n    return 1\n", encoding="utf-8")
    assert stm_particion.partir_si_excede(origen) is False


def test_partir_si_excede_pregunta_y_parte(tmp_path):
    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    assert stm_particion.partir_si_excede(origen) is True


def test_el_comando_pide_el_archivo(tmp_path, monkeypatch):
    import builtins

    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    monkeypatch.setattr(builtins, "input", lambda *_a: str(origen))
    monkeypatch.setattr(stm_particion, "partir_archivo", lambda *_a, **_k: {"partido": True})
    stm_particion.comando_partir_archivo()  # no debe lanzar
