extends Node3D

## Panel flotante 3D con el turno. En la recepción se desactiva porque el chat
## ya tiene su propio panel 2D y el holograma taparía el formulario.
@export var usar_holograma := true

signal conversacion_abierta
signal conversacion_cerrada

var modo_dao := false
var personaje_dao: LuciaPersonaje

const HOST := "127.0.0.1"
const PUERTO := 8765
const RECONEXION_SEG := 2.0
const CPS_BASE := 55.0
const CPS_MAX := 150.0
const COLA_BOCA_SEG := 0.35

const COLOR_TU := Color(0.45, 0.78, 1.0)
const COLOR_LUCIA := Color(1.0, 0.82, 0.35)
const COLOR_OK := Color(0.45, 1.0, 0.65)
const COLOR_ESPERA := Color(1.0, 0.8, 0.4)
const COLOR_ERROR := Color(1.0, 0.45, 0.45)

@onready var personaje: LuciaPersonaje = personaje_dao if modo_dao else $lucIA_BASE
@onready var reproductor: AudioStreamPlayer = $Voz
@onready var salida: RichTextLabel = $UI/Raiz/Panel/VBox/Salida
@onready var entrada: LineEdit = $UI/Raiz/Panel/VBox/Fila/Entrada
@onready var boton: Button = $UI/Raiz/Panel/VBox/Fila/Enviar
@onready var estado: Label = $UI/Raiz/Estado

var _tcp := StreamPeerTCP.new()
var _bytes := PackedByteArray()
var _conectado := false
var _esta_listo := false
var _enviando := false
var _fin_stream := false
var _hubo_token := false
var _prefijo_lucia := false
var _hablando := false
var _audio_sonando := false
var _voz_preparando := false
var _voz_restante := 0.0
var _ms_ultimo := 0
var _nucleo_resumen := ""
var _pendiente := ""
var _acumulador := 0.0
var _espera_cola := 0.0
var _espera_reconexion := 0.0
var _modelo := ""
var _turno := 0

const VENTANA_SEG := 0.02
const GANANCIA_BOCA := 1.2
const UMBRAL_SILENCIO := 0.015
var _envolvente := PackedFloat32Array()
var _boca_actual := 0.0
var _boca_objetivo := 0.0
var _t_boca := 0.0

# Holograma 3D con el texto del turno (sustituye al panel grande de chat).
var _holograma: PanelContainer
var _holo_texto: RichTextLabel
var _holo_usuario := ""
var _holo_respuesta := ""
var _holo_alfa := 0.0

func set_modo_dao(actor: LuciaPersonaje) -> void:
	modo_dao = true
	personaje_dao = actor
	usar_holograma = false
	for hijo in get_children():
		if hijo.name not in ["UI", "Voz"]:
			remove_child(hijo)
			hijo.free()

func _ready() -> void:
	if modo_dao:
		$UI.layer = 50
		$UI.hide()
		salida.hide()
		$UI/Raiz/Titulo.hide()
		$UI/Raiz/Marca.hide()
		estado.hide()
		$UI/Raiz/Panel.offset_top = -86.0
		$UI/Raiz/Panel.offset_left = 80.0
		$UI/Raiz/Panel.offset_right = -80.0
		var cerrar := Button.new()
		cerrar.name = "CerrarConversacion"
		cerrar.text = "Cerrar · Esc"
		cerrar.pressed.connect(cerrar_chat)
		$UI/Raiz/Panel/VBox/Fila.add_child(cerrar)
		_crear_holograma()
		_holograma.hide()
	else:
		var oficina := LuciaOficina.new()
		oficina.name = "Oficina"
		add_child(oficina)
		if usar_holograma:
			_crear_holograma()
		_encuadrar_camara()
	reproductor.finished.connect(_al_terminar_voz)
	entrada.text_submitted.connect(_al_enviar_texto)
	boton.pressed.connect(_al_pulsar_enviar)
	boton.focus_mode = Control.FOCUS_NONE
	_actualizar_entrada()
	_mostrar_estado("Conectando con el cerebro de LucIA…", COLOR_ESPERA)
	_conectar()

func _crear_holograma() -> void:
	_holograma = PanelContainer.new()
	_holograma.name = "BocadilloLucIA"
	_holograma.custom_minimum_size = Vector2(300, 190)
	_holograma.size = Vector2(300, 190)
	_holograma.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.015, 0.035, 0.075, 0.88)
	estilo.border_color = Color(0.25, 0.8, 1.0, 0.75)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(14)
	estilo.set_content_margin_all(14)
	_holograma.add_theme_stylebox_override("panel", estilo)
	_holo_texto = RichTextLabel.new()
	_holo_texto.custom_minimum_size = Vector2(272, 162)
	_holo_texto.fit_content = false
	_holo_texto.scroll_active = true
	_holo_texto.scroll_following = true
	_holo_texto.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_holo_texto.add_theme_font_size_override("normal_font_size", 14)
	_holo_texto.add_theme_color_override("default_color", Color(0.92, 0.97, 1.0))
	_holograma.add_child(_holo_texto)
	$UI/Raiz.add_child(_holograma)

