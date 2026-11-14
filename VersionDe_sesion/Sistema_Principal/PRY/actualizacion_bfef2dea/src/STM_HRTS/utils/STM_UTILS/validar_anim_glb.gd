extends SceneTree
## Comprueba con el cargador real de Godot que los *_anim.glb generados abren y
## que cada uno trae las 5 animaciones esperadas sobre un esqueleto con 65 huesos.
## Uso: python -m STM_HRTS ejecutar validar_anim_glb

const ESPERADAS := ["paradoMJ1_1", "caminarMJ1_2", "correrMJ1_3", "left_StrafeMJ1_4", "rightstrafeMJ1_5"]
const PATRON := "res://avtrnCRS/GTLF_GODOT/GltfIMP/AVATARES"


func _initialize() -> void:
	var fallos := 0
	var total := 0
	for ruta in _glbs(PATRON):
		total += 1
		fallos += _probar(ruta)
	print("== %d modelos, %d con fallo ==" % [total, fallos])
	quit(1 if fallos > 0 else 0)


func _glbs(carpeta: String) -> PackedStringArray:
	var salida := PackedStringArray()
	var pendientes := [carpeta]
	while not pendientes.is_empty():
		var actual: String = pendientes.pop_back()
		var dir := DirAccess.open(actual)
		if dir == null:
			continue
		dir.list_dir_begin()
		var nombre := dir.get_next()
		while nombre != "":
			var ruta := actual.path_join(nombre)
			if dir.current_is_dir():
				pendientes.append(ruta)
			elif nombre.ends_with("_anim.glb"):
				salida.append(ruta)
			nombre = dir.get_next()
		dir.list_dir_end()
	return salida


func _probar(ruta: String) -> int:
	var doc := GLTFDocument.new()
	var estado := GLTFState.new()
	var error := doc.append_from_file(ruta, estado)
	if error != OK:
		print("FALLO %s no se pudo leer (%s)" % [ruta.get_file(), error_string(error)])
		return 1
	var escena := doc.generate_scene(estado)
	if escena == null:
		print("FALLO %s no generó escena" % ruta.get_file())
		return 1

	var nombres: Array[String] = []
	var huesos := 0
	var cola: Array[Node] = [escena]
	while not cola.is_empty():
		var nodo: Node = cola.pop_back()
		if nodo is Skeleton3D:
			huesos = maxi(huesos, (nodo as Skeleton3D).get_bone_count())
		if nodo is AnimationPlayer:
			nombres.append_array((nodo as AnimationPlayer).get_animation_list())
		cola.append_array(nodo.get_children())
	escena.free()

	var faltan: Array[String] = []
	for esperada in ESPERADAS:
		if not nombres.has(esperada):
			faltan.append(esperada)
	var estado_txt := "OK" if faltan.is_empty() and huesos >= 60 else "FALLO"
	print("%s %-18s huesos=%d clips=%d %s" % [estado_txt, ruta.get_file(), huesos, nombres.size(),
		"" if faltan.is_empty() else "faltan: " + ", ".join(faltan)])
	return 0 if estado_txt == "OK" else 1
