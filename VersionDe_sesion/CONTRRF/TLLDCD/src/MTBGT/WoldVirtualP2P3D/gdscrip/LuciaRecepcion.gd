extends Node3D
## LucIA anfitriona: recibe al jugador ANTES del carrusel (nuevo diseño).
## Reutiliza la escena LucIA_Interfaz.tscn (personaje, oficina, holograma y voz)
## y le superpone el formulario de registro / inicio de sesión.
## LucIA ahora es el HOST: genera el link de validación de conexión.
## Emite `recepcion_completada("nuevo" | "existente")` cuando el jugador confirma.

signal recepcion_completada(modo: String)
signal validacion_conexion_solicitada()  # Nueva señal para pedir validación al visor C#

const ESCENA_LUCIA := preload("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIA_Interfaz.tscn")
const Identidad = preload("res://gdscrip/Identidad.gd")

const RUTA_CUENTA := "user://cuenta.json"
const RUTA_REGISTRO := "user://registro.cfg"
## Firma de ubicación física (SMTPLC) que el visor C# deja en user://. Godot no
## puede calcularla (ARP del gateway + Wi-Fi ambiental son del visor): solo la lee.
const RUTA_UBICACION := "user://ubicacion_smtplc.json"
const RUTA_VALIDACION := "user://validacion_conexion.json"
const BKSVCB_ALTA := "http://127.0.0.1:8545/alta-cuenta"
const BKSVCB_MIGRAR := "http://127.0.0.1:8545/migrar-cuenta"
const BKSVCB_DESCARGAR := "http://127.0.0.1:8545/descargar-cuenta-zip"

var _lucia: Node3D
var _modo := "nuevo"
var _cuenta := {}
var _validacion_pendiente := false  # Flag para saber si esperamos validación de conexión

var _capa: CanvasLayer
var _titulo: Label
var _sub: Label
var _estado: Label
var _nick: LineEdit
var _boton: Button
var _boton_sec: Button
var _link_validacion: Label  # Nuevo campo para mostrar el link de validación


func _ready() -> void:
	_detectar_modo()
	_montar_lucia()
	_montar_formulario()


## Decide el modo según lo que ya existe en el PC del jugador.
func _detectar_modo() -> void:
	if FileAccess.file_exists(RUTA_CUENTA):
		_modo = "existente"
		var crudo := FileAccess.get_file_as_string(RUTA_CUENTA)
		var datos = JSON.parse_string(crudo)
		if typeof(datos) == TYPE_DICTIONARY:
			_cuenta = datos
	elif FileAccess.file_exists(RUTA_REGISTRO):
		# Cuenta antigua (llave + hash de PC + semilla): modo migración.
		_modo = "existente"
	else:
		_modo = "nuevo"


func _montar_lucia() -> void:
	_lucia = ESCENA_LUCIA.instantiate()
	_lucia.name = "LucIA"
	add_child(_lucia)
	# Durante la recepción manda el formulario: se ocultan el chat libre y sus
	# rótulos (título y estado), que se solaparían con el subtítulo centrado.
	# La marca de la esquina (WoldVirtualP2P3D) se conserva.
	for ruta in ["UI/Raiz/Panel", "UI/Raiz/Titulo", "UI/Raiz/Estado"]:
		var n := _lucia.get_node_or_null(ruta)
		if n:
			(n as Control).visible = false