func _holo_actualizar() -> void:
	if _holo_texto == null:
		return
	var lineas := "LucIA · conversación\n" + estado.text
	if not _holo_usuario.is_empty():
		lineas += "\n\nTú: " + _holo_usuario
	if not _holo_respuesta.is_empty():
		lineas += "\n\nLucIA: " + _holo_respuesta
	_holo_texto.text = lineas

func _encuadrar_camara() -> void:
	var aabb: AABB = personaje.obtener_aabb_mundo()
	if aabb.size == Vector3.ZERO:
		return
	var centro := aabb.get_center()
	var altura := aabb.size.y
	var cam: Camera3D = $Camera3D
	var dist := (altura * 1.18) / (2.0 * tan(deg_to_rad(cam.fov) * 0.5))
	dist = maxf(dist, 0.8)
	var frente := aabb.position.z + aabb.size.z * 0.5
	# Desplazo la cámara a la derecha para dejar sitio al holograma.
	var desvio := 0.30
	cam.global_position = Vector3(centro.x + desvio, centro.y + altura * 0.04, frente + dist)
	cam.look_at(Vector3(centro.x + desvio, centro.y + altura * 0.02, aabb.get_center().z))

func _process(delta: float) -> void:
	_actualizar_socket(delta)
	_escribir_pendiente(delta)

	if _audio_sonando:
		_voz_restante -= delta
		if _voz_restante <= 0.0:
			reproductor.stop()
			_audio_sonando = false

	if not modo_dao or $UI.visible:
		_animar_boca(delta)

	if _holograma != null and modo_dao and $UI.visible:
		var camara := get_viewport().get_camera_3d()
		if camara != null:
			var caja := personaje.obtener_aabb_mundo()
			var punto := camara.unproject_position(caja.get_center() + Vector3.UP * caja.size.y * 0.35)
			var limite := get_viewport().get_visible_rect().size
			_holograma.position = Vector2(clampf(punto.x + 48.0, 16.0, limite.x - 316.0), clampf(punto.y - 220.0, 16.0, limite.y - 206.0))

	# Nota: antes se cerraba la boca mientras se preparaba la voz
	# (_voz_preparando). Eso dejaba los brazos gesticulando y los labios mudos
	# durante toda la síntesis; ahora la boca sigue con la envolvente sintética
	# hasta que llega el PCM.

	if _enviando and _fin_stream and _pendiente.is_empty() and not _audio_sonando:
		_espera_cola += delta
		if _espera_cola >= COLA_BOCA_SEG:
			_cerrar_boca()
			_terminar_turno()
	else:
		_espera_cola = 0.0

func enfocar_chat() -> void:
	if modo_dao:
		$UI.show()
		_holograma.show()
		_holo_actualizar()
		_holo_alfa = 1.0
		conversacion_abierta.emit()
	if entrada != null and entrada.visible:
		entrada.grab_focus()

func cerrar_chat() -> void:
	entrada.release_focus()
	if modo_dao:
		$UI.hide()
		_holograma.hide()
		_tcp.disconnect_from_host()
		_al_desconectar()
		personaje.detener_gesticulacion()
		personaje.fijar_apertura_boca(0.0)
		conversacion_cerrada.emit()

func _actualizar_socket(delta: float) -> void:
	_tcp.poll()
	var situacion := _tcp.get_status()

	if situacion == StreamPeerTCP.STATUS_CONNECTED:
		if not _conectado:
			_al_conectar()
		_leer_socket()
		return

	if _conectado:
		_al_desconectar()

	if situacion == StreamPeerTCP.STATUS_CONNECTING:
		return

	_espera_reconexion -= delta
	if _espera_reconexion <= 0.0:
		_espera_reconexion = RECONEXION_SEG
		_conectar()

func _conectar() -> void:
	_bytes.clear()
	_tcp = StreamPeerTCP.new()
	var error := _tcp.connect_to_host(HOST, PUERTO)
	if error != OK:
		_espera_reconexion = RECONEXION_SEG

