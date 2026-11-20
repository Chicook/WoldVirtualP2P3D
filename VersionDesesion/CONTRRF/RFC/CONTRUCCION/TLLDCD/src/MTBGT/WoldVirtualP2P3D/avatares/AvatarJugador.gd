extends CharacterBody3D
## Avatar humanoide autónomo: malla, colisión, cámara y animaciones.
##
## Nace de `res://avatares/<ID>.tscn`, que sólo declara el script y el glTF.
## Todo lo demás (normalización de altura, cápsula, cámara y reproducción de
## animaciones) se construye aquí, de modo que los ocho avatares compartan el
## mismo comportamiento sin ocho escenas distintas.

signal avatar_listo(id: String)

const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

enum Estado { IDLE, WALK, RUN, AIR, STRAFE_LEFT, STRAFE_RIGHT }

@export var avatar_id: String = ""
## En el carrusel no hay física, cámara propia ni entrada.
@export var es_selector: bool = false
@export var velocidad: float = 3.0
@export var velocidad_correr: float = 5.6
@export var fuerza_salto: float = 4.6
@export var sensibilidad_raton: float = 0.0032
@export var distancia_camara: float = 2.8
@export var altura_camara: float = 1.5
@export var altura_objetivo: float = 1.8

var modelo: Node3D
var animador: AnimationPlayer
var camara: Camera3D
var current_animation: int = Estado.IDLE
var es_clon_remoto: bool = false

var _yaw: float = PI
var _pitch: float = -0.16
var _anim_actual: String = ""
var _arrastrando: bool = false


func _ready() -> void:
	if avatar_id.is_empty():
		avatar_id = str(get_meta("avatar_id", ""))
	modelo = get_node_or_null("Modelo") as Node3D
	if modelo == null:
		modelo = _buscar_primer_modelo(self)
	if modelo != null:
		_normalizar_modelo()
		_crear_colision()
	animador = _buscar_animador(self)
	if animador != null:
		_reproducir(Catalogo.ANIM_IDLE, true)
	if not es_selector and not es_clon_remoto:
		_crear_camara()
	if es_selector:
		set_physics_process(false)
	avatar_listo.emit(avatar_id)


func _buscar_primer_modelo(nodo: Node) -> Node3D:
	for h in nodo.get_children():
		if h is Node3D and h.get_child_count() > 0:
			return h as Node3D
	return null


func _buscar_animador(nodo: Node) -> AnimationPlayer:
	for h in nodo.find_children("*", "AnimationPlayer", true, false):
		return h as AnimationPlayer
	return null


## Escala el modelo a una altura humana y lo apoya en el suelo (y = 0).
func _normalizar_modelo() -> void:
	if modelo == null or modelo.has_meta("avatar_normalizado"):
		return
	var caja := _caja_local(modelo)
	if caja.size.y < 0.01:
		return
	var escala: float = altura_objetivo / caja.size.y
	modelo.scale = Vector3.ONE * escala
	var centro := caja.get_center()
	modelo.position = Vector3(-centro.x * escala, -caja.position.y * escala, -centro.z * escala)
	modelo.set_meta("avatar_normalizado", true)
	modelo.set_meta("avatar_altura", caja.size.y * escala)


## AABB combinado de todas las mallas. Se mide en el espacio de la malla
## (no en el global): algunos glTF traen transformaciones de hueso con escalas
## raras en los MeshInstance3D y arruinarían la medida.
func _caja_local(raiz: Node3D) -> AABB:
	var caja := AABB()
	var primero := true
	for nodo in raiz.find_children("*", "MeshInstance3D", true, false):
		var malla := nodo as MeshInstance3D
		if malla == null or malla.mesh == null:
			continue
		var a: AABB = malla.get_aabb()
		if a.size.y <= 0.0001:
			continue
		if primero:
			caja = a
			primero = false
		else:
			caja = caja.merge(a)
	return caja


func _crear_colision() -> void:
	if get_node_or_null("ColisionAvatar") != null:
		return
	var forma := CapsuleShape3D.new()
	forma.radius = 0.32
	forma.height = 1.7
	var colision := CollisionShape3D.new()
	colision.name = "ColisionAvatar"
	colision.shape = forma
	colision.position = Vector3(0.0, 0.85, 0.0)
	add_child(colision)


func _crear_camara() -> void:
	if camara != null and is_instance_valid(camara):
		return
	camara = Camera3D.new()
	camara.name = "CamaraAvatar"
	camara.fov = 58.0
	camara.top_level = true
	camara.current = true
	add_child(camara)
	_actualizar_camara(1.0)


func _input(event: InputEvent) -> void:
	if es_selector or es_clon_remoto:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT:
		_arrastrando = event.pressed
	elif event is InputEventMouseMotion and _arrastrando:
		rotate_y(-event.relative.x * sensibilidad_raton)
		_yaw = rotation.y + PI
		_pitch = clampf(_pitch - event.relative.y * sensibilidad_raton, -1.1, 0.55)


