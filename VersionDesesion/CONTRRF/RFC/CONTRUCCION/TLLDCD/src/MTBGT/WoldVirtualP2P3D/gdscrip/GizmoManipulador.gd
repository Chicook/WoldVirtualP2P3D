extends Node3D
## Manipulador de objetos estilo Second Life / OpenSim: tres ejes de color
## (X rojo, Y verde, Z azul) para mover, girar o escalar el objeto seleccionado.
##
## No usa física: el "picking" se resuelve por distancia entre el rayo del ratón
## y cada eje, y el arrastre se calcula proyectando el ratón sobre el eje (o
## sobre el plano de giro). Se dibuja sin profundidad para verse siempre.

enum Eje { NINGUNO = -1, X = 0, Y = 1, Z = 2 }
enum Modo { MOVER = 0, GIRAR = 1, ESCALAR = 2 }

const EJES := [Vector3.RIGHT, Vector3.UP, Vector3.BACK]
const COLORES := [Color(1.0, 0.28, 0.28), Color(0.36, 1.0, 0.4), Color(0.4, 0.6, 1.0)]
const LARGO := 1.1
const RADIO_MANGO := 0.035

var modo: int = Modo.MOVER
var _mangos: Array = []        # Node3D raíz por eje
var _materiales: Array = []    # StandardMaterial3D por eje
var _resaltado := -1


func _ready() -> void:
	_construir()


func set_modo(nuevo: int) -> void:
	modo = nuevo
	if is_inside_tree():
		_construir()


func _construir() -> void:
	for hijo in get_children():
		remove_child(hijo)
		hijo.queue_free()
	_mangos.clear()
	_materiales.clear()
	for i in 3:
		var raiz := Node3D.new()
		var mat := _material(COLORES[i], 1.0)
		_materiales.append(mat)
		match modo:
			Modo.GIRAR:
				_anillo(raiz, EJES[i], mat)
			Modo.ESCALAR:
				_eje_recto(raiz, EJES[i], mat)
				_caja_punta(raiz, EJES[i], mat)
			_:
				_eje_recto(raiz, EJES[i], mat)
				_cono_punta(raiz, EJES[i], mat)
		add_child(raiz)
		_mangos.append(raiz)
	resaltar(-1)


## Longitud del eje en unidades de mundo (según la escala del gizmo).
func largo_mundo() -> float:
	return LARGO * maxf(0.001, global_transform.basis.get_scale().x)


func resaltar(eje: int) -> void:
	_resaltado = eje
	for i in _materiales.size():
		var mat: StandardMaterial3D = _materiales[i]
		var brillo := 1.55 if i == eje else 1.0
		mat.albedo_color = Color(COLORES[i].r * brillo, COLORES[i].g * brillo, COLORES[i].b * brillo)


func resaltado() -> int:
	return _resaltado


## Eje más cercano al rayo (origen, dirección) dentro de `umbral`. Devuelve un
## entero de Eje. El rayo y los ejes están en coordenadas de mundo.
func eje_bajo_rayo(origen: Vector3, direccion: Vector3, umbral: float) -> int:
	var mejor := -1
	var mejor_d := umbral
	var largo := largo_mundo()
	for i in 3:
		var d1: Vector3 = (global_transform.basis * EJES[i]).normalized()
		var res := _linea_linea(global_position, d1, origen, direccion)
		var t: float = res[0]
		var dist: float = res[2]
		if t < -0.08 * largo or t > largo * 1.08:
			continue
		if dist < mejor_d:
			mejor_d = dist
			mejor = i
	return mejor


## Parámetro t sobre el eje cuya recta queda más cerca del rayo del ratón.
func parametro_en_eje(i: int, origen: Vector3, direccion: Vector3) -> float:
	var d1: Vector3 = (global_transform.basis * EJES[i]).normalized()
	return _linea_linea(global_position, d1, origen, direccion)[0]


func direccion_eje(i: int) -> Vector3:
	return (global_transform.basis * EJES[i]).normalized()


## Intersección del rayo con el plano (centro, normal=eje). null si es paralelo.
func punto_en_plano_giro(i: int, origen: Vector3, direccion: Vector3):
	var normal := direccion_eje(i)
	var denom := normal.dot(direccion)
	if absf(denom) < 1e-5:
		return null
	var t := normal.dot(global_position - origen) / denom
	if t < 0.0:
		return null
	return origen + direccion * t


