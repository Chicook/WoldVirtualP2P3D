## CinematicIntroController.gd
## Orquesta la secuencia cinematográfica de introducción:
##
##   FASE 1 — ISLAND_RISING_360 (≈4.2 s)
##     La isla asciende desde el lecho marino (-160 m) hasta su posición final.
##     Mientras sube, la cámara hace un GIRO COMPLETO (360°) alrededor de la isla,
##     para mostrar todo el entorno desde su perspectiva actual.
##     El avatar permanece invisible durante este período.
##
##   FASE 2 — CAMERA_180_AROUND_AVATAR (≈1.8 s)
##     La cámara se posiciona ENFRENTE DEL AVATAR y gira 180° completos
##     hasta quedarse mirando directamente a su ESPALDA (posición TPV normal).
##
##   FASE 3 — DONE
##     Se entrega el control al jugador y se activa el avatar.
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
	ISLAND_RISING_360,
	CAMERA_180_AROUND_AVATAR,
	DONE
}

# ─── Parámetros de cámara cinemática ──────────────────────────────────────────
## Distancia radial a la isla durante la fase 1 (360°)
@export var island_cinematic_distance : float = 50.0
## Altura de la cámara sobre la isla (fase 1)
@export var island_cinematic_height   : float = 30.0
## Distancia radial al avatar durante la fase 2 (180°)
@export var avatar_cinematic_distance : float = 4.5
## Altura de la cámara sobre el avatar (fase 2)
@export var avatar_cinematic_height   : float = 1.8
## Altura del punto de mira para el avatar (cabeza)
@export var look_at_height            : float = 1.3
## Duración total del ascenso + 360°, segundos
@export var island_phase_duration     : float = 4.2
## Duración del giro de 180° alrededor del avatar, segundos
@export var avatar_phase_duration     : float = 1.8
## FOV cinemático para la isla
@export var island_fov                : float = 60.0
## FOV normal para el jugador
@export var normal_fov                : float = 75.0

# ─── Estado interno ────────────────────────────────────────────────────────────
var _phase              : Phase    = Phase.IDLE
var _elapsed            : float    = 0.0
var _island             : Node3D   = null
var _avatar             : Node3D   = null
var _cam_ctrl           : Node     = null   # CameraController
var _cam                : Camera3D = null
## Ángulo (radianes) inicial para la órbita de la isla
var _island_orbit_start : float    = 0.0
## Ángulo (radianes) inicial para la órbita del avatar
var _avatar_orbit_start : float    = 0.0
## Posición XZ del avatar al momento de spawnar
var _avatar_spawn_pos   : Vector3  = Vector3.ZERO
## Posición XZ original de la isla (para órbita)
var _island_center      : Vector3  = Vector3.ZERO

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

	# Guardar posiciones centrales
	_island_center = _island.global_position
	if is_instance_valid(_avatar):
		_avatar_spawn_pos = _avatar.global_position

	# ── Congelar avatar durante el ascenso de la isla ──────────────────────────
	if is_instance_valid(_avatar):
		_avatar.visible   = false
		_avatar.set_physics_process(false)
		_avatar.set_process_input(false)
		if _avatar is CharacterBody3D:
			(_avatar as CharacterBody3D).velocity = Vector3.ZERO
		_avatar.global_position = _avatar_spawn_pos

	# ── Suspender CameraController ─────────────────────────────────────────────
	_cam_ctrl.set_physics_process(false)
	_cam_ctrl.set_process_input(false)

	# ── Fase 1: lanzar animación de ascenso de la isla y empezar proceso de cámara ─────────────────────────
	_phase = Phase.ISLAND_RISING_360
	_elapsed = 0.0
	_island_orbit_start = 0.0

	var rise_anim : Node = load("res://woldvirtual/gdscrip/IslandRiseAnimation.gd").new()
	rise_anim.name = "IslandRiseAnim"
	_island.add_child(rise_anim)
	# Conectar la señal ANTES de llamar play() para no perderla
	rise_anim.finished.connect(_on_island_arrived)
	rise_anim.play(_island_center.y)

	# Empezar el proceso para controlar la cámara
	set_process(true)
	print("[CinematicIntro] Fase 1: isla emergiendo + cámara girando 360°...")

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
	print("[CinematicIntro] Fase 2: isla en superficie — girando 180° alrededor del avatar.")

	if !is_instance_valid(_avatar):
		_finish()
		return

	# ── Reposicionar el avatar SOBRE la isla ───────────────────────────────────
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

	# Iniciar fase de giro 180° alrededor del avatar
	_avatar_orbit_start = _avatar.global_rotation.y + PI   # empezar ENFRENTE del avatar
	_phase   = Phase.CAMERA_180_AROUND_AVATAR
	_elapsed = 0.0

