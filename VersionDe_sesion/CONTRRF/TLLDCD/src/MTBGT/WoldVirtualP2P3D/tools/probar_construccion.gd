extends SceneTree
## Prueba headless del sistema de construccion: terreno editable, prims y
## registro en Construccion. No abre red: los RPC se validan solo por tipos.

const Terreno := preload("res://gdscrip/TerrenoEditable.gd")
const Prims := preload("res://gdscrip/Prims.gd")
const VoxelSuave := preload("res://gdscrip/VoxelSuave.gd")
const Construccion := preload("res://gdscrip/Construccion.gd")
const ESCENA_ISLA := "res://gltfimport/terrenoblok/ISLA3DCHUNK.gltf"

var _ok := 0
var _fallos := 0
var _contexto := ""


class StubChunk:
	extends Node3D
	var island_owners := {}
	var my_own_index := -1
	var _mi_uuid := ""


class AvatarFalso:
	extends CharacterBody3D
	var control_avatar := true


func _initialize() -> void:
	_correr()


func _correr() -> void:
	# El árbol debe estar activo para que los nodos tengan transform global.
	await process_frame
	_probar_terreno()
	_probar_aislamiento()
	_probar_color_mover()
	_probar_prims()
	_probar_voxel()
	_probar_construccion()
	print("RESULTADO CONSTRUCCION: %d OK, %d FALLOS" % [_ok, _fallos])
	quit(0 if _fallos == 0 else 1)


func _check(condicion: bool, mensaje: String) -> void:
	if condicion:
		_ok += 1
	else:
		_fallos += 1
		push_error("[FALLO] %s -> %s" % [_contexto, mensaje])
		print("[FALLO] %s -> %s" % [_contexto, mensaje])


func _instancia_isla() -> Node3D:
	var packed := load(ESCENA_ISLA) as PackedScene
	var raiz := packed.instantiate() as Node3D
	root.add_child(raiz)
	return raiz


## Índice del vértice más cercano a una posición local XZ.
func _indice_cerca(t, lx: float, lz: float) -> int:
	var mejor := 0
	var mejor_d := 1e20
	for i in t.vertices.size():
		var d := Vector2(t.vertices[i].x - lx, t.vertices[i].z - lz).length()
		if d < mejor_d:
			mejor_d = d
			mejor = i
	return mejor


func _altura_cerca(t, lx: float, lz: float) -> float:
	return t.vertices[_indice_cerca(t, lx, lz)].y


## Altura media en un anillo local XZ (la plataforma lejos del montículo).
func _media_anillo(t, r0: float, r1: float) -> float:
	var suma := 0.0
	var n := 0
	for v in t.vertices:
		var r := Vector2(v.x, v.z).length()
		if r >= r0 and r <= r1:
			suma += v.y
			n += 1
	return suma / float(n) if n > 0 else 0.0


## Centro X del exceso de altura sobre `umbral` en una ventana local.
func _centroide_exceso(t, umbral: float, banda_x: float, banda_z: float) -> float:
	var suma := 0.0
	var peso := 0.0
	for v in t.vertices:
		if absf(v.x) > banda_x or absf(v.z) > banda_z:
			continue
		var exceso: float = float(v.y) - umbral
		if exceso <= 0.0:
			continue
		suma += v.x * exceso
		peso += exceso
	return suma / peso if peso > 0.0 else 0.0


## Altura media dentro de una caja local XZ.
func _media_caja(t, x0: float, x1: float, z0: float, z1: float) -> float:
	var suma := 0.0
	var n := 0
	for v in t.vertices:
		if v.x >= x0 and v.x <= x1 and v.z >= z0 and v.z <= z1:
			suma += v.y
			n += 1
	return suma / float(n) if n > 0 else 0.0


## Compara colores con la tolerancia de una cuantización RGBA8.
func _color_cerca(a: Color, b: Color) -> bool:
	var margen := 1.01 / 255.0
	return (absf(a.r - b.r) <= margen and absf(a.g - b.g) <= margen
			and absf(a.b - b.b) <= margen and absf(a.a - b.a) <= margen)


