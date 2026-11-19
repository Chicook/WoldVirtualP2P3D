extends Node
## Pone a LucIA en su animación idle.
##
## Usa las animaciones de los avatares varones (esqueleto Mixamo estándar)
## retargeteadas a los huesos `mixamorig8:` de LucIA. Si la librería no está,
## cae al clip `mixamo_com` original del GLB.

const ANIMS := preload("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/animaciones_avatar.tres")
const BIBLIOTECA := "avatar"
const PREFERIDOS := ["avatar/lucia_parado", "parada", "idle", "mixamo_com"]

var _jugador: AnimationPlayer


func _ready() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	_jugador = _buscar(get_parent())
	if _jugador == null:
		print("[LuciaIdle] sin AnimationPlayer")
		return
	_instalar_animaciones()
	var lista := _jugador.get_animation_list()
	if lista.is_empty():
		print("[LuciaIdle] el jugador no tiene clips")
		return
	var elegido := ""
	for candidato in PREFERIDOS:
		if candidato in lista:
			elegido = candidato
			break
	if elegido.is_empty():
		var mejor := 0.0
		for nombre in lista:
			var anim := _jugador.get_animation(nombre)
			if anim and anim.length > mejor:
				mejor = anim.length
				elegido = nombre
	if elegido.is_empty():
		return
	var animacion := _jugador.get_animation(elegido)
	if animacion:
		animacion.loop_mode = Animation.LOOP_LINEAR
	_jugador.play(elegido)
	print("[LuciaIdle] reproduciendo ", elegido, " en bucle")


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
