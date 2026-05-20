extends Control

var udp_server: PacketPeerUDP
var chat_log: RichTextLabel
var chunk_manager: Node3D

func _ready():
	# Configurar el contenedor principal
	set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	size = Vector2(350, 180)
	position = Vector2(15, get_viewport_rect().size.y - 200)
	
	# Crear el Panel translúcido de fondo programáticamente
	var panel = Panel.new()
	panel.name = "Panel"
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.size = Vector2(350, 180)
	add_child(panel)
	
	# Usar StyleBoxEmpty para que no tenga recuadro (fondo invisible y sin bordes)
	var sb_empty = StyleBoxEmpty.new()
	panel.add_theme_stylebox_override("panel", sb_empty)
	
	# Título de cabecera del chat (se oculta para dejar solo los mensajes)
	var title = Label.new()
	title.text = "💬 CHAT DE PROXIMIDAD"
	title.position = Vector2(10, 5)
	title.add_theme_font_size_override("font_size", 11)
	title.add_theme_color_override("font_color", Color(0.4, 0.85, 1.0))
	title.visible = false # Ocultar cabecera
	panel.add_child(title)
	
	# RichTextLabel para el historial de chat con scroll automático
	chat_log = RichTextLabel.new()
	chat_log.name = "ChatLog"
	chat_log.bbcode_enabled = true
	chat_log.scroll_following = true
	chat_log.position = Vector2(0, 0)
	chat_log.size = Vector2(350, 180)
	chat_log.add_theme_font_size_override("normal_font_size", 12)
	panel.add_child(chat_log)

	# Localizar el ChunkManager
	chunk_manager = get_node_or_null("/root/EscenaPrincipal/Metaverso3D/ChunkManager")

	# Inicializar el socket UDP
	udp_server = PacketPeerUDP.new()
	var err = udp_server.bind(50007, "127.0.0.1")
	if err == OK:
		print("Servidor UDP de chat iniciado en 127.0.0.1:50007")
		_add_log_message("[color=#45A29E][System] Canal de chat local enlazado.[/color]")
	else:
		print("Error al iniciar UDP chat server: ", err)
		_add_log_message("[color=#ff4d4d][System] Error al abrir puerto de chat 50007.[/color]")

func _process(_delta):
	# Auto-ajustar altura si el usuario redimensiona la ventana
	var target_y = get_viewport_rect().size.y - 200
	if abs(position.y - target_y) > 1.0:
		position.y = target_y

	# Procesar paquetes UDP entrantes sin bloquear
	if udp_server and udp_server.is_bound():
		while udp_server.get_available_packet_count() > 0:
			var packet = udp_server.get_packet()
			var data_str = packet.get_string_from_utf8()
			_process_chat_packet(data_str)

func _process_chat_packet(json_str: String):
	var json = JSON.new()
	var err = json.parse(json_str)
	if err == OK:
		var data = json.get_data()
		if typeof(data) == TYPE_DICTIONARY and data.get("type") == "chat":
			var user = data.get("user", "Anonymous")
			var text = data.get("text", "")
			
			# Añadir al visor log
			var formatted_msg = "[color=#66FCF1][b]%s:[/b][/color] %s" % [user, text]
			_add_log_message(formatted_msg)
			
			# Disparar la burbuja 3D flotante
			_trigger_bubble_on_avatar(user, text)

func _add_log_message(msg: String):
	if chat_log:
		chat_log.append_text(msg + "\n")

func _trigger_bubble_on_avatar(username: String, message: String):
	if !is_instance_valid(chunk_manager):
		return
		
	var world = chunk_manager.world
	if !is_instance_valid(world):
		return
		
	for user_id in world.active_users:
		var avatar = world.active_users[user_id]
		if is_instance_valid(avatar):
			var is_match = false
			
			# Obtener nombre local si es el avatar local
			var local_name = ""
			var f = FileAccess.open("res://woldvirtual/scene/MTC/users3D/current_user.json", FileAccess.READ)
			if f:
				var content = f.get_as_text()
				f.close()
				var p_json = JSON.new()
				if p_json.parse(content) == OK:
					var p_data = p_json.get_data()
					if typeof(p_data) == TYPE_DICTIONARY:
						local_name = p_data.get("username", "")
			
			if avatar.es_local and username == local_name:
				is_match = true
			elif user_id.to_lower() == username.to_lower() or user_id.to_lower().contains(username.to_lower()):
				is_match = true
				
			# Fallback si sólo hay una persona en escena
			if !is_match and world.active_users.size() == 1:
				is_match = true
				
			if is_match:
				if avatar.has_method("mostrar_mensaje_3d"):
					avatar.mostrar_mensaje_3d(message)
					break
