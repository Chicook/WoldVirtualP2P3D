# VehicleBase.gd - Godot 4.7.2 - Car, Plane, Boat, Bike - Enter/Exit + P2P sync
extends VehicleBody3D
class_name WoldVehicle

enum VehicleType { CAR, PLANE, BOAT, BIKE, HELICOPTER }

@export var vehicle_type: VehicleType = VehicleType.CAR
@export var max_speed: float = 50.0
@export var engine_power: float = 1500.0
@export var can_fly: bool = false
@export var fuel: float = 100.0

var is_occupied: bool = false
var driver: Node3D = null
var driver_peer_id: String = ""

@onready var enter_area: Area3D = $EnterArea
@onready var exit_marker: Marker3D = $ExitMarker
@onready var camera_mount: Marker3D = $CameraMount

func _ready():
	if enter_area:
		enter_area.body_entered.connect(_on_body_enter)
	# Setup wheels if car
	if vehicle_type == VehicleType.CAR:
		engine_power = 2000.0
		max_speed = 60.0
	elif vehicle_type == VehicleType.PLANE:
		can_fly = true
		engine_power = 5000.0
		max_speed = 200.0
		gravity_scale = 0.3

func _on_body_enter(body: Node3D):
	if is_occupied: return
	if body.has_method("get_peer_id") and body.is_in_group("player"):
		_show_enter_prompt(body)

func _show_enter_prompt(player: Node3D):
	# UI prompt - "Press E to enter %s" % vehicle_type
	if player.has_method("show_prompt"):
		player.show_prompt("Press [E] to enter %s - Fuel %.0f%%" % [VehicleType.keys()[vehicle_type], fuel])

func enter_vehicle(player: Node3D):
	if is_occupied: return false
	driver = player
	is_occupied = true
	driver_peer_id = player.get_peer_id() if player.has_method("get_peer_id") else "unknown"
	
	# Hide player, attach to vehicle
	player.visible = false
	player.set_physics_process(false)
	if player.has_method("set_driving"):
		player.set_driving(true, self)
	
	# Camera to vehicle
	if camera_mount and player.has_method("attach_camera_to"):
		player.attach_camera_to(camera_mount)
	
	print("[VEHICLE] %s entered %s Peer:%s" % [driver_peer_id, VehicleType.keys()[vehicle_type], driver_peer_id])
	return true

func exit_vehicle():
	if not is_occupied: return
	if driver:
		driver.global_position = exit_marker.global_position if exit_marker else global_position + Vector3(3,0,0)
		driver.visible = true
		driver.set_physics_process(true)
		if driver.has_method("set_driving"):
			driver.set_driving(false, null)
		if driver.has_method("attach_camera_to"):
			driver.attach_camera_to(null)
	
	print("[VEHICLE] %s exited %s" % [driver_peer_id, VehicleType.keys()[vehicle_type]])
	driver = null
	is_occupied = false
	driver_peer_id = ""

func _physics_process(delta):
	if not is_occupied: return
	if fuel <= 0: return
	
	var input_throttle = Input.get_action_strength("move_forward") - Input.get_action_strength("move_back")
	var input_steer = Input.get_action_strength("move_right") - Input.get_action_strength("move_left")
	
	if vehicle_type == VehicleType.CAR:
		engine_force = input_throttle * engine_power
		steering = input_steer * 0.6
		fuel -= abs(input_throttle) * delta * 0.1
	
	elif vehicle_type == VehicleType.PLANE and can_fly:
		# Plane flight - real lift
		var speed = linear_velocity.length()
		var lift = Vector3.UP * speed * 0.3 * max(0, input_throttle)
		apply_central_force(lift)
		apply_central_force(-global_transform.basis.z * input_throttle * engine_power)
		apply_torque(Vector3(input_steer * 1000, 0, -input_steer * 500))
		fuel -= abs(input_throttle) * delta * 0.3
		
		if Input.is_action_just_pressed("exit_vehicle"):
			exit_vehicle()

	# Exit
	if Input.is_action_just_pressed("exit_vehicle"):
		exit_vehicle()
