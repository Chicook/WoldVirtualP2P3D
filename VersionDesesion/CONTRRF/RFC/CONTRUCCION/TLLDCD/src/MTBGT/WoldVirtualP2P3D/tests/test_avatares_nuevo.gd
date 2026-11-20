extends Node
## Prueba de humo del módulo nuevo de avatares.
##   godot --headless --path <proyecto> res://tests/test_avatares_nuevo.tscn

const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

var _fallos: Array[String] = []


func _ready() -> void:
	await get_tree().process_frame
	print("==============================================")
	print(" TEST AVATARES NUEVOS")
	print("==============================================")
	_probar_catalogo()
	await _probar_escenas()
	await _probar_carrusel()
	print("----------------------------------------------")
	if _fallos.is_empty():
		print(" RESULTADO: OK")
		get_tree().quit(0)
	else:
		for f in _fallos:
			print(" FALLO: ", f)
		print(" RESULTADO: %d fallo(s)" % _fallos.size())
		get_tree().quit(1)


func _comprobar(condicion: bool, mensaje: String) -> void:
	if not condicion:
		_fallos.append(mensaje)
		print("  [X] ", mensaje)
	else:
		print("  [ok] ", mensaje)


func _probar_catalogo() -> void:
	print("\n[1] Catálogo")
	_comprobar(Catalogo.total() == 8, "hay 8 avatares (hay %d)" % Catalogo.total())
	for i in Catalogo.total():
		var m: Dictionary = Catalogo.por_indice(i)
		var id := str(m["id"])
		_comprobar(not id.is_empty(), "id del avatar %d" % i)
		_comprobar(ResourceLoader.exists(str(m["escena"])), "escena de %s existe" % id)
		_comprobar(ResourceLoader.exists(str(m["ruta"])), "glTF de %s existe" % id)
		_comprobar(Catalogo.id_de_ruta(str(m["escena"])) == id, "vuelta id<->ruta de %s" % id)


func _probar_escenas() -> void:
	print("\n[2] Escenas jugables")
	for i in Catalogo.total():
		var m: Dictionary = Catalogo.por_indice(i)
		var id := str(m["id"])
		var nodo: Node3D = Catalogo.crear(id)
		_comprobar(nodo != null, "%s se instancia" % id)
		if nodo == null:
			continue
		add_child(nodo)
		await get_tree().process_frame
		var jugador: Node = nodo
		_comprobar(jugador.get_script() != null, "%s usa script propio" % id)
		if jugador != null:
			var modelo = jugador.get("modelo")
			var animador = jugador.get("animador")
			_comprobar(modelo != null, "%s tiene modelo" % id)
			_comprobar(animador != null, "%s tiene AnimationPlayer" % id)
			_comprobar(nodo.get_node_or_null("ColisionAvatar") != null, "%s tiene cápsula" % id)
			if animador != null:
				var anims = animador.get_animation_list()
				_comprobar(anims.has(Catalogo.ANIM_IDLE), "%s tiene animación idle" % id)
			if modelo != null:
				var altura := float(modelo.get_meta("avatar_altura", 0.0))
				_comprobar(absf(altura - 1.8) < 0.25, "%s mide %.2f m" % [id, altura])
		nodo.queue_free()
		await get_tree().process_frame


func _probar_carrusel() -> void:
	print("\n[3] Carrusel")
	var packed := load("res://avatares/CarruselAvatares.tscn") as PackedScene
	_comprobar(packed != null, "carrusel carga")
	if packed == null:
		return
	var carrusel := packed.instantiate()
	add_child(carrusel)
	await get_tree().process_frame
	await get_tree().process_frame
	_comprobar(carrusel.get_node_or_null("Pivote") != null, "carrusel tiene pivote")
	_comprobar(carrusel.get_node_or_null("UI") != null, "carrusel tiene interfaz")
	var avatares: Array = carrusel.get("_avatares")
	_comprobar(avatares.size() == 8, "carrusel monta 8 avatares (monta %d)" % avatares.size())
	carrusel.call("_ir_a", 3, true)
	await get_tree().process_frame
	var indice := int(carrusel.get("_indice"))
	_comprobar(indice == 3, "el carrusel enfoca el índice 3")
	carrusel.call("_confirmar")
	await get_tree().process_frame
	var esperado := str(Catalogo.por_indice(3)["id"])
	_comprobar(Avatares.id_actual == esperado, "se guardó %s (guardado %s)" % [esperado, Avatares.id_actual])
	var cfg := ConfigFile.new()
	_comprobar(cfg.load("user://registro.cfg") == OK, "registro.cfg se escribe")
	if cfg.load("user://registro.cfg") == OK:
		var ruta := str(cfg.get_value("jugador", "avatar_scene", ""))
		_comprobar(ruta == str(Catalogo.por_indice(3)["escena"]), "registro apunta al avatar elegido")
	carrusel.queue_free()
	await get_tree().process_frame
