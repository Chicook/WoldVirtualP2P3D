extends Node3D
## Alta de ciudadano dentro de la Isla Única LucIA.
##
## Recorre el alta completa con el espacio real de la DAO:
##   1. Despacho de LucIA: el nuevo jugador aparece frente al escritorio.
##   2. Plaza de registro: camina a las cuatro estaciones cardinales y las sella.
##   3. Carrusel: la DAO muestra el carrusel de avatares y el jugador elige uno.
##   4. Bienvenida: LucIA recibe al nuevo ciudadano en el metaverso.
##   5. Espejo: cinemática del avatar elegido caminando al podio, donde el
##      editor de aspecto lo personaliza dentro de la DAO, sin sala aparte.
##   6. Portal: la cámara pasa a su espalda, el jugador toma el mando y cruza el
##      portal; ahí nace su isla y `Boot` monta el mundo.
##
## Durante el alta sólo existen la DAO y su mar: las islas de jugador aparecen
## cuando el portal registra la isla, nunca antes.

signal fase_cambiada(fase: StringName)
signal onboarding_completado(avatar_scene: String)

const RUTA_DAO := "res://lucia3D/IslaUnicaLucIA/ESCENAS/IslaUnicaLucIA.tscn"
const RUTA_MUNDO := "res://WoldVirtual3DP2P.tscn"
const RUTA_BLOQUE := "res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"
const EDITOR_SCENE: PackedScene = preload("res://avatares/EditorAspecto.tscn")
const VozLucIA = preload("res://lucia3D/IslaUnicaLucIA/ONBOARDING/VozLucIA.gd")
const Catalogo = preload("res://avatares/CatalogoAvatares.gd")
const Identidad = preload("res://gdscrip/Identidad.gd")
const RedSesion = preload("res://gdscrip/Red.gd")

const SUELO_ATRIO := 41.7
const ALTO_DAIS := 42.2
const OFICINA_SPAWN := Vector3(0.0, 42.2, 5.2)

@export var autoprueba := false

var _nick := ""
var _modular_token := ""
var _enlace_invitacion := ""
var _sonda: Node = null
var _ocupados: Array = []
var _dao: Node3D = null
var _interior: Node = null
var _plaza: Node = null
var _carrusel: Node = null
var _portal: Node = null
var _zona: Node3D = null
var _jugador: Node3D = null
var _lucia: Node3D = null
var _lucia_anclaje: Node3D = null
var _lucia_sigue := false
## Cuerpos que el rayo de suelo de LucIA no debe pisar: la malla de la isla
## (su cúpula tiene colisión trimesh) y su propia cápsula estática del despacho.
var _exclusiones_suelo: Array[RID] = []
var _editor: Node3D = null
var _avatar_id := ""
var _cruzando := false
var _fase: StringName = &""
var _regreso := false
var _contenedor_miembros_dao: Node3D = null
var _avatares_miembros_dao: Dictionary = {}

# Sistema Blockchain DAO de 4 bloques en estaciones
var _bloques_dao: Array = []
var _ultimo_hash_bloque := ""
var _panel_estacion: PanelContainer = null
var _btn_aceptar_proteger: Button = null
var _lbl_estacion_hash: Label = null
var _lbl_estacion_info: Label = null
var _confirmado_estacion := false

var _camara: Camera3D = null
var _cam_pos: Node3D = null
var _cam_meta: Node3D = null
var _tween_camara: Tween = null
var _seguir := false
var _offset_seguir := Vector3(4.2, 1.9, -3.6)

var _hud: CanvasLayer = null
var _dialogo: PanelContainer = null
var _dialogo_nombre: Label = null
var _dialogo_texto: Label = null
var _paso_label: Label = null
var _pista_label: Label = null
var _tween_dialogo: Tween = null

var _voz_oficial: Node = null


func set_nick(nick: String) -> void:
	_nick = nick.strip_edges()


func set_ocupados(plazas: Array) -> void:
	_ocupados = plazas.duplicate()


func _ready() -> void:
	if OS.get_environment("WVP_DAO_FLOW_TEST") == "1":
		autoprueba = true
		print("[OnboardingDAO] Modo de prueba integral activado para este perfil aislado")
	if get_tree().current_scene == self or get_parent() == get_tree().root:
		name = "WoldVirtual3DP2P"
		if get_node_or_null("Sonda") == null:
			var sonda := preload("res://gdscrip/Sonda.gd").new()
			sonda.name = "Sonda"
			add_child(sonda)
	if FileAccess.file_exists("user://abrir_recepcion.flag"):
		DirAccess.remove_absolute(ProjectSettings.globalize_path("user://abrir_recepcion.flag"))
	var perfil := ConfigFile.new()
	if perfil.load("user://registro.cfg") == OK and FileAccess.file_exists("user://cuenta.json"):
		var cuenta = JSON.parse_string(FileAccess.get_file_as_string("user://cuenta.json"))
		_regreso = cuenta is Dictionary and not str(cuenta.get("cuenta_hash", "")).is_empty() \
				and not str(perfil.get_value("jugador", "avatar_scene", "")).is_empty()
	_entorno()
	_mar()
	_montar_dao()
	await get_tree().process_frame
	await get_tree().process_frame
	if _dao == null:
		push_error("[OnboardingDAO] sin Isla Única LucIA; el alta no puede empezar")
		return
	_plaza = _dao.call("plaza_registro") if _dao.has_method("plaza_registro") else null
	_interior = _dao.get_node_or_null("InteriorDAO")
	if _interior != null:
		_carrusel = _interior.call("carrusel")
		_portal = _interior.call("portal")
		_zona = _interior.call("zona_personalizacion")
		_lucia = _interior.call("lucia") if _interior.has_method("lucia") else null
		if _lucia != null:
			_lucia_anclaje = _lucia.get_parent() as Node3D
	_preparar_exclusiones_suelo()
	if _carrusel != null:
		if _carrusel.has_method("set_nick"):
			_carrusel.call("set_nick", _nick)
		if _carrusel.has_method("set_ocupados"):
			_carrusel.call("set_ocupados", _ocupados)
		# La cinemática decide cuándo se abre: la proximidad queda apagada.
		if _carrusel.has_method("set_auto_abrir"):
			_carrusel.call("set_auto_abrir", false)
	if _portal is Area3D:
		# La salida del despacho cruza la vertical del portal; sin monitor no hay
		# cruce accidental durante la cinemática.
		(_portal as Area3D).monitoring = false
	_crear_jugador()
	_crear_camara()
	_construir_hud()
	_voz_oficial = VozLucIA.new()
	_voz_oficial.name = "VozLucIA"
	add_child(_voz_oficial)
	if _portal != null and _portal.has_signal("portal_cruzado"):
		_portal.connect("portal_cruzado", _al_cruzar_portal)
	if _regreso:
		_interior.call("configurar_asamblea")
		if _plaza != null:
			_plaza.hide()
			_plaza.process_mode = Node.PROCESS_MODE_DISABLED
		_recepcion_ciudadano()
	else:
		_secuencia()
	if ServicioConexionModular.habilitado():
		if not ServicioConexionModular.miembros_actualizados.is_connected(_actualizar_miembros_dao):
			ServicioConexionModular.miembros_actualizados.connect(_actualizar_miembros_dao)
		await ServicioConexionModular.refrescar_miembros(_sonda)


# ---------------------------------------------------------------------------
# Montaje del espacio real
# ---------------------------------------------------------------------------

func _entorno() -> void:
	if get_tree().root.find_child("WorldEnvironment", true, false) != null:
		return
	var recurso: Resource = load(RUTA_MUNDO)
	if not (recurso is PackedScene):
		return
	var mundo: Node = (recurso as PackedScene).instantiate()
	var ambiente: Node = mundo.get_node_or_null("WorldEnvironment")
	var sol: Node = mundo.get_node_or_null("DirectionalLight3D")
	if ambiente != null:
		ambiente.owner = null
		mundo.remove_child(ambiente)
		add_child(ambiente)
	if sol != null:
		sol.owner = null
		mundo.remove_child(sol)
		add_child(sol)
	mundo.free()


func _mar() -> void:
	var plantilla: Resource = load(RUTA_BLOQUE)
	if not (plantilla is PackedScene):
		return
	var bloque: Node = (plantilla as PackedScene).instantiate()
	var oceano: Node = bloque.get_node_or_null("Oceano3D")
	if oceano == null:
		bloque.free()
		return
	bloque.remove_child(oceano)
	oceano.owner = null
	var contenedor := Node3D.new()
	contenedor.name = "BloqueDAO"
	add_child(contenedor)
	contenedor.add_child(oceano)
	bloque.free()


