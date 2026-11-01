extends SceneTree
## Reparacion del avatar elegido cuando `avatar_scene` quedo con un sustituto.
## Copia el perfil real (`registro.cfg` + `avatar_hash.json`) con nombres unicos,
## prueba sobre ficheros de verdad y lo deja como estaba.

const Boot = preload("res://gdscrip/Boot.gd")
const Turnos = preload("res://gdscrip/Turnos.gd")

const PERFIL := "user://registro.cfg"
const REGISTRO := "user://avatar_hash.json"

var _fallos := 0


func _initialize() -> void:
	_correr()


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK   ", texto)
	else:
		print("FALLO ", texto)
		_fallos += 1


func _leer(ruta: String) -> PackedByteArray:
	if not FileAccess.file_exists(ruta):
		return PackedByteArray()
	var f := FileAccess.open(ruta, FileAccess.READ)
	var datos := f.get_buffer(f.get_length())
	f.close()
	return datos


func _escribir(ruta: String, datos: PackedByteArray) -> void:
	if datos.is_empty():
		if FileAccess.file_exists(ruta):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(ruta))
		return
	var f := FileAccess.open(ruta, FileAccess.WRITE)
	f.store_buffer(datos)
	f.close()


func _correr() -> void:
	await process_frame
	var sufijo := "%d_%d" % [Time.get_unix_time_from_system(), randi()]
	var respaldo_perfil := "user://prueba_reparar_%s.cfg.bak" % sufijo
	var respaldo_registro := "user://prueba_reparar_%s.json.bak" % sufijo
	var perfil_original := _leer(PERFIL)
	var registro_original := _leer(REGISTRO)
	_escribir(respaldo_perfil, perfil_original)
	_escribir(respaldo_registro, registro_original)

	var elegido: String = Turnos.AVATARES[4]
	var sustituto: String = Turnos.AVATARES[2]
	_check(elegido != sustituto, "elegido y sustituto son avatares distintos")

	# Perfil danado: el registro dice `elegido`, `avatar_scene` quedo con el sustituto.
	var cfg := ConfigFile.new()
	cfg.set_value("jugador", "nick", "Ana")
	cfg.set_value("jugador", "avatar_scene", sustituto)
	cfg.save(PERFIL)
	var registro := {"estado": "REGISTRADO", "usuario": "Ana", "avatar_scene": elegido}
	_escribir(REGISTRO, JSON.stringify(registro).to_utf8_buffer())

	var boot = Boot.new()
	_check(boot._reparar_avatar(cfg, sustituto, "Ana") == elegido,
			"devuelve el avatar elegido en el registro")
	var releido := ConfigFile.new()
	releido.load(PERFIL)
	_check(str(releido.get_value("jugador", "avatar_scene", "")) == elegido,
			"guarda el avatar reparado en el perfil")
	_check(bool(releido.get_value("jugador", "avatar_reparado", false)),
			"marca la reparacion como hecha")
	_check(str(releido.get_value("jugador", "nick", "")) == "Ana",
			"no pierde el nick")

	# Segunda vez: no se repite, para no pisar un cambio de avatar posterior.
	var cfg2 := ConfigFile.new()
	cfg2.set_value("jugador", "nick", "Ana")
	cfg2.set_value("jugador", "avatar_scene", sustituto)
	cfg2.set_value("jugador", "avatar_reparado", true)
	cfg2.save(PERFIL)
	_check(boot._reparar_avatar(cfg2, sustituto, "Ana") == sustituto,
			"con la reparacion ya hecha no se vuelve a cambiar")

	# Otra persona en el mismo PC no hereda la reparacion.
	var cfg3 := ConfigFile.new()
	cfg3.set_value("jugador", "nick", "Ana")
	cfg3.set_value("jugador", "avatar_scene", sustituto)
	cfg3.save(PERFIL)
	_check(boot._reparar_avatar(cfg3, sustituto, "Beto") == sustituto,
			"un registro de otro nick no repara el perfil")

	# Sin registro de avatar no hay nada que reparar.
	DirAccess.remove_absolute(ProjectSettings.globalize_path(REGISTRO))
	var cfg4 := ConfigFile.new()
	cfg4.set_value("jugador", "nick", "Ana")
	cfg4.set_value("jugador", "avatar_scene", sustituto)
	cfg4.save(PERFIL)
	_check(boot._reparar_avatar(cfg4, sustituto, "Ana") == sustituto,
			"sin avatar_hash.json se respeta el perfil")
	boot.free()

	_escribir(PERFIL, perfil_original)
	_escribir(REGISTRO, registro_original)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(respaldo_perfil))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(respaldo_registro))

	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)
