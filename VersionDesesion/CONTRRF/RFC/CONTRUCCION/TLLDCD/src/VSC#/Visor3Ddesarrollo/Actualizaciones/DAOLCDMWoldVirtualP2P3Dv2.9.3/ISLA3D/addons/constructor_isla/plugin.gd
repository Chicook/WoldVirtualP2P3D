@tool
extends EditorPlugin
## Guarda la escena que se está construyendo en Godot y la marca para que el
## visor la coloque en la isla del jugador.

var _panel: VBoxContainer
var _dialogo_importar: EditorFileDialog

func _enter_tree() -> void:
	set_process(true)
	_preparar_isla3d()
	_panel = VBoxContainer.new()
	_panel.name = "ConstruccionIsla"
	var titulo := Label.new()
	titulo.text = "Construcción → Isla"
	_panel.add_child(titulo)
	var boton := Button.new()
	boton.text = "Llevar lo construido a mi isla"
	boton.custom_minimum_size = Vector2(280, 36)
	boton.pressed.connect(_guardar_para_isla)
	_panel.add_child(boton)
	var importar := Button.new()
	importar.text = "📂 Importar carpeta del PC"
	importar.custom_minimum_size = Vector2(280, 32)
	importar.pressed.connect(_abrir_importar)
	_panel.add_child(importar)
	add_control_to_bottom_panel(_panel, "Construcción → Isla")


func _preparar_isla3d() -> void:
	var carpeta := ProjectSettings.globalize_path("res://ISLA3D")
	DirAccess.make_dir_recursive_absolute(carpeta)
	var escena := "res://ISLA3D/isla.tscn"
	if not FileAccess.file_exists(escena):
		var raiz := Node3D.new()
		raiz.name = "ISLA3D"
		var packed := PackedScene.new()
		packed.pack(raiz)
		ResourceSaver.save(packed, escena)
		raiz.free()


func _exit_tree() -> void:
	if _panel:
		remove_control_from_bottom_panel(_panel)
		_panel.queue_free()
		_panel = null


func _process(delta: float) -> void:
	# Solo guardar cuando el visor lo pide. El autoguardado periódico
	# reemplazaba mallas/materiales cada 2 s y provocaba parpadeos al editar
	# shaders.
	if FileAccess.file_exists("user://construccion_guardar.solicitud"):
		DirAccess.remove_absolute(ProjectSettings.globalize_path("user://construccion_guardar.solicitud"))
		_guardar_escena(true)


func _guardar_para_isla() -> void:
	_guardar_escena(true)


func _abrir_importar() -> void:
	if _dialogo_importar == null:
		_dialogo_importar = EditorFileDialog.new()
		_dialogo_importar.file_mode = EditorFileDialog.FILE_MODE_OPEN_DIR
		_dialogo_importar.access = EditorFileDialog.ACCESS_FILESYSTEM
		_dialogo_importar.title = "Importar carpeta de Godot al metaverso"
		_dialogo_importar.dir_selected.connect(_importar_carpeta)
		EditorInterface.get_base_control().add_child(_dialogo_importar)
	_dialogo_importar.popup_centered_ratio(0.72)


func _importar_carpeta(origen: String) -> void:
	if origen.is_empty():
		return
	var nombre := origen.get_file()
	if nombre.is_empty():
		nombre = "importado"
	nombre = nombre.validate_filename()
	var destino := "res://ISLA3D/importado/%s" % nombre
	_copiar_carpeta(origen, ProjectSettings.globalize_path(destino))
	EditorInterface.get_resource_filesystem().scan()
	print("[Construcción] Carpeta importada en ", destino)


func _copiar_carpeta(origen: String, destino: String) -> void:
	DirAccess.make_dir_recursive_absolute(destino)
	var dir := DirAccess.open(origen)
	if dir == null:
		return
	for archivo in dir.get_files():
		dir.copy_absolute(origen.path_join(archivo), destino.path_join(archivo))
	for sub in dir.get_directories():
		if sub == ".godot" or sub == ".import":
			continue
		_copiar_carpeta(origen.path_join(sub), destino.path_join(sub))


