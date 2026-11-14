extends Node3D
## Recepción de LucIA en el demo local (discusión #86).
##
## Idea fuerza: «una cuenta = un bloque = un archivo».
## Al crear la cuenta, el servidor de bloques (STM_BKCH) mina un bloque y
## devuelve su hash. **Ese hash ES la cuenta**: no hay contraseña ni frase
## semilla que recordar. El .zip que se descarga es la copia de ese hash; si se
## pierde, se pierde la cuenta, y aquí se dice a la cara.
##
## Esta versión del demo NO valida la conexión por túnel (eso era del visor C#):
## con la cuenta en el PC se entra directamente.

signal recepcion_completada(modo: String)

const ESCENA_LUCIA := preload("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIA_Interfaz.tscn")
const Identidad = preload("res://gdscrip/Identidad.gd")

const RUTA_CUENTA := "user://cuenta.json"
const RUTA_UBICACION := "user://ubicacion_smtplc.json"

const URL_BASE := "http://127.0.0.1:8545"
const URL_ALTA := URL_BASE + "/alta-cuenta"
const URL_ZIP := URL_BASE + "/descargar-cuenta-zip"

const NICK_MIN := 10
const NICK_MAX := 15

var _lucia: Node3D
var _idle: Node
var _boca: Node
var _movimiento: Node
var _modo := "nuevo"          # "nuevo" = sin cuenta · "existente" = cuenta en este PC
var _cuenta: Dictionary = {}  # contenido de user://cuenta.json cuando existe
var _nick_actual := ""
var _creando := false
var _cuenta_creada := false

var _capa: CanvasLayer
var _titulo: Label
var _sub: Label
var _guia: Label
var _estado: Label
var _nick: LineEdit
var _boton: Button
var _hash_label: Label


func _ready() -> void:
	_detectar_modo()
	print("[Recepcion] modo=", _modo, " · nick=", _nick_actual,
		" · cuenta=", FileAccess.file_exists(RUTA_CUENTA))
	_montar_lucia()
	_montar_formulario()
	_saludar()


## Nick de la cuenta, para que el Boot lo use en el carrusel y en el saludo.
func nick_cuenta() -> String:
	return _nick_actual


func _detectar_modo() -> void:
	if not FileAccess.file_exists(RUTA_CUENTA):
		_modo = "nuevo"
		return
	var crudo := FileAccess.get_file_as_string(RUTA_CUENTA)
	var datos = JSON.parse_string(crudo)
	if typeof(datos) != TYPE_DICTIONARY:
		_modo = "nuevo"
		return
	var hash := str(datos.get("cuenta_hash", "")).strip_edges()
	if not _hash_valido(hash):
		# Un cuenta.json corrupto no debe bloquear el arranque: se trata como nuevo.
		_modo = "nuevo"
		return
	_cuenta = datos
	_nick_actual = str(datos.get("nick", "")).strip_edges()
	_modo = "existente"


func _hash_valido(hash: String) -> bool:
	return hash.length() == 64 and hash.is_valid_hex_number()


func _montar_lucia() -> void:
	_lucia = ESCENA_LUCIA.instantiate()
	_lucia.name = "LucIA"
	add_child(_lucia)
	# El GLB de LucIA llega sin material, sin idle y con la boca quieta. Estos
	# cuatro nodos le devuelven el aspecto y la vida que tenía en el taller:
	#   LuciaIdle       -> deja el clip idle en bucle
	#   LuciaBoca       -> mueve el morph de la boca cuando habla
	#   LuciaMovimiento -> gestos con los brazos y caminar
	#   LuciaTexturas   -> aplica la piel sobre la malla
	_idle = preload("res://gdscrip/LuciaIdle.gd").new()
	_idle.name = "LuciaIdle"
	_lucia.add_child(_idle)
	_boca = preload("res://gdscrip/LuciaBoca.gd").new()
	_boca.name = "LuciaBoca"
	_lucia.add_child(_boca)
	_movimiento = preload("res://gdscrip/LuciaMovimiento.gd").new()
	_movimiento.name = "LuciaMovimiento"
	_lucia.add_child(_movimiento)
	var piel := preload("res://gdscrip/LuciaTexturas.gd").new()
	piel.name = "LuciaTexturas"
	_lucia.add_child(piel)
	# Durante la recepción manda el formulario: se ocultan el chat libre y sus
	# rótulos, que se solaparían con el subtítulo. La marca de la esquina se queda.
	for ruta in ["UI/Raiz/Panel", "UI/Raiz/Titulo", "UI/Raiz/Estado"]:
		var nodo := _lucia.get_node_or_null(ruta)
		if nodo:
			(nodo as Control).visible = false


