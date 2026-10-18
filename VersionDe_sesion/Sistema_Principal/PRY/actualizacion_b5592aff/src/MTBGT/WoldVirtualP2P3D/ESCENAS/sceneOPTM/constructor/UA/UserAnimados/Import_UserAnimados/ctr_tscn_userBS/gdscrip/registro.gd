extends Control
## Fase de registro: muestra el avatar de frente (idle) y pide nick.
## Al confirmar emite registro_completado; el Boot del metaverso escucha
## y pasa a la ventana de carga. Si se ejecuta suelto, cambia de escena.
signal registro_completado(nick: String)
@export var siguiente_escena: String = "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/mnpr.tscn"
@onready var nick_edit: LineEdit = $Panel/VBox/NickEdit
@onready var error_label: Label = $Panel/VBox/ErrorLabel

func _ready() -> void:
	# La cámara de preview manda; apagamos la cámara orbital del avatar instanciado.
	var avatar_cam: Camera3D = $Panel/VBox/ViewportContainer/Viewport/Preview3D/userbaseh1/Camera3D
	if avatar_cam:
		avatar_cam.current = false


func set_avatar_scene(scene_path: String) -> void:
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
	# Guarda el nick para usarlo en el juego.
	var cfg := ConfigFile.new()
	cfg.set_value("jugador", "nick", nick)
	cfg.save("user://registro.cfg")
	registro_completado.emit(nick)
	# Solo cambia de escena si se ejecuta suelto (sin Boot escuchando).
	if get_tree().current_scene == self:
		get_tree().change_scene_to_file(siguiente_escena)

func _on_nick_text_submitted(_new_text: String) -> void:
	_on_confirmar_pressed()
