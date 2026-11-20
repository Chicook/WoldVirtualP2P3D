extends Node3D
## Arranque del metaverso (demo local, discusión #86):
## 0. RECEPCIÓN EN LA DAO: LucIA recibe en su despacho. Allí se crea la cuenta
##    (un bloque = un hash) o se saluda al que ya la tiene en este PC. No hay
##    contraseña, ni semilla, ni validación de túnel.
## 1. ALTA EN LA DAO: el ciudadano recorre el despacho de LucIA, la plaza
##    de registro, el carrusel, el espejo del avatar y el portal.      [solo alta]
## 2. Ventana de carga hasta que aparece MI isla, ya registrada por el portal.
## 3. Se cierra la carga y queda el mundo jugable en su isla.
##
## Si ya hay cuenta (user://cuenta.json) y avatar (user://registro.cfg),
## se entra directamente a la isla sin pasar por recepción ni alta.

const ONBOARDING_SCENE: PackedScene = preload("res://lucia3D/IslaUnicaLucIA/ONBOARDING/OnboardingDAO.tscn")
const CARRUSEL_SCENE: PackedScene = preload("res://avatares/CarruselAvatares.tscn")
const EDITOR_ASPECTO_SCENE: PackedScene = preload("res://avatares/EditorAspecto.tscn")
const REGISTRO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/registro.tscn")
const PORTAL_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/entornodeprueba.tscn")
const MUNDO_SCENE: PackedScene = preload("res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn")
const Sonda = preload("res://gdscrip/Sonda.gd")
const Turnos = preload("res://gdscrip/Turnos.gd")
const Firma = preload("res://gdscrip/AvatarFirma.gd")
const Pers = preload("res://gdscrip/Personalizacion.gd")
const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

const URL_AVATAR := "http://127.0.0.1:8545/avatar-original"

var _carrusel: Node3D
var _editor_aspecto: Node3D
var _registro: Control
var _zona_portal: Node3D
var _mundo: Node3D
var _onboarding: Node3D
var _carga: CanvasLayer
var _carga_label: Label
var _carga_texto := "Conectando a la red P2P"
var _avatar_scene := ""
var _nick := ""
var _cargando := false
var _espera_isla: Timer
var _sonda
var _invitar_lucia := false
var _iniciar_en_dao := false