func _montar_dao() -> void:
	# La escena principal (WoldVirtual3DP2P) ya trae la sede como hermana del
	# mundo. Instanciar otra la descartaría por duplicada y el alta se quedaría
	# sin DAO; se reutiliza la que ya está viva.
	var existente := get_tree().get_first_node_in_group("isla_unica_lucia") as Node3D
	if existente != null:
		_dao = existente
		return
	var recurso: Resource = load(RUTA_DAO)
	if not (recurso is PackedScene):
		push_error("[OnboardingDAO] no carga " + RUTA_DAO)
		return
	_dao = (recurso as PackedScene).instantiate() as Node3D
	if _dao == null:
		return
	add_child(_dao)


func _crear_jugador() -> void:
	var id := Avatares.id_actual
	if id.is_empty():
		id = str(Catalogo.por_indice(0).get("id", ""))
	if id.is_empty():
		return
	_avatar_id = id
	var nodo: Node3D = Catalogo.crear(id)
	if nodo == null:
		return
	nodo.name = "Jugador"
	nodo.set("es_selector", true)
	nodo.position = OFICINA_SPAWN
	# Aún no hay avatar elegido: el arranque es de LucIA y el avatar se muestra
	# al confirmarse en el carrusel.
	nodo.visible = false
	add_child(nodo)
	# El avatar mira hacia su +Z local: se encara al despacho, no con look_at.
	nodo.rotation.y = atan2(0.0 - OFICINA_SPAWN.x, -0.6 - OFICINA_SPAWN.z)
	_jugador = nodo


func _crear_camara() -> void:
	_cam_pos = Node3D.new()
	_cam_pos.name = "CamPos"
	add_child(_cam_pos)
	_cam_meta = Node3D.new()
	_cam_meta.name = "CamMeta"
	add_child(_cam_meta)
	_camara = Camera3D.new()
	_camara.name = "CamaraDAO"
	_camara.fov = 46.0
	_camara.far = 3000.0
	add_child(_camara)
	_camara.current = true


# ---------------------------------------------------------------------------
# HUD de la cinemática
# ---------------------------------------------------------------------------

func _construir_hud() -> void:
	_hud = CanvasLayer.new()
	_hud.name = "HUDOnboarding"
	_hud.layer = 40
	add_child(_hud)

	var cabecera := Label.new()
	cabecera.text = "SEDE DE LA DAO · ASAMBLEAS" if _regreso else "SEDE DE LA DAO · ALTA DE CIUDADANO"
	cabecera.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cabecera.set_anchors_preset(Control.PRESET_CENTER_TOP)
	cabecera.offset_left = -520.0
	cabecera.offset_right = 520.0
	cabecera.offset_top = 22.0
	cabecera.offset_bottom = 52.0
	cabecera.add_theme_font_size_override("font_size", 20)
	cabecera.add_theme_color_override("font_color", Color(0.95, 0.82, 0.45))
	cabecera.add_theme_color_override("font_outline_color", Color(0.02, 0.04, 0.07))
	cabecera.add_theme_constant_override("outline_size", 6)
	cabecera.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(cabecera)

	_paso_label = Label.new()
	_paso_label.text = "1 · El despacho de LucIA"
	_paso_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_paso_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_paso_label.offset_left = -520.0
	_paso_label.offset_right = 520.0
	_paso_label.offset_top = 56.0
	_paso_label.offset_bottom = 90.0
	_paso_label.add_theme_font_size_override("font_size", 26)
	_paso_label.add_theme_color_override("font_color", Color(0.6, 0.9, 1.0))
	_paso_label.add_theme_color_override("font_outline_color", Color(0.02, 0.04, 0.07))
	_paso_label.add_theme_constant_override("outline_size", 6)
	_paso_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_paso_label)

	_dialogo = PanelContainer.new()
	_dialogo.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dialogo.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_dialogo.offset_left = -520.0
	_dialogo.offset_right = 520.0
	_dialogo.offset_top = -152.0
	_dialogo.offset_bottom = -42.0
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.015, 0.035, 0.06, 0.9)
	estilo.border_color = Color(0.72, 0.54, 0.18, 0.9)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(12)
	estilo.content_margin_left = 22.0
	estilo.content_margin_right = 22.0
	estilo.content_margin_top = 12.0
	estilo.content_margin_bottom = 12.0
	_dialogo.add_theme_stylebox_override("panel", estilo)
	_hud.add_child(_dialogo)
	var caja := VBoxContainer.new()
	caja.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_theme_constant_override("separation", 4)
	_dialogo.add_child(caja)
	_dialogo_nombre = Label.new()
	_dialogo_nombre.text = "LucIA"
	_dialogo_nombre.add_theme_font_size_override("font_size", 15)
	_dialogo_nombre.add_theme_color_override("font_color", Color(0.95, 0.82, 0.45))
	_dialogo_nombre.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(_dialogo_nombre)
	_dialogo_texto = Label.new()
	_dialogo_texto.text = ""
	_dialogo_texto.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_dialogo_texto.add_theme_font_size_override("font_size", 19)
	_dialogo_texto.add_theme_color_override("font_color", Color(0.86, 0.94, 1.0))
	_dialogo_texto.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(_dialogo_texto)

	_pista_label = Label.new()
	_pista_label.text = ""
	_pista_label.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	_pista_label.offset_left = 34.0
	_pista_label.offset_right = 780.0
	_pista_label.offset_top = -32.0
	_pista_label.offset_bottom = -10.0
	_pista_label.add_theme_font_size_override("font_size", 14)
	_pista_label.add_theme_color_override("font_color", Color(0.55, 0.72, 0.9))
	_pista_label.add_theme_color_override("font_outline_color", Color(0.02, 0.04, 0.07))
	_pista_label.add_theme_constant_override("outline_size", 4)
	_pista_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_pista_label)


func _decir(nombre: String, texto: String, segundos := 4.0) -> void:
	if _dialogo == null:
		return
	if _tween_dialogo != null and _tween_dialogo.is_valid():
		_tween_dialogo.kill()
	_dialogo_nombre.text = nombre
	_dialogo_texto.text = texto
	_dialogo.modulate.a = 1.0
	_dialogo.visible = true
	_tween_dialogo = create_tween()
	_tween_dialogo.tween_interval(segundos)
	_tween_dialogo.tween_property(_dialogo, "modulate:a", 0.0, 0.5)
	_tween_dialogo.tween_callback(func(): _dialogo.visible = false)


# ---------------------------------------------------------------------------
# Voz de LucIA
# ---------------------------------------------------------------------------

## LucIA habla en segundo plano: subtítulo y voz a la vez.
func _lucia_dice(texto: String, segundos := 0.0) -> void:
	if segundos <= 0.0:
		segundos = clampf(2.5 + float(texto.length()) / 16.0, 3.5, 9.0)
	_decir("LucIA", texto, segundos)
	_voz(texto)


func _voz(texto: String) -> void:
	if _voz_oficial != null:
		_voz_oficial.call("decir", texto)


func _callar() -> void:
	if _voz_oficial != null:
		_voz_oficial.call("callar")


func _voz_sonando() -> bool:
	return _voz_oficial != null and bool(_voz_oficial.call("esta_hablando"))


## Espera a que la línea actual termine. El tope evita bloquear el alta si el
## backend de voz no confirma el final (driver sin audio, TTS colgado).
func _esperar_voz(maximo := 90.0) -> void:
	var limite := Time.get_ticks_msec() + int(maximo * 1000.0)
	while _voz_sonando() and Time.get_ticks_msec() < limite:
		await get_tree().process_frame


func _exit_tree() -> void:
	_callar()


func _paso(texto: String) -> void:
	if _paso_label != null:
		_paso_label.text = texto


func _pista(texto: String) -> void:
	if _pista_label != null:
		_pista_label.text = texto


func _marcar(nombre: StringName) -> void:
	_fase = nombre
	fase_cambiada.emit(nombre)


func _esperar(seg: float) -> void:
	await get_tree().create_timer(seg).timeout


# ---------------------------------------------------------------------------
# Cinemática
# ---------------------------------------------------------------------------

