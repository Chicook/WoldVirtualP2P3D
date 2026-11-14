extends SceneTree
## E2E del demo local (discusión #86), sin ventana.
##
## Recorre el flujo real pulsando los mismos botones que una persona:
##   recepción LucIA -> "Crear mi cuenta" -> alta en la cadena -> descarga del .zip
##   -> "Entrar al mundo" -> carrusel -> registro -> portal -> isla.
##
## Uso (con el servidor de cuentas ya arrancado):
##   godot --headless --path <proyecto> --script res://tools/e2e_demo.gd -- --server
##
## Sale con 0 si llega a la isla y con 1 (y el motivo) si algo falla.

const ESCENA := "res://WoldVirtual3DP2P.tscn"
const AVATAR := "res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH1Ch3D.tscn"
const NICK := "e2edemo001"
const LIMITE_SEG := 120.0

var _boot: Node
var _fase := 0
var _t_fase := 0.0
var _inicio := 0.0
var _hitos: Array[String] = []
var _personalizado := false


func _init() -> void:
	_inicio = Time.get_ticks_msec() / 1000.0
	var escena := load(ESCENA) as PackedScene
	if escena == null:
		print("[E2E] FALLO: no se pudo cargar ", ESCENA)
		quit(1)
		return
	_boot = escena.instantiate()
	root.add_child.call_deferred(_boot)
	_bucle()


func _bucle() -> void:
	while true:
		await process_frame
		var ahora := Time.get_ticks_msec() / 1000.0
		if ahora - _inicio > LIMITE_SEG:
			_fallo("tiempo agotado en la fase %d" % _fase)
			return

		match _fase:
			0:
				if _buscar("LuciaRecepcion") != null:
					_hito("recepcion")
					_cambiar(1, ahora)
			1:
				if _crear_cuenta():
					_hito("alta_solicitada")
					_cambiar(2, ahora)
			2:
				if _cuenta_lista():
					_hito("cuenta_y_zip")
					_cambiar(3, ahora)
				elif int(ahora * 2.0) != int(_t_fase * 2.0):
					_t_fase = ahora
					print("[E2E] fase2: cuenta=%s zip=%s estado=%s" % [
						FileAccess.file_exists("user://cuenta.json"), _hay_zip(), _estado_texto()])
			3:
				var boton := _boton("Entrar al mundo")
				if boton != null:
					boton.pressed.emit()
					_hito("entrar_pulsado")
					_cambiar(4, ahora)
			4:
				var carrusel := _buscar("SLAV")
				if carrusel != null and carrusel.has_signal("avatar_confirmed"):
					# Esperar a que Boot haya conectado la señal antes de emitirla.
					if carrusel.avatar_confirmed.get_connections().size() > 0:
						carrusel.emit_signal("avatar_confirmed", AVATAR)
						_hito("avatar_elegido")
						_cambiar(5, ahora)
			5:
				var registro := _buscar("REGISTRO")
				if registro != null and not _personalizado:
					var confirmar := registro.get_node_or_null("Panel/VBox/Confirmar") as Button
					if confirmar == null:
						return
					# Validación 2 de 2: con el avatar base el registro está bloqueado.
					if confirmar.disabled:
						_hito("validacion_2_bloqueada")
					_personalizar(registro)
					_personalizado = true
					var aviso := registro.get_node_or_null("Panel/VBox/AvisoFirma") as Label
					if aviso != null:
						print("[E2E] validacion 2: ", aviso.text.replace("\n", " | "))
					if confirmar.disabled:
						_fallo("la validación 2 no se desbloqueó al personalizar el avatar")
						return
					_hito("validacion_2_superada")
					confirmar.pressed.emit()
					_hito("registro_confirmado")
					_cambiar(6, ahora)
			6:
				var portal := _buscar("entornodeprueba")
				if portal != null:
					var area := portal.get_node_or_null("Portal") as Area3D
					if area != null and area.portal_cruzado.get_connections().size() > 0:
						area.emit_signal("portal_cruzado")
						_hito("portal_cruzado")
						_cambiar(7, ahora)
			7:
				if _buscar("ISLA3Dblock") != null:
					_hito("isla_montada")
					_cambiar(8, ahora)
			8:
				# La isla está lista cuando Boot retira la pantalla de carga.
				var cargando := bool(_boot.get("_cargando"))
				if not cargando:
					_hito("isla_lista")
					_cambiar(9, ahora)
			9:
				# El avatar propio debe haber quedado en la cadena y dejar variantes.
				if _variantes_listas():
					_hito("avatar_original_y_variantes")
					print("[E2E] variantes: ", FileAccess.get_file_as_string("user://avatares_variantes.json").strip_edges())
					print("[E2E] OK - hitos: ", _hitos)
					print("[E2E] cuenta: ", FileAccess.get_file_as_string("user://cuenta.json").strip_edges())
					quit(0)
					return
				elif ahora - _t_fase > 15.0:
					_fallo("el avatar propio no se registró en la cadena (sin variantes)")
					return


