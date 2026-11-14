extends Node
## Envía dos consultas seguidas con el cliente real de LucIA.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(2.5).timeout
	var lucia := get_tree().root.find_child("LucIA", true, false)
	if lucia == null:
		print("[dos] no LucIA")
		get_tree().quit(1)
		return
	for n in [1, 2]:
		print("[dos] enviando ", n, " listo=", lucia.get("_esta_listo"),
			" conectado=", lucia.get("_conectado"))
		lucia.call("_al_enviar_texto", "Hola LucIA, consulta numero %d." % n)
		var espera := 0.0
		while espera < 25.0:
			await get_tree().create_timer(0.5).timeout
			espera += 0.5
			if not bool(lucia.get("_enviando")) and not bool(lucia.get("_audio_sonando")):
				break
		print("[dos] fin ", n, " enviando=", lucia.get("_enviando"),
			" listo=", lucia.get("_esta_listo"),
			" conectado=", lucia.get("_conectado"),
			" holo=", str(lucia.get("_holo_respuesta")).left(50))
		await get_tree().create_timer(1.0).timeout
	get_tree().quit(0)