## LucIA saluda al aparecer: un gesto con los brazos y la boca moviéndose.
## Los nodos son opcionales; si el modelo no trae esqueleto o morph, no falla.
func _saludar() -> void:
	await get_tree().create_timer(1.4).timeout
	if not is_inside_tree():
		return
	if is_instance_valid(_boca):
		_boca.call("hablar", 2.2)
	if is_instance_valid(_movimiento):
		_movimiento.call("gesticular")


func _montar_formulario() -> void:
	_capa = CanvasLayer.new()
	_capa.layer = 210
	add_child(_capa)

	var raiz := Control.new()
	raiz.set_anchors_preset(Control.PRESET_FULL_RECT)
	_capa.add_child(raiz)

	_titulo = _etiqueta("LucIA te recibe en Wold Virtual 3D", 26, Color(0.72, 0.94, 1.0, 1.0), 6)
	_titulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	_titulo.set_anchors_preset(Control.PRESET_TOP_LEFT)
	_titulo.offset_left = 40.0
	_titulo.offset_right = 640.0
	_titulo.offset_top = 18.0
	_titulo.offset_bottom = 56.0
	raiz.add_child(_titulo)

	_sub = _etiqueta(_texto_subtitulo(), 15, Color(0.62, 0.82, 1.0, 1.0), 4)
	_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	_sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_sub.set_anchors_preset(Control.PRESET_TOP_LEFT)
	_sub.offset_left = 40.0
	_sub.offset_right = 760.0
	_sub.offset_top = 58.0
	_sub.offset_bottom = 104.0
	raiz.add_child(_sub)

	# La voz de LucIA: guía paso a paso según lo que vaya pasando.
	_guia = _etiqueta("", 14, Color(0.85, 0.95, 1.0, 1.0), 4)
	_guia.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	_guia.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_guia.set_anchors_preset(Control.PRESET_TOP_LEFT)
	_guia.offset_left = 40.0
	_guia.offset_right = 900.0
	_guia.offset_top = 106.0
	_guia.offset_bottom = 146.0
	raiz.add_child(_guia)

	# El formulario ocupa la zona del monitor (izquierda), así LucIA queda entera
	# a la vista. Se ancla en proporción para aguantar cambios de tamaño.
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	panel.anchor_right = 0.31
	panel.anchor_bottom = 0.0
	panel.offset_left = 14.0
	panel.offset_top = 150.0
	panel.offset_right = -6.0
	panel.offset_bottom = 150.0
	raiz.add_child(panel)
	_ajustar_alto(panel)

	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.03, 0.05, 0.10, 0.92)
	estilo.border_color = Color(0.35, 0.8, 1.0, 0.9)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(12)
	estilo.content_margin_left = 20.0
	estilo.content_margin_right = 20.0
	estilo.content_margin_top = 16.0
	estilo.content_margin_bottom = 16.0
	panel.add_theme_stylebox_override("panel", estilo)

	var caja := VBoxContainer.new()
	caja.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	caja.size_flags_vertical = Control.SIZE_EXPAND_FILL
	caja.add_theme_constant_override("separation", 8)
	panel.add_child(caja)

	if _modo == "existente":
		_montar_existente(caja)
	else:
		_montar_nuevo(caja)
	_actualizar_guia()


