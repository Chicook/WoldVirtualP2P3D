extends Node3D
## Plaza de registro de la DAO del metaverso.
##
## El espacio físico reparte las cuatro estaciones del alta en cruz cardinal
## alrededor del centro de la isla, en el mismo orden que el reparto de islas:
## norte (enfrente) identidad, este (derecha) cuenta única, oeste (izquierda)
## huella del equipo, sur (detrás) firma de sesión.
##
## Este nodo aporta la capa de escena y las señales del trámite. La lógica de
## cada estación pertenece a los servicios de seguridad del Visor (STM_SGR,
## SMTPLC, SesionUnicaGuarda) y se conecta aquí sin cambiar la distribución.

signal estacion_abierta(estacion: StringName)
signal registro_completado(estacion: StringName, datos: Dictionary)

const ESTACIONES := {
	&"identidad": "RegistroNorte",
	&"cuenta_unica": "RegistroEste",
	&"huella_equipo": "RegistroOeste",
	&"firma_sesion": "RegistroSur",
}

var _completadas := {}
var _abierta: StringName = &""


func estaciones() -> Array:
	return ESTACIONES.keys()


func marcador(estacion: StringName) -> Marker3D:
	return get_node_or_null(str(ESTACIONES.get(estacion, ""))) as Marker3D


func abrir(estacion: StringName) -> bool:
	if not ESTACIONES.has(estacion):
		return false
	_abierta = estacion
	estacion_abierta.emit(estacion)
	return true


func completar(estacion: StringName, datos: Dictionary = {}) -> bool:
	if not ESTACIONES.has(estacion):
		return false
	_completadas[estacion] = true
	if _abierta == estacion:
		_abierta = &""
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
