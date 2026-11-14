extends SceneTree

var personaje: Node3D
var oficina: Node3D
var cam: Camera3D
var frames := 0

func _initialize() -> void:
	var escena: PackedScene = load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn")
	personaje = escena.instantiate()
	root.add_child(personaje)

	oficina = LuciaOficina.new()
	oficina.name = "Oficina"
	root.add_child(oficina)

	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.10, 0.12, 0.18)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.75, 0.8, 0.9)
	e.ambient_light_energy = 0.7
	env.environment = e
	root.add_child(env)

	var luz := DirectionalLight3D.new()
	luz.rotation_degrees = Vector3(-45, 35, 0)
	luz.light_energy = 1.0
	root.add_child(luz)

	var relleno := OmniLight3D.new()
	relleno.position = Vector3(0.6, 1.6, 1.5)
	relleno.light_energy = 1.2
	relleno.light_color = Color(0.6, 0.7, 1.0)
	root.add_child(relleno)

	cam = Camera3D.new()
	cam.current = true
	cam.fov = 38.0
	root.add_child(cam)

func _process(_delta: float) -> bool:
	frames += 1
	if frames == 2:
		var idle: AnimationPlayer = personaje.get_node_or_null("AnimIdle")
		if idle:
			idle.stop()
	elif frames == 4:
		_encuadrar()
	elif frames == 14:
		_disparar("res://.godot/skin_oficina.png")
		quit()
	return false

func _encuadrar() -> void:
	var aabb: AABB = personaje.obtener_aabb_mundo()
	var centro := aabb.get_center()
	var altura := aabb.size.y
	var dist := (altura * 1.3) / (2.0 * tan(deg_to_rad(cam.fov) * 0.5))
	dist = maxf(dist, 0.8)
	cam.global_position = Vector3(centro.x, centro.y + altura * 0.06, aabb.position.z + aabb.size.z * 0.5 + dist)
	cam.look_at(Vector3(centro.x, centro.y + altura * 0.02, aabb.get_center().z))

func _disparar(ruta: String) -> void:
	var img := root.get_texture().get_image()
	img.save_png(ruta)
	print("guardado: ", ruta)