func _process(delta: float) -> void:
	# La ancla de LucIA fija su altura; al acompañar al avatar debe pisar el
	# atrio y la rampa igual que él, no quedarse flotando a la altura del dais.
	if _lucia_sigue and _lucia != null and _lucia_anclaje != null:
		var p := _lucia.global_position
		var espacio := get_world_3d().direct_space_state
		if espacio != null:
			var rayo := PhysicsRayQueryParameters3D.create(
					Vector3(p.x, p.y + 2.0, p.z), Vector3(p.x, p.y - 3.0, p.z))
			var exclusiones := _exclusiones_suelo.duplicate()
			if _jugador is CollisionObject3D:
				exclusiones.append((_jugador as CollisionObject3D).get_rid())
			rayo.exclude = exclusiones
			var golpe := espacio.intersect_ray(rayo)
			if not golpe.is_empty():
				_lucia_anclaje.global_position.y = float(golpe["position"].y)

	if _camara == null or _cam_pos == null or _cam_meta == null:
		return
	if _seguir and _jugador != null:
		var meta := _jugador.global_position + Vector3(0.0, 1.25, 0.0)
		var destino := _jugador.global_position + _offset_seguir
		_cam_meta.global_position = _cam_meta.global_position.lerp(meta, clampf(delta * 4.5, 0.0, 1.0))
		_cam_pos.global_position = _cam_pos.global_position.lerp(destino, clampf(delta * 2.8, 0.0, 1.0))
	_camara.global_position = _cam_pos.global_position
	if _camara.global_position.distance_to(_cam_meta.global_position) > 0.05:
		_camara.look_at(_cam_meta.global_position, Vector3.UP)


func _encuadrar(pos: Vector3, meta: Vector3, fov := 46.0) -> void:
	_seguir = false
	if _tween_camara != null and _tween_camara.is_valid():
		_tween_camara.kill()
	_cam_pos.global_position = pos
	_cam_meta.global_position = meta
	_camara.fov = fov
	_camara.global_position = pos
	_camara.look_at(meta, Vector3.UP)
	# El carrusel y el editor devuelven su cámara al liberarse; el encuadre de la
	# cinemática siempre vuelve a tomar el mando.
	_camara.current = true


func _tomar_camara(pos: Vector3, meta: Vector3, dur: float, fov := -1.0) -> void:
	_seguir = false
	if _tween_camara != null and _tween_camara.is_valid():
		_tween_camara.kill()
	_tween_camara = create_tween()
	_tween_camara.set_parallel(true)
	_tween_camara.tween_property(_cam_pos, "global_position", pos, dur).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_tween_camara.tween_property(_cam_meta, "global_position", meta, dur).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	if fov > 0.0:
		_tween_camara.tween_property(_camara, "fov", fov, dur)


func _orientar(hacia: Vector3) -> void:
	if _jugador == null:
		return
	var actual := _jugador.global_position
	var plano := Vector3(hacia.x, actual.y, hacia.z)
	var delta := plano - actual
	if Vector2(delta.x, delta.z).length() < 0.05:
		return
	# El avatar mira hacia su +Z local; look_at() giraría su espalda al destino.
	_jugador.rotation = Vector3(0.0, atan2(delta.x, delta.z), 0.0)


func _caminar(puntos: Array, velocidad := 2.2, seguir := true, lateral := 1.35) -> void:
	if _jugador == null:
		return
	_seguir = seguir
	_jugador.call("reproducir_animacion", Catalogo.ANIM_WALK, false, 1.05)
	for i in range(1, puntos.size()):
		var hasta: Vector3 = puntos[i]
		var desde := _jugador.global_position
		var plano := Vector3(hasta.x - desde.x, 0.0, hasta.z - desde.z)
		var lado := Vector3.RIGHT
		if plano.length() > 0.2:
			var dir := plano.normalized()
			lado = dir.cross(Vector3.UP).normalized()
			_offset_seguir = -dir * 4.6 + lado * 1.8 + Vector3(0.0, 2.05, 0.0)
		_orientar(hasta)
		if _lucia_sigue:
			_lucia_caminar(hasta + lado * lateral, velocidad)
		var dur := maxf(desde.distance_to(hasta) / maxf(velocidad, 0.1), 0.18)
		var tw := create_tween()
		tw.tween_property(_jugador, "global_position", hasta, dur).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		await tw.finished
	_jugador.call("reproducir_animacion", Catalogo.ANIM_IDLE, true)


## LucIA recorre el mismo tramo que el avatar, un paso por delante y a su lado.
func _lucia_caminar(punto_global: Vector3, velocidad: float) -> void:
	if _lucia == null or _lucia_anclaje == null:
		return
	_lucia.call("fijar_velocidad_andar", velocidad + 0.25)
	_lucia.call("caminar_hasta", _lucia_anclaje.to_local(punto_global))


func _lucia_a(punto_global: Vector3) -> void:
	if _lucia == null or _lucia_anclaje == null:
		return
	_lucia_anclaje.global_position.y = punto_global.y
	_lucia.call("teleportar", _lucia_anclaje.to_local(punto_global))
	_columna(punto_global)


func _punto(x: float, z: float, esperado: float) -> Vector3:
	return Vector3(x, _suelo(x, z, esperado), z)


func _suelo(x: float, z: float, esperado: float) -> float:
	var espacio := get_world_3d().direct_space_state
	if espacio == null:
		return esperado
	var consulta := PhysicsRayQueryParameters3D.create(
			Vector3(x, esperado + 1.4, z), Vector3(x, esperado - 1.4, z))
	if _jugador is CollisionObject3D:
		consulta.exclude = [(_jugador as CollisionObject3D).get_rid()]
	var golpe := espacio.intersect_ray(consulta)
	if golpe.is_empty():
		return esperado
	return float((golpe["position"] as Vector3).y)


## La cúpula del GLB de la isla lleva colisión trimesh. El rayo de suelo de
## LucIA la tomaba por un piso y la subía por su cara interna hasta el techo,
## así que se descarta la malla de la isla y su cápsula estática del despacho.
## El avatar del jugador se añade aparte en cada consulta (cambia al elegirlo).
func _preparar_exclusiones_suelo() -> void:
	_exclusiones_suelo.clear()
	if _dao != null:
		_recoger_cuerpos(_dao.get_node_or_null("MallaIsla"))
	if _interior != null:
		_recoger_cuerpos(_interior.get_node_or_null("ColisionLucIA"))


func _recoger_cuerpos(nodo: Node) -> void:
	if nodo == null:
		return
	if nodo is CollisionObject3D:
		_exclusiones_suelo.append((nodo as CollisionObject3D).get_rid())
	for hijo in nodo.get_children():
		_recoger_cuerpos(hijo)


func _desplazar(destino: Vector3, mirar := Vector3.ZERO) -> void:
	_columna(_jugador.global_position if _jugador != null else destino)
	_tomar_camara(destino + Vector3(7.0, 5.5, 8.0), destino + Vector3(0.0, 1.2, 0.0), 0.55, 46.0)
	await _esperar(0.58)
	if _jugador == null:
		return
	_jugador.global_position = destino + Vector3(0.0, 0.05, 0.0)
	if mirar != Vector3.ZERO:
		_orientar(destino + mirar)
	_columna(destino)
	await _esperar(0.22)


