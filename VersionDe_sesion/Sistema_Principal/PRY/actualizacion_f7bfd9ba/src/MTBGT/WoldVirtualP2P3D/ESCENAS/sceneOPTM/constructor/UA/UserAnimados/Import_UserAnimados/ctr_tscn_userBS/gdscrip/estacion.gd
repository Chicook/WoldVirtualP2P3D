extends Node3D
## Hangar espacial alrededor del portal: paredes paneladas, techo con vigas,
## tiras de luz, zócalos emisivos y compuerta de fondo.

@export var ancho := 24.0
@export var fondo := 28.0
@export var alto := 9.0
@export var grosor := 0.4
@export var paso := 4.0
@export var luces_techo := true

const PANEL_SHADER := preload("res://gdshader/hangar_panel.gdshader")

var _panel: ShaderMaterial
var _metal: StandardMaterial3D
var _luz: StandardMaterial3D
var _acento: StandardMaterial3D


func _ready() -> void:
	_crear_materiales()
	_crear_carcasa()
	_crear_costillas()
	_crear_iluminacion()
	_crear_zocalos()
	_crear_detalles()


func _crear_materiales() -> void:
	_panel = ShaderMaterial.new()
	_panel.shader = PANEL_SHADER
	_panel.set_shader_parameter("base_color", Color(0.05, 0.062, 0.085))
	_panel.set_shader_parameter("seam_color", Color(0.008, 0.012, 0.018))
	_panel.set_shader_parameter("panel", 2.0)
	_panel.set_shader_parameter("variation", 0.35)

	_metal = StandardMaterial3D.new()
	_metal.albedo_color = Color(0.028, 0.035, 0.05)
	_metal.metallic = 0.9
	_metal.roughness = 0.3

	_luz = StandardMaterial3D.new()
	_luz.albedo_color = Color(0.75, 0.9, 1.0)
	_luz.emission_enabled = true
	_luz.emission = Color(0.55, 0.8, 1.0)
	_luz.emission_energy_multiplier = 2.4

	_acento = StandardMaterial3D.new()
	_acento.albedo_color = Color(0.05, 0.4, 0.55)
	_acento.emission_enabled = true
	_acento.emission = Color(0.06, 0.6, 0.85)
	_acento.emission_energy_multiplier = 1.5


func _deco(nombre: String, tam: Vector3, pos: Vector3, mat: Material) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = tam
	mesh.material = mat
	var mi := MeshInstance3D.new()
	mi.name = nombre
	mi.mesh = mesh
	mi.position = pos
	add_child(mi)
	return mi


func _muro(nombre: String, tam: Vector3, pos: Vector3) -> void:
	var body := StaticBody3D.new()
	body.name = nombre
	body.position = pos
	var mesh := BoxMesh.new()
	mesh.size = tam
	mesh.material = _panel
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	body.add_child(mi)
	var shape := BoxShape3D.new()
	shape.size = tam
	var cs := CollisionShape3D.new()
	cs.shape = shape
	body.add_child(cs)
	add_child(body)


func _crear_carcasa() -> void:
	var mx := ancho * 0.5
	var mz := fondo * 0.5
	var h := alto * 0.5
	_muro("ParedIzquierda", Vector3(grosor, alto, fondo + grosor), Vector3(-mx, h, 0))
	_muro("ParedDerecha", Vector3(grosor, alto, fondo + grosor), Vector3(mx, h, 0))
	_muro("ParedFondo", Vector3(ancho, alto, grosor), Vector3(0, h, -mz))
	_muro("ParedFrente", Vector3(ancho, alto, grosor), Vector3(0, h, mz))
	_deco("Techo", Vector3(ancho + grosor, grosor, fondo + grosor), Vector3(0, alto + grosor * 0.5, 0), _panel)