func _cambiar(fase: int, ahora: float) -> void:
	_fase = fase
	_t_fase = ahora


func _hito(nombre: String) -> void:
	_hitos.append(nombre)
	print("[E2E] hito: ", nombre, "  (+%.1fs)" % (Time.get_ticks_msec() / 1000.0 - _inicio))


## Lleva varias proporciones al máximo para que el avatar se aparte del base y
## supere el umbral de originalidad (AvatarFirma.UMBRAL_ORIGINALIDAD = 0.12).
func _personalizar(registro: Node) -> void:
	var rutas := [
		"Panel/Personalizacion/Tabs/Cuerpo/AlturaFila/Slider",
		"Panel/Personalizacion/Tabs/Cuerpo/AnchoFila/Slider",
		"Panel/Personalizacion/Tabs/Cuerpo/CabezaFila/Slider",
		"Panel/Personalizacion/Tabs/Cuerpo/HombrosFila/Slider",
		"Panel/Personalizacion/Tabs/Cuerpo/TorsoFila/Slider",
		"Panel/Personalizacion/Tabs/Cuerpo/BrazosFila/Slider",
		"Panel/Personalizacion/Tabs/Cuerpo/PiernasFila/Slider",
	]
	for ruta in rutas:
		var slider := registro.get_node_or_null(ruta) as HSlider
		if slider != null:
			slider.value = slider.max_value


func _fallo(motivo: String) -> void:
	print("[E2E] FALLO: ", motivo)
	print("[E2E] hitos alcanzados: ", _hitos)
	print("[E2E] estado en pantalla: ", _estado_texto())
	quit(1)


## Texto del rótulo de estado de la recepción, para diagnosticar fallos.
func _estado_texto() -> String:
	var recepcion := _buscar("LuciaRecepcion")
	if recepcion == null:
		return "(sin recepción)"
	var etiqueta = recepcion.get("_estado")
	if etiqueta == null:
		return "(sin estado)"
	return str(etiqueta.text)


func _buscar(nombre: String) -> Node:
	return _boot.find_child(nombre, true, false) if _boot != null else null


## Rellena el nick y pulsa "Crear mi cuenta" en la recepción.
func _crear_cuenta() -> bool:
	var recepcion := _buscar("LuciaRecepcion")
	if recepcion == null:
		return false
	for nodo in recepcion.find_children("*", "LineEdit", true, false):
		var campo := nodo as LineEdit
		if campo.placeholder_text.to_lower().contains("nick"):
			campo.text = NICK
			break
	var boton := _boton("Crear mi cuenta")
	if boton == null:
		return false
	boton.pressed.emit()
	return true


func _cuenta_lista() -> bool:
	if not FileAccess.file_exists("user://cuenta.json"):
		return false
	var datos = JSON.parse_string(FileAccess.get_file_as_string("user://cuenta.json"))
	if typeof(datos) != TYPE_DICTIONARY:
		return false
	var hash := str(datos.get("cuenta_hash", ""))
	if hash.length() != 64:
		return false
	return DirAccess.dir_exists_absolute(OS.get_user_data_dir()) and _hay_zip()


## ¿Están las variantes en el formato actual? Cada una debe traer su aspecto
## resuelto (`pers`); si el fichero es viejo, se sigue esperando a que Boot escriba.
func _variantes_listas() -> bool:
	if not FileAccess.file_exists("user://avatares_variantes.json"):
		return false
	var datos = JSON.parse_string(FileAccess.get_file_as_string("user://avatares_variantes.json"))
	if typeof(datos) != TYPE_DICTIONARY:
		return false
	var lista = datos.get("variantes", [])
	if typeof(lista) != TYPE_ARRAY or lista.is_empty():
		return false
	var primera = lista[0]
	return typeof(primera) == TYPE_DICTIONARY and primera.has("pers")


func _hay_zip() -> bool:
	var dir := DirAccess.open(OS.get_user_data_dir())
	if dir == null:
		return false
	for nombre in dir.get_files():
		if nombre.begins_with("cuenta_") and nombre.ends_with(".zip"):
			return true
	return false


func _boton(texto: String) -> Button:
	var recepcion := _buscar("LuciaRecepcion")
	if recepcion == null:
		return null
	for nodo in recepcion.find_children("*", "Button", true, false):
		var boton := nodo as Button
		if boton.text == texto and boton.is_visible_in_tree():
			return boton
	return null
