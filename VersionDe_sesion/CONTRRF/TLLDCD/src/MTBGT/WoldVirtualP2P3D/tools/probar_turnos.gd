extends SceneTree
## Prueba la reserva exclusiva de los 24 avatares por turnos, sin red.

const Turnos = preload("res://gdscrip/Turnos.gd")
const SLAV := "res://SLCAV/AVATARESCONANIMACION/SLAV.tscn"

var _fallos := 0


func _initialize() -> void:
	_correr()


func _check(cond: bool, texto: String) -> void:
	if cond:
		print("OK    ", texto)
	else:
		print("FALLO ", texto)
		_fallos += 1


func _correr() -> void:
	await process_frame

	_check(Turnos.AVATARES.size() == 24 and Turnos.NOMBRES.size() == 24, "catalogo de 24 avatares")
	_check(Turnos.indice(Turnos.AVATARES[17]) == 17, "indice inverso")
	_check(Turnos.turno_de(0) == 1 and Turnos.turno_de(7) == 1, "plazas 1-8 son turno 1")
	_check(Turnos.turno_de(8) == 2 and Turnos.turno_de(23) == 3, "plazas 9-24 son turnos 2 y 3")
	_check(Turnos.turno_de(-1) == 0, "turno invalido devuelve 0")

	var alterna := true
	for i in Turnos.NOMBRES.size():
		if Turnos.NOMBRES[i].begins_with("AVH") == (i % 2 == 1):
			alterna = false
	_check(alterna, "alternancia chico/chica del catalogo")

	# El catalogo debe seguir el mismo orden que las escenas jugables del carrusel.
	var carrusel = (load(SLAV) as PackedScene).instantiate()
	var rutas_ok: bool = carrusel.playable_scenes.size() == Turnos.AVATARES.size()
	if rutas_ok:
		for i in Turnos.AVATARES.size():
			if str(carrusel.playable_scenes[i]) != Turnos.AVATARES[i]:
				print("  ruta %d: SLAV=%s | Turnos=%s" % [i, carrusel.playable_scenes[i], Turnos.AVATARES[i]])
				rutas_ok = false
	_check(rutas_ok, "catalogo = playable_scenes de SLAV")
	_check(carrusel.avatar_names == Turnos.NOMBRES, "nombres = avatar_names de SLAV")
	_check(int(carrusel.per_turn) == Turnos.POR_TURNO, "per_turn = 8")
	carrusel.free()

	# 24 jugadores con avatares distintos: todos exclusivos y en su turno.
	var ocupacion := {}
	var usados := {}
	for id in range(1, 25):
		var a: Dictionary = Turnos.reservar(ocupacion, id, Turnos.AVATARES[id - 1])
		if a.is_empty() or str(a["ruta"]) != Turnos.AVATARES[id - 1] or bool(a["reciclado"]):
			_check(false, "reserva directa del jugador %d (%s)" % [id, Turnos.NOMBRES[id - 1]])
		usados[str(a.get("ruta", ""))] = true
	_check(ocupacion.size() == 24 and usados.size() == 24, "24 reservas exclusivas sin duplicados")

	# Avatar ocupado: sustituto del mismo genero y del mismo turno si hay hueco.
	var o2 := {}
	Turnos.reservar(o2, 1, Turnos.AVATARES[0])
	var s1: Dictionary = Turnos.reservar(o2, 2, Turnos.AVATARES[0])
	_check(str(s1.get("ruta", "")) == Turnos.AVATARES[2], "sustituto cercano en el mismo turno (AVH2)")
	_check(Turnos.genero_de(int(s1.get("indice", -1))) == "hombre", "sustituto del mismo genero")

	# Turno lleno para ese genero: pasa al siguiente turno.
	var o3 := {}
	for i in [0, 2, 4, 6]:
		Turnos.reservar(o3, 10 + i, Turnos.AVATARES[i])
	var s2: Dictionary = Turnos.reservar(o3, 20, Turnos.AVATARES[0])
	_check(str(s2.get("ruta", "")) == Turnos.AVATARES[8] and int(s2.get("turno", 0)) == 2,
			"turno 1 lleno -> primer avatar del turno 2 (AVH5)")

	# Al desconectarse un jugador su plaza vuelve a estar disponible.
	var o4 := {}
	Turnos.reservar(o4, 1, Turnos.AVATARES[0])
	Turnos.reservar(o4, 2, Turnos.AVATARES[1])
	var liberadas := Turnos.liberar(o4, 1)
	_check(liberadas.size() == 1 and int(liberadas[0]) == 0, "liberar deja libre la plaza de AVH1")
	var s3: Dictionary = Turnos.reservar(o4, 3, Turnos.AVATARES[0])
	_check(str(s3.get("ruta", "")) == Turnos.AVATARES[0] and int(s3.get("turno", 0)) == 1,
			"el siguiente jugador reutiliza el hueco liberado")

	# Redeclarar el mismo avatar no ocupa una plaza nueva.
	var o5 := {}
	Turnos.reservar(o5, 1, Turnos.AVATARES[0])
	var rep: Dictionary = Turnos.reservar(o5, 1, Turnos.AVATARES[0])
	_check(str(rep.get("ruta", "")) == Turnos.AVATARES[0] and o5.size() == 1, "redeclarar conserva la plaza")

	# Cambiar de avatar mueve la plaza: un peer no puede ocupar dos.
	var o5b := {}
	Turnos.reservar(o5b, 7, Turnos.AVATARES[0])
	Turnos.reservar(o5b, 7, Turnos.AVATARES[2])
	_check(not o5b.has(0) and int(o5b.get(2, -1)) == 7 and o5b.size() == 1,
			"cambiar de avatar libera la plaza anterior")

	# 24 plazas ocupadas: el jugador 25 recicla su avatar en el turno 4.
	var o6 := {}
	for i in 24:
		Turnos.reservar(o6, i + 1, Turnos.AVATARES[i])
	var r: Dictionary = Turnos.reservar(o6, 30, Turnos.AVATARES[3])
	_check(bool(r.get("reciclado", false)) and int(r.get("turno", 0)) == Turnos.TURNO_RECICLADO,
			"jugador 25 entra reciclado en el turno 4")
	_check(str(r.get("ruta", "")) == Turnos.AVATARES[3] and o6.size() == 24,
			"reciclar conserva el avatar pedido sin ocupar plaza nueva")

	# IDs que ya no estan conectados (migracion) liberan su plaza.
	var o7 := {0: 99, 2: 1}
	Turnos.limpiar(o7, {1: true})
	_check(not o7.has(0) and o7.has(2), "limpiar descarta IDs desconectados")

	_check(Turnos.reservar({}, 1, "res://no_existe.tscn").is_empty(), "ruta fuera del catalogo rechazada")

	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)
