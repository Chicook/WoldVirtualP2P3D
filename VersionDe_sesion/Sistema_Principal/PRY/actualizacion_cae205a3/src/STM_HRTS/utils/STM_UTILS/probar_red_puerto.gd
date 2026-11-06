extends SceneTree
## U-C8 (issue #1): un puerto distinto de 8911 tiene que llegar hasta la URL
## WebSocket real, y ningún destino con puerto explícito puede acabar tratado
## como túnel HTTPS. Cubre las tres fichas por las que pasa un destino:
## `Red.analizar_args` (banderas CLI), `Red.parsear_url_host_puerto` (enlaces) y
## `Red.resolver_url_ws` (URL final que consume ChunkManager/Sonda).
##
## Se lanza sin argumentos de línea de comandos: `analizar_args` es pura desde la
## separación en U4, así que las banderas se le pasan como lista y no hace falta
## relanzar el motor para probar cada escenario.

const Red = preload("res://gdscrip/Red.gd")
const ChunkManager = preload("res://gdscrip/ChunkManager.gd")

var _fallos := 0
var _lineas := 0


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame

	_tabla_de_puertos()
	_banderas_de_comando()
	_enlaces_y_direcciones()
	_url_final()
	_ruta_del_roster()

	print("== RESULTADO RED-PUERTO: %d líneas, %d fallos ==" % [_lineas, _fallos])
	quit(1 if _fallos > 0 else 0)


## Los números compartidos con el C# (VSC#/Nucleo/RedP2P/ConfigRed.cs) no pueden
## divergir sin que alguien lo note: aquí se fija el contrato del lado Godot.
func _tabla_de_puertos() -> void:
	_check(Red.PUERTO_WS == 8911, "Red.PUERTO_WS = 8911")
	_check(Red.PUERTO_BEACON == 8912, "Red.PUERTO_BEACON = 8912")
	_check(Red.PUERTO_API_P2P == 7890, "Red.PUERTO_API_P2P = 7890")
	_check(Red.PUERTO_PORTAL_MIN == 3030 and Red.PUERTO_PORTAL_MAX == 3040,
			"Red.PUERTO_PORTAL_MIN/MAX = 3030/3040")
	_check(ChunkManager.PUERTO_WS == Red.PUERTO_WS,
			"ChunkManager ya no repite el literal: toma el puerto de Red")


## U-C8: el puerto de la bandera llega resuelto, con o sin forma `--clave=valor`.
func _banderas_de_comando() -> void:
	var a: Dictionary = Red.analizar_args(["--ip=192.168.1.50", "--port=9500"])
	_check(str(a["ip"]) == "192.168.1.50" and int(a["port"]) == 9500,
			"--ip= / --port=9500 se leen juntos")

	a = Red.analizar_args(["--client", "--host", "10.0.0.7", "--port", "9500"])
	_check(bool(a["is_client"]) and str(a["ip"]) == "10.0.0.7" and int(a["port"]) == 9500,
			"forma con espacio: --host 10.0.0.7 --port 9500")

	a = Red.analizar_args([])
	_check(int(a["port"]) == 0, "sin bandera de puerto = 0 (lo decide resolver_objetivo)")

	a = Red.analizar_args(["--force-host", "--port=9700"])
	_check(bool(a["force_host"]) and int(a["port"]) == 9700,
			"--force-host conserva su puerto")

	# El enlace de invitación puede traer cualquier puerto propio del portal:
	# el host manda y el puerto se reescribe al del motor.
	a = Red.analizar_args(["--peer-url=https://mi-app.trycloudflare.com:3035/?invitacion=ABCD1234"])
	_check(str(a["ip"]) == "mi-app.trycloudflare.com" and int(a["port"]) == Red.PUERTO_WS,
			"--peer-url del portal: host correcto y puerto reescrito a 8911")
	_check(str(a["invitacion"]) == "ABCD1234", "--peer-url conserva la credencial de la sesión")

	# Antes de U4 el esquema ws:// no se cortaba y el host salía «ws».
	a = Red.analizar_args(["--peer-url=ws://192.168.1.50:9500"])
	_check(str(a["ip"]) == "192.168.1.50" and int(a["port"]) == 9500,
			"--peer-url=ws://ip:puerto deja de partir el host como «ws»")

	a = Red.analizar_args(["wss://mi-app.trycloudflare.com/?invitacion=XYZ"])
	_check(str(a["ip"]) == "mi-app.trycloudflare.com" and str(a["invitacion"]) == "XYZ",
			"un enlace wss:// suelto también se entiende como destino")

	# resolver_objetivo() con las banderas reales del proceso. Dependiente del
	# entorno: si existe un p2p_session.json de usuario, la sesión manda. Se
	# comprueba el puerto cuando el destino es el predeterminado, y se informa
	# de la fuente cuando no, para que el fallo nunca sea silencioso.
	var objetivo: Dictionary = Red.resolver_objetivo()
	var fuente := str(objetivo.get("source", ""))
	if fuente.begins_with("predeterminado"):
		_check(int(objetivo["port"]) == Red.PUERTO_WS,
				"resolver_objetivo sin banderas ni sesión = 8911")
	else:
		print("INFO ", "resolver_objetivo resuelto por: ", fuente,
				" (puerto ", int(objetivo.get('port', 0)), ")")
		_check(int(objetivo["port"]) > 0 and int(objetivo["port"]) <= 65535,
				"resolver_objetivo devuelve puerto válido con la sesión del equipo")


