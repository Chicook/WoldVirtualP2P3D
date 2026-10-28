extends Control
## Fase de registro: muestra el avatar de frente (idle), pide nick y permite
## personalizar su aspecto: tintes por prenda, altura/proporciones y rasgos
## faciales. Al confirmar emite registro_completado; el Boot del metaverso
## escucha y pasa a la ventana de carga. Si se ejecuta suelto, cambia de escena.
signal registro_completado(nick: String)
@export var siguiente_escena: String = "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/mnpr.tscn"

const Pers = preload("res://gdscrip/Personalizacion.gd")

@onready var nick_edit: LineEdit = $Panel/VBox/NickEdit
@onready var error_label: Label = $Panel/VBox/ErrorLabel
@onready var preview_host: Node3D = $Panel/VBox/ViewportContainer/Viewport/Preview3D

@onready var picker_piel: ColorPickerButton = $Panel/Personalizacion/Tabs/Colores/PersGrid/Piel/Color
@onready var picker_pelo: ColorPickerButton = $Panel/Personalizacion/Tabs/Colores/PersGrid/Pelo/Color
@onready var picker_camiseta: ColorPickerButton = $Panel/Personalizacion/Tabs/Colores/PersGrid/Camiseta/Color
@onready var picker_pantalon: ColorPickerButton = $Panel/Personalizacion/Tabs/Colores/PersGrid/Pantalon/Color
@onready var picker_zapatillas: ColorPickerButton = $Panel/Personalizacion/Tabs/Colores/PersGrid/Zapatillas/Color
@onready var boton_restablecer: Button = $Panel/Personalizacion/Restablecer

var _sliders := {}
var _valores := {}
var _selected_avatar_scene := ""
var _preview: Node = null
var _pers: Dictionary = {}
var _volcando := false


func _ready() -> void:
	# La cámara de preview manda; apagamos la cámara orbital del avatar instanciado.
	var avatar_cam: Camera3D = $Panel/VBox/ViewportContainer/Viewport/Preview3D/userbaseh1/Camera3D
	if avatar_cam:
		avatar_cam.current = false

	_sliders = {
		"altura_cm": $Panel/Personalizacion/Tabs/Cuerpo/AlturaFila/Slider,
		"ancho": $Panel/Personalizacion/Tabs/Cuerpo/AnchoFila/Slider,
		"cabeza": $Panel/Personalizacion/Tabs/Cuerpo/CabezaFila/Slider,
		"hombros": $Panel/Personalizacion/Tabs/Cuerpo/HombrosFila/Slider,
		"torso": $Panel/Personalizacion/Tabs/Cuerpo/TorsoFila/Slider,
		"brazos": $Panel/Personalizacion/Tabs/Cuerpo/BrazosFila/Slider,
		"piernas": $Panel/Personalizacion/Tabs/Cuerpo/PiernasFila/Slider,
		"nariz": $Panel/Personalizacion/Tabs/Cara/NarizFila/Slider,
		"labios": $Panel/Personalizacion/Tabs/Cara/LabiosFila/Slider,
		"orejas": $Panel/Personalizacion/Tabs/Cara/OrejasFila/Slider,
		"ojos": $Panel/Personalizacion/Tabs/Cara/OjosFila/Slider,
	}
	_valores = {
		"altura_cm": $Panel/Personalizacion/Tabs/Cuerpo/AlturaFila/Valor,
		"ancho": $Panel/Personalizacion/Tabs/Cuerpo/AnchoFila/Valor,
		"cabeza": $Panel/Personalizacion/Tabs/Cuerpo/CabezaFila/Valor,
		"hombros": $Panel/Personalizacion/Tabs/Cuerpo/HombrosFila/Valor,
		"torso": $Panel/Personalizacion/Tabs/Cuerpo/TorsoFila/Valor,
		"brazos": $Panel/Personalizacion/Tabs/Cuerpo/BrazosFila/Valor,
		"piernas": $Panel/Personalizacion/Tabs/Cuerpo/PiernasFila/Valor,
		"nariz": $Panel/Personalizacion/Tabs/Cara/NarizFila/Valor,
		"labios": $Panel/Personalizacion/Tabs/Cara/LabiosFila/Valor,
		"orejas": $Panel/Personalizacion/Tabs/Cara/OrejasFila/Valor,
		"ojos": $Panel/Personalizacion/Tabs/Cara/OjosFila/Valor,
	}

	_pers = Pers.leer()
	_volcar_controles(_pers)
	for picker in [picker_piel, picker_pelo, picker_camiseta, picker_pantalon, picker_zapatillas]:
		picker.color_changed.connect(_on_pers_cambiada)
	for slider in _sliders.values():
		(slider as HSlider).value_changed.connect(_on_pers_cambiada)
	boton_restablecer.pressed.connect(_on_restablecer_pressed)

	_preview = preview_host.get_node_or_null("userbaseh1")
	Pers.aplicar(_preview, _pers)

	# Asegurar que el campo de texto reciba el foco inmediatamente
	if nick_edit:
		nick_edit.grab_focus()


