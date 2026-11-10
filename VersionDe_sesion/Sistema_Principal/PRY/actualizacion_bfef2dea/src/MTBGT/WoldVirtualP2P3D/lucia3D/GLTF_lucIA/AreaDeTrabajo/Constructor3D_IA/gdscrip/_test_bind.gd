extends SceneTree

var _frames := 0

func _initialize() -> void:
	var escena: PackedScene = load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn")
	root.add_child(escena.instantiate())

func _process(_delta: float) -> bool:
	_frames += 1
	if _frames < 3:
		return false
	var raiz := root.get_child(0)
	var esq: Skeleton3D = raiz.get_node("LucIA/cuerpo/Esqueleto")
	for h in esq.get_bone_count():
		var rest := esq.get_bone_global_rest(h)
		var pose := esq.get_bone_global_pose(h)
		var bt := pose * rest.affine_inverse()
		print("%-8s rest=%s pose=%s | pose*inv(rest)=%s" % [esq.get_bone_name(h), rest.origin, pose.origin, bt])
	quit()
	return true
