extends Node
## Test de integración del gizmo: simula el rayo del ratón con una subclase que
## lo fija, y comprueba que arrastrar el eje X mueve el prim seleccionado.

const ConstruccionScript = preload("res://gdscrip/Construccion.gd")
const Prims = preload("res://gdscrip/Prims.gd")


class FakeConstruccion extends ConstruccionScript:
	var rayo: Array = []
	func _rayo_camara() -> Array:
		return rayo


func _cuerpo() -> StaticBody3D:
	var cuerpo := StaticBody3D.new()
	cuerpo.set_meta("isla", 0)
	cuerpo.set_meta("prim_id", 1)
	var malla := MeshInstance3D.new()
	malla.name = "Malla"
	malla.mesh = Prims.crear_malla("cubo", {})
	malla.material_override = Prims.crear_material(Color.WHITE)
	cuerpo.add_child(malla)
	var col := CollisionShape3D.new()
	col.name = "Colision"
	col.shape = Prims.crear_forma("cubo", {})
	cuerpo.add_child(col)
	return cuerpo


func test_arrastre_mover_eje_x() -> void:
	var c := FakeConstruccion.new()
	add_child(c) # dispara _ready: crea panel, mira y gizmo
	var cuerpo := _cuerpo()
	add_child(cuerpo)
	var datos := {
		"id": 1, "tipo": "cubo", "pos": Vector3.ZERO, "rot": Vector3.ZERO,
		"escala": Vector3.ONE, "color": Color.WHITE, "params": {},
	}
	c._prims = {0: {1: datos}}
	c._nodos = {0: {1: cuerpo}}
	c._seleccionado = cuerpo
	c._sel_isla = 0
	c._sel_id = 1
	c._herramienta = ConstruccionScript.Herramienta.SELECCION
	c._modo = true
	c._gizmo_modo = 0 # MOVER
	c._gizmo.global_position = Vector3.ZERO
	c._gizmo.scale = Vector3.ONE

	# Rayo que corta el eje X en x=0.5 -> elige X y fija t0=0.5.
	c.rayo = [Vector3(0.5, 0.0, 5.0), Vector3(0, 0, -1)]
	assert(c._gizmo_press(), "el rayo debe enganchar el eje X")
	# El ratón "avanza" por el eje hasta x=0.8 -> delta 0.3.
	c.rayo = [Vector3(0.8, 0.0, 5.0), Vector3(0, 0, -1)]
	c._gizmo_arrastrar()
	var pos: Vector3 = c._prims[0][1]["pos"]
	assert(absf(pos.x - 0.3) < 0.03, "el prim debe moverse +0.3 en X (fue %.3f)" % pos.x)
	assert(absf(pos.y) < 0.001 and absf(pos.z) < 0.001, "no debe moverse en Y/Z")
	c._gizmo_soltar()
	assert(c._historial.puede_deshacer(0), "el arrastre debe dejar paso de deshacer")

	remove_child(cuerpo)
	cuerpo.free()
	remove_child(c)
	c.free()


func test_arrastre_escalar_eje_y() -> void:
	var c := FakeConstruccion.new()
	add_child(c)
	var cuerpo := _cuerpo()
	add_child(cuerpo)
	var datos := {
		"id": 1, "tipo": "cubo", "pos": Vector3.ZERO, "rot": Vector3.ZERO,
		"escala": Vector3(2, 2, 2), "color": Color.WHITE, "params": {},
	}
	c._prims = {0: {1: datos}}
	c._nodos = {0: {1: cuerpo}}
	c._seleccionado = cuerpo
	c._sel_isla = 0
	c._sel_id = 1
	c._herramienta = ConstruccionScript.Herramienta.SELECCION
	c._modo = true
	c._gizmo_modo = 2 # ESCALAR
	c._gizmo.global_position = Vector3.ZERO
	c._gizmo.scale = Vector3.ONE

	c.rayo = [Vector3(5.0, 0.2, 0.0), Vector3(-1, 0, 0)]
	assert(c._gizmo_press(), "el rayo debe enganchar el eje Y")
	c.rayo = [Vector3(5.0, 0.5, 0.0), Vector3(-1, 0, 0)]
	c._gizmo_arrastrar()
	var esc: Vector3 = c._prims[0][1]["escala"]
	assert(absf(esc.y - 2.3) < 0.05, "la escala Y debe crecer ~0.3 (fue %.3f)" % esc.y)
	assert(absf(esc.x - 2.0) < 0.001, "X no debe cambiar")
	c._gizmo_soltar()
	remove_child(cuerpo)
	cuerpo.free()
	remove_child(c)
	c.free()