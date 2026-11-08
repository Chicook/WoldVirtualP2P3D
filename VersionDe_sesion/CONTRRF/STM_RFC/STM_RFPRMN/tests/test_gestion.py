"""Pruebas de los comandos de gestión y del registro de envíos (issue #81)."""
from __future__ import annotations

import json

import pytest

from STM_RFPRMN_stmDL import stm_gestion
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto, RAIZ, RFC_DIR, MODULO_DIR


# --- protección de rutas -----------------------------------------------------

def test_bloquea_borrar_la_raiz_del_proyecto():
    with pytest.raises(ErrorProyecto):
        stm_gestion._comprobar_borrado(RAIZ)


def test_bloquea_borrar_rfc():
    with pytest.raises(ErrorProyecto):
        stm_gestion._comprobar_borrado(RFC_DIR)


def test_bloquea_borrar_dentro_de_la_herramienta():
    with pytest.raises(ErrorProyecto):
        stm_gestion._comprobar_borrado(MODULO_DIR / "STM_RFPRMN_stmDL")


def test_permite_borrar_un_temporal(tmp_path):
    carpeta = tmp_path / "temporal"
    carpeta.mkdir()
    stm_gestion._comprobar_borrado(carpeta)  # no debe lanzar


# --- creación segura ---------------------------------------------------------

def test_crear_carpeta_rechaza_nombres_que_escapan(tmp_path):
    with pytest.raises(ErrorProyecto):
        stm_gestion.crear_carpeta(str(tmp_path), "..")
    with pytest.raises(ErrorProyecto):
        stm_gestion.crear_carpeta(str(tmp_path), "../fuera")


def test_crear_carpeta_normal(tmp_path):
    ruta = stm_gestion.crear_carpeta(str(tmp_path), "nueva")
    assert (tmp_path / "nueva").is_dir()
    assert ruta == str(tmp_path / "nueva")


# --- registro de envíos ------------------------------------------------------

def test_registrar_envio_es_atomico(tmp_path, monkeypatch):
    registro = tmp_path / "envios.json"
    monkeypatch.setattr(stm_gestion, "REGISTRO_ENVIOS", registro)
    stm_gestion._registrar_envio(tmp_path, tmp_path / "destino", 3, "OK")
    stm_gestion._registrar_envio(tmp_path, tmp_path / "destino", 4, "OK")
    datos = json.loads(registro.read_text(encoding="utf-8"))
    assert isinstance(datos, list) and len(datos) == 2
    assert datos[-1]["ficheros"] == 4
    sobrantes = [p.name for p in tmp_path.iterdir()
                 if p.name.endswith((".lock", ".tmp")) or ".tmp-" in p.name]
    assert sobrantes == []


def test_registrar_envio_conserva_json_corrupto(tmp_path, monkeypatch):
    registro = tmp_path / "envios.json"
    registro.write_text("{esto no es json", encoding="utf-8")
    monkeypatch.setattr(stm_gestion, "REGISTRO_ENVIOS", registro)
    stm_gestion._registrar_envio(tmp_path, tmp_path / "destino", 1, "OK")
    datos = json.loads(registro.read_text(encoding="utf-8"))
    assert len(datos) == 1
    assert (tmp_path / "envios.json.corrupto").exists()


def test_registrar_envio_tolera_registro_no_lista(tmp_path, monkeypatch):
    registro = tmp_path / "envios.json"
    registro.write_text('{"clave": "valor"}', encoding="utf-8")
    monkeypatch.setattr(stm_gestion, "REGISTRO_ENVIOS", registro)
    stm_gestion._registrar_envio(tmp_path, tmp_path / "destino", 1, "OK")
    datos = json.loads(registro.read_text(encoding="utf-8"))
    assert isinstance(datos, list) and len(datos) == 1


# --- P4: sin rama heredada ---------------------------------------------------

def test_refactorizar_sin_layout_no_toca_nada(monkeypatch):
    """P4: si el layout no se reconoce, se informa y no se copia nada."""
    errores: list[str] = []
    monkeypatch.setattr(stm_gestion, "_es_layout_actual", lambda: False)
    monkeypatch.setattr(stm_gestion, "reportar_error", errores.append)
    monkeypatch.setattr(stm_gestion, "_refactorizar_layout_actual",
                        lambda: (_ for _ in ()).throw(AssertionError("no debe copiar")))
    stm_gestion.comando_refactorizar()
    assert errores and "layout" in errores[0]


def test_actualizar_sin_layout_no_toca_nada(monkeypatch):
    errores: list[str] = []
    monkeypatch.setattr(stm_gestion, "_es_layout_actual", lambda: False)
    monkeypatch.setattr(stm_gestion, "reportar_error", errores.append)
    monkeypatch.setattr(stm_gestion, "_actualizar_layout_actual",
                        lambda: (_ for _ in ()).throw(AssertionError("no debe copiar")))
    stm_gestion.actualizar()
    assert errores and "layout" in errores[0]
