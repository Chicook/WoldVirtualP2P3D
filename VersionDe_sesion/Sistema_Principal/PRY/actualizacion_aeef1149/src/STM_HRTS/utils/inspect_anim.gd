extends SceneTree
## Inspecciona las escenas importadas de los *_anim.glb: raíz, hijos con índice,
## alto real del esqueleto y animaciones. Sirve para generar los *Ch3D.tscn.

const CARPETA := "res://avtrnCRS/GTLF_GODOT/GltfIMP/AVATARES"


func _initialize() -> void:
	for ruta in _glbs(CARPETA):
		var escena: PackedScene = load(ruta)
		if escena == null:
			print("ERROR no carga ", ruta)
			continue
		var inst := escena.instantiate()
		get_root().add_child(inst)
		var hijos := []
		for i in inst.get_child_count():
			hijos.append("%d:%s(%s)" % [i, inst.get_child(i).name, inst.get_child(i).get_class()])
		var esqueleto: Skeleton3D = null
		var reproductor: AnimationPlayer = null
		var cola: Array[Node] = [inst]
		while not cola.is_empty():
			var n: Node = cola.pop_back()
			if n is Skeleton3D and esqueleto == null:
				esqueleto = n as Skeleton3D
			elif n is AnimationPlayer and reproductor == null:
				reproductor = n as AnimationPlayer
			cola.append_array(n.get_children())
		var minimo := Vector3.INF
		var maximo := -Vector3.INF
		if esqueleto:
			for i in esqueleto.get_bone_count():
				var p := esqueleto.global_transform * esqueleto.get_bone_global_pose(i).origin
				minimo = minimo.min(p)
				maximo = maximo.max(p)
		var clips := []
		if reproductor:
			clips = reproductor.get_animation_list()
		var indice_reproductor := -1
		if reproductor and reproductor.get_parent() == inst:
			indice_reproductor = reproductor.get_index()
		print("%s | raiz=%s | hijos=[%s] | alto=%.3f (%.3f..%.3f) | clips=%s | esqueleto=%s idxAP=%d" % [
			ruta.get_file(), inst.name, ", ".join(hijos),
			maximo.y - minimo.y, minimo.y, maximo.y, clips,
			esqueleto.name if esqueleto else "NO", indice_reproductor,
		])
		inst.queue_free()
	quit()


func _glbs(carpeta: String) -> Array[String]:
	var salida: Array[String] = []
	var dir := DirAccess.open(carpeta)
	if dir == null:
		return salida
	dir.list_dir_begin()
	var nombre := dir.get_next()
	while nombre != "":
		var ruta := carpeta.path_join(nombre)
		if dir.current_is_dir():
			if nombre != "." and nombre != "..":
				salida.append_array(_glbs(ruta))
		elif nombre.ends_with("_anim.glb"):
			salida.append(ruta)
		nombre = dir.get_next()
	dir.list_dir_end()
	return salida
