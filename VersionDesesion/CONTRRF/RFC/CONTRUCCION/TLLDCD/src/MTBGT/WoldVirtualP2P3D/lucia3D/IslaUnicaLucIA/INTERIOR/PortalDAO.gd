extends Area3D
## Portal del archipiélago en la DAO.
##
## Al cruzar el portal con el avatar local abre el explorador de islas
## (TeleportPanel del mundo). El visual reutiliza los shaders del portal del
## metaverso y el guion de orbes existente.

const GUION_VISUAL := preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/gdscrip/portal_visual.gd")
const SHADER_ANILLO := preload("res://gdshader/portal_ring.gdshader")
const SHADER_ENERGIA := preload("res://gdshader/portal_energy.gdshader")

const GRUPO_PANEL := "teleport_panel"

var _estado: Label3D = null
var _bloqueo_hasta := 0


func _ready() -> void:
	monitoring = true
	body_entered.connect(_on_body_entered)
	_construir()


func _construir() -> void:
	var visual := Node3D.new()
	visual.name = "Visual"
	visual.set_script(GUION_VISUAL)
	visual.set("orb_radius", 3.15)
	visual.set("orb_height", 3.7)
	visual.set("orb_speed", 0.7)
	visual.set("pulse_speed", 1.6)
	visual.set("light_min", 3.0)
	visual.set("light_max", 4.6)
	visual.set("membrane_min", 1.1)
	visual.set("membrane_max", 1.7)

	var plataforma := MeshInstance3D.new()
	plataforma.name = "Plataforma"
	var cil := CylinderMesh.new()
	cil.top_radius = 4.2
	cil.bottom_radius = 4.35
	cil.height = 0.16
	cil.radial_segments = 96
	plataforma.mesh = cil
	plataforma.material_override = _mat(Color(0.05, 0.065, 0.09), 0.32, 0.85)
	plataforma.position = Vector3(0.0, 0.08, 0.0)
	visual.add_child(plataforma)

	var borde := MeshInstance3D.new()
	borde.name = "Borde"
	var toro := TorusMesh.new()
	toro.inner_radius = 4.16
	toro.outer_radius = 4.34
	toro.rings = 128
	toro.ring_segments = 8
	borde.mesh = toro
	borde.material_override = _mat(Color(0.72, 0.54, 0.18), 0.28, 0.85, Color(0.72, 0.54, 0.18), 0.8)
	borde.position = Vector3(0.0, 0.17, 0.0)
	visual.add_child(borde)

	var anillo := Node3D.new()
	anillo.name = "Anillo"
	anillo.position = Vector3(0.0, 3.7, 0.0)
	anillo.rotation.x = PI * 0.5
	visual.add_child(anillo)

	var material_ext := ShaderMaterial.new()
	material_ext.shader = SHADER_ANILLO
	material_ext.set_shader_parameter("base_color", Color(0.03, 0.05, 0.08))
	material_ext.set_shader_parameter("glow_color", Color(0.12, 0.6, 1.0))
	material_ext.set_shader_parameter("bands", 5.0)
	material_ext.set_shader_parameter("speed", 0.45)
	material_ext.set_shader_parameter("glow_energy", 1.4)
	var material_int := ShaderMaterial.new()
	material_int.shader = SHADER_ANILLO
	material_int.set_shader_parameter("base_color", Color(0.03, 0.09, 0.12))
	material_int.set_shader_parameter("glow_color", Color(0.3, 1.0, 0.95))
	material_int.set_shader_parameter("bands", 7.0)
	material_int.set_shader_parameter("speed", -0.8)
	material_int.set_shader_parameter("glow_energy", 2.6)

	var anillo_ext := MeshInstance3D.new()
	anillo_ext.name = "AnilloExterior"
	var toro_ext := TorusMesh.new()
	toro_ext.inner_radius = 3.25
	toro_ext.outer_radius = 3.65
	toro_ext.rings = 128
	toro_ext.ring_segments = 24
	anillo_ext.mesh = toro_ext
	anillo_ext.material_override = material_ext
	anillo.add_child(anillo_ext)

	var anillo_int := MeshInstance3D.new()
	anillo_int.name = "AnilloInterior"
	var toro_int := TorusMesh.new()
	toro_int.inner_radius = 2.96
	toro_int.outer_radius = 3.12
	toro_int.rings = 128
	toro_int.ring_segments = 20
	anillo_int.mesh = toro_int
	anillo_int.material_override = material_int
	anillo.add_child(anillo_int)

	var membrana := MeshInstance3D.new()
	membrana.name = "Membrana"
	var quad := QuadMesh.new()
	quad.size = Vector2(6.1, 6.1)
	var material_energia := ShaderMaterial.new()
	material_energia.shader = SHADER_ENERGIA
	material_energia.set_shader_parameter("color_a", Color(0.05, 0.55, 1.0))
	material_energia.set_shader_parameter("color_b", Color(0.55, 0.15, 0.95))
	material_energia.set_shader_parameter("speed", 0.5)
	material_energia.set_shader_parameter("intensity", 1.3)
	material_energia.set_shader_parameter("swirl", 2.4)
	quad.material = material_energia
	membrana.mesh = quad
	membrana.position = Vector3(0.0, 3.7, 0.03)
	visual.add_child(membrana)

	var luz := OmniLight3D.new()
	luz.name = "Luz"
	luz.position = Vector3(0.0, 3.7, 0.9)
	luz.light_color = Color(0.25, 0.75, 1.0)
	luz.light_energy = 2.4
	luz.omni_range = 13.0
	visual.add_child(luz)

	var material_orbe := _mat(Color(0.5, 1.0, 1.0), 0.2, 0.0, Color(0.3, 0.95, 1.0), 3.0)
	for i in 3:
		var orbe := MeshInstance3D.new()
		orbe.name = "Orbe%d" % (i + 1)
		var esfera := SphereMesh.new()
		esfera.radius = 0.1
		esfera.height = 0.2
		esfera.radial_segments = 16
		esfera.rings = 8
		orbe.mesh = esfera
		orbe.material_override = material_orbe
		orbe.position = Vector3(0.0, 3.7, 0.35)
		visual.add_child(orbe)

	add_child(visual)

	var forma := BoxShape3D.new()
	forma.size = Vector3(7.6, 7.0, 2.6)
	var collision := CollisionShape3D.new()
	collision.shape = forma
	collision.position = Vector3(0.0, 3.5, 0.0)
	add_child(collision)

	_texto("RotuloPortal", "PORTAL DEL ARCHIPIÉLAGO", Vector3(0.0, 7.95, 0.0),
			56, Color(0.55, 0.9, 1.0), 8)
	_estado = _texto("EstadoPortal", "Cruza el portal para explorar las islas",
			Vector3(0.0, 0.85, 3.8), 40, Color(0.75, 0.85, 1.0), 6)