func _leer_socket() -> void:
	var disponibles := _tcp.get_available_bytes()
	if disponibles <= 0:
		return
	var resultado: Array = _tcp.get_partial_data(disponibles)
	if resultado[0] != OK:
		_al_desconectar()
		return
	_bytes.append_array(resultado[1] as PackedByteArray)

	while true:
		var corte := _bytes.find(10)
		if corte < 0:
			break
		var crudo := _bytes.slice(0, corte)
		_bytes = _bytes.slice(corte + 1)
		var linea := crudo.get_string_from_utf8().strip_edges()
		if not linea.is_empty():
			_procesar_linea(linea)

func _procesar_linea(linea: String) -> void:
	var datos: Variant = JSON.parse_string(linea)
	if typeof(datos) != TYPE_DICTIONARY:
		return
	var evento := datos as Dictionary

	match str(evento.get("tipo", "")):
		"hola":
			_modelo = str(evento.get("modelo", ""))
			_esta_listo = true
			_actualizar_entrada()
			_mostrar_estado("En línea con LucIA · %s" % _modelo, COLOR_OK)
		"estado":
			var fase := str(evento.get("estado", ""))
			if fase == "pensando":
				_mostrar_estado("LucIA está pensando…", COLOR_ESPERA)
			elif fase == "sintetizando":
				_voz_preparando = true
				_mostrar_estado("Preparando la voz de LucIA…", COLOR_ESPERA)
		"token":
			var trozo := str(evento.get("texto", ""))
			if trozo.is_empty():
				return
			_hubo_token = true
			_pendiente += trozo
			if not _hablando:
				_abrir_boca()
		"voz":
			_voz_preparando = false
			_volcar_pendiente()
			var audio := _crear_audio(evento)
			if audio != null:
				reproductor.stop()
				reproductor.stream = audio
				reproductor.play()
				_audio_sonando = true
				_voz_restante = maxf(audio.get_length(), float(evento.get("duracion", 0.0)))
				_abrir_boca()
				_mostrar_estado("LucIA está hablando…", COLOR_OK)
			else:
				_mostrar_estado("En línea · voz no disponible", COLOR_ESPERA)
		"aviso":
			_voz_preparando = false
			var mensaje := str(evento.get("mensaje", ""))
			_mostrar_estado("En línea · sin voz: %s" % mensaje, COLOR_ESPERA)
			print("Aviso del cerebro de LucIA: ", mensaje)
		"fin":
			_fin_stream = true
			_voz_preparando = false
			var completa := str(evento.get("texto", ""))
			if not _hubo_token and not completa.is_empty():
				_pendiente = completa
				_abrir_boca()
			_ms_ultimo = int(evento.get("ms", 0))
			var nucleo_v: Variant = evento.get("nucleo", {})
			if typeof(nucleo_v) == TYPE_DICTIONARY:
				var nucleo: Dictionary = nucleo_v
				_nucleo_resumen = " · %d sinapsis · deriva %.4f" % [
					int(nucleo.get("neuronas", 0)),
					float(nucleo.get("deriva", 0.0)),
				]
			if not _audio_sonando:
				_mostrar_estado("LucIA en línea · %s · %d ms" % [_modelo, _ms_ultimo], COLOR_OK)
		"error":
			_pendiente = ""
			_fin_stream = true
			_voz_preparando = false
			reproductor.stop()
			_audio_sonando = false
			if not _prefijo_lucia:
				_prefijo_lucia = true
				_color("LucIA: ", COLOR_LUCIA)
			_color("No pude responder: %s\n" % str(evento.get("mensaje", "error desconocido")), COLOR_ERROR)
			_holo_respuesta = "No pude responder: " + str(evento.get("mensaje", "error desconocido"))
			_holo_actualizar()
			_mostrar_estado("Error del cerebro de LucIA", COLOR_ERROR)
			_cerrar_boca()
			_terminar_turno()
		"pong":
			pass

func _al_conectar() -> void:
	_conectado = true
	_esta_listo = false
	_actualizar_entrada()
	_mostrar_estado("Conectado · esperando al modelo…", COLOR_ESPERA)

func _al_desconectar() -> void:
	_conectado = false
	_esta_listo = false
	_bytes.clear()
	_actualizar_entrada()
	reproductor.stop()
	_audio_sonando = false
	_voz_preparando = false
	_voz_restante = 0.0
	_cerrar_boca()
	_mostrar_estado("Cerebro desconectado · reintentando…", COLOR_ERROR)
	if _enviando:
		_color("Se perdió la conexión con el cerebro de LucIA.\n", COLOR_ERROR)
		_terminar_turno()

