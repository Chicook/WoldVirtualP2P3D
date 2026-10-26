extends CanvasLayer
## Panel de construcción (terreno + prims). Solo emite intenciones; la lógica
## y la red viven en Construccion.gd.

signal alternar_solicitado
signal salir_solicitado
signal herramienta_cambiada(herramienta: int)
signal radio_cambiada(metros: float)
signal fuerza_cambiada(metros: float)
signal rez_solicitado(tipo: String)
signal duplicar_solicitado
signal borrar_solicitado
signal color_solicitado(color: Color)
signal escala_solicitada(metros: float)
signal snap_cambiada(activo: bool)

const Prims = preload("res://gdscrip/Prims.gd")
const HERRAMIENTAS := ["Seleccionar", "Subir", "Bajar", "Suavizar", "Aplanar"]

var _panel: PanelContainer = null
var _btn_abrir: Button = null
var _lbl_isla: Label = null
var _lbl_estado: Label = null
var _lbl_seleccion: Label = null
var _slider_radio: HSlider = null
var _slider_fuerza: HSlider = null
var _slider_escala: HSlider = null
var _snap: CheckButton = null
var _tipo: OptionButton = null
var _grupo: ButtonGroup = null
var _botones_herr: Array[Button] = []
var _valores := {} # HSlider -> Label con el valor formateado
var _abierto := false
var _herramienta := 0


func _ready() -> void:
	layer = 110
	_construir()
	visible = true
	_panel.visible = false


func esta_abierto() -> bool:
	return _abierto


func abrir(activo: bool) -> void:
	_abierto = activo
	_panel.visible = activo
	_btn_abrir.text = "Cerrar construcción" if activo else "Construcción (B)"


func herramienta() -> int:
	return _herramienta


func radio() -> float:
	return _slider_radio.value if _slider_radio != null else 8.0


func fuerza() -> float:
	return _slider_fuerza.value if _slider_fuerza != null else 1.0


func escala_objetivo() -> float:
	return _slider_escala.value if _slider_escala != null else 2.0


func tipo() -> String:
	if _tipo == null or _tipo.selected < 0:
		return "cubo"
	return Prims.TIPOS[_tipo.selected]


## Refleja el tamaño real del objeto seleccionado en el deslizador.
func set_escala_ui(valor: float) -> void:
	if _slider_escala == null:
		return
	_slider_escala.set_value_no_signal(valor)
	if _valores.has(_slider_escala):
		(_valores[_slider_escala] as Label).text = _formato(valor)


func snap_activo() -> bool:
	return _snap.button_pressed if _snap != null else true


func set_isla(texto: String, editable: bool) -> void:
	if _lbl_isla == null:
		return
	_lbl_isla.text = texto
	_lbl_isla.modulate = Color(0.72, 1.0, 0.85) if editable else Color(1.0, 0.75, 0.55)


func set_estado(texto: String) -> void:
	if _lbl_estado != null:
		_lbl_estado.text = texto


func set_seleccion(texto: String) -> void:
	if _lbl_seleccion != null:
		_lbl_seleccion.text = texto


