"""Pruebas del respaldo IPFS (P1: el shim no cuenta como subida real)."""
from __future__ import annotations

import sys
import types

import pytest

from STM_RFPRMN_stmDL import stm_ipfs


def _instalar_manager(monkeypatch, recibo: dict) -> None:
    """Sustituye ``STM_BKCH.compat_local`` por un doble que devuelve ``recibo``."""
    paquete = types.ModuleType("STM_BKCH")
    modulo = types.ModuleType("STM_BKCH.compat_local")

    class ManagerFalso:
        def almacenar_pesos(self, **_kwargs):
            return dict(recibo)

    modulo.get_ipfs_manager = lambda: ManagerFalso()
    monkeypatch.setitem(sys.modules, "STM_BKCH", paquete)
    monkeypatch.setitem(sys.modules, "STM_BKCH.compat_local", modulo)


def test_shim_simulado_no_cuenta_como_subida(monkeypatch):
    _instalar_manager(monkeypatch, {
        "cid": "QmLocalfake", "ok": False, "simulado": True,
        "error": "IPFS no disponible: shim local sin daemon."})
    with pytest.raises(ValueError) as error:
        stm_ipfs._subir_via_manager(b"{}", "pesos.json")
    assert "sin daemon" in str(error.value)


def test_cid_sintetico_tampoco_cuenta(monkeypatch):
    _instalar_manager(monkeypatch, {"cid": "QmLocalabc123", "ok": True})
    with pytest.raises(ValueError):
        stm_ipfs._subir_via_manager(b"{}", "pesos.json")


def test_manager_real_si_cuenta(monkeypatch):
    _instalar_manager(monkeypatch, {"cid": "QmRealDeVerdad123", "ok": True})
    recibo = stm_ipfs._subir_via_manager(b"{}", "pesos.json")
    assert recibo["cid"] == "QmRealDeVerdad123"
    assert recibo["via"] == "ipfs-manager"


def test_sin_daemon_el_flujo_cae_al_cid_local(monkeypatch, tmp_path):
    """Si el manager es un shim, se intentan API y CLI y se acaba en local."""
    _instalar_manager(monkeypatch, {"cid": "QmLocalfake", "ok": False, "simulado": True})
    monkeypatch.setattr(stm_ipfs, "_subir_via_api",
                        lambda *_a, **_k: (_ for _ in ()).throw(OSError("sin daemon")))
    monkeypatch.setattr(stm_ipfs, "_subir_via_cli",
                        lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError("sin binario")))
    pesos = tmp_path / "registro_pesos.json"
    pesos.write_text('{"vector": [0.1]}', encoding="utf-8")
    recibo = stm_ipfs.subir_a_ipfs(pesos)
    assert recibo["via"] == "local"
    assert recibo["cid"].startswith("QmLocal")
