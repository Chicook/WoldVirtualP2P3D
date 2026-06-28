extends Node3D

# --- Config & Scenes ---
@export var chunk_scene: PackedScene
@export var user_scene: PackedScene
@export var spacing: float = 512.0

# --- Sub-Controllers ---
var network: Node
var world: Node3D
var avatar_ctrl: Node

# --- Signals ---
signal network_updated(data)

# --- Compatibility Layer (RF-02 Refactor) ---
var local_id: String: get = _get_local_id
var my_avatar: CharacterBody3D: get = _get_my_avatar
const HEIGHT = 28.0

var _local_island_data: Dictionary = {}
var _persistent_island_id: String = ""

# ── Cinemática de introducción (una sola vez por sesión) ─────────────────────
var _cinematic_played    : bool  = false
var _cinematic_ctrl      : Node  = null
var _local_island_node   : Node3D = null

func _parse_cmdline_args():
	var args = OS.get_cmdline_args() + OS.get_cmdline_user_args()
	for i in args.size():
		if args[i] == "--island-id" and i + 1 < args.size():
			_persistent_island_id = args[i+1]
			break

func get_persistent_coords() -> Vector2:
	if _persistent_island_id == "" or not ":" in _persistent_island_id:
		return Vector2.ZERO
	var parts = _persistent_island_id.split(":")
	if parts.size() >= 2:
		var x_str = parts[0].strip_edges()
		var z_str = parts[1].strip_edges().split(".")[0].strip_edges()
		var x_val = x_str.to_int()
		var z_val = z_str.to_int()
		return Vector2(float(x_val), float(z_val))
	return Vector2.ZERO

func _get_local_id():
	if network and network.local_id != "":
		return network.local_id
	return ""

func _get_my_avatar(): return avatar_ctrl.my_avatar if avatar_ctrl else null

func _ready() -> void:
	_parse_cmdline_args()
	_initialize_sub_controllers()
	_setup_connections()
	_setup_dynamic_chat_ui()

func _initialize_sub_controllers():
	# Cargar NetworkLayer modular
	network = load("res://woldvirtual/gdscrip/NetworkLayer.gd").new()
	network.name = "NetworkLayer"
	add_child(network)

	# Cargar WorldManager modular
	world = load("res://woldvirtual/gdscrip/WorldManager.gd").new()
	world.name = "WorldManager"
	world.chunk_scene = chunk_scene
	world.user_scene = user_scene
	world.spacing = spacing
	add_child(world)
	world.cleanup_ghost_islands()

	# Cargar AvatarController modular
	avatar_ctrl = load("res://woldvirtual/gdscrip/AvatarController.gd").new()
	avatar_ctrl.name = "AvatarController"
	add_child(avatar_ctrl)

	# --- ECS Infra (DevVSghcopilotIA) ---
	var registry = load("res://woldvirtual/ecs/Registry.gd").new()
	registry.name = "ECSRegistry"
	add_child(registry)

	var interp_sys = load("res://woldvirtual/ecs/systems/InterpolationSystem.gd").new()
	interp_sys.name = "InterpolationSystem"
	registry.add_child(interp_sys)

	var output_sys = load("res://woldvirtual/ecs/systems/NetworkOutputSystem.gd").new()
	output_sys.name = "NetworkOutputSystem"
	registry.add_child(output_sys)

	var proxy_sys = load("res://woldvirtual/ecs/systems/ProxySystem.gd").new()
	proxy_sys.name = "ProxySystem"
	registry.add_child(proxy_sys)

func _setup_connections():
	network.network_updated.connect(_on_network_updated)

