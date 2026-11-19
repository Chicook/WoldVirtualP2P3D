extends Node3D
## Vista preliminar 2.9.3: oficina de LucIA, alta simple y presencia compartida.

const SERVER_NAME := "WoldVirtualP2P3D.Servidor.exe"
const POLL_SECONDS := 2.0

var _http: HTTPRequest
var _timer: Timer
var _ipc_timer: Timer
var _purpose := ""
var _busy := false
var _stage := "nick"
var _nick := ""
var _avatar := "Ciudadano"
var _token := ""
var _member_id := ""
var _base_url := "http://127.0.0.1:8765"
var _server_pid := 0
var _ipc_root := ""
var _ipc_request_id := ""
var _members_world: Node3D
var _member_count_label: Label

var _panel_body: VBoxContainer
var _nick_input: LineEdit
var _url_input: LineEdit
var _notice: Label
var _connect_button: Button
var _avatar_buttons: Array[Button] = []
var _members_list: VBoxContainer
var _tunnel_label: Label
var _top_tunnel_label: Label

const C_BG := Color("071426")
const C_PANEL := Color(0.025, 0.055, 0.11, 0.94)
const C_CYAN := Color("60e7ef")
const C_MINT := Color("81f2c0")
const C_TEXT := Color("e9f7ff")
const C_MUTED := Color("9fb8cc")


func _ready() -> void:
	_build_dao_room()
	_build_interface()
	_setup_local_ipc()
	_start_local_server()
	_http = HTTPRequest.new()
	_http.timeout = 5.0
	_http.request_completed.connect(_on_request_completed)
	add_child(_http)
	_timer = Timer.new()
	_timer.wait_time = POLL_SECONDS
	_timer.timeout.connect(_poll_services)
	add_child(_timer)
	_timer.start()
	_ipc_timer = Timer.new()
	_ipc_timer.wait_time = 0.08
	_ipc_timer.timeout.connect(_poll_ipc_response)
	add_child(_ipc_timer)
	_ipc_timer.start()
	_poll_services()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_leave_dao()
		if _server_pid > 0 and OS.is_process_running(_server_pid):
			OS.kill(_server_pid)


func _start_local_server() -> void:
	var override_path := OS.get_environment("WVP_SERVER_EXE").strip_edges()
	var exe_dir := OS.get_executable_path().get_base_dir()
	var candidates := [
		override_path,
		exe_dir.path_join("Servidor").path_join(SERVER_NAME),
		exe_dir.path_join(SERVER_NAME)
	]
	for path in candidates:
		if path.is_empty() or not FileAccess.file_exists(path):
			continue
		var args := PackedStringArray(["--urls", "http://0.0.0.0:8765"])
		_server_pid = OS.create_process(path, args, false)
		if _server_pid > 0:
			print("[Visor] Servidor local iniciado (pid=%d)." % _server_pid)
		else:
			push_warning("[Visor] No se pudo iniciar el servidor local: " + path)
		return
	print("[Visor] No hay un servidor junto al visor; se usará el que ya esté activo en localhost.")


func _setup_local_ipc() -> void:
	_ipc_root = OS.get_environment("WVP_IPC_DIR").strip_edges()
	if _ipc_root.is_empty():
		_ipc_root = ProjectSettings.globalize_path("user://wvp-ipc")
		OS.set_environment("WVP_IPC_DIR", _ipc_root)
	DirAccess.make_dir_recursive_absolute(_ipc_root.path_join("requests"))
	DirAccess.make_dir_recursive_absolute(_ipc_root.path_join("responses"))


