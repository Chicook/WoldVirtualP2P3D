extends Node3D
## Carrusel de avatares de la DAO: ocho estatuas vivas en un aro giratorio.
##
## Las estatuas son las escenas jugables reales del catálogo, instanciadas en
## modo `es_selector` (sin física, cámara ni entrada) para que respiren y
## miren al centro. La consola junto al aro abre el carrusel original
## (`res://avatares/CarruselAvatares.tscn`) para cambiar de avatar.
##
## El alta de ciudadano usa `abrir_en_dao`: la elección ocurre sobre este mismo
## aro, dentro del atrio, con la cámara entre los pilares. El aro se detiene al
## abrir y sigue parado durante el recorrido hasta que el jugador toma el mando.

const Catalogo = preload("res://avatares/CatalogoAvatares.gd")
const ESCENA_CARRUSEL: PackedScene = preload("res://avatares/CarruselAvatares.tscn")
const SUELO_Y := 41.7
const RADIO := 14.0
const VELOCIDAD_GIRO := 0.045
## Ángulo del primer pedestal del aro, igual que al construirlo.
const ANGULO_BASE := 0.3926990817
## Encuadre de la elección en el atrio: cámara al sureste del aro, entre
## pilares, con el atrio y el despacho de LucIA alrededor del elegido.
const CAMARA_ATRIO := Vector3(20.6, 44.9, 3.0)
const MIRADA_ATRIO := Vector3(4.0, 42.9, 0.0)

## Se emite al cerrar la capa interactiva. La ruta llega vacía si se canceló;
## con ruta, el jugador confirmó ese avatar y ya quedó guardado en `Avatares`.
signal carrusel_cerrado(ruta: String)

var _aro: Node3D = null
var _estatuas: Array[Node3D] = []
var _angulos: Array[float] = []
var _abierto := false
var _jugador: Node3D = null
var _camara_previa: Camera3D = null
var _capa_carrusel: Node3D = null
var _bloqueo_hasta := 0
var _nick := ""
var _ocupados: Array = []
## El onboarding conduce el carrusel: desactiva la apertura por proximidad para
## que ninguna cinemática lo abra a mitad de recorrido.
var _auto_abrir := true
## Giro del aro: `_velocidad` se frena con tween cuando la cinemática lo pide.
var _velocidad := VELOCIDAD_GIRO
var _tween_giro: Tween = null
## Elección in situ en el atrio (abrir_en_dao).
var _modo_dao := false
## Alta en curso: el aro no vuelve a girar hasta que el alta termina, ni al
## entregar el mando ni al cancelar la elección.
var _alta := false
var _foco := 0
var _confirmando := false
var _objetivo_aro := 0.0
var _camara_dao: Camera3D = null
var _ui_dao: CanvasLayer = null
var _ui_nombre: Label = null
var _ui_detalle: Label = null
var _ui_contador: Label = null
var _ui_aviso: Label = null


func _ready() -> void:
	_aro = Node3D.new()
	_aro.name = "AroAvatares"
	add_child(_aro)
	_construir_estatuas()
	_construir_consola()


func _process(delta: float) -> void:
	if _aro == null:
		return
	if _modo_dao:
		# En elección el aro va a foco; las estatuas se giran hacia la cámara.
		_aro.rotation.y = lerp_angle(_aro.rotation.y, _objetivo_aro, clampf(delta * 5.0, 0.0, 1.0))
		_animar_foco(delta)
		return
	_aro.rotation.y += delta * _velocidad


func _unhandled_input(event: InputEvent) -> void:
	if not _abierto:
		return
	if event.is_action_pressed("ui_cancel"):
		_cerrar("")
		get_viewport().set_input_as_handled()
		return
	if not _modo_dao:
		return
	if event.is_action_pressed("ui_right"):
		_mover_foco(1)
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("ui_left"):
		_mover_foco(-1)
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("ui_accept"):
		_confirmar_dao()
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		match (event as InputEventMouseButton).button_index:
			MOUSE_BUTTON_WHEEL_UP:
				_mover_foco(-1)
			MOUSE_BUTTON_WHEEL_DOWN:
				_mover_foco(1)


