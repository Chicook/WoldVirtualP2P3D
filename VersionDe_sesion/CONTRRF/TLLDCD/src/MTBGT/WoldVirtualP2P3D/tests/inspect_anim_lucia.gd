extends SceneTree
## Inspecciona las pistas de animación de LucIA tal como las importa Godot.

func _init() -> void:
	var packed := load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb") as PackedScene
	var nodo := packed.instantiate()
	get_root().add_child(nodo)
	var jugador: AnimationPlayer = null
	for n in nodo.find_children("*", "AnimationPlayer", true, false):
		jugador = n as AnimationPlayer
		break
	print("AnimationPlayer=", jugador)
	if jugador:
		print("root_node=", jugador.root_node)
		for nombre in jugador.get_animation_list():
			var a := jugador.get_animation(nombre)
			print("--- ", nombre, " tracks=", a.get_track_count(), " len=", a.length)
			for i in mini(6, a.get_track_count()):
				print("  ", a.track_get_type(i), " ", a.track_get_path(i))
	quit(0)