func _ready() -> void:
	print("================================================================")
	print("[Boot.gd] Arranque WoldVirtualP2P3D iniciado (Godot 4.7.2)")
	print("[Boot.gd] Argumentos motor (get_cmdline_args): ", OS.get_cmdline_args())
	print("[Boot.gd] Argumentos usuario (get_cmdline_user_args): ", OS.get_cmdline_user_args())

	# IMPORTANTE: Boot.gd NO decide el rol de red. El único responsable de resolver
	# y aplicar la topología (Servidor/Cliente + IP/puerto objetivo) es ChunkManager.gd,
	# que lee los mismos argumentos. Aquí solo se registra lo recibido para depurar.
	var _args_net: Array = OS.get_cmdline_args()
	_args_net.append_array(OS.get_cmdline_user_args())
	print("[Boot.gd] Argumentos totales vistos por el motor: ", _args_net)
	print("[Boot.gd] El rol de red (Servidor/Cliente) y la IP objetivo los resuelve ChunkManager.gd.")
	print("================================================================")

	var onboarding_dao_completado := "user://onboarding_dao_completado.flag"
	_iniciar_en_dao = _dao_lobby_solicitado()
	var modo_preview_dao := _dao_preview_solicitado()
	if _iniciar_en_dao:
		_desactivar_carrusel_automatico_dao()
	# ── RESET DE SESIÓN (flag escrito por el visor C# al arrancar) ──────────────
	# Si el visor detectó un reset limpio, borramos el registro para que
	# Godot arranque siempre como primera vez (carrusel + registro de nick).
	var reset_flag_path := OS.get_user_data_dir().path_join("reset_flag.txt")
	if FileAccess.file_exists(reset_flag_path) and not modo_preview_dao:
		if not FileAccess.file_exists(onboarding_dao_completado) \
				and FileAccess.file_exists("user://registro.cfg"):
			DirAccess.remove_absolute(
				OS.get_user_data_dir().path_join("registro.cfg"))
		DirAccess.remove_absolute(reset_flag_path)

	# «Oficina de Lucía 3D» desde el visor: el botón pide reabrir el alta para
	# actualizar cuenta/avatar. La marca abre la recepción de la DAO de forma
	# determinista, sin pasar por la antigua ventana de recepción.
	var marca_cuenta := OS.get_user_data_dir().path_join("abrir_recepcion.flag")
	var recepcion_solicitada := FileAccess.file_exists(marca_cuenta)
	if recepcion_solicitada:
		DirAccess.remove_absolute(marca_cuenta)
		print("[Boot] Oficina de Lucía solicitada desde el visor: alta en la DAO")

	# La sonda existe en todos los peers: el anfitrion responde consultas de
	# plazas y el invitado pregunta antes del carrusel.
	_sonda = Sonda.new()
	_sonda.name = "Sonda"
	add_child(_sonda)

	# Vista previa técnica del visor: usa un avatar de catálogo para mostrar la
	# DAO aunque este perfil de prueba no tenga cuenta local. No guarda ni altera
	# la cuenta/registro del usuario.
	if modo_preview_dao and not recepcion_solicitada:
		_cargar_nick_guardado()
		if _nick.is_empty():
			_nick = "Vecino DAO"
		var cfg := ConfigFile.new()
		if cfg.load("user://registro.cfg") == OK:
			var av: String = str(cfg.get_value("jugador", "avatar_scene", "")).strip_edges()
			if not av.is_empty():
				_avatar_scene = av
		if _avatar_scene.is_empty():
			_avatar_scene = "res://avatares/AVMJ1.tscn"
		print("[Boot] Vista previa del visor: recepción de LucIA en la DAO con avatar (", _avatar_scene, ") nick=", _nick)
		_iniciar_en_dao = true
		_mostrar_onboarding()
		return

	# El botón «Oficina de Lucía 3D» reabre el alta nueva dentro de la DAO.
	# Ignora la marca de alta completada para que el ciudadano pueda volver a
	# pasar por el carrusel y actualizar su avatar o su cuenta.
	if recepcion_solicitada:
		if FileAccess.file_exists(onboarding_dao_completado):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(onboarding_dao_completado))
		_iniciar_en_dao = true
		_cargar_nick_guardado()
		_mostrar_onboarding()
		return

	# El onboarding de la DAO ya guardó nick y avatar antes de cargar este mundo.
	# Consumir la marca evita volver a pedir recepción y continúa con el reparto
	# normal del ChunkManager.
	if FileAccess.file_exists(onboarding_dao_completado):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(onboarding_dao_completado))
		_iniciar_en_dao = false
		print("[Boot] Onboarding DAO completado; cargando directamente la isla personal")
		_continuar_registrado()
		return

	# LucIA recibe SIEMPRE primero (anfitriona), pero la recepción vive en su
	# despacho de la DAO: saludar o crear la cuenta es el arranque del alta.
	#
	# Excepción de autoprueba: el visor ejecuta el motor sin nadie delante y
	# necesita que la isla y el 8911 arranquen. Solo `--startup-selftest` pasa
	# `--sin-recepcion`; una sesión normal nunca lo lleva.
	if _sin_recepcion():
		print("[Boot] --sin-recepcion: entrada directa con el perfil guardado")
		_continuar_registrado()
		return

	print("[Boot] Recepción de LucIA en la DAO: alta en su despacho")
	_cargar_nick_guardado()
	_mostrar_onboarding()


## ¿Arranca para la autoprueba del visor (sin recepción)?
func _sin_recepcion() -> bool:
	var args: Array = OS.get_cmdline_args()
	args.append_array(OS.get_cmdline_user_args())
	return args.has("--sin-recepcion")


func _dao_lobby_solicitado() -> bool:
	var args: Array = OS.get_cmdline_args()
	args.append_array(OS.get_cmdline_user_args())
	return args.has("--dao-lobby")


func _dao_preview_solicitado() -> bool:
	var args: Array = OS.get_cmdline_args()
	args.append_array(OS.get_cmdline_user_args())
	return args.has("--dao-preview")


