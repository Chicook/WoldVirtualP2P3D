extends Node3D
## TeleportManager: NO modifica ChunkManager ni userbase.
## Observa islas generadas y guarda historial persistente (aunque el peer se vaya).
## Teleporte solo local; deja stub para futura sincronizacion P2P.
## Anadir como nodo hijo de IslaFinal (ver ISLA_FINAL.tscn).

signal islands_updated(islands: Array)
## Reemite el resultado del registro de isla que realiza ChunkManager.
signal isla_registrada(exito: bool, mensaje: String)

const SPAWN_HEIGHT := 45.0
const POLL_INTERVAL := 1.0

var island_history: Dictionary = {} # index(int) -> Vector3 (centro isla)
var owner_offline: Dictionary = {} # index(int) -> bool
var _timer := 0.0
var _chunk_manager: Node = null
var _userbase: CharacterBody3D = null

func _ready() -> void:
	_chunk_manager = get_parent()
	_userbase = get_parent().get_node_or_null("USERBASE") as CharacterBody3D
	if _chunk_manager != null and _chunk_manager.has_signal("isla_registrada"):
		_chunk_manager.connect("isla_registrada", _on_isla_registrada)
	set_process(true)
	# Escaneo inmediato + segundo escaneo tardio (los RPC de islas llegan con retardo en clientes)
	call_deferred("_scan_islands")
	await get_tree().create_timer(3.0).timeout
	_scan_islands()

func _process(delta: float) -> void:
	_timer += delta
	if _timer < POLL_INTERVAL:
		return
	_timer = 0.0
	_scan_islands()

func _scan_islands() -> void:
	if _chunk_manager == null:
		return
	var changed := false
	# 1) Leer diccionario active_islands si existe (solo lectura, sin modificarlo)
	var active: Dictionary = {}
	if _chunk_manager.get("active_islands") != null:
		active = _chunk_manager.get("active_islands")
	var chunk_size: float = float(_chunk_manager.get("chunk_size"))
	var per_row: int = int(_chunk_manager.get("islands_per_row"))
	if active != null:
		for p_id in active.keys():
			var idx := int(active[p_id])
			if not island_history.has(idx):
				island_history[idx] = _grid_pos(idx, chunk_size, per_row)
				owner_offline[idx] = false
				changed = true
		# Marcar offline las que ya no estan activas pero se conservan visitables
		for idx in island_history.keys():
			if not active.values().has(idx) and island_history.size() > 0:
				# Solo marcar offline si alguna vez hubo mas islas (evita falso offline al inicio)
				if active.size() > 0 and not owner_offline.get(idx, false):
					# No marcamos la isla 0 del host como offline mientras seamos server
					pass
	# 2) Deteccion por nodos: funciona tambien en clientes (active_islands solo vive en servidor).
	# Los duplicados de duplicate() se llaman "@ISLA3DCHUNK@N", por eso no usamos begins_with.
	# OJO: no meter "ISLA3DCHUNK"/"Oceano3D" en ignore: si Godot no renombra el
	# duplicado, comparte nombre con el original y lo descartariamos.
	# Los originales ya se excluyen por referencia (orig_island/orig_ocean).
	var ignore := ["WorldEnvironment", "DirectionalLight3D",
		"USERBASE", "TeleportManager", "TeleportPanel", "PlayerSync"]
	var orig_island: Node = _chunk_manager.get("original_island")
	var orig_ocean: Node = _chunk_manager.get("original_ocean")
	for child in _chunk_manager.get_children():
		if not (child is Node3D):
			continue
		if child == orig_island or child == orig_ocean:
			continue
		if ignore.has(child.name):
			continue
		if String(child.name).begins_with("RemotePlayer_"):
			continue
		if child is MeshInstance3D:
			continue # proxies remotos y mallas sueltas: no son islas (las islas son Node3D con hijos)
		# NOTA: los duplicados de duplicate() se llaman "@ISLA3DCHUNK@N" (empiezan
		# por @) y SI son islas: no filtrar por "@".
		var p: Vector3 = (child as Node3D).position
		# Sin filtro de cercania a (0,0): la isla 0 vive en el origen y los
		# originales ya se excluyen por referencia arriba.
		var flat := Vector3(p.x, 0, p.z)
		var found := false
		for k in island_history.keys():
			if (island_history[k] as Vector3).distance_to(flat) < chunk_size * 0.5:
				found = true
				break
		if not found:
			var idx2 := _nearest_index(flat, chunk_size, per_row)
			if not island_history.has(idx2):
				island_history[idx2] = flat
				owner_offline[idx2] = false
				changed = true
	if changed:
		islands_updated.emit(get_islands())

func _grid_pos(index: int, chunk_size: float, per_row: int) -> Vector3:
	var row: int = int(index / float(per_row))
	var col: int = index % per_row
	var pos_x := 0.0
	var pos_z := -row * chunk_size
	if row % 2 == 0:
		pos_x = -col * chunk_size
	else:
		pos_x = -(per_row - 1 - col) * chunk_size
	return Vector3(pos_x, 0, pos_z)

func _nearest_index(p: Vector3, chunk_size: float, per_row: int) -> int:
	# Encaja la posicion observada con la cuadricula teorica (tolerancia media celda).
	for i in range(0, 500):
		if island_history.has(i):
			continue
		if _grid_pos(i, chunk_size, per_row).distance_to(p) < chunk_size * 0.5:
			return i
	return island_history.size()

