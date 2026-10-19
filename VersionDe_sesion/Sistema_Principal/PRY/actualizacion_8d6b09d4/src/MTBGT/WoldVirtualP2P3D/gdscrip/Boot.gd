extends Node3D
## Arranque del metaverso:
## 1. CARRUSEL: se elige el avatar (3 chicas / 3 chicos).
## 2. REGISTRO con ese avatar (nick).
## 3. ZONA DEL PORTAL: el avatar camina y lo atraviesa.
## 4. Ventana de carga hasta que la red P2P conecta y aparece MI isla.
## 5. Se cierra la carga y queda el mundo jugable.

const CARRUSEL_SCENE: PackedScene = preload("res://SLCAV/AVATARESCONANIMACION/SLAV.tscn")
const REGISTRO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/registro.tscn")
const PORTAL_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/entornodeprueba.tscn")
const MUNDO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn")

var _carrusel: Node3D
var _registro: Control
var _zona_portal: Node3D
var _avatar_scene := ""
var _nick := ""
var _carga: CanvasLayer
var _carga_label: Label
var _puntos := 0
var _tiempo := 0.0
var _cargando := false


func _ready() -> void:
	_mostrar_carrusel()


func _process(delta: float) -> void:
	if not _cargando or _carga_label == null:
		return
	_tiempo += delta
	if _tiempo >= 0.5:
		_tiempo = 0.0
		_puntos = (_puntos + 1) % 4
		_carga_label.text = "Conectando a la red P2P" + ".".repeat(_puntos)


func _mostrar_carrusel() -> void:
	_carrusel = CARRUSEL_SCENE.instantiate() as Node3D
	add_child(_carrusel)
	_carrusel.connect("avatar_confirmed", _on_avatar_confirmed)


func _on_avatar_confirmed(scene_path: String) -> void:
	_avatar_scene = scene_path
	if _carrusel:
		_carrusel.queue_free()
		_carrusel = null
	_mostrar_registro()


func _mostrar_registro() -> void:
	_registro = REGISTRO_SCENE.instantiate() as Control
	add_child(_registro)
	_registro.connect("registro_completado", _on_registro_completado)
	if _avatar_scene != "" and _registro.has_method("set_avatar_scene"):
		_registro.set_avatar_scene(_avatar_scene)


func _on_registro_completado(nick: String) -> void:
	_nick = nick.strip_edges()
	if _registro:
		_registro.queue_free()
		_registro = null
	_mostrar_zona_portal()


func _mostrar_zona_portal() -> void:
	_zona_portal = PORTAL_SCENE.instantiate() as Node3D
	add_child(_zona_portal)
	if _avatar_scene != "" and _zona_portal.has_method("set_player_avatar"):
		_zona_portal.set_player_avatar(_avatar_scene)
	var portal: Area3D = _zona_portal.get_node("Portal") as Area3D
	portal.connect("portal_cruzado", _on_portal_cruzado)


func _on_portal_cruzado() -> void:
	if _zona_portal:
		_zona_portal.queue_free()
		_zona_portal = null
	_mostrar_carga()
	var mundo: Node3D = MUNDO_SCENE.instantiate() as Node3D
	mundo.name = "ISLA3Dblock"
	if _avatar_scene != "" and mundo.has_method("set_player_avatar"):
		mundo.call("set_player_avatar", _avatar_scene)
	add_child(mundo)
	mundo.connect("mi_isla_lista", _on_mi_isla_lista)


func _mostrar_carga() -> void:
	_cargando = true
	_carga = CanvasLayer.new()
	_carga.layer = 200
	add_child(_carga)
	var fondo := ColorRect.new()
	fondo.set_anchors_preset(Control.PRESET_FULL_RECT)
	fondo.color = Color(0.05, 0.06, 0.09, 1)
	_carga.add_child(fondo)
	var centro := CenterContainer.new()
	centro.set_anchors_preset(Control.PRESET_FULL_RECT)
	_carga.add_child(centro)
	_carga_label = Label.new()
	_carga_label.text = "Conectando a la red P2P"
	_carga_label.add_theme_font_size_override("font_size", 28)
	centro.add_child(_carga_label)


func _on_mi_isla_lista() -> void:
	_cargando = false
	if _carga:
		_carga.queue_free()
		_carga = null
	_mostrar_bienvenida()


## Aviso al llegar a la isla: felicita al jugador y lo saluda por su nick.
func _mostrar_bienvenida() -> void:
	var capa := CanvasLayer.new()
	capa.layer = 100
	add_child(capa)
	var caja := VBoxContainer.new()
	caja.set_anchors_preset(Control.PRESET_CENTER_TOP)
	caja.offset_left = -520.0
	caja.offset_right = 520.0
	caja.offset_top = 36.0
	caja.offset_bottom = 196.0
	caja.add_theme_constant_override("separation", 10)
	capa.add_child(caja)

	caja.add_child(_etiqueta_bienvenida("GRACIAS POR ENTRAR A WOLD VIRTUAL 3D", 20, Color(0.55, 0.8, 0.96, 1.0), 6))
	caja.add_child(_etiqueta_bienvenida("FELICIDADES, CREASTE TU ISLA", 30, Color(0.72, 0.94, 1.0, 1.0), 7))
	caja.add_child(_etiqueta_bienvenida(_texto_bienvenida(), 24, Color(0.62, 0.9, 1.0, 1.0), 6))

	var tween := create_tween()
	tween.tween_interval(4.5)
	tween.tween_property(caja, "modulate:a", 0.0, 1.6)
	tween.tween_callback(capa.queue_free)


func _etiqueta_bienvenida(texto: String, tam: int, color: Color, borde: int) -> Label:
	var etiqueta := Label.new()
	etiqueta.text = texto
	etiqueta.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	etiqueta.add_theme_font_size_override("font_size", tam)
	etiqueta.add_theme_color_override("font_color", color)
	etiqueta.add_theme_color_override("font_outline_color", Color(0.01, 0.05, 0.09, 1.0))
	etiqueta.add_theme_constant_override("outline_size", borde)
	return etiqueta


func _texto_bienvenida() -> String:
	var texto := _saludo()
	if _nick != "":
		texto += ", " + _nick
	return texto


## Saludo según el avatar elegido en el carrusel (AVMJ = mujer, AVH = hombre).
func _saludo() -> String:
	if _avatar_scene.contains("AVMJ"):
		return "BIENVENIDA"
	return "BIENVENIDO"