func _montar_formulario() -> void:
	_capa = CanvasLayer.new()
	_capa.layer = 210
	add_child(_capa)

	var raiz := Control.new()
	raiz.set_anchors_preset(Control.PRESET_FULL_RECT)
	_capa.add_child(raiz)

	_titulo = _etiqueta("LucIA te recibe en Wold Virtual 3D", 30, Color(0.72, 0.94, 1.0, 1.0), 7)
	_titulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_titulo.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_titulo.offset_left = -420.0
	_titulo.offset_right = 420.0
	_titulo.offset_top = 24.0
	_titulo.offset_bottom = 64.0
	raiz.add_child(_titulo)

	_sub = _etiqueta(_texto_subtitulo(), 18, Color(0.62, 0.82, 1.0, 1.0), 4)
	_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_sub.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_sub.offset_left = -420.0
	_sub.offset_right = 420.0
	_sub.offset_top = 66.0
	_sub.offset_bottom = 120.0
	raiz.add_child(_sub)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	panel.offset_left = -340.0
	panel.offset_right = 340.0
	panel.offset_top = -220.0  # Aumentado para acomodar el link de validación
	panel.offset_bottom = -28.0
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
	raiz.add_child(panel)

	var caja := VBoxContainer.new()
	caja.add_theme_constant_override("separation", 10)
	panel.add_child(caja)

	if _modo == "nuevo":
		_nick = LineEdit.new()
		_nick.placeholder_text = "Escribe tu nick (mínimo 3 letras)"
		_nick.add_theme_font_size_override("font_size", 18)
		_nick.custom_minimum_size = Vector2(0, 46)
		caja.add_child(_nick)

		_estado = _etiqueta("", 15, Color(1.0, 0.8, 0.4, 1.0), 3)
		_estado.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_estado.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		caja.add_child(_estado)

		_boton = Button.new()
		_boton.text = _texto_boton()
		_boton.add_theme_font_size_override("font_size", 19)
		_boton.custom_minimum_size = Vector2(0, 48)
		_boton.pressed.connect(_on_boton_principal)
		caja.add_child(_boton)

	if _modo == "existente":
		# Link de validación de conexión (generado por LucIA como host)
		_link_validacion = _etiqueta("Link de validación: generando...", 14, Color(0.45, 0.95, 0.55, 1.0), 2)
		_link_validacion.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_link_validacion.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		caja.add_child(_link_validacion)

		_estado = _etiqueta("", 15, Color(1.0, 0.8, 0.4, 1.0), 3)
		_estado.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_estado.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		caja.add_child(_estado)

		_boton = Button.new()
		_boton.text = "Validar conexión"
		_boton.add_theme_font_size_override("font_size", 19)
		_boton.custom_minimum_size = Vector2(0, 48)
		_boton.pressed.connect(_on_validar_conexion)
		caja.add_child(_boton)

		if not FileAccess.file_exists(RUTA_CUENTA):
			# Cuenta antigua: además del inicio de sesión se ofrece la migración.
			_boton_sec = Button.new()
			_boton_sec.text = "Migrar mi cuenta antigua al hash único"
			_boton_sec.add_theme_font_size_override("font_size", 16)
			_boton_sec.custom_minimum_size = Vector2(0, 44)
			_boton_sec.pressed.connect(_on_migrar)
			caja.add_child(_boton_sec)

	if _nick:
		_nick.grab_focus()

	# Si existe cuenta nueva, mostrar el link de validación
	if _modo == "existente" and not _cuenta.is_empty():
		_generar_link_validacion()


func _texto_subtitulo() -> String:
	if _modo == "existente":
		if _cuenta.is_empty():
			return "Ya tienes cuenta aquí. Esta versión usa un único hash de cuenta: te guío para iniciar sesión o migrar la antigua."
		return "Te saludo de nuevo, %s. Para iniciar sesión en esta versión, valida tu conexión con el link generado por LucIA." % str(_cuenta.get("nick", "jugador"))
	return "Es tu primera vez: yo te acompaño a crear tu cuenta y luego eliges tu avatar."


func _texto_boton() -> String:
	return "Crear mi cuenta" if _modo == "nuevo" else "Validar conexión"


func _on_boton_principal() -> void:
	if _modo == "nuevo":
		_crear_cuenta()
	else:
		_on_validar_conexion()


## Genera el link de validación de conexión (LucIA como host)
func _generar_link_validacion() -> void:
	if _link_validacion == null:
		return

	var cuenta_hash := str(_cuenta.get("cuenta_hash", ""))
	if cuenta_hash.is_empty():
		_link_validacion.text = "Error: hash de cuenta no encontrado"
		return

	# Generar un token temporal basado en el hash de cuenta y timestamp
	var timestamp := str(Time.get_unix_time_from_system())
	var raw_str := cuenta_hash + "|" + timestamp
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(raw_str.to_utf8_buffer())
	var token_bytes := ctx.finish()
	var token := token_bytes.hex_encode()

	# Guardar el token en un archivo para que el visor C# lo use
	var datos_validacion := {
		"cuenta_hash": cuenta_hash,
		"token": token,
		"timestamp": timestamp,
		"expira": str(int(Time.get_unix_time_from_system()) + 3600)  # 1 hora
	}
	var f := FileAccess.open(RUTA_VALIDACION, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(datos_validacion, "\t"))
		f.close()

	_link_validacion.text = "Link de validación: lucia://%s (token: %s...)" % [cuenta_hash, token.substr(0, 16)]


## Valida la conexión con el visor C# usando el túnel SSH efímero
func _on_validar_conexion() -> void:
	if _estado == null:
		return

	_estado.text = "Solicitando validación de conexión..."
	_boton.disabled = true
	_validacion_pendiente = true

	# Emitir señal para que el visor C# inicie el túnel SSH
	validacion_conexion_solicitada.emit()

	# Esperar respuesta del visor C# (se lee el archivo validacion_resultado.json)
	# Esto se maneja en un timer o polling
	var t := Timer.new()
	t.wait_time = 0.5
	t.autostart = true
	t.timeout.connect(_poll_validacion_resultado.bind(t))
	add_child(t)


