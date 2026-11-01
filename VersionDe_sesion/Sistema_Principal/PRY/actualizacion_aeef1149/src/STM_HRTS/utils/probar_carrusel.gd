extends SceneTree
## Prueba el carrusel de SLAV.tscn: alternancia estricta, 3 turnos de 8 y
## salto de turno al pasar del octavo avatar.

const RUTA := "res://SLCAV/AVATARESCONANIMACION/SLAV.tscn"


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var escena: PackedScene = load(RUTA)
	var carrusel := escena.instantiate()
	get_root().add_child(carrusel)
	await process_frame
	var nombres: Array = carrusel.avatar_names
	var fallos := 0
	for i in nombres.size():
		var es_hombre: bool = nombres[i].begins_with("AVH")
		if es_hombre == (i % 2 == 1):
			print("FALLO alternancia en ", i, ": ", nombres[i])
			fallos += 1
	print("alternancia: ", "OK" if fallos == 0 else "FALLO")
	for i in nombres.size():
		await process_frame
		print("paso %2d | %s | %s | avatares=%d" % [
			i, carrusel._name_label.text, carrusel._counter.text, carrusel._avatars.size()])
		if i < nombres.size() - 1:
			carrusel._move(1)
	print("== fin, fallos=%d ==" % fallos)
	quit(1 if fallos > 0 else 0)
