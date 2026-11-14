extends SceneTree

## Render del mÃ³dulo nuevo (procedural sobre rig Mixamo) para ver el estado real.

var personaje: LuciaPersonaje
var cam: Camera3D
var salida := "res://_pruebas/despues/"
var escenarios: Array = []
var indice := 0
var espera := 0

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(salida))
	var esc: PackedScene = load("res://GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn")
	personaje = esc.instantiate()
	get_root().add_child(personaje)
	await process_frame
	await process_frame

	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.09, 0.10, 0.13)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.75, 0.80, 0.90)
	e.ambient_light_energy = 0.55
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	get_root().add_child(env)

	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-28, 28, 0)
	key.light_energy = 1.9
	key.shadow_enabled = true
	get_root().add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-10, -60, 0)
	fill.light_energy = 0.7
	fill.light_color = Color(0.75, 0.85, 1.0)
	get_root().add_child(fill)
	var rim := OmniLight3D.new()
	rim.position = Vector3(0.4, 1.9, -1.2)
	rim.light_energy = 1.4
	get_root().add_child(rim)

	cam = Camera3D.new()
	cam.fov = 32.0
	cam.current = true
	get_root().add_child(cam)
	get_root().size = Vector2i(760, 1060)

	personaje.set_process(false)
	_crear_escenarios()
	_aplicar()

func _crear_escenarios() -> void:
	var completo := {"pos": Vector3(0.0, 0.95, 3.1), "mira": Vector3(0.0, 0.88, 0.0), "fov": 32.0}
	var retrato := {"pos": Vector3(0.0, 1.55, 0.95), "mira": Vector3(0.0, 1.52, 0.0), "fov": 30.0}
	var medio := {"pos": Vector3(0.0, 1.25, 1.85), "mira": Vector3(0.0, 1.20, 0.0), "fov": 32.0}

	escenarios = [
		{"n": "01_reposo_t0", "cam": completo, "f": func() -> void: _pose(0.0, 0.0, 0.0)},
		{"n": "02_reposo_t3", "cam": completo, "f": func() -> void: _pose(3.0, 0.0, 0.0)},
		{"n": "03_hablando_t1", "cam": medio, "f": func() -> void: _pose(1.0, 1.0, 0.0)},
		{"n": "04_hablando_t26", "cam": medio, "f": func() -> void: _pose(2.6, 1.0, 0.0)},
		{"n": "05_boca_abierta", "cam": retrato, "f": func() -> void:
			_pose(0.0, 0.0, 0.0)
			personaje.fijar_apertura_boca(1.0)},
		{"n": "06_boca_cerrada", "cam": retrato, "f": func() -> void: _pose(0.0, 0.0, 0.0)},
		{"n": "07_parpadeo", "cam": retrato, "f": func() -> void:
			_pose(0.0, 0.0, 0.08)
			personaje.fijar_apertura_boca(0.0)},
		{"n": "08_cabeza_giro_boca", "cam": retrato, "f": func() -> void:
			_pose(0.0, 0.0, 0.0)
			personaje._poner("cabeza", Quaternion(Vector3.UP, 0.35) * Quaternion(Vector3.RIGHT, 0.05))
			personaje.esqueleto.force_update_all_bone_transforms()
			personaje.fijar_apertura_boca(0.8)},
		{"n": "09_gesto_amplio", "cam": medio, "f": func() -> void:
			_pose(2.0, 1.0, 0.0)},
		{"n": "10_cabeza_giro", "cam": retrato, "f": func() -> void:
			_pose(0.0, 0.0, 0.0)
			personaje._poner("cabeza", Quaternion(Vector3.UP, 0.35))
			personaje.esqueleto.force_update_all_bone_transforms()
	]

func _pose(t: float, gesto: float, blink: float) -> void:
	personaje.fijar_apertura_boca(0.0)
	personaje._t = t
	personaje._peso_gesto = gesto
	personaje._blink_restante = blink
	personaje._aplicar_pose()
	personaje.esqueleto.force_update_all_bone_transforms()

func _aplicar() -> void:
	if indice >= escenarios.size():
		print("FIN despues: ", escenarios.size())
		quit()
		return
	var e: Dictionary = escenarios[indice]
	var c: Dictionary = e["cam"]
	cam.global_position = c["pos"]
	cam.look_at(c["mira"])
	cam.fov = c["fov"]
	espera = 6
	(e["f"] as Callable).call()
	print("capturando ", e["n"])

func _process(_d: float) -> bool:
	if personaje == null:
		return false
	if espera > 0:
		espera -= 1
		if espera == 1:
			var img := get_root().get_texture().get_image()
			img.save_png(salida + (escenarios[indice]["n"] as String) + ".png")
		if espera == 0:
			indice += 1
			_aplicar()
	return false
