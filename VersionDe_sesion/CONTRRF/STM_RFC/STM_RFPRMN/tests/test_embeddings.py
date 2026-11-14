"""Pruebas del codificador semántico (embeddings locales de Ollama)."""
from __future__ import annotations

import json

import pytest

from STM_RFPRMN_stmDL import stm_embeddings


class RespuestaFalsa:
    """Doble de ``urlopen``: devuelve el JSON que se le pida por ruta."""

    def __init__(self, datos: dict, status: int = 200) -> None:
        self._datos = json.dumps(datos).encode("utf-8")
        self.status = status

    def read(self, *_args) -> bytes:
        return self._datos

    def __enter__(self):
        return self

    def __exit__(self, *_excepcion):
        return False


@pytest.fixture(autouse=True)
def _sonda_limpia():
    stm_embeddings._SONDA.update({"hecha": False, "ok": False, "modelo": "",
                                  "dim": 0, "motivo": ""})
    stm_embeddings._CACHE_TEXTO.clear()
    yield


def _config(monkeypatch, tmp_path, modelo: str = "all-minilm"):
    monkeypatch.setenv("RFPRMN_EMBEDDING_MODEL", modelo)
    monkeypatch.setattr(stm_embeddings, "_cargar_configuracion_ia_local",
                        lambda: ("http://localhost:11434", "x"))
    monkeypatch.setattr(stm_embeddings, "modelos_instalados", lambda: {modelo})


# --- Detección ---------------------------------------------------------------

def test_sin_modelo_no_esta_disponible(monkeypatch):
    monkeypatch.delenv("RFPRMN_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr(stm_embeddings, "modelos_instalados", lambda: set())
    estado = stm_embeddings.estado()
    assert estado["ok"] is False
    assert "sin modelo" in estado["motivo"]


def test_detecta_el_mas_ligero_instalado(monkeypatch):
    monkeypatch.delenv("RFPRMN_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr(stm_embeddings, "modelos_instalados",
                        lambda: {"nomic-embed-text", "all-minilm"})
    assert stm_embeddings.detectar_modelo() == "all-minilm"


def test_el_entorno_manda(monkeypatch):
    monkeypatch.setenv("RFPRMN_EMBEDDING_MODEL", "mxbai-embed-large")
    monkeypatch.setattr(stm_embeddings, "modelos_instalados", lambda: {"all-minilm"})
    assert stm_embeddings.detectar_modelo() == "mxbai-embed-large"


def test_modelo_configurado_por_fichero(monkeypatch, tmp_path):
    monkeypatch.delenv("RFPRMN_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr(stm_embeddings, "leer_opciones",
                        lambda: {"embedding_model": "nomic-embed-text"})
    assert stm_embeddings.modelo_configurado() == "nomic-embed-text"


# --- Embeddings --------------------------------------------------------------

def test_codifica_con_api_embed(monkeypatch, tmp_path):
    _config(monkeypatch, tmp_path)
    vector = [0.1] * 384
    monkeypatch.setattr(stm_embeddings.urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa({"embeddings": [vector]}))
    assert stm_embeddings.estado()["ok"] is True
    assert len(stm_embeddings.codificar("hola") or []) == 384


def test_respaldo_al_endpoint_heredado(monkeypatch, tmp_path):
    _config(monkeypatch, tmp_path)
    vector = [0.2] * 384

    def _urlopen(peticion, **_kwargs):
        if str(peticion.full_url).endswith("/api/embed"):
            raise OSError("endpoint no disponible")
        return RespuestaFalsa({"embedding": vector})

    monkeypatch.setattr(stm_embeddings.urllib.request, "urlopen", _urlopen)
    assert stm_embeddings.codificar("hola") == vector


def test_si_falla_devuelve_none(monkeypatch, tmp_path):
    _config(monkeypatch, tmp_path)

    def _falla(*_args, **_kwargs):
        raise OSError("sin conexión")

    monkeypatch.setattr(stm_embeddings.urllib.request, "urlopen", _falla)
    assert stm_embeddings.estado()["ok"] is False
    assert stm_embeddings.codificar("hola") is None


def test_cachea_el_mismo_texto(monkeypatch, tmp_path):
    _config(monkeypatch, tmp_path)
    llamadas: list[str] = []

    def _urlopen(peticion, **_kwargs):
        llamadas.append(str(peticion.full_url))
        return RespuestaFalsa({"embeddings": [[0.3] * 384]})

    monkeypatch.setattr(stm_embeddings.urllib.request, "urlopen", _urlopen)
    stm_embeddings.estado()          # sonda inicial (una llamada)
    llamadas.clear()
    stm_embeddings.codificar("texto repetido")
    stm_embeddings.codificar("texto repetido")
    assert len(llamadas) == 1, "el segundo texto debe salir de la caché"


# --- Contracción -------------------------------------------------------------

def test_contraer_devuelve_la_dimension_pedida():
    vector = [0.01 * i for i in range(384)]
    contraido = stm_embeddings.contraer(vector)
    assert len(contraido) == stm_embeddings.DIMENSIONES
    assert all(0.0 <= valor <= 1.0 for valor in contraido)


def test_contraer_es_estable_y_sensible_al_contenido():
    primero = stm_embeddings.contraer([0.5] * 384)
    segundo = stm_embeddings.contraer([0.5] * 384)
    distinto = stm_embeddings.contraer([0.5] * 191 + [0.9] * 193)
    assert primero == segundo
    assert primero != distinto


def test_contraer_vacio_no_rompe():
    assert stm_embeddings.contraer([]) == [0.5] * stm_embeddings.DIMENSIONES


def test_contraer_conserva_rango_util():
    """Un embedding real no debe quedar aplastado alrededor de 0.5."""
    vector = [((i * 37) % 101) / 101 - 0.5 for i in range(384)]
    contraido = stm_embeddings.contraer(vector)
    assert max(contraido) - min(contraido) > 0.2


def test_describir_indica_el_estado(monkeypatch, tmp_path):
    _config(monkeypatch, tmp_path)
    monkeypatch.setattr(stm_embeddings.urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa({"embeddings": [[0.1] * 384]}))
    texto = stm_embeddings.describir()
    assert "all-minilm" in texto
    assert "384" in texto
    texto.encode("cp1252")  # la consola de Windows no admite todos los símbolos