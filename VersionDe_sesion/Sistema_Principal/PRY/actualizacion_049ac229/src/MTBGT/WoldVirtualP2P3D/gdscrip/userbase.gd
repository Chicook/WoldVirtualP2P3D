extends CharacterBody3D

const SPEED = 5.0
const JUMP_VELOCITY = 4.5
var mouse_sensitivity := 0.003

@onready var camera = $Camera3D

func _ready() -> void:
	# La cámara es hija del avatar: así siempre lo sigue sin cálculos extra.
	# Solo aseguramos una inclinación inicial limpia.
	camera.rotation = Vector3(0.0, 0.0, 0.0)

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		# 1. Giro horizontal (yaw): rota TODO el cuerpo, incluido el avatar visible.
		# Como el movimiento usa transform.basis, al pulsar W/A/S/D
		# el personaje ya se mueve hacia donde mira.
		rotate_y(-event.relative.x * mouse_sensitivity)
		# 2. Inclinación vertical (pitch): solo la cámara, sin tocar el cuerpo.
		# Se asigna en vez de usar rotate_x() para no acumular inclinación
		# lateral (roll) al girar muchas veces.
		camera.rotation.x = clampf(
			camera.rotation.x - event.relative.y * mouse_sensitivity,
			-deg_to_rad(80),
			deg_to_rad(80)
		)
		# 3. Seguridad: nunca dejar roll/z en la cámara hija.
		camera.rotation.y = 0.0
		camera.rotation.z = 0.0

func _physics_process(delta: float) -> void:
	# Add the gravity.
	if not is_on_floor():
		velocity += get_gravity() * delta

	# Handle jump.
	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = JUMP_VELOCITY

	# Get the input direction and handle the movement/deceleration.
	# As good practice, you should replace UI actions with custom gameplay actions.
	var input_dir := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var direction := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()
	if direction:
		velocity.x = direction.x * SPEED
		velocity.z = direction.z * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0, SPEED)
		velocity.z = move_toward(velocity.z, 0, SPEED)

	move_and_slide()
