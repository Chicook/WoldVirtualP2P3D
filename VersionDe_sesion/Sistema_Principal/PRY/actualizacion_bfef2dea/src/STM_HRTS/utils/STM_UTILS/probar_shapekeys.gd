extends SceneTree
## Prueba los shape keys por codigo sin depender de los GLB (que no estan en
## este arbol): construye una cabeza sintetica con esqueleto y comprueba que
## cada expresion mueve vertices, que las amplitudes son proporcionales al peso
## y que volver a cero restaura la malla original. Tambien valida el mapa de
## presets VRM del adaptador ShapeKeys y la persistencia en registro.cfg.

const Pers = preload("res://gdscrip/Personalizacion.gd")
const ShapeKeys = preload("res://gdscrip/ShapeKeys.gd")

var _fallos := 0
var _i_boca_izq := -1
var _i_boca_der := -1
var _i_nuca := -1
var _i_pestana := -1


func _initialize() -> void:
	_correr()


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK    ", texto)
	else:
		print("FALLO ", texto)
		_fallos += 1


func _correr() -> void:
	await process_frame
	_probar_mapa_vrm()
	await _probar_deformacion()
	_probar_persistencia()
	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)


# ---------------------------------------------------------------------------
# Adaptador de presets VRM
# ---------------------------------------------------------------------------

func _probar_mapa_vrm() -> void:
	_check(ShapeKeys.PRESETS.size() == 11, "catalogo de 11 presets VRM")
	_check(ShapeKeys.normalizar({"joy": 2.0})["joy"] == 1.0, "normalizar recorta a 1")
	_check(ShapeKeys.normalizar({"joy": -1.0})["joy"] == 0.0, "normalizar recorta a 0")

	var exp := ShapeKeys.a_expresiones({"joy": 1.0, "a": 0.6, "o": 0.3})
	_check(exp["sonrisa"] == 1.0, "joy -> sonrisa")
	_check(absf(exp["boca_abierta"] - 0.6) < 0.001, "a/o comparten boca abierta y gana el mayor")
	var vocales := ShapeKeys.a_expresiones({"i": 0.4, "e": 0.8, "u": 0.1})
	_check(absf(vocales["boca_ancha"] - 0.8) < 0.001, "i/e/u comparten boca ancha")

	var datos := Pers.POR_DEFECTO.duplicate()
	datos["camiseta"] = Color("c62828")
	var fusion := ShapeKeys.fusionar(datos, {"blink": 1.0})
	_check(fusion["camiseta"].is_equal_approx(Color("c62828")), "fusionar conserva los tintes")
	_check(fusion["parpadeo"] == 1.0, "fusionar aplica el parpadeo")

	_check(not ShapeKeys.nombre("joy").is_empty(), "cada preset tiene etiqueta")


# ---------------------------------------------------------------------------
# Deformacion real sobre una cabeza sintetica
# ---------------------------------------------------------------------------

