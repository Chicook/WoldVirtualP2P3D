extends Node3D
## Prueba visual real del alta de ciudadano en la DAO.
##
## Instancia `OnboardingDAO` con `autoprueba` y acompaña la secuencia real
## (despacho → plaza → carrusel → bienvenida → espejo → control → portal)
## capturando la cámara de la cinemática en cada fase. Al terminar valida el
## recorrido y deja las capturas en `.../capturas/onboarding`.
##
## El perfil del jugador se respalda y se restaura: el carrusel real guarda la
## elección, pero la prueba no debe pisar la selección del usuario.
##
## Uso:
##   godot --path <proyecto> res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/PreviewOnboardingDAO.tscn
## Código 1 si alguna comprobación falla.

const ALTA: PackedScene = preload("res://lucia3D/IslaUnicaLucIA/ONBOARDING/OnboardingDAO.tscn")
const SALIDA := "res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/capturas/onboarding"
const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

const NICK := "PruebaDAO"
const PERFIL := ["user://avatar_jugador.cfg", "user://registro.cfg"]
const LIMITE_MS := 300000

const FASES_ESPERADAS: Array[String] = [
	"despacho", "carrusel", "salida", "estacion_1", "estacion_2", "estacion_3", "estacion_4",
	"plaza_completa", "bienvenida", "personalizacion", "editor",
	"control", "portal", "completado",
]
## Segundos que se deja correr cada fase antes de disparar la captura.
const PAUSAS := {
	"despacho": 0.8, "salida": 2.6, "estacion_1": 1.1, "estacion_2": 1.1,
	"estacion_3": 1.1, "estacion_4": 1.1, "plaza_completa": 2.0,
	"carrusel": 2.0, "bienvenida": 3.0, "personalizacion": 3.2, "editor": 1.2,
	"control": 1.4, "portal": 1.0, "completado": 0.9,
}

var _alta: Node3D = null
var _fases: Array[String] = []
var _fallos: Array[String] = []
var _pantallazos: Array[String] = []
var _respaldo := {}
var _completado := false
var _ruta := ""
var _estado: Label = null
var _editor_visto := false
var _editor_en_dao := false
var _control_ok := false
var _seleccion_en_dao := false
var _camara_atrio := false
var _aro_parado := false
var _cruce_z := 0.0


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SALIDA))
	_respaldar()
	_hud()
	_alta = ALTA.instantiate() as Node3D
	if _alta == null:
		_fallos.append("no se instancia el alta")
		_cerrar()
		return
	_alta.set("autoprueba", true)
	_alta.call("set_nick", NICK)
	_alta.connect("fase_cambiada", _al_cambiar_fase)
	_alta.connect("onboarding_completado", _al_completar)
	add_child(_alta)
	print("[ONBOARDING] alta instanciada con autoprueba")

	var limite := Time.get_ticks_msec() + LIMITE_MS
	while not _completado and Time.get_ticks_msec() < limite:
		await get_tree().process_frame
	if not _completado:
		_fallos.append("el alta no terminó en %d s" % int(LIMITE_MS / 1000))
	await get_tree().create_timer(2.0).timeout
	_validar()
	_cerrar()


# ---------------------------------------------------------------------------
# Seguimiento de la secuencia
# ---------------------------------------------------------------------------

func _al_cambiar_fase(fase: StringName) -> void:
	var nombre := str(fase)
	if _fases.has(nombre):
		return
	_fases.append(nombre)
	if _estado != null:
		_estado.text = "FASE · %s" % nombre.to_upper()
	print("[ONBOARDING] fase ", nombre)
	if nombre == "portal" and _alta != null:
		var jugador: Node3D = _alta.call("jugador")
		if jugador != null:
			_cruce_z = jugador.global_position.z
	_capturar(nombre, _fases.size())


func _al_completar(ruta: String) -> void:
	_completado = true
	_ruta = ruta
	print("[ONBOARDING] alta completada con ", ruta)


func _comprobar_control() -> void:
	if _alta == null or not is_instance_valid(_alta):
		return
	var jugador: Node3D = _alta.call("jugador")
	if jugador == null:
		return
	var camara: Camera3D = jugador.get("camara") as Camera3D
	_control_ok = not bool(jugador.get("es_selector")) \
			and jugador.is_physics_processing() \
			and camara != null and camara.current
	if _estado != null:
		_estado.text = "FASE · CONTROL %s" % ("OK" if _control_ok else "FALLO")


