extends CanvasLayer
## TeleportPanel: UI lateral colapsable (tecla T o boton). Solo usa TeleportManager.

const INDICE_DAO := -1

var manager: Node = null
var panel: PanelContainer = null
var list_box: VBoxContainer = null
var toggle_btn: Button = null
var register_btn: Button = null
var dao_btn: Button = null
var location_lbl: Label = null
var _userbase: Node3D = null
var _expanded := true
var _cooldown := 0.0
var _loc_timer := 0.0
var _current_island := -999 # ultimo indice mostrado (-999 = sin inicializar)
var _status_timer := 0.0
var _register_pending := false
var _register_wait := 0.0
var _dao_connecting := false

func _ready() -> void:
	layer = 100
	visible = true
	add_to_group("teleport_panel")
	_build_ui()
	# Conexion diferida para asegurar que TeleportManager ya hizo _ready
	call_deferred("_late_connect")

func _late_connect() -> void:
	manager = get_parent().get_node_or_null("TeleportManager")
	if manager != null:
		if manager.has_signal("islands_updated"):
			if not Signal(manager, "islands_updated").is_connected(_on_islands_updated):
				manager.connect("islands_updated", _on_islands_updated)
		if manager.has_signal("isla_registrada"):
			if not Signal(manager, "isla_registrada").is_connected(_on_isla_registrada):
				manager.connect("isla_registrada", _on_isla_registrada)
		if manager.has_method("get_islands"):
			_on_islands_updated(manager.call("get_islands"))
			return
	# Si aun no hay manager, mostrar algo igualmente para verificar visibilidad
	_show_debug()

func _build_ui() -> void:
	# Barra superior: botón fijo + etiqueta elástica con recorte (sin solapes).
	var barra := HBoxContainer.new()
	barra.set_anchors_preset(Control.PRESET_TOP_WIDE)
	barra.offset_left = 10
	barra.offset_top = 10
	barra.offset_right = -10
	barra.offset_bottom = 46
	barra.add_theme_constant_override("separation", 8)
	add_child(barra)

	toggle_btn = Button.new()
	toggle_btn.text = "Explorador de islas"
	toggle_btn.custom_minimum_size = Vector2(170, 36)
	toggle_btn.tooltip_text = "Mostrar u ocultar el explorador (T)"
	toggle_btn.pressed.connect(_toggle_panel)
	barra.add_child(toggle_btn)

	register_btn = Button.new()
	register_btn.text = "Registra tu isla"
	register_btn.custom_minimum_size = Vector2(160, 36)
	register_btn.tooltip_text = "Guarda tu isla para recuperarla al volver"
	register_btn.pressed.connect(_on_register_island_pressed)
	barra.add_child(register_btn)

	dao_btn = Button.new()
	dao_btn.text = "🏛 Conectar DAO"
	dao_btn.custom_minimum_size = Vector2(160, 36)
	dao_btn.tooltip_text = "Conecta la DAO al metaverso, asegura el túnel efímero y copia el enlace de invitación"
	dao_btn.pressed.connect(_on_conectar_dao_pressed)
	barra.add_child(dao_btn)

	location_lbl = Label.new()
	location_lbl.text = "Isla ?"
	location_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	location_lbl.clip_text = true
	location_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	location_lbl.add_theme_font_size_override("font_size", 20)
	barra.add_child(location_lbl)

	panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	panel.position = Vector2(10, 54)
	panel.size = Vector2(300, 320)
	panel.custom_minimum_size = Vector2(300, 320)
	panel.visible = true
	add_child(panel)

	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(300, 320)
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_child(scroll)

	list_box = VBoxContainer.new()
	list_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list_box)

	var lbl := Label.new()
	lbl.text = "Cargando islas..."
	lbl.name = "DebugLabel"
	list_box.add_child(lbl)

func _show_debug() -> void:
	pass # el label "Cargando islas..." ya demuestra visibilidad

func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_T:
			_toggle_panel()

func _toggle_panel() -> void:
	_expanded = not _expanded
	if panel != null:
		panel.visible = _expanded


## Abre/cierra el explorador desde otros nodos (por ejemplo, el portal de la DAO).
func alternar() -> void:
	_toggle_panel()

func _process(delta: float) -> void:
	if _cooldown > 0.0:
		_cooldown -= delta
	if _status_timer > 0.0:
		_status_timer -= delta
		if _status_timer <= 0.0:
			_status_timer = 0.0
			_current_island = -999
			_refresh_location()
	if _register_pending:
		_register_wait -= delta
		if _register_wait <= 0.0:
			_register_pending = false
			if register_btn != null:
				register_btn.disabled = false
			_show_status("El anfitrión no respondió al registro.", 4.0)
	_loc_timer += delta
	if _loc_timer >= 0.3:
		_loc_timer = 0.0
		_refresh_location()

