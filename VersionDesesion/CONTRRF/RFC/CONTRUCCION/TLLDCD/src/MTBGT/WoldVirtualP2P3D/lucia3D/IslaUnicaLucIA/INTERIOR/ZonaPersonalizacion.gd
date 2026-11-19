extends Node3D
## Espejo del avatar en el salón de la DAO.
##
## El alta termina aquí: el ciudadano camina desde el carrusel hasta este podio
## y se mira en una puerta holográfica antes de abrir el editor de aspecto. La
## zona sólo construye la escena y expone sus puntos de llegada y de puesto; la
## cinemática del onboarding decide cuándo entrar.

const COLOR_ORO := Color(0.72, 0.54, 0.18)
const COLOR_CIAN := Color(0.12, 0.72, 1.0)
const COLOR_ACERO := Color(0.045, 0.055, 0.075)

var _aro_luz: Node3D = null
var _muestras: Array[Node3D] = []
var _t := 0.0


func _ready() -> void:
	add_to_group("zona_personalizacion")
	_construir()


func _process(delta: float) -> void:
	_t += delta
	if _aro_luz != null:
		_aro_luz.rotation.y += delta * 0.3
	for i in _muestras.size():
		var muestra := _muestras[i]
		if not is_instance_valid(muestra):
			continue
		var ang := _t * 0.55 + TAU * float(i) / float(maxi(_muestras.size(), 1))
		muestra.position = Vector3(sin(ang) * 2.05, 2.5 + sin(_t * 1.7 + float(i)) * 0.12, cos(ang) * 2.05)


# ---------------------------------------------------------------------------
# Montaje
# ---------------------------------------------------------------------------

func _construir() -> void:
	var metal := _mat(COLOR_ACERO, 0.4, 0.6)
	var oro := _mat(COLOR_ORO, 0.28, 0.85, COLOR_ORO, 0.7)
	var cian := _mat(Color(0.02, 0.1, 0.14), 0.3, 0.2, COLOR_CIAN, 2.4)

	var disco := MeshInstance3D.new()
	disco.name = "Podio"
	var cil := CylinderMesh.new()
	cil.top_radius = 3.2
	cil.bottom_radius = 3.35
	cil.height = 0.18
	cil.radial_segments = 96
	disco.mesh = cil
	disco.material_override = metal
	disco.position = Vector3(0.0, 0.09, 0.0)
	add_child(disco)

	var cuerpo := StaticBody3D.new()
	cuerpo.name = "ColisionPodio"
	var forma := CylinderShape3D.new()
	forma.radius = 3.2
	forma.height = 0.18
	var nodo_forma := CollisionShape3D.new()
	nodo_forma.shape = forma
	cuerpo.add_child(nodo_forma)
	cuerpo.position = Vector3(0.0, 0.09, 0.0)
	add_child(cuerpo)

	_aro("AroPodio", 3.24, 3.42, Vector3(0.0, 0.2, 0.0), oro)

	_aro_luz = _aro("AroGiratorio", 2.72, 2.86, Vector3(0.0, 0.24, 0.0), cian)
	_aro_luz.name = "AroGiratorio"

	_construir_espejo(oro, cian)
	_construir_pilares(metal, oro, cian)
	_construir_muestras()

	var rotulo := _texto("RotuloZona", "ZONA DE PERSONALIZACIÓN",
			Vector3(0.0, 5.4, 0.0), 64, Color(0.95, 0.82, 0.45), 0.008)
	rotulo.name = "RotuloZona"
	_texto("RotuloEspejo", "El espejo de tu avatar",
			Vector3(0.0, 4.62, 0.0), 34, Color(0.6, 0.9, 1.0), 0.006)

	var llegada := Marker3D.new()
	llegada.name = "Llegada"
	llegada.position = Vector3(0.0, 0.0, 3.9)
	add_child(llegada)

	var puesto := Marker3D.new()
	puesto.name = "Puesto"
	puesto.position = Vector3(0.0, 0.18, 0.1)
	add_child(puesto)

	var luz := OmniLight3D.new()
	luz.name = "LuzEspejo"
	luz.position = Vector3(0.0, 3.1, 1.4)
	luz.light_color = Color(0.32, 0.76, 1.0)
	luz.light_energy = 2.0
	luz.omni_range = 9.0
	add_child(luz)

	var luz_oro := OmniLight3D.new()
	luz_oro.name = "LuzPodio"
	luz_oro.position = Vector3(0.0, 0.8, -1.2)
	luz_oro.light_color = Color(1.0, 0.82, 0.5)
	luz_oro.light_energy = 1.1
	luz_oro.omni_range = 5.5
	add_child(luz_oro)


