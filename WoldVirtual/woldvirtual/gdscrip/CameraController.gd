extends Node3D
class_name CameraController

enum Profile { FIRST_PERSON, THIRD_PERSON, CINEMATIC }

@export var current_profile: Profile = Profile.THIRD_PERSON
@export var lerp_speed_base: float = 0.8
@export var mouse_sensitivity: float = 0.002
@export var tpv_distance: float = 1.8
@export var tpv_height: float = 1.6

var target_node: Node3D
var cam: Camera3D
var _rot_x: float = 0.0
var _rot_y: float = 0.0

func _ready():
	cam = Camera3D.new()
	cam.current = true
	cam.fov = 75.0
	cam.near = 0.05
	cam.far = 4000.0
	add_child(cam)
	
	# Mouse mode: visible by default (Social experience)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func set_target(node: Node3D):
	target_node = node
	if is_instance_valid(target_node):
		_rot_y = target_node.global_rotation.y

func _input(event):
	# Solo rotar si el click derecho está presionado
	if Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		if event is InputEventMouseMotion:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
			_rot_x -= event.relative.y * mouse_sensitivity
			_rot_y -= event.relative.x * mouse_sensitivity
			_rot_x = clamp(_rot_x, -1.2, 1.2) # Limitar pitch
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _physics_process(delta):
	if !is_instance_valid(target_node): return
	
	match current_profile:
		Profile.FIRST_PERSON:
			_update_fpv(delta)
		Profile.THIRD_PERSON:
			_update_tpv(delta)
		Profile.CINEMATIC:
			_update_cinematic(delta)

func _update_fpv(_delta):
	cam.global_position = target_node.global_position + Vector3(0, 1.7, 0)
	target_node.global_rotation.y = _rot_y
	cam.global_rotation = Vector3(_rot_x, _rot_y, 0)

func _update_tpv(delta):
	# Si no estamos orbitando, la cámara intenta seguir la espalda del avatar
	if !Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		_rot_y = lerp_angle(_rot_y, target_node.global_rotation.y, delta * 4.0)
		_rot_x = lerp(_rot_x, -0.2, delta * 4.0) # Inclinar un poco hacia abajo por defecto
	
	# Usar Basis con el offset configurable
	var basis = Basis(Vector3.UP, _rot_y) * Basis(Vector3.RIGHT, _rot_x)
	var target_pos = target_node.global_position + (basis * Vector3(0, tpv_height, -tpv_distance))
	
	# Suavizado de posición con delta (independiente de FPS)
	cam.global_position = cam.global_position.lerp(target_pos, delta * lerp_speed_base * 10.0)
	cam.look_at(target_node.global_position + Vector3(0, 1.2, 0))
	
	# Si el avatar se mueve y estamos orbitando, el avatar gira hacia donde mira la cámara
	if Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		if target_node is CharacterBody3D and target_node.velocity.length() > 0.5:
			target_node.global_rotation.y = lerp_angle(target_node.global_rotation.y, _rot_y, delta * 4.0)

func _update_cinematic(delta):
	# Movimiento orbital lento automático
	_rot_y += 0.2 * delta
	_update_tpv(delta)
	cam.fov = lerp(cam.fov, 60.0, 0.05)