## El carrusel de registro sigue disponible en la consola del atrio, pero no se
## abre al pasar por allí durante una sesión de un ciudadano ya registrado.
func _desactivar_carrusel_automatico_dao() -> void:
	var sede := get_tree().root.find_child("IslaUnicaLucIA", true, false)
	if sede == null:
		return
	var carrusel := sede.find_child("CarruselDAO", true, false)
	if carrusel != null and carrusel.has_method("set_auto_abrir"):
		carrusel.call("set_auto_abrir", false)


## El registro del jugador (user://avatar_hash.json) guarda la escena que eligió
## al registrarse. Si `avatar_scene` quedó con un sustituto de turno, se vuelve a
## esa elección una sola vez por perfil (`avatar_reparado`), para no pisar un
## cambio de avatar posterior.
func _reparar_avatar(cfg: ConfigFile, guardado: String, nick: String) -> String:
	if bool(cfg.get_value("jugador", "avatar_reparado", false)):
		return guardado
	if not FileAccess.file_exists("user://avatar_hash.json"):
		return guardado
	var datos = JSON.parse_string(FileAccess.get_file_as_string("user://avatar_hash.json"))
	if typeof(datos) != TYPE_DICTIONARY:
		return guardado
	var registro: Dictionary = datos
	if str(registro.get("estado", "")) != "REGISTRADO":
		return guardado
	if str(registro.get("usuario", "")) != nick:
		return guardado
	var elegido := str(registro.get("avatar_scene", ""))
	if Turnos.indice(elegido) < 0:
		# Perfil de una versión anterior: se traduce al avatar nuevo equivalente.
		var id_migrado := Catalogo.id_de_ruta(elegido)
		if not id_migrado.is_empty():
			elegido = Catalogo.escena_de(id_migrado)
	if Turnos.indice(elegido) < 0:
		return guardado
	if elegido != guardado:
		print("[Boot] avatar reparado desde el registro: ", elegido.get_file())
		guardado = elegido
		cfg.set_value("jugador", "avatar_scene", elegido)
	cfg.set_value("jugador", "avatar_reparado", true)
	cfg.save("user://registro.cfg")
	return guardado



func _process(delta: float) -> void:
	if not _cargando or _carga_label == null:
		return
	var puntos := int(Time.get_ticks_msec() / 400) % 4
	_carga_label.text = _carga_texto + ".".repeat(puntos)


## El alta completa se vive dentro de la DAO (despacho, plaza, carrusel, espejo
## y portal). Antes de montar el mundo se libera la DAO del alta: la del mundo
## es la única copia viva de la isla.
func _mostrar_onboarding() -> void:
	if _nick.strip_edges().is_empty():
		_nick = "Invitado"
	if ONBOARDING_SCENE == null:
		_mostrar_carrusel()
		return
	_mostrar_carga("Preparando la Sede de la DAO")
	var ocupados: Array = await _sonda.consultar()
	_ocultar_carga()
	_onboarding = ONBOARDING_SCENE.instantiate() as Node3D
	if _onboarding == null:
		_mostrar_carrusel()
		return
	if _onboarding.has_method("set_nick"):
		_onboarding.call("set_nick", _nick)
	if _onboarding.has_method("set_ocupados"):
		_onboarding.call("set_ocupados", ocupados)
	add_child(_onboarding)
	_onboarding.connect("onboarding_completado", _on_onboarding_completado)


