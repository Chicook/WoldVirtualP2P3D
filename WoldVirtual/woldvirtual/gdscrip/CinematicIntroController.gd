## CinematicIntroController.gd
## Orquesta la secuencia cinematográfica de introducción:
##
##   FASE 1 — ISLAND_RISING  (≈4.2 s)
##     La isla asciende desde el lecho marino (-160 m) hasta su posición final.
##     El avatar permanece invisible durante este período.
##
##   FASE 2 — CAMERA_APPROACH  (≈1.2 s)
##     La cámara parte desde la espalda del avatar y se desplaza suavemente
##     hasta quedar enfrente de él (avatar.rotation.y + 180°).
##
##   FASE 3 — CAMERA_ORBIT  (≈3.8 s)
##     La cámara orbita 360° completos alrededor del avatar con FOV cinemático.
##
##   FASE 4 — CAMERA_SETTLE  (≈1.5 s)
##     La cámara regresa suavemente a la espalda del avatar (TPV normal)
##     y se sincronizan los ángulos internos del CameraController para que
##     el control manual sea inmediatamente fluido.
##
## Uso (desde ChunkManager):
##   var ctrl = CinematicIntroController.new()
##   add_child(ctrl)
##   ctrl.begin(island_node, avatar_node, cam_controller)
extends Node
class_name CinematicIntroController

# ─── Señal de fin ──────────────────────────────────────────────────────────────
signal intro_completed

# ─── Fases ─────────────────────────────────────────────────────────────────────
enum Phase {
	IDLE,
	ISLAND_RISING_AND_ORBIT,
	AVATAR_APPEAR_AND_TURN,
	CAMERA_ZOOM_AND_SETTLE,
	DONE
}

# ─── Parámetros de cámara cinemática ──────────────────────────────────────────
## Distancia radial al avatar durante la cinemática
@export var cinematic_distance  : float = 4.5
## Altura de la cámara (metros sobre la base del avatar)
@export var cinematic_height    : float = 1.8
## Altura del punto de mira (cabeza del avatar)
@export var look_at_height      : float = 1.3
## Duración del arco de aproximación (espalda → enfrente), segundos
@export var approach_duration   : float = 1.2
## Duración de la órbita 360°, segundos
@export var orbit_duration      : float = 3.8
## Duración del asentamiento final (enfrente → espalda), segundos
@export var settle_duration     : float = 1.5
## Duración total del ascenso de la isla en segundos (copiado de IslandRiseAnimation.gd)
const rise_duration    : float =  4.2
## FOV durante la órbita (más tele = más dramático)
@export var cinematic_fov       : float = 55.0

# ─── Estado interno ────────────────────────────────────────────────────────────
var _phase              : Phase    = Phase.IDLE
var _elapsed            : float    = 0.0
var _island             : Node3D   = null
var _avatar             : Node3D   = null
var _cam_ctrl           : Node     = null   # CameraController
var _cam                : Camera3D = null
var _normal_fov         : float    = 75.0
## Ángulo (radianes) que marcará el inicio del arco de órbita
var _orbit_start_angle  : float    = 0.0
## Posición XZ del avatar al momento de spawnar (para recolocarle encima de la isla)
var _avatar_spawn_pos   : Vector3  = Vector3.ZERO

