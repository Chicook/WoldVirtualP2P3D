extends Node
## Test de integración del camino de aplicación de forma en Construccion:
## _norm_params y _rehacer_prim (regenera malla y colisión en el nodo existente).

const Construccion = preload("res://gdscrip/Construccion.gd")
const Prims = preload("res://gdscrip/Prims.gd")
const PanelConstruccion = preload("res://gdscrip/ConstructorPanel.gd")


func _nodo_prim(tipo: String) -> StaticBody3D:
	var cuerpo := StaticBody3D.new()
	var malla := MeshInstance3D.new()
	malla.name = "Malla"
	malla.mesh = Prims.crear_malla(tipo, {})
	malla.material_override = Prims.crear_material(Color.WHITE)
	cuerpo.add_child(malla)
	var col := CollisionShape3D.new()
	col.name = "Colision"
	col.shape = Prims.crear_forma(tipo, {})
	cuerpo.add_child(col)
	return cuerpo


func test_norm_params() -> void:
	var c = Construccion.new()
	var forma = c._norm_params("cubo", {"hueco": 2.0})
	assert(float(forma["hueco"]) <= 0.95, "el hueco debe sanearse")
	var voxel = c._norm_params("voxel", {"forma": "isla", "radio": 5.0})
	assert(voxel.has("forma"), "el voxel usa el saneado de VoxelSuave")
	c.free()


func test_rehacer_prim_regenera_malla_y_colision() -> void:
	var c = Construccion.new()
	var cuerpo := _nodo_prim("cilindro")
	c._nodos = {0: {1: cuerpo}}
	var datos := {
		"id": 1, "tipo": "cilindro", "pos": Vector3.ZERO, "rot": Vector3.ZERO,
		"escala": Vector3.ONE, "color": Color.WHITE, "params": {"hueco": 0.5},
	}
	c._rehacer_prim(0, 1, datos)
	var malla := cuerpo.get_node("Malla") as MeshInstance3D
	assert(malla.mesh is ArrayMesh, "la malla no se regeneró con la forma")
	var col := cuerpo.get_node("Colision") as CollisionShape3D
	assert(col.shape is ConcavePolygonShape3D, "la colisión no se regeneró")
	cuerpo.free()
	c.free()


func test_forma_neutra_vuelve_a_primitiva() -> void:
	var c = Construccion.new()
	var cuerpo := _nodo_prim("cilindro")
	c._nodos = {0: {1: cuerpo}}
	c._rehacer_prim(0, 1, {"id": 1, "tipo": "cilindro", "color": Color.WHITE, "params": {"hueco": 0.5}})
	c._rehacer_prim(0, 1, {"id": 1, "tipo": "cilindro", "color": Color.WHITE, "params": {}})
	var malla := cuerpo.get_node("Malla") as MeshInstance3D
	assert(malla.mesh is CylinderMesh, "con forma neutra debe volver a la primitiva")
	cuerpo.free()
	c.free()


func test_rehacer_prim_aplica_propiedades() -> void:
	var c = Construccion.new()
	var cuerpo := _nodo_prim("cubo")
	c._nodos = {0: {1: cuerpo}}
	c._rehacer_prim(0, 1, {"id": 1, "tipo": "cubo", "color": Color.WHITE, "params": {},
			"phantom": true, "temporal": true})
	var col := cuerpo.get_node("Colision") as CollisionShape3D
	assert(col.disabled, "phantom debe desactivar la colisión")
	var malla := cuerpo.get_node("Malla") as MeshInstance3D
	var mat := malla.material_override as StandardMaterial3D
	assert(mat != null and mat.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA,
			"temporal debe dibujarse translúcido")
	cuerpo.free()
	c.free()


func test_panel_refleja_y_emite_forma() -> void:
	var panel := PanelConstruccion.new()
	add_child(panel) # dispara _ready: construye la UI con la sección FORMA
	assert(panel._sliders_forma.has("hueco"), "la sección FORMA debe tener sliders")
	panel.set_forma_ui({"hueco": 0.6, "corte_ini": 0.25})
	assert(absf(float(panel._sliders_forma["hueco"].value) - 0.6) < 0.001,
			"el slider de hueco no refleja el valor")
	assert(absf(float(panel._sliders_forma["corte_ini"].value) - 0.25) < 0.001,
			"el slider de corte no refleja el valor")
	panel.set_forma_ui({})
	assert(absf(float(panel._sliders_forma["hueco"].value)) < 0.001,
			"forma neutra pone el hueco a 0")
	var recibidos: Array = []
	panel.forma_solicitada.connect(func(params): recibidos.append(params))
	panel._restablecer_forma()
	assert(recibidos.size() == 1, "restablecer debe emitir la forma neutra")
	remove_child(panel)
	panel.free()