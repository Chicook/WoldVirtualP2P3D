extends SceneTree
## Prueba la ocupacion en el carrusel (Fase B): abre en el primer hueco, salta
## plazas reservadas, no confirma una plaza ajena y recicla si las 24 estan
## ocupadas.

const RUTA := "res://SLCAV/AVATARESCONANIMACION/SLAV.tscn"

var _fallos := 0


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var carrusel = load(RUTA).instantiate()

	# Antes de entrar al arbol: plazas 0, 1 y 3 ocupadas -> abre en la 2.
	carrusel.set_ocupados([0, 1, 3])
	carrusel.abrir_en_primer_hueco()
	_check(carrusel._index == 2, "abre en el primer hueco (indice 2)")

	get_root().add_child(carrusel)
	await process_frame
	_check(carrusel._index == 2, "conserva el hueco tras montar el turno")
	_check(carrusel._avatars.size() == 8, "turno 1 monta 8 avatares")
	_check(carrusel._name_label.text.find("OCUPADO") == -1, "el hueco elegido no esta marcado")

	# Flecha derecha: 2 -> 4 (salta la 3 ocupada).
	carrusel._move(1)
	_check(carrusel._index == 4, "la flecha derecha salta la plaza ocupada 3")
	# Flecha izquierda: 4 -> 2 (salta la 3 otra vez).
	carrusel._move(-1)
	_check(carrusel._index == 2, "la flecha izquierda salta la plaza ocupada 3")

	# Forzar una plaza ocupada no permite confirmar.
	var confirmados := [0]
	carrusel.avatar_confirmed.connect(func(_ruta: String) -> void: confirmados[0] += 1)
	carrusel._ir_a(1, true)
	_check(carrusel._name_label.text.find("OCUPADO") != -1, "la plaza ocupada se anuncia en pantalla")
	carrusel._confirm()
	_check(confirmados[0] == 0, "no se confirma una plaza reservada por otro")

	# Etiquetas 3D sobre los avatares ocupados del turno montado.
	var marcas := 0
	for i in carrusel._avatars.size():
		if carrusel._avatars[i].get_node_or_null("Ocupado") != null:
			marcas += 1
	_check(marcas == 3, "tres etiquetas OCUPADO en el turno 1")

	# Con huecos libres se puede confirmar un avatar libre (indice 2).
	carrusel._ir_a(2, true)
	carrusel._confirm()
	_check(confirmados[0] == 1, "un hueco libre si se confirma")

	# Los 24 ocupados: modo reciclaje, sin saltos y con aviso en el contador.
	var todos := []
	for i in 24:
		todos.append(i)
	carrusel.set_ocupados(todos)
	carrusel.abrir_en_primer_hueco()
	await process_frame
	_check(carrusel._reciclando, "24 ocupados activa el modo reciclaje")
	_check(carrusel._index == 0, "reciclando abre en el primer avatar")
	_check(carrusel._counter.text.find("reciclando") != -1, "el contador avisa del reciclaje")
	carrusel._move(1)
	_check(carrusel._index == 1, "reciclando permite avanzar a plazas ocupadas")

	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK   ", texto)
	else:
		_fallos += 1
		print("FALLO ", texto)