func _on_body_entered(body: Node3D) -> void:
	if body == null or not (body is CharacterBody3D):
		return
	if bool(body.get("es_clon_remoto")):
		return
	if Time.get_ticks_msec() < _bloqueo_hasta:
		return
	_bloqueo_hasta = Time.get_ticks_msec() + 3000
	var panel := get_tree().get_first_node_in_group(GRUPO_PANEL)
	if panel != null and panel.has_method("alternar"):
		panel.call("alternar")
		if _estado != null:
			_estado.text = "Explorador de islas abierto"
		print("[DAO] portal abre el explorador de islas")
	elif _estado != null:
		_estado.text = "Portal en espera del archipiélago"


func _texto(nombre: String, contenido: String, pos: Vector3, tam: int, color: Color,
		outline: int) -> Label3D:
	var etiqueta := Label3D.new()
	etiqueta.name = nombre
	etiqueta.text = contenido
	etiqueta.font_size = tam
	etiqueta.pixel_size = 0.006
	etiqueta.modulate = color
	etiqueta.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
	etiqueta.outline_size = outline
	etiqueta.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	etiqueta.position = pos
	add_child(etiqueta)
	return etiqueta


func _mat(color: Color, roughness := 0.7, metal := 0.0,
		emision := Color.BLACK, energia := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	m.metallic = metal
	if emision != Color.BLACK:
		m.emission_enabled = true
		m.emission = emision
		m.emission_energy_multiplier = energia
	return m
