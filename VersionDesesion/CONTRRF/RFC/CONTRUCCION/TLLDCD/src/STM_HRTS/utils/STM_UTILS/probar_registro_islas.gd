extends SceneTree
## Prueba la identidad persistente, la resolución de isla reclamada y los
## botones del explorador. Usa un config aislado y no abre la red.

const Identidad = preload("res://gdscrip/Identidad.gd")
const CM := preload("res://gdscrip/ChunkManager.gd")
const TeleportManager := preload("res://gdscrip/TeleportManager.gd")
const TeleportPanel := preload("res://gdscrip/TeleportPanel.gd")
const RUTA := "user://prueba_identidad.cfg"
const RUTA_ISLAS := "user://prueba_islas_registro.cfg"
const OTRO_UUID := "0123456789abcdef0123456789abcdef"

var _fallos := 0


class StubManager extends Node:
	signal islands_updated(islands: Array)
	signal isla_registrada(exito: bool, mensaje: String)
	var llamadas := 0

	func get_islands() -> Array:
		return []

	func current_island_index(_pos: Vector3) -> int:
		return -1

	func teleport_to(_index: int) -> bool:
		return true

	func registrar_mi_isla() -> void:
		llamadas += 1
		isla_registrada.emit(true, "Isla 0 registrada para la prueba.")


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	if FileAccess.file_exists(RUTA):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(RUTA))
	var cfg := ConfigFile.new()
	cfg.set_value("jugador", "nick", "Ana")
	cfg.set_value("posicion", "has_saved_pos", true)
	cfg.save(RUTA)

	var uuid := Identidad.asegurar_identidad(RUTA)
	_check(Identidad.uuid_valido(uuid), "crea un UUID de 32 hex")
	_check(Identidad.asegurar_identidad(RUTA) == uuid, "el UUID se conserva al releer")
	var releido := ConfigFile.new()
	releido.load(RUTA)
	_check(str(releido.get_value("jugador", "nick", "")) == "Ana",
			"crear identidad no pierde el nick")
	_check(bool(releido.get_value("posicion", "has_saved_pos", false)),
			"crear identidad no pierde la posición")

	_check(Identidad.guardar_mi_isla(3, uuid, RUTA), "guarda la isla propia")
	_check(Identidad.leer_mi_isla(uuid, RUTA) == 3, "lee la isla de su identidad")
	_check(Identidad.leer_mi_isla(OTRO_UUID, RUTA) == -1,
			"otra identidad no hereda la isla")
	_check(not Identidad.guardar_mi_isla(-1, uuid, RUTA), "rechaza índices negativos")
	_check(not Identidad.guardar_mi_isla(4, "no-es-uuid", RUTA), "rechaza UUID inválido")
	if FileAccess.file_exists(RUTA):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(RUTA))

	var cm: Node3D = CM.new()
	cm._islas_por_uuid = {uuid: 3}
	cm._uuid_por_isla = {3: uuid, 4: OTRO_UUID}
	_check(cm._resolver_isla_reclamada(2, 3, uuid) == 3,
			"recupera la isla registrada por UUID")
	_check(cm._resolver_isla_reclamada(2, 99, uuid) == 3,
			"el UUID registrado manda sobre un índice viejo")
	_check(cm._resolver_isla_reclamada(2, 3, OTRO_UUID) == -1,
			"impide apropiarse de la isla de otra identidad")
	_check(cm._resolver_isla_reclamada(2, 4, OTRO_UUID) == 4,
			"reconoce la isla de la segunda identidad")
	_check(cm.has_signal("isla_registrada") and cm.has_method("registrar_mi_isla"),
			"ChunkManager expone el registro al panel")
	cm.free()

	var tm: Node3D = TeleportManager.new()
	_check(tm.has_signal("isla_registrada") and tm.has_method("registrar_mi_isla"),
			"TeleportManager reemite el registro")
	tm.free()

	var registro := ConfigFile.new()
	registro.set_value("propietarios", uuid, 7)
	registro.save(RUTA_ISLAS)
	var cargado: Node3D = CM.new()
	cargado._registro_islas_ruta = RUTA_ISLAS
	cargado._cargar_registro_islas()
	_check(int(cargado._islas_por_uuid.get(uuid, -1)) == 7,
			"el anfitrión recarga el UUID registrado")
	_check(str(cargado._uuid_por_isla.get(7, "")) == uuid,
			"el índice recuperado apunta al UUID")
	_check(cargado.next_island_index >= 8,
			"el siguiente índice no reutiliza el registrado")
	cargado.free()
	if FileAccess.file_exists(RUTA_ISLAS):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(RUTA_ISLAS))

	var mundo := Node3D.new()
	mundo.name = "MundoPanel"
	var manager := StubManager.new()
	manager.name = "TeleportManager"
	mundo.add_child(manager)
	var userbase := Node3D.new()
	userbase.name = "USERBASE"
	mundo.add_child(userbase)
	var panel = TeleportPanel.new()
	panel.name = "TeleportPanel"
	mundo.add_child(panel)
	get_root().add_child(mundo)
	await process_frame
	await process_frame
	_check(panel.toggle_btn.text == "Explorador de islas", "renombra el botón del panel")
	_check(panel.register_btn.text == "Registra tu isla", "añade el botón de registro")
	_check(panel.register_btn.visible, "el botón de registro es visible")
	panel._on_register_island_pressed()
	await process_frame
	_check(manager.llamadas == 1, "el botón invoca el registro del gestor")
	_check("Registro correcto" in panel.location_lbl.text,
			"la interfaz muestra la respuesta del registro")
	mundo.queue_free()
	await process_frame

	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK   ", texto)
	else:
		print("FALLO ", texto)
		_fallos += 1
