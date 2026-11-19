extends SceneTree
## Renderiza una miniatura de cada avatar para revisarlos de un vistazo.
## Uso: python -m STM_HRTS ejecutar render_avatares
## Necesita ventana (el modo headless no dibuja). La salida va a %TEMP%/thumbs.

const CARPETAS := ["res://avtrnCRS/GTLF_GODOT/GltfIMP/AVATARES", "res://gltfimport/avatares"]
const ANCHO := 420
const ALTO := 640

var _pendientes: Array[String] = []
var _indice := 0
var _salida := ""
var _capa: Node3D
var _cam: Camera3D


func _initialize() -> void:
	_salida = OS.get_environment("RENDER_AVATARES_DIR")
	if _salida.is_empty():
		_salida = OS.get_user_data_dir().path_join("thumbs")
	DirAccess.make_dir_recursive_absolute(_salida)
	for carpeta in CARPETAS:
		_pendientes.append_array(_buscar(carpeta))
	var solo := OS.get_environment("RENDER_SOLO")
	if not solo.is_empty():
		var filtro := solo.split(",")
		var elegidos: Array[String] = []
		for ruta in _pendientes:
			for trozo in filtro:
				if ruta.get_file().get_basename() == trozo:
					elegidos.append(ruta)
		_pendientes = elegidos

	var entorno := WorldEnvironment.new()
	var mundo := Environment.new()
	mundo.background_mode = Environment.BG_COLOR
	mundo.background_color = Color(0.13, 0.14, 0.17)
	mundo.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	mundo.ambient_light_color = Color(0.75, 0.75, 0.8)
	mundo.ambient_light_energy = 1.4
	entorno.environment = mundo
	get_root().add_child(entorno)

	var sol := DirectionalLight3D.new()
	sol.rotation_degrees = Vector3(-38, 28, 0)
	sol.light_energy = 1.6
	get_root().add_child(sol)

	_capa = Node3D.new()
	get_root().add_child(_capa)
	if OS.get_environment("RENDER_PISO") == "1":
		# Suelo a y=0 y una regla de 1,8 m para comprobar dónde apoya el modelo.
		var suelo := MeshInstance3D.new()
		suelo.mesh = BoxMesh.new()
		(suelo.mesh as BoxMesh).size = Vector3(3, 0.02, 3)
		var mate := StandardMaterial3D.new()
		mate.albedo_color = Color(0.35, 0.35, 0.4)
		suelo.material_override = mate
		suelo.position = Vector3(0, -0.01, 0)
		get_root().add_child(suelo)
		var regla := MeshInstance3D.new()
		regla.mesh = BoxMesh.new()
		(regla.mesh as BoxMesh).size = Vector3(0.06, 1.8, 0.06)
		var mate_regla := StandardMaterial3D.new()
		mate_regla.albedo_color = Color(1, 0.75, 0.1)
		regla.material_override = mate_regla
		regla.position = Vector3(-0.9, 0.9, 0)
		get_root().add_child(regla)
	_cam = Camera3D.new()
	_cam.fov = 32
	get_root().add_child(_cam)
	get_root().size = Vector2i(ANCHO, ALTO)
	_correr()


func _buscar(carpeta: String) -> Array[String]:
	var salida: Array[String] = []
	var pila: Array[String] = [carpeta]
	while not pila.is_empty():
		var actual: String = pila.pop_back()
		var dir := DirAccess.open(actual)
		if dir == null:
			continue
		dir.list_dir_begin()
		var nombre := dir.get_next()
		while nombre != "":
			var ruta := actual.path_join(nombre)
			if dir.current_is_dir():
				pila.append(ruta)
			elif nombre.ends_with(".glb") or nombre.ends_with(".gltf"):
				# Si hay versión animada al lado, se usa esa (tiene las 5 animaciones).
				if not nombre.contains("_anim") and FileAccess.file_exists(
						ruta.get_basename() + "_anim.glb"):
					pass
				else:
					salida.append(ruta)
			nombre = dir.get_next()
		dir.list_dir_end()
	return salida


func _cargar(ruta: String) -> Node3D:
	var doc := GLTFDocument.new()
	var estado := GLTFState.new()
	if doc.append_from_file(ruta, estado) != OK:
		push_error("no se pudo leer " + ruta)
		return null
	return doc.generate_scene(estado) as Node3D


func _encuadrar(modelo: Node3D) -> void:
	if OS.get_environment("RENDER_FIJA") == "1":
		# Encuadre fijo: sirve para comparar el tamaño real entre modelos.
		_cam.position = Vector3(0, 1.3, 4.8)
		_cam.look_at(Vector3(0, 0.95, 0), Vector3.UP)
		return
	# En glTF el AABB del mesh va en espacio de esqueleto, así que el tamaño se
	# saca de la posición global de los huesos, que sí respeta la escala real.
	var esqueleto: Skeleton3D = null
	var cola: Array[Node] = [modelo]
	while not cola.is_empty():
		var nodo: Node = cola.pop_back()
		if nodo is Skeleton3D and esqueleto == null:
			esqueleto = nodo as Skeleton3D
		cola.append_array(nodo.get_children())
	if esqueleto == null:
		return
	var minimo := Vector3.INF
	var maximo := -Vector3.INF
	for i in esqueleto.get_bone_count():
		var pos := esqueleto.global_transform * esqueleto.get_bone_global_pose(i).origin
		minimo = minimo.min(pos)
		maximo = maximo.max(pos)
	var alto := maxf((maximo.y - minimo.y) * 1.15, 0.4)
	var centro := Vector3(minimo.x * 0.0, (minimo.y + maximo.y) * 0.5, 0.0)
	if OS.get_environment("RENDER_CARA") == "1":
		# Primer plano de la cara: se centra en el hueso Head.
		var indice := -1
		for i in esqueleto.get_bone_count():
			var nombre := esqueleto.get_bone_name(i)
			if nombre == "Head" or nombre.ends_with(":Head") or nombre.ends_with("_Head"):
				indice = i
				break
		if indice >= 0:
			var cabeza := esqueleto.global_transform * esqueleto.get_bone_global_pose(indice).origin
			_cam.position = cabeza + Vector3(0, alto * 0.02, alto * 0.28)
			_cam.look_at(cabeza, Vector3.UP)
			return
	# Los Mixamo miran hacia +Z, así que la cámara se pone delante (+Z).
	_cam.position = centro + Vector3(0, alto * 0.06, alto * 1.25)
	_cam.look_at(centro + Vector3(0, alto * 0.06, 0), Vector3.UP)


func _correr() -> void:
	# El primer frame hace falta para que la camara este dentro del arbol.
	await process_frame
	while not _pendientes.is_empty():
		var ruta: String = _pendientes.pop_front()
		var modelo := _cargar(ruta)
		if modelo == null:
			continue
		_capa.add_child(modelo)
		_encuadrar(modelo)
		var clip := OS.get_environment("RENDER_CLIP")
		if not clip.is_empty():
			for n in modelo.find_children("*", "AnimationPlayer", true, false):
				var ap := n as AnimationPlayer
				if ap.has_animation(clip):
					ap.play(clip)
					ap.seek(1.2, true)
					break
			for _i in 6:
				await process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var imagen := get_root().get_texture().get_image()
		_indice += 1
		var destino := _salida.path_join("%02d_%s.png" % [_indice, ruta.get_file().get_basename()])
		imagen.save_png(destino)
		print("RENDER ", destino)
		_capa.remove_child(modelo)
		modelo.queue_free()
		await process_frame
	quit()
