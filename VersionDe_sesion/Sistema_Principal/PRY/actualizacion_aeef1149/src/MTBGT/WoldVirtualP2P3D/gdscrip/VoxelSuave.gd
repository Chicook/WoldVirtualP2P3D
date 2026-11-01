extends RefCounted
## Terreno voxel suave para el modo construcción.
##
## Adapta la idea de Voxel Tools (Zylann): un campo de distancias (SDF) se
## convierte en malla con surface nets, de modo que la superficie es orgánica y
## continua en vez de una pila de cubos. No se usa el addon nativo: su
## GDExtension pesa ~54 MB y el visor standalone empaqueta el motor oficial, así
## que la extracción se hace aquí en GDScript y el estado viaja como parámetros
## pequeños (forma, semilla, radio, altura) que cada peer regenera igual.
##
## Convención: distancia negativa dentro del sólido, positiva fuera.

const FORMAS := ["isla", "meseta", "arco", "cordillera"]
const NOMBRES := {
	"isla": "Isla",
	"meseta": "Meseta",
	"arco": "Arco",
	"cordillera": "Cordillera",
}

const DETALLE_MIN := 16
const DETALLE_MAX := 44
const DETALLE_DEFECTO := 30
const RADIO_MIN := 2.2
const RADIO_MAX := 30.0
const ALTURA_MAX := 30.0
const BORDE_MIN := 3.6
const FONDO_DEFECTO := 0.8
## Hueco entre el borde natural de la forma y el recorte duro lateral: así el
## ruido nunca llega a la pared del recorte y el contorno queda limpio.
const MARGEN_BORDE := 1.2
## Cuánto puede avanzar el terreno sobre el agua. Solo se usa al crear una
## playa: lo justo para que la arena toque la orilla, nunca para invadir el mar.
const MARGEN_MAR := 0.8

var _prm := {}
var _forma := "isla"
var _radio := 8.0
var _alto := 6.0
var _fondo := FONDO_DEFECTO
var _borde := 10.0
var _playa := 0.0
var _semilla := 0
var _amp := 0.4

var _nx := 0
var _ny := 0
var _nz := 0
var _celda := 0.5
var _cx := 0.0
var _cy := 0.0
var _cz := 0.0
var _dens := PackedFloat32Array()

const _ESQUINAS := [
	Vector3i(0, 0, 0), Vector3i(1, 0, 0), Vector3i(0, 1, 0), Vector3i(1, 1, 0),
	Vector3i(0, 0, 1), Vector3i(1, 0, 1), Vector3i(0, 1, 1), Vector3i(1, 1, 1),
]
const _ARISTAS := [
	[0, 1], [2, 3], [4, 5], [6, 7],
	[0, 2], [1, 3], [4, 6], [5, 7],
	[0, 4], [1, 5], [2, 6], [3, 7],
]


static func params_por_defecto(forma: String) -> Dictionary:
	var f := forma if FORMAS.has(forma) else "isla"
	var radio := 8.0
	var altura := 6.0
	var detalle := DETALLE_DEFECTO
	match f:
		"meseta":
			radio = 7.0
			altura = 5.0
		"arco":
			radio = 7.5
			altura = 9.0
			detalle = 32
		"cordillera":
			radio = 10.0
			altura = 7.0
			detalle = 34
	return {
		"forma": f,
		"semilla": randi(),
		"radio": radio,
		"altura": altura,
		"fondo": FONDO_DEFECTO,
		"detalle": detalle,
		"borde": radio + MARGEN_BORDE + 0.4,
		"playa": 0.0,
	}


