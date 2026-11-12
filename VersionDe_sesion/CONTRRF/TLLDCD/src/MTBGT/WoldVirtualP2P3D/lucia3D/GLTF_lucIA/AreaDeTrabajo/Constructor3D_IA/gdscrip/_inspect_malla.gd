extends SceneTree

func _initialize() -> void:
	var escena: PackedScene = load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn")
	var raiz: Node = escena.instantiate()
	root.add_child(raiz)
	var cuerpo: MeshInstance3D = raiz.get_node("LucIA/cuerpo")
	var m: ArrayMesh = cuerpo.mesh

	var arr: Array = m.surface_get_arrays(0)
	print("SURFACE slots=", arr.size())
	for k in arr.size():
		var a = arr[k]
		if a != null:
			print("  slot ", k, " typeof=", typeof(a), " size=", a.size())

	var todas: Array = m.surface_get_blend_shape_arrays(0)
	print("BLEND num=", todas.size())
	for b in todas.size():
		var ba: Array = todas[b]
		print("  bs ", b, " slots=", ba.size())
		for k in ba.size():
			var a = ba[k]
			if a != null:
				print("    slot ", k, " typeof=", typeof(a), " size=", a.size())
				if typeof(a) == TYPE_PACKED_FLOAT32_ARRAY and a.size() > 0:
					print("      first 9: ", a.slice(0, 9))

	quit()