# ---------------------------------------------------------------------------
# Montaje
# ---------------------------------------------------------------------------

func _construir_estatuas() -> void:
	var base := _mat(Color(0.05, 0.06, 0.09), 0.35, 0.6)
	var oro := _mat(Color(0.72, 0.54, 0.18), 0.28, 0.85, Color(0.72, 0.54, 0.18), 0.6)
	var total := Catalogo.total()
	for i in total:
		var modelo := Catalogo.por_indice(i)
		if modelo.is_empty():
			continue
		var ang := deg_to_rad(22.5) + TAU * float(i) / float(total)
		_angulos.append(ang)
		var centro := Vector3(sin(ang) * RADIO, SUELO_Y, cos(ang) * RADIO)
		var pedestal := Node3D.new()
		pedestal.name = "Pedestal_%s" % str(modelo["id"])
		pedestal.position = centro
		_aro.add_child(pedestal)

		var disco := MeshInstance3D.new()
		disco.name = "Disco"
		var cil := CylinderMesh.new()
		cil.top_radius = 1.15
		cil.bottom_radius = 1.25
		cil.height = 0.5
		cil.radial_segments = 64
		disco.mesh = cil
		disco.material_override = base
		disco.position = Vector3(0.0, 0.25, 0.0)
		pedestal.add_child(disco)

		var color: Color = modelo.get("color", Color(0.4, 0.8, 1.0))
		var anillo := MeshInstance3D.new()
		anillo.name = "AnilloAvatar"
		var toro := TorusMesh.new()
		toro.inner_radius = 1.16
		toro.outer_radius = 1.28
		toro.rings = 64
		toro.ring_segments = 8
		anillo.mesh = toro
		anillo.material_override = _mat(color * 0.3, 0.3, 0.2, color, 2.4)
		anillo.position = Vector3(0.0, 0.52, 0.0)
		pedestal.add_child(anillo)

		var forma := CylinderShape3D.new()
		forma.radius = 1.15
		forma.height = 0.5
		var cuerpo := StaticBody3D.new()
		cuerpo.name = "Colision"
		var nodo_forma := CollisionShape3D.new()
		nodo_forma.shape = forma
		cuerpo.add_child(nodo_forma)
		cuerpo.position = Vector3(0.0, 0.25, 0.0)
		pedestal.add_child(cuerpo)

		var avatar: Node3D = Catalogo.crear(str(modelo["id"]))
		if avatar == null:
			continue
		avatar.name = "Avatar_%s" % str(modelo["id"])
		avatar.set("es_selector", true)
		avatar.position = Vector3(0.0, 0.5, 0.0)
		avatar.rotation.y = ang + PI
		pedestal.add_child(avatar)
		_estatuas.append(avatar)

		var rotulo := Label3D.new()
		rotulo.name = "Nombre"
		rotulo.text = str(modelo["nombre"])
		rotulo.font_size = 48
		rotulo.pixel_size = 0.005
		rotulo.modulate = color
		rotulo.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
		rotulo.outline_size = 9
		rotulo.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		rotulo.position = Vector3(0.0, 2.5, 0.0)
		pedestal.add_child(rotulo)

		# Corchetes dorados en el borde del pedestal.
		var marca := MeshInstance3D.new()
		marca.name = "FiloDora"
		var aro := TorusMesh.new()
		aro.inner_radius = 1.0
		aro.outer_radius = 1.03
		aro.rings = 48
		aro.ring_segments = 6
		marca.mesh = aro
		marca.material_override = oro
		marca.position = Vector3(0.0, 0.51, 0.0)
		pedestal.add_child(marca)


