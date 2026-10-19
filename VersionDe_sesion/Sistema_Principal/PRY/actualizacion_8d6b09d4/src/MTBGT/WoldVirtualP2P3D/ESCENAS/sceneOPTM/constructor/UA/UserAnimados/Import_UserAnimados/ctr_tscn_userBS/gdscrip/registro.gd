extends Control
## Fase de registro: muestra el avatar de frente (idle) y pide nick.
## Al confirmar emite registro_completado; el Boot del metaverso escucha
## y pasa a la ventana de carga. Si se ejecuta suelto, cambia de escena.
signal registro_completado(nick: String)
@export var siguiente_escena: String = "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/mnpr.tscn"
@onready var nick_edit: LineEdit = $Panel/VBox/NickEdit
@onready var error_label: Label = $Panel/VBox/ErrorLabel

var _selected_avatar_scene := ""

func _ready() -> void:
	# La cámara de preview manda; apagamos la cámara orbital del avatar instanciado.
	var avatar_cam: Camera3D = $Panel/VBox/ViewportContainer/Viewport/Preview3D/userbaseh1/Camera3D
	if avatar_cam:
		avatar_cam.current = false
	
	# Asegurar que el campo de texto reciba el foco inmediatamente
	if nick_edit:
		nick_edit.grab_focus()


func set_avatar_scene(scene_path: String) -> void:
	_selected_avatar_scene = scene_path
	## Reemplaza el avatar de preview por el que se eligió en el carrusel.
	var ps: PackedScene = load(scene_path)
	if ps == null:
		return
	var host: Node3D = $Panel/VBox/ViewportContainer/Viewport/Preview3D
	var viejo := host.get_node_or_null("userbaseh1")
	if viejo:
		host.remove_child(viejo)
		viejo.queue_free()
	var inst := ps.instantiate()
	inst.name = "AvatarPreview"
	if inst.get("enable_control") != null:
		inst.enable_control = false
	host.add_child(inst)
	for cam in inst.find_children("*", "Camera3D", true, false):
		(cam as Camera3D).current = false
	for ap in inst.find_children("*", "AnimationPlayer", true, false):
		(ap as AnimationPlayer).play("paradoMJ1_1")

func _on_confirmar_pressed() -> void:
	var nick := nick_edit.text.strip_edges()
	if nick.length() < 3:
		error_label.text = "El nick debe tener al menos 3 letras."
		return
	
	# 1. Guardar local en user://registro.cfg
	var cfg := ConfigFile.new()
	cfg.set_value("jugador", "nick", nick)
	cfg.set_value("jugador", "avatar_scene", _selected_avatar_scene)
	cfg.save("user://registro.cfg")
	
	# 2. Generar el hash SHA-256 final del registro de avatar
	var raw_str := nick + "|" + _selected_avatar_scene + "|" + str(Time.get_unix_time_from_system())
	var raw_ctx := HashingContext.new()
	raw_ctx.start(HashingContext.HASH_SHA256)
	raw_ctx.update(raw_str.to_utf8_buffer())
	var hash_bytes := raw_ctx.finish()
	var sha256_hash := hash_bytes.hex_encode()
	
	# 3. Guardar el hash y datos en las rutas test_user_data/user de VSC# y publish_out
	_guardar_hash_usuario(nick, sha256_hash)
	
	registro_completado.emit(nick)
	# Solo cambia de escena si se ejecuta suelto (sin Boot escuchando).
	if get_tree().current_scene == self:
		get_tree().change_scene_to_file(siguiente_escena)

func _guardar_hash_usuario(nick: String, avatar_hash: String) -> void:
	var dict_data := {
		"usuario": nick,
		"avatar_scene": _selected_avatar_scene,
		"hash_sha256": avatar_hash,
		"generado": Time.get_datetime_string_from_system(true, true),
		"estado": "REGISTRADO"
	}
	var json_str := JSON.stringify(dict_data, "\t")
	
	# Rutas destino donde se requiere guardar el hash final
	var targets := [
		"C:/Users/User/Desktop/WoldVirtualP2P3D/VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/publish_out/test_user_data/user",
		"C:/Users/User/Desktop/WoldVirtualP2P3D/VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/test_user_data/user"
	]
	
	for dir_path in targets:
		if not DirAccess.dir_exists_absolute(dir_path):
			DirAccess.make_dir_recursive_absolute(dir_path)
		
		# Guardar avatar_hash.json
		var file_json := FileAccess.open(dir_path + "/avatar_hash.json", FileAccess.WRITE)
		if file_json:
			file_json.store_string(json_str)
			file_json.close()
		
		# Guardar también el hash sha256 en texto plano
		var file_sha := FileAccess.open(dir_path + "/avatar.sha256", FileAccess.WRITE)
		if file_sha:
			file_sha.store_string(avatar_hash)
			file_sha.close()

func _on_nick_text_submitted(_new_text: String) -> void:
	_on_confirmar_pressed()