## `parsear_url_host_puerto` es la puerta de entrada de todo enlace escrito por
## el visor C# en p2p_session.json.
func _enlaces_y_direcciones() -> void:
	var p := Red.parsear_url_host_puerto("ws://192.168.1.50:9500")
	_check(str(p["host"]) == "192.168.1.50" and int(p["port"]) == 9500,
			"ws://ip:9500 -> host e ip y puerto 9500")

	p = Red.parsear_url_host_puerto("wss://mi-app.trycloudflare.com:9500")
	_check(str(p["host"]) == "mi-app.trycloudflare.com" and int(p["port"]) == 9500,
			"wss://dominio:9500 -> puerto propio conservado")

	p = Red.parsear_url_host_puerto("192.168.1.50:9500")
	_check(str(p["host"]) == "192.168.1.50" and int(p["port"]) == 9500,
			"ip:9500 sin esquema -> 9500")

	for puerto_rewrite in [3030, 3035, 3040, 7890, 80, 443]:
		p = Red.parsear_url_host_puerto("192.168.1.50:%d" % puerto_rewrite)
		_check(int(p["port"]) == Red.PUERTO_WS,
				"puerto %d es del portal/API/HTTP: se reescribe al del motor" % puerto_rewrite)

	p = Red.parsear_url_host_puerto("https://mi-app.trycloudflare.com/r/1/?invitacion=ABCD")
	_check(str(p["host"]) == "mi-app.trycloudflare.com",
			"el camino y la consulta no ensucian el host")

	_check(Red.limpiar_destino("woldvirtual://sala.serveo.net/entrar") == "sala.serveo.net",
			"limpiar_destino recorta esquema y camino")
	_check(Red.lleva_puerto_explicito("10.0.0.7:9500"), "lleva_puerto_explicito: 10.0.0.7:9500")
	_check(not Red.lleva_puerto_explicito("10.0.0.7"), "lleva_puerto_explicito: 10.0.0.7 no")
	_check(not Red.lleva_puerto_explicito("tunel.example.com"), "lleva_puerto_explicito: dominio no")


## La URL final: aquí es donde el puerto tiene que verse, o la prueba no vale.
func _url_final() -> void:
	_check(Red.resolver_url_ws("192.168.1.50", 9500) == "ws://192.168.1.50:9500",
			"U-C8: IP LAN con puerto 9500 llega a ws://192.168.1.50:9500")
	_check(Red.resolver_url_ws("192.168.1.50", 0) == "ws://192.168.1.50:8911",
			"puerto inválido (0) cae al predeterminado")
	_check(Red.resolver_url_ws("192.168.1.50", 70000) == "ws://192.168.1.50:8911",
			"puerto fuera de rango cae al predeterminado")
	_check(Red.resolver_url_ws("localhost", 9500) == "ws://localhost:9500",
			"localhost con puerto propio")
	_check(Red.resolver_url_ws("mi-app.trycloudflare.com", 9500) == "wss://mi-app.trycloudflare.com",
			"dominio público: el túnel manda, se omite el puerto")
	_check(Red.resolver_url_ws("10.0.0.7:9500", Red.PUERTO_WS) == "ws://10.0.0.7:9500",
			"destino con puerto explícito NO se convierte en wss://")
	_check(Red.resolver_url_ws("https://mi-app.trycloudflare.com", Red.PUERTO_WS)
			== "wss://mi-app.trycloudflare.com",
			"enlace https:// del roster no produce wss://https://")
	_check(Red.resolver_url_ws("https://mi-app.trycloudflare.com:3035/", Red.PUERTO_WS)
			== "wss://mi-app.trycloudflare.com:3035",
			"enlace https:// con puerto del portal: conserva el destino limpio")
	_check(Red.resolver_url_ws("mi-app.trycloudflare.com", 8911, "ABCD 1234")
			== "wss://mi-app.trycloudflare.com/?invitacion=ABCD%201234",
			"la credencial se añade cifrada y una sola vez")


## ChunkManager arma la URL del anfitrión a partir del roster que le llega por
## RPC (`_reportar_direccion`), no de las banderas: es la ruta de migración.
func _ruta_del_roster() -> void:
	var cm = ChunkManager.new()
	_check(str(cm._url_candidato({"url": "wss://mi-app.trycloudflare.com"}))
			== "wss://mi-app.trycloudflare.com",
			"roster con URL de túnel: viaja intacta")
	_check(str(cm._url_candidato({"url": "192.168.1.50:9500"})) == "ws://192.168.1.50:9500",
			"roster con ip:9500: U-C8 se cumple también en la migración")
	_check(str(cm._url_candidato({"url": "https://mi-app.trycloudflare.com"}))
			== "wss://mi-app.trycloudflare.com",
			"roster con https://: no sale wss://https://")
	_check(str(cm._url_candidato({"url": ""})) == "", "roster sin URL: candidato vacío")
	cm.free()


func _check(ok: bool, texto: String) -> void:
	_lineas += 1
	if ok:
		print("OK   ", texto)
	else:
		_fallos += 1
		print("FALLO ", texto)
