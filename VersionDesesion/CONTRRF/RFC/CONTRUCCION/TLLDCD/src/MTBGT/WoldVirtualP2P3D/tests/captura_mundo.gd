extends Node
## Captura la isla con el avatar elegido para revisar el spawn.
##   godot --path <proyecto> res://tests/captura_mundo.tscn --resolution 1280x720

func _ready() -> void:
	var packed := load("res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn") as PackedScene
	var mundo := packed.instantiate()
	add_child(mundo)
	var id := Avatares.id_actual
	if id.is_empty():
		id = "AVMJ2"
	mundo.call("set_player_avatar", "res://avatares/%s.tscn" % id)
	print("[captura-mundo] avatar=", id)
	await get_tree().create_timer(7.0).timeout
	var jugador := mundo.get_node_or_null("USERBASE")
	print("[captura-mundo] USERBASE=", jugador, " clase=", jugador.get_class() if jugador else "null",
		" pos=", (jugador as Node3D).global_position if jugador is Node3D else "?")
	var imagen := get_viewport().get_texture().get_image()
	var destino := "user://captura_mundo.png"
	var error := imagen.save_png(destino)
	print("[captura-mundo] ", destino, " error=", error, " tamaño=", imagen.get_size())
	get_tree().quit(0 if error == OK else 1)
