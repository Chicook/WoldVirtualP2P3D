extends Node
## Captura el carrusel para revisión visual.
##   godot --path <proyecto> res://tests/captura_carrusel.tscn --resolution 1280x720

func _ready() -> void:
	var packed := load("res://avatares/CarruselAvatares.tscn") as PackedScene
	var carrusel := packed.instantiate()
	add_child(carrusel)
	carrusel.call("_ir_a", 1, true)
	await get_tree().create_timer(4.0).timeout
	var imagen := get_viewport().get_texture().get_image()
	var destino := "user://captura_carrusel.png"
	var error := imagen.save_png(destino)
	print("[captura] ", destino, " error=", error, " tamaño=", imagen.get_size())
	get_tree().quit(0 if error == OK else 1)