func _physics_process(delta: float) -> void:
	if es_selector or es_clon_remoto:
		return
	# Si el usuario está escribiendo en el chat, WASD no debe mover al avatar.
	var foco := get_viewport().gui_get_focus_owner()
	if foco is LineEdit or foco is TextEdit:
		return

	if not is_on_floor():
		velocity += get_gravity() * delta

	var entrada := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var direccion := (transform.basis * Vector3(entrada.x, 0.0, -entrada.y)).normalized()
	var moviendo := direccion.length_squared() > 0.001
	var corriendo := Input.is_key_pressed(KEY_SHIFT) or Input.is_key_pressed(KEY_ALT)

	if Input.is_physical_key_pressed(KEY_SPACE) and is_on_floor():
		velocity.y = fuerza_salto

	if moviendo:
		var rapidez := velocidad_correr if corriendo else velocidad
		velocity.x = direccion.x * rapidez
		velocity.z = direccion.z * rapidez
	else:
		velocity.x = move_toward(velocity.x, 0.0, velocidad * 10.0 * delta)
		velocity.z = move_toward(velocity.z, 0.0, velocidad * 10.0 * delta)

	move_and_slide()
	_actualizar_camara(delta)
	_actualizar_animacion(entrada, moviendo, corriendo)


func _actualizar_camara(delta: float) -> void:
	if camara == null or not is_instance_valid(camara):
		return
	var objetivo := global_position + Vector3(0.0, altura_camara, 0.0)
	var direccion := Vector3(sin(_yaw) * cos(_pitch), sin(_pitch), cos(_yaw) * cos(_pitch))
	var destino := objetivo + direccion * distancia_camara
	camara.global_position = camara.global_position.lerp(destino, clampf(delta * 7.0, 0.0, 1.0))
	camara.look_at(objetivo + Vector3(0.0, 0.15, 0.0), Vector3.UP)


func _actualizar_animacion(entrada: Vector2, moviendo: bool, corriendo: bool) -> void:
	if animador == null:
		return
	var estado := Estado.IDLE
	if not is_on_floor():
		estado = Estado.AIR
	elif moviendo:
		if absf(entrada.x) > 0.55 and absf(entrada.y) < 0.4:
			estado = Estado.STRAFE_RIGHT if entrada.x < 0.0 else Estado.STRAFE_LEFT
		elif corriendo:
			estado = Estado.RUN
		else:
			estado = Estado.WALK
	if estado == current_animation:
		return
	current_animation = estado
	match estado:
		Estado.WALK:
			_reproducir(Catalogo.ANIM_WALK, false, 1.15)
		Estado.RUN:
			_reproducir(Catalogo.ANIM_RUN, false, 1.25)
		Estado.AIR:
			_reproducir(Catalogo.ANIM_WALK, false, 0.8)
		Estado.STRAFE_LEFT:
			_reproducir(Catalogo.ANIM_LEFT, false, 1.1)
		Estado.STRAFE_RIGHT:
			_reproducir(Catalogo.ANIM_RIGHT, false, 1.1)
		_:
			_reproducir(Catalogo.ANIM_IDLE, true)


func _reproducir(nombre: String, bucle: bool = true, rapidez: float = 1.0) -> void:
	if animador == null or not animador.has_animation(nombre):
		return
	if _anim_actual == nombre and animador.is_playing():
		animador.speed_scale = rapidez
		return
	var anim := animador.get_animation(nombre)
	if anim != null:
		anim.loop_mode = Animation.LOOP_LINEAR
	animador.speed_scale = rapidez
	animador.play(nombre, 0.18)
	_anim_actual = nombre


## Coloca la cámara detrás del avatar sin transición (al entrar a la isla).
func snap_camera() -> void:
	_yaw = rotation.y + PI
	_pitch = -0.16
	_actualizar_camara(1.0)


## PlayerSync coloca y anima los clones remotos; aquí sólo se elige el clip.
func fija_estado_remoto(estado: int, _delta: float) -> void:
	current_animation = estado
	match estado:
		2:
			_reproducir(Catalogo.ANIM_RUN, false, 1.2)
		1:
			_reproducir(Catalogo.ANIM_WALK, false, 1.1)
		3:
			_reproducir(Catalogo.ANIM_IDLE, true, 0.85)
		6:
			_reproducir(Catalogo.ANIM_LEFT, false, 1.1)
		7:
			_reproducir(Catalogo.ANIM_RIGHT, false, 1.1)
		_:
			_reproducir(Catalogo.ANIM_IDLE, true)


func nombre_visible() -> String:
	return Catalogo.nombre_de(avatar_id)
