extends Node
## Pone a LucIA en su animación idle (`mixamo_com` del esqueleto).
##
## Se añade como hijo de la escena de LucIA: busca el AnimationPlayer del
## esqueleto, elige el clip idle y lo deja en bucle. Si el rig cambia de
## nombre, se coge el primer clip largo que encuentre.

const PREFERIDOS := ["parada", "idle", "mixamo_com"]

var _jugador: AnimationPlayer


func _ready() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	_jugador = _buscar(get_parent())
	if _jugador == null:
		print("[LuciaIdle] sin AnimationPlayer")
		return
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


func _buscar(nodo: Node) -> AnimationPlayer:
	if nodo is AnimationPlayer:
		return nodo
	for hijo in nodo.get_children():
		var encontrado := _buscar(hijo)
		if encontrado != null:
			return encontrado
	return null
