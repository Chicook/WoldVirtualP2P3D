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
	var cuerpo: MeshInstance3D = raiz.get_node("LucIA/cuerpo")
	var esq: Skeleton3D = cuerpo.get_node("Esqueleto")
	var m: ArrayMesh = cuerpo.mesh
	var arr: Array = m.surface_get_arrays(0)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var bones: PackedInt32Array = arr[Mesh.ARRAY_BONES]
	var weights: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]

	var con_cero := 0
	var cadera_solo := 0
	for v in verts.size():
		var base := v * 4
		var suma := weights[base] + weights[base + 1] + weights[base + 2] + weights[base + 3]
		if suma <= 0.0001:
			con_cero += 1
		if weights[base] >= 0.99 and bones[base] == esq.find_bone("cadera"):
			cadera_solo += 1
	print("verts=", verts.size(), " con_cero=", con_cero, " cadera_solo=", cadera_solo)

	_muestra("brazo", verts, bones, weights, esq, func(v: Vector3) -> bool: return v.x > 0.7)
	_muestra("cabeza", verts, bones, weights, esq, func(v: Vector3) -> bool: return v.y > 0.8)
	_muestra("torso", verts, bones, weights, esq, func(v: Vector3) -> bool: return absf(v.x) < 0.05 and v.y > 0.1 and v.y < 0.3)
	quit()
	return true

func _muestra(tag: String, verts: PackedVector3Array, bones: PackedInt32Array, weights: PackedFloat32Array, esq: Skeleton3D, cond: Callable) -> void:
	for v in verts.size():
		if cond.call(verts[v]):
			var base := v * 4
			var res := ""
			for k in 4:
				res += " %s(%.2f)" % [esq.get_bone_name(bones[base + k]), weights[base + k]]
			print(tag, " v[", v, "]=", verts[v], " ->", res)
			return
	print(tag, ": no encontrado")