func _crear_costillas() -> void:
	var mx := ancho * 0.5
	var mz := fondo * 0.5
	var x_in := mx - grosor * 0.5
	var z_in := mz - grosor * 0.5
	var i := 0
	var z := -mz + paso
	while z < mz - 0.01:
		_deco("CostillaL_%d" % i, Vector3(0.45, alto, 0.35), Vector3(-x_in + 0.22, alto * 0.5, z), _metal)
		_deco("CostillaR_%d" % i, Vector3(0.45, alto, 0.35), Vector3(x_in - 0.22, alto * 0.5, z), _metal)
		i += 1
		z += paso
	i = 0
	var x := -mx + paso
	while x < mx - 0.01:
		_deco("CostillaF_%d" % i, Vector3(0.35, alto, 0.45), Vector3(x, alto * 0.5, -z_in + 0.22), _metal)
		_deco("CostillaB_%d" % i, Vector3(0.35, alto, 0.45), Vector3(x, alto * 0.5, z_in - 0.22), _metal)
		i += 1
		x += paso
	i = 0
	z = -mz + paso
	while z < mz - 0.01:
		_deco("Viga_%d" % i, Vector3(ancho, 0.35, 0.35), Vector3(0, alto - 0.3, z), _metal)
		i += 1
		z += paso


func _crear_iluminacion() -> void:
	if not luces_techo:
		return
	for x in [-4.5, 4.5]:
		_deco("TiraLuz_%s" % str(x), Vector3(0.7, 0.08, fondo - 6.0), Vector3(x, alto - 0.16, 0), _luz)
		for z in [-9.0, -3.0, 3.0, 9.0]:
			var l := OmniLight3D.new()
			l.name = "LuzTecho_%d_%d" % [int(x), int(z)]
			l.position = Vector3(x, alto - 0.9, z)
			l.light_color = Color(0.72, 0.84, 1.0)
			l.light_energy = 1.1
			l.omni_range = 16.0
			l.shadow_enabled = false
			add_child(l)


func _crear_zocalos() -> void:
	var mx := ancho * 0.5
	var mz := fondo * 0.5
	var x_in := mx - grosor * 0.5
	var z_in := mz - grosor * 0.5
	_deco("ZocaloIzq", Vector3(0.08, 0.12, fondo - 0.6), Vector3(-x_in + 0.06, 0.11, 0), _acento)
	_deco("ZocaloDer", Vector3(0.08, 0.12, fondo - 0.6), Vector3(x_in - 0.06, 0.11, 0), _acento)
	_deco("ZocaloFondo", Vector3(ancho - 0.6, 0.12, 0.08), Vector3(0, 0.11, -z_in + 0.06), _acento)
	_deco("ZocaloFrente", Vector3(ancho - 0.6, 0.12, 0.08), Vector3(0, 0.11, z_in - 0.06), _acento)


func _crear_detalles() -> void:
	var mx := ancho * 0.5
	var mz := fondo * 0.5
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			_deco("Pilar_%d_%d" % [int(sx), int(sz)], Vector3(0.6, alto, 0.6),
				Vector3(sx * (mx - 0.5), alto * 0.5, sz * (mz - 0.5)), _metal)
	_deco("AcentoFondoIzq", Vector3(0.07, 6.6, 0.06), Vector3(-3.6, 4.0, -mz + grosor * 0.5 + 0.05), _acento)
	_deco("AcentoFondoDer", Vector3(0.07, 6.6, 0.06), Vector3(3.6, 4.0, -mz + grosor * 0.5 + 0.05), _acento)
	_deco("Compuerta", Vector3(6.4, 5.4, 0.14), Vector3(0, 2.9, mz - grosor * 0.5 - 0.08), _metal)
	_deco("CompuertaMarcoIzq", Vector3(0.1, 5.4, 0.1), Vector3(-3.2, 2.9, mz - grosor * 0.5 - 0.16), _acento)
	_deco("CompuertaMarcoDer", Vector3(0.1, 5.4, 0.1), Vector3(3.2, 2.9, mz - grosor * 0.5 - 0.16), _acento)
	_deco("CompuertaMarcoSup", Vector3(6.5, 0.1, 0.1), Vector3(0, 5.6, mz - grosor * 0.5 - 0.16), _acento)
