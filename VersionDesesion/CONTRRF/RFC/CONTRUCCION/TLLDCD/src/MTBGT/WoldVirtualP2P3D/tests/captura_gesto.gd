extends Node
## Captura a LucIA a mitad del gesto de saludo (2,4 s).

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(2.4).timeout
	var imagen := get_viewport().get_texture().get_image()
	var destino := "user://captura_lucia_gesto.png"
	print("[captura-gesto] error=", imagen.save_png(destino))
	get_tree().quit(0)
