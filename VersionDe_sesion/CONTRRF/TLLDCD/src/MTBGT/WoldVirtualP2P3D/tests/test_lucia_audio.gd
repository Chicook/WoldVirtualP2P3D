extends Node
## Comprueba que LucIA devuelve audio y que el cliente lo reproduce.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(2.5).timeout
	var lucia := get_tree().root.find_child("LucIA", true, false)
	if lucia == null:
		print("[audio] no LucIA")
		get_tree().quit(1)
		return
	lucia.call("_al_enviar_texto", "Hola LucIA, ¿me oyes?")
	for i in 30:
		await get_tree().create_timer(1.0).timeout
		print("[audio] t=", i + 1, " enviando=", lucia.get("_enviando"),
			" sonando=", lucia.get("_audio_sonando"),
			" restante=", lucia.get("_voz_restante"),
			" holo=", str(lucia.get("_holo_respuesta")).left(40))
		if not bool(lucia.get("_enviando")) and not bool(lucia.get("_audio_sonando")):
			break
	get_tree().quit(0)
