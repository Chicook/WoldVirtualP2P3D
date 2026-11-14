"""Tests G4 (Etapa 1, punto 7): la IP LAN no viaja en el roster ni llega a disco.

Verifica sobre el código fuente de ChunkManager.gd que la entrada del roster es
{order, url, nick}, que el cliente ya no informa su IP, que la recepción del
roster descarta cualquier IP heredada y que la sesión en disco solo guarda la
URL del túnel.
"""
from __future__ import annotations

from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
CHUNK = SRC_DIR / "MTBGT" / "WoldVirtualP2P3D" / "gdscrip" / "ChunkManager.gd"


def _contenido() -> str:
    assert CHUNK.is_file(), "ChunkManager.gd no encontrado"
    return CHUNK.read_text(encoding="utf-8")


def test_g4_roster_sin_clave_ip():
    """Ninguna construcción del roster ni de candidatos incluye la clave ip."""
    c = _contenido()
    assert '"ip":' not in c
    assert '["ip"]' not in c
    assert '.get("ip"' not in c
    assert '# id -> {order, url, nick}' in c


def test_g4_cliente_no_informa_su_ip():
    """El cliente informa solo su URL; el anfitrión no guarda ninguna IP."""
    c = _contenido()
    assert 'func _reportar_direccion(url: String) -> void:' in c
    assert 'rpc_id(1, "_reportar_direccion", _mi_url)' in c
    assert "_mi_ip" not in c
    assert "_primera_ip_lan" not in c


def test_g4_roster_recibido_se_sanea():
    """Un roster heredado con ip se descarta al recibirlo (_sync_roster)."""
    c = _contenido()
    assert 'data[id].erase("ip")' in c


def test_g4_sesion_en_disco_solo_url():
    """La escritura de sesión nunca cae a la IP: solo la URL del túnel."""
    c = _contenido()
    assert "_escribir_host_sesion(_mi_url)" in c
    assert "else _mi_ip" not in c
    # La lectura de p2p_session.json solo toma la URL del túnel
    assert 'j.get("myTunnelUrl", "")' in c


def test_g4_migracion_solo_por_url():
    """La reconexión tras migración usa la URL; no hay caída a ws://<ip>."""
    c = _contenido()
    assert '"ws://%s:%d" % [ip, PUERTO_WS]' not in c
    assert "return _resolver_url_ws(u, PUERTO_WS)" in c
