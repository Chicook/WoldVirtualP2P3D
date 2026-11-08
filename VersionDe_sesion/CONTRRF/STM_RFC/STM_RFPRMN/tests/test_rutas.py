"""Pruebas de la fuente única de rutas (R1/R2/R5 de la discusión #84)."""
from __future__ import annotations

import json

import pytest

from STM_RFPRMN_stmDL import stm_rutas
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto


# --- Lo que la herramienta escribe no puede caer en RFC/PRY ------------------

def test_los_pesos_no_viven_en_el_arbol_sincronizado():
    assert not stm_rutas.es_zona_sincronizada(stm_rutas.DIR_MODELOS_LOCAL)
    assert not stm_rutas.es_zona_sincronizada(stm_rutas.DIR_DATOS)


def test_el_registro_de_refactor_vive_junto_a_la_herramienta():
    assert not stm_rutas.es_zona_sincronizada(stm_rutas.REGISTRO_REFACTOR_MD)
    assert stm_rutas.REGISTRO_REFACTOR_MD.parent == stm_rutas.MODULO_DIR


def test_comprobar_ruta_segura_rechaza_rfc():
    with pytest.raises(ErrorProyecto):
        stm_rutas.comprobar_ruta_segura(stm_rutas.RFC_DIR / "src" / "modelo.gguf")


def test_comprobar_ruta_segura_rechaza_pry():
    with pytest.raises(ErrorProyecto):
        stm_rutas.comprobar_ruta_segura(
            stm_rutas.PRY_DIR / "actualizacion_x" / "registro.md")


def test_comprobar_ruta_segura_acepta_los_datos_propios():
    assert stm_rutas.comprobar_ruta_segura(
        stm_rutas.DIR_MODELOS_LOCAL) == stm_rutas.DIR_MODELOS_LOCAL


# --- Cadena de configuración -------------------------------------------------

def test_el_entorno_tiene_prioridad(monkeypatch, tmp_path):
    destino = tmp_path / "IAlocal.json"
    destino.write_text('{"endpoint": "http://localhost:11434"}', encoding="utf-8")
    monkeypatch.setenv("RFPRMN_IALOCAL_JSON", str(destino))
    assert stm_rutas.ruta_config_ia_local() == destino
    assert stm_rutas.candidatos_config_ia_local()[0] == destino


def test_la_cadena_incluye_la_ultima_actualizacion_de_pry():
    opciones = stm_rutas.candidatos_config_ia_local()
    assert opciones, "la cadena no puede estar vacía"
    ultima = stm_rutas.ultima_actualizacion_pry()
    if ultima is None:
        pytest.skip("PRY no tiene ninguna actualizacion_*")
    esperada = ultima / "src" / "STM_JSON" / "IAlocal.json"
    assert esperada in opciones


def test_la_cadena_no_tiene_duplicados():
    opciones = stm_rutas.candidatos_config_ia_local()
    normalizadas = [str(ruta).lower() for ruta in opciones]
    assert len(normalizadas) == len(set(normalizadas))


def test_encuentra_configuracion_aunque_rfc_este_vacio():
    ruta = stm_rutas.ruta_config_ia_local()
    if not stm_rutas.RFC_DIR.joinpath("src").is_dir() and not ruta.is_file():
        pytest.skip("no hay IAlocal.json en este equipo")
    assert ruta.is_file()
    assert ruta.suffix == ".json"


def test_descripcion_de_la_cadena_es_legible():
    texto = stm_rutas.describir_config_ia_local()
    assert "IAlocal.json" in texto
    assert " | " in texto
    texto.encode("cp1252")  # la consola de Windows no admite todos los símbolos


# --- Predicados --------------------------------------------------------------

def test_es_subruta_y_solape(tmp_path):
    padre = tmp_path / "padre"
    hijo = padre / "hijo"
    hijo.mkdir(parents=True)
    assert stm_rutas.es_subruta(hijo, padre)
    assert stm_rutas.rutas_se_solapan(padre, hijo)
    assert not stm_rutas.rutas_se_solapan(tmp_path / "otra", hijo)


def test_las_rutas_protegidas_incluyen_las_raices():
    protegidas = tuple(stm_rutas.rutas_protegidas())
    assert stm_rutas.RAIZ in protegidas
    assert stm_rutas.PRY_DIR in protegidas
    assert stm_rutas.RFC_DIR in protegidas
    assert stm_rutas.MODULO_DIR in protegidas


# --- R5: rutas elegidas por el usuario ---------------------------------------

def _preparar_config(monkeypatch, tmp_path):
    archivo = tmp_path / ".config" / "rutas.json"
    monkeypatch.setattr(stm_rutas, "ARCHIVO_RUTAS", archivo)
    monkeypatch.setattr(stm_rutas, "DIR_CONFIG", archivo.parent)
    return archivo


def test_guardar_rutas_escribe_el_archivo(monkeypatch, tmp_path):
    rfc = tmp_path / "RFC"
    pry = tmp_path / "PRY"
    rfc.mkdir()
    pry.mkdir()
    archivo = _preparar_config(monkeypatch, tmp_path)
    ruta = stm_rutas.guardar_rutas(rfc, pry)
    assert ruta == archivo
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    assert datos["rfc"] == str(rfc.resolve())
    assert datos["pry"] == str(pry.resolve())


def test_guardar_rutas_rechaza_rutas_solapadas(monkeypatch, tmp_path):
    rfc = tmp_path / "RFC"
    rfc.mkdir()
    _preparar_config(monkeypatch, tmp_path)
    with pytest.raises(ErrorProyecto):
        stm_rutas.guardar_rutas(rfc, rfc / "PRY")


def test_guardar_rutas_rechaza_directorio_inexistente(monkeypatch, tmp_path):
    _preparar_config(monkeypatch, tmp_path)
    with pytest.raises(ErrorProyecto):
        stm_rutas.guardar_rutas(tmp_path / "no-existe", tmp_path)


def test_estado_rutas_expone_el_origen():
    estado = stm_rutas.estado_rutas()
    assert set(estado) >= {"rfc", "pry", "origen_rfc", "origen_pry", "archivo"}


def test_resolver_prioriza_el_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("RFPRMN_RFC_DIR", str(tmp_path))
    ruta, origen = stm_rutas._resolver_directorio(
        "RFPRMN_RFC_DIR", "rfc", tmp_path / "oficial", tmp_path / "layout", {})
    assert ruta == tmp_path
    assert origen == "entorno"


def test_resolver_usa_el_archivo_si_no_hay_entorno(monkeypatch, tmp_path):
    monkeypatch.delenv("RFPRMN_RFC_DIR", raising=False)
    elegido = tmp_path / "elegido"
    ruta, origen = stm_rutas._resolver_directorio(
        "RFPRMN_RFC_DIR", "rfc", tmp_path / "oficial", tmp_path / "layout",
        {"rfc": str(elegido)})
    assert ruta == elegido
    assert origen == "archivo"
