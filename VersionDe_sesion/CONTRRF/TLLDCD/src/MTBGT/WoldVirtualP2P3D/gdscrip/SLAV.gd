extends Node3D
## SLAV - Selector de Avatares (carrusel 3D giratorio)
##
## Los avatares se agrupan en turnos de `per_turn` (8). El orden de los arrays
## es el orden real del carrusel y debe alternar chico/chica de forma estricta:
## AVH1, AVMJ1, AVH2, AVMJ2... Al pasar del ultimo avatar de un turno se monta
## el siguiente turno; al confirmar se emite la escena jugable elegida.
##
## Interaccion:
## - clic sobre un avatar: lo enfoca (lo trae al frente);
## - arrastrar a izquierda/derecha: gira el anillo de forma circular;
## - rueda del raton y flechas: mismo giro; ENTER confirma.
## El nick es obligatorio y el avatar elegido se guarda como "avatar original"
## del jugador antes de pasar al registro. El anfitrion sigue siendo quien
## reserva la plaza definitiva (cada avatar es unico en el metaverso).

signal avatar_confirmed(scene_path: String)

const Pers = preload("res://gdscrip/Personalizacion.gd")
const Anim := preload("res://gdscrip/AnimacionesCompartidas.gd")

const VERDE := Color(0.45, 0.95, 0.55, 1.0)
const AMBAR := Color(1.0, 0.82, 0.38, 1.0)
const ROJO := Color(1.0, 0.42, 0.38, 1.0)
const PASO_ARRASTRE := 70.0
const NICK_MINIMO := 3

@export var avatar_paths: Array[String] = []
@export var playable_scenes: Array[String] = []
@export var avatar_names: Array[String] = []
## Escala visual base por avatar (1.0 salvo modelos que vienen mas altos).
@export var avatar_scales: Array[float] = []
@export var per_turn := 8
@export var idle_animation := "paradoMJ1_1"
@export var radius := 1.95
@export var y_offset := 0.0
@export var face_offset_deg := 0.0
@export var rotate_speed := 6.0
@export var selected_scale := 1.14
@export var idle_scale := 0.86

var _pivot: Node3D
var _avatars: Array[Node3D] = []
var _index := 0
var _turn := -1
var _target_rot := 0.0
## Indices de avatar ya reservados por otros jugadores. Si los 24 estan
## ocupados se permite elegir igualmente (turno 4: avatar reutilizado).
var ocupados := {}
var _reciclando := false
var _indice_inicial := -1

var _pers: Dictionary = {}
var _indice_con_forma := -1
var _boton_pulsado := false
var _arrastrando := false
var _inicio_raton := Vector2.ZERO
var _arrastre_acum := 0.0

var _nick_edit: LineEdit
var _status: Label
var _boton_confirm: Button
var _hint: Label
var _sliders_shape := {}
var _valores_shape := {}

@onready var _name_label: Label = %NameLabel
@onready var _counter: Label = %Counter
@onready var _camara: Camera3D = $Camera3D


func _ready() -> void:
	_pivot = Node3D.new()
	_pivot.name = "Pivot"
	add_child(_pivot)
	_pers = Pers.leer()
	_construir_ui()
	_ir_a(maxi(_indice_inicial, 0), true)


## Marca las plazas ya reservadas por otros jugadores. Llamar antes o despues
## de anadir el nodo al arbol; si aun no se ha montado el carrusel se aplica al
## arrancar.
func set_ocupados(plazas: Array) -> void:
	ocupados.clear()
	for p in plazas:
		var idx := int(p)
		if idx >= 0 and idx < avatar_paths.size():
			ocupados[idx] = true
	_reciclando = not _hay_libres()
	if _pivot != null:
		_ir_a(_index, true)
		_refrescar_ocupados()
	else:
		_indice_inicial = _primer_hueco()
		_index = _indice_inicial


## Coloca el foco en el primer avatar libre (turno 1 con huecos). Si los 24
## estan ocupados se queda en el primero en modo reciclaje.
func abrir_en_primer_hueco() -> void:
	var idx := _primer_hueco()
	if _pivot != null:
		_ir_a(idx, true)
	else:
		_indice_inicial = idx
		_index = idx


func _hay_libres() -> bool:
	return not avatar_paths.is_empty() and ocupados.size() < avatar_paths.size()


func _primer_hueco() -> int:
	for i in avatar_paths.size():
		if not ocupados.has(i):
			return i
	return 0


