extends RefCounted
## Terreno editable de una isla: deforma la malla importada (ISLA3DCHUNK),
## recalcula normales y mantiene sincronizada la colisión trimesh.
##
## La malla original se hornea una vez por isla (morph targets incluidos) y se
## sustituye en ese MeshInstance3D, de modo que editar una isla no altera las
## demás. La colisión también se duplica para no compartir el recurso.

const MAGIA := "WVPT"
const VERSION := 1
## Alturas locales (la malla mide 2x1x2 con escala ~99.92 -> 1 unidad = ~100 m).
const ALTURA_MIN := 0.0
const ALTURA_MAX := 0.95

var indice := -1
var isla: Node3D = null
var malla: MeshInstance3D = null
var cuerpo: StaticBody3D = null
var forma: ConcavePolygonShape3D = null
var material: Material = null
var escala := 1.0

var vertices := PackedVector3Array()
var vertices_base := PackedVector3Array()
var normales := PackedVector3Array()
var tangentes := PackedFloat32Array()
var uvs := PackedVector2Array()
var uv2s := PackedVector2Array()
var indices := PackedInt32Array()

var _vecinos: Array = []
var _hash_base := 0
var _malla_actual: ArrayMesh = null


func configurar(nodo_isla: Node3D, idx: int) -> bool:
	if nodo_isla == null:
		return false
	isla = nodo_isla
	indice = idx
	malla = isla.get_node_or_null("isla3D") as MeshInstance3D
	if malla == null or malla.mesh == null:
		push_warning("[Terreno] Isla %d sin malla isla3D" % idx)
		return false

	# El horneado descarta el material de superficie: hay que leerlo antes.
	var malla_original := malla.mesh
	material = malla.get_surface_override_material(0)
	if material == null:
		material = malla.material_override
	if material == null and malla_original != null:
		material = malla_original.surface_get_material(0)

	# Horneado único: convierte el morph en geometría real y deja una malla
	# propia de esta isla (malla.mesh deja de compartirse entre duplicados).
	var horneada := malla.bake_mesh_from_current_blend_shape_mix()
	if horneada == null:
		push_warning("[Terreno] No se pudo hornear la malla de la isla %d" % idx)
		return false
	malla.mesh = horneada
	var anim := isla.get_node_or_null("AnimationPlayer") as AnimationPlayer
	if anim != null:
		anim.stop()
		anim.active = false

	var arrays := horneada.surface_get_arrays(0)
	vertices = arrays[Mesh.ARRAY_VERTEX]
	normales = arrays[Mesh.ARRAY_NORMAL]
	indices = arrays[Mesh.ARRAY_INDEX]
	var uv_raw = arrays[Mesh.ARRAY_TEX_UV]
	uvs = uv_raw if uv_raw is PackedVector2Array else PackedVector2Array()
	var uv2_raw = arrays[Mesh.ARRAY_TEX_UV2]
	uv2s = uv2_raw if uv2_raw is PackedVector2Array else PackedVector2Array()
	var tan_raw = arrays[Mesh.ARRAY_TANGENT]
	tangentes = tan_raw if tan_raw is PackedFloat32Array else PackedFloat32Array()
	vertices_base = vertices.duplicate()
	_hash_base = hash(vertices_base)

	cuerpo = malla.get_node_or_null("StaticBody3D") as StaticBody3D
	var colision := cuerpo.get_node_or_null("CollisionShape3D") as CollisionShape3D if cuerpo != null else null
	if colision != null and colision.shape is ConcavePolygonShape3D:
		forma = (colision.shape as ConcavePolygonShape3D).duplicate() as ConcavePolygonShape3D
		colision.shape = forma

	var s := malla.global_transform.basis.get_scale()
	escala = maxf(0.001, (absf(s.x) + absf(s.y) + absf(s.z)) / 3.0)
	_construir_vecinos()
	_reconstruir_malla()
	return true


## Aplica un paso de pincel. `centro_mundo` viene del raycast, `radio_m` y
## `fuerza_m` en metros. Devuelve cuántos vértices cambiaron.
func aplicar_pincel(centro_mundo: Vector3, radio_m: float, fuerza_m: float,
		dt: float, herramienta: int) -> int:
	if malla == null or vertices.is_empty():
		return 0
	var centro := malla.to_local(centro_mundo)
	var radio_local := maxf(radio_m, 0.5) / maxf(escala, 0.001)
	var r2 := radio_local * radio_local
	var paso := clampf(fuerza_m * dt / maxf(escala, 0.001), -0.02, 0.02)
	if herramienta == 2: # suavizar
		paso = clampf(absf(fuerza_m) * dt * 0.5, 0.0, 0.35)
	var afectados: Array[int] = []
	for i in vertices.size():
		var v := vertices[i]
		var dx := v.x - centro.x
		var dz := v.z - centro.z
		var d2 := dx * dx + dz * dz
		if d2 > r2:
			continue
		var caida := 1.0 - sqrt(d2 / r2)
		caida = caida * caida * (3.0 - 2.0 * caida) # smoothstep
		match herramienta:
			0: # subir
				v.y = minf(ALTURA_MAX, v.y + paso * caida)
			1: # bajar
				v.y = maxf(ALTURA_MIN, v.y - paso * caida)
			2: # suavizar
				var promedio := _promedio_vecinos(i)
				v.y = lerpf(v.y, promedio, clampf(paso * caida, 0.0, 0.5))
			3: # aplanar hacia la altura del impacto
				var delta := clampf(paso * caida * 2.0, -0.05, 0.05)
				v.y = move_toward(v.y, clampf(centro.y, ALTURA_MIN, ALTURA_MAX), absf(delta))
			_:
				continue
		vertices[i] = v
		afectados.append(i)
	if afectados.is_empty():
		return 0
	_recalcular_normales()
	_reconstruir_malla()
	return afectados.size()


