extends Node3D
## Arranque del metaverso (demo local, discusión #86):
## 0. RECEPCIÓN LUCIA: crea la cuenta (un bloque = un hash) o saluda al que ya la
##    tiene en este PC. No hay contraseña, ni semilla, ni validación de túnel.
## 1. CARRUSEL: se elige el avatar (24 avatares en 3 turnos de 8).   [solo primera vez]
## 2. REGISTRO con ese avatar (el nick ya viene fijado por la cuenta).
## 3. ZONA DEL PORTAL: el avatar camina y lo atraviesa.      [solo primera vez]
## 4. Ventana de carga hasta que aparece MI isla.
## 5. Se cierra la carga y queda el mundo jugable en su isla.
##
## Si ya hay cuenta (user://cuenta.json) y avatar (user://registro.cfg),
## se entra directamente a la isla sin pasar por recepción, carrusel ni registro.

const CARRUSEL_SCENE: PackedScene = preload("res://SLCAV/AVATARESCONANIMACION/SLAV.tscn")
const REGISTRO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/registro.tscn")
const PORTAL_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/entornodeprueba.tscn")
const MUNDO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn")
const Sonda = preload("res://gdscrip/Sonda.gd")
const Turnos = preload("res://gdscrip/Turnos.gd")
const LuciaRecepcion = preload("res://gdscrip/LuciaRecepcion.gd")
const Firma = preload("res://gdscrip/AvatarFirma.gd")
const Pers = preload("res://gdscrip/Personalizacion.gd")

const URL_AVATAR := "http://127.0.0.1:8545/avatar-original"

var _carrusel: Node3D
var _registro: Control
var _zona_portal: Node3D
var _mundo: Node3D
var _recepcion: Node3D
var _carga: CanvasLayer
var _carga_label: Label
var _carga_texto := "Conectando a la red P2P"
var _avatar_scene := ""
var _nick := ""
var _cargando := false
var _espera_isla: Timer
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

	# «Actualización de cuenta» desde el visor: este arranque ya entra en la
	# recepción de LucIA, así que solo se consume la marca y se deja constancia.
	var marca_cuenta := OS.get_user_data_dir().path_join("abrir_recepcion.flag")
	if FileAccess.file_exists(marca_cuenta):
		DirAccess.remove_absolute(marca_cuenta)
		print("[Boot] Actualización de cuenta solicitada desde el visor")

	# La sonda existe en todos los peers: el anfitrion responde consultas de
	# plazas y el invitado pregunta antes del carrusel.
	_sonda = Sonda.new()
	_sonda.name = "Sonda"
	add_child(_sonda)

	# LucIA recibe SIEMPRE primero (anfitriona): saluda al registrado y le dice
	# cómo iniciar sesión en esta versión, o guía el registro del nuevo.
	#
	# Excepción de autoprueba: el visor ejecuta el motor sin nadie delante y
	# necesita que la isla y el 8911 arranquen. Solo `--startup-selftest` pasa
	# `--sin-recepcion`; una sesión normal nunca lo lleva.
	if _sin_recepcion():
		print("[Boot] --sin-recepcion: entrada directa con el perfil guardado")
		_continuar_registrado()
		return

	_mostrar_lucia_recepcion()


## ¿Arranca para la autoprueba del visor (sin recepción)?
func _sin_recepcion() -> bool:
	var args: Array = OS.get_cmdline_args()
	args.append_array(OS.get_cmdline_user_args())
	return args.has("--sin-recepcion")


