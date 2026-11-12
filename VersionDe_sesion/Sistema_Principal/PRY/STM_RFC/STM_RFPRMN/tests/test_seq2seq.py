"""Pruebas del subsistema seq2seq de LC_STM y de su puente en el módulo."""
from __future__ import annotations

import pytest

from STM_RFPRMN_stmDL import stm_refactor, stm_seq2seq

ORIGINAL = "def sumar(a, b):\n    return a + b\n"
REFACTOR = 'def sumar(a, b):\n    """Suma dos números."""\n    return a + b\n'


@pytest.fixture(autouse=True)
def _memoria_aislada(monkeypatch, tmp_path):
    """Memoria propia por prueba y caché limpia."""
    monkeypatch.setattr(stm_seq2seq, "RUTA_MEMORIA", tmp_path / "seq2seq.json")
    stm_seq2seq._CACHE.update({"generador": None, "error": "", "cargado": False})
    yield


def _lc():
    """Importa ``LC_STM.seq2seq`` a través del puente (o salta la prueba)."""
    modulo, error = stm_seq2seq._importar()
    if modulo is None:
        pytest.skip(error)
    return modulo


# --- Subsistema LC_STM -------------------------------------------------------

def test_el_subsistema_esta_disponible():
    assert stm_seq2seq.disponible() is True
    assert stm_seq2seq.motivo_no_disponible() == ""


def test_tokenizador_separa_codigo():
    lc = _lc()
    tokens = lc.Tokenizador().tokenizar("def sumar(a, b):\n    return a + b\n")
    assert "def" in tokens and "sumar" in tokens and "return" in tokens
    assert "(" in tokens and "\n" in tokens


def test_el_vectorizador_es_determinista_y_ordena_por_parecido():
    lc = _lc()
    vectorizador = lc.Vectorizador(dims=128)
    base = vectorizador.vector("def sumar(a, b): return a + b")
    igual = vectorizador.vector("def sumar(a, b): return a + b")
    parecido = vectorizador.vector("def sumar(a, b):\n    return a + b")
    distinto = vectorizador.vector("import socket; socket.create_connection(x)")
    from LC_STM.seq2seq.vectorizador import similitud_coseno

    assert base == igual
    assert similitud_coseno(base, parecido) > similitud_coseno(base, distinto)


def test_memoria_acota_y_persiste(tmp_path):
    lc = _lc()
    memoria = lc.MemoriaPares(max_pares=2)
    for indice in range(4):
        memoria.agregar(f"peticion {indice}", f"respuesta {indice}", [0.1] * 8)
    assert len(memoria) == 2, "respeta max_pares"
    ruta = tmp_path / "memoria.json"
    memoria.guardar(ruta)
    otra = lc.MemoriaPares()
    assert otra.cargar(ruta) == 2


def test_generador_aprende_y_recupera():
    lc = _lc()
    generador = lc.crear(umbral=0.9)
    generador.aprender(ORIGINAL, REFACTOR)
    resultado = generador.generar(ORIGINAL)
    assert resultado.texto == REFACTOR
    assert resultado.similitud == pytest.approx(1.0)


def test_generador_se_niega_si_no_se_parece():
    lc = _lc()
    generador = lc.crear(umbral=0.9)
    generador.aprender(ORIGINAL, REFACTOR)
    assert generador.intentar_generar("import os\nos.getcwd()\n") is None


def test_neurona_seq2seq_cumple_el_protocolo(tmp_path):
    lc = _lc()
    neurona = lc.NeuronaSeq2Seq(64, 64)
    neurona.inicializar_pesos()
    import numpy as np

    perdida = neurona.train_step(np.ones(64), np.zeros(64))
    assert "loss" in perdida
    assert neurona.forward(np.ones(64)).shape == (1, 64)
    assert len(neurona.fit(np.ones((3, 64)), np.zeros((3, 64)), epochs=2)) == 2
    assert neurona.predict(np.ones((2, 64))).shape == (2, 64)
    assert neurona.params_count() > 0
    assert "Seq2Seq" in neurona.info()
    destino = tmp_path / "neurona.json"
    neurona.save(destino)
    otra = lc.NeuronaSeq2Seq(64, 64)
    otra.load(destino)
    assert otra.pasos == neurona.pasos


# --- Puente en STM_RFPRMN ----------------------------------------------------

def test_aprender_y_generar_desde_el_modulo():
    assert stm_seq2seq.aprender(ORIGINAL, REFACTOR) is True
    assert stm_seq2seq.generar(ORIGINAL) == REFACTOR
    datos = stm_seq2seq.estado()
    assert datos["disponible"] is True and datos["pares"] == 1
    assert "pares memorizados" in stm_seq2seq.describir()


def test_generar_sin_memoria_devuelve_none():
    assert stm_seq2seq.generar(ORIGINAL) is None


def test_olvidar_vacia_la_memoria():
    stm_seq2seq.aprender(ORIGINAL, REFACTOR)
    assert stm_seq2seq.olvidar() is True
    assert stm_seq2seq.estado()["pares"] == 0


def test_el_flujo_usa_la_memoria_como_ultimo_recurso(tmp_path, monkeypatch):
    archivo = tmp_path / "ejemplo.py"
    archivo.write_text(ORIGINAL, encoding="utf-8")
    monkeypatch.setattr(stm_seq2seq, "generar", lambda _texto: REFACTOR)
    assert stm_refactor._generar_con_memoria(archivo, ORIGINAL, "qwen") is True
    assert archivo.read_text(encoding="utf-8") == REFACTOR


def test_el_flujo_no_escribe_si_la_memoria_no_tiene_nada(tmp_path, monkeypatch):
    archivo = tmp_path / "ejemplo.py"
    archivo.write_text(ORIGINAL, encoding="utf-8")
    monkeypatch.setattr(stm_seq2seq, "generar", lambda _texto: None)
    assert stm_refactor._generar_con_memoria(archivo, ORIGINAL, "qwen") is False
    assert archivo.read_text(encoding="utf-8") == ORIGINAL
