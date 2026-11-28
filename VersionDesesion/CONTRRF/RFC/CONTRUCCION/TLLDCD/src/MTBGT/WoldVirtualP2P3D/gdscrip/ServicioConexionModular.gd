extends Node
## Cliente modular del servidor C# de DAO. Los invitados envían las llamadas
## por RPC a través de Sonda; solo el anfitrión abre el buzón local por archivos.

signal miembros_actualizados(miembros: Array)

const NOMBRE_SERVIDOR := "WoldVirtualP2P3D.Servidor.exe"
const TIEMPO_ESPERA_MS := 15000

var _raiz_ipc := ""
var _pid_servidor := 0
var _contador := 0
var _miembro_id := ""
var _sonda: Node
var _timer_presencia: Timer


func _ready() -> void:
	_raiz_ipc = OS.get_environment("WVP_IPC_DIR").strip_edges()
	if _raiz_ipc.is_empty():
		_raiz_ipc = ProjectSettings.globalize_path("user://wvp-ipc")
	_crear_buzones()
	_iniciar_servidor_si_corresponde()
	_timer_presencia = Timer.new()
	_timer_presencia.wait_time = 8.0
	_timer_presencia.timeout.connect(_enviar_heartbeat)
	add_child(_timer_presencia)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_PREDELETE:
		if _pid_servidor > 0 and OS.is_process_running(_pid_servidor):
			OS.kill(_pid_servidor)


func establecer_sonda(sonda: Node) -> void:
	_sonda = sonda


func habilitado() -> bool:
	return OS.get_environment("WVP_MODULAR_DAO") != "0"


func solicitar(metodo: String, ruta: String, datos: Dictionary = {}, sonda: Node = null) -> Dictionary:
	if not habilitado():
		return {"ok": false, "status": 503, "body": {"error": "Servicio modular desactivado."}}
	var api_multijugador: MultiplayerAPI = get_tree().get_multiplayer() if is_inside_tree() else null
	var peer: MultiplayerPeer = api_multijugador.multiplayer_peer if api_multijugador != null else null
	if peer != null and peer.get_connection_status() == MultiplayerPeer.CONNECTION_CONNECTED:
		if api_multijugador.is_server():
			return await solicitud_local(metodo, ruta, datos)
		var transporte := sonda if sonda != null else _sonda_actual()
		if transporte != null and transporte.has_method("solicitar_modular"):
			return await transporte.call("solicitar_modular", metodo, ruta, datos)
		return {"ok": false, "status": 503, "body": {"error": "No se encontró Sonda para reenviar al anfitrión."}}
	if OS.get_environment("WVP_LAUNCH_SERVER") == "1" or DirAccess.dir_exists_absolute(_raiz_ipc.path_join("requests")):
		return await solicitud_local(metodo, ruta, datos)
	return {"ok": false, "status": 503, "body": {"error": "No hay sesión conectada ni servidor DAO local."}}


