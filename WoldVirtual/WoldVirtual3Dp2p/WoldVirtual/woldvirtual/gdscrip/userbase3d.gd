extends CharacterBody3D

const SPEED = 8.0
const JUMP = 5.0
var sensitivity: float = 0.008
var es_local: bool = false

# Cámara interna eliminada para evitar conflictos con el visor global
# @onready var anim: AnimationPlayer = find_child("AnimationPlayer")
func _ready() -> void:
	# Movimiento y físicas únicamente
	if !es_local:
		set_process_unhandled_input(false)
		set_physics_process(false) # Ahorro masivo de CPU en remotos

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion && Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		# Rotación únicamente en el eje Y (Avatar)
		rotate_y(-event.relative.x * sensitivity)

func _physics_process(delta: float) -> void:
	if !is_on_floor():
		velocity += get_gravity() * delta

	if Input.is_action_just_pressed("ui_accept") && is_on_floor():
		velocity.y = JUMP

	# Movimiento relativo al Avatar (transform.basis)
	var dir_input := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var dir := (transform.basis * Vector3(dir_input.x, 0, dir_input.y)).normalized()
	
	if dir:
		velocity.x = dir.x * SPEED
		velocity.z = dir.z * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0, SPEED)
		velocity.z = move_toward(velocity.z, 0, SPEED)

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