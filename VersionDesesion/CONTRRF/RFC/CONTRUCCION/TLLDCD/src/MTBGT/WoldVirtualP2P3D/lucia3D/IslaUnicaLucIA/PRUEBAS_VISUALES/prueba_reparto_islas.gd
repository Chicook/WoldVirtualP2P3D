extends Control
## Prueba visual del reparto cardinal de islas alrededor de la DAO.
##
## Ejecutar:
##   godot --path <proyecto> res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/PruebaRepartoIslas.tscn --resolution 1000x1000
## Dibuja el plano con las posiciones que devuelve TeleportManager._grid_pos y
## guarda capturas/reparto_islas.png.

const RUTA_TM := "res://gdscrip/TeleportManager.gd"
const SALIDA := "res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/capturas"
const CHUNK := 199.5
const ESCALA := 0.62
const TOTAL := 12

var _posiciones: Array[Vector3] = []
var _fallos: Array[String] = []


func _ready() -> void:
	get_window().size = Vector2i(1000, 1000)
	set_anchors_preset(Control.PRESET_FULL_RECT)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SALIDA))

	var guion := load(RUTA_TM)
	_check(guion != null, "guion TeleportManager cargado")
	if guion == null:
		get_tree().quit(1)
		return
	var tm := Node3D.new()
	tm.set_script(guion)
	for i in TOTAL:
		_posiciones.append(tm.call("_grid_pos", i, CHUNK))
	tm.free()

	_comprobar()
	await get_tree().process_frame
	await get_tree().process_frame
	queue_redraw()
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var imagen := get_viewport().get_texture().get_image()
	var error := imagen.save_png(SALIDA + "/reparto_islas.png")
	_check(error == OK, "diagrama reparto_islas.png", "error=%d" % error)
	print("[PRUEBA] fallos: %d" % _fallos.size())
	get_tree().quit(0 if _fallos.is_empty() else 1)


func _comprobar() -> void:
	var esperado := [
		Vector3(0, 0, -CHUNK), Vector3(CHUNK, 0, 0), Vector3(-CHUNK, 0, 0), Vector3(0, 0, CHUNK),
		Vector3(0, 0, -CHUNK * 2.0), Vector3(CHUNK * 2.0, 0, 0),
		Vector3(-CHUNK * 2.0, 0, 0), Vector3(0, 0, CHUNK * 2.0),
		Vector3(0, 0, -CHUNK * 3.0), Vector3(CHUNK * 3.0, 0, 0),
		Vector3(-CHUNK * 3.0, 0, 0), Vector3(0, 0, CHUNK * 3.0),
	]
	for i in esperado.size():
		_check(_posiciones[i].is_equal_approx(esperado[i]),
				"isla %d en %s" % [i, esperado[i]], str(_posiciones[i]))
	var vistos := {}
	for i in _posiciones.size():
		var clave := str(_posiciones[i])
		_check(not vistos.has(clave), "isla %d en celda propia" % i, clave)
		vistos[clave] = true
	_check(not vistos.has(str(Vector3.ZERO)), "la DAO conserva el origen (0,0,0)")


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.04, 0.08, 0.12))
	var centro := size * 0.5
	var tope := CHUNK * 3.0 * ESCALA + 90.0

	# Anillos y ejes cardinales.
	var mar := Color(0.25, 0.55, 0.65, 0.55)
	for anillo in 3:
		draw_arc(centro, (anillo + 1) * CHUNK * ESCALA, 0.0, TAU, 160, mar, 2.0, true)
	draw_line(centro + Vector2(-tope, 0), centro + Vector2(tope, 0), mar, 2.0, true)
	draw_line(centro + Vector2(0, -tope), centro + Vector2(0, tope), mar, 2.0, true)
	_texto(centro + Vector2(0, -tope - 12), "NORTE (frente)", Color(0.7, 0.9, 1.0), 22, true)
	_texto(centro + Vector2(0, tope + 8), "SUR (detrás)", Color(0.7, 0.9, 1.0), 22, true)
	_texto(centro + Vector2(tope + 10, -26), "ESTE", Color(0.7, 0.9, 1.0), 22, false)
	_texto(centro + Vector2(-tope - 10, -26), "OESTE", Color(0.7, 0.9, 1.0), 22, false)

	# La DAO, fija en el origen.
	draw_circle(centro, 30.0, Color(0.96, 0.75, 0.2))
	draw_arc(centro, 30.0, 0.0, TAU, 64, Color(1, 0.95, 0.7), 2.0, true)
	var titulo_dao := "DAO · Isla Única LucIA"
	var ancho_dao := ThemeDB.fallback_font.get_string_size(
			titulo_dao, HORIZONTAL_ALIGNMENT_LEFT, -1, 22).x
	_texto(centro + Vector2(-ancho_dao * 0.5, -62), titulo_dao, Color(1.0, 0.9, 0.55), 22, false)

	var nombres := ["frente", "derecha", "izquierda", "detrás"]
	var colores := [Color(0.45, 0.8, 0.95), Color(0.4, 0.85, 0.55),
			Color(0.85, 0.55, 0.95), Color(0.95, 0.7, 0.4)]
	for i in _posiciones.size():
		var v := _posiciones[i]
		var p := centro + Vector2(v.x, v.z) * ESCALA
		var color: Color = colores[i % 4]
		draw_circle(p, 15.0, color)
		var etiqueta := "Isla %d" % i
		var ancho := ThemeDB.fallback_font.get_string_size(
				etiqueta, HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x
		match i % 4:
			1:
				_texto(p + Vector2(20, 6), etiqueta, Color(0.9, 0.95, 1.0), 18, false)
				_texto(p + Vector2(20, 25), nombres[i % 4], color, 15, false)
			2:
				_texto(p + Vector2(-20 - ancho, 6), etiqueta, Color(0.9, 0.95, 1.0), 18, false)
				_texto(p + Vector2(-20 - ancho, 25), nombres[i % 4], color, 15, false)
			_:
				_texto(p + Vector2(-ancho * 0.5, -34), etiqueta, Color(0.9, 0.95, 1.0), 18, false)
				_texto(p + Vector2(-ancho * 0.5, -15), nombres[i % 4], color, 15, false)


func _texto(punto: Vector2, texto: String, color: Color, tamano: int, centrado: bool) -> void:
	var ancho := -1.0
	if centrado:
		ancho = 0.0
	draw_string(ThemeDB.fallback_font, punto, texto, HORIZONTAL_ALIGNMENT_LEFT, ancho, tamano, color)


func _check(ok: bool, titulo: String, detalle: String = "") -> void:
	if ok:
		print("[PRUEBA] OK   %s %s" % [titulo, detalle])
	else:
		_fallos.append(titulo)
		print("[PRUEBA] FALLO %s %s" % [titulo, detalle])
