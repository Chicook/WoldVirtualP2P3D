extends CharacterBody3D

## Controlador adaptado al AnimationTree de userbaseh1.tscn.
## El árbol usa una cadena de Blend2: cada valor activa la animación
## situada en la entrada 1 de ese Blend2.

#region 1. EXPORTS (ajustes desde el editor)
@export var speed := 2.5
@export var run_speed := 5.0
@export var jump_velocity := 4.5
@export var blend_speed := 8.0
@export var mouse_sensitivity := 0.003
@export var camera_distance := 2.0
@export var camera_target_height := 1.0
@export var camera_pitch_limit := 75.0
@export var camera_follow_speed := 6.0
#endregion


#region 2. REFERENCIAS A NODOS
## Búsqueda dinámica en lugar de rutas hardcodeadas:
## El avatar elegido puede ser hm1, AVH1-12 o AVMJ1-12; cada uno tiene
## su AnimationTree y AnimationPlayer en ubicaciones distintas del árbol,
## pero find_child los localiza correctamente en cualquier caso.
@onready var animation_tree: AnimationTree  = find_child("AnimationTree",  true, false)
@onready var animation_player: AnimationPlayer = find_child("AnimationPlayer", true, false)
@onready var camera: Camera3D = find_child("Camera3D", true, false)
#endregion


#region 3. CONSTANTES Y ESTADOS
const BLEND_PATHS := [
	"parameters/Blend2/blend_amount",
	"parameters/Blend2 2/blend_amount",
	"parameters/Blend2 3/blend_amount",
	"parameters/Blend2 4/blend_amount",
	"parameters/Blend2 5/blend_amount",
	"parameters/Blend2 6/blend_amount",
	"parameters/Blend2 7/blend_amount",
]

enum AnimationState { IDLE, WALK, RUN, RUN_HTR, JUMP, AIR, STRAFE_LEFT, STRAFE_RIGHT }
#endregion


#region 4. VARIABLES DE ESTADO
var current_animation := AnimationState.IDLE
var blend_values := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
var alt_gr_pressed := false
## El avatar no responde a las flechas hasta que se hace clic sobre él
## (en el visor WPF el foco del teclado se comparte con el chat).
var control_avatar := false
var _clic_pendiente := Vector2.INF
# La cámara orbita con retardo: el cuerpo gira al instante (se VE girar),
# la cámara lo sigue suavemente y termina detrás (espalda).
var _cam_yaw := 0.0
var _cam_pitch := 0.0
# Clon remoto (PlayerSync): sin entrada ni física propias; PlayerSync
# coloca posición/rotación y fija la animación con fija_estado_remoto().
var es_clon_remoto := false
#endregion


#region 5. INICIALIZACIÓN
func _ready() -> void:
	# Cámara orbital detrás del avatar (lado -Z, viendo su espalda).
	# El avatar mira hacia +Z, por eso la cámara se coloca a PI del frente.
	# En clones remotos no se toca: PlayerSync libera su cámara.
	if not es_clon_remoto and camera != null:
		camera.top_level = true
		_cam_yaw = rotation.y + PI
		_cam_pitch = 0.0
		_update_camera_follow(1.0)

	# Falling_IdleOF existe solo en hm1 (Mixamo); AVMJ/AVH no la tienen → null-guard.
	if animation_player != null:
		var falling_animation := animation_player.get_animation("Falling_IdleOF") \
			if animation_player.has_animation("Falling_IdleOF") else null
		if falling_animation:
			falling_animation.loop_mode = Animation.LOOP_LINEAR

	if animation_tree != null:
		animation_tree.active = true
	_update_animation_tree(0.0)
#endregion


#region 6. ENTRADA (teclado y ratón)
func _input(event: InputEvent) -> void:
	if es_clon_remoto:
		return
	# 6.1. Tecla Alt Gr (sprint): puede llegar como KEY_ALT o Ctrl+Alt en Windows.
	if event is InputEventKey and not event.echo:
		if event.keycode == KEY_ALT or event.physical_keycode == KEY_ALT:
			alt_gr_pressed = event.pressed
		elif event.keycode == KEY_CTRL and event.alt_pressed:
			alt_gr_pressed = event.pressed

	# 6.2. Ratón con botón derecho: yaw gira el cuerpo, pitch la órbita.
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		# Yaw: gira el cuerpo AL INSTANTE (por eso se ve girar al avatar).
		# La cámara lo sigue con retardo en _physics_process.
		rotate_y(-event.relative.x * mouse_sensitivity)
		# Pitch: solo la órbita de la cámara, con límite.
		_cam_pitch = clampf(
			_cam_pitch - event.relative.y * mouse_sensitivity,
			-deg_to_rad(camera_pitch_limit),
			deg_to_rad(camera_pitch_limit)
		)


## Clic izquierdo: selecciona el avatar si el rayo de cámara lo alcanza.
## Un clic en cualquier otro sitio lo deselecciona.
func _unhandled_input(event: InputEvent) -> void:
	if es_clon_remoto or get_meta("construccion_activa", false):
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
func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		control_avatar = false
		alt_gr_pressed = false
		velocity.x = 0.0
		velocity.z = 0.0
		for accion in ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]:
			Input.action_release(accion)
#endregion


