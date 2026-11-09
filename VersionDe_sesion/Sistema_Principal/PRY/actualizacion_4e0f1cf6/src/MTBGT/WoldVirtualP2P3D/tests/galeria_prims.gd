extends Node3D
## Galería visual de prims paramétricos (test manual).
## Filas = tipo de prim · Columnas = variante de forma. Sirve para comprobar a
## ojo que corte, hueco, giro, estrechado y cizalla producen lo esperado y que
## las caras miran hacia fuera (si estuvieran invertidas, se verían oscuras).

const Prims = preload("res://gdscrip/Prims.gd")

const TIPOS := ["cubo", "cilindro", "cono", "esfera", "toro"]
const VARIANTES := [
	{"etiqueta": "neutro", "params": {}},
	{"etiqueta": "corte", "params": {"corte_ini": 0.25}},
	{"etiqueta": "hueco", "params": {"hueco": 0.5}},
	{"etiqueta": "giro", "params": {"giro": 180.0}},
	{"etiqueta": "estrechado", "params": {"estrechado_x": 0.6, "estrechado_y": 0.6}},
	{"etiqueta": "cizalla", "params": {"cizalla_x": 0.5}},
]

const SEP := 2.6


func _ready() -> void:
	_construir()
	_luz()
	_camara()


func _construir() -> void:
	for r in TIPOS.size():
		for c in VARIANTES.size():
			var var_: Dictionary = VARIANTES[c]
			var malla: Mesh = Prims.crear_malla(TIPOS[r], var_["params"])
			var mi := MeshInstance3D.new()
			mi.mesh = malla
			var color: Color = Prims.COLORES[(r * VARIANTES.size() + c) % Prims.COLORES.size()]
			mi.material_override = Prims.crear_material(color)
			mi.position = Vector3(c * SEP, 0.0, r * SEP)
			mi.scale = Vector3(2.0, 2.0, 2.0)
			add_child(mi)
	# Etiquetas de columna (arriba) y de fila (izquierda).
	for c in VARIANTES.size():
		_etiqueta(str(VARIANTES[c]["etiqueta"]), Vector3(c * SEP, 1.9, -1.6), 0.32)
	for r in TIPOS.size():
		_etiqueta(TIPOS[r], Vector3(-1.9, 1.9, r * SEP), 0.32)


func _etiqueta(texto: String, pos: Vector3, tam: float) -> void:
	var l := Label3D.new()
	l.text = texto
	l.position = pos
	l.pixel_size = tam * 0.01
	l.font_size = 64
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.modulate = Color(0.9, 0.95, 1.0)
	add_child(l)


func _luz() -> void:
	var luz := DirectionalLight3D.new()
	luz.rotation_degrees = Vector3(-55.0, -40.0, 0.0)
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


func _camara() -> void:
	var cam := Camera3D.new()
	add_child(cam)
	cam.position = Vector3(6.5, 14.0, 14.0)
	cam.look_at(Vector3(6.5, 0.3, 5.2), Vector3.UP)
	cam.current = true