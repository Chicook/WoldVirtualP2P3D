extends SceneTree
## Prueba de recuperación de avatares: carga las 24 plazas del carrusel y
## verifica que cada una instancia con mallas reales (MeshInstance3D).

func _init() -> void:
	var turnos := load("res://gdscrip/Turnos.gd")
	var rutas: Array = turnos.AVATARES
	var fallos := 0
	for i in rutas.size():
		var ps := load(rutas[i]) as PackedScene
		if ps == null:
			print("[FALLO] ", turnos.NOMBRES[i], " no carga: ", rutas[i])
			fallos += 1
			continue
		var nodo := ps.instantiate()
		var mallas := nodo.find_children("*", "MeshInstance3D", true, false)
		if mallas.is_empty():
			print("[FALLO] ", turnos.NOMBRES[i], " sin MeshInstance3D")
			fallos += 1
		else:
			print("[OK] ", turnos.NOMBRES[i], " mallas=", mallas.size())
		nodo.free()
	# glb sueltos restaurados (turnos 3 y 4 del carrusel)
	var base := "res://AreaDeTrabajo/GTLF_GODOT/GltfIMP/AVATARES/"
	var glbs := [
		"AVHM/AVmj1.glb", "AVHM/AVmj2.glb", "AVHM/AVmj3.glb", "AVHM/AVmj4.glb",
		"AVHM/AVmj5.glb", "AVHM/AVmj6.glb", "AVHM/AVmj7.glb",
		"AVMJ/avhm1.glb", "AVMJ/avhm2.glb", "AVMJ/avhm3.glb", "AVMJ/avhm4.glb",
		"AVMJ/avhm5.glb", "AVMJ/avhm6.glb", "AVMJ/avhm7.glb", "AVMJ/avhm8.glb", "AVMJ/avhm9.glb",
	]
	for g in glbs:
		var ps := load(base + g) as PackedScene
		if ps == null:
			print("[FALLO] glb no carga: ", g)
			fallos += 1
			continue
		var nodo := ps.instantiate()
		var mallas := nodo.find_children("*", "MeshInstance3D", true, false)
		if mallas.is_empty():
			print("[FALLO] glb sin mallas: ", g)
			fallos += 1
		else:
			print("[OK] glb ", g, " mallas=", mallas.size())
		nodo.free()
	print("RESULTADO: ", 40 - fallos, "/40 fallos=", fallos)
	quit(1 if fallos > 0 else 0)