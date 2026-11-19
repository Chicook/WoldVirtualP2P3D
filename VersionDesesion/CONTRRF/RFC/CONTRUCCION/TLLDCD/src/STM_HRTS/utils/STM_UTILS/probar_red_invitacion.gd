extends SceneTree
## Comprueba que la invitación de la sesión llega a Godot y viaja solo por los
## túneles (wss://), nunca en las conexiones directas de LAN.
##
## Uso:
##   python -m STM_HRTS ejecutar probar_red_invitacion -- \
##     --client --peer-url="https://demo.trycloudflare.com/?invitacion=<32 hex>"

const Red = preload("res://gdscrip/Red.gd")

const TOKEN := "0123456789abcdef0123456789abcdef"


func _initialize() -> void:
	var fallos := 0
	fallos += _comprobar(
		Red.token_de_url("https://demo.trycloudflare.com/?host=https%3A%2F%2Fotro&invitacion=" + TOKEN) == TOKEN,
		"token_de_url extrae la invitación del enlace")
	fallos += _comprobar(
		Red.token_de_url("https://demo.trycloudflare.com/").is_empty(),
		"token_de_url devuelve vacío si no hay invitación")

	fallos += _comprobar(
		Red.resolver_url_ws("demo.trycloudflare.com", 8911, TOKEN) ==
			"wss://demo.trycloudflare.com/?invitacion=" + TOKEN,
		"el túnel wss lleva la invitación")
	fallos += _comprobar(
		Red.resolver_url_ws("demo.trycloudflare.com", 8911) ==
			"wss://demo.trycloudflare.com",
		"sin invitación el túnel queda como antes")
	fallos += _comprobar(
		Red.resolver_url_ws("192.168.1.20", 8911, TOKEN) == "ws://192.168.1.20:8911",
		"la LAN directa no lleva invitación")

	var objetivo := Red.resolver_objetivo()
	fallos += _comprobar(
		str(objetivo.get("invitacion", "")) == TOKEN,
		"resolver_objetivo lee la invitación de --peer-url")
	fallos += _comprobar(
		str(objetivo.get("host", "")) == "demo.trycloudflare.com",
		"resolver_objetivo sigue leyendo el host del túnel")

	print("== red/invitación, fallos=%d ==" % fallos)
	quit(0 if fallos == 0 else 1)


func _comprobar(ok: bool, texto: String) -> int:
	print(("OK   " if ok else "FALLO ") + texto)
	return 0 if ok else 1
