extends Node3D
## Segunda validación: editor de aspecto del avatar elegido.
##
## Reutiliza `Personalizacion.gd` (tintes por prenda, proporciones, cara y
## expresiones) sobre la escena nueva `res://avatares/<ID>.tscn`. El resultado
## se guarda en `registro.cfg` y `ChunkManager` lo aplica al entrar a la isla.

signal aspecto_confirmado

const Pers = preload("res://gdscrip/Personalizacion.gd")
const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

const GRUPOS := [
	{"titulo": "Color", "tipo": "color", "claves": Pers.ORDEN},
	{"titulo": "Cuerpo", "tipo": "slider", "claves": ["ancho", "cabeza", "hombros", "torso", "brazos", "piernas", "altura_cm"]},
	{"titulo": "Cara", "tipo": "slider", "claves": ["nariz", "labios", "orejas", "ojos"]},
	{"titulo": "Expresión", "tipo": "slider", "claves": ["sonrisa", "enfado", "tristeza", "sorpresa", "parpadeo", "boca_abierta", "boca_ancha"]},
]

var avatar_id: String = ""
var _nick: String = ""
var _avatar: Node3D
var _pers: Dictionary = {}
var _sliders: Dictionary = {}
var _valores: Dictionary = {}
var _timer: Timer
var _nombre: Label
var _subtitulo: Label


func set_avatar(id: String) -> void:
	avatar_id = id
	if is_inside_tree():
		_montar()


func set_nick(nick: String) -> void:
	_nick = nick.strip_edges()
	_actualizar_textos()


func _ready() -> void:
	_construir_escena()
	_construir_ui()
	_timer = Timer.new()
	_timer.one_shot = true
	_timer.wait_time = 0.12
	_timer.timeout.connect(_aplicar)
	add_child(_timer)
	if not avatar_id.is_empty():
		_montar()


func _construir_escena() -> void:
	var entorno := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.012, 0.018, 0.035, 1)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.25, 0.33, 0.5, 1)
	env.ambient_light_energy = 0.9
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.glow_enabled = true
	env.glow_intensity = 0.6
	entorno.environment = env
	add_child(entorno)

	var camara := Camera3D.new()
	camara.name = "Camara"
	camara.position = Vector3(0.0, 1.35, 3.4)
	camara.fov = 38.0
	camara.current = true
	add_child(camara)
	camara.look_at(Vector3(0.0, 1.0, 0.0), Vector3.UP)

	var suelo := MeshInstance3D.new()
	var plano := PlaneMesh.new()
	plano.size = Vector2(14, 14)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.03, 0.045, 0.08, 1)
	mat.roughness = 0.8
	plano.material = mat
	suelo.mesh = plano
	suelo.position.y = -0.02
	add_child(suelo)

	for datos in [
		{"pos": Vector3(2.2, 3.0, 2.8), "color": Color(1, 0.95, 0.88), "energia": 3.2},
		{"pos": Vector3(-2.5, 2.0, 2.0), "color": Color(0.55, 0.72, 1), "energia": 2.4},
		{"pos": Vector3(0, 2.4, -3.2), "color": Color(0.4, 0.8, 1), "energia": 2.6},
	]:
		var luz := OmniLight3D.new()
		luz.position = datos["pos"] as Vector3
		luz.light_color = datos["color"] as Color
		luz.light_energy = float(datos["energia"])
		luz.omni_range = 12.0
		add_child(luz)


func _montar() -> void:
	if _avatar != null and is_instance_valid(_avatar):
		_avatar.queue_free()
	_pers = Pers.leer()
	_avatar = Catalogo.crear(avatar_id)
	if _avatar == null:
		push_error("[EditorAspecto] no se pudo crear ", avatar_id)
		return
	_avatar.name = "AvatarAspecto"
	_avatar.position = Vector3.ZERO
	_avatar.set("es_selector", true)
	add_child(_avatar)
	Pers.aplicar(_avatar, _pers)
	_sincronizar_controles()
	_actualizar_textos()


func _construir_ui() -> void:
	var capa := CanvasLayer.new()
	capa.name = "UI"
	capa.layer = 20
	add_child(capa)
	var raiz := Control.new()
	raiz.set_anchors_preset(Control.PRESET_FULL_RECT)
	capa.add_child(raiz)

	var titulo := _etiqueta("SEGUNDA VALIDACIÓN · TU AVATAR", 28, Color(0.78, 0.94, 1.0, 1.0))
	titulo.position = Vector2(34, 22)
	titulo.size = Vector2(760, 40)
	raiz.add_child(titulo)

	_subtitulo = _etiqueta("", 15, Color(0.62, 0.82, 1.0, 1.0))
	_subtitulo.position = Vector2(36, 62)
	_subtitulo.size = Vector2(760, 50)
	raiz.add_child(_subtitulo)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	panel.anchor_left = 0.6
	panel.anchor_right = 0.98
	panel.anchor_top = 0.07
	panel.anchor_bottom = 0.93
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.03, 0.05, 0.10, 0.94)
	estilo.border_color = Color(0.35, 0.72, 1.0, 0.6)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(12)
	estilo.content_margin_left = 16
	estilo.content_margin_right = 16
	estilo.content_margin_top = 14
	estilo.content_margin_bottom = 14
	panel.add_theme_stylebox_override("panel", estilo)
	raiz.add_child(panel)

	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_child(scroll)
	var caja := VBoxContainer.new()
	caja.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	caja.add_theme_constant_override("separation", 10)
	scroll.add_child(caja)

	for grupo in GRUPOS:
		var cabecera := _etiqueta(str(grupo["titulo"]).to_upper(), 16, Color(0.45, 0.85, 1.0, 1.0))
		caja.add_child(cabecera)
		for clave in grupo["claves"]:
			if grupo["tipo"] == "color":
				caja.add_child(_fila_color(str(clave)))
			else:
				caja.add_child(_fila_slider(str(clave)))

	var botones := HBoxContainer.new()
	botones.add_theme_constant_override("separation", 8)
	raiz.add_child(botones)
	botones.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	botones.offset_left = 34
	botones.offset_top = -74
	botones.offset_right = 900
	botones.offset_bottom = -24

	var guardar := Button.new()
	guardar.text = "GUARDAR Y ENTRAR"
	guardar.custom_minimum_size = Vector2(210, 44)
	guardar.add_theme_font_size_override("font_size", 16)
	guardar.pressed.connect(_guardar)
	botones.add_child(guardar)

	var reset := Button.new()
	reset.text = "RESTABLECER"
	reset.custom_minimum_size = Vector2(150, 44)
	reset.pressed.connect(_restablecer)
	botones.add_child(reset)

	var saltar := Button.new()
	saltar.text = "ENTRAR SIN CAMBIOS"
	saltar.custom_minimum_size = Vector2(190, 44)
	saltar.pressed.connect(func(): aspecto_confirmado.emit())
	botones.add_child(saltar)

	var pista := _etiqueta("Los cambios se aplican al avatar de la isla y se guardan en tu perfil.",
		13, Color(0.55, 0.68, 0.85, 0.9))
	pista.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	pista.offset_left = 34
	pista.offset_top = -104
	pista.offset_right = 900
	pista.offset_bottom = -82
	raiz.add_child(pista)


