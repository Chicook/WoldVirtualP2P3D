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
var _save_pos_timer := 0.0
var _last_saved_pos := Vector3.ZERO
var _last_target_host := "127.0.0.1"
var _last_target_port := 8910
var _is_explicit_client := false
var _beacon_udp: PacketPeerUDP = null
var _beacon_timer := 0.0

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
	userbase = nueva
	var tp = get_node_or_null("TeleportManager")
	if tp and "_userbase" in tp:
		tp._userbase = nueva
	var ps = get_node_or_null("PlayerSync")
	if ps and "_userbase" in ps:
		ps._userbase = nueva

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
	
	# Leer configuración de red P2P (vía argumentos CLI, p2p_session.json o auto-descubrimiento LAN)
	var peer_target := _obtener_peer_target()
	var target_host: String = peer_target.get("host", "127.0.0.1")
	var target_port: int = int(peer_target.get("port", 8910))
	var force_host: bool = bool(peer_target.get("force_host", false))
	var is_client: bool = bool(peer_target.get("is_client", false))
	var fuente: String = str(peer_target.get("source", "desconocida"))

	_last_target_host = target_host
	_last_target_port = target_port
	_is_explicit_client = is_client or (target_host != "127.0.0.1" and target_host != "localhost")

	print("================================================================")
	print("[ChunkManager/ENet] Configuración de Red P2P Resuelta:")
	print("[ChunkManager/ENet]   Origen/Fuente: ", fuente)
	print("[ChunkManager/ENet]   Rol asignado: ", "CLIENTE FORZADO" if is_client else ("SERVIDOR FORZADO" if force_host else "AUTO (Cliente/Local)"))
	print("[ChunkManager/ENet]   Host Objetivo: ", target_host)
	print("[ChunkManager/ENet]   Puerto Objetivo (ENet UDP): ", target_port)

	# Validación: si el rol es cliente explícito, el host no debe ser loopback.
	if _is_explicit_client and (target_host == "127.0.0.1" or target_host == "localhost" or target_host.is_empty()):
		printerr("[ChunkManager/ENet] ❌ INCONSISTENCIA: Rol cliente forzado pero host objetivo es loopback o vacío ('", target_host, "'). No se iniciará como cliente remoto.")
		_is_explicit_client = false

	print("[ChunkManager/ENet]   Rol EFECTIVO: ", "CLIENTE_REMOTO -> " + target_host + ":" + str(target_port) if _is_explicit_client else ("SERVIDOR_LOCAL -> 0.0.0.0:" + str(target_port) if force_host else "AUTO (intentará cliente en " + target_host + ":" + str(target_port) + ", fallback a servidor si falla)"))
	print("================================================================")

	# Diagnóstico: distinguir IP literal de nombre de host (típico de túnel HTTP).
	# Un túnel HTTP (cloudflared / serveo / localhost.run) solo reenvía TCP/HTTP y
	# NO puede transportar ENet (UDP 8910), por lo que el handshake nunca completará.
	if _is_explicit_client and not _es_ip_literal(target_host):
		printerr("[ChunkManager/ENet] ⚠ AVISO: el destino '", target_host, "' es un NOMBRE DE HOST, no una IP.")
		printerr("[ChunkManager/ENet]   Los túneles HTTP no transportan ENet (UDP). Para conexión remota usa la")
		printerr("[ChunkManager/ENet]   IP directa del anfitrión (IP LAN, o IP pública + UDP 8910 reenviado en el router).")

	if force_host:
		print("[ChunkManager/ENet] Iniciando explícitamente como Anfitrión (Servidor)...")
		_iniciar_como_servidor()
	elif _is_explicit_client:
		# Conexión remota explícita: conectar obligatoriamente como cliente a la IP remota.
		# Si falla el handshake, NO se degrada a servidor local silenciosamente.
		print("[ChunkManager/ENet] Conectando como CLIENTE hacia el anfitrión remoto: ", target_host, ":", target_port, "...")
		var err := peer.create_client(target_host, target_port)
		if err != OK:
			printerr("[ChunkManager/ENet] ERROR inmediato al crear cliente ENet hacia ", target_host, ":", target_port, " (Código: ", err, ")")
			print("[ChunkManager/ENet] Handshake remoto fallido. Revisar firewall/puerto UDP 8910 y que el anfitrión esté escuchando.")
			return
		else:
			multiplayer.multiplayer_peer = peer
			print("[ChunkManager/ENet] Socket cliente ENet abierto. Esperando handshake con ", target_host, ":", target_port, "...")
	else:
		# Modo autónomo / pruebas locales (loopback 127.0.0.1)
		print("[ChunkManager/ENet] Buscando red P2P en ", target_host, ":", target_port, "...")
		var err := peer.create_client(target_host, target_port)
		if err != OK:
			print("[ChunkManager/ENet] Sin servidor local activo (", err, "). Creando servidor local P2P...")
			_iniciar_como_servidor()
		else:
			multiplayer.multiplayer_peer = peer

