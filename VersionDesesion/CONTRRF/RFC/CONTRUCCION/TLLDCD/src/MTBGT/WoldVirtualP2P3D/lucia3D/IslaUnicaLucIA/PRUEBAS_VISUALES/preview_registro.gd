extends Node3D
## Vista previa del sistema de registro de la DAO.
##
## Recorre las cuatro estaciones con la API real de `PlazaRegistroDAO`
## (`abrir`/`completar`), comprueba señales y progreso, y deja ver el avance con
## la señalización que la propia plaza monta sobre la isla (halo, baliza y aviso
## de "COMPLETADA") más un panel de progreso. El panel es capa de la prueba: la
## plaza no se modifica desde aquí.
##
## Uso:
##   godot --path <proyecto> res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/PreviewRegistroDAO.tscn
## Capturas en .../PRUEBAS_VISUALES/capturas/registro y código 1 si algo falla.

const ESCENA_DAO := "res://lucia3D/IslaUnicaLucIA/ESCENAS/IslaUnicaLucIA.tscn"
const RUTA_MUNDO := "res://WoldVirtual3DP2P.tscn"
const RUTA_BLOQUE := "res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"
const SALIDA := "res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/capturas/registro"

const NOMBRES := {
	&"identidad": "1 · Identidad",
	&"cuenta_unica": "2 · Cuenta única",
	&"huella_equipo": "3 · Huella del equipo",
	&"firma_sesion": "4 · Firma de sesión",
}
## Puntos cardinales del reparto: norte (-z), este, oeste, sur (+z).
const CARDINALES := {
	&"identidad": Vector2(0, -36),
	&"cuenta_unica": Vector2(36, 0),
	&"huella_equipo": Vector2(-36, 0),
	&"firma_sesion": Vector2(0, 36),
}
const CAMARAS := {
	&"identidad": [Vector3(0, 50, -50), Vector3(0, 40.4, -36)],
	&"cuenta_unica": [Vector3(50, 50, 8), Vector3(36, 41.0, 0)],
	&"huella_equipo": [Vector3(-50, 50, -8), Vector3(-36, 41.0, 0)],
	&"firma_sesion": [Vector3(0, 50, 50), Vector3(0, 40.4, 36)],
}

var _dao: Node3D = null
var _plaza: Node = null
var _fallos: Array[String] = []
var _abiertas: Array[StringName] = []
var _completadas: Array[StringName] = []

var _hud_progreso: Label = null
var _hud_estado: Label = null


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SALIDA))
	_entorno()
	_mar()
	_cargar_dao()
	_hud()
	await get_tree().process_frame
	await get_tree().process_frame
	_plaza = _dao.call("plaza_registro") if _dao != null else null
	_check(_plaza != null, "plaza de registro presente")
	if _plaza == null:
		_cerrar()
		return
	_plaza.estacion_abierta.connect(_al_abrir)
	_plaza.registro_completado.connect(_al_completar)
	_validar_estaciones()
	await _recorrido()
	_validar_cierre()
	_cerrar()


func _cerrar() -> void:
	print("[REGISTRO] fallos: %d" % _fallos.size())
	get_tree().quit(0 if _fallos.is_empty() else 1)


# ---------------------------------------------------------------------------
# Entorno, mar y DAO
# ---------------------------------------------------------------------------

func _entorno() -> void:
	var recurso := load(RUTA_MUNDO)
	if not (recurso is PackedScene):
		_fallos.append("No carga la escena del mundo " + RUTA_MUNDO)
		return
	var mundo := (recurso as PackedScene).instantiate()
	var ambiente := mundo.get_node_or_null("WorldEnvironment")
	var sol := mundo.get_node_or_null("DirectionalLight3D")
	if ambiente != null:
		ambiente.owner = null
		mundo.remove_child(ambiente)
		add_child(ambiente)
	if sol != null:
		sol.owner = null
		mundo.remove_child(sol)
		add_child(sol)
	mundo.free()
	_check(ambiente != null and sol != null, "entorno del metaverso (cielo y sol)")


