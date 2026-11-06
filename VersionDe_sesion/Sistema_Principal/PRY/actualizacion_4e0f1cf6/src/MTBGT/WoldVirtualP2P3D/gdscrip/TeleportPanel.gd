extends CanvasLayer
## TeleportPanel: UI lateral colapsable (tecla T o boton). Solo usa TeleportManager.

var manager: Node = null
var panel: PanelContainer = null
var list_box: VBoxContainer = null
var toggle_btn: Button = null
var register_btn: Button = null
var location_lbl: Label = null
var _userbase: Node3D = null
var _expanded := true
var _cooldown := 0.0
var _loc_timer := 0.0
var _current_island := -2 # ultimo indice mostrado (-2 = sin inicializar)
var _status_timer := 0.0
var _register_pending := false
var _register_wait := 0.0

func _ready() -> void:
	layer = 100
	visible = true
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
	toggle_btn.custom_minimum_size = Vector2(190, 36)
	toggle_btn.tooltip_text = "Mostrar u ocultar el explorador (T)"
	toggle_btn.pressed.connect(_toggle_panel)
	barra.add_child(toggle_btn)

	register_btn = Button.new()
	register_btn.text = "Registra tu isla"
	register_btn.custom_minimum_size = Vector2(170, 36)
	register_btn.tooltip_text = "Guarda tu isla para recuperarla al volver"
	register_btn.pressed.connect(_on_register_island_pressed)
	barra.add_child(register_btn)

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

func _process(delta: float) -> void:
	if _cooldown > 0.0:
		_cooldown -= delta
	if _status_timer > 0.0:
		_status_timer -= delta
		if _status_timer <= 0.0:
			_status_timer = 0.0
			_current_island = -2
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
	_current_island = idx
	# Etiqueta y botón con la isla, su dueño y si la propiedad está registrada.
	var txt := "Mar"
	if idx >= 0 and manager.has_method("get_islands"):
		for entry in manager.call("get_islands"):
			if int(entry["index"]) == idx:
				txt = _texto_isla(idx, str(entry.get("nombre", "—")),
						str(entry.get("uuid", "------")), bool(entry.get("offline", false)),
						bool(entry.get("propia", false)), bool(entry.get("registrada", false)))
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
		var b := Button.new()
		b.text = _texto_isla(idx, nombre, uuid, offline, propia, registrada)
		b.tooltip_text = "Teletransportarse a Isla %d (%s)" % [idx, nombre]
		b.custom_minimum_size = Vector2(280, 32)
		b.set_meta("island_index", idx)
		b.set_meta("offline", offline)
		b.set_meta("nombre", nombre)
		b.set_meta("uuid", uuid)
		b.set_meta("propia", propia)
		b.set_meta("registrada", registrada)
		b.pressed.connect(_on_goto.bind(idx))
		list_box.add_child(b)
	_mark_current_button(_current_island)


## Texto con isla, dueño, código e indicador de propiedad persistente.
func _texto_isla(idx: int, nombre: String, uuid: String, offline: bool,
		propia: bool = false, registrada: bool = false) -> String:
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
					bool(c.get_meta("propia", false)), bool(c.get_meta("registrada", false)))
			c.text = ("> " + base) if b_idx == idx else base

func _on_goto(index: int) -> void:
	if _cooldown > 0.0 or manager == null:
		return
	_cooldown = 0.5
	manager.call("teleport_to", index)


func _on_register_island_pressed() -> void:
	if _register_pending:
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
