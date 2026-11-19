extends SceneTree
## Captura visual de la recepción de LucIA (F9). Windowed (sin --headless) para
## que save_png tenga texturas reales. No toca los datos reales de user://: el
## modo "nuevo" se fuerza con una subclase; el "existente" usa el estado real.
## Uso: Godot_console.exe --path . --script res://tools/capturar_recepcion.gd --audio-driver Dummy
## PNG en user://capturas_recepcion/ (regenerables, no son assets del visor).

const Forzada = preload("res://tools/recepcion_forzada.gd")
const Recepcion = preload("res://gdscrip/LuciaRecepcion.gd")
const DIR := "user://capturas_recepcion"

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(DIR)
	root.size = Vector2i(1280, 720)
	await process_frame
	await _capturar("recepcion_nuevo", Forzada.new(), "nuevo", {})
	await _capturar("recepcion_existente", Recepcion.new(), "", {})
	print("CAPTURAS_RECEPCION: hechas en ", ProjectSettings.globalize_path(DIR))
	quit(0)

func _capturar(nombre: String, nodo: Node3D, modo: String, cuenta: Dictionary) -> void:
	if modo != "":
		nodo.modo_forzado = modo
		nodo.cuenta_forzada = cuenta
	nodo.name = "Recepcion"
	root.add_child(nodo)
	for i in range(40):
		await process_frame
	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	var ruta := DIR.path_join(nombre + ".png")
	var err := img.save_png(ruta)
	print("captura ", nombre, " err=", err, " size=", img.get_size(), " -> ", ProjectSettings.globalize_path(ruta))
	nodo.queue_free()
	for i in range(5):
		await process_frame