func _probar_terreno() -> void:
	_contexto = "terreno"
	var isla := _instancia_isla()
	var malla_original := isla.get_node("isla3D") as MeshInstance3D
	var cuerpo_original := malla_original.get_node("StaticBody3D") as StaticBody3D
	var col_original := cuerpo_original.get_node("CollisionShape3D") as CollisionShape3D
	var forma_original := col_original.shape
	var t := Terreno.new()
	_check(t.configurar(isla, 0), "configurar() acepta la malla de la isla")
	_check(t.vertices.size() > 1000, "la malla tiene vertices (%d)" % t.vertices.size())
	_check(t.indices.size() % 3 == 0, "los indices forman triangulos")
	_check(t.forma != null, "la colision trimesh quedo disponible")
	_check(t.forma != forma_original, "la colision se duplico por isla")
	_check(t.normales.size() == t.vertices.size(), "hay una normal por vertice")
	_check(t.material != null, "la malla conserva su material (%s)" % t.material)
	var ymax := -1e20
	for v in t.vertices:
		ymax = maxf(ymax, v.y)
	_check(ymax <= Terreno.ALTURA_MAX + 0.0001, "la malla base cabe en ALTURA_MAX")

	# Un vertice concreto se mueve al aplicar el pincel en su posicion mundial.
	var objetivo := t.vertices.size() / 2
	var antes := t.vertices[objetivo].y
	var mundo := t.malla.to_global(t.vertices[objetivo])
	var t0 := Time.get_ticks_usec()
	var afectados := t.aplicar_pincel(mundo, 6.0, 2.0, 0.05, 0)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("[terreno] pincel: %d vertices afectados en %.2f ms" % [afectados, ms])
	_check(afectados > 0, "subir afecta a vertices cercanos")
	_check(t.vertices[objetivo].y > antes, "subir aumenta la altura del vertice")

	var tope := 0.0
	for i in 80:
		t.aplicar_pincel(mundo, 6.0, 4.0, 0.05, 0)
	for v in t.vertices:
		tope = maxf(tope, v.y)
	_check(tope <= Terreno.ALTURA_MAX + 0.0001, "subir no supera ALTURA_MAX (%.4f)" % tope)

	for i in 60:
		t.aplicar_pincel(mundo, 6.0, 4.0, 0.05, 1)
	var suelo := 1e20
	for v in t.vertices:
		suelo = minf(suelo, v.y)
	_check(suelo >= Terreno.ALTURA_MIN - 0.0001, "bajar no baja de ALTURA_MIN (%.4f)" % suelo)

	_check(t.aplicar_pincel(mundo, 6.0, 2.0, 0.05, 2) > 0, "suavizar modifica vertices")
	_check(t.aplicar_pincel(mundo, 6.0, 2.0, 0.05, 3) > 0, "aplanar modifica vertices")

	# Mover: el montículo viaja en la dirección del arrastre y deja hueco detrás.
	var isla_m := _instancia_isla()
	var tm := Terreno.new()
	_check(tm.configurar(isla_m, 2), "configurar() prepara la isla para mover")
	var cima := tm.malla.to_global(Vector3(0.0, _altura_cerca(tm, 0.0, 0.0), 0.0))
	var plataforma := _media_anillo(tm, 0.30, 0.45)
	for i in 30:
		tm.aplicar_pincel(cima, 10.0, 4.0, 0.05, Terreno.SUBIR)
	var umbral := plataforma + 0.01
	var centro_antes := _centroide_exceso(tm, umbral, 0.2, 0.2)
	var origen_antes := _media_caja(tm, -0.05, 0.0, -0.05, 0.05)
	_check(tm.aplicar_pincel(cima, 16.0, 4.0, 0.05, Terreno.MOVER) == 0,
			"mover sin arrastre no cambia nada")
	for i in 30:
		tm.aplicar_pincel(cima, 16.0, 4.0, 0.05, Terreno.MOVER, Vector3(0.5, 0.0, 0.0))
	var centro_despues := _centroide_exceso(tm, umbral, 0.2, 0.2)
	var origen_despues := _media_caja(tm, -0.05, 0.0, -0.05, 0.05)
	print("[mover] plataforma=%.4f umbral=%.4f centro %.4f -> %.4f origen %.4f -> %.4f"
			% [plataforma, umbral, centro_antes, centro_despues, origen_antes, origen_despues])
	_check(centro_despues > centro_antes + 0.02,
			"mover desplaza el montículo hacia +X (%.4f -> %.4f)" % [centro_antes, centro_despues])
	_check(origen_despues < origen_antes - 0.01,
			"mover vacía la posición original (%.4f -> %.4f)" % [origen_antes, origen_despues])
	for i in 60:
		tm.aplicar_pincel(cima, 16.0, 4.0, 0.05, Terreno.MOVER, Vector3(2.0, 0.0, 0.0))
	var tope_mover := -1e20
	var suelo_mover := 1e20
	for v in tm.vertices:
		tope_mover = maxf(tope_mover, v.y)
		suelo_mover = minf(suelo_mover, v.y)
	_check(tope_mover <= Terreno.ALTURA_MAX + 0.0001 and suelo_mover >= Terreno.ALTURA_MIN - 0.0001,
			"mover respeta los límites de altura (%.3f..%.3f)" % [suelo_mover, tope_mover])

	# Playa: aplana el borde costero a ~1 m sobre el agua y lo tiñe de arena.
	_check(absf(t.nivel_agua - Terreno.NIVEL_AGUA_DEFECTO) < 0.001,
			"sin océano se usa el nivel de agua por defecto (%.4f)" % t.nivel_agua)
	var costa := _indice_cerca(t, 0.50, 0.0)
	var costa_mundo := t.malla.to_global(t.vertices[costa])
	var objetivo_playa: float = t.nivel_agua + Terreno.MARGEN_PLAYA_M / t.escala
	for i in 60:
		t.aplicar_pincel(costa_mundo, 14.0, 4.0, 0.05, Terreno.PLAYA)
	_check(absf(t.vertices[costa].y - objetivo_playa) < 0.01,
			"playa aplana a agua+1 m (%.4f vs %.4f)" % [t.vertices[costa].y, objetivo_playa])
	_check(_color_cerca(t.colores[costa], Terreno.COLOR_PLAYA),
			"playa tiñe de arena (%s)" % t.colores[costa].to_html(true))

	var t1 := Time.get_ticks_usec()
	t.actualizar_colision()
	var ms_col := (Time.get_ticks_usec() - t1) / 1000.0
	print("[terreno] colision: %d caras en %.2f ms" % [t.indices.size(), ms_col])
	_check(t.forma.get_faces().size() == t.indices.size(), "la colision copia todas las caras")
	var caras := t.forma.get_faces()
	_check(caras.size() > 0 and caras[0].is_equal_approx(t.vertices[t.indices[0]]),
			"la primera cara coincide con el vertice")

	var datos := t.serializar()
	print("[terreno] blob: %d bytes, zstd %d bytes" % [
		datos.size(), datos.compress(FileAccess.COMPRESSION_ZSTD).size()])
	_check(datos.size() == 18 + t.vertices.size() * 8, "el blob v2 lleva alturas y colores")
	_check(datos.slice(0, 4).get_string_from_utf8() == "WVPT", "magia WVPT correcta")
	_check(datos.decode_u16(4) == Terreno.VERSION, "version del blob correcta")

	# Restaurar en otra malla independiente reproduce las mismas alturas.
	var isla2 := _instancia_isla()
	var t2 := Terreno.new()
	_check(t2.configurar(isla2, 1), "segunda isla configurada")
	_check(t2.cargar(datos), "cargar() acepta el blob guardado")
	var iguales := true
	for i in t.vertices.size():
		if absf(t2.vertices[i].y - t.vertices[i].y) > 0.0001:
			iguales = false
			break
	_check(iguales, "las alturas restauradas coinciden")
	_check(_color_cerca(t2.colores[costa], t.colores[costa]), "el color de arena se restaura (%s)" % t2.colores[costa].to_html(true))
	_check(t2.forma.get_faces().size() == t2.indices.size(), "la colision restaurada esta completa")

	# Un blob v1 (sin colores) sigue siendo válido y deja todo en blanco.
	var v1 := datos.slice(0, 18 + t.vertices.size() * 4)
	v1.encode_u16(4, 1)
	_check(t2.cargar(v1), "cargar() acepta blobs v1 sin colores")
	_check(t2.colores[costa].is_equal_approx(Terreno.COLOR_SIN_ARENA),
			"un blob v1 deja los colores sin arena")

	var malo := datos.duplicate()
	malo[0] = 65
	_check(not t2.cargar(malo), "rechaza magia desconocida")
	malo = datos.duplicate()
	malo.encode_u16(4, 99)
	_check(not t2.cargar(malo), "rechaza version desconocida")
	malo = datos.duplicate()
	malo.encode_u32(6, 5)
	_check(not t2.cargar(malo), "rechaza recuento distinto")
	malo = datos.duplicate()
	malo.encode_s64(10, datos.decode_s64(10) + 1)
	_check(not t2.cargar(malo), "rechaza geometria base distinta")
	_check(not t2.cargar(PackedByteArray()), "rechaza blob vacio")

	isla.queue_free()
	isla2.queue_free()