static func normalizar_params(d: Dictionary) -> Dictionary:
	var forma := str(d.get("forma", "isla"))
	if not FORMAS.has(forma):
		forma = "isla"
	var radio := clampf(float(d.get("radio", 8.0)), RADIO_MIN, RADIO_MAX)
	var altura := clampf(float(d.get("altura", 6.0)), 1.0, ALTURA_MAX)
	var fondo := clampf(float(d.get("fondo", FONDO_DEFECTO)), 0.2, 4.0)
	var detalle := clampi(int(d.get("detalle", DETALLE_DEFECTO)), DETALLE_MIN, DETALLE_MAX)
	# El borde duro siempre deja sitio al ruido; si el llamante manda menos, se
	# sube en vez de recortar la forma.
	var borde := clampf(float(d.get("borde", radio + MARGEN_BORDE)), radio + 0.9, radio + 14.0)
	var playa := clampf(float(d.get("playa", 0.0)), 0.0, 1.2)
	return {
		"forma": forma,
		"semilla": int(d.get("semilla", 0)),
		"radio": radio,
		"altura": altura,
		"fondo": fondo,
		"detalle": detalle,
		"borde": borde,
		"playa": playa,
	}


## Encaja la forma en el terreno disponible. `disponible` ya incluye, si
## procede, el margen de mar acotado por el contorno real de la isla. Sin
## `tocar_mar` la forma se queda medio metro dentro de la tierra.
static func ajustar_a_borde(d: Dictionary, disponible: float, tocar_mar := false) -> Dictionary:
	var prm := normalizar_params(d)
	var margen := 0.0 if tocar_mar else -0.5
	var borde := minf(float(prm["borde"]), disponible + margen)
	if borde < BORDE_MIN:
		return {}
	var radio := minf(float(prm["radio"]), borde - MARGEN_BORDE)
	if radio < RADIO_MIN:
		return {}
	prm["borde"] = borde
	prm["radio"] = radio
	if not tocar_mar:
		prm["playa"] = 0.0
	elif float(prm["playa"]) <= 0.02:
		prm["playa"] = 0.6
	return prm


func generar(params: Dictionary) -> ArrayMesh:
	_prm = normalizar_params(params)
	_forma = str(_prm["forma"])
	_radio = float(_prm["radio"])
	_alto = float(_prm["altura"])
	_fondo = float(_prm["fondo"])
	_borde = float(_prm["borde"])
	_playa = float(_prm["playa"])
	_semilla = int(_prm["semilla"])
	_amp = minf(0.42, 0.05 * _radio)
	_preparar_rejilla()
	_muestrear()
	return _extraer()


func _preparar_rejilla() -> void:
	var detalle := int(_prm["detalle"])
	var lado := maxf(2.0 * _borde, _alto * 1.15 + _fondo)
	_celda = lado / float(detalle)
	_nx = int(ceil((2.0 * _borde + 2.0 * _celda) / _celda)) + 1
	_ny = int(ceil((_alto * 1.15 + _fondo + 2.0 * _celda) / _celda)) + 1
	_nz = _nx
	_cx = -_borde - _celda
	_cy = -_fondo - _celda
	_cz = _cx


func _muestrear() -> void:
	_dens.resize(_nx * _ny * _nz)
	for k in _nz:
		var z := _cz + float(k) * _celda
		for j in _ny:
			var y := _cy + float(j) * _celda
			var base := (k * _ny + j) * _nx
			for i in _nx:
				_dens[base + i] = _dist(Vector3(_cx + float(i) * _celda, y, z))


func _indice(i: int, j: int, k: int) -> int:
	return (k * _ny + j) * _nx + i


func _indice_celda(i: int, j: int, k: int) -> int:
	return (k * (_ny - 1) + j) * (_nx - 1) + i


func _dist(p: Vector3) -> float:
	var d := 0.0
	match _forma:
		"meseta":
			d = _sd_meseta(p)
		"arco":
			d = _sd_arco(p)
		"cordillera":
			d = _sd_cordillera(p)
		_:
			d = _sd_isla(p)
	if _playa > 0.02:
		d = minf(d, _sd_playa(p))
	d -= _amp * _ruido(p)
	# Recortes duros: fondo plano (para enterrarlo en la isla) y contorno
	# circular. El segundo es la garantía de que la malla no sale del terreno.
	d = maxf(d, -_fondo - p.y)
	d = maxf(d, Vector2(p.x, p.z).length() - _borde)
	return d