func _construir_consola() -> void:
	var centro := Vector3(11.5, SUELO_Y, 11.5)
	var consola := Node3D.new()
	consola.name = "ConsolaAvatares"
	consola.position = centro
	consola.rotation.y = atan2(-centro.x, -centro.z)
	add_child(consola)

	var cuerpo := MeshInstance3D.new()
	cuerpo.name = "Cuerpo"
	var caja := BoxMesh.new()
	caja.size = Vector3(2.2, 1.05, 0.9)
	cuerpo.mesh = caja
	cuerpo.material_override = _mat(Color(0.05, 0.06, 0.09), 0.35, 0.6)
	cuerpo.position = Vector3(0.0, 0.52, 0.0)
	consola.add_child(cuerpo)

	var pantalla := MeshInstance3D.new()
	pantalla.name = "Pantalla"
	var panel := BoxMesh.new()
	panel.size = Vector3(1.9, 1.05, 0.08)
	pantalla.mesh = panel
	pantalla.material_override = _mat(Color(0.02, 0.09, 0.13), 0.2, 0.2, Color(0.12, 0.65, 1.0), 1.8)
	pantalla.position = Vector3(0.0, 1.55, 0.0)
	pantalla.rotation.x = -0.22
	consola.add_child(pantalla)

	var rotulo := Label3D.new()
	rotulo.name = "Rotulo"
	rotulo.text = "CARRUSEL DE AVATARES"
	rotulo.font_size = 72
	rotulo.pixel_size = 0.006
	rotulo.modulate = Color(0.55, 0.9, 1.0)
	rotulo.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
	rotulo.outline_size = 10
	rotulo.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	rotulo.position = Vector3(0.0, 3.3, 0.0)
	consola.add_child(rotulo)

	var ayuda := Label3D.new()
	ayuda.name = "Ayuda"
	ayuda.text = "Acércate para elegir tu avatar"
	ayuda.font_size = 34
	ayuda.pixel_size = 0.005
	ayuda.modulate = Color(0.7, 0.85, 1.0)
	ayuda.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
	ayuda.outline_size = 8
	ayuda.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	ayuda.position = Vector3(0.0, 2.7, 0.0)
	consola.add_child(ayuda)

	var zona := Area3D.new()
	zona.name = "ZonaAvatares"
	var forma := CylinderShape3D.new()
	forma.radius = 2.6
	forma.height = 3.0
	var nodo_forma := CollisionShape3D.new()
	nodo_forma.shape = forma
	zona.add_child(nodo_forma)
	zona.position = Vector3(0.0, 1.5, 0.0)
	consola.add_child(zona)
	zona.body_entered.connect(_on_zona_entrada)


func _on_zona_entrada(body: Node3D) -> void:
	if not _auto_abrir or _abierto or _jugador != null or body == null:
		return
	if Time.get_ticks_msec() < _bloqueo_hasta:
		return
	if not (body is CharacterBody3D):
		return
	if bool(body.get("es_clon_remoto")):
		return
	_abrir(body)


# ---------------------------------------------------------------------------
# Carrusel original como capa interactiva
# ---------------------------------------------------------------------------

func _abrir(jugador: Node3D) -> void:
	if _abierto or not ResourceLoader.exists(ESCENA_CARRUSEL.resource_path):
		return
	_abierto = true
	_jugador = jugador
	_camara_previa = get_viewport().get_camera_3d()
	jugador.set_physics_process(false)
	jugador.set_process_input(false)
	_capa_carrusel = ESCENA_CARRUSEL.instantiate() as Node3D
	if _capa_carrusel == null:
		_abierto = false
		_jugador = null
		_camara_previa = null
		return
	get_tree().root.add_child(_capa_carrusel)
	if _capa_carrusel.has_signal("avatar_confirmed"):
		_capa_carrusel.connect("avatar_confirmed", _al_confirmar)
	if _capa_carrusel.has_method("set_ocupados"):
		_capa_carrusel.call("set_ocupados", _ocupados)
	if _capa_carrusel.has_method("set_nick"):
		_capa_carrusel.call("set_nick", _nick)
	print("[DAO] carrusel de avatares abierto desde la DAO")


func _al_confirmar(ruta: String) -> void:
	_cerrar(ruta)


