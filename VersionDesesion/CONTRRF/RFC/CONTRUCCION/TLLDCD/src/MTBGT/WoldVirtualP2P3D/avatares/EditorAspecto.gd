extends Node3D
## Segunda validación: editor de aspecto del avatar elegido.
##
## Reutiliza `Personalizacion.gd` (tintes por prenda, proporciones, cara y
## expresiones) sobre la escena nueva `res://avatares/<ID>.tscn`. El resultado
## se guarda en `registro.cfg` y `ChunkManager` lo aplica al entrar a la isla.
##
## Con `set_modo_dao(true)` no monta sala propia: edita el avatar real del
## jugador dentro de la DAO, frente al espejo, con la cámara de la cinemática.

signal aspecto_confirmado

const Pers = preload("res://gdscrip/Personalizacion.gd")
const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

const UMBRAL_VARIACION_BLOQUE5 := 18.0  # 18% de variación para sellar el 5º bloque

const GRUPOS := [
	{"titulo": "Color", "tipo": "color", "claves": Pers.ORDEN},
	{"titulo": "Cuerpo", "tipo": "slider", "claves": ["ancho", "cabeza", "hombros", "torso", "brazos", "piernas", "altura_cm"]},
	{"titulo": "Cara", "tipo": "slider", "claves": ["nariz", "labios", "orejas", "ojos"]},
	{"titulo": "Expresión", "tipo": "slider", "claves": ["sonrisa", "enfado", "tristeza", "sorpresa", "parpadeo", "boca_abierta", "boca_ancha"]},
]

var avatar_id: String = ""
var _nick: String = ""
var _avatar: Node3D
var _avatar_dao: Node3D = null
var _modo_dao := false
var _pers: Dictionary = {}
var _sliders: Dictionary = {}
var _valores: Dictionary = {}
var _timer: Timer
var _nombre: Label
var _subtitulo: Label
var _etiqueta_bloque5: Label = null
var _barra_bloque5: ProgressBar = null
var _bloque5_hash := ""
var _bloque5_sellado := false
var _boton_guardar_ref: Button = null


func set_avatar(id: String) -> void:
	avatar_id = id
	if is_inside_tree():
		_montar()


func set_avatar_dao(nodo: Node3D) -> void:
	_avatar_dao = nodo


func set_modo_dao(activo: bool) -> void:
	_modo_dao = activo


func set_nick(nick: String) -> void:
	_nick = nick.strip_edges()
	_actualizar_textos()