func _build_dao_room() -> void:
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("071426")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("658cac")
	env.ambient_light_energy = 0.7
	environment.environment = env
	add_child(environment)

	var camera := Camera3D.new()
	camera.position = Vector3(0, 2.4, 8.7)
	camera.fov = 48
	add_child(camera)
	camera.look_at(Vector3(0, 1.55, 0), Vector3.UP)

	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-43, -27, 0)
	key.light_energy = 1.35
	key.light_color = Color("c9f8ff")
	add_child(key)
	var fill := OmniLight3D.new()
	fill.position = Vector3(0, 3.3, -1.8)
	fill.light_color = C_CYAN
	fill.light_energy = 2.2
	fill.omni_range = 9
	add_child(fill)

	_box(Vector3(24, 0.3, 24), Vector3(0, -0.18, 0), Color("101d37"))
	_box(Vector3(17, 6.5, 0.28), Vector3(0, 3.1, -5.4), Color("0b1932"))
	_box(Vector3(0.28, 6.5, 11), Vector3(-8.5, 3.1, 0), Color("0d1b35"))
	_box(Vector3(0.28, 6.5, 11), Vector3(8.5, 3.1, 0), Color("0d1b35"))
	for x in [-6.9, -3.45, 3.45, 6.9]:
		_box(Vector3(0.06, 4.8, 0.08), Vector3(x, 3.1, -5.18), Color("47bdcf"), true)
		_box(Vector3(0.1, 0.08, 0.12), Vector3(x, 5.62, -5.16), C_CYAN, true)

	# Plataforma de recepción y mostrador de LucIA.
	_box(Vector3(5.7, 0.18, 1.65), Vector3(0, 0.9, -1.15), Color("17304c"))
	_box(Vector3(5.9, 0.12, 1.78), Vector3(0, 1.04, -1.15), Color("3a637c"), true)
	_box(Vector3(5.3, 0.82, 0.17), Vector3(0, 0.55, -0.47), Color("162740"))
	_box(Vector3(4.6, 0.035, 0.04), Vector3(0, 0.91, -0.365), C_CYAN, true)
	for x in [-7.5, 7.5]:
		_box(Vector3(0.42, 5.4, 0.42), Vector3(x, 2.6, -3.0), Color("183c57"))

	# LucIA: figura de bienvenida estilizada para esta previsualización de conexión.
	var lucia := Node3D.new()
	lucia.position = Vector3(0, 1.16, -2.15)
	add_child(lucia)
	var cuerpo := CapsuleMesh.new()
	cuerpo.radius = 0.29
	cuerpo.height = 1.1
	_mesh(lucia, cuerpo, Vector3(0, 0.72, 0), Color("e8f5f7"))
	var cabeza := SphereMesh.new()
	cabeza.radius = 0.235
	cabeza.height = 0.47
	_mesh(lucia, cabeza, Vector3(0, 1.42, 0), Color("e8c9b9"))
	var pelo := SphereMesh.new()
	pelo.radius = 0.25
	pelo.height = 0.42
	_mesh(lucia, pelo, Vector3(0, 1.52, -0.025), Color("25334d"))
	var pelo_cubierta := SphereMesh.new()
	pelo_cubierta.radius = 0.205
	pelo_cubierta.height = 0.3
	_mesh(lucia, pelo_cubierta, Vector3(0, 1.57, 0.09), Color("e8c9b9"))
	_mesh(lucia, cuerpo, Vector3(-0.37, 0.72, 0), Color("e8f5f7"))
	var etiqueta := Label3D.new()
	etiqueta.text = "LUCÍA · ANFITRIONA"
	etiqueta.font_size = 40
	etiqueta.pixel_size = 0.005
	etiqueta.modulate = C_MINT
	etiqueta.position = Vector3(0, 2.0, 0)
	etiqueta.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lucia.add_child(etiqueta)

	# Emblema circular de la DAO en la pared posterior.
	var aro := TorusMesh.new()
	aro.inner_radius = 0.055
	aro.outer_radius = 1.25
	var placa := MeshInstance3D.new()
	placa.mesh = aro
	placa.position = Vector3(0, 4.05, -5.14)
	placa.material_override = _material(C_CYAN, true)
	add_child(placa)
	var emblema := Label3D.new()
	emblema.text = "DAO"
	emblema.font_size = 110
	emblema.pixel_size = 0.006
	emblema.modulate = C_CYAN
	emblema.position = Vector3(0, 4.02, -5.0)
	emblema.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	add_child(emblema)
	_members_world = Node3D.new()
	_members_world.name = "ParticipantesDAO"
	add_child(_members_world)