func _on_connected_ok():
	print("[ChunkManager/ENet] ✔ CONECTADO EXITOSAMENTE al mundo P2P! ID único asignado: ", multiplayer.get_unique_id())
	# Anunciar mi isla por si es una reconexion tras migracion de anfitrion:
	# el servidor me reconocera y NO me creara isla nueva.
	rpc_id(1, "_claim_island", my_own_index, _mi_nick)

func _iniciar_como_servidor():
	print("[ChunkManager/ENet] Creando Servidor ENet en puerto 8910...")
	peer = ENetMultiplayerPeer.new()
	var err := peer.create_server(8910, 32)
	if err != OK:
		printerr("[ChunkManager/ENet] ERROR al crear servidor ENet en puerto 8910: ", err)
		return
	multiplayer.multiplayer_peer = peer
	var mis_ips := IP.get_local_addresses()
	var ips_txt: String = ""
	for ip in mis_ips:
		if ip != "127.0.0.1":
			ips_txt += ip + " "
	print("[ChunkManager/ENet] ✔ Servidor ENet activo en 0.0.0.0:8910. ID del servidor: ", multiplayer.get_unique_id())
	print("[ChunkManager/ENet]   IPs locales para compartir (anfitrión): ", ips_txt.strip_edges() if not ips_txt.is_empty() else "(ninguna no-loopback detectada)")

	# Activar beacon LAN de auto-descubrimiento para que otros equipos en la misma red puedan unirse sin enlace
	_iniciar_lan_beacon()

	# El servidor registra su propia isla
	owner_names[multiplayer.get_unique_id()] = _nick_unico(_mi_nick, multiplayer.get_unique_id())
	_register_player(multiplayer.get_unique_id())

func _on_connected_fail():
	printerr("[ChunkManager/ENet] ❌ Falló la conexión con el nodo objetivo en ", _last_target_host, ":", _last_target_port)
	if _is_explicit_client:
		printerr("[ChunkManager/ENet] ADVERTENCIA: El host remoto ", _last_target_host, " no respondió al handshake ENet (puerto UDP 8910 no alcanzable o cerrado).")
		print("[ChunkManager/ENet] Rol cliente explícito: NO se degrada a servidor local. Revisar conexión remota.")
	else:
		print("[ChunkManager/ENet] Nadie alojando en el par objetivo. Creando servidor local P2P...")
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
		peer.create_client(_last_target_host, _last_target_port)
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
	
	# Si esta isla es para MÍ, muevo MI avatar al centro de esta isla o a su última posición guardada
	if id == multiplayer.get_unique_id():
		my_own_index = index
		var cfg := ConfigFile.new()
		var pos_cargada := false
		if cfg.load("user://registro.cfg") == OK:
			if cfg.has_section_key("posicion", "has_saved_pos") and bool(cfg.get_value("posicion", "has_saved_pos", false)):
				var sx: float = float(cfg.get_value("posicion", "x", pos_x))
				var sy: float = float(cfg.get_value("posicion", "y", 42.0))
				var sz: float = float(cfg.get_value("posicion", "z", pos_z))
				var srot: float = float(cfg.get_value("posicion", "rot_y", 0.0))
				if sy > -5.0:
					userbase.position = Vector3(sx, sy, sz)
					userbase.rotation.y = srot
					_last_saved_pos = userbase.position
					pos_cargada = true
		if not pos_cargada:
			userbase.position.x = pos_x
			userbase.position.z = pos_z
			_last_saved_pos = userbase.position
		# La cámara orbital queda lejos tras el salto: recolocarla al instante.
		if userbase.has_method("snap_camera"):
			userbase.call("snap_camera")
		mi_isla_lista.emit()


func _process(delta: float) -> void:
	if multiplayer.is_server():
		_beacon_timer += delta
		if _beacon_timer >= 2.0:
			_beacon_timer = 0.0
			_emitir_beacon_lan()
	_save_pos_timer += delta
	if _save_pos_timer >= 1.0:
		_save_pos_timer = 0.0
		_guardar_posicion_jugador()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_PREDELETE:
		_guardar_posicion_jugador()


