extends Node3D
## Carrusel de avatares de la DAO: ocho estatuas vivas en un aro giratorio.
##
## Las estatuas son las escenas jugables reales del catálogo, instanciadas en
## modo `es_selector` (sin física, cámara ni entrada) para que respiren y
## miren al centro. La consola junto al aro abre el carrusel original
## (`res://avatares/CarruselAvatares.tscn`) para cambiar de avatar.

const Catalogo = preload("res://avatares/CatalogoAvatares.gd")
const ESCENA_CARRUSEL: PackedScene = preload("res://avatares/CarruselAvatares.tscn")
const SUELO_Y := 41.7
const RADIO := 14.0
const VELOCIDAD_GIRO := 0.045

var _aro: Node3D = null
var _estatuas: Array[Node3D] = []
var _abierto := false
var _jugador: Node3D = null
var _camara_previa: Camera3D = null
var _capa_carrusel: Node3D = null
var _bloqueo_hasta := 0


func _ready() -> void:
	_aro = Node3D.new()
	_aro.name = "AroAvatares"
	add_child(_aro)
	_construir_estatuas()
	_construir_consola()


func _process(delta: float) -> void:
	if _aro != null:
		_aro.rotation.y += delta * VELOCIDAD_GIRO


func _unhandled_input(event: InputEvent) -> void:
	if _abierto and event.is_action_pressed("ui_cancel"):
		_cerrar()
		get_viewport().set_input_as_handled()


# ---------------------------------------------------------------------------
# Montaje
# ---------------------------------------------------------------------------

func _construir_estatuas() -> void:
	var base := _mat(Color(0.05, 0.06, 0.09), 0.35, 0.6)
	var oro := _mat(Color(0.72, 0.54, 0.18), 0.28, 0.85, Color(0.72, 0.54, 0.18), 0.6)
	var total := Catalogo.total()
	for i in total:
		var modelo := Catalogo.por_indice(i)
		if modelo.is_empty():
			continue
		var ang := deg_to_rad(22.5) + TAU * float(i) / float(total)
		var centro := Vector3(sin(ang) * RADIO, SUELO_Y, cos(ang) * RADIO)
		var pedestal := Node3D.new()
		pedestal.name = "Pedestal_%s" % str(modelo["id"])
		pedestal.position = centro
		_aro.add_child(pedestal)

		var disco := MeshInstance3D.new()
		disco.name = "Disco"
		var cil := CylinderMesh.new()
		cil.top_radius = 1.15
		cil.bottom_radius = 1.25
		cil.height = 0.5
		cil.radial_segments = 64
		disco.mesh = cil
		disco.material_override = base
		disco.position = Vector3(0.0, 0.25, 0.0)
		pedestal.add_child(disco)

		var color: Color = modelo.get("color", Color(0.4, 0.8, 1.0))
		var anillo := MeshInstance3D.new()
		anillo.name = "AnilloAvatar"
		var toro := TorusMesh.new()
		toro.inner_radius = 1.16
		toro.outer_radius = 1.28
		toro.rings = 64
		toro.ring_segments = 8
		anillo.mesh = toro
		anillo.material_override = _mat(color * 0.3, 0.3, 0.2, color, 2.4)
		anillo.position = Vector3(0.0, 0.52, 0.0)
		pedestal.add_child(anillo)

		var forma := CylinderShape3D.new()
		forma.radius = 1.15
		forma.height = 0.5
		var cuerpo := StaticBody3D.new()
		cuerpo.name = "Colision"
		var nodo_forma := CollisionShape3D.new()
		nodo_forma.shape = forma
		cuerpo.add_child(nodo_forma)
		cuerpo.position = Vector3(0.0, 0.25, 0.0)
		pedestal.add_child(cuerpo)

		var avatar: Node3D = Catalogo.crear(str(modelo["id"]))
		if avatar == null:
			continue
		avatar.name = "Avatar_%s" % str(modelo["id"])
		avatar.set("es_selector", true)
		avatar.position = Vector3(0.0, 0.5, 0.0)
		avatar.rotation.y = ang + PI
		pedestal.add_child(avatar)
		_estatuas.append(avatar)

		var rotulo := Label3D.new()
		rotulo.name = "Nombre"
		rotulo.text = str(modelo["nombre"])
		rotulo.font_size = 48
		rotulo.pixel_size = 0.005
		rotulo.modulate = color
		rotulo.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
		rotulo.outline_size = 9
		rotulo.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		rotulo.position = Vector3(0.0, 2.5, 0.0)
		pedestal.add_child(rotulo)

		# Corchetes dorados en el borde del pedestal.
		var marca := MeshInstance3D.new()
		marca.name = "FiloDora"
		var aro := TorusMesh.new()
		aro.inner_radius = 1.0
		aro.outer_radius = 1.03
		aro.rings = 48
		aro.ring_segments = 6
		marca.mesh = aro
		marca.material_override = oro
		marca.position = Vector3(0.0, 0.51, 0.0)
		pedestal.add_child(marca)


