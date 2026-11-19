extends SceneTree

var _frames := 0

func _initialize() -> void:
	var escena: PackedScene = load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn")
	var raiz: Node = escena.instantiate()
	root.add_child(raiz)

func _process(_delta: float) -> bool:
	_frames += 1
	if _frames < 3:
		return false
	var raiz := root.get_child(0)
	var personaje := raiz
	var cuerpo: MeshInstance3D = raiz.get_node("LucIA/cuerpo")
	var esqueleto: Skeleton3D = cuerpo.get_node_or_null("Esqueleto")

	print("== DIAGNÓSTICO SKINNING ==")
	print("cuerpo.mesh: ", cuerpo.mesh, " (", cuerpo.mesh.get_class(), ")")
	print("cuerpo.skin: ", cuerpo.skin)
	print("cuerpo.skeleton path: ", cuerpo.skeleton)
	if esqueleto:
		print("esqueleto huesos: ", esqueleto.get_bone_count())
		for h in esqueleto.get_bone_count():
			print("  [", h, "] ", esqueleto.get_bone_name(h), " global_rest=", esqueleto.get_bone_global_rest(h).origin)
	var m: ArrayMesh = cuerpo.mesh
	print("blend shapes: ", m.get_blend_shape_count(), " -> ", m.get_blend_shape_name(0) if m.get_blend_shape_count() > 0 else "")
	var arr: Array = m.surface_get_arrays(0)
	print("bones array size: ", arr[Mesh.ARRAY_BONES].size() if arr[Mesh.ARRAY_BONES] != null else -1)
	print("weights array size: ", arr[Mesh.ARRAY_WEIGHTS].size() if arr[Mesh.ARRAY_WEIGHTS] != null else -1)
	print("material: ", m.surface_get_material(0))

	# Prueba de pose: rotar hombroD y leer la pose
	if esqueleto:
		var hd := esqueleto.find_bone("hombroD")
		esqueleto.set_bone_pose_rotation(hd, Quaternion(Vector3(0, 0, 1), 0.6))
		print("pose hombroD tras rotar: ", esqueleto.get_bone_pose(hd))
		print("pose global hombroD: ", esqueleto.get_bone_global_pose(hd))
	quit()
	return true