## Las islas comparten la plantilla de ChunkManager: duplicar() reutiliza la
## malla y la colisión de origen hasta que cada terreno las sustituye. Esta
## prueba fija que esculpir una isla no alcanza a las demás ni a las que
## aparezcan después en el mundo.
func _probar_aislamiento() -> void:
	_contexto = "aislamiento"
	var plantilla := _instancia_isla()
	plantilla.name = "ISLA3DCHUNK"
	var a := plantilla.duplicate() as Node3D
	root.add_child(a)
	var b := plantilla.duplicate() as Node3D
	root.add_child(b)
	b.position.x = 199.5

	var ta := Terreno.new()
	var tb := Terreno.new()
	_check(ta.configurar(a, 10), "isla A preparada")
	_check(tb.configurar(b, 11), "isla B preparada")
	_check(ta.malla.mesh != tb.malla.mesh, "cada isla usa su propia malla")
	_check(ta.material != tb.material, "cada isla usa su propio material")
	_check(ta.forma != tb.forma, "cada isla usa su propia colisión")
	var malla_plantilla := plantilla.get_node("isla3D") as MeshInstance3D
	var base_plantilla: PackedVector3Array = malla_plantilla.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var base_b := tb.vertices.duplicate()
	var colores_b := tb.colores.duplicate()

	var cima := ta.malla.to_global(Vector3(0.0, _altura_cerca(ta, 0.0, 0.0), 0.0))
	for i in 30:
		ta.aplicar_pincel(cima, 18.0, 4.0, 0.05, Terreno.SUBIR)
	for i in 30:
		ta.aplicar_pincel(cima, 18.0, 4.0, 0.05, Terreno.PLAYA)
	_check(ta.vertices != ta.vertices_base, "esculpir A cambia su geometría")
	_check(tb.vertices == base_b, "esculpir A no cambia las alturas de B")
	_check(tb.colores == colores_b, "esculpir A no tiñe de arena B")

	# Una isla que aparece DESPUÉS de haber editado A debe nacer intacta.
	var c := plantilla.duplicate() as Node3D
	root.add_child(c)
	c.position.x = -199.5
	var tc := Terreno.new()
	_check(tc.configurar(c, 12), "isla C preparada tras editar A")
	_check(tc.vertices == tc.vertices_base, "la isla nueva nace intacta")
	_check(tc.vertices == base_b, "la isla nueva tiene la geometría base común")
	_check(tc.colores == colores_b, "la isla nueva nace sin arena")
	_check(tc.malla.mesh != ta.malla.mesh, "la isla nueva no comparte malla con A")
	_check(tc.material != ta.material, "la isla nueva no comparte material con A")
	_check(tc.forma != ta.forma, "la isla nueva no comparte colisión con A")
	_check(malla_plantilla.mesh != ta.malla.mesh,
			"la plantilla oculta conserva la malla sin editar")
	_check(base_plantilla == tc.vertices_base,
			"la plantilla no absorbe las alturas esculpidas en A")

	a.queue_free()
	b.queue_free()
	c.queue_free()
	plantilla.queue_free()


