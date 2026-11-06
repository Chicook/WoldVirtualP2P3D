extends SceneTree
## Invitado de prueba para la Sonda: pregunta al anfitrion de
## tools/probar_sonda_anfitrion.gd (ws://127.0.0.1:8911) que plazas estan
## ocupadas y comprueba la respuesta.

const Sonda = preload("res://gdscrip/Sonda.gd")


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var boot := Node.new()
	boot.name = "Boot"
	get_root().add_child(boot)

	var sonda = Sonda.new()
	sonda.name = "Sonda"
	boot.add_child(sonda)

	var plazas := []
	for _intento in 8:
		plazas = await sonda.consultar(1500)
		if not plazas.is_empty():
			break
		await create_timer(0.4).timeout

	var ok: bool = plazas.size() == 2 and int(plazas[0]) == 0 and int(plazas[1]) == 3
	print("GUEST_PLAZAS=", plazas)
	print("== fin, fallos=%d ==" % (0 if ok else 1))
	quit(0 if ok else 1)