func _construir() -> void:
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.03, 0.06, 0.10, 0.94)
	estilo.border_color = Color(0.18, 0.72, 0.85, 0.85)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(8)
	estilo.content_margin_left = 12.0
	estilo.content_margin_right = 12.0
	estilo.content_margin_top = 10.0
	estilo.content_margin_bottom = 10.0

	_btn_abrir = Button.new()
	_btn_abrir.text = "Construcción (B)"
	_btn_abrir.focus_mode = Control.FOCUS_NONE
	# Debajo de la barra del explorador de islas (que ocupa todo el ancho).
	_btn_abrir.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_btn_abrir.offset_left = -205.0
	_btn_abrir.offset_top = 54.0
	_btn_abrir.offset_right = -10.0
	_btn_abrir.offset_bottom = 90.0
	_btn_abrir.tooltip_text = "Editar terreno y construir objetos (B)"
	_btn_abrir.pressed.connect(func(): alternar_solicitado.emit())
	add_child(_btn_abrir)

	_panel = PanelContainer.new()
	_panel.add_theme_stylebox_override("panel", estilo)
	_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_panel.offset_left = -362.0
	_panel.offset_top = 96.0
	_panel.offset_right = -10.0
	_panel.offset_bottom = 682.0
	add_child(_panel)

	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(336, 570)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_panel.add_child(scroll)

	var caja := VBoxContainer.new()
	caja.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	caja.add_theme_constant_override("separation", 6)
	scroll.add_child(caja)

	caja.add_child(_etiqueta("CONSTRUCCIÓN", 18, Color(0.55, 0.92, 1.0)))
	_lbl_isla = _etiqueta("Isla —", 14, Color(0.85, 0.9, 1.0))
	caja.add_child(_lbl_isla)
	_lbl_estado = _etiqueta("", 12, Color(0.6, 0.78, 0.9))
	_lbl_estado.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(_lbl_estado)
	caja.add_child(HSeparator.new())

	caja.add_child(_etiqueta("TERRENO", 14, Color(0.45, 0.9, 0.8)))
	var fila_herr := HBoxContainer.new()
	fila_herr.add_theme_constant_override("separation", 3)
	_grupo = ButtonGroup.new()
	for i in HERRAMIENTAS.size():
		var b := Button.new()
		b.text = HERRAMIENTAS[i]
		b.toggle_mode = true
		b.button_group = _grupo
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(58, 28)
		b.add_theme_font_size_override("font_size", 11)
		b.pressed.connect(_on_herramienta.bind(i))
		fila_herr.add_child(b)
		_botones_herr.append(b)
	caja.add_child(fila_herr)
	_botones_herr[0].button_pressed = true

	_slider_radio = _deslizador(caja, "Radio", 2.0, 30.0, 1.0, 8.0, _on_radio)
	_slider_fuerza = _deslizador(caja, "Fuerza", 0.2, 4.0, 0.1, 1.2, _on_fuerza)

	var pista := _etiqueta("Arrastra con clic izquierdo sobre tu isla para esculpir.", 11, Color(0.55, 0.65, 0.75))
	pista.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(pista)
	caja.add_child(HSeparator.new())

	caja.add_child(_etiqueta("OBJETOS", 14, Color(0.45, 0.9, 0.8)))
	var fila_rez := HBoxContainer.new()
	fila_rez.add_theme_constant_override("separation", 6)
	_tipo = OptionButton.new()
	_tipo.focus_mode = Control.FOCUS_NONE
	for t in Prims.TIPOS:
		_tipo.add_item(Prims.NOMBRES[t])
	_tipo.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fila_rez.add_child(_tipo)
	var btn_rez := _boton("Rez")
	btn_rez.tooltip_text = "Crear el objeto en el punto apuntado"
	btn_rez.pressed.connect(func(): rez_solicitado.emit(tipo()))
	fila_rez.add_child(btn_rez)
	caja.add_child(fila_rez)

	var fila_edit := HBoxContainer.new()
	fila_edit.add_theme_constant_override("separation", 6)
	var btn_dup := _boton("Duplicar")
	btn_dup.tooltip_text = "Copia el objeto seleccionado"
	btn_dup.pressed.connect(func(): duplicar_solicitado.emit())
	fila_edit.add_child(btn_dup)
	var btn_del := _boton("Borrar")
	btn_del.tooltip_text = "Elimina el objeto seleccionado"
	btn_del.pressed.connect(func(): borrar_solicitado.emit())
	fila_edit.add_child(btn_del)
	caja.add_child(fila_edit)

	caja.add_child(_etiqueta("Color", 12, Color(0.75, 0.85, 0.95)))
	var paleta := GridContainer.new()
	paleta.columns = 8
	paleta.add_theme_constant_override("h_separation", 4)
	paleta.add_theme_constant_override("v_separation", 4)
	for c in Prims.COLORES:
		var bc := Button.new()
		bc.custom_minimum_size = Vector2(30, 24)
		bc.focus_mode = Control.FOCUS_NONE
		bc.tooltip_text = "Aplicar color"
		var estilo_color := StyleBoxFlat.new()
		estilo_color.bg_color = c
		estilo_color.set_corner_radius_all(4)
		bc.add_theme_stylebox_override("normal", estilo_color)
		bc.add_theme_stylebox_override("hover", estilo_color)
		bc.add_theme_stylebox_override("pressed", estilo_color)
		bc.pressed.connect(func(): color_solicitado.emit(c))
		paleta.add_child(bc)
	caja.add_child(paleta)

	_slider_escala = _deslizador(caja, "Tamaño", 0.4, 12.0, 0.1, 2.0, _on_escala)
	_snap = CheckButton.new()
	_snap.text = "Rejilla de 0,5 m"
	_snap.button_pressed = true
	_snap.focus_mode = Control.FOCUS_NONE
	_snap.toggled.connect(func(v): snap_cambiada.emit(v))
	caja.add_child(_snap)

	_lbl_seleccion = _etiqueta("Selección: —", 12, Color(0.65, 0.9, 1.0))
	_lbl_seleccion.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(_lbl_seleccion)

	var ayuda := _etiqueta("Flechas/WASD mover · Q/E girar · RePág/AvPág altura · +/- tamaño · Ctrl+D duplicar · Supr borrar · Esc soltar", 10, Color(0.5, 0.6, 0.72))
	ayuda.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caja.add_child(ayuda)

	var btn_salir := _boton("Salir del modo construcción")
	btn_salir.pressed.connect(func(): salir_solicitado.emit())
	caja.add_child(btn_salir)


