extends Node
## Captura la recepción de LucIA con el modelo ya resuelto.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(6.0).timeout
	var imagen := get_viewport().get_texture().get_image()
	var destino := "user://captura_recepcion.png"
	var error := imagen.save_png(destino)
	print("[captura-recepcion] ", destino, " error=", error)
	get_tree().quit(0 if error == OK else 1)
