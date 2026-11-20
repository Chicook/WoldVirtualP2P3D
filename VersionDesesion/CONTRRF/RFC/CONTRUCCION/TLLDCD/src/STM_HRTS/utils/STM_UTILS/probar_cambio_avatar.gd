extends SceneTree
## Comprueba el cambio de avatar en caliente que usa la reasignacion de turnos.
## No arranca la red. El unico uso de user://registro.cfg es el bloque de
## sustitucion, que respalda el perfil real con un nombre unico y lo restaura.
## El mundo falso queda fuera del arbol a proposito (evita abrir el WebSocket);
## por eso Personalizacion avisa de que no puede medir la altura global.

const Turnos = preload("res://gdscrip/Turnos.gd")
const CM := preload("res://gdscrip/ChunkManager.gd")
const PS := preload("res://gdscrip/PlayerSync.gd")

class StubTeleport extends Node:
	var _userbase: Node = null

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

	for ruta in ["res://gdscrip/Boot.gd", "res://gdscrip/Turnos.gd",
			"res://gdscrip/ChunkManager.gd", "res://gdscrip/PlayerSync.gd"]:
		_check(load(ruta) != null, "carga %s" % ruta)

	var avh1: String = Turnos.AVATARES[0]
	var avh2: String = Turnos.AVATARES[2]
	_check(Turnos.genero_de(0) == "hombre" and Turnos.genero_de(2) == "hombre",
			"AVH1 y AVH2 son del mismo genero")

	var cm: Node3D = CM.new()
	cm.name = "MundoFalso"
	var viejo = (load(avh1) as PackedScene).instantiate()
	viejo.name = "USERBASE"
	viejo.position = Vector3(5, 2, -3)
	viejo.rotation.y = 1.2
	cm.add_child(viejo)
	cm.userbase = viejo
	var extra := Node3D.new()
	extra.name = "Extra"
	cm.add_child(extra)
	var tp := StubTeleport.new()
	tp.name = "TeleportManager"
	tp._userbase = viejo
	cm.add_child(tp)
	var ps = PS.new()
	ps.name = "PlayerSync"
	ps._userbase = viejo
	cm.add_child(ps)

	_check(cm._avatar_local() == avh1, "_avatar_local lee el avatar de USERBASE")

	cm.set_player_avatar(avh2)
	var nuevo = cm.userbase
	_check(nuevo != null and nuevo != viejo, "userbase apunta al avatar nuevo")
	_check(nuevo.scene_file_path == avh2, "el avatar nuevo es %s" % avh2.get_file())
	_check(nuevo.name == "USERBASE", "el avatar nuevo conserva el nombre USERBASE")
	_check(nuevo.get_parent() == cm, "el avatar nuevo cuelga del mundo")
	_check(nuevo.position.is_equal_approx(Vector3(5, 2, -3)), "conserva la posicion")
	_check(is_equal_approx(nuevo.rotation.y, 1.2), "conserva la rotacion")
	_check(cm.get_node_or_null("USERBASE") == nuevo, "get_node encuentra el avatar nuevo")
	_check(nuevo.get_index() == 0, "conserva el indice dentro del mundo")
	_check(not is_instance_valid(viejo), "el avatar anterior se libera")
	_check(ps._userbase == nuevo, "PlayerSync apunta al avatar nuevo")
	_check(tp._userbase == nuevo, "TeleportManager apunta al avatar nuevo")
	_check(cm._avatar_local() == avh2, "_avatar_local refleja el cambio")
	_check(cm.avatar_confirmado() == false, "sin confirmacion hasta que responda el anfitrion")

	# Confirmacion del anfitrion con la misma ruta: solo fija turno y aviso.
	cm._aplicar_asignacion_local({"ruta": avh2, "turno": 2, "reciclado": true})
	_check(cm.avatar_confirmado(), "la asignacion confirma el avatar")
	_check(cm.mi_turno() == 2, "guarda el turno asignado")
	_check(cm.mi_reciclado(), "guarda el estado reciclado")

	# Una ruta fuera del catalogo se ignora.
	cm._aplicar_asignacion_local({"ruta": "res://no/existe.tscn", "turno": 9})
	_check(cm.mi_turno() == 2, "una ruta invalida no altera el turno")

	# El sustituto que asigna el anfitrion (plaza ocupada o migracion) cambia el
	# avatar de la sesion, pero nunca reescribe el avatar elegido en el registro.
	var avh3: String = Turnos.AVATARES[4]
	_check(load(avh3) != null and avh3 != avh1, "AVH3 sirve como sustituto distinto")
	var perfil := "user://registro.cfg"
	var respaldo := "user://prueba_avatar_%d_%d.bak" % [
		Time.get_unix_time_from_system(), randi()]
	var habia_perfil := FileAccess.file_exists(perfil)
	if habia_perfil:
		var original := FileAccess.get_file_as_bytes(perfil)
		var f := FileAccess.open(respaldo, FileAccess.WRITE)
		f.store_buffer(original)
		f.close()
	var cfg := ConfigFile.new()
	cfg.set_value("jugador", "nick", "Prueba")
	cfg.set_value("jugador", "avatar_scene", avh1)
	cfg.save(perfil)
	cm._aplicar_asignacion_local({"ruta": avh3, "turno": 4, "reciclado": true})
	_check(cm._avatar_local() == avh3, "el sustituto se aplica en la sesion")
	_check(cm.mi_turno() == 4, "el turno del sustituto se guarda en memoria")
	var releido := ConfigFile.new()
	releido.load(perfil)
	_check(str(releido.get_value("jugador", "avatar_scene", "")) == avh1,
			"el sustituto no pisa el avatar elegido en el registro")
	_check(str(releido.get_value("jugador", "nick", "")) == "Prueba",
			"el sustituto no altera el resto del registro")
	if habia_perfil:
		var f2 := FileAccess.open(respaldo, FileAccess.READ)
		var copia := f2.get_buffer(f2.get_length())
		f2.close()
		var f3 := FileAccess.open(perfil, FileAccess.WRITE)
		f3.store_buffer(copia)
		f3.close()
	else:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(perfil))
	if FileAccess.file_exists(respaldo):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(respaldo))

	cm.free()
	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)
