extends Node3D

## Se emite cuando MI isla está generada y el avatar colocado en ella.
## El Boot la usa para cerrar la ventana de carga.
signal mi_isla_lista

@export var chunk_size: float = 199.5
@export var islands_per_row: int = 10

@onready var original_island = $ISLA3DCHUNK
@onready var original_ocean = $Oceano3D
@onready var userbase = $USERBASE

var peer = ENetMultiplayerPeer.new()
var next_island_index = 0
var active_islands = {} # Diccionario: player_id -> island_index
var owner_names = {} # Diccionario: player_id -> nick del dueño
var island_owners = {} # Diccionario: island_index -> [owner_id, nick] (vive en TODOS los peers)
var spawned_indices := {} # indices ya instanciados en esta maquina (anti-duplicados)
var my_own_index := -1 # indice de MI isla (-1 = aun sin asignar)
var pending_claims := {} # peer_id -> indice reclamado al reconectar
var _mi_nick := ""

## Sustituye el avatar por defecto (userbaseh1) por el avatar elegido en el
## carrusel. Debe llamarse ANTES de add_child() para que "@onready userbase"
## recoja el nodo nuevo, y para que TeleportManager/PlayerSync lo encuentren.
func set_player_avatar(scene_path: String) -> void:
	if scene_path.is_empty() or not ResourceLoader.exists(scene_path):
		return
	var packed := load(scene_path) as PackedScene
	if packed == null:
		return
	var old := get_node_or_null("USERBASE")
	if old == null:
		return
	var nueva := packed.instantiate()
	if nueva == null:
		return
	nueva.name = "USERBASE"
	if old is Node3D:
		(nueva as Node3D).transform = (old as Node3D).transform
	var parent := old.get_parent()
	var idx := old.get_index()
	old.free()
	parent.add_child(nueva)
	parent.move_child(nueva, idx)