## El registro del jugador (user://avatar_hash.json) guarda la escena que eligió
## al registrarse. Si `avatar_scene` quedó con un sustituto de turno, se vuelve a
## esa elección una sola vez por perfil (`avatar_reparado`), para no pisar un
## cambio de avatar posterior.
func _reparar_avatar(cfg: ConfigFile, guardado: String, nick: String) -> String:
	if bool(cfg.get_value("jugador", "avatar_reparado", false)):
		return guardado
	if not FileAccess.file_exists("user://avatar_hash.json"):
		return guardado
	var datos = JSON.parse_string(FileAccess.get_file_as_string("user://avatar_hash.json"))
	if typeof(datos) != TYPE_DICTIONARY:
		return guardado
	var registro: Dictionary = datos
	if str(registro.get("estado", "")) != "REGISTRADO":
		return guardado
	if str(registro.get("usuario", "")) != nick:
		return guardado
	var elegido := str(registro.get("avatar_scene", ""))
	if Turnos.indice(elegido) < 0:
		return guardado
	if elegido != guardado:
		print("[Boot] avatar reparado desde el registro: ", elegido.get_file())
		guardado = elegido
		cfg.set_value("jugador", "avatar_scene", elegido)
	cfg.set_value("jugador", "avatar_reparado", true)
	cfg.save("user://registro.cfg")
	return guardado



func _process(delta: float) -> void:
	if not _cargando or _carga_label == null:
		return
	var puntos := int(Time.get_ticks_msec() / 400) % 4
	_carga_label.text = _carga_texto + ".".repeat(puntos)


func _mostrar_lucia_recepcion() -> void:
	_recepcion = LuciaRecepcion.new()
	_recepcion.name = "LuciaRecepcion"
	add_child(_recepcion)
	_recepcion.recepcion_completada.connect(_on_recepcion_completada)


func _on_recepcion_completada(modo: String) -> void:
	# El nick sale de la cuenta (hash del bloque), no de un segundo formulario.
	if _recepcion and _recepcion.has_method("nick_cuenta"):
		var nick := str(_recepcion.call("nick_cuenta")).strip_edges()
		if not nick.is_empty():
			_nick = nick
	if _recepcion:
		_recepcion.queue_free()
		_recepcion = null
	if modo == "existente":
		_continuar_registrado()
	else:
		_mostrar_carrusel()



## Un jugador ya registrado entra a su isla con el avatar guardado.
func _continuar_registrado() -> void:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") == OK:
		var saved_avatar: String = str(cfg.get_value("jugador", "avatar_scene", ""))
		var saved_nick: String   = str(cfg.get_value("jugador", "nick", ""))
		if not saved_avatar.is_empty() and not saved_nick.is_empty():
			_avatar_scene = _reparar_avatar(cfg, saved_avatar, saved_nick)
			_nick         = saved_nick
			_entrar_a_isla()
			return
	# Sin avatar guardado (borde): pasa por el carrusel igualmente.
	_mostrar_carrusel()


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
	# El nick ya lo fijó la cadena al crear la cuenta: aquí no se vuelve a pedir.
	if _nick != "" and _registro.has_method("set_nick"):
		_registro.call("set_nick", _nick, true)
	if _avatar_scene != "" and _registro.has_method("set_avatar_scene"):
		_registro.set_avatar_scene(_avatar_scene)


func _on_registro_completado(nick: String) -> void:
	_nick = nick.strip_edges()
	if _registro:
		_registro.queue_free()
		_registro = null
	_registrar_avatar_si_original()
	_mostrar_zona_portal()


