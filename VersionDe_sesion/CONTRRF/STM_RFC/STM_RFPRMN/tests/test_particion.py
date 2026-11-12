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
    assert "_partes" in principal and "import sys as _sys" in principal
    assert "from grande_p2 import *" in principal


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


def test_partir_si_excede_pregunta_y_parte(tmp_path, monkeypatch):
    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    salida = tmp_path / "CONTRUCCION"
    salida.mkdir()
    monkeypatch.setattr(stm_particion, "DIR_CONSTRUCCION", salida)
    assert stm_particion.partir_si_excede(origen) is True
    assert list(salida.glob("grande_p*.py")), "el exceso va a CONTRUCCION"


def test_el_comando_pide_el_archivo(tmp_path, monkeypatch):
    import builtins

    origen = tmp_path / "grande.py"
    origen.write_text(_modulo(20, 25), encoding="utf-8")
    monkeypatch.setattr(builtins, "input", lambda *_a: str(origen))
    monkeypatch.setattr(stm_particion, "partir_archivo", lambda *_a, **_k: {"partido": True})
    stm_particion.comando_partir_archivo()  # no debe lanzar


# --- Reparto entre los archivos que ya existen (al cerrar la sesión) ---------

def test_reparte_entre_los_archivos_que_ya_existen(tmp_path):
    (tmp_path / "grande.py").write_text(_modulo(20, 25), encoding="utf-8")
    (tmp_path / "pequeno.py").write_text(
        '"""Pequeño."""\n\n\ndef f():\n    return 1\n', encoding="utf-8")
    resultado = stm_particion.repartir_carpeta(tmp_path)
    assert resultado["movidas"] > 0
    assert len((tmp_path / "grande.py").read_text(encoding="utf-8").splitlines()) <= 450
    assert "funcion_" in (tmp_path / "pequeno.py").read_text(encoding="utf-8")


def test_los_imports_viajan_con_la_unidad(tmp_path):
    (tmp_path / "grande.py").write_text(_modulo(20, 25), encoding="utf-8")
    (tmp_path / "otro.py").write_text(
        '"""Otro."""\n\n\ndef g():\n    return 1\n', encoding="utf-8")
    stm_particion.repartir_carpeta(tmp_path)
    texto = (tmp_path / "otro.py").read_text(encoding="utf-8")
    assert "import math" in texto or "from pathlib import Path" in texto


def test_repartir_no_toca_los_que_ya_caben(tmp_path):
    antes = '"""x."""\n\n\ndef f():\n    return 1\n'
    (tmp_path / "a.py").write_text(antes, encoding="utf-8")
    resultado = stm_particion.repartir_carpeta(tmp_path)
    assert resultado["movidas"] == 0
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == antes


def test_crea_parte_si_no_hay_hueco_en_ninguno(tmp_path):
    (tmp_path / "solo.py").write_text(_modulo(20, 25), encoding="utf-8")
    resultado = stm_particion.repartir_carpeta(tmp_path)
    assert resultado["creados"] >= 1
    assert len((tmp_path / "solo.py").read_text(encoding="utf-8").splitlines()) <= 450
    assert list(tmp_path.glob("solo_p*.py"))


def test_repartir_carpeta_inexistente(tmp_path):
    assert stm_particion.repartir_carpeta(tmp_path / "no")["motivo"] == "no existe"


def test_repartir_carpeta_vacia(tmp_path):
    assert stm_particion.repartir_carpeta(tmp_path)["motivo"] == "nada que repartir"


# --- Candidato rechazado -----------------------------------------------------

def test_guardar_candidato_lo_deja_para_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(stm_particion, "DIR_CONSTRUCCION", tmp_path)
    destino = stm_particion.guardar_candidato("def f():\n    return 1\n",
                                              tmp_path / "x.py")
    assert destino == tmp_path / "x_candidato.py"
    assert destino.read_text(encoding="utf-8") == "def f():\n    return 1\n"


def test_no_guarda_candidato_vacio(tmp_path, monkeypatch):
    monkeypatch.setattr(stm_particion, "DIR_CONSTRUCCION", tmp_path)
    assert stm_particion.guardar_candidato("   ", tmp_path / "x.py") is None


def test_el_validador_deja_el_candidato_si_se_pide(tmp_path, monkeypatch):
    from STM_RFPRMN_stmDL import stm_refactor

    monkeypatch.setattr(stm_particion, "DIR_CONSTRUCCION", tmp_path)
    with pytest.raises(ErrorProyecto):
        stm_refactor._validar_refactor(
            "def a():\n    return 1\n", "def b():\n    return 2\n",
            tmp_path / "mod.py", False, True)
    assert (tmp_path / "mod_candidato.py").is_file()


def test_el_validador_no_escribe_si_no_se_pide(tmp_path, monkeypatch):
    from STM_RFPRMN_stmDL import stm_refactor

    monkeypatch.setattr(stm_particion, "DIR_CONSTRUCCION", tmp_path)
    with pytest.raises(ErrorProyecto):
        stm_refactor._validar_refactor(
            "def a():\n    return 1\n", "def b():\n    return 2\n",
            tmp_path / "mod.py")
    assert not list(tmp_path.glob("*_candidato.py"))