func _fila_color(clave: String) -> HBoxContainer:
	var fila := HBoxContainer.new()
	fila.add_theme_constant_override("separation", 8)
	var nombre := _etiqueta(str(Pers.NOMBRES.get(clave, clave)), 14, Color(0.8, 0.9, 1.0, 1.0))
	nombre.custom_minimum_size = Vector2(150, 30)
	fila.add_child(nombre)
	var selector := ColorPickerButton.new()
	selector.color = _pers.get(clave, Color.WHITE) as Color
	selector.custom_minimum_size = Vector2(120, 32)
	selector.edit_alpha = false
	selector.color_changed.connect(func(color: Color):
		_pers[clave] = color
		_programar())
	fila.add_child(selector)
	return fila


func _fila_slider(clave: String) -> VBoxContainer:
	var caja := VBoxContainer.new()
	caja.add_theme_constant_override("separation", 2)
	var fila := HBoxContainer.new()
	var nombre := _etiqueta(str(Pers.NOMBRES.get(clave, clave)), 13, Color(0.8, 0.9, 1.0, 1.0))
	nombre.custom_minimum_size = Vector2(150, 22)
	fila.add_child(nombre)
	var valor := _etiqueta("", 12, Color(0.55, 0.75, 0.95, 1.0))
	valor.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	valor.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fila.add_child(valor)
	caja.add_child(fila)
	var rango: Vector2 = Pers.RANGOS[clave]
	var slider := HSlider.new()
	slider.min_value = rango.x
	slider.max_value = rango.y
	slider.step = 0.01 if clave != "altura_cm" else 0.5
	slider.value = float(_pers.get(clave, Pers.POR_DEFECTO[clave]))
	slider.custom_minimum_size = Vector2(0, 22)
	slider.value_changed.connect(func(v: float):
		_pers[clave] = v
		_valores[clave].text = _formato(clave, v)
		_programar())
	caja.add_child(slider)
	_sliders[clave] = slider
	_valores[clave] = valor
	valor.text = _formato(clave, slider.value)
	return caja


func _formato(clave: String, valor: float) -> String:
	if clave == "altura_cm":
		return "+%.1f cm" % valor
	if clave in Pers.RANGOS and (clave in ["nariz", "labios", "orejas", "ojos", "sonrisa", "enfado", "tristeza", "sorpresa", "parpadeo", "boca_abierta", "boca_ancha"]):
		return "%d %%" % int(round(valor * 100.0))
	return "%.2f×" % valor


func _sincronizar_controles() -> void:
	for clave in _sliders.keys():
		var slider := _sliders[clave] as HSlider
		if slider == null:
			continue
		slider.set_value_no_signal(float(_pers.get(clave, Pers.POR_DEFECTO[clave])))
		_valores[clave].text = _formato(clave, slider.value)


func _programar() -> void:
	if _timer == null:
		return
	_timer.start()


func _aplicar() -> void:
	if _avatar == null or not is_instance_valid(_avatar):
		return
	Pers.aplicar(_avatar, _pers)


func _restablecer() -> void:
	_pers = Pers.POR_DEFECTO.duplicate()
	_sincronizar_controles()
	_aplicar()


func _guardar() -> void:
	Pers.guardar(_pers)
	if not avatar_id.is_empty():
		Avatares.sincronizar_registro(avatar_id, _nick)
	aspecto_confirmado.emit()


func _actualizar_textos() -> void:
	if _subtitulo == null:
		return
	var nombre := Catalogo.nombre_de(avatar_id)
	if _nick.is_empty():
		_subtitulo.text = "Ajusta el aspecto de %s antes de entrar a tu isla." % nombre
	else:
		_subtitulo.text = "%s, ajusta el aspecto de %s antes de entrar a tu isla." % [_nick, nombre]


func _etiqueta(texto: String, tam: int, color: Color) -> Label:
	var etiqueta := Label.new()
	etiqueta.text = texto
	etiqueta.add_theme_font_size_override("font_size", tam)
	etiqueta.add_theme_color_override("font_color", color)
	etiqueta.add_theme_color_override("font_outline_color", Color(0.01, 0.04, 0.08, 1.0))
	etiqueta.add_theme_constant_override("outline_size", 5)
	return etiqueta