# ─── API Pública ───────────────────────────────────────────────────────────────
## Inicia la secuencia completa.
## Llama a begin() una sola vez; llamadas posteriores son ignoradas.
func begin(island_node: Node3D, avatar_node: Node3D, cam_ctrl_node: Node) -> void:
	if _phase != Phase.IDLE:
		return

	_island   = island_node
	_avatar   = avatar_node
	_cam_ctrl = cam_ctrl_node

	# Localizar la Camera3D hija del CameraController
	_cam = _find_camera(_cam_ctrl)
	if !is_instance_valid(_cam):
		push_warning("CinematicIntroController: Camera3D no encontrada en CameraController.")
		_finish()
		return

	_normal_fov = _cam.fov

	# Calcular el ángulo inicial de la cámara alrededor de la isla
	var cam_to_island_vec = _cam.global_position - _island.global_position
	_orbit_start_angle = atan2(cam_to_island_vec.x, cam_to_island_vec.z)

	# ── Congelar avatar durante el ascenso de la isla ──────────────────────────
	# CRÍTICO: sin esto la gravedad hunde al CharacterBody3D bajo la isla.
	if is_instance_valid(_avatar):
		_avatar_spawn_pos = _avatar.global_position        # Guardar posición XZ
		_avatar.visible   = false
		# Desactivar física Y input del avatar para que no caiga
		_avatar.set_physics_process(false)
		_avatar.set_process_input(false)
		if _avatar is CharacterBody3D:
			(_avatar as CharacterBody3D).velocity = Vector3.ZERO
		# Mover al avatar a una posición segura fuera de cámara (invisible)
		# pero dentro de la isla para que las físicas no lo alteren
		_avatar.global_position = _avatar_spawn_pos

	# ── Suspender CameraController ─────────────────────────────────────────────
	_cam_ctrl.set_physics_process(false)
	_cam_ctrl.set_process_input(false)

	# ── Fase 1: lanzar animación de ascenso de la isla ─────────────────────────
	_phase = Phase.ISLAND_RISING_AND_ORBIT
	var target_y : float = _island.global_position.y

	var rise_anim : Node = load("res://woldvirtual/gdscrip/IslandRiseAnimation.gd").new()
	rise_anim.name = "IslandRiseAnim"
	_island.add_child(rise_anim)
	# Conectar la señal ANTES de llamar play() para no perderla
	rise_anim.finished.connect(_on_island_arrived)
	rise_anim.play(target_y)
	
	# Iniciar el proceso para la órbita de la cámara
	set_process(true)

	print("[CinematicIntro] Fase 1: isla ascendiendo y cámara orbitando...")

## Salta la cinemática y entrega el control al CameraController inmediatamente.
func skip() -> void:
	if is_instance_valid(_avatar):
		_avatar.visible = true
		_avatar.set_physics_process(true)
		_avatar.set_process_input(true)
		if _avatar is CharacterBody3D:
			(_avatar as CharacterBody3D).velocity = Vector3.ZERO
	_finish()

# ─── Callbacks de fases ────────────────────────────────────────────────────────
func _on_island_arrived() -> void:
	print("[CinematicIntro] Fase 2: isla en superficie — avatar aparece y gira.")

	if !is_instance_valid(_avatar):
		_finish()
		return

	# ── Reposicionar el avatar SOBRE la isla ───────────────────────────────────
	# La isla ya está en su Y final; colocamos al avatar en esa misma XZ
	# pero a la Y de spawn original (que es la altura correcta de la superficie).
	var surface_y : float = _avatar_spawn_pos.y
	_avatar.global_position = Vector3(
		_avatar_spawn_pos.x,
		surface_y,
		_avatar_spawn_pos.z
	)
	# Reactivar física y borrar velocidad acumulada antes de hacerlo visible
	if _avatar is CharacterBody3D:
		(_avatar as CharacterBody3D).velocity = Vector3.ZERO
	_avatar.set_physics_process(true)
	_avatar.set_process_input(true)
	_avatar.visible = true
	
	# El avatar gira suavemente para mostrar su espalda a la cámara
	var initial_avatar_rot_y = _avatar.global_rotation.y
	var target_avatar_rot_y = initial_avatar_rot_y + PI

	var tween = get_tree().create_tween()
	tween.tween_property(_avatar, "global_rotation:y", target_avatar_rot_y, approach_duration)
	tween.set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	tween.finished.connect(_on_avatar_turn_finished)

	# Iniciar fase de aproximación de cámara
	# _orbit_start_angle se calcula en base a la rotación FINAL del avatar
	_orbit_start_angle = target_avatar_rot_y + PI   # enfrente del avatar (después de girar)
	_phase   = Phase.AVATAR_APPEAR_AND_TURN
	_elapsed = 0.0
	set_process(true)

func _on_avatar_turn_finished() -> void:
	print("[CinematicIntro] Fase 3: cámara se acerca y asienta.")
	_phase   = Phase.CAMERA_ZOOM_AND_SETTLE
	_elapsed = 0.0

# ─── Loop de fases de cámara ───────────────────────────────────────────────────
func _ready() -> void:
	set_process(false)

