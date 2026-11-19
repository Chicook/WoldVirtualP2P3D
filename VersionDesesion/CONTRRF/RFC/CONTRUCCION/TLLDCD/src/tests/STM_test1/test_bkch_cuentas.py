"""Contrato del servidor de cuentas BKSVCB (demo local, discusión #86).

Cubre las tres rutas que usa el mundo Godot —``/alta-cuenta``,
``/descargar-cuenta-zip`` y ``/avatar-original``— sobre un ledger temporal:
estas pruebas **nunca** tocan ``STM_CH/blockchain_ledger.json``.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from STM_BKCH.stm_bkch1 import bksvcb_net

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from STM_BKCH.stm_bkch1 import BKSVCB  # noqa: E402

HUELLA = "a" * 32
NICK = "pruebacontrato"
FIRMA = "b" * 64


@pytest.fixture()
def cadena(tmp_path, monkeypatch):
    """Cadena aislada en tmp_path, con el singleton del HTTP reiniciado."""
    monkeypatch.setattr(BKSVCB, "LEDGER_PATH", tmp_path / "ledger.json")
    monkeypatch.setattr(BKSVCB, "PERMITIR_REPETIR", False)
    bksvcb_net._blockchain_instancia = None
    bksvcb_net._daemon_http_instancia = None
    yield BKSVCB.CelebroBlockchain()
    bksvcb_net._blockchain_instancia = None
    bksvcb_net._daemon_http_instancia = None


def _alta(cadena, nick: str = NICK, huella: str = HUELLA) -> dict:
    return cadena.alta_cuenta(nick=nick, huella=huella)


# ─── Alta de cuenta ─────────────────────────────────────────────────────────

def test_alta_devuelve_hash_de_bloque(cadena):
    res = _alta(cadena)
    assert res["codigo"] == 201
    assert len(res["cuenta_hash"]) == 64
    assert int(res["indice_bloque"]) >= 1


def test_alta_rechaza_nick_corto(cadena):
    res = _alta(cadena, nick="corto")
    assert res["codigo"] == 422
    assert "10" in res["error"]


def test_alta_rechaza_nick_largo(cadena):
    res = _alta(cadena, nick="x" * 16)
    assert res["codigo"] == 422


def test_alta_rechaza_huella_invalida(cadena):
    res = _alta(cadena, huella="no-es-un-uuid")
    assert res["codigo"] == 422


def test_alta_impide_dos_cuentas_por_pc(cadena):
    assert _alta(cadena)["codigo"] == 201
    segunda = _alta(cadena, nick="otrointentomas")
    assert segunda["codigo"] == 409


def test_alta_registra_un_solo_bloque_por_cuenta(cadena):
    _alta(cadena)
    bloques = [b for b in cadena.cadena
               if any(t.get("tipo") == "ALTA_CUENTA" for t in b.transacciones)]
    assert len(bloques) == 1


# ─── Archivo de cuenta ──────────────────────────────────────────────────────

def test_zip_de_cuenta_es_un_zip(cadena):
    alta = _alta(cadena)
    res = cadena.generar_zip_cuenta(alta["cuenta_hash"])
    assert res["exito"] is True
    assert res["zip_data"][:2] == b"PK"
    assert res["cuenta"]["nick"] == NICK


def test_zip_de_cuenta_inexistente_falla(cadena):
    res = cadena.generar_zip_cuenta("f" * 64)
    assert res["exito"] is False


def test_zip_rechaza_hash_mal_formado(cadena):
    res = cadena.generar_zip_cuenta("1234")
    assert res["exito"] is False


# ─── Avatar propio ──────────────────────────────────────────────────────────

def test_avatar_exige_diferencia_considerable(cadena):
    alta = _alta(cadena)
    res = cadena.registrar_avatar_original(
        alta["cuenta_hash"], NICK, FIRMA, 0.05)
    assert res["codigo"] == 422
    assert "diferencia" in res["error"]


def test_avatar_original_se_mina_y_entrena_neuronas(cadena):
    alta = _alta(cadena)
    res = cadena.registrar_avatar_original(
        alta["cuenta_hash"], NICK, FIRMA, 0.30)
    assert res["codigo"] == 201
    tipos = [t.get("tipo") for b in cadena.cadena for t in b.transacciones]
    assert "AVATAR_ORIGINAL" in tipos
    assert "ACTUALIZACION_SINAPTICA" in tipos
    assert res["neuronal"].get("sintesis")
    assert len(cadena.conversor.neuronas) == 50


def test_avatar_no_se_registra_dos_veces(cadena):
    alta = _alta(cadena)
    assert cadena.registrar_avatar_original(
        alta["cuenta_hash"], NICK, FIRMA, 0.30)["codigo"] == 201
    repetido = cadena.registrar_avatar_original(
        alta["cuenta_hash"], NICK, FIRMA, 0.30)
    assert repetido["codigo"] == 409


def test_avatar_de_cuenta_inexistente_falla(cadena):
    res = cadena.registrar_avatar_original("f" * 64, NICK, FIRMA, 0.30)
    assert res["codigo"] == 404


def test_avatar_rechaza_firma_mal_formada(cadena):
    alta = _alta(cadena)
    res = cadena.registrar_avatar_original(
        alta["cuenta_hash"], NICK, "zz", 0.30)
    assert res["codigo"] == 422


# ─── HTTP (el contrato que consume Godot) ───────────────────────────────────

@pytest.fixture()
def servidor(cadena):
    bksvcb_net._blockchain_instancia = cadena
    daemon = bksvcb_net.iniciar_servidor_blockchain(puerto=0)
    puerto = daemon.servidor.server_address[1]
    yield f"http://127.0.0.1:{puerto}"
    daemon.detener()


def _post(url: str, payload: dict) -> tuple[int, dict]:
    peticion = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            return respuesta.status, json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_http_alta_y_zip(servidor):
    codigo, alta = _post(servidor + "/alta-cuenta",
                         {"nick": NICK, "huella": HUELLA})
    assert codigo == 201
    assert len(alta["cuenta_hash"]) == 64

    with urllib.request.urlopen(
            servidor + "/descargar-cuenta-zip?cuenta_hash=" + alta["cuenta_hash"],
            timeout=15) as respuesta:
        assert respuesta.status == 200
        assert respuesta.read(2) == b"PK"


def test_http_avatar_original(servidor):
    _, alta = _post(servidor + "/alta-cuenta", {"nick": NICK, "huella": HUELLA})
    codigo, res = _post(servidor + "/avatar-original", {
        "cuenta_hash": alta["cuenta_hash"], "nick": NICK,
        "avatar_firma": FIRMA, "avatar_delta": 0.25,
    })
    assert codigo == 201
    assert res["indice_bloque"] >= 1