#region 7. FÍSICA Y MOVIMIENTO
func _physics_process(delta: float) -> void:
	if es_clon_remoto:
		return
	# 7.1. Gravedad.
	if not is_on_floor():
		velocity += get_gravity() * delta

	# 7.2. Selección diferida: el raycast se resuelve en el paso de física.
	if _clic_pendiente != Vector2.INF:
		control_avatar = _clic_sobre_avatar(_clic_pendiente)
		_clic_pendiente = Vector2.INF

	# 7.3. Salto. Sin clic previo sobre el avatar no hay control.
	if control_avatar and Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = jump_velocity
		current_animation = AnimationState.JUMP

	# 7.4. Dirección de movimiento (solo si el avatar está seleccionado).
	var input_dir := Vector2.ZERO
	if control_avatar:
		input_dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	# El modelo hm1 mira hacia +Z (al contrario que el -Z de Godot):
	# se gira la entrada 180° para que W avance hacia donde mira la cara
	# y A/D queden en su izquierda/derecha real.
	var direction := (transform.basis * Vector3(-input_dir.x, 0.0, -input_dir.y)).normalized()
	var moving := direction.length_squared() > 0.001
	# En Windows, Alt Gr se reporta como Alt derecho + Ctrl.
	# KEY_ALT permite detectarlo aunque el teclado use una distribución española.
	var sprinting := alt_gr_pressed or Input.is_key_pressed(KEY_ALT) or Input.is_key_pressed(KEY_AT)

	# 7.5. Velocidad y selección de animación.
	if moving:
		var selected_speed := run_speed if sprinting else speed
		velocity.x = direction.x * selected_speed
		velocity.z = direction.z * selected_speed

		if abs(input_dir.x) > 0.1 and abs(input_dir.y) < 0.6:
			current_animation = AnimationState.STRAFE_LEFT if input_dir.x < 0.0 else AnimationState.STRAFE_RIGHT
		elif input_dir.y > 0.1:
			# En Input.get_vector(), y positivo corresponde a "hacia atrás".
			# Esta rama usa la animación Correr_htr del AnimationTree.
			current_animation = AnimationState.RUN_HTR
		elif sprinting:
			# Hacia delante + Alt Gr usa CorrerOF.
			current_animation = AnimationState.RUN
		else:
			current_animation = AnimationState.WALK
	else:
		velocity.x = move_toward(velocity.x, 0.0, run_speed * 8.0 * delta)
		velocity.z = move_toward(velocity.z, 0.0, run_speed * 8.0 * delta)
		if is_on_floor():
			current_animation = AnimationState.IDLE

	# 7.6. Estado en aire: Saltar al subir, Falling_IdleOF al caer.
	if not is_on_floor():
		current_animation = AnimationState.JUMP if velocity.y >= 0.0 else AnimationState.AIR

	# 7.7. Aplicar animación, mover y seguir con la cámara.
	_update_animation_tree(delta)
	move_and_slide()
	_update_camera_follow(delta)
#endregion


#region 8. CÁMARA ORBITAL CON RETARDO
func _update_camera_follow(delta: float) -> void:
	# La cámara persigue el punto detrás del avatar con suavizado:
	# al girar se VE al avatar rotar y la cámara termina a su espalda.
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


## Recoloca la cámara detrás al instante (tras teleporte o spawn).
## La usan TeleportManager y ChunkManager tras mover al jugador.
func snap_camera() -> void:
	_cam_yaw = rotation.y + PI
	_update_camera_follow(1.0)


## Fija la animación del clon remoto (0=idle, 1=andar, 2=correr, 3=aire).
## La llama PlayerSync cada frame con su delta.
func fija_estado_remoto(estado: int, delta: float) -> void:
	match estado:
		1:
			current_animation = AnimationState.WALK
		2:
			current_animation = AnimationState.RUN
		3:
			current_animation = AnimationState.AIR
		_:
			current_animation = AnimationState.IDLE
	_update_animation_tree(delta)
#endregion


#region 9. ÁRBOL DE ANIMACIÓN
func _update_animation_tree(delta: float) -> void:
	if animation_tree == null:
		return

	var targets := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

	# Activa todas las ramas anteriores y luego la rama elegida.
	# Nota: AVMJ/AVH tienen 5 parámetros de blend (índices 0..4); hm1 tiene 7.
	# Los estados JUMP, AIR, STRAFE_* usan índices 3-6 que no existen en AVMJ/AVH.
	# En esos avatares el estado caída/salto se mapea al idle (índice 0 = 0).
	match current_animation:
		AnimationState.IDLE:
			pass
		AnimationState.WALK:
			targets[0] = 1.0
		AnimationState.RUN:
			targets[0] = 1.0
			targets[1] = 1.0
		AnimationState.RUN_HTR:
			targets[0] = 1.0
			targets[1] = 1.0
			targets[2] = 1.0
		AnimationState.JUMP:
			targets[0] = 1.0
			targets[1] = 1.0
			targets[2] = 1.0
			targets[3] = 1.0
		AnimationState.AIR:
			targets[0] = 1.0
			targets[1] = 1.0
			targets[2] = 1.0
			targets[3] = 1.0
			targets[4] = 1.0
		AnimationState.STRAFE_LEFT:
			targets[0] = 1.0
			targets[1] = 1.0
			targets[2] = 1.0
			targets[3] = 1.0
			targets[4] = 1.0
			targets[5] = 1.0
		AnimationState.STRAFE_RIGHT:
			targets[0] = 1.0
			targets[1] = 1.0
			targets[2] = 1.0
			targets[3] = 1.0
			targets[4] = 1.0
			targets[5] = 1.0
			targets[6] = 1.0

	var weight := 1.0 if delta <= 0.0 else minf(blend_speed * delta, 1.0)
	for index in BLEND_PATHS.size():
		# Saltar parámetros que no existen en este árbol (AVMJ/AVH vs hm1)
		if animation_tree.get(BLEND_PATHS[index]) == null:
			continue
		blend_values[index] = lerpf(blend_values[index], targets[index], weight)
		animation_tree.set(BLEND_PATHS[index], blend_values[index])
#endregion