func _cerrar(ruta: String = "") -> void:
	var cancelado := ruta.is_empty()
	_cerrar_capa_dao()
	if _capa_carrusel != null and is_instance_valid(_capa_carrusel):
		_capa_carrusel.queue_free()
	_capa_carrusel = null
	if _jugador != null and is_instance_valid(_jugador):
		_jugador.set_physics_process(true)
		_jugador.set_process_input(true)
	_jugador = null
	if _camara_previa != null and is_instance_valid(_camara_previa):
		_camara_previa.current = true
	_camara_previa = null
	_abierto = false
	_bloqueo_hasta = Time.get_ticks_msec() + 3500
	if cancelado and not _alta:
		set_girando(true)
	carrusel_cerrado.emit(ruta)


func _cerrar_capa_dao() -> void:
	if _camara_dao != null and is_instance_valid(_camara_dao):
		_camara_dao.queue_free()
	_camara_dao = null
	if _ui_dao != null and is_instance_valid(_ui_dao):
		_ui_dao.queue_free()
	_ui_dao = null
	_ui_nombre = null
	_ui_detalle = null
	_ui_contador = null
	_ui_aviso = null
	if _modo_dao:
		_restaurar_estatuas()
	_modo_dao = false
	_confirmando = false


# ---------------------------------------------------------------------------
# Elección in situ en el atrio (alta de ciudadano)
# ---------------------------------------------------------------------------

func abrir_en_dao(jugador: Node3D) -> bool:
	if _abierto or jugador == null or _estatuas.is_empty():
		return false
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_abierto = true
	_modo_dao = true
	_alta = true
	_confirmando = false
	_jugador = jugador
	_camara_previa = get_viewport().get_camera_3d()
	jugador.set_physics_process(false)
	jugador.set_process_input(false)
	# El aro se para para elegir y sigue parado durante el recorrido.
	if _tween_giro != null and _tween_giro.is_valid():
		_tween_giro.kill()
	_velocidad = 0.0
	_foco = _foco_inicial()
	_objetivo_aro = PI * 0.5 - _angulos[_foco]
	if _aro != null:
		_aro.rotation.y = _objetivo_aro
	_montar_camara_atrio()
	_montar_ui_atrio()
	_actualizar_ui_atrio()
	print("[DAO] carrusel de avatares abierto en el atrio")
	return true


func _foco_inicial() -> int:
	var indice := Catalogo.indice_de(Avatares.id_actual)
	if indice >= 0 and indice < _estatuas.size():
		return indice
	for i in _estatuas.size():
		if not _ocupados.has(i):
			return i
	return 0


func _mover_foco(paso: int) -> void:
	if not _modo_dao or _estatuas.is_empty():
		return
	_foco = wrapi(_foco + paso, 0, _estatuas.size())
	_objetivo_aro = PI * 0.5 - _angulos[_foco]
	_actualizar_ui_atrio()


func _animar_foco(delta: float) -> void:
	var camara := CAMARA_ATRIO
	if _camara_dao != null and is_instance_valid(_camara_dao):
		camara = _camara_dao.global_position
	for i in _estatuas.size():
		var estatua := _estatuas[i]
		if not is_instance_valid(estatua):
			continue
		var destino := _angulos[i] + PI
		if i == _foco:
			# El avatar enfocado se gira hacia la cámara del atrio.
			var hacia := camara - estatua.global_position
			destino = atan2(hacia.x, hacia.z) - _aro.rotation.y
		estatua.rotation.y = lerp_angle(estatua.rotation.y, destino, clampf(delta * 4.5, 0.0, 1.0))
		var escala := 1.06 if i == _foco else 1.0
		estatua.scale = estatua.scale.lerp(Vector3.ONE * escala, clampf(delta * 8.0, 0.0, 1.0))


func _restaurar_estatuas() -> void:
	for i in _estatuas.size():
		var estatua := _estatuas[i]
		if is_instance_valid(estatua):
			estatua.rotation.y = _angulos[i] + PI
			estatua.scale = Vector3.ONE