func _sd_isla(p: Vector3) -> float:
	var centro := Vector3(0.0, _alto * 0.34, 0.0)
	var r := Vector3(_radio, _alto * 0.66, _radio)
	return _sd_elipsoide(p - centro, r)


## Faldón de arena: sube `_playa` metros hacia dentro y muere en el borde, justo
## en el nivel del mar. Solo se genera si la pieza se creó junto a la costa.
func _sd_playa(p: Vector3) -> float:
	var r := Vector2(p.x, p.z).length()
	var interior := _radio * 0.78
	var t := clampf((r - interior) / maxf(_borde - interior, 0.05), 0.0, 1.0)
	var altura := _playa * (1.0 - t * t)
	return maxf(p.y - altura, r - _borde)


func _sd_meseta(p: Vector3) -> float:
	var cy := _alto * 0.48
	var hh := _alto * 0.42
	var rr := minf(1.1, _radio * 0.16)
	var q := Vector2(Vector2(p.x, p.z).length() - _radio + rr, absf(p.y - cy) - hh + rr)
	return q.length() - rr


func _sd_arco(p: Vector3) -> float:
	var r := _radio
	var a := _alto
	var br := maxf(0.7, r * 0.16)
	var d := 1e9
	for sx in [-1.0, 1.0]:
		d = _smin(d, _sd_capsula(p,
				Vector3(sx * r * 0.58, -_fondo, 0.0),
				Vector3(sx * r * 0.58, a * 0.30, 0.0), br * 1.25), br * 1.2)
	var previo := Vector3(-r * 0.58, a * 0.28, 0.0)
	for i in range(1, 7):
		var angulo := PI * (1.0 - float(i) / 6.0)
		var punto := Vector3(cos(angulo) * r * 0.58, a * 0.28 + sin(angulo) * a * 0.62, 0.0)
		d = _smin(d, _sd_capsula(p, previo, punto, br), br * 0.9)
		previo = punto
	for sx in [-1.0, 1.0]:
		var pie := Vector3(sx * r * 0.58, a * 0.02, 0.0)
		d = _smin(d, _sd_elipsoide(p - pie, Vector3(r * 0.24, a * 0.2, r * 0.24)),
				br * 1.4)
	return d


func _sd_cordillera(p: Vector3) -> float:
	var r := _radio
	var a := _alto
	var d := _sd_elipsoide(p - Vector3(0.0, a * 0.08, 0.0),
			Vector3(r * 0.86, a * 0.24, r * 0.5))
	var picos := [
		[Vector2(-0.44, 0.08), 0.92, 0.34],
		[Vector2(-0.10, -0.12), 1.0, 0.4],
		[Vector2(0.24, 0.10), 0.82, 0.32],
		[Vector2(0.50, -0.05), 0.6, 0.26],
	]
	for pico in picos:
		var base: Vector2 = pico[0]
		var h: float = float(pico[1])
		var rr: float = float(pico[2])
		var centro := Vector3(base.x * r, a * 0.30 * h, base.y * r)
		var radios := Vector3(r * rr, a * 0.62 * h, r * rr)
		d = _smin(d, _sd_elipsoide(p - centro, radios), r * 0.18)
	return d


func _sd_elipsoide(p: Vector3, r: Vector3) -> float:
	var q := Vector3(p.x / r.x, p.y / r.y, p.z / r.z)
	var k0 := q.length()
	var k1 := Vector3(p.x / (r.x * r.x), p.y / (r.y * r.y), p.z / (r.z * r.z)).length()
	return k0 * (k0 - 1.0) / maxf(k1, 1e-6)