func _probar_deformacion() -> void:
	var avatar := _crear_avatar()
	var cuerpo: MeshInstance3D = avatar.get_node("Cuerpo")
	var pestanas: MeshInstance3D = avatar.get_node("Eyelashes")
	var base: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
	var base_pestanas: PackedVector3Array = (pestanas.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]

	Pers.aplicar(avatar, Pers.POR_DEFECTO)
	_check(cuerpo.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX] == base,
		"sin expresiones la malla no se toca")

	# Sonrisa: la comisura sube y avanza; la nuca no se mueve.
	var d := Pers.POR_DEFECTO.duplicate()
	d["sonrisa"] = 1.0
	Pers.aplicar(avatar, d)
	var movida: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
	_check(movida != base, "la sonrisa reconstruye la malla")
	var dy_izq := movida[_i_boca_izq].y - base[_i_boca_izq].y
	_check(dy_izq > 0.002, "la comisura izquierda sube con la sonrisa (%.4f m)" % dy_izq)
	_check(movida[_i_boca_der].y - base[_i_boca_der].y > 0.002, "la comisura derecha sube")
	_check(movida[_i_boca_izq].z > base[_i_boca_izq].z, "la comisura avanza hacia delante")
	_check(movida[_i_nuca].is_equal_approx(base[_i_nuca]), "la nuca no se deforma")

	# Peso 0.5: mismo signo, menor amplitud.
	var medio := Pers.POR_DEFECTO.duplicate()
	medio["sonrisa"] = 0.5
	Pers.aplicar(avatar, medio)
	var a_medias: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
	var dy_medio := a_medias[_i_boca_izq].y - base[_i_boca_izq].y
	_check(dy_medio > 0.0 and dy_medio < dy_izq, "el peso 0.5 mueve la mitad")

	# Cada expresion debe mover al menos un vertice (shape key visible).
	for clave in Pers.EXPRESIONES:
		var e := Pers.POR_DEFECTO.duplicate()
		e[clave] = 1.0
		Pers.aplicar(avatar, e)
		var malla: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
		_check(_movidos(base, malla) > 0, "%s deforma la malla" % clave)
		if clave == "parpadeo":
			var p: PackedVector3Array = (pestanas.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
			_check(_movidos(base_pestanas, p) > 0, "el parpadeo cierra las pestanas")

	# La boca abierta baja el labio inferior y la ancha ensancha la boca.
	var abierta := Pers.POR_DEFECTO.duplicate()
	abierta["boca_abierta"] = 1.0
	Pers.aplicar(avatar, abierta)
	var m_abierta: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
	_check(m_abierta[_i_boca_izq].y < base[_i_boca_izq].y, "boca abierta baja el labio inferior")

	var ancha := Pers.POR_DEFECTO.duplicate()
	ancha["boca_ancha"] = 1.0
	Pers.aplicar(avatar, ancha)
	var m_ancha: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
	_check(absf(m_ancha[_i_boca_izq].x) > absf(base[_i_boca_izq].x), "boca ancha separa las comisuras")

	# Cambiar de expresion y volver a la anterior no debe derivar los anclajes
	# (la geometria de referencia se mide siempre sobre la malla sin deformar).
	var otra := Pers.POR_DEFECTO.duplicate()
	otra["enfado"] = 1.0
	Pers.aplicar(avatar, otra)
	Pers.aplicar(avatar, d)
	var repetida: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
	_check(repetida == movida, "volver a la misma expresion da la misma deformacion")

	# Volver a neutro restaura exactamente la malla original.
	Pers.aplicar(avatar, Pers.POR_DEFECTO)
	var restaurada: PackedVector3Array = (cuerpo.mesh.surface_get_arrays(0) as Array)[Mesh.ARRAY_VERTEX]
	_check(restaurada == base, "volver a cero restaura la malla original")

	avatar.free()


func _movidos(a: PackedVector3Array, b: PackedVector3Array) -> int:
	if a.size() != b.size():
		return 0
	var n := 0
	for i in a.size():
		if not a[i].is_equal_approx(b[i]):
			n += 1
	return n


# ---------------------------------------------------------------------------
# Avatar sintetico (cabeza + esqueleto + pestanas + cuerpo)
# ---------------------------------------------------------------------------

func _crear_avatar() -> Node3D:
	var avatar := Node3D.new()
	avatar.name = "AvatarPrueba"

	var sk := Skeleton3D.new()
	sk.name = "Skeleton3D"
	avatar.add_child(sk)
	sk.add_bone("mixamorig_Head")
	sk.add_bone("mixamorig_HeadTop_End")
	sk.set_bone_parent(1, 0)
	sk.set_bone_rest(0, Transform3D(Basis(), Vector3(0.0, 1.5, 0.0)))
	sk.set_bone_rest(1, Transform3D(Basis(), Vector3(0.0, 0.25, 0.0)))

	var verts: Array = []
	var huesos := PackedInt32Array()
	var pesos := PackedFloat32Array()

	# Esquinas de la cabeza: fijan la caja (0.16 m de ancho, 0.25 m de alto).
	for x in [-0.08, 0.08]:
		for y in [1.5, 1.75]:
			for z in [-0.07, 0.07]:
				_vertice(verts, huesos, pesos, Vector3(x, y, z), true)
	_i_boca_izq = _vertice(verts, huesos, pesos, Vector3(-0.018, 1.5675, 0.069), true)
	_i_boca_der = _vertice(verts, huesos, pesos, Vector3(0.018, 1.5675, 0.069), true)
	_vertice(verts, huesos, pesos, Vector3(0.0, 1.5675, 0.07), true)
	_vertice(verts, huesos, pesos, Vector3(0.0, 1.595, 0.08), true)
	_vertice(verts, huesos, pesos, Vector3(-0.078, 1.63, 0.0), true)
	_vertice(verts, huesos, pesos, Vector3(0.078, 1.63, 0.0), true)
	_vertice(verts, huesos, pesos, Vector3(-0.05, 1.63, 0.05), true)
	_vertice(verts, huesos, pesos, Vector3(0.05, 1.63, 0.05), true)
	_i_nuca = _vertice(verts, huesos, pesos, Vector3(0.0, 1.6, -0.07), true)

	# Cuerpo minimo para que la malla no sea solo cabeza.
	_vertice(verts, huesos, pesos, Vector3(0.0, 1.3, 0.0), false)
	_vertice(verts, huesos, pesos, Vector3(-0.12, 1.25, 0.0), false)
	_vertice(verts, huesos, pesos, Vector3(0.12, 1.25, 0.0), false)
	_vertice(verts, huesos, pesos, Vector3(0.0, 1.0, 0.0), false)

	var indices := PackedInt32Array([0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7])
	var cuerpo := MeshInstance3D.new()
	cuerpo.name = "Cuerpo"
	cuerpo.mesh = _malla(verts, huesos, pesos, indices)
	avatar.add_child(cuerpo)

	var pv: Array = []
	var ph := PackedInt32Array()
	var pp := PackedFloat32Array()
	_i_pestana = _vertice(pv, ph, pp, Vector3(0.05, 1.645, 0.045), false)
	_vertice(pv, ph, pp, Vector3(0.05, 1.615, 0.045), false)
	_vertice(pv, ph, pp, Vector3(-0.05, 1.645, 0.045), false)
	_vertice(pv, ph, pp, Vector3(-0.05, 1.615, 0.045), false)
	var pestanas := MeshInstance3D.new()
	pestanas.name = "Eyelashes"
	pestanas.mesh = _malla(pv, ph, pp, PackedInt32Array([0, 1, 2, 1, 3, 2]))
	avatar.add_child(pestanas)

	return avatar


func _vertice(verts: Array, huesos: PackedInt32Array, pesos: PackedFloat32Array,
		p: Vector3, cabeza: bool) -> int:
	verts.append(p)
	huesos.append(0)
	huesos.append(0)
	huesos.append(0)
	huesos.append(0)
	pesos.append(1.0 if cabeza else 0.0)
	pesos.append(0.0)
	pesos.append(0.0)
	pesos.append(0.0)
	return verts.size() - 1


func _malla(verts: Array, huesos: PackedInt32Array, pesos: PackedFloat32Array,
		indices: PackedInt32Array) -> ArrayMesh:
	var normales := PackedVector3Array()
	var uvs := PackedVector2Array()
	for v in verts:
		normales.append(Vector3.UP)
		uvs.append(Vector2(v.x, v.y))
	var arreglos := []
	arreglos.resize(Mesh.ARRAY_MAX)
	arreglos[Mesh.ARRAY_VERTEX] = PackedVector3Array(verts)
	arreglos[Mesh.ARRAY_NORMAL] = normales
	arreglos[Mesh.ARRAY_TEX_UV] = uvs
	arreglos[Mesh.ARRAY_BONES] = huesos
	arreglos[Mesh.ARRAY_WEIGHTS] = pesos
	arreglos[Mesh.ARRAY_INDEX] = indices
	var malla := ArrayMesh.new()
	malla.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arreglos)
	return malla


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

func _probar_persistencia() -> void:
	var datos := Pers.POR_DEFECTO.duplicate()
	datos["sonrisa"] = 0.75
	datos["boca_abierta"] = 0.5
	Pers.guardar(datos)
	var leido := Pers.leer()
	_check(absf(float(leido["sonrisa"]) - 0.75) < 0.001, "guardar/leer conserva la sonrisa")
	_check(absf(float(leido["boca_abierta"]) - 0.5) < 0.001, "guardar/leer conserva la boca abierta")

	var texto := Pers.codificar(datos)
	var vuelta := Pers.decodificar(texto)
	_check(absf(float(vuelta["sonrisa"]) - 0.75) < 0.001, "codificar/decodificar conserva la sonrisa")
	_check(absf(float(vuelta["boca_ancha"])) < 0.001, "codificar/decodificar rellena el resto a cero")

	# Dejar el cfg neutro para no contaminar otras pruebas del mismo APPDATA.
	Pers.guardar(Pers.POR_DEFECTO)
