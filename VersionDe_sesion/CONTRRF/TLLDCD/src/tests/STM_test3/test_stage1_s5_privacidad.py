"""Tests de la Etapa 1 S5 (G4): privacidad de la IP del par en ChunkManager.gd.

La IP LAN de un par no puede (a) formar parte del roster, (b) escribirse en
la persistencia de sesion, (c) sobrevivir a la carga de datos heredados ni
(d) viajar en ningun payload RPC de roster o de union. La IP usada solo en
local (el destino que el propio usuario elige en Red.gd, el beacon LAN) no
es la fuga G4 y queda fuera de estas prohibiciones.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2]
GD_DIR = SRC_DIR / "MTBGT" / "WoldVirtualP2P3D" / "gdscrip"
CHUNK = GD_DIR / "ChunkManager.gd"
RED = GD_DIR / "Red.gd"


def _contenido(ruta: Path = CHUNK) -> str:
    assert ruta.is_file(), f"{ruta.name} no encontrado"
    return ruta.read_text(encoding="utf-8")


def _cuerpo(contenido: str, nombre: str) -> str:
    """Cuerpo de una funcion: de 'func nombre(' a la siguiente funcion."""
    ini = contenido.index(f"func {nombre}(")
    resto = contenido[ini:]
    m = re.search(r"\nfunc \w+\(", resto[1:])
    return resto if m is None else resto[: m.start() + 1]


def test_s5_roster_sin_campo_ip_en_toda_construccion():
    """(a) Toda construccion del roster es {order, url, nick}, sin clave ip."""
    c = _contenido()
    literales = [
        ln for ln in c.splitlines()
        if "_roster" in ln and "= {" in ln and '"order"' in ln
    ]
    assert len(literales) >= 3, f"Construcciones del roster no halladas: {literales}"
    for ln in literales:
        assert '"url"' in ln and '"nick"' in ln, ln
        assert '"ip"' not in ln, f"El roster aun guarda la IP: {ln.strip()}"
    # Ninguna escritura posterior introduce la clave en una entrada ya creada
    assert '["ip"]' not in c
    assert '"ip":' not in c


def test_s5_la_unica_clave_ip_del_archivo_es_su_borrado():
    """La sola aparicion de la clave ip es el saneado al recibir el roster."""
    c = _contenido()
    apariciones = [ln.strip() for ln in c.splitlines() if '"ip"' in ln]
    assert apariciones == ['data[id].erase("ip")'], apariciones


def test_s5_reportar_direccion_solo_url_en_firma_y_llamadas():
    """(d) El cliente informa solo su URL de tunel; la firma no acepta IP."""
    c = _contenido()
    assert "func _reportar_direccion(url: String) -> void:" in c
    llamadas = re.findall(r'rpc_id\(1, "_reportar_direccion"[^)]*\)', c)
    assert len(llamadas) >= 2, llamadas
    for ll in llamadas:
        assert ll == 'rpc_id(1, "_reportar_direccion", _mi_url)', ll
    cuerpo = _cuerpo(c, "_reportar_direccion")
    assert '_roster[sender]["url"] = url' in cuerpo
    assert '"ip"' not in cuerpo


def test_s5_sin_variable_de_ip_propia_que_alimente_el_roster():
    """Sin _mi_ip ni _primera_ip_lan: ya no existe el dato que viajaba."""
    c = _contenido()
    assert "_mi_ip" not in c
    assert "_primera_ip_lan" not in c


def test_s5_persistencia_de_sesion_solo_escribe_la_url():
    """(b) session_host.txt solo recibe la URL; sin URL no se escribe nada."""
    c = _contenido()
    llamadas = [
        ln.strip() for ln in c.splitlines()
        if "_escribir_host_sesion(" in ln and not ln.strip().startswith("func ")
    ]
    assert len(llamadas) >= 3, llamadas
    for ll in llamadas:
        assert "_mi_ip" not in ll, ll
        assert '"ip"' not in ll, ll
    assert llamadas.count("_escribir_host_sesion(_mi_url)") >= 3, llamadas
    cuerpo = _cuerpo(c, "_escribir_host_sesion")
    assert "session_host.txt" in cuerpo
    assert "if url.is_empty():" in cuerpo
    assert cuerpo.index("if url.is_empty():") < cuerpo.index("FileAccess.WRITE")
    assert "f.store_string(url)" in cuerpo


def test_s5_p2p_session_json_nunca_se_escribe_desde_gdscript():
    """(b) ChunkManager solo LEE p2p_session.json; jamas lo escribe."""
    c = _contenido()
    assert 'p2p_session.json", FileAccess.WRITE' not in c
    assert 'FileAccess.open("user://p2p_session.json", FileAccess.READ)' in c
    for ln in c.splitlines():
        if "p2p_session.json" in ln and "FileAccess.open" in ln:
            assert "FileAccess.READ" in ln, ln


def test_s5_carga_de_sesion_ignora_ip_heredada_del_json():
    """(c) _leer_mi_url solo extrae myTunnelUrl; una IP heredada se ignora."""
    c = _contenido()
    cuerpo = _cuerpo(c, "_leer_mi_url")
    claves = re.findall(r'j\.get\("([^"]+)"', cuerpo)
    assert claves == ["myTunnelUrl"], claves
    assert "remoteIp" not in cuerpo and '"ip"' not in cuerpo


def test_s5_sync_roster_descarta_ip_heredada_antes_de_guardar():
    """(c) Un roster de un anfitrion antiguo pierde su ip al recibirse."""
    c = _contenido()
    cuerpo = _cuerpo(c, "_sync_roster")
    assert "is Dictionary" in cuerpo
    assert 'erase("ip")' in cuerpo
    assert cuerpo.index('erase("ip")') < cuerpo.index("_roster = data")


def test_s5_ningun_payload_rpc_lleva_ip():
    """(d) Ninguna llamada rpc/rpc_id del archivo transporta la IP."""
    c = _contenido()
    llamadas = re.findall(r'rpc(?:_id)?\([^\n]*', c)
    assert llamadas, "No se hallaron llamadas RPC"
    for ll in llamadas:
        assert "_mi_ip" not in ll, ll
        assert '"ip"' not in ll, ll
        assert '["ip"]' not in ll, ll
    difusion = _cuerpo(c, "_broadcast_roster")
    assert 'rpc("_sync_roster", _roster)' in difusion


def test_s5_migracion_solo_reconecta_por_url_de_tunel():
    """(d) Los candidatos de migracion no llevan ip ni caen a ws://<ip>."""
    c = _contenido()
    cand = _cuerpo(c, "_candidatos_migracion")
    assert '"ip"' not in cand and '.get("ip"' not in cand
    assert '"url": str(e.get("url", ""))' in cand
    url_c = _cuerpo(c, "_url_candidato")
    assert '"ip"' not in url_c and '.get("ip"' not in url_c
    assert "return _resolver_url_ws(u, PUERTO_WS)" in url_c
    assert 'return ""' in url_c
    assert '"ws://%s:%d" % [ip, PUERTO_WS]' not in c


def test_s5_red_destino_elegido_por_el_usuario_no_es_roster():
    """Red.gd resuelve el destino que el propio usuario elige (CLI, su
    p2p_session.json local o el beacon LAN): es uso local de una direccion
    de destino, no difusion de la IP de un par, y no debe romperse."""
    r = _contenido(RED)
    assert "static func resolver_objetivo() -> Dictionary:" in r
    assert 'j.get("remoteIp", "")' in r
    assert 'j.get("peerUrl", "")' in r
    # Red.gd no difunde nada: no tiene RPC ni escribe ficheros
    assert "rpc(" not in r and "rpc_id(" not in r
    assert "FileAccess.WRITE" not in r
    c = _contenido()
    assert "return Red.resolver_objetivo()" in c
