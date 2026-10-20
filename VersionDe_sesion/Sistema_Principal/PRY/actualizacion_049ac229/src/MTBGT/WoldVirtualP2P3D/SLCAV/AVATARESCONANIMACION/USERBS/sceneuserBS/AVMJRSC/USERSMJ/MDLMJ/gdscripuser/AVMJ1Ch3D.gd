extends CharacterBody3D
## Controlador del avatar (selector / portal).
## Reproduce TODAS las animaciones del AnimationTree del avatar:
## parado, caminar, correr y strafe izquierda/derecha, con cámara orbital
## en tercera persona igual que userbaseh1.

@export var speed := 2.5
@export var run_speed := 5.0
@export var jump_velocity := 4.5
@export var blend_speed := 8.0
@export var mouse_sensitivity := 0.003
@export var camera_distance := 2.3
@export var camera_target_height := 1.0
@export var camera_pitch_limit := 75.0
@export var camera_follow_speed := 6.0
## En la vista previa del registro se pone en false (no se mueve ni toca cámara).
@export var enable_control := true

enum St { IDLE, WALK, RUN, STRAFE_LEFT, STRAFE_RIGHT }

const BLEND_PATHS := [
	"parameters/ANMJ/blend_amount",
	"parameters/Add2/add_amount",
	"parameters/Blend2/blend_amount",
	"parameters/Blend2 2/blend_amount",
	"parameters/Blend2 3/blend_amount",
]

var _state := St.IDLE
## Estado expuesto para compatibilidad con PlayerSync (0=idle, 1=andar, 2=correr).
var current_animation: int = 0
var _blends := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0])
var alt_gr_pressed := false
var _cam_yaw := 0.0
var _cam_pitch := 0.18

@onready var animation_tree: AnimationTree = find_child("AnimationTree", true, false)
@onready var camera: Camera3D = find_child("Camera3D", true, false)


func _ready() -> void:
	if animation_tree:
		animation_tree.active = true
	if camera and enable_control:
		camera.top_level = true
		camera.current = true
		_cam_yaw = rotation.y + PI
		_update_camera(1.0)
	_update_tree(0.0)


func _input(event: InputEvent) -> void:
	if not enable_control:
		return
	if event is InputEventKey and not event.echo:
		if event.keycode == KEY_ALT or event.physical_keycode == KEY_ALT:
			alt_gr_pressed = event.pressed
		elif event.keycode == KEY_CTRL and event.alt_pressed:
			alt_gr_pressed = event.pressed
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		rotate_y(-event.relative.x * mouse_sensitivity)
		_cam_pitch = clampf(
			_cam_pitch - event.relative.y * mouse_sensitivity,
			-deg_to_rad(camera_pitch_limit),
			deg_to_rad(camera_pitch_limit)
		)


func _physics_process(delta: float) -> void:
	if not enable_control:
		return
	if not is_on_floor():
		velocity += get_gravity() * delta
	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = jump_velocity

	var input_dir := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	# El modelo del avatar mira hacia +Z (como hm1): se invierte la entrada.
	var direction := (transform.basis * Vector3(-input_dir.x, 0.0, -input_dir.y)).normalized()
	var moving := direction.length_squared() > 0.001
	var sprinting := alt_gr_pressed or Input.is_key_pressed(KEY_ALT) or Input.is_key_pressed(KEY_AT)

	if moving:
		var selected_speed := run_speed if sprinting else speed
		velocity.x = direction.x * selected_speed
		velocity.z = direction.z * selected_speed
		if absf(input_dir.x) > 0.1 and absf(input_dir.y) < 0.6:
			_state = St.STRAFE_LEFT if input_dir.x < 0.0 else St.STRAFE_RIGHT
		elif sprinting:
			_state = St.RUN
		else:
			_state = St.WALK
	else:
		velocity.x = move_toward(velocity.x, 0.0, run_speed * 8.0 * delta)
		velocity.z = move_toward(velocity.z, 0.0, run_speed * 8.0 * delta)
		if is_on_floor():
			_state = St.IDLE

	_update_tree(delta)
	move_and_slide()
	_update_camera(delta)


func _update_camera(delta: float) -> void:
	if camera == null or not is_instance_valid(camera):
		return
	var target_yaw := rotation.y + PI
	var weight := 1.0 if delta >= 1.0 else minf(camera_follow_speed * delta, 1.0)
	_cam_yaw = lerp_angle(_cam_yaw, target_yaw, weight)
	var target := global_position + Vector3.UP * camera_target_height
	var horizontal := cos(_cam_pitch)
	var offset := Vector3(
		sin(_cam_yaw) * horizontal,
		sin(_cam_pitch),
		cos(_cam_yaw) * horizontal
	) * camera_distance
	camera.global_position = target + offset
	camera.look_at(target, Vector3.UP)


func snap_camera() -> void:
	_cam_yaw = rotation.y + PI
	_update_camera(1.0)


## Animación de clones remotos (PlayerSync): 0=idle, 1=andar, 2=correr, 3=aire.
func fija_estado_remoto(estado: int, delta: float) -> void:
	match estado:
		2:
			_state = St.RUN
		1:
			_state = St.WALK
		_:
			_state = St.IDLE
	_update_tree(delta)


func _update_tree(delta: float) -> void:
	if animation_tree == null:
		return
	var targets := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0])
	match _state:
		St.IDLE:
			current_animation = 0
		St.WALK:
			targets[0] = 1.0
			current_animation = 1
		St.RUN:
			targets[0] = 1.0
			targets[2] = 1.0
			current_animation = 2
		St.STRAFE_LEFT:
			targets[3] = 1.0
			current_animation = 1
		St.STRAFE_RIGHT:
			targets[4] = 1.0
			current_animation = 1

	var weight := 1.0 if delta <= 0.0 else minf(blend_speed * delta, 1.0)
	for index in BLEND_PATHS.size():
		_blends[index] = lerpf(_blends[index], targets[index], weight)
		animation_tree.set(BLEND_PATHS[index], _blends[index])