func solicitud_local(metodo: String, ruta: String, datos: Dictionary = {}) -> Dictionary:
	_crear_buzones()
	var id := _nuevo_id()
	var ruta_peticion := _raiz_ipc.path_join("requests").path_join(id + ".req")
	var temporal := ruta_peticion + ".tmp"
	var archivo := FileAccess.open(temporal, FileAccess.WRITE)
	if archivo == null:
		return {"ok": false, "status": 500, "body": {"error": "No se puede escribir en el buzón DAO."}}
	archivo.store_string(JSON.stringify({"id": id, "method": metodo, "path": ruta, "body": datos}))
	archivo.close()
	var renombrar := DirAccess.rename_absolute(temporal, ruta_peticion)
	if renombrar != OK:
		return {"ok": false, "status": 500, "body": {"error": "No se pudo enviar la llamada al servidor DAO."}}

	var ruta_respuesta := _raiz_ipc.path_join("responses").path_join(id + ".res")
	var limite := Time.get_ticks_msec() + TIEMPO_ESPERA_MS
	while Time.get_ticks_msec() < limite:
		if not is_inside_tree() or get_tree() == null:
			return {"ok": false, "status": 503, "body": {"error": "El servicio DAO todavía no está conectado al árbol de escena."}}
		if FileAccess.file_exists(ruta_respuesta):
			var respuesta: Variant = JSON.parse_string(FileAccess.get_file_as_string(ruta_respuesta))
			DirAccess.remove_absolute(ruta_respuesta)
			if typeof(respuesta) != TYPE_DICTIONARY:
				return {"ok": false, "status": 502, "body": {"error": "Respuesta IPC mal formada."}}
			var estado := int(respuesta.get("status", 500))
			return {"ok": estado >= 200 and estado < 300, "status": estado, "body": respuesta.get("body", {})}
		var arbol := get_tree()
		if arbol == null:
			return {"ok": false, "status": 503, "body": {"error": "El servicio DAO perdió el árbol de escena durante la solicitud."}}
		await arbol.create_timer(0.05).timeout
	return {"ok": false, "status": 504, "body": {"error": "El servidor modular DAO no respondió a tiempo."}}


func conectar(nick: String, sonda: Node = null) -> Dictionary:
	return await solicitar("POST", "/api/session/connect", {"nick": nick}, sonda)


func registrar(token: String, nick: String, avatar: String, sonda: Node = null) -> Dictionary:
	return await solicitar("POST", "/api/dao/register",
		{"token": token, "nick": nick, "avatar": avatar}, sonda)


func activar_presencia(id: String) -> void:
	_miembro_id = id
	if _timer_presencia != null and not id.is_empty():
		_timer_presencia.start()
		_enviar_heartbeat()


func refrescar_miembros(sonda: Node = null) -> Dictionary:
	var resultado := await solicitar("GET", "/api/dao/members", {}, sonda)
	if bool(resultado.get("ok", false)) and typeof(resultado.get("body")) == TYPE_ARRAY:
		miembros_actualizados.emit(resultado.body)
	return resultado


func _enviar_heartbeat() -> void:
	if _miembro_id.is_empty():
		return
	var resultado: Dictionary = await solicitar("POST", "/api/dao/heartbeat", {"id": _miembro_id})
	if not bool(resultado.get("ok", false)):
		push_warning("[DAO modular] No se pudo renovar la presencia: %s" % str(resultado.get("body", {})))
	else:
		await refrescar_miembros()


func _iniciar_servidor_si_corresponde() -> void:
	if OS.get_environment("WVP_LAUNCH_SERVER") != "1":
		return
	var ejecutable := OS.get_environment("WVP_SERVER_EXE").strip_edges()
	if ejecutable.is_empty():
		var directorio := OS.get_executable_path().get_base_dir()
		ejecutable = directorio.path_join("Servidor").path_join(NOMBRE_SERVIDOR)
	if not FileAccess.file_exists(ejecutable):
		push_error("[DAO modular] No se encuentra el servidor C#: " + ejecutable)
		return
	var puerto := OS.get_environment("WVP_PORT").strip_edges()
	if puerto.is_empty():
		puerto = "8765"
	_pid_servidor = OS.create_process(ejecutable,
		PackedStringArray(["--urls", "http://0.0.0.0:" + puerto]), false)
	if _pid_servidor <= 0:
		push_error("[DAO modular] No se pudo iniciar el servidor C#.")
	else:
		print("[DAO modular] Servidor local iniciado; IPC: ", _raiz_ipc)


func _crear_buzones() -> void:
	DirAccess.make_dir_recursive_absolute(_raiz_ipc.path_join("requests"))
	DirAccess.make_dir_recursive_absolute(_raiz_ipc.path_join("responses"))


func _nuevo_id() -> String:
	_contador += 1
	return "%d-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec(), _contador]


func _sonda_actual() -> Node:
	if is_instance_valid(_sonda):
		return _sonda
	_sonda = get_tree().root.find_child("Sonda", true, false)
	return _sonda
