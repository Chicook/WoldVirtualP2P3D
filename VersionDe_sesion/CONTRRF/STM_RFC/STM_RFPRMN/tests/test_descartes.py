"""Pruebas de la lista de modelos descartados y de su efecto en la elección."""
from __future__ import annotations

import json

import pytest

from STM_RFPRMN_stmDL import stm_descartes, stm_modelos


@pytest.fixture
def ruta(tmp_path, monkeypatch):
    """Aísla el JSON de descartados en el directorio temporal de la prueba."""
    destino = tmp_path / "modelos_descartados.json"
    monkeypatch.setattr(stm_descartes, "ruta_descartados", lambda: destino)
    return destino


def test_sin_archivo_no_hay_descartados(ruta):
    assert stm_descartes.leer_descartados() == {}


def test_descartar_borra_y_apunta(tmp_path, ruta, monkeypatch):
    borrados: list[str] = []
    monkeypatch.setattr(stm_modelos, "_borrar_modelo_ollama",
                        lambda _e, modelo: borrados.append(modelo) or True)
    assert stm_descartes.descartar_modelo("http://x", "qwen2.5-coder:7b",
                                          "código inválido") is True
    assert borrados == ["qwen2.5-coder:7b"]
    assert stm_descartes.leer_descartados() == {"qwen2.5-coder:7b": "código inválido"}


def test_si_el_borrado_falla_igual_queda_apuntado(ruta, monkeypatch):
    monkeypatch.setattr(stm_modelos, "_borrar_modelo_ollama", lambda *_a: False)
    assert stm_descartes.descartar_modelo("http://x", "starcoder2:7b") is False
    assert "starcoder2:7b" in stm_descartes.leer_descartados()


def test_varios_descartados_se_acumulan(ruta, monkeypatch):
    monkeypatch.setattr(stm_modelos, "_borrar_modelo_ollama", lambda *_a: True)
    stm_descartes.descartar_modelo("http://x", "qwen2.5-coder:3b")
    stm_descartes.descartar_modelo("http://x", "starcoder2:7b")
    assert set(stm_descartes.leer_descartados()) == {"qwen2.5-coder:3b", "starcoder2:7b"}


def test_olvidar_descartados_vacia_la_lista(ruta, monkeypatch):
    monkeypatch.setattr(stm_modelos, "_borrar_modelo_ollama", lambda *_a: True)
    stm_descartes.descartar_modelo("http://x", "qwen2.5-coder:7b")
    stm_descartes.olvidar_descartados()
    assert stm_descartes.leer_descartados() == {}


def test_un_json_corrupto_no_rompe(ruta):
    ruta.write_text("no es json", encoding="utf-8")
    assert stm_descartes.leer_descartados() == {}


def test_los_descartados_no_son_candidatos(ruta, monkeypatch):
    ruta.write_text(json.dumps({"qwen2.5-coder:3b": "inválido"}), encoding="utf-8")
    monkeypatch.setattr(stm_modelos, "_leer_candidatos_codigo",
                        lambda: ["qwen2.5-coder:3b", "starcoder2:7b"])
    monkeypatch.setattr(stm_modelos, "_modelos_ollama_instalados", lambda: set())
    assert stm_modelos._candidatos_disponibles() == ["starcoder2:7b"]


def test_si_todo_esta_descartado_se_reinicia(ruta, monkeypatch):
    ruta.write_text(json.dumps({"starcoder2:7b": "inválido"}), encoding="utf-8")
    monkeypatch.setattr(stm_modelos, "_leer_candidatos_codigo",
                        lambda: ["starcoder2:7b"])
    monkeypatch.setattr(stm_modelos, "_modelos_ollama_instalados", lambda: set())
    assert stm_modelos._candidatos_disponibles() == ["starcoder2:7b"]
    assert stm_descartes.leer_descartados() == {}, "se reinicia la lista"