func _build_interface() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layer.add_child(root)

	var top := Label.new()
	top.text = "WOLD VIRTUAL  ·  DAO DE LUCÍA"
	top.position = Vector2(34, 18)
	top.add_theme_font_size_override("font_size", 17)
	top.add_theme_color_override("font_color", C_CYAN)
	root.add_child(top)

	_top_tunnel_label = Label.new()
	_top_tunnel_label.text = "🌐 Túnel efímero: Iniciando..."
	_top_tunnel_label.position = Vector2(34, 46)
	_top_tunnel_label.add_theme_font_size_override("font_size", 12)
	_top_tunnel_label.add_theme_color_override("font_color", C_MINT)
	root.add_child(_top_tunnel_label)

	var pill := Label.new()
	pill.text = "VISTA PRELIMINAR 2.9.3"
	pill.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	pill.offset_left = -270
	pill.offset_right = -34
	pill.offset_top = 22
	pill.offset_bottom = 52
	pill.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	pill.add_theme_color_override("font_color", C_MUTED)
	pill.add_theme_font_size_override("font_size", 14)
	root.add_child(pill)
	_member_count_label = Label.new()
	_member_count_label.text = "DAO · esperando participantes"
	_member_count_label.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_member_count_label.offset_left = -420
	_member_count_label.offset_right = -34
	_member_count_label.offset_top = 60
	_member_count_label.offset_bottom = 84
	_member_count_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_member_count_label.add_theme_color_override("font_color", C_MINT)
	_member_count_label.add_theme_font_size_override("font_size", 14)
	root.add_child(_member_count_label)

	var panel := PanelContainer.new()
	panel.position = Vector2(36, 82)
	panel.custom_minimum_size = Vector2(440, 0)
	panel.set_anchors_preset(Control.PRESET_LEFT_WIDE)
	panel.offset_left = 36
	panel.offset_right = 476
	panel.offset_top = 82
	panel.offset_bottom = -34
	var panel_style := StyleBoxFlat.new()
	panel_style.bg_color = C_PANEL
	panel_style.border_color = Color(0.24, 0.76, 0.86, 0.86)
	panel_style.set_border_width_all(1)
	panel_style.set_corner_radius_all(16)
	panel_style.content_margin_left = 24
	panel_style.content_margin_right = 24
	panel_style.content_margin_top = 20
	panel_style.content_margin_bottom = 20
	panel.add_theme_stylebox_override("panel", panel_style)
	root.add_child(panel)
	_panel_body = VBoxContainer.new()
	_panel_body.add_theme_constant_override("separation", 10)
	panel.add_child(_panel_body)
	_render_stage()


