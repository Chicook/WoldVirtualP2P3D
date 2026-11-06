extends Node3D
## Zona del portal. Permite usar el avatar elegido en el carrusel como jugador.

const Pers = preload("res://gdscrip/Personalizacion.gd")


func set_player_avatar(scene_path: String) -> void:
	var ps: PackedScene = load(scene_path)
	if ps == null:
		return
	var viejo := get_node_or_null("userbaseh1")
	var pos := Vector3(0.0, 0.5, 2.0)
	if viejo is Node3D:
		pos = (viejo as Node3D).position
		remove_child(viejo)
		viejo.queue_free()
	var inst := ps.instantiate()
	inst.name = "PlayerAvatar"
	if inst is Node3D:
		# Mira hacia el portal (-Z) para que se vea de frente al portón.
		(inst as Node3D).position = pos
		(inst as Node3D).rotation.y = PI
	add_child(inst)
	Pers.aplicar(inst, Pers.leer())
	# La camara que maneja el controlador del avatar es la primera del subtree; el
	# resto se apaga. Poner `current` en todas dejaba activa una camara que nadie
	# mueve (queda dentro del cuerpo, mirando desde dentro de la malla) y el cielo
	# se veia torcido segun que camara ganara el fotograma.
	var camaras := inst.find_children("*", "Camera3D", true, false)
	for indice in camaras.size():
		var cam := camaras[indice] as Camera3D
		if indice == 0:
			cam.top_level = true
			cam.current = true
		else:
			cam.current = false
