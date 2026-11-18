extends Node3D
## Plaza de registro de la DAO del metaverso.
##
## El espacio físico reparte las cuatro estaciones del alta en cruz cardinal
## alrededor del centro de la isla, en el mismo orden que el reparto de islas:
## norte (enfrente) identidad, este (derecha) cuenta única, oeste (izquierda)
## huella del equipo, sur (detrás) firma de sesión.
##
## Este nodo aporta la capa de escena, la señalización física y las señales del
## trámite. Cada estación lleva un halo en el suelo, una baliza en el borde y un
## aviso de "COMPLETADA", de modo que el alta se ve sobre la propia isla. La
## lógica de cada estación pertenece a los servicios de seguridad del Visor
## (STM_SGR, SMTPLC, SesionUnicaGuarda) y se conecta aquí sin cambiar la
## distribución.

signal estacion_abierta(estacion: StringName)
signal registro_completado(estacion: StringName, datos: Dictionary)

const ESTACIONES := {
	&"identidad": "RegistroNorte",
	&"cuenta_unica": "RegistroEste",
	&"huella_equipo": "RegistroOeste",
	&"firma_sesion": "RegistroSur",
}
const COLOR_CIAN := Color(0.12, 0.72, 1.0)
const COLOR_ORO := Color(0.72, 0.54, 0.18)

var _completadas := {}
var _abierta: StringName = &""
var _materiales := {}
var _avisos := {}
var _t := 0.0


func _ready() -> void:
	_montar_senalizacion()


func _process(delta: float) -> void:
	_t += delta
	if _abierta != &"" and _materiales.has(_abierta):
		var mat: StandardMaterial3D = _materiales[_abierta]
		mat.emission_energy_multiplier = 2.1 + 0.7 * sin(_t * 4.0)


func estaciones() -> Array:
	return ESTACIONES.keys()


func marcador(estacion: StringName) -> Marker3D:
	return get_node_or_null(str(ESTACIONES.get(estacion, ""))) as Marker3D


func abrir(estacion: StringName) -> bool:
	if not ESTACIONES.has(estacion):
		return false
	if _abierta != &"" and _abierta != estacion:
		_pintar(_abierta, "completa" if esta_completa(_abierta) else "inactiva")
	_abierta = estacion
	_pintar(estacion, "activa")
	estacion_abierta.emit(estacion)
	return true


func completar(estacion: StringName, datos: Dictionary = {}) -> bool:
	if not ESTACIONES.has(estacion):
		return false
	_completadas[estacion] = true
	if _abierta == estacion:
		_abierta = &""
	_pintar(estacion, "completa")
	registro_completado.emit(estacion, datos)
	return true


func esta_completa(estacion: StringName) -> bool:
	return bool(_completadas.get(estacion, false))


func progreso() -> int:
	return _completadas.size()


func registro_completo() -> bool:
	return _completadas.size() == ESTACIONES.size()


func reiniciar() -> void:
	_completadas.clear()
	_abierta = &""
	for clave in ESTACIONES:
		_pintar(clave, "inactiva")


func _montar_senalizacion() -> void:
	for clave in ESTACIONES:
		var marcador := marcador(clave)
		if marcador == null or marcador.has_node("HaloRegistro"):
			continue
		var material := StandardMaterial3D.new()
		material.albedo_color = Color(0.02, 0.05, 0.07)
		material.roughness = 0.4
		material.metallic = 0.3
		material.emission_enabled = true
		material.emission = COLOR_CIAN
		material.emission_energy_multiplier = 0.35
		_materiales[clave] = material

		var halo := MeshInstance3D.new()
		halo.name = "HaloRegistro"
		var toro := TorusMesh.new()
		toro.inner_radius = 5.05
		toro.outer_radius = 5.3
		toro.rings = 96
		toro.ring_segments = 8
		halo.mesh = toro
		halo.material_override = material
		halo.position = Vector3(0.0, 0.03, 0.0)
		marcador.add_child(halo)

		var baliza := MeshInstance3D.new()
		baliza.name = "BalizaRegistro"
		var cil := CylinderMesh.new()
		cil.top_radius = 0.12
		cil.bottom_radius = 0.12
		cil.height = 6.0
		cil.radial_segments = 16
		baliza.mesh = cil
		baliza.material_override = material
		baliza.position = Vector3(4.35, 3.0, 0.0)
		marcador.add_child(baliza)

		var aviso := Label3D.new()
		aviso.name = "AvisoCompletada"
		aviso.text = "COMPLETADA"
		aviso.font_size = 64
		aviso.pixel_size = 0.010
		aviso.modulate = Color(1.0, 0.87, 0.5)
		aviso.outline_modulate = Color(0.02, 0.03, 0.05, 1.0)
		aviso.outline_size = 10
		aviso.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		aviso.position = Vector3(0.0, 5.9, 0.0)
		aviso.visible = false
		marcador.add_child(aviso)
		_avisos[clave] = aviso


func _pintar(estacion: StringName, estado: String) -> void:
	var mat: StandardMaterial3D = _materiales.get(estacion)
	if mat == null:
		return
	match estado:
		"activa":
			mat.albedo_color = Color(0.03, 0.14, 0.2)
			mat.emission = COLOR_CIAN
			mat.emission_energy_multiplier = 2.4
		"completa":
			mat.albedo_color = Color(0.2, 0.15, 0.05)
			mat.emission = COLOR_ORO
			mat.emission_energy_multiplier = 1.9
			if _avisos.has(estacion):
				(_avisos[estacion] as Label3D).visible = true
		_:
			mat.albedo_color = Color(0.02, 0.05, 0.07)
			mat.emission = COLOR_CIAN
			mat.emission_energy_multiplier = 0.35
			if _avisos.has(estacion):
				(_avisos[estacion] as Label3D).visible = false