func _al_enviar_texto(texto: String) -> void:
	texto = texto.strip_edges()
	if texto.is_empty() or _enviando:
		return
	if not (_conectado and _esta_listo):
		_mostrar_estado("LucIA no conectada; reintentando…", COLOR_ERROR)
		_conectar()
		return

	_turno += 1
	_enviando = true
	_fin_stream = false
	_hubo_token = false
	_prefijo_lucia = false
	_voz_preparando = false
	_voz_restante = 0.0
	_ms_ultimo = 0
	_nucleo_resumen = ""
	_pendiente = ""
	_acumulador = 0.0
	_espera_cola = 0.0
	if _audio_sonando:
		reproductor.stop()
		_audio_sonando = false
	entrada.clear()
	entrada.release_focus()
	_actualizar_entrada()

	if _turno > 1:
		_texto("\n")
	_color("Tú: ", COLOR_TU)
	_texto(texto + "\n")
	_holo_usuario = texto
	_holo_respuesta = ""
	_holo_actualizar()

	_enviar_json({"tipo": "consulta", "texto": texto})
	_mostrar_estado("LucIA está pensando…", COLOR_ESPERA)

func _al_pulsar_enviar() -> void:
	_al_enviar_texto(entrada.text)

func _enviar_json(datos: Dictionary) -> void:
	var linea := JSON.stringify(datos) + "\n"
	_tcp.put_data(linea.to_utf8_buffer())

func _escribir_pendiente(delta: float) -> void:
	if _pendiente.is_empty():
		return
	var velocidad := minf(CPS_BASE + float(_pendiente.length()) * 0.8, CPS_MAX)
	_acumulador += delta * velocidad
	var cantidad := int(_acumulador)
	if cantidad <= 0:
		return
	cantidad = mini(cantidad, _pendiente.length())
	_acumulador = maxf(_acumulador - float(cantidad), 0.0)
	if not _prefijo_lucia:
		_prefijo_lucia = true
		_color("LucIA: ", COLOR_LUCIA)
	var fragmento := _pendiente.substr(0, cantidad)
	_texto(fragmento)
	_holo_respuesta += fragmento
	_holo_actualizar()
	_pendiente = _pendiente.substr(cantidad)

func _animar_boca(delta: float) -> void:
	_t_boca += delta
	if _audio_sonando and _envolvente.size() > 0:
		# Lipsync real contra la envolvente del PCM.
		var pos := reproductor.get_playback_position()
		var idx := clampi(int(pos / VENTANA_SEG), 0, _envolvente.size() - 1)
		var volumen := _envolvente[idx]
		if volumen < UMBRAL_SILENCIO:
			_boca_objetivo = 0.0
		else:
			_boca_objetivo = volumen * GANANCIA_BOCA
	elif _hablando:
		# Hablando sin audio (voz no disponible, mute, fallo de gTTS):
		# boca sintética para que los labios se muevan igualmente.
		_boca_objetivo = _boca_sintetica()
	else:
		# En reposo: micro-apertura lenta; la cara no se queda congelada.
		_boca_objetivo = 0.035 + 0.025 * sin(_t_boca * 1.15)
	_boca_actual = lerpf(_boca_actual, _boca_objetivo, minf(1.0, delta * 18.0))
	personaje.fijar_apertura_boca(_boca_actual)

func _boca_sintetica() -> float:
	## Envolvente de habla de relleno: varias frecuencias para que no sea un
	## metrónomo. Solo se usa cuando no hay PCM que seguir.
	var t := _t_boca
	var a := 0.5 + 0.5 * sin(t * TAU * 4.6)
	var b := 0.5 + 0.5 * sin(t * TAU * 7.7 + 1.3)
	var c := 0.5 + 0.5 * sin(t * TAU * 2.3 + 0.7)
	return clampf(0.22 + 0.55 * (a * b * 0.65 + c * 0.35), 0.0, 1.0)

func _volcar_pendiente() -> void:
	if _pendiente.is_empty():
		return
	if not _prefijo_lucia:
		_prefijo_lucia = true
		_color("LucIA: ", COLOR_LUCIA)
	_texto(_pendiente)
	_holo_respuesta += _pendiente
	_holo_actualizar()
	_pendiente = ""
	_acumulador = 0.0

func _terminar_turno() -> void:
	if not _enviando:
		return
	personaje.detener_gesticulacion()
	_enviando = false
	_fin_stream = false
	_hubo_token = false
	_prefijo_lucia = false
	_voz_preparando = false
	_pendiente = ""
	if _audio_sonando:
		reproductor.stop()
		_audio_sonando = false
	_voz_restante = 0.0
	reproductor.stream = null
	_texto("\n")
	if _ms_ultimo > 0 and not _modelo.is_empty():
		_mostrar_estado("LucIA en línea · %s · %d ms" % [_modelo, _ms_ultimo], COLOR_OK)
	_ms_ultimo = 0
	_actualizar_entrada()