func _mar() -> void:
	var plantilla := load(RUTA_BLOQUE)
	if not (plantilla is PackedScene):
		_fallos.append("No carga el bloque de isla " + RUTA_BLOQUE)
		return
	var bloque: Node = (plantilla as PackedScene).instantiate()
	var oceano: Node = bloque.get_node_or_null("Oceano3D")
	if oceano == null:
		_fallos.append("El bloque de isla no trae Oceano3D")
		bloque.free()
		return
	bloque.remove_child(oceano)
	oceano.owner = null
	var contenedor := Node3D.new()
	contenedor.name = "BloqueDAO"
	add_child(contenedor)
	contenedor.add_child(oceano)
	bloque.free()
	_check(true, "mar del metaverso alrededor de la DAO")


func _cargar_dao() -> void:
	var recurso := load(ESCENA_DAO)
	if not (recurso is PackedScene):
		_fallos.append("No carga la escena DAO " + ESCENA_DAO)
		return
	_dao = (recurso as PackedScene).instantiate() as Node3D
	if _dao == null:
		_fallos.append("No se pudo instanciar la DAO")
		return
	add_child(_dao)


# ---------------------------------------------------------------------------
# Validación del sistema real
# ---------------------------------------------------------------------------

func _validar_estaciones() -> void:
	var claves: Array = _plaza.call("estaciones")
	_check(claves.size() == 4, "cuatro estaciones de registro", str(claves))
	_check(int(_plaza.call("progreso")) == 0, "registro arranca en cero")
	for clave in claves:
		var marcador: Marker3D = _plaza.call("marcador", clave)
		_check(marcador != null, "marcador de %s" % clave)
		if marcador == null:
			continue
		var plano := Vector2(marcador.global_position.x, marcador.global_position.z)
		_check(plano.distance_to(CARDINALES[clave]) < 0.5,
				"estación %s en su punto cardinal" % clave, str(plano))
		_check(marcador.get_child_count() >= 5,
				"estación %s con piso, etiqueta y señalización" % clave,
				"hijos=%d" % marcador.get_child_count())
		var halo := marcador.get_node_or_null("HaloRegistro")
		var baliza := marcador.get_node_or_null("BalizaRegistro")
		var aviso := marcador.get_node_or_null("AvisoCompletada") as Label3D
		_check(halo != null and baliza != null and aviso != null,
				"señalización montada en %s" % clave)
		_check(aviso != null and not aviso.visible,
				"aviso de %s oculto al inicio" % clave)


func _al_abrir(clave: StringName) -> void:
	_abiertas.append(clave)


func _al_completar(clave: StringName, _datos: Dictionary) -> void:
	_completadas.append(clave)


# ---------------------------------------------------------------------------
# Recorrido y capturas
# ---------------------------------------------------------------------------

func _recorrido() -> void:
	await _vista("01_plaza_registro", Vector3(0, 75, 62), Vector3(0, 41, 0), 58.0)
	var claves: Array = _plaza.call("estaciones")
	for i in claves.size():
		var clave: StringName = claves[i]
		_hud_estado.text = "%s · EN CURSO" % NOMBRES[clave]
		_hud_progreso.text = "Progreso %d/4" % int(_plaza.call("progreso"))
		var abierta: bool = _plaza.call("abrir", clave)
		_check(abierta and _abiertas.size() == i + 1 and _abiertas[i] == clave,
				"abrir estación %s" % clave, "señales=%s" % str(_abiertas))
		var cam: Array = CAMARAS[clave]
		await _vista("%02d_%s_abierta" % [i + 2, clave], cam[0], cam[1], 40.0)

		var completada: bool = _plaza.call("completar", clave, {"prueba": true})
		_check(completada and bool(_plaza.call("esta_completa", clave)),
				"completar estación %s" % clave)
		var marcador: Marker3D = _plaza.call("marcador", clave)
		var aviso := marcador.get_node_or_null("AvisoCompletada") as Label3D
		_check(aviso != null and aviso.visible, "aviso COMPLETADA visible en %s" % clave)
		var progreso := int(_plaza.call("progreso"))
		_check(progreso == i + 1, "progreso %d/4 tras %s" % [i + 1, clave],
				"progreso=%d" % progreso)
		_hud_progreso.text = "Progreso %d/4" % progreso
		_hud_estado.text = "%s · COMPLETADA" % NOMBRES[clave]
		print("[REGISTRO] %s completada (%d/4)" % [NOMBRES[clave], progreso])
		await get_tree().process_frame
	await _vista("06_registro_completo", Vector3(0, 108, 52), Vector3(0, 41, 0), 58.0)
	await _vista("07_estacion_completada", Vector3(0, 50, 50), Vector3(-4.0, 42.8, 36), 46.0)