## Centro X (local) de la máscara de arena, ponderado por alfa.
func _centroide_arena(t) -> float:
	var suma := 0.0
	var peso := 0.0
	for i in t.colores.size():
		var a: float = t.colores[i].a
		if a <= 0.05:
			continue
		suma += t.vertices[i].x * a
		peso += a
	return suma / peso if peso > 0.0 else 0.0


func _masa_arena(t) -> float:
	var total := 0.0
	for c in t.colores:
		total += c.a
	return total


func _max_alfa_cerca(t, lx: float) -> float:
	var mejor := 0.0
	for i in t.vertices.size():
		if absf(t.vertices[i].x - lx) > 0.05 or absf(t.vertices[i].z) > 0.10:
			continue
		mejor = maxf(mejor, t.colores[i].a)
	return mejor


## Mover debe arrastrar el color de la tierra: una playa bajo un montículo
## viaja con él y el terreno desplazado conserva su aspecto de arena.
func _probar_color_mover() -> void:
	_contexto = "mover color"
	var isla := _instancia_isla()
	var t := Terreno.new()
	_check(t.configurar(isla, 20), "isla preparada para mover con arena")

	var costa := _indice_cerca(t, 0.50, 0.0)
	var costa_mundo: Vector3 = t.malla.to_global(t.vertices[costa])
	for i in 60:
		t.aplicar_pincel(costa_mundo, 14.0, 4.0, 0.05, Terreno.PLAYA)
	var masa_antes := _masa_arena(t)
	_check(masa_antes > 100.0, "la playa deja máscara de arena (%.0f)" % masa_antes)
	for i in 20:
		t.aplicar_pincel(costa_mundo, 8.0, 4.0, 0.05, Terreno.SUBIR)
	var arena_x := _centroide_arena(t)
	_check(t.vertices[costa].y > t.nivel_agua + 0.02,
			"el montículo eleva la arena (%.3f)" % t.vertices[costa].y)

	for i in 40:
		t.aplicar_pincel(costa_mundo, 20.0, 4.0, 0.05, Terreno.MOVER, Vector3(0.5, 0.0, 0.0))
	var arena_despues := _centroide_arena(t)
	var masa_despues := _masa_arena(t)
	print("[mover color] arena x %.4f -> %.4f (%.2f m), masa %.0f -> %.0f"
			% [arena_x, arena_despues, (arena_despues - arena_x) * t.escala,
			masa_antes, masa_despues])
	_check((arena_despues - arena_x) * t.escala > 3.0,
			"la arena viaja con el montículo (%.2f m)"
			% ((arena_despues - arena_x) * t.escala))
	_check(absf(masa_despues - masa_antes) < masa_antes * 0.25,
			"la máscara de arena se conserva (%.0f -> %.0f)" % [masa_antes, masa_despues])
	var alfa := _max_alfa_cerca(t, arena_despues)
	_check(alfa > 0.5, "el terreno desplazado sigue siendo arena (alfa %.2f)" % alfa)
	isla.queue_free()