## Poll para verificar si el visor C# completó la validación
func _poll_validacion_resultado(timer: Timer) -> void:
	var ruta_resultado := "user://validacion_resultado.json"
	if FileAccess.file_exists(ruta_resultado):
		timer.queue_free()
		var crudo := FileAccess.get_file_as_string(ruta_resultado)
		var datos = JSON.parse_string(crudo)
		if typeof(datos) == TYPE_DICTIONARY:
			var exito := datos.get("exito", false)
			var mensaje := datos.get("mensaje", "")
			if exito:
				_estado.text = "Conexión validada correctamente"
				_boton.text = "Entrar al mundo"
				_boton.pressed.disconnect(_on_validar_conexion)
				_boton.pressed.connect(_on_entrar_mundo)
				_boton.disabled = false
				_validacion_pendiente = false
			else:
				_estado.text = "Error de validación: %s" % mensaje
				_boton.disabled = false
				_validacion_pendiente = false
	else:
		# Continuar polling
		if _validacion_pendiente:
			return
		else:
			timer.queue_free()


## Pasar al mundo después de validar conexión
func _on_entrar_mundo() -> void:
	recepcion_completada.emit("existente")


func _crear_cuenta() -> void:
	var nick := _nick.text.strip_edges() if _nick else ""
	if nick.length() < 3:
		_estado.text = "El nick debe tener al menos 3 letras."
		return
	_mintar_cuenta(nick)