func _validar_cierre() -> void:
	_check(_abiertas.size() == 4 and _abiertas[0] == &"identidad"
			and _abiertas[3] == &"firma_sesion",
			"señal estacion_abierta en las cuatro", str(_abiertas))
	_check(_completadas.size() == 4 and _completadas[0] == &"identidad"
			and _completadas[3] == &"firma_sesion",
			"señal registro_completado en las cuatro", str(_completadas))
	_check(bool(_plaza.call("registro_completo")), "registro completo 4/4")
	_plaza.call("reiniciar")
	_check(int(_plaza.call("progreso")) == 0, "reiniciar deja el registro en cero")
	for clave in _plaza.call("estaciones"):
		var marcador: Marker3D = _plaza.call("marcador", clave)
		var aviso := marcador.get_node_or_null("AvisoCompletada") as Label3D
		_check(aviso != null and not aviso.visible,
				"reiniciar oculta el aviso de %s" % clave)
	_hud_progreso.text = "Progreso 4/4 · cerrado"
	_hud_estado.text = "Registro completo: las 4 estaciones"


func _vista(nombre: String, desde: Vector3, hacia: Vector3, fov: float) -> void:
	var cam := Camera3D.new()
	cam.name = "Cam_" + nombre
	cam.fov = fov
	cam.far = 3000.0
	add_child(cam)
	cam.global_position = desde
	cam.look_at(hacia, Vector3.UP)
	cam.current = true
	for i in 4:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var imagen := get_viewport().get_texture().get_image()
	var ruta := SALIDA + "/" + nombre + ".png"
	var error := imagen.save_png(ruta)
	_check(error == OK, "captura " + nombre, "error=%d" % error)
	cam.queue_free()


# ---------------------------------------------------------------------------
# HUD de la vista previa y utilidades
# ---------------------------------------------------------------------------

func _hud() -> void:
	var capa := CanvasLayer.new()
	capa.name = "HUDRegistro"
	capa.layer = 30
	add_child(capa)
	var panel := PanelContainer.new()
	panel.position = Vector2(36, 36)
	panel.custom_minimum_size = Vector2(430, 0)
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.015, 0.03, 0.055, 0.88)
	estilo.border_color = Color(0.72, 0.54, 0.18, 0.95)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(12)
	estilo.content_margin_left = 20.0
	estilo.content_margin_right = 20.0
	estilo.content_margin_top = 16.0
	estilo.content_margin_bottom = 16.0
	panel.add_theme_stylebox_override("panel", estilo)
	capa.add_child(panel)
	var caja := VBoxContainer.new()
	caja.add_theme_constant_override("separation", 6)
	panel.add_child(caja)
	var titulo := Label.new()
	titulo.text = "REGISTRO DAO"
	titulo.add_theme_font_size_override("font_size", 30)
	titulo.add_theme_color_override("font_color", Color(0.95, 0.82, 0.45))
	caja.add_child(titulo)
	var sub := Label.new()
	sub.text = "Isla Única LucIA · vista previa del alta"
	sub.add_theme_font_size_override("font_size", 16)
	sub.add_theme_color_override("font_color", Color(0.6, 0.9, 1.0))
	caja.add_child(sub)
	_hud_progreso = Label.new()
	_hud_progreso.text = "Progreso 0/4"
	_hud_progreso.add_theme_font_size_override("font_size", 24)
	caja.add_child(_hud_progreso)
	_hud_estado = Label.new()
	_hud_estado.text = "Listo para abrir la primera estación"
	_hud_estado.add_theme_font_size_override("font_size", 18)
	_hud_estado.add_theme_color_override("font_color", Color(0.75, 0.85, 1.0))
	caja.add_child(_hud_estado)


func _check(ok: bool, titulo: String, detalle: String = "") -> void:
	if ok:
		print("[REGISTRO] OK   %s %s" % [titulo, detalle])
	else:
		_fallos.append(titulo)
		print("[REGISTRO] FALLO %s %s" % [titulo, detalle])