func _probar_prims() -> void:
	_contexto = "prims"
	for tipo in Prims.TIPOS:
		_check(Prims.crear_malla(tipo) != null, "malla de %s" % tipo)
		_check(Prims.crear_forma(tipo) != null, "colision de %s" % tipo)
		var tam := Prims.tamano_por_defecto(tipo)
		_check(tam.x > 0.0 and tam.y > 0.0 and tam.z > 0.0, "tamano por defecto de %s" % tipo)
	_check(Prims.crear_forma("toro") is ConcavePolygonShape3D, "el toro usa colision trimesh")

	var datos := {
		7: {
			"id": 7,
			"tipo": "cilindro",
			"pos": Vector3(1.5, 2.0, -3.0),
			"rot": Vector3(0.0, 45.0, 0.0),
			"escala": Vector3(1.4, 2.2, 1.4),
			"color": Color(0.28, 0.68, 0.95),
		},
	}
	var texto := Prims.serializar_isla(datos, 8, "UUID-PRUEBA")
	var leido := Prims.deserializar_isla(texto)
	_check(not leido.is_empty(), "JSON de prims legible")
	_check(int(leido["siguiente"]) == 8, "conserva el siguiente id")
	var p: Dictionary = leido["prims"][7]
	_check(p["tipo"] == "cilindro", "conserva el tipo")
	_check((p["pos"] as Vector3).is_equal_approx(Vector3(1.5, 2.0, -3.0)), "conserva la posicion")
	_check((p["escala"] as Vector3).is_equal_approx(Vector3(1.4, 2.2, 1.4)), "conserva la escala")
	_check((p["color"] as Color).to_html(true) == Color(0.28, 0.68, 0.95).to_html(true),
			"conserva el color")
	_check(Prims.deserializar_isla("[1, 2, 3]").is_empty(), "rechaza JSON que no es objeto")
	_check(Prims.deserializar_isla('{"version": 2, "prims": []}').is_empty(),
			"rechaza version desconocida")
	var con_id_malo := Prims.deserializar_isla(
			'{"version": 1, "siguiente": 1, "prims": [{"id": 0, "tipo": "cubo"}]}')
	_check(con_id_malo["prims"].is_empty(), "descarta ids no positivos")