# Actualiza boton y etiqueta con la isla bajo el avatar (Isla 0, Isla 1...).
func _refresh_location() -> void:
	if _status_timer > 0.0:
		return
	if manager == null or not manager.has_method("current_island_index"):
		return
	if _userbase == null or not is_instance_valid(_userbase):
		_userbase = get_parent().get_node_or_null("USERBASE") as Node3D
		if _userbase == null:
			return
	var idx: int = int(manager.call("current_island_index", _userbase.position))
	if idx == _current_island:
		return
	var anterior := _current_island
	_current_island = idx

	if _current_island == INDICE_DAO:
		if register_btn != null:
			register_btn.text = "🏛 Conectar DAO"
			register_btn.tooltip_text = "Conecta la sede DAO al metaverso, asegura el túnel y copia el enlace"
		if anterior != -999 and anterior != INDICE_DAO:
			# El jugador acaba de llegar a la DAO: reconectar siempre (el JSON
			# fue invalidado al salir, así el _poll_dao detectará el cambio).
			call_deferred("_auto_conectar_dao")
	else:
		# El jugador abandona la DAO: invalidar tunel_dao_url.json marcándolo
		# como "exito=false" para que al volver _poll_dao dispare un nuevo estado
		# y _auto_conectar_dao lance una conexión fresca.
		if anterior == INDICE_DAO:
			_invalidar_tunel_dao()
		if register_btn != null:
			register_btn.text = "Registra tu isla"
			register_btn.tooltip_text = "Guarda tu isla para recuperarla al volver"
	# Etiqueta y botón con la isla, su dueño y si la propiedad está registrada.
	# La DAO también es una entrada válida (índice negativo reservado).
	var txt := "Mar"
	if manager.has_method("get_islands"):
		for entry in manager.call("get_islands"):
			if int(entry["index"]) == idx:
				txt = _texto_isla(idx, str(entry.get("nombre", "—")),
						str(entry.get("uuid", "------")), bool(entry.get("offline", false)),
						bool(entry.get("propia", false)), bool(entry.get("registrada", false)),
						bool(entry.get("dao", false)))
				break
		if txt == "Mar" and idx >= 0:
			txt = "Isla %d" % idx
	location_lbl.text = txt
	_mark_current_button(idx)

func _on_islands_updated(islands: Array) -> void:
	if list_box == null:
		return
	for c in list_box.get_children():
		c.queue_free()
	if islands.is_empty():
		var lbl := Label.new()
		lbl.text = "Buscando islas..."
		list_box.add_child(lbl)
		return
	for entry in islands:
		var idx: int = int(entry["index"])
		var offline: bool = bool(entry.get("offline", false))
		var nombre: String = str(entry.get("nombre", "—"))
		var uuid: String = str(entry.get("uuid", "------"))
		var propia: bool = bool(entry.get("propia", false))
		var registrada: bool = bool(entry.get("registrada", false))
		var dao: bool = bool(entry.get("dao", false))
		var b := Button.new()
		b.text = _texto_isla(idx, nombre, uuid, offline, propia, registrada, dao)
		if dao:
			b.tooltip_text = "Ir a la Isla DAO (sede de LucIA)"
		else:
			b.tooltip_text = "Teletransportarse a Isla %d (%s)" % [idx, nombre]
		b.custom_minimum_size = Vector2(280, 32)
		b.set_meta("island_index", idx)
		b.set_meta("offline", offline)
		b.set_meta("nombre", nombre)
		b.set_meta("uuid", uuid)
		b.set_meta("propia", propia)
		b.set_meta("registrada", registrada)
		b.set_meta("dao", dao)
		b.pressed.connect(_on_goto.bind(idx))
		list_box.add_child(b)
	_mark_current_button(_current_island)


## Texto con isla, dueño, código e indicador de propiedad persistente.
func _texto_isla(idx: int, nombre: String, uuid: String, offline: bool,
		propia: bool = false, registrada: bool = false, dao: bool = false) -> String:
	if dao:
		return "DAO · Isla Única LucIA (sede)"
	var txt := "Isla %d · %s (%s)" % [idx, nombre, uuid]
	if propia:
		txt += " · TU ISLA" if registrada else " · TU ISLA (sin registrar)"
	elif registrada:
		txt += " · registrada"
	if offline:
		txt += " (libre)"
	return txt

