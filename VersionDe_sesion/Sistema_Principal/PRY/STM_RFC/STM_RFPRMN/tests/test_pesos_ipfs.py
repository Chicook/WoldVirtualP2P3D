"""Pruebas del guardado en IPFS de los pesos y del historial."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from STM_RFPRMN_stmDL import stm_pesos_ipfs as pi


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    """Aísla la carpeta de pesos y el puntero en el directorio de la prueba."""
    monkeypatch.setattr(pi, "DIR_MODELOS_LOCAL", tmp_path)
    monkeypatch.setattr(pi, "RUTA_AGENTE", tmp_path / "agente.json")
    monkeypatch.setattr(pi, "RUTA_PUNTERO", tmp_path / "ipfs_pesos.json")
    return tmp_path


def _paquete(archivos: dict[str, bytes]) -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as paquete:
        for nombre, datos in archivos.items():
            paquete.writestr(nombre, datos)
    return memoria.getvalue()


# --- Historial ---------------------------------------------------------------

def test_guardar_y_cargar_historial(carpeta):
    assert pi.guardar_historial({"informe": [0.9, 2]}) is not None
    assert pi.cargar_historial() == {"informe": [0.9, 2]}


def test_un_historial_corrupto_no_rompe(carpeta):
    (carpeta / "agente.json").write_text("no es json", encoding="utf-8")
    assert pi.cargar_historial() == {}


def test_sin_historial_devuelve_vacio(carpeta):
    assert pi.cargar_historial() == {}


# --- Empaquetar --------------------------------------------------------------

def test_empaqueta_los_pesos_y_el_historial(carpeta):
    (carpeta / "lucia_rn_31x1.pkl").write_bytes(b"\x80\x04binario")
    (carpeta / "agente.json").write_text("{}", encoding="utf-8")
    datos, nombres = pi.empaquetar()
    assert set(nombres) == {"lucia_rn_31x1.pkl", "agente.json"}
    with zipfile.ZipFile(io.BytesIO(datos)) as paquete:
        assert paquete.read("lucia_rn_31x1.pkl") == b"\x80\x04binario"


def test_sin_archivos_el_paquete_esta_vacio(carpeta):
    assert pi.empaquetar()[1] == []


# --- Subir -------------------------------------------------------------------

def test_subir_guarda_el_puntero_con_sha_y_cid(carpeta, monkeypatch):
    (carpeta / "agente.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(pi, "subir_a_ipfs",
                        lambda _ruta: {"cid": "QmPrueba", "via": "api-http",
                                       "modo": "real"})
    recibo = pi.subir()
    assert recibo["ok"] is True and recibo["cid"] == "QmPrueba"
    puntero = json.loads((carpeta / "ipfs_pesos.json").read_text(encoding="utf-8"))
    assert puntero["cid"] == "QmPrueba"
    assert len(puntero["sha256"]) == 64


def test_subir_sin_pesos_no_hace_nada(carpeta):
    assert pi.subir()["ok"] is False


# --- Descargar ---------------------------------------------------------------

def test_descargar_verifica_y_restaura(carpeta, monkeypatch):
    datos = _paquete({"lucia_rn_31x1.pkl": b"\x80\x04pesos",
                      "agente.json": b'{"informe": [1.0, 1]}'})
    puntero = {"cid": "QmPrueba", "modo": "real",
               "sha256": hashlib.sha256(datos).hexdigest()}
    (carpeta / "ipfs_pesos.json").write_text(json.dumps(puntero), encoding="utf-8")

    class _Respuesta:
        def read(self):
            return datos

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(pi.urllib.request, "urlopen", lambda *_a, **_k: _Respuesta())
    resultado = pi.descargar()
    assert resultado["ok"] is True
    assert (carpeta / "lucia_rn_31x1.pkl").read_bytes() == b"\x80\x04pesos"
    assert (carpeta / "agente.json").read_text(encoding="utf-8").startswith("{")


def test_descargar_rechaza_si_el_sha_no_coincide(carpeta, monkeypatch):
    puntero = {"cid": "QmPrueba", "modo": "real", "sha256": "0" * 64}
    (carpeta / "ipfs_pesos.json").write_text(json.dumps(puntero), encoding="utf-8")

    class _Respuesta:
        def read(self):
            return b"otra cosa"

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(pi.urllib.request, "urlopen", lambda *_a, **_k: _Respuesta())
    resultado = pi.descargar()
    assert resultado["ok"] is False and "SHA-256" in resultado["motivo"]


def test_descargar_sin_cid(carpeta):
    assert pi.descargar()["ok"] is False


def test_descargar_cid_local_no_se_intenta(carpeta):
    puntero = {"cid": "QmLocal123", "modo": "local-sin-daemon", "sha256": "0" * 64}
    (carpeta / "ipfs_pesos.json").write_text(json.dumps(puntero), encoding="utf-8")
    resultado = pi.descargar()
    assert resultado["ok"] is False and "local" in resultado["motivo"]


def test_sincronizar_no_baja_si_hay_pesos_locales(carpeta):
    (carpeta / "lucia_rn_31x1.pkl").write_bytes(b"x")
    assert "presentes" in pi.sincronizar_al_iniciar()["motivo"]


def test_sincronizar_sin_puntero_no_hace_nada(carpeta):
    assert pi.sincronizar_al_iniciar()["ok"] is False


# --- Estado ------------------------------------------------------------------

def test_estado_resume_el_puntero(carpeta):
    (carpeta / "agente.json").write_text("{}", encoding="utf-8")
    (carpeta / "ipfs_pesos.json").write_text(
        json.dumps({"cid": "QmX", "via": "cli", "archivos": ["agente.json"]}),
        encoding="utf-8")
    datos = pi.estado()
    assert datos["cid"] == "QmX" and datos["pesos"] >= 1
