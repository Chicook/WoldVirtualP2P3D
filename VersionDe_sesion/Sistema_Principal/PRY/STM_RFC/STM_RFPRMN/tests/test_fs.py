"""Pruebas de las primitivas de sistema de archivos (issue #81)."""
from __future__ import annotations

import json
import os
import stat

import pytest

from STM_RFPRMN_stmDL import stm_fs
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto


def _crear_arbol(raiz, ficheros):
    """Crea ``raiz`` con el mapa ``{ruta_relativa: bytes}`` indicado."""
    for relativa, datos in ficheros.items():
        destino = raiz / relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    return raiz


def test_verificar_copia_ok(tmp_path):
    origen = _crear_arbol(tmp_path / "origen", {"a.txt": b"uno", "sub/b.txt": b"dos"})
    destino = _crear_arbol(tmp_path / "destino", {"a.txt": b"uno", "sub/b.txt": b"dos"})
    resultado = stm_fs.verificar_copia(origen, destino)
    assert resultado["ok"] is True
    assert resultado["origen"] == 2


def test_verificar_copia_detecta_faltantes(tmp_path):
    origen = _crear_arbol(tmp_path / "origen", {"a.txt": b"uno", "b.txt": b"dos"})
    destino = _crear_arbol(tmp_path / "destino", {"a.txt": b"uno"})
    resultado = stm_fs.verificar_copia(origen, destino)
    assert resultado["ok"] is False
    assert resultado["faltan"] == ["b.txt"]


def test_verificar_copia_detecta_contenido_distinto(tmp_path):
    origen = _crear_arbol(tmp_path / "origen", {"a.txt": b"uno"})
    destino = _crear_arbol(tmp_path / "destino", {"a.txt": b"UNO"})
    resultado = stm_fs.verificar_copia(origen, destino)
    assert resultado["ok"] is False
    assert resultado["distintos"] == ["a.txt"]


def test_reemplazar_directorio_copia_y_sustituye(tmp_path):
    origen = _crear_arbol(tmp_path / "origen", {"nuevo.txt": b"nuevo"})
    destino = _crear_arbol(tmp_path / "destino", {"viejo.txt": b"viejo"})
    info = stm_fs.reemplazar_directorio(origen, destino)
    assert info["reemplazado"] is True
    assert (destino / "nuevo.txt").read_bytes() == b"nuevo"
    assert not (destino / "viejo.txt").exists()
    assert not any(p.name.startswith(".destino.tmp") for p in tmp_path.iterdir())


def test_reemplazar_directorio_crea_destino_si_no_existe(tmp_path):
    origen = _crear_arbol(tmp_path / "origen", {"a.txt": b"a"})
    destino = tmp_path / "nuevo" / "destino"
    info = stm_fs.reemplazar_directorio(origen, destino)
    assert info["reemplazado"] is False
    assert (destino / "a.txt").read_bytes() == b"a"


def test_reemplazar_directorio_no_pierde_datos_si_la_copia_falla(tmp_path, monkeypatch):
    origen = _crear_arbol(tmp_path / "origen", {"nuevo.txt": b"nuevo"})
    destino = _crear_arbol(tmp_path / "destino", {"viejo.txt": b"viejo"})

    def _fallar(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(stm_fs.shutil, "copytree", _fallar)
    with pytest.raises(OSError):
        stm_fs.reemplazar_directorio(origen, destino)
    assert (destino / "viejo.txt").read_bytes() == b"viejo"


def test_reemplazar_directorio_rechaza_solape(tmp_path):
    origen = _crear_arbol(tmp_path / "origen", {"a.txt": b"a"})
    with pytest.raises(ErrorProyecto):
        stm_fs.reemplazar_directorio(origen, origen / "dentro")


def test_reemplazar_directorio_rechaza_origen_inexistente(tmp_path):
    with pytest.raises(ErrorProyecto):
        stm_fs.reemplazar_directorio(tmp_path / "no-existe", tmp_path / "destino")


def test_eliminar_ruta_borra_fichero_de_solo_lectura(tmp_path):
    archivo = tmp_path / "solo_lectura.txt"
    archivo.write_text("x", encoding="utf-8")
    os.chmod(archivo, stat.S_IREAD)
    stm_fs.eliminar_ruta(archivo)
    assert not archivo.exists()


def test_eliminar_ruta_borra_arbol_completo(tmp_path):
    arbol = _crear_arbol(tmp_path / "arbol", {"a/b/c.txt": b"c", "d.txt": b"d"})
    stm_fs.eliminar_ruta(arbol)
    assert not arbol.exists()


def test_eliminar_ruta_inexistente_no_falla(tmp_path):
    stm_fs.eliminar_ruta(tmp_path / "fantasma")


def test_borrar_contenido_conserva_el_directorio(tmp_path):
    carpeta = _crear_arbol(tmp_path / "carpeta", {"a.txt": b"a", "sub/b.txt": b"b"})
    stm_fs.borrar_contenido(carpeta)
    assert carpeta.is_dir()
    assert list(carpeta.iterdir()) == []


def test_es_subruta(tmp_path):
    padre = tmp_path / "padre"
    hijo = padre / "hijo"
    hijo.mkdir(parents=True)
    assert stm_fs.es_subruta(hijo, padre)
    assert stm_fs.es_subruta(padre, padre)
    assert not stm_fs.es_subruta(padre, hijo)


def test_copiar_contenido_rechaza_copia_en_si_misma(tmp_path):
    origen = _crear_arbol(tmp_path / "origen", {"a.txt": b"a"})
    with pytest.raises(ErrorProyecto):
        stm_fs.copiar_contenido(origen, origen / "sub")


def test_escribir_texto_atomico_no_deja_temporales(tmp_path):
    destino = tmp_path / "salida.txt"
    stm_fs.escribir_texto_atomico(destino, "contenido\n")
    assert destino.read_text(encoding="utf-8") == "contenido\n"
    sobrantes = [p.name for p in tmp_path.iterdir() if ".tmp-" in p.name]
    assert sobrantes == []


def test_escribir_texto_atomico_conserva_el_original_si_falla(tmp_path, monkeypatch):
    destino = tmp_path / "salida.txt"
    destino.write_text("original", encoding="utf-8")

    def _fallar(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(stm_fs.os, "replace", _fallar)
    with pytest.raises(OSError):
        stm_fs.escribir_texto_atomico(destino, "nuevo")
    assert destino.read_text(encoding="utf-8") == "original"


def test_escribir_json_atomico(tmp_path):
    destino = tmp_path / "datos.json"
    stm_fs.escribir_json_atomico(destino, [{"a": 1}])
    assert json.loads(destino.read_text(encoding="utf-8")) == [{"a": 1}]


def test_bloqueo_se_libera(tmp_path):
    objetivo = tmp_path / "registro.json"
    with stm_fs.bloqueo(objetivo):
        assert (tmp_path / "registro.json.lock").exists()
    assert not (tmp_path / "registro.json.lock").exists()


def test_huella_directorio_es_estable(tmp_path):
    arbol = _crear_arbol(tmp_path / "arbol", {"a.txt": b"a", "b/c.txt": b"c"})
    primera = stm_fs.huella_directorio(arbol)
    segunda = stm_fs.huella_directorio(arbol)
    assert primera == segunda
    assert set(primera) == {"a.txt", "b/c.txt"}
