extends Node
## Mueve la boca de LucIA con su blend shape `BOCAVOZ`.
##
## El modelo trae un único morph target para la voz, así que se abre y cierra
## con una oscilación irregular (para que no parezca un metrónomo). Expone
## `hablar(segundos)` y `callar()` para engancharlo al texto o al audio.

const NOMBRE_BOCA := "boca"

var _malla: MeshInstance3D
var _indice := -1
var _nivel := 0.0
var _fase := 0.0
var _hablando := false
var _fin := 0.0
var _ciclo := 0.0


func _ready() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	_localizar()


func _localizar() -> void:
	for nodo in get_parent().find_children("*", "MeshInstance3D", true, false):
		var malla := nodo as MeshInstance3D
		if malla == null or malla.mesh == null:
			continue
		# No todas las mallas del GLB traen morph targets (ni siquiera exponen el
		# método): se ignoran sin romper el resto de la búsqueda.
		if not malla.mesh.has_method("get_blend_shape_count"):
			continue
		if malla.mesh.get_blend_shape_count() <= 0:
			continue
		_malla = malla
		for i in malla.mesh.get_blend_shape_count():
			var nombre: String = malla.mesh.get_blend_shape_name(i).to_lower()
			if nombre.contains(NOMBRE_BOCA):
				_indice = i
				break
		if _indice < 0:
			_indice = 0
		break
	if _malla == null:
		print("[LuciaBoca] el modelo no tiene blend shapes")
	else:
		print("[LuciaBoca] boca lista: ", _malla.mesh.get_blend_shape_name(_indice))


## Abre y cierra la boca durante `segundos`.
func hablar(segundos: float) -> void:
	_hablando = true
	_fin = Time.get_ticks_msec() / 1000.0 + segundos


## Cierra la boca y deja de hablar.
func callar() -> void:
	_hablando = false


func _process(delta: float) -> void:
	if _malla == null or _indice < 0:
		return
	_ciclo += delta
	var ahora := Time.get_ticks_msec() / 1000.0
	var objetivo := 0.0
	if _hablando and ahora < _fin:
		_fase += delta * 11.0
		var onda := 0.5 + 0.5 * sin(_fase)
		onda *= 0.75 + 0.25 * sin(_fase * 0.31)
		objetivo = clampf(onda, 0.0, 1.0) * 0.9
	_nivel = lerpf(_nivel, objetivo, minf(1.0, delta * 16.0))
	_malla.set_blend_shape_value(_indice, _nivel)