func _guardar_posicion_jugador() -> void:
	if userbase == null or not is_instance_valid(userbase):
		return
	if my_own_index < 0:
		return
	if userbase.position.y < -5.0:
		return
	var pos: Vector3 = userbase.position
	var rot_y: float = userbase.rotation.y
	if pos.distance_to(_last_saved_pos) < 0.05:
		return
	_last_saved_pos = pos
	var cfg := ConfigFile.new()
	var _err = cfg.load("user://registro.cfg")
	cfg.set_value("posicion", "has_saved_pos", true)
	cfg.set_value("posicion", "x", pos.x)
	cfg.set_value("posicion", "y", pos.y)
	cfg.set_value("posicion", "z", pos.z)
	cfg.set_value("posicion", "rot_y", rot_y)
	cfg.save("user://registro.cfg")


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


## Obtiene la dirección del nodo objetivo a partir de argumentos CLI, p2p_session.json o auto-descubrimiento LAN
func _obtener_peer_target() -> Dictionary:
	var res := {
		"host": "127.0.0.1",
		"port": 8910,
		"force_host": false,
		"is_client": false,
		"source": "predeterminado (loopback local)"
	}
	
	# 1. Revisar argumentos de línea de comandos (tanto de usuario como generales del motor)
	var all_args: Array = OS.get_cmdline_args()
	all_args.append_array(OS.get_cmdline_user_args())
	print("[ChunkManager/ENet] Args evaluados para resolver rol/host: ", all_args)
	
	var cli_ip := ""
	var cli_port := 0
	var cli_is_client := false
	var cli_force_host := false
	
	for i in range(all_args.size()):
		var arg: String = str(all_args[i]).strip_edges()
		if arg == "--client":
			cli_is_client = true
		elif arg == "--force-host" or arg == "--server":
			cli_force_host = true
		elif arg.begins_with("--ip="):
			cli_ip = arg.get_slice("=", 1).strip_edges().replace("\"", "").replace("'", "")
		elif arg.begins_with("--host="):
			cli_ip = arg.get_slice("=", 1).strip_edges().replace("\"", "").replace("'", "")
		elif arg.begins_with("--port="):
			cli_port = int(arg.get_slice("=", 1).strip_edges())
		elif arg == "--ip" or arg == "-ip" or arg == "--host":
			if i + 1 < all_args.size() and not str(all_args[i + 1]).begins_with("-"):
				cli_ip = str(all_args[i + 1]).strip_edges().replace("\"", "").replace("'", "")
		elif arg == "--port":
			if i + 1 < all_args.size() and not str(all_args[i + 1]).begins_with("-"):
				cli_port = int(str(all_args[i + 1]).strip_edges())
		elif arg.begins_with("--peer-url="):
			var url := arg.get_slice("=", 1).strip_edges().replace("\"", "").replace("'", "")
			if not url.is_empty():
				var parsed := _parse_url_host_port(url)
				if not parsed.get("host", "").is_empty():
					cli_ip = parsed["host"]
					if cli_port == 0:
						cli_port = parsed["port"]
		elif arg.begins_with("http://") or arg.begins_with("https://") or arg.begins_with("woldvirtual://"):
			var parsed := _parse_url_host_port(arg)
			if not parsed.get("host", "").is_empty():
				cli_ip = parsed["host"]
				if cli_port == 0:
					cli_port = parsed["port"]

	if cli_force_host:
		res["force_host"] = true
		res["source"] = "Línea de comandos (--force-host / --server)"
		return res

	if not cli_ip.is_empty():
		var final_port := cli_port if cli_port > 0 else 8910
		res["host"] = cli_ip
		res["port"] = final_port
		res["is_client"] = true
		res["source"] = "Línea de comandos (--client / --ip / --peer-url)"
		return res

	if cli_is_client:
		res["is_client"] = true

	# 2. Revisar archivos de sesión p2p_session.json generados por el Visor C#
	var posibles_rutas := [
		"user://p2p_session.json",
		"res://p2p_session.json",
		OS.get_executable_path().get_base_dir().path_join("test_user_data/user/p2p_session.json"),
		OS.get_executable_path().get_base_dir().path_join("p2p_session.json")
	]
	
	for ruta in posibles_rutas:
		if FileAccess.file_exists(ruta):
			var fa := FileAccess.open(ruta, FileAccess.READ)
			if fa:
				var txt := fa.get_as_text()
				fa.close()
				var j = JSON.parse_string(txt)
				if j is Dictionary:
					var remote_ip: String = str(j.get("remoteIp", "")).strip_edges()
					var remote_port: int = int(j.get("remotePort", 8910))
					var es_cliente: bool = bool(j.get("esCliente", false))
					var es_primero: bool = bool(j.get("esPrimerUsuario", false))
					var p_url: String = str(j.get("peerUrl", "")).strip_edges()
					
					if not remote_ip.is_empty() and remote_ip != "127.0.0.1" and remote_ip != "localhost":
						res["host"] = remote_ip
						res["port"] = remote_port if remote_port > 0 else 8910
						res["is_client"] = true
						res["source"] = "p2p_session.json (remoteIp explícito: " + ruta + ")"
						return res

					if not p_url.is_empty():
						var parsed := _parse_url_host_port(p_url)
						if not parsed.get("host", "").is_empty() and parsed["host"] != "127.0.0.1" and parsed["host"] != "localhost":
							res["host"] = parsed["host"]
							res["port"] = parsed["port"]
							res["is_client"] = true
							res["source"] = "p2p_session.json (peerUrl: " + ruta + ")"
							return res

					if es_primero:
						res["force_host"] = true
						res["source"] = "p2p_session.json (esPrimerUsuario=true)"
						return res

	# 3. Auto-descubrimiento en red local (LAN Beacon)
	# Si no se pasó enlace ni parámetro y no está forzado el anfitrión,
	# buscar brevemente si ya hay otro equipo emitiendo en la misma red LAN.
	var lan_host := _buscar_host_en_lan(350)
	if not lan_host.is_empty():
		res["host"] = lan_host["host"]
		res["port"] = int(lan_host.get("port", 8910))
		res["is_client"] = true
		res["source"] = "Auto-descubrimiento en red local (Beacon UDP LAN)"
		return res

	return res


