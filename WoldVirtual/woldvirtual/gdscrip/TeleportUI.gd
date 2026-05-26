extends Control

@onready var container: VBoxContainer = $Panel/ScrollContainer/VBoxContainer
@onready var manager: Node3D = get_node("../../ChunkManager")

func _ready() -> void:
	# ── Si estamos embebidos en el Visor WPF, no ocultar la UI para permitir teleportación ──
	# var args = OS.get_cmdline_args()
	# if args.has("--wid") or args.has("--wallet"):
	# 	visible = false
	# 	return
	# ── Panel lateral: Glassmorphism con borde izquierdo brillante ──
	var panel = $Panel
	var sb_panel = StyleBoxFlat.new()
	sb_panel.bg_color = Color(0.03, 0.04, 0.08, 0.88)
	sb_panel.corner_radius_top_left = 0
	sb_panel.corner_radius_bottom_left = 0
	sb_panel.corner_radius_top_right = 16
	sb_panel.corner_radius_bottom_right = 16
	sb_panel.border_width_right = 1
	sb_panel.border_width_top = 1
	sb_panel.border_width_bottom = 1
	sb_panel.border_color = Color(0.0, 0.75, 1.0, 0.2)
	sb_panel.shadow_color = Color(0, 0, 0, 0.4)
	sb_panel.shadow_size = 12
	sb_panel.content_margin_left = 12
	sb_panel.content_margin_right = 12
	sb_panel.content_margin_top = 8
	sb_panel.content_margin_bottom = 8
	panel.add_theme_stylebox_override("panel", sb_panel)

	# ── Título del panel ──
	var title = $Panel/Title
	title.text = "🌐  RED P2P"
	title.add_theme_font_size_override("font_size", 16)
	title.add_theme_color_override("font_color", Color(0.55, 0.85, 1.0, 1.0))

	manager.network_updated.connect(_update_list)

func _update_list(state: Dictionary) -> void:
	var users = state.get("u", {})
	var islands = state.get("i", {})

	var ids = islands.keys()
	ids.sort()

	# Limpiar
	for child in container.get_children():
		child.queue_free()

	# Subtítulo
	var label_all = Label.new()
	label_all.text = "ISLAS ACTIVAS"
	label_all.add_theme_font_size_override("font_size", 11)
	label_all.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6, 0.7))
	container.add_child(label_all)

	# Separador visual
	var sep = HSeparator.new()
	sep.add_theme_constant_override("separation", 6)
	container.add_child(sep)

	for id in ids:
		var isl = islands.get(id, {})
		var b = _create_button(id, isl, users.get(id, {}))
		container.add_child(b)

func _create_button(id: String, isl: Dictionary, _u: Dictionary) -> Button:
	var b = Button.new()
	b.custom_minimum_size.y = 42
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

	# ── Estilo Normal: fondo oscuro traslúcido con borde lateral ──
	var sb_normal = StyleBoxFlat.new()
	sb_normal.bg_color = Color(0.08, 0.1, 0.18, 0.6)
	sb_normal.set_corner_radius_all(8)
	sb_normal.border_width_left = 3
	sb_normal.border_color = Color(0.0, 0.65, 1.0, 0.5)
	sb_normal.content_margin_left = 14
	sb_normal.content_margin_right = 10

	# ── Hover: iluminación ──
	var sb_hover = StyleBoxFlat.new()
	sb_hover.bg_color = Color(0.12, 0.18, 0.35, 0.75)
	sb_hover.set_corner_radius_all(8)
	sb_hover.border_width_left = 3
	sb_hover.border_color = Color(0.0, 0.9, 1.0, 0.9)
	sb_hover.content_margin_left = 14
	sb_hover.content_margin_right = 10
	sb_hover.shadow_color = Color(0.0, 0.7, 1.0, 0.15)
	sb_hover.shadow_size = 4

	# ── Pressed ──
	var sb_pressed = StyleBoxFlat.new()
	sb_pressed.bg_color = Color(0.0, 0.3, 0.6, 0.8)
	sb_pressed.set_corner_radius_all(8)
	sb_pressed.border_width_left = 3
	sb_pressed.border_color = Color(0.0, 1.0, 1.0, 1.0)
	sb_pressed.content_margin_left = 14
	sb_pressed.content_margin_right = 10

	b.add_theme_stylebox_override("normal", sb_normal)
	b.add_theme_stylebox_override("hover", sb_hover)
	b.add_theme_stylebox_override("pressed", sb_pressed)
	b.add_theme_stylebox_override("focus", sb_normal)
	b.add_theme_color_override("font_color", Color(0.85, 0.9, 1.0))
	b.add_theme_color_override("font_hover_color", Color(1.0, 1.0, 1.0))
	b.add_theme_font_size_override("font_size", 13)

	if id != "":
		var display_name = isl.get("n", "Isla " + id.substr(0, 6))
		if id == manager.local_id and not "(Tú)" in display_name:
			display_name = "⬢  " + display_name + "  (Tú)"
		else:
			display_name = "◇  " + display_name
		b.text = display_name
		b.pressed.connect(_go.bind(id, isl))

	return b

func _go(id: String, d: Dictionary) -> void:
	if !manager.my_avatar: return

	var offset_x = 0.0
	var state = manager.network._last_good_state
	var users_on_island = []
	for uid in state.get("u", {}):
		if uid == manager.local_id: continue
		var u = state.u[uid]
		if int(u.get("ix", -999)) == int(d.x) and int(u.get("iz", -999)) == int(d.z):
			users_on_island.append(u)

	if !users_on_island.is_empty():
		offset_x = 3.5 if users_on_island.size() % 2 == 0 else -3.5

	var target = Vector3(
		d.x * manager.spacing + offset_x,
		manager.HEIGHT,
		d.z * manager.spacing
	)

	manager.my_avatar.global_position = target
