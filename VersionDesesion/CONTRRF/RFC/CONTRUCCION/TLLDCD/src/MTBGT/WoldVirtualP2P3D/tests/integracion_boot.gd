extends Node
## Integración: arranca Boot como jugador ya registrado y comprueba la isla.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(12.0).timeout
	var isla := get_tree().root.find_child("ISLA3Dblock", true, false)
	print("[integra] isla=", isla)
	if isla != null:
		var jugador: Node = isla.get_node_or_null("USERBASE")
		print("[integra] USERBASE=", jugador)
		if jugador is Node3D:
			print("[integra] pos=", (jugador as Node3D).global_position)
			print("[integra] escena=", (jugador as Node3D).scene_file_path)
			print("[integra] altura modelo=", (jugador as Node3D).get_meta("avatar_id", "?"))
	var imagen := get_viewport().get_texture().get_image()
	var destino := "user://captura_integracion.png"
	var error := imagen.save_png(destino)
	print("[integra] captura error=", error)
	get_tree().quit(0)