func _montar_nuevo(caja: VBoxContainer) -> void:
	_nick = LineEdit.new()
	_nick.placeholder_text = "Tu nick (entre %d y %d letras)" % [NICK_MIN, NICK_MAX]
	_nick.max_length = NICK_MAX
	_nick.add_theme_font_size_override("font_size", 16)
	_nick.custom_minimum_size = Vector2(0, 42)
	_nick.text_submitted.connect(func(_t: String): _crear_cuenta())
	_nick.text_changed.connect(func(_t: String): _actualizar_guia())
	caja.add_child(_nick)

	var aviso := _etiqueta(
		"Validación 1 de 2 · Tu cuenta será el hash de un bloque: sin contraseña y sin " +
		"frase semilla. Al crearla podrás descargar tu archivo de cuenta.",
		13, Color(0.62, 0.82, 1.0, 1.0), 2)
	aviso.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(aviso)

	# Hueco reservado para el hash: se rellena al crear la cuenta. Reservarlo
	# desde el principio evita recolocar nodos (y el error de «already has a parent»).
	_hash_label = _etiqueta("", 11, Color(0.55, 0.75, 0.95, 1.0), 2)
	_hash_label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	_hash_label.visible = false
	caja.add_child(_hash_label)

	_estado = _etiqueta("", 14, Color(1.0, 0.8, 0.4, 1.0), 3)
	_estado.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_estado.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(_estado)

	_boton = Button.new()
	_boton.text = "Crear mi cuenta"
	_boton.add_theme_font_size_override("font_size", 19)
	_boton.custom_minimum_size = Vector2(0, 48)
	_boton.pressed.connect(_crear_cuenta)
	caja.add_child(_boton)

	if _nick:
		_nick.grab_focus()


func _montar_existente(caja: VBoxContainer) -> void:
	var saludo := _etiqueta("Hola de nuevo, %s." % _nick_actual, 18, Color(0.72, 0.94, 1.0, 1.0), 3)
	saludo.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(saludo)

	var nota := _etiqueta(
		"Tu cuenta ya está en este PC. No hay contraseña que escribir: el hash " +
		"del bloque es la cuenta.",
		13, Color(0.62, 0.82, 1.0, 1.0), 2)
	nota.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(nota)

	_hash_label = _etiqueta(str(_cuenta.get("cuenta_hash", "")), 11, Color(0.55, 0.75, 0.95, 1.0), 2)
	_hash_label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	caja.add_child(_hash_label)

	_estado = _etiqueta("", 13, Color(1.0, 0.8, 0.4, 1.0), 3)
	_estado.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_estado.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(_estado)

	_boton = Button.new()
	_boton.text = "Entrar al mundo"
	_boton.add_theme_font_size_override("font_size", 19)
	_boton.custom_minimum_size = Vector2(0, 48)
	_boton.pressed.connect(_entrar)
	caja.add_child(_boton)

	# Acceso al carrusel para cambiar de avatar: es donde aparecen las variantes
	# generadas a partir del avatar propio.
	var boton_avatar := Button.new()
	boton_avatar.text = "Elegir otro avatar"
	boton_avatar.add_theme_font_size_override("font_size", 14)
	boton_avatar.custom_minimum_size = Vector2(0, 36)
	boton_avatar.pressed.connect(func(): recepcion_completada.emit("avatar"))
	caja.add_child(boton_avatar)


func _texto_subtitulo() -> String:
	if _modo == "existente":
		return "Te recibo otra vez. Tu cuenta vive en este PC: entramos a tu isla."
	return ("Es tu primera vez. Validación 1 de 2: creo tu cuenta (un bloque = un hash). " +
		"Después eliges avatar: la validación 2 es tu avatar propio.")


