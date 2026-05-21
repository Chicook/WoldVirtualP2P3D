extends Control

var udp_server: PacketPeerUDP
var udp_client: PacketPeerUDP
var chunk_manager: Node3D

func _ready():
	# Este nodo ahora es "headless" (sin UI) para delegar el chat al visor C# (WPF).
	# Se mantiene activo únicamente para procesar los sockets UDP y las burbujas 3D de los avatars.
	visible = false

	# Localizar el ChunkManager
	chunk_manager = get_node_or_null("/root/EscenaPrincipal/Metaverso3D/ChunkManager")

	# Inicializar el cliente UDP para enviar mensajes a WPF (puerto 50008)
	udp_client = PacketPeerUDP.new()
	var client_err = udp_client.connect_to_host("127.0.0.1", 50008)
	if client_err == OK:
		print("Cliente UDP de chat conectado a 127.0.0.1:50008")
	else:
		print("Error al conectar cliente UDP: ", client_err)

	# Inicializar el socket UDP para recibir mensajes de WPF (puerto 50007)
	udp_server = PacketPeerUDP.new()
	var err = udp_server.bind(50007, "127.0.0.1")
	if err == OK:
		print("Servidor UDP de chat iniciado en 127.0.0.1:50007")
		_send_system_message_to_wpf("Canal de chat local enlazado.")
	else:
		print("Error al iniciar UDP chat server: ", err)
		_send_system_message_to_wpf("Error al abrir puerto de chat 50007.")

func _process(_delta):
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
			
			# Reenviar el mensaje al visor C# (WPF) para su representación
			_send_chat_message_to_wpf(user, text)
			
			# Disparar la burbuja 3D flotante sobre el avatar correspondiente
			_trigger_bubble_on_avatar(user, text)

func _send_chat_message_to_wpf(user: String, text: String):
	if udp_client:
		var data = {
			"type": "chat",
			"user": user,
			"text": text
		}
		var packet_data = JSON.stringify(data).to_utf8_buffer()
		udp_client.put_packet(packet_data)

func _send_system_message_to_wpf(text: String):
	if udp_client:
		var data = {
			"type": "system",
			"text": text
		}
		var packet_data = JSON.stringify(data).to_utf8_buffer()
		udp_client.put_packet(packet_data)

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
