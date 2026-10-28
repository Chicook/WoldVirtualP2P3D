extends Node3D
## Arranque del metaverso:
## 1. CARRUSEL: se elige el avatar (24 avatares en 3 turnos de 8).   [solo primera vez]
## 2. REGISTRO con ese avatar (nick).                        [solo primera vez]
## 3. ZONA DEL PORTAL: el avatar camina y lo atraviesa.      [solo primera vez]
## 4. Ventana de carga hasta que la red P2P conecta y aparece MI isla.
## 5. Se cierra la carga y queda el mundo jugable en su isla.
##
## Si el jugador ya tiene registro (user://registro.cfg con avatar_scene y nick),
## entra directamente a su isla con el avatar elegido sin pasar por carrusel ni registro.

const CARRUSEL_SCENE: PackedScene = preload("res://SLCAV/AVATARESCONANIMACION/SLAV.tscn")
const REGISTRO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/registro.tscn")
const PORTAL_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/entornodeprueba.tscn")
const MUNDO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn")
const Sonda = preload("res://gdscrip/Sonda.gd")

var _carrusel: Node3D
var _registro: Control
var _zona_portal: Node3D
var _mundo: Node3D
var _carga: CanvasLayer
var _carga_label: Label
var _carga_texto := "Conectando a la red P2P"
var _avatar_scene := ""
var _nick := ""
var _cargando := false
var _sonda


func _ready() -> void:
	print("================================================================")
	print("[Boot.gd] Arranque WoldVirtualP2P3D iniciado (Godot 4.7.2)")
	print("[Boot.gd] Argumentos motor (get_cmdline_args): ", OS.get_cmdline_args())
	print("[Boot.gd] Argumentos usuario (get_cmdline_user_args): ", OS.get_cmdline_user_args())

	# IMPORTANTE: Boot.gd NO decide el rol de red. El único responsable de resolver
	# y aplicar la topología (Servidor/Cliente + IP/puerto objetivo) es ChunkManager.gd,
	# que lee los mismos argumentos. Aquí solo se registra lo recibido para depurar.
	var _args_net: Array = OS.get_cmdline_args()
	_args_net.append_array(OS.get_cmdline_user_args())
	print("[Boot.gd] Argumentos totales vistos por el motor: ", _args_net)
	print("[Boot.gd] El rol de red (Servidor/Cliente) y la IP objetivo los resuelve ChunkManager.gd.")
	print("================================================================")

	# ── RESET DE SESIÓN (flag escrito por el visor C# al arrancar) ──────────────
	# Si el visor detectó un reset limpio, borramos el registro para que
	# Godot arranque siempre como primera vez (carrusel + registro de nick).
	var reset_flag_path := OS.get_user_data_dir().path_join("reset_flag.txt")
	if FileAccess.file_exists(reset_flag_path):
		if FileAccess.file_exists("user://registro.cfg"):
			DirAccess.remove_absolute(
				OS.get_user_data_dir().path_join("registro.cfg"))
		DirAccess.remove_absolute(reset_flag_path)

	# La sonda existe en todos los peers: el anfitrion responde consultas de
	# plazas y el invitado pregunta antes del carrusel.
	_sonda = Sonda.new()
	_sonda.name = "Sonda"
	add_child(_sonda)

	# Si el usuario ya tiene avatar y nick guardados, entrar directo a su isla
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") == OK:
		var saved_avatar: String = str(cfg.get_value("jugador", "avatar_scene", ""))
		var saved_nick: String   = str(cfg.get_value("jugador", "nick", ""))
		if not saved_avatar.is_empty() and not saved_nick.is_empty():
			_avatar_scene = saved_avatar
			_nick         = saved_nick
			_entrar_a_isla()
			return
	# Primera vez: carrusel -> registro -> portal -> isla
	_mostrar_carrusel()



func _process(delta: float) -> void:
	if not _cargando or _carga_label == null:
		return
	var puntos := int(Time.get_ticks_msec() / 400) % 4
	_carga_label.text = _carga_texto + ".".repeat(puntos)


func _mostrar_carrusel() -> void:
	# Antes de elegir avatar se pregunta al anfitrion que plazas ya estan
	# reservadas; si no hay sesion abierta la consulta vuelve vacia.
	_mostrar_carga("Buscando jugadores en la red")
	var ocupados: Array = await _sonda.consultar()
	_ocultar_carga()
	_carrusel = CARRUSEL_SCENE.instantiate() as Node3D
	if _carrusel.has_method("set_ocupados"):
		_carrusel.call("set_ocupados", ocupados)
	if _carrusel.has_method("abrir_en_primer_hueco"):
		_carrusel.call("abrir_en_primer_hueco")
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
	_entrar_a_isla()


