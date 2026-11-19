extends SceneTree
## Prueba Red.gd (descubrimiento compartido por mundo y sonda) y valida que los
## scripts de la Fase B se cargan sin errores de sintaxis.

const Red = preload("res://gdscrip/Red.gd")
const SCRIPTS := [
	"res://gdscrip/Red.gd",
	"res://gdscrip/Sonda.gd",
	"res://gdscrip/EcoMundo.gd",
	"res://gdscrip/ChunkManager.gd",
	"res://gdscrip/Boot.gd",
	"res://gdscrip/SLAV.gd",
]

var _fallos := 0


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame

	_check(Red.PUERTO_WS == 8911, "puerto WebSocket del mundo")

	var p := Red.parsear_url_host_puerto("https://mi-app.trycloudflare.com:3040/entrar")
	_check(str(p["host"]) == "mi-app.trycloudflare.com", "URL WebNodo: host")
	_check(int(p["port"]) == 8911, "URL WebNodo: puerto se traduce a 8911")

	p = Red.parsear_url_host_puerto("192.168.1.7:9000")
	_check(str(p["host"]) == "192.168.1.7" and int(p["port"]) == 9000, "host:puerto directo se conserva")

	p = Red.parsear_url_host_puerto("woldvirtual://sala.serveo.net/entrar")
	_check(str(p["host"]) == "sala.serveo.net" and int(p["port"]) == 8911, "esquema woldvirtual se resuelve")

	p = Red.parsear_url_host_puerto("http://example.com:8080")
	_check(int(p["port"]) == 8080, "puerto HTTP explicito se conserva")

	_check(Red.resolver_url_ws("192.168.1.7", 8911) == "ws://192.168.1.7:8911",
			"IP LAN -> ws://host:8911")
	_check(Red.resolver_url_ws("mi-app.trycloudflare.com", 8911) == "wss://mi-app.trycloudflare.com",
			"dominio publico -> wss://host")
	_check(Red.resolver_url_ws("wss://ya-resuelto.example.com", 8911) == "wss://ya-resuelto.example.com",
			"URL ya resuelta se devuelve tal cual")
	_check(Red.resolver_url_ws("localhost", 8911) == "ws://localhost:8911",
			"localhost nunca se trata como dominio publico")

	_check(not Red.parece_dominio_publico("localhost"), "localhost no es dominio publico")
	_check(not Red.parece_dominio_publico("127.0.0.1"), "IP no es dominio publico")
	_check(not Red.parece_dominio_publico("pc-salon.local"), "sufijo .local no es dominio publico")
	_check(Red.parece_dominio_publico("abc.serveo.net"), "serveo.net si es dominio publico")

	for ruta in SCRIPTS:
		var script = load(ruta)
		_check(script != null, "carga " + ruta)

	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK   ", texto)
	else:
		_fallos += 1
		print("FALLO ", texto)
