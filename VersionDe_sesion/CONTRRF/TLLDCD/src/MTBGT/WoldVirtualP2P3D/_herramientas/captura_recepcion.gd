extends SceneTree
## Captura la pantalla de recepción de LucIA para revisión visual.
## Uso: godot --path <proyecto> --script res://_herramientas/captura_recepcion.gd
##      --resolution 1280x720
## Guarda user://captura_migracion3.png y sale.

var _tiempo := 0.0
var _hecho := false


func _initialize() -> void:
	var escena := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	if escena == null:
		print("[captura] no se pudo cargar la escena principal")
		quit(1)
		return
	root.add_child(escena.instantiate())


func _process(delta: float) -> bool:
	if _hecho:
		return true
	_tiempo += delta
	if _tiempo < 9.0:
		return false
	_hecho = true
	var imagen := root.get_texture().get_image()
	# El nombre se puede cambiar sin tocar el script: CAPTURA=final_nuevo.png
	var nombre := OS.get_environment("CAPTURA")
	if nombre.is_empty():
		nombre = "captura_recepcion.png"
	var destino := "E:/WoldVirtualP2P3D/_tmp_tests/" + nombre
	var error := imagen.save_png(destino)
	print("[captura] %dx%d en %s (error=%d)" % [imagen.get_width(), imagen.get_height(), destino, error])
	return true