func _construir_consola() -> void:
	var centro := Vector3(11.5, SUELO_Y, 11.5)
	var consola := Node3D.new()
	consola.name = "ConsolaAvatares"
	consola.position = centro
	consola.rotation.y = atan2(-centro.x, -centro.z)
	add_child(consola)

	var cuerpo := MeshInstance3D.new()
	cuerpo.name = "Cuerpo"
	var caja := BoxMesh.new()
	caja.size = Vector3(2.2, 1.05, 0.9)
	cuerpo.mesh = caja
	cuerpo.material_override = _mat(Color(0.05, 0.06, 0.09), 0.35, 0.6)
	cuerpo.position = Vector3(0.0, 0.52, 0.0)
	consola.add_child(cuerpo)

	var pantalla := MeshInstance3D.new()
	pantalla.name = "Pantalla"
	var panel := BoxMesh.new()
	panel.size = Vector3(1.9, 1.05, 0.08)
	pantalla.mesh = panel
	pantalla.material_override = _mat(Color(0.02, 0.09, 0.13), 0.2, 0.2, Color(0.12, 0.65, 1.0), 1.8)
	pantalla.position = Vector3(0.0, 1.55, 0.0)
	pantalla.rotation.x = -0.22
	consola.add_child(pantalla)

	var rotulo := Label3D.new()
	rotulo.name = "Rotulo"
	rotulo.text = "CARRUSEL DE AVATARES"
	rotulo.font_size = 72
	rotulo.pixel_size = 0.006
	rotulo.modulate = Color(0.55, 0.9, 1.0)
	rotulo.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
	rotulo.outline_size = 10
	rotulo.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	rotulo.position = Vector3(0.0, 3.3, 0.0)
	consola.add_child(rotulo)

	var ayuda := Label3D.new()
	ayuda.name = "Ayuda"
	ayuda.text = "Acércate para elegir tu avatar"
	ayuda.font_size = 34
	ayuda.pixel_size = 0.005
	ayuda.modulate = Color(0.7, 0.85, 1.0)
	ayuda.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
	ayuda.outline_size = 8
	ayuda.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	ayuda.position = Vector3(0.0, 2.7, 0.0)
	consola.add_child(ayuda)

	var zona := Area3D.new()
	zona.name = "ZonaAvatares"
	var forma := CylinderShape3D.new()
	forma.radius = 2.6
	forma.height = 3.0
	var nodo_forma := CollisionShape3D.new()
	nodo_forma.shape = forma
	zona.add_child(nodo_forma)
	zona.position = Vector3(0.0, 1.5, 0.0)
	consola.add_child(zona)
	zona.body_entered.connect(_on_zona_entrada)


func _on_zona_entrada(body: Node3D) -> void:
	if _abierto or _jugador != null or body == null:
		return
	if Time.get_ticks_msec() < _bloqueo_hasta:
		return
	if not (body is CharacterBody3D):
		return
	if bool(body.get("es_clon_remoto")):
		return
	_abrir(body)


# ---------------------------------------------------------------------------
# Carrusel original como capa interactiva
# ---------------------------------------------------------------------------

func _abrir(jugador: Node3D) -> void:
	if _abierto or not ResourceLoader.exists(ESCENA_CARRUSEL.resource_path):
		return
	_abierto = true
	_jugador = jugador
	_camara_previa = get_viewport().get_camera_3d()
	jugador.set_physics_process(false)
	jugador.set_process_input(false)
	_capa_carrusel = ESCENA_CARRUSEL.instantiate() as Node3D
	if _capa_carrusel == null:
		_abierto = false
		_jugador = null
		_camara_previa = null
		return
	get_tree().root.add_child(_capa_carrusel)
	if _capa_carrusel.has_signal("avatar_confirmed"):
		_capa_carrusel.connect("avatar_confirmed", _al_confirmar)
	print("[DAO] carrusel de avatares abierto desde la DAO")


func _al_confirmar(_ruta: String) -> void:
	_cerrar()


func _cerrar() -> void:
	if _capa_carrusel != null and is_instance_valid(_capa_carrusel):
		_capa_carrusel.queue_free()
	_capa_carrusel = null
	if _jugador != null and is_instance_valid(_jugador):
		_jugador.set_physics_process(true)
		_jugador.set_process_input(true)
	_jugador = null
	if _camara_previa != null and is_instance_valid(_camara_previa):
		_camara_previa.current = true
	_camara_previa = null
	_abierto = false
	_bloqueo_hasta = Time.get_ticks_msec() + 3500


# ---------------------------------------------------------------------------
# Materiales y API
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


func estatuas() -> Array[Node3D]:
	return _estatuas


func abierto() -> bool:
	return _abierto


func total_estatuas() -> int:
	return _estatuas.size()
