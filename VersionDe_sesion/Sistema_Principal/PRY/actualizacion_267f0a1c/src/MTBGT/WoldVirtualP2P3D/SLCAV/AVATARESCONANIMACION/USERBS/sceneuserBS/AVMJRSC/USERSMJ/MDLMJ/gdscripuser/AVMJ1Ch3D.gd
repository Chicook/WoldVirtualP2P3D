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
## El avatar responde a las flechas desde el arranque; sólo se suelta
## mientras el teclado está en el chat del visor o en modo construcción.
var control_avatar := true
var _clic_pendiente := Vector2.INF
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


## Clic izquierdo: si el rayo de cámara alcanza al avatar, recupera el control
## (por ejemplo, tras escribir en el chat). Un clic fuera no lo suelta.
func _unhandled_input(event: InputEvent) -> void:
	if not enable_control or get_meta("construccion_activa", false):
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_clic_pendiente = event.position


func _clic_sobre_avatar(screen_pos: Vector2) -> bool:
	if camera == null or not is_instance_valid(camera):
		# Sin cámara orbital (primera persona) cualquier clic toma el control.
		return true
	var origen := camera.project_ray_origin(screen_pos)
	var destino := origen + camera.project_ray_normal(screen_pos) * 1000.0
	var consulta := PhysicsRayQueryParameters3D.create(origen, destino)
	consulta.collide_with_areas = false
	var impacto := get_world_3d().direct_space_state.intersect_ray(consulta)
	return not impacto.is_empty() and impacto.get("collider") == self


## Al salir de Godot (clic en el chat del visor) se suelta el avatar y las
## teclas: evita que una flecha pulsada durante el cambio de foco lo mueva.
## Al volver a la vista 3D recupera el control sin exigir otro clic.
func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		control_avatar = false
		alt_gr_pressed = false
		velocity.x = 0.0
		velocity.z = 0.0
		for accion in ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]:
			Input.action_release(accion)
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		control_avatar = not get_meta("construccion_activa", false)


func _physics_process(delta: float) -> void:
	if not enable_control:
		return
	if not is_on_floor():
		velocity += get_gravity() * delta
	# El raycast se resuelve aquí: el estado físico solo se consulta en física.
	# Sólo devuelve el control; un clic fuera del cuerpo no lo quita.
	if _clic_pendiente != Vector2.INF:
		if _clic_sobre_avatar(_clic_pendiente):
			control_avatar = true
		_clic_pendiente = Vector2.INF
	if control_avatar and Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = jump_velocity

	# Las flechas sólo mueven al avatar cuando tiene el control (sin chat ni construcción).
	var input_dir := Vector2.ZERO
	if control_avatar:
		input_dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
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
		# Saltar parámetros que no existen en este árbol
		if animation_tree.get(BLEND_PATHS[index]) == null:
			continue
		_blends[index] = lerpf(_blends[index], targets[index], weight)
		animation_tree.set(BLEND_PATHS[index], _blends[index])

