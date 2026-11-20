extends SceneTree
## Verifica el carrusel de la 2.8.0: solo los 8 avatares buenos del catálogo,
## sin variantes al final y sin panel de blend shapes (la personalización es el
## paso siguiente, el registro).
##
## Uso: godot --headless --path <proyecto> --script res://tools/e2e_carrusel.gd

const ESCENA := "res://SLCAV/AVATARESCONANIMACION/SLAV.tscn"
const ESPERADOS := 8

var _carrusel: Node3D
var _fallos := 0


func _init() -> void:
	_correr()


func _correr() -> void:
	var escena := load(ESCENA) as PackedScene
	if escena == null:
		_fallo("no se pudo cargar SLAV.tscn")
		_terminar()
		return
	_carrusel = escena.instantiate() as Node3D
	root.add_child.call_deferred(_carrusel)
	await process_frame
	await process_frame
	await process_frame

	var base: int = (_carrusel.get("avatar_paths") as Array).size()
	var variantes: Array = _carrusel.get("_variantes")
	var total := int(_carrusel.call("_total_plazas"))
	print("[carrusel] avatares=%d · variantes=%d · plazas=%d" % [base, variantes.size(), total])

	_check(base == ESPERADOS, "el catálogo tiene %d avatares" % ESPERADOS)
	_check(variantes.is_empty(), "no hay variantes al final del carrusel")
	_check(total == base, "no se añaden plazas extra")
	_check(_carrusel.get_node_or_null("UI/Root/ShapePanel") == null,
		"sin panel de blend shapes en el carrusel")

	# La primera plaza debe cargar un avatar real (malla instanciada).
	_carrusel.call("_ir_a", 0, true)
	await process_frame
	var pivote := _carrusel.get_node_or_null("Pivot")
	var hijos := pivote.get_child_count() if pivote != null else 0
	print("[carrusel] avatares montados en el turno visible: ", hijos)
	_check(hijos > 0, "el carrusel monta los avatares del turno")

	_terminar()


func _check(condicion: bool, texto: String) -> void:
	if condicion:
		print("[ok]     ", texto)
	else:
		print("[FALLO]  ", texto)
		_fallos += 1


func _fallo(motivo: String) -> void:
	print("[FALLO]  ", motivo)
	_fallos += 1


func _terminar() -> void:
	print("[e2e_carrusel] ", "OK" if _fallos == 0 else ("FALLOS: %d" % _fallos))
	quit(0 if _fallos == 0 else 1)
