extends Node3D
## Test en vivo del módulo de construcción real: levanta Construccion como
## ChunkManager lo haría, registra una isla y reza varios prims con parámetros
## de forma para comprobarlos dentro del juego (no solo en la galería).

const Construccion = preload("res://gdscrip/Construccion.gd")
const Prims = preload("res://gdscrip/Prims.gd")

# Variables que Construccion consulta del padre (como hace ChunkManager).
var island_owners := {}
var my_own_index := 0
var _mi_uuid := "prueba"

var _construccion

const CASOS := [
	["cilindro", {"hueco": 0.5}],
	["cubo", {"corte_ini": 0.3}],
	["esfera", {"corte_ini": 0.3}],
	["toro", {"corte_ini": 0.25}],
	["cono", {}],
	["cilindro", {"estrechado_x": 0.6, "estrechado_y": 0.6}],
]


func _ready() -> void:
	island_owners[0] = [1, "prueba", "prueba"]

	var isla := Node3D.new()
	isla.name = "Isla0"
	add_child(isla)
	# Terreno mínimo (malla simple) para que registrar_isla tenga dónde montar
	# el contenedor de objetos; el esculpido no es objeto de este test.
	var suelo := MeshInstance3D.new()
	suelo.name = "isla3D"
	var plano := PlaneMesh.new()
	plano.size = Vector2(30, 30)
	suelo.mesh = plano
	isla.add_child(suelo)

	_construccion = Construccion.new()
	_construccion.name = "Construccion"
	add_child(_construccion)
	_construccion.registrar_isla(0, isla)

	_rezar()

	# Activa el modo construcción y selecciona el primer prim para ver el gizmo.
	_construccion._activar_modo(true)
	var nodos: Dictionary = _construccion._nodos.get(0, {})
	if not nodos.is_empty():
		_construccion._seleccionar(nodos[nodos.keys()[0]])

	var luz := DirectionalLight3D.new()
	luz.rotation_degrees = Vector3(-55.0, -35.0, 0.0)
	luz.light_energy = 1.3
	add_child(luz)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.08, 0.10, 0.14)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.5, 0.56, 0.66)
	e.ambient_light_energy = 0.7
	env.environment = e
	add_child(env)
	var cam := Camera3D.new()
	add_child(cam)
	cam.position = Vector3(7.5, 5.0, 12.0)
	cam.look_at(Vector3(7.5, 1.2, 0.0), Vector3.UP)
	cam.current = true


func _rezar() -> void:
	for i in CASOS.size():
		var caso: Array = CASOS[i]
		var pos := Vector3(i * 3.0, 1.0, 0.0)
		_construccion._rez_con_datos(0, str(caso[0]), pos, Vector3.ZERO,
				Vector3(2.0, 2.0, 2.0), Prims.COLORES[i % Prims.COLORES.size()], caso[1])