func _process(delta: float) -> void:
	if !is_instance_valid(_avatar) or !is_instance_valid(_cam):
		_finish()
		return

	_elapsed += delta
	var avatar_pos  : Vector3 = _avatar.global_position
	var look_target : Vector3 = avatar_pos + Vector3(0.0, look_at_height, 0.0)

	match _phase:

		# ── FASE 1: Isla ascendiendo y cámara orbitando ──────────────────────────
		Phase.ISLAND_RISING_AND_ORBIT:
			var t     : float = clamp(_elapsed / rise_duration, 0.0, 1.0)
			var et    : float = _ease_in_out_quad(t)
			var angle : float = _orbit_start_angle - (et * TAU)   # TAU = 2π
			_place_cam(angle, avatar_pos, look_target)
			_cam.fov = lerp(_cam.fov, cinematic_fov, delta * 2.5)
			# La transición de fase se maneja en _on_island_arrived()

		# ── FASE 2: Avatar aparece y gira para mostrar la espalda ────────────────
		Phase.AVATAR_APPEAR_AND_TURN:
			# La rotación del avatar se maneja con un Tween en _on_island_arrived()
			# Aquí solo actualizamos la cámara para seguir al avatar
			var back  : float = _avatar.global_rotation.y
			_place_cam(back, avatar_pos, look_target)

			# La transición de fase se maneja cuando el tween del avatar termina
			# (o si el tiempo de approach_duration ha pasado, como fallback)
			# if _elapsed >= approach_duration:
			# 	print("[CinematicIntro] Fase 3: cámara se acerca y asienta.")
			# 	_phase   = Phase.CAMERA_ZOOM_AND_SETTLE
			# 	_elapsed = 0.0

		# ── FASE 3: Cámara se acerca y asienta en TPV ───────────────────────────
		Phase.CAMERA_ZOOM_AND_SETTLE:
			var t     : float = clamp(_elapsed / settle_duration, 0.0, 1.0)
			var et    : float = _smoothstep(t)
			var back  : float = _avatar.global_rotation.y
			_place_cam(back, avatar_pos, look_target, et) # et controla la distancia
			_cam.fov = lerp(_cam.fov, _normal_fov, delta * 2.5)

			if t >= 1.0:
				print("[CinematicIntro] Fase 4: cinemática completada, control al jugador.")
				_sync_cam_ctrl()
				_finish()

# ─── Helpers ───────────────────────────────────────────────────────────────────
## Coloca la cámara en posición orbital y la apunta al avatar
func _place_cam(angle: float, avatar_pos: Vector3, look_target: Vector3, progress: float = 1.0) -> void:
	var current_distance = lerp(cinematic_distance * 2.0, cinematic_distance, progress) # Zoom in from further away
	var cam_x = avatar_pos.x + current_distance * sin(angle)
	var cam_z = avatar_pos.z + current_distance * cos(angle)
	_cam.global_position = Vector3(cam_x, avatar_pos.y + cinematic_height, cam_z)
	_cam.look_at(look_target)

## Sincroniza los ángulos internos del CameraController para evitar salto
func _sync_cam_ctrl() -> void:
	if !is_instance_valid(_cam_ctrl): return
	# Escribir _rot_y y _rot_x directamente (son vars públicas en CameraController)
	if "_rot_y" in _cam_ctrl:
		_cam_ctrl._rot_y = _avatar.global_rotation.y
	if "_rot_x" in _cam_ctrl:
		_cam_ctrl._rot_x = -0.2   # inclinación por defecto de TPV

## Busca la Camera3D hija del CameraController
func _find_camera(ctrl: Node) -> Camera3D:
	for ch in ctrl.get_children():
		if ch is Camera3D:
			return ch
	return null

func _finish() -> void:
	if _phase == Phase.DONE: return

	# Asegurarse de que el avatar esté visible y con físicas/input activados
	if is_instance_valid(_avatar):
		_avatar.visible = true
		_avatar.set_physics_process(true)
		_avatar.set_process_input(true)
		if _avatar is CharacterBody3D:
			(_avatar as CharacterBody3D).velocity = Vector3.ZERO

	# Reactivar CameraController
	if is_instance_valid(_cam_ctrl):
		_cam_ctrl.set_physics_process(true)
		_cam_ctrl.set_process_input(true)
		# Sincronizar ángulos para evitar saltos de cámara
		if _cam_ctrl.has_method("sync_angles_to_camera"):
			_cam_ctrl.sync_angles_to_camera(_cam)

	_cam.fov = _normal_fov # Restaurar FOV normal

	_phase = Phase.DONE
	intro_completed.emit()
	queue_free()

# ─── Curvas de easing ──────────────────────────────────────────────────────────
static func _smoothstep(t: float) -> float:
	return t * t * (3.0 - 2.0 * t)

static func _ease_out_cubic(t: float) -> float:
	var u := 1.0 - t
	return 1.0 - (u * u * u)

static func _ease_in_out_quad(t: float) -> float:
	if t < 0.5:
		return 2.0 * t * t
	else:
		return 1.0 - pow(-2.0 * t + 2.0, 2.0) * 0.5
