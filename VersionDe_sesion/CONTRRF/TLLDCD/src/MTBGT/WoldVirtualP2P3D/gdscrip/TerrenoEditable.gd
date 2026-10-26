extends RefCounted
## Terreno editable de una isla: deforma la malla importada (ISLA3DCHUNK),
## recalcula normales y mantiene sincronizada la colisión trimesh.
##
## La malla original se hornea una vez por isla (morph targets incluidos) y se
## sustituye en ese MeshInstance3D, de modo que editar una isla no altera las
## demás. La colisión también se duplica para no compartir el recurso.

const MAGIA := "WVPT"
## v1: solo alturas. v2: alturas + color RGBA8 por vértice (arena de playa).
const VERSION := 2
## Alturas locales (la malla mide 2x1x2 con escala ~99.92 -> 1 unidad = ~100 m).
const ALTURA_MIN := 0.0
const ALTURA_MAX := 0.95

## Índices de herramienta que viajan en el pincel (Parámetro `herramienta`).
const SUBIR := 0
const BAJAR := 1
const SUAVIZAR := 2
const APLANAR := 3
## Desplaza el montículo en la dirección del arrastre (advección de alturas).
const MOVER := 4
## Aplana hacia ~1 m sobre el agua y tiñe de arena.
const PLAYA := 5

## Nivel del agua en la escena de isla (malla local). Se detecta del nodo
## Oceano; si no existe (glTF suelto en pruebas) se usa el valor del mundo.
const NIVEL_AGUA_DEFECTO := 0.4897
const MARGEN_PLAYA_M := 1.0
## COLOR.a funciona como máscara de superposición en TERRENO_EDITABLE: 0 deja
## la textura original, 1 pinta el color del vértice (arena). Es albedo lineal
## (~#8A7550 en sRGB); con la luz de la isla (cielo + sol) el valor final ronda
## #E4CD99, así que no se sube o la playa se quema a blanco.
const COLOR_PLAYA := Color(0.24, 0.17, 0.09, 1.0)
## Mismo RGB que la arena y alfa 0: al interpolar solo cambia la máscara, sin el
## halo claro que aparece si el color sin arena fuese blanco.
const COLOR_SIN_ARENA := Color(COLOR_PLAYA.r, COLOR_PLAYA.g, COLOR_PLAYA.b, 0.0)

var indice := -1
var isla: Node3D = null
var malla: MeshInstance3D = null
var cuerpo: StaticBody3D = null
var forma: ConcavePolygonShape3D = null
var material: Material = null
var escala := 1.0
var nivel_agua := NIVEL_AGUA_DEFECTO

var vertices := PackedVector3Array()
var vertices_base := PackedVector3Array()
var normales := PackedVector3Array()
var tangentes := PackedFloat32Array()
var uvs := PackedVector2Array()
var uv2s := PackedVector2Array()
var indices := PackedInt32Array()
var colores := PackedColorArray()

var _vecinos: Array = []
var _hash_base := 0
var _espaciado := 0.02
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

	# Copia propia de los arrays: editar una isla no debe poder tocar la malla
	# horneada que sirve de base a esta misma isla en futuros reinicios.
	var arrays := horneada.surface_get_arrays(0)
	vertices = (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).duplicate()
	normales = (arrays[Mesh.ARRAY_NORMAL] as PackedVector3Array).duplicate()
	indices = (arrays[Mesh.ARRAY_INDEX] as PackedInt32Array).duplicate()
	var uv_raw = arrays[Mesh.ARRAY_TEX_UV]
	uvs = uv_raw.duplicate() if uv_raw is PackedVector2Array else PackedVector2Array()
	var uv2_raw = arrays[Mesh.ARRAY_TEX_UV2]
	uv2s = uv2_raw.duplicate() if uv2_raw is PackedVector2Array else PackedVector2Array()
	var tan_raw = arrays[Mesh.ARRAY_TANGENT]
	tangentes = tan_raw.duplicate() if tan_raw is PackedFloat32Array else PackedFloat32Array()
	var col_raw = arrays[Mesh.ARRAY_COLOR]
	if col_raw is PackedColorArray and col_raw.size() == vertices.size():
		colores = col_raw.duplicate()
	else:
		colores = PackedColorArray()
		colores.resize(vertices.size())
		colores.fill(COLOR_SIN_ARENA)
	vertices_base = vertices.duplicate()
	_hash_base = hash(vertices_base)

	# TERRENO_EDITABLE conserva la textura original y superpone el color por
	# vértice (arena). Se clona por isla para no alterar el recurso compartido.
	var original := material as BaseMaterial3D
	if original != null:
		var shader_mat := ShaderMaterial.new()
		shader_mat.shader = preload("res://gdshader/TERRENO_EDITABLE.gdshader")
		if original.albedo_texture != null:
			shader_mat.set_shader_parameter("albedo_tex", original.albedo_texture)
		shader_mat.set_shader_parameter("roughness_val", original.roughness)
		shader_mat.set_shader_parameter("metallic_val", original.metallic)
		material = shader_mat

	cuerpo = malla.get_node_or_null("StaticBody3D") as StaticBody3D
	var colision := cuerpo.get_node_or_null("CollisionShape3D") as CollisionShape3D if cuerpo != null else null
	if colision != null and colision.shape is ConcavePolygonShape3D:
		forma = (colision.shape as ConcavePolygonShape3D).duplicate() as ConcavePolygonShape3D
		colision.shape = forma

	var s := malla.global_transform.basis.get_scale()
	escala = maxf(0.001, (absf(s.x) + absf(s.y) + absf(s.z)) / 3.0)
	nivel_agua = _detectar_nivel_agua()
	_construir_vecinos()
	_reconstruir_malla()
	return true


