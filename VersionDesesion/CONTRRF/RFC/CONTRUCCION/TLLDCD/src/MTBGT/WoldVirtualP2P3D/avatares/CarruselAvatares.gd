extends Node3D
## Carrusel de avatares reconstruido desde cero.
##
## Muestra los ocho avatares del catálogo en un anillo 3D. Se puede girar con
## las flechas, la rueda, arrastrando con el ratón o haciendo clic sobre un
## avatar; ENTER o el botón confirman la elección.
##
## No depende de las escenas antiguas de SLAV: instancia las escenas jugables
## de `res://avatares/` y guarda la elección en `Avatares` (autoload).

signal avatar_confirmed(scene_path: String)

const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

const RADIO := 2.5
const ESCALA_ELEGIDO := 1.05
const ESCALA_RESTO := 0.8
const PIXELES_ARRASTRE := 70.0

var _pivote: Node3D
var _camara: Camera3D
var _avatares: Array[Node3D] = []
var _indice: int = 0
var _objetivo_rot: float = 0.0
var _ocupados: Dictionary = {}
var _nick: String = ""
var _confirmando: bool = false

var _pulsado: bool = false
var _arrastrando: bool = false
var _inicio_raton: Vector2 = Vector2.ZERO
var _acumulado: float = 0.0

var _titulo: Label
var _subtitulo: Label
var _nombre: Label
var _detalle: Label
var _contador: Label
var _aviso: Label
var _boton_elegir: Button


func _ready() -> void:
	_pivote = get_node_or_null("Pivote") as Node3D
	if _pivote == null:
		_pivote = Node3D.new()
		_pivote.name = "Pivote"
		add_child(_pivote)
	_camara = get_node_or_null("Camara") as Camera3D
	if _camara == null:
		_camara = Camera3D.new()
		_camara.name = "Camara"
		_camara.position = Vector3(0.0, 1.55, 5.4)
		add_child(_camara)
	_camara.current = true
	_construir_ui()
	_montar_avatares()
	var inicial := Catalogo.indice_de(Avatares.id_actual)
	_ir_a(inicial if inicial >= 0 else _primer_hueco(), true)


func set_nick(nick: String) -> void:
	_nick = nick.strip_edges()
	_actualizar_ui()


## Plazas ya reservadas por otros jugadores (índices del catálogo).
func set_ocupados(plazas: Array) -> void:
	_ocupados.clear()
	for p in plazas:
		var i := int(p)
		if i >= 0 and i < Catalogo.total():
			_ocupados[i] = true
	if _pivote != null:
		_refrescar_ocupados()


func abrir_en_primer_hueco() -> void:
	_ir_a(_primer_hueco(), true)


func _primer_hueco() -> int:
	for i in Catalogo.total():
		if not _ocupados.has(i):
			return i
	return 0


func _montar_avatares() -> void:
	var total := Catalogo.total()
	for i in total:
		var nodo := Catalogo.crear(str(Catalogo.por_indice(i)["id"]))
		if nodo == null:
			continue
		nodo.name = "Avatar_%s" % str(Catalogo.por_indice(i)["id"])
		if nodo is CharacterBody3D:
			nodo.set("es_selector", true)
		var angulo := TAU * float(i) / float(total)
		nodo.position = Vector3(sin(angulo) * RADIO, 0.0, cos(angulo) * RADIO)
		nodo.rotation.y = angulo
		_pivote.add_child(nodo)
		nodo.set_meta("indice_carrusel", i)
		_avatares.append(nodo)
	_refrescar_ocupados()


func _refrescar_ocupados() -> void:
	for nodo in _avatares:
		if not is_instance_valid(nodo):
			continue
		var i := int(nodo.get_meta("indice_carrusel", -1))
		var ocupado := _ocupados.has(i)
		# CharacterBody3D no tiene modulate: se atenúan sus mallas.
		for malla in nodo.find_children("*", "MeshInstance3D", true, false):
			(malla as MeshInstance3D).transparency = 0.55 if ocupado else 0.0


