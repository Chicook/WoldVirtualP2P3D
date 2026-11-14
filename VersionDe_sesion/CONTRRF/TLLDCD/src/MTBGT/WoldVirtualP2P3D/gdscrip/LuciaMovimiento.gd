extends Node
## Gestos y caminar de LucIA con los clips de su GLB.
##
## Clips disponibles: `parada` (reposo), `andar`/`andar_001`, `Action`,
## `Action_001`, `Action_002`, `MVbrazo1`, `MVbrazo2`.
## - Al hablar, gesticula con los brazos y vuelve a `parada`.
## - `caminar(segundos)` la saca del sitio un paso y la devuelve.

const REPOSO := "avatar/lucia_parado"
const CAMINAR := "avatar/lucia_caminar"
const ANIMS := preload("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/animaciones_avatar.tres")
const BIBLIOTECA := "avatar"
## Clips que no son gestos aunque tengan contenido.
const NO_GESTO := ["andar", "caminar", "correr", "parada", "parado", "idle", "tpose", "saltar", "strafe", "mixamo", "ablando"]
## Gestos preferidos: si el modelo trae más (saludo, señalar…), se añaden solos.
const GESTOS := ["lucia_hablando"]

var _jugador: AnimationPlayer
var _raiz: Node3D
var _origen := Vector3.ZERO
var _gesto_actual := 0
var _ocupado := false


func _ready() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	_jugador = _buscar(get_parent())
	_raiz = get_parent() as Node3D
	if _raiz:
		_origen = _raiz.position
	if _jugador == null:
		print("[LuciaMovimiento] sin AnimationPlayer")
		return
	_instalar_animaciones()
	print("[LuciaMovimiento] clips: ", _jugador.get_animation_list())
	_reposo()


## Añade las animaciones de los avatares retargeteadas a los huesos de LucIA.
func _instalar_animaciones() -> void:
	if ANIMS == null or _jugador == null:
		return
	if _jugador.has_animation_library(BIBLIOTECA):
		return
	var libreria := AnimationLibrary.new()
	for nombre in ANIMS.get_animation_list():
		libreria.add_animation(nombre, ANIMS.get_animation(nombre))
	_jugador.add_animation_library(BIBLIOTECA, libreria)


func _buscar(nodo: Node) -> AnimationPlayer:
	if nodo is AnimationPlayer:
		return nodo
	for hijo in nodo.get_children():
		var encontrado := _buscar(hijo)
		if encontrado != null:
			return encontrado
	return null


## Un clip sirve si existe, tiene pistas y dura algo (los vacíos no).
func _existe(nombre: String) -> bool:
	if _jugador == null or not _jugador.has_animation(nombre):
		return false
	var anim := _jugador.get_animation(nombre)
	return anim != null and anim.get_track_count() > 0 and anim.length > 0.1


func _reposo() -> void:
	if _existe(REPOSO):
		_jugador.play(REPOSO)


## Gestos disponibles: la lista fija más cualquier clip con contenido que no
## sea caminar/correr/reposo (así, si exportas «saludo», entra solo).
func _gestos() -> Array[String]:
	var lista: Array[String] = []
	for nombre in GESTOS:
		if _existe(nombre):
			lista.append(nombre)
	if _jugador:
		for nombre in _jugador.get_animation_list():
			if nombre in lista:
				continue
			var bajo := nombre.to_lower()
			var descartado := false
			for clave in NO_GESTO:
				if bajo.contains(clave):
					descartado = true
					break
			if not descartado and _existe(nombre):
				lista.append(nombre)
	return lista


## Gesto con los brazos; al terminar vuelve al reposo.
func gesticular() -> void:
	if _ocupado or _jugador == null:
		return
	var disponibles := _gestos()
	if disponibles.is_empty():
		return
	var elegido: String = disponibles[_gesto_actual % disponibles.size()]
	_gesto_actual = (_gesto_actual + 1) % disponibles.size()
	_ocupado = true
	_jugador.play(elegido)
	await get_tree().create_timer(1.8).timeout
	_ocupado = false
	if not _andando:
		_reposo()


var _andando := false


## Camina unos pasos (hacia atrás, para no meterse en la mesa) y vuelve.
func caminar(segundos: float = 3.0) -> void:
	if _jugador == null or _andando:
		return
	_andando = true
	if _existe(CAMINAR):
		_jugador.play(CAMINAR)
	var destino := _origen + Vector3(0.0, 0.0, -1.1)
	var tween := create_tween()
	tween.tween_property(_raiz, "position", destino, segundos * 0.5)
	tween.tween_interval(0.4)
	tween.tween_property(_raiz, "position", _origen, segundos * 0.5)
	await tween.finished
	_andando = false
	_reposo()


func esta_andando() -> bool:
	return _andando
