extends Node
## Pregunta a LucIA por el socket 8765 y comprueba que responde.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(2.5).timeout
	var lucia := get_tree().root.find_child("LucIA", true, false)
	if lucia == null:
		print("[chat] no se encontró LucIA")
		get_tree().quit(1)
		return
	print("[chat] conectado=", lucia.get("_conectado"), " listo=", lucia.get("_esta_listo"))
	lucia.call("_al_enviar_texto", "¿Quién eres y para qué sirves?")
	for i in 60:
		await get_tree().create_timer(0.5).timeout
		var respuesta := str(lucia.get("_holo_respuesta"))
		if not respuesta.is_empty() and bool(lucia.get("_esta_listo")) and not bool(lucia.get("_enviando")):
			print("[chat] respuesta=", respuesta)
			get_tree().quit(0)
			return
	print("[chat] sin respuesta · holo=", str(lucia.get("_holo_respuesta")))
	get_tree().quit(1)