## Altura local de la superficie del océano. El agua de cada isla es un
## duplicado hermano de la isla; si no hay océano (glTF suelto) se usa el valor
## del mundo de ISLA3Dblock.
func _detectar_nivel_agua() -> float:
	var malla_agua := _buscar_malla_oceano(isla.get_parent() if isla.get_parent() != null else isla, 0)
	if malla_agua == null:
		malla_agua = _buscar_malla_oceano(isla, 0)
	if malla_agua == null or malla_agua.mesh == null:
		return NIVEL_AGUA_DEFECTO
	var caja: AABB = malla_agua.global_transform * malla_agua.mesh.get_aabb()
	return malla.to_local(Vector3(0.0, caja.end.y, 0.0)).y


func _buscar_malla_oceano(nodo: Node, profundidad: int) -> MeshInstance3D:
	if nodo == null or profundidad > 3:
		return null
	if nodo is MeshInstance3D and str(nodo.name).begins_with("Oceano"):
		return nodo as MeshInstance3D
	for hijo in nodo.get_children():
		var hallado := _buscar_malla_oceano(hijo, profundidad + 1)
		if hallado != null:
			return hallado
	return null


## Aplica un paso de pincel. `centro_mundo` viene del raycast, `radio_m` y
## `fuerza_m` en metros. `delta_mundo` es el arrastre del ratón desde el paso
## anterior y solo lo usa MOVER. Devuelve cuántos vértices cambiaron.
func aplicar_pincel(centro_mundo: Vector3, radio_m: float, fuerza_m: float,
		dt: float, herramienta: int, delta_mundo := Vector3.ZERO) -> int:
	if malla == null or vertices.is_empty():
		return 0
	var centro := malla.to_local(centro_mundo)
	var radio_local := maxf(radio_m, 0.5) / maxf(escala, 0.001)
	var r2 := radio_local * radio_local
	var paso := clampf(fuerza_m * dt / maxf(escala, 0.001), -0.02, 0.02)
	if herramienta == SUAVIZAR:
		paso = clampf(absf(fuerza_m) * dt * 0.5, 0.0, 0.35)
	var dir_mover := Vector2.ZERO
	var avance_mover := 0.0
	if herramienta == MOVER:
		var arrastre := Vector2(delta_mundo.x, delta_mundo.z) / maxf(escala, 0.001)
		# Un paso mayor que media celda rompe el esquema upwind; el resto se
		# recupera en los siguientes ticks.
		avance_mover = minf(arrastre.length(), _espaciado * 0.5)
		if avance_mover < 0.000001:
			return 0
		dir_mover = arrastre.normalized()
	var objetivo_playa := nivel_agua + MARGEN_PLAYA_M / maxf(escala, 0.001)
	var afectados: Array[int] = []
	var alfa_antes := 0.0
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
			SUBIR:
				v.y = minf(ALTURA_MAX, v.y + paso * caida)
			BAJAR:
				v.y = maxf(ALTURA_MIN, v.y - paso * caida)
			SUAVIZAR:
				var promedio := _promedio_vecinos(i)
				v.y = lerpf(v.y, promedio, clampf(paso * caida, 0.0, 0.5))
			APLANAR:
				var delta := clampf(paso * caida * 2.0, -0.05, 0.05)
				v.y = move_toward(v.y, clampf(centro.y, ALTURA_MIN, ALTURA_MAX), absf(delta))
			MOVER:
				# Advección upwind: cada vértice toma la altura y el color de
				# donde venía la tierra. La arena viaja con el montículo en vez
				# de quedarse atrás. El borde del pincel se mueve menos para no
				# dejar un escalón.
				var flujo := _flujo_ascendente(i, dir_mover)
				if flujo.is_empty():
					continue
				var salto := -avance_mover * float(flujo["pendiente"]) * caida
				v.y = clampf(v.y + clampf(salto, -0.02, 0.02), ALTURA_MIN, ALTURA_MAX)
				var mezcla := caida * minf(1.0, avance_mover / maxf(_espaciado, 1e-6))
				alfa_antes += colores[i].a
				colores[i] = colores[i].lerp(flujo["color"], clampf(mezcla, 0.0, 1.0))
			PLAYA:
				# Objetivo mezclado con la altura actual según la caída: el
				# centro llega a agua+1 m y el borde apenas cambia.
				var destino := lerpf(v.y, objetivo_playa, caida)
				var mezcla := clampf(absf(fuerza_m) * dt * 1.2, 0.0, 0.45) * caida
				var nuevo := lerpf(v.y, destino, mezcla)
				v.y = clampf(move_toward(v.y, nuevo, 0.02), ALTURA_MIN, ALTURA_MAX)
				colores[i] = colores[i].lerp(COLOR_PLAYA, clampf(caida * 0.4, 0.0, 0.4))
			_:
				continue
		vertices[i] = v
		afectados.append(i)
	if afectados.is_empty():
		return 0
	# El upwind de primer orden difumina la máscara de arena. Se le devuelve el
	# alfa perdido en el borde para que la tierra arrastrada no palidezca.
	if herramienta == MOVER:
		_equilibrar_alfa(afectados, alfa_antes)
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