## La voz de LucIA: guía contextual. Con cuenta, se pone a disposición; sin
## cuenta, explica el alta paso a paso y reacciona a lo que escribe el jugador.
func _actualizar_guia() -> void:
	if _guia == null:
		return
	if _modo == "existente":
		_guia.text = ("LucIA: bienvenido de nuevo, %s. Estoy a tu disposición: entra cuando " +
			"quieras o pulsa «Elegir otro avatar» para cambiar de aspecto.") % _nick_actual
		_guia.add_theme_color_override("font_color", Color(0.72, 0.95, 0.82, 1.0))
		return
	_guia.add_theme_color_override("font_color", Color(0.85, 0.95, 1.0, 1.0))
	var nick := _nick.text.strip_edges() if _nick else ""
	if _cuenta_creada:
		_guia.text = ("LucIA: cuenta creada. Guarda tu .zip —es tu cuenta— y pulsa " +
			"«Entrar al mundo»; después eliges avatar.")
	elif _creando:
		_guia.text = "LucIA: estoy pidiendo tu bloque a la cadena…"
	elif nick.is_empty():
		_guia.text = ("LucIA: paso 1 de 2 · escribe un nick de %d a %d letras. " +
			"Lo compruebo mientras escribes.") % [NICK_MIN, NICK_MAX]
	elif nick.length() < NICK_MIN:
		_guia.text = "LucIA: te faltan %d letras para el mínimo de %d." % [NICK_MIN - nick.length(), NICK_MIN]
	elif nick.length() > NICK_MAX:
		_guia.text = "LucIA: el nick no puede pasar de %d letras." % NICK_MAX
	else:
		_guia.text = ("LucIA: nick correcto. Paso 2: pulsa «Crear mi cuenta» y mino tu bloque " +
			"en la cadena.")


func _ajustar_alto(panel: PanelContainer) -> void:
	await get_tree().process_frame
	if not is_instance_valid(panel):
		return
	var alto := panel.get_combined_minimum_size().y
	var disponible := get_viewport().get_visible_rect().size.y - panel.offset_top - 12.0
	panel.offset_bottom = panel.offset_top + clampf(alto, 140.0, maxf(disponible, 140.0))


func _entrar() -> void:
	recepcion_completada.emit(_modo)


# ─── Alta de cuenta ──────────────────────────────────────────────────────────

