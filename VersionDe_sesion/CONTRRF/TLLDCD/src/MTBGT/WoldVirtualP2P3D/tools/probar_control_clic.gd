extends SceneTree
## Comprueba el control por clic del avatar:
##   - sin clic, las flechas no lo mueven;
##   - un clic sobre el cuerpo lo selecciona y entonces sí responde;
##   - perder el foco (clic en el chat del visor) lo deselecciona.
## Cubre los dos controladores de avatar en tercera persona.

const HM1 := "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/userbaseh1.tscn"
const AVMJ := "res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ1Ch3D.tscn"
const CAPSULA := "res://ESCENAS/sceneOPTM/constructor/user/userbase.tscn"

var _fallos := 0


func _initialize() -> void:
	_correr()


func _check(cond: bool, texto: String) -> void:
	if cond:
		print("OK    ", texto)
	else:
		print("FALLO ", texto)
		_fallos += 1


func _correr() -> void:
	await process_frame
	_check(load(HM1) != null, "carga userbaseh1")
	_check(load(AVMJ) != null, "carga AVMJ1Ch3D")
	await _probar_avatar(HM1, "userbaseh1")
	await _probar_avatar(AVMJ, "AVMJ1Ch3D")
	await _probar_capsula()
	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)


func _probar_avatar(ruta: String, etiqueta: String) -> void:
	var mundo := Node3D.new()
	mundo.name = "MundoPrueba"
	root.add_child(mundo)

	var suelo := StaticBody3D.new()
	var forma := BoxShape3D.new()
	forma.size = Vector3(40.0, 1.0, 40.0)
	var colision := CollisionShape3D.new()
	colision.shape = forma
	suelo.add_child(colision)
	suelo.position = Vector3(0.0, -0.5, 0.0)
	mundo.add_child(suelo)

	var avatar: CharacterBody3D = (load(ruta) as PackedScene).instantiate()
	mundo.add_child(avatar)

	# Dejar que caiga, se asiente y la cámara se coloque detrás.
	for i in 40:
		await physics_frame

	_check(avatar.control_avatar == false, "%s empieza sin control" % etiqueta)

	# Sin selección, las flechas no deben moverlo.
	var inicio := avatar.global_position
	Input.action_press("ui_right")
	for i in 20:
		await physics_frame
	Input.action_release("ui_right")
	_check(_plano(avatar.global_position - inicio) < 0.05, "%s quieto sin clic" % etiqueta)

	# Un clic sobre el cuerpo (rayo desde la cámara) lo alcanza.
	var cam: Camera3D = avatar.find_child("Camera3D", true, false)
	_check(cam != null, "%s tiene cámara" % etiqueta)
	var punto := cam.unproject_position(avatar.global_position + Vector3.UP * 1.0)
	_check(avatar._clic_sobre_avatar(punto), "%s el rayo sobre el cuerpo acierta" % etiqueta)
	_check(not avatar._clic_sobre_avatar(Vector2(2, 2)), "%s un clic fuera no lo alcanza" % etiqueta)

	# Clic completo: entra por _unhandled_input y se resuelve en el paso de física.
	var clic := InputEventMouseButton.new()
	clic.button_index = MOUSE_BUTTON_LEFT
	clic.pressed = true
	clic.position = punto
	avatar._unhandled_input(clic)
	await physics_frame
	_check(avatar.control_avatar, "%s queda seleccionado tras el clic" % etiqueta)

	inicio = avatar.global_position
	Input.action_press("ui_right")
	for i in 20:
		await physics_frame
	Input.action_release("ui_right")
	_check(_plano(avatar.global_position - inicio) > 0.1, "%s se mueve con flechas tras el clic" % etiqueta)

	# Perder el foco lo suelta y limpia la velocidad horizontal.
	avatar._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	_check(avatar.control_avatar == false, "%s perder foco lo deselecciona" % etiqueta)
	_check(absf(avatar.velocity.x) < 0.01 and absf(avatar.velocity.z) < 0.01,
		"%s perder foco detiene el avatar" % etiqueta)

	mundo.free()
	await process_frame


## En primera persona no hay cuerpo visible: basta un clic en la vista.
func _probar_capsula() -> void:
	var mundo := Node3D.new()
	mundo.name = "MundoCapsula"
	root.add_child(mundo)

	var suelo := StaticBody3D.new()
	var forma := BoxShape3D.new()
	forma.size = Vector3(40.0, 1.0, 40.0)
	var colision := CollisionShape3D.new()
	colision.shape = forma
	suelo.add_child(colision)
	suelo.position = Vector3(0.0, -0.5, 0.0)
	mundo.add_child(suelo)

	var avatar: CharacterBody3D = (load(CAPSULA) as PackedScene).instantiate()
	mundo.add_child(avatar)
	for i in 40:
		await physics_frame

	_check(avatar.control_avatar == false, "cápsula empieza sin control")

	var inicio := avatar.global_position
	Input.action_press("ui_right")
	for i in 20:
		await physics_frame
	Input.action_release("ui_right")
	_check(_plano(avatar.global_position - inicio) < 0.05, "cápsula quieta sin clic")

	var clic := InputEventMouseButton.new()
	clic.button_index = MOUSE_BUTTON_LEFT
	clic.pressed = true
	clic.position = Vector2(400, 300)
	avatar._unhandled_input(clic)
	_check(avatar.control_avatar, "cápsula seleccionada con un clic")

	inicio = avatar.global_position
	Input.action_press("ui_right")
	for i in 20:
		await physics_frame
	Input.action_release("ui_right")
	_check(_plano(avatar.global_position - inicio) > 0.1, "cápsula se mueve con flechas tras el clic")

	avatar._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	_check(avatar.control_avatar == false, "cápsula perder foco la deselecciona")

	mundo.free()
	await process_frame


func _plano(v: Vector3) -> float:
	return Vector2(v.x, v.z).length()