func _probar_voxel() -> void:
	_contexto = "voxel"
	for forma in VoxelSuave.FORMAS:
		var prm := VoxelSuave.params_por_defecto(forma)
		var malla := VoxelSuave.new().generar(prm)
		_check(malla.get_surface_count() == 1, "malla voxel de %s" % forma)
		if malla.get_surface_count() == 0:
			continue
		var arrays := malla.surface_get_arrays(0)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		var normales: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		_check(verts.size() > 100, "%s genera geometría (%d vértices)" % [forma, verts.size()])
		_check(indices.size() > 0 and indices.size() % 3 == 0,
				"%s genera triángulos (%d)" % [forma, indices.size()])
		_check(normales.size() == verts.size(), "%s tiene normales por vértice" % forma)
		var radio_max := 0.0
		var ymin := 1e9
		var ymax := -1e9
		for v in verts:
			radio_max = maxf(radio_max, Vector2(v.x, v.z).length())
			ymin = minf(ymin, v.y)
			ymax = maxf(ymax, v.y)
		_check(radio_max <= float(prm["borde"]) + 0.001,
				"%s cabe en el borde (%.2f <= %.2f)" % [forma, radio_max, prm["borde"]])
		_check(ymin >= -float(prm["fondo"]) - 0.001,
				"%s respeta el fondo (%.2f)" % [forma, ymin])
		_check(ymax <= float(prm["altura"]) * 1.16,
				"%s respeta la altura (%.2f)" % [forma, ymax])
		var otra := VoxelSuave.new().generar(prm)
		var arrays2 := otra.surface_get_arrays(0)
		_check((arrays2[Mesh.ARRAY_VERTEX] as PackedVector3Array) == verts,
				"%s se regenera igual con la misma semilla" % forma)

	var malo := VoxelSuave.normalizar_params(
			{"forma": "castillo", "radio": -5.0, "altura": 900.0, "detalle": 999})
	_check(malo["forma"] == "isla", "una forma desconocida cae a isla")
	_check(float(malo["radio"]) >= VoxelSuave.RADIO_MIN, "el radio se acota")
	_check(float(malo["altura"]) <= VoxelSuave.ALTURA_MAX, "la altura se acota")
	_check(int(malo["detalle"]) <= VoxelSuave.DETALLE_MAX, "el detalle se acota")

	var ajuste := VoxelSuave.ajustar_a_borde(VoxelSuave.params_por_defecto("isla"), 20.0, false)
	_check(not ajuste.is_empty() and float(ajuste["borde"]) <= 19.5,
			"en tierra firme el borde queda dentro del contorno")
	var costa := VoxelSuave.ajustar_a_borde(VoxelSuave.params_por_defecto("isla"), 6.0, true)
	_check(not costa.is_empty(), "junto a la costa se puede crear una playa")
	_check(float(costa["borde"]) <= 6.0 + 0.001,
			"la playa no se sale del contorno medido")
	_check(float(costa["playa"]) > 0.0, "la playa activa el faldón de arena")
	_check(VoxelSuave.ajustar_a_borde(VoxelSuave.params_por_defecto("isla"), 2.0, true).is_empty(),
			"rechaza un punto sin tierra firme suficiente")

	_check(Prims.es_tipo_valido("voxel"), "voxel es un tipo válido")
	var prm_meseta := VoxelSuave.params_por_defecto("meseta")
	var malla_prims := Prims.crear_malla("voxel", prm_meseta)
	_check(malla_prims is ArrayMesh and malla_prims.get_surface_count() == 1,
			"Prims crea la malla voxel")
	_check(Prims.crear_forma("voxel", prm_meseta) is ConcavePolygonShape3D,
			"Prims crea la colisión trimesh del voxel")
	var texto := Prims.serializar_isla({1: {
		"id": 1, "tipo": "voxel", "pos": Vector3(2, 3, 4), "rot": Vector3.ZERO,
		"escala": Vector3.ONE, "color": Color.WHITE, "params": prm_meseta,
	}}, 2, "UUID-VOXEL")
	var leido := Prims.deserializar_isla(texto)
	_check(not leido.is_empty() and leido["prims"][1]["tipo"] == "voxel",
			"el JSON conserva el prim voxel")
	_check(leido["prims"][1]["params"]["forma"] == "meseta",
			"el JSON conserva la forma del terreno")
	_check(int(leido["prims"][1]["params"]["semilla"]) == int(prm_meseta["semilla"]),
			"el JSON conserva la semilla del terreno")
	var sin_params := Prims.desde_dict({"id": 2, "tipo": "voxel"})
	_check(sin_params["params"]["forma"] == "isla",
			"un voxel sin params usa la forma por defecto")