func _sd_capsula(p: Vector3, a: Vector3, b: Vector3, r: float) -> float:
	var pa := p - a
	var ba := b - a
	var h := clampf(pa.dot(ba) / maxf(ba.length_squared(), 1e-6), 0.0, 1.0)
	return (pa - ba * h).length() - r


func _smin(a: float, b: float, k: float) -> float:
	var h := clampf(0.5 + 0.5 * (b - a) / maxf(k, 1e-6), 0.0, 1.0)
	return lerpf(b, a, h) - k * h * (1.0 - h)


## Ruido de valor determinista: la misma semilla y posición dan el mismo
## resultado en todos los peers, sin depender de FastNoiseLite ni del motor.
func _ruido(p: Vector3) -> float:
	var n1 := _vn(p * 0.33 + Vector3(11.7, 5.3, 7.9), _semilla)
	var n2 := _vn(p * 0.78 + Vector3(2.1, 9.4, 3.6), _semilla + 101)
	return 0.68 * n1 + 0.32 * n2


func _vn(p: Vector3, semilla: int) -> float:
	var xi := floori(p.x)
	var yi := floori(p.y)
	var zi := floori(p.z)
	var fx := p.x - float(xi)
	var fy := p.y - float(yi)
	var fz := p.z - float(zi)
	var u := fx * fx * (3.0 - 2.0 * fx)
	var v := fy * fy * (3.0 - 2.0 * fy)
	var w := fz * fz * (3.0 - 2.0 * fz)
	var c000 := _hash(xi, yi, zi, semilla)
	var c100 := _hash(xi + 1, yi, zi, semilla)
	var c010 := _hash(xi, yi + 1, zi, semilla)
	var c110 := _hash(xi + 1, yi + 1, zi, semilla)
	var c001 := _hash(xi, yi, zi + 1, semilla)
	var c101 := _hash(xi + 1, yi, zi + 1, semilla)
	var c011 := _hash(xi, yi + 1, zi + 1, semilla)
	var c111 := _hash(xi + 1, yi + 1, zi + 1, semilla)
	var abajo := lerpf(lerpf(c000, c100, u), lerpf(c010, c110, u), v)
	var arriba := lerpf(lerpf(c001, c101, u), lerpf(c011, c111, u), v)
	return lerpf(abajo, arriba, w)


static func _hash(x: int, y: int, z: int, semilla: int) -> float:
	var n := x * 374761393 + y * 668265263 + z * 1442695041 + semilla * 2654435761
	n = (n ^ (n >> 13)) * 1274126177
	n = n ^ (n >> 16)
	return float(n & 0xffff) / 32767.5 - 1.0


func _gradiente(p: Vector3) -> Vector3:
	var e := _celda * 0.35
	var g := Vector3(
			_dist(p + Vector3(e, 0.0, 0.0)) - _dist(p - Vector3(e, 0.0, 0.0)),
			_dist(p + Vector3(0.0, e, 0.0)) - _dist(p - Vector3(0.0, e, 0.0)),
			_dist(p + Vector3(0.0, 0.0, e)) - _dist(p - Vector3(0.0, 0.0, e)))
	return g.normalized() if g.length_squared() > 1e-12 else Vector3.UP