# Marca con "> " el boton de la isla actual en la lista.
func _mark_current_button(idx: int) -> void:
	if list_box == null:
		return
	for c in list_box.get_children():
		if c is Button and c.has_meta("island_index"):
			var b_idx: int = int(c.get_meta("island_index"))
			var base := _texto_isla(b_idx, str(c.get_meta("nombre", "—")),
					str(c.get_meta("uuid", "------")), bool(c.get_meta("offline", false)),
					bool(c.get_meta("propia", false)), bool(c.get_meta("registrada", false)),
					bool(c.get_meta("dao", false)))
			c.text = ("> " + base) if b_idx == idx else base

func _on_goto(index: int) -> void:
	if _cooldown > 0.0 or manager == null:
		return
	_cooldown = 0.5
	manager.call("teleport_to", index)


func _on_register_island_pressed() -> void:
	if _register_pending or _dao_connecting:
		return
	if _current_island == INDICE_DAO:
		_on_conectar_dao_pressed()
		return
	if manager == null or not manager.has_method("registrar_mi_isla"):
		_show_status("El gestor de islas todavía no está disponible.", 4.0)
		return
	_register_pending = true
	_register_wait = 4.0
	if register_btn != null:
		register_btn.disabled = true
	_show_status("Registrando tu isla...", 4.0)
	manager.call("registrar_mi_isla")


func _on_conectar_dao_pressed() -> void:
	if _dao_connecting:
		return
	_dao_connecting = true
	if dao_btn != null:
		dao_btn.disabled = true
	if register_btn != null and _current_island == INDICE_DAO:
		register_btn.disabled = true
	_show_status("🏛 Conectando DAO al metaverso y abriendo túnel efímero...", 6.0)

	var res: Dictionary = await _ejecutar_conexion_dao()
	_dao_connecting = false
	if dao_btn != null:
		dao_btn.disabled = false
	if register_btn != null:
		register_btn.disabled = false

	var url := str(res.get("enlace", res.get("url", ""))).strip_edges()
	if not url.is_empty():
		_show_status("🏛 DAO conectada · Enlace copiado: " + url, 8.0)
	else:
		_show_status("🏛 DAO conectada al metaverso", 5.0)


func _auto_conectar_dao() -> void:
	if _dao_connecting:
		return
	_dao_connecting = true
	var res: Dictionary = await _ejecutar_conexion_dao()
	_dao_connecting = false
	var url := str(res.get("enlace", res.get("url", ""))).strip_edges()
	if not url.is_empty():
		_show_status("🏛 Bienvenido a la DAO · Túnel activo copiado", 6.0)


func _ejecutar_conexion_dao() -> Dictionary:
	var dao := get_tree().get_first_node_in_group("isla_unica_lucia")
	if dao != null and dao.has_method("conectar_dao_al_metaverso"):
		return await dao.call("conectar_dao_al_metaverso")
	return {"ok": false}


func _on_isla_registrada(exito: bool, mensaje: String) -> void:
	_register_pending = false
	if register_btn != null:
		register_btn.disabled = false
	_show_status(("Registro correcto: " if exito else "Error: ") + mensaje, 6.0)
	if exito and manager != null and manager.has_method("get_islands"):
		_on_islands_updated(manager.call("get_islands"))


func _show_status(texto: String, duracion: float) -> void:
	if location_lbl == null:
		return
	location_lbl.text = texto
	_status_timer = duracion


## Invalida tunel_dao_url.json al salir de la DAO para que al volver
## _poll_dao() detecte el cambio y _auto_conectar_dao() lance reconexión fresca.
func _invalidar_tunel_dao() -> void:
	# Resetear flag de estado en la isla para permitir nueva conexión.
	var dao := get_tree().get_first_node_in_group("isla_unica_lucia")
	if dao != null:
		dao.set("_dao_conectada", false)
	var ruta := "user://tunel_dao_url.json"
	var datos := {
		"exito": false,
		"url": "",
		"enlace": "",
		"mensaje": "Túnel DAO liberado — reconectando al volver",
		"timestamp": Time.get_datetime_string_from_system()
	}
	var tmp := ruta + ".tmp"
	var fw := FileAccess.open(tmp, FileAccess.WRITE)
	if fw != null:
		fw.store_string(JSON.stringify(datos))
		fw.close()
		DirAccess.rename_absolute(
			ProjectSettings.globalize_path(tmp),
			ProjectSettings.globalize_path(ruta)
		)
	else:
		# Si no existe aún, simplemente no hacer nada; _poll_dao lo ignorará.
		pass
