extends SceneTree
## Inspecciona un avatar jugable: mallas, superficies, materiales, morph targets
## y huesos. Sirve para decidir que personalizacion se puede hacer por script.

const RUTAS := [
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ6Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH1Ch3D.tscn",
]


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	for ruta in RUTAS:
		print("\n===== ", ruta, " =====")
		var inst := (load(ruta) as PackedScene).instantiate()
		get_root().add_child(inst)
		for mi in inst.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = mi.mesh
			if mesh == null:
				continue
			print("MALLA ", mi.name, "  superficies=", mesh.get_surface_count(),
				"  blend_shapes=", mesh.get_blend_shape_count())
			for s in mesh.get_surface_count():
				var mat := mesh.surface_get_material(s)
				var desc := "?"
				if mat is BaseMaterial3D:
					desc = "albedo=%s tex=%s" % [mat.albedo_color, mat.albedo_texture.resource_path if mat.albedo_texture else "sin"]
				print("   sup ", s, " mat=", mat.resource_name if mat else "null", " ", desc)
			for b in mesh.get_blend_shape_count():
				print("   shape ", b, ": ", mesh.get_blend_shape_name(b))
		for sk in inst.find_children("*", "Skeleton3D", true, false):
			var huesos: Array[String] = []
			for b in sk.get_bone_count():
				huesos.append(sk.get_bone_name(b))
			print("ESQUELETO ", sk.name, " huesos=", huesos.size())
			print("   ", ", ".join(huesos))
		inst.queue_free()
		await process_frame
	quit()
