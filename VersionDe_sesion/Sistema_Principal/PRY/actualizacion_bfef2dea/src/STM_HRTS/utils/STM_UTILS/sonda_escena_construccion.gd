extends SceneTree
## Comprueba que ISLA3Dblock.tscn carga con el nodo Constructor y sus scripts
## sin errores de compilación (no entra al árbol: no abre red).

const RUTA := "res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"

func _initialize() -> void:
	var packed := load(RUTA) as PackedScene
	if packed == null:
		push_error("[sonda] no se pudo cargar %s" % RUTA)
		quit(1)
		return
	var raiz := packed.instantiate()
	var constructor := raiz.get_node_or_null("Constructor")
	var chunk := raiz.get_node_or_null("ISLA3DCHUNK")
	print("[sonda] raiz=", raiz.name, " chunk=", chunk != null)
	print("[sonda] Constructor=", constructor != null,
			" script=", constructor.get_script().resource_path if constructor != null else "—")
	var ok: bool = constructor != null and constructor.get_script() != null \
			and constructor.get_script().resource_path == "res://gdscrip/Construccion.gd"
	if ok and constructor.has_method("registrar_isla"):
		print("[sonda] registrar_isla disponible")
	ok = ok and constructor.has_method("registrar_isla")
	raiz.free()
	print("[sonda] resultado=", "OK" if ok else "FALLO")
	quit(0 if ok else 1)
