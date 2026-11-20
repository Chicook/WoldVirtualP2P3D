extends Node
## Flujo: carrusel → editor de aspecto → isla.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	var boot := packed.instantiate()
	add_child(boot)
	await get_tree().create_timer(1.0).timeout
	boot.call("_on_avatar_confirmed", "res://avatares/AVMJ1.tscn")
	await get_tree().create_timer(1.5).timeout
	var editor = boot.get("_editor_aspecto")
	print("[flujo] editor=", editor)
	if editor == null:
		get_tree().quit(1)
		return
	editor.call("_guardar")
	await get_tree().create_timer(5.0).timeout
	var isla := get_tree().root.find_child("ISLA3Dblock", true, false)
	print("[flujo] isla=", isla)
	get_tree().quit(0 if isla != null else 1)
