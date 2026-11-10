extends SceneTree
## Renderiza primeros planos del rostro original y con cada rasgo al maximo,
## para ajustar anclajes y radios de la deformacion.

const Pers = preload("res://gdscrip/Personalizacion.gd")

const RUTAS := [
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ6Ch3D.tscn",
]

const VARIANTES := {
	"0_original": {},
	"1_nariz": {"nariz": 1.0},
	"2_labios": {"labios": 1.0},
	"3_orejas": {"orejas": 1.0},
	"4_ojos": {"ojos": 1.0},
	"5_todo": {"nariz": 1.0, "labios": 1.0, "orejas": 1.0, "ojos": 1.0},
}


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var carpeta := OS.get_environment("TEMP").path_join("pers")
	DirAccess.make_dir_recursive_absolute(carpeta)
	get_root().size = Vector2i(640, 640)

	var mundo := Node3D.new()
	get_root().add_child(mundo)

	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.08, 0.10, 0.14)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.85, 0.88, 0.95)
	env.ambient_light_energy = 0.9
	var we := WorldEnvironment.new()
	we.environment = env
	mundo.add_child(we)

	var clave := DirectionalLight3D.new()
	clave.rotation_degrees = Vector3(-25, 20, 0)
	clave.light_energy = 1.5
	mundo.add_child(clave)
	var relleno := DirectionalLight3D.new()
	relleno.rotation_degrees = Vector3(-10, -160, 0)
	relleno.light_energy = 0.5
	mundo.add_child(relleno)

	var cam := Camera3D.new()
	cam.fov = 30.0
	cam.position = Vector3(0, 1.645, 0.78)
	mundo.add_child(cam)
	cam.look_at(Vector3(0, 1.635, 0), Vector3.UP)
	cam.current = true

	for ruta in RUTAS:
		var nombre: String = str(ruta).get_file().get_basename()
		for clave_var in VARIANTES:
			await _capturar(mundo, cam, ruta, VARIANTES[clave_var],
				carpeta.path_join(nombre + "_" + clave_var + ".png"))
		cam.position = Vector3(0.50, 1.70, 0.62)
		cam.look_at(Vector3(0, 1.63, 0), Vector3.UP)
		for clave_var in ["0_original", "1_nariz", "5_todo"]:
			await _capturar(mundo, cam, ruta, VARIANTES[clave_var],
				carpeta.path_join(nombre + "_lado_" + clave_var + ".png"))
		cam.position = Vector3(0, 1.645, 0.78)
		cam.look_at(Vector3(0, 1.635, 0), Vector3.UP)
	quit()


func _capturar(mundo: Node3D, cam: Camera3D, ruta: String, extra: Dictionary, destino: String) -> void:
	var avatar := (load(ruta) as PackedScene).instantiate() as Node3D
	mundo.add_child(avatar)
	avatar.position = Vector3.ZERO
	avatar.set_physics_process(false)
	for c in avatar.find_children("*", "Camera3D", true, false):
		(c as Camera3D).current = false
	cam.current = true
	for ap in avatar.find_children("*", "AnimationPlayer", true, false):
		(ap as AnimationPlayer).play("paradoMJ1_1")
	var datos := Pers.POR_DEFECTO.duplicate()
	for k in extra:
		datos[k] = extra[k]
	Pers.aplicar(avatar, datos)
	await create_timer(0.5).timeout
	get_root().get_texture().get_image().save_png(destino)
	print("CAPTURA ", destino)
	avatar.queue_free()
	await process_frame