func _process(delta: float) -> void:
	if _pivote == null:
		return
	_pivote.rotation.y = lerp_angle(_pivote.rotation.y, _objetivo_rot, clampf(delta * 7.0, 0.0, 1.0))
	for nodo in _avatares:
		if not is_instance_valid(nodo):
			continue
		var i := int(nodo.get_meta("indice_carrusel", -1))
		var destino := ESCALA_ELEGIDO if i == _indice else ESCALA_RESTO
		nodo.scale = nodo.scale.lerp(Vector3.ONE * destino, clampf(delta * 8.0, 0.0, 1.0))


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_right"):
		_mover(1)
		return
	if event.is_action_pressed("ui_left"):
		_mover(-1)
		return
	if event.is_action_pressed("ui_accept"):
		_confirmar()
		return
	if event is InputEventMouseButton:
		_evento_raton(event as InputEventMouseButton)
	elif event is InputEventMouseMotion and _pulsado:
		_evento_arrastre(event as InputEventMouseMotion)


func _evento_raton(mb: InputEventMouseButton) -> void:
	match mb.button_index:
		MOUSE_BUTTON_LEFT:
			if mb.pressed:
				_pulsado = true
				_arrastrando = false
				_inicio_raton = mb.position
				_acumulado = 0.0
			else:
				_pulsado = false
				var clic := not _arrastrando
				_arrastrando = false
				_acumulado = 0.0
				if clic:
					var i := _avatar_bajo_punto(mb.position)
					if i >= 0:
						_ir_a(i, false)
		MOUSE_BUTTON_WHEEL_UP:
			if mb.pressed:
				_mover(-1)
		MOUSE_BUTTON_WHEEL_DOWN:
			if mb.pressed:
				_mover(1)


func _evento_arrastre(mm: InputEventMouseMotion) -> void:
	_acumulado += mm.relative.x
	if absf(_acumulado) >= PIXELES_ARRASTRE:
		_arrastrando = true
		_mover(-1 if _acumulado > 0.0 else 1)
		_acumulado = 0.0


func _avatar_bajo_punto(punto: Vector2) -> int:
	if _camara == null:
		return -1
	var mejor := -1
	var mejor_dist := 120.0
	for nodo in _avatares:
		if not is_instance_valid(nodo):
			continue
		var pantalla := _camara.unproject_position(nodo.global_position + Vector3(0.0, 0.9, 0.0))
		var d := pantalla.distance_to(punto)
		if d < mejor_dist:
			mejor_dist = d
			mejor = int(nodo.get_meta("indice_carrusel", -1))
	return mejor


func _mover(paso: int) -> void:
	var total := _avatares.size()
	if total == 0:
		return
	_ir_a(posmod(_indice + paso, total), false)


func _ir_a(indice: int, inmediato: bool) -> void:
	if _avatares.is_empty():
		return
	_indice = clampi(indice, 0, _avatares.size() - 1)
	_objetivo_rot = -TAU * float(_indice) / float(_avatares.size())
	if inmediato and _pivote != null:
		_pivote.rotation.y = _objetivo_rot
	_actualizar_ui()


func _confirmar() -> void:
	if _confirmando or _avatares.is_empty():
		return
	var modelo := Catalogo.por_indice(_indice)
	if modelo.is_empty():
		return
	_confirmando = true
	var id := str(modelo["id"])
	Avatares.guardar(id)
	if not _nick.is_empty():
		Avatares.sincronizar_registro(id, _nick)
	if _boton_elegir != null:
		_boton_elegir.disabled = true
		_boton_elegir.text = "AVATAR ELEGIDO"
	avatar_confirmed.emit(str(modelo["escena"]))


func _actualizar_ui() -> void:
	if _nombre == null:
		return
	var modelo := Catalogo.por_indice(_indice)
	if modelo.is_empty():
		return
	_nombre.text = str(modelo["nombre"])
	var genero := str(modelo["genero"])
	_detalle.text = "%s · %s · Altura 1,80 m" % [str(modelo["id"]), genero.capitalize()]
	_contador.text = "%d / %d" % [_indice + 1, _avatares.size()]
	var ocupado := _ocupados.has(_indice)
	_aviso.text = "Esa plaza ya está ocupada; se te asignará un sustituto." if ocupado else ""
	if _nick.is_empty():
		_subtitulo.text = "Elige tu avatar para entrar al metaverso"
	else:
		_subtitulo.text = "%s, elige tu avatar para entrar al metaverso" % _nick


# ---------------------------------------------------------------------------
# Interfaz 2D
# ---------------------------------------------------------------------------

