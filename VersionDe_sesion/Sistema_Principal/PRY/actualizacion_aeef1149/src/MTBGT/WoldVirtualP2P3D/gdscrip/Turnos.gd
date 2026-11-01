extends RefCounted
## Reserva exclusiva de los 24 avatares del carrusel.
##
## El turno es la pagina del carrusel a la que pertenece el avatar elegido:
## turno 1 = plazas 1-8, turno 2 = 9-16, turno 3 = 17-24. Un avatar solo puede
## estar reservado por un jugador a la vez; al liberarse, la plaza vuelve a estar
## disponible para el siguiente que entre. Con las 24 plazas ocupadas, los
## jugadores adicionales reutilizan su avatar en el turno 4.

const POR_TURNO := 8
const TURNOS := 3
const TURNO_RECICLADO := 4

## Mismo orden que `avatar_paths` de SLAV.tscn (lo comprueba probar_turnos.gd).
const AVATARES: Array[String] = [
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH1Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ1Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH2Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ2Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH3Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ3Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH4Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ4Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ5Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH6Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ6Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH7Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ7Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH8Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ8Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH9Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ9Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH10Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ10Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH11Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ11Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH12Ch3D.tscn",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ/AVMJ12Ch3D.tscn",
]

const NOMBRES: Array[String] = [
	"AVH1", "AVMJ1", "AVH2", "AVMJ2", "AVH3", "AVMJ3", "AVH4", "AVMJ4",
	"AVH5", "AVMJ5", "AVH6", "AVMJ6", "AVH7", "AVMJ7", "AVH8", "AVMJ8",
	"AVH9", "AVMJ9", "AVH10", "AVMJ10", "AVH11", "AVMJ11", "AVH12", "AVMJ12",
]


static func indice(ruta: String) -> int:
	return AVATARES.find(ruta)


static func nombre_de(i: int) -> String:
	return NOMBRES[i] if i >= 0 and i < NOMBRES.size() else ""


static func genero_de(i: int) -> String:
	if i < 0 or i >= NOMBRES.size():
		return ""
	return "mujer" if NOMBRES[i].begins_with("AVMJ") else "hombre"


## Turno 1-based; 0 si el indice no es valido.
static func turno_de(i: int) -> int:
	if i < 0 or i >= AVATARES.size():
		return 0
	return i / POR_TURNO + 1


static func primera_libre(ocupacion: Dictionary) -> int:
	for i in AVATARES.size():
		if not ocupacion.has(i):
			return i
	return -1


## Reserva `ruta` para `id`. Si ya la tiene otro, devuelve un sustituto del mismo
## genero (mismo turno -> siguiente -> siguiente -> vuelta). Si las 24 plazas
## estan ocupadas, devuelve la ruta pedida marcada como reciclada (turno 4) sin
## ocupar plaza. Devuelve {} si la ruta no pertenece al catalogo.
static func reservar(ocupacion: Dictionary, id: int, ruta: String) -> Dictionary:
	var pedido := indice(ruta)
	if pedido < 0:
		return {}
	# Un peer ocupa una sola plaza: si cambia de avatar, libera la anterior.
	for i in ocupacion.keys():
		if int(ocupacion[i]) == id and int(i) != pedido:
			ocupacion.erase(i)
	if not ocupacion.has(pedido) or int(ocupacion[pedido]) == id:
		ocupacion[pedido] = id
		return _asignacion(pedido, false)
	var sustituto := _sustituto(ocupacion, pedido)
	if sustituto >= 0:
		ocupacion[sustituto] = id
		return _asignacion(sustituto, false)
	return _asignacion(pedido, true)


## Libera todas las plazas de `id` y devuelve sus indices.
static func liberar(ocupacion: Dictionary, id: int) -> Array:
	var liberadas := []
	for i in ocupacion.keys():
		if int(ocupacion[i]) == id:
			liberadas.append(int(i))
	for i in liberadas:
		ocupacion.erase(i)
	return liberadas


## Descarta reservas de jugadores que ya no estan conectados (p. ej. IDs viejos
## tras una migracion de anfitrion).
static func limpiar(ocupacion: Dictionary, conectados: Dictionary) -> void:
	for i in ocupacion.keys():
		if not conectados.has(int(ocupacion[i])):
			ocupacion.erase(i)


static func _sustituto(ocupacion: Dictionary, pedido: int) -> int:
	var turno_pedido := pedido / POR_TURNO
	var orden_turnos := []
	for k in TURNOS:
		orden_turnos.append((turno_pedido + k) % TURNOS)
	var genero := genero_de(pedido)
	for filtrar_genero in [true, false]:
		for t in orden_turnos:
			var mejor := -1
			var mejor_dist := 1 << 30
			var inicio: int = int(t) * POR_TURNO
			var fin: int = mini(inicio + POR_TURNO, AVATARES.size())
			for i in range(inicio, fin):
				if ocupacion.has(i):
					continue
				if filtrar_genero and genero_de(i) != genero:
					continue
				var d := absi(i - pedido)
				if d < mejor_dist:
					mejor_dist = d
					mejor = i
			if mejor >= 0:
				return mejor
	return -1


static func _asignacion(i: int, reciclado: bool) -> Dictionary:
	return {
		"ruta": AVATARES[i],
		"indice": i,
		"nombre": NOMBRES[i],
		"turno": TURNO_RECICLADO if reciclado else turno_de(i),
		"reciclado": reciclado,
	}