func _comprobar_carrusel_dao() -> void:
	if _alta == null or not is_instance_valid(_alta):
		return
	var carrusel: Node = _alta.call("carrusel")
	_seleccion_en_dao = carrusel != null and carrusel.has_method("seleccion_en_dao") \
			and bool(carrusel.call("seleccion_en_dao"))
	var camara := get_viewport().get_camera_3d()
	_camara_atrio = camara != null and camara.name == "CamaraEleccionDAO"
	print("[ONBOARDING] carrusel en la DAO=%s cámara atrio=%s"
			% [_seleccion_en_dao, _camara_atrio])


func _comprobar_aro_parado() -> void:
	if _alta == null or not is_instance_valid(_alta):
		return
	var carrusel: Node = _alta.call("carrusel")
	_aro_parado = carrusel != null and carrusel.has_method("girando") \
			and not bool(carrusel.call("girando"))
	print("[ONBOARDING] aro parado durante el recorrido=%s" % _aro_parado)


func _comprobar_editor_dao() -> void:
	var editor := _alta.get_node_or_null("EditorAspecto")
	if editor == null:
		return
	# En la DAO el editor no monta sala: ni cámara, ni entorno, ni copia del
	# avatar. Edita el nodo real del jugador que ya está frente al espejo.
	_editor_en_dao = editor.get_node_or_null("Camara") == null \
			and editor.get_node_or_null("WorldEnvironment") == null \
			and editor.find_child("AvatarAspecto", true, false) == null
	print("[ONBOARDING] editor dentro de la DAO=%s" % _editor_en_dao)


func _capturar(nombre: String, orden: int) -> void:
	var pausa := float(PAUSAS.get(nombre, 0.8))
	await get_tree().create_timer(pausa).timeout
	if nombre == "editor" and _alta != null and is_instance_valid(_alta):
		_editor_visto = _alta.get_node_or_null("EditorAspecto") != null
		_comprobar_editor_dao()
	if nombre == "carrusel":
		_comprobar_carrusel_dao()
	if nombre == "personalizacion":
		_comprobar_aro_parado()
	if nombre == "control":
		_comprobar_control()
	await RenderingServer.frame_post_draw
	var imagen := get_viewport().get_texture().get_image()
	var archivo := "%02d_%s.png" % [orden, nombre]
	var ruta := ProjectSettings.globalize_path(SALIDA + "/" + archivo)
	var error := imagen.save_png(ruta)
	if error != OK:
		print("[ONBOARDING] captura fallida %s size=%s empty=%s error=%d"
				% [ruta, imagen.get_size(), imagen.is_empty(), error])
	if error == OK:
		_pantallazos.append(archivo)
		print("[ONBOARDING] captura ", archivo)
	else:
		_fallos.append("captura %s (error %d)" % [archivo, error])


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

