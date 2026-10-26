extends CharacterBody3D

const SPEED = 5.0
const JUMP_VELOCITY = 4.5
var mouse_sensitivity := 0.003
## La cápsula no responde a las flechas hasta hacer clic en la vista 3D.
var control_avatar := false

@onready var camera = $Camera3D

func _ready() -> void:
	# La cámara es hija del avatar: así siempre lo sigue sin cálculos extra.
	# Solo aseguramos una inclinación inicial limpia.
	camera.rotation = Vector3(0.0, 0.0, 0.0)

## En primera persona no se ve el cuerpo: cualquier clic izquierdo en la
## vista 3D toma el control para mover la cápsula con las flechas.
func _unhandled_input(event: InputEvent) -> void:
	if get_meta("construccion_activa", false):
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		control_avatar = true


## Al perder el foco (clic en el chat del visor) se suelta el avatar y las
## teclas para que ninguna flecha retenida lo mueva.
func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		control_avatar = false
		velocity.x = 0.0
		velocity.z = 0.0
		for accion in ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]:
			Input.action_release(accion)


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

	# Handle jump (solo con la cápsula seleccionada).
	if control_avatar and Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = JUMP_VELOCITY

	# Get the input direction and handle the movement/deceleration.
	# As good practice, you should replace UI actions with custom gameplay actions.
	var input_dir := Vector2.ZERO
	if control_avatar:
		input_dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var direction := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()
	if direction:
		velocity.x = direction.x * SPEED
		velocity.z = direction.z * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0, SPEED)
		velocity.z = move_toward(velocity.z, 0, SPEED)

	move_and_slide()
