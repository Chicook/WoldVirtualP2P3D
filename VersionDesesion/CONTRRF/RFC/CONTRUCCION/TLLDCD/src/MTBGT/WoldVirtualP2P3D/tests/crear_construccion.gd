extends SceneTree

func _init() -> void:
	var raiz := Node3D.new()
	raiz.name = "ConstruccionPrueba"
	var malla := MeshInstance3D.new()
	malla.name = "CuboPrueba"
	var caja := BoxMesh.new()
	caja.size = Vector3.ONE
	malla.mesh = caja
	raiz.add_child(malla)
	var escena := PackedScene.new()
	var err := escena.pack(raiz)
	print("pack=", err)
	err = ResourceSaver.save(escena, "user://isla_construida.tscn")
	print("save=", err)
	var f := FileAccess.open("user://construccion_lista.flag", FileAccess.WRITE)
	f.store_string("user://isla_construida.tscn")
	f.close()
	quit(0)