## True si el texto es una dirección IPv4 literal (p. ej. 192.168.1.10).
func _es_ip_literal(texto: String) -> bool:
	var partes := texto.strip_edges().split(".")
	if partes.size() != 4:
		return false
	for p in partes:
		if not p.is_valid_int():
			return false
		var n := int(p)
		if n < 0 or n > 255:
			return false
	return true


func _parse_url_host_port(url_str: String) -> Dictionary:
	var clean := url_str.strip_edges().replace("\"", "").replace("'", "")
	clean = clean.replace("https://", "").replace("http://", "").replace("woldvirtual://", "").strip_edges()
	if clean.contains("/"):
		clean = clean.split("/")[0]
	var host := clean
	var port := 8910
	if clean.contains(":"):
		var partes := clean.split(":")
		host = partes[0].strip_edges()
		var p := int(partes[1].strip_edges())
		# Si el puerto en la URL es el de WebNodo HTTP (3030..3040), de la API P2P (7890), o HTTP/HTTPS (80/443),
		# redirigir al puerto ENet UDP estándar del motor (8910)
		if (p >= 3030 and p <= 3040) or p == 7890 or p == 80 or p == 443:
			port = 8910
		elif p > 0 and p <= 65535:
			port = p
	return {"host": host, "port": port}


func _iniciar_lan_beacon() -> void:
	if _beacon_udp == null:
		_beacon_udp = PacketPeerUDP.new()
		_beacon_udp.set_broadcast_enabled(true)
		_beacon_udp.set_dest_address("255.255.255.255", 8912)
		print("[ChunkManager/ENet] Beacon LAN activo en puerto UDP 8912 para auto-descubrimiento.")


func _emitir_beacon_lan() -> void:
	if _beacon_udp and multiplayer.is_server():
		var msg := "WOLDVIRTUAL_HOST_8910".to_utf8_buffer()
		_beacon_udp.put_packet(msg)


func _buscar_host_en_lan(timeout_ms: int = 350) -> Dictionary:
	var listener := PacketPeerUDP.new()
	var bind_err := listener.bind(8912)
	if bind_err != OK:
		return {}

	var start_time := Time.get_ticks_msec()
	while Time.get_ticks_msec() - start_time < timeout_ms:
		OS.delay_msec(25)
		if listener.get_available_packet_count() > 0:
			var pkt := listener.get_packet()
			var msg := pkt.get_string_from_utf8()
			var sender_ip := listener.get_packet_ip()
			if msg.begins_with("WOLDVIRTUAL_HOST") and not sender_ip.is_empty():
				# Descartar paquetes propios si provienen de esta misma máquina
				var mis_ips := IP.get_local_addresses()
				if not mis_ips.has(sender_ip) and sender_ip != "127.0.0.1":
					listener.close()
					print("[ChunkManager/ENet] Par anfitrión detectado en LAN: ", sender_ip, ":8910")
					return {"host": sender_ip, "port": 8910}
	listener.close()
	return {}

