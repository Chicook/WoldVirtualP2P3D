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
	ISLAND_RISING,
	CAMERA_APPROACH,
	CAMERA_ORBIT,
	CAMERA_SETTLE,
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
	_phase = Phase.ISLAND_RISING
	var target_y : float = _island.global_position.y

	var rise_anim : Node = load("res://woldvirtual/gdscrip/IslandRiseAnimation.gd").new()
	rise_anim.name = "IslandRiseAnim"
	_island.add_child(rise_anim)
	# Conectar la señal ANTES de llamar play() para no perderla
	rise_anim.finished.connect(_on_island_arrived)
	rise_anim.play(target_y)

	print("[CinematicIntro] Fase 1: isla ascendiendo desde el lecho marino...")

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
	print("[CinematicIntro] Fase 2: isla en superficie — avatar aparece encima.")

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

	# Iniciar fase de aproximación de cámara
	_orbit_start_angle = _avatar.global_rotation.y + PI   # enfrente del avatar
	_phase   = Phase.CAMERA_APPROACH
	_elapsed = 0.0
	set_process(true)

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

		# ── FASE 2: Espalda → Enfrente ──────────────────────────────────────────
		Phase.CAMERA_APPROACH:
			var t       : float = clamp(_elapsed / approach_duration, 0.0, 1.0)
			var et      : float = _smoothstep(t)
			var back    : float = _avatar.global_rotation.y
			var front   : float = _avatar.global_rotation.y + PI
			var angle   : float = lerp_angle(back, front, et)
			_place_cam(angle, avatar_pos, look_target)

			if t >= 1.0:
				print("[CinematicIntro] Fase 3: órbita 360°.")
				_orbit_start_angle = _avatar.global_rotation.y + PI
				_phase   = Phase.CAMERA_ORBIT
				_elapsed = 0.0

		# ── FASE 3: Órbita 360° ─────────────────────────────────────────────────
		Phase.CAMERA_ORBIT:
			var t     : float = clamp(_elapsed / orbit_duration, 0.0, 1.0)
			var et    : float = _ease_in_out_quad(t)
			var angle : float = _orbit_start_angle - (et * TAU)   # TAU = 2π
			_place_cam(angle, avatar_pos, look_target)
			# FOV cinemático
			_cam.fov = lerp(_cam.fov, cinematic_fov, delta * 2.5)

			if t >= 1.0:
				print("[CinematicIntro] Fase 4: asentamiento en espalda TPV.")
				_phase   = Phase.CAMERA_SETTLE
				_elapsed = 0.0

		# ── FASE 4: Enfrente → Espalda (TPV normal) ─────────────────────────────
		Phase.CAMERA_SETTLE:
			var t     : float = clamp(_elapsed / settle_duration, 0.0, 1.0)
			var et    : float = _ease_out_cubic(t)
			var front : float = _orbit_start_angle
			var back  : float = _avatar.global_rotation.y
			var angle : float = lerp_angle(front, back, et)
			_place_cam(angle, avatar_pos, look_target)
			# Restaurar FOV normal
			_cam.fov = lerpf(_cam.fov, _normal_fov, et)

			if t >= 1.0:
				_sync_cam_ctrl()
				_finish()

# ─── Helpers ───────────────────────────────────────────────────────────────────
## Coloca la cámara en posición orbital y la apunta al avatar
func _place_cam(angle: float, avatar_pos: Vector3, look_target: Vector3) -> void:
	var cam_x = avatar_pos.x + cinematic_distance * sin(angle)
	var cam_z = avatar_pos.z + cinematic_distance * cos(angle)
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
	_phase = Phase.DONE
	set_process(false)
	if is_instance_valid(_cam):
		_cam.fov = _normal_fov
	if is_instance_valid(_cam_ctrl):
		_cam_ctrl.set_physics_process(true)
		_cam_ctrl.set_process_input(true)
	intro_completed.emit()
	print("[CinematicIntro] Secuencia completada. Control devuelto al jugador.")

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
