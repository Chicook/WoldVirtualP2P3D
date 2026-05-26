extends Node3D

@export var chunk_scene: PackedScene
@export var user_scene: PackedScene
@export var spacing: float = 512.0

const ISLAND_BASE_OFFSET = 33.0
const AVATAR_HEARTBEAT_TIMEOUT = 25.0

var active_islands: Dictionary = {}
var active_users: Dictionary = {}

func update_world(state: Dictionary, local_id: String):
	var users = state.get("u", {})
	var islands = state.get("i", {})
	var now = Time.get_unix_time_from_system()
	
	_update_islands(islands)
	_update_users(users, local_id, now)

func _update_islands(islands: Dictionary):
	var pos_to_id := {}
	for iid in islands:
		var d = islands[iid]
		var key = "%d_%d" % [int(d.get("x", 0)), int(d.get("z", 0))]
		if !pos_to_id.has(key): pos_to_id[key] = iid

	for key in pos_to_id:
		if !active_islands.has(key):
			var d = islands[pos_to_id[key]]
			var ch = chunk_scene.instantiate()
			add_child(ch)
			_clean_baked_water(ch)
			ch.global_position = Vector3(d.get("x", 0) * spacing, ISLAND_BASE_OFFSET, d.get("z", 0) * spacing)
			active_islands[key] = ch
			
			_attach_island_ecs(ch, pos_to_id[key], d)

	for key in active_islands.keys():
		if !pos_to_id.has(key):
			if is_instance_valid(active_islands[key]): active_islands[key].queue_free()
			active_islands.erase(key)

func _attach_island_ecs(node: Node, id: String, data: Dictionary):
	var registry = get_parent().get_node_or_null("ECSRegistry")
	if !is_instance_valid(registry): return
	
	var entity = registry.register_node_as_entity(node)
	entity.name = "ECSEntity"
	
	var spatial = load("res://woldvirtual/ecs/components/SpatialComponent.gd").new()
	spatial.position = node.global_position
	entity.add_component(spatial)
	
	var isl = load("res://woldvirtual/ecs/components/IslandComponent.gd").new()
	isl.id = id
	isl.island_name = data.get("n", "Unknown")
	isl.owner_id = data.get("w", "")
	isl.grid_pos = Vector2(data.get("x", 0), data.get("z", 0))
	entity.add_component(isl)
	
	var proxy = load("res://woldvirtual/ecs/components/ProxyComponent.gd").new()
	proxy.visibility_range = 3500.0 # Las islas se ven desde más lejos
	entity.add_component(proxy)

func _update_users(users: Dictionary, local_id: String, now: float):
	for uid in users:
		if uid == local_id: continue
		
		var is_active = now - users[uid].get("t", 0) < AVATAR_HEARTBEAT_TIMEOUT
		if !active_users.has(uid) and is_active:
			_spawn_remote_user(uid, users[uid])
		elif active_users.has(uid) and !is_active:
			active_users[uid].queue_free()
			active_users.erase(uid)
			continue

		if active_users.has(uid):
			var av = active_users[uid]
			var entity = av.get_node_or_null("ECSEntity")
			if is_instance_valid(entity):
				var net = entity.get_component(load("res://woldvirtual/ecs/components/NetworkStateComponent.gd"))
				if net:
					net.raw_data = users[uid]
					net.last_timestamp = users[uid].get("t", 0)

func _spawn_remote_user(id: String, d: Dictionary):
	var av = user_scene.instantiate()
	av.es_local = false
	add_child(av)
	av.global_position = Vector3(d.x, d.y, d.z)
	active_users[id] = av
	
	_attach_ecs_entity(av, id, d, false)

func spawn_local_user(id: String, d: Dictionary) -> CharacterBody3D:
	var av = user_scene.instantiate()
	av.es_local = true
	add_child(av)
	av.global_position = Vector3(d.x, d.y, d.z)
	active_users[id] = av
	
	_attach_ecs_entity(av, id, d, true)
	return av

func _attach_ecs_entity(node: Node, id: String, data: Dictionary, is_local: bool):
	var registry = get_parent().get_node_or_null("ECSRegistry")
	if !is_instance_valid(registry): return
	
	var entity = registry.register_node_as_entity(node)
	entity.name = "ECSEntity"
	
	var spatial = load("res://woldvirtual/ecs/components/SpatialComponent.gd").new()
	spatial.position = node.global_position
	spatial.rotation = node.global_rotation.y
	entity.add_component(spatial)
	
	var net = load("res://woldvirtual/ecs/components/NetworkStateComponent.gd").new()
	net.id = id
	net.raw_data = data
	net.is_local = is_local
	entity.add_component(net)
	
	if !is_local:
		var proxy = load("res://woldvirtual/ecs/components/ProxyComponent.gd").new()
		proxy.visibility_range = 1500.0 # Los usuarios desaparecen antes que las islas
		entity.add_component(proxy)