func _ready():
	# Garantizar entorno con cielo y nubes si la escena se ejecuta de forma aislada
	if get_tree().root.find_child("WorldEnvironment", true, false) == null:
		var env_node := WorldEnvironment.new()
		env_node.name = "WorldEnvironment"
		env_node.environment = preload("res://gdshader/cielo_isla_env.tres")
		add_child(env_node)
		var sun_node := DirectionalLight3D.new()
		sun_node.name = "DirectionalLight3D"
		sun_node.rotation_degrees = Vector3(-35, 45, 0)
		sun_node.light_color = Color(1.0, 0.98, 0.93)
		sun_node.light_energy = 1.15
		sun_node.shadow_enabled = true
		add_child(sun_node)

	# Escondemos la isla original hasta saber si somos host o cliente
	original_island.hide()
	original_ocean.hide()
	_mi_nick = _leer_nick()
	
	multiplayer.connected_to_server.connect(_on_connected_ok)
	multiplayer.connection_failed.connect(_on_connected_fail)
	multiplayer.peer_connected.connect(_on_peer_connected)
	# Migracion de anfitrion: si el servidor se cae, un cliente asume el rol
	multiplayer.server_disconnected.connect(_on_server_disconnected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	
	# Leer configuración de red P2P (vía argumentos de usuario o archivo p2p_session.json)
	var peer_target := _obtener_peer_target()
	var target_host: String = peer_target.get("host", "127.0.0.1")
	var target_port: int = int(peer_target.get("port", 8910))
	var force_host: bool = bool(peer_target.get("force_host", false))

	if force_host:
		print("Iniciando como Anfitrión de la red P2P...")
		_iniciar_como_servidor()
	else:
		# Intentar conectarse como cliente
		print("Buscando red P2P en ", target_host, ":", target_port, "...")
		var err := peer.create_client(target_host, target_port)
		if err != OK:
			print("Error al iniciar cliente (", err, "). Creando servidor local P2P...")
			_iniciar_como_servidor()
		else:
			multiplayer.multiplayer_peer = peer

func _on_connected_ok():
	print("Conectado al mundo P2P exitosamente.")
	# Anunciar mi isla por si es una reconexion tras migracion de anfitrion:
	# el servidor me reconocera y NO me creara isla nueva.
	rpc_id(1, "_claim_island", my_own_index, _mi_nick)

func _iniciar_como_servidor():
	peer = ENetMultiplayerPeer.new()
	var err := peer.create_server(8910, 32)
	if err != OK:
		print("Error al crear servidor ENet: ", err)
		return
	multiplayer.multiplayer_peer = peer
	
	# El servidor registra su propia isla
	owner_names[multiplayer.get_unique_id()] = _nick_unico(_mi_nick, multiplayer.get_unique_id())
	_register_player(multiplayer.get_unique_id())

func _on_connected_fail():
	print("Nadie alojando en el par objetivo. Creando servidor local P2P...")
	_iniciar_como_servidor()

func _on_peer_connected(id):
	if multiplayer.is_server():
		# Enviar a este nuevo jugador las islas que ya existen (con su dueño)
		for p_id in active_islands:
			rpc_id(id, "_spawn_island_for_player", p_id, active_islands[p_id], str(owner_names.get(p_id, "")))
		# Cinturon y tirantes: reenviar islas huerfanas del historial que no esten
		# en el registro (p. ej. tras migracion de anfitrion o salidas previas).
		_send_orphan_islands(id)
		# NO registrar de inmediato: esperar la reclamacion del cliente. Si es
		# una reconexion (ya tenia isla), se adopta sin crear nada nuevo.
		_adopt_or_register.bind(id).call_deferred()

# El cliente anuncia el indice de su isla y su nick al conectarse
# (-1 = jugador nuevo).
@rpc("any_peer", "reliable")
func _claim_island(idx: int, nick: String) -> void:
	var sender := multiplayer.get_remote_sender_id()
	pending_claims[sender] = idx
	# Nombre único: si otro jugador ya usa ese nick, se sufija (#2, #3...).
	owner_names[sender] = _nick_unico(nick, sender)

# Tras el margen de reclamacion: adoptar isla existente o crear una nueva.
func _adopt_or_register(id: int) -> void:
	if not multiplayer.is_server():
		return
	await get_tree().create_timer(2.5).timeout
	if not multiplayer.get_peers().has(id):
		pending_claims.erase(id)
		return # se fue durante el margen
	var claimed := int(pending_claims.get(id, -1))
	pending_claims.erase(id)
	if claimed >= 0 and spawned_indices.has(claimed):
		# Reconexion: ya tiene isla instanciada aqui. Solo mapear, sin generar.
		# Se depuran entradas obsoletas con el mismo indice (IDs antiguos).
		_drop_fake_key(claimed)
		for old_id in active_islands.keys():
			if int(old_id) != id and int(active_islands[old_id]) == claimed and int(old_id) > 0:
				active_islands.erase(old_id)
		active_islands[id] = claimed
		next_island_index = maxi(next_island_index, claimed + 1)
		print("Reconexion reconocida: jugador ", id, " conserva isla ", claimed)
		return
	# Jugador verdaderamente nuevo: crear su isla
	_register_player(id)

# Elimina la clave ficticia que reservaba una isla huerfana ahora reclamada.
func _drop_fake_key(idx: int) -> void:
	var fakekey := -1000 - idx
	if active_islands.has(fakekey):
		active_islands.erase(fakekey)

# Envia al recien llegado las islas del historial persistente que no cubre
# active_islands. El id remitente es ficticio: _spawn solo mueve el avatar si
# coincide con el propio id, asi que es seguro.
func _send_orphan_islands(to_id: int) -> void:
	var tm = get_node_or_null("TeleportManager")
	if tm == null or not tm.has_method("get_islands"):
		return
	var covered := {}
	for idx in active_islands.values():
		covered[int(idx)] = true
	for entry in tm.get_islands():
		var idx := int(entry["index"])
		if not covered.has(idx):
			rpc_id(to_id, "_spawn_island_for_player", -1000 - idx, idx, "")
			covered[idx] = true

func _register_player(id):
	active_islands[id] = next_island_index
	rpc("_spawn_island_for_player", id, next_island_index, str(owner_names.get(id, "")))
	next_island_index += 1

# El servidor CONSERVA el registro del peer salido (no se borra): sus nodos de
# isla siguen en escena y los futuros jugadores deben recibirlos al conectarse.
func _on_peer_disconnected(id):
	var tm = get_node_or_null("TeleportManager")
	if tm != null and tm.has_method("mark_owner_left"):
		tm.mark_owner_left(id)

# Si el servidor (usuario 1) se va, este cliente asume el rol de anfitrion para
# que las nuevas instancias tengan a quien conectarse. Reconstruye el estado a
# partir del historial persistente de TeleportManager (islas ya generadas).
func _on_server_disconnected():
	print("Servidor caido. Intentando asumir el rol de anfitrion...")
	multiplayer.multiplayer_peer = null
	await get_tree().create_timer(1.0).timeout
	peer = ENetMultiplayerPeer.new()
	var err = peer.create_server(8910, 32)
	if err != OK:
		# Otro peer asumio el rol antes: reintentar como cliente
		print("Puerto ocupado, otro peer es el nuevo anfitrion. Reconectando...")
		await get_tree().create_timer(1.0).timeout
		peer = ENetMultiplayerPeer.new()
		peer.create_client("127.0.0.1", 8910)
		multiplayer.multiplayer_peer = peer
		return
	multiplayer.multiplayer_peer = peer
	# Reconstruir registro sin duplicar islas: conservar mi isla y reservar indices usados
	var tm2 = get_node_or_null("TeleportManager")
	var used_max := -1
	if tm2 != null and tm2.has_method("get_max_index"):
		used_max = tm2.get_max_index()
	next_island_index = maxi(next_island_index, used_max + 1)
	my_own_index = _my_island_index(tm2)
	var new_id := multiplayer.get_unique_id()
	# Depurar mi entrada con el ID antiguo (tras promocionar soy ID 1).
	for old_id in active_islands.keys():
		if int(old_id) != new_id and int(active_islands[old_id]) == my_own_index and int(old_id) > 0:
			active_islands.erase(old_id)
	active_islands[new_id] = my_own_index
	# Reservar las islas huerfanas del historial con claves ficticias negativas
	# para que _on_peer_connected las envie a los futuros jugadores.
	if tm2 != null and tm2.has_method("get_islands"):
		var covered := {}
		for idx in active_islands.values():
			covered[int(idx)] = true
		for entry in tm2.get_islands():
			var hidx := int(entry["index"])
			if not covered.has(hidx):
				active_islands[-1000 - hidx] = hidx
				covered[hidx] = true
	print("Ahora soy el anfitrion. next_island_index=", next_island_index)

# Recupera el indice de mi propia isla desde el historial (la isla bajo mis pies
# o la mas cercana a mi avatar); -1 si aun no hay historial.
func _my_island_index(tm) -> int:
	if tm == null or not tm.has_method("get_islands"):
		return 0
	var islands: Array = tm.get_islands()
	if islands.is_empty():
		return 0
	var best := int(islands[0]["index"])
	var best_d := 1e20
	for entry in islands:
		var pos: Vector3 = entry["position"]
		var d := Vector2(pos.x - userbase.position.x, pos.z - userbase.position.z).length()
		if d < best_d:
			best_d = d
			best = int(entry["index"])
	return best

@rpc("authority", "call_local", "reliable")
func _spawn_island_for_player(id: int, index: int, nick: String = ""):
	if spawned_indices.has(index):
		return # ya instanciada aqui (reenvio tras migracion o reconexion)
	spawned_indices[index] = true
	# Dueño conocido en todos los peers (los clientes no ven active_islands).
	island_owners[index] = [id, nick]
	print("Generando isla ", index, " para el jugador ", id)
	
	var row := int(float(index) / float(islands_per_row))
	var col = index % islands_per_row
	
	var pos_x = 0.0
	var pos_z = -row * chunk_size
	
	if row % 2 == 0:
		pos_x = -col * chunk_size
	else:
		pos_x = -(islands_per_row - 1 - col) * chunk_size
		
	# Instanciar nueva isla
	var new_island = original_island.duplicate()
	new_island.show()
	add_child(new_island)
	new_island.position.x += pos_x
	new_island.position.z += pos_z
	
	var new_ocean = original_ocean.duplicate()
	new_ocean.show()
	add_child(new_ocean)
	new_ocean.position.x += pos_x
	new_ocean.position.z += pos_z
	
	# Si esta isla es para MÍ, muevo MI avatar al centro de esta isla
	if id == multiplayer.get_unique_id():
		my_own_index = index
		userbase.position.x = pos_x
		userbase.position.z = pos_z
		# La cámara orbital queda lejos tras el salto: recolocarla al instante.
		if userbase.has_method("snap_camera"):
			userbase.call("snap_camera")
		mi_isla_lista.emit()


## Nick guardado en el registro (user://registro.cfg).
func _leer_nick() -> String:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") == OK:
		return str(cfg.get_value("jugador", "nick", ""))
	return ""


## Devuelve el nick garantizando que no lo usa otro jugador activo.
## Si está repetido, añade sufijo (#2, #3...). Solo el servidor lo aplica.
func _nick_unico(nick: String, id: int) -> String:
	var base := nick if nick != "" else ("Jugador %d" % id)
	var usados := {}
	for k in active_islands.keys():
		var kid := int(k)
		if kid != id and owner_names.has(k):
			usados[str(owner_names[k])] = true
	if not usados.has(base):
		return base
	var n := 2
	while usados.has("%s#%d" % [base, n]):
		n += 1
	return "%s#%d" % [base, n]


## Obtiene la dirección del nodo objetivo a partir de argumentos CLI o p2p_session.json
func _obtener_peer_target() -> Dictionary:
	var res := {
		"host": "127.0.0.1",
		"port": 8910,
		"force_host": false
	}
	
	# 1. Revisar argumentos de línea de comandos pasados por Visor3D
	var user_args := OS.get_cmdline_user_args()
	for arg in user_args:
		if arg.begins_with("--peer-url="):
			var url := arg.get_slice("=", 1).strip_edges().replace("\"", "")
			if not url.is_empty():
				var parsed := _parse_url_host_port(url)
				if not parsed.get("host", "").is_empty():
					res["host"] = parsed["host"]
					res["port"] = parsed["port"]
					return res
		elif arg == "--force-host":
			res["force_host"] = true
			return res

	# 2. Revisar archivos de sesión p2p_session.json
	var posibles_rutas := [
		"user://p2p_session.json",
		"C:/Users/User/Desktop/WoldVirtualP2P3D/VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/publish_out/test_user_data/user/p2p_session.json",
		"C:/Users/User/Desktop/WoldVirtualP2P3D/VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/test_user_data/user/p2p_session.json"
	]
	
	for ruta in posibles_rutas:
		if FileAccess.file_exists(ruta):
			var fa := FileAccess.open(ruta, FileAccess.READ)
			if fa:
				var txt := fa.get_as_text()
				fa.close()
				var j = JSON.parse_string(txt)
				if j is Dictionary:
					var p_url: String = str(j.get("peerUrl", "")).strip_edges()
					var es_primero: bool = bool(j.get("esPrimerUsuario", false))
					if not p_url.is_empty():
						var parsed := _parse_url_host_port(p_url)
						if not parsed.get("host", "").is_empty():
							res["host"] = parsed["host"]
							res["port"] = parsed["port"]
							return res
					# Usuario conectando sin enlace de invitación explícito:
					# Conecta automáticamente al host P2P activo (127.0.0.1:8910).
					# Al conectarse, el host le enviará su isla y spawneará la nueva isla en ambos visores.
					res["host"] = "127.0.0.1"
					res["port"] = 8910
					res["force_host"] = false
					return res

	return res


func _parse_url_host_port(url_str: String) -> Dictionary:
	var clean := url_str.replace("https://", "").replace("http://", "").strip_edges()
	if clean.contains("/"):
		clean = clean.split("/")[0]
	var host := clean
	var port := 8910
	if clean.contains(":"):
		var partes := clean.split(":")
		host = partes[0]
		port = int(partes[1])
	return {"host": host, "port": port}