func _columna(pos: Vector3, dur := 0.9) -> void:
	var raiz := Node3D.new()
	raiz.name = "ColumnaDAO"
	add_child(raiz)
	raiz.global_position = pos
	var mi := MeshInstance3D.new()
	var cil := CylinderMesh.new()
	cil.top_radius = 0.85
	cil.bottom_radius = 1.3
	cil.height = 9.0
	cil.radial_segments = 48
	mi.mesh = cil
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.albedo_color = Color(0.35, 0.78, 1.0, 0.28)
	mi.material_override = mat
	mi.position = Vector3(0.0, 4.5, 0.0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	raiz.add_child(mi)
	var luz := OmniLight3D.new()
	luz.light_color = Color(0.35, 0.8, 1.0)
	luz.light_energy = 3.0
	luz.omni_range = 7.0
	luz.position = Vector3(0.0, 2.2, 0.0)
	raiz.add_child(luz)
	var tw := create_tween()
	tw.tween_property(raiz, "scale", Vector3(1.5, 1.15, 1.5), 0.9)
	tw.tween_interval(maxf(dur - 1.6, 0.0))
	tw.tween_property(mi, "transparency", 1.0, 0.7)
	tw.finished.connect(raiz.queue_free)


# ---------------------------------------------------------------------------
# Secuencia del alta
# ---------------------------------------------------------------------------

func _recepcion_ciudadano() -> void:
	_marcar(&"asamblea")
	_paso("Asamblea de la DAO")
	_encuadrar(Vector3(18.0, 44.8, 8.0), Vector3(0.0, 42.9, 0.0), 48.0)
	_jugador.visible = true
	_lucia_dice("Bienvenido de nuevo a la DAO. Tu cuenta y tu avatar se conservan. La sede está preparada para las asambleas.", 9.0)
	await _esperar_voz()
	if _cruzando:
		return
	await _entregar_control()
	if _cruzando:
		return
	_jugador.global_position = Vector3(0.0, SUELO_ATRIO + 0.03, 9.0)
	_orientar(Vector3(14.0, SUELO_ATRIO, 0.0))
	_jugador.call("snap_camera")
	_paso("Asamblea de la DAO")
	_marcar(&"asamblea")


func _solicitar_nick() -> void:
	_marcar(&"nick")
	_paso("2 · Tu nombre en el metaverso")
	_lucia_dice("¿Cómo quieres que te llame? Escribe tu nick antes de elegir tu avatar.", 5.0)
	var panel := PanelContainer.new()
	panel.name = "SolicitudNick"
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.offset_left = -260.0
	panel.offset_right = 260.0
	panel.offset_top = -85.0
	panel.offset_bottom = 85.0
	_hud.add_child(panel)
	var columna := VBoxContainer.new()
	columna.add_theme_constant_override("separation", 8)
	panel.add_child(columna)
	var titulo := Label.new()
	titulo.text = "Identidad en la DAO"
	columna.add_child(titulo)
	var entrada := LineEdit.new()
	entrada.max_length = 32
	entrada.placeholder_text = "Escribe tu nombre"
	if _nick.is_empty():
		_nick = "Vecino"
	entrada.text = _nick
	columna.add_child(entrada)
	var conectar := Button.new()
	conectar.text = "🏛 CONECTAR PARA VER A TUS VECINOS EN LA DAO"
	conectar.disabled = false
	conectar.visible = true
	columna.add_child(conectar)
	entrada.text_submitted.connect(func(_texto: String):
		if not conectar.disabled:
			conectar.pressed.emit())
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	entrada.grab_focus()
	if autoprueba:
		entrada.text = OS.get_environment("WVP_DAO_TEST_NICK").strip_edges()
		if entrada.text.is_empty():
			entrada.text = "PruebaDAO"
	var estado := Label.new()
	estado.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	estado.text = "Pincha en conectar para abrir el túnel efímero y ver a tus vecinos en la DAO."
	columna.add_child(estado)
	var sonda := get_node_or_null("Sonda")
	if sonda == null:
		sonda = get_parent().get_node_or_null("Sonda")
	_sonda = sonda
	if ServicioConexionModular.has_method("establecer_sonda"):
		ServicioConexionModular.establecer_sonda(_sonda)
	_lucia_dice("Pincha en conectar para ver a tus vecinos en la DAO.", 5.0)
	if autoprueba:
		conectar.call_deferred("emit_signal", "pressed")
	while true:
		await conectar.pressed
		_nick = entrada.text.strip_edges()
		if _nick.is_empty():
			_nick = "Vecino"
		entrada.editable = false
		conectar.disabled = true
		var objetivo_red: Dictionary = RedSesion.resolver_objetivo()
		var tunel: Dictionary
		if bool(objetivo_red.get("is_client", false)):
			estado.text = "Enlace de invitación detectado. Conectando con el anfitrión…"
			tunel = {"exito": true, "mensaje": "Conectando con el anfitrión de la invitación."}
		else:
			estado.text = "Abriendo el túnel efímero de invitación…"
			tunel = await _solicitar_tunel_invitacion()
		if not bool(tunel.get("exito", false)):
			estado.text = str(tunel.get("mensaje", "El visor no pudo abrir el túnel efímero."))
			conectar.disabled = false
			continue
		_enlace_invitacion = str(tunel.get("enlace", tunel.get("url", ""))).strip_edges()
		if not _enlace_invitacion.is_empty():
			DisplayServer.clipboard_set(_enlace_invitacion)
			estado.text = "Túnel activo. Enlace de invitación copiado. Validando la sesión P2P…"
		else:
			estado.text = "Túnel activo. Validando la sesión P2P…"
		var resultado: Dictionary = {"ok": false, "error": "No hay Sonda de sesión"}
		if sonda != null:
			resultado = await sonda.validar_conexion()
		if not bool(resultado.get("ok", false)):
			estado.text = str(resultado.get("error", "Conexión no validada")) + ". Reintenta."
			conectar.disabled = false
			continue
		_ocupados = resultado.get("ocupados", []).duplicate()
		if ServicioConexionModular.habilitado():
			estado.text = "Sesión P2P lista. Conectando el registro con la DAO…"
			var conexion: Dictionary = await ServicioConexionModular.conectar(_nick, _sonda)
			if not bool(conexion.get("ok", false)):
				estado.text = str(conexion.get("body", {}).get("error", "No se pudo conectar con el servidor DAO."))
				conectar.disabled = false
				continue
			_modular_token = str(conexion.get("body", {}).get("token", ""))
		estado.text = "Conectado con LucIA. El enlace efímero está copiado para invitar a otra persona."
		await get_tree().create_timer(1.2).timeout
		break
	_carrusel.call("set_ocupados", _ocupados)
	_carrusel.call("set_nick", _nick)
	panel.queue_free()
	await _esperar_voz()


func _solicitar_tunel_invitacion() -> Dictionary:
	# MainWindow.xaml.cs vigila este buzón en user:// y levanta el mismo túnel
	# efímero que se usa al crear/copiar un enlace de invitación.
	var ruta_solicitud := ProjectSettings.globalize_path("user://tunel_solicitud.json")
	var ruta_temporal := ruta_solicitud + ".tmp"
	var ruta_resultado := ProjectSettings.globalize_path("user://validacion_resultado.json")
	if FileAccess.file_exists("user://validacion_resultado.json"):
		DirAccess.remove_absolute(ruta_resultado)
	var solicitud := FileAccess.open("user://tunel_solicitud.json.tmp", FileAccess.WRITE)
	if solicitud == null:
		return {"exito": false, "mensaje": "No se pudo solicitar el túnel al visor."}
	solicitud.store_string(JSON.stringify({"accion": "conectar", "nick": _nick}))
	solicitud.close()
	var renombrar := DirAccess.rename_absolute(ruta_temporal, ruta_solicitud)
	if renombrar != OK:
		return {"exito": false, "mensaje": "No se pudo enviar la solicitud del túnel al visor."}

	var limite := Time.get_ticks_msec() + 120000
	while Time.get_ticks_msec() < limite:
		if FileAccess.file_exists("user://validacion_resultado.json"):
			var respuesta: Variant = JSON.parse_string(FileAccess.get_file_as_string("user://validacion_resultado.json"))
			if respuesta is Dictionary:
				return respuesta
		await get_tree().create_timer(0.2).timeout
	return {"exito": false, "mensaje": "El túnel no respondió en 120 segundos. Revisa la conexión y vuelve a pulsar Conectar."}


func _secuencia() -> void:
	_marcar(&"despacho")
	_paso("1 · El despacho de LucIA")
	_encuadrar(Vector3(2.4, 43.4, 3.6), Vector3(0.0, 42.95, -0.6), 36.0)
	if _lucia != null:
		var frente := _camara.global_position - _lucia.global_position
		_lucia.global_rotation.y = atan2(frente.x, frente.z)

	if _portal is Node3D:
		(_portal as Node3D).hide()
	var saludo_lucia := "Bienvenido a la Sede de la DAO. Soy LucIA y te acompañaré durante el registro."
	_lucia_dice(saludo_lucia, 5.5)
	await _esperar(2.6)
	_tomar_camara(Vector3(1.7, 43.35, 2.9), Vector3(0.0, 43.0, -0.6), 2.0, 34.0)
	# Cada frase termina antes de empezar la siguiente: nada de cortes a medias.
	await _esperar_voz()
	await _solicitar_nick()
	if _cruzando:
		return
	_lucia_dice("Tu cuenta se registra en las cuatro estaciones de la plaza.", 5.0)
	await _esperar_voz()

	_lucia_dice("Antes de recorrer la sede, elige tu avatar: será tu identidad aquí.", 4.0)
	await _esperar_voz()

	await _carrusel_avatares()
	if _cruzando:
		return

	_paso("3 · La plaza de registro")
	_marcar(&"salida")
	# El avatar ya está elegido: LucIA baja del estrado y lo acompaña por la DAO.
	_lucia_sigue = true
	_lucia_a(_jugador.global_position + Vector3(1.4, 0.0, 0.0))
	_lucia_dice("Ese avatar es tu aspecto en el metaverso. Sígueme: bajamos por la rampa sur; el portal queda para el final.", 4.5)
	_seguir = true
	await _caminar([
		_jugador.global_position,
		_punto(13.0, 15.9, SUELO_ATRIO),
		_punto(9.6, 16.4, SUELO_ATRIO),
		_punto(5.0, 17.2, SUELO_ATRIO),
		_punto(0.0, 20.4, SUELO_ATRIO),
	], 2.2)
	if _cruzando:
		return
	_encuadrar(Vector3(17.0, 46.4, 27.0), Vector3(0.0, 41.4, 20.0), 48.0)
	await _esperar(1.2)
	await _caminar([
		_jugador.global_position,
		_punto(0.0, 27.6, SUELO_ATRIO),
		_punto(0.0, 30.9, SUELO_ATRIO),
		_punto(0.0, 36.1, 40.2),
	], 2.2)
	if _cruzando:
		return
	_encuadrar(Vector3(10.6, 44.6, 44.6), Vector3(0.0, 40.8, 33.6), 44.0)
	await _esperar(1.0)
	_lucia_dice("La DAO reparte el alta en cuatro estaciones. Empecemos por la identidad, al norte.", 4.5)
	await _esperar_voz()

	await _registro_estaciones()
	if not await _registrar_en_servidor_modular():
		return
	await _bienvenida_metaverso()
	await _caminar_al_espejo()
	_abrir_editor()


func _registro_estaciones() -> void:
	if _cruzando:
		return
	var estaciones := [
		{"clave": &"identidad", "nombre": "Identidad", "bloque": 1,
			"llegada": Vector3(0.0, 41.6, -32.2), "puesto": Vector3(0.0, 41.6, -34.4),
			"cam": [Vector3(6.2, 43.9, -26.0), Vector3(0.0, 41.2, -35.2)],
			"texto": "Identidad: tu cuenta queda ligada a esta isla y no se repite en el archipiélago.",
			"detalle": "Mina el Bloque #1: Crea el anclaje criptográfico de tu identidad única en la blockchain de la DAO.",
			"garantia": "Nadie puede crear una segunda identidad con tu nombre ni copiar la tuya: el anclaje es único en todo el archipiélago."},
		{"clave": &"cuenta_unica", "nombre": "Cuenta única", "bloque": 2,
			"llegada": Vector3(32.2, 41.6, 0.0), "puesto": Vector3(34.4, 41.6, 0.0),
			"cam": [Vector3(29.2, 44.9, 7.6), Vector3(34.4, 42.2, 0.0)],
			"texto": "Cuenta única: una sola cuenta por persona, firmada por la DAO.",
			"detalle": "Mina el Bloque #2: Vinculación de cuenta personal con firma simétrica inmutable.",
			"garantia": "La DAO firma tu cuenta: si alguien intenta duplicarla o cambiar su dueño, la firma deja de cuadrar y la operación se rechaza."},
		{"clave": &"huella_equipo", "nombre": "Huella del equipo", "bloque": 3,
			"llegada": Vector3(-32.2, 41.6, 0.0), "puesto": Vector3(-34.4, 41.6, 0.0),
			"cam": [Vector3(-29.2, 44.9, 7.6), Vector3(-34.4, 41.35, 0.0)],
			"texto": "Huella del equipo: este dispositivo queda reconocido para tus próximas sesiones.",
			"detalle": "Mina el Bloque #3: Sella el hash de hardware (UUID) para acceso seguro sin contraseña.",
			"garantia": "Solo tu equipo puede entrar sin contraseña. Si otra máquina lo intenta, la huella no coincide y el acceso queda bloqueado."},
		{"clave": &"firma_sesion", "nombre": "Firma de sesión", "bloque": 4,
			"llegada": Vector3(0.0, 41.6, 32.2), "puesto": Vector3(0.0, 41.6, 34.4),
			"cam": [Vector3(-6.2, 43.9, 26.0), Vector3(0.0, 41.2, 35.2)],
			"texto": "Firma de sesión: cada entrada se sella aquí. Nadie puede suplantarte.",
			"detalle": "Mina el Bloque #4: Firma de sesión viva anti-suplantación (P2P Handshake).",
			"garantia": "Cada conexión lleva una firma viva que caduca: aunque alguien espíe la red, no puede reutilizarla para hacerse pasar por ti."},
	]

	# Inicializar la cadena de bloques local si no hay previa
	_inicializar_bloques_dao()

	for i in estaciones.size():
		var e: Dictionary = estaciones[i]
		var clave: StringName = e["clave"]
		var destino := _punto(e["llegada"].x, e["llegada"].z, e["llegada"].y)
		var puesto := _punto(e["puesto"].x, e["puesto"].z, e["puesto"].y)
		if i > 0:
			_decir("DAO", "La DAO te desplaza a la siguiente estación.", 2.0)
		await _desplazar(destino, puesto - destino)
		if _lucia_sigue:
			var dir := (puesto - destino).normalized()
			_lucia_a(destino + dir.cross(Vector3.UP).normalized() * 1.35)
		_paso("%d · %s (Bloque #%d)" % [i + 1, e["nombre"], e["bloque"]])
		_seguir = true
		_lucia_dice(e["texto"], 4.0)
		await _caminar([_jugador.global_position, puesto], 1.9)
		var cam: Array = e["cam"]
		_encuadrar(cam[0], cam[1], 42.0)
		_marcar(StringName("estacion_" + str(i + 1)))
		if _plaza != null:
			_plaza.call("abrir", clave)

		# Mostrar diálogo interactivo de la estación para "Aceptar y proteger mi cuenta"
		await _mostrar_dialogo_estacion_proteccion(e)

		# Minar/generar el bloque correspondiente
		var bloque_hash := _minar_bloque_estacion(e)

		if _plaza != null:
			_plaza.call("completar", clave,
					{"nick": _nick, "orden": i + 1, "bloque_hash": bloque_hash, "origen": "onboarding_dao"})
		await _esperar(0.9)
		_lucia_dice("%s sellada en Bloque #%d." % [str(e["nombre"]), e["bloque"]], 2.2)
		await _esperar_voz()

	_encuadrar(Vector3(0.0, 112.0, 58.0), Vector3(0.0, 41.0, 0.0), 58.0)
	_marcar(&"plaza_completa")
	_paso("3 · Registro protegido")
	_lucia_dice("Alta sellada en las cuatro estaciones. Tu cuenta ya está protegida en la DAO.", 4.0)
	await _esperar_voz()
	await _esperar(0.6)


func _inicializar_bloques_dao() -> void:
	_bloques_dao.clear()
	var ruta_cuenta := "user://cuenta.json"
	if FileAccess.file_exists(ruta_cuenta):
		var crudo := FileAccess.get_file_as_string(ruta_cuenta)
		var datos = JSON.parse_string(crudo)
		if typeof(datos) == TYPE_DICTIONARY:
			_ultimo_hash_bloque = str(datos.get("cuenta_hash", ""))
	if _ultimo_hash_bloque.is_empty():
		var semilla := "%s:%d:genesis_dao" % [_nick, Time.get_unix_time_from_system()]
		_ultimo_hash_bloque = semilla.sha256_text()


func _registrar_en_servidor_modular() -> bool:
	if not ServicioConexionModular.habilitado():
		return true
	if _modular_token.is_empty():
		_lucia_dice("La conexión DAO no quedó preparada. Vuelve a validar tu nick para continuar.", 5.0)
		return false
	var respuesta: Dictionary = await ServicioConexionModular.registrar(
		_modular_token, _nick, _avatar_id, _sonda)
	if not bool(respuesta.get("ok", false)):
		var cuerpo: Dictionary = respuesta.get("body", {})
		_lucia_dice("No se pudo sellar tu registro en el servidor DAO: %s" % str(cuerpo.get("error", "sin respuesta")), 7.0)
		return false
	var miembro: Dictionary = respuesta.get("body", {}).get("miembro", {})
	var miembro_id := str(miembro.get("id", ""))
	ServicioConexionModular.activar_presencia(miembro_id)
	await ServicioConexionModular.refrescar_miembros(_sonda)
	print("[OnboardingDAO] Registro modular confirmado para ", _nick)
	return true


## Representa en la sede a los miembros presentes que vienen del servidor modular.
## Las escenas de avatar son las mismas del carrusel y del mundo; aquí quedan
## inmóviles para no interferir con el recorrido ni con los avatares locales.
func _actualizar_miembros_dao(miembros: Array) -> void:
	if _dao == null or not is_instance_valid(_dao):
		return
	if _contenedor_miembros_dao == null or not is_instance_valid(_contenedor_miembros_dao):
		_contenedor_miembros_dao = Node3D.new()
		_contenedor_miembros_dao.name = "MiembrosModularesDAO"
		_dao.add_child(_contenedor_miembros_dao)
	var presentes: Dictionary = {}
	var visibles: Array[Dictionary] = []
	for item in miembros:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var miembro: Dictionary = item
		if bool(miembro.get("isHost", miembro.get("IsHost", false))):
			continue # LucIA ya está representada por su personaje de la escena.
		var id := str(miembro.get("id", miembro.get("Id", "")))
		if id.is_empty():
			continue
		presentes[id] = true
		visibles.append(miembro)
		if not _avatares_miembros_dao.has(id):
			var avatar_id := str(miembro.get("avatar", miembro.get("Avatar", "")))
			var avatar := Catalogo.crear(avatar_id)
			if avatar == null:
				push_warning("[DAO] No se pudo cargar el avatar %s del miembro %s" % [avatar_id, str(miembro.get("nick", miembro.get("Nick", "")))])
				continue
			avatar.name = "Miembro_" + id
			avatar.set("es_selector", true)
			avatar.set_physics_process(false)
			avatar.set_process_input(false)
			avatar.set_process_unhandled_input(false)
			_bloquear_colisiones_avatar(avatar)
			var placa := Label3D.new()
			placa.name = "NombreDAO"
			placa.text = str(miembro.get("nick", miembro.get("Nick", "Miembro")))
			placa.position.y = 2.05
			placa.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			placa.font_size = 32
			placa.outline_size = 8
			avatar.add_child(placa)
			_contenedor_miembros_dao.add_child(avatar)
			_avatares_miembros_dao[id] = avatar
	for i in visibles.size():
		var miembro: Dictionary = visibles[i]
		var id := str(miembro.get("id", miembro.get("Id", "")))
		if not _avatares_miembros_dao.has(id):
			continue
		var avatar: Node3D = _avatares_miembros_dao[id]
		var angulo := TAU * float(i) / maxf(float(visibles.size()), 1.0)
		avatar.position = Vector3(cos(angulo) * 7.0, SUELO_ATRIO, sin(angulo) * 7.0)
		avatar.look_at(Vector3(0.0, SUELO_ATRIO, 0.0), Vector3.UP)
	for id in _avatares_miembros_dao.keys():
		if not presentes.has(str(id)):
			var avatar: Node = _avatares_miembros_dao[id]
			if is_instance_valid(avatar):
				avatar.queue_free()
			_avatares_miembros_dao.erase(id)


func _bloquear_colisiones_avatar(nodo: Node) -> void:
	if nodo is CollisionShape3D:
		(nodo as CollisionShape3D).disabled = true
	elif nodo is CollisionPolygon3D:
		(nodo as CollisionPolygon3D).disabled = true
	elif nodo is CollisionObject3D:
		(nodo as CollisionObject3D).collision_layer = 0
		(nodo as CollisionObject3D).collision_mask = 0
	for hijo in nodo.get_children():
		_bloquear_colisiones_avatar(hijo)


func _mostrar_dialogo_estacion_proteccion(estacion: Dictionary) -> void:
	if _hud == null:
		return
	# La explicación de la estación termina antes de abrir el panel: la
	# garantía no debe pisar la frase que aún está sonando.
	await _esperar_voz()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

	_panel_estacion = PanelContainer.new()
	_panel_estacion.set_anchors_preset(Control.PRESET_CENTER)
	_panel_estacion.offset_left = -320.0
	_panel_estacion.offset_right = 320.0
	_panel_estacion.offset_top = -140.0
	_panel_estacion.offset_bottom = 140.0

	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.02, 0.05, 0.10, 0.95)
	estilo.border_color = Color(0.12, 0.72, 1.0, 0.95)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(12)
	estilo.content_margin_left = 24.0
	estilo.content_margin_right = 24.0
	estilo.content_margin_top = 18.0
	estilo.content_margin_bottom = 18.0
	_panel_estacion.add_theme_stylebox_override("panel", estilo)
	_hud.add_child(_panel_estacion)

	var caja := VBoxContainer.new()
	caja.add_theme_constant_override("separation", 10)
	_panel_estacion.add_child(caja)

	var titulo := Label.new()
	titulo.text = "🏛️ ESTACIÓN DE PROTECCIÓN DAO · BLOQUE #%d" % int(estacion["bloque"])
	titulo.add_theme_font_size_override("font_size", 17)
	titulo.add_theme_color_override("font_color", Color(0.95, 0.84, 0.5))
	caja.add_child(titulo)

	_lbl_estacion_info = Label.new()
	_lbl_estacion_info.text = str(estacion["detalle"])
	_lbl_estacion_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_lbl_estacion_info.add_theme_font_size_override("font_size", 14)
	_lbl_estacion_info.add_theme_color_override("font_color", Color(0.85, 0.95, 1.0))
	caja.add_child(_lbl_estacion_info)

	# LucIA explica en segundo plano qué garantiza este bloque para tu seguridad.
	var garantia := str(estacion.get("garantia", ""))
	if not garantia.is_empty():
		var lbl_garantia := Label.new()
		lbl_garantia.text = "🛡️ " + garantia
		lbl_garantia.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		lbl_garantia.add_theme_font_size_override("font_size", 13)
		lbl_garantia.add_theme_color_override("font_color", Color(0.72, 0.9, 0.78))
		caja.add_child(lbl_garantia)
		_voz("Garantía de seguridad: " + garantia)

	_lbl_estacion_hash = Label.new()
	_lbl_estacion_hash.text = "Hash previo: %s…" % _ultimo_hash_bloque.substr(0, 24)
	_lbl_estacion_hash.add_theme_font_size_override("font_size", 11)
	_lbl_estacion_hash.add_theme_color_override("font_color", Color(0.55, 0.75, 0.95))
	caja.add_child(_lbl_estacion_hash)

	_btn_aceptar_proteger = Button.new()
	_btn_aceptar_proteger.text = "🛡️ Aceptar y proteger mi cuenta"
	_btn_aceptar_proteger.custom_minimum_size = Vector2(0, 46)
	_btn_aceptar_proteger.add_theme_font_size_override("font_size", 16)
	caja.add_child(_btn_aceptar_proteger)

	_confirmado_estacion = false
	_btn_aceptar_proteger.pressed.connect(func():
		_confirmado_estacion = true
	)

	if autoprueba:
		await _esperar(1.2)
		_confirmado_estacion = true

	# Esperar a que el usuario pulse el botón
	while not _confirmado_estacion:
		await get_tree().process_frame

	_btn_aceptar_proteger.disabled = true
	# El bloque no se sella ni avanza el siguiente paso hasta que LucIA termina
	# de explicar la garantía: el botón confirma la cuenta, no corta la voz.
	_btn_aceptar_proteger.text = "⏳ Sellando el bloque…"
	await _esperar_voz(30.0)
	_btn_aceptar_proteger.text = "✅ Bloque minado y sellado"
	await _esperar(0.6)

	if _panel_estacion != null and is_instance_valid(_panel_estacion):
		_panel_estacion.queue_free()
		_panel_estacion = null


