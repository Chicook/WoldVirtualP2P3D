extends RefCounted
## Resolucion del destino de red P2P: argumentos CLI, p2p_session.json y beacon LAN.
## La usan ChunkManager (mundo) y Sonda (consulta antes del carrusel) para que
## ambos lados interpreten las mismas banderas (REGLAS_DE_ACTUALIZACION R8).

const PUERTO_WS := 8911


## Devuelve {host, port, force_host, is_client, source}.
static func resolver_objetivo() -> Dictionary:
	var res := {
		"host": "127.0.0.1",
		"port": PUERTO_WS,
		"force_host": false,
		"is_client": false,
		"source": "predeterminado (loopback local)"
	}

	# 1. Argumentos de linea de comandos (motor y usuario).
	var all_args: Array = OS.get_cmdline_args()
	all_args.append_array(OS.get_cmdline_user_args())
	print("[Red/WS] Args evaluados para resolver rol/host: ", all_args)

	var cli_ip := ""
	var cli_port := 0
	var cli_is_client := false
	var cli_force_host := false

	for i in range(all_args.size()):
		var arg: String = str(all_args[i]).strip_edges()
		if arg == "--client":
			cli_is_client = true
		elif arg == "--force-host" or arg == "--server":
			cli_force_host = true
		elif arg.begins_with("--ip="):
			cli_ip = arg.get_slice("=", 1).strip_edges().replace("\"", "").replace("'", "")
		elif arg.begins_with("--host="):
			cli_ip = arg.get_slice("=", 1).strip_edges().replace("\"", "").replace("'", "")
		elif arg.begins_with("--port="):
			cli_port = int(arg.get_slice("=", 1).strip_edges())
		elif arg == "--ip" or arg == "-ip" or arg == "--host":
			if i + 1 < all_args.size() and not str(all_args[i + 1]).begins_with("-"):
				cli_ip = str(all_args[i + 1]).strip_edges().replace("\"", "").replace("'", "")
		elif arg == "--port":
			if i + 1 < all_args.size() and not str(all_args[i + 1]).begins_with("-"):
				cli_port = int(str(all_args[i + 1]).strip_edges())
		elif arg.begins_with("--peer-url="):
			var url := arg.get_slice("=", 1).strip_edges().replace("\"", "").replace("'", "")
			if not url.is_empty():
				var parsed := parsear_url_host_puerto(url)
				if not parsed.get("host", "").is_empty():
					cli_ip = parsed["host"]
					if cli_port == 0:
						cli_port = parsed["port"]
		elif arg.begins_with("http://") or arg.begins_with("https://") or arg.begins_with("woldvirtual://"):
			var parsed := parsear_url_host_puerto(arg)
			if not parsed.get("host", "").is_empty():
				cli_ip = parsed["host"]
				if cli_port == 0:
					cli_port = parsed["port"]

	if cli_force_host:
		res["force_host"] = true
		res["source"] = "Linea de comandos (--force-host / --server)"
		return res

	if not cli_ip.is_empty():
		var final_port := cli_port if cli_port > 0 else PUERTO_WS
		res["host"] = cli_ip
		res["port"] = final_port
		res["is_client"] = true
		res["source"] = "Linea de comandos (--client / --ip / --peer-url)"
		return res

	if cli_is_client:
		res["is_client"] = true

	# 2. p2p_session.json escrito por el Visor C#.
	var posibles_rutas := [
		"user://p2p_session.json",
		"res://p2p_session.json",
		OS.get_executable_path().get_base_dir().path_join("test_user_data/user/p2p_session.json"),
		OS.get_executable_path().get_base_dir().path_join("p2p_session.json")
	]

	for ruta in posibles_rutas:
		if FileAccess.file_exists(ruta):
			var fa := FileAccess.open(ruta, FileAccess.READ)
			if fa:
				var txt := fa.get_as_text()
				fa.close()
				var j = JSON.parse_string(txt)
				if j is Dictionary:
					var remote_ip: String = str(j.get("remoteIp", "")).strip_edges()
					var remote_port: int = int(j.get("remotePort", PUERTO_WS))
					var es_cliente: bool = bool(j.get("esCliente", false))
					var es_primero: bool = bool(j.get("esPrimerUsuario", false))
					var p_url: String = str(j.get("peerUrl", "")).strip_edges()

					if not remote_ip.is_empty() and remote_ip != "127.0.0.1" and remote_ip != "localhost":
						res["host"] = remote_ip
						res["port"] = remote_port if remote_port > 0 else PUERTO_WS
						res["is_client"] = true
						res["source"] = "p2p_session.json (remoteIp explicito: " + ruta + ")"
						return res

					if not p_url.is_empty():
						var parsed := parsear_url_host_puerto(p_url)
						if not parsed.get("host", "").is_empty() and parsed["host"] != "127.0.0.1" and parsed["host"] != "localhost":
							res["host"] = parsed["host"]
							res["port"] = parsed["port"]
							res["is_client"] = true
							res["source"] = "p2p_session.json (peerUrl: " + ruta + ")"
							return res

					if es_primero:
						res["force_host"] = true
						res["source"] = "p2p_session.json (esPrimerUsuario=true)"
						return res

	# 3. Auto-descubrimiento en red local (beacon UDP).
	var lan_host := buscar_host_en_lan(350)
	if not lan_host.is_empty():
		res["host"] = lan_host["host"]
		res["port"] = int(lan_host.get("port", PUERTO_WS))
		res["is_client"] = true
		res["source"] = "Auto-descubrimiento en red local (Beacon UDP LAN)"
		return res

	return res


