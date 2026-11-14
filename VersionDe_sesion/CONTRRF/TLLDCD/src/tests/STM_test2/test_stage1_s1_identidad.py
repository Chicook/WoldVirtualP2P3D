"""Tests de la Etapa 1 S1: identidad de pares V2 (prueba de posesión).

Verifica sobre la fuente GDScript que declarar el UUID de un dueño
desconectado ya no basta para quedarse su isla: hay prueba de posesión
con sal fresca, reclamación en cola con confirmación diferida y un mapa
privado uuid -> peer_id que solo vive en el anfitrión.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2]
GD_DIR = SRC_DIR / "MTBGT" / "WoldVirtualP2P3D" / "gdscrip"


def _leer(nombre: str) -> str:
    ruta = GD_DIR / nombre
    assert ruta.is_file(), f"{nombre} no encontrado"
    return ruta.read_text(encoding="utf-8")


def _cuerpo(contenido: str, inicio: str) -> str:
    """Cuerpo de una función: desde su firma hasta la siguiente función."""
    pos = contenido.index(inicio)
    resto = contenido[pos + len(inicio):]
    fin = len(resto)
    for marca in ("\nfunc ", "\n@rpc(", "\nstatic func ", "\n## "):
        idx = resto.find(marca)
        if 0 <= idx < fin:
            fin = idx
    return resto[:fin]


def test_identidad_prueba_de_posesion_es_hash_salado():
    """Identidad.gd: la credencial comparada es el hash salado, no el UUID."""
    contenido = _leer("Identidad.gd")

    assert 'const DOMINIO_PRUEBA := "wv-p2p3d-prueba-v2"' in contenido
    assert "static func generar_sal() -> String:" in contenido
    assert "Crypto.new().generate_random_bytes(16).hex_encode()" in contenido

    cuerpo = _cuerpo(contenido, "static func prueba_de_posesion(uuid: String, sal: String) -> String:")
    assert "if not uuid_valido(uuid) or sal.is_empty():" in cuerpo
    assert "HashingContext.HASH_SHA256" in cuerpo
    assert "ctx.finish().hex_encode()" in cuerpo
    # El orden de las partes es el del diseño: dominio, sal y por último el UUID.
    i_dominio = cuerpo.index("DOMINIO_PRUEBA.to_utf8_buffer()")
    i_sal = cuerpo.index("sal.to_utf8_buffer()")
    i_uuid = cuerpo.index("uuid.to_utf8_buffer()")
    assert i_dominio < i_sal < i_uuid

    verificar = _cuerpo(contenido, "static func verificar_prueba(uuid: String, sal: String, prueba: String) -> bool:")
    assert "if prueba.is_empty():" in verificar
    assert "var esperada := prueba_de_posesion(uuid, sal)" in verificar
    # Se compara la prueba recibida contra la recomputada, nunca el UUID solo.
    assert "prueba == esperada" in verificar


def test_red_expone_version_prueba_sin_credencial_lan():
    """Red.gd: apoyo V2 (versión y sal delegada) sin ganar credencial LAN (H7)."""
    contenido = _leer("Red.gd")

    assert "const VERSION_PRUEBA := 2" in contenido
    assert '"version_prueba": VERSION_PRUEBA' in contenido
    assert 'const Identidad = preload("res://gdscrip/Identidad.gd")' in contenido

    sal = _cuerpo(contenido, "static func generar_sal_desafio() -> String:")
    assert "return Identidad.generar_sal()" in sal

    version = _cuerpo(contenido, "static func es_version_con_prueba(version: int) -> bool:")
    assert "return version >= VERSION_PRUEBA" in version

    # Las firmas del handshake existente no cambian y no nace ninguna
    # función de credencial o token LAN nueva en Red.gd.
    assert "static func resolver_url_ws(host: String, port: int, invitacion: String" in contenido
    assert "static func token_de_url(url: String) -> String:" in contenido
    assert not re.search(r"func \w*(credencial_lan|token_lan|lan_token)\w*", contenido)


def test_chunkmanager_estado_privado_y_ventanas():
    """ChunkManager.gd: constantes de ventana y estado solo del anfitrión."""
    contenido = _leer("ChunkManager.gd")

    assert "const VENTANA_VERIFICADA_MS := 10000" in contenido
    assert "const VENTANA_COMPAT_MS := 30000" in contenido
    assert "const TTL_DESAFIO_MS := 15000" in contenido

    assert "var _mapa_privado_uuid_peer := {}" in contenido
    assert "var _peer_por_uuid_verificado := {}" in contenido
    assert "var _desafios := {}" in contenido
    assert "var _reclamaciones_pendientes := {}" in contenido
    # La cola nueva no reutiliza el margen inicial de 2,5 s existente.
    assert "var pending_claims := {}" in contenido
    assert "var pending_uuids := {}" in contenido

    assert "func peer_verificado(id: int, uuid: String) -> bool:" in contenido
    verificado = _cuerpo(contenido, "func peer_verificado(id: int, uuid: String) -> bool:")
    assert "_mapa_privado_uuid_peer" in verificado
    assert "return false" in verificado

    registrar = _cuerpo(contenido, "func _registrar_verificado(id: int, uuid: String) -> void:")
    assert "_mapa_privado_uuid_peer" in registrar
    assert "_peer_por_uuid_verificado" in registrar

    olvidar = _cuerpo(contenido, "func _olvidar_verificado(id: int) -> void:")
    assert "_mapa_privado_uuid_peer" in olvidar
    assert "_peer_por_uuid_verificado" in olvidar


def test_chunkmanager_desafio_de_posesion_por_rpc():
    """El anfitrión desafía y solo acepta la reclamación si la prueba verifica."""
    contenido = _leer("ChunkManager.gd")

    assert 'func _desafio_posesion(sal: String, indice: int) -> void:' in contenido
    desafio = _cuerpo(contenido, "func _desafio_posesion(sal: String, indice: int) -> void:")
    # El cliente responde con la prueba de SU uuid, sin enviar el uuid en claro.
    assert "Identidad.prueba_de_posesion(_mi_uuid, sal)" in desafio
    assert 'rpc_id(1, "_responder_desafio", prueba)' in desafio

    assert 'func _responder_desafio(prueba: String) -> void:' in contenido
    respuesta = _cuerpo(contenido, "func _responder_desafio(prueba: String) -> void:")
    assert "_desafios" in respuesta
    assert "TTL_DESAFIO_MS" in respuesta
    assert "Identidad.verificar_prueba(" in respuesta
    assert "_reclamaciones_pendientes" in respuesta
    assert "verificada" in respuesta

    # _claim_island conserva su firma (compat) pero además emite el desafío.
    claim = _cuerpo(contenido, 'func _claim_island(idx: int, nick: String, uuid: String = "") -> void:')
    assert "_desafios[" in claim
    assert "generar_sal" in claim
    assert '"_desafio_posesion"' in claim


def test_reclamacion_de_dueno_desconectado_se_encola():
    """La isla de un dueño desconectado se encola; no se adopta al instante."""
    contenido = _leer("ChunkManager.gd")

    assert "func _encolar_reclamacion(id: int, indice: int, uuid: String, nick: String) -> void:" in contenido
    cola = _cuerpo(contenido, "func _encolar_reclamacion(id: int, indice: int, uuid: String, nick: String) -> void:")
    assert "_reclamaciones_pendientes[id] =" in cola
    assert "verificada" in cola
    assert "madura_en" in cola
    assert "VENTANA_COMPAT_MS" in cola

    # El camino de adopción tras el margen inicial pasa por la cola en el
    # caso de dueño registrado ausente, en vez de adoptar directamente.
    adoptar = _cuerpo(contenido, "func _adopt_or_register(id: int) -> void:")
    assert "_encolar_reclamacion(" in adoptar

    assert "func _procesar_reclamaciones() -> void:" in contenido
    proceso = _cuerpo(contenido, "func _process(delta: float) -> void:")
    assert "_procesar_reclamaciones()" in proceso
    procesar = _cuerpo(contenido, "func _procesar_reclamaciones() -> void:")
    assert "_reclamaciones_pendientes" in procesar
    assert "_adoptar_isla(" in procesar

    assert "func _cancelar_reclamaciones_de_isla(indice: int, excepto_id: int) -> void:" in contenido

    puede = _cuerpo(contenido, "func _puede_reclamar_isla(index: int, id: int, uuid: String) -> bool:")
    assert "_reclamaciones_pendientes" in puede
    assert "_mapa_privado_uuid_peer" in puede

    adopcion = _cuerpo(contenido, "func _adoptar_isla(id: int, index: int, uuid: String) -> void:")
    assert "_registrar_verificado(" in adopcion
    assert "_cancelar_reclamaciones_de_isla(" in adopcion

    desconexion = _cuerpo(contenido, "func _on_peer_disconnected(id):")
    assert "_olvidar_verificado(" in desconexion
    assert "_desafios" in desconexion
    assert "_reclamaciones_pendientes" in desconexion


def test_mapa_privado_no_se_difunde_ni_se_persiste():
    """El mapa uuid -> peer_id verificado nunca sale del anfitrión."""
    contenido = _leer("ChunkManager.gd")
    # Primero debe existir: sin mapa privado, lo demás pasaría en vacío.
    assert "var _mapa_privado_uuid_peer := {}" in contenido
    privados = ("_mapa_privado_uuid_peer", "_peer_por_uuid_verificado",
                "_reclamaciones_pendientes")

    # Ninguna llamada rpc()/rpc_id() transporta el estado privado.
    for linea in contenido.splitlines():
        if "rpc(" in linea or "rpc_id(" in linea:
            for nombre in privados + ("_desafios",):
                assert nombre not in linea, f"estado privado en RPC: {linea.strip()}"

    # Ni la difusión de dueños/roster ni el registro persistente lo contienen.
    for firma in ("func _spawn_island_for_player(", "func _sync_island_owner(",
                  "func _sync_roster(", "func _broadcast_roster()",
                  "func _guardar_registro_islas()", "func _vincular_propietario("):
        cuerpo = _cuerpo(contenido, firma)
        for nombre in privados:
            assert nombre not in cuerpo, f"{nombre} aparece en {firma}"

    # island_owners sigue llevando solo [id, nick, uuid dueño], sin el mapa.
    assert "island_owners[index] = [id, nick, dueno_actual]" in contenido


def test_construccion_validar_remitente_exige_verificado():
    """Construccion.gd: en el anfitrión no basta el UUID declarado."""
    contenido = _leer("Construccion.gd")

    cuerpo = _cuerpo(contenido, "func _validar_remitente(idx: int, remitente: int) -> bool:")
    # Primero la comprobación de siempre contra island_owners...
    assert "if int(dato[0]) != remitente:" in cuerpo
    # ...y después, solo en el anfitrión y con guarda, la identidad verificada.
    assert 'if multiplayer.is_server() and cm.has_method("peer_verificado"):' in cuerpo
    assert "var dueno_uuid := _uuid_dueno(idx)" in cuerpo
    assert 'return bool(cm.call("peer_verificado", remitente, dueno_uuid))' in cuerpo
    assert cuerpo.index("int(dato[0])") < cuerpo.index("peer_verificado")

    # _es_mi_isla queda como comprobación local: no consulta el mapa privado
    # (en el cliente no existe) y conserva su lógica por índice y por UUID.
    mia = _cuerpo(contenido, "func _es_mi_isla(idx: int) -> bool:")
    assert "int(propio) == idx" in mia
    assert "dueno == _mi_uuid()" in mia
    assert "peer_verificado" not in mia
