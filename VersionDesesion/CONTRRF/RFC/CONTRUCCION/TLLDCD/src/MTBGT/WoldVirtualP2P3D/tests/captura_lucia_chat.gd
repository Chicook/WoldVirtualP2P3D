extends Node
## Envía una pregunta a LucIA y captura la respuesta en pantalla.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(2.5).timeout
	var lucia := get_tree().root.find_child("LucIA", true, false)
	if lucia:
		lucia.call("_al_enviar_texto", "¿Quién eres y en qué puedes ayudarme?")
	await get_tree().create_timer(9.0).timeout
	if lucia:
		print("[captura-chat] enviando=", lucia.get("_enviando"), " holo=", str(lucia.get("_holo_respuesta")))
	var imagen := get_viewport().get_texture().get_image()
	print("[captura-chat] error=", imagen.save_png("user://captura_lucia_chat.png"))
	get_tree().quit(0)
