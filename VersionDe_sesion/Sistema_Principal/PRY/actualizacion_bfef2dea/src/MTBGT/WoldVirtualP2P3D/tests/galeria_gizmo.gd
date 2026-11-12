extends Node3D
## Galería del manipulador de ejes: muestra los tres modos (mover/girar/escalar)
## con sus colores X rojo / Y verde / Z azul, estilo Second Life.

const GizmoManipulador = preload("res://gdscrip/GizmoManipulador.gd")

func _ready() -> void:
	var nombres := ["Mover", "Girar", "Escalar"]
	for i in 3:
		var g := GizmoManipulador.new()
		add_child(g)
		g.set_modo(i)
		g.global_position = Vector3(i * 3.0, 0.0, 0.0)
		g.scale = Vector3(1.7, 1.7, 1.7)
		var ref := MeshInstance3D.new()
		var caja := BoxMesh.new()
		caja.size = Vector3(0.5, 0.5, 0.5)
		ref.mesh = caja
		add_child(ref)
		ref.global_position = Vector3(i * 3.0, 0.0, 0.0)
		var l := Label3D.new()
		l.text = nombres[i]
		l.position = Vector3(i * 3.0, 1.9, 0.0)
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		add_child(l)
	var luz := DirectionalLight3D.new()
	luz.rotation_degrees = Vector3(-50.0, -30.0, 0.0)
	add_child(luz)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.07, 0.08, 0.11)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.6, 0.62, 0.7)
	env.environment = e
	add_child(env)
	var cam := Camera3D.new()
	add_child(cam)
	cam.position = Vector3(3.0, 4.0, 9.0)
	cam.look_at(Vector3(3.0, 0.0, 0.0), Vector3.UP)
	cam.current = true