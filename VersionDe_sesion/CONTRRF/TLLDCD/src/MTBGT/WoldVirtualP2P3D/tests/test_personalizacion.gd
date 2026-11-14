extends SceneTree
## Comprueba que Personalizacion.aplicar funciona sobre una escena nueva.

func _init() -> void:
	var packed := load("res://avatares/AVH1.tscn") as PackedScene
	var n := packed.instantiate()
	get_root().add_child(n)
	var Pers = load("res://gdscrip/Personalizacion.gd")
	var d: Dictionary = Pers.POR_DEFECTO.duplicate()
	d["camiseta"] = Color(0.9, 0.1, 0.1)
	d["altura_cm"] = 5.0
	Pers.aplicar(n, d)
	var pintadas := 0
	for m in n.find_children("*", "MeshInstance3D", true, false):
		var mi := m as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var mat := mi.get_surface_override_material(s)
			if mat is BaseMaterial3D and (mat as BaseMaterial3D).albedo_color.r > 0.5 and (mat as BaseMaterial3D).albedo_color.g < 0.5:
				pintadas += 1
	print("[pers] superficies teñidas=", pintadas, " escala=", n.get_node("Modelo").scale)
	quit(0 if pintadas > 0 else 1)