## Pide el alta a la blockchain local (un bloque = una cuenta). Es el contrato
## de F9: el servidor devuelve el hash único y lo guardamos en cuenta.json.
## Si el visor dejó la firma SMTPLC, viaja como ubicacion_hash para la cuota por
## ubicación; si no, el alta sigue (el servidor aún aplica «un bloque por PC»).
func _mintar_cuenta(nick: String) -> void:
	_boton.disabled = true
	var huella := Identidad.asegurar_identidad()
	var ubicacion := _leer_ubicacion_hash()
	var payload := {"nick": nick, "huella": huella}
	if ubicacion.is_empty():
		_estado.text = "Generando tu cuenta (sin verificación de ubicación física)…"
	else:
		payload["ubicacion_hash"] = ubicacion
		_estado.text = "Generando tu cuenta en la cadena…"
	var http := HTTPRequest.new()
	http.timeout = 8.0
	add_child(http)
	http.request_completed.connect(_on_alta_completada.bind(http))
	var err := http.request(BKSVCB_ALTA, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		http.queue_free()
		_estado.text = "El servidor de cuentas no responde (error %d)." % err
		_boton.disabled = false


## Lee el hash de ubicación física que el visor C# escribe en user://. Devuelve ""
## si falta o no es un SHA-256 de 64 hexadecimales (mismo formato que valida BKSVCB).
func _leer_ubicacion_hash() -> String:
	if not FileAccess.file_exists(RUTA_UBICACION):
		return ""
	var crudo := FileAccess.get_file_as_string(RUTA_UBICACION)
	var datos = JSON.parse_string(crudo)
	if typeof(datos) != TYPE_DICTIONARY:
		return ""
	var h := str(datos.get("ubicacion_hash", "")).strip_edges()
	var re := RegEx.new()
	re.compile("^[0-9a-fA-F]{64}$")
	return h.to_lower() if re.search(h) else ""


func _on_alta_completada(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, http: HTTPRequest) -> void:
	http.queue_free()
	_boton.disabled = false
	if result != HTTPRequest.RESULT_SUCCESS or code != 201:
		_estado.text = "No se pudo crear la cuenta (código %d)." % code
		return
	var datos = JSON.parse_string(body.get_string_from_utf8())
	if typeof(datos) != TYPE_DICTIONARY:
		_estado.text = "Respuesta de cuenta inválida."
		return
	var cuenta_hash := str(datos.get("cuenta_hash", ""))
	if cuenta_hash.is_empty():
		_estado.text = "La cadena no devolvió un hash de cuenta."
		return
	var nick := str(datos.get("nick", _nick.text if _nick else ""))
	_guardar_cuenta(nick, cuenta_hash)
	recepcion_completada.emit("nuevo")


func _guardar_cuenta(nick: String, cuenta_hash: String) -> void:
	var datos := {
		"nick": nick,
		"cuenta_hash": cuenta_hash,
		"red": "WoldVirtualP2P3D",
		"fecha_alta": Time.get_datetime_string_from_system(true, true),
	}
	var f := FileAccess.open(RUTA_CUENTA, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(datos, "\t"))
		f.close()


## Migración de cuenta antigua: solicita al blockchain generar el .zip con el hash único
func _on_migrar() -> void:
	if _estado == null:
		return

	_estado.text = "Iniciando migración de cuenta..."
	_boton_sec.disabled = true if _boton_sec else false

	# Leer datos de la cuenta antigua
	var cfg := ConfigFile.new()
	if cfg.load(RUTA_REGISTRO) != OK:
		_estado.text = "Error: no se puede leer el registro antiguo"
		if _boton_sec:
			_boton_sec.disabled = false
		return

	var nick := str(cfg.get_value("jugador", "nick", ""))
	var huella := Identidad.leer_identidad(RUTA_REGISTRO)

	if nick.is_empty() or huella.is_empty():
		_estado.text = "Error: datos de cuenta antigua incompletos"
		if _boton_sec:
			_boton_sec.disabled = false
		return

	# Solicitar migración al blockchain
	var payload := {
		"nick": nick,
		"huella": huella,
		"ubicacion_hash": _leer_ubicacion_hash()
	}

	var http := HTTPRequest.new()
	http.timeout = 15.0
	add_child(http)
	http.request_completed.connect(_on_migrar_completada.bind(http))
	var err := http.request(BKSVCB_MIGRAR, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		http.queue_free()
		_estado.text = "El servidor de cuentas no responde (error %d)." % err
		if _boton_sec:
			_boton_sec.disabled = false


func _on_migrar_completada(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, http: HTTPRequest) -> void:
	http.queue_free()
	if _boton_sec:
		_boton_sec.disabled = false

	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		_estado.text = "No se pudo migrar la cuenta (código %d)." % code
		return

	var datos = JSON.parse_string(body.get_string_from_utf8())
	if typeof(datos) != TYPE_DICTIONARY:
		_estado.text = "Respuesta de migración inválida."
		return

	var cuenta_hash := str(datos.get("cuenta_hash", ""))
	if cuenta_hash.is_empty():
		_estado.text = "La cadena no devolvió un hash de cuenta."
		return

	var nick := str(datos.get("nick", ""))
	_guardar_cuenta(nick, cuenta_hash)

	# Descargar el .zip con el hash único de cuenta
	_descargar_zip_cuenta(cuenta_hash)


## Descarga el .zip JSON con el hash único de cuenta desde el blockchain
func _descargar_zip_cuenta(cuenta_hash: String) -> void:
	if _estado == null:
		return

	_estado.text = "Descargando archivo de cuenta (.zip)..."

	var http := HTTPRequest.new()
	http.timeout = 30.0
	add_child(http)
	http.request_completed.connect(_on_zip_descargado.bind(http, cuenta_hash))
	var url := "%s?cuenta_hash=%s" % [BKSVCB_DESCARGAR, cuenta_hash]
	var err := http.request(url)
	if err != OK:
		http.queue_free()
		_estado.text = "Error al descargar el archivo (error %d)." % err


func _on_zip_descargado(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, http: HTTPRequest, cuenta_hash: String) -> void:
	http.queue_free()

	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		_estado.text = "Error al descargar el archivo (código %d)." % code
		return

	# Guardar el .zip en user://
	var ruta_zip := "user://cuenta_%s.zip" % cuenta_hash.substr(0, 16)
	var f := FileAccess.open(ruta_zip, FileAccess.WRITE)
	if f:
		f.store_buffer(body)
		f.close()
		_estado.text = "Migración completada. Archivo guardado: %s" % ruta_zip.get_file()
	else:
		_estado.text = "Error al guardar el archivo .zip"
		return

	# Eliminar el registro antiguo
	if FileAccess.file_exists(RUTA_REGISTRO):
		DirAccess.remove_absolute(OS.get_user_data_dir().path_join("registro.cfg"))

	# Actualizar UI
	_cuenta = {"nick": _cuenta.get("nick", ""), "cuenta_hash": cuenta_hash}
	_modo = "existente"
	_generar_link_validacion()

	# Recargar el formulario
	_limpiar_formulario()
	_montar_formulario()


func _limpiar_formulario() -> void:
	if _capa:
		_capa.queue_free()
		_capa = null


func _etiqueta(texto: String, tam: int, color: Color, borde: int) -> Label:
	var e := Label.new()
	e.text = texto
	e.add_theme_font_size_override("font_size", tam)
	e.add_theme_color_override("font_color", color)
	e.add_theme_color_override("font_outline_color", Color(0.01, 0.05, 0.09, 1.0))
	e.add_theme_constant_override("outline_size", borde)
	return e
