extends SceneTree
## Diagnóstico de avatares: carga los glTF y las escenas jugables del carrusel.

const GLTFS := [
	"res://gltfimport/avatares/AVH1.gltf",
	"res://gltfimport/avatares/AVMJ1.gltf",
	"res://gltfimport/avatares/AVH2.gltf",
	"res://gltfimport/avatares/AVMJ2.gltf",
	"res://gltfimport/avatares/AVH3.gltf",
	"res://gltfimport/avatares/AVMJ3.gltf",
	"res://gltfimport/avatares/AVH4.gltf",
	"res://gltfimport/avatares/AVMJ4.gltf",
]

const ESCENAS := [
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH1Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ1Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH2Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ2Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH3Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ3Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH4Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ4Ch3D.tscn",
]

func _init() -> void:
	print("=== TEST AVATARES ===")
	var ok := 0
	for i in GLTFS.size():
		var ruta: String = GLTFS[i]
		var t0 := Time.get_ticks_msec()
		if not ResourceLoader.exists(ruta):
			print("[FALTA] ", ruta)
			continue
		var ps := load(ruta)
		if ps == null:
			print("[ERROR load] ", ruta)
			continue
		var nodo: Node = (ps as PackedScene).instantiate()
		get_root().add_child(nodo)
		var mallas := _contar(nodo, "MeshInstance3D")
		var esqueletos := _contar(nodo, "Skeleton3D")
		var players := _contar(nodo, "AnimationPlayer")
		var anims: Array = []
		for p in _buscar(nodo, "AnimationPlayer"):
			anims.append_array((p as AnimationPlayer).get_animation_list())
		print("[GLTF %d] %s mallas=%d esqueletos=%d anims=%s (%d ms)" % [
			i, ruta.get_file(), mallas, esqueletos, str(anims), Time.get_ticks_msec() - t0])
		nodo.queue_free()
		ok += 1

	for i in ESCENAS.size():
		var ruta: String = ESCENAS[i]
		if not ResourceLoader.exists(ruta):
			print("[FALTA ESCENA] ", ruta)
			continue
		var ps := load(ruta)
		if ps == null:
			print("[ERROR load ESCENA] ", ruta)
			continue
		var nodo: Node = (ps as PackedScene).instantiate()
		get_root().add_child(nodo)
		var players := _buscar(nodo, "AnimationPlayer")
		var anims: Array = []
		for p in players:
			anims = (p as AnimationPlayer).get_animation_list()
		print("[ESCENA %d] %s anims=%s" % [i, ruta.get_file(), str(anims)])
		nodo.queue_free()
		ok += 1

	print("=== AVATARES OK: %d ===" % ok)
	quit(0 if ok == GLTFS.size() + ESCENAS.size() else 1)


func _buscar(n: Node, clase: String) -> Array:
	var out: Array = []
	if n.is_class(clase):
		out.append(n)
	for h in n.get_children():
		out.append_array(_buscar(h, clase))
	return out


func _contar(n: Node, clase: String) -> int:
	return _buscar(n, clase).size()
