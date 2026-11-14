extends Node
## Depuración de la caja de un avatar.

func _ready() -> void:
	for id in ["AVH1", "AVMJ1", "AVH2", "AVMJ2"]:
		var n: Node3D = load("res://avatares/%s.tscn" % id).instantiate()
		add_child(n)
		await get_tree().process_frame
		var modelo: Node3D = n.get_node("Modelo")
		print("\n=== ", id, " modelo=", modelo, " global=", modelo.global_transform)
		var caja := AABB()
		var primero := true
		var inv := modelo.global_transform.affine_inverse()
		for nodo in modelo.find_children("*", "MeshInstance3D", true, false):
			var mi := nodo as MeshInstance3D
			var a := mi.get_aabb()
			var rel := inv * mi.global_transform
			var at := rel * a
			print("  ", mi.name, " mesh=", mi.mesh, " aabb=", a, " size=", a.size, " rel_size=", at.size)
			if primero:
				caja = at
				primero = false
			else:
				caja = caja.merge(at)
		print("  TOTAL=", caja, " size=", caja.size)
		n.queue_free()
		await get_tree().process_frame
	get_tree().quit(0)