func _minar_bloque_estacion(estacion: Dictionary) -> String:
	var payload := "%s:%s:%s:%d:%s" % [
		_ultimo_hash_bloque,
		str(estacion["clave"]),
		_nick,
		Time.get_unix_time_from_system(),
		Identidad.asegurar_identidad()
	]
	var nuevo_hash := payload.sha256_text()
	_ultimo_hash_bloque = nuevo_hash
	var bloque_dict := {
		"bloque": int(estacion["bloque"]),
		"estacion": str(estacion["clave"]),
		"nombre": str(estacion["nombre"]),
		"hash": nuevo_hash,
		"timestamp": Time.get_datetime_string_from_system(true, true),
		"nick": _nick
	}
	_bloques_dao.append(bloque_dict)

	# Actualizar o guardar en user://cuenta.json
	_actualizar_cuenta_con_bloques()
	return nuevo_hash


func _actualizar_cuenta_con_bloques() -> void:
	var ruta_cuenta := "user://cuenta.json"
	var datos: Dictionary = {}
	if FileAccess.file_exists(ruta_cuenta):
		var crudo := FileAccess.get_file_as_string(ruta_cuenta)
		var parseado = JSON.parse_string(crudo)
		if typeof(parseado) == TYPE_DICTIONARY:
			datos = parseado
	datos["nick"] = _nick if not _nick.is_empty() else datos.get("nick", "CiudadanoDAO")
	datos["cuenta_hash"] = _ultimo_hash_bloque
	datos["bloques_dao"] = _bloques_dao
	datos["fecha_actualizacion"] = Time.get_datetime_string_from_system(true, true)

	var f := FileAccess.open(ruta_cuenta, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(datos, "\t"))
		f.close()


