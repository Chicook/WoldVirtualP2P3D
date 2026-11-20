extends Node
## Sonda de sesion: consulta puntual de plazas ocupadas antes del carrusel.
##
## Vive en <Boot>/Sonda en todos los peers. El anfitrion la usa para responder
## (lee las plazas de su mundo) y el invitado para preguntar. La conexion es
## corta y se cierra al recibir la respuesta: el mundo abre despues su propia
## conexion, de modo que el flujo de red del mundo no cambia.

const Red = preload("res://gdscrip/Red.gd")
const EcoMundo = preload("res://gdscrip/EcoMundo.gd")

var _conectado := false
var _fallo := false
var _recibido := false
var _plazas := {}
var _eco: Node = null
var _abierta := false


## Devuelve los indices de avatar ocupados ([] si no hay anfitrion alcanzable).
func consultar(timeout_ms: int = 2500) -> Array:
	if _abierta:
		return []
	var objetivo := Red.resolver_objetivo()
	if bool(objetivo.get("force_host", false)):
		return []

	var host := str(objetivo.get("host", "127.0.0.1")).strip_edges()
	if host.is_empty():
		host = "127.0.0.1"
	var url := Red.resolver_url_ws(host, int(objetivo.get("port", Red.PUERTO_WS)),
			str(objetivo.get("invitacion", "")))

	_abierta = true
	_conectado = false
	_fallo = false
	_recibido = false
	_plazas = {}
	_preparar_eco()
	multiplayer.connected_to_server.connect(_on_conectado)
	multiplayer.connection_failed.connect(_on_fallo)
	multiplayer.server_disconnected.connect(_on_fallo)

	var peer := WebSocketMultiplayerPeer.new()
	var err := peer.create_client(url)
	if err != OK:
		_cerrar()
		return []
	multiplayer.multiplayer_peer = peer

	var inicio := Time.get_ticks_msec()
	while Time.get_ticks_msec() - inicio < timeout_ms and not _conectado and not _fallo:
		await get_tree().create_timer(0.05).timeout
	if not _conectado:
		print("[Sonda] Sin sesion en ", url)
		_cerrar()
		return []

	rpc_id(1, "_pedir_turnos")
	inicio = Time.get_ticks_msec()
	while Time.get_ticks_msec() - inicio < timeout_ms and not _recibido and not _fallo:
		await get_tree().create_timer(0.05).timeout

	var plazas := _plazas.duplicate()
	_cerrar()
	if not _recibido:
		print("[Sonda] El anfitrion no respondio a tiempo")
		return []
	print("[Sonda] Plazas ocupadas: ", plazas.size(), " -> ", _indices(plazas))
	return _indices(plazas)


## El invitado pregunta. Solo responde el anfitrion, que es la autoridad.
@rpc("any_peer", "reliable")
func _pedir_turnos() -> void:
	if not multiplayer.is_server():
		return
	var sender := multiplayer.get_remote_sender_id()
	if sender == 0:
		return
	var mundo := get_parent().get_node_or_null("ISLA3Dblock")
	if mundo == null:
		rpc_id(sender, "_turnos_recibidos", {})
		return
	if mundo.has_method("marcar_sonda"):
		mundo.call("marcar_sonda", sender)
	var plazas := {}
	if mundo.has_method("turnos_snapshot"):
		plazas = mundo.call("turnos_snapshot")
	rpc_id(sender, "_turnos_recibidos", plazas)


@rpc("authority", "reliable")
func _turnos_recibidos(plazas: Dictionary) -> void:
	_plazas = plazas
	_recibido = true


func _on_conectado() -> void:
	_conectado = true


func _on_fallo() -> void:
	_fallo = true


## El mundo del anfitrion envia islas/roster al consultante; se descartan aqui.
func _preparar_eco() -> void:
	if get_parent().get_node_or_null("ISLA3Dblock") != null:
		return
	_eco = EcoMundo.new()
	_eco.name = "ISLA3Dblock"
	var eco_sync := EcoMundo.EcoPlayerSync.new()
	eco_sync.name = "PlayerSync"
	_eco.add_child(eco_sync)
	get_parent().add_child(_eco)


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
	if _eco != null and is_instance_valid(_eco):
		_eco.free()
	_eco = null
	_abierta = false


func _indices(plazas: Dictionary) -> Array:
	var ocupados := []
	for k in plazas.keys():
		var i := int(k)
		if i >= 0:
			ocupados.append(i)
	ocupados.sort()
	return ocupados
