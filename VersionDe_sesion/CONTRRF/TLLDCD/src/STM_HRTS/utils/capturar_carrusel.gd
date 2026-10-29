extends SceneTree
## Captura el carrusel en ventana para revisar turnos y escalas.
## Uso: godot --path . --script res://tools/capturar_carrusel.gd

const RUTA := "res://SLCAV/AVATARESCONANIMACION/SLAV.tscn"
const PASOS := [0, 1, 7, 8, 11, 15, 16, 17, 19, 23]


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var salida := OS.get_environment("CARRUSEL_DIR")
	if salida.is_empty():
		salida = OS.get_user_data_dir().path_join("carrusel")
	DirAccess.make_dir_recursive_absolute(salida)
	var carrusel := (load(RUTA) as PackedScene).instantiate()
	get_root().add_child(carrusel)
	get_root().size = Vector2i(1280, 720)
	await process_frame
	var actual := 0
	for objetivo in PASOS:
		while actual < objetivo:
			carrusel._move(1)
			actual += 1
			await process_frame
		for _i in 24:
			await process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var destino := salida.path_join("%02d_%s.png" % [objetivo, carrusel.avatar_names[objetivo]])
		get_root().get_texture().get_image().save_png(destino)
		print("CAPTURA ", destino)
	quit()
