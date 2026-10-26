extends RefCounted
## Catálogo y serialización de prims (objetos construibles).
## Inspirado en el rezado de Second Life/OpenSim, sin copiar su implementación:
## primitivas procedurales, color plano y edición por transformación.

const TIPOS := ["cubo", "esfera", "cilindro", "cono", "toro"]
const NOMBRES := {
	"cubo": "Cubo",
	"esfera": "Esfera",
	"cilindro": "Cilindro",
	"cono": "Cono",
	"toro": "Toro",
}
const COLORES := [
	Color(0.85, 0.85, 0.88),
	Color(0.93, 0.32, 0.31),
	Color(0.95, 0.66, 0.22),
	Color(0.36, 0.82, 0.45),
	Color(0.28, 0.68, 0.95),
	Color(0.66, 0.42, 0.94),
	Color(0.95, 0.55, 0.78),
	Color(0.15, 0.17, 0.22),
]


static func tamano_por_defecto(tipo: String) -> Vector3:
	match tipo:
		"cubo":
			return Vector3(1.6, 1.6, 1.6)
		"esfera":
			return Vector3(1.8, 1.8, 1.8)
		"cilindro":
			return Vector3(1.4, 2.2, 1.4)
		"cono":
			return Vector3(1.6, 2.4, 1.6)
		"toro":
			return Vector3(2.0, 2.0, 2.0)
	return Vector3.ONE


static func crear_malla(tipo: String) -> Mesh:
	match tipo:
		"esfera":
			var esfera := SphereMesh.new()
			esfera.radius = 0.5
			esfera.height = 1.0
			esfera.radial_segments = 32
			esfera.rings = 16
			return esfera
		"cilindro":
			var cilindro := CylinderMesh.new()
			cilindro.top_radius = 0.5
			cilindro.bottom_radius = 0.5
			cilindro.height = 1.0
			cilindro.radial_segments = 32
			return cilindro
		"cono":
			var cono := CylinderMesh.new()
			cono.top_radius = 0.02
			cono.bottom_radius = 0.5
			cono.height = 1.0
			cono.radial_segments = 32
			return cono
		"toro":
			var toro := TorusMesh.new()
			toro.inner_radius = 0.32
			toro.outer_radius = 0.5
			toro.rings = 32
			toro.ring_segments = 16
			return toro
	var caja := BoxMesh.new()
	caja.size = Vector3.ONE
	return caja


static func crear_material(color: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.62
	mat.metallic = 0.0
	return mat


static func crear_forma(tipo: String) -> Shape3D:
	match tipo:
		"esfera":
			var esfera := SphereShape3D.new()
			esfera.radius = 0.5
			return esfera
		"cilindro", "cono":
			var cilindro := CylinderShape3D.new()
			cilindro.radius = 0.5
			cilindro.height = 1.0
			return cilindro
		"toro":
			var malla := crear_malla("toro")
			return malla.create_trimesh_shape()
	var caja := BoxShape3D.new()
	caja.size = Vector3.ONE
	return caja


## Diccionario interno -> diccionario JSON seguro (sin Vector3/Color).
static func a_dict(datos: Dictionary) -> Dictionary:
	var pos: Vector3 = datos.get("pos", Vector3.ZERO)
	var rot: Vector3 = datos.get("rot", Vector3.ZERO)
	var esc: Vector3 = datos.get("escala", Vector3.ONE)
	var color: Color = datos.get("color", COLORES[0])
	return {
		"id": int(datos.get("id", 0)),
		"tipo": str(datos.get("tipo", "cubo")),
		"pos": [pos.x, pos.y, pos.z],
		"rot": [rot.x, rot.y, rot.z],
		"escala": [esc.x, esc.y, esc.z],
		"color": color.to_html(true),
	}


## Diccionario JSON -> diccionario interno, con saneado de valores.
static func desde_dict(d: Dictionary) -> Dictionary:
	var tipo := str(d.get("tipo", "cubo"))
	if not TIPOS.has(tipo):
		tipo = "cubo"
	return {
		"id": int(d.get("id", 0)),
		"tipo": tipo,
		"pos": _leer_vec3(d.get("pos", []), Vector3.ZERO),
		"rot": _leer_vec3(d.get("rot", []), Vector3.ZERO),
		"escala": _leer_vec3(d.get("escala", []), tamano_por_defecto(tipo)).clamp(
				Vector3(0.15, 0.15, 0.15), Vector3(40.0, 40.0, 40.0)),
		"color": Color.html(str(d.get("color", "#d9d9e0"))),
	}


static func serializar_isla(prims: Dictionary, siguiente: int, uuid: String) -> String:
	var lista: Array = []
	for id in prims.keys():
		lista.append(a_dict(prims[id]))
	lista.sort_custom(func(a, b): return int(a["id"]) < int(b["id"]))
	return JSON.stringify({
		"version": 1,
		"siguiente": maxi(1, siguiente),
		"uuid": uuid,
		"prims": lista,
	})


## Devuelve {siguiente, prims}; vacío si el texto no es válido.
static func deserializar_isla(texto: String) -> Dictionary:
	var parsed = JSON.parse_string(texto)
	if not (parsed is Dictionary):
		return {}
	if int(parsed.get("version", 0)) != 1:
		return {}
	var prims := {}
	var mayor := 0
	for item in parsed.get("prims", []):
		if not (item is Dictionary):
			continue
		var datos := desde_dict(item)
		var id := int(datos["id"])
		if id <= 0:
			continue
		prims[id] = datos
		mayor = maxi(mayor, id)
	return {
		"siguiente": maxi(int(parsed.get("siguiente", 1)), mayor + 1),
		"prims": prims,
	}


static func _leer_vec3(valor, por_defecto: Vector3) -> Vector3:
	if valor is Array and valor.size() >= 3:
		return Vector3(float(valor[0]), float(valor[1]), float(valor[2]))
	return por_defecto
