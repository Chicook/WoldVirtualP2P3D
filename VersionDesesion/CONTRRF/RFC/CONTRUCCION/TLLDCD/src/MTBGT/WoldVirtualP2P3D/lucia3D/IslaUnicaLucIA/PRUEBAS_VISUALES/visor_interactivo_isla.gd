extends Node3D
## Visor Interactivo 3D de la Isla Única LucIA (DAO).
##
## Carga el entorno real del metaverso (sol, cielo, WorldEnvironment de
## WoldVirtual3DP2P.tscn, océano y las 4 islas periféricas) y monta la
## Isla Única LucIA completa con su atrio, carrusel, despacho y rampas.
##
## Permite volar libremente con la cámara o saltar con las teclas 1..5 a
## los puntos clave de la cinemática.

const ESCENA_DAO := "res://lucia3D/IslaUnicaLucIA/ESCENAS/IslaUnicaLucIA.tscn"
const RUTA_MUNDO := "res://WoldVirtual3DP2P.tscn"
const RUTA_BLOQUE := "res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"
const CHUNK := 199.5

var _camara: Camera3D = null
var _velocidad := 24.0
var _arrastrando := false
var _rot_x := -0.25
var _rot_y := 0.75
var _hud: CanvasLayer = null
var _info_label: Label = null

# Puntos clave del recorrido cinematográfico para teletransporte rápido:
const PUNTOS_CLAVE := {
	KEY_1: {"nombre": "1 · Vista Aérea General", "pos": Vector3(120.0, 110.0, 120.0), "meta": Vector3(0.0, 42.0, 0.0)},
	KEY_2: {"nombre": "2 · Plaza de Registro (Norte)", "pos": Vector3(0.0, 46.0, -52.0), "meta": Vector3(0.0, 41.0, -34.0)},
	KEY_3: {"nombre": "3 · Despacho de LucIA (Estrado)", "pos": Vector3(7.8, 44.6, 9.0), "meta": Vector3(0.0, 43.2, 0.0)},
	KEY_4: {"nombre": "4 · Atrio y Carrusel de Avatares", "pos": Vector3(0.0, 45.0, 16.8), "meta": Vector3(0.0, 43.0, 0.0)},
	KEY_5: {"nombre": "5 · Portal del Archipiélago", "pos": Vector3(0.0, 44.5, 9.0), "meta": Vector3(0.0, 45.5, 18.2)},
	KEY_6: {"nombre": "6 · Estación Este (Cuenta Única)", "pos": Vector3(50.0, 48.0, 8.0), "meta": Vector3(34.0, 41.5, 0.0)},
	KEY_7: {"nombre": "7 · Acceso Rampa Sur", "pos": Vector3(0.0, 48.0, 48.0), "meta": Vector3(0.0, 42.0, 24.0)},
}


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_montar_entorno()
	_montar_bloques()
	_cargar_dao()
	_crear_camara()
	_crear_hud()


func _montar_entorno() -> void:
	if not ResourceLoader.exists(RUTA_MUNDO):
		return
	var recurso := load(RUTA_MUNDO) as PackedScene
	if recurso == null:
		return
	var mundo := recurso.instantiate()
	var ambiente := mundo.get_node_or_null("WorldEnvironment")
	var sol := mundo.get_node_or_null("DirectionalLight3D")
	if ambiente != null:
		ambiente.owner = null
		mundo.remove_child(ambiente)
		add_child(ambiente)
	if sol != null:
		sol.owner = null
		mundo.remove_child(sol)
		add_child(sol)
	mundo.free()


func _montar_bloques() -> void:
	if not ResourceLoader.exists(RUTA_BLOQUE):
		return
	var plantilla := load(RUTA_BLOQUE) as PackedScene
	if plantilla == null:
		return
	_montar_bloque(plantilla, Vector3.ZERO, "BloqueDAO", true)
	var celdas := [
		Vector3(0, 0, -CHUNK),
		Vector3(CHUNK, 0, 0),
		Vector3(-CHUNK, 0, 0),
		Vector3(0, 0, CHUNK)
	]
	for i in celdas.size():
		_montar_bloque(plantilla, celdas[i], "IslaVecina_%d" % i, false)


func _montar_bloque(plantilla: PackedScene, posicion: Vector3, nombre: String, solo_mar: bool) -> void:
	var bloque := plantilla.instantiate()
	var oceano := bloque.get_node_or_null("Oceano3D")
	var isla := bloque.get_node_or_null("ISLA3DCHUNK")
	if oceano != null:
		bloque.remove_child(oceano)
		oceano.owner = null
	if not solo_mar and isla != null:
		bloque.remove_child(isla)
		isla.owner = null
	var contenedor := Node3D.new()
	contenedor.name = nombre
	contenedor.position = posicion
	add_child(contenedor)
	if oceano != null:
		contenedor.add_child(oceano)
	if not solo_mar and isla != null:
		contenedor.add_child(isla)
	bloque.free()