func _crear_cuenta() -> void:
	if _creando:
		return
	var nick := _nick.text.strip_edges() if _nick else ""
	if nick.length() < NICK_MIN:
		_estado.text = "El nick necesita al menos %d letras (tienes %d)." % [NICK_MIN, nick.length()]
		return
	if nick.length() > NICK_MAX:
		_estado.text = "El nick no puede pasar de %d letras." % NICK_MAX
		return

	_creando = true
	_boton.disabled = true
	_estado.text = "Creando tu cuenta: la cadena está minando el bloque…"
	_actualizar_guia()

	var payload := {
		"nick": nick,
		"huella": Identidad.asegurar_identidad(),
	}
	var ubicacion := _leer_ubicacion_hash()
	if not ubicacion.is_empty():
		payload["ubicacion_hash"] = ubicacion

	var http := HTTPRequest.new()
	http.timeout = 8.0
	add_child(http)
	http.request_completed.connect(_on_alta_completada.bind(http))
	var err := http.request(URL_ALTA, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		http.queue_free()
		_creando = false
		_boton.disabled = false
		_estado.text = "No se pudo contactar con el servidor de cuentas (error %d)." % err


func _on_alta_completada(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, http: HTTPRequest) -> void:
	http.queue_free()
	_creando = false
	_boton.disabled = false
	_actualizar_guia()

	if result != HTTPRequest.RESULT_SUCCESS:
		_estado.text = "El servidor de cuentas no responde. Arranca el demo con .\\demo_local.ps1"
		return

	var datos = JSON.parse_string(body.get_string_from_utf8())
	if typeof(datos) != TYPE_DICTIONARY:
		_estado.text = "Respuesta del servidor ilegible (código %d)." % code
		return

	if code == 201:
		var hash := str(datos.get("cuenta_hash", "")).strip_edges()
		if not _hash_valido(hash):
			_estado.text = "La cadena no devolvió un hash de cuenta válido."
			return
		var nick := str(datos.get("nick", _nick.text if _nick else "")).strip_edges()
		if not _guardar_cuenta(nick, hash):
			# Sin guardar no hay cuenta: el hash solo existe en este PC, así que
			# no se deja continuar; se muestra para que se apunte a mano.
			if _nick:
				_nick.visible = false
			if _hash_label:
				_hash_label.text = hash
				_hash_label.visible = true
			if _boton:
				_boton.visible = false
			_estado.text = ("ATENCIÓN: la cadena creó tu cuenta, pero no se pudo guardar en " +
				"este PC (permisos de user://). Apunta este hash a mano: es tu única copia.")
			return
		_nick_actual = nick
		_descargar_zip(hash)
		return

	if code == 409:
		_estado.text = ("Este PC ya tiene una cuenta en la cadena. Si perdiste el archivo " +
			"de cuenta, esta demo no puede recuperarla (así está diseñado): reinicia con -Reset.")
		return
	if code == 429:
		var espera := int(datos.get("reintentar_en_segundos", 0))
		_estado.text = "Esta ubicación está en espera. Reintenta en %d s." % espera
		return
	_estado.text = str(datos.get("error", "No se pudo crear la cuenta (código %d)." % code))


func _guardar_cuenta(nick: String, hash: String) -> bool:
	var datos := {
		"nick": nick,
		"cuenta_hash": hash,
		"red": "WoldVirtualP2P3D",
		"fecha_alta": Time.get_datetime_string_from_system(true, true),
	}
	var f := FileAccess.open(RUTA_CUENTA, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(JSON.stringify(datos, "\t"))
	f.close()
	return true


## Descarga el .zip de la cuenta recién minada y lo deja en user://.
## Ese archivo es la copia de seguridad del hash: sin él no hay cuenta.
func _descargar_zip(hash: String) -> void:
	_estado.text = "Cuenta creada. Descargando tu archivo de cuenta…"
	var http := HTTPRequest.new()
	http.timeout = 20.0
	add_child(http)
	http.request_completed.connect(_on_zip_descargado.bind(http, hash))
	var err := http.request("%s?cuenta_hash=%s" % [URL_ZIP, hash])
	if err != OK:
		http.queue_free()
		_mostrar_cuenta_creada(hash, "")


func _on_zip_descargado(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, http: HTTPRequest, hash: String) -> void:
	http.queue_free()
	if result != HTTPRequest.RESULT_SUCCESS or code != 200 or body.is_empty():
		_mostrar_cuenta_creada(hash, "")
		return
	var nombre := "cuenta_%s.zip" % hash.substr(0, 16)
	var f := FileAccess.open("user://" + nombre, FileAccess.WRITE)
	if f:
		f.store_buffer(body)
		f.close()
		_mostrar_cuenta_creada(hash, nombre)
	else:
		_mostrar_cuenta_creada(hash, "")


func _mostrar_cuenta_creada(hash: String, archivo: String) -> void:
	_cuenta_creada = true
	if _nick:
		_nick.visible = false
	if _hash_label:
		_hash_label.text = hash
		_hash_label.visible = true

	if archivo.is_empty():
		_estado.text = ("Cuenta creada (validación 1 de 2). No se pudo descargar el .zip: usa " +
			"el hash de arriba como tu cuenta y guárdalo a mano.")
	else:
		_estado.text = ("Cuenta creada (validación 1 de 2) y archivo guardado: %s\n" % archivo +
			"Guárdalo fuera de este PC. Si lo pierdes, pierdes la cuenta.")

	_boton.text = "Entrar al mundo"
	_boton.pressed.disconnect(_crear_cuenta)
	_boton.pressed.connect(_entrar)
	_actualizar_guia()


func _leer_ubicacion_hash() -> String:
	if not FileAccess.file_exists(RUTA_UBICACION):
		return ""
	var crudo := FileAccess.get_file_as_string(RUTA_UBICACION)
	var datos = JSON.parse_string(crudo)
	if typeof(datos) != TYPE_DICTIONARY:
		return ""
	var h := str(datos.get("ubicacion_hash", "")).strip_edges().to_lower()
	if h.length() != 64 or not h.is_valid_hex_number():
		return ""
	return h


func _etiqueta(texto: String, tam: int, color: Color, borde: int) -> Label:
	var e := Label.new()
	e.text = texto
	e.add_theme_font_size_override("font_size", tam)
	e.add_theme_color_override("font_color", color)
	e.add_theme_color_override("font_outline_color", Color(0.01, 0.05, 0.09, 1.0))
	e.add_theme_constant_override("outline_size", borde)
	return e
