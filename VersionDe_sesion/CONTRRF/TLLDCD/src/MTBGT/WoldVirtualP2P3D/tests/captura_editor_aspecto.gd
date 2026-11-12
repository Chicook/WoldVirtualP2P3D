extends Node
## Captura el editor de aspecto para revisión visual.

func _ready() -> void:
	var packed := load("res://avatares/EditorAspecto.tscn") as PackedScene
	var editor := packed.instantiate()
	editor.call("set_avatar", "AVMJ1")
	editor.call("set_nick", "ChicookFarrior")
	add_child(editor)
	await get_tree().create_timer(4.0).timeout
	var imagen := get_viewport().get_texture().get_image()
	var destino := "user://captura_editor_aspecto.png"
	print("[captura-editor] error=", imagen.save_png(destino))
	get_tree().quit(0)