func _carrusel_avatares() -> void:
	if _jugador == null or _cruzando:
		return
	var llegada := _punto(14.9, 14.9, SUELO_ATRIO)
	await _desplazar(llegada, Vector3(-1.0, 0.0, -1.0))
	await _caminar([_jugador.global_position, _punto(13.5, 13.5, SUELO_ATRIO)], 1.8)
	_encuadrar(Vector3(18.6, 44.6, 18.6), Vector3(11.5, 43.0, 11.5), 44.0)
	if _carrusel == null:
		return
	_marcar(&"carrusel")
	_paso("2 · Elige tu avatar")
	var estado := [true, ""]
	var al_cerrar := func(ruta: String):
		estado[0] = false
		estado[1] = ruta
	_carrusel.connect("carrusel_cerrado", al_cerrar)
	if _hud != null:
		_hud.visible = false
	var abierto := false
	if _carrusel.has_method("abrir_en_dao"):
		abierto = bool(_carrusel.call("abrir_en_dao", _jugador))
	else:
		abierto = bool(_carrusel.call("abrir_para", _jugador))
	if not abierto:
		_carrusel.disconnect("carrusel_cerrado", al_cerrar)
		if _hud != null:
			_hud.visible = true
		if _jugador != null:
			_jugador.visible = true
		return
	if autoprueba:
		await _esperar(2.4)
		_carrusel.call("confirmar_actual")
	var limite := Time.get_ticks_msec() + 300000
	while bool(estado[0]) and Time.get_ticks_msec() < limite:
		await get_tree().process_frame
	_carrusel.disconnect("carrusel_cerrado", al_cerrar)
	if _hud != null:
		_hud.visible = true
	var ruta := str(estado[1])
	if ruta.is_empty():
		ruta = Avatares.ruta_actual()
	if not ruta.is_empty():
		var id := Catalogo.id_de_ruta(ruta)
		if not id.is_empty():
			_avatar_id = id
			_cambiar_avatar(id)
	# El avatar entra en escena al confirmarse la elección, no antes.
	if _jugador != null:
		_jugador.visible = true
	# El aro queda parado desde la elección: el recorrido del avatar no lo gira.
	if _carrusel != null and _carrusel.has_method("set_girando"):
		_carrusel.call("set_girando", false)


