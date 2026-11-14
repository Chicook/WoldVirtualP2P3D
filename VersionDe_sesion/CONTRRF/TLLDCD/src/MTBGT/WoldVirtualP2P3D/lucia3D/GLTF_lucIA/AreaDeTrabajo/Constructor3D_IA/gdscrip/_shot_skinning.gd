extends SceneTree

var cam: Camera3D
var personaje: Node
var frames := 0

func _initialize() -> void:
	var escena: PackedScene = load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn")
	personaje = escena.instantiate()
	root.add_child(personaje)

	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.10, 0.12, 0.18)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.75, 0.8, 0.9)
	e.ambient_light_energy = 0.9
	env.environment = e
	root.add_child(env)

	var luz := DirectionalLight3D.new()
	luz.rotation_degrees = Vector3(-45, 35, 0)
	luz.light_energy = 1.3
	root.add_child(luz)

	var relleno := OmniLight3D.new()
	relleno.position = Vector3(0.6, 1.4, 1.2)
	relleno.light_energy = 2.0
	relleno.light_color = Color(0.55, 0.65, 1.0)
	root.add_child(relleno)

	cam = Camera3D.new()
	cam.current = true
	cam.fov = 38.0
	root.add_child(cam)

func _process(_delta: float) -> bool:
	frames += 1
	if frames == 1:
		_congelar_idle()
	elif frames == 3:
		cam.global_position = Vector3(0.0, 0.9, 3.0)
		cam.look_at(Vector3(0.0, 0.85, 0.0))
	elif frames == 12:
		_disparar("res://.godot/skin_reposo.png")
	elif frames == 20:
		_aplicar_gesto()
	elif frames == 30:
		_disparar("res://.godot/skin_gesto.png")
		_diferenciar("res://.godot/skin_reposo.png", "res://.godot/skin_gesto.png")
		print("--- PERFIL REPOSO ---")
		_perfil("res://.godot/skin_reposo.png")
		print("--- PERFIL GESTO ---")
		_perfil("res://.godot/skin_gesto.png")
		quit()
	return false

func _congelar_idle() -> void:
	var anim: AnimationPlayer = personaje.get_node_or_null("AnimIdle")
	if anim:
		anim.stop()
	var lucia: Node3D = personaje.get_node("LucIA")
	lucia.transform = Transform3D.IDENTITY

func _esqueleto() -> Skeleton3D:
	return personaje.get_node("LucIA/cuerpo/Esqueleto")

func _aplicar_gesto() -> void:
	var esq := _esqueleto()
	esq.set_bone_pose_rotation(esq.find_bone("hombroD"), Quaternion(Vector3(0, 0, 1), 1.4))
	esq.set_bone_pose_rotation(esq.find_bone("brazoD"), Quaternion(Vector3(0, 0, 1), 1.6))
	esq.set_bone_pose_rotation(esq.find_bone("hombroI"), Quaternion(Vector3(0, 0, 1), -1.4))
	esq.set_bone_pose_rotation(esq.find_bone("brazoI"), Quaternion(Vector3(0, 0, 1), -1.6))

func _disparar(ruta: String) -> void:
	var img := root.get_texture().get_image()
	img.save_png(ruta)
	print("guardado: ", ruta)

func _diferenciar(a: String, b: String) -> void:
	var ia := Image.load_from_file(a)
	var ib := Image.load_from_file(b)
	var cambios := 0
	var minx := 99999
	var maxx := -1
	var miny := 99999
	var maxy := -1
	for y in ia.get_height():
		for x in ia.get_width():
			var pa: Color = ia.get_pixel(x, y)
			var pb: Color = ib.get_pixel(x, y)
			var d := absf(pa.r - pb.r) + absf(pa.g - pb.g) + absf(pa.b - pb.b)
			if d > 0.02:
				cambios += 1
				minx = mini(minx, x)
				maxx = maxi(maxx, x)
				miny = mini(miny, y)
				maxy = maxi(maxy, y)
	print("DIF: cambios=", cambios, " bbox x[", minx, ",", maxx, "] y[", miny, ",", maxy, "]")

func _perfil(ruta: String) -> void:
	var img := Image.load_from_file(ruta)
	var fondo: Color = img.get_pixel(5, 5)
	var h := img.get_height()
	var w := img.get_width()
	var paso := 40
	for y in range(0, h, paso):
		var mn := -1
		var mx := -1
		for x in w:
			var c: Color = img.get_pixel(x, y)
			var d := absf(c.r - fondo.r) + absf(c.g - fondo.g) + absf(c.b - fondo.b)
			if d > 0.05:
				if mn < 0:
					mn = x
				mx = x
		if mn >= 0:
			print("  y=", y, " x[", mn, ",", mx, "] ancho=", mx - mn)