func _ready() -> void:
	if not _modo_dao:
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
	if _modo_dao:
		return
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
	_pers = Pers.leer()
	if _modo_dao and _avatar_dao != null and is_instance_valid(_avatar_dao):
		# El espejo edita al jugador real: lo que se ve es lo que se lleva.
		_avatar = _avatar_dao
		Pers.aplicar(_avatar, _pers)
		_sincronizar_controles()
		_actualizar_textos()
		return
	if _avatar != null and is_instance_valid(_avatar):
		_avatar.queue_free()
	_avatar = Catalogo.crear(avatar_id)
	if _avatar == null:
		push_error("[EditorAspecto] no se encontró el avatar para editar: ", avatar_id)
		return
	if not _modo_dao:
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

	var titulo := _etiqueta("EL ESPEJO DE LA DAO · TU AVATAR" if _modo_dao
			else "SEGUNDA VALIDACIÓN · TU AVATAR", 28, Color(0.78, 0.94, 1.0, 1.0))
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
	guardar.text = "GUARDAR Y SEGUIR" if _modo_dao else "GUARDAR Y ENTRAR"
	guardar.custom_minimum_size = Vector2(210, 44)
	guardar.add_theme_font_size_override("font_size", 16)
	guardar.pressed.connect(_guardar)
	botones.add_child(guardar)
	_boton_guardar_ref = guardar

	var reset := Button.new()
	reset.text = "RESTABLECER"
	reset.custom_minimum_size = Vector2(150, 44)
	reset.pressed.connect(_restablecer)
	botones.add_child(reset)

	var saltar := Button.new()
	saltar.text = "SEGUIR SIN CAMBIOS" if _modo_dao else "ENTRAR SIN CAMBIOS"
	saltar.custom_minimum_size = Vector2(190, 44)
	saltar.pressed.connect(func(): aspecto_confirmado.emit())
	botones.add_child(saltar)

	# Panel de validación del Bloque 5 (Personalización del Avatar)
	var panel_bloque5 := PanelContainer.new()
	panel_bloque5.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	panel_bloque5.offset_left = 34
	panel_bloque5.offset_top = -175
	panel_bloque5.offset_right = 620
	panel_bloque5.offset_bottom = -88
	var estilo_b5 := StyleBoxFlat.new()
	estilo_b5.bg_color = Color(0.02, 0.05, 0.10, 0.92)
	estilo_b5.border_color = Color(0.2, 0.7, 0.9, 0.8)
	estilo_b5.set_border_width_all(2)
	estilo_b5.set_corner_radius_all(8)
	estilo_b5.content_margin_left = 12
	estilo_b5.content_margin_right = 12
	estilo_b5.content_margin_top = 8
	estilo_b5.content_margin_bottom = 8
	panel_bloque5.add_theme_stylebox_override("panel", estilo_b5)
	raiz.add_child(panel_bloque5)

	var caja_b5 := VBoxContainer.new()
	caja_b5.add_theme_constant_override("separation", 4)
	panel_bloque5.add_child(caja_b5)

	_etiqueta_bloque5 = _etiqueta("Bloque #5 de Validación: Variación de Avatar: 0.0% / 18% requerido", 13, Color(0.7, 0.9, 1.0))
	caja_b5.add_child(_etiqueta_bloque5)

	_barra_bloque5 = ProgressBar.new()
	_barra_bloque5.min_value = 0.0
	_barra_bloque5.max_value = 100.0
	_barra_bloque5.value = 0.0
	_barra_bloque5.custom_minimum_size = Vector2(0, 16)
	caja_b5.add_child(_barra_bloque5)

	var pista := _etiqueta("El espejo de la DAO aplica el aspecto a tu avatar y sella el 5º bloque."
			if _modo_dao else "Los cambios se aplican al avatar de la isla y se guardan en tu perfil.",
		12, Color(0.55, 0.68, 0.85, 0.9))
	pista.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	pista.offset_left = 34
	pista.offset_top = -205
	pista.offset_right = 900
	pista.offset_bottom = -182
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
	_actualizar_bloque5()


func _programar() -> void:
	if _timer == null:
		return
	_timer.start()


func _aplicar() -> void:
	if _avatar == null or not is_instance_valid(_avatar):
		return
	Pers.aplicar(_avatar, _pers)
	_actualizar_bloque5()


func calcular_variacion_respecto_defecto() -> float:
	var total_elementos := 0
	var suma_deltas := 0.0

	# 1. Variación en colores (prendas y piel)
	for col_key in Pers.ORDEN:
		var c_actual: Color = _pers.get(col_key, Pers.POR_DEFECTO.get(col_key, Color.WHITE))
		var c_def: Color = Pers.POR_DEFECTO.get(col_key, Color.WHITE)
		var delta_r := absf(c_actual.r - c_def.r)
		var delta_g := absf(c_actual.g - c_def.g)
		var delta_b := absf(c_actual.b - c_def.b)
		var delta_col := (delta_r + delta_g + delta_b) / 3.0
		suma_deltas += delta_col
		total_elementos += 1

	# 2. Variación en sliders numéricos (cuerpo, cara, expresiones)
	for campo in Pers.CAMPOS:
		if not Pers.RANGOS.has(campo):
			continue
		var val_actual := float(_pers.get(campo, Pers.POR_DEFECTO.get(campo, 0.0)))
		var val_def := float(Pers.POR_DEFECTO.get(campo, 0.0))
		var rango: Vector2 = Pers.RANGOS[campo]
		var span := maxf(rango.y - rango.x, 0.001)
		var delta_norm := absf(val_actual - val_def) / span
		suma_deltas += clampf(delta_norm, 0.0, 1.0)
		total_elementos += 1

	if total_elementos == 0:
		return 0.0

	var porcentaje := (suma_deltas / float(total_elementos)) * 100.0
	# Factor de escala sensorial: cambios notables en 2 o 3 partes deben reflejar el % de impacto
	porcentaje = clampf(porcentaje * 2.8, 0.0, 100.0)
	return porcentaje


