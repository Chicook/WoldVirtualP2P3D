extends Node
## Arranca primero para montar la base 2.8.6 cuando el PCK principal es un delta.
## La build 2.8.7 lleva el mundo completo y no define WOLD_BASE_PCK: el arranque sigue igual.

func _init() -> void:
	var ruta_base := OS.get_environment("WOLD_BASE_PCK").strip_edges()
	# La 2.8.7 lleva el mundo completo: sin base es un arranque normal, no un error.
	if ruta_base.is_empty():
		return
	if not FileAccess.file_exists(ruta_base):
		push_error("[DAOBasePackLoader] No se encontró el PCK base: " + ruta_base)
		return

	if not ProjectSettings.load_resource_pack(ruta_base, false):
		push_error("[DAOBasePackLoader] No se pudo montar el PCK base 2.8.6")
		return

	print("[DAOBasePackLoader] Base 2.8.6 montada; el PCK delta DAO 2.8.7 mantiene prioridad")
