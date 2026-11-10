extends Node
## Tests del generador paramétrico de prims (PrimGeometria) y de su integración
## con Prims (malla, colisión y serialización v1/v2).

const PrimGeometria = preload("res://gdscrip/PrimGeometria.gd")
const Prims = preload("res://gdscrip/Prims.gd")

const TIPOS := ["cubo", "cilindro", "cono", "esfera", "toro"]


func test_neutros() -> void:
	assert(PrimGeometria.params_neutros({}), "vacío debe ser neutro")
	assert(PrimGeometria.params_neutros(PrimGeometria.HUELLAS), "huellas debe ser neutro")
	assert(not PrimGeometria.params_neutros({"corte_ini": 0.25}), "corte no es neutro")
	assert(not PrimGeometria.params_neutros({"hueco": 0.5}), "hueco no es neutro")
	assert(not PrimGeometria.params_neutros({"giro": 90.0}), "giro no es neutro")


func test_normalizar_sanea() -> void:
	var p := PrimGeometria.normalizar({
		"corte_ini": -1.0, "corte_fin": 5.0, "hueco": 9.0, "giro": 1000.0,
		"estrechado_x": -4.0, "cizalla_y": 3.0,
	})
	assert(is_equal_approx(float(p["corte_ini"]), 0.0), "corte_ini clamp")
	assert(is_equal_approx(float(p["corte_fin"]), 1.0), "corte_fin clamp")
	assert(float(p["hueco"]) <= 0.95, "hueco clamp")
	assert(absf(float(p["giro"])) <= 360.0, "giro clamp")
	assert(absf(float(p["estrechado_x"])) <= 1.0, "estrechado clamp")
	assert(absf(float(p["cizalla_y"])) <= 1.0, "cizalla clamp")
	for k in PrimGeometria.CLAVES:
		assert(p.has(k), "falta clave %s" % k)


func test_genera_todos_los_tipos() -> void:
	for t in TIPOS:
		var malla := PrimGeometria.generar(t, {"corte_ini": 0.2, "hueco": 0.3})
		assert(malla.get_surface_count() == 1, "%s sin superficie" % t)
		var verts = malla.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		assert(verts.size() >= 12, "%s con muy pocos vértices" % t)
		assert(malla.get_aabb().size.length() > 0.1, "%s AABB degenerada" % t)


func test_normales_validas() -> void:
	for t in TIPOS:
		var malla := PrimGeometria.generar(t, {"corte_ini": 0.0, "corte_fin": 0.5, "hueco": 0.4})
		var arr = malla.surface_get_arrays(0)
		var nrm: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		for n in nrm:
			assert(not is_nan(n.x) and not is_nan(n.y) and not is_nan(n.z),
					"%s normal NaN" % t)
			assert(absf(n.length() - 1.0) < 0.01, "%s normal no unitaria" % t)


## Una malla cerrada bien orientada encierra volumen positivo. Si sale negativo,
## las caras están invertidas (hay que voltear el generador).
func test_orientacion_volumen() -> void:
	for t in ["cubo", "cilindro", "esfera", "toro"]:
		var malla := PrimGeometria.generar(t, {})
		var vol := _volumen(malla)
		assert(vol > 0.0, "%s con volumen negativo (%.4f): caras invertidas" % [t, vol])


func test_hueco_anade_geometria() -> void:
	var solido := PrimGeometria.generar("cilindro", {})
	var hueco := PrimGeometria.generar("cilindro", {"hueco": 0.5})
	var v_solido = solido.surface_get_arrays(0)[Mesh.ARRAY_VERTEX].size()
	var v_hueco = hueco.surface_get_arrays(0)[Mesh.ARRAY_VERTEX].size()
	assert(v_hueco > v_solido, "el hueco debe añadir pared interior")