func _probar_construccion() -> void:
	_contexto = "construccion"
	var stub := StubChunk.new()
	stub.name = "StubChunk"
	root.add_child(stub)
	var avatar := AvatarFalso.new()
	avatar.name = "USERBASE"
	stub.add_child(avatar)
	stub.island_owners = {99: [1, "Prueba", "UUID-PRUEBA"]}
	stub.my_own_index = 99
	stub._mi_uuid = "UUID-PRUEBA"

	var c := Construccion.new()
	c.name = "Constructor"
	stub.add_child(c)
	_check(c._panel != null, "_ready construye el panel")
	_check(c._panel._botones_herr.size() == 7, "el panel ofrece las 7 herramientas")
	_check(c._panel._botones_herr[5].text == "Mover" and c._panel._botones_herr[6].text == "Playa",
			"mover y playa están en el panel")

	var isla := _instancia_isla()
	isla.get_parent().remove_child(isla)
	stub.add_child(isla)
	c.registrar_isla(99, isla)
	_check(c._terrenos.has(99), "la isla queda registrada con terreno")
	_check(c._contenedores.has(99), "la isla tiene contenedor de objetos")
	_check(c._prims.has(99) and c._prims[99].is_empty(), "empieza sin objetos")

	var id: int = c._host_crear_prim(99, "cilindro", Vector3(1.0, 2.0, 3.0),
			Vector3(0.0, 45.0, 0.0), Vector3(1.4, 2.2, 1.4), Color(0.28, 0.68, 0.95))
	_check(id == 1, "el primer prim recibe id 1")
	_check(c._prims[99].has(1), "el prim queda en el registro")
	_check(c._nodos[99].has(1), "el prim se instancia en la isla")
	var nodo: Node3D = c._nodos[99][1]
	_check(nodo.position.is_equal_approx(Vector3(1.0, 2.0, 3.0)), "posicion aplicada al nodo")
	_check(nodo.scale.is_equal_approx(Vector3(1.4, 2.2, 1.4)), "escala aplicada al nodo")
	_check(nodo.get_node_or_null("Malla") is MeshInstance3D, "el prim tiene malla")
	_check(nodo.get_node_or_null("Colision") is CollisionShape3D, "el prim tiene colision")

	# Simula el aviso del anfitrion con un id creado por otro peer.
	c._siguiente[99] = 1
	c._prim_creado(99, 5, "cubo", Vector3.ZERO, Vector3.ZERO, Vector3.ONE, Color.WHITE, {})
	_check(int(c._siguiente[99]) == 6, "el contador avanza con ids remotos")
	_check(c._prims[99].has(5), "un prim remoto se instancia")
	c._prim_borrado(99, 5)

	c._seleccionar(nodo)
	_check(c._sel_id == 1 and c._sel_isla == 99, "seleccionar fija isla e id")
	_check(c._puedo_editar(99), "la isla propia se puede editar")
	_check(not c._puedo_editar(123), "una isla desconocida no se puede editar")
	_check(is_equal_approx(c._panel.escala_objetivo(), 2.2), "el panel muestra el tamano real")

	# Propiedad: la isla de otro peer ni se edita ni se puede esculpir por RPC.
	var isla_ajena := _instancia_isla()
	isla_ajena.get_parent().remove_child(isla_ajena)
	stub.add_child(isla_ajena)
	isla_ajena.position.x = 199.5
	stub.island_owners[100] = [2, "Otro", "UUID-OTRO"]
	c.registrar_isla(100, isla_ajena)
	_check(c._terrenos.has(100), "la isla ajena también se registra")
	_check(not c._puedo_editar(100), "la isla de otro peer no se puede editar")
	_check(c._validar_remitente(100, 2), "el dueño puede esculpir su isla por RPC")
	_check(not c._validar_remitente(100, 3), "un tercer peer no puede esculpir la isla ajena")
	_check(not c._validar_remitente(100, 0), "un remitente sin identificar se rechaza")
	var base_ajena: PackedVector3Array = c._terrenos[100].vertices.duplicate()
	var mio: Vector3 = c._terrenos[99].malla.to_global(c._terrenos[99].vertices[0])
	c._terrenos[99].aplicar_pincel(mio, 40.0, 4.0, 0.05, Terreno.SUBIR)
	_check(c._terrenos[100].vertices == base_ajena, "esculpir mi isla no toca la ajena")
	c.registrar_isla(101, isla)
	_check(not c._islas.has(101), "registrar_isla rechaza un nodo ya registrado")

	c._aplicar_escala(4.4)
	var esc: Vector3 = c._prims[99][1]["escala"]
	_check(esc.is_equal_approx(Vector3(2.8, 4.4, 2.8)), "escalar conserva la proporcion")

	var antes_x: float = c._prims[99][1]["pos"].x
	c._mover_seleccion(KEY_RIGHT, false)
	_check(is_equal_approx(c._prims[99][1]["pos"].x, antes_x + 0.5), "mover desplaza con la rejilla")

	c._aplicar_color(Color(0.93, 0.32, 0.31))
	_check((c._prims[99][1]["color"] as Color).to_html(true) == Color(0.93, 0.32, 0.31).to_html(true),
			"el color se aplica al prim")

	var serializado := Prims.serializar_isla(c._prims[99], int(c._siguiente[99]), "UUID-PRUEBA")
	var releido := Prims.deserializar_isla(serializado)
	_check(int(releido["siguiente"]) == int(c._siguiente[99]), "el estado guardado conserva el contador")
	_check(releido["prims"].has(1), "el estado guardado incluye el prim")

	c._borrar()
	_check(not c._prims[99].has(1), "borrar elimina el prim del registro")
	_check(not c._nodos[99].has(1), "borrar elimina el nodo")

	var params_voxel := VoxelSuave.params_por_defecto("arco")
	var id_voxel: int = c._host_crear_prim(99, "voxel", Vector3(-4.0, 1.0, 2.0),
			Vector3.ZERO, Vector3.ONE, Color(0.66, 0.60, 0.52), params_voxel)
	_check(id_voxel > 0 and c._nodos[99].has(id_voxel), "el anfitrión instancia un terreno voxel")
	if id_voxel > 0:
		var nodo_voxel: Node3D = c._nodos[99][id_voxel]
		var malla_voxel := nodo_voxel.get_node_or_null("Malla") as MeshInstance3D
		var colision_voxel := nodo_voxel.get_node_or_null("Colision") as CollisionShape3D
		_check(malla_voxel != null and malla_voxel.mesh != null
				and malla_voxel.mesh.get_surface_count() == 1, "el terreno voxel tiene malla")
		_check(colision_voxel != null and colision_voxel.shape is ConcavePolygonShape3D,
				"el terreno voxel tiene colisión trimesh")
		_check(malla_voxel.material_override is StandardMaterial3D
				and (malla_voxel.material_override as StandardMaterial3D).vertex_color_use_as_albedo,
				"el terreno voxel usa el color por vértice")
		_check(str(c._prims[99][id_voxel]["params"]["forma"]) == "arco",
				"el registro conserva la forma del terreno")
		c._seleccionar(nodo_voxel)
		c._duplicar()
		var copia := -1
		for otro in c._prims[99]:
			if int(otro) != id_voxel and c._prims[99][otro]["tipo"] == "voxel":
				copia = int(otro)
		_check(copia > 0, "duplicar crea otro terreno voxel")
		if copia > 0:
			_check(c._prims[99][copia]["params"] == c._prims[99][id_voxel]["params"],
					"la copia conserva los parámetros del terreno")
			c._solicitar_borrado(99, copia)
		c._seleccionar(nodo_voxel)
		c._borrar()
		_check(not c._prims[99].has(id_voxel), "borrar elimina el terreno voxel")

	# ── Deshacer y guardar en inventario (v2.6.0) ──────────────────────
	_check(c._panel._btn_deshacer != null and c._panel._btn_deshacer.text == "Deshacer isla",
			"el panel ofrece Deshacer isla")
	_check(c._panel._lista_actual != null and c._panel._lista_guardado != null,
			"la pestaña Inventario tiene las dos listas")
	c._carpeta_inventario = "user://inventario_prueba"
	var terreno99 = c._terrenos[99]
	_check(terreno99.esta_editado(), "el pincel marca el terreno como esculpido")
	var id_inv: int = c._host_crear_prim(99, "cubo", Vector3(2.0, 1.0, 2.0),
			Vector3.ZERO, Vector3.ONE, Color.WHITE)
	_check(id_inv > 0, "hay un objeto para inventariar")
	c._guardar_en_inventario()
	var ruta_indice := "user://inventario_prueba/inventario.json"
	_check(FileAccess.file_exists(ruta_indice), "guardar en inventario crea el índice")
	var entradas := c._leer_entradas_inventario()
	_check(entradas.size() == 1, "el índice lista la copia guardada")
	if not entradas.is_empty():
		var entrada: Dictionary = entradas[0]
		_check(int(entrada.get("isla", -1)) == 99, "la copia guarda la isla")
		_check(bool(entrada.get("terreno", false)), "la copia marca el terreno")
		_check(int(entrada.get("assets", 0)) >= 1, "la copia cuenta los assets")
		_check(FileAccess.file_exists("user://inventario_prueba/%s" % str(entrada.get("archivo", ""))),
				"la copia tiene su propio archivo")
	c._refrescar_inventario()
	_check(c._panel._lista_actual.get_child_count() >= 3,
			"la pestaña lista el terreno y los objetos de la isla")
	_check(c._panel._lista_guardado.get_child_count() >= 3,
			"la pestaña lista la copia con sus etiquetas")

	c._deshacer_isla()
	_check(c._prims[99].is_empty(), "deshacer vacía los objetos")
	_check(not terreno99.esta_editado(), "deshacer restaura el estado original del terreno")
	_check(terreno99.vertices == terreno99.vertices_base, "deshacer devuelve las alturas base")
	_check(terreno99.colores == terreno99.colores_base, "deshacer devuelve los colores base")
	c._refrescar_inventario()
	_check(c._panel._lista_actual.get_child_count() >= 2,
			"tras deshacer la pestaña sigue describiendo la isla")

	# Limpieza: sólo los artefactos de esta prueba.
	var dir_inv := DirAccess.open("user://inventario_prueba")
	if dir_inv != null:
		for archivo in dir_inv.get_files():
			dir_inv.remove(archivo)
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://inventario_prueba"))
	for ruta_tmp in ["user://construccion/terreno_99_UUID-PRUEBA.bin",
			"user://construccion/prims_99_UUID-PRUEBA.json"]:
		if FileAccess.file_exists(ruta_tmp):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(ruta_tmp))

	c._bloquear_avatar(true)
	_check(avatar.get_meta("construccion_activa", false), "el modo construccion marca al avatar")
	_check(not avatar.control_avatar, "el avatar suelto no responde a flechas")
	c._bloquear_avatar(false)
	_check(not avatar.get_meta("construccion_activa", true), "al salir se retira la marca")
	_check(avatar.control_avatar, "al salir se devuelve el control sin otro clic")

	_check(c._validar_remitente(99, root.multiplayer.get_unique_id()), "el anfitrion puede editar")
	_check(not c._validar_remitente(99, 777), "un peer ajeno no puede editar")
	_check(not c._validar_remitente(123, 777), "una isla desconocida se rechaza")

	c._refrescar_estado_ui()
	_check(c._isla_actual() == 99, "_isla_actual usa my_own_index")

	c._sucio.clear()
	stub.free()
