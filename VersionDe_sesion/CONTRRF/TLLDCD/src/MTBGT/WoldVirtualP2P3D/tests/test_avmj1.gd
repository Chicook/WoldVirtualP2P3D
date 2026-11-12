extends SceneTree

func _init() -> void:
	var ruta := "res://gltfimport/avatares/AVMJ1.gltf"
	print("cargando ", ruta)
	var ps := load(ruta)
	print("ps=", ps)
	if ps:
		var n: Node = (ps as PackedScene).instantiate()
		print("instanciado ", n)
		get_root().add_child(n)
		print("hijos=", n.get_child_count())
		for h in n.get_children():
			print(" - ", h.name, " ", h.get_class())
	quit(0)