## Ángulo (radianes) del punto respecto al centro, medido en el plano de giro.
func angulo_en_plano(i: int, punto: Vector3) -> float:
	var normal := direccion_eje(i)
	var u := Vector3.UP if absf(normal.dot(Vector3.UP)) < 0.9 else Vector3.RIGHT
	u = (u - normal * u.dot(normal)).normalized()
	var v := normal.cross(u)
	var r := punto - global_position
	return atan2(r.dot(v), r.dot(u))


# ------------------------------------------------------------------ geometría

func _eje_recto(padre: Node3D, dir: Vector3, mat: StandardMaterial3D) -> void:
	var cil := CylinderMesh.new()
	cil.top_radius = RADIO_MANGO
	cil.bottom_radius = RADIO_MANGO
	cil.height = LARGO * 0.82
	var mi := MeshInstance3D.new()
	mi.mesh = cil
	mi.material_override = mat
	_orientar(mi, dir)
	mi.position = dir * (LARGO * 0.41)
	padre.add_child(mi)


func _cono_punta(padre: Node3D, dir: Vector3, mat: StandardMaterial3D) -> void:
	var cono := CylinderMesh.new()
	cono.top_radius = 0.0
	cono.bottom_radius = 0.075
	cono.height = 0.22
	cono.radial_segments = 16
	var mi := MeshInstance3D.new()
	mi.mesh = cono
	mi.material_override = mat
	_orientar(mi, dir)
	mi.position = dir * (LARGO * 0.94)
	padre.add_child(mi)


func _caja_punta(padre: Node3D, dir: Vector3, mat: StandardMaterial3D) -> void:
	var caja := BoxMesh.new()
	caja.size = Vector3(0.12, 0.12, 0.12)
	var mi := MeshInstance3D.new()
	mi.mesh = caja
	mi.material_override = mat
	mi.position = dir * (LARGO * 0.94)
	padre.add_child(mi)


func _anillo(padre: Node3D, dir: Vector3, mat: StandardMaterial3D) -> void:
	var toro := TorusMesh.new()
	toro.inner_radius = LARGO * 0.86
	toro.outer_radius = LARGO * 0.95
	toro.rings = 48
	toro.ring_segments = 8
	var mi := MeshInstance3D.new()
	mi.mesh = toro
	mi.material_override = mat
	# El toro vive en el plano XZ (eje Y): se gira para envolver su eje.
	_orientar(mi, dir)
	padre.add_child(mi)


func _orientar(nodo: Node3D, dir: Vector3) -> void:
	if dir.is_equal_approx(Vector3.RIGHT):
		nodo.rotation_degrees = Vector3(0.0, 0.0, -90.0)
	elif dir.is_equal_approx(Vector3.BACK):
		nodo.rotation_degrees = Vector3(90.0, 0.0, 0.0)


func _material(color: Color, brillo: float) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(color.r * brillo, color.g * brillo, color.b * brillo)
	mat.no_depth_test = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color.a = 0.95
	return mat


# -------------------------------------------------------------------- matemática

## Distancia mínima entre dos rectas. Devuelve [t, s, distancia] donde t es el
## parámetro sobre la primera recta (p1 + t*d1) y s sobre la segunda.
func _linea_linea(p1: Vector3, d1: Vector3, p2: Vector3, d2: Vector3) -> Array:
	var w0 := p1 - p2
	var a := d1.dot(d1)
	var b := d1.dot(d2)
	var c := d2.dot(d2)
	var d := d1.dot(w0)
	var e := d2.dot(w0)
	var denom := a * c - b * b
	var t := 0.0
	var s := 0.0
	if absf(denom) < 1e-8:
		# Rectas casi paralelas: fija t y proyecta.
		t = 0.0
		s = (e / c) if b > 0.0001 else 0.0
	else:
		t = (b * e - c * d) / denom
		s = (a * e - b * d) / denom
	var c1 := p1 + d1 * t
	var c2 := p2 + d2 * s
	return [t, s, c1.distance_to(c2)]