## Recalcula la colisión trimesh. Es la operación más pesada: llamarla al
## soltar el pincel o como mucho cada ~200 ms durante el trazo.
func actualizar_colision() -> void:
	if forma == null or indices.is_empty():
		return
	var caras := PackedVector3Array()
	caras.resize(indices.size())
	for i in indices.size():
		caras[i] = vertices[indices[i]]
	forma.set_faces(caras)


## Blob binario (cabecera + alturas float32) para disco y para el túnel.
func serializar() -> PackedByteArray:
	var datos := PackedByteArray()
	var total := 4 + 2 + 4 + 8 + vertices.size() * 4
	datos.resize(total)
	var off := 0
	var magia := MAGIA.to_utf8_buffer()
	for b in magia:
		datos[off] = b
		off += 1
	datos.encode_u16(off, VERSION)
	off += 2
	datos.encode_u32(off, vertices.size())
	off += 4
	datos.encode_s64(off, _hash_base)
	off += 8
	for i in vertices.size():
		datos.encode_float(off, vertices[i].y)
		off += 4
	return datos


## Carga un blob. Devuelve false si la geometría base no coincide (el mundo
## cambió de versión y las alturas guardadas ya no se pueden aplicar).
func cargar(datos: PackedByteArray) -> bool:
	if datos.size() < 18 or vertices.is_empty():
		return false
	var off := 0
	var magia := datos.slice(0, 4).get_string_from_utf8()
	off += 4
	if magia != MAGIA:
		return false
	var version := datos.decode_u16(off)
	off += 2
	if version != VERSION:
		return false
	var cuenta := datos.decode_u32(off)
	off += 4
	if cuenta != vertices.size() or datos.size() < 18 + cuenta * 4:
		return false
	var hash_guardado := datos.decode_s64(off)
	off += 8
	if hash_guardado != _hash_base:
		push_warning("[Terreno] Geometría base distinta en isla %d; se descartan alturas" % indice)
		return false
	for i in cuenta:
		var v := vertices[i]
		v.y = clampf(datos.decode_float(off), ALTURA_MIN, ALTURA_MAX)
		off += 4
		vertices[i] = v
	_recalcular_normales()
	_reconstruir_malla()
	actualizar_colision()
	return true


func altura_en(punto_mundo: Vector3) -> float:
	if malla == null:
		return 0.0
	return malla.to_local(punto_mundo).y * escala


func _promedio_vecinos(i: int) -> float:
	if i < 0 or i >= _vecinos.size():
		return vertices[i].y if i < vertices.size() else 0.0
	var lista: PackedInt32Array = _vecinos[i]
	if lista.is_empty():
		return vertices[i].y
	var suma := 0.0
	for j in lista:
		suma += vertices[j].y
	return suma / float(lista.size())


func _recalcular_normales() -> void:
	var acum := PackedVector3Array()
	acum.resize(vertices.size())
	for t in range(0, indices.size(), 3):
		var ia := indices[t]
		var ib := indices[t + 1]
		var ic := indices[t + 2]
		var a := vertices[ia]
		var b := vertices[ib]
		var c := vertices[ic]
		# Winding original: el acumulado (b-a)x(c-a) sale invertido.
		var cara := (a - b).cross(c - a)
		acum[ia] += cara
		acum[ib] += cara
		acum[ic] += cara
	for i in acum.size():
		if acum[i].length_squared() > 1e-20:
			normales[i] = acum[i].normalized()


func _reconstruir_malla() -> void:
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normales
	if tangentes.size() == vertices.size() * 4:
		arrays[Mesh.ARRAY_TANGENT] = tangentes
	if uvs.size() == vertices.size():
		arrays[Mesh.ARRAY_TEX_UV] = uvs
	if uv2s.size() == vertices.size():
		arrays[Mesh.ARRAY_TEX_UV2] = uv2s
	arrays[Mesh.ARRAY_INDEX] = indices
	var nueva := ArrayMesh.new()
	nueva.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	if material != null:
		nueva.surface_set_material(0, material)
	_malla_actual = nueva
	malla.mesh = nueva


func _construir_vecinos() -> void:
	var listas: Array = []
	listas.resize(vertices.size())
	for i in listas.size():
		listas[i] = PackedInt32Array()
	var vistos := {}
	for t in range(0, indices.size(), 3):
		_agregar_arista(listas, vistos, indices[t], indices[t + 1])
		_agregar_arista(listas, vistos, indices[t + 1], indices[t + 2])
		_agregar_arista(listas, vistos, indices[t + 2], indices[t])
	_vecinos = listas


func _agregar_arista(listas: Array, vistos: Dictionary, a: int, b: int) -> void:
	if a == b:
		return
	var clave := mini(a, b) * 100000 + maxi(a, b)
	if vistos.has(clave):
		return
	vistos[clave] = true
	var la: PackedInt32Array = listas[a]
	la.append(b)
	listas[a] = la
	var lb: PackedInt32Array = listas[b]
	lb.append(a)
	listas[b] = lb
