extends SceneTree
## Mide las shape keys sobre una malla real del catalogo (GLTF importado).
##
## Los GLB/GLTF del proyecto no traen morph targets, asi que las shape keys son
## deformacion analitica de vertices. Esta prueba lo comprueba en una malla real
## y exige desplazamientos visibles (>= 4 mm en un avatar de 1,75 m).
## Si el arbol no incluye los .gltf de avatar (el snapshot de fuentes no los
## lleva), la prueba se omite con exit 0.

const Pers = preload("res://gdscrip/Personalizacion.gd")
const RUTAS := [
	"res://gltfimport/avatares/AVH1.gltf",
	"res://gltfimport/avatares/AVMJ1.gltf",
]
const MINIMO_VISIBLE := 0.004

var _fallos := 0


func _initialize() -> void:
	await _correr()
	print("== fin, fallos=%d ==" % _fallos)
	quit(0 if _fallos == 0 else 1)


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK    ", texto)
	else:
		_fallos += 1
		print("FALLO ", texto)


func _correr() -> void:
	var ruta := ""
	for candidata in RUTAS:
		if ResourceLoader.exists(candidata):
			ruta = candidata
			break
	if ruta == "":
		print("OMITIDO: este arbol no trae los .gltf de avatar (gltfimport/avatares)")
		return
	await process_frame

	var avatar: Node = (load(ruta) as PackedScene).instantiate()
	root.add_child(avatar)
	await process_frame
	await process_frame

	_check(Pers._esqueleto(avatar) != null, "%s trae esqueleto" % ruta.get_file())
	_check(Pers._hueso(Pers._esqueleto(avatar), "Head") >= 0, "el esqueleto tiene hueso Head")
	_check(Pers._modelo(avatar) != null, "hay nodo modelo para escalar")

	var targets := 0
	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		targets += (nodo as MeshInstance3D).get_blend_shape_count()
	_check(targets == 0, "la malla no trae morph targets (%d): shape keys analiticas" % targets)

	Pers.aplicar(avatar, Pers.POR_DEFECTO)
	var base := _posiciones(avatar)
	_check(int(base["vertices"]) > 1000, "malla real con %d vertices" % int(base["vertices"]))

	var medido := {}
	for clave in Pers.EXPRESIONES:
		var d := Pers.POR_DEFECTO.duplicate()
		d[clave] = 1.0
		Pers.aplicar(avatar, d)
		var ahora := _posiciones(avatar)
		var maximo := _max_desplazamiento(base, ahora)
		var movidos := _cuenta_desplazados(base, ahora, 0.0005)
		medido[clave] = maximo
		_check(maximo >= MINIMO_VISIBLE,
			"%s mueve %.1f mm (%d vertices)" % [clave, maximo * 1000.0, movidos])

	# Dos expresiones seguidas y vuelta a la primera: sin deriva de anclajes.
	var primera := Pers.POR_DEFECTO.duplicate()
	primera["sonrisa"] = 1.0
	Pers.aplicar(avatar, primera)
	var con_sonrisa := _posiciones(avatar)
	var segunda := Pers.POR_DEFECTO.duplicate()
	segunda["enfado"] = 1.0
	Pers.aplicar(avatar, segunda)
	Pers.aplicar(avatar, primera)
	_check(_max_desplazamiento(con_sonrisa, _posiciones(avatar)) == 0.0,
		"volver a la misma expresion reproduce la malla")

	Pers.aplicar(avatar, Pers.POR_DEFECTO)
	_check(_max_desplazamiento(base, _posiciones(avatar)) == 0.0,
		"volver a cero restaura la malla original")

	var sum := 0.0
	for clave in medido:
		sum += float(medido[clave])
	print("RESUMEN media=%.1f mm max=%.1f mm" % [sum / maxf(medido.size(), 1) * 1000.0,
		_maximo_de(medido) * 1000.0])

	avatar.free()


func _maximo_de(d: Dictionary) -> float:
	var maximo := 0.0
	for clave in d:
		maximo = maxf(maximo, float(d[clave]))
	return maximo


## Copia de los vertices de cada superficie, sin depender de la instancia.
func _posiciones(avatar: Node) -> Dictionary:
	var d := {"vertices": 0, "mallas": {}}
	var por_malla := {}
	var total := 0
	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		if mi.mesh == null:
			continue
		var superficies := []
		for s in mi.mesh.get_surface_count():
			var arr: Array = mi.mesh.surface_get_arrays(s)
			var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			superficies.append(verts)
			total += verts.size()
		por_malla[str(avatar.get_path_to(mi))] = superficies
	d["vertices"] = total
	d["mallas"] = por_malla
	return d


func _max_desplazamiento(a: Dictionary, b: Dictionary) -> float:
	var maximo := 0.0
	var mallas_a: Dictionary = a["mallas"]
	var mallas_b: Dictionary = b["mallas"]
	for ruta in mallas_a:
		if not mallas_b.has(ruta):
			continue
		var sup_a: Array = mallas_a[ruta]
		var sup_b: Array = mallas_b[ruta]
		if sup_a.size() != sup_b.size():
			continue
		for s in sup_a.size():
			var va: PackedVector3Array = sup_a[s]
			var vb: PackedVector3Array = sup_b[s]
			if va.size() != vb.size():
				continue
			for v in va.size():
				maximo = maxf(maximo, va[v].distance_to(vb[v]))
	return maximo


func _cuenta_desplazados(a: Dictionary, b: Dictionary, umbral: float) -> int:
	var n := 0
	var mallas_a: Dictionary = a["mallas"]
	var mallas_b: Dictionary = b["mallas"]
	for ruta in mallas_a:
		if not mallas_b.has(ruta):
			continue
		var sup_a: Array = mallas_a[ruta]
		var sup_b: Array = mallas_b[ruta]
		if sup_a.size() != sup_b.size():
			continue
		for s in sup_a.size():
			var va: PackedVector3Array = sup_a[s]
			var vb: PackedVector3Array = sup_b[s]
			if va.size() != vb.size():
				continue
			for v in va.size():
				if va[v].distance_to(vb[v]) > umbral:
					n += 1
	return n
