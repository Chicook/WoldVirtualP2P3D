extends RefCounted
## Copias del progreso de una isla: `user://inventario/`.
##
## Cada copia guarda el blob del terreno (base64) y la lista de objetos en su
## propio JSON; el índice (`inventario.json`) solo lista metadatos para pintar
## la pestaña sin abrir todas las copias. La carpeta se pasa en cada llamada
## para que las pruebas puedan redirigirla sin tocar datos reales.

const CARPETA := "user://inventario"
const VERSION := 1


func ruta_indice(carpeta: String) -> String:
	return carpeta.path_join("inventario.json")


func leer_entradas(carpeta: String) -> Array:
	var ruta := ruta_indice(carpeta)
	if not FileAccess.file_exists(ruta):
		return []
	var f := FileAccess.open(ruta, FileAccess.READ)
	if f == null:
		return []
	var texto := f.get_as_text()
	f.close()
	var leido = JSON.parse_string(texto)
	if leido is Dictionary and leido.get("entradas") is Array:
		return leido["entradas"]
	return []


## Guarda una copia del terreno y de los objetos de la isla. Devuelve
## {"ok": true, "entrada": {...}} o {"ok": false, "mensaje": "..."}.
func guardar(carpeta: String, idx: int, blob: PackedByteArray, texto_prims: String,
		uuid: String) -> Dictionary:
	var leido = JSON.parse_string(texto_prims)
	var assets: Array = leido.get("prims", []) if leido is Dictionary else []
	if blob.is_empty() and assets.is_empty():
		return {"ok": false, "mensaje": "No hay nada construido que guardar en el inventario."}

	var sello := Time.get_datetime_string_from_system()
	var id := "%s-%d" % [sello.replace("-", "").replace(":", "").replace("T", "-"),
			Time.get_ticks_msec()]
	var archivo := "inv_%s_isla%d.json" % [id, idx]

	var dir := DirAccess.open("user://")
	if dir != null:
		dir.make_dir_recursive(carpeta.trim_prefix("user://"))

	var contenido := {
		"version": VERSION,
		"id": id,
		"fecha": sello,
		"isla": idx,
		"uuid": uuid,
		"terreno": not blob.is_empty(),
		"terreno_b64": Marshalls.raw_to_base64(blob) if not blob.is_empty() else "",
		"prims": assets,
	}
	var f := FileAccess.open(carpeta.path_join(archivo), FileAccess.WRITE)
	if f == null:
		return {"ok": false, "mensaje": "No se pudo escribir la copia del inventario."}
	f.store_string(JSON.stringify(contenido, "\t"))
	f.close()

	var entrada := {
		"id": id,
		"fecha": sello,
		"isla": idx,
		"terreno": not blob.is_empty(),
		"assets": assets.size(),
		"archivo": archivo,
	}
	var entradas := leer_entradas(carpeta)
	entradas.append(entrada)
	var fi := FileAccess.open(ruta_indice(carpeta), FileAccess.WRITE)
	if fi == null:
		return {"ok": false, "mensaje": "No se pudo actualizar el índice del inventario."}
	fi.store_string(JSON.stringify({"version": VERSION, "entradas": entradas}, "\t"))
	fi.close()
	return {"ok": true, "entrada": entrada}