func _confirmar_dao() -> void:
	if not _modo_dao or _confirmando or _estatuas.is_empty():
		return
	var modelo := Catalogo.por_indice(_foco)
	if modelo.is_empty():
		return
	_confirmando = true
	var id := str(modelo["id"])
	Avatares.guardar(id)
	if not _nick.is_empty():
		Avatares.sincronizar_registro(id, _nick)
	_cerrar(str(modelo["escena"]))


func _montar_camara_atrio() -> void:
	_camara_dao = Camera3D.new()
	_camara_dao.name = "CamaraEleccionDAO"
	_camara_dao.fov = 50.0
	_camara_dao.far = 200.0
	add_child(_camara_dao)
	_camara_dao.global_position = CAMARA_ATRIO
	_camara_dao.look_at(MIRADA_ATRIO, Vector3.UP)
	_camara_dao.current = true


func _montar_ui_atrio() -> void:
	_ui_dao = CanvasLayer.new()
	_ui_dao.name = "UIEleccionDAO"
	_ui_dao.layer = 20
	add_child(_ui_dao)
	var raiz := Control.new()
	raiz.name = "Raiz"
	raiz.set_anchors_preset(Control.PRESET_FULL_RECT)
	raiz.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_dao.add_child(raiz)

	var titulo := _etiqueta_atrio("ELIGE TU AVATAR", 34, Color(0.78, 0.94, 1.0, 1.0))
	titulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	titulo.set_anchors_preset(Control.PRESET_CENTER_TOP)
	titulo.offset_left = -420.0
	titulo.offset_right = 420.0
	titulo.offset_top = 26.0
	titulo.offset_bottom = 76.0
	raiz.add_child(titulo)

	var subtitulo := _etiqueta_atrio("El carrusel de la DAO · tu avatar te espera",
			17, Color(0.66, 0.82, 1.0, 1.0))
	subtitulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitulo.set_anchors_preset(Control.PRESET_CENTER_TOP)
	subtitulo.offset_left = -420.0
	subtitulo.offset_right = 420.0
	subtitulo.offset_top = 78.0
	subtitulo.offset_bottom = 108.0
	raiz.add_child(subtitulo)

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
	anterior.pressed.connect(_mover_foco.bind(-1))
	fila.add_child(anterior)

	var centro := VBoxContainer.new()
	centro.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	centro.alignment = BoxContainer.ALIGNMENT_CENTER
	fila.add_child(centro)

	_ui_nombre = _etiqueta_atrio("", 30, Color(0.95, 0.98, 1.0, 1.0))
	_ui_nombre.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	centro.add_child(_ui_nombre)

	_ui_detalle = _etiqueta_atrio("", 15, Color(0.62, 0.82, 1.0, 1.0))
	_ui_detalle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	centro.add_child(_ui_detalle)

	_ui_contador = _etiqueta_atrio("", 14, Color(0.5, 0.7, 0.9, 1.0))
	_ui_contador.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	centro.add_child(_ui_contador)

	var siguiente := Button.new()
	siguiente.text = "▶"
	siguiente.custom_minimum_size = Vector2(56, 64)
	siguiente.add_theme_font_size_override("font_size", 26)
	siguiente.pressed.connect(_mover_foco.bind(1))
	fila.add_child(siguiente)

	var elegir := Button.new()
	elegir.text = "ELEGIR AVATAR"
	elegir.custom_minimum_size = Vector2(220, 64)
	elegir.add_theme_font_size_override("font_size", 19)
	elegir.pressed.connect(_confirmar_dao)
	fila.add_child(elegir)

	_ui_aviso = _etiqueta_atrio("", 14, Color(1.0, 0.78, 0.4, 1.0))
	_ui_aviso.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_ui_aviso.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_ui_aviso.offset_left = -420.0
	_ui_aviso.offset_right = 420.0
	_ui_aviso.offset_top = -202.0
	_ui_aviso.offset_bottom = -176.0
	raiz.add_child(_ui_aviso)

	var pista := _etiqueta_atrio("Flechas / rueda para girar · ENTER para elegir",
			13, Color(0.55, 0.66, 0.8, 0.9))
	pista.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pista.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	pista.offset_left = -460.0
	pista.offset_right = 460.0
	pista.offset_top = -174.0
	pista.offset_bottom = -152.0
	raiz.add_child(pista)