func _entrar_a_isla() -> void:
	_mostrar_carga()
	var mundo: Node3D = MUNDO_SCENE.instantiate() as Node3D
	mundo.name = "ISLA3Dblock"
	_mundo = mundo
	mundo.connect("mi_isla_lista", _on_mi_isla_lista)
	if mundo.has_signal("avatar_asignado"):
		mundo.connect("avatar_asignado", _on_avatar_asignado)
	if _avatar_scene != "" and mundo.has_method("set_player_avatar"):
		mundo.call("set_player_avatar", _avatar_scene)
	add_child(mundo)


func _mostrar_carga(texto: String = "Conectando a la red P2P") -> void:
	_cargando = true
	_carga_texto = texto
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
	_carga_label.text = texto
	_carga_label.add_theme_font_size_override("font_size", 28)
	centro.add_child(_carga_label)


func _ocultar_carga() -> void:
	_cargando = false
	if _carga:
		_carga.queue_free()
		_carga = null
	_carga_label = null


func _on_mi_isla_lista() -> void:
	_ocultar_carga()
	_mostrar_bienvenida()


## El anfitrión cambió el avatar porque la plaza ya estaba reservada.
func _on_avatar_asignado(anterior: String, nuevo: String, turno: int, reciclado: bool) -> void:
	var texto := ""
	if anterior != "":
		texto = "El avatar %s ya estaba en uso. " % anterior
	texto += "Se te asignó %s" % nuevo
	if turno > 0:
		texto += " · Turno %d" % turno
	if reciclado:
		texto += " (avatar reutilizado)"
	_mostrar_aviso(texto)


func _mostrar_aviso(texto: String) -> void:
	var capa := CanvasLayer.new()
	capa.layer = 150
	add_child(capa)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER_TOP)
	panel.offset_left = -360.0
	panel.offset_right = 360.0
	# Debajo del cartel de bienvenida para que ambos textos se lean a la vez.
	panel.offset_top = 210.0
	capa.add_child(panel)
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.03, 0.07, 0.12, 0.94)
	estilo.border_color = Color(0.35, 0.8, 1.0, 0.9)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(8)
	estilo.content_margin_left = 18.0
	estilo.content_margin_right = 18.0
	estilo.content_margin_top = 12.0
	estilo.content_margin_bottom = 12.0
	panel.add_theme_stylebox_override("panel", estilo)
	var etiqueta := Label.new()
	etiqueta.text = texto
	etiqueta.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	etiqueta.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	etiqueta.add_theme_font_size_override("font_size", 18)
	etiqueta.add_theme_color_override("font_color", Color(0.82, 0.94, 1.0, 1.0))
	panel.add_child(etiqueta)
	var tw := create_tween()
	tw.tween_interval(7.0)
	tw.tween_property(capa, "modulate:a", 0.0, 1.0)
	tw.tween_callback(capa.queue_free)


## Aviso al llegar a la isla: felicita al jugador y lo saluda por su nick.
func _mostrar_bienvenida() -> void:
	var capa := CanvasLayer.new()
	capa.layer = 100
	add_child(capa)
	var caja := VBoxContainer.new()
	caja.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.set_anchors_preset(Control.PRESET_CENTER_TOP)
	caja.offset_left = -520.0
	caja.offset_right = 520.0
	caja.offset_top = 36.0
	caja.offset_bottom = 196.0
	caja.add_theme_constant_override("separation", 10)
	capa.add_child(caja)

	var l1 := _etiqueta_bienvenida("GRACIAS POR ENTRAR A WOLD VIRTUAL 3D", 20, Color(0.55, 0.8, 0.96, 1.0), 6)
	l1.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(l1)

	var l2 := _etiqueta_bienvenida("BIENVENIDO A TU ISLA!", 30, Color(0.72, 0.94, 1.0, 1.0), 7)
	l2.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(l2)

	var l3 := _etiqueta_bienvenida(_texto_bienvenida(), 24, Color(0.62, 0.9, 1.0, 1.0), 6)
	l3.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(l3)

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
	if _mundo != null and _mundo.has_method("mi_turno"):
		var turno := int(_mundo.call("mi_turno"))
		if turno > 0:
			texto += "  ·  TURNO %d" % turno
			if bool(_mundo.call("mi_reciclado")):
				texto += " (REUTILIZADO)"
	return texto


## Saludo segun el avatar elegido en el carrusel (AVMJ = mujer, AVH = hombre).
func _saludo() -> String:
	if _avatar_scene.contains("AVMJ"):
		return "BIENVENIDA"
	return "BIENVENIDO"
