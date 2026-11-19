extends SceneTree

var frames := 0

func _initialize() -> void:
	var escena: PackedScene = load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIA_Interfaz.tscn")
	root.add_child(escena.instantiate())

func _process(_delta: float) -> bool:
	frames += 1
	if frames >= 30:
		quit()
	return false