func _process(delta: float) -> void:
	if _pivot == null:
		return
	_pivot.rotation.y = lerp_angle(_pivot.rotation.y, _target_rot,
		clampf(delta * rotate_speed, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Entrada: teclado, clic para enfocar y arrastre circular
# ---------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_right"):
		_move(1)
		return
	if event.is_action_pressed("ui_left"):
		_move(-1)
		return
	if event.is_action_pressed("ui_accept"):
		_confirm()
		return
	if event is InputEventMouseButton:
		_evento_raton(event as InputEventMouseButton)
	elif event is InputEventMouseMotion and _boton_pulsado:
		_evento_arrastre(event as InputEventMouseMotion)


func _evento_raton(mb: InputEventMouseButton) -> void:
	match mb.button_index:
		MOUSE_BUTTON_LEFT:
			if mb.pressed:
				_boton_pulsado = true
				_arrastrando = false
				_inicio_raton = mb.position
				_arrastre_acum = 0.0
			else:
				_boton_pulsado = false
				var soltar_sin_arrastrar := not _arrastrando
				_arrastrando = false
				_arrastre_acum = 0.0
				if soltar_sin_arrastrar:
					var idx := _indice_bajo_punto(mb.position)
					if idx >= 0:
						_ir_a(idx, false)
		MOUSE_BUTTON_WHEEL_UP:
			if mb.pressed:
				_move(1)
		MOUSE_BUTTON_WHEEL_DOWN:
			if mb.pressed:
				_move(-1)


## Cada `PASO_ARRASTRE` px de arrastre horizontal equivale a un avatar. Se
## acumula el sobrante para que el giro sea continuo y no se pierda el gesto.
func _evento_arrastre(ev: InputEventMouseMotion) -> void:
	if not _arrastrando and ev.position.distance_to(_inicio_raton) < 6.0:
		return
	_arrastre_acum += -ev.relative.x
	var paso := int(_arrastre_acum / PASO_ARRASTRE)
	if paso == 0:
		return
	_arrastrando = true
	var dir := 1 if paso > 0 else -1
	for _i in absi(paso):
		_move(dir)
	_arrastre_acum -= float(paso) * PASO_ARRASTRE


## Indice (global) del avatar cuyo cuerpo cae bajo el punto de pantalla. Se
## mide la altura proyectada del avatar para que el area de clic crezca con la
## distancia del modelo, igual que el propio cuerpo en pantalla.
func _indice_bajo_punto(punto: Vector2) -> int:
	if _camara == null or _avatars.is_empty():
		return -1
	var mejor := -1
	var mejor_dist := INF
	var inicio := maxi(_turn, 0) * per_turn
	for i in _avatars.size():
		var avatar := _avatars[i]
		if avatar == null or not is_instance_valid(avatar):
			continue
		var base := avatar.global_position
		var alto := maxf(Pers.altura_total(avatar) * avatar.scale.y, 0.5)
		var cima := base + Vector3.UP * alto
		if _camara.is_position_behind(base) and _camara.is_position_behind(cima):
			continue
		var p_base := _camara.unproject_position(base)
		var p_cima := _camara.unproject_position(cima)
		var radio := maxf(p_base.distance_to(p_cima) * 0.55, 28.0)
		var centro := (p_base + p_cima) * 0.5
		var dist := punto.distance_to(centro)
		if dist <= radio and dist < mejor_dist:
			mejor_dist = dist
			mejor = inicio + i
	return mejor


# ---------------------------------------------------------------------------
# Navegacion por turnos
# ---------------------------------------------------------------------------

func _move(dir: int) -> void:
	if avatar_paths.is_empty():
		return
	var total := avatar_paths.size()
	if _hay_libres():
		# Salta las plazas reservadas; da una vuelta completa como maximo.
		var i := _index
		for _paso in total:
			i = wrapi(i + dir, 0, total)
			if not ocupados.has(i):
				_ir_a(i, false)
				return
	_ir_a(_index + dir, false)


func _ir_a(indice: int, instant: bool) -> void:
	if avatar_paths.is_empty():
		_index = 0
		_refrescar_textos()
		return
	_index = wrapi(indice, 0, avatar_paths.size())
	var turno := _index / per_turn
	if turno != _turn:
		_montar_turno(turno)
	_apply_selection(instant)


func _montar_turno(turno: int) -> void:
	_turn = turno
	_indice_con_forma = -1
	for avatar in _avatars:
		_pivot.remove_child(avatar)
		avatar.queue_free()
	_avatars.clear()

	# Solo se cargan los 8 avatares del turno visible: los modelos son pesados.
	var inicio := turno * per_turn
	var n := mini(per_turn, avatar_paths.size() - inicio)
	for i in n:
		var escena := load(avatar_paths[inicio + i]) as PackedScene
		if escena == null:
			continue
		var inst := escena.instantiate() as Node3D
		if inst == null:
			continue
		# Antes de entrar en el arbol: si no, el avatar aplica gravedad y su
		# camara orbital se vuelve la camara activa del carrusel.
		if inst.get("enable_control") != null:
			inst.set("enable_control", false)
		_pivot.add_child(inst)
		for cam in inst.find_children("*", "Camera3D", true, false):
			(cam as Camera3D).current = false
		var angulo := TAU * float(i) / float(n)
		inst.position = Vector3(sin(angulo) * radius, y_offset, cos(angulo) * radius)
		inst.rotation.y = angulo + deg_to_rad(face_offset_deg)
		# Los GLB de las plazas 9-24 no traen animaciones: se las presta el avatar
		# principal para que el carrusel no se quede en la pose de reposo.
		Anim.asegurar(inst)
		_arrancar_idle(inst)
		_avatars.append(inst)

	_target_rot = 0.0
	_pivot.rotation.y = 0.0
	if _camara != null:
		_camara.current = true
	_refrescar_ocupados()


## Arranca la animacion idle en el avatar del carrusel.
## Estrategia robusta:
##   1) Si el avatar tiene AnimationTree, lo activa y deja los parametros en 0
##      (idle) — NO se llama .play() directo porque el arbol controla el player.
##   2) Si no hay arbol, se busca el AnimationPlayer y se reproduce la animacion
##      idle disponible (la primera cuyo nombre contiene "parad" o "idle", o
##      la primera de la lista si ninguna coincide).
## El seek() con un offset aleatorio evita que todos los avatares esten
## sincronizados en la misma fase del ciclo.
func _arrancar_idle(inst: Node3D) -> void:
	# 1) Intentar activar el AnimationTree (presente en todos los AVMJ/AVH).
	var at := inst.find_child("AnimationTree", true, false) as AnimationTree
	if at != null:
		at.active = true
		# Todos los parametros de blend a 0 -> estado idle.
		for param in ["parameters/ANMJ/blend_amount",
					  "parameters/Add2/add_amount",
					  "parameters/Blend2/blend_amount",
					  "parameters/Blend2 2/blend_amount",
					  "parameters/Blend2 3/blend_amount"]:
			if at.get(param) != null:
				at.set(param, 0.0)
		# Fase aleatoria en el AnimationPlayer subyacente (sin pausar el arbol).
		var ap_linked := at.get_node_or_null(at.anim_player) as AnimationPlayer
		if ap_linked and ap_linked.has_animation(idle_animation):
			ap_linked.seek(randf() * ap_linked.get_animation(idle_animation).length, false)
		return

	# 2) Fallback: AnimationPlayer sin arbol.
	for ap_node in inst.find_children("*", "AnimationPlayer", true, false):
		var ap := ap_node as AnimationPlayer
		if ap == null:
			continue
		# Elegir la mejor animacion idle disponible.
		var candidato := idle_animation
		if not ap.has_animation(candidato):
			candidato = ""
			for anim_name in ap.get_animation_list():
				var lo := anim_name.to_lower()
				if lo.contains("parad") or lo.contains("idle"):
					candidato = anim_name
					break
			if candidato.is_empty() and ap.get_animation_list().size() > 0:
				candidato = ap.get_animation_list()[0]
		if not candidato.is_empty():
			ap.play(candidato)
			ap.seek(randf() * ap.get_animation(candidato).length, true)
		break


## Etiqueta "OCUPADO" sobre los avatares ya reservados del turno montado.
## Como cuelgan del avatar, se liberan solas al cambiar de turno.
func _refrescar_ocupados() -> void:
	if _pivot == null:
		return
	var inicio := _turn * per_turn
	for i in _avatars.size():
		var marca := _avatars[i].get_node_or_null("Ocupado") as Label3D
		var esta_ocupado := ocupados.has(inicio + i)
		if esta_ocupado and marca == null:
			marca = Label3D.new()
			marca.name = "Ocupado"
			marca.text = "OCUPADO"
			marca.font_size = 40
			marca.pixel_size = 0.0045
			marca.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			marca.modulate = Color(1.0, 0.35, 0.35, 1.0)
			marca.outline_size = 12
			marca.outline_modulate = Color(0.08, 0.02, 0.02, 1.0)
			marca.render_priority = 1
			marca.position = Vector3(0.0, 2.35, 0.0)
			_avatars[i].add_child(marca)
		elif not esta_ocupado and marca != null:
			marca.queue_free()


func _apply_selection(instant: bool) -> void:
	var n := _avatars.size()
	if n > 0:
		var local := _index % per_turn
		var want := -TAU * float(local) / float(n)
		if instant:
			_target_rot = want
			_pivot.rotation.y = want
		else:
			while want - _target_rot > PI:
				want -= TAU
			while want - _target_rot < -PI:
				want += TAU
			_target_rot = want
		for i in n:
			var s := selected_scale if i == local else idle_scale
			if not _reciclando and ocupados.has(_turn * per_turn + i):
				s *= 0.8
			s *= _escala_base(_turn * per_turn + i)
			var tw := create_tween()
			tw.tween_property(_avatars[i], "scale", Vector3.ONE * s, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	# Las etiquetas y el estado se actualizan aunque los modelos no hayan
	# podido cargarse: la plaza elegida y el aviso verde no dependen de la malla.
	_refrescar_textos()
	_aplicar_forma()


func _refrescar_textos() -> void:
	var nombre := _nombre_actual()
	if _name_label:
		var texto := nombre
		if not _reciclando and ocupados.has(_index):
			texto += "  ·  OCUPADO"
		_name_label.text = texto
	if _counter:
		var total_turnos := maxi(1, ceili(float(avatar_paths.size()) / float(maxi(per_turn, 1))))
		var local := _index % maxi(per_turn, 1)
		var por_turno := maxi(1, mini(per_turn, avatar_paths.size() - maxi(_turn, 0) * per_turn))
		var contador := "Turno %d/%d  ·  %d/%d" % [maxi(_turn, 0) + 1, total_turnos, local + 1, por_turno]
		if _reciclando:
			contador += "  ·  reciclando"
		_counter.text = contador
	_refrescar_estado()


## Mensaje verde "AVATAR ORIGINAL" para el avatar disponible; rojo si la plaza
## ya la reservo otro jugador y ambar cuando el catalogo esta completo y el
## avatar se reutiliza (turno 4).
func _refrescar_estado() -> void:
	var nick := _nick_actual()
	var ocupado := not _reciclando and ocupados.has(_index)
	var texto := ""
	var color := VERDE
	if ocupado:
		texto = "PLAZA OCUPADA · elige otro avatar para entrar"
		color = ROJO
	elif _reciclando:
		texto = "TURNO 4 · catalogo completo: %s se reutiliza" % _nombre_actual()
		color = AMBAR
	else:
		texto = "✔ AVATAR ORIGINAL · %s · Turno %d" % [_nombre_actual(), maxi(_turn, 0) + 1]
	if _status:
		_status.text = texto
		_status.add_theme_color_override("font_color", color)
	if _hint:
		if nick.length() < NICK_MINIMO:
			_hint.text = "Escribe tu nick (minimo %d letras) para entrar" % NICK_MINIMO
			_hint.add_theme_color_override("font_color", AMBAR)
		else:
			_hint.text = "Clic para enfocar  ·  arrastra o usa <- ->  ·  ENTER elige"
			_hint.add_theme_color_override("font_color", Color(0.55, 0.6, 0.7, 1.0))
	if _boton_confirm:
		_boton_confirm.disabled = ocupado or nick.length() < NICK_MINIMO


func _escala_base(indice: int) -> float:
	if indice < avatar_scales.size() and avatar_scales[indice] > 0.0:
		return avatar_scales[indice]
	return 1.0


func _nombre_actual() -> String:
	if _index >= 0 and _index < avatar_names.size():
		return avatar_names[_index]
	return str(_index + 1)


func _nick_actual() -> String:
	if _nick_edit == null:
		return ""
	return _nick_edit.text.strip_edges()


# ---------------------------------------------------------------------------
# Shape keys: panel de expresiones del avatar enfocado
# ---------------------------------------------------------------------------

func _avatar_de_indice(indice: int) -> Node3D:
	if indice < 0 or _turn < 0 or indice / per_turn != _turn:
		return null
	var local := indice % per_turn
	if local < 0 or local >= _avatars.size():
		return null
	return _avatars[local]


func _avatar_actual() -> Node3D:
	return _avatar_de_indice(_index)


## Aplica el aspecto (tintes, cuerpo y shape keys) solo al avatar enfocado;
## devuelve el anterior a su malla original para no acumular deformaciones.
func _aplicar_forma() -> void:
	if _indice_con_forma >= 0 and _indice_con_forma != _index:
		var previo := _avatar_de_indice(_indice_con_forma)
		if previo != null and is_instance_valid(previo):
			Pers.aplicar(previo, Pers.POR_DEFECTO)
	_indice_con_forma = _index
	var actual := _avatar_actual()
	if actual != null:
		Pers.aplicar(actual, _pers)


func _on_shape_cambiada(valor: float, clave: String) -> void:
	_pers[clave] = clampf(valor, 0.0, 1.0)
	if _valores_shape.has(clave):
		(_valores_shape[clave] as Label).text = "%d%%" % roundi(valor * 100.0)
	_aplicar_forma()


func _on_reset_shape() -> void:
	for clave in Pers.EXPRESIONES:
		_pers[clave] = 0.0
		if _sliders_shape.has(clave):
			(_sliders_shape[clave] as HSlider).set_value_no_signal(0.0)
		if _valores_shape.has(clave):
			(_valores_shape[clave] as Label).text = "0%"
	_aplicar_forma()


# ---------------------------------------------------------------------------
# Confirmacion y guardado
# ---------------------------------------------------------------------------

func _confirm() -> void:
	if not _reciclando and ocupados.has(_index):
		return # plaza reservada por otro jugador
	var nick := _nick_actual()
	if nick.length() < NICK_MINIMO:
		_refrescar_estado()
		if _nick_edit != null:
			_nick_edit.grab_focus()
		return
	if _index >= playable_scenes.size() or playable_scenes[_index].is_empty():
		return
	var ruta := playable_scenes[_index]
	_guardar_eleccion(nick, ruta)
	avatar_confirmed.emit(ruta)
	# Solo cambia de escena si se ejecuta suelto (sin nadie escuchando).
	if get_tree().current_scene == self:
		get_tree().change_scene_to_file(ruta)


## Guarda la eleccion para el registro que viene despues. `avatar_scene` y
## `nick` los sigue escribiendo el registro al confirmar: entrar al metaverso
## exige pasar por ese paso, no basta con abrir el carrusel.
func _guardar_eleccion(nick: String, ruta: String) -> void:
	var cfg := ConfigFile.new()
	cfg.load("user://registro.cfg")
	cfg.set_value("jugador", "nick_selector", nick)
	cfg.set_value("jugador", "avatar_selector", ruta)
	cfg.set_value("jugador", "avatar_nombre", _nombre_actual())
	cfg.set_value("jugador", "avatar_turno", maxi(_turn, 0) + 1)
	cfg.set_value("jugador", "avatar_reciclado", _reciclando)
	cfg.save("user://registro.cfg")
	Pers.guardar(_pers)


func _on_prev_pressed() -> void:
	_move(-1)


func _on_next_pressed() -> void:
	_move(1)


func _on_confirm_pressed() -> void:
	_confirm()


func _on_nick_cambiada(_texto: String) -> void:
	_refrescar_estado()


# ---------------------------------------------------------------------------
# Interfaz construida en codigo (nick, aviso y panel de shape keys)
# ---------------------------------------------------------------------------

func _construir_ui() -> void:
	var raiz := get_node_or_null("UI/Root") as Control
	if raiz == null:
		return
	_boton_confirm = get_node_or_null("UI/Root/Confirm") as Button
	_hint = get_node_or_null("UI/Root/Hint") as Label

	var caja_nick := HBoxContainer.new()
	caja_nick.name = "NickBox"
	caja_nick.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	caja_nick.offset_left = -190.0
	caja_nick.offset_right = 190.0
	caja_nick.offset_top = -206.0
	caja_nick.offset_bottom = -156.0
	caja_nick.add_theme_constant_override("separation", 10)
	raiz.add_child(caja_nick)

	var etiqueta := Label.new()
	etiqueta.text = "NICK"
	etiqueta.add_theme_font_size_override("font_size", 22)
	etiqueta.add_theme_color_override("font_color", Color(0.75, 0.86, 1.0, 1.0))
	caja_nick.add_child(etiqueta)

	_nick_edit = LineEdit.new()
	_nick_edit.name = "NickEdit"
	_nick_edit.placeholder_text = "Tu nick"
	_nick_edit.max_length = 16
	_nick_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_nick_edit.add_theme_font_size_override("font_size", 22)
	_nick_edit.text_changed.connect(_on_nick_cambiada)
	caja_nick.add_child(_nick_edit)

	_status = Label.new()
	_status.name = "Status"
	_status.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_status.offset_left = -520.0
	_status.offset_right = 520.0
	_status.offset_top = 224.0
	_status.offset_bottom = 276.0
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_status.add_theme_font_size_override("font_size", 26)
	_status.add_theme_color_override("font_outline_color", Color(0.01, 0.04, 0.02, 1.0))
	_status.add_theme_constant_override("outline_size", 8)
	_status.text = "AVATAR ORIGINAL"
	raiz.add_child(_status)

	_precargar_nick()
	_construir_panel_shape(raiz)
	_refrescar_textos()


func _precargar_nick() -> void:
	if _nick_edit == null:
		return
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") != OK:
		return
	var nick := str(cfg.get_value("jugador", "nick_selector", ""))
	if nick.is_empty():
		nick = str(cfg.get_value("jugador", "nick", ""))
	_nick_edit.text = nick


func _construir_panel_shape(raiz: Control) -> void:
	var panel := PanelContainer.new()
	panel.name = "ShapePanel"
	panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	panel.offset_left = -352.0
	panel.offset_right = -24.0
	panel.offset_top = 104.0
	panel.offset_bottom = 452.0
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.035, 0.06, 0.10, 0.86)
	estilo.border_color = Color(0.30, 0.55, 0.85, 0.65)
	estilo.set_border_width_all(1)
	estilo.set_corner_radius_all(10)
	estilo.content_margin_left = 14.0
	estilo.content_margin_right = 14.0
	estilo.content_margin_top = 10.0
	estilo.content_margin_bottom = 10.0
	panel.add_theme_stylebox_override("panel", estilo)
	raiz.add_child(panel)

	var caja := VBoxContainer.new()
	caja.name = "ShapeVBox"
	caja.add_theme_constant_override("separation", 6)
	panel.add_child(caja)

	var titulo := Label.new()
	titulo.text = "SHAPE KEYS"
	titulo.add_theme_font_size_override("font_size", 22)
	titulo.add_theme_color_override("font_color", Color(0.55, 0.82, 1.0, 1.0))
	caja.add_child(titulo)

	var sub := Label.new()
	sub.text = "Expresiones del avatar enfocado"
	sub.add_theme_font_size_override("font_size", 13)
	sub.add_theme_color_override("font_color", Color(0.58, 0.65, 0.76, 1.0))
	caja.add_child(sub)

	for clave in Pers.EXPRESIONES:
		var fila := HBoxContainer.new()
		fila.name = "Fila_" + clave
		fila.add_theme_constant_override("separation", 6)
		var nombre := Label.new()
		nombre.text = str(Pers.NOMBRES.get(clave, clave))
		nombre.custom_minimum_size = Vector2(112.0, 0.0)
		nombre.add_theme_font_size_override("font_size", 15)
		fila.add_child(nombre)
		var slider := HSlider.new()
		slider.name = "Shape_" + clave
		slider.min_value = 0.0
		slider.max_value = 1.0
		slider.step = 0.01
		slider.value = float(_pers.get(clave, 0.0))
		slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slider.value_changed.connect(_on_shape_cambiada.bind(clave))
		fila.add_child(slider)
		var valor := Label.new()
		valor.custom_minimum_size = Vector2(42.0, 0.0)
		valor.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		valor.add_theme_font_size_override("font_size", 14)
		valor.text = "%d%%" % roundi(float(_pers.get(clave, 0.0)) * 100.0)
		fila.add_child(valor)
		caja.add_child(fila)
		_sliders_shape[clave] = slider
		_valores_shape[clave] = valor

	var boton := Button.new()
	boton.name = "ResetShape"
	boton.text = "RESTABLECER CARA"
	boton.pressed.connect(_on_reset_shape)
	caja.add_child(boton)