func _guardar_escena(escribir_marca: bool) -> void:
	var raiz := EditorInterface.get_edited_scene_root()
	if raiz == null:
		if escribir_marca:
			push_warning("[Construcción] Abre o crea una escena antes de guardarla.")
		return
	# Incrustar materiales, shaders y texturas para que la escena no dependa
	# de archivos res:// del proyecto vacío del editor.
	_embeber_recursos(raiz)
	var escena := PackedScene.new()
	var error := escena.pack(raiz)
	if error != OK:
		if escribir_marca:
			push_error("[Construcción] No se pudo empaquetar la escena: %s" % error)
		return
	var ruta := "user://isla_construida.tscn"
	error = ResourceSaver.save(escena, ruta)
	if error != OK:
		if escribir_marca:
			push_error("[Construcción] No se pudo guardar: %s" % error)
		return
	if escribir_marca:
		var marca := FileAccess.open("user://construccion_lista.flag", FileAccess.WRITE)
		if marca:
			marca.store_string(ruta)
			marca.close()
		print("[Construcción] Escena guardada para la isla: ", ruta)


func _embeber_recursos(nodo: Node) -> void:
	if nodo is MeshInstance3D:
		var mi := nodo as MeshInstance3D
		if mi.mesh != null:
			var malla := mi.mesh.duplicate(true) as Mesh
			if malla != null:
				for i in malla.get_surface_count():
					var mat := malla.surface_get_material(i)
					if mat != null:
						malla.surface_set_material(i, _material_local(mat))
				malla.resource_path = ""
				mi.mesh = malla
	if nodo is CSGMesh3D:
		var csg := nodo as CSGMesh3D
		if csg.mesh != null:
			var malla_csg := csg.mesh.duplicate(true) as Mesh
			if malla_csg != null:
				for i in malla_csg.get_surface_count():
					var mat_csg := malla_csg.surface_get_material(i)
					if mat_csg != null:
						malla_csg.surface_set_material(i, _material_local(mat_csg))
				malla_csg.resource_path = ""
				csg.mesh = malla_csg
	if nodo is GeometryInstance3D:
		var gi := nodo as GeometryInstance3D
		gi.material_override = _material_local(gi.material_override)
		gi.material_overlay = _material_local(gi.material_overlay)
		if "material" in gi:
			gi.set("material", _material_local(gi.get("material")))
	for hijo in nodo.get_children():
		_embeber_recursos(hijo)


func _material_local(mat: Material) -> Material:
	if mat == null:
		return null
	var copia := mat.duplicate(true) as Material
	if copia == null:
		return mat
	copia.resource_path = ""
	if copia is ShaderMaterial:
		var sm := copia as ShaderMaterial
		if sm.shader != null:
			var shader := sm.shader.duplicate(true) as Shader
			if shader != null:
				if shader.resource_path.begins_with("res://"):
					# Guardar el shader en user:// para que el visor pueda
					# cargarlo aunque el proyecto del editor esté en otro sitio.
					DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("user://shaders"))
					var destino_shader := "user://shaders/%s" % shader.resource_path.get_file()
					if ResourceSaver.save(shader, destino_shader) == OK:
						shader.resource_path = destino_shader
					else:
						shader.resource_path = ""
				else:
					shader.resource_path = ""
				sm.shader = shader
	for prop in copia.get_property_list():
		if prop.type == TYPE_OBJECT:
			var valor = copia.get(prop.name)
			if valor is Texture2D and not valor.resource_path.is_empty():
				var textura := valor.duplicate(true) as Texture2D
				if textura != null:
					textura.resource_path = ""
					copia.set(prop.name, textura)
	return copia
