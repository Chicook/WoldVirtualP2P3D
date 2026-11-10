extends Node
## Tests de la matemática del manipulador de ejes (picking y proyección).

const GizmoManipulador = preload("res://gdscrip/GizmoManipulador.gd")


func _gizmo() -> Node3D:
	var g := GizmoManipulador.new()
	add_child(g)
	g.global_position = Vector3.ZERO
	g.scale = Vector3.ONE
	g.set_modo(GizmoManipulador.Modo.MOVER)
	return g


func test_direcciones_de_eje() -> void:
	var g := _gizmo()
	assert(g.direccion_eje(0).is_equal_approx(Vector3.RIGHT), "eje 0 = X")
	assert(g.direccion_eje(1).is_equal_approx(Vector3.UP), "eje 1 = Y")
	assert(g.direccion_eje(2).is_equal_approx(Vector3.BACK), "eje 2 = Z")
	g.free()


func test_picking_elige_el_eje_correcto() -> void:
	var g := _gizmo()
	# Un rayo que pasa bordeando el eje X debe elegir X.
	assert(g.eje_bajo_rayo(Vector3(0.5, 0.0, 5.0), Vector3(0, 0, -1), 0.3) == 0,
			"debe elegir el eje X")
	# Un rayo a la altura del centro del eje Y debe elegir Y.
	assert(g.eje_bajo_rayo(Vector3(5.0, 0.5, 0.0), Vector3(-1, 0, 0), 0.3) == 1,
			"debe elegir el eje Y")
	# Un rayo que no roza ningún mango no toca ningún eje.
	assert(g.eje_bajo_rayo(Vector3(0.0, 5.0, 5.0), Vector3(1, 0, 0), 0.2) == -1,
			"lejos no debe elegir eje")
	g.free()


func test_parametro_en_eje() -> void:
	var g := _gizmo()
	# El rayo corta el eje X en x = 0.5.
	var t: float = g.parametro_en_eje(0, Vector3(0.5, 0.0, 5.0), Vector3(0, 0, -1))
	assert(absf(t - 0.5) < 0.02, "el parámetro sobre X debe ser 0.5, fue %.3f" % t)
	g.free()


func test_angulo_en_plano() -> void:
	var g := _gizmo()
	# Puntos sobre el plano XZ (normal Y, eje 1): el ángulo debe avanzar.
	var a: float = g.angulo_en_plano(1, Vector3(1.0, 0.0, 0.0))
	var b: float = g.angulo_en_plano(1, Vector3(0.0, 0.0, 1.0))
	assert(absf(absf(b - a) - PI * 0.5) < 0.05, "90° entre +X y +Z en el plano Y")
	g.free()