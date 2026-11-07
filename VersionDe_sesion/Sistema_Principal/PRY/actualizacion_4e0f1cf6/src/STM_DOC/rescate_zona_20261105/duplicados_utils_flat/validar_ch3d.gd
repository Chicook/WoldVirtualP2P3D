extends SceneTree
## Valida que cada *Ch3D.tscn carga, tiene esqueleto, los 5 clips y el
## AnimationTree con los parametros que espera AVMJ1Ch3D.gd.

const RUTAS := [
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH6Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH7Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH8Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH9Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH10Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH11Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH12Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ5Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ6Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ7Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ8Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ9Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ10Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ11Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ12Ch3D.tscn",
]
const CLIPS := ["caminarMJ1_2", "correrMJ1_3", "left_StrafeMJ1_4", "paradoMJ1_1", "rightstrafeMJ1_5"]
const BLEND := ["ANMJ", "Add2", "Blend2", "Blend2 2", "Blend2 3"]


func _initialize() -> void:
	_correr()


func _correr() -> void:
	# Sin este frame la raiz aun no esta en el arbol y add_child no dispara
	# _enter_tree, que es donde se montan los clips prestados.
	await process_frame
	var fallos := 0
	for ruta in RUTAS:
		var escena: PackedScene = load(ruta)
		if escena == null:
			print("FALLO carga ", ruta)
			fallos += 1
			continue
		var inst := escena.instantiate()
		# Los clips prestados y el AnimationPlayer se montan al entrar en escena.
		get_root().add_child(inst)
		var esqueleto: Skeleton3D = null
		var reproductor: AnimationPlayer = null
		var arbol: AnimationTree = null
		var cola: Array[Node] = [inst]
		while not cola.is_empty():
			var n: Node = cola.pop_back()
			if n is Skeleton3D and esqueleto == null:
				esqueleto = n
			elif n is AnimationPlayer and reproductor == null:
				reproductor = n
			elif n is AnimationTree and arbol == null:
				arbol = n
			cola.append_array(n.get_children())
		var problemas: Array[String] = []
		if esqueleto == null:
			problemas.append("sin esqueleto")
		if reproductor == null:
			problemas.append("sin AnimationPlayer")
		else:
			for clip in CLIPS:
				if not reproductor.has_animation(clip):
					problemas.append("falta clip " + clip)
		if arbol == null:
			problemas.append("sin AnimationTree")
		elif arbol.tree_root == null:
			problemas.append("AnimationTree sin arbol")
		var modelo := inst.get_node_or_null("CS3D" + inst.name.trim_suffix("Ch3D") + "/" + inst.name.trim_suffix("Ch3D"))
		var escala := 1.0
		if modelo:
			escala = modelo.scale.x
		print("%s | %s | escala=%.2f" % [
			"OK " if problemas.is_empty() else "FALLO ",
			ruta.get_file(), escala,
		] + ("" if problemas.is_empty() else " | " + ", ".join(problemas)))
		if not problemas.is_empty():
			fallos += 1
		inst.queue_free()
		await process_frame
	print("== %d escenas, %d con fallo ==" % [RUTAS.size(), fallos])
	quit(1 if fallos > 0 else 0)
