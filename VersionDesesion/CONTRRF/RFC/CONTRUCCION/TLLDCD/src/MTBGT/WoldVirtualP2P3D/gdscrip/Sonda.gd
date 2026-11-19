extends Node
## Valida el transporte y la respuesta RPC sin cerrar la sesión aceptada.
const Red = preload("res://gdscrip/Red.gd")
const EcoMundo = preload("res://gdscrip/EcoMundo.gd")
var _conectado := false
var _fallo := false
var _recibido := false
var _world_ready := false
var _plazas := {}
var _eco: Node = null
var _abierta := false
var _respuestas_modulares: Dictionary = {}


## API temporal anterior; nunca sustituye una sesión ya validada.
func consultar(timeout_ms: int = 2500) -> Array:
	if Red.sesion_validada():
		if _abierta:
			return _indices(_plazas)
		var actual: Dictionary = await validar_conexion(timeout_ms)
		return actual.get("ocupados", [])
	if _abierta:
		return []
	var objetivo := Red.resolver_objetivo()
	if bool(objetivo.get("force_host", false)):
		return []
	var resultado: Dictionary = await _validar(objetivo, timeout_ms, false)
	var ocupados: Array = resultado.get("ocupados", [])
	_cerrar()
	return ocupados


func validar_conexion(timeout_ms: int = 10000) -> Dictionary:
	if _abierta:
		return _resultado(false, "Validación en curso")
	return await _validar(Red.resolver_objetivo(), timeout_ms, true)


func _resultado(ok: bool, error: String = "") -> Dictionary:
	return {"ok": ok, "error": error, "ocupados": _indices(_plazas) if ok else []}


func _validar(objetivo: Dictionary, timeout_ms: int, conservar: bool) -> Dictionary:
	_abierta = true
	_fallo = false
	_recibido = false
	_world_ready = false
	_plazas = {}
	_preparar_eco()
	if not multiplayer.connected_to_server.is_connected(_on_conectado):
		multiplayer.connected_to_server.connect(_on_conectado)
	if not multiplayer.connection_failed.is_connected(_on_fallo):
		multiplayer.connection_failed.connect(_on_fallo)
	if not multiplayer.server_disconnected.is_connected(_on_fallo):
		multiplayer.server_disconnected.connect(_on_fallo)
	var existente = multiplayer.multiplayer_peer
	# En el alta local, ChunkManager ya abrió el servidor WS en este mismo
	# MultiplayerAPI. Crear otro servidor para validar el botón Conectar falla
	# con ERR_ALREADY_IN_USE; reutilizamos el host que ya está atendiendo la isla.
	var anfitrion_local_activo := (
		conservar
		and bool(objetivo.get("force_host", false))
		and existente is WebSocketMultiplayerPeer
		and multiplayer.is_server()
		and existente.get_connection_status() == MultiplayerPeer.CONNECTION_CONNECTED
	)
	var reutilizar := (Red.sesion_validada() and existente is WebSocketMultiplayerPeer) or anfitrion_local_activo
	if reutilizar and existente.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
		_cerrar()
		return _resultado(false, "La sesión validada se desconectó")
	if not reutilizar:
		var peer := WebSocketMultiplayerPeer.new()
		var err: int
		if bool(objetivo.get("force_host", false)) and conservar:
			err = peer.create_server(int(objetivo.get("port", Red.PUERTO_WS)))
		else:
			var url := Red.resolver_url_ws(str(objetivo.get("host", "127.0.0.1")),
				int(objetivo.get("port", Red.PUERTO_WS)), str(objetivo.get("invitacion", "")))
			err = peer.create_client(url)
		if err == OK:
			multiplayer.multiplayer_peer = peer
		var limite := Time.get_ticks_msec() + timeout_ms
		while err == OK and peer.get_connection_status() == MultiplayerPeer.CONNECTION_CONNECTING and not _fallo and Time.get_ticks_msec() < limite:
			await get_tree().create_timer(0.05).timeout
		if err != OK or _fallo or peer.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
			_cerrar()
			var host := str(objetivo.get("host", "127.0.0.1"))
			if conservar and not bool(objetivo.get("force_host", false)) and not bool(objetivo.get("is_client", false)) and host in ["127.0.0.1", "localhost", ""]:
				objetivo["force_host"] = true
				return await _validar(objetivo, timeout_ms, conservar)
			return _resultado(false, "No se pudo conectar al destino WebSocket")
	if multiplayer.is_server():
		_pedir_turnos()
	else:
		rpc_id(1, "_pedir_turnos")
	var limite_rpc := Time.get_ticks_msec() + timeout_ms
	while not _recibido and not _fallo and Time.get_ticks_msec() < limite_rpc:
		await get_tree().create_timer(0.05).timeout
	if not _recibido or _fallo:
		_cerrar()
		return _resultado(false, "El anfitrión no respondió a la consulta RPC")
	if conservar:
		Red.guardar_validacion(objetivo)
	_abierta = false
	return _resultado(true)


## El cliente conserva el socket mientras el anfitrión termina su alta.
func esperar_mundo(timeout: float = 180.0) -> Dictionary:
	_preparar_eco()
	if multiplayer.multiplayer_peer == null or multiplayer.multiplayer_peer.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
		return _resultado(false, "Sesión desconectada antes de entrar al mundo")
	if multiplayer.is_server():
		return _resultado(true)
	var limite := Time.get_ticks_msec() + int(timeout * 1000.0)
	while Time.get_ticks_msec() < limite:
		if multiplayer.multiplayer_peer.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
			return _resultado(false, "El anfitrión se desconectó")
		_recibido = false
		_world_ready = false
		rpc_id(1, "_pedir_turnos")
		var respuesta := mini(limite, Time.get_ticks_msec() + 2000)
		while not _recibido and Time.get_ticks_msec() < respuesta:
			await get_tree().create_timer(0.05).timeout
		if _recibido and _world_ready:
			return _resultado(true)
		await get_tree().create_timer(0.5).timeout
	return _resultado(false, "El anfitrión no preparó el mundo a tiempo")