func _deslizador(padre: VBoxContainer, titulo: String, minimo: float, maximo: float,
		paso: float, inicial: float, al_cambiar: Callable) -> HSlider:
	var fila := HBoxContainer.new()
	fila.add_theme_constant_override("separation", 6)
	var lbl := _etiqueta(titulo, 12, Color(0.78, 0.86, 0.95))
	lbl.custom_minimum_size = Vector2(52, 0)
	fila.add_child(lbl)
	var slider := HSlider.new()
	slider.min_value = minimo
	slider.max_value = maximo
	slider.step = paso
	slider.value = inicial
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.focus_mode = Control.FOCUS_NONE
	slider.custom_minimum_size = Vector2(150, 22)
	fila.add_child(slider)
	var valor := _etiqueta(_formato(inicial), 11, Color(0.55, 0.85, 1.0))
	valor.custom_minimum_size = Vector2(48, 0)
	fila.add_child(valor)
	_valores[slider] = valor
	slider.value_changed.connect(func(v):
		valor.text = _formato(v)
		al_cambiar.call(v))
	padre.add_child(fila)
	return slider


func _formato(valor: float) -> String:
	return ("%.1f" % valor).replace(".", ",")


func _etiqueta(texto: String, tam: int, color: Color) -> Label:
	var l := Label.new()
	l.text = texto
	l.add_theme_font_size_override("font_size", tam)
	l.add_theme_color_override("font_color", color)
	return l


func _boton(texto: String) -> Button:
	var b := Button.new()
	b.text = texto
	b.focus_mode = Control.FOCUS_NONE
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return b


func _on_herramienta(indice: int) -> void:
	_herramienta = indice
	herramienta_cambiada.emit(indice)


func _on_radio(valor: float) -> void:
	radio_cambiada.emit(valor)


func _on_fuerza(valor: float) -> void:
	fuerza_cambiada.emit(valor)


func _on_escala(valor: float) -> void:
	escala_solicitada.emit(valor)