func _bienvenida_metaverso() -> void:
	if _cruzando:
		return
	_marcar(&"bienvenida")
	_paso("4 · Bienvenido al metaverso")
	# El aro queda parado: la cinemática del recorrido sale limpia.
	if _carrusel != null and _carrusel.has_method("set_girando"):
		_carrusel.call("set_girando", false)
	_tomar_camara(Vector3(6.4, 44.7, 10.8), Vector3(-0.4, 42.9, 0.8), 1.8, 44.0)
	await _esperar(0.6)
	var saludo := "Bienvenido al metaverso"
	if not _nick.is_empty():
		saludo = "%s, bienvenido al metaverso" % _nick
	_lucia_dice(saludo + ". Tu alta como ciudadano ya está sellada.", 5.0)
	await _esperar(2.4)
	# El aviso del aspecto ya se dijo al arrancar el recorrido: este plano solo
	# presenta al avatar antes de encarar el espejo.
	_tomar_camara(Vector3(21.0, 44.6, 21.4), Vector3(4.0, 42.7, 4.0), 2.2, 46.0)
	await _esperar(2.6)
	await _esperar_voz()


func _cambiar_avatar(id: String) -> void:
	var nuevo: Node3D = Catalogo.crear(id)
	if nuevo == null or _jugador == null:
		return
	var viejo := _jugador
	nuevo.name = "Jugador"
	nuevo.set("es_selector", true)
	nuevo.position = viejo.position
	nuevo.rotation = viejo.rotation
	add_child(nuevo)
	_jugador = nuevo
	viejo.queue_free()
	_columna(nuevo.global_position)


func _caminar_al_espejo() -> void:
	if _jugador == null or _cruzando:
		return
	_paso("5 · El espejo del avatar")
	_marcar(&"personalizacion")
	_lucia_dice("Tu avatar ya tiene forma. El espejo de la DAO te espera para personalizarlo.", 4.5)
	# El aro queda parado mientras el avatar cruza el atrio.
	if _carrusel != null and _carrusel.has_method("set_girando"):
		_carrusel.call("set_girando", false)
	var puesto := Vector3(0.0, 41.88, 10.7)
	if _zona != null and _zona.has_method("punto_puesto"):
		puesto = _zona.call("punto_puesto")
	_seguir = true
	await _caminar([
		_jugador.global_position,
		_punto(0.0, 24.0, SUELO_ATRIO),
		_punto(0.0, 20.0, SUELO_ATRIO),
		puesto,
	], 2.0, true, 0.75)
	# El editor vive dentro de la DAO: el avatar se gira al frente para que la
	# cámara del atrio lo vea de cara, con el espejo a su espalda.
	var giro := create_tween()
	giro.tween_property(_jugador, "rotation:y", 0.0, 0.9) \
			.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await giro.finished
	# Encuadre de frente y por dentro del aro (r<14): a r=14 hay estatuas del
	# carrusel que taparían la vista del avatar.
	_tomar_camara(Vector3(2.2, 43.35, 13.3), Vector3(0.0, 43.05, 10.66), 1.6, 38.0)
	await _esperar(1.8)


func _abrir_editor() -> void:
	if _avatar_id.is_empty() or _cruzando:
		return
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_marcar(&"editor")
	if _hud != null:
		_hud.visible = false
	_editor = EDITOR_SCENE.instantiate() as Node3D
	if _editor == null:
		if _hud != null:
			_hud.visible = true
		return
	# El editor edita al jugador real frente al espejo: no monta sala, cámara ni
	# luz propias; la cinemática ya lo encuadró de cara dentro de la DAO.
	_editor.call("set_modo_dao", true)
	_editor.call("set_avatar_dao", _jugador)
	_editor.call("set_avatar", _avatar_id)
	if not _nick.is_empty():
		_editor.call("set_nick", _nick)
	add_child(_editor)
	_editor.connect("aspecto_confirmado", _al_confirmar_aspecto)
	if autoprueba:
		await _esperar(2.8)
		# En prueba se confirma sin guardar el aspecto: no se toca el perfil real.
		if _editor != null and is_instance_valid(_editor):
			_editor.emit_signal("aspecto_confirmado")


func _al_confirmar_aspecto() -> void:
	if _editor != null and is_instance_valid(_editor):
		_editor.queue_free()
		_editor = null
	if _hud != null:
		_hud.visible = true
	_entregar_control()


func _entregar_control() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	if _camara != null:
		_camara.current = true
	if _jugador == null:
		return
	_paso("6 · El portal")
	_marcar(&"control")
	var borde := _punto(2.6, 13.2, SUELO_ATRIO)
	_jugador.global_position = borde + Vector3(0.0, 0.03, 0.0)
	_orientar(Vector3(0.0, borde.y, 18.2))
	_jugador.call("activar_control")
	_jugador.call("snap_camera")
	if _portal is Area3D:
		(_portal as Area3D).show()
		(_portal as Area3D).monitoring = true
	if _carrusel != null and _carrusel.has_method("set_auto_abrir"):
		_carrusel.call("set_auto_abrir", false)
	# El aro sigue parado: el alta no lo suelta hasta cruzar el portal.
	_baliza_portal()
	_lucia_dice("Puedes recorrer la asamblea. Cruza el portal cuando quieras volver a tu isla." if _regreso else "Desde aquí caminas tú. Sigue la baliza hasta el portal: al cruzarlo nace tu isla.", 7.0)
	_pista("WASD / flechas para moverte · ratón con botón derecho para mirar · SHIFT para correr")
	_montar_boton_guardar_dao()
	_montar_chat_dao()
	if autoprueba:
		_auto_portal()


func _montar_chat_dao() -> void:
	if get_node_or_null("ChatLucIADAO") != null:
		return
	var escena := load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIA_Interfaz.tscn") as PackedScene
	var chat: Node3D = escena.instantiate()
	chat.name = "ChatLucIADAO"
	chat.call("set_modo_dao", _lucia)
	chat.connect("conversacion_abierta", func():
		_callar()
		_dialogo.hide()
		_hud.hide()
		_jugador.set_process_input(false)
		_jugador.set_physics_process(false))
	chat.connect("conversacion_cerrada", func():
		if not _cruzando:
			_hud.show()
			_jugador.set_process_input(true)
			_jugador.set_physics_process(true))
	add_child(chat)
	var btn := Button.new()
	btn.name = "BotonHablarLucIA"
	btn.text = "Hablar con LucIA · T"
	btn.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	btn.offset_left = 34.0
	btn.offset_right = 300.0
	btn.offset_top = -64.0
	btn.offset_bottom = -20.0
	btn.add_theme_font_size_override("font_size", 16)
	btn.pressed.connect(func(): chat.call("enfocar_chat"))
	_hud.add_child(btn)