func _construir_espejo(oro: Material, cian: Material) -> void:
	# Puerta holográfica vertical detrás del podio: el avatar se mira en ella.
	var puerta := Node3D.new()
	puerta.name = "Espejo"
	puerta.position = Vector3(0.0, 2.9, -0.6)
	add_child(puerta)

	var marco_ext := MeshInstance3D.new()
	marco_ext.name = "MarcoEspejo"
	var toro := TorusMesh.new()
	toro.inner_radius = 2.72
	toro.outer_radius = 2.94
	toro.rings = 128
	toro.ring_segments = 16
	marco_ext.mesh = toro
	marco_ext.material_override = oro
	marco_ext.rotation.x = PI * 0.5
	puerta.add_child(marco_ext)

	var marco_int := MeshInstance3D.new()
	marco_int.name = "AroEspejo"
	var toro_int := TorusMesh.new()
	toro_int.inner_radius = 2.5
	toro_int.outer_radius = 2.58
	toro_int.rings = 128
	toro_int.ring_segments = 12
	marco_int.mesh = toro_int
	marco_int.material_override = cian
	marco_int.rotation.x = PI * 0.5
	puerta.add_child(marco_int)

	var membrana := MeshInstance3D.new()
	membrana.name = "MembranaEspejo"
	var quad := QuadMesh.new()
	quad.size = Vector2(4.9, 4.9)
	var velo := StandardMaterial3D.new()
	velo.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	velo.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	velo.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	velo.cull_mode = BaseMaterial3D.CULL_DISABLED
	velo.albedo_color = Color(0.25, 0.62, 1.0, 0.16)
	membrana.mesh = quad
	membrana.material_override = velo
	membrana.position = Vector3(0.0, 0.0, 0.02)
	puerta.add_child(membrana)


func _construir_pilares(metal: Material, oro: Material, cian: Material) -> void:
	for lado in [-3.1, 3.1]:
		_caja("Pilar", Vector3(0.42, 4.6, 0.42), Vector3(lado, 2.3, 0.2), metal)
		_caja("Capital", Vector3(0.62, 0.16, 0.62), Vector3(lado, 4.64, 0.2), oro)
		_caja("Filamento", Vector3(0.08, 3.8, 0.08),
				Vector3(lado * 0.86, 2.2, 0.2), cian)


func _construir_muestras() -> void:
	var colores := [
		Color(0.36, 0.72, 1.0), Color(1.0, 0.56, 0.78),
		Color(0.42, 0.9, 0.72), Color(0.95, 0.82, 0.45),
	]
	for i in colores.size():
		var muestra := MeshInstance3D.new()
		muestra.name = "Muestra_%d" % i
		var esfera := SphereMesh.new()
		esfera.radius = 0.2
		esfera.height = 0.4
		esfera.radial_segments = 20
		esfera.rings = 10
		muestra.mesh = esfera
		muestra.material_override = _mat(colores[i], 0.2, 0.2, colores[i], 2.0)
		add_child(muestra)
		_muestras.append(muestra)


# ---------------------------------------------------------------------------
# Primitivas
# ---------------------------------------------------------------------------

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


func _aro(nombre: String, radio_int: float, radio_ext: float, pos: Vector3,
		mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = nombre
	var toro := TorusMesh.new()
	toro.inner_radius = radio_int
	toro.outer_radius = radio_ext
	toro.rings = 128
	toro.ring_segments = 8
	mi.mesh = toro
	mi.material_override = mat
	mi.position = pos
	add_child(mi)
	return mi


func _caja(nombre: String, tam: Vector3, pos: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = nombre
	var caja := BoxMesh.new()
	caja.size = tam
	mi.mesh = caja
	mi.material_override = mat
	mi.position = pos
	add_child(mi)
	return mi


func _texto(nombre: String, contenido: String, pos: Vector3, tam: int,
		color: Color, ancho: float) -> Label3D:
	var etiqueta := Label3D.new()
	etiqueta.name = nombre
	etiqueta.text = contenido
	etiqueta.font_size = tam
	etiqueta.pixel_size = ancho
	etiqueta.modulate = color
	etiqueta.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
	etiqueta.outline_size = 10
	etiqueta.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	etiqueta.position = pos
	add_child(etiqueta)
	return etiqueta


# ---------------------------------------------------------------------------
# API para la cinemática
# ---------------------------------------------------------------------------

func punto_llegada() -> Vector3:
	var marcador := get_node_or_null("Llegada") as Marker3D
	return marcador.global_position if marcador != null else global_position


func punto_puesto() -> Vector3:
	var marcador := get_node_or_null("Puesto") as Marker3D
	return marcador.global_position if marcador != null else global_position
