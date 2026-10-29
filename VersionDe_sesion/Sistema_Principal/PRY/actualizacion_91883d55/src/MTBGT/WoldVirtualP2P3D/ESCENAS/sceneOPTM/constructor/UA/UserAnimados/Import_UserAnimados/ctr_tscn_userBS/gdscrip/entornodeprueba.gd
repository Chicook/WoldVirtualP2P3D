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
	for cam in inst.find_children("*", "Camera3D", true, false):
		(cam as Camera3D).current = true