func _actualizar_bloque5() -> void:
	var variacion := calcular_variacion_respecto_defecto()
	if _barra_bloque5 != null:
		_barra_bloque5.value = variacion

	if variacion >= UMBRAL_VARIACION_BLOQUE5:
		if not _bloque5_sellado:
			_bloque5_sellado = true
			var crypto_source := "%s:%s:bloque5_avatar:%.2f:%d" % [_nick, avatar_id, variacion, Time.get_unix_time_from_system()]
			_bloque5_hash = crypto_source.sha256_text()
		if _etiqueta_bloque5 != null:
			_etiqueta_bloque5.text = "✅ Bloque #5 SELLADO (%.1f%% / 18%%)\nHash: %s…" % [
				variacion, _bloque5_hash.substr(0, 16)
			]
			_etiqueta_bloque5.add_theme_color_override("font_color", Color(0.4, 1.0, 0.6))
		if _boton_guardar_ref != null:
			_boton_guardar_ref.modulate = Color(1.0, 1.0, 1.0, 1.0)
	else:
		_bloque5_sellado = false
		if _etiqueta_bloque5 != null:
			_etiqueta_bloque5.text = "Bloque #5 de Validación: Variación: %.1f%% / 18%% requerido" % variacion
			_etiqueta_bloque5.add_theme_color_override("font_color", Color(1.0, 0.8, 0.4))


func _restablecer() -> void:
	_pers = Pers.POR_DEFECTO.duplicate()
	_sincronizar_controles()
	_aplicar()


func _guardar() -> void:
	Pers.guardar(_pers)
	if not avatar_id.is_empty():
		Avatares.sincronizar_registro(avatar_id, _nick)
	# Si se selló el bloque 5, lo anexamos a la cuenta local
	if _bloque5_sellado and not _bloque5_hash.is_empty():
		_guardar_bloque5_en_cuenta()
	aspecto_confirmado.emit()


func _guardar_bloque5_en_cuenta() -> void:
	var ruta_cuenta := "user://cuenta.json"
	var datos: Dictionary = {}
	if FileAccess.file_exists(ruta_cuenta):
		var crudo := FileAccess.get_file_as_string(ruta_cuenta)
		var parseado = JSON.parse_string(crudo)
		if typeof(parseado) == TYPE_DICTIONARY:
			datos = parseado
	var bloques: Array = datos.get("bloques_dao", [])
	bloques.append({
		"bloque": 5,
		"tipo": "personalizacion_avatar",
		"avatar_id": avatar_id,
		"hash": _bloque5_hash,
		"variacion": calcular_variacion_respecto_defecto(),
		"timestamp": Time.get_datetime_string_from_system(true, true)
	})
	datos["bloques_dao"] = bloques
	datos["bloque5_hash"] = _bloque5_hash
	var f := FileAccess.open(ruta_cuenta, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(datos, "\t"))
		f.close()


## Confirma y guarda sin depender del botón (onboarding/pruebas).
func confirmar_actual() -> void:
	_guardar()


func _actualizar_textos() -> void:
	if _subtitulo == null:
		return
	var nombre := Catalogo.nombre_de(avatar_id)
	if _modo_dao:
		var quien := "Tu avatar" if _nick.is_empty() else "%s, tu avatar" % _nick
		_subtitulo.text = "%s está de pie frente al espejo de la DAO. Lo que ajustes aquí es lo que entras llevando a tu isla." % quien
		return
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
