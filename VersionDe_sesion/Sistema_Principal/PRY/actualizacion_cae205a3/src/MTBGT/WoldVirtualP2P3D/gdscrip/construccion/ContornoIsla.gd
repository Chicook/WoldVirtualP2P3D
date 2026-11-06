extends RefCounted
## Mayor círculo de tierra firme alrededor de un punto de una isla.
##
## Lanza rayos verticales contra el terreno propio en varias direcciones y se
## queda con el radio que cabe en todas. Cada dirección se resuelve de fuera
## hacia dentro con pasos gruesos y un refinado binario: ~600 rayos en vez de
## los ~7 600 de recorrer el radio entero a 0,5 m, sin cambio apreciable en la
## medida (el paso fino solo afina el último metro).

const DIRECCIONES := 24
const PASO_GRUESO := 1.0
const REFINADOS := 3
const RADIO_MINIMO := 0.75


## `centro` va en metros de isla; la malla del glTF está escalada ~100x, así que
## la conversión se hace aquí. Devuelve 0 si alguna dirección no toca tierra.
func medir(espacio: PhysicsDirectSpaceState3D, malla: MeshInstance3D, escala: float,
		agua_y: float, centro: Vector3, maximo: float, idx: int,
		excluir: Array[RID], permitir_sumergido := false) -> float:
	if espacio == null or malla == null:
		return 0.0
	var radio := maxf(1.0, maximo)
	var menor := radio
	for a in DIRECCIONES:
		var angulo := TAU * float(a) / float(DIRECCIONES)
		var limite := _en_direccion(espacio, malla, escala, agua_y, centro,
				Vector2(cos(angulo), sin(angulo)), radio, idx, excluir, permitir_sumergido)
		if limite <= 0.0:
			return 0.0
		menor = minf(menor, limite)
	return menor


func _en_direccion(espacio: PhysicsDirectSpaceState3D, malla: MeshInstance3D,
		escala: float, agua_y: float, centro: Vector3, dir: Vector2, radio: float,
		idx: int, excluir: Array[RID], permitir_sumergido: bool) -> float:
	var alto := -1.0
	var r := radio
	while r >= RADIO_MINIMO:
		if _tierra(espacio, malla, escala, agua_y, centro, dir, r, idx, excluir,
				permitir_sumergido):
			alto = r
			break
		r -= PASO_GRUESO
	if alto < 0.0:
		return 0.0
	if alto >= radio:
		return alto
	var bajo := maxf(RADIO_MINIMO, alto - PASO_GRUESO)
	for _i in REFINADOS:
		var medio := (bajo + alto) * 0.5
		if _tierra(espacio, malla, escala, agua_y, centro, dir, medio, idx, excluir,
				permitir_sumergido):
			alto = medio
		else:
			bajo = medio
	return alto


func _tierra(espacio: PhysicsDirectSpaceState3D, malla: MeshInstance3D, escala: float,
		agua_y: float, centro: Vector3, dir: Vector2, r: float, idx: int,
		excluir: Array[RID], permitir_sumergido: bool) -> bool:
	var local := Vector3((centro.x + dir.x * r) / escala, 0.0,
			(centro.z + dir.y * r) / escala)
	var mundo: Vector3 = malla.to_global(local)
	var consulta := PhysicsRayQueryParameters3D.create(
			Vector3(mundo.x, agua_y + 240.0, mundo.z),
			Vector3(mundo.x, agua_y - 90.0, mundo.z))
	consulta.collide_with_areas = false
	consulta.exclude = excluir
	var golpe := espacio.intersect_ray(consulta)
	if golpe.is_empty():
		return false
	var col = golpe["collider"]
	if not (col is Node):
		return false
	var nodo := col as Node
	if not nodo.has_meta("terreno_editable") or int(nodo.get_meta("isla", -1)) != idx:
		return false
	return permitir_sumergido or (golpe["position"] as Vector3).y >= agua_y - 0.18
