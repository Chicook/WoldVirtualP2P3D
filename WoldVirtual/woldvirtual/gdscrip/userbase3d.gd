extends CharacterBody3D

const WALK_SPEED = 6.0
const RUN_SPEED = 12.0
const JUMP = 5.0
var sensitivity: float = 0.008
var es_local: bool = false

# === Indicador de voz estilo OpenSimulator ===
var _voice_label: Label3D = null
var _voice_tween: Tween = null

# Estados de teclas manuales para evitar problemas de foco de OS en ventanas embebidas
var _key_up: bool = false
var _key_down: bool = false
var _key_left: bool = false
var _key_right: bool = false
var _key_ctrl: bool = false
var _key_0: bool = false
var _key_space: bool = false

var _was_zero_pressed: bool = false
var _was_space_pressed: bool = false

# Cámara interna eliminada para evitar conflictos con el visor global
func _ready() -> void:
	# Movimiento y físicas únicamente
	if !es_local:
		set_process_input(false)
		set_physics_process(false) # Ahorro masivo de CPU en remotos

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion && Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		# Rotación únicamente en el eje Y (Avatar)
		rotate_y(-event.relative.x * sensitivity)

	if event is InputEventKey:
		# Actualizar el estado de nuestras teclas manuales
		match event.keycode:
			KEY_UP, KEY_W:
				_key_up = event.pressed
			KEY_DOWN, KEY_S:
				_key_down = event.pressed
			KEY_LEFT, KEY_A:
				_key_left = event.pressed
			KEY_RIGHT, KEY_D:
				_key_right = event.pressed
			KEY_CTRL:
				_key_ctrl = event.pressed
			KEY_0, KEY_KP_0:
				_key_0 = event.pressed
			KEY_SPACE:
				_key_space = event.pressed

func _physics_process(delta: float) -> void:
	if !is_on_floor():
		velocity += get_gravity() * delta

	# Comprobación de salto con Espacio o Cero "0"
	var zero_just_pressed = _key_0 and not _was_zero_pressed
	_was_zero_pressed = _key_0
	
	var space_just_pressed = _key_space and not _was_space_pressed
	_was_space_pressed = _key_space

	if (space_just_pressed or zero_just_pressed) and is_on_floor():
		velocity.y = JUMP

	# Movimiento relativo al Avatar (transform.basis)
	var current_speed = WALK_SPEED
	var dir_input = Vector2.ZERO

	# Si se mantiene pulsada la tecla Control, corre hacia adelante (puede combinar con strafe)
	if _key_ctrl:
		current_speed = RUN_SPEED
		var left_right = 0.0
		if _key_left:
			left_right -= 1.0
		if _key_right:
			left_right += 1.0
		dir_input = Vector2(left_right, -1.0).normalized()
	else:
		# Movimiento estándar con flechas o WASD
		var forward_back = 0.0
		var left_right = 0.0
		
		if _key_up:
			forward_back -= 1.0
		if _key_down:
			forward_back += 1.0
		if _key_left:
			left_right -= 1.0
		if _key_right:
			left_right += 1.0
			
		if forward_back != 0.0 or left_right != 0.0:
			dir_input = Vector2(left_right, forward_back).normalized()

	var dir := (transform.basis * Vector3(dir_input.x, 0, dir_input.y)).normalized()
	
	if dir:
		velocity.x = dir.x * current_speed
		velocity.z = dir.z * current_speed
	else:
		velocity.x = move_toward(velocity.x, 0, current_speed)
		velocity.z = move_toward(velocity.z, 0, current_speed)

	move_and_slide()
	
	# Animación básica para evitar el T-Pose (Comentado temporalmente por petición del usuario)
	# if anim:
	# 	if velocity.length() > 0.1:
	# 		if anim.has_animation("walk"): anim.play("walk")
	# 		elif anim.has_animation("run"): anim.play("run")
	# 		elif anim.get_animation_list().size() > 0: anim.play(anim.get_animation_list()[0])
	# 	else:
	# 		if anim.has_animation("idle"): anim.play("idle")
	# 		elif anim.get_animation_list().size() > 0: anim.play(anim.get_animation_list()[0])

func mostrar_mensaje_3d(texto: String):
	# Si ya existe un mensaje anterior, lo quitamos para que no se solape
	var old_label = get_node_or_null("FloatingChatLabel")
	if is_instance_valid(old_label):
		old_label.queue_free()

	var label = Label3D.new()
	label.name = "FloatingChatLabel"
	label.text = texto
	label.position = Vector3(0, 2.2, 0) # Posición flotando sobre la cabeza del avatar
	label.billboard = 1 # Billboard enabled: siempre mirando de frente a la cámara
	label.font_size = 30
	label.outline_size = 10
	label.modulate = Color(0.4, 0.9, 1.0, 1.0) # Hermoso cian cyberpunk brillante
	label.outline_modulate = Color.BLACK
	add_child(label)

	# Animación de desvanecimiento estilo Second Life / OpenSimulator
	var tween = create_tween()
	# Esperar 5.0 segundos flotando estático
	tween.tween_interval(5.0)
	# Desvanecer la opacidad del texto y del contorno en 1.5 segundos
	tween.tween_property(label, "modulate:a", 0.0, 1.5)
	tween.parallel().tween_property(label, "outline_modulate:a", 0.0, 1.5)
	# Eliminar el nodo al terminar
	tween.tween_callback(label.queue_free)

# ────────────────────────────────────────────────
# VOICE CHAT — Indicador de voz flotante (estilo OpenSimulator)
# ────────────────────────────────────────────────
func mostrar_indicador_voz(speaking: bool) -> void:
	if speaking:
		_crear_indicador_voz()
	else:
		_ocultar_indicador_voz()

func _crear_indicador_voz() -> void:
	# Si ya existe no lo recreamos
	if is_instance_valid(_voice_label):
		return
	
	_voice_label = Label3D.new()
	_voice_label.name = "VoiceIndicator"
	# Icono de onda de radio — idéntico al de OpenSimulator
	_voice_label.text = "((·))"
	_voice_label.position = Vector3(0, 2.65, 0)  # Justo sobre la cabeza
	_voice_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_voice_label.font_size = 30
	_voice_label.outline_size = 8
	_voice_label.modulate = Color(0.2, 1.0, 0.45, 1.0)   # Verde vibrante
	_voice_label.outline_modulate = Color(0.0, 0.0, 0.0, 1.0)
	add_child(_voice_label)
	
	# Animación de pulso de escala (anillos de radio expandándose)
	_voice_tween = create_tween().set_loops()
	_voice_tween.tween_property(_voice_label, "scale",
								Vector3(1.2, 1.2, 1.2), 0.35)\
					.set_ease(Tween.EASE_OUT)\
					.set_trans(Tween.TRANS_SINE)
	_voice_tween.tween_property(_voice_label, "scale",
								Vector3(1.0, 1.0, 1.0), 0.35)\
					.set_ease(Tween.EASE_IN)\
					.set_trans(Tween.TRANS_SINE)

func _ocultar_indicador_voz() -> void:
	if _voice_tween:
		_voice_tween.kill()
		_voice_tween = null
	if is_instance_valid(_voice_label):
		# Pequeño desvanecimiento antes de eliminar
		var fade = create_tween()
		fade.tween_property(_voice_label, "modulate:a", 0.0, 0.3)
		fade.tween_callback(_voice_label.queue_free)
		_voice_label = null