func _render_stage() -> void:
	for child in _panel_body.get_children():
		child.queue_free()
	_avatar_buttons.clear()
	_members_list = null
	_tunnel_label = null
	_connect_button = null

	var eyebrow := _label("SEDE FIJA · 0, 0, 0", 12, C_CYAN)
	_panel_body.add_child(eyebrow)
	var title := _label("Lucía te recibe en la DAO", 27, C_TEXT)
	_panel_body.add_child(title)
	var description := _label("Vista enfocada en conectar participantes y volver juntos a la sede.", 14, C_MUTED)
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_panel_body.add_child(description)
	_panel_body.add_child(_separator())

	_notice = _label("Iniciando los módulos locales…", 13, C_MINT)
	_notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_notice.custom_minimum_size.y = 38
	_panel_body.add_child(_notice)

	if _stage == "nick":
		_panel_body.add_child(_label("1 · ¿Cómo te llamas en el metaverso?", 15, C_TEXT))
		_nick_input = _line_edit(_nick, "Escribe tu nick")
		_nick_input.text_submitted.connect(func(_t): _on_conectar_directo())
		_panel_body.add_child(_nick_input)
		_panel_body.add_child(_label("Dirección de Lucía (localhost para el anfitrión)", 12, C_MUTED))
		_url_input = _line_edit(_base_url, "http://127.0.0.1:8765")
		_url_input.text_submitted.connect(func(_t): _on_conectar_directo())
		_panel_body.add_child(_url_input)
		_connect_button = _button("🏛 CONECTAR A LA DAO", _on_conectar_directo, true)
		_panel_body.add_child(_connect_button)
		_panel_body.add_child(_upcoming_row())
	elif _stage == "connect":
		_panel_body.add_child(_label("2 · Comprueba la conexión con Lucía", 15, C_TEXT))
		_panel_body.add_child(_label("Al continuar, contactaremos con el servidor y túnel de Lucía antes de crear tu cuenta.", 13, C_MUTED))
		_connect_button = _button("⚡ CONECTAR CON LUCÍA", _on_connect, true)
		_panel_body.add_child(_connect_button)
		_panel_body.add_child(_button("Volver", _on_back_to_nick, false))
	elif _stage == "avatar":
		_panel_body.add_child(_label("3 · Elige tu avatar para la sede", 15, C_TEXT))
		for avatar_name in ["Ciudadano", "Explorador", "Mediador"]:
			var avatar_button := _button(avatar_name, _on_choose_avatar.bind(avatar_name), avatar_name == _avatar)
			_avatar_buttons.append(avatar_button)
			_panel_body.add_child(avatar_button)
		_panel_body.add_child(_button("Registrar y volver a la DAO", _on_register, true))
	elif _stage == "dao":
		_panel_body.add_child(_label("ASAMBLEA · PARTICIPANTES EN LÍNEA", 12, C_CYAN))
		_tunnel_label = _label("Comprobando la URL de Lucía…", 12, C_MINT)
		_tunnel_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_panel_body.add_child(_tunnel_label)
		_panel_body.add_child(_label("Personas que comparten esta sesión", 14, C_TEXT))
		_members_list = VBoxContainer.new()
		_members_list.add_theme_constant_override("separation", 5)
		_panel_body.add_child(_members_list)
		_panel_body.add_child(_upcoming_row())
		_panel_body.add_child(_button("Salir de la sesión", _on_sign_out, false))


func _on_conectar_directo() -> void:
	var candidate := _nick_input.text.strip_edges() if _nick_input != null else _nick
	if candidate.is_empty():
		candidate = "Ciudadano"
	_nick = candidate
	if _url_input != null:
		_base_url = _normalize_base(_url_input.text)
	_stage = "connect"
	_render_stage()
	_on_connect()


func _on_continue() -> void:
	var candidate := _nick_input.text.strip_edges()
	if candidate.length() < 2 or candidate.length() > 24:
		_set_notice("El nick debe tener entre 2 y 24 caracteres.", true)
		return
	_nick = candidate
	_base_url = _normalize_base(_url_input.text)
	_stage = "connect"
	_render_stage()
	_request_api("/api/health", HTTPClient.METHOD_GET, {}, "health")


func _on_connect() -> void:
	if _busy:
		return
	if _connect_button:
		_connect_button.disabled = true
	_set_notice("Conectando con el servidor de Lucía…", false)
	_request_api("/api/session/connect", HTTPClient.METHOD_POST, {"nick": _nick}, "connect")


func _on_back_to_nick() -> void:
	_stage = "nick"
	_render_stage()


func _on_choose_avatar(avatar_name: String) -> void:
	_avatar = avatar_name
	for button in _avatar_buttons:
		button.button_pressed = button.text == avatar_name


func _on_register() -> void:
	if _busy:
		return
	_set_notice("Minando el bloque local de alta…", false)
	_request_api("/api/dao/register", HTTPClient.METHOD_POST,
		{"token": _token, "nick": _nick, "avatar": _avatar}, "register")