func _on_onboarding_completado(avatar_scene: String) -> void:
	if is_instance_valid(_onboarding):
		_nick = str(_onboarding.get("_nick")).strip_edges()
	_iniciar_en_dao = false
	_avatar_scene = avatar_scene
	var id := Catalogo.id_de_ruta(avatar_scene)
	if not id.is_empty():
		Avatares.guardar(id)
		Avatares.sincronizar_registro(id, _nick)
	if _onboarding != null and is_instance_valid(_onboarding):
		_onboarding.queue_free()
		_onboarding = null
	# Solo el anfitrión de desarrollo integra la recepción en la escena raíz.
	# El invitado debe pasar a la escena P2P para ver la DAO del anfitrión, no
	# conservar una DAO local duplicada en su recepción.
	var red := preload("res://gdscrip/Red.gd")
	if bool(red.resolver_objetivo().get("is_client", false)):
		var marca := FileAccess.open("user://onboarding_dao_completado.flag", FileAccess.WRITE)
		if marca != null:
			marca.store_string("1")
			marca.close()
		get_tree().call_deferred("change_scene_to_file", "res://WoldVirtual3DP2P.tscn")
		return
	# Mantener la única DAO del anfitrión actual y añadir el mundo común.
	var cfg := ConfigFile.new()
	cfg.load("user://registro.cfg")
	cfg.set_value("jugador", "nick", _nick)
	cfg.save("user://registro.cfg")
	await get_tree().process_frame
	await get_tree().process_frame
	_entrar_a_isla()



## Nick del perfil local para reabrir el alta sin volver a pedirlo.
func _cargar_nick_guardado() -> void:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") == OK:
		_nick = str(cfg.get_value("jugador", "nick", "")).strip_edges()
	if _nick.is_empty() and FileAccess.file_exists("user://cuenta.json"):
		var datos = JSON.parse_string(FileAccess.get_file_as_string("user://cuenta.json"))
		if typeof(datos) == TYPE_DICTIONARY:
			_nick = str(datos.get("nick", "")).strip_edges()


## Un jugador ya registrado entra a su isla con el avatar guardado.
func _continuar_registrado() -> void:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") == OK:
		var saved_avatar: String = str(cfg.get_value("jugador", "avatar_scene", ""))
		var saved_nick: String   = str(cfg.get_value("jugador", "nick", ""))
		if saved_nick.is_empty():
			saved_nick = _nick
		if Turnos.indice(saved_avatar) < 0:
			var id_viejo := Catalogo.id_de_ruta(saved_avatar)
			if not id_viejo.is_empty():
				saved_avatar = Catalogo.escena_de(id_viejo)
				Avatares.guardar(id_viejo)
		if not saved_avatar.is_empty() and not saved_nick.is_empty():
			_avatar_scene = _reparar_avatar(cfg, saved_avatar, saved_nick)
			_nick         = saved_nick
			_entrar_a_isla()
			return
	# Sin avatar guardado (borde): pasa por el carrusel igualmente.
	_mostrar_carrusel()


func _mostrar_carrusel() -> void:
	if _nick.strip_edges().is_empty():
		_nick = "Invitado"
	# Antes de elegir avatar se pregunta al anfitrion que plazas ya estan
	# reservadas; si no hay sesion abierta la consulta vuelve vacia.
	_mostrar_carga("Buscando jugadores en la red")
	var ocupados: Array = await _sonda.consultar()
	_ocultar_carga()
	_carrusel = CARRUSEL_SCENE.instantiate() as Node3D
	if _carrusel.has_method("set_ocupados"):
		_carrusel.call("set_ocupados", ocupados)
	if _carrusel.has_method("set_nick"):
		_carrusel.call("set_nick", _nick)
	if _carrusel.has_method("abrir_en_primer_hueco"):
		_carrusel.call("abrir_en_primer_hueco")
	add_child(_carrusel)
	_carrusel.connect("avatar_confirmed", _on_avatar_confirmed)


func _on_avatar_confirmed(scene_path: String) -> void:
	_avatar_scene = scene_path
	var id := Catalogo.id_de_ruta(scene_path)
	if not id.is_empty():
		Avatares.guardar(id)
		Avatares.sincronizar_registro(id, _nick)
	if _carrusel:
		_carrusel.queue_free()
		_carrusel = null
	# Segunda validación: aspecto del avatar propio antes de entrar.
	if not id.is_empty():
		_mostrar_editor_aspecto(id)
	else:
		_entrar_a_isla()


func _mostrar_editor_aspecto(id: String) -> void:
	_editor_aspecto = EDITOR_ASPECTO_SCENE.instantiate() as Node3D
	if _editor_aspecto.has_method("set_avatar"):
		_editor_aspecto.call("set_avatar", id)
	if _editor_aspecto.has_method("set_nick"):
		_editor_aspecto.call("set_nick", _nick)
	add_child(_editor_aspecto)
	_editor_aspecto.connect("aspecto_confirmado", _on_aspecto_confirmado)


