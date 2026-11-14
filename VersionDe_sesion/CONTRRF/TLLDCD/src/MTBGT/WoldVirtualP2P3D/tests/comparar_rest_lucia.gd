extends SceneTree

func _init() -> void:
	var a := _cargar("res://gltfimport/avatares/AVH1.gltf")
	var b := _cargar("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb")
	var sa := _sk(a)
	var sb := _sk(b)
	print("avatar skeleton=", sa, " lucia skeleton=", sb)
	for base in ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftUpLeg", "RightUpLeg"]:
		var ia := _hueso(sa, "mixamorig_" + base)
		var ib := _hueso(sb, "mixamorig8_" + base)
		if ia < 0 or ib < 0:
			print(base, " falta ", ia, "/", ib)
			continue
		var ra := sa.get_bone_rest(ia)
		var rb := sb.get_bone_rest(ib)
		print(base, " restA=", ra.basis.get_euler(), " restB=", rb.basis.get_euler(), " delta=", (ra.basis.inverse() * rb.basis).get_euler())
	quit(0)


func _cargar(ruta: String) -> Node:
	var p := load(ruta) as PackedScene
	var n := p.instantiate()
	get_root().add_child(n)
	return n


func _sk(n: Node) -> Skeleton3D:
	for s in n.find_children("*", "Skeleton3D", true, false):
		return s as Skeleton3D
	return null


func _hueso(sk: Skeleton3D, nombre: String) -> int:
	if sk == null:
		return -1
	for i in sk.get_bone_count():
		if str(sk.get_bone_name(i)) == nombre:
			return i
	return -1