func _cargar_dao() -> void:
	if not ResourceLoader.exists(ESCENA_DAO):
		push_error("No se encontró " + ESCENA_DAO)
		return
	var escena := load(ESCENA_DAO) as PackedScene
	if escena == null:
		return
	var dao := escena.instantiate() as Node3D
	add_child(dao)


func _crear_camara() -> void:
	_camara = Camera3D.new()
	_camara.name = "CamaraLibre"
	_camara.fov = 55.0
	_camara.far = 4000.0
	_camara.global_position = Vector3(80.0, 75.0, 80.0)
	_camara.look_at(Vector3(0.0, 42.0, 0.0), Vector3.UP)
	_camara.current = true
	add_child(_camara)


func _crear_hud() -> void:
	_hud = CanvasLayer.new()
	_hud.name = "HUDVisor"
	add_child(_hud)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	panel.offset_left = 18.0
	panel.offset_top = 18.0
	panel.offset_right = 540.0
	panel.offset_bottom = 210.0

	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.02, 0.04, 0.08, 0.88)
	estilo.border_color = Color(0.95, 0.82, 0.45, 0.95)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(10)
	estilo.content_margin_left = 16.0
	estilo.content_margin_right = 16.0
	estilo.content_margin_top = 12.0
	estilo.content_margin_bottom = 12.0
	panel.add_theme_stylebox_override("panel", estilo)
	_hud.add_child(panel)

	var caja := VBoxContainer.new()
	caja.add_theme_constant_override("separation", 5)
	panel.add_child(caja)

	var titulo := Label.new()
	titulo.text = "🏛️ EXPLORADOR 3D · ISLA ÚNICA LUCIA (DAO)"
	titulo.add_theme_font_size_override("font_size", 16)
	titulo.add_theme_color_override("font_color", Color(0.95, 0.82, 0.45))
	caja.add_child(titulo)

	var ayuda := Label.new()
	ayuda.text = "• WASD: Volar cámara  |  E/Q o Espacio/Ctrl: Subir/Bajar\n• Botón Derecho Ratón (mantener): Mirar en 360°\n• Shift: Acelerar vuelo (x3)  |  Rueda ratón: Velocidad\n• Teclas 1 al 7: Teletransporte a puntos del recorrido"
	ayuda.add_theme_font_size_override("font_size", 12)
	ayuda.add_theme_color_override("font_color", Color(0.85, 0.92, 1.0))
	caja.add_child(ayuda)

	_info_label = Label.new()
	_info_label.text = "Ubicación: Vista libre"
	_info_label.add_theme_font_size_override("font_size", 13)
	_info_label.add_theme_color_override("font_color", Color(0.55, 0.85, 0.55))
	caja.add_child(_info_label)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_RIGHT:
			_arrastrando = mb.pressed
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if _arrastrando else Input.MOUSE_MODE_VISIBLE
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_velocidad = clampf(_velocidad * 1.15, 3.0, 180.0)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_velocidad = clampf(_velocidad * 0.85, 3.0, 180.0)

	elif event is InputEventMouseMotion and _arrastrando:
		var mm := event as InputEventMouseMotion
		if _camara != null:
			_camara.rotate_y(-mm.relative.x * 0.003)
			_camara.rotate_object_local(Vector3.RIGHT, -mm.relative.y * 0.003)
			# Evitar dar la vuelta vertical completa
			var rot := _camara.rotation
			rot.x = clampf(rot.x, -1.45, 1.45)
			_camara.rotation = rot

	elif event is InputEventKey and event.is_pressed() and not event.is_echo():
		var ke := event as InputEventKey
		if ke.keycode in PUNTOS_CLAVE:
			var info: Dictionary = PUNTOS_CLAVE[ke.keycode]
			_camara.global_position = info["pos"]
			_camara.look_at(info["meta"], Vector3.UP)
			if _info_label != null:
				_info_label.text = "Ubicación: " + str(info["nombre"])
		elif ke.keycode == KEY_ESCAPE:
			_arrastrando = false
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _process(delta: float) -> void:
	if _camara == null:
		return
	var direccion := Vector3.ZERO
	if Input.is_key_pressed(KEY_W):
		direccion -= _camara.global_transform.basis.z
	if Input.is_key_pressed(KEY_S):
		direccion += _camara.global_transform.basis.z
	if Input.is_key_pressed(KEY_A):
		direccion -= _camara.global_transform.basis.x
	if Input.is_key_pressed(KEY_D):
		direccion += _camara.global_transform.basis.x
	if Input.is_key_pressed(KEY_E) or Input.is_key_pressed(KEY_SPACE):
		direccion += Vector3.UP
	if Input.is_key_pressed(KEY_Q) or Input.is_key_pressed(KEY_C):
		direccion -= Vector3.UP

	if direccion.length_squared() > 0.001:
		var mult := 3.0 if Input.is_key_pressed(KEY_SHIFT) else 1.0
		_camara.global_position += direccion.normalized() * (_velocidad * mult * delta)