func _on_aspecto_confirmado() -> void:
	if _editor_aspecto:
		_editor_aspecto.queue_free()
		_editor_aspecto = null
	_entrar_a_isla()


func _mostrar_registro() -> void:
	_registro = REGISTRO_SCENE.instantiate() as Control
	add_child(_registro)
	_registro.connect("registro_completado", _on_registro_completado)
	# El nick ya lo fijó la cadena al crear la cuenta: aquí no se vuelve a pedir.
	if _nick != "" and _registro.has_method("set_nick"):
		_registro.call("set_nick", _nick, true)
	if _avatar_scene != "" and _registro.has_method("set_avatar_scene"):
		_registro.set_avatar_scene(_avatar_scene)


func _on_registro_completado(nick: String) -> void:
	_nick = nick.strip_edges()
	if _registro:
		_registro.queue_free()
		_registro = null
	_registrar_avatar_si_original()
	_mostrar_zona_portal()


## Si el avatar se diferenció del base lo suficiente, se ancla en la cadena y
## alimenta las neuronas de LucIA (bloque AVATAR_ORIGINAL). No bloquea el flujo:
## si el servidor no está, el jugador entra igual y solo se registra en consola.
func _registrar_avatar_si_original() -> void:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") != OK:
		return
	if not bool(cfg.get_value("jugador", "avatar_original", false)):
		return
	var firma := str(cfg.get_value("jugador", "avatar_firma", ""))
	var delta := float(cfg.get_value("jugador", "avatar_delta", 0.0))
	var hash := _hash_cuenta()
	if hash.length() != 64 or firma.length() != 64:
		return
	var payload := {
		"cuenta_hash": hash,
		"nick": _nick,
		"avatar_firma": firma,
		"avatar_delta": delta,
	}
	var http := HTTPRequest.new()
	http.timeout = 10.0
	add_child(http)
	http.request_completed.connect(_on_avatar_registrado.bind(http, firma))
	var err := http.request(URL_AVATAR, ["Content-Type: application/json"],
		HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		http.queue_free()


func _hash_cuenta() -> String:
	if not FileAccess.file_exists("user://cuenta.json"):
		return ""
	var datos = JSON.parse_string(FileAccess.get_file_as_string("user://cuenta.json"))
	if typeof(datos) != TYPE_DICTIONARY:
		return ""
	return str(datos.get("cuenta_hash", "")).strip_edges()


func _on_avatar_registrado(result: int, code: int, _headers: PackedStringArray,
		body: PackedByteArray, http: HTTPRequest, firma: String) -> void:
	http.queue_free()
	if result != HTTPRequest.RESULT_SUCCESS or code != 201:
		print("[Boot] avatar propio no registrado (código ", code, ")")
		return
	var datos = JSON.parse_string(body.get_string_from_utf8())
	if typeof(datos) != TYPE_DICTIONARY:
		return
	var indice := int(datos.get("indice_bloque", 0))
	print("[Boot] avatar propio registrado en el bloque #", indice)
	_guardar_variantes(firma)
	_mostrar_aviso("Cuenta validada (2 de 2) · avatar propio en el bloque #%d." % indice)


## Deja 3 variantes deterministas del avatar propio en user://avatares_variantes.json.
## El carrusel las reconstruye con la personalización ya resuelta: aquí se guarda
## el aspecto completo (tintes en HTML y campos numéricos), no la imagen.
func _guardar_variantes(firma: String) -> void:
	var cfg := ConfigFile.new()
	cfg.load("user://registro.cfg")
	var base_scene := str(cfg.get_value("jugador", "avatar_scene", ""))
	var pers: Dictionary = Pers.leer()
	var lista := []
	for i in 3:
		var v: Dictionary = Firma.variante(pers, firma, i)
		lista.append({
			"indice": i,
			"avatar_firma": Firma.firma(v),
			"avatar_delta": Firma.delta_base(v),
			"base_scene": base_scene,
			"pers": _pers_a_json(v),
		})
	var salida := {
		"origen_firma": firma,
		"cuenta_hash": _hash_cuenta(),
		"base_scene": base_scene,
		"pers_origen": _pers_a_json(pers),
		"variantes": lista,
	}
	var f := FileAccess.open("user://avatares_variantes.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(salida, "\t"))
		f.close()


## Aspecto a JSON: los tintes como HTML (#rrggbb) y los campos como número.
func _pers_a_json(pers: Dictionary) -> Dictionary:
	var salida := {}
	for clave in Pers.ORDEN:
		var color: Color = pers.get(clave, Color.WHITE)
		salida[clave] = color.to_html(false)
	for clave in Pers.CAMPOS:
		salida[clave] = float(pers.get(clave, Pers.POR_DEFECTO[clave]))
	return salida


func _mostrar_zona_portal() -> void:
	_zona_portal = PORTAL_SCENE.instantiate() as Node3D
	add_child(_zona_portal)
	if _avatar_scene != "" and _zona_portal.has_method("set_player_avatar"):
		_zona_portal.set_player_avatar(_avatar_scene)
	var portal: Area3D = _zona_portal.get_node("Portal") as Area3D
	portal.connect("portal_cruzado", _on_portal_cruzado)


func _on_portal_cruzado() -> void:
	if _zona_portal:
		_zona_portal.queue_free()
		_zona_portal = null
	_entrar_a_isla()


func _entrar_a_isla() -> void:
	_mostrar_carga()
	if preload("res://gdscrip/Red.gd").sesion_validada():
		_carga_texto = "Esperando el mundo compartido del anfitrión"
		var resultado: Dictionary = await _sonda.esperar_mundo()
		if not bool(resultado.get("ok", false)):
			_ocultar_carga()
			_mostrar_aviso(str(resultado.get("error", "Mundo no disponible")))
			return
	_sonda.liberar_eco()
	var mundo: Node3D = MUNDO_SCENE.instantiate() as Node3D
	mundo.name = "ISLA3Dblock"
	_mundo = mundo
	mundo.connect("mi_isla_lista", _on_mi_isla_lista)
	if mundo.has_signal("avatar_asignado"):
		mundo.connect("avatar_asignado", _on_avatar_asignado)
	if _avatar_scene != "" and mundo.has_method("set_player_avatar"):
		mundo.call("set_player_avatar", _avatar_scene)
	add_child(mundo)
	_invitar_lucia = FileAccess.file_exists("user://invitar_lucia.flag")
	if _invitar_lucia:
		DirAccess.remove_absolute(ProjectSettings.globalize_path("user://invitar_lucia.flag"))
	_esperar_isla(25.0)


## Red de seguridad: si el mundo no confirma la isla (red, assets), no dejamos al
## jugador mirando una pantalla de carga para siempre. El mundo ya está montado:
## se retira la carga y se avisa.
func _esperar_isla(segundos: float) -> void:
	if _espera_isla and is_instance_valid(_espera_isla):
		_espera_isla.queue_free()
	_espera_isla = Timer.new()
	_espera_isla.one_shot = true
	_espera_isla.wait_time = segundos
	_espera_isla.timeout.connect(_on_espera_isla_agotada)
	add_child(_espera_isla)
	_espera_isla.start()


func _on_espera_isla_agotada() -> void:
	if not _cargando:
		return
	_ocultar_carga()
	_mostrar_aviso("Tu isla no confirmó a tiempo. El mundo sigue abierto; revisa la red P2P.")


func _mostrar_carga(texto: String = "Conectando a la red P2P") -> void:
	_cargando = true
	_carga_texto = texto
	_carga = CanvasLayer.new()
	_carga.layer = 200
	add_child(_carga)
	var fondo := ColorRect.new()
	fondo.set_anchors_preset(Control.PRESET_FULL_RECT)
	fondo.color = Color(0.05, 0.06, 0.09, 1)
	_carga.add_child(fondo)
	var centro := CenterContainer.new()
	centro.set_anchors_preset(Control.PRESET_FULL_RECT)
	_carga.add_child(centro)
	_carga_label = Label.new()
	_carga_label.text = texto
	_carga_label.add_theme_font_size_override("font_size", 28)
	centro.add_child(_carga_label)


func _ocultar_carga() -> void:
	_cargando = false
	if _carga:
		_carga.queue_free()
		_carga = null
	_carga_label = null


func _on_mi_isla_lista() -> void:
	if _espera_isla and is_instance_valid(_espera_isla):
		_espera_isla.stop()
	_ocultar_carga()
	if _iniciar_en_dao:
		_colocar_jugador_en_dao()
	_mostrar_bienvenida()
	if _invitar_lucia:
		_invitar_lucia = false
		_mostrar_aviso("LucIA ya está en la DAO única. Tu isla está conectada al mismo mundo.")


## Reubica solo al jugador local en la DAO compartida; no altera el índice ni la
## posición de su isla personal, que sigue siendo vecina y se asigna por sesión.
func _colocar_jugador_en_dao() -> void:
	if _mundo == null or not is_instance_valid(_mundo):
		return
	var jugador := _mundo.get_node_or_null("USERBASE") as CharacterBody3D
	if jugador == null:
		return
	var dao: Node3D = get_node_or_null("IslaUnicaLucIA") as Node3D
	if dao == null:
		dao = get_tree().get_first_node_in_group("isla_unica_lucia") as Node3D
	if dao == null and _mundo != null and is_instance_valid(_mundo):
		dao = _mundo.get_tree().root.find_child("IslaUnicaLucIA", true, false) as Node3D
	if dao == null:
		return
	var spawn := dao.to_global(Vector3(0.0, 42.2, 5.2))
	jugador.global_position = spawn
	jugador.velocity = Vector3.ZERO
	# Desde el punto de recepción, LucIA está al otro lado del eje Z local.
	jugador.global_rotation.y = dao.global_rotation.y + PI
	if jugador.has_method("snap_camera"):
		jugador.call("snap_camera")
	if dao.has_method("conectar_dao_al_metaverso"):
		dao.call("conectar_dao_al_metaverso")


## LucIA acompaña al jugador en su isla cuando se pide desde el visor.
func _spawn_lucia_invitada() -> void:
	if _mundo == null or not is_instance_valid(_mundo):
		return
	var packed := load("res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn") as PackedScene
	if packed == null:
		return
	var lucia := packed.instantiate() as Node3D
	var userbase := _mundo.get_node_or_null("USERBASE") as Node3D
	var base := Vector3(0, 42, 0)
	var frente := Vector3(0, 0, 1)
	var derecha := Vector3(1, 0, 0)
	if userbase != null:
		base = userbase.global_position
		frente = userbase.global_transform.basis.z.normalized()
		derecha = userbase.global_transform.basis.x.normalized()
	var destino := base + Vector3(2.0, 0.0, 0.5)
	var camara := get_viewport().get_camera_3d()
	if camara != null:
		var delante := -camara.global_transform.basis.z.normalized()
		var lado := camara.global_transform.basis.x.normalized()
		destino = camara.global_position + delante * 3.2 + lado * 1.1
		destino.y = base.y + 0.05
	lucia.name = "LuciaInvitada"
	_mundo.add_child(lucia)
	# LuciaPersonaje mueve el nodo con _posicion_base; hay que sembrarla.
	lucia.position = destino
	lucia.set("_posicion_base", destino)
	lucia.add_child(preload("res://gdscrip/LuciaIdle.gd").new())
	lucia.add_child(preload("res://gdscrip/LuciaBoca.gd").new())
	var etiqueta := Label3D.new()
	etiqueta.text = "LucIA"
	etiqueta.font_size = 48
	etiqueta.modulate = Color(1.0, 0.85, 0.45)
	etiqueta.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	etiqueta.position = Vector3(0, 2.15, 0)
	lucia.add_child(etiqueta)
	_mostrar_aviso("LucIA se ha unido a tu isla.")


## El anfitrión cambió el avatar porque la plaza ya estaba reservada.
func _on_avatar_asignado(anterior: String, nuevo: String, turno: int, reciclado: bool) -> void:
	var texto := ""
	if anterior != "":
		texto = "El avatar %s ya estaba en uso. " % anterior
	texto += "Se te asignó %s" % nuevo
	if turno > 0:
		texto += " · Turno %d" % turno
	if reciclado:
		texto += " (avatar reutilizado)"
	_mostrar_aviso(texto)


func _mostrar_aviso(texto: String) -> void:
	var capa := CanvasLayer.new()
	capa.layer = 150
	add_child(capa)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER_TOP)
	panel.offset_left = -360.0
	panel.offset_right = 360.0
	# Debajo del cartel de bienvenida para que ambos textos se lean a la vez.
	panel.offset_top = 210.0
	capa.add_child(panel)
	var estilo := StyleBoxFlat.new()
	estilo.bg_color = Color(0.03, 0.07, 0.12, 0.94)
	estilo.border_color = Color(0.35, 0.8, 1.0, 0.9)
	estilo.set_border_width_all(2)
	estilo.set_corner_radius_all(8)
	estilo.content_margin_left = 18.0
	estilo.content_margin_right = 18.0
	estilo.content_margin_top = 12.0
	estilo.content_margin_bottom = 12.0
	panel.add_theme_stylebox_override("panel", estilo)
	var etiqueta := Label.new()
	etiqueta.text = texto
	etiqueta.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	etiqueta.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	etiqueta.add_theme_font_size_override("font_size", 18)
	etiqueta.add_theme_color_override("font_color", Color(0.82, 0.94, 1.0, 1.0))
	panel.add_child(etiqueta)
	# CanvasLayer no tiene modulate: se desvanece el panel y después se libera la capa.
	var tw := create_tween()
	tw.tween_interval(7.0)
	tw.tween_property(panel, "modulate:a", 0.0, 1.0)
	tw.tween_callback(capa.queue_free)


## Aviso al llegar a la isla: felicita al jugador y lo saluda por su nick.
func _mostrar_bienvenida() -> void:
	var capa := CanvasLayer.new()
	capa.layer = 100
	add_child(capa)
	var caja := VBoxContainer.new()
	caja.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.set_anchors_preset(Control.PRESET_CENTER_TOP)
	caja.offset_left = -520.0
	caja.offset_right = 520.0
	caja.offset_top = 36.0
	caja.offset_bottom = 196.0
	caja.add_theme_constant_override("separation", 10)
	capa.add_child(caja)

	var l1 := _etiqueta_bienvenida("GRACIAS POR ENTRAR A WOLD VIRTUAL 3D", 20, Color(0.55, 0.8, 0.96, 1.0), 6)
	l1.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(l1)

	var l2 := _etiqueta_bienvenida("BIENVENIDO A TU ISLA!", 30, Color(0.72, 0.94, 1.0, 1.0), 7)
	l2.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(l2)

	var l3 := _etiqueta_bienvenida(_texto_bienvenida(), 24, Color(0.62, 0.9, 1.0, 1.0), 6)
	l3.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caja.add_child(l3)

	var tween := create_tween()
	tween.tween_interval(4.5)
	tween.tween_property(caja, "modulate:a", 0.0, 1.6)
	tween.tween_callback(capa.queue_free)


func _etiqueta_bienvenida(texto: String, tam: int, color: Color, borde: int) -> Label:
	var etiqueta := Label.new()
	etiqueta.text = texto
	etiqueta.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	etiqueta.add_theme_font_size_override("font_size", tam)
	etiqueta.add_theme_color_override("font_color", color)
	etiqueta.add_theme_color_override("font_outline_color", Color(0.01, 0.05, 0.09, 1.0))
	etiqueta.add_theme_constant_override("outline_size", borde)
	return etiqueta


func _texto_bienvenida() -> String:
	var texto := _saludo()
	if _nick != "":
		texto += ", " + _nick
	if _mundo != null and _mundo.has_method("mi_turno"):
		var turno := int(_mundo.call("mi_turno"))
		if turno > 0:
			texto += "  ·  TURNO %d" % turno
			if bool(_mundo.call("mi_reciclado")):
				texto += " (REUTILIZADO)"
	return texto


## Saludo segun el avatar elegido en el carrusel (AVMJ = mujer, AVH = hombre).
func _saludo() -> String:
	if _avatar_scene.contains("AVMJ"):
		return "BIENVENIDA"
	return "BIENVENIDO"