## URL WebSocket del anfitrion a partir del host/puerto resueltos.
## - Túneles HTTP (cloudflared / serveo / localhost.run) -> wss://<host>
## - IP o nombre LAN -> ws://host:8911
static func resolver_url_ws(host: String, _port: int) -> String:
	var h := host.strip_edges()
	if h.begins_with("ws://") or h.begins_with("wss://"):
		return h
	if parece_dominio_publico(h):
		return "wss://%s" % h
	return "ws://%s:%d" % [h, PUERTO_WS]


## True para nombres de dominio enroutables por Internet (no IP, no LAN).
static func parece_dominio_publico(h: String) -> bool:
	var bajo := h.to_lower()
	if bajo.is_empty() or bajo == "localhost":
		return false
	if bajo.is_valid_ip_address():
		return false
	for sufijo in [".local", ".lan", ".home", ".internal", ".localdomain"]:
		if bajo.ends_with(sufijo):
			return false
	return bajo.contains(".")


static func parsear_url_host_puerto(url_str: String) -> Dictionary:
	var clean := url_str.strip_edges().replace("\"", "").replace("'", "")
	clean = clean.replace("https://", "").replace("http://", "").replace("woldvirtual://", "").strip_edges()
	if clean.contains("/"):
		clean = clean.split("/")[0]
	var host := clean
	var port := PUERTO_WS
	if clean.contains(":"):
		var partes := clean.split(":")
		host = partes[0].strip_edges()
		var p := int(partes[1].strip_edges())
		# 3030..3040 (WebNodo), 7890 (API P2P), 80/443 (HTTP) -> WebSocket del motor.
		if (p >= 3030 and p <= 3040) or p == 7890 or p == 80 or p == 443:
			port = PUERTO_WS
		elif p > 0 and p <= 65535:
			port = p
	return {"host": host, "port": port}


static func buscar_host_en_lan(timeout_ms: int = 350) -> Dictionary:
	var listener := PacketPeerUDP.new()
	var bind_err := listener.bind(8912)
	if bind_err != OK:
		return {}

	var start_time := Time.get_ticks_msec()
	while Time.get_ticks_msec() - start_time < timeout_ms:
		OS.delay_msec(25)
		if listener.get_available_packet_count() > 0:
			var pkt := listener.get_packet()
			var msg := pkt.get_string_from_utf8()
			var sender_ip := listener.get_packet_ip()
			if msg.begins_with("WOLDVIRTUAL_HOST") and not sender_ip.is_empty():
				var mis_ips := IP.get_local_addresses()
				if not mis_ips.has(sender_ip) and sender_ip != "127.0.0.1":
					listener.close()
					print("[Red/WS] Par anfitrion detectado en LAN: ", sender_ip, ":", PUERTO_WS)
					return {"host": sender_ip, "port": PUERTO_WS}
	listener.close()
	return {}