func _actualizar_ui_atrio() -> void:
	if _ui_nombre == null:
		return
	var modelo := Catalogo.por_indice(_foco)
	if modelo.is_empty():
		return
	_ui_nombre.text = str(modelo.get("nombre", ""))
	_ui_detalle.text = "%s · %s · Altura 1,80 m" % [str(modelo.get("id", "")),
			str(modelo.get("genero", "")).capitalize()]
	_ui_contador.text = "%d / %d" % [_foco + 1, _estatuas.size()]
	_ui_aviso.text = "Esa plaza ya está ocupada; se te asignará un sustituto." \
			if _ocupados.has(_foco) else ""


func _etiqueta_atrio(texto: String, tam: int, color: Color) -> Label:
	var etiqueta := Label.new()
	etiqueta.text = texto
	etiqueta.add_theme_font_size_override("font_size", tam)
	etiqueta.add_theme_color_override("font_color", color)
	etiqueta.add_theme_color_override("font_outline_color", Color(0.01, 0.04, 0.08, 1.0))
	etiqueta.add_theme_constant_override("outline_size", 6)
	etiqueta.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return etiqueta


# ---------------------------------------------------------------------------
# Materiales y API
# ---------------------------------------------------------------------------

func _mat(color: Color, roughness := 0.7, metal := 0.0,
		emision := Color.BLACK, energia := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	m.metallic = metal
	if emision != Color.BLACK:
		m.emission_enabled = true
		m.emission = emision
		m.emission_energy_multiplier = energia
	return m


func estatuas() -> Array[Node3D]:
	return _estatuas


## Datos de sesión que la capa interactiva necesita antes de abrirse.
func set_nick(nick: String) -> void:
	_nick = nick.strip_edges()


func set_ocupados(plazas: Array) -> void:
	_ocupados = plazas.duplicate()


func set_auto_abrir(activo: bool) -> void:
	_auto_abrir = activo


## Abre la capa interactiva para un jugador concreto (onboarding de la DAO).
func abrir_para(jugador: Node3D) -> bool:
	if _abierto or jugador == null:
		return false
	_abrir(jugador)
	return _abierto


## Confirma el avatar enfocado. La cinemática de onboarding lo usa cuando
## conduce ella misma la elección; en mano, basta ENTER o el botón.
func confirmar_actual() -> void:
	if _modo_dao:
		_confirmar_dao()
		return
	if _capa_carrusel != null and is_instance_valid(_capa_carrusel):
		if _capa_carrusel.has_method("confirmar_actual"):
			_capa_carrusel.call("confirmar_actual")


## Para o reanuda el giro del aro. Durante el alta el aro queda parado: reanudar
## antes de tiempo descoloca el recorrido del avatar.
func set_girando(activo: bool) -> void:
	if _modo_dao:
		return
	if _alta and activo:
		return
	var destino := VELOCIDAD_GIRO if activo else 0.0
	if is_equal_approx(_velocidad, destino):
		return
	if _tween_giro != null and _tween_giro.is_valid():
		_tween_giro.kill()
	_tween_giro = create_tween()
	_tween_giro.tween_property(self, "_velocidad", destino, 1.1) \
			.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


## Cierra el alta: a partir de aquí el aro puede girar otra vez. Se llama al
## cruzar el portal; hasta entonces la elección conduce el carrusel.
func fin_alta() -> void:
	if not _alta:
		return
	_alta = false
	if not _abierto:
		set_girando(true)


func girando() -> bool:
	return _velocidad > 0.001


func abierto() -> bool:
	return _abierto


## Verdadero mientras la elección ocurre en el propio atrio.
func seleccion_en_dao() -> bool:
	return _modo_dao


func total_estatuas() -> int:
	return _estatuas.size()
