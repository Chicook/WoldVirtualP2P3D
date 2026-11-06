@tool
extends EditorPlugin
## Limpia cache de Godot SIN afectar la logica del metaverso:
##  - Borra imports HUERFANOS de .godot/imported (los que ya no referencia
##    ningun .import), incluidos sus .md5. Nunca borra los recursos en uso.
##  - Vacia .godot/shader_cache y .godot/editor (regenerables).
## Se ejecuta al PARAR la ejecucion y al CERRAR el editor.
## En modo headless (--import / CI) no hace nada.

var _was_playing := false
var _acc := 0.0


func _process(delta: float) -> void:
	if DisplayServer.get_name() == "headless":
		return
	_acc += delta
	if _acc < 1.0:
		return
	_acc = 0.0
	var playing: bool = EditorInterface.is_playing_scene()
	if _was_playing and not playing:
		_limpiar()
	_was_playing = playing


func _exit_tree() -> void:
	if DisplayServer.get_name() == "headless":
		return
	_limpiar()


func _limpiar() -> void:
	var referenced := {}
	_recoger("res://", referenced)

	var imp := "res://.godot/imported"
	var borrados := 0
	var d := DirAccess.open(imp)
	if d != null:
		d.list_dir_begin()
		var f := d.get_next()
		while f != "":
			if not d.current_is_dir() and not referenced.has(f):
				if DirAccess.remove_absolute(ProjectSettings.globalize_path(imp + "/" + f)) == OK:
					borrados += 1
			f = d.get_next()
		d.list_dir_end()

	for sub in ["shader_cache", "editor"]:
		_vaciar("res://.godot/" + sub)

	if borrados > 0:
		print("[limpiar_cache] imports huerfanos borrados: ", borrados)


func _vaciar(path: String) -> void:
	var d := DirAccess.open(path)
	if d == null:
		return
	d.list_dir_begin()
	var f := d.get_next()
	while f != "":
		var full := path.path_join(f)
		if d.current_is_dir():
			_vaciar(full)
			DirAccess.remove_absolute(ProjectSettings.globalize_path(full))
		else:
			DirAccess.remove_absolute(ProjectSettings.globalize_path(full))
		f = d.get_next()
	d.list_dir_end()


func _recoger(path: String, referenced: Dictionary) -> void:
	var d := DirAccess.open(path)
	if d == null:
		return
	d.list_dir_begin()
	var f := d.get_next()
	while f != "":
		var full := path.path_join(f)
		if d.current_is_dir():
			if not f.begins_with("."):
				_recoger(full, referenced)
		elif f.ends_with(".import"):
			var txt := FileAccess.get_file_as_string(full)
			var re := RegEx.new()
			re.compile("res://\\.godot/imported/([^\"\\],\\s]+)")
			for m in re.search_all(txt):
				var fn: String = m.get_string(1)
				referenced[fn] = true
				referenced[fn.get_basename() + ".md5"] = true
		f = d.get_next()
	d.list_dir_end()