func _on_network_updated(state: Dictionary):
	var lid = network.get_local_id()
	var users = state.get("u", {})
	var islands = state.get("i", {})
	
	print("[ChunkManager] Sincronización recibida. Usuarios: ", users.keys(), " Islas: ", islands.keys())

	if !users.has(lid):
		# A list of slots occupied by OTHER active users:
		var occupied_slots = []
		var now = Time.get_unix_time_from_system()
		for uid in users:
			if uid != lid:
				var user_t = users[uid].get("t", 0)
				if now - user_t < 25.0: # active peer (AVATAR_HEARTBEAT_TIMEOUT)
					occupied_slots.append(Vector2(users[uid].get("ix", 0), users[uid].get("iz", 0)))

		var is_alone = occupied_slots.is_empty()

		var slot = Vector2.ZERO
		var island_name = "Isla 1"
		var display_id = lid

		if !is_alone:
			slot = world.find_slot(occupied_slots)
			var p_coords = get_persistent_coords()
			if p_coords != Vector2.ZERO:
				# Check if the persistent slot is occupied by any active user
				var is_persistent_occupied = false
				for occ in occupied_slots:
					if occ.distance_to(p_coords) < 0.1:
						is_persistent_occupied = true
						break
				if not is_persistent_occupied:
					slot = p_coords

			island_name = "Isla de " + lid.substr(0, 4)
			if _persistent_island_id != "":
				display_id = _persistent_island_id
				if ":" in _persistent_island_id:
					island_name = "Isla " + _persistent_island_id.split(":")[0].strip_edges()

		var me_data = {
			"ix": slot.x, "iz": slot.y,
			"x": slot.x * spacing,
			"y": HEIGHT,
			"z": slot.y * spacing,
			"r": 0.0, "t": Time.get_unix_time_from_system()
		}

		_local_island_data = {
			"i": display_id,
			"n": island_name,
			"o": true,
			"x": slot.x,
			"z": slot.y,
			"w": lid
		}
		network.send_state(me_data, _local_island_data)
	else:
		_local_island_data = islands[lid]

	world.update_world(state, lid)

	if !is_instance_valid(avatar_ctrl.my_avatar) and world.active_users.has(lid):
		avatar_ctrl.setup_avatar(world.active_users[lid])
		_setup_camera_controller(world.active_users[lid])
	elif !world.active_users.has(lid) and users.has(lid):
		var av = world.spawn_local_user(lid, users[lid])
		avatar_ctrl.setup_avatar(av)
		world.active_users[lid] = av
		_setup_camera_controller(av)

	# ── Detectar isla local recién creada y lanzar cinemática ────────────────────
	var local_key = "%d_%d" % [int(_local_island_data.get("x", 0)), int(_local_island_data.get("z", 0))]
	if !_cinematic_played and world.active_islands.has(local_key):
		var island_node = world.active_islands[local_key]
		if is_instance_valid(island_node) and island_node != _local_island_node:
			_local_island_node = island_node
			_launch_cinematic(island_node)

	if is_instance_valid(avatar_ctrl.my_avatar):
		var entity = avatar_ctrl.my_avatar.get_node_or_null("ECSEntity")
		if is_instance_valid(entity):
			var net = entity.get_component(load("res://woldvirtual/ecs/components/NetworkStateComponent.gd"))
			if net:
				network.send_state(net.raw_data, _local_island_data)

	network_updated.emit(state)

func _setup_camera_controller(av: Node3D):
	var cam_ctrl = get_node_or_null("CameraController")
	if !cam_ctrl:
		cam_ctrl = load("res://woldvirtual/gdscrip/CameraController.gd").new()
		cam_ctrl.name = "CameraController"
		add_child(cam_ctrl)
	cam_ctrl.set_target(av)

# ─── Cinemática de introducción ───────────────────────────────────────────────
func _launch_cinematic(island_node: Node3D) -> void:
	_cinematic_played = true  # Marcar como reproducida aunque algo falle

	var av       = avatar_ctrl.my_avatar if avatar_ctrl else null
	var cam_ctrl = get_node_or_null("CameraController")

	if !is_instance_valid(av) or !is_instance_valid(cam_ctrl):
		# Avatar o cámara aún no listos: aplicar solo el rise sin cinemática de cámara
		_play_island_rise_only(island_node)
		return

	# 1) Crear el CinematicIntroController
	_cinematic_ctrl = load("res://woldvirtual/gdscrip/CinematicIntroController.gd").new()
	_cinematic_ctrl.name = "CinematicIntroController"
	add_child(_cinematic_ctrl)

	# 2) Iniciar secuencia completa
	_cinematic_ctrl.begin(island_node, av, cam_ctrl)
	print("[ChunkManager] Cinemática de introducción iniciada.")

func _play_island_rise_only(island_node: Node3D) -> void:
	# Fallback: solo anima el ascenso de la isla sin secuencia de cámara
	var target_y  = island_node.global_position.y
	var rise_anim = load("res://woldvirtual/gdscrip/IslandRiseAnimation.gd").new()
	island_node.add_child(rise_anim)
	rise_anim.play(target_y)
	print("[ChunkManager] Rise-only iniciado (sin avatar/cámara listos).")

func _setup_dynamic_chat_ui():
	# Buscar el CanvasLayer UI_Layer (padre de ChunkManager es N3DWoldVirtualMT)
	var ui_layer = get_parent().get_node_or_null("UI_Layer")
	if is_instance_valid(ui_layer):
		# Instanciar el control de Chat
		var chat_control = Control.new()
		chat_control.name = "ChatUI"
		chat_control.set_script(load("res://woldvirtual/gdscrip/ChatUI.gd"))
		ui_layer.add_child(chat_control)
		print("ChatUI instanciado dinámicamente en UI_Layer.")
	else:
		print("Error: No se encontró UI_Layer para inyectar el ChatUI.")
