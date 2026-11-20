extends SceneTree

func _init() -> void:
	_probar("res://gltfimport/avatares/AVH1.gltf", "mixamorig_", "paradoMJ1_1")
	_probar("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb", "mixamorig8_", "mixamo_com")
	quit(0)


func _probar(ruta: String, prefijo: String, clip: String) -> void:
	var p := load(ruta) as PackedScene
	var n := p.instantiate()
	get_root().add_child(n)
	var jug: AnimationPlayer = null
	for x in n.find_children("*", "AnimationPlayer", true, false):
		jug = x as AnimationPlayer
		break
	var sk: Skeleton3D = null
	for x in n.find_children("*", "Skeleton3D", true, false):
		sk = x as Skeleton3D
		break
	var a := jug.get_animation(clip)
	var idx := -1
	for i in a.get_track_count():
		if str(a.track_get_path(i)).ends_with(prefijo + "Hips") and a.track_get_type(i) == Animation.TYPE_ROTATION_3D:
			idx = i
			break
	print("\n", ruta, " track=", idx)
	if idx >= 0:
		var q: Quaternion = a.rotation_track_interpolate(idx, 0.0)
		print("  key[0]=", q, " euler=", q.get_euler())
	var ih := -1
	for i in sk.get_bone_count():
		if str(sk.get_bone_name(i)) == prefijo + "Hips":
			ih = i
			break
	if ih >= 0:
		var r := sk.get_bone_rest(ih).basis.get_rotation_quaternion()
		print("  rest=", r, " euler=", r.get_euler())