func _validar() -> void:
	for fase in FASES_ESPERADAS:
		_check(_fases.has(fase), "fase %s emitida" % fase)
	var orden_ok := _fases.size() >= FASES_ESPERADAS.size()
	if orden_ok:
		for i in FASES_ESPERADAS.size():
			if _fases[i] != FASES_ESPERADAS[i]:
				orden_ok = false
				break
	_check(orden_ok, "orden completo del alta", str(_fases))

	var grupo := get_tree().get_nodes_in_group("isla_unica_lucia")
	_check(grupo.size() == 1, "una sola DAO viva durante el alta", "islas=%d" % grupo.size())
	_check(get_tree().root.find_child("ISLA3Dblock", true, false) == null,
			"ninguna isla de jugador durante el alta")
	_check(_alta.get_node_or_null("BloqueDAO") != null, "mar del metaverso en la DAO")
	_check(_pantallazos.size() == _fases.size() and _pantallazos.size() >= FASES_ESPERADAS.size(),
			"capturas de todas las fases", str(_pantallazos))

	var plaza: Node = _alta.call("plaza")
	if plaza != null:
		var progreso := int(plaza.call("progreso"))
		_check(progreso == 4 and bool(plaza.call("registro_completo")),
				"registro de las cuatro estaciones", "progreso=%d" % progreso)
	else:
		_check(false, "plaza de registro disponible")

	var carrusel: Node = _alta.call("carrusel")
	_check(carrusel != null and not bool(carrusel.call("abierto")),
			"carrusel abierto y cerrado por el alta")
	_check(_seleccion_en_dao, "la elección ocurre sobre el aro del atrio")
	_check(_camara_atrio, "cámara de elección dentro de la DAO")
	_check(_aro_parado, "el aro queda parado durante el recorrido")

	var jugador: Node3D = _alta.call("jugador")
	if jugador != null:
		var id := str(jugador.get_meta("avatar_id", ""))
		_check(Catalogo.id_valido(id), "avatar elegido instanciado en la DAO", id)
	else:
		_check(false, "jugador de la cinemática")
	_check(_editor_visto, "editor de aspecto montado en el espejo")
	_check(_editor_en_dao, "el editor personaliza al jugador dentro de la DAO")
	_check(_control_ok, "el mando pasa al jugador tras el espejo")
	_check(_cruce_z > 16.5, "el jugador cruza el portal caminando", "z=%.2f" % _cruce_z)
	_check(_completado and not _ruta.is_empty(), "alta completa con avatar", _ruta)
	_check(Catalogo.id_valido(Catalogo.id_de_ruta(_ruta)),
			"la ruta del avatar es del catálogo", _ruta)
	_check(FileAccess.file_exists(_ruta), "la escena del avatar existe", _ruta)


# ---------------------------------------------------------------------------
# Perfil, HUD y utilidades
# ---------------------------------------------------------------------------

func _respaldar() -> void:
	for ruta in PERFIL:
		if FileAccess.file_exists(ruta):
			_respaldo[ruta] = FileAccess.get_file_as_bytes(ruta)
		else:
			_respaldo[ruta] = null


func _restaurar() -> void:
	for ruta in _respaldo.keys():
		var datos = _respaldo[ruta]
		if datos == null:
			if FileAccess.file_exists(ruta):
				DirAccess.remove_absolute(ProjectSettings.globalize_path(ruta))
			continue
		var archivo := FileAccess.open(ruta, FileAccess.WRITE)
		if archivo != null:
			archivo.store_buffer(datos)
			archivo.close()
	print("[ONBOARDING] perfil del jugador restaurado")


func _hud() -> void:
	var capa := CanvasLayer.new()
	capa.name = "HUDPRUEBA"
	capa.layer = 60
	add_child(capa)
	var panel := PanelContainer.new()
	panel.position = Vector2(12, 12)
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.015, 0.03, 0.055, 0.88)
	estilo.border_color = Color(0.95, 0.82, 0.45, 0.95)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(10)
	estilo.content_margin_left = 14.0
	estilo.content_margin_right = 14.0
	estilo.content_margin_top = 8.0
	estilo.content_margin_bottom = 8.0
	panel.add_theme_stylebox_override("panel", estilo)
	capa.add_child(panel)
	var caja := VBoxContainer.new()
	caja.add_theme_constant_override("separation", 2)
	panel.add_child(caja)
	var titulo := Label.new()
	titulo.text = "PRUEBA · ALTA EN LA DAO"
	titulo.add_theme_font_size_override("font_size", 16)
	titulo.add_theme_color_override("font_color", Color(0.95, 0.82, 0.45))
	caja.add_child(titulo)
	_estado = Label.new()
	_estado.text = "INICIANDO"
	_estado.add_theme_font_size_override("font_size", 13)
	_estado.add_theme_color_override("font_color", Color(0.6, 0.9, 1.0))
	caja.add_child(_estado)


func _check(ok: bool, titulo: String, detalle: String = "") -> void:
	if ok:
		print("[ONBOARDING] OK   %s %s" % [titulo, detalle])
	else:
		_fallos.append(titulo)
		print("[ONBOARDING] FALLO %s %s" % [titulo, detalle])


func _cerrar() -> void:
	_restaurar()
	print("[ONBOARDING] capturas: %d · fallos: %d" % [_pantallazos.size(), _fallos.size()])
	get_tree().quit(0 if _fallos.is_empty() else 1)
