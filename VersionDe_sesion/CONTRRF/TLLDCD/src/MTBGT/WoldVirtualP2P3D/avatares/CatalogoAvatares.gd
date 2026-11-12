extends RefCounted
## Catálogo único de avatares del metaverso.
##
## Los ocho modelos viven en `res://gltfimport/avatares` y comparten el mismo
## esqueleto y las mismas cinco animaciones. Cada entrada apunta a una escena
## jugable propia (`res://avatares/<ID>.tscn`) para que el carrusel, el mundo y
## la red P2P hablen siempre del mismo recurso.

const ANIM_IDLE := "paradoMJ1_1"
const ANIM_WALK := "caminarMJ1_2"
const ANIM_RUN := "correrMJ1_3"
const ANIM_LEFT := "left_StrafeMJ1_4"
const ANIM_RIGHT := "rightstrafeMJ1_5"

const MODELOS: Array[Dictionary] = [
	{
		"id": "AVH1", "nombre": "Bruno", "genero": "hombre", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVH1.gltf",
		"escena": "res://avatares/AVH1.tscn",
		"color": Color(0.36, 0.72, 1.0, 1.0),
	},
	{
		"id": "AVMJ1", "nombre": "Alba", "genero": "mujer", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVMJ1.gltf",
		"escena": "res://avatares/AVMJ1.tscn",
		"color": Color(1.0, 0.56, 0.78, 1.0),
	},
	{
		"id": "AVH2", "nombre": "Darío", "genero": "hombre", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVH2.gltf",
		"escena": "res://avatares/AVH2.tscn",
		"color": Color(0.42, 0.9, 0.72, 1.0),
	},
	{
		"id": "AVMJ2", "nombre": "Clara", "genero": "mujer", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVMJ2.gltf",
		"escena": "res://avatares/AVMJ2.tscn",
		"color": Color(1.0, 0.76, 0.42, 1.0),
	},
	{
		"id": "AVH3", "nombre": "Elián", "genero": "hombre", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVH3.gltf",
		"escena": "res://avatares/AVH3.tscn",
		"color": Color(0.66, 0.6, 1.0, 1.0),
	},
	{
		"id": "AVMJ3", "nombre": "Elena", "genero": "mujer", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVMJ3.gltf",
		"escena": "res://avatares/AVMJ3.tscn",
		"color": Color(0.52, 0.94, 0.94, 1.0),
	},
	{
		"id": "AVH4", "nombre": "Hugo", "genero": "hombre", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVH4.gltf",
		"escena": "res://avatares/AVH4.tscn",
		"color": Color(1.0, 0.56, 0.46, 1.0),
	},
	{
		"id": "AVMJ4", "nombre": "Irene", "genero": "mujer", "turno": 1,
		"ruta": "res://gltfimport/avatares/AVMJ4.gltf",
		"escena": "res://avatares/AVMJ4.tscn",
		"color": Color(0.78, 1.0, 0.5, 1.0),
	},
]

const ALTURA_OBJETIVO := 1.8


static func total() -> int:
	return MODELOS.size()


static func ids() -> Array[String]:
	var salida: Array[String] = []
	for m in MODELOS:
		salida.append(str(m["id"]))
	return salida


static func rutas() -> Array[String]:
	var salida: Array[String] = []
	for m in MODELOS:
		salida.append(str(m["escena"]))
	return salida


static func modelo(id: String) -> Dictionary:
	var limpio := id.strip_edges().to_upper()
	for m in MODELOS:
		if str(m["id"]) == limpio:
			return m
	return {}


static func por_indice(indice: int) -> Dictionary:
	if indice < 0 or indice >= MODELOS.size():
		return {}
	return MODELOS[indice]


static func indice_de(id: String) -> int:
	var limpio := id.strip_edges().to_upper()
	for i in MODELOS.size():
		if str(MODELOS[i]["id"]) == limpio:
			return i
	return -1


static func id_de_ruta(ruta: String) -> String:
	var normal := ruta.strip_edges()
	if normal.is_empty():
		return ""
	for m in MODELOS:
		if str(m["escena"]) == normal or str(m["ruta"]) == normal:
			return str(m["id"])
	# Acepta también un id suelto ("AVH1").
	var directo := str(modelo(normal).get("id", ""))
	if not directo.is_empty():
		return directo
	# Migración: perfiles antiguos guardaban rutas como
	# ".../AVHMBSC/AVH1Ch3D.tscn". Se reconoce el id por el nombre del archivo.
	var archivo := normal.get_file().to_upper()
	for m in MODELOS:
		var id := str(m["id"])
		if archivo.begins_with(id):
			return id
	return ""


static func ruta_de(id: String) -> String:
	var m := modelo(id)
	return str(m.get("escena", ""))


static func escena_de(id: String) -> String:
	return ruta_de(id)


static func nombre_de(id: String) -> String:
	return str(modelo(id).get("nombre", ""))


static func genero_de(id: String) -> String:
	return str(modelo(id).get("genero", ""))


static func color_de(id: String) -> Color:
	var m := modelo(id)
	return m.get("color", Color.WHITE)


static func id_valido(id: String) -> bool:
	return indice_de(id) >= 0


## Instancia la escena jugable del avatar. Devuelve null si el id no existe o
## el recurso no está importado.
static func crear(id: String) -> Node3D:
	var m := modelo(id)
	if m.is_empty():
		return null
	var ruta := str(m["escena"])
	if not ResourceLoader.exists(ruta):
		push_error("[CatalogoAvatares] falta la escena %s (avatar %s)" % [ruta, id])
		return null
	var packed := load(ruta) as PackedScene
	if packed == null:
		push_error("[CatalogoAvatares] no se pudo cargar %s" % ruta)
		return null
	var nodo := packed.instantiate() as Node3D
	if nodo != null:
		nodo.set_meta("avatar_id", str(m["id"]))
	return nodo
