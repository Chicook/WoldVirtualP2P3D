"""Pruebas de la descarga verificada de pesos GGUF (issue #80)."""
from __future__ import annotations

import urllib.request

import pytest

from STM_RFPRMN_stmDL import stm_descarga
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

CABECERA_GGUF = b"GGUF\x03\x00\x00\x00"


class RespuestaFalsa:
    """Doble de ``urlopen``: sirve un cuerpo fijo y cabeceras controladas."""

    def __init__(self, datos: bytes, cabeceras: dict, status: int = 200) -> None:
        self._datos = datos
        self._posicion = 0
        self.headers = cabeceras
        self.status = status

    def read(self, tamano: int = -1) -> bytes:
        if self._posicion >= len(self._datos):
            return b""
        fin = self._posicion + tamano if tamano and tamano > 0 else len(self._datos)
        trozo = self._datos[self._posicion:fin]
        self._posicion += len(trozo)
        return trozo

    def __enter__(self):
        return self

    def __exit__(self, *_excepcion):
        return False


@pytest.fixture(autouse=True)
def _sin_esperas(monkeypatch):
    """Evita las pausas entre reintentos durante las pruebas."""
    monkeypatch.setattr(stm_descarga.time, "sleep", lambda *_: None)


def _cuerpo(total: int) -> bytes:
    relleno = b"\x00" * max(total - len(CABECERA_GGUF), 0)
    return CABECERA_GGUF + relleno


def test_peso_gguf_valido_acepta_cabecera_correcta(tmp_path):
    archivo = tmp_path / "modelo.gguf"
    archivo.write_bytes(_cuerpo(1024))
    assert stm_descarga.peso_gguf_valido(archivo, minimo=100) is True


def test_peso_gguf_valido_rechaza_truncado(tmp_path):
    archivo = tmp_path / "modelo.gguf"
    archivo.write_bytes(_cuerpo(10))
    assert stm_descarga.peso_gguf_valido(archivo, minimo=100) is False


def test_peso_gguf_valido_rechaza_cabecera_ajena(tmp_path):
    archivo = tmp_path / "modelo.gguf"
    archivo.write_bytes(b"XXXX" + b"\x00" * 1024)
    assert stm_descarga.peso_gguf_valido(archivo, minimo=100) is False


def test_descarga_acepta_archivo_completo(tmp_path, monkeypatch):
    datos = _cuerpo(4096)
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(
                            datos, {"Content-Length": str(len(datos))}))
    destino = tmp_path / "modelos"
    ruta = stm_descarga.descargar_gguf("repo/x", "modelo.gguf", destino,
                                       minimo=1024, reintentos=1)
    assert ruta == destino / "modelo.gguf"
    assert ruta.stat().st_size == len(datos)
    assert not (destino / "modelo.gguf.part").exists()


def test_descarga_no_repite_si_el_peso_ya_es_valido(tmp_path, monkeypatch):
    destino = tmp_path / "modelos"
    destino.mkdir()
    (destino / "modelo.gguf").write_bytes(_cuerpo(4096))

    def _no_debe_llamarse(*_a, **_k):
        raise AssertionError("no debería tocar la red")

    monkeypatch.setattr(urllib.request, "urlopen", _no_debe_llamarse)
    ruta = stm_descarga.descargar_gguf("repo/x", "modelo.gguf", destino,
                                       minimo=1024)
    assert ruta.exists()


def test_descarga_descarta_un_final_truncado(tmp_path, monkeypatch):
    destino = tmp_path / "modelos"
    destino.mkdir()
    (destino / "modelo.gguf").write_bytes(_cuerpo(10))  # resto de una caída
    datos = _cuerpo(4096)
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(
                            datos, {"Content-Length": str(len(datos))}))
    ruta = stm_descarga.descargar_gguf("repo/x", "modelo.gguf", destino,
                                       minimo=1024, reintentos=1)
    assert ruta.stat().st_size == len(datos)


def test_descarga_reanuda_con_range(tmp_path, monkeypatch):
    destino = tmp_path / "modelos"
    destino.mkdir()
    completo = _cuerpo(2048)
    mitad = 1024
    (destino / "modelo.gguf.part").write_bytes(completo[:mitad])
    enviado = {}

    def _urlopen(peticion, **_kwargs):
        enviado["range"] = peticion.headers.get("Range")
        resto = completo[mitad:]
        return RespuestaFalsa(resto, {
            "Content-Length": str(len(resto)),
            "Content-Range": f"bytes {mitad}-{len(completo) - 1}/{len(completo)}",
        }, status=206)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    ruta = stm_descarga.descargar_gguf("repo/x", "modelo.gguf", destino,
                                       minimo=1024, reintentos=1)
    assert enviado["range"] == f"bytes={mitad}-"
    assert ruta.read_bytes() == completo


def test_descarga_rechaza_contenido_que_no_es_gguf(tmp_path, monkeypatch):
    datos = b"XXXX" + b"\x00" * 4092
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(
                            datos, {"Content-Length": str(len(datos))}))
    destino = tmp_path / "modelos"
    with pytest.raises(ErrorProyecto):
        stm_descarga.descargar_gguf("repo/x", "modelo.gguf", destino,
                                    minimo=1024, reintentos=1)
    assert not (destino / "modelo.gguf").exists()


def test_descarga_conserva_el_part_si_el_tamano_no_cuadra(tmp_path, monkeypatch):
    datos = _cuerpo(512)
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *_a, **_k: RespuestaFalsa(
                            datos, {"Content-Length": "999999"}))
    destino = tmp_path / "modelos"
    with pytest.raises(ErrorProyecto):
        stm_descarga.descargar_gguf("repo/x", "modelo.gguf", destino,
                                    minimo=256, reintentos=1)
    assert (destino / "modelo.gguf.part").exists()
    assert not (destino / "modelo.gguf").exists()