func _on_sign_out() -> void:
	_leave_dao()
	_token = ""
	_member_id = ""
	_stage = "nick"
	_render_stage()


func _leave_dao() -> void:
	if not _member_id.is_empty() and not _busy:
		_request_api("/api/dao/members/" + _member_id.uri_encode(), HTTPClient.METHOD_DELETE, {}, "leave")


func _poll_services() -> void:
	if _busy:
		return
	if _stage == "dao" and not _member_id.is_empty():
		_request_api("/api/dao/heartbeat", HTTPClient.METHOD_POST, {"id": _member_id}, "heartbeat")
	else:
		_request_api("/api/tunnel/status", HTTPClient.METHOD_GET, {}, "tunnel")


func _request_api(path: String, method: HTTPClient.Method, payload: Dictionary, purpose: String) -> void:
	if _busy:
		return
	_busy = true
	_purpose = purpose
	if _uses_local_ipc():
		_ipc_request_id = str(OS.get_process_id()) + "-" + str(Time.get_ticks_usec())
		var request := {
			"id": _ipc_request_id,
			"method": _method_name(method),
			"path": path,
			"body": payload
		}
		var request_path := _ipc_root.path_join("requests").path_join(_ipc_request_id + ".req")
		var temporary_path := request_path + ".tmp"
		var file := FileAccess.open(temporary_path, FileAccess.WRITE)
		if file == null:
			_busy = false
			_set_notice("No se puede escribir en el puente local de Lucía.", true)
			return
		file.store_string(JSON.stringify(request))
		file.close()
		var rename_error := DirAccess.rename_absolute(temporary_path, request_path)
		if rename_error != OK:
			_busy = false
			_set_notice("No se pudo enviar la solicitud al puente local: " + error_string(rename_error), true)
		return
		return
	if _http == null:
		_busy = false
		return
	var headers := PackedStringArray()
	var body := ""
	if method == HTTPClient.METHOD_POST or method == HTTPClient.METHOD_PUT:
		headers.append("Content-Type: application/json")
		body = JSON.stringify(payload)
	var error := _http.request(_base_url + path, headers, method, body)
	if error != OK:
		_busy = false
		_set_notice("No se pudo iniciar la petición: " + error_string(error), true)


func _poll_ipc_response() -> void:
	if _ipc_request_id.is_empty():
		return
	var response_path := _ipc_root.path_join("responses").path_join(_ipc_request_id + ".res")
	if not FileAccess.file_exists(response_path):
		return
	var text := FileAccess.get_file_as_string(response_path)
	DirAccess.remove_absolute(response_path)
	_ipc_request_id = ""
	var response: Variant = JSON.parse_string(text)
	if typeof(response) != TYPE_DICTIONARY:
		_busy = false
		_set_notice("El puente local devolvió una respuesta no válida.", true)
		return
	var response_body: Variant = response.get("body", {})
	_handle_api_response(HTTPRequest.RESULT_SUCCESS, int(response.get("status", 500)), JSON.stringify(response_body).to_utf8_buffer())


func _uses_local_ipc() -> bool:
	var host := _base_url.to_lower()
	return host.contains("127.0.0.1") or host.contains("localhost") or host.contains("0.0.0.0")


func _method_name(method: HTTPClient.Method) -> String:
	match method:
		HTTPClient.METHOD_GET: return "GET"
		HTTPClient.METHOD_POST: return "POST"
		HTTPClient.METHOD_PUT: return "PUT"
		HTTPClient.METHOD_DELETE: return "DELETE"
		_: return "GET"


func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_handle_api_response(result, response_code, body)