@rpc("any_peer", "reliable")
func _pedir_turnos() -> void:
	if not multiplayer.is_server():
		return
	var sender := multiplayer.get_remote_sender_id()
	var mundo := get_parent().get_node_or_null("ISLA3Dblock")
	var listo := mundo != null and mundo.has_method("_claim_island")
	var plazas := {}
	if listo:
		if sender > 0 and mundo.has_method("marcar_sonda"):
			mundo.call("marcar_sonda", sender)
		if mundo.has_method("turnos_snapshot"):
			plazas = mundo.call("turnos_snapshot")
	if sender == 0:
		_turnos_recibidos(plazas, listo)
	else:
		rpc_id(sender, "_turnos_recibidos", plazas, listo)


@rpc("authority", "reliable")
func _turnos_recibidos(plazas: Dictionary, world_ready: bool = false) -> void:
	_plazas = plazas.duplicate()
	_world_ready = world_ready
	_recibido = true


func _on_conectado() -> void:
	_conectado = true


func _on_fallo() -> void:
	_fallo = true


func _preparar_eco() -> void:
	if get_parent().get_node_or_null("ISLA3Dblock") != null:
		return
	_eco = EcoMundo.new()
	_eco.name = "ISLA3Dblock"
	var eco_sync := EcoMundo.EcoPlayerSync.new()
	eco_sync.name = "PlayerSync"
	_eco.add_child(eco_sync)
	get_parent().add_child(_eco)


func liberar_eco() -> void:
	if is_instance_valid(_eco):
		_eco.free()
	_eco = null


func _cerrar() -> void:
	if multiplayer.connected_to_server.is_connected(_on_conectado):
		multiplayer.connected_to_server.disconnect(_on_conectado)
	if multiplayer.connection_failed.is_connected(_on_fallo):
		multiplayer.connection_failed.disconnect(_on_fallo)
	if multiplayer.server_disconnected.is_connected(_on_fallo):
		multiplayer.server_disconnected.disconnect(_on_fallo)
	if multiplayer.multiplayer_peer != null:
		multiplayer.multiplayer_peer.close()
	multiplayer.multiplayer_peer = null
	Red.limpiar_validacion()
	liberar_eco()
	_abierta = false


func _indices(plazas: Dictionary) -> Array:
	var ocupados := []
	for k in plazas.keys():
		var i := int(k)
		if i >= 0:
			ocupados.append(i)
	ocupados.sort()
	return ocupados


## Reenvía llamadas de DAO por la sesión Godot ya validada. El servidor C# solo
## vive en el anfitrión y los clientes nunca abren un segundo túnel o socket.
func solicitar_modular(metodo: String, ruta: String, datos: Dictionary = {}) -> Dictionary:
	if multiplayer.multiplayer_peer == null or multiplayer.multiplayer_peer.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
		return {"ok": false, "status": 503, "body": {"error": "La sesión con el anfitrión no está conectada."}}
	if multiplayer.is_server():
		return await _servicio_local().solicitud_local(metodo, ruta, datos)
	var id := "%d-%d" % [OS.get_process_id(), Time.get_ticks_usec()]
	rpc_id(1, "_procesar_solicitud_modular", id, metodo, ruta, datos)
	var limite := Time.get_ticks_msec() + 20000
	while Time.get_ticks_msec() < limite:
		if _respuestas_modulares.has(id):
			var respuesta: Dictionary = _respuestas_modulares[id]
			_respuestas_modulares.erase(id)
			return respuesta
		await get_tree().create_timer(0.05).timeout
	return {"ok": false, "status": 504, "body": {"error": "El anfitrión no respondió al módulo DAO."}}


@rpc("any_peer", "reliable")
func _procesar_solicitud_modular(id: String, metodo: String, ruta: String, datos: Dictionary) -> void:
	if not multiplayer.is_server() or not _ruta_modular_permitida(metodo, ruta):
		return
	var sender := multiplayer.get_remote_sender_id()
	if sender <= 1:
		return
	var servicio := _servicio_local()
	if servicio == null:
		rpc_id(sender, "_recibir_respuesta_modular", id,
			{"ok": false, "status": 503, "body": {"error": "Servicio C# DAO no disponible."}})
		return
	var respuesta: Dictionary = await servicio.solicitud_local(metodo, ruta, datos)
	rpc_id(sender, "_recibir_respuesta_modular", id, respuesta)


@rpc("authority", "reliable")
func _recibir_respuesta_modular(id: String, respuesta: Dictionary) -> void:
	_respuestas_modulares[id] = respuesta


func _servicio_local() -> Node:
	return get_node_or_null("/root/ServicioConexionModular")


func _ruta_modular_permitida(metodo: String, ruta: String) -> bool:
	if metodo == "POST" and ruta in ["/api/session/connect", "/api/dao/register", "/api/dao/heartbeat"]:
		return true
	if metodo == "GET" and ruta == "/api/dao/members":
		return true
	return metodo == "DELETE" and ruta.begins_with("/api/dao/members/")
