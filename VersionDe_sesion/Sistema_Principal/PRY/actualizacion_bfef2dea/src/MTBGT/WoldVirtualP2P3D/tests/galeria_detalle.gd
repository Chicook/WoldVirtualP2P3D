extends Node3D
## Primer plano de los casos clave del editor de prims (test manual):
## hueco de caja (marco), corte de cilindro (cuña), corte de cubo, corte de
## esfera y corte de toro.

const Prims = preload("res://gdscrip/Prims.gd")

const CASOS := [
	["cubo", {"hueco": 0.5}],
	["cilindro", {"corte_ini": 0.25}],
	["cilindro", {"hueco": 0.5}],
	["cubo", {"corte_ini": 0.3}],
	["esfera", {"corte_ini": 0.3}],
	["toro", {"corte_ini": 0.25}],
]

const SEP := 3.4


func _ready() -> void:
	for i in CASOS.size():
		var caso: Array = CASOS[i]
		var malla: Mesh = Prims.crear_malla(str(caso[0]), caso[1])
		var mi := MeshInstance3D.new()
		mi.mesh = malla
		mi.material_override = Prims.crear_material(Prims.COLORES[i % Prims.COLORES.size()])
		mi.position = Vector3(i * SEP, 0.0, 0.0)
		mi.scale = Vector3(2.4, 2.4, 2.4)
		add_child(mi)
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
	cam.position = Vector3(8.5, 7.5, 9.5)
	cam.look_at(Vector3(8.5, 0.3, 1.2), Vector3.UP)
	cam.current = true