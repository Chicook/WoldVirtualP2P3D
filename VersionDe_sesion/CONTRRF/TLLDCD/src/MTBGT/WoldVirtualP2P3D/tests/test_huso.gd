extends Node
## Test de huso (spindle/threaded rod style prim)
## Un huso en Second Life es como un cono con taper y shear para simular
## un eje con cabeza hexagonal o forma de rosca.

const PrimGeometria = preload("res://gdscrip/PrimGeometria.gd")
const Prims = preload("res://gdscrip/Prims.gd")


func test_huso_cono_base() -> void:
	"""Un cono simple debe generar malla válida."""
	var malla := PrimGeometria.generar("cono", {})
	assert(malla.get_surface_count() == 1, "cono tiene 1 superficie")
	var verts = malla.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	assert(verts.size() >= 12, "cone con suficientes vértices (%d)" % verts.size())
	print("✓ cono base: %d vertices" % verts.size())


func test_huso_con_taper() -> void:
	"""Un huso con taper en X (engrosado hacia la base)"""
	var malla := PrimGeometria.generar("cono", {
		"estrechado_x": 0.7,  # más estrecho en X
		"cizalla_x": 0.0,
	})
	assert(malla.get_surface_count() == 1, "cono con taper tiene superficie")
	var verts = malla.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	assert(verts.size() >= 12, "cono con taper tiene vértices (%d)" % verts.size())
	# Verificar que hay variación de vértices (taper afecta el tamaño)
	var aabb := malla.get_aabb()
	assert(aabb.size.length() > 0.1, "AABB no degenerada")
	print("✓ cono con taper: %d vertices, AABB: %.2f x %.2f x %.2f" % [
		verts.size(), aabb.size.x, aabb.size.y, aabb.size.z])


func test_huso_con_shear() -> void:
	"""Un huso con cizalla para simular forma de rosca."""
	var malla := PrimGeometria.generar("cono", {
		"cizalla_x": 0.3,
		"cizalla_y": 0.1,
		"estrechado_x": 0.5,
		"estrechado_y": 0.5,
	})
	assert(malla.get_surface_count() == 1, "cono con shear tiene superficie")
	var verts = malla.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	assert(verts.size() >= 12, " cono con shear tiene vértices (%d)" % verts.size())
	var nrm = malla.surface_get_arrays(0)[Mesh.ARRAY_NORMAL]
	for n in nrm:
		assert(not is_nan(n.x) and not is_nan(n.y) and not is_nan(n.z),
				"normal no NaN en huso con shear")
	print("✓ cono con shear: %d vertices, normals válidas" % verts.size())


func test_huso_serializacion() -> void:
	"""Test round-trip de un huso con parámetros complejos."""
	var datos := {
		"id": 5, "tipo": "cono",
		"pos": Vector3.ZERO, "rot": Vector3.ZERO, "escala": Vector3.ONE,
		"color": Color(0.8, 0.6, 0.4),  # color madera/metal
		"params": {
			"hueco": 0.1,      # ligeramente hueco (como tubo delgado)
			"giro": 270.0,     # 3/4 de vuelta como una espiral
			"corte_ini": 0.1,  # corte en la base
			"corte_fin": 0.9,  # corte en la punta
			"estrechado_x": 0.5,  # tapered (más estrecho)
			"cizalla_x": 0.2,   # shear
		},
	}
	var j := Prims.a_dict(datos)
	assert(j.has("params"), "params deben guardarse")
	assert(j.has("nombre") == false, "sin nombre por defecto")
	
	var vuelta := Prims.desde_dict(j)
	assert(str(vuelta["tipo"]) == "cono", "tipo debe volverse cono")
	assert(absf(float(vuelta["params"]["hueco"]) - 0.1) < 0.01, "hueco survive: %.4f" % vuelta["params"]["hueco"])
	assert(absf(float(vuelta["params"]["giro"]) - 270.0) < 1.0, "giro survive: %.1f" % vuelta["params"]["giro"])
	assert(absf(float(vuelta["params"]["corte_ini"]) - 0.1) < 0.01, "corte_ini survive: %.4f" % vuelta["params"]["corte_ini"])
	assert(absf(float(vuelta["params"]["corte_fin"]) - 0.9) < 0.01, "corte_fin survive: %.4f" % vuelta["params"]["corte_fin"])
	assert(absf(float(vuelta["params"]["estrechado_x"]) - 0.5) < 0.01, "estrechado survive: %.4f" % vuelta["params"]["estrechado_x"])
	assert(absf(float(vuelta["params"]["cizalla_x"]) - 0.2) < 0.01, "cizalla survive: %.4f" % vuelta["params"]["cizalla_x"])
	print("✓ serialización huso ida/vuelta exitosa")


func test_huso_versus_primitiva_rapida() -> void:
	"""Un cono con params debe usar el generador, no la primitiva rápida."""
	var malla := Prims.crear_malla("cono", {"hueco": 0.3, "giro": 180.0})
	assert(malla is ArrayMesh, "cono con params debe usar generador (ArrayMesh), no BoxMesh")
	print("✓ cono con params usa generador (ArrayMesh)")


func test_huso_con_historial() -> void:
	"""Test que un huso se registre en el historial de construcción."""
	# Esto es más un test de integración, verificamos que la estructura
	# de datos es compatible con lo que espera Construccion.gd
	var datos := {
		"id": 1, "tipo": "cono",
		"pos": Vector3(10, 0, 0), "rot": Vector3.ZERO, "escala": Vector3(1, 1, 1),
		"color": Color(0.8, 0.8, 0.8),
		"params": {"hueco": 0.2, "giro": 45.0},
	}
	# Verificamos que a_dict y desde_dict funcionan
	var j := Prims.a_dict(datos)
	assert(j.has("params"), "params incluidas")
	var restored := Prims.desde_dict(j)
	assert(str(restored["tipo"]) == "cono", "tipo restaurado")
	var params_ok = absf(float(restored["params"]["hueco"]) - 0.2) < 0.01
	assert(params_ok, "params hueco restaurados correctly")
	print("✓ huso compatible con estructura de Construccion.gd")


func _es_neutro(params: Dictionary) -> bool:
	"""Verifica si los params son todos valores por defecto."""
	return PrimGeometria.params_neutros(params)


# Para poder ejecutar individualmente desde Godot:
# func _test_all_huso() -> void:
# 	test_huso_cono_base()
# 	test_huso_con_taper()
# 	test_huso_con_shear()
# 	test_huso_serializacion()
# 	test_huso_versus_primitiva_rapida()
# 	test_huso_con_historial()
# 	print("\n=== Todos los tests de huso PASARON ===")