func _handle_api_response(result: int, response_code: int, body: PackedByteArray) -> void:
	_busy = false
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if result != HTTPRequest.RESULT_SUCCESS:
		_set_notice("No hay respuesta del anfitrión. Comprueba la dirección y que su servidor siga activo.", true)
		return
	if response_code < 200 or response_code >= 300:
		var error_text := "El servidor respondió %d." % response_code
		if typeof(parsed) == TYPE_DICTIONARY:
			error_text = str(parsed.get("error", error_text))
		_set_notice(error_text, true)
		if _connect_button:
			_connect_button.disabled = false
		return

	match _purpose:
		"health":
			_set_notice("Servidor del anfitrión alcanzable. Pulsa Conectar para continuar.", false)
		"connect":
			if typeof(parsed) != TYPE_DICTIONARY:
				_set_notice("Respuesta de conexión no válida.", true)
				return
			_token = str(parsed.get("token", ""))
			_stage = "avatar"
			_render_stage()
			_set_notice("Conexión establecida con Lucía. Elige tu avatar para registrarte.", false)
		"register":
			if typeof(parsed) != TYPE_DICTIONARY:
				_set_notice("Respuesta de registro no válida.", true)
				return
			var member: Dictionary = parsed.get("miembro", {})
			_member_id = str(member.get("id", ""))
			_stage = "dao"
			_render_stage()
			_set_notice("Cuenta registrada. Ya estás en la sede compartida.", false)
			_refresh_members()
		"members":
			_render_members(parsed)
			_request_api("/api/tunnel/status", HTTPClient.METHOD_GET, {}, "tunnel")
		"tunnel":
			_render_tunnel(parsed)
		"heartbeat":
			_refresh_members()
		"leave":
			pass


func _refresh_members() -> void:
	if not _busy:
		_request_api("/api/dao/members", HTTPClient.METHOD_GET, {}, "members")


func _render_members(value: Variant) -> void:
	if _members_list == null or typeof(value) != TYPE_ARRAY:
		return
	for child in _members_list.get_children():
		child.queue_free()
	for child in _members_world.get_children():
		child.queue_free()
	var participant_index := 0
	if value.is_empty():
		_members_list.add_child(_label("Esperando a los primeros participantes…", 12, C_MUTED))
		return
	for item in value:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var person := HBoxContainer.new()
		var color := C_MINT if bool(item.get("isHost", false)) else C_CYAN
		person.add_child(_label("●", 13, color))
		var name := str(item.get("nick", "Participante"))
		var role := "Lucía · anfitriona" if bool(item.get("isHost", false)) else str(item.get("avatar", "Participante"))
		person.add_child(_label(name + "  ·  " + role, 13, C_TEXT))
		_members_list.add_child(person)
		if not bool(item.get("isHost", false)):
			_spawn_member(name, role, participant_index)
			participant_index += 1
	if _member_count_label:
		_member_count_label.text = "DAO · %d participante(s) · Lucía anfitriona" % value.size()


func _spawn_member(nick: String, _avatar: String, index: int) -> void:
	# Distribución determinista en anillos alrededor del centro de la DAO (origen).
	var ring := int(index / 16)
	var slot := index % 16
	var angle := TAU * float(slot) / 16.0
	var radius := 2.2 + float(ring) * 1.35
	var person := Node3D.new()
	person.position = Vector3(cos(angle) * radius, 0, sin(angle) * radius)
	person.scale = Vector3.ONE * maxf(0.62, 0.82 - float(ring) * 0.025)
	_members_world.add_child(person)
	var hue := fmod(float(index) * 0.173 + 0.52, 1.0)
	var tunic := Color.from_hsv(hue, 0.36, 0.86)
	var body := CapsuleMesh.new()
	body.radius = 0.22
	body.height = 0.94
	_mesh(person, body, Vector3(0, 0.48, 0), tunic)
	var head := SphereMesh.new()
	head.radius = 0.17
	head.height = 0.34
	_mesh(person, head, Vector3(0, 1.1, 0), Color("e2c5ad"))
	var nameplate := Label3D.new()
	nameplate.text = nick
	nameplate.font_size = 28
	nameplate.pixel_size = 0.004
	nameplate.position = Vector3(0, 1.4, 0)
	nameplate.modulate = C_TEXT
	nameplate.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	person.add_child(nameplate)


