extends SceneTree
## Anfitrion de prueba para la Sonda: levanta un servidor WebSocket en 8911 y
## responde a la consulta de plazas con un mundo simulado. Se usa junto a
## tools/probar_sonda_invitado.gd (dos procesos Godot).

const Sonda = preload("res://gdscrip/Sonda.gd")

var _mundo: MundoSonda


class MundoSonda extends Node3D:
	var consultas := []

	## Plazas simuladas: avatares 0 y 3 reservados.
	func turnos_snapshot() -> Dictionary:
		return {0: 1, 3: 2}

	func marcar_sonda(id: int) -> void:
		consultas.append(id)


func _initialize() -> void:
	await process_frame
	var boot := Node.new()
	boot.name = "Boot"
	get_root().add_child(boot)

	var sonda = Sonda.new()
	sonda.name = "Sonda"
	boot.add_child(sonda)

	_mundo = MundoSonda.new()
	_mundo.name = "ISLA3Dblock"
	boot.add_child(_mundo)

	var peer := WebSocketMultiplayerPeer.new()
	var err := peer.create_server(8911)
	if err != OK:
		print("HOST_ERROR=", err)
		quit(1)
		return
	boot.multiplayer.multiplayer_peer = peer
	print("HOST_LISTO")

	await create_timer(15.0).timeout
	print("HOST_FIN sondas=%d" % _mundo.consultas.size())
	quit(0 if _mundo.consultas.size() == 1 else 1)
