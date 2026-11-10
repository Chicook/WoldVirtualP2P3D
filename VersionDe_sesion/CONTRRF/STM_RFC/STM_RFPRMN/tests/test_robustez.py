"""Pruebas de robustez del comando y de la shell (fallos reales reportados)."""
from __future__ import annotations

import builtins
import json

import pytest

from STM_RFPRMN_stmDL import stm_analisis, stm_flujo, stm_refactor
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto


class RespuestaFalsa:
    """Doble de ``urlopen`` para ``/api/tags``."""

    def __init__(self, datos: dict) -> None:
        self._datos = json.dumps(datos).encode("utf-8")

    def read(self, *_args) -> bytes:
        return self._datos

    def __enter__(self):
        return self

    def __exit__(self, *_excepcion):
        return False


def _tags(*nombres: str) -> dict:
    return {"models": [{"name": nombre, "model": nombre} for nombre in nombres]}


# --- Archivo vacío -----------------------------------------------------------

def test_ds_ialocal_avisa_si_el_archivo_esta_vacio(tmp_path, monkeypatch):
    vacio = tmp_path / "vacio.cs"
    vacio.write_text("   \n\n", encoding="utf-8")
    errores: list[str] = []
    monkeypatch.setattr(builtins, "input", lambda *_a: str(vacio))
    monkeypatch.setattr(stm_refactor, "reportar_error", errores.append)
    assert stm_refactor.comando_ds_ialocal() is False
    assert errores and "vacío" in errores[0]


def test_ds_ialocal_no_rompe_si_el_flujo_lanza(tmp_path, monkeypatch):
    archivo = tmp_path / "algo.py"
    archivo.write_text("def a():\n    return 1\n", encoding="utf-8")
    errores: list[str] = []
    monkeypatch.setattr(builtins, "input", lambda *_a: str(archivo))
    monkeypatch.setattr(stm_refactor, "reportar_error", errores.append)

    class FlujoFalso:
        def __init__(self, *_a, **_k):
            pass

        def ejecutar(self):
            raise ErrorProyecto("fallo simulado del flujo")

    monkeypatch.setattr(stm_flujo, "FlujoRefactorLucIA", FlujoFalso)
    assert stm_refactor.comando_ds_ialocal() is False
    assert errores and "fallo simulado" in errores[0]


# --- La shell sobrevive ------------------------------------------------------

def test_la_shell_sobrevive_a_un_comando_que_falla(monkeypatch):
    entradas = iter(["ia local", "cerrar"])
    monkeypatch.setattr(builtins, "input", lambda *_a: next(entradas))
    errores: list[str] = []
    monkeypatch.setattr(stm_flujo, "reportar_error", errores.append)

    def _explotar():
        raise ErrorProyecto("boom")

    monkeypatch.setattr(stm_flujo, "comando_ia_local", _explotar)
    stm_flujo.ejecutar_comandos()  # no debe propagar la excepción
    assert errores and "boom" in errores[0]


# --- Modelo de chat instalado ------------------------------------------------

def test_usa_el_preferido_si_esta_instalado(monkeypatch):
    monkeypatch.setattr(stm_analisis.urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(_tags("cogito:3b", "qwen2.5:7b")))
    assert stm_analisis._modelo_instalado("http://x", "cogito:3b") == "cogito:3b"


def test_el_preferido_ausente_cae_al_instalado_mas_ligero(monkeypatch):
    monkeypatch.setattr(stm_analisis.urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(
                            _tags("qwen2.5:7b", "qwen2.5-coder:3b")))
    assert stm_analisis._modelo_instalado("http://x", "cogito:3b") == "qwen2.5-coder:3b"


def test_los_modelos_de_embeddings_no_se_usan_para_chat(monkeypatch):
    monkeypatch.setattr(stm_analisis.urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(
                            _tags("all-minilm:latest", "qwen2.5-coder:7b")))
    assert stm_analisis._modelo_instalado("http://x", "cogito:3b") == "qwen2.5-coder:7b"


def test_sin_ollama_se_intenta_el_preferido(monkeypatch):
    def _falla(*_a, **_k):
        raise OSError("sin conexión")

    monkeypatch.setattr(stm_analisis.urllib.request, "urlopen", _falla)
    assert stm_analisis._modelo_instalado("http://x", "cogito:3b") == "cogito:3b"


@pytest.mark.parametrize("nombre", ["all-minilm:latest", "nomic-embed-text:latest"])
def test_los_embeddings_nunca_ganan_por_tamano(nombre, monkeypatch):
    monkeypatch.setattr(stm_analisis.urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(_tags(nombre)))
    # Sin ningún modelo de chat, se mantiene el preferido (no el embedder).
    assert stm_analisis._modelo_instalado("http://x", "cogito:3b") == "cogito:3b"