func get_islands() -> Array:
	var out: Array = []
	# Dueño de cada isla (solo el servidor conoce active_islands/owner_names).
	var active: Dictionary = {}
	var names: Dictionary = {}
	if _chunk_manager != null:
		if _chunk_manager.get("active_islands") != null:
			active = _chunk_manager.get("active_islands")
		if _chunk_manager.get("owner_names") != null:
			names = _chunk_manager.get("owner_names")
	var mi_isla := -1
	if _chunk_manager != null and _chunk_manager.get("my_own_index") != null:
		mi_isla = int(_chunk_manager.get("my_own_index"))
	for idx in island_history.keys():
		var dueno_uuid := _uuid_dueno(int(idx))
		out.append({
			"index": idx,
			"position": island_history[idx],
			"offline": owner_offline.get(idx, false),
			"nombre": _nombre_dueno(int(idx), active, names),
			"uuid": _uuid_corto(int(idx)),
			"propia": int(idx) == mi_isla,
			"registrada": not dueno_uuid.is_empty(),
		})
	out.sort_custom(func(a, b): return a["index"] < b["index"])
	return out


## UUID estable del dueño, o "" si el dueño no está registrado.
func _uuid_dueno(idx: int) -> String:
	if _chunk_manager == null or _chunk_manager.get("island_owners") == null:
		return ""
	var owners: Dictionary = _chunk_manager.get("island_owners")
	if not owners.has(idx):
		return ""
	var dato: Array = owners[idx]
	return str(dato[2]) if dato.size() > 2 else ""


## Nombre del dueño de la isla (nick del registro, "—" si no se conoce).
func _nombre_dueno(idx: int, active: Dictionary, names: Dictionary) -> String:
	# 1) Mapa isla->dueño: vive en TODOS los peers (los clientes no ven active_islands).
	if _chunk_manager != null and _chunk_manager.get("island_owners") != null:
		var owners: Dictionary = _chunk_manager.get("island_owners")
		if owners.has(idx):
			var dato: Array = owners[idx]
			var oid := int(dato[0])
			var nick := str(dato[1])
			if oid == multiplayer.get_unique_id():
				var propio := _leer_nick()
				return propio if propio != "" else "Tú"
			if nick != "":
				return nick
			if oid >= 0:
				return "Jugador %d" % oid
			return "—"
	# 2) Reserva solo-servidor: mapa peer->isla + nicks anunciados.
	var owner_id := -1
	for p_id in active.keys():
		if int(active[p_id]) == idx:
			owner_id = int(p_id)
			break
	if owner_id < 0:
		return "—"
	if owner_id == multiplayer.get_unique_id():
		var propio2 := _leer_nick()
		return propio2 if propio2 != "" else "Tú"
	var nombre := str(names.get(owner_id, ""))
	if nombre != "":
		return nombre
	return "Jugador %d" % owner_id


## UUID corto determinista de 6 caracteres (estable por isla, único).
func _uuid_corto(idx: int) -> String:
	var abc := "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
	var h: int = abs(int(abs(hash("WVP3D-isla-%d" % idx))) % 1073741824)
	var out := ""
	for i in 6:
		out += abc[h % 32]
		h = h >> 5
	return out


## Nick guardado en el registro (user://registro.cfg).
func _leer_nick() -> String:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") == OK:
		return str(cfg.get_value("jugador", "nick", ""))
	return ""

# Indice maximo conocido (para que un nuevo anfitrion no reutilice indices).
func get_max_index() -> int:
	var m := -1
	for idx in island_history.keys():
		m = maxi(m, int(idx))
	return m

# Isla bajo la posicion dada (la mas cercana dentro de media celda), -1 si ninguna.
func current_island_index(pos: Vector3) -> int:
	if island_history.is_empty():
		return -1
	var chunk_size := 199.5
	if _chunk_manager != null and _chunk_manager.get("chunk_size") != null:
		chunk_size = float(_chunk_manager.get("chunk_size"))
	var best := -1
	var best_d := chunk_size * 0.5
	for idx in island_history.keys():
		var c: Vector3 = island_history[idx]
		var d := Vector2(c.x - pos.x, c.z - pos.z).length()
		if d < best_d:
			best_d = d
			best = int(idx)
	return best

func mark_owner_left(_player_id: int) -> void:
	# Llamar en el futuro desde peer_disconnected sin borrar la isla.
	if _chunk_manager == null:
		return
	var _active: Dictionary = {}
	if _chunk_manager.get("active_islands") != null:
		_active = _chunk_manager.get("active_islands")
	# La isla queda en island_history para visita publica.
	islands_updated.emit(get_islands())

## API que usa el panel; el registro real vive en ChunkManager.
func registrar_mi_isla() -> void:
	if _chunk_manager != null and _chunk_manager.has_method("registrar_mi_isla"):
		_chunk_manager.call("registrar_mi_isla")
		return
	isla_registrada.emit(false, "El mundo todavía no está listo para registrar la isla.")


func _on_isla_registrada(exito: bool, mensaje: String) -> void:
	isla_registrada.emit(exito, mensaje)


func teleport_to(index: int) -> bool:
	if not island_history.has(index):
		return false
	if _userbase == null:
		_userbase = get_parent().get_node_or_null("USERBASE") as CharacterBody3D
	if _userbase == null:
		return false
	var target: Vector3 = island_history[index]
	_userbase.velocity = Vector3.ZERO
	_userbase.position = Vector3(target.x, SPAWN_HEIGHT, target.z)
	# La cámara orbital queda lejos tras el salto: recolocarla al instante.
	if _userbase.has_method("snap_camera"):
		_userbase.call("snap_camera")
	# STUB futuro sincronizado: descomentar para replicar en red
	# rpc("_sync_teleport", multiplayer.get_unique_id(), index)
	return true

# STUB reservado para sincronizacion futura (actualmente sin uso -> teleporte local).
# @rpc("any_peer", "reliable")
# func _sync_teleport(player_id: int, index: int) -> void:
# 	pass