## Blob binario (cabecera + alturas float32 + color RGBA8) para disco y túnel.
func serializar() -> PackedByteArray:
	var datos := PackedByteArray()
	var total := 18 + vertices.size() * 8
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
	for i in colores.size():
		var c := colores[i]
		datos[off] = clampi(roundi(c.r * 255.0), 0, 255)
		datos[off + 1] = clampi(roundi(c.g * 255.0), 0, 255)
		datos[off + 2] = clampi(roundi(c.b * 255.0), 0, 255)
		datos[off + 3] = clampi(roundi(c.a * 255.0), 0, 255)
		off += 4
	return datos


## Carga un blob. Devuelve false si la geometría base no coincide (el mundo
## cambió de versión y las alturas guardadas ya no se pueden aplicar).
## Acepta v1 (solo alturas) y v2 (alturas + colores).
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
	if version < 1 or version > VERSION:
		return false
	var cuenta := datos.decode_u32(off)
	off += 4
	var cargado := 4 if version == 1 else 8
	if cuenta != vertices.size() or datos.size() < 18 + cuenta * cargado:
		return false
	var hash_guardado := datos.decode_s64(off)
	off += 8
	if hash_guardado != _hash_base:
		push_warning("[Terreno] Geometría base distinta en isla %d; se descartan alturas" % indice)
		return false
	if colores.size() != vertices.size():
		colores.resize(vertices.size())
		colores.fill(COLOR_SIN_ARENA)
	# El blob guarda primero todas las alturas y después todos los colores.
	for i in cuenta:
		var v := vertices[i]
		v.y = clampf(datos.decode_float(off), ALTURA_MIN, ALTURA_MAX)
		off += 4
		vertices[i] = v
	if version >= 2:
		for i in cuenta:
			colores[i] = Color8(datos[off], datos[off + 1], datos[off + 2], datos[off + 3])
			off += 4
	else:
		colores.fill(COLOR_SIN_ARENA)
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


## Devuelve al conjunto `afectados` el alfa total que tenía antes del paso,
## sin pasar de 1 por vértice. Solo actúa si el transporte perdió máscara.
func _equilibrar_alfa(afectados: Array[int], objetivo: float) -> void:
	if objetivo <= 0.0:
		return
	var actual := 0.0
	for i in afectados:
		actual += colores[i].a
	if actual >= objetivo * 0.999 or actual <= 1e-6:
		return
	var factor := objetivo / actual
	for i in afectados:
		var c := colores[i]
		c.a = minf(1.0, c.a * factor)
		colores[i] = c


## Flujo de barlovento: media de altura y color de los vecinos que quedan
## contra el arrastre. Un gradiente centrado es inestable para advectar:
## difumina el montículo en vez de trasladarlo. Devuelve {} si no hay vecinos
## de barlovento (borde de la malla o arrastre nulo).
func _flujo_ascendente(i: int, dir: Vector2) -> Dictionary:
	if i < 0 or i >= _vecinos.size():
		return {}
	var v := vertices[i]
	var suma := 0.0
	var color := Color(0.0, 0.0, 0.0, 0.0)
	var n := 0
	var distancia := 0.0
	for j in _vecinos[i]:
		var w := vertices[j]
		var off := Vector2(w.x - v.x, w.z - v.z)
		var largo := off.length()
		if largo < 1e-6:
			continue
		var alineacion := (off.x * dir.x + off.y * dir.y) / largo
		if alineacion < -0.45:
			suma += w.y
			color += colores[j]
			n += 1
			distancia += largo
	if n == 0:
		return {}
	var paso := maxf(distancia / float(n), 1e-6)
	return {
		"pendiente": (v.y - suma / float(n)) / paso,
		"color": color / float(n),
	}


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
	if colores.size() == vertices.size():
		arrays[Mesh.ARRAY_COLOR] = colores
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
	var suma := 0.0
	var cuenta := 0
	for i in listas.size():
		var lista: PackedInt32Array = listas[i]
		if lista.is_empty():
			continue
		suma += vertices[i].distance_to(vertices[lista[0]])
		cuenta += 1
	_espaciado = maxf(0.001, suma / float(maxi(cuenta, 1)))


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