func _montar_boton_guardar_dao() -> void:
	if _hud == null or _hud.get_node_or_null("BotonGuardarDAO") != null:
		return
	var btn := Button.new()
	btn.name = "BotonGuardarDAO"
	btn.text = "💾 Guardar copia de seguridad (.zip)"
	btn.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	btn.offset_left = -320.0
	btn.offset_right = -34.0
	btn.offset_top = -64.0
	btn.offset_bottom = -20.0
	btn.add_theme_font_size_override("font_size", 14)
	var estilo_btn := StyleBoxFlat.new()
	estilo_btn.bg_color = Color(0.04, 0.08, 0.16, 0.95)
	estilo_btn.border_color = Color(0.35, 0.8, 1.0, 0.9)
	estilo_btn.set_border_width_all(2)
	estilo_btn.set_corner_radius_all(8)
	btn.add_theme_stylebox_override("normal", estilo_btn)
	btn.pressed.connect(_abrir_guardar_dialogo_dao)
	_hud.add_child(btn)


func _abrir_guardar_dialogo_dao() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var dialogo := FileDialog.new()
	dialogo.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	dialogo.access = FileDialog.ACCESS_FILESYSTEM
	dialogo.add_filter("*.zip", "Cuenta WoldVirtual (.zip)")
	dialogo.current_file = "cuenta_%s.zip" % (_nick if not _nick.is_empty() else "woldvirtual")
	dialogo.file_selected.connect(_guardar_cuenta_zip_en_ruta)
	add_child(dialogo)
	dialogo.popup_centered_ratio(0.7)


func _guardar_cuenta_zip_en_ruta(ruta: String) -> void:
	var ruta_c := "user://cuenta.json"
	var datos: Dictionary = {}
	if FileAccess.file_exists(ruta_c):
		var cr := FileAccess.get_file_as_string(ruta_c)
		var d = JSON.parse_string(cr)
		if typeof(d) == TYPE_DICTIONARY:
			datos = d
	if datos.is_empty():
		datos = {
			"nick": _nick,
			"cuenta_hash": _ultimo_hash_bloque,
			"bloques_dao": _bloques_dao,
			"fecha_alta": Time.get_datetime_string_from_system(true, true)
		}

	var texto := JSON.stringify(datos, "\t")
	var metadata := ("Cuenta WoldVirtualP2P3D - DAO Isla Única\nNick: %s\nHash: %s\n" +
		"Bloques minados: %d\n\nEste archivo contiene las firmas criptográficas de tu cuenta.\n") % [
			str(datos.get("nick", "")), str(datos.get("cuenta_hash", "")), datos.get("bloques_dao", []).size()]

	if ClassDB.class_exists("ZIPPacker"):
		var packer := ZIPPacker.new()
		if packer.open(ruta) == OK:
			packer.start_file("cuenta.json")
			packer.write_file(texto.to_utf8_buffer())
			packer.close_file()
			packer.start_file("metadata.txt")
			packer.write_file(metadata.to_utf8_buffer())
			packer.close_file()
			packer.close()
			_decir("LucIA", "Copia de seguridad (.zip) guardada con éxito en tu equipo.", 4.0)
	else:
		var f := FileAccess.open(ruta, FileAccess.WRITE)
		if f != null:
			f.store_string(texto)
			f.close()
			_decir("LucIA", "Copia de cuenta guardada con éxito en tu equipo.", 4.0)


func _baliza_portal() -> void:
	if _portal == null or not (_portal is Node3D):
		return
	var raiz := Node3D.new()
	raiz.name = "BalizaOnboarding"
	raiz.position = Vector3(0.0, 5.4, 0.0)
	_portal.add_child(raiz)
	var mi := MeshInstance3D.new()
	mi.name = "Flecha"
	var cono := CylinderMesh.new()
	cono.top_radius = 0.0
	cono.bottom_radius = 0.55
	cono.height = 0.9
	cono.radial_segments = 24
	mi.mesh = cono
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.95, 0.82, 0.45)
	mat.emission_enabled = true
	mat.emission = Color(0.95, 0.82, 0.45)
	mat.emission_energy_multiplier = 2.4
	mi.material_override = mat
	mi.rotation.x = PI
	raiz.add_child(mi)
	var rotulo := Label3D.new()
	rotulo.name = "RotuloBaliza"
	rotulo.text = "SIGUE LA BALIZA"
	rotulo.font_size = 40
	rotulo.pixel_size = 0.005
	rotulo.modulate = Color(0.95, 0.82, 0.45)
	rotulo.outline_modulate = Color(0.02, 0.03, 0.05, 1.0)
	rotulo.outline_size = 8
	rotulo.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	rotulo.position = Vector3(0.0, 1.1, 0.0)
	raiz.add_child(rotulo)
	var tw := create_tween().set_loops()
	tw.tween_property(raiz, "position:y", 5.9, 0.9).set_trans(Tween.TRANS_SINE)
	tw.tween_property(raiz, "position:y", 5.4, 0.9).set_trans(Tween.TRANS_SINE)


func _auto_portal() -> void:
	await _esperar(0.6)
	Input.action_press("ui_up")
	var limite := Time.get_ticks_msec() + 12000
	while Time.get_ticks_msec() < limite and not _cruzando:
		await get_tree().process_frame
	Input.action_release("ui_up")


func _al_cruzar_portal() -> void:
	if _cruzando:
		return
	_cruzando = true
	if autoprueba:
		Input.action_release("ui_up")
	if _jugador != null:
		_jugador.call("desactivar_control")
		_jugador.call("reproducir_animacion", Catalogo.ANIM_IDLE, true)
	# El alta termina al cruzar el portal: solo aquí el aro recupera el giro.
	if _carrusel != null and _carrusel.has_method("fin_alta"):
		_carrusel.call("fin_alta")
	_marcar(&"portal")
	_paso("6 · Tu isla")
	_encuadrar(Vector3(8.6, 44.7, 13.8), Vector3(0.0, 42.6, 18.2), 40.0)
	# La indicación de caminar hacia la baliza termina antes de la frase del
	# portal: al cruzar nunca se corta lo que LucIA está diciendo.
	await _esperar_voz(15.0)
	_lucia_dice("Portal del archipiélago. Registro tu isla y la despliego en tu punto del reparto.", 5.0)
	await _esperar_voz()
	await _esperar(0.4)
	if _jugador != null:
		_columna(_jugador.global_position, 5.5)
	_tomar_camara(Vector3(7.6, 44.2, 15.6), Vector3(0.0, 43.0, 18.2), 1.6, 42.0)
	_mostrar_creando()
	await _esperar(2.6)
	_marcar(&"completado")
	var ruta := Avatares.ruta_actual()
	if ruta.is_empty() and not _avatar_id.is_empty():
		ruta = Catalogo.escena_de(_avatar_id)
	if onboarding_completado.get_connections().is_empty():
		var marca := FileAccess.open("user://onboarding_dao_completado.flag", FileAccess.WRITE)
		if marca != null:
			marca.store_string("1")
			marca.close()
		get_tree().change_scene_to_file(RUTA_MUNDO)
	else:
		onboarding_completado.emit(ruta)


func _mostrar_creando() -> void:
	if _hud == null:
		return
	var capa := Control.new()
	capa.name = "CreandoIsla"
	capa.set_anchors_preset(Control.PRESET_FULL_RECT)
	capa.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(capa)
	var caja := VBoxContainer.new()
	caja.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.set_anchors_preset(Control.PRESET_CENTER)
	caja.offset_left = -480.0
	caja.offset_right = 480.0
	caja.offset_top = -60.0
	caja.offset_bottom = 60.0
	caja.alignment = BoxContainer.ALIGNMENT_CENTER
	capa.add_child(caja)
	var titulo := Label.new()
	titulo.text = "CREANDO TU ISLA"
	titulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	titulo.add_theme_font_size_override("font_size", 44)
	titulo.add_theme_color_override("font_color", Color(0.95, 0.84, 0.5))
	titulo.add_theme_color_override("font_outline_color", Color(0.02, 0.04, 0.07))
	titulo.add_theme_constant_override("outline_size", 10)
	titulo.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(titulo)
	var sub := Label.new()
	sub.text = "Las islas nacen cuando registras la tuya"
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.add_theme_font_size_override("font_size", 20)
	sub.add_theme_color_override("font_color", Color(0.62, 0.9, 1.0))
	sub.add_theme_color_override("font_outline_color", Color(0.02, 0.04, 0.07))
	sub.add_theme_constant_override("outline_size", 6)
	sub.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(sub)
	capa.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(capa, "modulate:a", 1.0, 0.7)


# ---------------------------------------------------------------------------
# API para pruebas y para Boot
# ---------------------------------------------------------------------------

func jugador() -> Node3D:
	return _jugador


func dao() -> Node3D:
	return _dao


func plaza() -> Node:
	return _plaza


func carrusel() -> Node:
	return _carrusel


func portal() -> Node:
	return _portal


func fase_actual() -> StringName:
	return _fase