func _extraer() -> ArrayMesh:
	var total := (_nx - 1) * (_ny - 1) * (_nz - 1)
	if total <= 0:
		return ArrayMesh.new()
	var vertice_celda := PackedInt32Array()
	vertice_celda.resize(total)
	vertice_celda.fill(-1)
	var verts := PackedVector3Array()
	for k in _nz - 1:
		for j in _ny - 1:
			for i in _nx - 1:
				var d := PackedFloat32Array()
				d.resize(8)
				var mascara := 0
				for c in 8:
					var esq: Vector3i = _ESQUINAS[c]
					var valor := _dens[_indice(i + esq.x, j + esq.y, k + esq.z)]
					d[c] = valor
					if valor < 0.0:
						mascara |= 1 << c
				if mascara == 0 or mascara == 255:
					continue
				var suma := Vector3.ZERO
				var cruces := 0
				for a in 12:
					var arista: Array = _ARISTAS[a]
					var da := d[arista[0]]
					var db := d[arista[1]]
					if (da < 0.0) == (db < 0.0):
						continue
					var t := da / (da - db)
					var ea: Vector3i = _ESQUINAS[arista[0]]
					var eb: Vector3i = _ESQUINAS[arista[1]]
					suma += Vector3(ea).lerp(Vector3(eb), t)
					cruces += 1
				if cruces == 0:
					continue
				var local := suma / float(cruces)
				verts.append(Vector3(
						_cx + (float(i) + local.x) * _celda,
						_cy + (float(j) + local.y) * _celda,
						_cz + (float(k) + local.z) * _celda))
				vertice_celda[_indice_celda(i, j, k)] = verts.size() - 1
	if verts.is_empty():
		return ArrayMesh.new()

	var indices := PackedInt32Array()
	for k in _nz:
		for j in _ny:
			for i in _nx:
				var dentro := _dens[_indice(i, j, k)] < 0.0
				if i + 1 < _nx and j > 0 and k > 0:
					if (_dens[_indice(i + 1, j, k)] < 0.0) != dentro:
						_quad(vertice_celda, indices, [
							Vector3i(i, j - 1, k - 1), Vector3i(i, j, k - 1),
							Vector3i(i, j, k), Vector3i(i, j - 1, k)])
				if j + 1 < _ny and i > 0 and k > 0:
					if (_dens[_indice(i, j + 1, k)] < 0.0) != dentro:
						_quad(vertice_celda, indices, [
							Vector3i(i - 1, j, k - 1), Vector3i(i, j, k - 1),
							Vector3i(i, j, k), Vector3i(i - 1, j, k)])
				if k + 1 < _nz and i > 0 and j > 0:
					if (_dens[_indice(i, j, k + 1)] < 0.0) != dentro:
						_quad(vertice_celda, indices, [
							Vector3i(i - 1, j - 1, k), Vector3i(i, j - 1, k),
							Vector3i(i, j, k), Vector3i(i - 1, j, k)])
	if indices.is_empty():
		return ArrayMesh.new()

	var normales := PackedVector3Array()
	normales.resize(verts.size())
	var colores := PackedColorArray()
	colores.resize(verts.size())
	for i in verts.size():
		var p := verts[i]
		normales[i] = _gradiente(p)
		# Variación sutil de albedo para que la roca no sea una superficie
		# plana; el color elegido sigue mandando desde el material.
		var g := 0.86 + 0.14 * (0.5 + 0.5 * _vn(p * 1.7, _semilla + 37))
		colores[i] = Color(g, g * 0.985, g * 0.955, 1.0)

	# El orden de los quads no depende del signo; se corrige contra el gradiente
	# para que todas las caras miren hacia fuera y la luz no las apague.
	for t in range(0, indices.size(), 3):
		var ia := indices[t]
		var ib := indices[t + 1]
		var ic := indices[t + 2]
		var a := verts[ia]
		var b := verts[ib]
		var c := verts[ic]
		var cara := (b - a).cross(c - a)
		if cara.dot(_gradiente((a + b + c) / 3.0)) < 0.0:
			indices[t + 1] = ic
			indices[t + 2] = ib

	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normales
	arrays[Mesh.ARRAY_COLOR] = colores
	arrays[Mesh.ARRAY_INDEX] = indices
	var malla := ArrayMesh.new()
	malla.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return malla


func _quad(vertice_celda: PackedInt32Array, indices: PackedInt32Array,
		celdas: Array) -> void:
	var ids := PackedInt32Array()
	for c in celdas:
		var celda: Vector3i = c
		var id := vertice_celda[_indice_celda(celda.x, celda.y, celda.z)]
		if id < 0:
			return
		ids.append(id)
	indices.append_array([ids[0], ids[1], ids[2], ids[0], ids[2], ids[3]])
