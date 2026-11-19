extends SceneTree

var personaje: Node
var frames := 0

func _initialize() -> void:
	var escena: PackedScene = load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn")
	personaje = escena.instantiate()
	root.add_child(personaje)

func _process(_delta: float) -> bool:
	frames += 1
	if frames == 2:
		var idle: AnimationPlayer = personaje.get_node_or_null("AnimIdle")
		if idle:
			idle.stop()
		var lucia: Node3D = personaje.get_node("LucIA")
		lucia.transform = Transform3D.IDENTITY
		personaje.iniciar_gesticulacion()
	elif frames == 45:
		var esq: Skeleton3D = personaje.get_node("LucIA/cuerpo/Esqueleto")
		var hd := esq.find_bone("hombroD")
		var bd := esq.find_bone("brazoD")
		var hi := esq.find_bone("hombroI")
		var cab := esq.find_bone("cabeza")
		print("hombroD rot=", esq.get_bone_pose_rotation(hd))
		print("brazoD  rot=", esq.get_bone_pose_rotation(bd))
		print("hombroI rot=", esq.get_bone_pose_rotation(hi))
		print("cabeza  rot=", esq.get_bone_pose_rotation(cab))
		var gestos: AnimationPlayer = personaje.get_node("AnimGestos")
		print("gestos playing=", gestos.is_playing(), " pos=", gestos.current_animation_position)
		quit()
	return false