func test_prims_primitiva_vs_forma() -> void:
	assert(Prims.crear_malla("cubo", {}) is BoxMesh, "neutro usa primitiva rápida")
	assert(Prims.crear_malla("cubo", PrimGeometria.HUELLAS) is BoxMesh, "huellas usa primitiva")
	assert(Prims.crear_malla("cubo", {"corte_ini": 0.3}) is ArrayMesh, "corte usa generador")
	assert(Prims.crear_forma("cilindro", {"hueco": 0.4}) is ConcavePolygonShape3D,
			"forma usa colisión trimesh")


func test_serializacion_ida_vuelta() -> void:
	var datos := {
		"id": 3, "tipo": "cilindro",
		"pos": Vector3(1, 2, 3), "rot": Vector3(0, 45, 0), "escala": Vector3(2, 2, 2),
		"color": Color(1, 0, 0),
		"params": {"hueco": 0.4, "giro": 90.0, "corte_ini": 0.2},
	}
	var j := Prims.a_dict(datos)
	assert(j.has("params"), "los params no neutros deben guardarse")
	var vuelta := Prims.desde_dict(j)
	assert(absf(float(vuelta["params"]["hueco"]) - 0.4) < 1e-4, "hueco no sobrevive")
	assert(absf(float(vuelta["params"]["giro"]) - 90.0) < 1e-4, "giro no sobrevive")
	assert(absf(float(vuelta["params"]["corte_ini"]) - 0.2) < 1e-4, "corte no sobrevive")


func test_serializacion_neutro_sin_params() -> void:
	var datos := {
		"id": 1, "tipo": "cubo", "pos": Vector3.ZERO, "rot": Vector3.ZERO,
		"escala": Vector3.ONE, "color": Color(1, 1, 1),
		"params": PrimGeometria.HUELLAS,
	}
	var j := Prims.a_dict(datos)
	assert(not j.has("params"), "un prim neutro no debe arrastrar params")
	assert(not j.has("nombre") and not j.has("phantom"), "sin propiedades por defecto")


func test_propiedades_ida_vuelta() -> void:
	var datos := {
		"id": 2, "tipo": "cubo", "pos": Vector3.ZERO, "rot": Vector3.ZERO,
		"escala": Vector3.ONE, "color": Color(1, 1, 1), "params": {},
		"nombre": "Torre", "phantom": true, "temporal": true,
	}
	var j := Prims.a_dict(datos)
	assert(str(j.get("nombre", "")) == "Torre", "el nombre debe guardarse")
	assert(bool(j.get("phantom", false)), "phantom debe guardarse")
	var back := Prims.desde_dict(j)
	assert(str(back["nombre"]) == "Torre", "el nombre debe volver")
	assert(bool(back["phantom"]) and bool(back["temporal"]), "los flags deben volver")


func test_deserializar_versiones() -> void:
	var v1 := '{"version":1,"siguiente":2,"uuid":"x","prims":[{"id":1,"tipo":"cubo","pos":[0,0,0],"rot":[0,0,0],"escala":[1,1,1],"color":"#ffffff"}]}'
	assert(not Prims.deserializar_isla(v1).is_empty(), "v1 debe seguir cargando")
	var v2 := '{"version":2,"siguiente":2,"uuid":"x","prims":[{"id":1,"tipo":"cilindro","pos":[0,0,0],"rot":[0,0,0],"escala":[1,1,1],"color":"#ffffff","params":{"hueco":0.5}}]}'
	var leido := Prims.deserializar_isla(v2)
	assert(not leido.is_empty(), "v2 debe cargar")
	assert(absf(float(leido["prims"][1]["params"]["hueco"]) - 0.5) < 1e-4,
			"v2 debe conservar params")
	assert(Prims.deserializar_isla('{"version":9}').is_empty(), "versión futura se rechaza")


func _volumen(malla: ArrayMesh) -> float:
	var arr := malla.surface_get_arrays(0)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var vol := 0.0
	for t in range(0, verts.size(), 3):
		var a := verts[t]
		var b := verts[t + 1]
		var c := verts[t + 2]
		vol += a.dot(b.cross(c)) / 6.0
	return vol