func _render_tunnel(value: Variant) -> void:
	if typeof(value) != TYPE_DICTIONARY:
		return
	var url := str(value.get("url", ""))
	var active := bool(value.get("activo", false))
	var error := str(value.get("error", ""))
	var message := "Lucía anfitriona: " + url if active else (error if not error.is_empty() else "Túnel efímero preparando el acceso…")
	if _tunnel_label:
		_tunnel_label.text = message
	if _top_tunnel_label:
		_top_tunnel_label.text = "🌐 " + message
	if active and not url.is_empty():
		_base_url = url


func _set_notice(message: String, is_error: bool) -> void:
	if _notice:
		_notice.text = message
		_notice.add_theme_color_override("font_color", Color("ffba9b") if is_error else C_MINT)


func _normalize_base(value: String) -> String:
	var cleaned := value.strip_edges().trim_suffix("/")
	if cleaned.is_empty():
		return "http://127.0.0.1:8765"
	if not cleaned.contains("://"):
		cleaned = "https://" + cleaned
	return cleaned


func _label(text: String, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label


func _line_edit(text: String, placeholder: String) -> LineEdit:
	var field := LineEdit.new()
	field.text = text
	field.placeholder_text = placeholder
	field.custom_minimum_size.y = 44
	field.add_theme_color_override("font_color", C_TEXT)
	field.add_theme_color_override("font_placeholder_color", C_MUTED)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("0b1d32")
	style.border_color = Color("28475f")
	style.set_border_width_all(1)
	style.set_corner_radius_all(8)
	style.content_margin_left = 12
	style.content_margin_right = 12
	field.add_theme_stylebox_override("normal", style)
	field.add_theme_stylebox_override("focus", style)
	return field


func _button(text: String, callback: Callable, selected: bool) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = 44
	button.toggle_mode = text in ["Ciudadano", "Explorador", "Mediador"]
	button.button_pressed = selected and button.toggle_mode
	button.add_theme_font_size_override("font_size", 15)
	button.add_theme_color_override("font_color", C_TEXT)
	var normal := StyleBoxFlat.new()
	normal.bg_color = Color("124b61") if selected else Color("14263b")
	normal.border_color = Color("55d9e5") if selected else Color("304e64")
	normal.set_border_width_all(1)
	normal.set_corner_radius_all(8)
	button.add_theme_stylebox_override("normal", normal)
	var hover := normal.duplicate() as StyleBoxFlat
	hover.bg_color = Color("17657a")
	button.add_theme_stylebox_override("hover", hover)
	button.pressed.connect(callback)
	return button


func _separator() -> Control:
	var line := ColorRect.new()
	line.color = Color(0.25, 0.65, 0.74, 0.4)
	line.custom_minimum_size.y = 1
	return line


func _upcoming_row() -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	var title := _label("PRÓXIMAMENTE", 11, C_MUTED)
	box.add_child(title)
	for feature in ["Asambleas y votaciones", "Cursos gratuitos con Lucía", "Chat y economía DAO"]:
		var row := _label("◦  " + feature, 12, Color("607388"))
		box.add_child(row)
	return box


func _material(color: Color, emissive: bool = false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.metallic = 0.28
	material.roughness = 0.38
	if emissive:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 1.4
	return material


func _box(size: Vector3, position: Vector3, color: Color, emissive: bool = false) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var item := MeshInstance3D.new()
	item.mesh = mesh
	item.position = position
	item.material_override = _material(color, emissive)
	add_child(item)
	return item


func _mesh(parent: Node3D, mesh: Mesh, position: Vector3, color: Color) -> MeshInstance3D:
	var item := MeshInstance3D.new()
	item.mesh = mesh
	item.position = position
	item.material_override = _material(color)
	parent.add_child(item)
	return item