func _al_terminar_voz() -> void:
	_audio_sonando = false
	_voz_restante = 0.0

func _crear_audio(evento: Dictionary) -> AudioStreamWAV:
	var crudo := Marshalls.base64_to_raw(str(evento.get("pcm", "")))
	if crudo.is_empty():
		return null
	var frecuencia := int(evento.get("rate", 24000))
	if frecuencia <= 0:
		frecuencia = 24000
	var canales := int(evento.get("canales", 1))
	_envolvente = _calcular_envolvente(crudo, frecuencia)
	var audio := AudioStreamWAV.new()
	audio.format = AudioStreamWAV.FORMAT_16_BITS
	audio.mix_rate = frecuencia
	audio.stereo = canales >= 2
	audio.data = crudo
	return audio

func _calcular_envolvente(crudo: PackedByteArray, frecuencia: int) -> PackedFloat32Array:
	var ventana := int(frecuencia * VENTANA_SEG)
	if ventana <= 0:
		return PackedFloat32Array()
	var muestras := int(crudo.size() / 2)
	var res := PackedFloat32Array()
	var i := 0
	while i < muestras:
		var fin := mini(i + ventana, muestras)
		var suma := 0.0
		var n := 0
		var j := i
		while j < fin:
			var v := float(_leer_i16(crudo, j)) / 32768.0
			suma += v * v
			n += 1
			j += 1
		if n > 0:
			res.append(sqrt(suma / float(n)))
		i = fin
	var maximo := 0.0
	for v in res:
		maximo = maxf(maximo, v)
	if maximo > 0.0001:
		for k in res.size():
			res[k] = res[k] / maximo
	return res

func _leer_i16(bytes: PackedByteArray, muestra: int) -> int:
	var idx := muestra * 2
	var v := bytes[idx] | (bytes[idx + 1] << 8)
	if v & 0x8000:
		v -= 0x10000
	return v

func _actualizar_entrada() -> void:
	var activa := _conectado and _esta_listo and not _enviando
	# Dejar escribir siempre: si el cerebro aún no está listo, al pulsar
	# Enter se reintenta la conexión en lugar de bloquear el campo.
	entrada.editable = true
	# El botón siempre responde: si LucIA aún no está lista, _al_enviar_texto
	# reintenta la conexión; antes quedaba deshabilitado y parecía roto.
	boton.disabled = false
	entrada.placeholder_text = "Escribe a LucIA y pulsa Enter..." if activa else "LucIA reconectando… pulsa Enviar"
	boton.disabled = not activa

func _abrir_boca() -> void:
	_hablando = true
	personaje.iniciar_gesticulacion()

func _cerrar_boca() -> void:
	_hablando = false

func _mostrar_estado(texto: String, color: Color) -> void:
	estado.text = texto
	estado.add_theme_color_override("font_color", color)
	if modo_dao:
		_holo_actualizar()

func _texto(texto: String) -> void:
	salida.add_text(texto)

func _color(texto: String, color: Color) -> void:
	salida.push_color(color)
	salida.add_text(texto)
	salida.pop()

func _input(event: InputEvent) -> void:
	## Atajos de demostración del cuerpo (F1 sentarse/levantarse, F2 andar,
	## F3 volver). No interfieren con el campo de texto.
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	if modo_dao:
		if event.keycode == KEY_T and not entrada.has_focus():
			enfocar_chat()
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_ESCAPE and $UI.visible:
			cerrar_chat()
			get_viewport().set_input_as_handled()
		return
	match (event as InputEventKey).keycode:
		KEY_T:
			if not entrada.has_focus():
				entrada.grab_focus()
				_mostrar_estado("Escribe a LucIA y pulsa Enter", COLOR_OK)
				get_viewport().set_input_as_handled()
		KEY_ESCAPE:
			if entrada.has_focus():
				entrada.release_focus()
				get_viewport().set_input_as_handled()
		KEY_F1:
			if personaje.esta_sentada():
				personaje.levantarse()
				_mostrar_estado("LucIA se levanta", COLOR_ESPERA)
			else:
				personaje.sentarse()
				_mostrar_estado("LucIA se sienta", COLOR_ESPERA)
		KEY_F2:
			personaje.caminar_adelante(0.8)
			_mostrar_estado("LucIA camina", COLOR_ESPERA)
		KEY_F3:
			personaje.volver()
			_mostrar_estado("LucIA vuelve", COLOR_ESPERA)