func _construir_ui() -> void:
	var capa := CanvasLayer.new()
	capa.name = "UI"
	capa.layer = 20
	add_child(capa)
	var raiz := Control.new()
	raiz.set_anchors_preset(Control.PRESET_FULL_RECT)
	raiz.mouse_filter = Control.MOUSE_FILTER_IGNORE
	capa.add_child(raiz)

	_titulo = _etiqueta("ELIGE TU AVATAR", 34, Color(0.78, 0.94, 1.0, 1.0))
	_titulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_titulo.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_titulo.offset_left = -420.0
	_titulo.offset_right = 420.0
	_titulo.offset_top = 26.0
	_titulo.offset_bottom = 76.0
	raiz.add_child(_titulo)

	_subtitulo = _etiqueta("Elige tu avatar para entrar al metaverso", 17, Color(0.66, 0.82, 1.0, 1.0))
	_subtitulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_subtitulo.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_subtitulo.offset_left = -420.0
	_subtitulo.offset_right = 420.0
	_subtitulo.offset_top = 78.0
	_subtitulo.offset_bottom = 108.0
	raiz.add_child(_subtitulo)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	panel.offset_left = -330.0
	panel.offset_right = 330.0
	panel.offset_top = -132.0
	panel.offset_bottom = -16.0
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.03, 0.06, 0.11, 0.97)
	estilo.border_color = Color(0.35, 0.72, 1.0, 0.6)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(14)
	estilo.content_margin_left = 22.0
	estilo.content_margin_right = 22.0
	estilo.content_margin_top = 14.0
	estilo.content_margin_bottom = 14.0
	panel.add_theme_stylebox_override("panel", estilo)
	raiz.add_child(panel)

	var fila := HBoxContainer.new()
	fila.add_theme_constant_override("separation", 18)
	panel.add_child(fila)

	var anterior := Button.new()
	anterior.text = "◀"
	anterior.custom_minimum_size = Vector2(56, 64)
	anterior.add_theme_font_size_override("font_size", 26)
	anterior.pressed.connect(_mover.bind(-1))
	fila.add_child(anterior)

	var centro := VBoxContainer.new()
	centro.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	centro.alignment = BoxContainer.ALIGNMENT_CENTER
	fila.add_child(centro)

	_nombre = _etiqueta("", 30, Color(0.95, 0.98, 1.0, 1.0))
	_nombre.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	centro.add_child(_nombre)

	_detalle = _etiqueta("", 15, Color(0.62, 0.82, 1.0, 1.0))
	_detalle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	centro.add_child(_detalle)

	_contador = _etiqueta("", 14, Color(0.5, 0.7, 0.9, 1.0))
	_contador.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	centro.add_child(_contador)

	var siguiente := Button.new()
	siguiente.text = "▶"
	siguiente.custom_minimum_size = Vector2(56, 64)
	siguiente.add_theme_font_size_override("font_size", 26)
	siguiente.pressed.connect(_mover.bind(1))
	fila.add_child(siguiente)

	_boton_elegir = Button.new()
	_boton_elegir.text = "ELEGIR AVATAR"
	_boton_elegir.custom_minimum_size = Vector2(220, 64)
	_boton_elegir.add_theme_font_size_override("font_size", 19)
	_boton_elegir.pressed.connect(_confirmar)
	fila.add_child(_boton_elegir)

	_aviso = _etiqueta("", 14, Color(1.0, 0.78, 0.4, 1.0))
	_aviso.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_aviso.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_aviso.offset_left = -420.0
	_aviso.offset_right = 420.0
	_aviso.offset_top = -174.0
	_aviso.offset_bottom = -146.0
	raiz.add_child(_aviso)

	var pista := _etiqueta("Rueda / flechas / arrastra para girar · clic para enfocar · ENTER para elegir",
		13, Color(0.55, 0.66, 0.8, 0.9))
	pista.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pista.set_anchors_preset(Control.PRESET_CENTER_TOP)
	pista.offset_left = -460.0
	pista.offset_right = 460.0
	pista.offset_top = 112.0
	pista.offset_bottom = 134.0
	raiz.add_child(pista)


func _etiqueta(texto: String, tam: int, color: Color) -> Label:
	var etiqueta := Label.new()
	etiqueta.text = texto
	etiqueta.add_theme_font_size_override("font_size", tam)
	etiqueta.add_theme_color_override("font_color", color)
	etiqueta.add_theme_color_override("font_outline_color", Color(0.01, 0.04, 0.08, 1.0))
	etiqueta.add_theme_constant_override("outline_size", 6)
	etiqueta.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return etiqueta