## Si el avatar se diferenció del base lo suficiente, se ancla en la cadena y
## alimenta las neuronas de LucIA (bloque AVATAR_ORIGINAL). No bloquea el flujo:
## si el servidor no está, el jugador entra igual y solo se registra en consola.
func _registrar_avatar_si_original() -> void:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") != OK:
		return
	if not bool(cfg.get_value("jugador", "avatar_original", false)):
		return
	var firma := str(cfg.get_value("jugador", "avatar_firma", ""))
	var delta := float(cfg.get_value("jugador", "avatar_delta", 0.0))
	var hash := _hash_cuenta()
	if hash.length() != 64 or firma.length() != 64:
		return
	var payload := {
		"cuenta_hash": hash,
		"nick": _nick,
		"avatar_firma": firma,
		"avatar_delta": delta,
	}
	var http := HTTPRequest.new()
	http.timeout = 10.0
	add_child(http)
	http.request_completed.connect(_on_avatar_registrado.bind(http, firma))
	var err := http.request(URL_AVATAR, ["Content-Type: application/json"],
		HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		http.queue_free()


func _hash_cuenta() -> String:
	if not FileAccess.file_exists("user://cuenta.json"):
		return ""
	var datos = JSON.parse_string(FileAccess.get_file_as_string("user://cuenta.json"))
	if typeof(datos) != TYPE_DICTIONARY:
		return ""
	return str(datos.get("cuenta_hash", "")).strip_edges()


func _on_avatar_registrado(result: int, code: int, _headers: PackedStringArray,
		body: PackedByteArray, http: HTTPRequest, firma: String) -> void:
	http.queue_free()
	if result != HTTPRequest.RESULT_SUCCESS or code != 201:
		print("[Boot] avatar propio no registrado (código ", code, ")")
		return
	var datos = JSON.parse_string(body.get_string_from_utf8())
	if typeof(datos) != TYPE_DICTIONARY:
		return
	var indice := int(datos.get("indice_bloque", 0))
	print("[Boot] avatar propio registrado en el bloque #", indice)
	_guardar_variantes(firma)
	_mostrar_aviso("Cuenta validada (2 de 2) · avatar propio en el bloque #%d." % indice)


## Deja 3 variantes deterministas del avatar propio en user://avatares_variantes.json.
## El carrusel las reconstruye con la personalización ya resuelta: aquí se guarda
## el aspecto completo (tintes en HTML y campos numéricos), no la imagen.
func _guardar_variantes(firma: String) -> void:
	var cfg := ConfigFile.new()
	cfg.load("user://registro.cfg")
	var base_scene := str(cfg.get_value("jugador", "avatar_scene", ""))
	var pers: Dictionary = Pers.leer()
	var lista := []
	for i in 3:
		var v: Dictionary = Firma.variante(pers, firma, i)
		lista.append({
			"indice": i,
			"avatar_firma": Firma.firma(v),
			"avatar_delta": Firma.delta_base(v),
			"base_scene": base_scene,
			"pers": _pers_a_json(v),
		})
	var salida := {
		"origen_firma": firma,
		"cuenta_hash": _hash_cuenta(),
		"base_scene": base_scene,
		"pers_origen": _pers_a_json(pers),
		"variantes": lista,
	}
	var f := FileAccess.open("user://avatares_variantes.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(salida, "\t"))
		f.close()


## Aspecto a JSON: los tintes como HTML (#rrggbb) y los campos como número.
func _pers_a_json(pers: Dictionary) -> Dictionary:
	var salida := {}
	for clave in Pers.ORDEN:
		var color: Color = pers.get(clave, Color.WHITE)
		salida[clave] = color.to_html(false)
	for clave in Pers.CAMPOS:
		salida[clave] = float(pers.get(clave, Pers.POR_DEFECTO[clave]))
	return salida


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
	_esperar_isla(25.0)


## Red de seguridad: si el mundo no confirma la isla (red, assets), no dejamos al
## jugador mirando una pantalla de carga para siempre. El mundo ya está montado:
## se retira la carga y se avisa.
func _esperar_isla(segundos: float) -> void:
	if _espera_isla and is_instance_valid(_espera_isla):
		_espera_isla.queue_free()
	_espera_isla = Timer.new()
	_espera_isla.one_shot = true
	_espera_isla.wait_time = segundos
	_espera_isla.timeout.connect(_on_espera_isla_agotada)
	add_child(_espera_isla)
	_espera_isla.start()


func _on_espera_isla_agotada() -> void:
	if not _cargando:
		return
	_ocultar_carga()
	_mostrar_aviso("Tu isla no confirmó a tiempo. El mundo sigue abierto; revisa la red P2P.")


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
	if _espera_isla and is_instance_valid(_espera_isla):
		_espera_isla.stop()
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