# ─── Loop de fases de cámara ───────────────────────────────────────────────────
func _ready() -> void:
	set_process(false)

func _process(delta: float) -> void:
	if !is_instance_valid(_island):
		_finish()
		return

	_elapsed += delta

	match _phase:

		# ── FASE 1: Isla emergiendo + cámara 360° alrededor de ella ─────────────────────
		Phase.ISLAND_RISING_360:
			var t       : float = clamp(_elapsed / island_phase_duration, 0.0, 1.0)
			var et      : float = _ease_in_out_quad(t)
			var angle   : float = et * TAU   # GIRO COMPLETO (360°)

			# Posición de la cámara: órbita alrededor del centro de la isla, con altura constante
			var island_current_pos : Vector3 = _island.global_position
			var cam_pos : Vector3 = island_current_pos + Vector3(
				sin(angle) * island_cinematic_distance,
				island_cinematic_height,
				cos(angle) * island_cinematic_distance
			)
			_cam.global_position = cam_pos
			# Mirar al centro de la isla
			_cam.look_at(island_current_pos + Vector3(0, 5, 0))
			# FOV cinemático
			_cam.fov = lerp(_cam.fov, island_fov, delta * 3.0)

			# (Nota: la animación de la isla se gestiona separadamente por IslandRiseAnimation)

		# ── FASE 2: Giro 180° alrededor del avatar ─────────────────────────────────────────
		Phase.CAMERA_180_AROUND_AVATAR:
			if !is_instance_valid(_avatar):
				_finish()
				return

			var t       : float = clamp(_elapsed / avatar_phase_duration, 0.0, 1.0)
			var et      : float = _ease_out_cubic(t)
			# Ángulo: empezar enfrente del avatar (PI) y terminar en su espalda (0)
			var start_angle : float = _avatar_orbit_start
			var end_angle   : float = _avatar.global_rotation.y
			var angle       : float = lerp_angle(start_angle, end_angle, et)

			_place_cam_around_avatar(angle)
			# Restaurar FOV normal
			_cam.fov = lerp(_cam.fov, normal_fov, delta * 4.0)

			if t >= 1.0:
				_sync_cam_ctrl()
				_finish()

# ─── Helpers ───────────────────────────────────────────────────────────────────
## Coloca la cámara en posición orbital alrededor del avatar y la apunta a él
func _place_cam_around_avatar(angle: float) -> void:
	if !is_instance_valid(_avatar):
		return

	var avatar_pos    : Vector3 = _avatar.global_position
	var look_target   : Vector3 = avatar_pos + Vector3(0.0, look_at_height, 0.0)

	_cam.global_position = avatar_pos + Vector3(
		sin(angle) * avatar_cinematic_distance,
		avatar_cinematic_height,
		cos(angle) * avatar_cinematic_distance
	)
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
	_phase = Phase.DONE
	set_process(false)
	if is_instance_valid(_cam):
		_cam.fov = normal_fov
	if is_instance_valid(_cam_ctrl):
		_cam_ctrl.set_physics_process(true)
		_cam_ctrl.set_process_input(true)
	intro_completed.emit()
	print("[CinematicIntro] Secuencia completada. Control devuelto al jugador.")

# ─── Curvas de easing ──────────────────────────────────────────────────────────
static func _ease_out_cubic(t: float) -> float:
	var u := 1.0 - t
	return 1.0 - (u * u * u)

static func _ease_in_out_quad(t: float) -> float:
	if t < 0.5:
		return 2.0 * t * t
	else:
		return 1.0 - pow(-2.0 * t + 2.0, 2.0) * 0.5
