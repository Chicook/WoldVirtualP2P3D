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

	if !users.has(lid):
		var slot = world.find_slot(users.values().map(func(u): return Vector2(u.get("ix", 0), u.get("iz", 0))))
		var p_coords = get_persistent_coords()
		if p_coords != Vector2.ZERO:
			slot = p_coords

		# Si solo hay un usuario conectado, su ubicacion por defecto es 0,0,0 (evita tembleque de floats)
		var is_alone = true
		for uid in users:
			if uid != lid:
				is_alone = false
				break
		if is_alone:
			slot = Vector2.ZERO

		var me_data = {
			"ix": slot.x, "iz": slot.y,
			"x": slot.x * spacing,
			"y": HEIGHT,
			"z": slot.y * spacing,
			"r": 0.0, "t": Time.get_unix_time_from_system()
		}
		var island_name = "Isla de " + lid.substr(0, 4)
		var display_id = lid
		
		if _persistent_island_id != "":
			display_id = _persistent_island_id
			if ":" in _persistent_island_id:
				island_name = "Isla " + _persistent_island_id.split(":")[0].strip_edges()

		_local_island_data = {
			"i": display_id,
			"n": island_name,
			"o": true,
			"x": slot.x,
			"z": slot.y
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
