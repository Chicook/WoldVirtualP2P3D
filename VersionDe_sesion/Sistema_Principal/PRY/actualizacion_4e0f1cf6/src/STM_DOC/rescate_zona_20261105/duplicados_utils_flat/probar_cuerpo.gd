extends SceneTree
## Renderiza cuerpo completo: altura +30 cm, complexion, hombros, torso,
## brazos y piernas al maximo para revisar costuras y volumen.

const Pers = preload("res://gdscrip/Personalizacion.gd")

const RUTAS := [
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ6Ch3D.tscn",
]

const VARIANTES := {
	"0_original": {},
	"1_altura30": {"altura_cm": 30.0},
	"2_hombros": {"hombros": 1.15},
	"3_torso": {"torso": 1.15},
	"4_brazos": {"brazos": 1.15},
	"5_piernas": {"piernas": 1.15},
	"6_todo": {"altura_cm": 30.0, "ancho": 1.10, "cabeza": 1.10, "hombros": 1.15,
		"torso": 1.10, "brazos": 1.10, "piernas": 1.10},
}


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var carpeta := OS.get_environment("TEMP").path_join("pers")
	DirAccess.make_dir_recursive_absolute(carpeta)
	get_root().size = Vector2i(560, 800)

	var mundo := Node3D.new()
	get_root().add_child(mundo)

	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.09, 0.11, 0.15)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.8, 0.85, 0.95)
	env.ambient_light_energy = 0.7
	var we := WorldEnvironment.new()
	we.environment = env
	mundo.add_child(we)

	var luz := DirectionalLight3D.new()
	luz.rotation_degrees = Vector3(-32, 28, 0)
	luz.light_energy = 1.4
	mundo.add_child(luz)

	var cam := Camera3D.new()
	cam.fov = 32.0
	cam.position = Vector3(0, 1.3, 4.8)
	mundo.add_child(cam)
	cam.look_at(Vector3(0, 0.95, 0), Vector3.UP)
	cam.current = true

	for ruta in RUTAS:
		var nombre: String = str(ruta).get_file().get_basename()
		for clave_var in VARIANTES:
			await _capturar(mundo, cam, ruta, VARIANTES[clave_var],
				carpeta.path_join(nombre + "_cuerpo_" + clave_var + ".png"))
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
	print("CAPTURA ", destino, " altura=", Pers.altura_total(avatar))
	avatar.queue_free()
	await process_frame