func set_avatar_scene(scene_path: String) -> void:
	_selected_avatar_scene = scene_path
	## Reemplaza el avatar de preview por el que se eligió en el carrusel.
	var ps: PackedScene = load(scene_path)
	if ps == null:
		return
	var host: Node3D = $Panel/VBox/ViewportContainer/Viewport/Preview3D
	var viejo := host.get_node_or_null("userbaseh1")
	if viejo:
		host.remove_child(viejo)
		viejo.queue_free()
	var inst := ps.instantiate()
	inst.name = "AvatarPreview"
	if inst.get("enable_control") != null:
		inst.enable_control = false
	host.add_child(inst)
	for cam in inst.find_children("*", "Camera3D", true, false):
		(cam as Camera3D).current = false
	for ap in inst.find_children("*", "AnimationPlayer", true, false):
		(ap as AnimationPlayer).play("paradoMJ1_1")
	_preview = inst
	Pers.aplicar(inst, _pers)


func _volcar_controles(datos: Dictionary) -> void:
	_volcando = true
	picker_piel.color = datos["piel"]
	picker_pelo.color = datos["pelo"]
	picker_camiseta.color = datos["camiseta"]
	picker_pantalon.color = datos["pantalon"]
	picker_zapatillas.color = datos["zapatillas"]
	for clave in _sliders:
		(_sliders[clave] as HSlider).value = float(datos[clave])
	_actualizar_valores()
	_volcando = false


func _leer_controles() -> Dictionary:
	var d := {
		"piel": picker_piel.color,
		"pelo": picker_pelo.color,
		"camiseta": picker_camiseta.color,
		"pantalon": picker_pantalon.color,
		"zapatillas": picker_zapatillas.color,
	}
	for clave in _sliders:
		d[clave] = (_sliders[clave] as HSlider).value
	return d


func _on_pers_cambiada(_valor: Variant = null) -> void:
	if _volcando:
		return
	_pers = Pers.normalizar(_leer_controles())
	_actualizar_valores()
	Pers.aplicar(_preview if is_instance_valid(_preview) else null, _pers)


func _on_restablecer_pressed() -> void:
	_volcar_controles(Pers.POR_DEFECTO)
	_on_pers_cambiada()


func _actualizar_valores() -> void:
	for clave in _sliders:
		var etiqueta: Label = _valores[clave]
		if clave == "altura_cm":
			etiqueta.text = "+%d cm" % roundi((_sliders[clave] as HSlider).value)
		else:
			etiqueta.text = "%d%%" % roundi((_sliders[clave] as HSlider).value * 100.0)


func _on_confirmar_pressed() -> void:
	var nick := nick_edit.text.strip_edges()
	if nick.length() < 3:
		error_label.text = "El nick debe tener al menos 3 letras."
		return

	# 1. Guardar local en user://registro.cfg (nick, avatar y aspecto)
	var cfg := ConfigFile.new()
	cfg.set_value("jugador", "nick", nick)
	cfg.set_value("jugador", "avatar_scene", _selected_avatar_scene)
	cfg.save("user://registro.cfg")
	Pers.guardar(_pers)

	# 2. Generar el hash SHA-256 final del registro de avatar
	var raw_str := nick + "|" + _selected_avatar_scene + "|" + str(Time.get_unix_time_from_system())
	var raw_ctx := HashingContext.new()
	raw_ctx.start(HashingContext.HASH_SHA256)
	raw_ctx.update(raw_str.to_utf8_buffer())
	var hash_bytes := raw_ctx.finish()
	var sha256_hash := hash_bytes.hex_encode()

	# 3. Guardar el hash y datos en las rutas test_user_data/user de VSC# y publish_out
	_guardar_hash_usuario(nick, sha256_hash)

	registro_completado.emit(nick)
	# Solo cambia de escena si se ejecuta suelto (sin Boot escuchando).
	if get_tree().current_scene == self:
		get_tree().change_scene_to_file(siguiente_escena)


func _guardar_hash_usuario(nick: String, avatar_hash: String) -> void:
	var dict_data := {
		"usuario": nick,
		"avatar_scene": _selected_avatar_scene,
		"hash_sha256": avatar_hash,
		"generado": Time.get_datetime_string_from_system(true, true),
		"estado": "REGISTRADO"
	}
	var json_str := JSON.stringify(dict_data, "\t")

	# Guardar siempre en el almacenamiento local seguro del visor (user://)
	var file_json := FileAccess.open("user://avatar_hash.json", FileAccess.WRITE)
	if file_json:
		file_json.store_string(json_str)
		file_json.close()

	var file_sha := FileAccess.open("user://avatar.sha256", FileAccess.WRITE)
	if file_sha:
		file_sha.store_string(avatar_hash)
		file_sha.close()

	# Guardar también en test_user_data/user si la carpeta existe localmente
	if DirAccess.dir_exists_absolute("test_user_data/user"):
		var f1 := FileAccess.open("test_user_data/user/avatar_hash.json", FileAccess.WRITE)
		if f1:
			f1.store_string(json_str)
			f1.close()
		var f2 := FileAccess.open("test_user_data/user/avatar.sha256", FileAccess.WRITE)
		if f2:
			f2.store_string(avatar_hash)
			f2.close()


func _on_nick_text_submitted(_new_text: String) -> void:
	_on_confirmar_pressed()
