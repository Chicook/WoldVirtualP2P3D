extends SceneTree
## Mide el camino del usuario que vuelve: recepción -> "Entrar al mundo" -> isla.
##
## Uso: godot --headless --path <proyecto> --script res://tools/e2e_existente.gd -- --server
## Sale 0 si llega a la isla, 2 si aparece el carrusel (no hay avatar guardado)
## y 1 si se agota el tiempo.

const ESCENA := "res://WoldVirtual3DP2P.tscn"

var _boot: Node
var _inicio := 0.0
var _t_recepcion := 0.0
var _t_pulsado := 0.0
var _pulsado := false


func _init() -> void:
	_inicio = Time.get_ticks_msec() / 1000.0
	var escena := load(ESCENA) as PackedScene
	if escena == null:
		print("[existente] FALLO: no se pudo cargar ", ESCENA)
		quit(1)
		return
	_boot = escena.instantiate()
	root.add_child.call_deferred(_boot)
	_bucle()


func _bucle() -> void:
	while true:
		await process_frame
		var ahora := Time.get_ticks_msec() / 1000.0
		if ahora - _inicio > 60.0:
			print("[existente] FALLO: tiempo agotado (pulsado=", _pulsado, ")")
			quit(1)
			return

		var recepcion := _buscar("LuciaRecepcion")
		if recepcion != null and _t_recepcion == 0.0:
			_t_recepcion = ahora
			print("[existente] recepcion en %.2f s · modo=%s · nick=%s · cuenta=%s" % [
				ahora - _inicio,
				str(recepcion.get("_modo")),
				str(recepcion.call("nick_cuenta")),
				str(FileAccess.file_exists("user://cuenta.json")),
			])

		if not _pulsado:
			var boton := _boton("Entrar al mundo")
			if boton != null:
				boton.pressed.emit()
				_pulsado = true
				_t_pulsado = ahora
				print("[existente] 'Entrar al mundo' pulsado en %.2f s" % (ahora - _inicio))
		else:
			var isla := _buscar("ISLA3Dblock")
			if isla != null and not bool(_boot.get("_cargando")):
				print("[existente] isla lista en %.2f s (desde el botón: %.2f s)" % [
					ahora - _inicio, ahora - _t_pulsado])
				quit(0)
				return
			if _buscar("SLAV") != null:
				print("[existente] sin avatar guardado: carrusel en %.2f s" % (ahora - _inicio))
				quit(2)
				return


func _buscar(nombre: String) -> Node:
	return _boot.find_child(nombre, true, false) if _boot != null else null


func _boton(texto: String) -> Button:
	for nodo in _boot.find_children("*", "Button", true, false):
		var boton := nodo as Button
		if boton.text == texto and boton.is_visible_in_tree():
			return boton
	return null
