extends SceneTree
## Prueba el selector con avatares sinteticos (los GLB reales viven en el PCK):
## clic para enfocar, arrastre circular, rueda, nick obligatorio, aviso verde
## AVATAR ORIGINAL, plaza ocupada, reciclaje del turno 4 y guardado de la
## eleccion sin saltarse el registro.

const SLAV := "res://SLCAV/AVATARESCONANIMACION/SLAV.tscn"
const RUTA_FALSO := "user://avatar_selector_prueba.tscn"

var _fallos := 0


func _initialize() -> void:
	_correr()


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK    ", texto)
	else:
		print("FALLO ", texto)
		_fallos += 1


func _correr() -> void:
	await process_frame
	get_root().size = Vector2i(1280, 720)
	_crear_avatar_falso()

	var carrusel := (load(SLAV) as PackedScene).instantiate()
	var rutas: Array[String] = [RUTA_FALSO, RUTA_FALSO, RUTA_FALSO, RUTA_FALSO]
	var nombres: Array[String] = ["AVH1", "AVMJ1", "AVH2", "AVMJ2"]
	carrusel.avatar_paths = rutas
	carrusel.playable_scenes = rutas
	carrusel.avatar_names = nombres
	carrusel.per_turn = 4
	carrusel.set_ocupados([1])
	carrusel.abrir_en_primer_hueco()
	get_root().add_child(carrusel)
	await create_timer(0.6).timeout

	_check(carrusel._avatars.size() == 4, "el turno monta 4 avatares sinteticos")
	_check(carrusel._index == 0, "abre en el primer hueco")

	# Aviso verde del avatar original.
	_check(carrusel._status.text.contains("AVATAR ORIGINAL"), "el estado anuncia AVATAR ORIGINAL")
	var verde: Color = carrusel._status.get_theme_color("font_color")
	_check(verde.g > verde.r and verde.g > 0.7, "el aviso AVATAR ORIGINAL es verde")

	# Sin nick no se puede confirmar.
	_check(carrusel._boton_confirm.disabled, "sin nick el boton esta deshabilitado")
	carrusel._nick_edit.text = "Lucia"
	carrusel._on_nick_cambiada("Lucia")
	_check(not carrusel._boton_confirm.disabled, "con nick el boton se habilita")

	# Clic sobre el cuerpo: enfoca el avatar 3 (a la izquierda del anillo).
	var avatar3: Node3D = carrusel._avatars[3]
	var punto: Vector2 = carrusel._camara.unproject_position(
		avatar3.global_position + Vector3.UP * 0.9)
	_check(carrusel._indice_bajo_punto(punto) == 3, "el clic sobre el cuerpo acierta el avatar 3")
	_raton(carrusel, MOUSE_BUTTON_LEFT, true, punto)
	_raton(carrusel, MOUSE_BUTTON_LEFT, false, punto)
	await process_frame
	_check(carrusel._index == 3, "el clic enfoca el avatar 3")

	# Arrastre circular: 160 px a la izquierda avanzan dos avatares (3 -> 0 -> 2,
	# saltando la plaza ocupada 1) y el soltar no cambia de avatar.
	_raton(carrusel, MOUSE_BUTTON_LEFT, true, Vector2(640.0, 400.0))
	var movimiento := InputEventMouseMotion.new()
	movimiento.position = Vector2(480.0, 400.0)
	movimiento.relative = Vector2(-160.0, 0.0)
	carrusel._unhandled_input(movimiento)
	_check(carrusel._index == 2, "arrastrar a la izquierda gira dos plazas")
	var antes: int = carrusel._index
	_raton(carrusel, MOUSE_BUTTON_LEFT, false, Vector2(480.0, 400.0))
	_check(carrusel._index == antes, "soltar tras arrastrar no cambia de avatar")

	# Rueda del raton.
	var rueda := InputEventMouseButton.new()
	rueda.button_index = MOUSE_BUTTON_WHEEL_UP
	rueda.pressed = true
	rueda.position = Vector2(640.0, 400.0)
	carrusel._unhandled_input(rueda)
	_check(carrusel._index == 3, "la rueda avanza al siguiente avatar")

	# Plaza ocupada: aviso rojo, boton desactivado y no se confirma.
	var confirmados := [0]
	carrusel.avatar_confirmed.connect(func(_ruta: String) -> void: confirmados[0] += 1)
	carrusel._ir_a(1, true)
	_check(carrusel._status.text.contains("OCUPADA"), "la plaza ocupada se anuncia en rojo")
	var rojo: Color = carrusel._status.get_theme_color("font_color")
	_check(rojo.r > rojo.g, "el aviso de plaza ocupada es rojo")
	_check(carrusel._boton_confirm.disabled, "una plaza ocupada no se puede confirmar")
	carrusel._confirm()
	_check(confirmados[0] == 0, "no se emite la confirmacion de una plaza ajena")

	# Eleccion valida: guarda selector, nombre y turno, sin escribir avatar_scene.
	carrusel._ir_a(0, true)
	carrusel._confirm()
	_check(confirmados[0] == 1, "un avatar libre se confirma")
	var cfg := ConfigFile.new()
	cfg.load("user://registro.cfg")
	_check(str(cfg.get_value("jugador", "nick_selector", "")) == "Lucia", "guarda el nick del selector")
	_check(str(cfg.get_value("jugador", "avatar_selector", "")) == RUTA_FALSO, "guarda la escena elegida")
	_check(str(cfg.get_value("jugador", "avatar_nombre", "")) == "AVH1", "guarda el nombre del avatar")
	_check(int(cfg.get_value("jugador", "avatar_turno", 0)) == 1, "guarda el turno del avatar")
	_check(str(cfg.get_value("jugador", "avatar_scene", "SIN")) == "SIN",
		"no escribe avatar_scene: el registro sigue siendo obligatorio")

	# Los 4 ocupados: modo reciclaje del turno 4, sin saltos y confirmable.
	carrusel.set_ocupados([0, 1, 2, 3])
	_check(carrusel._reciclando, "4/4 ocupados activa el reciclaje")
	_check(carrusel._status.text.contains("TURNO 4"), "el aviso anuncia el turno 4")
	carrusel._move(1)
	_check(carrusel._index == 1, "reciclando permite avanzar a plazas ocupadas")
	carrusel._confirm()
	_check(confirmados[0] == 2, "reciclando se puede confirmar")
	cfg.load("user://registro.cfg")
	_check(bool(cfg.get_value("jugador", "avatar_reciclado", false)), "guarda que el avatar se reutiliza")

	carrusel.queue_free()
	await process_frame
	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)


func _raton(carrusel, boton: int, pulsado: bool, pos: Vector2) -> void:
	var ev := InputEventMouseButton.new()
	ev.button_index = boton
	ev.pressed = pulsado
	ev.position = pos
	carrusel._unhandled_input(ev)


## Escena minima jugable para el carrusel (sin mallas ni esqueleto).
func _crear_avatar_falso() -> void:
	var raiz := Node3D.new()
	raiz.name = "AvatarFalso"
	var mi := MeshInstance3D.new()
	mi.name = "Body"
	mi.mesh = BoxMesh.new()
	raiz.add_child(mi)
	mi.owner = raiz
	var ps := PackedScene.new()
	ps.pack(raiz)
	raiz.free()
	ResourceSaver.save(ps, RUTA_FALSO)