func _clean_baked_water(node: Node):
	for child in node.get_children(true):
		var n = child.name.to_lower()
		if n.contains("water") or n.contains("ocean") or n.contains("mar") or n.contains("agua"):
			if child is VisualInstance3D: child.hide()
		_clean_baked_water(child)

func cleanup_ghost_islands():
	for child in get_children():
		if child.name.contains("islachunk3D"):
			if !active_islands.has("0_0"):
				active_islands["0_0"] = child
				child.name = "ISLA_MAESTRA"
			else: child.queue_free()

# Patrón Boustrophedon (Zigzag) de 5x5 (RF-05 / DevTraeIA)
const _FIND_SLOT_MAX_STEPS := 512

func find_slot(occ: Array) -> Vector2:
	var valid: Array[Vector2] = []
	for entry in occ:
		if entry is Vector2: valid.append(entry)
		elif entry is Vector2i: valid.append(Vector2(entry))
		elif entry is Dictionary:
			if entry.has("ix") and entry.has("iz"): valid.append(Vector2(float(entry.ix), float(entry.iz)))
			elif entry.has("x") and entry.has("z"): valid.append(Vector2(float(entry.x), float(entry.z)))

	var n := 0
	while n < _FIND_SLOT_MAX_STEPS:
		var block_idx = floor(n / 25) # Bloque actual
		var local_n = n % 25
		var l_ix = floor(local_n / 5) # Columna local 0..4
		var l_iz_raw = local_n % 5    # Fila local 0..4
		
		# Zigzag: alterna dirección entre columnas
		var l_iz = l_iz_raw if (int(l_ix) % 2 == 0) else (4 - l_iz_raw)
		
		# Expansión hacia la izquierda (-X) por cada bloque de 5x5 completado
		var ix = (block_idx * -5) + l_ix
		var iz = l_iz
		
		var p = Vector2(ix, iz)
		if not valid.any(func(o): return o.distance_to(p) < 0.1):
			_expand_ocean_to_block(block_idx)
			return p
		n += 1

	return Vector2.ZERO

func _expand_ocean_to_block(_block_idx: int):
	# El océano se queda fijo en su posición inicial, no se mueve.
	pass

# Asigna una ubicación cercana a la isla anfitriona (RF-05 / DevTraeIA)
func assign_nearby_location(host_island_id: String, new_user_id: String) -> Vector2:
	# Obtener posición de la isla anfitriona
	var host_position = Vector2.ZERO
	
	# Buscar en active_islands
	for key in active_islands.keys():
		if key.contains(host_island_id) or key == host_island_id:
			var island_node = active_islands[key]
			if is_instance_valid(island_node):
				host_position = Vector2(island_node.global_position.x / spacing, island_node.global_position.z / spacing)
				break
	
	# Si no encontramos la isla, usar posición 0,0
	if host_position == Vector2.ZERO:
		host_position = Vector2.ZERO
	
	# Posiciones predefinidas alrededor de la isla (radio de 1 unidad de grid)
	var nearby_positions = [
		Vector2(host_position.x + 1, host_position.z),     # Derecha
		Vector2(host_position.x - 1, host_position.z),     # Izquierda
		Vector2(host_position.x, host_position.z + 1),     # Arriba
		Vector2(host_position.x, host_position.z - 1),     # Abajo
		Vector2(host_position.x + 1, host_position.z + 1), # Diagonal superior derecha
		Vector2(host_position.x - 1, host_position.z + 1), # Diagonal superior izquierda
		Vector2(host_position.x + 1, host_position.z - 1), # Diagonal inferior derecha
		Vector2(host_position.x - 1, host_position.z - 1)  # Diagonal inferior izquierda
	]
	
	# Obtener posiciones ocupadas actualmente
	var occupied_positions = []
	for user_id in active_users:
		if user_id != new_user_id:
			var user_node = active_users[user_id]
			if is_instance_valid(user_node):
				var grid_pos = Vector2(user_node.global_position.x / spacing, user_node.global_position.z / spacing)
				occupied_positions.append(grid_pos)
	
	# Encontrar primera posición disponible
	for pos in nearby_positions:
		var available = true
		for occupied in occupied_positions:
			if pos.distance_to(occupied) < 0.5:  # Margen de 0.5 unidades
				available = false
				break
		
		if available:
			print("Asignada ubicación cercana para ", new_user_id, ": ", pos, " (cerca de isla ", host_island_id, ")")
			return pos
	
	# Si todas las posiciones cercanas están ocupadas, usar el algoritmo find_slot
	print("Todas las posiciones cercanas ocupadas, usando algoritmo find_slot para ", new_user_id)
	return find_slot(occupied_positions)
